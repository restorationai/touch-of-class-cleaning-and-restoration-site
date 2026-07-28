#!/usr/bin/env python3
"""Client Concierge (phase 1) — agentic follow-up on what clients owe us.

Complements client_ops_sync.py: that script watches for answers arriving in
the app; THIS script goes and gets them. It knows every client's outstanding
asks (pending `client_intake_items` + planned `client_input` rows in
`marketing_action_plan`), drafts one warm consolidated SMS/email via Claude,
sends through GoHighLevel, understands the replies, and writes matched
answers back into `client_intake_items` (status=answered, answer={"value":…},
answered_at) so the EXISTING client_ops_sync handlers apply them downstream.

CONVERSATION-HISTORY AWARENESS
    Every compose/classify decision is grounded in the contact's real GHL
    conversation history (fetch_history: all conversations merged, newest
    first, normalized to sms/email/call/other; calls shown as "[phone call]",
    email bodies trimmed to ~500 chars). Compose mirrors the client's texting
    tone, never re-asks something the history shows they already answered
    (those items are excluded and escalated as "history suggests already
    answered: …"), and never talks over a human: if the newest OUTBOUND
    message in the thread was not sent by the concierge (sent message ids are
    tracked in the state file — any outbound we didn't send = a human, e.g.
    Santino, incl. calls) and is <12h old, the nudge is skipped for the cycle
    ("recent human conversation — deferred"). Inbound classification receives
    the last ~10 history messages as context so short replies like "yes" or
    "the second one" disambiguate correctly.

MEETING-INTEL AWARENESS
    clients/_ops/meeting-intel/{slug}.md holds internal notes from client
    meetings. One file may cover several companies (sister companies sharing
    an owner), so compose + inbound load the company's own file PLUS any
    intel file whose text mentions the company's id or name. The notes go to
    Claude with hard rules: items the intel marks ANSWERED / in progress on
    the client's side are EXCLUDED from nudges and escalated ("meeting intel
    says answered/in progress: …") so a human backfills the DB; the intel may
    shape phrasing naturally ("Great meeting with the team on Tuesday") but
    private discussion details are never quoted back to the client.

Subcommands
    status                       Table of every tracked client: pending intake
                                 count, open client_input asks, last concierge
                                 contact, nudges used, next eligible date,
                                 resolved business-hours timezone + source,
                                 history (message count + days since last
                                 exchange; needs GHL env, else "-").
    compose --company CO-…       Draft ONE consolidated message for a client
        [--channel sms|email]    (max 3 items, highest priority first, always
        [--send]                 ends with the reply-first + self-serve close).
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
    - business hours only: 9:00-18:00 in the CLIENT'S local timezone,
      resolved in order: (a) the GHL contact's timezone field, (b)
      companies.timezone, (c) inferred from the state in the client's
      clients/{slug}/plan-input.json (primary service area), (d)
      America/Los_Angeles with a loud warning. Enforced on EVERY send path
      (compose --send, inbound auto-replies); the canary is exempt. Outside
      the window the send is refused and flagged "outside business hours —
      will send after 9am {tz}" (phase 1: refuse + flag; queueing later).

State: clients/_ops/concierge-state.json — per-company contact bookkeeping
(ghl_contact_id, last_contacted, nudge_count) + the inbound message cursor
+ sent_message_ids (every GHL message id the concierge itself delivered —
the ground truth for "was that outbound one of ours or a human?").
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

Messaging target: the PREFERRED entry of integration_settings.contacts
(array of {role owner|office, first_name, last_name, cell, email, title?,
ghl_contact_id?, preferred} written by the app's onboarding wizard + Contact
Card; exactly one preferred). Fallbacks, in order: the legacy
owner_first_name/owner_last_name/owner_cell keys, then the top-level
integration_settings.ghl_contact_id linkage (written by scripts/ghl_link.py
and the ghl-sync-contact edge fn), then full-text search — every fallback
resolution is flagged loudly in the output. When the preferred contact is
the OFFICE contact (not the owner), the first-contact intro says we help
"collect what's needed to finish {Company}'s setup" instead of implying we
run their account.

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
import hashlib
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
MEETING_INTEL_DIR = OPS_DIR / "meeting-intel"
COMPANY_MAP_PATH = ROOT / "clients" / "company_map.json"

GHL_BASE = "https://services.leadconnectorhq.com"
GHL_VERSION = "2021-07-28"
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-5"
UA = "rank-ai-client-concierge/1.0"

# Client-facing persona (Santino 2026-07-13): a named human assistant, and
# NEVER em/en dashes in client copy (they read as AI tells).
ASSISTANT_NAME = os.environ.get("CONCIERGE_ASSISTANT_NAME", "Monica")
# Client-facing company name: Restoration AI is the company (matches every
# link we send: app/setup@/upload links on restorationai.io); "Rank AI" is
# the product and stays in sales materials only. Swap here on any rebrand.
BRAND_NAME = os.environ.get("CONCIERGE_BRAND_NAME", "Restoration AI")

# Required closing pattern (Santino's copy): reply-first, then self-serve.
# No standing closer line — messages end after the last ask (2026-07-22,
# Santino: "purely conversational, slightly informal").
APP_SETUP_LINK = "https://app.restorationai.io/?setup=1"   # auto-opens the guide
INTRO_TEMPLATE = ("Hi {first}, this is {name} with Santino's team at "
                  "{brand}. I help get everything set up for your account.")
# Preferred contact is the office/day-to-day person, not the owner: don't
# imply it's "their" account — we're collecting what finishes the setup.
INTRO_TEMPLATE_OFFICE = ("Hi {first}, this is {name} with Santino's team "
                         "at {brand}. I help collect what's needed to "
                         "finish {company}'s setup.")
SMS_MAX_CHARS = 450
SMS_MAX_CHARS_FIRST = 550   # first-ever message carries the intro line
MAX_ITEMS_PER_MESSAGE = 2
# A first text from an unknown number must feel like a person saying hi with
# one small favor to ask — never a checklist. Follow-ups may carry two.
FIRST_CONTACT_MAX_ITEMS = 1
MIN_DAYS_BETWEEN_SENDS = 3
HISTORY_MAX_MSGS = 25          # default fetch_history depth for compose/status
CLASSIFY_HISTORY_MSGS = 10     # history context given to inbound classification
HISTORY_EMAIL_TRIM = 500       # chars kept per email body (threads get long)
HUMAN_DEFER_HOURS = 12         # human outbound newer than this => skip nudge
MAX_NUDGES = 4
# Ops ping: every escalation also fires ONE summary SMS to Santino's cell so
# a human hears about it without reading concierge-escalations.md. The 805
# company number is the GHL location's own number and can't receive sends
# from its own location — the ping goes to the ops cell via the toll-free,
# which still lands the thread in GHL where the team can see it.
OPS_PING_CELL = os.environ.get("CONCIERGE_OPS_CELL", "+18089891078")
OPS_PING_CONTACT_ID = os.environ.get("CONCIERGE_OPS_CONTACT_ID",
                                     "MIJ5Jm4sobdzSRtnYSzU")  # Santino Velci
OPS_PING_DEDUPE_HOURS = 24
_OPS_PINGS: list = []          # (company name, reason) accumulated per run
BUSINESS_HOUR_START = 9
BUSINESS_HOUR_END = 18
DEFAULT_TZ = "America/Los_Angeles"

# US state -> IANA timezone, for inferring a client's business-hours zone
# from clients/{slug}/plan-input.json when GHL and companies.timezone are
# both empty. States that straddle zones get their dominant zone.
US_STATE_TZ = {
    # Pacific
    "WA": "America/Los_Angeles", "OR": "America/Los_Angeles",
    "CA": "America/Los_Angeles", "NV": "America/Los_Angeles",
    # Mountain (AZ observes no DST -> Phoenix)
    "UT": "America/Denver", "CO": "America/Denver", "MT": "America/Denver",
    "ID": "America/Denver", "WY": "America/Denver", "NM": "America/Denver",
    "AZ": "America/Phoenix",
    # Central
    "TX": "America/Chicago", "AL": "America/Chicago", "TN": "America/Chicago",
    "OK": "America/Chicago", "LA": "America/Chicago", "MS": "America/Chicago",
    "AR": "America/Chicago", "MO": "America/Chicago", "IA": "America/Chicago",
    "MN": "America/Chicago", "WI": "America/Chicago", "IL": "America/Chicago",
    "KS": "America/Chicago", "NE": "America/Chicago", "ND": "America/Chicago",
    "SD": "America/Chicago",
    # Eastern
    "PA": "America/New_York", "NJ": "America/New_York",
    "SC": "America/New_York", "NY": "America/New_York",
    "FL": "America/New_York", "GA": "America/New_York",
    "NC": "America/New_York", "VA": "America/New_York",
    "WV": "America/New_York", "OH": "America/New_York",
    "MI": "America/New_York", "IN": "America/New_York",
    "KY": "America/New_York", "MD": "America/New_York",
    "DE": "America/New_York", "CT": "America/New_York",
    "RI": "America/New_York", "MA": "America/New_York",
    "VT": "America/New_York", "NH": "America/New_York",
    "ME": "America/New_York", "DC": "America/New_York",
    # Non-contiguous
    "HI": "Pacific/Honolulu", "AK": "America/Anchorage",
}

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


def kv_get(k: str):
    from urllib.parse import quote
    rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{quote(k)}&select=v")
    return rows[0]["v"] if rows else None


def kv_set(k: str, v) -> None:
    _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
        {"k": k, "v": v, "updated_at": datetime.now(timezone.utc).isoformat()},
        prefer="resolution=merge-duplicates,return=minimal")


def kv_prefix(prefix: str) -> dict:
    from urllib.parse import quote
    rows = _sb("GET", f"/rest/v1/ops_kv?k=like.{quote(prefix)}*&select=k,v")
    return {r["k"]: r["v"] for r in (rows or [])}


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


def anthropic_json(system: str, user: str, *, max_tokens: int = 4000) -> dict:
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
    state = kv_get("concierge-state")
    if state is None and STATE_PATH.exists():   # one-time seed from pre-kv file
        state = json.loads(STATE_PATH.read_text())
    if state is None:
        state = {"inbound_cursor": None, "companies": {}}
    state.setdefault("sent_message_ids", [])
    state.setdefault("companies", {})
    return state


def save_state(state: dict, dry_run: bool) -> None:
    if dry_run:
        print("  [dry-run] state not written")
        return
    kv_set("concierge-state", state)


def company_state(state: dict, company_id: str) -> dict:
    return state["companies"].setdefault(company_id, {
        "ghl_contact_id": None, "last_contacted": None, "first_contacted": None,
        "nudge_count": 0, "last_channel": None})


def sent_message_ids(state: dict) -> set[str]:
    return {i for i in state.get("sent_message_ids", []) if i}


def record_sent_message(state: dict, result: dict | None) -> None:
    """Track the GHL id(s) of a message WE just delivered.

    This is the ground truth for the human-conversation check: any outbound
    message in a thread whose id is NOT in state.sent_message_ids was sent by
    a human (Santino / the app's automations acting as him), not the
    concierge. Empty until the first real send by design."""
    ids = state.setdefault("sent_message_ids", [])
    for key in ("messageId", "emailMessageId"):
        mid = (result or {}).get(key)
        if mid and mid not in ids:
            ids.append(mid)


# ---------------------------------------------------------------- history
def fetch_history(contact_id: str, max_msgs: int = HISTORY_MAX_MSGS) -> list[dict]:
    """The contact's full cross-conversation message history, newest first.

    Pulls every conversation for the contact, merges the messages and
    normalizes each to {id, when: datetime, direction: "in"|"out",
    channel: "sms"|"email"|"call"|"other", body}. Calls carry no body and are
    represented as "[phone call]"; email bodies are trimmed to the first
    ~HISTORY_EMAIL_TRIM chars (reply threads get enormous). TYPE_ACTIVITY_*
    rows (opportunity/appointment system events) are dropped — they are not
    messages anyone wrote."""
    convs = _ghl("GET", "/conversations/search", params={
        "locationId": _loc(), "contactId": contact_id, "limit": 20})
    merged: list[dict] = []
    for conv in convs.get("conversations", []) or []:
        data = _ghl("GET", f"/conversations/{conv['id']}/messages",
                    params={"limit": max(50, max_msgs * 2)})
        for msg in (data.get("messages") or {}).get("messages", []) or []:
            mtype = msg.get("messageType") or ""
            if mtype.startswith("TYPE_ACTIVITY"):
                continue
            try:
                when = datetime.fromisoformat(
                    (msg.get("dateAdded") or "").replace("Z", "+00:00"))
            except ValueError:
                continue
            channel = {"TYPE_SMS": "sms", "TYPE_EMAIL": "email",
                       "TYPE_CALL": "call"}.get(mtype, "other")
            body = (msg.get("body") or "").strip()
            if channel == "call":
                body = "[phone call]"
            elif channel == "email":
                body = body[:HISTORY_EMAIL_TRIM]
            n_att = len(msg.get("attachments") or [])
            if n_att:
                # photo-only MMS must be visible in history or the composer
                # re-asks for photos the client already texted (Jeff, 07-22)
                tag = f"[sent {n_att} photo/video attachment(s)]"
                body = f"{body} {tag}".strip() if body else tag
            if not body:
                continue
            merged.append({
                "id": msg.get("id"), "when": when,
                "direction": "in" if msg.get("direction") == "inbound" else "out",
                "channel": channel, "body": body})
    merged.sort(key=lambda m: m["when"], reverse=True)
    return merged[:max_msgs]


def format_history(history: list[dict]) -> str:
    """Prompt-ready rendering, newest first ('them' = the client, 'us' = our side)."""
    return "\n".join(
        f"{m['when'].strftime('%Y-%m-%d %H:%M')} "
        f"{'them' if m['direction'] == 'in' else 'us'} ({m['channel']}): {m['body']}"
        for m in history)


def human_conversation_deferral(history: list[dict], state: dict) -> str | None:
    """Reason to skip this cycle's nudge, or None.

    If the newest OUTBOUND message in the thread was not sent by the
    concierge (its id is not in state.sent_message_ids — so a human wrote it
    or made the call) and it is < HUMAN_DEFER_HOURS old, the concierge stays
    quiet: never talk over Santino mid-conversation."""
    ours = sent_message_ids(state)
    last_out = next((m for m in history if m["direction"] == "out"), None)
    if not last_out or (last_out["id"] and last_out["id"] in ours):
        return None
    age = datetime.now(timezone.utc) - last_out["when"]
    if age < timedelta(hours=HUMAN_DEFER_HOURS):
        return ("recent human conversation — deferred (human outbound "
                f"{last_out['channel']} at "
                f"{last_out['when'].strftime('%Y-%m-%d %H:%M UTC')}, "
                f"{age.total_seconds() / 3600:.1f}h ago, within the "
                f"{HUMAN_DEFER_HOURS}h defer window)")
    return None


# ---------------------------------------------------------------- timezone
def _valid_tz(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


def company_slug(company_id: str) -> str | None:
    """Reverse lookup in clients/company_map.json (slug -> CO-… id)."""
    try:
        cmap = json.loads(COMPANY_MAP_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    for slug, cid in cmap.items():
        if cid == company_id:
            return slug
    return None


def plan_input_state(slug: str) -> str | None:
    """US state of the client's primary service area (plan-input.json)."""
    path = ROOT / "clients" / slug / "plan-input.json"
    if not path.exists():
        return None
    try:
        plan = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    areas = [a for a in (plan.get("service_areas") or []) if isinstance(a, dict)]
    primary = next((a for a in areas if a.get("primary")),
                   areas[0] if areas else None)
    state = (((primary or {}).get("state")
              or (plan.get("brand") or {}).get("state") or "")).strip().upper()
    return state or None


def resolve_timezone(company: dict, contact: dict | None = None) -> tuple[str, str]:
    """The client's business-hours timezone as (IANA key, source).

    Resolution order:
      (a) the GHL contact's own timezone field (timezone / timezoneId),
      (b) companies.timezone,
      (c) inferred from the client's business location — the state of the
          primary service area in clients/{slug}/plan-input.json,
      (d) DEFAULT_TZ with a loud warning (business hours may be wrong).
    """
    cand = str((contact or {}).get("timezone")
               or (contact or {}).get("timezoneId") or "").strip()
    if cand and _valid_tz(cand):
        return cand, "ghl-contact"
    cand = str(company.get("timezone") or "").strip()
    if cand and _valid_tz(cand):
        return cand, "companies.timezone"
    slug = company_slug(company.get("id") or "")
    if slug:
        state = plan_input_state(slug)
        if state and state in US_STATE_TZ:
            return US_STATE_TZ[state], f"plan-input:{state}"
    print(f"  WARNING: could not resolve a timezone for "
          f"{company.get('name', '?')} ({company.get('id', '?')}) — no GHL "
          f"contact timezone, no companies.timezone, no plan-input state. "
          f"Defaulting to {DEFAULT_TZ}; business-hours enforcement may be "
          f"wrong for this client.", file=sys.stderr)
    return DEFAULT_TZ, "DEFAULT-unresolved"


def business_hours_check(company: dict, contact: dict | None = None) -> str | None:
    """Refusal reason when now is outside the client's 9:00-18:00 local
    window, or None if a send is allowed. Phase 1: refuse + flag (no queue)."""
    tz_key, source = resolve_timezone(company, contact)
    local = datetime.now(timezone.utc).astimezone(ZoneInfo(tz_key))
    if not (BUSINESS_HOUR_START <= local.hour < BUSINESS_HOUR_END):
        return (f"outside business hours — will send after "
                f"{BUSINESS_HOUR_START}am {tz_key} (local now "
                f"{local.strftime('%H:%M')}, tz via {source})")
    return None


# ---------------------------------------------------------------- meeting intel
def load_meeting_intel(company: dict) -> str | None:
    """Meeting-intel notes relevant to this company, or None.

    Loads clients/_ops/meeting-intel/{slug}.md for the company's own slug,
    PLUS any other intel file whose text mentions the company's id or name —
    one meeting often covers sister companies sharing an owner (they may
    even share integration_settings.ghl_contact_id), and the notes live in
    just one of the slugs' files."""
    docs: dict[str, str] = {}
    if MEETING_INTEL_DIR.exists():
        for path in sorted(MEETING_INTEL_DIR.glob("*.md")):
            try:
                docs[path.stem] = path.read_text()
            except OSError:
                pass
    try:
        for k, v in kv_prefix("meeting-intel/").items():
            key = k.split("/", 1)[1]
            content = v.get("content", "") if isinstance(v, dict) else str(v)
            docs[key] = (docs.get(key, "") + "\n" + content).strip() \
                if key in docs else content
    except Exception as e:  # kv down must not kill compose
        print(f"  [intel] kv fetch failed: {e}", file=sys.stderr)
    if not docs:
        return None
    slug = company_slug(company.get("id") or "")
    cid = (company.get("id") or "").strip().lower()
    name = (company.get("name") or "").strip().lower()
    # "core" name without legal boilerplate, so "ProRestoration Services"
    # still matches a note that just says "ProRestoration".
    core = re.sub(r"\b(inc|llc|corp|co|company|services?)\b\.?", "", name).strip()
    parts: list[str] = []
    for key in sorted(docs):
        text = docs[key].strip()
        low = text.lower()
        hit = ((slug and key == slug)
               or (cid and cid in low)
               or (name and name in low)
               or (len(core) >= 5 and core in low))
        if hit and text:
            parts.append(f"[{key}]\n{text}")
    return "\n\n".join(parts) or None


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
    """Durable top-level linkage (ghl_link.py / ghl-sync-contact edge fn)."""
    return ((company.get("integration_settings") or {}).get("ghl_contact_id")
            or None)


def preferred_contact_entry(company: dict) -> dict | None:
    """The preferred entry of integration_settings.contacts, or None.

    The app guarantees exactly one preferred=true; be defensive anyway:
    preferred -> owner -> first entry.
    """
    contacts = (company.get("integration_settings") or {}).get("contacts")
    if not isinstance(contacts, list):
        return None
    entries = [c for c in contacts if isinstance(c, dict)
               and ((c.get("first_name") or "").strip()
                    or (c.get("cell") or "").strip()
                    or (c.get("email") or "").strip())]
    if not entries:
        return None
    return (next((c for c in entries if c.get("preferred")), None)
            or next((c for c in entries if c.get("role") == "owner"), None)
            or entries[0])


def messaging_target(company: dict) -> dict:
    """WHO we message for this company.

    Order: (1) integration_settings.contacts preferred entry, (2) the legacy
    owner_first_name/owner_last_name/owner_cell keys, (3) the company row
    itself (account_owner_name / phone / email).
    Returns {role, first_name, last_name, cell, email, ghl_contact_id, source}.
    """
    settings = company.get("integration_settings") or {}
    pref = preferred_contact_entry(company)
    if pref:
        return {
            "role": pref.get("role") or "owner",
            "first_name": (pref.get("first_name") or "").strip(),
            "last_name": (pref.get("last_name") or "").strip(),
            "cell": (pref.get("cell") or "").strip(),
            "email": (pref.get("email") or "").strip(),
            "ghl_contact_id": pref.get("ghl_contact_id") or None,
            "source": "contacts[] preferred",
        }
    owner_parts = (company.get("account_owner_name") or "").strip().split()
    first = (settings.get("owner_first_name") or "").strip() or (owner_parts[0] if owner_parts else "")
    last = ((settings.get("owner_last_name") or "").strip()
            or " ".join(owner_parts[1:]))
    if (settings.get("owner_first_name") or settings.get("owner_cell")):
        source = "legacy owner_* keys"
    else:
        source = "company row"
    return {
        "role": "owner",
        "first_name": first,
        "last_name": last,
        "cell": (settings.get("owner_cell") or "").strip() or (company.get("phone") or ""),
        "email": (company.get("email") or "").strip(),
        "ghl_contact_id": None,  # per-entry id only lives in contacts[]
        "source": source,
    }


def target_label(company: dict) -> str:
    """'Jane Smith (owner)' — for status output / compose logs."""
    t = messaging_target(company)
    name = " ".join(x for x in (t["first_name"], t["last_name"]) if x) or "?"
    return f"{name} ({t['role']})"


def resolve_contact(company: dict) -> dict | None:
    """Find the messaging target's GHL contact.

    Order: (1) the preferred contacts[] entry's own ghl_contact_id, (2) the
    durable top-level integration_settings.ghl_contact_id linkage, (3)
    full-text search fallback by the target's email/cell, then company
    email, phone, name — flagged LOUDLY because search matches are
    best-effort guesses.
    """
    target = messaging_target(company)

    def fetch(cid: str, what: str) -> dict | None:
        try:
            data = _ghl("GET", f"/contacts/{cid}")
            contact = (data or {}).get("contact") or data
            if contact and contact.get("id"):
                return contact
            print(f"  WARNING: {what} {cid} returned no record — "
                  "falling back", file=sys.stderr)
        except RuntimeError as e:
            print(f"  WARNING: {what} {cid} lookup failed ({e}) — "
                  "falling back", file=sys.stderr)
        return None

    if target.get("ghl_contact_id"):
        contact = fetch(target["ghl_contact_id"], "preferred contact's GHL id")
        if contact:
            return contact
    cid = linked_contact_id(company)
    if cid and cid != target.get("ghl_contact_id"):
        contact = fetch(cid, "linked GHL contact")
        if contact:
            if target["source"] == "contacts[] preferred":
                print(f"  WARNING: preferred contact entry has no working "
                      f"ghl_contact_id — using the top-level linkage {cid} "
                      f"(the OWNER's). Re-save the Contact Card in the app "
                      f"to sync + link the preferred contact.", file=sys.stderr)
            return contact
    queries = [target.get("email"), target.get("cell"),
               company.get("email"), company.get("phone"), company.get("name")]
    seen: set[str] = set()
    for query in queries:
        q = str(query or "").strip()
        if not q or q in seen:
            continue
        seen.add(q)
        data = _ghl("GET", "/contacts/", params={
            "locationId": _loc(), "query": q, "limit": 5})
        contacts = data.get("contacts") or []
        if contacts:
            print(f"  WARNING: {company.get('id')} has NO working GHL "
                  f"linkage — resolved {contacts[0]['id']} via search "
                  f"fallback ({q!r}). Run scripts/ghl_link.py (or re-save "
                  f"the Contact Card in the app) to link durably.",
                  file=sys.stderr)
            return contacts[0]
    return None


def contact_first_name(contact: dict | None, company: dict) -> str:
    # The preferred contact's own first name wins (they told us who to talk
    # to); the GHL record and company row are fallbacks.
    target = messaging_target(company)
    if target.get("first_name"):
        return target["first_name"].title()
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


def cadence_check(cs: dict, company: dict, contact: dict | None = None,
                  enforce_hours: bool = True) -> str | None:
    """Return a human-readable refusal reason, or None if a send is allowed now.

    Business hours run in the client's OWN timezone (resolve_timezone: GHL
    contact -> companies.timezone -> plan-input state -> default+warning) and
    are enforced on every send path; the canary passes enforce_hours=False."""
    if cs.get("nudge_count", 0) >= MAX_NUDGES:
        return f"max {MAX_NUDGES} nudges reached — ESCALATE to Santino"
    ne = next_eligible(cs)
    now = datetime.now(timezone.utc)
    if ne and now < ne:
        return f"cooldown — next eligible {ne.strftime('%Y-%m-%d %H:%M UTC')}"
    if enforce_hours:
        reason = business_hours_check(company, contact)
        if reason:
            return reason
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

    body = re.sub(r"\s*[\u2014\u2013]\s*", ", ", body)  # no em/en dashes ever
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
        payload["subject"] = subject or f"Your {BRAND_NAME} setup"
        payload["html"] = body.replace("\n", "<br>")
    result = _ghl("POST", "/conversations/messages", body=payload)
    print(f"  SENT {channel} to {recipient} (contact {contact['id']})")
    return result or {}


# ---------------------------------------------------------------- compose
COMPOSE_SYSTEM = """\
You are Monica, an assistant on "Santino's team at Restoration AI" (the
client's marketing/website team; never say "Rank AI", that is an internal
product name), writing short follow-up texts to home-services business
owners. You sound like a real person, never like software. NEVER
use em dashes or en dashes anywhere in the message; use a comma, a period,
or the word "and" instead. Voice: warm,
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

NOTHING IS EVER REQUIRED FOR A CALL. Never present asks as things to have
ready "before the call", "for the kickoff", or "to make it quick" — clients
hear homework, feel behind, and RESCHEDULE the call to buy time (it happened
twice in one week). If an upcoming call is mentioned, say plainly that nothing
is needed for it and we get everything set up together on the call. Asks stand
alone on their own timeline, never as prerequisites for a meeting.

KEEP IT SMALL — the second most important rule. A text that asks for a lot,
or asks in long dense sentences, gets ignored or scares people off.
- The character budget is a CEILING, not a target. Shorter always wins.
- One short sentence of context per ask, then the ask itself. Never explain
  our process or why our systems need something.
- Shrink every ask to its minimum viable version and SAY that the minimum is
  fine: "even 5 names is plenty", "a couple phone photos work great",
  "whatever you have handy". They can always send more later.
- Never ask for structured data ("name, phone, email, and job type for
  each") in a text. Ask for the simple human version ("a handful of past
  customers who'd leave you a review, names and numbers is perfect") and let
  us sort out the details on our side.
- One thing per sentence. If the message reads like a to-do list or a form,
  rewrite it.

Rules:
- Cover AT MOST the items given (they are already priority-ordered). Weave
  them in conversationally — short sentences or a compact list, not a form.
- Never invent items, prices, or deadlines. Never promise work.
- CLOSING: end the message right after the last ask. NO closing line of any
  kind — never "just reply here", never "I'll add it all in for you", never
  an email address tacked on the end. Replying is obvious. The ONLY
  exceptions, woven in naturally mid-sentence rather than appended:
    * an actual FILE or DOCUMENT (spreadsheet, PDF, insurance certificate)
      that can't travel by text -> "you can email it to
      setup@restorationai.io"
    * PHOTOS or FILES when the company has a hub link (provided in context
      as photo_upload_link) -> "easiest way: {photo_upload_link} — tap
      Upload Job Photos and add them right from your phone"
- OPENERS: no filler. Never "quick question", "two quick ones", "a couple
  quick things", "just checking in", "hope you're well", "touching base".
  Anchor to the real subject instead: "Hey Jack, regarding your website,
  should we say…". Slightly informal, like a competent coworker texting.
- SMS: total body within the character budget given. If space is tight, cut
  an item, not words mid-thought. No subject, no links other than the ones
  the rules above allow.
- Email: give a short subject (<= 60 chars) and a slightly fuller body
  (still under ~140 words), sign off as "Monica, Santino's team at
  Restoration AI" (no dashes).

HISTORY RULES (apply when a "Recent conversation history" block is provided):
- Match the tone and formality of the prior successful exchanges with this
  person — mirror how they text. Short casual texter gets short casual
  sentences; formal emailer gets fuller sentences. Same warmth either way.
- NEVER re-ask something the history shows they already answered. If the
  history contains an apparent answer to one of the outstanding items, leave
  that item OUT of the message body entirely and report it in
  "history_answered" with the item id and a one-line paraphrased summary of
  the evidence (never a verbatim quote of their message).
- Reference recent context naturally when it genuinely helps ("Great talking
  to you last week about the site") — but never quote private history
  verbatim and never recite details back at them.

- RECENCY RULE — conversation history OUTRANKS meeting intel and outstanding
  item descriptions whenever they conflict, because history is newer. If a
  history message contradicts a fact in the intel or an item's rationale
  (e.g. intel says "awaiting Google's decision" but the client texted that
  it already came through), TRUST THE HISTORY: do not repeat the stale fact,
  acknowledge the newer state naturally ("Congrats on getting the listing
  back!"), and report it in "history_answered" as stale-intel so a human
  updates the records.

MEETING INTEL RULES (apply when a "Meeting intel" block is provided):
- ITEM SELECTION IS A HARD FILTER — apply it BEFORE writing anything:
  (1) If the intel contains explicit concierge guidance about what to ask or
      not ask (e.g. "remaining asks = X only", "wait before nudging about
      Y"), OBEY IT EXACTLY: any outstanding item the guidance rules out must
      not appear in the body, even if it looks otherwise askable.
  (2) Any item the intel marks as ANSWERED / resolved / handled on a call,
      or as IN PROGRESS on the client's side (they're chasing it with a
      third party), must be left OUT of the body — never nudge for something
      already answered or in motion.
  Report every filtered item in "intel_resolved" with its item id and a
  one-line reason. These exclusions override every other instruction about
  covering the items.
- The intel is our team's INTERNAL notes. Never quote it and never recite
  private discussion details back to the client.
- Use the intel for natural phrasing context — when it shows a recent
  meeting or call with the client's team, DO acknowledge it warmly in one
  short clause right after the greeting/intro ("Great meeting with the team
  on Tuesday…" adjusted to the actual day). Reference that the meeting
  happened and its tone, never what was privately discussed.

Return ONLY a JSON object:
{"subject": string|null, "body": string,
 "history_answered": [{"item_id": string, "evidence": string}],
 "intel_resolved": [{"item_id": string, "reason": string}]}
"history_answered" is [] when nothing in the history answers an item;
"intel_resolved" is [] when no meeting intel excludes an item. If EVERY item
ends up excluded (history + intel), return "body": "" — there is nothing
worth nudging about this cycle.
Keep drafting deterministic: choose the most natural single phrasing, no
alternatives or commentary."""


def gbp_photo_count(company: dict) -> int | None:
    """Total photos on the client's GBP (via their connected Google token),
    cached in kv for 7 days. None = unknown (not connected / API failure)."""
    cid = company.get("id") or ""
    cache = kv_get(f"gbp-photo-count/{cid}")
    if cache and (datetime.now(timezone.utc)
                  - datetime.fromisoformat(cache["at"])).days < 7:
        return cache["count"]
    rows = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
               "&provider=eq.google&select=connection_metadata")
    meta = (rows or [{}])[0].get("connection_metadata") or {}
    refresh = meta.get("refresh_token")
    if not refresh:
        return None
    try:
        tok = requests.post("https://oauth2.googleapis.com/token", data={
            "refresh_token": refresh,
            "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
            "grant_type": "refresh_token"}, timeout=30).json()["access_token"]
        H = {"Authorization": f"Bearer {tok}"}
        total = 0
        accts = requests.get(
            "https://mybusinessaccountmanagement.googleapis.com/v1/accounts",
            headers=H, timeout=30).json().get("accounts", [])
        for a in accts:
            locs = requests.get(
                "https://mybusinessbusinessinformation.googleapis.com/v1/"
                f"{a['name']}/locations?readMask=name&pageSize=100",
                headers=H, timeout=30).json().get("locations", [])
            for l in locs:
                media = requests.get(
                    f"https://mybusiness.googleapis.com/v4/{a['name']}/"
                    f"{l['name']}/media", headers=H, timeout=30).json()
                total += int(media.get("totalMediaItemCount",
                                       len(media.get("mediaItems", []))))
        kv_set(f"gbp-photo-count/{cid}",
               {"count": total, "at": datetime.now(timezone.utc).isoformat()})
        return total
    except Exception as e:
        print(f"  [gbp-photos] count failed: {e}", file=sys.stderr)
        return None


_COMPANY_SLUGS: dict | None = None


def photo_upload_link(company: dict) -> str | None:
    """The client's hub link (integration_settings.hub_url, written by
    bootstrap). One link for everything — photos, files, reviews. Never hand
    out the raw /gbpphotos/ URL in messages (2026-07-22 decision)."""
    settings = company.get("integration_settings") or {}
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except ValueError:
            settings = {}
    return settings.get("hub_url") or None


GHL_LOCATION_TZ = "America/Los_Angeles"  # GHL returns naive local times


def fetch_upcoming_appointments(contact_id: str, client_tz: str) -> str | None:
    """Human-readable block of the contact's upcoming GHL appointments,
    rendered in the CLIENT's local time. Live calendar data — compose is told
    to trust this over meeting-intel dates."""
    from zoneinfo import ZoneInfo
    try:
        data = _ghl("GET", f"/contacts/{contact_id}/appointments") or {}
    except RuntimeError as e:
        print(f"  [appointments] fetch failed: {e}", file=sys.stderr)
        return None
    now = datetime.now(timezone.utc)
    lines = []
    for ev in data.get("events", []) or []:
        if ev.get("deleted"):
            continue
        status = (ev.get("appointmentStatus") or "").lower()
        if status in ("cancelled", "noshow", "invalid"):
            continue
        try:
            start = datetime.strptime(ev["startTime"], "%Y-%m-%d %H:%M:%S")
            start = start.replace(tzinfo=ZoneInfo(GHL_LOCATION_TZ))
        except (KeyError, ValueError):
            continue
        if start < now or (start - now).days > 30:
            continue
        local = start.astimezone(ZoneInfo(client_tz))
        lines.append(f"- {local.strftime('%A %b %-d, %-I:%M %p')} "
                     f"(their local time): {ev.get('title', 'appointment')}"
                     f" [{status or 'booked'}]")
    return "\n".join(lines) if lines else None


def compose_draft(company: dict, first_name: str, items: list[dict],
                  channel: str, first_contact: bool,
                  history: list[dict] | None = None,
                  intel: str | None = None,
                  appointments: str | None = None,
                  sister_names: list[str] | None = None) -> dict:
    chosen = items[:FIRST_CONTACT_MAX_ITEMS if first_contact
                   else MAX_ITEMS_PER_MESSAGE]
    lines = []
    for i, it in enumerate(chosen, 1):
        detail = (it["detail"] or "")[:300]
        lines.append(f"{i}. id={it['id']} [{it['kind']}] {it['text']}"
                     + (f" — context: {detail}" if detail else ""))
    sms_budget = SMS_MAX_CHARS_FIRST if first_contact else SMS_MAX_CHARS
    # Quote the model a smaller budget than we enforce: it drafts to the
    # ceiling, and the safety clip mid-sentence reads worse than a tighter
    # draft. The clip at sms_budget then almost never fires.
    stated_budget = sms_budget - 60
    # Office/day-to-day preferred contact gets the "finish {Company}'s setup"
    # intro — it's not their account, they're helping us finish the setup.
    if messaging_target(company).get("role") == "office":
        intro = INTRO_TEMPLATE_OFFICE.format(first=first_name,
                                             company=company["name"],
                                             name=ASSISTANT_NAME,
                                             brand=BRAND_NAME)
    else:
        intro = INTRO_TEMPLATE.format(first=first_name, name=ASSISTANT_NAME,
                                      brand=BRAND_NAME)
    history_block = ""
    if history:
        history_block = (
            "\nRecent conversation history with this person (newest first; "
            "'them' = the client, 'us' = anyone on our side):\n"
            + format_history(history) + "\n")
    intel_block = ""
    if intel:
        intel_block = (
            "\nMeeting intel (INTERNAL team notes — apply the MEETING INTEL "
            "RULES; never quote this to the client):\n" + intel + "\n")
    appt_block = ""
    if appointments:
        appt_block = (
            "\nUpcoming appointments (LIVE calendar — when referencing any "
            "call/meeting date, use THESE times, not the meeting intel; "
            "phrase relative to today, e.g. 'today at 12' / 'tomorrow'):\n"
            + appointments + "\n")
    # "Today" must be the CLIENT's calendar date — UTC rolls over at 5pm PT
    # and would make an evening compose reference "tomorrow" off by one.
    from zoneinfo import ZoneInfo
    tz_name, _tz_src = resolve_timezone(company, None)
    today = datetime.now(ZoneInfo(tz_name)).strftime(
        "%Y-%m-%d (%A), their local date")
    photo_link = photo_upload_link(company)
    photo_block = ""
    if photo_link:
        photo_block = (
            f"\nPhoto upload link for THIS client: {photo_link}\n"
            "Whenever you ask for photos, include that exact link as the way "
            "to send them (\"here's a link that uploads straight from your "
            "phone\"), and add that texting them here works too.\n")
        n_photos = gbp_photo_count(company)
        if n_photos is not None and n_photos >= 20:
            photo_block += (
                f"NOTE: this client's Google listing already has {n_photos} "
                "photos we can use — do NOT ask them for photos in this "
                "message; drop any photo request entirely.\n")
    sister_block = ""
    if sister_names:
        sister_block = (
            "\nNOTE: this person owns multiple companies we manage: "
            + company["name"].strip() + " plus " + ", ".join(sister_names)
            + ". The outstanding items below are prefixed with [Company Name]. "
            "Write ONE message that covers everything; when an item belongs to "
            "a different company than the main one, say naturally which company "
            "it's about (e.g. 'and for Pro Restoration, ...'). Never draft as if "
            "these were separate conversations.\n")
    user = (f"Client: {company['name']} (first name: {first_name})\n"
            f"Today's date: {today}\n"
            f"Channel: {channel} (character budget for SMS: {stated_budget})\n"
            f"FIRST CONTACT: {'yes' if first_contact else 'no'}\n"
            + sister_block
            + (f"Intro line to open with, exactly: \"{intro}\"\n"
               if first_contact else "")
            + history_block
            + intel_block
            + appt_block
            + photo_block
            + f"Outstanding items (priority order, cover all of these and "
            f"nothing else):\n" + "\n".join(lines))
    draft = anthropic_json(COMPOSE_SYSTEM, user)
    body = (draft.get("body") or "").strip()
    if channel == "sms" and len(body) > sms_budget:
        body = body[:sms_budget - 1].rsplit(" ", 1)[0] + "…"

    def _flags(key):
        return [f for f in (draft.get(key) or [])
                if isinstance(f, dict) and f.get("item_id")]

    return {"subject": (draft.get("subject") or None), "body": body,
            "items": chosen, "history_answered": _flags("history_answered"),
            "intel_resolved": _flags("intel_resolved")}


def _companies_with_items() -> list[str]:
    ids = {r["company_id"] for r in fetch_pending_intake()}
    ids |= {r["company_id"] for r in fetch_open_asks()}
    return sorted(i for i in ids if i)


def cmd_compose(args) -> int:
    if getattr(args, "all", False):
        # SAME-OWNER MERGE (Santino 2026-07-28): All Pro + ProRestoration share
        # one owner (Jack, one phone, one GHL contact) — composing per company
        # would text the same person twice back-to-back. Group companies by
        # their resolved messaging target; one merged message per human.
        cids = _companies_with_items()
        companies = fetch_companies(cids)
        groups: dict[str, list[str]] = {}
        for cid in cids:
            co = companies.get(cid)
            key = cid
            if co:
                t = messaging_target(co)
                key = (t.get("ghl_contact_id")
                       or re.sub(r"\D", "", t.get("cell") or "")
                       or (t.get("email") or "").lower() or cid)
            groups.setdefault(str(key), []).append(cid)
        rc = 0
        for group in groups.values():
            # primary = the company with the most outstanding items
            group = sorted(group, key=lambda c: -len(gather_items(c)))
            sub = argparse.Namespace(**{**vars(args), "all": False,
                                        "company": group[0],
                                        "merge_with": group[1:]})
            print(f"\n{'=' * 70}")
            if group[1:]:
                names = ", ".join((companies.get(c) or {}).get("name", c)
                                  for c in group)
                print(f"[same-owner merge] one message covers: {names}")
            rc = max(rc, cmd_compose(sub))
        return rc
    state = load_state()
    companies = fetch_companies([args.company])
    company = companies.get(args.company)
    if not company:
        print(f"ERROR: company {args.company} not found", file=sys.stderr)
        return 1
    items = gather_items(args.company)
    # Same-owner merge: fold sister companies' items into this compose, each
    # prefixed with its company name so the draft can attribute them.
    merge_with = [c for c in (getattr(args, "merge_with", None) or [])
                  if c and c != args.company]
    sister_names: list[str] = []
    if merge_with:
        sisters = fetch_companies(merge_with)
        for scid in merge_with:
            sco = sisters.get(scid)
            if not sco:
                continue
            s_items = gather_items(scid)
            if not s_items:
                continue
            sister_names.append((sco.get("name") or scid).strip())
            for it in s_items:
                it["text"] = "[{}] {}".format((sco.get("name") or scid).strip(),
                                              it["text"])
            items.extend(s_items)
        if sister_names:
            for it in items:
                if not str(it.get("text", "")).startswith("["):
                    it["text"] = "[{}] {}".format(company["name"].strip(), it["text"])
    if not items:
        print(f"{company['name']}: nothing outstanding — no message needed.")
        return 0
    contact = resolve_contact(company)
    first = contact_first_name(contact, company)
    cs = company_state(state, args.company)
    first_contact = not cs.get("first_contacted")
    print(f"Company: {company['name']} ({args.company})")
    target = messaging_target(company)
    print(f"Messaging target: {target_label(company)} — via {target['source']}")
    linked = target.get("ghl_contact_id") or linked_contact_id(company)
    print(f"GHL contact: "
          + (f"{contact['id']} ({contact.get('contactName')}, "
             f"{contact.get('phone')}, {contact.get('email')})" if contact
             else "NOT FOUND — compose only, send would fail")
          + ("" if linked else "  [NO DURABLE LINKAGE — search fallback]"))
    print(f"First contact: {'yes — intro line required' if first_contact else 'no'}")
    tz_key, tz_src = resolve_timezone(company, contact)
    print(f"Timezone: {tz_key} (via {tz_src})")
    cap = FIRST_CONTACT_MAX_ITEMS if first_contact else MAX_ITEMS_PER_MESSAGE
    print(f"Outstanding items: {len(items)} (messaging top {min(len(items), cap)})")
    intel = load_meeting_intel(company)
    print("Meeting intel: "
          + (f"loaded ({len(intel)} chars)" if intel else "none"))

    history = fetch_history(contact["id"]) if contact else []
    if history:
        newest = history[0]
        print(f"History: {len(history)} message(s), newest "
              f"{newest['when'].strftime('%Y-%m-%d %H:%M UTC')} "
              f"({newest['channel']}, "
              f"{'them' if newest['direction'] == 'in' else 'us'})")
    else:
        print("History: none found")

    # Never talk over a human: newest outbound not sent by the concierge and
    # <12h old means Santino (or someone on the team) is mid-conversation.
    defer_reason = human_conversation_deferral(history, state)
    if defer_reason:
        print(f"\nDEFERRED: {defer_reason}")
        append_escalation(company, None, defer_reason, dry_run=not args.send,
                          ping=False)
        if args.send:
            print("[nudge skipped this cycle — no draft, no send]")
            return 0
        print("[dry run: a real cycle would SKIP here — drafting anyway for "
              "inspection]")

    if args.send:
        gate = cadence_check(cs, company, contact)
        if gate:
            print(f"[gated, no draft: {gate}]")
            if "ESCALATE" in gate and not cs.get("max_nudges_escalated"):
                append_escalation(company, None,
                                  f"no reply after {MAX_NUDGES} nudges — "
                                  "needs a human touch (call them?)", False)
                cs["max_nudges_escalated"] = True
                save_state(state, dry_run=False)
            return 0
    appts = None
    if contact:
        tz_name, _tz_src = resolve_timezone(company, contact)
        appts = fetch_upcoming_appointments(contact["id"], tz_name)
        if appts:
            print(f"Upcoming appointments (live GHL calendar):\n{appts}")
    # STALE-INTEL RE-ASK (Santino 2026-07-28, "reach out consistently"): All
    # Pro's Google-connect ask sat excluded for weeks because kickoff-call
    # intel said "in progress" — and nothing ever aged that out. Any item the
    # intel suppressed 7+ days ago that is STILL open gets force-included as
    # a light check-in. Prepended (detail is clipped at 300 chars downstream).
    for it in items:
        ts = state.get("intel_flagged", {}).get(it.get("id"))
        if not ts:
            continue
        try:
            age_days = (datetime.now(timezone.utc)
                        - datetime.fromisoformat(ts)).days
        except ValueError:
            continue
        if age_days >= 7:
            it["detail"] = (
                "RE-ASK OVERRIDE: an earlier call said this was in progress, but "
                f"it has been open {age_days} days and still is not done. Do NOT "
                "exclude this item based on meeting intel or history — include it "
                "as a light check-in ('circling back on...'). || "
                + (it.get("detail") or ""))
    draft = compose_draft(company, first, items, args.channel, first_contact,
                          history=history, intel=intel, appointments=appts,
                          sister_names=sister_names)
    print("\n" + "=" * 62)
    if draft["subject"] and args.channel == "email":
        print(f"Subject: {draft['subject']}")
    print(draft["body"])
    print("=" * 62)
    print(f"({len(draft['body'])} chars, channel={args.channel})")

    # Items the history shows were already answered: excluded from the body
    # by the compose model; escalate so a human backfills the DB.
    for flag in draft["history_answered"]:
        it = next((i for i in draft["items"] if i["id"] == flag["item_id"]), None)
        label = it["text"] if it else flag["item_id"]
        reason = (f"history suggests already answered: {label} — "
                  f"{flag.get('evidence') or 'see thread'} "
                  f"(item excluded from the nudge; verify + record the answer)")
        print(f"ESCALATION: {reason}")
        append_escalation(company, None, reason, dry_run=not args.send)

    # Items meeting intel marks answered / in progress client-side: excluded
    # from the body by the compose model; escalate so a human backfills the DB.
    intel_state_dirty = False
    for flag in draft["intel_resolved"]:
        it = next((i for i in draft["items"] if i["id"] == flag["item_id"]), None)
        label = it["text"] if it else flag["item_id"]
        if not intel_flag_once(state, flag["item_id"]):
            print(f"[intel-suppressed, already flagged once: {label[:60]}]")
            continue
        intel_state_dirty = True
        reason = (f"meeting intel says answered/in progress: {label} — "
                  f"{flag.get('reason') or 'see meeting-intel notes'} "
                  f"(item excluded from the nudge; verify + record the answer)")
        print(f"ESCALATION: {reason}")
        append_escalation(company, None, reason, dry_run=not args.send)
    if intel_state_dirty and args.send:
        save_state(state, dry_run=False)

    if not draft["body"]:
        print("\nNO NUDGE: every item is answered or in progress per "
              "history/meeting intel — nothing to send this cycle.")
        return 0

    if not args.send:
        print("\n[draft only — pass --send to deliver (canary gate applies)]")
        return 0

    reason = cadence_check(cs, company, contact)
    if reason:
        print(f"\nSEND REFUSED (cadence): {reason}", file=sys.stderr)
        return 0
    if not contact:
        print("\nSEND REFUSED: no GHL contact resolved", file=sys.stderr)
        return 1
    try:
        result = send_message(contact, args.channel, draft["body"],
                              draft["subject"])
    except SendBlocked as e:
        print(f"\nSEND BLOCKED: {e}", file=sys.stderr)
        return 1
    record_sent_message(state, result)
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
        co = companies.get(cid, {"id": cid, "name": cid, "timezone": None})
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
        has_settings = co.get("integration_settings") is not None
        target = messaging_target(co) if has_settings else None
        link = ((target or {}).get("ghl_contact_id")
                or (linked_contact_id(co) if has_settings else None))
        if not link:
            unlinked.append((cid, co["name"]))
        # history column: message count + days since last exchange. Best
        # effort — needs GHL env (status alone doesn't) and a known contact.
        ghl_ok = bool(os.environ.get("GHL_API_KEY")
                      and os.environ.get("GHL_LOCATION_ID"))
        hist_contact = cs.get("ghl_contact_id") or link
        hist = "-"
        contact_payload = None
        if ghl_ok and hist_contact:
            try:
                data = _ghl("GET", f"/contacts/{hist_contact}")
                contact_payload = (data or {}).get("contact") or data
            except RuntimeError:
                contact_payload = None
            try:
                h = fetch_history(hist_contact)
                if h:
                    days = (datetime.now(timezone.utc) - h[0]["when"]).days
                    hist = f"{len(h)}m/{days}d"
                else:
                    hist = "0m"
            except RuntimeError:
                hist = "err"
        # Resolved business-hours timezone + its source (ghl-contact /
        # companies.timezone / plan-input:{state} / DEFAULT-unresolved).
        tz_key, tz_src = resolve_timezone(co, contact_payload)
        tz_disp = f"{tz_key} [{tz_src}]"[:36]
        rows.append((cid, co["name"][:30], n_intake, n_asks, last, nudges, nxt,
                     "yes" if link else "NO",
                     (target_label(co) if has_settings else "?")[:26], hist,
                     tz_disp))

    hdr = (f"{'company':<20} {'name':<30} {'target (who we message)':<26} "
           f"{'intake':>6} {'asks':>4} {'last contact':<16} {'n':>2} "
           f"{'ghl':>3} {'history':<8} {'timezone (business hours)':<36} "
           f"{'next eligible':<20}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r[0]:<20} {r[1]:<30} {r[8]:<26} {r[2]:>6} {r[3]:>4} "
              f"{r[4]:<16} {r[5]:>2} {r[7]:>3} {r[9]:<8} {r[10]:<36} "
              f"{r[6]:<20}")
    print(f"\n{len(rows)} client(s) with outstanding items "
          f"({len(intake)} intake, {len(asks)} asks). "
          f"Allowlist entries: {len(allowed_recipients())}.")
    for cid, name in unlinked:
        print(f"!! WARNING: {name} ({cid}) has NO GHL linkage (no "
              f"ghl_contact_id on the preferred contacts[] entry or "
              f"top-level) — sends would rely on search guessing. Fix with: "
              f"python3 scripts/ghl_link.py link (or re-save the app's "
              f"Contact Card).")
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

A "Recent conversation history" block may be provided — use it to work out
what a short reply ("yes", "the second one", "that works") is answering; the
reply usually responds to the most recent thing WE asked in the thread.

A "Meeting intel" block may be provided — our team's INTERNAL notes from
meetings with this client. Use it as context for classification, and report
any open item the intel marks as ANSWERED / resolved on a call, or as IN
PROGRESS on the client's side, in "intel_resolved" (item id + one-line
reason) — those items must not be re-asked in any follow-up nudge. Never
treat intel alone as the client's answer to an item (that needs a human to
verify); intel_resolved is a flag, not a match.

If the reply is a PURE ACKNOWLEDGMENT of our last outbound message — an
emoji (👍, 🙏), "ok", "sounds good", "thanks", "see you then", "perfect" —
with no information in it, set "ack": true and nothing else. Acknowledgments
need no reply and no human.

If the reply asks to MOVE/RESCHEDULE/CANCEL an upcoming call or meeting
("can we reschedule?", "can't make it Tuesday", "push it a few days"), set
"reschedule" with their timing preference in plain words — that is handled
by a booking flow, not escalation. Do not also set escalate for this.

Return ONLY JSON:
{"matches": [{"item_id": "<id from the list>", "value": "<extracted answer>",
              "answer_type": "license|yes_no|free_text|customer_list"}],
 "intel_resolved": [{"item_id": "<id from the list>", "reason": string}],
 "ack": bool,
 "reschedule": {"requested": bool, "preference": string}|null,
 "escalate": bool,
 "escalate_reason": string|null,
 "sentiment": "positive|neutral|negative"}
"intel_resolved" is [] when no meeting intel is provided or none applies.
Match at most the items clearly answered. When in doubt, do not match — set
escalate true with a reason instead."""

REPLY_SYSTEM = """\
You are Monica from Santino's team at Restoration AI, replying after a
client answered something. Voice: warm, brief, human. NEVER use em dashes or en
dashes; use a comma or a period instead. Thank them, confirm
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
            attachments = msg.get("attachments") or []
            # A photo-only MMS has an empty body — those are real client
            # messages too (the Jeff Sibley case, 2026-07-22).
            if not body and not attachments:
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
                             "attachments": attachments,
                             "channel": "sms" if msg["messageType"] == "TYPE_SMS"
                             else "email"})
    return sorted(messages, key=lambda m: m["ts"])


def ingest_inbound_media(company: dict, msg: dict, dry_run: bool) -> dict:
    """File a client's texted photos/videos where the hub upload page puts
    them, so nothing a client sends is ever lost:
      photos       -> branding/{cid}/job-photos/        (weekly GBP poster feed)
      screenshots  -> branding/{cid}/job-photos/inbox/  (very tall images are
                      usually phone screenshots, not job photos — quarantined
                      so they never get posted to Google)
      videos       -> branding/{cid}/job-videos/        (the GBP poster only
                      handles PHOTO media; keep its folder clean)
    Images are re-encoded (EXIF/GPS stripped) like the upload page does."""
    out = {"photos": 0, "screenshots": 0, "videos": 0, "failed": 0}
    cid = company["id"]
    for url in msg.get("attachments") or []:
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            raw = r.content
            if not raw or len(raw) > 25 * 1024 * 1024:
                out["failed"] += 1
                continue
            ctype = (r.headers.get("Content-Type") or "").lower()
            ext = url.rsplit(".", 1)[-1].lower() if "." in url.rsplit("/", 1)[-1] else ""
            stamp = "{}-{}".format(int(msg["ts"].timestamp() * 1000),
                                   hashlib.sha1(url.encode()).hexdigest()[:8])
            sb_url = os.environ["SUPABASE_URL"].rstrip("/")
            sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
            if ctype.startswith("video/") or ext in ("mp4", "mpg4", "mov", "m4v"):
                path = f"{cid}/job-videos/sms-{stamp}.mp4"
                body, up_type, kind = raw, (ctype or "video/mp4"), "videos"
            elif ctype.startswith("image/") or ext in ("jpg", "jpeg", "png", "webp", "heic"):
                from io import BytesIO
                from PIL import Image
                img = Image.open(BytesIO(raw)).convert("RGB")
                w, h = img.size
                if max(w, h) > 2000:
                    s = 2000 / max(w, h)
                    img = img.resize((round(w * s), round(h * s)))
                buf = BytesIO()
                img.save(buf, "JPEG", quality=85)   # re-encode = EXIF/GPS gone
                body, up_type = buf.getvalue(), "image/jpeg"
                if h and w / h < 0.5:               # screenshot-shaped
                    path, kind = f"{cid}/job-photos/inbox/sms-{stamp}.jpg", "screenshots"
                else:
                    path, kind = f"{cid}/job-photos/sms-{stamp}.jpg", "photos"
            else:
                out["failed"] += 1
                continue
            if dry_run:
                print(f"    [dry-run] would store {kind[:-1]} -> {path}")
            else:
                up = requests.post(
                    f"{sb_url}/storage/v1/object/branding/{path}", data=body,
                    headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
                             "Content-Type": up_type, "x-upsert": "false"},
                    timeout=120)
                if up.status_code not in (200, 201):
                    # already stored on a previous partial run is fine
                    if up.status_code != 409:
                        print(f"    [media] upload {up.status_code}: "
                              f"{up.text[:120]}", file=sys.stderr)
                        out["failed"] += 1
                        continue
            out[kind] += 1
        except Exception as e:
            print(f"    [media] ingest failed for {url[-40:]}: {e}",
                  file=sys.stderr)
            out["failed"] += 1
    return out


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


def append_escalation(company: dict, msg: dict | None, reason: str,
                      dry_run: bool, ping: bool = True) -> None:
    """Append one escalation block. msg is the triggering inbound message when
    there is one; compose-side escalations (history-answered items, human-
    conversation deferrals) pass msg=None."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = (f"\n## {stamp} — {company.get('name', '?')} ({company.get('id', '?')})\n"
             + (f"- Channel: {msg['channel']}  Message id: {msg['id']}\n"
                f"- Reply: {msg['body'][:400]!r}\n" if msg else "")
             + f"- Reason: {reason}\n")
    if ping:
        _OPS_PINGS.append((company.get("name", "?"), reason))
    if dry_run:
        print(f"    [dry-run] would append escalation:{block}")
        return
    try:
        _sb("POST", "/rest/v1/concierge_escalations",
            {"company_id": company.get("id"), "company_name": company.get("name"),
             "reason": reason, "message": msg}, prefer="return=minimal")
    except Exception as e:
        print(f"  [escalation] supabase insert failed ({e}) — falling back "
              "to local file", file=sys.stderr)
        OPS_DIR.mkdir(parents=True, exist_ok=True)
        if not ESCALATIONS_PATH.exists():
            ESCALATIONS_PATH.write_text("# Concierge Escalations\n")
        with ESCALATIONS_PATH.open("a") as f:
            f.write(block)


def intel_flag_once(state: dict, item_id: str) -> bool:
    """True the FIRST time an intel-suppressed item is seen (caller should
    escalate); False afterwards — Santino gets pinged about each such item
    exactly once, however the model re-words the reason each cycle."""
    flagged = state.setdefault("intel_flagged", {})
    if item_id in flagged:
        return False
    flagged[item_id] = datetime.now(timezone.utc).isoformat()
    return True


def flush_ops_pings(dry_run: bool) -> None:
    """One summary SMS per run to the ops cell when escalations occurred.
    Deduped: an identical summary within OPS_PING_DEDUPE_HOURS is skipped so
    repeated dry/cron runs don't spam. Goes through send_message, so the
    allowlist gate still applies."""
    from zoneinfo import ZoneInfo
    held = kv_get("held-ops-pings") or []
    if not _OPS_PINGS and not held:
        return
    hour = datetime.now(ZoneInfo("America/Los_Angeles")).hour
    if not 8 <= hour < 20:
        merged = held + [list(t) for t in _OPS_PINGS]
        if not dry_run:
            kv_set("held-ops-pings", merged)
        print(f"  [ops-ping] outside 8am-8pm PT — holding {len(merged)} "
              "item(s) for morning")
        _OPS_PINGS.clear()
        return
    _OPS_PINGS[:0] = [tuple(h) for h in held]
    if held and not dry_run:
        kv_set("held-ops-pings", [])
    lines = []
    seen = set()
    for name, reason in _OPS_PINGS:
        key = (name, reason[:80])
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- {name}: {reason[:160]}")
    body = (f"Concierge: {len(lines)} item(s) need a human:\n"
            + "\n".join(lines))[:900]
    import hashlib
    digest = hashlib.sha256(body.encode()).hexdigest()[:16]
    state = load_state()
    last = state.get("ops_ping") or {}
    if last.get("hash") == digest:
        try:
            age_h = (datetime.now(timezone.utc)
                     - datetime.fromisoformat(last["at"])).total_seconds() / 3600
        except Exception:
            age_h = OPS_PING_DEDUPE_HOURS + 1
        if age_h < OPS_PING_DEDUPE_HOURS:
            print(f"  [ops-ping] identical ping {age_h:.1f}h ago — skipping")
            return
    if dry_run:
        print(f"  [dry-run] would ops-ping {OPS_PING_CELL}:\n{body}")
        return
    try:
        send_message({"id": OPS_PING_CONTACT_ID, "phone": OPS_PING_CELL},
                     "sms", body)
        state["ops_ping"] = {"hash": digest,
                             "at": datetime.now(timezone.utc).isoformat()}
        save_state(state, dry_run=False)
    except SendBlocked as e:
        print(f"  [ops-ping] blocked: {e}", file=sys.stderr)


RESCHEDULE_OFFER_SYSTEM = """\
You are Monica from Santino's team at Restoration AI, replying to a client
who asked to move an upcoming call. Voice: warm, human, like a real scheduler.
NEVER use em dashes or en dashes; use a comma or a period instead. Confirm moving is no problem, then offer
the provided slot options (their local time) — lead with the first. Ask them
to pick one or say what works better. CONCISE: 2-3 sentences, <= 320 chars,
no emojis, no corporate filler.
Return ONLY JSON: {"body": string}"""

RESCHEDULE_PICK_SYSTEM = """\
A client was offered these time slots for their rescheduled call (their
local time, ISO + label). Their reply is below. Decide:
- picked one -> {"picked": "<iso of the slot>"}
- wants something else / none work -> {"picked": null, "counter": "<their
  preference in plain words>"}
- unrelated reply -> {"picked": null, "counter": null}
Return ONLY JSON."""


def _upcoming_appointment(contact_id: str) -> dict | None:
    data = _ghl("GET", f"/contacts/{contact_id}/appointments") or {}
    best = None
    for ev in data.get("events", []) or []:
        if ev.get("deleted"):
            continue
        if (ev.get("appointmentStatus") or "").lower() in ("cancelled", "noshow"):
            continue
        st = ev.get("startTime", "")
        if st <= datetime.now(timezone.utc).astimezone(
                __import__("zoneinfo").ZoneInfo(GHL_LOCATION_TZ)
        ).strftime("%Y-%m-%d %H:%M:%S"):
            continue
        if best is None or st < best.get("startTime", ""):
            best = ev
    return best


def _free_slots(calendar_id: str, tz: str, days: int = 8) -> list[str]:
    import time as _t
    start = int(_t.time() * 1000)
    end = start + days * 86400 * 1000
    fs = _ghl("GET", f"/calendars/{calendar_id}/free-slots",
              params={"startDate": start, "endDate": end, "timezone": tz})
    out: list[str] = []
    for day, val in (fs or {}).items():
        if not isinstance(val, dict):
            continue
        out.extend(val.get("slots") or [])
    return sorted(out)


def _pick_offer_slots(slots: list[str], current_start_local, tz: str) -> list[str]:
    """Same clock time ~2 days later first (per 'couple of days'), then the
    closest alternatives on later days at varied times. Max 3."""
    from zoneinfo import ZoneInfo
    from datetime import timedelta
    want = current_start_local + timedelta(days=2)
    parsed = [(datetime.fromisoformat(x), x) for x in slots]
    parsed = [(dt, raw) for dt, raw in parsed
              if dt >= current_start_local + timedelta(days=1)
              and 8 <= dt.hour < 18]  # offer business-hours slots only
    if not parsed:
        return []
    exact = [raw for dt, raw in parsed
             if dt.date() >= want.date() and dt.hour == want.hour
             and dt.minute == want.minute]
    offers = exact[:1]
    for dt, raw in sorted(parsed, key=lambda t: abs(t[0] - want)):
        if raw in offers:
            continue
        if any(datetime.fromisoformat(o).date() == dt.date() for o in offers):
            continue
        offers.append(raw)
        if len(offers) == 3:
            break
    return offers


def _fmt_slot(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%A %b %-d at %-I:%M %p")


def handle_reschedule_request(company: dict, contact: dict, preference: str,
                              state: dict, dry_run: bool) -> None:
    from zoneinfo import ZoneInfo
    tz, _src = resolve_timezone(company, contact)
    appt = _upcoming_appointment(contact["id"])
    if not appt:
        append_escalation(company, None,
                          "asked to reschedule but no upcoming appointment "
                          "found on their contact — needs a human", dry_run)
        return
    cur = datetime.strptime(appt["startTime"], "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=ZoneInfo(GHL_LOCATION_TZ)).astimezone(ZoneInfo(tz))
    slots = _free_slots(appt["calendarId"], tz)
    offers = _pick_offer_slots(slots, cur, tz)
    if not offers:
        append_escalation(company, None,
                          "reschedule requested but no free slots in the next "
                          "8 days — needs a human", dry_run)
        return
    labels = [_fmt_slot(o) for o in offers]
    draft = anthropic_json(RESCHEDULE_OFFER_SYSTEM,
                           f"Client first name: {contact_first_name(contact, company)}\n"
                           f"Their current call: {_fmt_slot(cur.isoformat())}\n"
                           f"Their stated preference: {preference or 'unspecified'}\n"
                           f"Slot options (their local time): {', '.join(labels)}")
    body = (draft.get("body") or "").strip()
    print(f"    RESCHEDULE OFFER -> {body!r}")
    if dry_run:
        print(f"    [dry-run] offers: {labels}")
        return
    res = send_message(contact, "sms", body)
    record_sent_message(state, res)
    cs = company_state(state, company["id"])
    cs["pending_reschedule"] = {
        "appointment_id": appt["id"], "calendar_id": appt["calendarId"],
        "tz": tz, "offered": offers,
        "duration_min": 60,
        "at": datetime.now(timezone.utc).isoformat()}


def handle_reschedule_reply(company: dict, contact: dict, msg: dict,
                            state: dict, dry_run: bool) -> bool:
    """Returns True when the inbound message was consumed by the pending
    reschedule flow."""
    from zoneinfo import ZoneInfo
    from datetime import timedelta
    cs = company_state(state, company["id"])
    pend = cs.get("pending_reschedule")
    if not pend:
        return False
    labels = [f"{o} = {_fmt_slot(o)}" for o in pend["offered"]]
    result = anthropic_json(RESCHEDULE_PICK_SYSTEM,
                            "Offered slots:\n" + "\n".join(labels)
                            + f"\n\nClient reply: {msg['body'][:400]}")
    picked = result.get("picked")
    if picked and picked in pend["offered"]:
        start = datetime.fromisoformat(picked)
        # GHL appointment times are written in the location timezone, naive.
        start_loc = start.astimezone(ZoneInfo(GHL_LOCATION_TZ))
        end_loc = start_loc + timedelta(minutes=pend.get("duration_min", 60))
        if not dry_run:
            try:
                _ghl("PUT", f"/calendars/events/appointments/{pend['appointment_id']}",
                     body={"startTime": start_loc.strftime("%Y-%m-%dT%H:%M:%S%z"),
                           "endTime": end_loc.strftime("%Y-%m-%dT%H:%M:%S%z"),
                           "calendarId": pend["calendar_id"]})
            except RuntimeError as e:
                append_escalation(company, msg,
                                  f"client picked {picked} but the calendar "
                                  f"update FAILED ({e}) — fix manually", dry_run)
                return True
            confirm = (f"You're all set, moved to {_fmt_slot(picked)}. "
                       "Talk to you then!")
            res = send_message(contact, "sms", confirm)
            record_sent_message(state, res)
            cs.pop("pending_reschedule", None)
            append_escalation(company, None,
                              f"FYI (no action needed): call rescheduled to "
                              f"{_fmt_slot(picked)} at the client's request",
                              dry_run)
        print(f"    RESCHEDULED -> {picked}")
        return True
    if result.get("counter"):
        cs.pop("pending_reschedule", None)
        handle_reschedule_request(company, contact, result["counter"],
                                  state, dry_run)
        return True
    return False


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
        if contact_id == OPS_PING_CONTACT_ID:
            msgs = fetch_inbound_since(contact_id, since)
            if msgs:
                handled_any = True
                for msg in msgs:
                    print(f"\n[boss-feedback] ops-thread reply (not a client "
                          f"message): {msg['body'][:200]!r}")
                    if not dry_run:
                        _sb("POST", "/rest/v1/concierge_escalations",
                            {"company_id": None, "company_name": "OPS THREAD",
                             "reason": "boss-feedback (Santino reply on ops "
                                       "thread — review in session)",
                             "message": msg}, prefer="return=minimal")
            continue
        company = companies.get(company_id, {"id": company_id, "name": company_id})
        msgs = fetch_inbound_since(contact_id, since)
        if not msgs:
            continue
        open_items = gather_items(company_id)
        # Last ~10 history messages disambiguate short replies ("yes",
        # "the second one") against what was actually asked.
        history = fetch_history(contact_id, max_msgs=CLASSIFY_HISTORY_MSGS)
        history_block = (
            f"\n\nRecent conversation history (newest first; 'them' = the "
            f"client, 'us' = our side) — use it to disambiguate short "
            f"replies:\n{format_history(history)}" if history else "")
        intel = load_meeting_intel(company)
        intel_block = (
            f"\n\nMeeting intel (INTERNAL team notes — context only, never "
            f"quote to the client):\n{intel}" if intel else "")
        # Business-hours enforcement needs the contact's own timezone field.
        contact_payload = None
        if args.send:
            try:
                data = _ghl("GET", f"/contacts/{contact_id}")
                contact_payload = (data or {}).get("contact") or data
            except RuntimeError:
                contact_payload = None
        cs_reset = company_state(state, company_id)
        if cs_reset.get("nudge_count"):
            cs_reset["nudge_count"] = 0
            cs_reset.pop("max_nudges_escalated", None)
            print(f"  [cadence] client replied — nudge counter reset")
        for msg in msgs:
            handled_any = True
            print(f"\n  {company['name']}: inbound {msg['channel']} "
                  f"{msg['ts'].strftime('%m-%d %H:%M')}: {msg['body'][:90]!r}")
            if msg.get("attachments"):
                media = ingest_inbound_media(company, msg, dry_run)
                print(f"    [media] photos={media['photos']} "
                      f"videos={media['videos']} "
                      f"screenshots={media['screenshots']} "
                      f"failed={media['failed']}")
                if not msg["body"]:
                    if media["photos"] or media["videos"]:
                        # Give the normal reply flow something to acknowledge
                        # (marks photo intake items answered + thanks them).
                        n = media["photos"] + media["videos"]
                        msg["body"] = (
                            f"(the client texted {n} photo(s)/video(s) with no "
                            "message — they are already saved on our side; "
                            "treat this as them sending the photos we asked "
                            "for and thank them briefly)")
                    else:
                        append_escalation(
                            company, msg,
                            "client texted a screenshot/attachment we could "
                            "not auto-file — check the conversation", dry_run)
                        continue
            contact_for_flow = contact_payload or {"id": contact_id}
            if handle_reschedule_reply(company, contact_for_flow, msg,
                                       state, dry_run):
                continue
            item_list = "\n".join(
                f"- id={it['id']} kind={it['kind']} type={it['field_type']} "
                f"q={it['text'][:110]!r}" for it in open_items) or "(none)"
            result = anthropic_json(
                CLASSIFY_SYSTEM,
                f"Open items for {company['name']}:\n{item_list}"
                f"{history_block}{intel_block}\n\n"
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
            # Items meeting intel marks answered / in progress client-side:
            # never re-asked in the follow-up; escalated for human backfill.
            intel_ids = set()
            for flag in result.get("intel_resolved") or []:
                it = next((i for i in open_items
                           if i["id"] == flag.get("item_id")), None)
                if not it:
                    continue
                intel_ids.add(it["id"])
                if not intel_flag_once(state, it["id"]):
                    continue
                reason = (f"meeting intel says answered/in progress: "
                          f"{it['text']} — "
                          f"{flag.get('reason') or 'see meeting-intel notes'} "
                          f"(excluded from follow-up nudges; verify + record "
                          f"the answer)")
                print(f"    INTEL: {reason}")
                append_escalation(company, None, reason, dry_run)
            if result.get("ack"):
                print("    acknowledgment — no action, no escalation")
                continue
            resc = result.get("reschedule") or {}
            if resc.get("requested"):
                handle_reschedule_request(company, contact_for_flow,
                                          resc.get("preference") or "",
                                          state, dry_run)
                continue
            if (result.get("escalate") or result.get("sentiment") == "negative"
                    or not result.get("matches")):
                reason = result.get("escalate_reason") or (
                    "negative sentiment" if result.get("sentiment") == "negative"
                    else "no open item matched")
                print(f"    ESCALATE: {reason}")
                append_escalation(company, msg, reason, dry_run)
            if matched_ids:
                remaining = [i for i in open_items
                             if i["id"] not in matched_ids
                             and i["id"] not in intel_ids]
                nxt = (f"Next open item to ask: {remaining[0]['text']}"
                       if remaining else "No items remain.")
                reply = anthropic_json(
                    REPLY_SYSTEM,
                    f"Client first name: "
                    f"{contact_first_name(None, company)}\n"
                    f"They just answered: {msg['body'][:400]}\n{nxt}")
                print(f"    reply draft: {reply.get('body', '')!r}")
                if args.send:
                    # Business hours enforced on EVERY send path (client's
                    # local tz). Phase 1: refuse + flag, no queue.
                    hours_reason = business_hours_check(company, contact_payload)
                    if hours_reason:
                        print(f"    SEND FLAGGED: {hours_reason} — reply not "
                              f"sent this cycle")
                        append_escalation(company, msg, hours_reason, dry_run)
                        continue
                    target = messaging_target(company)
                    contact = {"id": contact_id,
                               "phone": target.get("cell") or company.get("phone"),
                               "email": target.get("email") or company.get("email")}
                    try:
                        sent = send_message(contact, msg["channel"],
                                            reply.get("body", ""))
                        record_sent_message(state, sent)
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
    # 1. find-or-create the canary contact in GHL — PHONE match first (the
    # location dedupes on phone, so the phone owner is the only sendable row)
    contact = None
    data = _ghl("GET", "/contacts/", params={
        "locationId": _loc(), "query": args.phone, "limit": 5})
    for c in data.get("contacts") or []:
        if _norm_phone(c.get("phone")) == _norm_phone(args.phone):
            contact = c
            break
    if not contact:
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
    history = fetch_history(contact["id"])
    draft = compose_draft(company, "Canary", items, args.channel,
                          first_contact=not cs_peek.get("first_contacted"),
                          history=history)
    print("\n" + "=" * 62)
    if draft["subject"] and args.channel == "email":
        print(f"Subject: {draft['subject']}")
    print(draft["body"])
    print("=" * 62)

    cs = company_state(state, CANARY_COMPANY_ID)
    # Canary is EXEMPT from business-hours enforcement (it's Santino testing
    # the pipe, whatever the hour); nudge-count + cooldown still apply.
    reason = cadence_check(cs, company, enforce_hours=False)
    if reason:
        print(f"SEND REFUSED (cadence): {reason}", file=sys.stderr)
        return 1
    send_contact = {"id": contact["id"],
                    "phone": contact.get("phone") or args.phone,
                    "email": contact.get("email") or args.email}
    try:
        result = send_message(send_contact, args.channel, draft["body"],
                              draft["subject"])
    except SendBlocked as e:
        print(f"SEND BLOCKED: {e}", file=sys.stderr)
        return 1
    record_sent_message(state, result)
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
    gcomp = pc.add_mutually_exclusive_group(required=True)
    gcomp.add_argument("--company", help="company id (CO-…)")
    gcomp.add_argument("--all", action="store_true",
                       help="every company with outstanding items")
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
    ret = {"status": cmd_status, "compose": cmd_compose,
           "inbound": cmd_inbound, "canary": cmd_canary}[args.cmd](args)
    if args.cmd in ("compose", "inbound"):
        flush_ops_pings(dry_run=not getattr(args, "send", False))
    return ret


if __name__ == "__main__":
    sys.exit(main())
