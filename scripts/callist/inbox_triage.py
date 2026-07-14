#!/usr/bin/env python3
"""
Restoration AI — Inbox Triage (the "left on read" catcher).

Scans recent conversations for leads who sent us an inbound message (email/SMS) we
HAVEN'T answered, and drafts a reply for each. Writes inbox_needs_response.json, which
the daily page renders as a "📬 Needs a Response" section at the very top. Draft-only —
you approve/edit, then it sends (see apply step). Idempotent-ish via message dates.

Flags: --dry-run   --hours N (lookback, default 168 = 7 days)
"""
import os, sys, re, json, argparse
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_router as R
from _http import HTTP

BASE_DIR = os.environ.get("RAI_BASE") or os.path.expanduser("~/restoration-ai")
LOG_FILE = os.path.join(BASE_DIR, "inbox_triage.log")
OUT_FILE = os.path.join(BASE_DIR, "inbox_needs_response.json")
GHL_BASE = R.GHL_BASE; GHL_H = R.GHL_HEADERS; LOC = R.GHL_LOCATION_ID

def log(m):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); line = f"[{ts}] {m}"; print(line)
    with open(LOG_FILE, "a") as f: f.write(line + "\n")

def strip(t): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t or "")).strip()
def rtype(m): return str(m.get("messageType", "")).replace("TYPE_", "")

def email_body(m):
    """GHL stores email bodies separately — fetch the real reply text for an email message."""
    ids = (m.get("meta", {}).get("email", {}) or {}).get("messageIds") or []
    if not ids: return ""
    r = HTTP.get(f"{GHL_BASE}/conversations/messages/email/{ids[0]}", headers=GHL_H)
    if r.status_code != 200: return ""
    body = strip((r.json().get("emailMessage", {}) or {}).get("body", ""))
    return re.split(r"From:\s*\S+@|On .{0,40} wrote:", body)[0].strip()  # drop quoted original

def msg_text(m):
    return (email_body(m) if rtype(m) == "EMAIL" else strip(m.get("body"))) or ""

def no_emdash(t):
    """House style: never use em/en dashes in outbound copy — commas instead."""
    t = (t or "").replace(" — ", ", ").replace("—", ", ").replace(" – ", ", ").replace("–", ", ")
    t = re.sub(r"\s*,\s*,", ", ", t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()

def recent_conversations(hours):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out, start = [], None
    for _ in range(30):
        p = {"locationId": LOC, "limit": 100, "sortBy": "last_message_date", "sort": "desc"}
        if start: p["startAfterDate"] = start
        r = HTTP.get(f"{GHL_BASE}/conversations/search", headers=GHL_H, params=p)
        if r.status_code != 200: break
        batch = r.json().get("conversations", [])
        if not batch: break
        out += batch
        lm = batch[-1].get("lastMessageDate") or batch[-1].get("dateUpdated")
        try:
            if datetime.fromtimestamp(int(str(lm)[:13]) / 1000, tz=timezone.utc) < cutoff: break
        except Exception: pass
        start = lm
        if len(batch) < 100: break
    return out

def get_messages(conv_id):
    out, cursor = [], None
    while True:
        p = {"limit": 100}
        if cursor: p["lastMessageId"] = cursor
        r = HTTP.get(f"{GHL_BASE}/conversations/{conv_id}/messages", headers=GHL_H, params=p)
        if r.status_code != 200: break
        block = r.json().get("messages", {}); msgs = block.get("messages", [])
        out += msgs
        if block.get("nextPage") and msgs: cursor = msgs[-1].get("id")
        else: break
    return sorted(out, key=lambda m: m.get("dateAdded", ""))

def unanswered(messages):
    """Return the inbound message that still needs a reply, else None."""
    last_inbound = None
    for m in messages:
        if m.get("direction") == "inbound" and rtype(m) in ("SMS", "EMAIL"):
            last_inbound = m
    if not last_inbound:
        return None
    li = last_inbound.get("dateAdded", "")
    after = [m for m in messages if m.get("direction") == "outbound" and m.get("dateAdded", "") > li]
    manual_after = any(m.get("source") == "app" and m.get("userId") and rtype(m) in ("SMS", "EMAIL", "CALL")
                       for m in after)
    if rtype(last_inbound) == "EMAIL":
        # an email reply is only "answered" by an email back
        if not any(rtype(m) == "EMAIL" for m in after):
            return last_inbound
        return None
    return last_inbound if not manual_after else None

def thread_text(messages):
    out = []
    for m in messages[-12:]:
        if rtype(m) not in ("SMS", "EMAIL", "SMS_REACTION"): continue
        who = "LEAD" if m.get("direction") == "inbound" else "US"
        sub = (m.get("meta", {}).get("email", {}) or {}).get("subject", "")
        body = strip(m.get("body")) or (f"[email: {sub}]" if sub else "")
        if body: out.append(f"{who}: {body[:400]}")
    return "\n".join(out)

# Cheap pre-filter: contacts that are really vendors/system senders, not leads.
VENDOR_BLOCK = ("supabase", "google", "highlevel", "gohighlevel", "godaddy", "github", "notion",
                "stripe", "workspace team", "no-reply", "noreply", "restoration ai", "mailer",
                "cloudflare", "openai", "sendgrid", "twilio", "zoom", "calendly", "fathom", "railway")

TRIAGE_SYS = (
 "You triage a LEAD's inbound message for Rank AI (a 24/7 AI receptionist + Google-ranking system "
 "for water-damage restoration companies). Decide if it needs a HUMAN response. Set "
 "needs_response=false if it is: a system/automated/vendor notification (security alert, verification "
 "code, GitHub/PR, billing, legal/ToS, our own outbound emails), a wrong number, or just a "
 "pleasantry/acknowledgment ('thanks', 'ok', an emoji) that needs no reply. If it IS a real "
 "lead/customer who genuinely needs a reply, set needs_response=true and draft a short, warm reply "
 "in Santino's voice nudging toward a free 15-min demo (email = 2-4 sentences + subject reusing "
 "'Re:'; SMS = 1-2 casual sentences, no subject). NEVER use em dashes or en dashes in the body; "
 "use commas or periods instead. Reply ONLY JSON: "
 '{"needs_response":true|false,"reason":"short","subject":"... or null","body":"..."}')

def send_message(contact_id, channel, subject, body):
    """Send an SMS or Email to a contact via GHL (into the conversation thread)."""
    body = no_emdash(body)
    if str(channel).upper() == "EMAIL":
        payload = {"type": "Email", "contactId": contact_id,
                   "subject": no_emdash(subject or "Following up"),
                   "html": body.replace("\n", "<br>"), "message": body}
    else:
        payload = {"type": "SMS", "contactId": contact_id, "message": body}
    r = HTTP.post(f"{GHL_BASE}/conversations/messages", headers=GHL_H, json=payload)
    return r.status_code, r.text[:250]

def classify_and_draft(name, channel, thread, inbound_subject, inbound_body):
    user = (f"Lead: {name}\nChannel: {channel}\nEmail subject: {inbound_subject or '(n/a)'}\n"
            f"THEIR LATEST MESSAGE: {inbound_body or '(could not read the body)'}\n\n"
            f"Recent thread:\n{thread}")
    return R.anthropic_json(TRIAGE_SYS, user, max_tokens=1500) or {"needs_response": False}

def run(dry_run=False, hours=168):
    log(f"=== Inbox Triage ({'DRY RUN' if dry_run else 'live'}, lookback {hours}h) ===")
    convos = recent_conversations(hours)
    log(f"Scanning {len(convos)} recent conversations")
    items = []
    skipped_vendor = skipped_noreply = 0
    for cv in convos:
        cid = cv.get("contactId"); name = cv.get("fullName") or cv.get("contactName") or cid
        if not cid: continue
        if any(v in (name or "").lower() for v in VENDOR_BLOCK):
            skipped_vendor += 1; continue          # vendor / system sender, not a lead
        msgs = get_messages(cv["id"])
        inb = unanswered(msgs)
        if not inb: continue
        channel = rtype(inb)
        sub = (inb.get("meta", {}).get("email", {}) or {}).get("subject", "")
        ibody = msg_text(inb)                      # real content (fetches email body if needed)
        d = classify_and_draft(name, channel, thread_text(msgs), sub, ibody)
        if not d.get("needs_response"):            # AI says system/pleasantry/no-reply
            skipped_noreply += 1; continue
        inbound_text = ibody or (f"(email — subject: {sub})" if sub else "(no text)")
        log(f"  📬 {name} [{channel}] — needs response (since {inb.get('dateAdded','')[:16]})")
        items.append({"contact_id": cid, "conversation_id": cv["id"], "name": name,
                      "channel": channel, "inbound_date": inb.get("dateAdded", "")[:16],
                      "inbound_text": inbound_text[:400],
                      "subject": (no_emdash(d.get("subject") or "") or None),
                      "draft": no_emdash(d.get("body", ""))})
    log(f"Filtered: {skipped_vendor} vendor/system, {skipped_noreply} no-reply/pleasantry")
    items.sort(key=lambda x: x["inbound_date"], reverse=True)
    if not dry_run:
        json.dump({"generated_at": datetime.now().isoformat(), "date": str(datetime.now().date()),
                   "items": items}, open(OUT_FILE, "w"), indent=2)
    log(f"Done. {len(items)} lead(s) awaiting a response.")
    if dry_run:
        for it in items:
            print(f"\n📬 {it['name']} [{it['channel']}] (since {it['inbound_date']})")
            print(f"   they said: {it['inbound_text'][:120]}")
            print(f"   draft: {(it['subject']+' | ') if it['subject'] else ''}{it['draft'][:200]}")
    return items

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--hours", type=int, default=168)
    a = ap.parse_args()
    run(dry_run=a.dry_run, hours=a.hours)
