#!/usr/bin/env python3
"""
Automatic end-of-day note sync for the Restoration AI daily call list.

Reads TODAY's Notion call-list page, pulls the text each rep typed under
"✍️ Your notes for today:" for every contact, and POSTs real notes back to
that contact's GHL notes. Replaces the manual "sync my notes" prompt.

- Maps a note to a GHL contact via the embedded `ref:{contact_id}` line.
  Falls back to phone-number matching for pages created before refs existed.
- Skips empty notes and any "no action needed" variation.
- Never changes pipeline stages.
- Idempotent: records which contacts were synced per page so a re-run
  (or launchd re-fire) never double-posts.
"""
import os, re, json, requests
from _http import HTTP
from datetime import date, datetime

BASE_DIR  = os.path.expanduser("~/restoration-ai")
LOG_FILE  = os.path.join(BASE_DIR, "auto_sync_notes.log")
PAGE_FILE = os.path.join(BASE_DIR, "notion_page_id.txt")
SYNC_FILE = os.path.join(BASE_DIR, "synced_notes.json")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# --- Credentials (reuse the daily-call-list script's constants) ---
GHL_API_KEY     = os.environ.get("GHL_API_KEY") or "pit-c75a84bf-6d23-4a8a-a1ff-a88054b0e1bc"
GHL_LOCATION_ID = "Tx5eKisj3Xluq1SeZKe3"
GHL_BASE_URL    = "https://services.leadconnectorhq.com"
GHL_HEADERS     = {
    "Authorization": f"Bearer {GHL_API_KEY}",
    "Version":       "2021-07-28",
    "Content-Type":  "application/json",
}

def _notion_token():
    # Single source of truth: the token embedded in the daily-call-list script,
    # with a fallback to the rank-ai repo .env.
    try:
        src = open(os.path.join(BASE_DIR, "workflows", "auto_daily_call_list.py"), encoding="utf-8").read()
        m = re.search(r'NOTION_TOKEN\s*=\s*"(ntn_[A-Za-z0-9]+)"', src)
        if m:
            return m.group(1)
    except Exception:
        pass
    try:
        for line in open("/Users/santino/restoration-ai/.env", encoding="utf-8"):
            if line.strip().startswith("NOTION_TOKEN="):
                return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return ""

NOTION_TOKEN   = _notion_token()
NOTION_HEADERS = {
    "Authorization":  f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type":   "application/json",
}

# Pipeline stages, mirrored from auto_daily_call_list.py — used to build the
# phone->contact_id fallback map only when a page has no `ref:` lines.
CALL_STAGES = [
    {"pipeline_id": "hPnHBxO63YMecyG219V5", "stage_id": "9fb3928a-33e3-4592-a080-56b3f353e56b"},
    {"pipeline_id": "OP4aWjh91AfikmEYKDHk", "stage_id": "892dfc0e-cec3-4b43-8a6e-0805348ee723"},
    {"pipeline_id": "KRokx3RqJjNzUg8YCbWk", "stage_id": "ce155700-eb61-4d8b-899a-55baaa7d9a6e"},
]

NO_ACTION = {"", "noaction", "noactionneeded", "none", "na", "nothing", "nonotes",
             "noactiontoday", "nothingtoday", "skip", "noupdate", "noupdates"}

# ---------- Notion helpers ----------
def block_plain_text(b):
    t = b.get("type", "")
    node = b.get(t, {})
    rts = node.get("rich_text", []) if isinstance(node, dict) else []
    return "".join(rt.get("plain_text", "") for rt in rts)

def get_page(page_id):
    r = HTTP.get(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS)
    return r.json() if r.status_code == 200 else None

def get_all_children(page_id):
    blocks, cursor = [], None
    while True:
        url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = HTTP.get(url, headers=NOTION_HEADERS)
        if r.status_code != 200:
            break
        d = r.json()
        blocks.extend(d.get("results", []))
        if d.get("has_more"):
            cursor = d.get("next_cursor")
        else:
            break
    return blocks

def page_title(page):
    for v in (page or {}).get("properties", {}).values():
        if v.get("type") == "title":
            return "".join(x.get("plain_text", "") for x in v["title"])
    return ""

# ---------- GHL helpers ----------
def normalize_phone(s):
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits

def build_phone_map():
    pmap = {}
    for st in CALL_STAGES:
        params = {"location_id": GHL_LOCATION_ID, "pipeline_id": st["pipeline_id"],
                  "pipeline_stage_id": st["stage_id"], "status": "open", "limit": 50}
        r = HTTP.get(f"{GHL_BASE_URL}/opportunities/search", headers=GHL_HEADERS, params=params)
        for opp in r.json().get("opportunities", []):
            c = opp.get("contact", {})
            ph, cid = normalize_phone(c.get("phone") or ""), c.get("id")
            if ph and cid:
                pmap[ph] = cid
    return pmap

def post_note(contact_id, body):
    r = HTTP.post(f"{GHL_BASE_URL}/contacts/{contact_id}/notes",
                      headers=GHL_HEADERS, json={"body": body})
    return r.status_code in (200, 201)

# ---------- Parsing ----------
def extract_phone_from_header(txt):
    if "📞" not in txt:
        return ""
    after = txt.split("📞", 1)[1]
    after = after.split("·")[0]
    return normalize_phone(after)

def parse_contacts(blocks):
    """Return list of dicts: {cid, phone, note}."""
    contacts, cur = [], None
    for b in blocks:
        typ = b.get("type", "")
        txt = block_plain_text(b)
        stripped = txt.strip()

        if "📞" in txt:  # contact header → starts a new contact segment
            if cur:
                contacts.append(cur)
            cur = {"cid": None, "phone": extract_phone_from_header(txt),
                   "note_parts": [], "collecting": False}
            continue
        if cur is None:
            continue
        if stripped.startswith("ref:"):
            cur["cid"] = stripped[4:].strip()
            continue
        if typ.startswith("heading") or typ == "divider":
            contacts.append(cur); cur = None
            continue
        if "Your notes for today" in txt:
            cur["collecting"] = True
            after = txt.split("Your notes for today:", 1)[-1].strip()
            if after:
                cur["note_parts"].append(after)
            continue
        if cur["collecting"] and stripped:
            cur["note_parts"].append(stripped)
    if cur:
        contacts.append(cur)

    out = []
    for c in contacts:
        note = "\n".join(c["note_parts"]).strip()
        out.append({"cid": c["cid"], "phone": c["phone"], "note": note})
    return out

def is_no_action(note):
    collapsed = re.sub(r"[^a-z]", "", note.lower())
    return collapsed in NO_ACTION

# ---------- State ----------
def load_synced():
    from auto_daily_call_list import _kv
    kv = _kv("GET", "callist-synced-notes")
    if kv is not None:
        return kv
    try:
        return json.load(open(SYNC_FILE))
    except Exception:
        return {}

def save_synced(data):
    from auto_daily_call_list import _kv
    if _kv("POST", "callist-synced-notes", data) is not None:
        return
    json.dump(data, open(SYNC_FILE, "w"))

# ---------- Main ----------
def main():
    today = date.today()
    today_display = today.strftime("%B %-d, %Y")
    log(f"=== Auto note sync for {today} ===")

    try:
        page_id = open(PAGE_FILE).read().strip()
    except Exception:
        page_id = ""
    if not page_id:
        log("No current page id on file. Nothing to sync. Exiting.")
        return

    page = get_page(page_id)
    if not page:
        log(f"Could not fetch page {page_id}. Exiting.")
        return
    if page.get("archived"):
        log("Current page is archived (no list created today). Exiting.")
        return
    title = page_title(page)
    if today_display not in title:
        log(f"Page title '{title}' is not today's list. Exiting without syncing.")
        return

    blocks   = get_all_children(page_id)
    contacts = parse_contacts(blocks)
    log(f"Parsed {len(contacts)} contact blocks from the page")

    # Build phone fallback only if some contact lacks a ref id
    need_fallback = any(not c["cid"] and c["phone"] for c in contacts)
    pmap = build_phone_map() if need_fallback else {}
    if need_fallback:
        log(f"Built phone fallback map ({len(pmap)} contacts) for blocks missing ref ids")

    synced = load_synced()
    already = set(synced.get(page_id, []))

    posted = skipped_noaction = skipped_empty = skipped_done = unresolved = failed = 0
    for c in contacts:
        cid = c["cid"] or pmap.get(c["phone"])
        note = c["note"]
        if not note:
            skipped_empty += 1; continue
        if is_no_action(note):
            skipped_noaction += 1; continue
        if not cid:
            unresolved += 1
            log(f"  ! Could not resolve a contact_id (phone={c['phone']}) — note left unsynced")
            continue
        if cid in already:
            skipped_done += 1; continue
        if post_note(cid, note):
            posted += 1
            already.add(cid)
            log(f"  ✓ Posted note to contact {cid} ({len(note)} chars)")
        else:
            failed += 1
            log(f"  ✗ FAILED to post note to contact {cid}")

    synced[page_id] = sorted(already)
    save_synced(synced)
    log(f"Done. posted={posted} already_synced={skipped_done} "
        f"empty={skipped_empty} no_action={skipped_noaction} "
        f"unresolved={unresolved} failed={failed}")

    # Then apply YOUR written decisions from the "Suggested Moves" section to GHL.
    # Only acts where you typed a note; never auto-applies the AI's own guesses.
    try:
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import apply_moves
        apply_moves.run(dry_run=False)
    except Exception as e:
        log(f"apply_moves step skipped: {e}")

if __name__ == "__main__":
    main()
