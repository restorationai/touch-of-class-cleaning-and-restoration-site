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
    - REPLYING IS NOT A NUDGE (2026-08-02: Todd's "I wonder why they
      suspended the listing" sat behind the cooldown): an unanswered client
      message — the awaiting_reply flag set by inbound, or simply the client
      having spoken last in the thread — bypasses the cooldown + nudge cap
      exactly like a boss directive; business hours, the human-defer window
      and the canary gate still apply, and the draft answers the client
      FIRST before any outstanding item. Same for a client who just
      ANSWERED our question (awaiting_reply kind="answer", Todd's
      "Invoices2Go" 15:48 case): the follow-through — acknowledge + next
      step, a short meeting for non-technical clients — is owed
      immediately, and the flag is voided by ANY newer outbound so the
      thread is never advanced twice.
    - ALWAYS THE LAST TO SEND (Santino 2026-08-02): when the client's last
      message is substantive but needs no answer (sign-off, thank-you with
      content, commitment), Monica still sends ONE short warm closer — the
      batch's single outbound. Anti-loop: reaction events (Liked "...")
      are not messages; a bare thanks/ok/emoji never gets a
      counter-acknowledgment (one closer per wrap-up); and if our closer
      is already newest, nothing is owed.
    - SANTINO NOTIFICATIONS (2026-08-02: "I should not be texted every time
      a client responds"): he is texted only for (a) tripped escalation
      ladders (max nudges, angry client), (b) things needing HIS action or
      decision, (c) client questions Monica can't answer herself. Everything
      else still lands in concierge_escalations (Ops Attention) and reaches
      him via the morning digest email (concierge_digest.py). Every
      boss-facing SMS is rewritten to plain human copy before sending —
      never raw system reasons ("meeting intel says answered/in progress").
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
    CONCIERGE_WEBHOOK_SECRET                  shared secret for the Railway
                                              POST /concierge-inbound webhook
                                              (instant inbound: GHL fires it
                                              the moment a client responds ->
                                              webhook_inbound() analyzes +
                                              replies immediately; falls back
                                              to LEAD_AUDIT_FUNNEL_SECRET)
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
import base64
import hashlib
import json
import os
import re
import sys
import time
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
# ONE PURPOSE PER MESSAGE (Santino 2026-08-02, Todd thread review): every
# text carries at most ONE question — the single most valuable next thing.
# Stacked asks ("What day works? Also, any brand col...") read robotic and
# get half-answered. Other open items wait for their own message.
MAX_ITEMS_PER_MESSAGE = 1
# A first text from an unknown number must feel like a person saying hi with
# one small favor to ask — never a checklist. Follow-ups may carry two.
FIRST_CONTACT_MAX_ITEMS = 1
MIN_DAYS_BETWEEN_SENDS = 3
HISTORY_MAX_MSGS = 25          # default fetch_history depth for compose/status
CLASSIFY_HISTORY_MSGS = 10     # history context given to inbound classification
HISTORY_EMAIL_TRIM = 500       # chars kept per email body (threads get long)
HUMAN_DEFER_HOURS = 12         # human outbound newer than this => skip nudge
MAX_NUDGES = 4
# INBOUND DEBOUNCE (Santino 2026-08-02: "Blue like water" + "And white"
# seconds apart each got their own ack+question — two near-duplicate texts
# back to back). The webhook waits for this quiet window before composing,
# folding rapid-fire messages into ONE conversational turn.
INBOUND_QUIET_WINDOW_S = 100
INBOUND_DEBOUNCE_MAX_S = 360   # never hold a reply hostage longer than this
# Similarity guard: refuse to send an outbound that near-duplicates our own
# last outbound when that one is recent — the last line of defense against
# double-texting the same question (Jaccard on >2-char words).
SIMILAR_JACCARD = 0.55
SIMILAR_RECENT_HOURS = 24
# STOP-KEYWORD AWARENESS (Santino 2026-08-03: Angie texted a bare "end"
# mid-conversation and carrier compliance flipped her to PERMANENT SMS DND
# — the API cannot lift it; only she can, by texting START). A bare
# stop-word inbound is escalated to Santino immediately with the ready
# instruction, and the contact is switched to EMAIL automatically. A
# STOP_KEYWORD/DND contact is never sent SMS again until the flag clears.
_STOP_WORD_RE = re.compile(
    r"^\s*(?:stop(?:all)?|unsubscribe|cancel|end|quit)\s*[.!]?\s*$", re.I)


def _sms_dnd(contact: dict | None) -> bool:
    """True when GHL shows SMS DND on the contact (incl. STOP_KEYWORD)."""
    if not contact:
        return False
    if contact.get("dnd") is True:
        return True
    sms = ((contact.get("dndSettings") or {}).get("SMS") or {})
    return str(sms.get("status", "")).lower() in ("permanent", "active")


# iMessage/Android reaction events arrive from GHL as ordinary inbound SMS
# ('Liked "Got it, Invoice2go works great..."'). They are NOT messages —
# never classify them, never reply to them, never treat them as a client
# message waiting on us (Santino 2026-08-02 anti-loop rule (a)).
_REACTION_RE = re.compile(
    r'^(?:liked|loved|laughed at|emphasi[sz]ed|disliked|questioned)\s+["“]',
    re.I)
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


def anthropic_json(system: str, user: str, *, max_tokens: int = 4000,
                   images: list[dict] | None = None) -> dict:
    """One Messages call, expects a single JSON object in the reply.
    Retries once on an empty/non-JSON reply (2026-07-29: intermittent empty
    responses starved whole compose passes). `images` (from _vision_blocks:
    [{"media_type", "data"(b64)}]) ride along so inbound analysis can SEE
    what a client texted (Angie's browser-warning screenshot, 2026-08-02)."""
    content: list | str = user
    if images:
        content = ([{"type": "image",
                     "source": {"type": "base64",
                                "media_type": im["media_type"],
                                "data": im["data"]}} for im in images]
                   + [{"type": "text", "text": user}])
    last_text = ""
    last_stop = None
    messages: list[dict] = [{"role": "user", "content": content}]
    for attempt in (1, 2, 3):
        resp = requests.post(ANTHROPIC_API, timeout=120, headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json", "User-Agent": UA,
        }, json={
            "model": ANTHROPIC_MODEL, "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        })
        resp.raise_for_status()
        data = resp.json()
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text").strip()
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        last_text = text
        last_stop = data.get("stop_reason")
        if attempt < 3:
            # claude-sonnet-5 runs ADAPTIVE THINKING by default and max_tokens
            # caps thinking + text TOGETHER — on hard prompts thinking can eat
            # the whole budget and the reply arrives with stop_reason
            # "max_tokens" and zero text blocks (PuroClean compose failed
            # every GH-Actions run this way, 08-03). Double the budget before
            # retrying so the text actually fits.
            if last_stop == "max_tokens":
                max_tokens = min(max_tokens * 2, 16000)
            elif text:
                # NON-JSON with a normal end_turn: the model wrote the message
                # as prose instead of the JSON envelope (Mold Solutionz
                # compose failed 6/6 identical retries this way, 08-03).
                # Blind retries reproduce it — a CORRECTIVE turn (same trick
                # as gbp.py's _anthropic_json) reliably snaps it back.
                messages = messages[:1] + [
                    {"role": "assistant", "content": text[:3000]},
                    {"role": "user", "content":
                     "That was not the required format. Reply again with "
                     "ONLY the JSON object described in the instructions — "
                     "put your draft in its fields. The very first character "
                     "of your reply must be '{'."}]
            print(f"  [anthropic_json] empty/non-JSON reply "
                  f"(stop_reason={last_stop}) — retrying "
                  f"(max_tokens now {max_tokens})")
            time.sleep(3)
    raise RuntimeError(f"Claude returned no JSON object "
                       f"(stop_reason={last_stop}): {last_text[:200]!r}")


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
    # EMAIL ID RECONCILIATION (PuroClean 2026-08-03 post-mortem): for Email
    # sends GHL returns emailMessageId, but the message row that later shows
    # up in the conversation carries a DIFFERENT id — so Monica's own email
    # read as a HUMAN outbound and tripped the 12h human-defer window on
    # every hourly compose after her 07-29 intro email to Greg. Best-effort:
    # pull the conversation's newest outbound email id and record it too.
    conv = (result or {}).get("conversationId")
    if conv and (result or {}).get("emailMessageId"):
        try:
            data = _ghl("GET", f"/conversations/{conv}/messages",
                        params={"limit": 10})
            best = None
            for msg in (data.get("messages") or {}).get("messages", []) or []:
                if (msg.get("direction") == "inbound"
                        or msg.get("messageType") != "TYPE_EMAIL"
                        or not msg.get("id")):
                    continue
                when = msg.get("dateAdded") or ""
                if best is None or when > best[0]:
                    best = (when, msg["id"])
            if best and best[1] not in ids:
                ids.append(best[1])
        except Exception as e:  # noqa: BLE001 — bookkeeping never fails a send
            print(f"  [sent-ids] email reconcile failed: {str(e)[:80]}")


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


def pending_client_message(cs: dict, history: list[dict], state: dict) -> dict | None:
    """The newest substantive client message still owed a real reply, as
    {"body", "kind"} — or None when nothing is owed.

    Replying to a client who spoke last is NOT a nudge — this drives the
    compose-side cooldown/nudge-cap bypass (2026-08-02: Todd's "I wonder why
    they suspended the listing" sat unanswered behind the 3-day cooldown
    while the daily ack cap ate the holding line). Two sources:
      (1) cs["awaiting_reply"], set by the inbound engine — kind "question"
          (their reply needed a real answer and matched no item; survives
          Monica's own holding ack sitting newest in the thread) or kind
          "answer" (they answered OUR question — the follow-through is owed;
          Todd's "Invoices2Go" got silence, 2026-08-02 15:48);
      (2) the live thread: the newest message is inbound sms/email, not a
          pure acknowledgment, and < 7 days old (kind "message").
    Void rules (the no-double-send property):
      - kind "answer": ANY newer outbound voids it, ours included — once
        something advanced the thread after their answer, never send twice;
      - kind "question": only a newer HUMAN outbound (not one of ours) voids
        it — Santino answered it himself; our own holding ack does not."""
    now = datetime.now(timezone.utc)
    ours = sent_message_ids(state)

    def outbound_after(after: datetime, human_only: bool) -> bool:
        for m in history:
            if m["direction"] != "out" or m["when"] <= after:
                continue
            if not human_only:
                return True
            if not (m["id"] and m["id"] in ours):
                return True   # a human (not the concierge) wrote it
        return False

    flag = cs.get("awaiting_reply") or {}
    if flag.get("body"):
        kind = str(flag.get("kind") or "question")
        try:
            at = datetime.fromisoformat(flag["at"])
        except (KeyError, ValueError):
            at = now
        advanced = outbound_after(at, human_only=(kind != "answer"))
        if (now - at) > timedelta(days=7) or advanced:
            cs.pop("awaiting_reply", None)   # stale, or the thread moved on
        else:
            return {"body": str(flag["body"]), "kind": kind}
    if history:
        newest = history[0]
        body = (newest.get("body") or "").strip()
        # Reactions (Liked "...") are not messages; bare thanks/ok never
        # get a counter-acknowledgment — both end the exchange with the
        # client "last" and that is fine (anti-loop rules a + c). Anything
        # substantive owes at least a closer: "I always want us to be the
        # last person to send a message" (Santino 2026-08-02).
        if (newest["direction"] == "in"
                and newest.get("channel") in ("sms", "email") and body
                and not _REACTION_RE.match(body)
                and not _bare_ack(body)
                and (now - newest["when"]) < timedelta(days=7)):
            return {"body": body, "kind": "message"}
    return None


# ---------------------------------------------------------------- timezone
def repeats_last_outbound(body: str, history: list[dict]) -> str | None:
    """Refusal reason when `body` near-duplicates our most recent outbound
    and that outbound is < SIMILAR_RECENT_HOURS old — else None.

    The hard guard behind the no-double-question rule (Santino 2026-08-02:
    two team-photo asks landed one minute apart). Jaccard overlap on words
    longer than 2 chars; the recency condition keeps legitimate re-asks
    after the 3-day cooldown from tripping it."""
    last = next((m for m in history if m.get("direction") == "out"
                 and (m.get("body") or "").strip()), None)
    if not last:
        return None
    age_h = (datetime.now(timezone.utc) - last["when"]).total_seconds() / 3600
    if age_h >= SIMILAR_RECENT_HOURS:
        return None

    def toks(s: str) -> set:
        return {w for w in re.findall(r"[a-z']+", (s or "").lower())
                if len(w) > 2}

    a, b = toks(body), toks(last["body"])
    if not a or not b:
        return None
    overlap = len(a & b) / len(a | b)
    if overlap >= SIMILAR_JACCARD:
        return (f"too similar to our last outbound ({overlap:.0%} word "
                f"overlap, sent {age_h:.1f}h ago: {last['body'][:70]!r})")
    return None


# GROUNDING GUARD (Santino 2026-08-02, LIVE failure): Monica texted Flood
# Fixers "That review request is already out to him and Ed." — but
# review_requests had ZERO rows for the company; she claimed a completed
# action that never happened. The prompts now forbid ungrounded DONE-claims;
# this is the mechanical backstop: a claim that our review/post/listing/
# request work is DONE may only ship when the LEDGER portion of the compose
# context (Santino's ops notes + the WORK ALREADY DONE block) mentions that
# subject. Meeting-intel prose does not count — it speaks in plans.
_DONE_CLAIM_RE = re.compile(
    r"\b(?:(?:is|are|was|were|has been|have been|got|went)\s+(?:already\s+)?"
    r"(?:sent|out|posted|live|submitted|published|done|handled)"
    r"|already\s+(?:sent|out|posted|live|submitted|done|handled|went out)"
    r"|we(?:'ve| have)?\s+(?:already\s+)?"
    r"(?:sent|submitted|posted|filed|published))\b", re.I)
_CLAIM_SUBJECTS = ("review", "post", "listing", "invite", "request",
                   "campaign", "appeal")


def _evidence_slice(intel: str | None) -> str:
    """The LEDGER portion of the compose context — Santino's ops notes +
    the WORK ALREADY DONE block. Meeting-intel prose is excluded on
    purpose: it records intentions ("wants a review campaign"), and a
    DONE-claim must trace to recorded work, never to a plan."""
    if not intel:
        return ""
    out = []
    for marker in ("[OPS NOTES", "[WORK ALREADY DONE"):
        i = intel.find(marker)
        if i >= 0:
            j = intel.find("\n\n[", i + 1)
            out.append(intel[i:j if j > 0 else len(intel)])
    return "\n".join(out)


def unsupported_done_claim(body: str, evidence: str | None) -> str | None:
    """Refusal reason when `body` claims completed work on a tracked
    subject (reviews/posts/listings/requests/...) that the ledger evidence
    does not mention — else None. Callers with no ledger context (inline
    replies, acks) pass evidence=None: for them ANY such DONE-claim is
    unsupported by construction."""
    ev = (evidence or "").lower()
    for sent in re.split(r"(?<=[.!?])\s+", body or ""):
        if not _DONE_CLAIM_RE.search(sent):
            continue
        subjects = [s for s in _CLAIM_SUBJECTS if s in sent.lower()]
        if not subjects:
            continue
        if not any(s in ev for s in subjects):
            return (f"claims '{subjects[0]}' work is already done but the "
                    f"ledger context has no evidence of it: {sent[:90]!r}")
    return None


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
    # OPS NOTES (Santino 2026-07-28): super-admin notes written in the app
    # (marketing_ops_notes) are direct instructions to Monica — priorities,
    # context, "still waiting on their YouTube connection, make it a
    # priority". Open notes ride in with the meeting intel every compose.
    try:
        notes = _sb("GET", "/rest/v1/marketing_ops_notes"
                    f"?company_id=eq.{company.get('id')}&status=eq.open"
                    "&select=body,created_at&order=created_at.desc&limit=10") or []
        if notes:
            lines = "\n".join(
                f"- ({(n.get('created_at') or '')[:10]}) {n.get('body', '').strip()}"
                for n in notes)
            parts.append("[OPS NOTES from Santino — treat as current instructions, "
                         "they override older meeting intel]\n" + lines)
    except Exception as e:
        print(f"  [intel] ops-notes fetch failed: {e}", file=sys.stderr)
    # ALREADY-DONE CONTEXT (Santino 2026-08-02: Monica asked for job photos
    # we harvested the day before): the recent work ledger + recently
    # RESOLVED ops notes ride along, so compose/classify can see what we
    # already hold and exclude those asks via the intel_resolved machinery.
    try:
        # date-only: an isoformat "+00:00" reads as a space in the URL (400)
        since14 = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()
        done = _sb("GET", "/rest/v1/marketing_work_log"
                   f"?company_id=eq.{company.get('id')}"
                   f"&ts=gte.{since14}"
                   "&select=action,detail,ts"
                   "&order=ts.desc&limit=12") or []
        resolved = _sb("GET", "/rest/v1/marketing_ops_notes"
                       f"?company_id=eq.{company.get('id')}"
                       f"&status=eq.resolved&created_at=gte.{since14}"
                       "&select=body,created_at&order=created_at.desc&limit=6") or []
        lines = [f"- ({str(w.get('ts'))[:10]}) "
                 f"{str(w.get('detail') or w.get('action'))[:160]}"
                 for w in done]
        lines += [f"- (resolved {str(n.get('created_at'))[:10]}) "
                  f"{str(n.get('body'))[:160]}" for n in resolved]
        if lines:
            parts.append(
                "[WORK ALREADY DONE — recent ledger + resolved notes. If an "
                "outstanding item asks the client for something these lines "
                "show we already have or did, EXCLUDE that item (report it "
                "in intel_resolved) instead of asking]\n" + "\n".join(lines))
    except Exception as e:
        print(f"  [intel] work-done fetch failed: {e}", file=sys.stderr)
    return "\n\n".join(parts) or None


# ---------------------------------------------------------------- data pulls
def company_inactive(company: dict | None) -> str | None:
    """Reason string when this company must NOT be messaged because the
    account is paused/cancelled — else None.

    Santino 2026-08-04 (Mold Solutionz paused after the client cancelled):
    the pause button writes companies.status='paused', but the concierge
    never read it — outstanding intake/plan rows would have kept Monica
    texting Andrea. Statuses are mixed-case in prod ('Active' vs 'paused'),
    so compare case-insensitively. Deleted accounts vanish from companies
    entirely (delete-account fn), so 'active'-only is the safe allow-list;
    unknown/empty statuses stay contactable (legacy rows predate status)."""
    st = str((company or {}).get("status") or "").strip().lower()
    if st in ("paused", "cancelled", "canceled", "churned", "inactive",
              "archived"):
        return f"account status is '{st}' — concierge muted for this company"
    return None


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

    items = ([norm_intake(i) for i in blocking]
             + [norm_plan(p) for p in asks]
             + [norm_intake(i) for i in rest])

    return sorted(items, key=ask_rank)


# ---- already-have check (Santino 2026-08-02: Monica asked Todd for
# "finished job photos" the day after we harvested 50 from his Facebook
# page). Ground truth is the branding bucket itself — tool-agnostic, so it
# closes the item on the first pass after ANY harvest (FB agent, SMS
# intake, hub uploads), before an ask can ever be drafted.
JOB_PHOTO_SATISFIED_AT = 8


def _job_photo_count_storage(company_id: str) -> int:
    """Files under branding/{cid}/job-photos/ (the inbox/ quarantine rows
    come back in the same listing; screenshots there still count as held
    media a human can promote — the point is we're not empty-handed)."""
    try:
        url = (os.environ["SUPABASE_URL"].rstrip("/")
               + "/storage/v1/object/list/branding")
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        r = requests.post(url, json={"prefix": f"{company_id}/job-photos/",
                                     "limit": 300},
                          headers={"apikey": key,
                                   "Authorization": f"Bearer {key}"},
                          timeout=30)
        r.raise_for_status()
        return sum(1 for f in (r.json() or []) if f.get("id"))
    except Exception as e:  # noqa: BLE001 — an asset count must never kill compose
        print(f"  [already-have] job-photo count failed: {str(e)[:80]}",
              file=sys.stderr)
        return 0


# ---- domain-access state gate (2026-08-03): asks about the client's domain
# are STATE-DRIVEN now, not keyword-driven. setup_ledger maintains
# marketing_sites.domain_access_status (none -> promised ->
# delegate_granted | creds_provided -> ns_live) and seeds/retires the plan
# rows, but ledger passes run every ~4h — this gate is the same-day belt:
# the moment the client provides access, Monica must never ask again, even
# if the ledger hasn't swept the plan row yet.
_DOMAIN_ASK_RE = re.compile(r"domain|registrar|godaddy|nameserver", re.I)


def _domain_access_status(company_id: str) -> str:
    """Current domain_access_status from marketing_sites ('' = no site row)."""
    try:
        rows = _sb("GET", f"/rest/v1/marketing_sites?company_id=eq.{company_id}"
                   "&select=domain_access_status&limit=1") or []
        return str((rows[0] if rows else {}).get("domain_access_status") or "")
    except Exception:
        return ""


def _gbp_suspended(company_id: str) -> bool:
    """Best signal on file: any OPEN ops note mentioning a suspension."""
    try:
        rows = _sb("GET", f"/rest/v1/marketing_ops_notes?company_id=eq.{company_id}"
                   "&status=eq.open&select=body&limit=20") or []
        return any(re.search(r"suspend", str(r.get("body", "")), re.I)
                   for r in rows)
    except Exception:
        return False


def filter_already_satisfied(company: dict, items: list[dict],
                             dry_run: bool) -> list[dict]:
    """Drop (and auto-close) asks for things we already hold, before any
    message is drafted.

    (a) Finished/job-photo items: when the branding bucket already holds
        JOB_PHOTO_SATISFIED_AT+ job photos, the item is AUTO-SATISFIED —
        answered in the DB with the evidence, not just skipped — so it can
        never be asked again by any path.
    (b) GBP-facing photo/post asks while the listing is SUSPENDED are
        pointless until reinstatement: deferred (kept open, not asked)."""
    kept: list[dict] = []
    n_photos: int | None = None
    suspended: bool | None = None
    da_status: str | None = None
    for it in items:
        text = str(it.get("text", "")).lower()
        # (c) DOMAIN-ACCESS STATE GATE — per-state behavior:
        #     none      -> ask normally (the ledger seeded the rank-1 ask)
        #     promised  -> the ledger swapped the ask for a verify nudge; the
        #                  normal cooldown paces it — nothing to do here
        #     delegate_granted / creds_provided -> STOP asking + speak
        #                  forward (compose gets a context note: access is in
        #                  hand, the site is being put live)
        #     ns_live   -> done; drop any straggler ask outright
        if _DOMAIN_ASK_RE.search(text):
            if da_status is None:
                da_status = _domain_access_status(company["id"])
            if da_status in ("delegate_granted", "creds_provided"):
                print(f"  [domain-state] {it['text'][:60]!r}: access already "
                      f"in hand ({da_status}) — never ask again; speaking "
                      "forward instead")
                company["_domain_forward_note"] = da_status
                if it.get("kind") == "plan":
                    resolve_plan_row(it["id"], dry_run)
                continue
            if da_status == "ns_live":
                print(f"  [domain-state] {it['text'][:60]!r}: nameservers are "
                      "live — retiring the stale ask")
                if it.get("kind") == "plan":
                    resolve_plan_row(it["id"], dry_run)
                continue
        if re.search(r"(finished|job)[ -]?(site )?photos?", text):
            if n_photos is None:
                n_photos = _job_photo_count_storage(company["id"])
            if n_photos >= JOB_PHOTO_SATISFIED_AT:
                val = (f"auto-satisfied {datetime.now(timezone.utc).date()}: "
                       f"{n_photos} job photos already in the branding "
                       "library (harvest/SMS/hub) — nothing to ask the "
                       "client for")
                print(f"  [already-have] {it['text'][:60]!r}: {n_photos} job "
                      "photos on file — auto-satisfying, not asking")
                if it.get("kind") == "intake":
                    apply_answer(it["id"], val, dry_run)
                else:
                    resolve_plan_row(it["id"], dry_run)
                continue
        if (re.search(r"google business|business profile|\bgbp\b", text)
                and re.search(r"photos?|posts?", text)):
            if suspended is None:
                suspended = _gbp_suspended(company["id"])
            if suspended:
                print(f"  [suspended-gate] {it['text'][:60]!r}: their Google "
                      "listing is suspended — deferring this ask until it "
                      "is reinstated")
                continue
        kept.append(it)
    return kept


# BUSINESS-PRIORITY RANK (Santino 2026-07-30: "she always works on the
# first priority item" — All Pro got a YouTube ask while their Google
# account sat unconnected). Rank classes trump source ordering; Python's
# stable sort keeps the original order within a class. Module-level so the
# same-owner merge can re-rank across companies too.
def ask_rank(it) -> int:
    # Rank on the item TITLE only — details are prose and full of incidental
    # keyword matches ("sign into that Google account" on a YouTube ask).
    t = it["text"].lower()
    if "youtube" in t:
        return 4   # nice-to-have, never outranks foundations
    # "verify": GBP verification is a launch blocker on par with domain
    # access (Santino 2026-08-03: top messaging priority, paired with the
    # domain ask when both are open — the launch-blocker pair).
    if "google" in t and any(k in t for k in ("connect", "access",
                                              "re-engage", "verify")):
        return 0   # nothing works without the Google connection/verification
    if any(k in t for k in ("domain", "registrar", "godaddy", "nameserver")):
        return 1   # launch blocker
    if "customer list" in t or "review campaign" in t:
        return 2   # revenue engine
    if "logo" in t or "brand" in t:
        return 3
    return 5


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
                # Same person? (Go Green: the preferred entry IS the owner,
                # just missing its ghl_contact_id — the top-level linkage
                # resolves to the same phone.) Then this is log noise, not a
                # mis-target: one quiet line, no stderr WARNING. The durable
                # fix stays data-side: re-save the Contact Card in the app.
                same_person = (
                    (_norm_phone(contact.get("phone") or "")
                     and _norm_phone(contact.get("phone") or "")
                     == _norm_phone(target.get("cell") or ""))
                    or (_norm_email(contact.get("email") or "")
                        and _norm_email(contact.get("email") or "")
                        == _norm_email(target.get("email") or "")))
                if same_person:
                    print(f"  [linkage] preferred contact entry lacks "
                          f"ghl_contact_id; top-level linkage {cid} is the "
                          f"same person (phone/email match) — using it. "
                          f"Re-save the Contact Card to persist the link.")
                else:
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


def has_boss_directive(company_id: str | None) -> bool:
    """True when an open ops note is a DIRECT order from Santino
    ([FROM SANTINO...] advice-loop answers, [SEND-PREVIEW] approvals).
    Acting on his order is not a nudge — it must bypass cooldown and the
    nudge cap (2026-08-01: Angie's direct question sat two days behind the
    cooldown gate while his answer was already on file). Business hours
    still apply."""
    if not company_id:
        return False
    try:
        rows = _sb("GET", f"/rest/v1/marketing_ops_notes?company_id=eq.{company_id}"
                   "&status=eq.open&select=body&limit=20") or []
        return any(str(r.get("body", "")).startswith(("[FROM SANTINO", "[SEND-PREVIEW]"))
                   for r in rows)
    except Exception:
        return False


def cadence_check(cs: dict, company: dict, contact: dict | None = None,
                  enforce_hours: bool = True, boss_override: bool = False,
                  client_waiting: bool = False) -> str | None:
    """Return a human-readable refusal reason, or None if a send is allowed now.

    Business hours run in the client's OWN timezone (resolve_timezone: GHL
    contact -> companies.timezone -> plan-input state -> default+warning) and
    are enforced on every send path; the canary passes enforce_hours=False.
    boss_override (an open [FROM SANTINO]/[SEND-PREVIEW] note) and
    client_waiting (pending_client_message: the client spoke last and nobody
    answered — replying is not a nudge, 2026-08-02) both skip the cooldown
    and nudge cap — never the hours or the allowlist canary."""
    if not (boss_override or client_waiting):
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
    if os.environ.get("CONCIERGE_PAUSED", "").strip() in ("1", "true", "yes"):
        raise SendBlocked("CONCIERGE_PAUSED is set — Santino paused all "
                          "concierge sending 2026-07-29. Unset it in .env / "
                          "the workflow env to resume.")
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
    # No emoji/astral chars EVER: one emoji flips Twilio to UCS-2 encoding and
    # doubles the segment cost (Santino 2026-07-30).
    body = re.sub(r"[\U0001F000-\U0010FFFF\u2600-\u27bf\ufe0f\u200d]", "", body)
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
    try:
        result = _ghl("POST", "/conversations/messages", body=payload)
    except RuntimeError as e:
        # GHL 400 "Cannot send message as DND is active for SMS" — the client
        # has texting turned off at the CRM level. That's their choice, not an
        # outage: treat it as a send-block (skip + surface), never a crash
        # (PuroClean/Gregory reddened the whole GH-Actions run this way, 08-03).
        if "DND is active" in str(e):
            raise SendBlocked(
                f"GHL DND active for {channel} on contact {contact.get('id')} "
                f"({recipient}) — client has this channel turned off in the "
                "CRM; nothing sent. Clear DND in GHL (or switch channel) to "
                "resume.") from e
        raise
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
human, zero corporate filler, no exclamation-point spam, no emojis. Never
use teaser-colon constructions ("Big news:", "Quick update:", "Great news:")
— a human says "I have some great news" and keeps talking. You are
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

LOCAL SERVICES ADS: never pitch LSA / "Google Guaranteed" or discuss its
pricing — Santino owns pricing and strategy conversations. The context
includes an "LSA decision" line:
- "no" or "later": NEVER mention LSA at all.
- "yes": you may drive the SETUP LOGISTICS when an outstanding item asks
  for it (connecting their Google Ads account, sending their contractor
  license number, proof of insurance, background-check steps) — plain
  words, one thing at a time. Never talk cost.
- "unset": only if an outstanding item explicitly asks about LSA.

LINKS ARE ALL-OR-NOTHING. Only include a link whose FULL URL is literally in
your context. If context does not contain the URL for something (like a
website preview), do NOT mention it at all — never write "your preview is up
at" and trail off, never invent or abbreviate a URL. Every message must end
as a complete sentence; a message ending in "at…" or mid-thought is a
hard failure (it happened to a real client 2026-07-29).

GOOGLE-CONNECT ASKS ALWAYS CARRY THE LINK (Santino 2026-08-03). Whenever the
message asks the client to connect (or reconnect, grant access to, sign
into) their Google business listing, it MUST include the "Google connect
link for THIS client" from the context, exactly as written — that link IS
the ask ("here's the link, it takes about two minutes"). A connect ask
without that link is a hard failure: the client has nothing to tap and the
message wastes the touch (a real client got "here's a link" with no link
attached, MCC 2026-07-25). This applies even when the connect ask rides
along with other content, like sharing their website preview.

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
- PURPOSE: when explaining WHY we ask for something, use that item's own
  "context:" text; if it doesn't state a purpose, don't invent one
  (2026-08-03: the supplier question got a made-up "ads setup" purpose).
- GROUNDING (hard rule — 2026-08-02: Monica told a client "that review
  request is already out to him and Ed" when NO request existed anywhere):
  never state that an action is DONE (sent / out / posted / live /
  submitted / handled) unless the context EXPLICITLY shows it happened —
  an ops note from Santino, a WORK ALREADY DONE ledger line, or an item
  marked answered. Meeting-intel plans ("wants a review campaign") and
  your own assumptions are NOT evidence. Without evidence, speak forward
  in present tense ("we're getting Steve added now", "that's going out
  shortly"), never past or perfect tense about our own work.
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
- NAME BUDGET (Santino 2026-08-02: every message opened "Hey Todd," /
  "Thanks, Todd," — humans don't repeat names constantly mid-thread): use
  the first name at most ONCE per day of conversation. If any outbound in
  today's history already used it, or you are replying mid-conversation,
  open with content instead: "Got it...", "Sounds good...", or just the
  answer. Never open consecutive messages with "Hey {name}" or
  "Thanks, {name}".
- ONE QUESTION PER MESSAGE (hard rule, Santino 2026-08-02): each message
  has ONE purpose and at most ONE question — the single most valuable next
  thing. Never stack a second ask ("Also, ...", "While I have you...")
  onto a message that already asks something, proposes a meeting, or
  closes a commitment. Every other open item WAITS for its own message.
  SOLE EXCEPTION: a "LAUNCH-BLOCKER PAIR" block in the context — then, and
  only then, bundle exactly those two asks with one shared call offer.
- ACKNOWLEDGE FORWARD, never echo: never restate what the client just told
  you as a third-person summary ("got it, you'll grab a company photo once
  you're back in town" is the banned pattern). Point forward instead:
  "Thanks, definitely send those over when you get back into town." When
  the client just COMMITTED to do something later, the entire message is
  that warm forward-pointing close — never a new ask on top of it.
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
worth nudging about this cycle. EXCEPTION: when an "UNANSWERED CLIENT
MESSAGE" block is present, never return an empty body — answering the
client comes before, and regardless of, the items.
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


# ---- GBP-connect link rule (Santino 2026-08-03: "when we send them a
# message to connect their gbp listing, make sure to attach their connection
# link too"). A connect ask is only actionable WITH the client's short
# connect link — https://restorationai.io/connect/{slug}, the KV-backed 302
# that client_ops_sync's seeder mints. Detection is on the item TITLE, same
# altitude as ask_rank; "verify" is excluded on purpose (postcard
# verification of the listing has no link to tap).
_GOOGLE_CONNECT_RE = re.compile(
    r"\b(connect|reconnect|re-?engage|access|sign.?in)\b", re.I)


def is_google_connect_ask(item: dict) -> bool:
    t = str(item.get("text", "")).lower()
    return (("google" in t or "business profile" in t)
            and bool(_GOOGLE_CONNECT_RE.search(t))
            and "verify" not in t)


def google_connect_link(company: dict, items: list[dict] | None = None) -> str | None:
    """The client's short Google-connect link, never a dead one.

    1) Prefer the exact short link already written on one of the items (the
       ops-sync seeder embeds it in the ask's rationale) — guaranteed minted.
    2) Otherwise reconstruct from marketing_sites.rank_ai_slug and verify the
       KV entry behind restorationai.io/connect/{slug} actually exists
       (intake items like FireDEX's access ask predate the seeder); missing
       and no way to check -> None, because a linkless ask beats a 404.
    """
    for it in items or []:
        m = re.search(r"https://restorationai\.io/connect/[\w-]+",
                      str(it.get("detail") or "") + " " + str(it.get("text") or ""))
        if m:
            return m.group(0)
    try:
        rows = _sb("GET", f"/rest/v1/marketing_sites?company_id=eq.{company['id']}"
                   "&select=rank_ai_slug&limit=1") or []
        slug = str((rows[0] if rows else {}).get("rank_ai_slug") or "").strip()
        if not slug:
            return None
        acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        ctok = os.environ.get("CLOUDFLARE_R2_API_TOKEN")
        if not (acct and ctok):
            return None
        r = requests.get(
            "https://api.cloudflare.com/client/v4/accounts/{}/storage/kv/"
            "namespaces/404d46bf0c72404495ab66d15157c499/values/connect%3A{}".format(acct, slug),
            headers={"Authorization": "Bearer " + ctok}, timeout=20)
        if r.ok:
            return "https://restorationai.io/connect/" + slug
    except Exception as e:  # noqa: BLE001 — the link lookup must never kill compose
        print(f"  [connect-link] lookup failed: {str(e)[:80]}", file=sys.stderr)
    return None


GHL_LOCATION_TZ = "America/Los_Angeles"  # GHL returns naive local times


def fetch_upcoming_appointments(contact_id: str, client_tz: str) -> tuple[str | None, datetime | None]:
    """(block, soonest_start) of the contact's upcoming GHL appointments,
    rendered in the CLIENT's local time. Live calendar data — compose is told
    to trust this over meeting-intel dates. soonest_start drives the
    meeting-imminent nudge gate."""
    from zoneinfo import ZoneInfo
    try:
        data = _ghl("GET", f"/contacts/{contact_id}/appointments") or {}
    except RuntimeError as e:
        print(f"  [appointments] fetch failed: {e}", file=sys.stderr)
        return None
    now = datetime.now(timezone.utc)
    lines = []
    soonest: datetime | None = None
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
        if soonest is None or start < soonest:
            soonest = start
        local = start.astimezone(ZoneInfo(client_tz))
        lines.append(f"- {local.strftime('%A %b %-d, %-I:%M %p')} "
                     f"(their local time): {ev.get('title', 'appointment')}"
                     f" [{status or 'booked'}]")
    return ("\n".join(lines), soonest) if lines else (None, None)


def compose_draft(company: dict, first_name: str, items: list[dict],
                  channel: str, first_contact: bool,
                  history: list[dict] | None = None,
                  intel: str | None = None,
                  appointments: str | None = None,
                  sister_names: list[str] | None = None,
                  pending_reply: dict | None = None,
                  commitment: dict | None = None) -> dict:
    chosen = items[:FIRST_CONTACT_MAX_ITEMS if first_contact
                   else MAX_ITEMS_PER_MESSAGE]
    # LAUNCH-BLOCKER PAIR (Santino 2026-08-03, his explicit design and the
    # ONLY exception to one-question-per-message): when BOTH launch
    # blockers are open — domain access AND Google-listing verification —
    # Monica bundles exactly those two in ONE message with one shared
    # 15-minute call offer. Never more than two, never pair anything else.
    pair = None
    if not first_contact:
        t = lambda i: str(i.get("text", "")).lower()  # noqa: E731
        ver = next((i for i in items
                    if "verify" in t(i) and ("google" in t(i)
                                             or "listing" in t(i))), None)
        dom = next((i for i in items if "domain" in t(i)
                    and "verify" not in t(i)), None)
        if ver and dom:
            pair = (ver, dom)
            chosen = [ver, dom]   # verification leads (top priority)
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
    # NAME BUDGET context: the mechanical signal behind the prompt rule
    # (first name at most once per day of thread — Santino 2026-08-02).
    name_line = ""
    if not first_contact and history:
        used_today = any(
            m["direction"] == "out"
            and first_name.lower() in str(m.get("body") or "").lower()
            and (datetime.now(timezone.utc) - m["when"]) < timedelta(hours=24)
            for m in history)
        name_line = (
            "Name budget: their first name was ALREADY used in a message "
            "within the last day — do NOT use it anywhere in this message; "
            "open with content.\n" if used_today else
            "Name budget: their first name has not been used in the last "
            "day; you may use it once, or not at all.\n")
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
    pending_block = ""
    if pending_reply:
        p_body = str((pending_reply or {}).get("body", ""))[:400] \
            if isinstance(pending_reply, dict) else str(pending_reply)[:400]
        p_kind = (pending_reply or {}).get("kind", "message") \
            if isinstance(pending_reply, dict) else "message"
        if p_kind == "answer":
            pending_block = (
                "\nCLIENT ANSWERED OUR QUESTION — the newest client message "
                "answers something we asked them:\n"
                f"  \"{p_body}\"\n"
                "Your ONLY job is the follow-through: acknowledge what they "
                "gave us in a few forward-pointing words (never restate "
                "their message back as a summary), then give the concrete "
                "NEXT STEP. Follow the standing policy: for a non-technical "
                "client the next step is a short meeting to do it together "
                "(recommend it warmly and propose times), never a "
                "multi-step text walkthrough; only give steps by text when "
                "it is genuinely one simple action. If their message was a "
                "COMMITMENT to do something later, the whole reply is a "
                "warm close ('Sounds good, whenever you're back works'). "
                "Do NOT add any outstanding item or extra ask to this "
                "message — the follow-through is its one purpose; other "
                "items wait for their own message. Never re-ask what they "
                "just told you. The body must NOT be empty even if every "
                "item is excluded.\n")
        else:
            pending_block = (
                "\nUNANSWERED CLIENT MESSAGE — the newest message in this thread "
                "is from the client and nobody has replied yet:\n"
                f"  \"{p_body}\"\n"
                "Your FIRST job is to respond to it like a human would. If the "
                "meeting intel, ops notes or the items below contain the answer, "
                "give it plainly and warmly; if they do not, say you are on it "
                "and will get back to them shortly (never invent an answer). If "
                "it needs no real answer at all (a sign-off, a thank-you with "
                "substance, a commitment), the whole reply is ONE short warm "
                "closing line pointing forward — we are always the one to "
                "close the exchange, never leave the client's last message "
                "hanging. If "
                "the message is angry or a complaint, keep it short, acknowledge "
                "it, and say Santino will reach out personally; never argue. "
                "Do NOT add any outstanding item or extra ask to this "
                "message — responding to them is its one purpose; asks wait "
                "for their own later message. Because a reply is owed, the "
                "body must NOT be empty even if every item is excluded.\n")
    pair_block = ""
    if pair:
        pair_block = (
            "\nLAUNCH-BLOCKER PAIR (explicit exception, Santino 2026-08-03): "
            "the two items given are the ONLY case where one message may "
            "carry TWO asks — the site cannot launch without domain access "
            "and the listing is invisible on Maps without verification, so "
            "they are paired deliberately. Bundle both warmly: lead with the "
            "Google-listing verification, then the domain, and offer ONE "
            "shared 15-minute call to knock out both together (we guide, "
            "they just hold the phone). Never add anything else to this "
            "message.\n")
    commit_block = ""
    if commitment:
        commit_block = (
            "\nOPEN COMMITMENT — Monica already told this client: "
            f"\"{str(commitment.get('promise', ''))[:250]}\" (they had said: "
            f"\"{str(commitment.get('context', ''))[:250]}\").\n"
            "THIS message must deliver on that promise concretely: give the "
            "actual steps or the actual answer, or ask the one concrete "
            "question that unblocks them (for a customer list, the opener is "
            "ONE simple question: \"Where do your previous customer contacts "
            "live?\" — no system menus, no jargon; review campaigns need the "
            "FULL list, hundreds of contacts, so NEVER suggest a screenshot "
            "— Santino 2026-08-02). For a client who reads non-technical "
            "(struggles with 'how do I' tasks), do NOT attempt a text "
            "walkthrough: after that one question, recommend a short "
            "meeting to do it together and propose times. Do not "
            "promise again, do not say you'll follow up later, never make "
            "a new promise this pipeline won't deliver, and do NOT stack "
            "any other ask onto this message — delivering the promise is "
            "its one purpose. The body must NOT be empty.\n")
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
    # GBP-CONNECT LINK RULE (Santino 2026-08-03: "when we send them a message
    # to connect their gbp listing, make sure to attach their connection link
    # too"): whenever a Google-connect ask is among the chosen items, compose
    # is handed the client's short connect link with an explicit must-include
    # instruction; the guard after the draft is the belt (the model dropped a
    # promised link on a real client — MCC 2026-07-25).
    connect_link = google_connect_link(company, chosen) \
        if any(is_google_connect_ask(it) for it in chosen) else None
    connect_block = ""
    if connect_link:
        connect_block = (
            f"\nGoogle connect link for THIS client: {connect_link}\n"
            "One of the items asks them to connect their Google business "
            "listing. If your message makes that ask (even as a side note "
            "next to other content), you MUST include that exact link as "
            "the way to do it (\"here's the link, it takes about two "
            "minutes: ...\"). Never make the connect ask without the "
            "link.\n")
    # Domain-access forward note (2026-08-03): set by the state gate in
    # filter_already_satisfied when access is already in hand.
    domain_block = ""
    if company.get("_domain_forward_note"):
        domain_block = (
            "\nDOMAIN ACCESS — HANDLED: the client already gave us what we "
            "need to put their website live on their real web address "
            "(access is in hand). NEVER ask for domain/registrar access or "
            "logins again in any form. If it fits naturally (especially if "
            "they ask about it), speak forward in plain words: their new "
            "website is being put live on their web address now and we'll "
            "let them know the moment it's up. Do not explain the "
            "mechanics.\n")
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
    ints_lsa = company.get("integration_settings") or {}
    if isinstance(ints_lsa, str):
        try:
            ints_lsa = json.loads(ints_lsa)
        except json.JSONDecodeError:
            ints_lsa = {}
    li = ints_lsa.get("lsa_intent") or {}
    if isinstance(li, str):
        # Legacy shape: ops recorded lsa_intent as a plain string ("yes - LSA
        # already live..., managed by RGP") before the {answer, revisit_on}
        # dict existed. .get() on the str crashed Crew's compose — and with
        # rc=1 the whole GH-Actions run — every cycle 07-30..07-31.
        li = {"answer": li}
    lsa_line = (f"LSA decision: {li.get('answer')}"
                + (f" (revisit {li['revisit_on']})" if li.get("revisit_on") else "")
                if li.get("answer") else "LSA decision: unset")
    user = (f"Client: {company['name']} (first name: {first_name})\n"
            f"Today's date: {today}\n"
            f"{lsa_line}\n"
            f"Channel: {channel} (character budget for SMS: {stated_budget})\n"
            f"FIRST CONTACT: {'yes' if first_contact else 'no'}\n"
            + name_line
            + sister_block
            + (f"Intro line to open with, exactly: \"{intro}\"\n"
               if first_contact else "")
            + history_block
            + intel_block
            + appt_block
            + pending_block
            + pair_block
            + commit_block
            + domain_block
            + photo_block
            + connect_block
            + f"Outstanding items (priority order, cover all of these and "
            f"nothing else):\n" + "\n".join(lines))
    draft = anthropic_json(COMPOSE_SYSTEM, user)
    body = (draft.get("body") or "").strip()
    if channel == "sms" and len(body) > sms_budget:
        # NEVER hard-chop: the old mid-sentence cut + "…" mailed clients
        # dangling half-thoughts and linkless "your preview is up at…"
        # (Kenneth, Isaac, Jose — 2026-07-29). Drop whole trailing sentences
        # instead; if even the first sentence is over budget, send it whole.
        sentences = re.split(r"(?<=[.!?])\s+", body)
        trimmed = ""
        for s in sentences:
            if trimmed and len(trimmed) + len(s) + 1 > sms_budget:
                break
            trimmed = (trimmed + " " + s).strip()
        body = trimmed or body

    # GBP-CONNECT LINK GUARD (the "must not pass" half of the rule): a
    # Google-connect ask never goes out linkless. If the draft (or the
    # budget trim above) asks for the connection without the link, append it
    # as its own complete sentence — the link is load-bearing, so running a
    # little over the SMS budget beats dropping it (the stated budget already
    # left 60 chars of headroom).
    if connect_link and body and connect_link not in body:
        asks_in_body = re.search(
            r"\b(connect|reconnect|sign(?:ing)? in|log ?in|hook(?:ing)? up)\b"
            r"[^.!?]{0,80}\b(google|listing|business profile)\b"
            r"|\b(google|listing)\b[^.!?]{0,80}\b(connect|sign in)\b",
            body, re.I)
        excluded = {str(f.get("item_id"))
                    for k in ("history_answered", "intel_resolved")
                    for f in (draft.get(k) or []) if isinstance(f, dict)}
        ask_live = any(is_google_connect_ask(it)
                       and str(it.get("id")) not in excluded for it in chosen)
        # pending-reply / commitment messages carry no asks by design — only
        # force the link when the body actually made the ask.
        if asks_in_body or (ask_live and not pending_reply and not commitment):
            body = body.rstrip()
            if body[-1:] not in ".!?":
                body += "."
            body += f" Here's the link to connect it: {connect_link}"
            print("  [connect-link] draft asked for the Google connection "
                  "without the link — appended it")

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
            if group[0] not in companies:
                # Orphaned intake/plan rows from a deleted company (the ghost
                # CO-1784568896815 failed the whole 07-30 run). Warn, skip,
                # and DON'T fail the run — a stale row isn't an outage.
                print(f"  !! skipping {group[0]}: company row no longer exists "
                      "(orphaned items — clean them up)")
                continue
            muted = company_inactive(companies.get(group[0]))
            if muted:
                print(f"  skipping {companies[group[0]].get('name', group[0])}: "
                      f"{muted}")
                continue
            try:
                rc = max(rc, cmd_compose(sub))
            except Exception as e:  # noqa: BLE001 — one bad company must never
                # abort the whole --all pass (2026-07-29: an empty Claude
                # response on the first company silently starved 17 others)
                print(f"  !! compose failed for {group[0]}: {str(e)[:160]} — continuing")
                rc = max(rc, 1)
        return rc
    state = load_state()
    companies = fetch_companies([args.company])
    company = companies.get(args.company)
    if not company:
        print(f"ERROR: company {args.company} not found", file=sys.stderr)
        return 1
    muted = company_inactive(company)
    if muted:
        # Hard mute — paused/cancelled accounts get NO drafts and NO sends,
        # scheduled or explicit (Santino 2026-08-04, Mold Solutionz).
        print(f"{company.get('name', args.company)}: {muted} — no draft, "
              "no send.")
        return 0
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
            s_muted = company_inactive(sco)
            if s_muted:
                print(f"  [merge] skipping sister {sco.get('name', scid)}: "
                      f"{s_muted}")
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
            # Re-rank ACROSS the merged pair — a sister's Google-connect must
            # outrank the primary's nice-to-haves (All Pro sat unconnected
            # while Angie got a YouTube ask, 2026-07-30).
            items.sort(key=ask_rank)
    # ALREADY-HAVE CHECK: auto-close asks for things the asset library
    # already holds; defer GBP asks while the listing is suspended.
    items = filter_already_satisfied(company, items, dry_run=not args.send)
    # NOTE: zero outstanding items no longer returns here — an unanswered
    # client message (pending_client_message below) still deserves a reply.
    contact = resolve_contact(company)
    first = contact_first_name(contact, company)
    cs = company_state(state, args.company)
    first_contact = not cs.get("first_contacted")
    # STOP_KEYWORD / CRM DND (Santino 2026-08-03, Angie's accidental "end"):
    # a DND contact is NEVER attempted by SMS — the channel preference flips
    # to email up front (proactive twin of the reactive SendBlocked
    # fallback below; that one stays as the belt for mid-flight DND).
    if _sms_dnd(contact) and not cs.get("channel_override"):
        cs["channel_override"] = "email"
        print("SMS DND on the contact (STOP keyword / CRM) — channel "
              "preference flipped to email")
    elif cs.get("channel_override") == "email" and contact \
            and not _sms_dnd(contact):
        # UN-STICK (Santino 2026-08-04, Angie/All Pro): the override is
        # DND-derived, so when the client lifts DND themselves (texted
        # "Start") it must clear — Angie's answers went to email she wasn't
        # reading while her SMS thread looked ignored.
        cs.pop("channel_override", None)
        print("SMS DND lifted on the contact — email channel override "
              "cleared, back to SMS")
    if (cs.get("channel_override") == "email" and args.channel == "sms"
            and (contact or {}).get("email")):
        args.channel = "email"
        print("Channel override: email (SMS is DND for this contact)")
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
    # RE-INTRO GUARD (Santino 2026-07-29: Kenneth got "this is Monica…" twice).
    # Monica-state alone misses intros sent before state tracking (or from
    # another path) — if the actual thread already contains her intro, this
    # is NOT a first contact regardless of what our state says.
    if first_contact and any(
            m.get("direction") != "in"
            and "this is monica" in str(m.get("body") or "").lower()
            for m in history):
        first_contact = False
        print("First contact OVERRIDE: thread already contains Monica's intro")

    # CLIENT-WAITING BYPASS (Santino 2026-08-02): if the client spoke last
    # and no human answered, this compose is a REPLY, not a nudge — it
    # bypasses the cooldown + nudge cap (business hours, the human-defer
    # window and the canary still apply) and the draft answers them FIRST.
    pending = pending_client_message(cs, history, state)
    if pending:
        label = ("answered our question" if pending["kind"] == "answer"
                 else "waiting on a reply")
        print(f"Client {label}: {pending['body'][:90]!r} "
              "(cooldown/nudge-cap bypassed — this send is a reply, not a nudge)")
    # OPEN COMMITMENT (Santino 2026-08-02: "I'll walk you through it" must
    # actually happen): a promise made in an ack is owed like a reply —
    # same bypass, and the draft is forced to deliver it. Expires at 7 days
    # (by then the thread has moved on; don't dredge up stale promises).
    commitment = cs.get("pending_commitment") or None
    if commitment:
        try:
            stale = (datetime.now(timezone.utc)
                     - datetime.fromisoformat(commitment.get("at", ""))).days >= 7
        except ValueError:
            stale = False
        if stale:
            cs.pop("pending_commitment", None)
            commitment = None
        else:
            print(f"Open commitment to deliver: "
                  f"{str(commitment.get('promise', ''))[:80]!r}")
    owed = bool(pending or commitment)
    if not items and not owed:
        print(f"{company['name']}: nothing outstanding — no message needed.")
        return 0

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
        gate = cadence_check(cs, company, contact,
                             boss_override=has_boss_directive(company.get("id")),
                             client_waiting=owed)
        if gate:
            print(f"[gated, no draft: {gate}]")
            if "ESCALATE" in gate and not cs.get("max_nudges_escalated"):
                append_escalation(company, None,
                                  f"no reply after {MAX_NUDGES} nudges — "
                                  "needs a human touch (call them?)", False,
                                  ping=True)  # ladder tripped — text Santino
                cs["max_nudges_escalated"] = True
                save_state(state, dry_run=False)
            return 0
    appts = None
    if contact:
        tz_name, _tz_src = resolve_timezone(company, contact)
        appts, appt_soonest = fetch_upcoming_appointments(contact["id"], tz_name)
        if appts:
            print(f"Upcoming appointments (live GHL calendar):\n{appts}")
        # MEETING-IMMINENT GATE (Santino 2026-07-29: Monica nudged Fran/QCI
        # right before her kickoff call). Check EVERY contact linked to the
        # company, not just the one we message — Fran was a GUEST on the
        # owner's kickoff booking, invisible on her own contact record.
        ids = {contact["id"]}
        ints_c = (company.get("integration_settings") or {})
        if isinstance(ints_c, str):
            try:
                ints_c = json.loads(ints_c)
            except json.JSONDecodeError:
                ints_c = {}
        for ct_ in ints_c.get("contacts", []) or []:
            if ct_.get("ghl_contact_id"):
                ids.add(ct_["ghl_contact_id"])
        if ints_c.get("ghl_contact_id"):
            ids.add(ints_c["ghl_contact_id"])
        for cid_ in ids:
            if cid_ == contact["id"]:
                soon = appt_soonest
            else:
                _blk, soon = fetch_upcoming_appointments(cid_, tz_name)
            # A pending client message / open commitment disarms this gate:
            # it only stops NUDGES before a call — answering a question or
            # delivering a promise is not a nudge.
            if soon and (soon - datetime.now(timezone.utc)).days < 7 \
                    and not owed:
                print("[gated, no draft: appointment within 7 days on this "
                      f"company's calendar ({soon.strftime('%Y-%m-%d %H:%M UTC')}"
                      f", contact {cid_}) — the call covers the open items; "
                      "no nudge this cycle]")
                return 0
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
    # ESCALATION LADDER (Santino 2026-07-28): 4+ open items AND 2+ outbound
    # nudges with no reply → stop retail-texting; this message proposes a
    # 15-minute setup call and carries the checklist-card image link.
    consecutive_out = 0
    for m_ in history:
        if m_.get("direction") == "out":
            consecutive_out += 1
        else:
            break
    if len(items) >= 4 and consecutive_out >= 2:
        try:
            import subprocess as _sp
            r_ = _sp.run([sys.executable,
                          str(ROOT / "scripts" / "checklist_image.py"),
                          "--company", args.company],
                         capture_output=True, text=True, timeout=120)
            card_url = (r_.stdout or "").strip().splitlines()[-1] if r_.returncode == 0 else ""
        except Exception:
            card_url = ""
        if card_url.startswith("http"):
            intel = ((intel or "") +
                     f"\n\n[ESCALATION LADDER — follow this]\nThis client has {len(items)} "
                     f"open items and {consecutive_out} unanswered nudges. In THIS message: "
                     "lead with wanting to hop on a quick 15-minute call this week to knock "
                     "everything out together (offer 2-3 concrete times plus an easy out), and "
                     f"include this link to a picture of their setup checklist: {card_url} . "
                     "Keep individual asks brief; the call is the main CTA.")
            print(f"[ladder] escalation active — checklist card: {card_url}")
    draft = compose_draft(company, first, items, args.channel, first_contact,
                          history=history, intel=intel, appointments=appts,
                          sister_names=sister_names, pending_reply=pending,
                          commitment=commitment)
    print("\n" + "=" * 62)
    if draft["subject"] and args.channel == "email":
        print(f"Subject: {draft['subject']}")
    print(draft["body"])
    print("=" * 62)
    print(f"({len(draft['body'])} chars, channel={args.channel})")
    # GROUNDING GUARD: a DONE-claim must trace to the ledger portion of the
    # context. Better a blocked send than a lie to a client (Flood Fixers
    # "review request is already out", 2026-08-02).
    grounding = unsupported_done_claim(draft["body"], _evidence_slice(intel))
    if grounding:
        print(f"GROUNDING WARNING: {grounding}")

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

    reason = cadence_check(cs, company, contact,
                           boss_override=has_boss_directive(company.get("id")),
                           client_waiting=owed)
    if reason:
        print(f"\nSEND REFUSED (cadence): {reason}", file=sys.stderr)
        return 0
    if not contact:
        print("\nSEND REFUSED: no GHL contact resolved", file=sys.stderr)
        return 1
    if grounding:
        print(f"\nSEND REFUSED (grounding guard): {grounding}", file=sys.stderr)
        append_escalation(company, None,
                          f"grounding guard blocked a send: {grounding}",
                          False)
        return 0
    # Hard duplicate guard (Santino 2026-08-02: two team-photo asks landed
    # one minute apart): never send a message that near-repeats our own
    # recent last outbound, whatever path drafted it.
    dup = repeats_last_outbound(draft["body"], history)
    if dup:
        print(f"\nSEND REFUSED (duplicate guard): {dup}", file=sys.stderr)
        return 0
    channel_used = args.channel
    try:
        result = send_message(contact, args.channel, draft["body"],
                              draft["subject"])
    except SendBlocked as e:
        # A tripped gate (canary allowlist, DND, paused) is the guardrail
        # WORKING, not an outage — returning 1 here failed the whole
        # GH-Actions run on every cycle with any non-allowlisted nudge
        # target (the workflow had literally never gone green, 08-03).
        # Surface it in Ops Attention ONCE per company+channel, then move on.
        # DND EMAIL FALLBACK (Greg/PuroClean 2026-08-03: his SMS DND sits
        # 'permanent' from a Twilio 21614 "not a valid mobile" — SMS can
        # never land, and he got zero outreach): when the CRM has SMS turned
        # off but the contact has an email, the same message goes out by
        # email instead of going silent. Every other block keeps skip+surface.
        result = None
        if ("DND active" in str(e) and args.channel == "sms"
                and (contact.get("email") or "").strip()):
            print(f"\nSMS blocked by CRM DND — falling back to email "
                  f"({contact.get('email')})", file=sys.stderr)
            try:
                result = send_message(contact, "email", draft["body"],
                                      draft["subject"])
                channel_used = "email"
            except SendBlocked as e2:
                print(f"SEND BLOCKED (email fallback too): {e2}",
                      file=sys.stderr)
        if result is None:
            print(f"\nSEND BLOCKED: {e}", file=sys.stderr)
            if intel_flag_once(state, f"send-block:{args.company}:{args.channel}"):
                append_escalation(company, None, f"send blocked: {e}",
                                  dry_run=False, ping=False)
                save_state(state, dry_run=False)
            return 0
    record_sent_message(state, result)
    # Work ledger (fail-open): one line item per DELIVERED message — logged
    # only after send_message() returned, never on drafts/blocked sends.
    try:
        from work_log import work_log
        verb = "Texted" if channel_used == "sms" else "Emailed"
        work_log(company["id"], "outreach",
                 f"{channel_used}-sent",
                 f"{verb} {first}: {draft['body'][:80]}",
                 evidence={"channel": channel_used,
                           "ghl_contact_id": contact["id"],
                           "chars": len(draft["body"])},
                 actor="monica", source="client_concierge.py compose")
    except Exception as e:  # noqa: BLE001 — ledger must never fail the send path
        print(f"  [work-log] warn: {str(e)[:100]}")
    now = datetime.now(timezone.utc).isoformat()
    cs.pop("awaiting_reply", None)       # this send answered the client
    cs.pop("pending_commitment", None)   # and delivered what was promised
    cs.update({"ghl_contact_id": contact["id"],
               "last_contacted": now,
               "first_contacted": cs.get("first_contacted") or now,
               "nudge_count": cs.get("nudge_count", 0) + 1,
               "last_channel": channel_used})
    save_state(state, dry_run=False)
    # One-shot boss directives ([FROM SANTINO...], [SEND-PREVIEW]) are acted on
    # by THIS send — resolve them so the cadence bypass they grant can't keep
    # firing on every future compose (they'd otherwise stay open until Santino
    # manually hit Done, re-bypassing the cooldown daily).
    try:
        dnotes = _sb("GET", f"/rest/v1/marketing_ops_notes?company_id=eq.{company['id']}"
                     "&status=eq.open&select=id,body&limit=20") or []
        for n in dnotes:
            if str(n.get("body", "")).startswith(("[FROM SANTINO", "[SEND-PREVIEW]")):
                _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{n['id']}",
                    {"status": "resolved", "resolved_at": now})
                print(f"  [directive] acted on + resolved: {n['body'][:70]!r}")
    except Exception as e:  # bookkeeping must never fail the send
        print(f"  [directive] resolve failed: {str(e)[:100]}")
    return 0


# ---------------------------------------------------------------- preview
def preview_compose(company_id: str, channel: str = "sms") -> dict:
    """READ-ONLY preview of the next concierge message for one company — the
    engine behind the Railway POST /concierge-preview endpoint (Santino
    2026-08-03: "Is there a way to see a preview of the upcoming message in
    the app? Or does it generate on the spot?" — it generates on the spot,
    so the preview runs the SAME compose in dry-run). Writes NOTHING: no
    state, no escalations, no sends, no intake/plan mutations. The real send
    may differ slightly because it re-composes with whatever is newest in
    the thread at send time.

    Returns {company, channel, draft, subject, gate, items}:
      gate  = why a real send would currently be refused or deferred
              (cooldown / business hours / human-defer / max nudges), or
              None when a send would go out now. The draft is returned
              either way so the copy can be inspected."""
    state = load_state()
    company = fetch_companies([company_id]).get(company_id)
    if not company:
        return {"error": f"company {company_id} not found"}
    muted = company_inactive(company)
    if muted:
        return {"company": company.get("name"), "channel": channel,
                "gate": muted, "draft": "", "subject": None, "items": []}
    items = gather_items(company_id)
    items = filter_already_satisfied(company, items, dry_run=True)
    contact = resolve_contact(company)
    first = contact_first_name(contact, company)
    # copy: pending_client_message may pop stale flags — never persisted here
    cs = dict(company_state(state, company_id))
    first_contact = not cs.get("first_contacted")
    history = fetch_history(contact["id"]) if contact else []
    if first_contact and any(
            m.get("direction") != "in"
            and "this is monica" in str(m.get("body") or "").lower()
            for m in history):
        first_contact = False
    pending = pending_client_message(cs, history, state)
    commitment = cs.get("pending_commitment") or None
    owed = bool(pending or commitment)
    gate = (human_conversation_deferral(history, state)
            or cadence_check(cs, company, contact,
                             boss_override=has_boss_directive(company_id),
                             client_waiting=owed))
    if not items and not owed:
        return {"company": company.get("name"), "channel": channel,
                "gate": "nothing outstanding — no message would be sent",
                "draft": "", "subject": None, "items": []}
    intel = load_meeting_intel(company)
    appts = None
    if contact:
        tz_name, _src = resolve_timezone(company, contact)
        res = fetch_upcoming_appointments(contact["id"], tz_name)
        appts = res[0] if isinstance(res, tuple) else None
    draft = compose_draft(company, first, items, channel, first_contact,
                          history=history, intel=intel, appointments=appts,
                          pending_reply=pending, commitment=commitment)
    return {"company": company.get("name"), "channel": channel, "gate": gate,
            "draft": draft["body"], "subject": draft.get("subject"),
            "items": [i["text"] for i in draft.get("items", [])]}


# ---------------------------------------------------------------- send now
def send_now(company_id: str, channel: str = "sms") -> dict:
    """One explicit human click on the previewed draft = authorization
    (Santino 2026-08-03, right after loving the Crew preview: "Send now").
    Runs the SAME compose as the preview, then delivers — with
    boss-directive semantics, exactly like an open [FROM SANTINO] note:

      BYPASSED : cooldown + nudge cap (the click IS the authorization),
                 business hours (NOT hard-blocked — the response carries
                 local_time/in_business_hours so the UI confirms first).
      KEPT     : canary allowlist (inside send_message, no override), CRM
                 DND (with the same SMS->email fallback as compose),
                 grounding guard, and the no-double-send duplicate guard —
                 a second immediate click recomposes near-identical copy
                 and is refused by repeats_last_outbound.

    Flows through the normal send path so everything downstream sees a real
    Monica send: sent-ids ledger, work_log outreach line, awaiting/
    commitment bookkeeping, one-shot directive resolution, cadence state.

    Returns {sent: bool, reason?, body?, channel_used?, company,
             local_time, tz, in_business_hours}."""
    state = load_state()
    company = fetch_companies([company_id]).get(company_id)
    if not company:
        return {"sent": False, "reason": f"company {company_id} not found"}
    muted = company_inactive(company)
    if muted:
        # Even the explicit human click refuses on a paused/cancelled
        # account — unpause first if a send is truly intended.
        return {"sent": False, "reason": muted, "company": company.get("name")}
    contact = resolve_contact(company)
    tz_key, _tz_src = resolve_timezone(company, contact)
    local = datetime.now(timezone.utc).astimezone(ZoneInfo(tz_key))
    base = {"company": company.get("name"), "tz": tz_key,
            "local_time": local.strftime("%-I:%M %p"),
            "in_business_hours":
                BUSINESS_HOUR_START <= local.hour < BUSINESS_HOUR_END}
    if not contact:
        return {**base, "sent": False, "reason": "no GHL contact resolved"}
    items = filter_already_satisfied(company, gather_items(company_id),
                                     dry_run=False)
    first = contact_first_name(contact, company)
    cs = company_state(state, company_id)
    first_contact = not cs.get("first_contacted")
    history = fetch_history(contact["id"])
    if first_contact and any(
            m.get("direction") != "in"
            and "this is monica" in str(m.get("body") or "").lower()
            for m in history):
        first_contact = False
    pending = pending_client_message(cs, history, state)
    commitment = cs.get("pending_commitment") or None
    if not items and not (pending or commitment):
        return {**base, "sent": False,
                "reason": "nothing outstanding — no message to send"}
    intel = load_meeting_intel(company)
    appts_res = fetch_upcoming_appointments(contact["id"], tz_key)
    appts = appts_res[0] if isinstance(appts_res, tuple) else None
    draft = compose_draft(company, first, items, channel, first_contact,
                          history=history, intel=intel, appointments=appts,
                          pending_reply=pending, commitment=commitment)
    body = draft["body"]
    if not body:
        return {**base, "sent": False,
                "reason": "compose produced nothing (every item excluded "
                          "by history/meeting intel)"}
    grounding = unsupported_done_claim(body, _evidence_slice(intel))
    if grounding:
        return {**base, "sent": False, "body": body,
                "reason": f"grounding guard: {grounding}"}
    dup = repeats_last_outbound(body, history)
    if dup:
        return {**base, "sent": False, "body": body,
                "reason": f"duplicate guard: {dup}"}
    channel_used = channel
    try:
        try:
            result = send_message(contact, channel, body, draft["subject"])
        except SendBlocked as e:
            # same DND fallback as the scheduled compose path
            if ("DND active" in str(e) and channel == "sms"
                    and (contact.get("email") or "").strip()):
                result = send_message(contact, "email", body, draft["subject"])
                channel_used = "email"
            else:
                raise
    except SendBlocked as e:
        return {**base, "sent": False, "body": body,
                "reason": f"send blocked: {e}"}
    record_sent_message(state, result)
    try:
        from work_log import work_log
        verb = "Texted" if channel_used == "sms" else "Emailed"
        work_log(company_id, "outreach", f"{channel_used}-sent",
                 f"{verb} {first}: {body[:80]}",
                 evidence={"channel": channel_used,
                           "ghl_contact_id": contact["id"],
                           "chars": len(body), "trigger": "send-now"},
                 actor="monica", source="client_concierge.py send_now")
    except Exception as e:  # noqa: BLE001
        print(f"  [work-log] warn: {str(e)[:100]}")
    now = datetime.now(timezone.utc).isoformat()
    cs.pop("awaiting_reply", None)
    cs.pop("pending_commitment", None)
    cs.update({"ghl_contact_id": contact["id"], "last_contacted": now,
               "first_contacted": cs.get("first_contacted") or now,
               "nudge_count": cs.get("nudge_count", 0) + 1,
               "last_channel": channel_used})
    save_state(state, dry_run=False)
    try:  # one-shot boss directives are satisfied by this send too
        dnotes = _sb("GET", f"/rest/v1/marketing_ops_notes?company_id=eq.{company_id}"
                     "&status=eq.open&select=id,body&limit=20") or []
        for n in dnotes:
            if str(n.get("body", "")).startswith(("[FROM SANTINO", "[SEND-PREVIEW]")):
                _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{n['id']}",
                    {"status": "resolved", "resolved_at": now})
    except Exception as e:  # noqa: BLE001
        print(f"  [directive] resolve failed: {str(e)[:100]}")
    return {**base, "sent": True, "body": body, "channel_used": channel_used}


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

IMAGES: when the client's message included photos or screenshots, they are
attached to this request — base your summary, matching and suggested_reply
on what the image ACTUALLY shows, never on a guess. KNOWN CASE (Santino
2026-08-02): a screenshot of a browser security interstitial hit while
opening our connect/preview link (Chrome "Your connection is not private" /
"the site ahead" warning page) — the fix is one step and you may give it
directly, modeled on Santino's own wording: 'Click the advanced button and
then the "proceed to restoration ai"'. That case is needs_answer with
response_needed "answer" and the fix as the suggested_reply.

PURPOSE QUESTIONS: when the client asks WHY we are asking something
("what's the purpose of that question?"), the answer MUST come from that
item's purpose= text in the list. If the item shows no purpose= text, set
needs_answer with a holding line — NEVER invent a reason (2026-08-03:
Monica told a client the supplier question was "for the ads setup" when
its real purpose is the supplier/dealer listing links program).

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

CONTACT CARDS: a bracketed note like "(the client texted N contact
card(s): ...)" means they shared vCards — real customer contacts, already
parsed and filed on our side. That is SUBSTANTIVE content, never a failed
attachment and never escalate-worthy by itself: response_needed is
"acknowledge", and suggested_reply is a short forward ack that may name the
person ("Got Ed's contact, thanks"). One or a few texted cards are NOT the
full customer list — do not match a customer-list item on cards alone.
GROUNDING: receiving a card never means a review request went out; never
say or imply anything was sent to those people (enrolling them is a human
decision on our side, not something to discuss with the client).

If the reply asks to MOVE/RESCHEDULE/CANCEL an upcoming call or meeting
("can we reschedule?", "can't make it Tuesday", "push it a few days"), set
"reschedule" with their timing preference in plain words — that is handled
by a booking flow, not escalation. Do not also set escalate for this.

NEEDS-ANSWER DETECTION: set "needs_answer": true whenever the reply asks us
anything (with or without a question mark — "I wonder why they suspended
the listing" IS a question) OR says they don't know how / can't do / are
stuck on something we asked ("I don't know how to send all customers at
once") — anything a good assistant must actually ANSWER or walk them
through, not just thank them for. Additionally set "needs_santino": true
ONLY when the boss himself must answer: pricing, billing, contracts,
strategy, complaints about our service, cancellation talk. How-to, setup,
status and "why did X happen" questions are needs_answer WITHOUT
needs_santino — the assistant handles those herself.

FULL ANALYSIS — required for EVERY message, even pure acknowledgments
(the boss's spec 2026-08-02: every inbound gets analyzed — does it need a
response, does it need escalation, and what should the response be):
"analysis": {
  "summary": one plain line saying what the client is saying or needs,
  "response_needed": "none" | "acknowledge" | "answer" | "answer_by_boss",
  "suggested_reply": the exact reply Monica should send, or null when
                     response_needed is "none"}
suggested_reply rules — Monica's voice: warm, brief (under 300 characters),
plain 6th-grade words, NEVER em or en dashes (use a comma or period), no
emojis, no canned filler ("Perfect, thanks for getting back to me" is
banned). Respond to what they SAID. When they are stuck ("I don't know how
to..."), do the FIRST STEP of the walk-through right now: ask ONE simple
question that unblocks them (customer list example: "Where do your
previous customer contacts live?" — plain words, no system menus; a
review campaign needs the FULL list, hundreds of contacts, so never
suggest a screenshot). For a non-technical client (Santino 2026-08-02:
"someone like Todd, definitely just recommend a meeting"), the next move
after that one question is a short meeting to do it together — propose
times, don't text a multi-step walkthrough at them.
Conversation rules for suggested_reply (Santino 2026-08-02):
- Mid-conversation, so do NOT open with their name; start with content
  ("Got it...", "No problem..."). Names at most once per day of thread.
- At most ONE question; never stack a second ask onto the reply.
- ACKNOWLEDGE FORWARD, never echo their message back as a summary ("got
  it, you'll grab a photo when you're back" is banned; "Thanks, definitely
  send those over when you get back into town" is the model).
- If the client COMMITTED to do something later, the whole reply is that
  warm forward-pointing close, nothing else.
- GROUNDING: never claim an action already happened (sent / out / posted /
  live) — this reply is drafted without ledger evidence; speak forward
  ("we're getting that set up"), never past tense about our own work.
Only promise a follow-up when the answer genuinely needs research we
cannot do in this text, and say specifically what you will come back with.
When response_needed is "answer" and the open items / history / intel
contain the answer, give it plainly; otherwise write a specific holding
line. NEVER promise anything that will not actually happen.

Return ONLY JSON:
{"matches": [{"item_id": "<id from the list>", "value": "<extracted answer>",
              "answer_type": "license|yes_no|free_text|customer_list"}],
 "intel_resolved": [{"item_id": "<id from the list>", "reason": string}],
 "ack": bool,
 "needs_answer": bool,
 "needs_santino": bool,
 "analysis": {"summary": string,
              "response_needed": "none|acknowledge|answer|answer_by_boss",
              "suggested_reply": string|null},
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
dashes; use a comma or a period instead.
- This is mid-conversation: do NOT open with their name ("Hey Todd," /
  "Thanks, Todd,") — start with content: "Got it...", "Sounds good...",
  "Perfect..." (Santino 2026-08-02: names at most once per day).
- ACKNOWLEDGE FORWARD, never echo: never restate what they said as a
  summary ("got it, you'll grab a photo when you're back"). Point forward:
  "Thanks, definitely send those over when you get back into town."
- If they COMMITTED to do something later ("I'll get the photo when I'm
  back"), the ENTIRE reply is that warm forward-pointing close. No next
  question, no extra ask.
- Otherwise advance with at most ONE next question — the single
  highest-priority open item provided, nothing stacked on. When the
  natural next step after their answer is hands-on (exporting a list,
  account settings) and the client reads non-technical, propose a short
  call to do it together instead of text steps (Santino 2026-08-02).
- If nothing remains, close warmly ("that's everything we needed").
- GROUNDING: never claim our work is already done (sent / out / posted /
  live). You see only the thread, not the ledger — speak forward ("we're
  getting that set up now"), never "is already out" (2026-08-02).
SMS-length: <= 450 chars. No emojis.
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
            # Reaction events (Liked "...") are not messages — drop them
            # here so neither the poll nor the webhook ever processes one.
            if _REACTION_RE.match(body):
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


def _vcard_phone(raw_tel: str) -> str:
    """Normalize a vCard TEL to +1XXXXXXXXXX when it reads as a US number
    (iPhone exports both '(760) 505-7855' and bare '17605355181')."""
    tel = re.sub(r"[^\d+]", "", raw_tel or "")
    digits = tel.lstrip("+")
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return tel


def parse_vcards(raw: bytes) -> list[dict]:
    """Tiny vCard reader for texted contact cards — no deps (iPhone shares
    are simple VERSION:3.0 files, see Gabriel's two on 2026-08-01). Handles
    folded lines (continuation starts with space/tab), item1.-style group
    prefixes, ;TYPE=... params, backslash escapes, and multiple cards per
    file. Returns [{"name","phone","email"}] — first TEL/EMAIL per card
    wins, FN preferred over an assembled N."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")
    lines: list[str] = []
    for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if ln[:1] in (" ", "\t") and lines:
            lines[-1] += ln[1:]        # unfold RFC 6350 continuation
        else:
            lines.append(ln)

    def unesc(v: str) -> str:
        return (v.replace("\\n", " ").replace("\\N", " ")
                 .replace("\\,", ",").replace("\\;", ";")
                 .replace("\\\\", "\\").strip())

    cards: list[dict] = []
    cur: dict | None = None
    for ln in lines:
        if ":" not in ln:
            continue
        prop, _, value = ln.partition(":")
        prop = prop.split(".", 1)[-1]              # strip "item1." group
        pname = prop.split(";", 1)[0].strip().upper()   # strip TYPE params
        if pname == "BEGIN" and value.strip().upper() == "VCARD":
            cur = {"name": "", "phone": "", "email": "", "_n": ""}
        elif cur is None:
            continue
        elif pname == "END" and value.strip().upper() == "VCARD":
            cur["name"] = cur["name"] or cur["_n"]
            if cur["name"] or cur["phone"] or cur["email"]:
                cards.append({k: v for k, v in cur.items() if k != "_n"})
            cur = None
        elif pname == "FN" and not cur["name"]:
            cur["name"] = unesc(value)
        elif pname == "N" and not cur["_n"]:
            parts = value.split(";")
            family = unesc(parts[0]) if parts else ""
            given = unesc(parts[1]) if len(parts) > 1 else ""
            cur["_n"] = " ".join(p for p in (given, family) if p)
        elif pname == "TEL" and not cur["phone"]:
            cur["phone"] = _vcard_phone(unesc(value))
        elif pname == "EMAIL" and not cur["email"]:
            cur["email"] = unesc(value)
    return cards


def _fmt_card(c: dict) -> str:
    bits = " ".join(x for x in (c.get("name"), c.get("phone"),
                                c.get("email")) if x)
    return bits or "contact card (could not parse — raw .vcf saved)"


def ingest_inbound_media(company: dict, msg: dict, dry_run: bool) -> dict:
    """File a client's texted photos/videos where the hub upload page puts
    them, so nothing a client sends is ever lost:
      photos       -> branding/{cid}/job-photos/        (weekly GBP poster feed)
      screenshots  -> branding/{cid}/job-photos/inbox/  (very tall images are
                      usually phone screenshots, not job photos — quarantined
                      so they never get posted to Google)
      videos       -> branding/{cid}/job-videos/        (the GBP poster only
                      handles PHOTO media; keep its folder clean)
      contacts     -> client-contacts/{cid}/contacts/   (texted vCards — a
                      shared customer contact used to die in "failed" and
                      only survive if a human copied it into a note; Gabriel
                      / Flood Fixers 2026-08-01. Raw .vcf kept + parsed
                      name/phone/email returned in "contact_cards".
                      PRIVATE bucket, service-role only: vCards carry
                      customer names+phones, so they must never live in the
                      public 'branding' bucket like the media does)
    Images are re-encoded (EXIF/GPS stripped) like the upload page does."""
    out = {"photos": 0, "screenshots": 0, "videos": 0, "contacts": 0,
           "failed": 0, "contact_cards": []}
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
            fname = url.rsplit("/", 1)[-1].split("?", 1)[0]
            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
            stamp = "{}-{}".format(int(msg["ts"].timestamp() * 1000),
                                   hashlib.sha1(url.encode()).hexdigest()[:8])
            sb_url = os.environ["SUPABASE_URL"].rstrip("/")
            sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
            bucket = "branding"                 # public — media only, no PII
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
            elif "vcard" in ctype or ext == "vcf":
                # A texted contact card is CONTENT, never "failed": keep the
                # raw .vcf and surface the parsed contact to the caller (ops
                # note + ack). No auto-enrollment happens here or downstream
                # — review-campaign sender gates are a human decision.
                cards = parse_vcards(raw) or [
                    {"name": "", "phone": "", "email": ""}]
                out["contact_cards"].extend(cards)
                path = f"{cid}/contacts/sms-{stamp}.vcf"
                bucket = "client-contacts"      # PRIVATE — customer PII
                body, up_type, kind = raw, "text/vcard", "contacts"
            else:
                out["failed"] += 1
                continue
            if dry_run:
                print(f"    [dry-run] would store {kind[:-1]} -> {bucket}/{path}")
            else:
                up = requests.post(
                    f"{sb_url}/storage/v1/object/{bucket}/{path}", data=body,
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


def file_contact_note(company: dict, cards: list[dict],
                      open_items: list[dict], contact_payload: dict | None,
                      dry_run: bool) -> None:
    """ONE open ops note per inbound batch of contact cards, so shared
    customers surface on the Ops Attention board instead of living only in
    a hand-written note (the Ed/Steve lesson, 2026-08-01). If an open
    intake item is about the customer list, the linkage is noted. This
    files paperwork only — it never enrolls anyone in a review campaign."""
    sender = contact_first_name(contact_payload, company)
    lines = [f"[CONTACT RECEIVED] {_fmt_card(c)} — sent by {sender} via "
             "text; likely a review-campaign customer" for c in cards]
    body = "\n".join(lines)
    linked = next((i for i in open_items if re.search(
        r"customer.{0,40}(list|contact)|(list|contact).{0,40}customer"
        r"|past customers|review.{0,30}(campaign|request)",
        i.get("text") or "", re.I)), None)
    if linked:
        body += (f"\n(likely relates to open {linked['kind']} item "
                 f"{str(linked['id'])[:8]}: {linked['text'][:120]!r})")
    body += ("\n(raw .vcf saved to private client-contacts/{}/contacts/ — "
             "NOT enrolled in any review campaign; sender gates are a human "
             "decision)".format(company.get("id")))
    if dry_run:
        print(f"    [dry-run] would file ops note:\n      "
              + body.replace("\n", "\n      "))
        return
    try:
        _sb("POST", "/rest/v1/marketing_ops_notes",
            {"company_id": company.get("id"), "body": body,
             "status": "open"}, prefer="return=minimal")
        print(f"    [contacts] ops note filed ({len(cards)} contact(s))")
    except Exception as e:  # noqa: BLE001 — never lose the contact silently
        print(f"    [contacts] ops-note insert failed ({e}) — escalating",
              file=sys.stderr)
        append_escalation(company, None, "contact card(s) received but the "
                          f"ops note failed to write: {body[:300]}", dry_run)


def apply_answer(item_id: str, value: str, dry_run: bool) -> None:
    body = {"status": "answered", "answer": {"value": value},
            "answered_at": datetime.now(timezone.utc).isoformat()}
    if dry_run:
        print(f"    [dry-run] would PATCH client_intake_items/{item_id[:8]} -> {body}")
        return
    _sb("PATCH", f"/rest/v1/client_intake_items?id=eq.{item_id}", body,
        prefer="return=minimal")


def resolve_plan_row(row_id: str, dry_run: bool,
                     answer: str | None = None) -> None:
    """Resolve a plan ask; the client's answer is APPENDED to the rationale
    so it survives (Curt/Home Pride 2026-08-03: "Yes, we do these services"
    resolved the row and the answer text vanished)."""
    if dry_run:
        print(f"    [dry-run] would PATCH marketing_action_plan/{row_id[:8]} "
              f"-> resolved" + (f" + record answer {answer[:50]!r}"
                                if answer else ""))
        return
    body: dict = {"status": "resolved"}
    if answer:
        try:
            rows = _sb("GET", f"/rest/v1/marketing_action_plan?id=eq.{row_id}"
                       "&select=rationale") or []
            old = str((rows[0] if rows else {}).get("rationale") or "")
            stamp = datetime.now(timezone.utc).date()
            body["rationale"] = (old + f"\n\nCLIENT ANSWERED ({stamp}): "
                                 + answer[:300]).strip()
        except Exception as e:  # noqa: BLE001 — bookkeeping never blocks resolve
            print(f"    [plan-answer] rationale append failed: {str(e)[:80]}")
    _sb("PATCH", f"/rest/v1/marketing_action_plan?id=eq.{row_id}",
        body, prefer="return=minimal")


_AFFIRMATIVE_RE = re.compile(
    r"^\s*(?:yes|yep|yeah|yup|correct|we do|all of|absolutely|for sure)", re.I)
_QUALIFIER_RE = re.compile(r"\b(?:not|don'?t|except|only|no longer|stopped)\b",
                           re.I)


def route_confirmed_services(company: dict, answer: str, dry_run: bool) -> None:
    """The client answered the GBP service sanity-check ("ASK CLIENT:
    confirm N service(s) on their Google listing"). Route it.

    Clear YES -> AUTO-APPLY (Santino 2026-08-03 policy change: "If Curt
    says yes, why not just add it automatically? Waiting for my approval
    doesn't seem necessary — they've already confirmed"). No approval
    click: gbp.apply_confirmed_services() writes the confirmed services to
    the GBP listing NOW (each add recorded in marketing_gbp_changes),
    queues the service pages into marketing_page_requests (the site
    content pipeline drains it), flips the board cards to done WITH the
    evidence (visible, never hidden), and writes the work-log line items.
    CATEGORY changes are never auto-applied — those keep the app's
    one-click approval (highest-stakes GBP edit).

    Mixed/negative ("we do X but not Y") -> never bulk-apply; escalate to
    the digest so a human maps which services survive."""
    cid = company.get("id")
    ans = (answer or "").strip()
    if not (_AFFIRMATIVE_RE.match(ans) and not _QUALIFIER_RE.search(ans)):
        append_escalation(company, None,
                          "client gave a mixed or negative answer to the "
                          f"GBP service confirm ({ans[:120]!r}) — map which "
                          "services to keep manually in Marketing -> "
                          "Locations", dry_run)
        return
    try:
        import gbp  # same scripts/ dir
        res = gbp.apply_confirmed_services(cid, answer=ans, dry_run=dry_run)
        print("    [svc-confirm] auto-apply: "
              f"{len(res.get('added') or [])} added to the listing, "
              f"{len(res.get('kept') or [])} confirmed-kept, "
              f"{len(res.get('pages_queued') or [])} page(s) queued"
              + (f", {len(res['categories_pending'])} categor(ies) left for "
                 "one-click approval" if res.get("categories_pending") else ""))
        for err in res.get("errors") or []:
            print(f"    [svc-confirm] ERROR: {err}")
            append_escalation(company, None,
                              f"confirmed-services auto-apply hit an error: "
                              f"{err[:200]}", dry_run)
    except Exception as e:  # noqa: BLE001 — routing must never kill the poll
        print(f"    [svc-confirm] routing failed: {str(e)[:100]}")


# ---------------------------------------------------------- advice loop
# (Santino 2026-07-30: "can Monica come to me for advice on what to say?").
# Every escalation also TEXTS Santino; his reply (caught by the inbound
# poll) becomes an ops note the next compose treats as instructions.
ADVICE_CONTACT_ID = os.environ.get("OPS_ADVICE_CONTACT_ID", "MIJ5Jm4sobdzSRtnYSzU")
ADVICE_PHONE = os.environ.get("OPS_ADVICE_PHONE", "+18089891078")
_ADVICE_SENT_THIS_RUN = {"n": 0}

ADVICE_MATCH_SYSTEM = """\
Santino (the boss) was texted one or more open questions about clients. He
just replied. Decide which open question his reply answers and restate his
instruction plainly for the assistant to act on.
Return ONLY JSON: {"index": <int index of the question answered, or null if
his reply clearly is not an answer to any of them>, "instruction": "<his
directive, restated as a clear instruction, keeping any links exactly>"}"""

# Boss-facing SMS copy (Santino 2026-08-02: "Intel says finished job photos
# ... have been answered/in progress" reached his phone verbatim). Every
# text to Santino is rewritten from internal system reasons into how a human
# assistant texts her boss — the raw reason still goes to the escalations
# table untouched, so dedupe hashes and the Ops Attention view keep the
# stable wording.
BOSS_SMS_SYSTEM = """\
You are Monica, Santino's assistant, texting HIM (your boss) a short
heads-up about his clients. The input is one or more internal system notes.
Rewrite them the way a sharp human assistant texts her boss: plain English,
specific, brief.
- Name the person and company when the notes show them, e.g. "Todd from Go
  Green replied, he doesn't know how to send the customer list. I'll walk
  him through it."
- Say what actually happened, then what you need from him or what you will
  do next.
- ABSOLUTELY no system jargon: never "intel", "escalation", "nudge",
  "item", "classified", "answered/in progress", no ids, no slash-separated
  statuses, no internal file or table names.
- No em or en dashes, no emojis. One short line per client; whole text
  under 600 characters.
Return ONLY JSON: {"body": string}."""


def humanize_boss_sms(raw: str, ask_for_decision: bool = False) -> str | None:
    """Rewrite internal system notes into the SMS Santino actually reads.
    Returns None on any failure so callers fall back to the raw text — a
    lost alert is worse than an ugly one."""
    try:
        draft = anthropic_json(
            BOSS_SMS_SYSTEM,
            (("These need his decision — end by asking him to reply with "
              "what to do.\n") if ask_for_decision else
             ("These are heads-up notes — say what happened and what you'll "
              "do about it.\n"))
            + "Internal notes:\n" + raw[:1200])
        text = (draft.get("body") or "").strip()
        return text[:900] or None
    except Exception as e:  # noqa: BLE001 — copy polish must never eat an alert
        print(f"  [boss-sms] humanize failed ({str(e)[:80]}) — raw copy",
              file=sys.stderr)
        return None


def _advice_requests() -> list:
    return kv_get("advice-requests") or []


def ask_santino_for_advice(company: dict, reason: str, dry_run: bool,
                           client_msg: str | None = None) -> None:
    if _ADVICE_SENT_THIS_RUN["n"] >= 5:
        return  # never blow up his phone in one pass
    reqs = _advice_requests()
    now = datetime.now(timezone.utc)
    for r in reqs:
        if r.get("company_id") != company.get("id"):
            continue
        # ONE open ask per company — the model re-words the same underlying
        # question every cycle, so matching on reason text is no dedupe at
        # all (07-31: 17 near-identical All Pro texts in five hours).
        if r.get("status") == "open":
            return  # already asked, still waiting on Santino
        # And even after an answer, don't re-ask about the same company for
        # 24h — if the situation is truly new, tomorrow is soon enough.
        try:
            asked = datetime.fromisoformat(r.get("asked_at", ""))
            if (now - asked) < timedelta(hours=24):
                return
        except ValueError:
            pass
    if dry_run:
        print(f"    [dry-run] would text Santino for advice: {reason[:80]}")
        return
    # Human copy for his phone; the raw reason stays in the escalation row.
    body = (humanize_boss_sms(
                f"[{company.get('name', '?')}] {reason[:300]}"
                + (f"\nThe client's own words: {client_msg[:200]!r}"
                   if client_msg else ""),
                ask_for_decision=True)
            or (f"Monica here. Need your call on {company.get('name', '?')}: "
                f"{reason[:300]} Reply with what to do and I'll take it "
                f"from there."))
    try:
        send_message({"id": ADVICE_CONTACT_ID, "phone": ADVICE_PHONE}, "sms", body)
        _ADVICE_SENT_THIS_RUN["n"] += 1
        reqs.append({"company_id": company.get("id"),
                     "company_name": company.get("name"),
                     "reason": reason[:300],
                     "asked_at": datetime.now(timezone.utc).isoformat(),
                     "status": "open"})
        kv_set("advice-requests", reqs)
        print("    advice request texted to Santino")
    except SendBlocked as e:
        print(f"    advice SMS blocked: {e}")


def append_escalation(company: dict, msg: dict | None, reason: str,
                      dry_run: bool, ping: bool = False) -> None:
    """Append one escalation block. msg is the triggering inbound message when
    there is one; compose-side escalations (history-answered items, human-
    conversation deferrals) pass msg=None.

    NOTIFICATION POLICY (Santino 2026-08-02: "I should not be texted every
    time a client responds"): ping=True texts Santino now (advice loop +
    end-of-run summary) — reserve it for (a) a tripped escalation ladder
    (max nudges, angry client), (b) something needing HIS action or
    decision, (c) a client question Monica can't answer herself. The
    default ping=False still writes concierge_escalations (the app's Ops
    Attention view) and reaches him in the morning digest email
    (concierge_digest.py) — bookkeeping flags and FYIs go there, never to
    his phone mid-day."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = (f"\n## {stamp} — {company.get('name', '?')} ({company.get('id', '?')})\n"
             + (f"- Channel: {msg['channel']}  Message id: {msg['id']}\n"
                f"- Reply: {msg['body'][:400]!r}\n" if msg else "")
             + f"- Reason: {reason}\n")
    if ping:
        _OPS_PINGS.append((company.get("name", "?"), reason))
        ask_santino_for_advice(company, reason, dry_run,
                               client_msg=(msg or {}).get("body"))
    if dry_run:
        print(f"    [dry-run] would append escalation:{block}")
        return
    try:
        _sb("POST", "/rest/v1/concierge_escalations",
            {"company_id": company.get("id"), "company_name": company.get("name"),
             "reason": reason,
             # msg carries datetime objects from inbound parsing — stringify
             # or the insert 400s and escalations silently drop to a local
             # file nobody watches (found 2026-07-29)
             "message": json.loads(json.dumps(msg, default=str)) if msg else None},
            prefer="return=minimal")
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
        print(f"  [dry-run] would ops-ping {OPS_PING_CELL} (raw; humanized "
              f"at send time):\n{body}")
        return
    # Humanize ONLY here, after the dedupe: the hash must stay on the raw
    # stable wording (LLM rewrites vary per run and would defeat it, the
    # exact failure of the 07-31 advice-storm). Falls back to raw copy.
    send_body = humanize_boss_sms("\n".join(lines)) or body
    try:
        send_message({"id": OPS_PING_CONTACT_ID, "phone": OPS_PING_CELL},
                     "sms", send_body)
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
                          "found on their contact — needs a human", dry_run,
                          ping=True)  # needs his action
        return
    cur = datetime.strptime(appt["startTime"], "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=ZoneInfo(GHL_LOCATION_TZ)).astimezone(ZoneInfo(tz))
    slots = _free_slots(appt["calendarId"], tz)
    offers = _pick_offer_slots(slots, cur, tz)
    if not offers:
        append_escalation(company, None,
                          "reschedule requested but no free slots in the next "
                          "8 days — needs a human", dry_run,
                          ping=True)  # needs his action
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
                                  f"update FAILED ({e}) — fix manually", dry_run,
                                  ping=True)  # needs his action
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


# Vision for inbound analysis (Santino 2026-08-02: Angie texted a
# screenshot of a browser warning; Monica couldn't see it and Santino had
# to answer manually). Cost guard: only the first VISION_MAX_IMAGES images
# per message, videos/documents skipped, big images downscaled + JPEG
# re-encoded before the base64 ride to the model.
VISION_MAX_IMAGES = 2


def _vision_blocks(attachments: list | None) -> list[dict]:
    """Download up to VISION_MAX_IMAGES image attachments (GHL CDN URLs)
    and prep them for anthropic_json(images=...). Never fatal."""
    out: list[dict] = []
    for url in attachments or []:
        if len(out) >= VISION_MAX_IMAGES:
            break
        ext = str(url).rsplit(".", 1)[-1].lower()
        if ext in ("mp4", "mov", "m4v", "mpg4", "avi", "vcf", "pdf", "csv"):
            continue   # videos/documents: never sent to vision
        try:
            r = requests.get(url, timeout=45)
            r.raise_for_status()
            ctype = (r.headers.get("Content-Type") or "").lower()
            if not (ctype.startswith("image/")
                    or ext in ("jpg", "jpeg", "png", "webp", "heic", "gif")):
                continue
            from io import BytesIO
            from PIL import Image
            img = Image.open(BytesIO(r.content)).convert("RGB")
            w, h = img.size
            if max(w, h) > 1568:   # vision sweet spot; keeps payloads small
                s = 1568 / max(w, h)
                img = img.resize((round(w * s), round(h * s)))
            buf = BytesIO()
            img.save(buf, "JPEG", quality=80)
            out.append({"media_type": "image/jpeg",
                        "data": base64.b64encode(buf.getvalue()).decode()})
        except Exception as e:  # noqa: BLE001 — a bad image must not kill the poll
            print(f"    [vision] attachment skipped ({str(e)[:60]})")
    return out


# Shared ledger of processed inbound message ids. The 5-min poll and the
# instant webhook (webhook_inbound) both read the same GHL threads — this,
# not the poll's cursor, is what stops the second entry point from
# re-replying to a message the first already handled.
HANDLED_IDS_MAX = 400


def _record_handled(state: dict, msg_id: str) -> None:
    ids = state.setdefault("handled_msg_ids", [])
    if msg_id and msg_id not in ids:
        ids.append(msg_id)
        del ids[:-HANDLED_IDS_MAX]   # bound the ledger, keep the newest


def process_inbound_messages(state: dict, company: dict, contact_id: str,
                             msgs: list[dict], do_send: bool, dry_run: bool,
                             compose_next: bool = False) -> dict:
    """Analyze + act on one contact's new inbound messages — the shared
    engine behind the 5-min poll (cmd_inbound) and the instant webhook
    (webhook_inbound). EVERY message gets one full classify+analysis call
    (Santino's spec 2026-08-02: does it need a response, does it need
    escalation, what should the response be) — but the burst is answered as
    ONE CONVERSATIONAL TURN: analysis + answer extraction run per message
    (phase 1, no sends), then exactly one outbound decision covers the
    whole batch (phase 2). Before this, "Blue like water" and "And white"
    seconds apart each got their own ack+question — two near-duplicate
    texts back to back (2026-08-02 16:12).

    compose_next=True is the webhook path: an immediate compose for this
    company follows, so anything owed (answer follow-through, question) is
    left to it — no thin inline reply plus a second text seconds later.
    Messages are deduped across entry points via the handled-ids ledger;
    each id is recorded BEFORE processing so a mid-message crash can never
    storm (the 07-31 lesson: prefer losing one reply over resending
    forever).

    Returns {"processed", "matched", "awaiting", "escalated"}."""
    company_id = company["id"]
    out = {"processed": 0, "matched": 0, "awaiting": False, "escalated": 0}
    handled = set(state.get("handled_msg_ids") or [])
    msgs = [m for m in msgs if m["id"] not in handled]
    if not msgs:
        return out
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
    if do_send:
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
    # STOP_KEYWORD / CRM DND: flip the channel preference the moment the
    # contact record shows SMS DND, so no path ever attempts SMS again.
    if _sms_dnd(contact_payload) and not cs_reset.get("channel_override"):
        cs_reset["channel_override"] = "email"
        print("  [dnd] SMS DND on contact — channel preference flipped to email")
    elif (cs_reset.get("channel_override") == "email" and contact_payload
            and not _sms_dnd(contact_payload)):
        # Symmetric un-stick (Angie 2026-08-04: she texted "Start" to lift
        # her own DND, but the sticky override kept every reply on email).
        cs_reset.pop("channel_override", None)
        print("  [dnd] SMS DND lifted — email override cleared, back to SMS")
    # ---- phase 1: per-message analysis + answer extraction. NO sends here;
    # everything response-worthy accumulates into `turn` for one decision.
    turn = {"bodies": [], "matched": set(), "intel": set(),
            "needs_answer": False, "needs_santino": False, "negative": False,
            "suggested": None, "last_msg": None, "closer_only": False,
            "contact_cards": []}
    for msg in msgs:
        out["processed"] += 1
        _record_handled(state, msg["id"])
        print(f"\n  {company['name']}: inbound {msg['channel']} "
              f"{msg['ts'].strftime('%m-%d %H:%M')}: {msg['body'][:90]!r}")
        # Belt-and-suspenders: fetch_inbound_since already drops reaction
        # events, but nothing that renders as one may ever reach a reply.
        if _REACTION_RE.match((msg.get("body") or "").strip()):
            print("    [reaction event — not a message, nothing to do]")
            continue
        # BARE STOP-WORD ("end", "stop", ...): the carrier just flipped this
        # contact to permanent SMS DND — no classify, no reply. Escalate to
        # Santino once with the fix in hand, switch the thread to email.
        if (msg.get("channel") == "sms"
                and _STOP_WORD_RE.match((msg.get("body") or "").strip())):
            cs_reset["channel_override"] = "email"
            print(f"    [STOP keyword {msg['body'].strip()!r} — SMS DND is "
                  "now permanent; switching this contact to email]")
            if not cs_reset.get("dnd_escalated"):
                cs_reset["dnd_escalated"] = True
                append_escalation(
                    company, msg,
                    f"client texted the SMS stop-word {msg['body'].strip()!r} "
                    "(likely accidental mid-conversation) — the carrier set "
                    "PERMANENT SMS DND which we cannot lift. Fix: have them "
                    "text START back to our number to re-enable texting. "
                    "Monica reaches them by email meanwhile.",
                    dry_run, ping=True)  # needs Santino's action
            continue
        had_cards = False
        if msg.get("attachments"):
            media = ingest_inbound_media(company, msg, dry_run)
            print(f"    [media] photos={media['photos']} "
                  f"videos={media['videos']} "
                  f"screenshots={media['screenshots']} "
                  f"contacts={media['contacts']} "
                  f"failed={media['failed']}")
            if media["contact_cards"]:
                # A vCard is SUBSTANTIVE content (a customer the client is
                # handing us, likely for the review campaign) — never the
                # failed-media path. One ops note covers the whole batch
                # (filed after this loop); here the analysis just gets the
                # facts so the ack reads "Got Ed's contact, thanks", with
                # grounding intact: receiving a card is NOT evidence any
                # review request was sent. Gate on the PARSE result, not the
                # upload counter — the parsed contact must survive even a
                # storage hiccup (the .vcf upload 415'd until text/vcard was
                # added to the branding bucket's allowed MIME types,
                # 2026-08-02).
                had_cards = True
                turn["contact_cards"].extend(media["contact_cards"])
                who = "; ".join(_fmt_card(c) for c in media["contact_cards"])
                note = (f"the client texted "
                        f"{len(media['contact_cards'])} contact "
                        f"card(s): {who} — parsed and filed for the team "
                        "as likely review-campaign customers. Nothing has "
                        "been sent to these people and nothing may be "
                        "claimed as sent")
                if msg["body"]:
                    msg["body"] += f"\n({note})"
                else:
                    msg["body"] = (f"({note}. Treat this as them sharing "
                                   "customer contacts: thank them briefly, "
                                   "forward-looking)")
            if not msg["body"]:
                if media["photos"] or media["videos"]:
                    # Give the normal reply flow something to acknowledge
                    # (marks photo intake items answered + thanks them).
                    n = media["photos"] + media["videos"]
                    msg["body"] = (
                        f"(the client texted {n} photo(s)/video(s) with no "
                        "message — the images are attached; if they are "
                        "job/company photos, they are already saved on our "
                        "side, thank them briefly; if a screenshot of an "
                        "error or a question, analyze it and answer it)")
                else:
                    append_escalation(
                        company, msg,
                        "client texted a screenshot/attachment we could "
                        "not auto-file — check the conversation", dry_run,
                        ping=True)  # Monica can't handle it herself
                    continue
        contact_for_flow = contact_payload or {"id": contact_id}
        if handle_reschedule_reply(company, contact_for_flow, msg,
                                   state, dry_run):
            continue
        # purpose= comes from the item's help_text: WHY-questions must be
        # answered from it, never invented (Curt/Home Pride 2026-08-03:
        # Monica said the supplier question was "for the ads setup" when
        # its stated purpose is the supplier/dealer listing-links program).
        item_list = "\n".join(
            f"- id={it['id']} kind={it['kind']} type={it['field_type']} "
            f"q={it['text'][:110]!r}"
            + (f" purpose={str(it['detail'])[:140]!r}" if it.get("detail") else "")
            for it in open_items) or "(none)"
        # Vision: the analysis SEES what they texted (screenshots, photos).
        vision = (_vision_blocks(msg.get("attachments"))
                  if msg.get("attachments") else [])
        if vision:
            print(f"    [vision] {len(vision)} image(s) attached to analysis")
        result = anthropic_json(
            CLASSIFY_SYSTEM,
            f"Open items for {company['name']}:\n{item_list}"
            f"{history_block}{intel_block}\n\n"
            f"Inbound reply:\n{msg['body'][:1200]}",
            images=vision or None)
        # FULL ANALYSIS (every message): the single classify call also says
        # whether a response is needed, who should answer, and drafts it.
        analysis = result.get("analysis") or {}
        resp_need = str(analysis.get("response_needed") or "").strip()
        suggested = (str(analysis.get("suggested_reply") or "").strip()
                     or None)
        if analysis.get("summary"):
            print(f"    analysis: {str(analysis['summary'])[:110]} "
                  f"[response_needed={resp_need or '?'}]")
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
                resolve_plan_row(it["id"], dry_run,
                                 answer=str(match.get("value", "")))
                # Confirmed GBP services route into the existing apply +
                # site-page queues (Curt's yes went nowhere, 2026-08-03).
                if str(it.get("text", "")).startswith("ASK CLIENT: confirm"):
                    route_confirmed_services(company,
                                             str(match.get("value", "")),
                                             dry_run)
        out["matched"] += len(matched_ids)
        turn["matched"] |= matched_ids
        # Items meeting intel marks answered / in progress client-side:
        # never re-asked in the follow-up; escalated for human backfill.
        for flag in result.get("intel_resolved") or []:
            it = next((i for i in open_items
                       if i["id"] == flag.get("item_id")), None)
            if not it:
                continue
            turn["intel"].add(it["id"])
            if not intel_flag_once(state, it["id"]):
                continue
            reason = (f"meeting intel says answered/in progress: "
                      f"{it['text']} — "
                      f"{flag.get('reason') or 'see meeting-intel notes'} "
                      f"(excluded from follow-up nudges; verify + record "
                      f"the answer)")
            print(f"    INTEL: {reason}")
            append_escalation(company, None, reason, dry_run)
        # A "none"/ack verdict must NEVER swallow a matched answer: at 15:48
        # on 2026-08-02 Todd answered "Invoices2Go" to our own question, the
        # analysis said response_needed=none, and this continue skipped the
        # follow-through — Monica extracted the answer and went silent. When
        # the client answered US, we owe the next step regardless.
        if (result.get("ack") or resp_need == "none") and not matched_ids:
            if _bare_ack(msg["body"]):
                # Bare thanks/ok/emoji: the exchange is already closed —
                # never counter-acknowledge (anti-loop rule c).
                print("    bare acknowledgment — exchange closed, no "
                      "counter-ack")
                continue
            # Substantive sign-off ("Sounds good, I appreciate you guys"):
            # needs no answer, but "I always want us to be the last person
            # to send a message" (Santino 2026-08-02) — flows to the
            # phase-2 CLOSER: one short warm line, no ask.
            print("    sign-off with substance — owed a closer")
            turn["bodies"].append(msg["body"][:300])
            turn["last_msg"] = msg
            turn["closer_only"] = True
            if suggested:
                turn["suggested"] = suggested
            continue
        resc = result.get("reschedule") or {}
        if resc.get("requested"):
            handle_reschedule_request(company, contact_for_flow,
                                      resc.get("preference") or "",
                                      state, dry_run)
            continue
        negative = result.get("sentiment") == "negative"
        needs_answer = (bool(result.get("needs_answer"))
                        or resp_need in ("answer", "answer_by_boss")
                        or "?" in (msg["body"] or ""))
        needs_santino = (bool(result.get("needs_santino"))
                         or resp_need == "answer_by_boss")
        turn["bodies"].append(msg["body"][:300])
        turn["last_msg"] = msg
        turn["negative"] = turn["negative"] or negative
        turn["needs_answer"] = turn["needs_answer"] or needs_answer
        turn["needs_santino"] = turn["needs_santino"] or needs_santino
        if suggested:
            turn["suggested"] = suggested   # newest message's draft wins
        # A filed contact card already surfaces on the board via its own
        # open ops note — the mechanical "no open item matched" fallback on
        # top of that is duplicate noise. Classify-driven escalations
        # (negative, explicit escalate) still apply to card messages.
        if (result.get("escalate") or negative
                or (not result.get("matches") and not had_cards)):
            reason = result.get("escalate_reason") or (
                "negative sentiment" if negative
                else "no open item matched")
            print(f"    ESCALATE: {reason}")
            out["escalated"] += 1
            # Text Santino ONLY for angry clients or questions only
            # he can answer; routine unmatched chatter reaches him
            # via the morning digest (policy 2026-08-02).
            append_escalation(company, msg, reason, dry_run,
                              ping=negative or needs_santino)

    # Contact cards: ONE open ops note per batch (surfaces on the Ops
    # Attention board) — filed before any early return so the paperwork
    # never depends on the outbound decision.
    if turn["contact_cards"]:
        file_contact_note(company, turn["contact_cards"], open_items,
                          contact_payload, dry_run)

    # ---- phase 2: ONE outbound decision for the whole turn.
    if not turn["last_msg"]:
        return out
    combined = " / ".join(turn["bodies"])[:400]
    stamp_at = turn["last_msg"]["ts"].isoformat()
    channel = turn["last_msg"]["channel"]
    # A DND/STOP contact is never replied to by SMS — email instead
    # (Angie's accidental "end", 2026-08-03).
    if cs_reset.get("channel_override") == "email" and channel == "sms":
        channel = "email"
        print("    [dnd] reply channel switched to email (SMS DND)")
    if turn["matched"]:
        # ANSWER FOLLOW-THROUGH (Santino 2026-08-02: Todd's "Invoices2Go"
        # answered OUR question and got silence): when a client answers us
        # we owe acknowledge + the next step. Flag the thread as owed BEFORE
        # any send attempt so the immediate webhook compose — or the next
        # scheduled one as backstop — delivers even if the inline reply is
        # skipped, hours-gated or blocked. kind stays "question" when the
        # burst ALSO asked something (question flags survive our own
        # outbounds; answer flags are voided by any newer outbound).
        kind = "question" if turn["needs_answer"] else "answer"
        cs_reset["awaiting_reply"] = {"body": combined, "at": stamp_at,
                                      "channel": channel, "kind": kind}
        out["awaiting"] = True
        if compose_next:
            # Webhook path: the immediate compose that follows has the full
            # context (intel, ops notes, the meeting-not-walkthrough policy)
            # — let it write ONE proper follow-through.
            print("    [inline confirmation skipped — immediate compose "
                  "delivers the follow-through]")
            return out
        remaining = [i for i in open_items
                     if i["id"] not in turn["matched"]
                     and i["id"] not in turn["intel"]]
        nxt = (f"Next open item to ask: {remaining[0]['text']}"
               if remaining else "No items remain.")
        reply = anthropic_json(
            REPLY_SYSTEM,
            f"Client first name: {contact_first_name(None, company)}\n"
            f"They just said (one burst, oldest first): {combined}\n{nxt}")
        body_out = (reply.get("body") or "").strip()
        print(f"    reply draft: {body_out!r}")
        # Inline replies carry no ledger context: any DONE-claim about
        # reviews/posts/requests is unsupported by construction — the
        # compose backstop (which has the ledger) takes over instead.
        grounding = unsupported_done_claim(body_out, None)
        if grounding:
            print(f"    GROUNDING WARNING: {grounding}")
        if do_send and body_out:
            if grounding:
                print("    SEND SKIPPED (grounding guard) — the compose "
                      "backstop carries the follow-through with ledger "
                      "context")
                return out
            # Business hours enforced on EVERY send path (client's local
            # tz). Phase 1 of the rollout: refuse + flag, no queue.
            hours_reason = business_hours_check(company, contact_payload)
            if hours_reason:
                print(f"    SEND FLAGGED: {hours_reason} — reply not "
                      f"sent this cycle")
                append_escalation(company, turn["last_msg"], hours_reason,
                                  dry_run)
                return out
            dup = repeats_last_outbound(body_out, history)
            if dup:
                print(f"    SEND SKIPPED: {dup} — the compose backstop "
                      "carries the follow-through")
                return out
            target = messaging_target(company)
            contact = {"id": contact_id,
                       "phone": target.get("cell") or company.get("phone"),
                       "email": target.get("email") or company.get("email")}
            try:
                sent = send_message(contact, channel, body_out)
                record_sent_message(state, sent)
                if kind == "answer":
                    # the follow-through went out — nothing pending. A
                    # question in the burst keeps its flag: this thin
                    # confirmation didn't answer it; compose will.
                    cs_reset.pop("awaiting_reply", None)
            except SendBlocked as e:
                print(f"    SEND BLOCKED: {e}")
        return out
    if turn["negative"]:
        return out   # escalated to Santino above; a human takes it from here
    if turn["needs_answer"]:
        cs_reset["awaiting_reply"] = {"body": combined, "at": stamp_at,
                                      "channel": channel, "kind": "question"}
        out["awaiting"] = True
        print("    [awaiting_reply set — next compose answers this, "
              "cooldown bypassed]")
        if compose_next:
            print("    [holding ack skipped — immediate compose follows "
                  "with the real answer]")
            return out
        _maybe_send_ack(state, company, contact_id,
                        {"body": combined, "channel": channel},
                        contact_payload, do_send, dry_run, history=history,
                        needs_answer=True,
                        needs_santino=turn["needs_santino"],
                        suggested=turn["suggested"])
        return out
    # Plain statement(s) / substantive sign-offs: ONE warm CLOSER for the
    # whole burst — "I always want us to be the last person to send a
    # message" (Santino 2026-08-02). Webhook path included: the compose
    # that follows only carries owed replies, and the closer IS the whole
    # response. The loop can't ping-pong: a bare thanks back never gets a
    # counter-ack, reactions aren't messages, and the duplicate guard
    # blocks a repeat closer.
    _maybe_send_ack(state, company, contact_id,
                    {"body": combined, "channel": channel},
                    contact_payload, do_send, dry_run, history=history,
                    needs_answer=False, needs_santino=False,
                    suggested=turn["suggested"], closer=True)
    return out


def webhook_inbound(contact_id: str, do_send: bool = True) -> dict:
    """Instant inbound for ONE contact — the Railway POST /concierge-inbound
    webhook (Santino 2026-08-02: GHL fires the moment a client responds; no
    more waiting on the 5-min poll + hourly compose). Same engine as
    cmd_inbound scoped to this contact, then an IMMEDIATE compose for the
    company so a warranted reply goes out now. Every gate still applies —
    business hours, canary allowlist, human-defer window, PAUSE switch —
    and the client_waiting bypass covers the cooldown since the client just
    spoke. Unknown contacts are ignored (server-side filter, so the GHL
    workflow can fire on every inbound message; no tag required). The
    poll's inbound_cursor is never touched here; dedupe against the poll is
    the handled-ids ledger."""
    dry_run = not do_send
    state = load_state()
    company_id = _tracked_contacts(state).get(contact_id)
    if not company_id:
        print(f"[webhook] contact {contact_id} is not tracked — ignoring")
        return {"status": "ignored",
                "reason": "contact not tracked by the concierge"}
    company = (fetch_companies([company_id]).get(company_id)
               or {"id": company_id, "name": company_id})
    muted = company_inactive(company)
    if muted:
        # Paused/cancelled account (Santino 2026-08-04, Mold Solutionz): no
        # ack, no compose, no state writes — the message stays visible in
        # GHL for a human to handle.
        print(f"[webhook] {company.get('name')}: {muted} — no auto-reply")
        return {"status": "ignored", "reason": muted}
    cursor = state.get("inbound_cursor")
    since = (datetime.fromisoformat(cursor) if cursor
             else datetime.now(timezone.utc) - timedelta(hours=48))
    msgs = fetch_inbound_since(contact_id, since)
    if not msgs:
        # GHL sometimes fires the webhook before the message is readable
        # via the API — one short retry before giving up.
        time.sleep(5)
        msgs = fetch_inbound_since(contact_id, since)
    # DEBOUNCE (Santino 2026-08-02: "Blue like water" + "And white" seconds
    # apart each got their own reply). People text in bursts — wait for a
    # quiet window and fold whatever arrives into ONE conversational turn.
    # The per-contact lock in the API serializes the burst's other webhook
    # events; they find everything already in the handled ledger and no-op.
    handled_now = set(state.get("handled_msg_ids") or [])
    deadline = time.time() + INBOUND_DEBOUNCE_MAX_S
    while msgs and time.time() < deadline:
        fresh = [m for m in msgs if m["id"] not in handled_now]
        if not fresh:
            break
        age = (datetime.now(timezone.utc)
               - max(m["ts"] for m in fresh)).total_seconds()
        if age >= INBOUND_QUIET_WINDOW_S:
            break
        wait = min(INBOUND_QUIET_WINDOW_S - age + 3, deadline - time.time())
        if dry_run:
            print(f"[webhook] [dry-run] would debounce {wait:.0f}s "
                  "(burst still warm) then re-fetch")
            break
        time.sleep(max(wait, 1))
        msgs = fetch_inbound_since(contact_id, since)
    print(f"[webhook] {company.get('name')}: {len(msgs)} new message(s) "
          f"since cursor{' [DRY RUN — no writes, no sends]' if dry_run else ''}")
    summary = process_inbound_messages(state, company, contact_id, msgs,
                                       do_send, dry_run, compose_next=True)
    # Persist BEFORE composing: cmd_compose loads its own state copy and
    # must see awaiting_reply / handled ids / commitments from this pass.
    save_state(state, dry_run)
    composed = False
    # Compose only when the turn left something OWED (answer follow-through
    # or a question). For plain statements the single ack above IS the whole
    # response — composing too would race the just-sent ack in the thread
    # and risk a second text. Negative sentiment goes to a human.
    if summary["awaiting"]:
        sub = argparse.Namespace(all=False, company=company_id,
                                 merge_with=None, channel="sms", send=do_send)
        try:
            cmd_compose(sub)
            composed = True
        except Exception as e:  # noqa: BLE001 — webhook must return a summary
            print(f"[webhook] compose failed: {str(e)[:150]}")
    flush_ops_pings(dry_run)
    return {"status": "processed", "company_id": company_id,
            "company": company.get("name"), **summary,
            "compose_ran": composed}


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
        try:
            if contact_id == OPS_PING_CONTACT_ID:
                msgs = fetch_inbound_since(contact_id, since)
                if msgs:
                    handled_any = True
                    for msg in msgs:
                        print(f"\n[boss-feedback] ops-thread reply (not a client "
                              f"message): {msg['body'][:200]!r}")
                        if not dry_run:
                            # datetime fields must be stringified or the insert
                            # raises and KILLS the whole poll before the cursor
                            # saves — the 07-31 every-5-min All Pro SMS storm was
                            # exactly this crash looping. Never let it be fatal.
                            try:
                                _sb("POST", "/rest/v1/concierge_escalations",
                                    {"company_id": None, "company_name": "OPS THREAD",
                                     "reason": "boss-feedback (Santino reply on ops "
                                               "thread — review in session)",
                                     "message": json.loads(json.dumps(msg, default=str))},
                                    prefer="return=minimal")
                            except Exception as e:  # noqa: BLE001
                                print(f"  [boss-feedback] insert failed: {str(e)[:120]}")
                continue
            company = companies.get(company_id, {"id": company_id, "name": company_id})
            muted = company_inactive(company)
            if muted:
                # Paused/cancelled account: leave their messages for a human
                # (Santino 2026-08-04, Mold Solutionz).
                print(f"  [inbound] {company.get('name', company_id)}: "
                      f"{muted} — skipped")
                continue
            msgs = fetch_inbound_since(contact_id, since)
            if not msgs:
                continue
            handled_any = True
            process_inbound_messages(state, company, contact_id, msgs,
                                     args.send, dry_run)
        except Exception as e:  # noqa: BLE001 — one bad thread must never
            # kill the poll: the 07-31 storm was a single crash looping the
            # cursor (same message re-escalated + re-texted every 5 min).
            print(f"  [inbound] contact {contact_id} ({company_id}): "
                  f"processing failed — {str(e)[:150]} (continuing)")


    # ---- advice replies from Santino -> ops notes (the loop closes here)
    reqs = _advice_requests()
    open_reqs = [r for r in reqs if r.get("status") == "open"]
    if open_reqs:
        try:
            adv_msgs = fetch_history(ADVICE_CONTACT_ID, max_msgs=10)
            new_replies = [m for m in adv_msgs
                           if m.get("direction") == "in" and m.get("when")
                           and m["when"] > since]
            for m in reversed(new_replies):
                match = anthropic_json(
                    ADVICE_MATCH_SYSTEM,
                    "Open questions:\n" + "\n".join(
                        f"{i}: [{r.get('company_name')}] {r.get('reason', '')[:140]}"
                        for i, r in enumerate(open_reqs))
                    + f"\n\nSantino's reply: {m.get('body', '')[:500]}")
                idx = match.get("index")
                instr = (match.get("instruction") or m.get("body") or "").strip()
                if idx is None or not (0 <= int(idx) < len(open_reqs)) or not instr:
                    continue
                req = open_reqs[int(idx)]
                print(f"  [advice] Santino answered re {req.get('company_name')}: {instr[:100]}")
                if not dry_run:
                    _sb("POST", "/rest/v1/marketing_ops_notes", body={
                        "company_id": req["company_id"],
                        "body": f"[FROM SANTINO via SMS] {instr} "
                                f"(answering: {req.get('reason', '')[:120]})"})
                    # One answer settles EVERY open ask for that company —
                    # they're rewordings of the same underlying question.
                    stamp_ans = datetime.now(timezone.utc).isoformat()
                    for r in reqs:
                        if (r.get("status") == "open"
                                and r.get("company_id") == req["company_id"]):
                            r["status"] = "answered"
                            r["answered_at"] = stamp_ans
                    kv_set("advice-requests", reqs)
                    if args.send:
                        try:
                            send_message({"id": ADVICE_CONTACT_ID, "phone": ADVICE_PHONE},
                                         "sms",
                                         f"Got it, noted for {req.get('company_name')}. I'll handle it on my next pass.")
                        except SendBlocked:
                            pass
        except Exception as e:  # noqa: BLE001 — advice loop must never break the poll
            print(f"  [advice] reply processing failed: {str(e)[:120]}")

    if not handled_any:
        print("  no new inbound messages for tracked contacts.")
    state["inbound_cursor"] = run_start.isoformat()
    save_state(state, dry_run)
    print(f"cursor -> {run_start.isoformat()}"
          + (" (not persisted — dry run)" if dry_run else ""))
    return 0


# ------------------------------------------------------------- ack replies
# A one-line acknowledgment so no client reply ever dead-ends (Santino
# 2026-07-30). Rules: never ack an ack, one PLAIN ack per contact per day
# (a reply that needs a real answer ALWAYS gets a holding line — the daily
# cap swallowing Todd's suspension question is how 2026-08-02 happened),
# business hours only, and the matched-item path (which sends a real reply)
# never acks on top of it. Copy is drafted from the client's actual words:
# "Perfect, thanks for getting back to me!" after "I don't know how to send
# all customers at once" is why the canned rotation died (2026-08-02).
_TERMINAL_ACK_RE = re.compile(
    r"^(ok(ay)?|k+|sure|thanks?( you| u)?|thank you|got it|sounds good|"
    r"perfect|great|awesome|no problem|np|will do|yes ?sir|yup|yep|"
    r"👍|🙏)[.! ]*$", re.I)

# Words that can appear in a message that is ONLY gratitude/agreement.
# Anything outside this set means the message carries content and deserves
# a response (a closer at minimum — "we are always the last to send").
_ACK_WORDS = {
    "thanks", "thank", "you", "u", "so", "much", "ok", "okay", "k", "kk",
    "great", "sounds", "good", "perfect", "awesome", "got", "it", "will",
    "do", "cool", "no", "problem", "np", "yes", "sir", "yup", "yep",
    "yeah", "sure", "appreciate", "appreciated", "that", "works", "all",
    "right", "alright", "roger", "bet", "10-4", "ty", "tysm"}


def _bare_ack(body: str) -> bool:
    """Cheap semantic-ish test: is this message ONLY thanks/agreement with
    no content ("Thanks!", "ok great", "sounds good thank you", a bare
    emoji)? A bare ack never gets a counter-acknowledgment — one closer per
    wrap-up, the closer already ended the exchange (Santino 2026-08-02
    anti-loop rule (c)). Reactions (Liked "...") are handled separately by
    _REACTION_RE and are not messages at all."""
    text = (body or "").strip()
    if not text:
        return True
    if _TERMINAL_ACK_RE.match(text) and len(text) <= 25:
        return True
    if len(text) > 40:
        return False
    words = re.findall(r"[a-z0-9'\-]+", text.lower())
    if not words:
        return True   # pure emoji/punctuation
    return all(w in _ACK_WORDS for w in words)

ACK_SYSTEM = """\
You are Monica from Santino's team at Restoration AI, texting ONE short
holding line right after a client replied with something we can't fully
resolve this minute. NEVER use em dashes or en dashes; use a comma or a
period. No emojis, no exclamation spam, no canned filler ("Perfect, thanks
for getting back to me" is banned). Respond to what they actually SAID:
- They asked something we need to look into: acknowledge the question
  specifically and say you'll find out and get right back to them.
- They said they don't know how to do something, or are stuck: do the
  FIRST STEP of the walk-through right now — ask the one concrete question
  that unblocks them ("where do your customers live today, phone contacts,
  a spreadsheet, an invoicing app? Even a screenshot works") instead of
  promising future help.
- A plain statement or update: thank them naturally. ACKNOWLEDGE FORWARD,
  never echo: never restate their message back as a summary ("got it,
  you'll grab a photo when you're back" is banned); point at what happens
  next ("Thanks, definitely send those over when you get back into town").
  If they committed to do something later, that warm forward close IS the
  whole text — never stack an ask onto it.
This is mid-conversation: do NOT open with their name (names at most once
per day of thread — Santino 2026-08-02); start with content ("Got it...",
"No problem...", "Sounds good...").
Do NOT attempt to answer the question here (you don't have the answer yet),
do not promise dates, and only mention checking with Santino when the input
says the boss must decide. NEVER promise anything that will not actually
happen on its own ("I'll walk you through it" is banned unless this very
text starts the walk-through), and NEVER claim something is already done
or sent — you cannot see the ledger; speak forward ("we're on it now"),
never "is already out" (2026-08-02). At most ONE question in the text.
One or two short sentences, under 220 characters.
Return ONLY JSON: {"body": string}."""

# COMMITMENT FOLLOW-THROUGH (Santino 2026-08-02: the ack drafted "I'll walk
# you through it" and nobody ever walked him through anything). Any promise
# that slips into a sent ack is captured here and queued as
# cs["pending_commitment"] — the next compose MUST deliver it (see the OPEN
# COMMITMENT block in compose_draft). General rule: never promise what the
# pipeline won't deliver; prefer doing the first step in the ack itself.
_PROMISE_RE = re.compile(
    r"\bI(?:'ll| will)\s+(?:walk you|get (?:right )?back|find out|check|"
    r"look into|send (?:you|over|it)|follow up|get you|dig|circle back|"
    r"ask santino|talk to santino|have (?:an answer|that|it))", re.I)


def _record_commitment(cs: dict, sent_text: str, client_msg: str,
                       dry_run: bool) -> None:
    """If the text we just sent PROMISES future work, queue it so the next
    compose is forced to deliver (never a promise the pipeline drops)."""
    m = _PROMISE_RE.search(sent_text or "")
    if not m:
        return
    cs["pending_commitment"] = {
        "promise": sent_text[:300],
        "context": (client_msg or "")[:300],
        "at": datetime.now(timezone.utc).isoformat()}
    print(f"    [commitment recorded — next compose must deliver: "
          f"{m.group(0)!r}]"
          + (" (dry run: not persisted)" if dry_run else ""))


def _maybe_send_ack(state: dict, company: dict, contact_id: str, msg: dict,
                    contact_payload: dict | None, do_send: bool,
                    dry_run: bool, history: list[dict] | None = None,
                    needs_answer: bool = False,
                    needs_santino: bool = False,
                    suggested: str | None = None,
                    closer: bool = False) -> None:
    body = (msg.get("body") or "").strip()
    if not body or _bare_ack(body):
        print("    [ack skipped: their message is itself an acknowledgment]")
        return
    cs = company_state(state, company["id"])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    acks = cs.setdefault("acks", {})
    if acks.get(contact_id) == today and not (needs_answer or closer):
        # The daily cap applies to PLAIN thank-you acks only. A question or
        # stuck reply always gets a holding line (on 2026-08-02 the cap ate
        # the reply to "I wonder why they suspended the listing"), and a
        # CLOSER always sends — being the last to speak is the policy, and
        # each closer requires a fresh substantive client message anyway.
        print("    [ack skipped: already acknowledged this contact today]")
        return
    if business_hours_check(company, contact_payload):
        print("    [ack skipped: outside their business hours]")
        return
    # The full-analysis classify already drafted the reply with the whole
    # context (open items, history, intel) — use it and save a model call.
    # ACK_SYSTEM is the fallback when the analysis gave nothing usable.
    text = (suggested or "").strip()[:320]
    if not text:
        last_out = next((m for m in (history or [])
                         if m.get("direction") == "out"), None)
        try:
            draft = anthropic_json(
                ACK_SYSTEM,
                f"Client first name: {contact_first_name(None, company)}\n"
                + (f"Our last message to them: {last_out['body'][:200]}\n"
                   if last_out else "")
                + f"Their reply: {body[:400]}\n"
                + ("Only the boss can decide this one, say you'll check with "
                   "Santino and get back to them.\n" if needs_santino else "")
                + ("This reply needs a real answer later; write the holding "
                   "line." if needs_answer else
                   ("This message WRAPS UP the exchange: write ONE short "
                    "warm closing line pointing forward (no question, no "
                    "ask, no new information). We are always the one to "
                    "close." if closer else
                    "This is a statement; write the short natural thanks.")))
            text = (draft.get("body") or "").strip()
        except Exception as e:  # noqa: BLE001 — a failed draft must not kill the poll
            print(f"    [ack] draft failed ({str(e)[:80]}) — using fallback")
    if not text:
        text = ("Let me look into that and get right back to you."
                if needs_answer else "Got it, thank you.")
    print(f"    ack draft: {text!r}")
    grounding = unsupported_done_claim(text, None)
    if grounding:
        print(f"    [ack blocked by grounding guard: {grounding}]")
        return
    dup = repeats_last_outbound(text, history or [])
    if dup:
        print(f"    [ack skipped: {dup}]")
        return
    if not do_send:
        _record_commitment(cs, text, body, dry_run=True)
        return
    target = messaging_target(company)
    contact = {"id": contact_id,
               "phone": target.get("cell") or company.get("phone"),
               "email": target.get("email") or company.get("email")}
    try:
        sent = send_message(contact, msg.get("channel") or "sms", text)
        record_sent_message(state, sent)
        acks[contact_id] = today
        _record_commitment(cs, text, body, dry_run)
        save_state(state, dry_run)
    except SendBlocked as e:
        print(f"    ACK BLOCKED: {e}")


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
