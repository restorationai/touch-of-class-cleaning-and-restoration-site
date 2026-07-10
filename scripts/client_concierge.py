#!/usr/bin/env python3
"""Client Concierge (phase 1) — agentic follow-up on what clients owe us.

Complements client_ops_sync.py: that script watches for answers arriving in
the app; THIS script goes and gets them. It knows every client's outstanding
asks (pending `client_intake_items` + planned `client_input` rows in
`marketing_action_plan`), drafts one warm consolidated SMS/email via Claude,
sends through GoHighLevel, understands the replies, and writes matched
answers back into `client_intake_items` (status=answered, answer={"value":…},
answered_at) so the EXISTING client_ops_sync handlers apply them downstream.

Subcommands
    status                       Table of every tracked client: pending intake
                                 count, open client_input asks, last concierge
                                 contact, nudges used, next eligible date.
    compose --company CO-…       Draft ONE consolidated message for a client
        [--channel sms|email]    (max 3 items, highest priority first, always
        [--send]                 ends with the app self-serve alternative).
                                 Prints the draft; --send delivers via GHL
                                 (CANARY GATE + cadence guardrails apply).
    inbound --poll [--send]      Pull inbound GHL messages for tracked
                                 contacts since the state cursor, classify
                                 each reply with Claude against that client's
                                 open items, write matched answers to
                                 Supabase, resolve matched plan rows, draft a
                                 confirmation + next-question reply (printed;
                                 --send gated). Non-matches / negative
                                 sentiment / questions back at us are appended
                                 to clients/_ops/concierge-escalations.md.
    canary --phone +1… --email … Create/find the "Concierge Canary" GHL
                                 contact, seed 2-3 fake intake items on the
                                 Test (Rank AI) company (CO-1782880883337),
                                 and run the full outbound compose+send to
                                 ONLY that contact.

CANARY GATE (hard constraint, phase 1)
    ALLOWED_RECIPIENTS is loaded from env CONCIERGE_ALLOWLIST — a
    comma-separated list of phone numbers and/or email addresses. The gate
    lives INSIDE send_message(): any computed recipient (phone for SMS, email
    for Email) not in the allowlist makes the send function raise
    SendBlocked loudly. The default allowlist is EMPTY, so nothing can be
    delivered anywhere until Santino explicitly adds his own number/email:
        CONCIERGE_ALLOWLIST=+18089891939,ignitesystems3@gmail.com
    Phones are compared on their last 10 digits; emails case-insensitively.
    There is no bypass flag on purpose.

Cadence guardrails (enforced in code at send time)
    - min 3 days between sends per company (state: last_contacted)
    - max 4 total nudges, then the company is flagged "ESCALATE to Santino"
    - business hours only: 9:00-18:00 in companies.timezone
      (default America/Los_Angeles)

State: clients/_ops/concierge-state.json — per-company contact bookkeeping
(ghl_contact_id, last_contacted, nudge_count) + the inbound message cursor.
Committed by the workflow (no secrets in it — GHL contact ids + timestamps).
Escalations: clients/_ops/concierge-escalations.md (append-only).

Env (rank-ai/.env or CI secrets):
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY   app database
    GHL_API_KEY, GHL_LOCATION_ID              LeadConnector private token +
                                              location (token verified to have
                                              conversations/message write scope)
    ANTHROPIC_API_KEY                         drafting + reply classification
                                              (claude-sonnet-5; sampling params
                                              are not accepted on this model,
                                              so determinism is prompt-driven)
    CONCIERGE_ALLOWLIST                       canary gate (default EMPTY)
    CONCIERGE_FROM_NUMBER                     SMS sender number. The assistant
                                              identity is the location TOLL-FREE
                                              +18556484464; the 805 local number
                                              (+18053293449) stays Santino's
                                              personal thread — never send
                                              concierge SMS from it. Unset =>
                                              loud startup warning and GHL picks
                                              its default number (the 805!).

GHL contact linkage: companies.integration_settings.ghl_contact_id (written by
scripts/ghl_link.py) is the source of truth; full-text search is only a
fallback and every fallback resolution is flagged loudly in the output.

Workflow: .github/workflows/client-concierge.yml — workflow_dispatch ONLY in
phase 1 (no cron until real-client enrollment is approved).

Usage examples
    python3 scripts/client_concierge.py status
    python3 scripts/client_concierge.py compose --company CO-1783380243102
    python3 scripts/client_concierge.py compose --company CO-… --channel email
    python3 scripts/client_concierge.py inbound --poll            # dry run
    python3 scripts/client_concierge.py inbound --poll --send     # gated
    python3 scripts/client_concierge.py canary --phone +1808… --email me@x.com
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
OPS_DIR = ROOT / "clients" / "_ops"
STATE_PATH = OPS_DIR / "concierge-state.json"
ESCALATIONS_PATH = OPS_DIR / "concierge-escalations.md"

GHL_BASE = "https://services.leadconnectorhq.com"
GHL_VERSION = "2021-07-28"
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-5"
UA = "rank-ai-client-concierge/1.0"

APP_SELF_SERVE = ("Or do it yourself: log in at app.restorationai.io and "
                  "click the 'Setup Guide' button at the top.")
APP_SETUP_LINK = "https://app.restorationai.io/?setup=1"   # auto-opens the guide
INTRO_TEMPLATE = ("Hi {first}, this is the onboarding assistant from "
                  "Santino's team at Rank AI — I help get everything set up "
                  "for your account.")
SMS_MAX_CHARS = 450
SMS_MAX_CHARS_FIRST = 900   # first-ever message carries the intro line
MAX_ITEMS_PER_MESSAGE = 3
MIN_DAYS_BETWEEN_SENDS = 3
MAX_NUDGES = 4
BUSINESS_HOUR_START = 9
BUSINESS_HOUR_END = 18
DEFAULT_TZ = "America/Los_Angeles"

CANARY_COMPANY_ID = "CO-1782880883337"   # "Test (Rank AI)" — reused for canary
CANARY_CONTACT_NAME = "Concierge Canary"


# ---------------------------------------------------------------- env / gate
def load_env() -> None:
    """Fail-soft .env loader (matches client_ops_sync.py) — never overrides CI env."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class SendBlocked(RuntimeError):
    """Raised by send_message() when a recipient is not on the canary allowlist."""


def _norm_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p or "")
    return digits[-10:]  # compare on national number


def _norm_email(e: str) -> str:
    return (e or "").strip().lower()


def allowed_recipients() -> set[str]:
    """CONCIERGE_ALLOWLIST env (comma-separated phones/emails). Default EMPTY."""
    out: set[str] = set()
    for tok in os.environ.get("CONCIERGE_ALLOWLIST", "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.add(_norm_email(tok) if "@" in tok else _norm_phone(tok))
    return out


# ---------------------------------------------------------------- REST helpers
def _sb(method: str, path: str, body=None, prefer: str = "return=representation"):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    resp = requests.request(method, url, json=body, timeout=30, headers={
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "Prefer": prefer, "User-Agent": UA,
    })
    resp.raise_for_status()
    return resp.json() if resp.content else None


def _ghl(method: str, path: str, *, params=None, body=None):
    resp = requests.request(
        method, GHL_BASE + path, params=params, json=body, timeout=30,
        headers={"Authorization": f"Bearer {os.environ['GHL_API_KEY']}",
                 "Version": GHL_VERSION, "Accept": "application/json",
                 "User-Agent": UA})
    if resp.status_code >= 400:
        raise RuntimeError(f"GHL {method} {path} -> {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.content else None


def _loc() -> str:
    return os.environ["GHL_LOCATION_ID"]


def anthropic_json(system: str, user: str, *, max_tokens: int = 1500) -> dict:
    """One Messages call, expects a single JSON object in the reply."""
    resp = requests.post(ANTHROPIC_API, timeout=120, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json", "User-Agent": UA,
    }, json={
        "model": ANTHROPIC_MODEL, "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    })
    resp.raise_for_status()
    data = resp.json()
    text = "".join(b.get("text", "") for b in data.get("content", [])
                   if b.get("type") == "text").strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError(f"Claude returned no JSON object: {text[:200]!r}")
    return json.loads(m.group(0))


# ---------------------------------------------------------------- state
def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"inbound_cursor": None, "companies": {}}


def save_state(state: dict, dry_run: bool) -> None:
    if dry_run:
        print("  [dry-run] state not written")
        return
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def company_state(state: dict, company_id: str) -> dict:
    return state["companies"].setdefault(company_id, {
        "ghl_contact_id": None, "last_contacted": None, "first_contacted": None,
        "nudge_count": 0, "last_channel": None})


# ---------------------------------------------------------------- data pulls
def fetch_companies(ids: list[str] | None = None) -> dict[str, dict]:
    q = ("/rest/v1/companies?select=id,name,timezone,phone,email,"
         "account_owner_name,status,integration_settings")
    if ids:
        q += "&id=in.(" + ",".join(urllib.parse.quote(i) for i in ids) + ")"
    return {c["id"]: c for c in _sb("GET", q) or []}


def fetch_pending_intake(company_id: str | None = None) -> list[dict]:
    q = ("/rest/v1/client_intake_items?status=eq.pending"
         "&select=id,company_id,question,help_text,field_type,blocks,sort,"
         "parent_id,trigger_value,answer,status&order=sort.asc")
    if company_id:
        q += f"&company_id=eq.{urllib.parse.quote(company_id)}"
    items = _sb("GET", q) or []
    # Conditional children (parent_id + trigger_value) only apply once the
    # parent is answered with the trigger value — skip the rest.
    by_id_all = {i["id"]: i for i in items}
    out = []
    for it in items:
        pid = it.get("parent_id")
        if not pid:
            out.append(it)
            continue
        parent = by_id_all.get(pid)
        if parent is not None:  # parent still pending -> child not yet active
            continue
        out.append(it)  # parent answered elsewhere; keep (best effort)
    return out


def fetch_open_asks(company_id: str | None = None) -> list[dict]:
    q = ("/rest/v1/marketing_action_plan?action_type=eq.client_input"
         "&status=eq.planned"
         "&select=id,company_id,rank_ai_slug,title,rationale,priority"
         "&order=priority.asc")
    if company_id:
        q += f"&company_id=eq.{urllib.parse.quote(company_id)}"
    rows = _sb("GET", q) or []
    # "Client answered 'yes': …" rows are team notifications produced when a
    # gating intake answer lands — nothing to ask the client. Skip them.
    return [r for r in rows
            if not (r.get("title") or "").startswith("Client answered")]


def gather_items(company_id: str) -> list[dict]:
    """Outstanding items, highest priority first.

    Ordering: blocking intake items, then plan asks by priority, then the
    remaining intake items by sort. Each entry is normalized to
    {kind: intake|plan, id, text, detail, field_type}.
    """
    intake = fetch_pending_intake(company_id)
    asks = fetch_open_asks(company_id)
    blocking = [i for i in intake if i.get("blocks")]
    rest = [i for i in intake if not i.get("blocks")]

    def norm_intake(i):
        return {"kind": "intake", "id": i["id"], "text": i["question"],
                "detail": i.get("help_text") or "", "field_type": i["field_type"],
                "blocks": i.get("blocks")}

    def norm_plan(p):
        return {"kind": "plan", "id": p["id"], "text": p["title"],
                "detail": p.get("rationale") or "", "field_type": "free_text",
                "blocks": None}

    return ([norm_intake(i) for i in blocking]
            + [norm_plan(p) for p in asks]
            + [norm_intake(i) for i in rest])


# ---------------------------------------------------------------- GHL contact
def linked_contact_id(company: dict) -> str | None:
    """Durable linkage written by scripts/ghl_link.py."""
    return ((company.get("integration_settings") or {}).get("ghl_contact_id")
            or None)


def resolve_contact(company: dict) -> dict | None:
    """Find the client's GHL contact.

    Order: (1) durable integration_settings.ghl_contact_id linkage (source of
    truth, written by scripts/ghl_link.py), (2) full-text search fallback by
    company email, phone, then name — flagged LOUDLY because search matches
    are best-effort guesses.
    """
    cid = linked_contact_id(company)
    if cid:
        try:
            data = _ghl("GET", f"/contacts/{cid}")
            contact = (data or {}).get("contact") or data
            if contact and contact.get("id"):
                return contact
            print(f"  WARNING: linked GHL contact {cid} returned no record — "
                  "falling back to search", file=sys.stderr)
        except RuntimeError as e:
            print(f"  WARNING: linked GHL contact {cid} lookup failed ({e}) — "
                  "falling back to search", file=sys.stderr)
    for query in (company.get("email"), company.get("phone"), company.get("name")):
        if not query or not str(query).strip():
            continue
        data = _ghl("GET", "/contacts/", params={
            "locationId": _loc(), "query": str(query).strip(), "limit": 5})
        contacts = data.get("contacts") or []
        if contacts:
            print(f"  WARNING: {company.get('id')} has NO ghl_contact_id "
                  f"linkage — resolved {contacts[0]['id']} via search "
                  f"fallback. Run scripts/ghl_link.py to link durably.",
                  file=sys.stderr)
            return contacts[0]
    return None


def contact_first_name(contact: dict | None, company: dict) -> str:
    if contact and contact.get("firstName"):
        return contact["firstName"].strip().title()
    owner = (company.get("account_owner_name") or "").strip()
    if owner:
        return owner.split()[0].title()
    email = company.get("email") or ""
    local = email.split("@")[0]
    m = re.match(r"[a-zA-Z]{3,}", local)
    if m and m.group(0).lower() not in ("info", "contact", "office", "admin", "hello"):
        return m.group(0).title()
    return "there"


# ---------------------------------------------------------------- guardrails
def next_eligible(cs: dict) -> datetime | None:
    if not cs.get("last_contacted"):
        return None
    last = datetime.fromisoformat(cs["last_contacted"])
    return last + timedelta(days=MIN_DAYS_BETWEEN_SENDS)


def cadence_check(cs: dict, company: dict) -> str | None:
    """Return a human-readable refusal reason, or None if a send is allowed now."""
    if cs.get("nudge_count", 0) >= MAX_NUDGES:
        return f"max {MAX_NUDGES} nudges reached — ESCALATE to Santino"
    ne = next_eligible(cs)
    now = datetime.now(timezone.utc)
    if ne and now < ne:
        return f"cooldown — next eligible {ne.strftime('%Y-%m-%d %H:%M UTC')}"
    tz = ZoneInfo(company.get("timezone") or DEFAULT_TZ)
    local = now.astimezone(tz)
    if not (BUSINESS_HOUR_START <= local.hour < BUSINESS_HOUR_END):
        return (f"outside business hours ({local.strftime('%H:%M')} "
                f"{tz.key}; window {BUSINESS_HOUR_START}:00-{BUSINESS_HOUR_END}:00)")
    return None


# ---------------------------------------------------------------- SEND (gated)
def send_message(contact: dict, channel: str, body: str,
                 subject: str | None = None) -> dict:
    """Deliver via GHL POST /conversations/messages. CANARY GATE lives HERE.

    The recipient (contact phone for SMS, contact email for Email) must be on
    the CONCIERGE_ALLOWLIST or this function raises SendBlocked. There is no
    override. Callers decide dry-run/--send; this function is the last line.
    """
    allow = allowed_recipients()
    if channel == "sms":
        recipient = contact.get("phone") or ""
        key = _norm_phone(recipient)
    else:
        recipient = contact.get("email") or ""
        key = _norm_email(recipient)
    if not recipient:
        raise SendBlocked(f"contact {contact.get('id')} has no {channel} recipient")
    if not allow:
        raise SendBlocked(
            "CANARY GATE: CONCIERGE_ALLOWLIST is empty — refusing to send "
            f"{channel} to {recipient!r}. Nothing can be delivered until the "
            "allowlist is populated.")
    if key not in allow:
        raise SendBlocked(
            f"CANARY GATE: {recipient!r} is not on CONCIERGE_ALLOWLIST — "
            f"refusing {channel} send to contact {contact.get('id')}.")

    payload: dict = {"type": "SMS" if channel == "sms" else "Email",
                     "contactId": contact["id"]}
    if channel == "sms":
        payload["message"] = body
        from_number = os.environ.get("CONCIERGE_FROM_NUMBER", "").strip()
        if from_number:
            payload["fromNumber"] = from_number
        else:
            print("  WARNING: CONCIERGE_FROM_NUMBER unset — GHL will pick the "
                  "location default (the 805 local, Santino's personal "
                  "thread). Set it to the toll-free +18556484464.",
                  file=sys.stderr)
    else:
        payload["subject"] = subject or "A few quick things for your Rank AI setup"
        payload["html"] = body.replace("\n", "<br>")
    result = _ghl("POST", "/conversations/messages", body=payload)
    print(f"  SENT {channel} to {recipient} (contact {contact['id']})")
    return result or {}


# ---------------------------------------------------------------- compose
COMPOSE_SYSTEM = """\
You write short follow-up messages to home-services business owners on behalf
of "Santino's team at Rank AI" (their marketing/website team). Voice: warm,
human, zero corporate filler, no exclamation-point spam, no emojis. You are
asking the client for things only they can provide. Be specific and easy to
answer by simply replying to the message.

PLAIN LANGUAGE — the most important rule. Clients are contractors, not tech
people, and they do not know industry or web terms — ever. Write at a
6th-grade reading level. Every ask must be answerable by a busy contractor on
his phone without googling anything. Ask for the THING, not the mechanism.

BANNED WORDS — never use these; use the plain version instead:
- "registrar"            -> "the website where you bought your domain name (like GoDaddy)"
- "nameserver change" / "nameservers" -> "a small settings change we make when your new site goes live"
- "DBA"                  -> ask it as "does your business operate under this license number"
- "DNS" / "zone" / "NS"  -> never mention them at all; describe the outcome
                            (e.g. "so your new website can go live")
- "CSLB"                 -> "contractor license number"
- "COI"                  -> "proof of insurance from your insurance agent"
- "GBP" / "Google Business Profile" -> "your Google business listing"
Items handed to you may be written in jargon by our internal systems —
translate them into plain asks before writing. Never quote the internal
wording. No acronyms of any kind unless they are everyday words (OK, TV).

INTRO RULE:
- If told "FIRST CONTACT: yes", open with EXACTLY the intro line provided,
  then continue naturally.
- Otherwise just greet by first name — no intro, no re-introduction.

Rules:
- Cover AT MOST the items given (they are already priority-ordered). Weave
  them in conversationally — short sentences or a compact list, not a form.
- Never invent items, prices, or deadlines. Never promise work.
- Always end with the exact self-serve alternative line provided. If (and
  only if) you include a clickable link to the app, the link must be exactly
  https://app.restorationai.io/?setup=1 — it opens the Setup Guide by itself.
- SMS: total body within the character budget given — the budget includes the
  intro and the closing self-serve line, and the closing line must NEVER be
  cut. If space is tight, trim item detail, not the closing. No subject, no
  links other than the optional setup link.
- Email: give a short subject (<= 60 chars) and a slightly fuller body
  (still under ~140 words), sign off as "— Santino's team at Rank AI".
Return ONLY a JSON object: {"subject": string|null, "body": string}.
Keep drafting deterministic: choose the most natural single phrasing, no
alternatives or commentary."""


def compose_draft(company: dict, first_name: str, items: list[dict],
                  channel: str, first_contact: bool) -> dict:
    chosen = items[:MAX_ITEMS_PER_MESSAGE]
    lines = []
    for i, it in enumerate(chosen, 1):
        detail = (it["detail"] or "")[:300]
        lines.append(f"{i}. [{it['kind']}] {it['text']}"
                     + (f" — context: {detail}" if detail else ""))
    sms_budget = SMS_MAX_CHARS_FIRST if first_contact else SMS_MAX_CHARS
    intro = INTRO_TEMPLATE.format(first=first_name)
    user = (f"Client: {company['name']} (first name: {first_name})\n"
            f"Channel: {channel} (character budget for SMS: {sms_budget})\n"
            f"FIRST CONTACT: {'yes' if first_contact else 'no'}\n"
            + (f"Intro line to open with, exactly: \"{intro}\"\n"
               if first_contact else "")
            + f"Outstanding items (priority order, cover all of these and "
            f"nothing else):\n" + "\n".join(lines) +
            f"\n\nEnd with exactly: \"{APP_SELF_SERVE}\"")
    draft = anthropic_json(COMPOSE_SYSTEM, user)
    body = (draft.get("body") or "").strip()
    if channel == "sms" and len(body) > sms_budget:
        body = body[:sms_budget - 1].rsplit(" ", 1)[0] + "…"
    return {"subject": (draft.get("subject") or None), "body": body,
            "items": chosen}


def cmd_compose(args) -> int:
    state = load_state()
    companies = fetch_companies([args.company])
    company = companies.get(args.company)
    if not company:
        print(f"ERROR: company {args.company} not found", file=sys.stderr)
        return 1
    items = gather_items(args.company)
    if not items:
        print(f"{company['name']}: nothing outstanding — no message needed.")
        return 0
    contact = resolve_contact(company)
    first = contact_first_name(contact, company)
    cs = company_state(state, args.company)
    first_contact = not cs.get("first_contacted")
    print(f"Company: {company['name']} ({args.company})")
    linked = linked_contact_id(company)
    print(f"GHL contact: "
          + (f"{contact['id']} ({contact.get('contactName')}, "
             f"{contact.get('phone')}, {contact.get('email')})" if contact
             else "NOT FOUND — compose only, send would fail")
          + ("" if linked else "  [NO DURABLE LINKAGE — search fallback]"))
    print(f"First contact: {'yes — intro line required' if first_contact else 'no'}")
    print(f"Outstanding items: {len(items)} (messaging top {min(len(items), MAX_ITEMS_PER_MESSAGE)})")

    draft = compose_draft(company, first, items, args.channel, first_contact)
    print("\n" + "=" * 62)
    if draft["subject"] and args.channel == "email":
        print(f"Subject: {draft['subject']}")
    print(draft["body"])
    print("=" * 62)
    print(f"({len(draft['body'])} chars, channel={args.channel})")

    if not args.send:
        print("\n[draft only — pass --send to deliver (canary gate applies)]")
        return 0

    reason = cadence_check(cs, company)
    if reason:
        print(f"\nSEND REFUSED (cadence): {reason}", file=sys.stderr)
        return 1
    if not contact:
        print("\nSEND REFUSED: no GHL contact resolved", file=sys.stderr)
        return 1
    try:
        send_message(contact, args.channel, draft["body"], draft["subject"])
    except SendBlocked as e:
        print(f"\nSEND BLOCKED: {e}", file=sys.stderr)
        return 1
    now = datetime.now(timezone.utc).isoformat()
    cs.update({"ghl_contact_id": contact["id"],
               "last_contacted": now,
               "first_contacted": cs.get("first_contacted") or now,
               "nudge_count": cs.get("nudge_count", 0) + 1,
               "last_channel": args.channel})
    save_state(state, dry_run=False)
    return 0


# ---------------------------------------------------------------- status
def cmd_status(_args) -> int:
    state = load_state()
    intake = fetch_pending_intake()
    asks = fetch_open_asks()
    ids = sorted({i["company_id"] for i in intake} | {a["company_id"] for a in asks})
    companies = fetch_companies(ids)
    rows = []
    unlinked = []
    for cid in ids:
        co = companies.get(cid, {"name": cid, "timezone": None})
        cs = state["companies"].get(cid, {})
        n_intake = sum(1 for i in intake if i["company_id"] == cid)
        n_asks = sum(1 for a in asks if a["company_id"] == cid)
        last = (cs.get("last_contacted") or "never")[:16]
        nudges = cs.get("nudge_count", 0)
        if nudges >= MAX_NUDGES:
            nxt = "ESCALATE to Santino"
        elif cs.get("last_contacted"):
            nxt = next_eligible(cs).strftime("%Y-%m-%d")
        else:
            nxt = "now (business hrs)"
        link = linked_contact_id(co) if co.get("integration_settings") is not None else None
        if not link:
            unlinked.append((cid, co["name"]))
        rows.append((cid, co["name"][:34], n_intake, n_asks, last, nudges, nxt,
                     "yes" if link else "NO"))

    hdr = (f"{'company':<20} {'name':<34} {'intake':>6} {'asks':>4} "
           f"{'last contact':<16} {'n':>2} {'ghl':>3} {'next eligible':<20}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r[0]:<20} {r[1]:<34} {r[2]:>6} {r[3]:>4} {r[4]:<16} "
              f"{r[5]:>2} {r[7]:>3} {r[6]:<20}")
    print(f"\n{len(rows)} client(s) with outstanding items "
          f"({len(intake)} intake, {len(asks)} asks). "
          f"Allowlist entries: {len(allowed_recipients())}.")
    for cid, name in unlinked:
        print(f"!! WARNING: {name} ({cid}) has NO GHL linkage "
              f"(integration_settings.ghl_contact_id) — sends would rely on "
              f"search guessing. Fix with: python3 scripts/ghl_link.py link")
    return 0


# ---------------------------------------------------------------- inbound
CLASSIFY_SYSTEM = """\
You classify a client's inbound reply against their open onboarding items.
Decide which item (if any) the reply answers and extract the answer value.

Few-shot guide:
- "CSLB is 1043821" / "lic # C-36 998877"      -> license answer, value is the
  number (e.g. "1043821"), matches a license/registration item.
- "yes that's fine" / "yep go ahead" / "no"    -> yes_no consent answer for the
  most plausible pending yes_no item; value "yes" or "no".
- "we bought it under jack@gmail.com" /
  "godaddy account is under my wife's email"   -> free-text answer to a domain/
  registrar/email question; value is the verbatim useful part.
- "just emailed you the customer list" /
  "sent the export over"                       -> customer-list confirmation;
  value "confirmed", matches a customer-list/checklist item.
- "who is this?" / "stop texting me" /
  "call me" / anything angry or unrelated      -> no match; escalate.

Return ONLY JSON:
{"matches": [{"item_id": "<id from the list>", "value": "<extracted answer>",
              "answer_type": "license|yes_no|free_text|customer_list"}],
 "escalate": bool,
 "escalate_reason": string|null,
 "sentiment": "positive|neutral|negative"}
Match at most the items clearly answered. When in doubt, do not match — set
escalate true with a reason instead."""

REPLY_SYSTEM = """\
You write the concierge's next reply after a client answered something.
Voice: warm, brief, from "Santino's team at Rank AI". Thank them, confirm
what you recorded (one clause), then ask ONE next question if any remain —
the highest-priority open item provided. If nothing remains, close warmly
("that's everything we needed"). SMS-length: <= 450 chars. No emojis.
Return ONLY JSON: {"body": string}."""


def _tracked_contacts(state: dict) -> dict[str, str]:
    """contact_id -> company_id for every company we've engaged (incl. canary)."""
    out = {}
    for cid, cs in state.get("companies", {}).items():
        if cs.get("ghl_contact_id"):
            out[cs["ghl_contact_id"]] = cid
    return out


def fetch_inbound_since(contact_id: str, since: datetime) -> list[dict]:
    convs = _ghl("GET", "/conversations/search", params={
        "locationId": _loc(), "contactId": contact_id, "limit": 20})
    messages: list[dict] = []
    for conv in convs.get("conversations", []) or []:
        data = _ghl("GET", f"/conversations/{conv['id']}/messages",
                    params={"limit": 50})
        for msg in (data.get("messages") or {}).get("messages", []) or []:
            if msg.get("direction") != "inbound":
                continue
            if msg.get("messageType") not in ("TYPE_SMS", "TYPE_EMAIL"):
                continue
            body = (msg.get("body") or "").strip()
            if not body:
                continue
            added = msg.get("dateAdded")
            try:
                ts = datetime.fromisoformat(added.replace("Z", "+00:00"))
            except (AttributeError, ValueError):
                continue
            if ts <= since:
                continue
            messages.append({"id": msg["id"], "body": body, "ts": ts,
                             "conversation_id": conv["id"],
                             "channel": "sms" if msg["messageType"] == "TYPE_SMS"
                             else "email"})
    return sorted(messages, key=lambda m: m["ts"])


def apply_answer(item_id: str, value: str, dry_run: bool) -> None:
    body = {"status": "answered", "answer": {"value": value},
            "answered_at": datetime.now(timezone.utc).isoformat()}
    if dry_run:
        print(f"    [dry-run] would PATCH client_intake_items/{item_id[:8]} -> {body}")
        return
    _sb("PATCH", f"/rest/v1/client_intake_items?id=eq.{item_id}", body,
        prefer="return=minimal")


def resolve_plan_row(row_id: str, dry_run: bool) -> None:
    if dry_run:
        print(f"    [dry-run] would PATCH marketing_action_plan/{row_id[:8]} -> resolved")
        return
    _sb("PATCH", f"/rest/v1/marketing_action_plan?id=eq.{row_id}",
        {"status": "resolved"}, prefer="return=minimal")


def append_escalation(company: dict, msg: dict, reason: str, dry_run: bool) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = (f"\n## {stamp} — {company.get('name', '?')} ({company.get('id', '?')})\n"
             f"- Channel: {msg['channel']}  Message id: {msg['id']}\n"
             f"- Reply: {msg['body'][:400]!r}\n"
             f"- Reason: {reason}\n")
    if dry_run:
        print(f"    [dry-run] would append escalation:{block}")
        return
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    if not ESCALATIONS_PATH.exists():
        ESCALATIONS_PATH.write_text("# Concierge Escalations\n")
    with ESCALATIONS_PATH.open("a") as f:
        f.write(block)


def cmd_inbound(args) -> int:
    if not args.poll:
        print("inbound: pass --poll", file=sys.stderr)
        return 1
    dry_run = not args.send
    state = load_state()
    run_start = datetime.now(timezone.utc)
    cursor = state.get("inbound_cursor")
    since = (datetime.fromisoformat(cursor) if cursor
             else run_start - timedelta(days=7))
    tracked = _tracked_contacts(state)
    print(f"inbound poll since {since.strftime('%Y-%m-%dT%H:%M:%SZ')} — "
          f"{len(tracked)} tracked contact(s)"
          f"{' [DRY RUN — no writes, no sends]' if dry_run else ''}")

    companies = fetch_companies(sorted(set(tracked.values()))) if tracked else {}
    handled_any = False
    for contact_id, company_id in tracked.items():
        company = companies.get(company_id, {"id": company_id, "name": company_id})
        msgs = fetch_inbound_since(contact_id, since)
        if not msgs:
            continue
        open_items = gather_items(company_id)
        for msg in msgs:
            handled_any = True
            print(f"\n  {company['name']}: inbound {msg['channel']} "
                  f"{msg['ts'].strftime('%m-%d %H:%M')}: {msg['body'][:90]!r}")
            item_list = "\n".join(
                f"- id={it['id']} kind={it['kind']} type={it['field_type']} "
                f"q={it['text'][:110]!r}" for it in open_items) or "(none)"
            result = anthropic_json(
                CLASSIFY_SYSTEM,
                f"Open items for {company['name']}:\n{item_list}\n\n"
                f"Inbound reply:\n{msg['body'][:1200]}")
            matched_ids = set()
            for match in result.get("matches", []):
                it = next((i for i in open_items if i["id"] == match.get("item_id")), None)
                if not it:
                    continue
                matched_ids.add(it["id"])
                print(f"    matched [{match.get('answer_type')}] "
                      f"{it['text'][:60]!r} -> {match.get('value')!r}")
                if it["kind"] == "intake":
                    apply_answer(it["id"], str(match.get("value", "")), dry_run)
                else:
                    resolve_plan_row(it["id"], dry_run)
            if (result.get("escalate") or result.get("sentiment") == "negative"
                    or not result.get("matches")):
                reason = result.get("escalate_reason") or (
                    "negative sentiment" if result.get("sentiment") == "negative"
                    else "no open item matched")
                print(f"    ESCALATE: {reason}")
                append_escalation(company, msg, reason, dry_run)
            if matched_ids:
                remaining = [i for i in open_items if i["id"] not in matched_ids]
                nxt = (f"Next open item to ask: {remaining[0]['text']}"
                       if remaining else "No items remain.")
                reply = anthropic_json(
                    REPLY_SYSTEM,
                    f"Client first name: "
                    f"{contact_first_name(None, company)}\n"
                    f"They just answered: {msg['body'][:400]}\n{nxt}")
                print(f"    reply draft: {reply.get('body', '')!r}")
                if args.send:
                    contact = {"id": contact_id,
                               "phone": company.get("phone"),
                               "email": company.get("email")}
                    try:
                        send_message(contact, msg["channel"],
                                     reply.get("body", ""))
                    except SendBlocked as e:
                        print(f"    SEND BLOCKED: {e}")

    if not handled_any:
        print("  no new inbound messages for tracked contacts.")
    state["inbound_cursor"] = run_start.isoformat()
    save_state(state, dry_run)
    print(f"cursor -> {run_start.isoformat()}"
          + (" (not persisted — dry run)" if dry_run else ""))
    return 0


# ---------------------------------------------------------------- canary
CANARY_ITEMS = [
    {"question": "[CANARY] What is your contractor license number (CSLB)?",
     "field_type": "text", "blocks": None, "sort": 900},
    {"question": "[CANARY] OK to use your current logo on the new site?",
     "field_type": "yes_no", "blocks": "site_build", "sort": 901},
    {"question": "[CANARY] Which email owns your domain registrar (GoDaddy) account?",
     "field_type": "text", "blocks": "site_build", "sort": 902},
]


def cmd_canary(args) -> int:
    state = load_state()
    # 1. find-or-create the canary contact in GHL
    contact = None
    data = _ghl("GET", "/contacts/", params={
        "locationId": _loc(), "query": args.email, "limit": 5})
    for c in data.get("contacts") or []:
        if _norm_email(c.get("email")) == _norm_email(args.email):
            contact = c
            break
    if not contact:
        created = _ghl("POST", "/contacts/upsert", body={
            "locationId": _loc(), "firstName": "Concierge",
            "lastName": "Canary", "name": CANARY_CONTACT_NAME,
            "email": args.email, "phone": args.phone,
            "tags": ["concierge-canary"]})
        contact = created.get("contact") or created
    print(f"canary contact: {contact['id']} "
          f"({contact.get('phone') or args.phone}, {contact.get('email') or args.email})")

    # 2. seed fake intake items on the Test (Rank AI) company (idempotent)
    existing = fetch_pending_intake(CANARY_COMPANY_ID)
    existing_q = {i["question"] for i in existing}
    to_seed = [dict(company_id=CANARY_COMPANY_ID, status="pending",
                    source="concierge-canary", **spec)
               for spec in CANARY_ITEMS if spec["question"] not in existing_q]
    if to_seed:
        _sb("POST", "/rest/v1/client_intake_items", to_seed, prefer="return=minimal")
        print(f"seeded {len(to_seed)} canary intake item(s) on {CANARY_COMPANY_ID}")
    else:
        print("canary intake items already seeded")

    # 3. full outbound: compose + send to ONLY this contact
    companies = fetch_companies([CANARY_COMPANY_ID])
    company = companies[CANARY_COMPANY_ID]
    items = gather_items(CANARY_COMPANY_ID)
    cs_peek = state["companies"].get(CANARY_COMPANY_ID, {})
    draft = compose_draft(company, "Canary", items, args.channel,
                          first_contact=not cs_peek.get("first_contacted"))
    print("\n" + "=" * 62)
    if draft["subject"] and args.channel == "email":
        print(f"Subject: {draft['subject']}")
    print(draft["body"])
    print("=" * 62)

    cs = company_state(state, CANARY_COMPANY_ID)
    reason = cadence_check(cs, company)
    if reason:
        print(f"SEND REFUSED (cadence): {reason}", file=sys.stderr)
        return 1
    send_contact = {"id": contact["id"],
                    "phone": contact.get("phone") or args.phone,
                    "email": contact.get("email") or args.email}
    try:
        send_message(send_contact, args.channel, draft["body"], draft["subject"])
    except SendBlocked as e:
        print(f"SEND BLOCKED: {e}", file=sys.stderr)
        return 1
    now = datetime.now(timezone.utc).isoformat()
    cs.update({"ghl_contact_id": contact["id"],
               "last_contacted": now,
               "first_contacted": cs.get("first_contacted") or now,
               "nudge_count": cs.get("nudge_count", 0) + 1,
               "last_channel": args.channel})
    save_state(state, dry_run=False)
    return 0


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="table of clients with outstanding items")

    pc = sub.add_parser("compose", help="draft (and optionally send) one nudge")
    pc.add_argument("--company", required=True, help="company id (CO-…)")
    pc.add_argument("--channel", choices=("sms", "email"), default="sms")
    pc.add_argument("--send", action="store_true",
                    help="actually deliver via GHL (canary gate applies)")

    pi = sub.add_parser("inbound", help="poll + classify inbound replies")
    pi.add_argument("--poll", action="store_true")
    pi.add_argument("--send", action="store_true",
                    help="write answers + deliver confirmations (gated)")

    pk = sub.add_parser("canary", help="seed + message the canary contact only")
    pk.add_argument("--phone", required=True)
    pk.add_argument("--email", required=True)
    pk.add_argument("--channel", choices=("sms", "email"), default="sms")

    args = ap.parse_args()
    load_env()
    need = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    if args.cmd != "status":
        need += ["ANTHROPIC_API_KEY", "GHL_API_KEY", "GHL_LOCATION_ID"]
    missing = [k for k in need if not os.environ.get(k)]
    if missing:
        print(f"ERROR: missing env: {', '.join(missing)}", file=sys.stderr)
        return 1
    if args.cmd != "status" and not os.environ.get("CONCIERGE_FROM_NUMBER", "").strip():
        print("!! WARNING: CONCIERGE_FROM_NUMBER is not set. SMS sends would "
              "go out on GHL's default number — the 805 local, which is "
              "Santino's personal thread. Set CONCIERGE_FROM_NUMBER="
              "+18556484464 (the toll-free) before any real send.",
              file=sys.stderr)
    return {"status": cmd_status, "compose": cmd_compose,
            "inbound": cmd_inbound, "canary": cmd_canary}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
