#!/usr/bin/env python3
"""sales_followup.py — post-demo automation for the sales team.

After a sales demo ends (any rep: Levi, Santino, future hires), this sends
the prospect a recap email from THE REP WHO RAN THE CALL, with links to a
full audit (the real R2-hosted report, not the funnel screenshot) and the
fixed-wording proposal. Spec settled with Santino + Levi 2026-09-06.

Every gate fails CLOSED — a missed send costs a manual email; a wrong send
tells a paying customer our system doesn't know who they are.

Gate ladder (all must pass):
  1. Meeting title contains "Rank #1 On Google And Chat GPT" (normalized,
     so "ChatGPT" vs "Chat GPT" both match).
  2. Title containing "Follow Up" → recap email only, never audit/proposal.
  3. Host (Fathom recorded_by) must be a known rep in REPS — unknown host
     means we can't sign the email honestly, so we alert instead of send.
  4. External invitee must resolve to a GHL contact carrying one of the
     demo-booked tags ("rank ai demo booked", "(optdig)", "(onyx)").
  5. Secured-client exclusion: explicit tag set (NOT substring — the
     location has both "client secured" and "client not yet secured") PLUS
     ground truth: email/phone matching an active company's contacts.
  6. Transcript discernment: Claude reads the call; if the prospect signed
     up / paid / created their account mid-call, or anything else says a
     proposal would land wrong, nothing sends and the rep gets the reason.
  7. Dedupe: "full audit sent" / "proposal sent" contact tags suppress a
     second audit/proposal forever; per-recording state suppresses reruns.

Approval mode (default): the finished package emails to the rep for a
one-click forward instead of the prospect. SALES_FOLLOWUP_AUTOSEND=1 flips
to direct sending once the drafts have earned trust.

State: ops_kv "sales-followup-state" (fathom_sync pattern: baseline on
first run, per-recording status, commit state after every meeting).

Usage:
  python3 scripts/sales_followup.py sync            # dry run
  python3 scripts/sales_followup.py sync --send
  python3 scripts/sales_followup.py sync --send --backfill 5
  python3 scripts/sales_followup.py one --recording 123456 [--send]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html as _html
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client_concierge import (  # noqa: E402
    fetch_companies, kv_get, kv_set, load_env,
)
import lead_audit as la  # noqa: E402  _ghl, run_audit, send_email, r2_put
import requests  # noqa: E402
from fathom_sync import FATHOM_API, meeting_when  # noqa: E402

STATE_KEY = "sales-followup-state"
NOTIFY = la.NOTIFY_EMAIL


def _fathom_keys() -> list[str]:
    """Santino's key + each rep's own (Levi records demos under HIS Fathom
    account, invisible to other keys). FATHOM_SALES_API_KEYS: comma-separated."""
    keys = [os.environ.get("FATHOM_API_KEY", "")]
    keys += (os.environ.get("FATHOM_SALES_API_KEYS") or "").split(",")
    return [k.strip() for k in keys if k.strip()]


def all_meetings(limit: int = 25) -> list[dict]:
    """Recent meetings across every configured Fathom account, newest first,
    each tagged with the key that can fetch its transcript."""
    out = []
    for key in _fathom_keys():
        try:
            r = requests.get(f"{FATHOM_API}/meetings",
                             params={"include_summary": "true", "limit": limit},
                             headers={"X-Api-Key": key}, timeout=60)
            r.raise_for_status()
            for m in r.json().get("items", []):
                m["_api_key"] = key
                out.append(m)
        except Exception as e:  # noqa: BLE001  one dead key != no sales flow
            print(f"    ! fathom key …{key[-4:]} failed: {str(e)[:100]}",
                  file=sys.stderr)
    out.sort(key=lambda m: m.get("recording_start_time") or "", reverse=True)
    return out


def transcript_tail(m: dict, chars: int = 24000) -> str:
    rid = m.get("recording_id")
    r = requests.get(f"{FATHOM_API}/recordings/{rid}/transcript",
                     headers={"X-Api-Key": m["_api_key"]}, timeout=60)
    r.raise_for_status()
    lines = [f"{((s.get('speaker') or {}).get('display_name')) or '?'}: "
             f"{s.get('text') or ''}"
             for s in r.json().get("transcript") or []]
    return "\n".join(lines)[-chars:]

# The demo calendar's title phrase. Normalization strips spaces/punctuation
# so "Chat GPT" / "ChatGPT" / stray hyphens all match.
TITLE_TOKEN = "rank#1ongoogleandchatgpt"
FOLLOWUP_TOKEN = "followup"

# Rep roster: Fathom recorded_by email -> sending identity. Santino's Fathom
# records under the ignite Gmail; sends still go out from the company address.
REPS = {
    "levi@restorationai.io": {"name": "Levi", "email": "levi@restorationai.io"},
    "ignitesystems3@gmail.com": {"name": "Santino",
                                 "email": "contact@restorationai.io"},
    "contact@restorationai.io": {"name": "Santino",
                                 "email": "contact@restorationai.io"},
}
INTERNAL_DOMAINS = {"restorationai.io"}

DEMO_TAG_PREFIX = "rank ai demo booked"   # matches all 3 source variants
AUDIT_TAG = "full audit sent"             # distinct from funnel "audit sent"
PROPOSAL_TAG = "proposal sent"
SUMMARY_TAG = "demo summary sent"

# Exact-match exclusion set. NEVER substring: "client not yet secured" and
# "client follow up" live in the same tag list and must NOT exclude.
SECURED_EXACT = {
    "client", "client secured", "secured", "customer", "existing client",
    "paid", "rank-ai-client", "rank-ai-paid", "trial", "onboard",
    "onboarding", "client - pro plan", "onboarding form completed",
    "onboarding-form-submitted", "onboarding-call-booked",
    "onboarding-call-complete", "onboarding-complete",
    "needs to fill out onboarding form",
}
SECURED_PREFIXES = ("restoration ai client",)

DISCERN_SYSTEM = """\
You are the send/no-send gate for Rank AI's post-demo automation. You read a
sales-call transcript and decide whether an automated recap email with a full
audit link and a proposal should go to the prospect.

DEFAULT TO NOT SENDING the audit/proposal. Only approve when this was clearly
a first sales demo with a prospect who has NOT yet signed up, and nothing in
the call makes an automated proposal inappropriate.

Set send_audit_proposal to false when ANY of these hold:
- The prospect signed up, paid, gave card details, or created/started their
  Rank AI account during the call (they are a customer now, not a prospect).
- The call was actually onboarding, support, or an internal conversation.
- The prospect firmly declined, was hostile, or the call ended badly.
- The rep explicitly said they would NOT send a proposal, or promised a
  different next step that a proposal would contradict.
- You cannot confidently identify who the prospect is or what their
  business is.
- Anything else that makes you hesitate. Hesitation means no.

send_summary may stay true even when the proposal is suppressed (a polite
recap is almost always safe), but set it false too if the call was not a
sales conversation with this prospect at all.

Also extract, from the transcript only (null when not stated):
- quoted_price_monthly: the monthly price the rep quoted, digits only.
- business_name, website, city: the prospect's company details.
- prospect_first_name: the name the prospect goes by on the call.

Return JSON only:
{"send_summary": bool, "send_audit_proposal": bool, "reason": str,
 "signed_up_on_call": bool, "quoted_price_monthly": int|null,
 "business_name": str|null, "website": str|null, "city": str|null,
 "prospect_first_name": str|null}"""

DISCERN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "send_summary": {"type": "boolean"},
        "send_audit_proposal": {"type": "boolean"},
        "reason": {"type": "string"},
        "signed_up_on_call": {"type": "boolean"},
        "quoted_price_monthly": {"anyOf": [{"type": "integer"},
                                           {"type": "null"}]},
        "business_name": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "website": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "city": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "prospect_first_name": {"anyOf": [{"type": "string"},
                                          {"type": "null"}]},
    },
    "required": ["send_summary", "send_audit_proposal", "reason",
                 "signed_up_on_call"],
}

SUMMARY_SYSTEM = """\
You write the post-demo recap email a Rank AI sales rep sends a prospect
right after their demo call. You get the transcript, the rep's first name,
the prospect's first name, and the links to include.

Rules:
- Write as the rep, first person, warm and direct. Sign with the rep's first
  name only.
- Open by thanking them for the time today, then recap the 2-4 things that
  actually mattered on THIS call: their situation, what we showed them, and
  anything specific they reacted to. Concrete beats generic.
- If an audit link is provided: one short paragraph introducing their full
  audit (deeper than anything shown on the call) with the link.
- If a proposal link is provided: one short paragraph introducing the
  proposal with the link, and note the price only if a price was discussed.
- Close with the clear next step from the call (or invite a reply).
- NEVER use em dashes. Use periods, commas, or colons instead.
- Keep it under 220 words of body text. Plain inline-styled HTML, single
  font, no images, no buttons: this should read like a personal email.
- Address the prospect by the name they used on the call.

Return JSON only: {"subject": str, "html": str}"""

SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"subject": {"type": "string"}, "html": {"type": "string"}},
    "required": ["subject", "html"],
}


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9#]", "", (t or "").lower())


def title_is_demo(title: str) -> bool:
    return TITLE_TOKEN in _norm(title)


def title_is_followup(title: str) -> bool:
    return FOLLOWUP_TOKEN in _norm(title)


def rep_for(m: dict) -> dict | None:
    email = ((m.get("recorded_by") or {}).get("email") or "").lower().strip()
    return REPS.get(email)


def prospect_invitee(m: dict) -> dict | None:
    """First external invitee with an email that isn't one of ours."""
    for inv in (m.get("calendar_invitees") or []):
        email = (inv.get("email") or "").lower().strip()
        if not email or email in REPS:
            continue
        if email.split("@")[-1] in INTERNAL_DOMAINS:
            continue
        if inv.get("is_external") is False:
            continue
        return {"email": email, "name": (inv.get("name") or "").strip()}
    return None


def ghl_contact_by_email(email: str) -> dict | None:
    res = la._ghl("GET", "/contacts/", params={"query": email})
    for c in (res.get("contacts") or []):
        if (c.get("email") or "").lower().strip() == email:
            return c
    return None


_TITLE_PHRASE_RE = re.compile(
    r"rank\s*#?\s*1\s*on\s*google\s*and\s*chat\s*gpt", re.I)


def name_from_title(title: str) -> str | None:
    """'Rank #1 On Google And Chat GPT - Bryan Almeida' -> 'Bryan Almeida'.
    GHL-booked Zoom demos often have NO prospect on the calendar invite
    (kickoff_prep learned this first), but the appointment title carries
    the contact's name."""
    t = _TITLE_PHRASE_RE.sub(" ", title or "")
    t = re.sub(r"follow[\s-]*up", " ", t, flags=re.I)
    t = re.sub(r"[-–—|:·(),]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    words = [w for w in t.split(" ") if re.fullmatch(r"[A-Za-z'.]+", w)]
    if len(words) < 2 or len(words) > 4:
        return None
    return " ".join(words)


def ghl_contact_by_name(name: str) -> dict | None:
    """Exactly one demo-tagged contact matching this full name, else None.
    Ambiguity fails closed like everything here."""
    res = la._ghl("GET", "/contacts/", params={"query": name})
    hits = []
    want = name.lower().strip()
    for c in (res.get("contacts") or []):
        full = (c.get("contactName")
                or f"{c.get('firstName', '')} {c.get('lastName', '')}").strip()
        if full.lower() != want:
            continue
        tags = [(t or "").lower().strip() for t in (c.get("tags") or [])]
        if any(t.startswith(DEMO_TAG_PREFIX) for t in tags):
            hits.append(c)
    return hits[0] if len(hits) == 1 else None


def is_secured_by_tags(tags: list[str]) -> str | None:
    for t in tags:
        tl = (t or "").lower().strip()
        if "not yet" in tl:
            continue
        if tl in SECURED_EXACT:
            return tl
        if any(tl.startswith(p) for p in SECURED_PREFIXES):
            return tl
    return None


def _digits(p: str) -> str:
    return re.sub(r"\D", "", p or "")[-10:]


def client_identity_sets() -> tuple[set, set]:
    """Emails + last-10-digit phones of every ACTIVE company's contacts.
    Ground truth for 'already a client', independent of GHL tag hygiene."""
    emails, phones = set(), set()
    inactive = {"paused", "suspended", "cancelled", "canceled", "churned",
                "inactive", "archived"}
    for co in fetch_companies().values():
        if str(co.get("status") or "").lower() in inactive:
            continue
        for c in ((co.get("integration_settings") or {}).get("contacts")) or []:
            if c.get("email"):
                emails.add(c["email"].lower().strip())
            if c.get("phone"):
                phones.add(_digits(c["phone"]))
    phones.discard("")
    return emails, phones


# ---------------------------------------------------------------------------
# Proposal: fixed wording (Levi 2026-09-05: same template every time, all ten
# deliverables, only the personalization slots change). Based on
# sales/proposals/*.html. No em dashes anywhere (outbound-writing law).
# ---------------------------------------------------------------------------

PROPOSAL_DELIVERABLES = [
    ("Brand-new, conversion-built website",
     "a modern site with the correct architecture, covering every service "
     "across your service area, with clickable phone numbers and lead capture "
     "built in. Included at no extra cost."),
    ("AI Search Optimization",
     "JSON-LD schema and structure engineered to get {biz} read and cited by "
     "name in ChatGPT, Gemini, and Google AI for local restoration searches."),
    ("Local SEO and business listings",
     "consistent name, address, and phone across the directories Google and "
     "AI engines trust."),
    ("Complete Google Business Profile management",
     "full optimization and consistent posting to own the Google Maps 3-pack "
     "where nearby customers search."),
    ("Review reactivation and automated review engine",
     "reach past customers to build Google review volume fast, then keep new "
     "reviews coming automatically after every job."),
    ("Ongoing content engine",
     "targeted blogs, FAQs, and videos that build the topical authority "
     "Google and AI reward."),
    ("Google LSA management",
     "your Local Service Ads run directly at true cost. Real jobs, not "
     "resold leads."),
    ("Google PPC management",
     "paid search that brings leads now, while rankings compound."),
    ("24/7 AI receptionist and call tracking",
     "every lead answered, booked, and attributed, day or night."),
    ("Live analytics dashboard",
     "real-time geo-grid map rankings and AI-visibility tracking, so you see "
     "exactly where you stand."),
]

PROPOSAL_CSS = """
  *{box-sizing:border-box}html,body{margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,
  sans-serif;color:#1a1a1a;background:#f1f5f9;line-height:1.55;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}
  .sheet{max-width:8.5in;margin:24px auto;background:#fff;padding:54px 60px;
  box-shadow:0 8px 30px rgba(0,0,0,.1)}
  .brand{font-size:18px;font-weight:800;margin-bottom:2px}
  .brand span{color:#7c3aed}
  .for{font-size:13px;color:#666;margin-bottom:34px}
  h1{font-size:23px;line-height:1.25;margin:0 0 14px}
  p{font-size:14px;margin:0 0 14px}.lede{color:#444}
  h2{font-size:12px;text-transform:uppercase;letter-spacing:.09em;
  color:#7c3aed;margin:26px 0 10px;font-weight:700}
  ul{margin:0;padding:0;list-style:none}
  li{font-size:14px;padding:6px 0 6px 22px;position:relative}
  li::before{content:"\\2022";position:absolute;left:4px;color:#7c3aed;
  font-weight:700}
  li b{font-weight:600}
  .price{margin:28px 0 8px;padding:18px 0;border-top:2px solid #1a1a1a;
  border-bottom:2px solid #1a1a1a;display:flex;align-items:baseline;
  justify-content:space-between}
  .price .amt{font-size:30px;font-weight:800}
  .price .amt small{font-size:14px;font-weight:600;color:#666}
  .price .terms{font-size:13px;color:#666}
  .next{margin-top:24px;font-size:14px}.next b{font-weight:700}
  .foot{margin-top:40px;padding-top:14px;border-top:1px solid #ddd;
  font-size:12px;color:#888;display:flex;justify-content:space-between}
  @media print{body{background:#fff}
  .sheet{box-shadow:none;margin:0;max-width:none;padding:.55in .7in}
  @page{margin:0;size:letter}}
"""


def proposal_html(biz: str, *, domain: str | None, city: str | None,
                  price: int) -> str:
    e = lambda s: _html.escape(s or "", quote=False)  # noqa: E731
    month = _dt.date.today().strftime("%B %Y")
    where = f"{e(city)} homeowner" if city else "homeowner"
    sub = " · ".join(x for x in (e(biz), e(domain or ""), month) if x)
    items = "\n".join(
        f"    <li><b>{e(t)}</b>: {e(d.format(biz=biz))}</li>"
        for t, d in PROPOSAL_DELIVERABLES)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Rank AI Proposal: {e(biz)}</title>
<style>{PROPOSAL_CSS}</style></head>
<body><div class="sheet">
  <div class="brand">Rank <span>AI</span></div>
  <div class="for">Proposal for {sub}</div>
  <h1>Get found first, in Google and in AI search.</h1>
  <p class="lede">When a {where} has water, fire, or mold damage, they ask
  Google and ChatGPT "who's the best company near me?" and the AI names one
  company. Our job is to make that company {e(biz)}, own the Google Maps
  results across your service area, and feed you a steady stream of jobs.</p>
  <h2>What's included: ${price}/month, all of it</h2>
  <ul>
{items}
  </ul>
  <div class="price">
    <div class="amt">${price} <small>/ month</small></div>
    <div class="terms">No long-term contract. No setup fee. Cancel anytime.</div>
  </div>
  <p class="next"><b>Next step:</b> Reply "yes" and I'll send the onboarding
  link. We can start within 48 hours.</p>
  <div class="foot"><div>Rank AI, restorationai.io</div>
  <div>contact@restorationai.io</div></div>
</div></body></html>
"""


def publish_proposal(rid: str, htmlsrc: str) -> str:
    key = f"sales-proposals/{rid}/proposal.html"
    la.r2_put(la.BUCKET, key, htmlsrc.encode(), "text/html; charset=utf-8")
    return f"{la.PUBLIC_BASE}/{key}"


# ---------------------------------------------------------------------------
# Send paths
# ---------------------------------------------------------------------------

def send_as_rep(contact_id: str, rep: dict, subject: str, body_html: str) -> bool:
    payload = {"type": "Email", "contactId": contact_id, "subject": subject,
               "html": body_html, "emailFrom": rep["email"]}
    try:
        r = la._ghl("POST", "/conversations/messages", params={}, body=payload)
    except Exception as e:  # noqa: BLE001  emailFrom unsupported? plain send
        print(f"    emailFrom send failed ({str(e)[:100]}) — retrying plain",
              file=sys.stderr)
        payload.pop("emailFrom", None)
        r = la._ghl("POST", "/conversations/messages", params={}, body=payload)
    return bool(r.get("messageId") or r.get("emailMessageId") or r.get("msg"))


def add_tags(contact: dict, new: list[str]) -> None:
    have = {t.lower() for t in (contact.get("tags") or [])}
    add = [t for t in new if t.lower() not in have]
    if add:
        la._ghl("PUT", f"/contacts/{contact['id']}", params={},
                body={"tags": (contact.get("tags") or []) + add})


_DRY = True  # set per-run in process_meeting; guards every outbound email


def notify_rep(rep: dict | None, subject: str, body_html: str) -> None:
    if _DRY:
        print(f"    [dry-run] would notify rep: {subject}")
        return
    to = {NOTIFY}
    if rep:
        to.add(rep["email"])
    for addr in sorted(to):
        la.send_email(addr, subject, body_html)


# ---------------------------------------------------------------------------
# Per-meeting processing
# ---------------------------------------------------------------------------

def process_meeting(m: dict, *, dry_run: bool,
                    client_ids: tuple[set, set]) -> str:
    """Returns the state to record for this recording."""
    global _DRY
    _DRY = dry_run
    rid = str(m.get("recording_id"))
    title = m.get("title") or m.get("meeting_title") or ""
    when = meeting_when(m)

    if not title_is_demo(title):
        return "not-demo"

    followup = title_is_followup(title)
    print(f"    demo call{' (follow up)' if followup else ''}: {title!r}")

    summary_md = ((m.get("default_summary") or {})
                  .get("markdown_formatted") or "")
    if not summary_md:
        print("    no summary/transcript yet — leaving for next run")
        return "defer"

    rep = rep_for(m)
    if not rep:
        host = (m.get("recorded_by") or {}).get("email", "?")
        notify_rep(None, f"[sales-followup] unknown rep on demo {rid}",
                   f"<p>Demo call {_html.escape(title)} on {when} was "
                   f"recorded by <b>{_html.escape(host)}</b>, who is not in "
                   "the rep map (scripts/sales_followup.py REPS). Nothing "
                   "was sent. Add them to send automatically next time.</p>")
        return "unknown-host"

    # Resolve the prospect: calendar invitee email first, then the name in
    # the appointment title (GHL-booked Zooms often carry no invitee email).
    contact = None
    inv = prospect_invitee(m)
    if inv:
        contact = ghl_contact_by_email(inv["email"])
    if not contact:
        tname = name_from_title(title)
        if tname:
            contact = ghl_contact_by_name(tname)
            if contact:
                inv = {"email": (contact.get("email") or "").lower().strip(),
                       "name": tname}
    if not contact or not inv or not inv["email"]:
        notify_rep(rep, f"[sales-followup] prospect unresolved on demo {rid}",
                   f"<p>Demo {_html.escape(title)} on {when}: could not match "
                   "the prospect to a GoHighLevel contact (no external invitee "
                   "email, and the title name matched no single demo-tagged "
                   "contact). Nothing sent.</p>")
        return "no-prospect"

    tags = [(t or "").lower().strip() for t in (contact.get("tags") or [])]
    if not any(t.startswith(DEMO_TAG_PREFIX) for t in tags):
        print(f"    contact {inv['email']} lacks a demo-booked tag — skipping")
        return "no-demo-tag"

    secured = is_secured_by_tags(contact.get("tags") or [])
    emails, phones = client_ids
    if inv["email"] in emails or _digits(contact.get("phone") or "") in phones:
        secured = secured or "active company contact"
    if secured:
        print(f"    already a client ({secured}) — nothing sends, ever")
        return f"secured:{secured}"

    # Transcript discernment — ANY failure here means nothing sends.
    try:
        tail = transcript_tail(m, chars=24000)
        client = la._claude()
        verdict, _ = la.claude_json(
            client, DISCERN_SYSTEM,
            f"Meeting title: {title}\nDate: {when}\n"
            f"Rep on the call: {rep['name']}\n"
            f"Prospect (calendar): {inv['name']} <{inv['email']}>\n\n"
            f"Transcript (tail):\n{tail}",
            schema=DISCERN_SCHEMA)
    except Exception as e:  # noqa: BLE001
        notify_rep(rep, f"[sales-followup] discernment failed for {rid}",
                   f"<p>Could not analyze the transcript for demo "
                   f"{_html.escape(title)} ({when}): {_html.escape(str(e)[:200])}."
                   " Nothing was sent. Handle this one manually.</p>")
        return "discern-error"

    reason = (verdict.get("reason") or "").strip()
    send_ap = bool(verdict.get("send_audit_proposal")) and not followup
    send_sum = bool(verdict.get("send_summary"))
    already_audited = AUDIT_TAG in tags or PROPOSAL_TAG in tags
    if already_audited:
        send_ap = False
    print(f"    discernment: summary={send_sum} audit/proposal={send_ap} "
          f"({reason[:120]})")

    if not send_sum and not send_ap:
        notify_rep(rep, f"[sales-followup] held: {inv['name'] or inv['email']}",
                   f"<p>Demo {_html.escape(title)} ({when}) was held, nothing "
                   f"sent. Reason: {_html.escape(reason)}</p>")
        return f"held:{reason[:80]}"

    first = (verdict.get("prospect_first_name")
             or contact.get("firstName") or inv["name"].split(" ")[0] or "")
    biz = (verdict.get("business_name")
           or contact.get("companyName") or "").strip()
    website = (verdict.get("website") or contact.get("website") or "").strip()
    city = (verdict.get("city") or contact.get("city") or "").strip()
    price = verdict.get("quoted_price_monthly") or 997
    if not isinstance(price, int) or not 100 <= price <= 20000:
        price = 997

    audit_url = proposal_url = None
    if send_ap:
        if not biz:
            send_ap = False
            reason += " | no business name identified, proposal suppressed"
        elif dry_run:
            audit_url = "(dry-run: audit skipped)"
            proposal_url = "(dry-run: proposal not uploaded)"
        else:
            try:
                print(f"    running full audit for {website or biz} …")
                res = la.run_audit(
                    website, first or inv["name"], inv["email"],
                    contact.get("phone") or "", email_mode="none",
                    business_name=biz, ghl_contact_id=contact["id"]) or {}
                audit_url = res.get("report_url")
            except Exception as e:  # noqa: BLE001
                print(f"    audit failed: {str(e)[:150]}", file=sys.stderr)
            phtml = proposal_html(biz, domain=la._norm_domain(website) or None,
                                  city=city or None, price=price)
            proposal_url = publish_proposal(rid, phtml)

    links = []
    if audit_url:
        links.append(f"Full audit: {audit_url}")
    if proposal_url and send_ap:
        links.append(f"Proposal: {proposal_url}")
    try:
        copy, _ = la.claude_json(
            la._claude(), SUMMARY_SYSTEM,
            f"Rep first name: {rep['name']}\n"
            f"Prospect first name: {first or '(unknown, use no name)'}\n"
            f"Business: {biz or '(unknown)'}\n"
            f"Links to include:\n" + ("\n".join(links) or "(none)") + "\n"
            + (f"Price discussed: ${price}/month\n" if send_ap else "")
            + f"\nTranscript (tail):\n{tail[-16000:]}",
            schema=SUMMARY_SCHEMA)
    except Exception as e:  # noqa: BLE001
        notify_rep(rep, f"[sales-followup] compose failed for {rid}",
                   f"<p>Drafting the recap for {_html.escape(title)} failed: "
                   f"{_html.escape(str(e)[:200])}. Nothing sent.</p>")
        return "compose-error"

    if "—" in copy.get("html", "") + copy.get("subject", ""):
        copy["html"] = copy["html"].replace("—", ", ")
        copy["subject"] = copy["subject"].replace("—", ", ")

    autosend = os.environ.get("SALES_FOLLOWUP_AUTOSEND") == "1"
    if dry_run:
        print(f"    [dry-run] would {'send' if autosend else 'draft for approval'}:"
              f" subj={copy['subject']!r} audit={audit_url} proposal={proposal_url}")
        return "dry-run"

    if not autosend:
        notify_rep(rep,
                   f"[sales-followup] READY for {first or inv['email']}"
                   f" ({biz or 'unknown biz'})",
                   "<p><b>Approval mode.</b> Forward this to the prospect or "
                   "copy what you want. Nothing was sent to them, and no tags "
                   "were added. After you send it, add the tags "
                   "<b>Full Audit Sent</b> and <b>Proposal Sent</b> on the "
                   "contact so a future follow-up call never re-sends.</p>"
                   f"<p><b>To:</b> {_html.escape(inv['email'])}<br>"
                   f"<b>Subject:</b> {_html.escape(copy['subject'])}<br>"
                   f"<b>Audit:</b> {audit_url or 'n/a'}<br>"
                   f"<b>Proposal:</b> {proposal_url or 'n/a'}<br>"
                   f"<b>Discernment:</b> {_html.escape(reason)}</p><hr>"
                   + copy["html"])
        return "approval-sent"

    ok = send_as_rep(contact["id"], rep, copy["subject"], copy["html"])
    if not ok:
        notify_rep(rep, f"[sales-followup] send FAILED for {inv['email']}",
                   "<p>GHL email send did not confirm. Check the conversation "
                   "and send manually if needed.</p>" + copy["html"])
        return "send-failed"

    stamp = ["Demo Summary Sent"]
    if send_ap:
        stamp += ["Full Audit Sent", "Proposal Sent"]
    try:
        add_tags(contact, stamp)
    except Exception as e:  # noqa: BLE001
        print(f"    tagging failed: {str(e)[:120]}", file=sys.stderr)
    notify_rep(rep, f"[sales-followup] sent to {first or inv['email']}"
                    f" ({biz or 'unknown biz'})",
               f"<p>Recap {'with audit + proposal ' if send_ap else ''}sent "
               f"from {rep['name']}.<br>Audit: {audit_url or 'n/a'}<br>"
               f"Proposal: {proposal_url or 'n/a'}</p>")
    return "sent" + ("+audit+proposal" if send_ap else "")


# ---------------------------------------------------------------------------

def main() -> int:
    load_env()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("sync")
    sp.add_argument("--send", action="store_true")
    sp.add_argument("--backfill", type=int, default=0,
                    help="on first run, process the N most recent meetings "
                         "instead of baselining them")
    so = sub.add_parser("one")
    so.add_argument("--recording", required=True)
    so.add_argument("--send", action="store_true")
    args = ap.parse_args()
    dry_run = not args.send

    state = kv_get(STATE_KEY) or {}
    state.setdefault("processed", {})
    meetings = all_meetings()
    client_ids = client_identity_sets()

    if args.cmd == "one":
        targets = [m for m in meetings
                   if str(m.get("recording_id")) == str(args.recording)]
        if not targets:
            print(f"recording {args.recording} not in the recent window")
            return 1
    else:
        first_run = state.get("initialized_at") is None
        if first_run:
            state["initialized_at"] = _dt.datetime.now(
                _dt.timezone.utc).isoformat()
            if not args.backfill:
                for m in meetings:
                    state["processed"][str(m.get("recording_id"))] = "baseline"
                print(f"first run: baselined {len(meetings)} meeting(s) — only"
                      " new demos will be processed (--backfill N to mine now)")
                if not dry_run:
                    kv_set(STATE_KEY, state)
                return 0
            meetings = meetings[:args.backfill]
        targets = [m for m in meetings
                   if str(m.get("recording_id")) not in state["processed"]]

    print(f"sales followup: {len(targets)} meeting(s) to check"
          + (" [DRY RUN]" if dry_run else ""))
    for m in reversed(targets):
        rid = str(m.get("recording_id"))
        title = m.get("title") or m.get("meeting_title") or "?"
        print(f"\n--- {meeting_when(m)} {title!r} (recording {rid})")
        # CLAIM before processing (2026-09-06): the Fathom webhook dispatch
        # and the Railway 30-min poll can run concurrently, and an audit
        # takes minutes — plenty of window for a double-send. A fresh state
        # read + an immediate "processing:" stamp shrinks that window to
        # seconds. Stale claims (>2h, crashed run) are reprocessable.
        if not dry_run:
            fresh = ((kv_get(STATE_KEY) or {}).get("processed") or {})
            cur = fresh.get(rid)
            if cur and not (isinstance(cur, str) and cur.startswith("processing:")
                            and cur[11:] < (_dt.datetime.now(_dt.timezone.utc)
                                            - _dt.timedelta(hours=2)).isoformat()):
                if cur != state["processed"].get(rid):
                    print("    claimed by a concurrent run — skipping")
                    state["processed"][rid] = cur
                    continue
            state["processed"][rid] = ("processing:"
                                       + _dt.datetime.now(_dt.timezone.utc).isoformat())
            kv_set(STATE_KEY, state)
        try:
            status = process_meeting(m, dry_run=dry_run, client_ids=client_ids)
        except Exception as e:  # noqa: BLE001  one bad meeting != whole run
            print(f"    ! error: {str(e)[:200]}", file=sys.stderr)
            status = "error"
        print(f"    -> {status}")
        if status == "defer":
            # summary not ready; release the claim so the next pass retries
            if not dry_run and str(state["processed"].get(rid, "")
                                   ).startswith("processing:"):
                state["processed"].pop(rid, None)
                kv_set(STATE_KEY, state)
            continue
        if args.cmd == "one" and dry_run:
            continue  # dry single-shot leaves state untouched for a real run
        state["processed"][rid] = status
        if not dry_run:
            kv_set(STATE_KEY, state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
