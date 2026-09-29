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
    shape phrasing naturally ("Sounds like a great call with Santino on
    Tuesday") but private discussion details are never quoted back to the
    client, and Monica never speaks as though SHE was there (2026-08-04).

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
    CONCIERGE_FROM_NUMBER                     SMS sender number. Monica sends
                                              ONLY from the 805 local number
                                              +18053293449 (Santino 2026-08-07,
                                              reversing the earlier toll-free
                                              policy: the toll-free is no longer
                                              a concierge sender). Unset =>
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
sys.path.insert(0, str(ROOT / "scripts"))
# Domain-access truth lives in ONE place (client_ops_sync) so the app card,
# the setup ledger and Monica's texts can never drift apart — 2026-08-04.
from client_ops_sync import (  # noqa: E402
    DOMAIN_ACCESS_HOWTO, DOMAIN_ACCESS_INVITE_EMAIL, DOMAIN_ACCESS_TRUTH)

OPS_DIR = ROOT / "clients" / "_ops"
STATE_PATH = OPS_DIR / "concierge-state.json"
ESCALATIONS_PATH = OPS_DIR / "concierge-escalations.md"
MEETING_INTEL_DIR = OPS_DIR / "meeting-intel"
COMPANY_MAP_PATH = ROOT / "clients" / "company_map.json"

GHL_BASE = "https://services.leadconnectorhq.com"
GHL_VERSION = "2021-07-28"
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
# Opus 5.5 (Santino 2026-09-27): Monica's compose + intent/topic reads are
# where the judgment failures happened (Sarah/Greg conflation); upgraded.
ANTHROPIC_MODEL = "claude-opus-5-5"
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
# CONCISION IS A HARD RULE (Santino 2026-08-04, reviewing the Reign
# Restoration thread: "I like what she said but it also seems like a quick
# patch. I don't want her sending long messages like that. Very concise,
# ALWAYS, don't overexplain, just ask and get the info.").
#
# The old numbers were 450 hard / 390 stated, and the model drafted TO the
# stated budget every time: Jerrott got a 198-char hosting explainer and a
# 282-char reviews acknowledgment where two short sentences would have done.
# TARGET is what the model is told to write to; MAX is the mechanical
# ceiling that triggers the shorten/trim loop (_fit_sms). A normal message
# is one idea: a sentence of context at most, then the ask.
SMS_TARGET_CHARS = 200      # what compose is told to aim for (~160-200)
SMS_MAX_CHARS = 260         # ceiling for a normal message -> shorten loop
# EXCEPTION 1 — first contact: the intro line ("Hi X, this is Monica with
# Santino's team at Restoration AI. I help get everything set up for your
# account.") is ~112 chars of required identity before the ask even starts.
SMS_TARGET_CHARS_FIRST = 260
SMS_MAX_CHARS_FIRST = 340
# EXCEPTION 2 — a step-by-step the client explicitly asked for (the GoDaddy
# "Invite to Access" walk-through is the canonical case). Still capped: tight
# steps, no preamble around them.
SMS_TARGET_CHARS_STEPS = 340
SMS_MAX_CHARS_STEPS = 420
# ONE PURPOSE PER MESSAGE (Santino 2026-08-02, Todd thread review): every
# text carries at most ONE question — the single most valuable next thing.
# Stacked asks ("What day works? Also, any brand col...") read robotic and
# get half-answered. Other open items wait for their own message.
MAX_ITEMS_PER_MESSAGE = 1
# A first text from an unknown number must feel like a person saying hi with
# one small favor to ask — never a checklist. Follow-ups may carry two.
FIRST_CONTACT_MAX_ITEMS = 1
# How long a finished site sits before we show it to a brand-new client
# (Santino 2026-08-05). Not a delay for its own sake: every other ask goes out
# immediately, so the client sees steady progress, and the gap doubles as the
# QA window that would have caught DISS's broken logo before they ever saw it.
# This gates the PROACTIVE ask only. A client who writes in asking about their
# site is answered by the reply path, which never consults this filter.
PREVIEW_SOAK_DAYS = 10  # Santino 2026-09-11: was 7 (08-29: was 5; 08-10: was 3) — ten days of visible progress before any site-live notice, every path
MIN_DAYS_BETWEEN_SENDS = 3
HISTORY_MAX_MSGS = 25          # default fetch_history depth for compose/status
CLASSIFY_HISTORY_MSGS = 10     # history context given to inbound classification
HISTORY_EMAIL_TRIM = 500       # chars kept per email body (threads get long)
HUMAN_DEFER_HOURS = 12         # human outbound newer than this => skip nudge
HUMAN_REPLY_HOLD_MIN = 60      # Santino spoke => ALL sends to that thread wait
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
    # Apple/Android tapbacks: 'Liked "…"'.  GHL also relays raw emoji
    # reactions as '<emoji> to "…"' (Greg/PuroClean 2026-08-05 sent 🤙🏽 and
    # Monica replied to it — reactions are never messages, never answer one).
    r'^\s*(?:(?:liked|loved|laughed at|emphasi[sz]ed|disliked|questioned)\s+["“]'
    r'|[^\w\s,.!?]{1,8}[​️\s]*to\s+["“])',
    re.I)
# Ops ping: every escalation also fires ONE summary SMS to Santino's cell so
# a human hears about it without reading concierge-escalations.md. The 805
# company number is the GHL location's own number and can't receive sends
# from its own location — the ping goes to the ops cell via the toll-free,
# which still lands the thread in GHL where the team can see it.
# TRAVEL SWITCH (Santino 2026-08-11): his 808 cell cannot receive SMS abroad;
# Ops pings reach Santino's personal cell, the 808 (reverted 2026-08-18 on
# his word after travel; the traveling 805-539 pair was Ib2kYCeRf02fIJEgKgF3 /
# +18055392313). The env overrides were also CLEARED from both Railway
# services on 08-18 so this default is the single source of truth — set the
# env pair (cell AND contact id together, never one) only for future travel.
OPS_PING_CELL = os.environ.get("CONCIERGE_OPS_CELL", "+18089891078")
OPS_PING_CONTACT_ID = os.environ.get("CONCIERGE_OPS_CONTACT_ID",
                                     "MIJ5Jm4sobdzSRtnYSzU")  # Santino (808)
OPS_PING_DEDUPE_HOURS = 24
_OPS_PINGS: list = []          # (company name, reason) accumulated per run
BUSINESS_HOUR_START = 9
BUSINESS_HOUR_END = 18
# REPLYING IS NOT INTERRUPTING (Santino 2026-08-04, Fran/Quality Contracting:
# "if somebody responds, we can always respond to them as long as it's within
# 5 or 10 minutes... when Fran responded, a simple acknowledgement would have
# been okay"). Fran texted at 19:00 his time and the 9-18 gate ate the closer,
# so the warm two-second reply became a next-day message. Three tiers now:
#
#   quiet hours   21:00-07:00  NOTHING sends. Not a nudge, not a reply, not a
#                              reply two seconds after theirs. A buzz at 2am is
#                              never right and there is no override.
#   business      09:00-18:00  anything may go: nudges, outreach, replies.
#   shoulder      07:00-09:00  REPLIES ONLY, and only inside the fast window
#                 18:00-21:00  below. Unprompted outreach still waits for 9am.
#
# FAST WINDOW: a reply sent within FAST_REPLY_MINUTES of the client's own
# message is a reply, not an interruption — their phone is already in their
# hand. Allowed anywhere outside quiet hours.
# EVENING ACK: in the 18:00-21:00 shoulder a reply may still go out after the
# fast window has closed, but only as a SHORT acknowledgment (see
# evening_ack_only) — evening is for "got it, I'm on it", not for asks.
# The morning shoulder (07:00-09:00) has no such extension: a 7am text about
# something they said last night can wait for business hours.
QUIET_HOUR_START = 21          # 9pm client-local: hard floor, no exceptions
QUIET_HOUR_END = 7             # 7am client-local
FAST_REPLY_MINUTES = 10
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


DEPARTED_STATUSES = {"archived", "churned", "paused", "cancelled", "inactive", "suspended"}
_ALLOW_CACHE: dict = {"at": None, "value": None}


def _env_allowlist() -> set[str]:
    """CONCIERGE_ALLOWLIST env (comma-separated phones/emails). Default EMPTY."""
    out: set[str] = set()
    for tok in os.environ.get("CONCIERGE_ALLOWLIST", "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.add(_norm_email(tok) if "@" in tok else _norm_phone(tok))
    return out


def _client_allowlist() -> tuple[set[str], list[str]]:
    """Preferred contact of every CURRENT client, straight from the app.

    Returns (recipients, labels). Fails closed: on any error the caller keeps
    the env list alone rather than widening the gate on bad data.
    """
    out: set[str] = set()
    who: list[str] = []
    try:
        rows = _sb("GET", "/rest/v1/companies?select=id,name,status,plan,"
                          "integration_settings&limit=500") or []
    except Exception as e:  # noqa: BLE001 — never widen the gate on a bad read
        print(f"  [allowlist] client read failed ({str(e)[:70]}) — env list only")
        return out, who
    for c in rows:
        if str(c.get("status") or "").strip().lower() in DEPARTED_STATUSES:
            continue
        pref = preferred_contact_entry(c)
        if not pref:
            continue          # no contact card yet: nothing to authorise
        cell, email = pref.get("cell") or "", pref.get("email") or ""
        added = False
        if _norm_phone(cell):
            out.add(_norm_phone(cell)); added = True
        if "@" in email:
            out.add(_norm_email(email)); added = True
        if added:
            name = " ".join(x for x in ((pref.get("first_name") or "").strip(),
                                        (pref.get("last_name") or "").strip()) if x)
            who.append(f"{c.get('name')} -> {name or '?'}")
        # THE LINKED GHL CONTACT IS THE SAME PERSON (Sarah/Heritage
        # 2026-09-19): sends go to the GHL record's phone, which can differ
        # from the card's cell (8 of 38 clients on the day this shipped).
        # Authorising only the card number left every such client silently
        # canary-blocked. When the company's ghl_contact_id link is
        # identity-verified against the card (shared email OR shared phone),
        # the GHL record's other coordinates are the same person — authorise
        # them. No match = possibly the wrong person = add nothing.
        gid = str((c.get("integration_settings") or {})
                  .get("ghl_contact_id") or "").strip()
        if gid and pref:
            try:
                g = (_ghl("GET", f"/contacts/{gid}") or {}).get("contact") or {}
                gp, ge = _norm_phone(g.get("phone")), _norm_email(g.get("email"))
                same = ((ge and ge == _norm_email(email))
                        or (gp and gp == _norm_phone(cell)))
                if same:
                    if gp:
                        out.add(gp)
                    if ge:
                        out.add(ge)
            except Exception:  # noqa: BLE001 — fail closed, card list stands
                pass
    return out, who


def allowed_recipients() -> set[str]:
    """Who Monica is allowed to message.

    Two sources, unioned:
      1. CONCIERGE_ALLOWLIST env — Santino's own numbers, canary contacts, and
         anyone he wants reachable who is not a client contact card.
      2. The PREFERRED CONTACT of every current client, read live from
         integration_settings.contacts — the same card the app shows under
         Contact info, marked with the star.

    Source 2 exists because source 1 alone was silently dropping real clients
    (Santino, 2026-08-05). The env list is hand-typed and nothing in the
    onboarding wizard ever appended to it, so a client could finish onboarding,
    have a complete GHL-linked contact card in the app, and still be
    unreachable forever with the failure buried in a log line. DISS
    (TJ Stoian), HomeLyft (josiah Viland) and AAA (Christopher Pruett) were all
    in exactly that state, HomeLyft having already done their kickoff call.

    The gate still does its job: it authorises the person the app says to
    message, and nobody else. Departed clients drop out, a company with no
    contact card adds nothing, and a Supabase failure falls back to the env
    list rather than opening up.

    Cached for 5 minutes so a batch compose does not re-read per send.
    """
    now = datetime.now(timezone.utc)
    cached = _ALLOW_CACHE.get("value")
    if cached is not None and _ALLOW_CACHE.get("at") \
            and (now - _ALLOW_CACHE["at"]).total_seconds() < 300:
        return cached
    env = _env_allowlist()
    derived, who = _client_allowlist()
    if who:
        print(f"  [allowlist] {len(env)} from env + {len(who)} client contact "
              f"card(s) from the app")
    out = env | derived
    _ALLOW_CACHE.update({"at": now, "value": out})
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
                   images: list[dict] | None = None,
                   model: str | None = None, timeout: int = 120) -> dict:
    """One Messages call, expects a single JSON object in the reply.
    Retries once on an empty/non-JSON reply (2026-07-29: intermittent empty
    responses starved whole compose passes). `images` (from _vision_blocks:
    [{"media_type", "data"(b64)}]) ride along so inbound analysis can SEE
    what a client texted (Angie's browser-warning screenshot, 2026-08-02)."""
    content: list | str = user
    if images:
        # PDFs ride as document blocks (Rachelle/DVC 2026-09-22: her
        # recorded FFN certificate is a PDF; image-only blocks made the
        # DBA lane call it unreadable).
        content = ([{"type": ("document" if im["media_type"]
                              == "application/pdf" else "image"),
                     "source": {"type": "base64",
                                "media_type": im["media_type"],
                                "data": im["data"]}} for im in images]
                   + [{"type": "text", "text": user}])
    last_text = ""
    last_stop = None
    messages: list[dict] = [{"role": "user", "content": content}]
    for attempt in (1, 2, 3):
        resp = requests.post(ANTHROPIC_API, timeout=timeout, headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json", "User-Agent": UA,
        }, json={
            "model": model or ANTHROPIC_MODEL, "max_tokens": max_tokens,
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


def _is_machine_sent(message_id: str | None) -> bool:
    """Durable second source for "did WE send this?" — one ops_kv row per
    delivered message id, written in send_message. Exists because the
    state-blob ledger races across processes (2026-09-14: a concurrent run
    clobbered fresh ids and the human gates then blocked Monica's instant
    replies for an hour per thread)."""
    if not message_id:
        return False
    try:
        return kv_get(f"machine-sent:{message_id}") is not None
    except Exception:  # noqa: BLE001 — a kv hiccup must not block detection
        return False


def record_sent_message(state: dict, result: dict | None) -> None:
    """Track the GHL id(s) of a message WE just delivered.

    This is the ground truth for the human-conversation check: any outbound
    message in a thread whose id is NOT in state.sent_message_ids was sent by
    a human (Santino / the app's automations acting as him), not the
    concierge. Empty until the first real send by design."""
    ids = state.setdefault("sent_message_ids", [])
    for key in ("messageId", "emailMessageId", "messageIds", "id"):
        val = (result or {}).get(key)
        for mid in (val if isinstance(val, list) else [val]):
            if mid and isinstance(mid, str) and mid not in ids:
                ids.append(mid)
    # ID RECONCILIATION — ALL CHANNELS (email: PuroClean 2026-08-03; SMS:
    # Reign 2026-08-04). GHL's send response returns one id, but the message
    # row that later shows up in the conversation can carry a DIFFERENT one.
    # An unrecorded id reads as a HUMAN outbound, so Monica deferred to
    # HERSELF: seconds after her inline reply "Give me a second while I grab
    # the correct link for you" (22:56), the next compose refused with
    # "recent human conversation — deferred (human outbound sms at 22:56,
    # 0.1h ago)" and she broke her own promise until Santino forced it
    # through send-now. The email path had already been fixed this way; the
    # inline/ack/webhook SMS path had not. Fix: after ANY send, pull the
    # conversation's newest outbound ids and record every one written in the
    # last few minutes, whatever channel and whatever id shape GHL used.
    conv = (result or {}).get("conversationId")
    if not conv:
        _note_unrecorded_send(result)
        return
    try:
        data = _ghl("GET", f"/conversations/{conv}/messages",
                    params={"limit": 15})
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        added = 0
        for msg in (data.get("messages") or {}).get("messages", []) or []:
            mid = msg.get("id")
            if not mid or mid in ids or msg.get("direction") == "inbound":
                continue
            try:
                when = datetime.fromisoformat(
                    (msg.get("dateAdded") or "").replace("Z", "+00:00"))
            except ValueError:
                continue
            if when >= cutoff:
                ids.append(mid)
                added += 1
        if added:
            print(f"  [sent-ids] reconciled {added} outbound id(s) from the "
                  "conversation — Monica never defers to herself")
    except Exception as e:  # noqa: BLE001 — bookkeeping never fails a send
        print(f"  [sent-ids] reconcile failed: {str(e)[:80]}")
    _CLIENT_SENDS["recorded"] += 1


# REGRESSION CHECK (2026-08-04): every path that sends to a CLIENT must
# register the id, or the human-defer window silences Monica against her own
# message. send_message() counts; record_sent_message() clears. A mismatch is
# printed loudly at the end of the run — a new send path that forgets to
# record can never again go unnoticed.
_CLIENT_SENDS = {"sent": 0, "recorded": 0, "unrecorded": []}


def _note_unrecorded_send(result: dict | None) -> None:
    _CLIENT_SENDS["unrecorded"].append(str((result or {}).get("messageId")
                                           or "<no id>"))


def sent_id_regression_check() -> None:
    """Print (loudly) if any client send this run went unrecorded."""
    sent, rec = _CLIENT_SENDS["sent"], _CLIENT_SENDS["recorded"]
    if sent > rec:
        print(f"!! SENT-ID REGRESSION: {sent} client send(s) this run but "
              f"only {rec} recorded into sent_message_ids — the unrecorded "
              "ones will read as HUMAN outbound and trip the 12h human-defer "
              "against Monica herself. Every send path must call "
              "record_sent_message(state, result).", file=sys.stderr)


# ---------------------------------------------------------------- history
def is_internal_sender(msg: dict) -> bool:
    """INTERNAL SENDER MAP (2026-08-20, the Bobby misattribution): True when
    a raw GHL message row was written (or answered) by a human on OUR side,
    regardless of what its direction field claims.

    GHL's two-way email sync logs sends made from our EXTERNAL mailboxes
    (Santino replying from the contact@getrestorationai.com Gmail instead of
    the GHL app) as direction=inbound — but it stamps the workspace user's
    id on the row. On 08-19 Monica read Santino's "These are perfect. We'll
    add them in for ya" as BOBBY's words and thanked him for them. userId is
    the same human signal the quiet window and nudge deferral already key
    on: real people carry it, Monica's API sends and true client messages
    never do (fleet sample 08-20: 371 inbound rows across 13 clients, 7
    carried a userId, every readable one was ours — two external-mailbox
    emails, the rest empty email stubs and one human-answered call).

    EXCEPT workflow sends (2026-09-06, Mike Luna): GHL calendar-reminder
    workflows run under Santino's user, so their messages CARRY his userId —
    an automated "your call is tomorrow" email deferred Monica for 12 hours
    while Mike's Bakersfield request sat unanswered. GHL stamps
    source="workflow" on those rows and source="app" on genuinely human
    sends; a workflow row is a robot whatever userId it wears."""
    if str(msg.get("source") or "").lower() == "workflow":
        return False
    return bool(msg.get("userId"))


def _is_machine_row(msg: dict) -> bool:
    """True when a raw GHL row was sent by our machinery, not typed by a
    person: an API send (GHL stamps the marketplace appId on those; Santino's
    own app sends carry none) or a workflow automation."""
    meta = msg.get("meta") or {}
    if isinstance(meta, dict) and (meta.get("marketplace") or {}).get("appId"):
        return True
    return str(msg.get("source") or "").lower() == "workflow"


# A message that itself promises or stalls ("I'll get you the exact number,
# one sec", "passing this along to Santino") is a HOLDING line, not the
# delivery of anything. Used to decide whether our own later message closed
# an owed answer or promise (Jim/CRW 2026-09-28).
_HOLDING_EXTRA_RE = re.compile(
    r"\b(?:pass(?:ing)? (?:this|it|that) along|one sec|give me a (?:sec|second|"
    r"minute|moment)|let me (?:check|find out|look)|checking (?:on|into)|"
    r"looking into|flagging (?:this|it))\b", re.I)


def _is_holding_line(body: str | None) -> bool:
    b = body or ""
    return bool(_PROMISE_RE.search(b) or _HOLDING_EXTRA_RE.search(b))


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
                if not body:
                    # Inbound emails land in the conversations feed as SHELLS
                    # (body AND attachments null); the real content sits behind
                    # the email endpoint. Jaziel/RestorationXpress 2026-08-24:
                    # the customer-list email was silently dropped right here
                    # by the `if not body: continue` below. Hydrate first.
                    email_ids = (((msg.get("meta") or {}).get("email") or {})
                                 .get("messageIds") or [])
                    if email_ids:
                        try:
                            full = _ghl("GET",
                                        f"/conversations/messages/email/{email_ids[0]}") or {}
                            e = full.get("emailMessage", full)
                            subj = (e.get("subject") or "").strip()
                            raw = re.sub(r"<[^>]+>", " ", e.get("body") or "")
                            raw = re.sub(r"\s+", " ", raw).strip()
                            att = e.get("attachments") or []
                            parts = [f"[email: {subj}]" if subj else "[email]"]
                            if raw:
                                parts.append(raw[:HISTORY_EMAIL_TRIM])
                            if att:
                                names = ", ".join(a.rsplit("/", 1)[-1] for a in att[:3])
                                parts.append(f"[{len(att)} attachment(s): {names}]")
                            body = " ".join(parts).strip()
                        except Exception:  # noqa: BLE001 — hydration is best-effort
                            body = "[inbound email — content unavailable]"
            n_att = len(msg.get("attachments") or [])
            if n_att:
                # photo-only MMS must be visible in history or the composer
                # re-asks for photos the client already texted (Jeff, 07-22)
                tag = f"[sent {n_att} photo/video attachment(s)]"
                # VISION TAGS (ACS 2026-09-19): inbound images get a one-line
                # description so the composer knows WHAT the client is
                # pointing at — a screenshot of our own site is site
                # feedback, not name feedback. Cached per URL; fail-soft to
                # the plain count tag.
                if msg.get("direction") == "inbound":
                    try:
                        vt = attachment_vision_tags(msg.get("attachments"))
                        if vt:
                            tag = f"[sent {n_att} attachment(s) — {vt}]"
                    except Exception:  # noqa: BLE001
                        pass
                body = f"{body} {tag}".strip() if body else tag
            if not body:
                continue
            merged.append({
                "id": msg.get("id"), "when": when,
                # A row bearing a userId is OURS whatever the direction
                # field says (is_internal_sender: external-mailbox sends
                # come back through GHL's sync marked "inbound") — so the
                # transcript reads it as our side and the human-defer /
                # quiet-window logic sees the human activity it represents.
                "direction": ("out" if is_internal_sender(msg)
                              else "in" if msg.get("direction") == "inbound"
                              else "out"),
                # user_id: set ONLY on messages a real person sent from the
                # GHL app (texts AND calls). MACHINE rows carry it too and are
                # nulled here: since 2026-09-04 every API send through our
                # GHL key (Monica, Claude one-offs) is stamped with Santino's
                # userId, and the only thing telling them apart is the
                # marketplace appId GHL adds to API sends (his app sends have
                # none). Unnulled, Monica read her own holding acks as
                # Santino answering, so owed follow-ups silently voided
                # (Jim/CRW 2026-09-28). Workflow rows are robots whatever
                # userId they wear (is_internal_sender, Mike Luna 09-06).
                "channel": channel, "body": body,
                "machine": _is_machine_row(msg),
                "user_id": (None if _is_machine_row(msg)
                            else msg.get("userId"))})
    merged.sort(key=lambda m: m["when"], reverse=True)
    return merged[:max_msgs]


def format_history(history: list[dict]) -> str:
    """Prompt-ready rendering, newest first ('them' = the client, 'us' =
    Monica/automation, 'us-human' = a real person on our team, usually
    Santino himself — their words must never be attributed to the client)."""
    return "\n".join(
        f"{m['when'].strftime('%Y-%m-%d %H:%M')} "
        f"{'them' if m['direction'] == 'in' else 'us-human' if m.get('user_id') else 'us'}"
        f" ({m['channel']}): {m['body']}"
        for m in history)


def human_conversation_deferral(history: list[dict], state: dict) -> str | None:
    """Reason to skip this cycle's nudge, or None.

    If the newest OUTBOUND message in the thread was written by a REAL HUMAN
    and it is < HUMAN_DEFER_HOURS old, the concierge stays quiet: never talk
    over Santino mid-conversation.

    Human detection is the GHL userId (2026-08-19, the Fran incident): every
    send a person makes from the app carries their user id; Monica's API
    sends and other automations carry none. The old signal — "id not in
    state.sent_message_ids" — deferred Monica against HERSELF whenever the
    ledger missed a send (a state-save race on the kv blob lost her 14:06
    webhook reply's id, and she then ignored Fran's "How's the website
    coming" through both afternoon passes while believing a human had the
    thread). userId cannot have that failure mode."""
    last_out = next((m for m in history if m["direction"] == "out"), None)
    if not last_out or not last_out.get("user_id"):
        return None
    # userId alone is NOT proof of a human (2026-09-14: sends through the
    # local .env GHL key stamp Santino's userId, so Monica's own machinery
    # and Claude's manual assists read as "Santino is mid-conversation" and
    # every follow-up self-deferred 12h — the Coastal/Arch/Desert Valley
    # silence). A message we delivered ourselves is in the sent ledger
    # (record_sent_message reconciles ids per-conversation), so userId +
    # ledger-hit = machine, keep going. Ledger misses still defer (safe
    # direction) and the reconciliation pass keeps those rare.
    if last_out.get("id") in sent_message_ids(state):
        return None
    if _is_machine_sent(last_out.get("id")):
        return None
    age = datetime.now(timezone.utc) - last_out["when"]
    if age < timedelta(hours=HUMAN_DEFER_HOURS):
        return ("recent human conversation — deferred (human outbound "
                f"{last_out['channel']} at "
                f"{last_out['when'].strftime('%Y-%m-%d %H:%M UTC')}, "
                f"{age.total_seconds() / 3600:.1f}h ago, within the "
                f"{HUMAN_DEFER_HOURS}h defer window)")
    return None


def human_reply_hold(contact_id: str) -> str | None:
    """SEND-TIME QUIET WINDOW (Santino 2026-08-18: "add a rule that she
    waits an hour whenever I reply"). If a real person on our side wrote to
    this contact, or called them, less than HUMAN_REPLY_HOLD_MIN minutes
    ago, every concierge send to that contact is blocked.

    Human detection is the GHL userId, not the sent-ids ledger: every
    message a person sends from the app (texts AND phone calls) carries the
    user's id; Monica's API sends carry none. Direct signal, so this can
    never trip the defer-against-herself trap the 12h nudge window fell
    into (see record_sent_message).

    Live failure this fixes, Tony Mendez 08-17: Santino took the thread
    over himself at 20:36 ("Hey Tony its Santino yes lets talk") and Monica
    talked over him at 20:38, 21:00 and 21:27 while he was live-texting the
    call coordination. Unlike the 12h nudge deferral above, this gate lives
    in send_message and covers EVERY path, inline replies and acks
    included. Blocked sends are safe: anything still owed stays armed as
    awaiting_reply and recomposes after the hour. send_now bypasses it, the
    explicit click IS Santino speaking. Fails OPEN on API errors: a guard
    that cannot see the thread must not silence real work."""
    try:
        history = fetch_history(contact_id, max_msgs=25)
    except Exception as e:  # noqa: BLE001
        print(f"  [human-hold] history fetch failed, not holding: "
              f"{str(e)[:80]}", file=sys.stderr)
        return None
    now = datetime.now(timezone.utc)
    # Same userId caveat as human_conversation_deferral (2026-09-14): our
    # own sends can carry Santino's userId when the GHL key is user-scoped.
    # Anything in the sent ledger is ours, never a reason to hold.
    try:
        machine_ids = sent_message_ids(load_state())
    except Exception:  # noqa: BLE001 — hold logic must never crash a send
        machine_ids = set()
    for m in history:                      # newest first
        if m["direction"] != "out" or not m.get("user_id"):
            continue
        if m.get("id") in machine_ids or _is_machine_sent(m.get("id")):
            continue
        age_min = (now - m["when"]).total_seconds() / 60
        if age_min < HUMAN_REPLY_HOLD_MIN:
            return (f"HUMAN QUIET WINDOW — Santino (or another human) sent a "
                    f"{m['channel']} in this thread {age_min:.0f} min ago "
                    f"({m['body'][:40]!r}); Monica waits "
                    f"{HUMAN_REPLY_HOLD_MIN} min after a human speaks "
                    "(Santino 2026-08-18). Anything still owed sends next "
                    "cycle.")
        break                              # newest human outbound is old enough
    return None


def pending_client_message(cs: dict, history: list[dict], state: dict) -> dict | None:
    """The newest substantive client message still owed a real reply, as
    {"body", "kind", "at", "recheck"} — or None when nothing is owed.

    THIS FUNCTION IS THE RE-CHECK (Santino 2026-08-04: "if a message is
    outside the window, it doesn't just get queued up to send first thing in
    the morning — it double-checks the context before sending, because things
    may have changed"). Nothing deferred is ever stored as finished TEXT: what
    persists is this flag, and every pass re-derives the answer from the live
    thread, so a message held overnight is recomposed in the morning against
    whatever the thread looks like then, never replayed. The checks below run
    at the moment we are about to act, not when the reason was armed:
      - the client spoke AGAIN since we armed -> the armed body is stale; the
        flag is REFRESHED to what they actually said last, so the draft
        answers the newest thing rather than quoting yesterday's message as
        "the newest message in this thread";
      - somebody advanced the thread -> the reason evaporated, flag cleared,
        nothing sends (the void rules below);
      - the reason aged out past 7 days -> cleared.
    Facts inside the draft are re-verified separately at send time:
    verify_outbound_links (a link that has since died blocks the send and
    heals from marketing_sites), topic_ban_violation, outbound_guard,
    repeats_last_outbound, and filter_already_satisfied for items the client
    has since answered.

    Replying to a client who spoke last is NOT a nudge — this drives the
    compose-side cooldown/nudge-cap bypass (2026-08-02: Todd's "I wonder why
    they suspended the listing" sat unanswered behind the 3-day cooldown
    while the daily ack cap ate the holding line). Two sources:
      (1) cs["awaiting_reply"], set by the inbound engine — kind "question"
          (their reply needed a real answer and matched no item; survives
          Monica's own holding ack sitting newest in the thread), kind
          "answer" (they answered OUR question — the follow-through is owed;
          Todd's "Invoices2Go" got silence, 2026-08-02 15:48), or kind
          "closer" (substantive but needs no answer — we still owe the last
          word; Fran/QCI 2026-08-04, see the closer branch in cmd_inbound);
      (2) the live thread: the newest message is inbound sms/email, not a
          pure acknowledgment, and < 7 days old (kind "message").
    Void rules (the no-double-send property):
      - kind "answer" / "closer": ANY newer outbound voids it, ours included
        — once something advanced the thread after their message we already
        have the last word, never send twice;
      - kind "question": a newer HUMAN outbound voids it (Santino answered
        it himself), and so does our own SUBSTANTIVE answer (Jim/CRW
        2026-09-28); only our holding ack ("one sec", "I'll get you
        that") leaves it owed."""
    now = datetime.now(timezone.utc)

    def outbound_after(after: datetime, human_only: bool) -> bool:
        for m in history:
            if m["direction"] != "out" or m["when"] <= after:
                continue
            if not human_only:
                return True
            if m.get("user_id"):
                return True   # a real human wrote it (fetch_history nulls
                              # user_id on machine rows)
            # OUR OWN REAL ANSWER counts too (Jim/CRW 2026-09-28): only a
            # holding line ("one sec", "I'll get you the number") leaves the
            # question owed. Monica's correction with the actual price did
            # not close "How much is it?", so three days later she answered
            # it again and contradicted herself.
            if m.get("machine") and not _is_holding_line(m.get("body")):
                return True
        return False

    def substantive_inbound_after(after: datetime) -> dict | None:
        """The newest real client message later than `after` (oldest-first
        scan so we end on the newest), or None."""
        found = None
        for m in reversed(history):
            if m["direction"] != "in" or m["when"] <= after:
                continue
            if m.get("channel") not in ("sms", "email"):
                continue
            body_ = (m.get("body") or "").strip()
            if not body_ or _REACTION_RE.match(body_) or _bare_ack(body_):
                continue
            found = m
        return found

    flag = cs.get("awaiting_reply") or {}
    if flag.get("body"):
        kind = str(flag.get("kind") or "question")
        try:
            at = datetime.fromisoformat(flag["at"])
        except (KeyError, ValueError):
            at = now
        advanced = outbound_after(at, human_only=(kind == "question"))
        if (now - at) > timedelta(days=7) or advanced:
            cs.pop("awaiting_reply", None)   # stale, or the thread moved on
        else:
            # RE-CHECK: did they say something newer while we were holding
            # this? Then the armed body is history and answering it would be
            # answering the wrong message. Re-point the flag at what they
            # actually said last and let the caller recompose. A newer
            # message also RESETS the clock, which is what the fast-reply
            # window should measure against.
            newer = substantive_inbound_after(at)
            recheck = None
            if newer:
                recheck = (f"client sent a newer message since this was "
                           f"armed ({at:%m-%d %H:%M} -> "
                           f"{newer['when']:%m-%d %H:%M} UTC) — recomposing "
                           f"against {newer['body'][:60]!r}")
                flag["body"] = newer["body"][:300]
                flag["at"] = newer["when"].isoformat()
                flag["channel"] = newer.get("channel") or flag.get("channel")
                at = newer["when"]
            return {"body": str(flag["body"]), "kind": kind,
                    "at": at.isoformat(), "recheck": recheck}
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
            return {"body": body, "kind": "message",
                    "at": newest["when"].isoformat(), "recheck": None}
    return None


def revalidate_commitment(cs: dict, history: list[dict], state: dict,
                          evidence: str | None = None) -> str | None:
    """Drop a pending_commitment somebody else already delivered, returning
    the audit line — else None.

    Same re-check discipline as pending_client_message (Santino 2026-08-04): a
    promise recorded last night is not automatically still owed this morning.
    If a HUMAN outbound (not one of ours) landed after we made the promise,
    Santino answered it himself and re-delivering would be the second time the
    client hears it.

    A FINISHED PROMISE IS NOT AN OPEN ONE (2026-08-05, Reign): when the work
    ledger shows the promised work shipped, the commitment is satisfied. Left
    armed, it forces the next compose to "deliver" a promise about work that
    is already live, which is exactly how a client hears "we'll get that
    matched up" an hour after we told him it was matched."""
    commitment = cs.get("pending_commitment") or {}
    at = _as_utc(commitment.get("at"))
    if not commitment.get("promise") or at is None:
        return None
    ours = sent_message_ids(state)
    for m in history:
        if m["direction"] != "out" or m["when"] <= at:
            continue
        machine = m.get("machine") or (m["id"] and m["id"] in ours)
        if not machine:
            cs.pop("pending_commitment", None)
            return (f"open commitment dropped: a human answered it at "
                    f"{m['when']:%m-%d %H:%M} UTC "
                    f"({str(m.get('body'))[:60]!r}) — not delivering it twice")
        # WE ALREADY DELIVERED IT (Jim/CRW 2026-09-28): "I'll get you the
        # exact number" stayed armed after Monica's own correction gave him
        # the price, because only a HUMAN reply ever cleared a promise; on
        # the Sunday it was "delivered" again as "Good question, that's one
        # Santino handles". A later substantive message from us is the
        # delivery; a holding line (the promise itself included) is not.
        if not _is_holding_line(m.get("body")):
            cs.pop("pending_commitment", None)
            return (f"open commitment dropped: we already followed through at "
                    f"{m['when']:%m-%d %H:%M} UTC "
                    f"({str(m.get('body'))[:60]!r}) — not delivering it twice")
    topics = message_topics(commitment.get("promise"))
    if topics and evidence:
        for line in _evidence_done_lines(evidence):
            if _WORK_DONE_RE.search(line) and (topics & message_topics(line)):
                cs.pop("pending_commitment", None)
                return (f"open commitment dropped: the work ledger shows it "
                        f"shipped ({line[:70]!r}) — it is done, not owed")
    return None


# PROMISE HOLD (Santino 2026-09-29, Katofsky): Monica kept nudging Michael
# for a customer list that was not due for weeks while OUR promise to him sat
# seven days overdue. While a client holds an OVERDUE open commitment of ours
# (public.client_commitments, written by scripts/promise_tracker.py), the
# proactive nudge path stops asking them for anything. Replies to their
# messages, delivering our own promise and Santino's directives still go;
# only client-owed asks are dropped. Fail-open: a lookup error never blocks.
def overdue_commitments(company_ids: list[str] | str,
                        now: datetime | None = None) -> list[dict]:
    ids = [company_ids] if isinstance(company_ids, str) else list(company_ids)
    ids = [i for i in ids if i]
    if not ids:
        return []
    now = now or datetime.now(timezone.utc)
    # WHICH PROMISES HOLD (2026-09-29 backfill): the client is waiting on an
    # ANSWER / decision / message from us (owner monica or santino: the
    # Katofsky name options). Build work (owner dev: "build the site", "set
    # up LSA") lives on the dev queue and often NEEDS the very items Monica
    # nudges for, and the 21-day backfill found 100+ such rows the close
    # check cannot prove from messages; holding on them would silence Monica
    # fleet-wide. PROMISES_HOLD_OWNERS widens it (e.g. "monica,santino,dev").
    owners = [o.strip() for o in os.environ.get(
        "PROMISES_HOLD_OWNERS", "monica,santino").split(",") if o.strip()]
    # ROLLOUT GATE: the 21-day backfill (57 overdue monica/santino rows over
    # 22 clients, unreviewed) would have held Monica fleet-wide on day one.
    # Only promises made on/after PROMISES_HOLD_SINCE hold; move the date
    # back once Santino has triaged the backfill in the digest.
    hold_since = os.environ.get("PROMISES_HOLD_SINCE", "2026-09-29T00:00:00+00:00")
    try:
        return _sb("GET", "/rest/v1/client_commitments?status=eq.open"
                   "&company_id=in.(" + ",".join(ids) + ")"
                   "&owner=in.(" + ",".join(owners) + ")"
                   "&said_at=gte." + urllib.parse.quote(hold_since)
                   + "&due_at=lt." + urllib.parse.quote(now.isoformat())
                   + "&select=id,company_id,what,quote,owner,due_at"
                   "&order=due_at.asc") or []
    except Exception as e:  # noqa: BLE001 — the hold is fail-open
        print(f"  [promise-hold] lookup failed ({str(e)[:80]}) — no hold")
        return []


def promise_hold(items: list[dict], overdue: list[dict]
                 ) -> tuple[list[dict], str | None]:
    """(items to keep, hold reason). An overdue promise of ours empties the
    client-owed ask list; the caller skips the send entirely when nothing
    else (a reply, our own promise, a directive) is owed."""
    if not overdue or not items:
        return items, None
    o = overdue[0]
    due = str(o.get("due_at") or "")[:10]
    return [], (f"promise-hold: we owe them {len(overdue)} overdue "
                f"promise(s), oldest due {due}: {str(o.get('what'))[:90]!r} "
                f"— not nudging for {len(items)} client-owed item(s) until "
                "we deliver (scripts/promise_tracker.py list)")


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


# ------------------------------------------- second-pass / contradiction guard
# TWO MESSAGES ONE MINUTE APART THAT CONTRADICT EACH OTHER (Santino
# 2026-08-05, LIVE on Reign Restoration). Jerrott wrote at 15:52 "I did like
# the about photo... I just wanted the logos to match on the company
# vehicles", and Monica answered TWICE:
#   15:54:23  "The van logos are already matched to your real logo on the
#              staging preview" — true, the fix shipped at 15:19
#   15:55:23  "We'll get the vehicle logos matched up so they look
#              consistent across all the trucks" — false, and it made the
#              finished work sound like it had not started
# Twenty minutes earlier the same thread took "Will do, talk soon." TWICE,
# four seconds apart.
#
# ROOT CAUSE — two passes processed the same inbound and neither could see
# the other:
#   1. webhook_inbound() loads the state blob, then DEBOUNCES (up to 360s)
#      before processing, and only saves at the end. The handled-message
#      ledger therefore is not durable until the whole run finishes, so a
#      second pass that starts inside that window sees the message as fresh,
#      classifies it again (the 15:55:21 work-log row is a duplicate
#      client-feedback card filed by that second pass) and answers it again.
#   2. The API's per-contact lock is a threading.Lock — it serializes threads
#      inside ONE Railway process and does nothing about the scheduled
#      GitHub-Actions run, a second Railway replica, or send-now.
#   3. repeats_last_outbound() compares against the newest message in a GHL
#      history snapshot. GHL indexes with a lag (the 4-second pair was
#      invisible to both runs) and the snapshot is taken before the debounce,
#      so the guard was comparing against yesterday's thread.
#   4. It also only ever looked at the SINGLE newest outbound and only at
#      word overlap, so "already matched" vs "we'll get them matched" (the
#      halves diverge) scored under the 0.55 threshold anyway.
#
# THE FIX, in layers, so no single failure re-opens it:
#   - every client send is stamped into a cross-process outbox in ops_kv the
#     instant it lands, so the next pass in ANY process sees it with no GHL
#     lag (note_outbound / recent_outbounds)
#   - BACK-TO-BACK RULE: we never send twice inside TOPIC_REPEAT_MINUTES
#     unless the client spoke in between. That is the whole anti-pattern,
#     stated once, and it needs no lexical luck.
#   - CONTRADICTION RULE: a message that promises FUTURE work on a subject we
#     have already reported DONE (in a recent outbound or in the ledger
#     evidence) is refused outright, however differently it is worded.
#   - inbound messages are CLAIMED durably before any work (claim_inbound_
#     message), so a second pass never re-classifies or re-queues them.
OUTBOX_KEY = "concierge-outbox"       # {company_id: [{body, at, reply_to}]}
OUTBOX_KEEP = 6                       # entries kept per company
OUTBOX_LOOKBACK_MIN = 180             # how far back this guard looks
TOPIC_REPEAT_MINUTES = 15             # no two sends inside this, unless they spoke


def note_outbound(company_id: str | None, body: str,
                  reply_to: str | None = None) -> None:
    """Stamp a delivered client message into the cross-process outbox.

    Called from send_message, so EVERY path (compose, send-now, inline
    reply, ack, closer, reschedule) is covered by construction. Best-effort:
    a KV hiccup must never fail a send that already went out."""
    if not company_id:
        return
    try:
        box = kv_get(OUTBOX_KEY) or {}
        if not isinstance(box, dict):
            box = {}
        now = datetime.now(timezone.utc)
        rows = [r for r in (box.get(company_id) or []) if isinstance(r, dict)]
        rows.append({"body": (body or "")[:400], "at": now.isoformat(),
                     "reply_to": reply_to})
        box[company_id] = rows[-OUTBOX_KEEP:]
        # keep the key small: drop companies quiet for a day
        cutoff = now - timedelta(hours=24)
        box = {c: rs for c, rs in box.items()
               if any((_as_utc(r.get("at")) or now) >= cutoff for r in rs)}
        kv_set(OUTBOX_KEY, box)
    except Exception as e:  # noqa: BLE001
        print(f"  [outbox] stamp failed ({str(e)[:80]}) — the duplicate "
              "guard falls back to GHL history for this send")


def recent_outbounds(company_id: str | None,
                     minutes: int = OUTBOX_LOOKBACK_MIN) -> list[dict]:
    """Our own recent sends to this company, newest first, from the outbox."""
    if not company_id:
        return []
    try:
        box = kv_get(OUTBOX_KEY) or {}
    except Exception:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    rows = []
    for r in (box.get(company_id) or []):
        when = _as_utc(r.get("at"))
        if when and when >= cutoff:
            rows.append({"body": r.get("body") or "", "when": when,
                         "reply_to": r.get("reply_to")})
    return sorted(rows, key=lambda r: r["when"], reverse=True)


CLAIMS_KEY = "concierge-claims"       # {msg_id: iso} claimed inbound messages
CLAIM_TTL_H = 24


def claim_inbound_message(msg_id: str, dry_run: bool) -> bool:
    """True when THIS run owns the message and may process it.

    The handled-ids ledger inside the big state blob is not durable until the
    end of a run — and a webhook run can sleep for minutes in the debounce
    before it ever saves. A second pass starting inside that window saw the
    message as brand new, re-classified it, filed a DUPLICATE feedback card
    and answered it again (Reign, 2026-08-05, 15:54 and 15:55). This claim
    is its own small KV key, written the instant the message is picked up, so
    the window shrinks from minutes to milliseconds and is shared across
    processes. Fails OPEN: if the KV is unreachable, better a rare double
    than a silent Monica."""
    if not msg_id:
        return True
    try:
        claims = kv_get(CLAIMS_KEY) or {}
        if not isinstance(claims, dict):
            claims = {}
    except Exception as e:  # noqa: BLE001
        print(f"    [claim] lookup failed ({str(e)[:70]}) — processing anyway")
        return True
    if msg_id in claims:
        return False
    if dry_run:
        return True
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=CLAIM_TTL_H)
    claims = {k: v for k, v in claims.items()
              if (_as_utc(v) or now) >= cutoff}
    claims[msg_id] = now.isoformat()
    try:
        kv_set(CLAIMS_KEY, claims)
    except Exception as e:  # noqa: BLE001
        print(f"    [claim] write failed ({str(e)[:70]}) — the outbox guard "
              "is the remaining net")
    return True


# Subject tagging for the contradiction rule. Deliberately coarse: it only
# has to answer "are these two messages about the same thing?".
_TOPIC_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("vehicles", re.compile(r"\b(van|vans|truck|trucks|vehicle|vehicles|"
                            r"decal|decals|wrap|wraps|livery|fleet)\b", re.I)),
    ("brand", re.compile(r"\b(logo|logos|gold|yellow|colou?rs?|branding|"
                         r"palette)\b", re.I)),
    ("imagery", re.compile(r"\b(photo|photos|picture|pictures|image|images|"
                           r"ppe|gear|uniform|headshot)\b", re.I)),
    ("service_area", re.compile(r"\b(service area|cities|coverage|dallas|"
                                r"plano|frisco|mckinney)\b", re.I)),
    ("domain", re.compile(r"\b(domain|godaddy|registrar|go live|launch)\b",
                          re.I)),
    ("reviews", re.compile(r"\b(review|reviews|customer list|past customers)\b",
                           re.I)),
    ("google_listing", re.compile(r"\b(google (?:business )?listing|"
                                  r"business profile|maps)\b", re.I)),
    ("scheduling", re.compile(r"\b(call|meeting|zoom|reschedule)\b", re.I)),
)


def message_topics(text: str | None) -> set[str]:
    return {tag for tag, rx in _TOPIC_PATTERNS if rx.search(text or "")}


# "already matched", "all three are fixed", "your photos are live" — we told
# them the work is DONE.
_WORK_DONE_RE = re.compile(
    r"\b(?:already|now|just)\s+(?:match(?:ed|es)?|fixed|updated|changed|"
    r"swapped|added|replaced|live|done|in place)\b"
    r"|\b(?:is|are|all)\s+(?:fixed|updated|matched|live|done|set|"
    r"good to go|taken care of|in)\b"
    r"|\bfixed (?:all|them|it|those|the)\b"
    r"|\bwe(?:'ve| have)\s+(?:fixed|updated|matched|changed|added|swapped|"
    r"replaced)\b", re.I)
# "we'll get the logos matched", "I'll fix that", "we're going to update it"
_WORK_FUTURE_RE = re.compile(
    r"\b(?:we'?ll|we will|i'?ll|i will|we(?:'re| are) going to|"
    r"i(?:'m| am) going to|we can|we'?re gonna)\s+"
    r"(?:go ahead and |just |also )?"
    r"(?:get|fix|match|update|change|add|swap|redo|regenerate|make|sort|"
    r"take care of|clean up|work on|adjust)\b", re.I)


def _evidence_done_lines(evidence: str | None) -> list[str]:
    """WORK ALREADY DONE / ops-note lines that report finished work."""
    out = []
    for line in (evidence or "").splitlines():
        line = line.strip(" -")
        if line and not line.startswith("["):
            out.append(line)
    return out


def _reply_key(target: dict | None) -> str | None:
    """Stable, cross-process id for the CLIENT message an outbound answers.

    Prefers the timestamp, because that is the one field every path holds:
    the armed awaiting_reply flag (compose), the ack's synthetic message and
    the raw inbound all carry the same instant. Two passes answering the same
    text therefore produce the same key even though only one of them ever
    saw a GHL message id."""
    if not target:
        return None
    at = target.get("at") or target.get("ts")
    if at:
        return f"at:{at.isoformat() if hasattr(at, 'isoformat') else at}"
    mid = target.get("id")
    return f"msg:{mid}" if mid else None


def repeats_recent_outbound(company_id: str | None, body: str,
                            history: list[dict], *,
                            evidence: str | None = None,
                            reply_to: str | None = None,
                            boss_directive: bool = False) -> str | None:
    """Reason to hold this outbound because we ALREADY spoke, or because it
    contradicts what we already told them — else None.

    Four independent nets (Santino 2026-08-05, Reign):
      1. word overlap with any of our last few outbounds (the original guard,
         widened from the single newest message)
      2. we already answered this exact client message in another pass
      3. BACK-TO-BACK: a send inside TOPIC_REPEAT_MINUTES with nothing from
         the client in between — the second pass stays silent
      4. CONTRADICTION: promising FUTURE work on a subject a recent outbound
         (or the ledger evidence) already reported DONE"""
    now = datetime.now(timezone.utc)
    # A phone call is not a message (fetch_history renders calls as
    # "[phone call]"): a human dialling the client must never read as "we
    # already texted them" — the human-defer window covers that case.
    hist_out = [{"body": m.get("body") or "", "when": m["when"],
                 "reply_to": None}
                for m in (history or [])
                if m.get("direction") == "out"
                and m.get("channel") != "call"
                and (m.get("body") or "").strip()
                and (m.get("body") or "").strip() != "[phone call]"]
    mine = recent_outbounds(company_id)
    seen, cands = set(), []
    for row in sorted(hist_out + mine, key=lambda r: r["when"], reverse=True):
        key = (row["body"] or "").strip()[:120]
        if key in seen:
            continue
        seen.add(key)
        cands.append(row)
    # 4b FIRST, because it needs no prior outbound at all: the ledger says
    # this work shipped, so promising it forward is false whatever else the
    # thread looks like.
    # BOSS-DIRECTIVE BYPASS (Todd 2026-08-11): nets 4/4b are skipped when the
    # draft carries Santino's exact words. His correction "site is live AND
    # we're working the reinstatement" held twice: topic matching is message-
    # level, so a draft that truthfully pairs done work with in-progress work
    # trips against the done line. A verbatim order is human-adjudicated;
    # the dedupe nets (1-3) still apply to it in full.
    if not boss_directive and _WORK_FUTURE_RE.search(body or ""):
        topics = message_topics(body)
        for line in _evidence_done_lines(evidence):
            if topics and (_WORK_DONE_RE.search(line)
                           or "fix" in line.lower()) and (
                    topics & message_topics(line)):
                return ("CONTRADICTS the work ledger: this promises future "
                        f"work the record shows is already done ({line[:80]!r})"
                        " — say it is done, or say nothing")
    if not cands:
        return None
    last_in = next((m["when"] for m in (history or [])
                    if m.get("direction") == "in"), None)

    def toks(s: str) -> set:
        return {w for w in re.findall(r"[a-z']+", (s or "").lower())
                if len(w) > 2}

    new_topics = message_topics(body)
    a = toks(body)
    for cand in cands[:4]:
        age_min = (now - cand["when"]).total_seconds() / 60
        # 1. lexical near-duplicate (unchanged threshold, wider net)
        b = toks(cand["body"])
        if a and b and age_min < SIMILAR_RECENT_HOURS * 60:
            overlap = len(a & b) / len(a | b)
            if overlap >= SIMILAR_JACCARD:
                return (f"too similar to an outbound {age_min:.0f} min ago "
                        f"({overlap:.0%} word overlap): {cand['body'][:70]!r}")
        # 2. another pass already answered this same client message
        if (reply_to and cand.get("reply_to") == reply_to
                and age_min <= OUTBOX_LOOKBACK_MIN):
            return (f"another pass already answered this same message "
                    f"{age_min:.0f} min ago: {cand['body'][:70]!r}")
        # 4. contradiction: they were told it is DONE, this says we will do it
        if (not boss_directive
                and age_min <= OUTBOX_LOOKBACK_MIN
                and _WORK_FUTURE_RE.search(body or "")
                and _WORK_DONE_RE.search(cand["body"])
                and (new_topics & message_topics(cand["body"]))):
            return ("CONTRADICTS what we already told them: we reported this "
                    f"work DONE {age_min:.0f} min ago ({cand['body'][:70]!r}) "
                    "and this message promises it as future work")
    # 3. back-to-back: we spoke last and the client has not answered yet.
    # BOSS-DIRECTIVE EXEMPTION (ACS 2026-09-19): a [FROM SANTINO] correction
    # of a wrong outbound has to land IN the same turn — that is when the
    # client is about to act on the wrong message. Net 3's target is
    # accidental second passes; a directive is human-adjudicated, and the
    # directive resolves on first send so a racing pass no longer carries
    # it. Nets 1-2 (same copy / already answered) still apply in full.
    if boss_directive:
        return None
    newest = cands[0]
    gap_min = (now - newest["when"]).total_seconds() / 60
    if gap_min <= TOPIC_REPEAT_MINUTES and (
            last_in is None or newest["when"] > last_in):
        return (f"we already sent a message {gap_min:.0f} min ago and they "
                f"have not replied since: {newest['body'][:70]!r} (one "
                "outbound per turn — a second pass stays silent)")
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


# PERSONA GUARD (Santino 2026-08-04, LIVE failure): Monica opened Jerrott
# Gray's first-day thread with "Great meeting with you yesterday!" — and the
# HomeLyft draft carried "Great meeting with you all Thursday". Monica is a
# non-human assistant on Santino's team. She has never been on a call, in a
# meeting, on a site visit, or in a room with anybody, and a client who later
# finds that out stops trusting every other word she wrote. The prompts now
# forbid first-person attendance; this is the mechanical backstop.
#
# The BANNED shape is first-person experience ("great meeting you", "as we
# discussed on the call", "when we met", "I saw"). The CORRECT shape is the
# team in third person: "Santino mentioned...", "great call with Santino
# yesterday", "the team went over...". A sentence that attributes to a named
# human third-personally is exempt — that is the fix we want people writing.
_THIRD_PERSON_ATTRIB_RE = re.compile(
    r"\bsantino(?:'s)?\b[^.!?]{0,20}\b(?:said|mentioned|told|says|noted|"
    r"passed along|loved|enjoyed|went over|walked|covered|shared|put)\b"
    r"|\b(?:the|our|his) team\b[^.!?]{0,20}\b(?:said|mentioned|told|went "
    r"over|covered|walked|noted|loved|enjoyed|shared)\b"
    r"|\bfrom santino\b|\bwith santino\b", re.I)

_PERSONA_CLAIMS: tuple[tuple[re.Pattern, str], ...] = (
    # "Great meeting you yesterday" / "nice talking with you" / "great to
    # meet you all" — a pleasantry only somebody who was THERE can offer.
    # Deliberately TIGHT (only connective words may sit between the parts):
    # a loose window turned the perfectly good "we're excited for you to see
    # it" into a false refusal on the very first Reign draft, 2026-08-04.
    (re.compile(r"\b(?:great|good|nice|lovely|wonderful|awesome|glad|"
                r"pleasure|enjoyed)\b\s+(?:it\s+was\s+|to\s+|really\s+|"
                r"so\s+)*(?:meeting|meet|talking|talk|speaking|speak|"
                r"chatting|chat|catching\s+up|connecting|seeing|see)\s+"
                r"(?:up\s+)?(?:with\s+|to\s+)?(?:you|y'?all|ya'?ll|"
                r"your\s+team|the\s+team|everyone|the\s+crew)\b", re.I),
     "greets the client as though Monica personally met or spoke with them"),
    # "glad we could finally connect" / "great that we met"
    (re.compile(r"\b(?:glad|great|good|nice|happy)\b[^.!?]{0,15}\bwe\s+"
                r"(?:could\s+|finally\s+|got\s+to\s+)*(?:met|meet|connected|"
                r"connect|spoke|speak|talked|talk)\b", re.I),
     "celebrates a meeting Monica was supposedly part of"),
    # "looking forward to meeting you" — she will not be there either.
    (re.compile(r"\blook(?:ing)?\s+forward\s+to\s+(?:meeting|seeing|"
                r"talking\s+to|speaking\s+with|chatting\s+with)\s+"
                r"(?:you|y'?all|the\s+team)\b", re.I),
     "promises Monica will attend something she cannot attend"),
    # "when we met" / "since we last spoke"
    (re.compile(r"\b(?:when|since|after|before) we (?:met|spoke|talked|"
                r"sat down|chatted|last (?:spoke|talked|met))\b", re.I),
     "refers to a meeting Monica was supposedly part of"),
    # "we met Thursday" / "we spoke on the phone" / "we caught up yesterday"
    (re.compile(r"\bwe (?:met|spoke|talked|chatted|caught up)\b[^.!?]{0,30}"
                r"\b(?:yesterday|today|earlier|this morning|last week|"
                r"the other day|monday|tuesday|wednesday|thursday|friday|"
                r"on the (?:call|phone|zoom))\b", re.I),
     "claims Monica was on a past call or meeting with the client"),
    # "as we discussed" / "like we went over"
    (re.compile(r"\b(?:as|like) we (?:discussed|talked about|spoke about|"
                r"went over|covered|reviewed|agreed)\b", re.I),
     "cites a conversation Monica was supposedly in"),
    # "on our call" / "during our meeting" — "the call" (a future one we set
    # up together) stays legal; "OUR call" puts Monica in the room.
    (re.compile(r"\b(?:on|during|in|from|after|before) our (?:call|meeting|"
                r"zoom|conversation|chat|visit|kick-?off)\b", re.I),
     "says 'our call/meeting', which puts Monica in the room"),
    # "...meeting with me" / "hopping on with me"
    (re.compile(r"\b(?:meet|met|meeting|speak|spoke|speaking|talk|talked|"
                r"talking|chat|chatted|hop(?:ped|ping)? on|sit|sat) (?:down "
                r")?(?:with )?me\b", re.I),
     "invites the client to meet Monica, who cannot attend anything"),
    # First-person sensory/attendance. Reading a text or an emailed photo is
    # something she genuinely does, so message artifacts are exempt.
    (re.compile(r"\bI (?:saw|heard|watched|listened(?: to)?|sat in|attended|"
                r"joined|was on|was in|met|visited|stopped by)\b"
                r"(?!\s+(?:from\s+santino|(?:your|the|a|an|that|his|their)\s+)?"
                r"(?:message|messages|text|texts|reply|email|note|photos?|"
                r"pictures?|screenshot|voicemail))", re.I),
     "makes a first-person 'I was there / I saw it' claim"),
)


def persona_attendance_claim(body: str) -> str | None:
    """Refusal reason when `body` implies Monica personally attended a call,
    meeting or visit (or met the client), else None.

    Third-person team attribution is the sanctioned form and passes through:
    "Santino mentioned...", "great call with Santino yesterday", "the team
    went over the plan"."""
    for sent in re.split(r"(?<=[.!?])\s+", body or ""):
        if _THIRD_PERSON_ATTRIB_RE.search(sent):
            continue
        for rx, why in _PERSONA_CLAIMS:
            m = rx.search(sent)
            if m:
                return (f"persona violation — {why} ({m.group(0).strip()[:50]!r}). "
                        "Monica has never attended a call, meeting or visit; "
                        "reference the team in third person instead "
                        f"('Santino mentioned...'): {sent[:90]!r}")
    return None


# REGISTRAR-TRUTH GUARD (Santino 2026-08-04, LIVE failure): Monica told
# Jerrott "We'll reach out through GoDaddy to get the switch made so
# reign-restoration.com can go live." False, and worse than false — it told
# the client the launch blocker was OURS to clear, so he did nothing and the
# site stayed dark. No registrar exposes any way for us to request access.
# See DOMAIN_ACCESS_TRUTH (scripts/client_ops_sync.py) for the canonical text.
_REGISTRAR_NAMES = (r"(?:go\s?daddy|namecheap|name\s?cheap|bluehost|"
                    r"hostgator|hostinger|wix|squarespace|network\s?solutions|"
                    r"ionos|hover|dreamhost|enom|moniker|route\s?53|"
                    r"(?:the|your|their) registrar|"
                    r"(?:the|your|their) domain (?:provider|company|host|"
                    r"registrar|people))")

_FALSE_REGISTRAR_CLAIMS: tuple[tuple[re.Pattern, str], ...] = (
    # "we'll reach out through GoDaddy" / "I'll contact your registrar"
    (re.compile(r"\b(?:we|i)\b(?:'ll|'re| will| are| can| am)?[^.!?]{0,50}?"
                r"\b(?:reach(?:ing)? out|contact(?:ing)?|get(?:ting)? in "
                r"touch|call(?:ing)?|email(?:ing)?|work(?:ing)? with|"
                r"go(?:ing)? through|talk(?:ing)? to|request(?:ing)?|"
                r"ask(?:ing)?|coordinat(?:e|ing)|deal(?:ing)? with)\b"
                r"[^.!?]{0,40}?\b(?:through |with |to |at |via |from )?"
                + _REGISTRAR_NAMES, re.I),
     "says we will contact the registrar ourselves — no registrar offers "
     "that path"),
    # "we'll get access" / "we'll grab the access" — the acquisition claim
    # itself, with or without a registrar named.
    (re.compile(r"\b(?:we|i)\b(?:'ll| will|'re going to| am going to| can)\s*"
                r"(?:just |then |also |go ahead and )?"
                r"(?:get|obtain|grab|pull|retrieve|secure|request|ask for|"
                r"set up)\s+(?:the |your |their |domain |that )*access\b",
                re.I),
     "claims we will obtain the domain access ourselves"),
    # "GoDaddy will give us access" / "they'll send us the access"
    (re.compile(_REGISTRAR_NAMES + r"[^.!?]{0,40}\b(?:will|can|is going to|"
                r"'ll)\b[^.!?]{0,25}\b(?:give|send|grant|hand|get)\b"
                r"[^.!?]{0,15}\bus\b", re.I),
     "claims the registrar will hand access to us"),
)


def false_registrar_claim(body: str) -> str | None:
    """Refusal reason when `body` claims WE will obtain domain access from a
    registrar, else None. Only the owner can grant it (delegate invite to
    setup@restorationai.io, or their login) — see DOMAIN_ACCESS_TRUTH."""
    for sent in re.split(r"(?<=[.!?])\s+", body or ""):
        for rx, why in _FALSE_REGISTRAR_CLAIMS:
            m = rx.search(sent)
            if m:
                return (f"registrar-truth violation — {why} "
                        f"({m.group(0).strip()[:60]!r}). The CLIENT must "
                        "grant access (GoDaddy: account.godaddy.com/access "
                        f"-> Invite to Access -> {DOMAIN_ACCESS_INVITE_EMAIL})"
                        f": {sent[:90]!r}")
    return None


# CAPABILITY CONTRACT (Santino 2026-08-05, LIVE failure, caught 15 minutes
# after it went out): Tony at Coastal texted "Call me when u have a minute"
# and Monica answered "Got it, I'll give you a call shortly." She has no
# voice line and never will. This is worse than the "I'll walk you through
# it" class fixed on 08-02: that promise could at least be kept by the next
# message, this one cannot be kept by anything, so the client sits waiting by
# a phone that will never ring and every other word she wrote loses value.
#
# WHAT MONICA GENUINELY CAN DO (audited against this file, 2026-08-05):
#   - send and receive SMS + email (send_message / fetch_history). A text
#     thread is her entire body.
#   - answer from context she actually holds: open items, thread history,
#     meeting intel, ops notes, the WORK ALREADY DONE ledger.
#   - record an answer (apply_answer), resolve a plan row (resolve_plan_row),
#     close an item the conversation already satisfied.
#   - file paperwork a human will see: ops notes (file_contact_note),
#     escalations (append_escalation), a direct ping to Santino
#     (ask_santino_for_advice).
#   - share a link we already hold: website preview, Google-connect, hub
#     upload, setup-checklist card.
#   - MOVE AN EXISTING BOOKED CALL and offer that calendar's real free slots
#     (handle_reschedule_request -> GHL PUT /calendars/events/appointments).
#
# WHAT SHE CANNOT DO — claiming any of these is a lie to a client:
#   - make or receive a phone call. There is no voice path anywhere in this
#     system; CONCIERGE_FROM_NUMBER is an SMS sender, nothing answers it.
#   - BOOK A NEW MEETING. Verified 2026-08-05: the only calendar WRITE in the
#     concierge is the reschedule PUT above. Creating an appointment (POST
#     /calendars/events/appointments) exists solely in scripts/kickoff_prep.py
#     and is unreachable from every concierge path — so "I'll get you on
#     Santino's calendar" is the same false promise in a different hat. She
#     may ask for their best window and hand it to a human. That is all.
#   - sign into or change the client's Google / GoDaddy / Twilio / hosting
#     accounts on her own (the registrar half is false_registrar_claim above).
#   - be anywhere physically: no visits, no "stopping by", no "see you there".
#   - commit a specific human's clock ("Santino will call you", timed or
#     not — REVERSED 2026-08-18: naming Santino used to sanction the
#     promise; after Monica committed him to calls he never agreed to (Tony
#     Mendez 08-17) he ruled that only he commits himself).
#   - commit to a deadline no scheduled system action will honor.
#
# THE HONEST MOVE when a client asks for a call: say you are passing it
# along to Santino, ask for their best window, and ESCALATE so he actually
# sees it. Being asked for a call is a needs_santino event by definition.

# What the drafting models are told, once, in one place (substituted into
# COMPOSE/REPLY/ACK/CLASSIFY exactly like DOMAIN_ACCESS_TRUTH) so the prompts
# and the mechanical guard below can never tell two different stories.
CAPABILITY_CONTRACT = """\
WHAT YOU CAN AND CANNOT DO — HARD RULE (Santino 2026-08-05, live failure: a
client texted "Call me when u have a minute" and Monica answered "Got it,
I'll give you a call shortly." She cannot make phone calls. He waited for a
call that could never come).
YOU CAN: send and receive texts and emails; answer from what is in your
context; record their answers; share a link you were given; hand something to
Santino; move a call they already have booked.
OUR WORK IS OURS (Santino 2026-09-14): directory listings, citations and
business profiles are BUILT BY US, in-house, always. Never say "ordered",
"purchased", "credits", or name any vendor or third-party service for this
work — say "building", "created", "publishing". The client's perception
that we create these ourselves is correct and must stay intact.
WHAT WE BUILD (Santino 2026-09-18, live failure: Alfredo asked "Are you
the ones making AI YouTube videos on my behalf?" and Monica said it wasn't
something on our side — it was OUR System 5 videos on the channel we run
for him). Our service for every client includes: their website and its
blog posts, Google Business Profile posts and optimization, directory
listings and citations, review campaigns, AND YouTube videos — we produce
AI-made videos and publish them to a YouTube channel we set up and run
for the client. When a client notices videos, posts, or listings about
their business appearing online, the answer is a confident YES, that is
us, part of the visibility system they pay for — never "not something on
our side" and never "let me check". If they dislike any of it, note the
feedback and pass it along; but authorship is never in doubt. The SCHEDULING SYSTEM (not
you) can also book a NEW call: when a client asks to schedule, a separate
flow offers real open slots and sends its own confirmation only after the
calendar write succeeds — so YOUR text never proposes, names, or confirms a
meeting time. Referencing a call that already exists in your Upcoming
appointments context is fine, phrased as "your call is on the calendar
for ...".
YOU CANNOT, EVER: make or take a phone call; promise, propose or confirm a
meeting time in your own words (the scheduling flow owns every sentence
like "you're all set for Tuesday"); log into or change their Google,
GoDaddy, Twilio or hosting accounts; show up anywhere in person; promise
that Santino (or anyone else) WILL call, or when anyone will be available;
promise a deadline ("by end of day", "within the hour", "first thing
tomorrow").
BANNED, no exceptions: "I'll give you a call", "I'll call you", "let me hop
on a call", "I'll ring you", "I'll get on the phone", "give me a call",
"call me at", "Santino will give you a call", "Santino will call you",
"I'll have Santino call you", "I'll get you on his calendar", "I'll book a
time", "talk to you then", "see you then", "I'll stop by".
TRACKING NUMBERS (Frontline/Jared 2026-09-12): the phone number displayed on
the client's website is usually a TRACKING line that rings their real number
and powers their call reporting — that is a feature they pay for, not a bug.
If a client says the website number is "wrong" or asks to change it, your
FIRST reply explains exactly that: the displayed number forwards every call
to their real line and lets us report where their calls come from; nothing
is broken. Only if they push back AGAIN after that explanation do you
escalate to Santino for the change — never swap or promise to swap a number
yourself.
WHEN THEY ASK FOR A CALL, this is the whole reply: say you are passing it
along to Santino and ask for the best time to reach them ("Got it, I'll pass
this along to Santino right now. What's the best time to reach you?").
Never promise that Santino WILL call (Santino 2026-08-18: Monica kept
committing him to calls he never agreed to; only Santino commits Santino).
Never a specific time, never yourself, never "we'll call". Passing it along
is true: he is pinged the same second.
Offering a call is fine when nobody is committed to placing it ("we can hop
on a quick 15 minute call and do it together" is the sanctioned domain-access
line, and "Santino CAN hop on a quick call" is an offer) — but any "will
call you", whoever is named, is a promise nobody made.
FACTS ABOUT SANTINO you may state, and the ONLY ones: he is based in
California (West Coast, Pacific time). NEVER infer or state his location,
timezone, or travel from a phone number's area code — his cell carries a
Hawaii area code and he is NOT in Hawaii (live failure 2026-08-19: told Fran
"he's based in Hawaii" and Fran caught the contradiction). When his location
does not matter to the message, leave it out entirely.
LIST REMOVALS / OPT-OUTS — HARD RULE (Santino 2026-09-09, live failure:
Roy at RestorationXpress asked to remove a customer from the review texts,
Monica said "Got it, pulling Barbara off the list now", nothing removed her,
and the customer got texted again a week later). The system removes people
automatically the moment the request lands, IF it can identify them. You may
say a removal is done ONLY when a directive in your context explicitly says
it is done and verified. Without that directive you must NOT say "done",
"removed", "pulling them off", "she won't get any more texts", or anything
that sounds like the removal happened. Instead: ask for the person's full
name and mobile number in one short line and say you are flagging it right
now. Never guess which person a first name refers to."""

# The other half of "say only true things" (Santino 2026-08-05, Reign): do
# not contradict yourself. Single-sourced into every drafting prompt beside
# the capability contract.
CONSISTENCY_RULE = """\
NEVER CONTRADICT WHAT WE ALREADY TOLD THEM (Santino 2026-08-05, live on
Reign Restoration: at 15:54 Monica wrote "the van logos are already matched
to your real logo on the staging preview", and at 15:55 she wrote "we'll get
the vehicle logos matched up" — the same finished work, promised as if it had
not started). Before writing, read the last few messages in the thread and
the WORK ALREADY DONE block:
- Once we have told them something is done, it stays done. Never re-promise
  it as future work.
- If the ledger shows the work shipped, speak about it in the present or past
  tense, or do not mention it. "We'll get that fixed" about work that landed
  an hour ago is a lie.
- If our own last message already answered this exact client message, there
  is nothing to send. Return an empty body rather than a second take.
- Internal build-queue cards ([DEV], [TODO-...]) are OUR paperwork, never a
  promise to the client and never a reason to say we are "going to" do
  something."""

# A client asking for a phone call. Every path treats this as needs_santino:
# nothing in this system can dial a phone, so a human has to.
_CALL_REQUEST_RE = re.compile(
    r"\bcall me\b|\bgive me a (?:call|ring|buzz)\b|\bgimme a call\b"
    r"|\bcan (?:you|we|i) (?:please )?(?:give me a call|call me|talk|"
    r"hop on a (?:quick )?call|jump on a call|get on the phone)\b"
    r"|\b(?:let'?s|lets|wanna|want to|need to|would like to) (?:talk|"
    r"hop on a (?:quick )?call|jump on a call|get on the phone|"
    r"speak on the phone)\b"
    r"|\bwhen can (?:you|we) (?:talk|call)\b"
    r"|\bare you (?:free|available) (?:to talk|for a call)\b"
    r"|\bgot a (?:minute|second|sec) to talk\b"
    r"|\bwhat'?s a good time to (?:talk|call)\b"
    r"|\bcall (?:my|the) (?:cell|office|shop)\b", re.I)


def client_asked_for_a_call(text: str | None) -> bool:
    """True when the client is asking for a PHONE CALL. By definition a
    needs_santino event — no code path in this repo can dial a phone."""
    return bool(_CALL_REQUEST_RE.search(text or ""))


# The truthful answer to a call request. Promises only what Monica can
# actually do (pass it along), asks for the window (so Santino can pick a
# good time IF he calls), commits nobody's clock. Escalated to Santino
# wherever it is substituted, so "passing it along" is literally true the
# same second it is said. REWORDED 2026-08-18 (was "Santino will give you a
# call"): Monica kept committing Santino to calls he never agreed to (Tony
# Mendez 08-17); he ruled she passes along, she never speaks for his clock.
CALL_HANDOFF_REPLY = ("Got it, I'll pass this along to Santino right now. "
                      "What's the best time to reach you?")

_TIME_EXPR = (r"(?:at \d{1,2}(?::\d{2})?\s?(?:am|pm|a\.m\.|p\.m\.)?"
              r"|by \d{1,2}(?::\d{2})?\s?(?:am|pm)"
              r"|this (?:morning|afternoon|evening)|right now|in a bit"
              r"|first thing|in (?:an hour|a few minutes|\d+ minutes)"
              r"|tonight|later today)")

_DEADLINE_EXPR = (r"(?:by (?:the )?end of (?:the )?day|by eod\b|by cob\b"
                  r"|by tonight|by tomorrow|by (?:this )?(?:morning|afternoon|"
                  r"evening)|within the hour|in the next (?:hour|30 minutes|"
                  r"few minutes)|in an hour|first thing (?:tomorrow|in the "
                  r"morning)|tomorrow morning|by (?:monday|tuesday|wednesday|"
                  r"thursday|friday|saturday|sunday)|by \d{1,2}(?::\d{2})?\s?"
                  r"(?:am|pm)|by noon)")

# (pattern, why). Until 2026-08-18 a third human_exempt flag let any sentence
# naming Santino pass the call patterns ("Santino will give you a call" was
# the sanctioned rewrite). Santino reversed that after Monica kept committing
# him to calls he never agreed to (Tony Mendez 08-17): naming a human no
# longer sanctions a promise. Offers ("Santino can hop on a quick call") stay
# legal; the definite future does not, whoever is named.
_CAPABILITY_CLAIMS: tuple[tuple[re.Pattern, str], ...] = (
    # THE TONY CASE. First person singular + any call verb, with or without a
    # modal: an OFFER is as false as a promise, she can never be on a call.
    (re.compile(r"\bi\b\s*(?:'?ll|'?m|\s?will|\s?can|\s?could|\s?would|"
                r"\s?shall|\s?may|\s?am going to|'?m going to|\s?wanted to|"
                r"\s?would love to|\s?am happy to|'?d be happy to)?\s*"
                r"(?:just |quickly |go ahead and |also )?"
                r"(?:give (?:you|him|her|them|ya) a (?:call|ring|buzz|shout)|"
                r"call (?:you|him|her|them|ya)\b|ring (?:you|him|her|them)\b|"
                r"phone (?:you|him|her|them)\b|"
                r"hop on (?:a |the |our )?(?:quick |short )?"
                r"(?:call|phone|zoom)|"
                r"jump on (?:a |the )?(?:quick |short )?(?:call|phone|zoom)|"
                r"get on (?:a |the )?(?:quick )?(?:call|phone)|"
                r"reach out by phone|dial you)", re.I),
     "promises Monica will personally be on a phone call"),
    # "let me give you a call" / "let me hop on a call"
    (re.compile(r"\blet me\s+(?:just |quickly )?"
                r"(?:give (?:you|him|her) a (?:call|ring|buzz)|"
                r"call (?:you|him|her)\b|ring you\b|"
                r"hop on (?:a |the )?(?:quick )?(?:call|phone|zoom)|"
                r"jump on (?:a |the )?(?:quick )?call|"
                r"get (?:you )?on the phone|grab you on the phone)", re.I),
     "offers a phone call Monica cannot place"),
    # Inviting an INBOUND call — she cannot receive one either. The concierge
    # number is an SMS sender; a client who dials it reaches nobody.
    (re.compile(r"\b(?:give (?:me|us) a (?:call|ring|buzz)|"
                r"call (?:me|us) (?:at|on|back|any ?time|directly|whenever|"
                r"when |if )|(?:feel free to|you can|happy for you to) "
                r"call (?:me|us)|call my (?:cell|phone|line|number)|"
                r"reach me (?:at|by phone|on my cell))", re.I),
     "invites the client to phone Monica, who has no line to answer"),
    # Team call COMMITMENT with nobody named to place it. Offers stay legal on
    # purpose ("we can hop on a quick 15 minute call and do it together" is
    # Santino's own domain-access copy) — only the definite future is a
    # promise somebody has to keep.
    (re.compile(r"\bwe\s*(?:'?ll|\s?will|\s?are going to|'?re going to)\s*"
                r"(?:just |go ahead and )?"
                r"(?:give (?:you|him|her|them) a (?:call|ring|buzz)|"
                r"call (?:you|him|her|them)\b|ring (?:you|him|her|them)\b|"
                r"phone (?:you|him|her|them)\b|"
                r"hop on (?:a |the )?(?:quick |short )?(?:call|phone|zoom)|"
                r"jump on (?:a |the )?(?:quick )?call|"
                r"get on (?:a |the )?(?:quick )?(?:call|phone)|"
                r"get you on the phone)", re.I),
     "commits the team to placing a phone call"),
    # Booking a NEW meeting IN PROSE. Since 2026-09-12 the booking FLOW can
    # create appointments (handle_booking_request: real free slots, calendar
    # write first, code-generated confirm) — but Monica's own drafted text
    # still never promises or performs a booking; that promise is only true
    # when the flow's POST succeeded, and drafts run before any POST.
    (re.compile(r"\b(?:i|we)\s*(?:'?ll|\s?will|'?m going to|'?re going to|"
                r"\s?can|\s?could)\s*(?:just |go ahead and )?[^.!?]{0,30}?"
                r"\b(?:on (?:the|his|her|santino'?s) calendar|on the books|"
                r"send (?:you )?(?:a |an )?(?:calendar )?invite|"
                r"put (?:you|it|that) (?:down|in) for)", re.I),
     "claims we will book a meeting in prose; only the booking flow may "
     "create appointments (and it confirms after the write, never before)"),
    # THE FRAN CASE (2026-09-10): confirming a SPECIFIC meeting time in a
    # drafted reply ("11am tomorrow works", "you're all set for Tuesday")
    # with no appointment behind it. Drafts may never confirm times — the
    # booking flow's code-generated confirm (sent only after the calendar
    # POST returns an id) is the single sanctioned source of that sentence.
    # Referencing an EXISTING appointment stays legal via the phrasing the
    # compose prompt mandates ("your call is on the calendar for ..."),
    # which this pattern deliberately does not match.
    (re.compile(r"(?![^.!?]*\bmoved to\b)"  # reschedule flow's own confirm shape stays legal (selfcheck 2e)
                r"(?=[^.!?]*\b(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)|"
                r"(?:mon|tues|wednes|thurs|fri|satur|sun)day|tomorrow)\b)"
                r"[^.!?]*\b(?:works(?: great| perfectly)?(?: for "
                r"(?:us|him|santino|me))?[.!\s]|(?:you'?re|we'?re|it'?s) "
                r"(?:all )?set\b|confirmed\b|booked\b|locked in\b|"
                r"see you (?:then|at)\b)", re.I),
     "confirms a specific meeting time in a drafted reply with no "
     "appointment behind it (Fran case); only the booking flow's "
     "post-write confirm may say this"),
    (re.compile(r"\b(?:i|we)\s*(?:'?ll|\s?will|'?m going to|'?re going to|"
                r"\s?can)\s*(?:just |go ahead and )?(?:book|schedule)\b"
                r"[^.!?]{0,25}\b(?:call|meeting|time|appointment|zoom)\b",
                re.I),
     "claims we will book a new meeting; nothing in the concierge can create "
     "one"),
    # Promising Santino's clock, timed or not. THE TONY MENDEZ CASE
    # (2026-08-18): "Got it, Santino will give you a call" was the sanctioned
    # canned reply until Monica kept volunteering him for calls he never
    # agreed to. Now ANY definite-future call attributed to him is blocked;
    # the honest move is the pass-along (CALL_HANDOFF_REPLY). "Can/could"
    # offers still pass: an offer commits nobody.
    (re.compile(r"\b(?:santino|he|the boss)\b[^.!?]{0,40}?"
                r"\b(?:will|'?ll|is going to|is gonna)\b[^.!?]{0,30}?"
                r"\b(?:call|ring|phone|dial|"
                r"give (?:you|him|her|them) a (?:call|ring|buzz)|"
                r"get on the phone|hop on (?:a |the )?(?:quick )?"
                r"(?:call|zoom|phone)|reach out by phone|be calling)\b",
                re.I),
     "promises a phone call from Santino; only Santino commits his own "
     "clock (2026-08-18)"),
    # Same promise, Monica as the arranger: "I'll have Santino call you."
    # Definite future only — "want me to find a time with Santino?" and
    # "I can ask Santino" stay legal, they commit nobody.
    (re.compile(r"\b(?:i|we)\s*(?:'?ll|\s?will|'?m going to|'?re going to)\s*"
                r"(?:just |go ahead and )?(?:have|get|ask|tell)\s+"
                r"(?:santino|him|the boss)\s+(?:to\s+)?"
                r"(?:call|ring|phone|dial|give (?:you|him|her|them) a "
                r"(?:call|ring|buzz)|hop on (?:a |the )?(?:quick )?call)",
                re.I),
     "volunteers Santino for a phone call; only Santino commits his own "
     "clock (2026-08-18)"),
    # Promising when a human will be available, with a clock attached.
    (re.compile(r"\b(?:santino|he|the boss)\b[^.!?]{0,30}?"
                r"\b(?:will|'?ll|is going to|is)\b[^.!?]{0,25}?"
                r"\b(?:reach out|be available|be free)\b"
                r"[^.!?]{0,25}?" + _TIME_EXPR, re.I),
     "commits a specific human's clock; we cannot promise when Santino is "
     "free"),
    # Deadlines no scheduled system action will honor. Vague forward language
    # ("shortly", "soon", "we're on it") stays legal on purpose.
    (re.compile(r"\b(?:i|we)\s*(?:'?ll|\s?will|'?m going to|'?re going to)\s+"
                r"[^.!?]{0,60}?" + _DEADLINE_EXPR, re.I),
     "commits to a clock deadline no scheduled system action will honor"),
    # Physical presence.
    (re.compile(r"\b(?:i|we)\s*(?:'?ll|\s?will|'?m going to|'?re going to|"
                r"\s?can|\s?could)\s*(?:just )?"
                r"(?:stop by|swing by|come by|come out|drop by|be there|"
                r"head over|meet you (?:at|there|in person))", re.I),
     "promises a physical visit; Monica exists only in a text thread"),
    # Sign-offs that put her on the call or in the room. "Talk soon" (vague,
    # means "we'll be in touch") stays legal; "talk to you then" does not.
    (re.compile(r"\b(?:talk|speak|chat) (?:to|with) you (?:then|tomorrow|"
                r"(?:on )?\w+day|at \d)|\bsee you (?:then|there|tomorrow|"
                r"(?:on )?\w+day|at \d{1,2})", re.I),
     "signs off as though Monica will be on the call or in the room"),
    # Logging into the client's accounts ourselves (registrar half lives in
    # false_registrar_claim).
    (re.compile(r"\b(?:i|we)\s*(?:'?ll|\s?will|\s?can|'?m going to|"
                r"'?re going to)\s*(?:just |go ahead and )?"
                r"(?:log|sign) ?(?:in|into|in to)\b[^.!?]{0,25}"
                r"\b(?:your|their|his|her)\b", re.I),
     "claims we will sign into the client's own account"),
)


def capability_violation(body: str) -> str | None:
    """Refusal reason when `body` commits Monica to an action outside the
    capability contract above — a phone call, a new booking, a visit, a
    human's clock, a hard deadline, logging into their accounts — else None.

    Naming a human sanctions NOTHING (Santino 2026-08-18, reversing the
    08-05 design): "Santino will give you a call" is exactly the promise he
    banned. The sanctioned rewrite is the pass-along (CALL_HANDOFF_REPLY)."""
    vv = video_verification_call_offer(body or "")
    if vv:
        return f"capability violation — {vv}"
    for sent in re.split(r"(?<=[.!?])\s+", body or ""):
        for rx, why in _CAPABILITY_CLAIMS:
            m = rx.search(sent)
            if m:
                return (f"capability violation — {why} "
                        f"({m.group(0).strip()[:60]!r}). Monica can only text "
                        "and email: say you'll pass it along to Santino and "
                        "ask for their best window: "
                        f"{sent[:90]!r}")
    return None


def honest_substitute(reason: str | None, client_msg: str | None) -> str | None:
    """The TRUE message to send instead of a blocked one, or None when there
    is no safe canned answer and the send must simply be refused.

    Only the call class has one: a named human calls, and we ask for the
    window. Every caller that substitutes it ALSO escalates to Santino — the
    text is only true because a person is told the same second (2026-08-05)."""
    if not reason or "capability violation" not in reason:
        return None
    if client_asked_for_a_call(client_msg) or "phone call" in reason:
        return CALL_HANDOFF_REPLY
    return None


def escalate_call_request(company: dict, msg: dict | None,
                          client_msg: str | None, dry_run: bool) -> None:
    """A client asked for a call: text Santino NOW. This is the half that
    makes CALL_HANDOFF_REPLY true — Monica says she is passing it along,
    and this is the passing along. ping=True by policy: whether and when to
    call is HIS decision (2026-08-18: she never commits him to calling)."""
    append_escalation(
        company, msg,
        "CALL REQUESTED — Monica has no phone. She told them she's passing "
        "it along to you and asked for their best window. She did NOT "
        "promise a call; calling (or texting back) is your call: "
        f"{str(client_msg or '')[:120]!r}",
        dry_run, ping=True)


_VERIF_VIDEO_RE = re.compile(
    r"\b(?:video verification|verification video|verification walkthrough|"
    r"verify (?:the |your )?(?:listing|profile)[^.!?]{0,30}video)\b", re.I)
_CALL_OFFER_RE = re.compile(
    r"\b(?:hop on|jump on|get on|quick call|video call|zoom|"
    r"walk(?:s|ing)? you through|knock (?:it|this|that|both) out together|"
    r"do it together|while (?:we|i) (?:watch|guide))\b", re.I)
_BEFORE_FILM_RE = re.compile(
    r"\bbefore (?:you|they) (?:film|record|start)\b", re.I)


def video_verification_call_offer(body: str) -> str | None:
    """MESSAGE-LEVEL ban (Santino 2026-08-20): never offer a call/Zoom/live
    walkthrough for Google VIDEO verification — the client cannot film and be
    on a call at once, and our voices would bleed into the recording. A call
    offered explicitly for questions BEFORE filming is fine. Message-level
    because the real incident split the offer across two sentences
    ("...verification video walkthrough knocked out? Santino can hop on a
    quick 15 minute call...")."""
    text = body or ""
    if not _VERIF_VIDEO_RE.search(text):
        return None
    if _CALL_OFFER_RE.search(text) and not _BEFORE_FILM_RE.search(text):
        return ("video-verification call offer — filming is a SOLO task; "
                "send the checklist and offer questions BEFORE filming, "
                "never live help (Santino 2026-08-20)")
    return None


def unlinked_preview_invite(body: str) -> str | None:
    """A message that mentions the client's website/preview MUST carry a full
    URL in the same message — Jimmy / California Restoration West 2026-08-28:
    the instant inbound reply wrote "take a look at your new website preview"
    two days into the build, with no link and nothing review-ready. The
    composer's prompt rules could not save a path that freeforms; this makes
    the class mechanically unsendable from EVERY path. (The 5-day soak is
    enforced where preview links get released into context, so a linkless
    mention has no legitimate form.)"""
    if _PREVIEW_ASK_RE.search(body) and not re.search(r"https?://\S+", body):
        return ("mentions the website preview without a URL — either the "
                "verified preview link is in the message or the preview is "
                "not mentioned at all")
    return None


_UPLOAD_VERB_RE = re.compile(
    r"\b(upload|send (it|the file|your logo|the logo|the list|photos?)|"
    r"drop (it|the file)|attach)\b", re.I)


def upload_to_preview_link(body: str) -> str | None:
    """An upload instruction must never point at a *.pages.dev site URL —
    Rob Carpenter / TDI 2026-08-31: Monica worked a logo ask whose rationale
    hard-coded the hub upload link and still told Rob to 'upload it here:
    https://rankai-tdi-builders.pages.dev'. Nothing in our stack accepts
    uploads on pages.dev, so the pairing has no legitimate form; the upload
    destinations are restorationai.io hub/logo/photo pages."""
    if _UPLOAD_VERB_RE.search(body) and re.search(r"https?://\S*pages\.dev", body, re.I):
        return ("pairs an upload instruction with a pages.dev site link — "
                "uploads only ever go to a restorationai.io hub/upload link; "
                "use the exact link from the ask, or drop the upload ask")
    return None


def outbound_guard(body: str, evidence: str | None) -> str | None:
    """Every mechanical refusal an outbound must survive, in one call so no
    send path can quietly miss one. Returns the first violation, else None.

    Callers with no ledger context (inline replies, acks) pass evidence=None;
    the persona, registrar and capability guards need no context at all —
    those claims are wrong regardless of what the ledger says."""
    return (unsupported_done_claim(body, evidence)
            or persona_attendance_claim(body)
            or false_registrar_claim(body)
            or capability_violation(body)
            or unlinked_preview_invite(body)
            or upload_to_preview_link(body))


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


def _as_utc(val) -> datetime | None:
    """Coerce an ISO string / datetime into an aware UTC datetime, or None."""
    if val is None:
        return None
    if isinstance(val, str):
        try:
            val = datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(val, datetime):
        return None
    return val if val.tzinfo else val.replace(tzinfo=timezone.utc)


def business_hours_check(company: dict, contact: dict | None = None,
                         *, reply_to=None) -> str | None:
    """Refusal reason for sending RIGHT NOW, or None if a send is allowed.

    `reply_to` is the timestamp (datetime or ISO string) of the CLIENT message
    this send answers — pass it on every reply path and leave it None for
    unprompted outreach. It unlocks the shoulder hours; see the window map at
    QUIET_HOUR_START. Nudges are unaffected: without reply_to this is exactly
    the old 9-18 gate."""
    tz_key, source = resolve_timezone(company, contact)
    now = datetime.now(timezone.utc)
    local = now.astimezone(ZoneInfo(tz_key))
    hour = local.hour
    where = f"local now {local.strftime('%H:%M')}, tz via {source}"

    # QUIET HOURS — the hard floor, checked first so nothing can argue past it.
    if hour >= QUIET_HOUR_START or hour < QUIET_HOUR_END:
        return (f"quiet hours — nothing goes out between {QUIET_HOUR_START}:00 "
                f"and {QUIET_HOUR_END:02d}:00 {tz_key}, not even a reply "
                f"({where})")
    if BUSINESS_HOUR_START <= hour < BUSINESS_HOUR_END:
        return None                      # normal window: anything may go

    # Shoulder hours (07-09, 18-21). Unprompted outreach always waits.
    at = _as_utc(reply_to)
    if at is None:
        return (f"outside business hours — will send after "
                f"{BUSINESS_HOUR_START}am {tz_key} ({where})")
    age_min = (now - at).total_seconds() / 60
    if age_min <= FAST_REPLY_MINUTES:
        return None                      # they just texted; answering is fine
    if hour >= BUSINESS_HOUR_END:
        return None                      # evening: a SHORT ack is still fine
    return (f"outside business hours — their message is {age_min:.0f} min old, "
            f"past the {FAST_REPLY_MINUTES}-minute fast-reply window, and the "
            f"morning shoulder carries no ack extension; will send after "
            f"{BUSINESS_HOUR_START}am {tz_key} ({where})")


def evening_ack_only(company: dict, contact: dict | None = None,
                     *, reply_to=None) -> bool:
    """True when the ONLY thing that may go out right now is a short
    acknowledgment: the 18:00-21:00 shoulder, answering a client message that
    is already past the fast-reply window. The draft paths turn this into a
    hard brevity + no-asks instruction (Santino 2026-08-04: "a simple
    acknowledgement would have been okay")."""
    tz_key, _src = resolve_timezone(company, contact)
    hour = datetime.now(timezone.utc).astimezone(ZoneInfo(tz_key)).hour
    if not (BUSINESS_HOUR_END <= hour < QUIET_HOUR_START):
        return False
    at = _as_utc(reply_to)
    if at is None:
        return False
    age_min = (datetime.now(timezone.utc) - at).total_seconds() / 60
    return age_min > FAST_REPLY_MINUTES


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
        # key == company id: a client whose meeting was mined before its
        # slug existed (fathom_sync keys that intel by company id, Katofsky
        # / RestoPros 2026-09-29)
        hit = ((slug and key == slug)
               or (cid and key.lower() == cid)
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
        # WORK QUEUE IS NOT AN INSTRUCTION (Santino 2026-08-05, Reign): a
        # [DEV] client-feedback card is a task on OUR build queue, filed by
        # the classifier seconds earlier. Riding into compose as a "current
        # instruction from Santino" is how "we'll get the vehicle logos
        # matched up" got texted to a client one minute after we had told him
        # the same logos were already matched. These notes stay in context —
        # Monica should know the work exists — but in their own block that
        # forbids speaking them forward as a promise.
        queue_tags = ("[DEV]", "[DEV-PROPOSED]", "[TODO-PROPOSED]",
                      "[TODO-SANTINO]", "[TODO-", "[FEEDBACK", "[BUG",
                      "[FLAG")
        instructions = [n for n in notes
                        if not str(n.get("body", "")).lstrip().startswith(queue_tags)]
        queued = [n for n in notes if n not in instructions]
        if instructions:
            lines = "\n".join(
                f"- ({(n.get('created_at') or '')[:10]}) {n.get('body', '').strip()}"
                for n in instructions)
            parts.append("[OPS NOTES from Santino — treat as current instructions, "
                         "they override older meeting intel]\n" + lines)
        if queued:
            lines = "\n".join(
                f"- ({(n.get('created_at') or '')[:16]}) "
                f"{str(n.get('body', '')).strip()[:200]}"
                for n in queued)
            parts.append(
                "[INTERNAL WORK QUEUE — build tasks already filed on OUR "
                "side. They are context, never instructions and never "
                "promises. NEVER tell the client we are 'going to' do one of "
                "these: they are already queued or already shipped. If the "
                "WORK ALREADY DONE block below shows the work landed, speak "
                "about it as DONE. Otherwise say nothing about it and nothing "
                "about timing]\n" + lines)
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
                "[WORK ALREADY DONE — recent ledger + resolved notes. These "
                "are FINISHED. If an outstanding item asks the client for "
                "something these lines show we already have or did, EXCLUDE "
                "that item (report it in intel_resolved) instead of asking. "
                "And if the client raises one of these, it is DONE: say so "
                "in the present or past tense. NEVER promise it as future "
                "work ('we'll get that matched up' about something shipped "
                "an hour ago is a lie that makes finished work look "
                "untouched — Reign, 2026-08-05)]\n" + "\n".join(lines))
    except Exception as e:
        print(f"  [intel] work-done fetch failed: {e}", file=sys.stderr)
    # RENAME KNOWLEDGE EVERYWHERE (Santino 2026-09-29, Michael/Katofsky): the
    # rename options went out as a plain scheduled text, the rename flow was
    # never armed, and Monica answered "why do I need a DBA?" with "checking
    # with Santino" twice and dropped plumbing on the first objection.
    # RENAME_TRUTH used to ride ONLY inside an armed rename conversation; now
    # it rides into every compose/reply whenever a rename is in play.
    try:
        if _rename_in_play(company):
            parts.append("[RENAME KNOWLEDGE — answer rename/DBA/plumbing "
                         "questions from this; never defer them to Santino]\n"
                         + RENAME_TRUTH + "\n" + RENAME_PLUMBING_PUSHBACK)
    except Exception as e:  # noqa: BLE001 — knowledge is best-effort
        print(f"  [intel] rename knowledge skipped: {e}", file=sys.stderr)
    return "\n\n".join(parts) or None


def _rename_in_play(company: dict) -> bool:
    """A rename is in play when a name is seeded/chosen, the rename flow is
    armed, or rename_intent exists."""
    cid = company.get("id")
    if not cid:
        return False
    ints = company.get("integration_settings") or {}
    if ints.get("rename_intent"):
        return True
    if kv_get(f"rename-convo:{cid}"):
        return True
    rows = _sb("GET", "/rest/v1/marketing_gbp_suggestions"
               f"?company_id=eq.{cid}&item_type=eq.name"
               "&status=in.(open,chosen)&select=item&limit=1") or []
    return bool(rows)


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
              "archived", "suspended"):
        return f"account status is '{st}' — concierge muted for this company"
    return None


# ---------------------------------------------------------------------------
# SUSPENSION DUNNING (Santino 2026-08-23, Coastal never added a payment
# method): status='Suspended' means the account owes us a payment method.
# Suspended is NOT muted — Monica runs a warm human ladder instead of the
# normal nurture (normal compose skips Suspended; see cmd_compose). State
# lives in companies.integration_settings.suspension.dunning so it survives
# every process. Timeline (days since suspended_at):
#   0   friendly heads-up SMS         3   reminder ("avoid disruptions")
#   7   honest pause date             10  [SUSPENSION] card — Santino calls
#   14  marketing work marked paused  30  SITE COMES DOWN AUTOMATICALLY
# Day 30 is explicitly authorized to run WITHOUT approval (Santino
# 2026-08-23: "At day 30, the site can come down without our approval").
# ---------------------------------------------------------------------------

SUSPENSION_BILLING_LINK = "https://app.restorationai.io/settings/billing"

def _suspension_messages(first: str, pause_date: str) -> list[tuple[str, int, str]]:
    """(step_key, due_day, body) — human tone, never robotic, no em dashes."""
    return [
        ("d0", 0,
         f"Hey {first}, it's Monica with Santino's team. Quick heads up, the "
         f"payment method on your account isn't going through. Everything is "
         f"still running on our end. You can update it here: "
         f"{SUSPENSION_BILLING_LINK} . If something changed with the card, "
         f"just reply here and we'll get it sorted."),
        ("d3", 3,
         f"Hey {first}, just circling back on the payment method. When you "
         f"get a minute, updating it here keeps everything running without "
         f"any disruptions to your site, ads, and campaigns: "
         f"{SUSPENSION_BILLING_LINK}"),
        ("d7", 7,
         f"Hey {first}, I want to be straight with you so nothing here is a "
         f"surprise. If we can't get the payment method sorted by "
         f"{pause_date}, we'll have to pause the marketing work. Your "
         f"website stays up. The update takes about a minute: "
         f"{SUSPENSION_BILLING_LINK} . If anything is going on, reply here "
         f"and we'll figure it out together."),
    ]


def suspension_dunning(state: dict, dry_run: bool = False) -> int:
    """Run the suspension ladder for every Suspended company. Returns the
    number of actions taken. Rides every compose --all slot; per-step stamps
    in integration_settings.suspension.dunning make it idempotent, and a
    48h spacing guard stops step pile-ups when a suspension is discovered
    late (day 5 gets d0 today, d3 two days later, never both in one day)."""
    try:
        rows = _sb("GET", "/rest/v1/companies?status=eq.Suspended"
                   "&select=id,name,timezone,phone,email,account_owner_name,"
                   "status,integration_settings") or []
    except Exception as e:  # noqa: BLE001
        print(f"  [suspension] fetch failed: {str(e)[:120]}")
        return 0
    actions = 0
    now = datetime.now(timezone.utc)
    for company in rows:
        cid = company.get("id")
        integ = company.get("integration_settings") or {}
        susp = integ.get("suspension") or {}
        started = _as_utc(susp.get("suspended_at"))
        if not cid or not started:
            continue
        age_days = int((now - started).total_seconds() // 86400)
        dn = dict(susp.get("dunning") or {})
        changed = False
        name = company.get("name", cid)

        # --- message steps (one per slot max, 48h apart) -------------------
        contact = resolve_contact(company)
        first = contact_first_name(contact, company) if contact else "there"
        pause_date = (started + timedelta(days=14)).strftime("%B %d").replace(" 0", " ")
        last_send = _as_utc(dn.get("last_send_at"))
        spacing_ok = not last_send or (now - last_send) >= timedelta(hours=48)
        for key, due_day, body in _suspension_messages(first, pause_date):
            if age_days < due_day or dn.get(f"{key}_sent_at"):
                continue
            if not contact:
                if not dn.get("no_contact_card"):
                    _suspension_card(cid, f"[SUSPENSION] {name}: payment "
                                     "ladder cannot run, no reachable contact "
                                     "on file. Needs a human touch.", dry_run)
                    dn["no_contact_card"] = now.isoformat(); changed = True
                break
            if not spacing_ok:
                break
            hours_block = business_hours_check(company, contact)
            if hours_block:
                print(f"  [suspension] {name}: step {key} due, holding "
                      f"({hours_block})")
                break
            channel = "email" if _sms_dnd(contact) else "sms"
            if dry_run:
                print(f"  [suspension] DRY {name}: would send {key} via "
                      f"{channel}: {body[:80]}…")
            else:
                try:
                    send_message(contact, channel, body, company=company,
                                 subject=("Your Restoration AI account"
                                          if channel == "email" else None))
                    print(f"  [suspension] {name}: sent {key} via {channel}")
                except Exception as e:  # noqa: BLE001
                    print(f"  [suspension] {name}: {key} send failed: "
                          f"{str(e)[:120]}")
                    break
            dn[f"{key}_sent_at"] = now.isoformat()
            dn["last_send_at"] = now.isoformat()
            changed = True
            actions += 1
            break  # one step per slot

        # --- day 10: human escalation -------------------------------------
        if age_days >= 10 and not dn.get("escalated_at"):
            _suspension_card(cid, f"[SUSPENSION] {name}: 10 days without a "
                             "payment method after three notices. Needs a "
                             "personal call from Santino before the day-14 "
                             "work pause.", dry_run)
            dn["escalated_at"] = now.isoformat(); changed = True; actions += 1

        # --- day 14: marketing work paused --------------------------------
        if age_days >= 14 and not dn.get("work_paused_at"):
            _suspension_card(cid, f"[SUSPENSION] {name}: day 14 reached, "
                             "marketing work is now marked paused (ads, "
                             "posts, campaigns). Site stays up until day 30.",
                             dry_run)
            dn["work_paused_at"] = now.isoformat(); changed = True; actions += 1

        # --- day 30: site comes down (pre-authorized, no approval) --------
        if age_days >= 30 and not dn.get("site_down_at") \
                and not dn.get("site_down_blocked_at"):
            removed = _suspension_site_down(cid, name, dry_run)
            if removed is None:
                dn["site_down_blocked_at"] = now.isoformat()
            else:
                dn["site_down_at"] = now.isoformat()
                dn["site_down_domains"] = removed
            changed = True; actions += 1

        if changed and not dry_run:
            integ["suspension"] = {**susp, "dunning": dn}
            try:
                _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                    {"integration_settings": integ}, prefer="return=minimal")
            except Exception as e:  # noqa: BLE001
                print(f"  [suspension] {name}: state save failed: "
                      f"{str(e)[:120]}")
    return actions


def _suspension_card(company_id: str, body: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  [suspension] DRY card: {body[:100]}")
        return
    try:
        _sb("POST", "/rest/v1/marketing_ops_notes",
            {"company_id": company_id, "author": "concierge",
             "status": "open", "body": body}, prefer="return=minimal")
    except Exception as e:  # noqa: BLE001
        print(f"  [suspension] card failed: {str(e)[:100]}")


def _suspension_site_down(cid: str, name: str, dry_run: bool):
    """Detach the client's custom domain(s) from their Cloudflare Pages
    project. Returns the list of removed domains, [] if none were attached,
    or None when the takedown cannot run here (missing creds/slug/project) —
    in which case an URGENT card is filed instead. The *.pages.dev preview
    always survives; DNS zone is untouched, so restoring is re-adding the
    domain."""
    token = os.environ.get("CLOUDFLARE_R2_API_TOKEN")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    slug = company_slug(cid)
    if not (token and account and slug):
        _suspension_card(cid, f"[SUSPENSION] URGENT {name}: day 30 reached "
                         "and the automatic site takedown could not run here "
                         f"(creds={'y' if token and account else 'n'}, "
                         f"slug={'y' if slug else 'n'}). Take the site down "
                         "manually or clear the suspension.", dry_run)
        return None
    project = f"rankai-{slug}"
    base = (f"https://api.cloudflare.com/client/v4/accounts/{account}"
            f"/pages/projects/{project}/domains")
    hdrs = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(base, headers=hdrs, timeout=30)
        if r.status_code == 404:
            _suspension_card(cid, f"[SUSPENSION] {name}: day 30, no Pages "
                             f"project '{project}' found — nothing to take "
                             "down (site may never have launched).", dry_run)
            return []
        doms = [d.get("name") for d in (r.json().get("result") or [])
                if d.get("name") and not d["name"].endswith(".pages.dev")]
        if dry_run:
            print(f"  [suspension] DRY {name}: would detach {doms}")
            return doms
        removed = []
        for d in doms:
            dr = requests.delete(f"{base}/{d}", headers=hdrs, timeout=30)
            if dr.ok:
                removed.append(d)
        _suspension_card(cid, f"[SUSPENSION] {name}: day 30 reached with no "
                         f"payment method. Site domain(s) detached "
                         f"automatically per standing policy: "
                         f"{', '.join(removed) or 'none were attached'}. "
                         "Restore = re-add the domain on the Pages project "
                         "after payment.", dry_run)
        print(f"  [suspension] {name}: site down — detached {removed}")
        return removed
    except Exception as e:  # noqa: BLE001
        print(f"  [suspension] {name}: takedown error {str(e)[:120]}")
        _suspension_card(cid, f"[SUSPENSION] URGENT {name}: day-30 takedown "
                         f"errored: {str(e)[:160]}", dry_run)
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


_REVIEW_ASK_RE = re.compile(r"\breview|customer list", re.I)
_REVIEWS_OPTOUT_CACHE: dict[str, bool] = {}


def _reviews_opted_out(company_id: str) -> bool:
    """True when the client said NO review outreach (TDI/Rob 2026-09-26:
    he told Santino directly he has no list and wants no campaign, but
    nothing recorded it and Monica kept asking). Source of truth:
    integration_settings.reviews_intent.decision == "none" — set from the
    Build Stages reviews board or by hand. Cached per run; fail-open."""
    if company_id not in _REVIEWS_OPTOUT_CACHE:
        try:
            rows = _sb("GET", f"/rest/v1/companies?id=eq.{company_id}"
                       "&select=integration_settings") or []
            ints = (rows[0].get("integration_settings") if rows else {}) or {}
            if isinstance(ints, str):
                ints = json.loads(ints)
            _REVIEWS_OPTOUT_CACHE[company_id] = (
                str(((ints.get("reviews_intent") or {}).get("decision")
                     or "")).lower() == "none")
        except Exception:  # noqa: BLE001 — fail-open, never block asks
            _REVIEWS_OPTOUT_CACHE[company_id] = False
    return _REVIEWS_OPTOUT_CACHE[company_id]


def fetch_open_asks(company_id: str | None = None) -> list[dict]:
    q = ("/rest/v1/marketing_action_plan?action_type=eq.client_input"
         "&status=eq.planned"
         "&select=id,company_id,rank_ai_slug,title,rationale,priority,target"
         "&order=priority.asc")
    if company_id:
        q += f"&company_id=eq.{urllib.parse.quote(company_id)}"
    rows = _sb("GET", q) or []
    # "Client answered 'yes': …" rows are team notifications produced when a
    # gating intake answer lands — nothing to ask the client. Skip them.
    rows = [r for r in rows
            if not (r.get("title") or "").startswith("Client answered")]
    # REVIEWS OPT-OUT (2026-09-26): review-flavored asks never reach a
    # client who declined review campaigns.
    return [r for r in rows
            if not (_REVIEW_ASK_RE.search(str(r.get("title") or ""))
                    and r.get("company_id")
                    and _reviews_opted_out(r["company_id"]))]


# WORK THAT IS OURS, surfaced to Monica READ-ONLY (Santino 2026-08-08).
#
# These action types are internal: a site we can launch, an MCC invite we owe
# ourselves. They must NEVER become an ask — there is nothing to request from
# the client — but Monica being blind to them is its own failure. Go Green is
# the case: his domain resolved to nothing for two weeks while his queue was
# empty, so his state read "all caught up" when the truth was "we owe this
# client a website". Worse, with no visibility she would happily ask him for
# domain access on a domain WE ALREADY OWN.
#
# Read-only means exactly that: they inform tone and stop wrong asks, and the
# outbound guard below refuses any draft that mentions them.
INTERNAL_ACTION_TYPES = ("site_launch", "mcc_access")


def fetch_internal_work(company_id: str) -> list[dict]:
    types = ",".join(INTERNAL_ACTION_TYPES)
    q = (f"/rest/v1/marketing_action_plan?action_type=in.({types})"
         "&status=eq.planned&select=id,title,action_type,target"
         f"&company_id=eq.{urllib.parse.quote(company_id)}")
    try:
        return _sb("GET", q) or []
    except Exception:  # noqa: BLE001 — never take compose down for context
        return []


def gather_items(company_id: str) -> list[dict]:
    """Outstanding items, highest priority first.

    Ordering: blocking intake items, then plan asks by priority, then the
    remaining intake items by sort. Each entry is normalized to
    {kind: intake|plan, id, text, detail, field_type}.

    Internal work is deliberately NOT here — see fetch_internal_work.
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
                "blocks": None, "target": p.get("target") or None}

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


# A seeded ask carries TWO audiences in one row. The title is a work order for
# the ops board ("ASK CLIENT: confirm they actually offer 13 services listed on
# their Google profile"); the rationale often ends with a `MONICA:` segment
# that is the actual script — what to say, how much to raise at once, and what
# the client must NOT be made to do. Both were reaching the model, but
# lopsidedly: the title went in verbatim and in full while the rationale was
# sliced at 300 chars, which cut the script mid-sentence and dropped its
# constraints entirely. Rudy got asked to "confirm all 13 services" when the
# script beneath it said max 3, conversational, client does nothing in Google.
#
# Where a script exists it IS the instruction, and the headline is not spoken
# at all (Santino 2026-08-07).
_MONICA_SCRIPT_RE = re.compile(r"\bMONICA\s*:\s*", re.I)


def split_monica_script(rationale) -> tuple[str, str]:
    """(purpose_for_the_board, script_for_the_client). Script is "" when the
    row has no MONICA: segment, which is the common case."""
    text = str(rationale or "").strip()
    m = _MONICA_SCRIPT_RE.search(text)
    if not m:
        return text, ""
    return text[:m.start()].strip(), text[m.end():].strip()


def _clip(text: str, limit: int) -> str:
    """Truncate on a sentence boundary, else a word boundary. A script cut
    mid-word ("...do you folks handle Water damage restoration? Want t") reads
    as noise to the model and loses whatever followed."""
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    for sep in (". ", "! ", "? "):
        cut = head.rfind(sep)
        if cut > limit * 0.5:
            return head[:cut + 1]
    cut = head.rfind(" ")
    return (head[:cut] if cut > limit * 0.5 else head).rstrip() + "…"


def _domain_access_status(company_id: str) -> str:
    """Current domain_access_status from marketing_sites ('' = no site row).

    A state of delegate_granted that the AGENCY MAILBOX cannot back up is
    downgraded to 'promised' here (Santino 2026-08-05, Crew Restoration): the
    Ops Attention button used to assert an invite nobody had received, the
    state went green, and Monica stopped asking the one person who could
    unblock the launch. setup_ledger writes the verdict onto the domain-access
    ledger row (evidence.access_in_hand); a human's word alone never silences
    the ask.
    """
    try:
        rows = _sb("GET", f"/rest/v1/marketing_sites?company_id=eq.{company_id}"
                   "&select=domain_access_status&limit=1") or []
        status = str((rows[0] if rows else {}).get("domain_access_status") or "")
        if status in ("delegate_granted", "creds_provided"):
            led = _sb("GET", "/rest/v1/marketing_setup_ledger"
                      f"?company_id=eq.{company_id}&item_key=eq.domain-access"
                      "&select=evidence&limit=1") or []
            ev = (led[0] if led else {}).get("evidence") or {}
            if ev.get("access_in_hand") is False:
                print(f"  [domain-state] {company_id}: '{status}' is a human "
                      "assertion with NO registrar invite in the inbox — "
                      "treating as 'promised', the ask stays alive")
                return "promised"
        return status
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
    preview_ready_at: str | None = None
    for it in items:
        text = str(it.get("text", "")).lower()
        # (d) PREVIEW SOAK — a finished site is not shown to a brand-new client
        # the moment the build lands (Santino 2026-08-05: "I'm actually happy
        # that we didn't send them their website so quickly. I want it to feel
        # like we're spending time"). The site waits PREVIEW_SOAK_DAYS from the
        # build; every OTHER ask goes out immediately, so the days read as
        # steady progress rather than silence. The wait is also a QA window —
        # DISS's logo was broken for its whole first day.
        # Proactive ask only — a client who writes in asking about their site
        # is answered by the reply path, which never reaches this filter.
        if "preview" in text and ("site" in text or "website" in text):
            if preview_ready_at is None:
                try:
                    # STABLE ANCHOR (2026-09-20, FIX/DryCor): updated_at is
                    # bumped by every deploy — content pushes kept resetting
                    # the soak clock, holding finished sites indefinitely.
                    # scaffolded_at (first build) is immutable; staging push
                    # is the next-best; updated_at only as a last resort.
                    rows = _sb("GET", "/rest/v1/marketing_sites?company_id=eq."
                               f"{company.get('id')}&select=scaffolded_at,"
                               "last_pushed_staging_at,updated_at,build_status") or []
                    r0 = rows[0] if rows else {}
                    preview_ready_at = (r0.get("scaffolded_at")
                                        or r0.get("last_pushed_staging_at")
                                        or r0.get("updated_at") or "")
                except Exception:  # noqa: BLE001 — unknown age: show it, don't stall
                    preview_ready_at = ""
            if preview_ready_at:
                try:
                    built = datetime.fromisoformat(
                        preview_ready_at.replace("Z", "+00:00"))
                    age_d = (datetime.now(timezone.utc) - built).days
                    # FINISHING GATE (pairs with the stable anchor above):
                    # a slow build can pass day 10 with pages still
                    # rendering — the reveal waits for BOTH the clock and a
                    # finished site, exactly like setup_ledger's window.
                    unfinished: list = []
                    if age_d >= PREVIEW_SOAK_DAYS:
                        try:
                            from setup_ledger import _site_unfinished_bits
                            _srows = _sb(
                                "GET", "/rest/v1/marketing_sites?company_id="
                                f"eq.{company.get('id')}"
                                "&select=rank_ai_slug&limit=1") or []
                            _slug = str((_srows[0] if _srows else {})
                                        .get("rank_ai_slug") or "")
                            if _slug:
                                unfinished = _site_unfinished_bits(_slug)
                        except Exception:  # noqa: BLE001 — fail open (ready)
                            unfinished = []
                    if age_d < PREVIEW_SOAK_DAYS or unfinished:
                        # "share now" note override (2026-09-11, DryCor: a
                        # deploy refresh reset updated_at, so an explicitly
                        # approved reveal would have re-soaked 10 days) —
                        # mirrors setup_ledger's release valve.
                        released = False
                        try:
                            released = any(
                                re.search(r"share\s+now|release\s+early|reveal\s+now",
                                          str(n.get("body", "")), re.I)
                                for n in _sb("GET", "/rest/v1/marketing_ops_notes"
                                             f"?company_id=eq.{company.get('id')}"
                                             "&status=eq.open&select=body&limit=20",
                                             prefer="return=representation") or [])
                        except Exception:  # noqa: BLE001
                            released = False
                        if not released:
                            print(f"    [preview-soak] site is {age_d}d old"
                                  + (f", unfinished: {', '.join(unfinished)}"
                                     if unfinished else "")
                                  + f" — holding the preview until day "
                                  f"{PREVIEW_SOAK_DAYS} and finished; other "
                                  f"asks still go out")
                            continue
                        print("    [preview-soak] released by 'share now' note")
                except ValueError:
                    pass
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
        # (e) SEND-TIME REVALIDATION (2026-08-12): the ledger seeds asks from
        # derived checks and retires them the same way, but it sweeps every
        # ~4h — an ask can sit satisfied-but-open between passes (the logo
        # lands in the bucket, the NAP gets backfilled, the domain goes
        # live). ask_revalidate.ask_still_valid re-runs the EXACT check that
        # seeded the row (setup_ledger's own helpers, imported not copied):
        # False = stale -> auto-resolve with the reason and never draft it;
        # True/None (still needed / not a seed it knows) keep the item. Runs
        # LAST so the richer gates above (domain forward-note, photo
        # auto-satisfy) keep their behavior. Fail-open: a revalidation error
        # must never kill compose.
        if it.get("kind") == "plan":
            try:
                import ask_revalidate
                if ask_revalidate.ask_still_valid(company["id"], it) is False:
                    why = (it.get("_stale_reason")
                           or "the condition that seeded it is satisfied")
                    print(f"  [revalidate] {it['text'][:60]!r}: {why} — "
                          "auto-resolving, not asking")
                    ask_revalidate.resolve_stale(it["id"], why, dry_run)
                    continue
            except Exception as e:  # noqa: BLE001
                print(f"  [revalidate] check failed ({str(e)[:80]}) — "
                      "keeping the ask")
        kept.append(it)
    return kept


# ---- preview-share priority (Santino 2026-08-04) ---------------------------
# Reign Restoration's site was BUILT on 08-03 and the share ask was seeded
# correctly the same evening (setup_ledger's preview-share heal did its job) —
# but the concierge ranked "Take a look at your new website preview" into the
# catch-all bucket 5, dead last, so every compose picked the domain ask and
# then the customer list and Jerrott never once saw his own site. A client
# whose site is finished and who has NEVER seen it gets the link first: it is
# the single most valuable thing we can put in front of them.
_PREVIEW_ASK_RE = re.compile(
    r"(?:website|web ?site|site)\s+preview|preview\s+(?:of\s+)?(?:your\s+)?"
    r"(?:new\s+)?(?:website|web ?site|site)|new website preview", re.I)


def preview_link_for(company: dict, items: list[dict]) -> str | None:
    """The staging/preview URL for this client, VERIFIED before it is used.

    Candidate order: the share ask's own target (marketing_action_plan.
    target), a URL in its rationale, then marketing_sites. Each candidate is
    fetched and the first one that actually serves wins — a plan row's target
    is a snapshot from build time and goes stale when the site is rebuilt
    under a new project name (FireDEX's Bob got the dead
    rankai-firedex-butler.pages.dev, 2026-08-04). Returns None when nothing
    resolves, and boost_preview_share then keeps the link out of the draft
    entirely."""
    candidates: list[str] = []
    for it in items:
        if _PREVIEW_ASK_RE.search(str(it.get("text", ""))):
            tgt = str(it.get("target") or "").strip()
            if tgt.startswith("http"):
                candidates.append(_clean_url(tgt))
            m = re.search(r"https?://\S+", str(it.get("detail") or ""))
            if m:
                candidates.append(_clean_url(m.group(0)))
    live = live_site_url(company)
    if live:
        candidates.append(_clean_url(live))
    for url in dict.fromkeys(candidates):
        if url_alive(url):
            if candidates and url != candidates[0]:
                print(f"  [preview-share] plan-row target was dead — using "
                      f"the live URL {url}")
            return url
    if candidates:
        print("  [preview-share] every preview URL on file is dead "
              f"({', '.join(dict.fromkeys(candidates))}) — no link will be "
              "mentioned; rebuild/repair the site record")
    return None


def boost_preview_share(company: dict, items: list[dict],
                        history: list[dict] | None) -> str | None:
    """Rank the website-preview ask against the actual thread.

    Never sent the link -> _rank -1, ahead of every other ask (the client has
    not seen the thing we built for them). Already sent -> _rank 11, its normal
    slot inside the Website tier: a feedback nudge that must not keep
    outranking launch blockers. (Was 4, which after the Phase 2 renumbering
    would have placed a stale nudge ABOVE the brand-assets ask at 10.)
    Returns the preview URL when it should LEAD this message, else None."""
    share = [it for it in items if _PREVIEW_ASK_RE.search(str(it.get("text", "")))]
    if not share:
        return None
    url = preview_link_for(company, share)
    if not url:
        print("  [preview-share] share ask is open but no preview URL is on "
              "file (marketing_sites.cloudflare_pages_url empty) — leaving it "
              "at normal rank; do NOT let the draft mention a link")
        for it in share:
            it["_rank"] = 11
        return None
    # The URL may have gone out as a bare host, with or without scheme.
    host = re.sub(r"^https?://", "", url).rstrip("/").lower()
    sent = any(host in str(m.get("body") or "").lower()
               for m in (history or []) if m.get("direction") != "in")
    for it in share:
        it["_rank"] = 11 if sent else -1
        it["target"] = url
    if sent:
        print(f"  [preview-share] {url} was already sent to this client — "
              "ranked as a normal feedback nudge")
        return None
    print(f"  [preview-share] this client has NEVER been sent their site "
          f"({url}) — promoting the share ask above every other item")
    return url


# BUSINESS-PRIORITY RANK (Santino 2026-07-30: "she always works on the
# first priority item" — All Pro got a YouTube ask while their Google
# account sat unconnected). Rank classes trump source ordering; Python's
# stable sort keeps the original order within a class. Module-level so the
# same-owner merge can re-rank across companies too.
# PHASE 2 — NESTED PRIORITY FRAMEWORK (Santino 2026-08-08). The old ranking was
# a flat list of six buckets, so "domain access" and "preview confirmed" fought
# each other at the same rank instead of reading as two steps of one goal, and
# anything worded unexpectedly fell into the catch-all: 59 of ~116 open asks
# were sitting in bucket 6, including every photo, EIN and licence question.
#
# Tiers are now spaced by 10 so sub-steps sort WITHIN a tier and can be inserted
# later without renumbering. Lower wins.
#
#   0   GBP connection            nothing works without it
#   10  Website / brand assets    logo + colours FIRST: the van, uniform and
#                                 crew imagery is generated FROM them, and
#                                 regenerating a finished site is far more
#                                 expensive than waiting for a logo
#   11  Website / preview + feedback
#   12  Website / domain access
#   13  Website / PUSH IT LIVE    ours, not theirs (see INTERNAL below)
#   20  Ads / does the client want LSA
#   21  Ads / connect LSA
#   22  Ads / grant ourselves MCC access      ours
#   23  Ads / documents needed for LSA
#   24  Ads / upload those documents          ours
#   30  Reviews / customer list
#   31  Reviews / team photo
#   40  YouTube
#   50  Everything else (EIN, licence, citations, meeting-derived tasks)
#
# INTERNAL steps (13, 22, 24) are the ones that had no representation at all.
# They are why Go Green sat dark from 2026-07-24: we owned the domain, the
# client owed us nothing, and because every rank described something to ASK a
# client, "we have not launched this yet" was invisible on every board.
_INTERNAL_RE = re.compile(
    r"\b(push (the )?site live|go.?live|launch (the )?site|cut ?over|"
    r"mcc access|manager access|grant ourselves|upload (the )?(lsa )?documents)\b",
    re.I)


def ask_rank(it) -> int:
    # A dynamic override wins outright — set by boost_preview_share() once
    # the thread has been read (see there).
    if it.get("_rank") is not None:
        return int(it["_rank"])
    # Rank on the item TITLE only — details are prose and full of incidental
    # keyword matches ("sign into that Google account" on a YouTube ask).
    t = it["text"].lower()

    # --- Tier 1: the Google connection, above everything -------------------
    # "verify" belongs here too (Santino 2026-08-03): a suspended or
    # unverified profile is invisible, which is the same outcome as unconnected.
    if "google" in t and any(k in t for k in ("connect", "access", "re-engage",
                                              "verify", "suspend", "reinstat")):
        return 0

    # --- Tier 2: Website ----------------------------------------------------
    if _PREVIEW_ASK_RE.search(t):
        # SHOW THEM THE SITE (Santino 2026-08-04, Reign). boost_preview_share()
        # promotes this to -1 when the link was never actually sent: once a site
        # exists, showing it beats collecting brand assets for it.
        return 11
    if any(k in t for k in ("domain", "registrar", "godaddy", "nameserver")):
        return 12
    if _INTERNAL_RE.search(t) and any(k in t for k in ("site", "live", "launch",
                                                       "cutover", "cut over")):
        return 13
    if "logo" in t or "brand" in t:
        return 10

    # --- Tier 3: Ads / LSA --------------------------------------------------
    if "local services" in t or "lsa" in t or "google guaranteed" in t:
        if _INTERNAL_RE.search(t):
            return 22 if "access" in t else 24
        if any(k in t for k in ("document", "licence", "license", "insurance",
                                "coi", "verification")):
            return 23
        if "connect" in t or "link" in t:
            return 21
        return 20
    if _INTERNAL_RE.search(t) and ("mcc" in t or "manager access" in t):
        return 22

    # --- Tier 4: Reviews ----------------------------------------------------
    if "customer list" in t or "review campaign" in t:
        return 30
    if "team photo" in t:
        return 31

    # --- Tier 5 / 6 ---------------------------------------------------------
    if "youtube" in t:
        return 40
    return 50


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


# ------------------------------------------------------------- boss directives
# Machine-written notes that are ALWAYS a direct order to Monica:
#   [FROM SANTINO ...]  advice-loop answers texted back by Santino
#   [SEND-PREVIEW]      the app's Website Approve button
#   [FOR MONICA]        explicit "for Monica" notes filed from chat/ops
_DIRECTIVE_TAGS = ("[FROM SANTINO", "[SEND-PREVIEW]", "[FOR MONICA]")

# ...and the case that had NO tag at all (Santino 2026-08-04): the app's Ops
# Attention note composer defaults its kind dropdown to "For Monica", whose
# option value is the EMPTY STRING (OpsAttention.tsx), so a note typed there
# lands in marketing_ops_notes with a bare body. categorizeNote() files every
# untagged body under the Monica category, but has_boss_directive() only ever
# matched the literal "[FROM SANTINO" prefix — so his ProRestoration order,
# "Reach out and set a meeting up sometime tomorrow or Thursday.", was
# invisible to Monica all day and he ended up texting Angie himself at 22:23.
#
# Untagged notes are NOT all orders, though. The same box holds standing
# CONSTRAINTS ("Do NOT mention prorestorationca.com ... off-limits for client
# outreach") and pure context ("Greg provided his review campaign list
# already"). Promoting those to directives would grant that company a
# PERMANENT cooldown + human-defer bypass and Monica would text every hour
# forever. So an untagged note counts only when it reads as an ORDER TO
# CONTACT THE CLIENT: an action verb in the imperative, at the start of a
# sentence (or after "Monica:", "please", a dash — how he actually writes
# them). Everything else stays what it always was: context that rides into
# compose with the meeting intel.
_DIRECTIVE_IMPERATIVE_RE = re.compile(
    r"(?:^|[.\n!?;]\s*|\bmonica\s*[:,]\s*|\bplease\s+|\s[—–-]\s*)"
    r"(?:reach\s+(?:back\s+)?out|follow\s+up|circle\s+back|check\s+in|touch\s+base"
    r"|get\s+in\s+touch|text|call|email|message|ping|nudge|remind|ask|tell"
    r"|let\s+(?:them|him|her)\s+know|invite|offer|schedule|book|set\s+up|send"
    r"|confirm|chase|push|make\s+(?:it|this|that)\s+a\s+priority"
    r"|prioriti[sz]e|thank|congratulate|walk\s+(?:them|him|her)\s+through)\b",
    re.I)
# A note that OPENS with a prohibition is a standing constraint, never an
# order to go text someone ("Do NOT ask Jose to confirm services...").
_DIRECTIVE_PROHIBIT_RE = re.compile(
    r"^\s*(?:do\s*n['’]?o?t|don['’]t|never|no\b|hold\s+off|wait\b"
    r"|stop\b|pause\b|heads?\s*up\b|fyi\b)", re.I)
# Authors that are machines, not Santino. The column DEFAULTS to 'santino'
# (see the 20260728090000 migration), so author can only ever DISQUALIFY.
_MACHINE_AUTHORS = ("webhook", "system", "cron", "monica", "concierge")


def is_boss_directive(note: dict) -> bool:
    """Does this open ops note order Monica to contact the client now?"""
    body = str(note.get("body") or "").strip()
    if not body:
        return False
    if body.startswith(_DIRECTIVE_TAGS):
        return True
    if body.startswith("["):
        return False          # some other machine tag: [DEV], [LSA-INTENT], ...
    author = str(note.get("author") or "").strip().lower()
    if any(m in author for m in _MACHINE_AUTHORS):
        return False
    if _DIRECTIVE_PROHIBIT_RE.match(body):
        return False
    return bool(_DIRECTIVE_IMPERATIVE_RE.search(body))


def open_boss_directives(company_id: str | None) -> list[dict]:
    """Open ops notes for this company that are DIRECT orders from Santino.

    Acting on his order is not a nudge: it bypasses the cooldown, the nudge
    cap and (2026-08-04) his own 12h human-defer — see cmd_compose. Business
    hours and the canary allowlist always survive."""
    if not company_id:
        return []
    try:
        rows = _sb("GET", f"/rest/v1/marketing_ops_notes?company_id=eq.{company_id}"
                   "&status=eq.open&select=id,body,author,created_at"
                   "&order=created_at.desc&limit=20") or []
    except Exception:
        return []
    return [r for r in rows if is_boss_directive(r)]


def _companies_with_directives() -> list[str]:
    """Every company carrying an open boss directive (one query, for --all)."""
    try:
        rows = _sb("GET", "/rest/v1/marketing_ops_notes?status=eq.open"
                   "&select=company_id,body,author&limit=500") or []
    except Exception:
        return []
    return sorted({r["company_id"] for r in rows
                   if r.get("company_id") and is_boss_directive(r)})


def resolve_directives(directives: list[dict], why: str = "acted on") -> None:
    """One-shot: a directive Monica has now acted on is closed, so the
    cadence bypass it grants can't keep firing on every future compose."""
    now = datetime.now(timezone.utc).isoformat()
    for d in directives or []:
        try:
            _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{d['id']}",
                {"status": "resolved", "resolved_at": now})
            print(f"  [directive] {why} + resolved: "
                  f"{str(d.get('body', ''))[:70]!r}")
        except Exception as e:  # bookkeeping must never fail the send
            print(f"  [directive] resolve failed: {str(e)[:100]}")


def has_boss_directive(company_id: str | None) -> bool:
    """Back-compat boolean wrapper (cadence_check's boss_override)."""
    return bool(open_boss_directives(company_id))


# ------------------------------------------- Google manager-link (LSA) asks
# TWO CLIENTS IN ONE HOUR (Santino 2026-08-04). Monica asked Greg Arianoff and
# Curt Eddy to accept a Google manager invite; both replied that they already
# had, and both were right.
#   Greg's link had gone ACTIVE that evening — we asked off a stale flag,
#   because nothing ever read the link back (see scripts/lsa_link_audit.py).
#   Curt had accepted the invite for Home Pride's GOOGLE ADS account
#   (2347693633, ACTIVE since ~May). The one still pending is their separate
#   LOCAL SERVICES account (2957729882) — and the text he got said "your ads
#   account", which is exactly the one he had already accepted.
# So: check the live link before asking anyone to accept it, and when the ask
# is genuinely due, name the account and own the history.
# "approve" belongs here as much as "accept" (2026-08-05): the text Monica
# actually sent Jaziel said "have Isaac APPROVE Google's request to let us
# manage their Local Services Ads", and an accept-only pattern would not have
# recognised its own incident even once the guard could reach the truth.
_LSA_ASK_RE = re.compile(
    r"(?=.*\b(?:manager|management|mcc|access|manage)\b)"
    r"(?=.*\b(?:invite|invitation|request|link)\b)"
    r"(?=.*\b(?:accept\w*|approv\w*)\b)", re.I | re.S)
# ...and it has to be about GOOGLE. Without this clause the pattern also
# matched Crew Restoration's [DOMAIN-ACCESS-UNVERIFIED] card (registrar
# "access" + "invite" + "accept" in one note), which would have let the guard
# resolve a DOMAIN item the day their Ads link went ACTIVE — an unrelated ask
# closed by unrelated evidence. Verified 2026-08-05 against the fleet sweep.
_LSA_CONTEXT_RE = re.compile(
    r"\b(?:google|ads?|adwords|lsa|local services|gbp|business profile|mcc)\b",
    re.I)
# ...but a note CONFIRMING a link is not an ask to accept one.
_LSA_ASK_NOT_RE = re.compile(
    r"do ?n['’]?o?t ask|don['’]t ask|no need to ask|nothing else needed"
    r"|already (?:accepted|linked|active)|ask is (?:done|retired)", re.I)


def _is_lsa_ask(text) -> bool:
    t = str(text or "")
    return (bool(_LSA_ASK_RE.search(t)) and bool(_LSA_CONTEXT_RE.search(t))
            and not _LSA_ASK_NOT_RE.search(t))


def _fmt_acct(a: str) -> str:
    a = str(a or "")
    return f"{a[:3]}-{a[3:6]}-{a[6:]}" if len(a) == 10 and a.isdigit() else a


_MCC_LINKS: dict | None | bool = False   # False = not attempted yet


def _mcc_links() -> dict | None:
    """{account_id: [(link_id, status), ...]} on the agency MCC, or None.

    Fail-open by design: with no Ads credentials (CI) this returns None and
    every caller behaves exactly as it did before.
    """
    global _MCC_LINKS
    if _MCC_LINKS is not False:
        return _MCC_LINKS
    _MCC_LINKS = None
    try:
        from lsa_detect import build_mcc_client
        from lsa_link_audit import link_states
        client, mcc = build_mcc_client()
        if client:
            _MCC_LINKS = link_states(client, mcc)
    except Exception as e:
        print(f"  [lsa-link] live check unavailable ({str(e)[:70]}) — "
              "falling back to stored state")
    return _MCC_LINKS


# The link state as last WRITTEN DOWN by scripts/lsa_link_audit.py --apply,
# in connection_metadata's own vocabulary.
_STORED_TO_LINK = {"accepted": "ACTIVE", "invited": "PENDING",
                   "canceled": "CANCELED", "refused": "REFUSED",
                   "unlinked": "INACTIVE"}


def _stored_link_facts(cm: dict, target: str, is_lsa: bool) -> dict | None:
    """ACTIVE-only fallback for when the live Ads check cannot run.

    THE GUARD WAS INERT IN PRODUCTION (Santino 2026-08-05). lsa_ask_guard was
    built on 08-04 to stop exactly this and then, at 13:13 on 08-05, Monica
    asked Jaziel at RestorationXpress to accept a manager invite their office
    had already accepted the day before. The guard did not misjudge it — the
    guard never ran. It reaches the truth only through the live Google Ads
    API, and the Railway ops-worker that runs `compose --all --send` has no
    Google Ads credentials at all (no GOOGLE_ADS_MCC_CUSTOMER_ID, no
    developer token, no refresh token — verified against the service's env).
    build_mcc_client() returned (None, None) on every pass, _mcc_links()
    returned None, lsa_link_facts() returned None, and the ask sailed through
    untouched. The guard had only ever fired on Santino's Mac, where a
    client's own .ads-token.json happens to sit.

    Meanwhile the answer was already in our own database: lsa_link_audit had
    written lsa_link_status "ACTIVE" / lsa_invite_status "accepted" onto
    RestorationXpress at 00:10 that morning, thirteen hours before the text.
    _mcc_links() even prints "falling back to stored state" — a fallback that
    did not exist until this function.

    Deliberately narrow: it can only ever SILENCE an ask, never write one.
    A stored ACTIVE retires the ask outright. A stored PENDING is honoured
    only in the direction of silence — see ads_link_self_serve below —
    because writing the ask (naming the account, owning the history) needs
    the link history that only the API has.
    """
    status = (str(cm.get("lsa_link_status") or "").upper()
              or _STORED_TO_LINK.get(
                  str(cm.get("lsa_invite_status") or "").lower(), ""))
    if status not in ("ACTIVE", "PENDING"):
        return None
    return {"account": target, "is_lsa": is_lsa, "status": status,
            "link_id": cm.get("lsa_link_id"), "prior": [], "other_active": [],
            "source": "stored",
            "self_serve": cm.get("ads_link_self_serve"),
            "self_serve_reason": cm.get("ads_link_self_serve_reason"),
            "checked_at": cm.get("lsa_link_checked_at")
            or cm.get("lsa_invite_at")}


def lsa_link_facts(company: dict) -> dict | None:
    """Manager-link state for the account an invite is/was for.

    Live from the agency MCC when we can reach it, from what the last audit
    wrote down when we cannot (see _stored_link_facts)."""
    links = _mcc_links()
    rows = _sb("GET", "/rest/v1/user_integrations"
               f"?client_id=eq.{company['id']}&provider=eq.google"
               "&select=connection_metadata") or []
    cm = (rows[0].get("connection_metadata") or {}) if rows else {}
    ints = company.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except (json.JSONDecodeError, TypeError):
            ints = {}
    lsa_id = str((ints.get("lsa") or {}).get("customer_id")
                 or cm.get("lsa_customer_id") or "").replace("-", "")
    ads_id = str(cm.get("selected_ads_customer_id")
                 or cm.get("ads_customer_id") or "").replace("-", "")
    target = lsa_id or ads_id
    if links is None:
        return _stored_link_facts(cm, target, bool(lsa_id) and target == lsa_id)
    if not target:
        return None
    cur = links.get(target) or []
    other = [(ads_id, links[ads_id][-1][1],
              cm.get("selected_ads_account_name") or "their Google Ads account")
             for _ in (0,)
             if ads_id and ads_id != target and ads_id in links]
    return {"account": target,
            "is_lsa": bool(lsa_id) and target == lsa_id,
            "status": cur[-1][1] if cur else "NONE",
            "link_id": cur[-1][0] if cur else None,
            "prior": cur[:-1],
            "self_serve": cm.get("ads_link_self_serve"),
            "self_serve_reason": cm.get("ads_link_self_serve_reason"),
            "other_active": [o for o in other if o[1] == "ACTIVE"]}


def lsa_ask_guard(company: dict, items: list[dict],
                  directives: list[dict] | None, dry_run: bool):
    """Check the link BEFORE asking anyone to accept it.

    Returns (items, directives, note). The ask is dropped when the link is
    already ACTIVE (rows closed — it is done) or when no invite is actually
    outstanding (rows kept open — that one is OUR job, not theirs). When the
    ask is genuinely due, `note` tells compose exactly how to word it.
    """
    directives = directives or []
    ask_items = [i for i in items if _is_lsa_ask(i.get("text"))]
    ask_dirs = [d for d in directives if _is_lsa_ask(d.get("body"))]
    if not (ask_items or ask_dirs):
        return items, directives, None
    f = lsa_link_facts(company)
    if not f:
        return items, directives, None
    acct = _fmt_acct(f["account"])

    if f["status"] == "ACTIVE":
        src = ("live Google Ads check" if f.get("source") != "stored"
               else f"stored link state, last verified "
                    f"{str(f.get('checked_at') or '?')[:16]}")
        print(f"  [lsa-link] {acct or 'their Google account'} is already "
              f"ACTIVE ({src}) — retiring the accept ask instead of sending it")
        for it in ask_items:
            val = (f"auto-satisfied {datetime.now(timezone.utc).date()}: "
                   f"manager link ACTIVE on {acct} (link {f['link_id']}, "
                   f"{src})")
            if it.get("kind") == "intake":
                apply_answer(it["id"], val, dry_run)
            else:
                resolve_plan_row(it["id"], dry_run)
        if not dry_run:
            resolve_directives(ask_dirs, why="manager link already ACTIVE")
        return ([i for i in items if i not in ask_items],
                [d for d in directives if d not in ask_dirs], None)

    if f["status"] != "PENDING":
        print(f"  [lsa-link] nothing outstanding on {acct} "
              f"(status {f['status']}) — there is no invite for them to "
              "accept; holding the ask (we owe the invite, not them)")
        return ([i for i in items if i not in ask_items],
                [d for d in directives if d not in ask_dirs], None)

    # PENDING IS OUR JOB, NOT THEIRS (Santino 2026-08-05). A pending manager
    # link was treated as the one thing only the client could clear, and the
    # whole apology machinery below was built to ask for it politely. Tested
    # on 08-05 against the real API: a client-side ADMIN can flip
    # customer_manager_link to ACTIVE, the Google user the client granted us
    # IS that admin (every grant carries the adwords scope), and
    # scripts/ads_link_accept.py cleared six accounts — Ads and Local
    # Services alike — with nobody touching a phone. So a pending link only
    # ever justifies an ask once we have TRIED and Google refused us.
    # ads_link_self_serve is that verdict, written by the nightly pass onto
    # connection_metadata where the credential-less Railway worker can read
    # it. Unknown (never attempted) stays silent on purpose: the cost of
    # waiting one night is nothing, the cost of asking wrongly is Curt and
    # Greg and Jaziel all answering "I already did this".
    if f.get("self_serve") is not False:
        why = ("we have not tried yet — the nightly pass will"
               if f.get("self_serve") is None
               else "we can accept it ourselves and will")
        print(f"  [lsa-link] {acct} is PENDING but {why} approve it with the "
              "client's own admin grant — dropping the ask (ours to do, not "
              "theirs). scripts/ads_link_accept.py")
        return ([i for i in items if i not in ask_items],
                [d for d in directives if d not in ask_dirs], None)

    label = "Local Services Ads account" if f["is_lsa"] else "Google Ads account"
    lines = [
        "\nMANAGER-LINK ASK — NAME THE ACCOUNT (Santino 2026-08-04): the "
        f"invite is for their {label} {acct}. Say WHICH account. Two clients "
        "in one hour answered \"I already did this\" because the text just "
        "said \"your ads account\", which for one of them was a different "
        "account he really had accepted. Accepting lets us manage that "
        "account for them — one short clause on why, no more.",
    ]
    if f["other_active"]:
        a, _st, nm = f["other_active"][0]
        lines.append(
            "THEY ARE NOT MISREMEMBERING — our records show they already "
            f"accepted the invite for {nm} ({_fmt_acct(a)}). Lead with that: "
            "they did accept one, this is a second, separate account. Never "
            "imply they forgot.")
    elif any(s == "INACTIVE" for _i, s in f["prior"]):
        # INACTIVE = a link that was live and later came apart. CANCELED is
        # different: a resend WITHDRAWS the old pending invite, so a CANCELED
        # predecessor proves only that an older email went dead — never that
        # they accepted it. Do not apologise for the wrong thing.
        lines.append(
            "THEY DID ACCEPT ONE BEFORE on this same account and the link "
            "later came apart on our side. Own that first (\"you did accept "
            "one, it dropped on our end, sorry for the runaround\") and then "
            "ask.")
    elif f["prior"]:
        lines.append(
            "AN EARLIER INVITE TO THIS ACCOUNT WAS WITHDRAWN when we re-sent "
            "it, so an older Google email they may have kept no longer works "
            "— tell them to use the most recent one. Do not say they accepted "
            "before; a withdrawn invite is not proof that they did.")
    if f.get("self_serve_reason"):
        lines.append(
            "WE TRIED TO DO THIS FOR THEM AND GOOGLE REFUSED "
            f"({str(f['self_serve_reason'])[:120]}), which is the only reason "
            "this ask exists. Do not imply they have been sitting on it.")
    return items, directives, "\n".join(lines) + "\n"


# ------------------------------------------- Google Business Profile access
# THE SECOND HALF OF THE SAME RULE (Santino 2026-08-05): "asking a client for
# things we already have access to is a big no-no." On 08-05 directives went
# out asking ProRestoration's and PuroClean's owners to add
# contact@restorationai.io as a GBP manager, worded "we can't get on their
# Google listing". That wording was false. We are ON both listings — the
# audit that morning shows our grant holding MANAGER on each — and Monica had
# been posting to them for weeks. What is actually missing is narrower: the
# AGENCY account's own manager seat, which only Bing's and Apple's GBP import
# need. An ask that overstates what we lack is still an ask for access we
# already hold.
#
# So this guard reads the same ground truth gbp_admin_invite.py writes to
# ops_kv 'gbp-manager-access' (Supabase — so the credential-less Railway
# worker sees it too) and allows exactly one case through:
#
#   manager         we hold the seat            -> RETIRE the ask
#   none / pending  the API can still get it    -> DROP it (ours to do)
#   owner_must_add  Google 404s a manager       -> the ONLY fair ask, and it
#                   adding an admin                must be worded as the Bing
#                                                  and Apple seat, not as
#                                                  "we can't reach your
#                                                  listing"
#   unknown         no location/place_id yet    -> DROP (nothing to hold)
#
# Verified against the fleet on 2026-08-05: 9 clients already manager, 3
# genuinely owner_must_add (HomeLyft, ProRestoration, PuroClean East Las
# Vegas), 8 with no GBP location connected at all.
# An explicit GBP noun is required, never a bare "google": "accept the Google
# Ads manager invite" would otherwise match both guards, and the Ads one owns
# it. The negative clause keeps Ads/LSA wording out for the same reason.
_GBP_MGR_ASK_RE = re.compile(
    r"(?=.*\b(?:gbp|business\s*profile|business\s*listing|google\s*listing|"
    r"business\.google\.com)\b)"
    r"(?!.*\b(?:adwords|local\s+services|lsa|google\s+ads)\b)"
    r"(?=.*\b(?:manager|admin|administrator|people\s+and\s+access|access)\b)"
    r"(?=.*\b(?:add|invite|grant|give)\b)", re.I | re.S)
# The OAuth connect ask is the same family: never ask a client to connect an
# account they have already connected.
_GBP_CONNECT_ASK_RE = re.compile(
    r"(?=.*\bconnect\b)(?=.*\bgoogle\b)"
    r"(?=.*\b(?:account|listing|business\s*profile|gbp)\b)", re.I | re.S)
_GBP_ASK_NOT_RE = re.compile(
    r"do ?n['’]?o?t ask|don['’]t ask|no need to ask|already (?:connected|added)"
    r"|nothing else needed", re.I)


def _gbp_access_state(company_id: str) -> str:
    """Agency-seat state for this client's GBP, from the memo the daily
    gbp_admin_invite pass re-derives from Google itself.

    '' when we have never evaluated this client — treated as 'unknown'."""
    try:
        rows = _sb("GET", "/rest/v1/ops_kv?k=eq.gbp-manager-access&select=v") or []
        memo = (rows[0].get("v") or {}) if rows else {}
    except Exception:
        return ""
    try:
        from client_ops_sync import slug_map
        slug = slug_map().get(company_id)
    except Exception:
        slug = None
    return str(((memo.get(slug) or {}) if slug else {}).get("state") or "")


def _has_google_grant(company_id: str) -> bool:
    """Does this client already have a live Google OAuth connection?"""
    try:
        rows = _sb("GET", "/rest/v1/user_integrations"
                   f"?client_id=eq.{company_id}&provider=eq.google"
                   "&select=id&limit=1") or []
        return bool(rows)
    except Exception:
        return False


def gbp_ask_guard(company: dict, items: list[dict],
                  directives: list[dict] | None, dry_run: bool):
    """Never ask for Google access we hold, or could take ourselves.

    Same contract as lsa_ask_guard: (items, directives, note)."""
    directives = directives or []

    def _is(rx, t):
        t = str(t or "")
        return bool(rx.search(t)) and not _GBP_ASK_NOT_RE.search(t)

    conn_items = [i for i in items if _is(_GBP_CONNECT_ASK_RE, i.get("text"))]
    conn_dirs = [d for d in directives if _is(_GBP_CONNECT_ASK_RE, d.get("body"))]
    mgr_items = [i for i in items if _is(_GBP_MGR_ASK_RE, i.get("text"))
                 and i not in conn_items]
    mgr_dirs = [d for d in directives if _is(_GBP_MGR_ASK_RE, d.get("body"))
                and d not in conn_dirs]
    if not (conn_items or conn_dirs or mgr_items or mgr_dirs):
        return items, directives, None

    drop_i: list[dict] = []
    drop_d: list[dict] = []
    note: str | None = None

    if conn_items or conn_dirs:
        if _has_google_grant(company["id"]):
            print("  [gbp-access] their Google account is ALREADY connected "
                  "(user_integrations holds a live grant) — retiring the "
                  "connect ask instead of sending it")
            for it in conn_items:
                val = (f"auto-satisfied {datetime.now(timezone.utc).date()}: "
                       "Google account already connected — nothing to ask")
                if it.get("kind") == "intake":
                    apply_answer(it["id"], val, dry_run)
                else:
                    resolve_plan_row(it["id"], dry_run)
            if not dry_run:
                resolve_directives(conn_dirs, why="Google already connected")
            drop_i += conn_items
            drop_d += conn_dirs

    if mgr_items or mgr_dirs:
        state = _gbp_access_state(company["id"])
        if state == "manager":
            print("  [gbp-access] contact@restorationai.io is ALREADY an "
                  "accepted manager on their listing — retiring the ask "
                  "instead of sending it")
            for it in mgr_items:
                val = (f"auto-satisfied {datetime.now(timezone.utc).date()}: "
                       "agency account is already a manager on the GBP "
                       "listing (gbp-manager-access memo)")
                if it.get("kind") == "intake":
                    apply_answer(it["id"], val, dry_run)
                else:
                    resolve_plan_row(it["id"], dry_run)
            if not dry_run:
                resolve_directives(mgr_dirs, why="agency is already a manager")
            drop_i += mgr_items
            drop_d += mgr_dirs
        elif state == "owner_must_add":
            note = (
                "\nGBP MANAGER ASK — SAY WHAT IS ACTUALLY MISSING (Santino "
                "2026-08-05): we ALREADY manage this listing; the Google user "
                "they connected gives us that. Never say or imply we cannot "
                "get on their listing, cannot see it, or cannot work on it — "
                "it is false and they know it. The one thing we cannot do "
                "through the API is add our own agency address, because "
                "Google will not let a manager add another admin. Ask for "
                "exactly that and give the reason honestly: adding "
                "contact@restorationai.io as a Manager at business.google.com "
                "(Business Profile settings, People and access, Add) is what "
                "lets us publish their listing to Bing and Apple Maps. One "
                "ask, no other ask in that message.\n")
        elif not _has_google_grant(company["id"]):
            # No OAuth grant at all: the invite API has no way in, so this is
            # NOT ours to take and the ask stands (FireDEX, AAA, Davis, Paul
            # Davis, DISS on 2026-08-05 — their "give us access" items are the
            # honest kind). Left exactly as found, no note.
            print("  [gbp-access] no Google grant on file — the API cannot "
                  "reach this listing at all, so the access ask is genuine; "
                  "leaving it open")
        else:
            # none / pending — the API path is still open to us.
            print(f"  [gbp-access] agency seat state is {state or 'unknown'!r} "
                  "— the invite/accept API can still get it, so this is ours "
                  "to do, not theirs; dropping the ask "
                  "(scripts/gbp_admin_invite.py)")
            drop_i += mgr_items
            drop_d += mgr_dirs

    return ([i for i in items if i not in drop_i],
            [d for d in directives if d not in drop_d], note)


_ASK_TOPIC_RES = {
    # topic keywords a prohibition note might name -> ask text that topic owns
    "google-connect": re.compile(
        r"google|business\s+profile|\bgbp\b|\bconnect", re.I),
    # "Hold off telling X their website is live / sharing the site" — the
    # perception-of-value hold (Jimmy / cal-west 2026-08-28): suppresses the
    # share-the-site / preview-reveal asks while the note is open.
    "site-share": re.compile(
        r"web\s?site|\bsite\b|preview|launch", re.I),
}


def boss_prohibition_guard(company: dict, items: list[dict],
                           directives: list[dict] | None, dry_run: bool):
    """An OPEN prohibitive ops note from Santino ("Stop reaching out and
    asking Heath to connect his Google Business profile", Davis 2026-08-28)
    must mechanically drop the matching recurring asks — not just sit in the
    LLM's context hoping to be honored. Scoped to the topics the note names;
    everything else composes normally. The note staying OPEN keeps the
    suppression alive; resolving it re-arms the asks."""
    directives = directives or []
    try:
        notes = _sb("GET", f"/rest/v1/marketing_ops_notes?company_id=eq."
                    f"{company['id']}&status=eq.open&select=body,author") or []
    except Exception:  # noqa: BLE001 — fail open, other guards still run
        return items, directives, None
    prohibitions = [
        str(n.get("body") or "") for n in notes
        if _DIRECTIVE_PROHIBIT_RE.match(str(n.get("body") or "").strip())
        and not str(n.get("author") or "").strip().lower().startswith(_MACHINE_AUTHORS)]
    if not prohibitions:
        return items, directives, None
    drop_i: list[dict] = []
    drop_d: list[dict] = []
    reasons: list[str] = []
    for topic, topic_re in _ASK_TOPIC_RES.items():
        hits = [b for b in prohibitions if topic_re.search(b)]
        if not hits:
            continue
        for coll, dropped in ((items, drop_i), (directives, drop_d)):
            for it in coll:
                blob = " ".join(str(it.get(k) or "") for k in
                                ("action_key", "title", "rationale", "body"))
                if topic_re.search(blob):
                    dropped.append(it)
        reasons.append(f"[boss-prohibition] {topic}: open note "
                       f"({hits[0][:70]!r}) suppresses the ask")
    for r in reasons:
        print("  " + r)
    return ([i for i in items if i not in drop_i],
            [d for d in directives if d not in drop_d],
            ("\n".join(reasons) or None))


def access_ask_guard(company: dict, items: list[dict],
                     directives: list[dict] | None, dry_run: bool):
    """One gate over every ask for access we might already hold.

    Google Ads / Local Services manager links, then Google Business Profile
    (agency seat + OAuth connect). Kept as one call so no compose path can
    pick up one guard and miss the other — that is exactly how the GBP ask
    slipped out on 08-05 while the Ads guard was sitting right there."""
    items, directives, ads_note = lsa_ask_guard(company, items, directives,
                                                dry_run)
    items, directives, gbp_note = gbp_ask_guard(company, items, directives,
                                                dry_run)
    items, directives, veto_note = boss_prohibition_guard(company, items,
                                                          directives, dry_run)
    note = "\n".join(n for n in (ads_note, gbp_note, veto_note) if n)
    return items, directives, (note or None)


# ------------------------------------------------------------- topic bans
# The other half of the untagged-note vocabulary: the notes that say what NOT
# to say. "Do NOT mention prorestorationca.com, the domain, or registrar
# access to Angie in ANY message ... off-limits for client outreach until
# Santino says otherwise" (2026-07-30) has been open the whole time, rides
# into compose with the intel, and the model still drafted the domain ask at
# Angie on 2026-08-04. A prompt line is not a guarantee; this is the gate.
# High precision on purpose: only an explicit domain/URL named in the ban
# clause, or a topic from a small curated vocabulary, ever blocks a send —
# a vague ban is left to the prompt.
_BAN_CLAUSE_RE = re.compile(
    r"\b(?:do\s*n['’]?o?t|don['’]t|never)\s+(?:ever\s+)?"
    r"(?:mention|bring\s+up|discuss|talk\s+about|raise|ask\s+(?:\w+\s+)?"
    r"(?:about|to|for)?)\b(?P<what>.{0,180})", re.I | re.S)
_BAN_DOMAIN_RE = re.compile(r"\b[a-z0-9][a-z0-9-]*\.(?:com|net|org|io|co|us)\b",
                            re.I)
_BAN_TOPICS = {
    "domain": r"\bdomain\b|\bregistrar\b|\bnameserver",
    "registrar access": r"\bgodaddy\b|\bnamecheap\b|\bbluehost\b|\bmoniker\b",
    "lsa": r"\blsa\b|local services ads|google guaranteed",
    "pricing": r"\bpricing\b|\bprice\b|\bcost\b|\bquote\b",
    "billing": r"\binvoice\b|\bbilling\b|\bcontract\b",
    "review campaign": r"review campaign",
}


# A hold is stronger than a topic ban: not "avoid this subject" but "say
# NOTHING to this client until Santino says otherwise". It was being recorded
# as an ops note and enforced by nothing (2026-08-05). Jerrott Gray only stayed
# un-messaged because his number happened to be missing from the hand-typed
# allowlist, which stopped being true the moment the allowlist started deriving
# from client contact cards. High precision on purpose: an explicit marker, not
# the word "hold" appearing in prose.
# HARD-GAG is unambiguous and matches anywhere. HOLD must be the note's
# HEADLINE — inside the first 160 characters — because ordinary notes discuss
# holding things constantly. The loose form of this ("do not contact/text/
# message") was tried first and immediately caught HomeLyft on a dev-agent
# instruction reading "Do not text the client yourself", in a note whose whole
# point was that Monica SHOULD message them. A false positive here silences a
# client completely, which is the exact failure this file is being changed to
# stop, so the bar is an explicit marker rather than a sentiment.
#
# To put a client on hold, open a note whose first line is:
#     [TODO-SANTINO] HOLD — <why>
_HOLD_HEADLINE = 160
_HOLD_RE = re.compile(r"HARD-?GAG(?:GED)?|\bHOLD\b\s*[—:-]", re.I)


def company_hold(company_id: str | None) -> str | None:
    """Reason string when this client is under a total communication hold.

    Read from the same open ops notes the rest of the gates use, so putting a
    client on hold stays a one-line board action with no code change, and
    resolving that note lifts it.
    """
    if not company_id:
        return None
    try:
        rows = _sb("GET", f"/rest/v1/marketing_ops_notes?company_id=eq.{company_id}"
                   "&status=eq.open&select=body&limit=20") or []
    except Exception:  # noqa: BLE001 — a read failure must not unblock a hold
        return "could not verify hold state (ops-notes read failed)"
    for r in rows:
        body = " ".join(str(r.get("body") or "").split())
        if _HOLD_RE.search(body[:_HOLD_HEADLINE]):
            return f"open note says so: {body[:150]}"
    return None


def banned_topics(company_id: str | None) -> list[tuple[str, str]]:
    """[(label, regex)] this client must not be messaged about, read from the
    open prohibition notes. Empty when nothing is off-limits."""
    if not company_id:
        return []
    try:
        rows = _sb("GET", f"/rest/v1/marketing_ops_notes?company_id=eq.{company_id}"
                   "&status=eq.open&select=body&limit=20") or []
    except Exception:
        return []
    out: dict[str, str] = {}
    for r in rows:
        body = str(r.get("body") or "")
        for m in _BAN_CLAUSE_RE.finditer(body):
            clause = m.group("what")
            for dom in set(_BAN_DOMAIN_RE.findall(clause)) | {
                    d for d in _BAN_DOMAIN_RE.findall(clause)}:
                out[dom.lower()] = re.escape(dom)
            for label, pat in _BAN_TOPICS.items():
                if re.search(pat, clause, re.I):
                    out[label] = pat
    return sorted(out.items())


def topic_ban_violation(company_id: str | None, body: str) -> str | None:
    """Refusal reason when the draft touches an off-limits topic, else None."""
    for label, pat in banned_topics(company_id):
        if re.search(pat, body or "", re.I):
            return (f"an open ops note puts '{label}' off-limits for this "
                    "client and the draft mentions it — message held (Angie / "
                    "prorestorationca.com, 2026-07-30 note). Resolve the note "
                    "when the topic is allowed again.")
    return None


# INTERNAL WORK MUST NOT LEAK INTO A CLIENT MESSAGE (Santino 2026-08-08).
#
# Internal items are given to the composer as read-only context so Monica stops
# treating a client as "all caught up" while we owe them a launch, and so she
# never asks for domain access on a domain we already own. But anything in a
# prompt can come back out of it — that is exactly how "I'll get that
# screenshot over to you" reached Rudy. An instruction in the system prompt is
# a preference; this is the enforcement.
#
# Deliberately narrow. It fires on the language of OUR pipeline, not on
# ordinary words a client message may legitimately contain ("your site is
# live" is fine and true; "pushing your site live tonight" is a commitment
# nobody authorised).
_INTERNAL_LEAK_RE = re.compile(
    r"\b(push(ing)? (your |the )?site live|cut ?over|nameserver|"
    r"cloudflare|pages\.dev|mcc|manager link|customer_client_link|"
    r"action[- ]plan row|ops board|internal task)\b", re.I)


# FILE REQUESTS ARE HUB-LINK-ONLY, AND DEVICE-NEUTRAL (Santino 2026-08-09).
#
# Two live failures on the same day. Josiah Viland was told to EMAIL his
# customer list and playbook to setup@restorationai.io, and Bob Olson was told
# to "tap Upload Photos and add it from your phone" for a customer list he was
# always going to send from a desk.
#
# Both are the same root cause: the wording lives in several places and nothing
# enforced the rule across them. Fixing the instructions is necessary and not
# sufficient — the previous fix corrected the logo ask and the LSA-docs ask
# kept saying "email contact@restorationai.io" for another two days. This is
# the enforcement.
#
# WHY IT MATTERS beyond tidiness: an emailed attachment lands in an ops row
# that needs a human to file it, so the client has done the work and we still
# have not received it. A hub upload goes straight to storage and pins its own
# task.
_EMAIL_A_FILE_RE = re.compile(
    r"(email|e-mail|send)\s+(it|them|that|these|those|the\s+\w+)?\s*"
    r"(to\s+)?(us\s+)?(at\s+)?[\w.+-]*@[\w.-]+\.\w+"
    r"|reply\s+(to\s+this\s+)?(message\s+)?with\s+the\s+(file|photo|list|attach)"
    r"|attach\s+(it|them|the\s+\w+)\s+to\s+(an?\s+)?(email|reply)", re.I)
_DEVICE_ASSUMED_RE = re.compile(
    r"\b(from|on)\s+your\s+phone\b|\btap\s+(the\s+)?\w+\b|\bon\s+your\s+cell\b",
    re.I)


def file_request_violation(body: str) -> str | None:
    """Refusal reason when a draft asks a client to email a file, else None.

    Device wording is corrected, not blocked: "tap" instead of "click" is a
    poor guess, not a broken instruction, and holding a whole message over one
    verb would cost more than it saves.
    """
    m = _EMAIL_A_FILE_RE.search(body or "")
    # ACCESS INVITES ARE NOT FILES (Jerrott 2026-08-11): "send the invite to
    # setup@restorationai.io" is the CORRECT GoDaddy/registrar delegate-access
    # instruction — the invite must go to an email address by design, nothing
    # lands in an inbox needing hand-filing. Two passes drafted the right
    # answer and this guard shredded both while he waited on "What do you
    # need?". Only the file case stays blocked.
    if m and re.search(r"\b(invite|delegate|access)\b",
                       (body or "")[max(0, m.start() - 40):m.end() + 40], re.I):
        m = None
    if m:
        return (f"draft tells the client to email us a file ({m.group(0)!r}). "
                "File requests are HUB-LINK-ONLY: an emailed attachment lands "
                "in an ops row needing a human to file it, so the client does "
                "the work and we still do not have it. Send the hub link "
                "instead. Message held.")
    return None


def soften_device_assumption(body: str) -> str:
    """Rewrite phone-only phrasing so a desktop client is not told to 'tap'."""
    out = re.sub(r"\b[Tt]ap\b", "Click", body or "")
    out = re.sub(r"\b(from|on) your phone\b", r"\1 your phone or computer", out,
                 flags=re.I)
    return out


_SVC_DISCLAIM_RE = re.compile(
    r"\bwe (?:don'?t|do not|never|no longer) (?:do|offer|handle|touch|"
    r"provide|perform)\s+(?:the\s+)?([a-z][a-z &/-]{2,50}?)"
    r"(?:\s+(?:work|jobs|side|stuff))?\s*(?:[.!,\n]|$)", re.I)


def record_service_disclaimers(company: dict | None, pending: dict) -> None:
    """A client saying plainly "we don't do X" is a durable SERVICE FACT,
    not just conversation (single-source-of-truth law; ACS 2026-09-19:
    "We don't do Mold or fire" + "We don't do the rebuild" had to be
    hand-carried into the site prompts). Record the exact phrases they
    used on integration_settings.services_excluded and file ONE ops note
    so the systems that consume scope (site prompts, GBP services, name
    slates) get trued up. Records only what they literally named; never
    infers. Deduped per message."""
    cid = str((company or {}).get("id") or "")
    body = str((pending or {}).get("body") or "")
    if not (cid and body):
        return
    hits = []
    for m in _SVC_DISCLAIM_RE.finditer(body):
        phrase = re.sub(r"\s+", " ", m.group(1)).strip(" -/&").lower()
        if phrase and phrase not in ("it", "that", "this", "them", "anything"):
            hits.append(phrase)
    if not hits:
        return
    import hashlib
    dkey = ("svc-disclaim:" + cid + ":"
            + hashlib.sha1(body.encode()).hexdigest()[:12])
    if kv_get(dkey):
        return  # this exact message already recorded
    rows = _sb("GET", f"/rest/v1/companies?id=eq.{cid}"
               "&select=integration_settings") or []
    ints = (rows[0].get("integration_settings") if rows else {}) or {}
    excl = list(ints.get("services_excluded") or [])
    new = [h for h in hits if h not in excl]
    if new:
        ints["services_excluded"] = excl + new
        _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
            {"integration_settings": ints})
        _sb("POST", "/rest/v1/marketing_ops_notes",
            {"company_id": cid, "status": "open", "author": "monica",
             "body": ("[SERVICE SCOPE] Client stated they do NOT do: "
                      + ", ".join(new) + f" (from their text: "
                      f"\"{body[:140]}\"). Recorded on "
                      "services_excluded. True up wherever scope lives: "
                      "site content/prompts, GBP services, name "
                      "candidates, content lanes.")},
            prefer="return=minimal")
        print(f"  [svc-disclaim] recorded: {', '.join(new)}")
    kv_set(dkey, {"at": datetime.now(timezone.utc).isoformat(),
                  "phrases": hits})


_LOCKED_NAME_CACHE: dict = {}


def locked_name_violation(company: dict | None, body: str) -> str | None:
    """Refusal reason when a draft proposes a business name different from
    the client's LOCKED chosen name, else None (ACS 2026-09-19: Monica
    misread site feedback and texted 'let's drop carpet and duct from the
    name. New fit: "..." Want to lock that in?' about a name the client had
    already been told to file letter for letter). Name changes are a human
    decision; Monica never renegotiates one. Fail-open when no name is
    locked."""
    cid = str((company or {}).get("id") or "")
    if not cid or not body:
        return None
    if cid not in _LOCKED_NAME_CACHE:
        chosen = ""
        try:
            rows = _sb("GET", "/rest/v1/marketing_gbp_suggestions"
                       f"?company_id=eq.{cid}&item_type=eq.name"
                       "&status=eq.chosen&select=item&limit=1") or []
            chosen = str((rows[0] if rows else {}).get("item") or "").strip()
            if not chosen:
                kv = kv_get(f"rename-convo:{cid}") or {}
                chosen = str(kv.get("chosen") or "").strip()
        except Exception:  # noqa: BLE001 — unknown = no lock = no guard
            chosen = ""
        _LOCKED_NAME_CACHE[cid] = chosen
    chosen = _LOCKED_NAME_CACHE[cid]
    if not chosen:
        return None

    def _norm(t: str) -> str:
        t = re.sub(r"\s*&\s*", " and ", str(t))
        return re.sub(r"\s+", " ", t).strip().lower().rstrip(".")

    # Net A: a quoted keyworded-name-looking string that is NOT the locked
    # name (brand prefix + " - " + descriptor is our naming shape).
    for m in re.finditer(r'"([^"\n]{10,110} - [^"\n]{4,90})"', body):
        if _norm(m.group(1)) != _norm(chosen):
            return ("locked-name guard: the draft proposes a name "
                    f"({m.group(1)[:60]!r}) different from the LOCKED chosen "
                    f"name — name changes are a human decision, never "
                    "Monica's. Message held.")
    # Net B: renegotiation phrasing about the name while a lock exists.
    if re.search(r"(drop (it|that|those|them)? ?from the name|new fit:|"
                 r"(change|update|revise|rework) the name|"
                 r"different name|new name idea)", body, re.I):
        return ("locked-name guard: the draft renegotiates a LOCKED business "
                "name. Acknowledge and route to the team instead. "
                "Message held.")
    return None


def internal_leak_violation(body: str, internal: list[dict] | None,
                            company: dict | None = None) -> str | None:
    """Refusal reason when a draft leaks internal work, else None.

    Only armed when this client actually HAS internal work in play — the same
    words in an unrelated message are not evidence of a leak, and a guard that
    fires on everything gets switched off.

    THE CLIENT'S OWN PREVIEW LINK IS NOT A LEAK (2026-09-19: ACS + DryCor
    reveals both held the same afternoon — the preview-share flow EXISTS to
    send a rankai-{slug}.pages.dev URL, so any client with an open internal
    task could never be shown their site). Strip this client's own sanctioned
    preview URLs before matching; every other pages.dev / cutover / NS
    mention still holds.
    """
    if not internal:
        return None
    scan = body or ""
    slug = str((company or {}).get("rank_ai_slug") or "").strip()
    if not slug and (company or {}).get("id"):
        try:
            rows = _sb("GET", "/rest/v1/marketing_sites?company_id=eq."
                       f"{company['id']}&select=rank_ai_slug&limit=1") or []
            slug = str((rows[0] if rows else {}).get("rank_ai_slug")
                       or "").strip()
        except Exception:  # noqa: BLE001 — no slug just means no exemption
            slug = ""
    if slug:
        scan = re.sub(
            r"https?://(staging\.)?rankai-" + re.escape(slug)
            + r"\.pages\.dev[^\s]*", " ", scan, flags=re.I)
    m = _INTERNAL_LEAK_RE.search(scan)
    if not m:
        return None
    return (f"draft mentions internal work ({m.group(0)!r}) while "
            f"{len(internal)} internal task(s) are open for this client. "
            "Internal items are read-only context: they exist to stop wrong "
            "asks and to inform tone, never to be described or promised to a "
            "client. Message held.")


def cadence_check(cs: dict, company: dict, contact: dict | None = None,
                  enforce_hours: bool = True, boss_override: bool = False,
                  client_waiting: bool = False, reply_to=None) -> str | None:
    """Return a human-readable refusal reason, or None if a send is allowed now.

    Business hours run in the client's OWN timezone (resolve_timezone: GHL
    contact -> companies.timezone -> plan-input state -> default+warning) and
    are enforced on every send path; the canary passes enforce_hours=False.
    boss_override (an open [FROM SANTINO]/[SEND-PREVIEW] note) and
    client_waiting (pending_client_message: the client spoke last and nobody
    answered — replying is not a nudge, 2026-08-02) both skip the cooldown
    and nudge cap — never the hours or the allowlist canary.

    reply_to (2026-08-04) is the timestamp of the client message being
    answered. It opens the shoulder hours for REPLIES ONLY — see
    business_hours_check. A boss directive is not a reply: Santino ordering
    outreach does not make an 8pm text welcome, so directives pass reply_to
    None and keep waiting for 9am."""
    if not (boss_override or client_waiting):
        if cs.get("nudge_count", 0) >= MAX_NUDGES:
            return f"max {MAX_NUDGES} nudges reached — ESCALATE to Santino"
        ne = next_eligible(cs)
        now = datetime.now(timezone.utc)
        if ne and now < ne:
            return f"cooldown — next eligible {ne.strftime('%Y-%m-%d %H:%M UTC')}"
    if enforce_hours:
        reason = business_hours_check(company, contact, reply_to=reply_to)
        if reason:
            return reason
    return None


# ---------------------------------------------------------------- SEND (gated)
def owed_reply_channel(requested: str, cs: dict | None,
                       contact: dict | None) -> str:
    """REPLY-IN-CHANNEL (2026-08-20, Monica email evolution 2d — the Bobby
    case: he emailed, Monica answered by SMS). When the send is the backstop
    ANSWERING a client message that arrived by EMAIL, answer by email.
    Upgrades only the sms DEFAULT (an explicit email request stays email, an
    explicit sms choice was never expressible — argparse default is sms) and
    only when the contact has an email on file. Proactive nudges (no
    awaiting_reply armed) keep the SMS default: SMS converts better and
    clients say so (Kenny 08-11: 'better chance via text vs email')."""
    owed = (cs or {}).get("awaiting_reply") or {}
    if (requested == "sms" and owed.get("channel") == "email"
            and ((contact or {}).get("email") or "").strip()):
        return "email"
    return requested


def _re_subject(subject: str | None) -> str | None:
    """'Re: {original}' so the reply threads in the client's mailbox even
    when GHL sends a fresh email; an existing Re: prefix is kept as-is."""
    if not subject or not str(subject).strip():
        return None
    s = str(subject).strip()
    return s if s.lower().startswith("re:") else f"Re: {s}"


def _email_thread_fields(m: dict | None) -> dict:
    """The threading crumbs an email inbound carries (fetch_inbound_since):
    subject for the Re: line, GHL email message id for a true in-thread
    reply. Empty for SMS — safe to splat anywhere."""
    out = {}
    if (m or {}).get("email_subject"):
        out["email_subject"] = m["email_subject"]
    if (m or {}).get("email_msg_id"):
        out["email_msg_id"] = m["email_msg_id"]
    return out


def _first_token(name: str) -> str:
    return (name or "").strip().split()[0] if (name or "").strip() else ""


def _same_first_name(a: str, b: str) -> bool:
    """Rob == Robert, Ash == Ashley: prefix match either way, min 3 chars."""
    a, b = a.lower(), b.lower()
    return bool(a and b and len(a) >= 3 and len(b) >= 3
                and (a.startswith(b) or b.startswith(a)))


def wrong_name_violation(company: dict, contact: dict,
                         body: str) -> str | None:
    """GREETING NAME GUARD (Santino 2026-09-16 — the Ashley/DryCor
    incident: two post-meeting recaps opened "Rob" but delivered to the
    PREFERRED contact's thread, Ashley, twice). The recipient's true name
    comes from the app Contact Card entry matched to the resolved GHL
    contact by phone/email — the names Santino keeps on file — with the
    GHL record as fallback. If the message's first sentence addresses a
    DIFFERENT known person of this company in vocative position (their
    name followed by , . ! or ?), the send blocks: recompose for the
    person who will actually read it. Deterministic on purpose — this
    backstops every sender, one-shots and humans-in-a-hurry included."""
    ints = company.get("integration_settings") or {}
    entries = ints.get("contacts") or []
    gp = _norm_phone(contact.get("phone") or "")
    ge = _norm_email(contact.get("email") or "")

    recipient = ""
    for c in entries:
        cp = _norm_phone(c.get("cell") or c.get("phone") or "")
        ce = _norm_email(c.get("email") or "")
        if (gp and cp and cp == gp) or (ge and ce and ce == ge):
            recipient = _first_token(
                c.get("first_name")
                or f"{c.get('name') or ''}".strip())
            break
    if not recipient:
        recipient = (contact.get("firstName") or "").strip()
    if not recipient:
        return None  # nobody on file to judge against

    known: set[str] = set()
    for c in entries:
        known.add(_first_token(c.get("first_name") or c.get("name") or ""))
    known.add(_first_token(company.get("account_owner_name") or ""))
    known.add(_first_token(ints.get("owner_first_name") or ""))
    known.discard("")

    stripped = body.strip()
    cut = re.search(r"[.!?\n]", stripped)
    first_sentence = stripped[:cut.end() if cut else 160][:160]
    # Vocative position only: the name is preceded by a greeting word or a
    # comma (or starts the message) AND followed by punctuation or the
    # sentence end. Catches "Morning Rob," and "Great catching up today,
    # Rob." while leaving third-person mentions ("call with Rob") alone.
    voc = re.compile(
        r"(?:^(?:hi|hey|hello|(?:good\s+)?(?:morning|afternoon|evening)"
        r"|thanks|thank you)[\s,]+|^|,\s+)"
        r"([A-Z][a-z]{2,})(?=\s*[,.!?]|\s*$)", re.IGNORECASE)
    for m in voc.finditer(first_sentence):
        tok = m.group(1)
        if _same_first_name(tok, recipient):
            continue
        for k in known:
            if _same_first_name(tok, k):
                return (f"WRONG-NAME GUARD: message opens addressing "
                        f"'{tok}' but the recipient on file for "
                        f"{contact.get('phone') or contact.get('email')} "
                        f"is {recipient} (app Contact Card). Recompose "
                        f"for {recipient}.")
    return None


_SLUG_CACHE: dict = {}


def _company_slug(cid: str) -> str:
    """rank_ai_slug for a company id, cached per process ('' = no site)."""
    if cid not in _SLUG_CACHE:
        try:
            rows = _sb("GET", "/rest/v1/marketing_sites?company_id=eq."
                       f"{cid}&select=rank_ai_slug&limit=1") or []
            _SLUG_CACHE[cid] = str((rows[0] if rows else {})
                                   .get("rank_ai_slug") or "").strip()
        except Exception:  # noqa: BLE001
            return ""  # transient read failure: don't cache the miss
    return _SLUG_CACHE[cid]


def _stamp_preview_reveal(company: dict | None, body: str,
                          contact: dict | None = None) -> None:
    """Successful client send carrying THIS client's preview URL = a
    reveal moment. Writes integration_settings.site_reveal {sent_at, url};
    the Build Stages website board anchors its silence-release clock to
    sent_at (FIX Restoration 2026-09-20).

    ROUND RE-ARM (Santino 2026-09-21): revision cycles restart the wait.
    When the client has REPLIED since the current anchor and we send the
    link again (the "updates are in, take another look" reply), sent_at
    moves to now and the follow-up stamp clears — a fresh 2-day wait, one
    nudge, 2 more quiet days, then Ready to Launch. Without an inbound
    since the anchor our own resends still never restart the clock (the
    FIX lesson): the 12h+ second link-send is the one follow-up nudge."""
    cid = str((company or {}).get("id") or "")
    if not (cid and body):
        return
    slug = _company_slug(cid)
    if not slug or f"rankai-{slug}.pages.dev" not in body:
        return
    rows = _sb("GET", f"/rest/v1/companies?id=eq.{cid}"
               "&select=integration_settings") or []
    ints = (rows[0].get("integration_settings") if rows else {}) or {}
    reveal = ints.get("site_reveal") or {}
    now = datetime.now(timezone.utc)
    if reveal.get("sent_at"):
        try:
            anchor = datetime.fromisoformat(
                str(reveal["sent_at"]).replace("Z", "+00:00"))
        except ValueError:
            return
        replied_since = False
        try:
            if contact and contact.get("id"):
                for m in fetch_history(contact["id"], 40) or []:
                    if (m.get("direction") == "in" and m.get("when")
                            and m["when"] > anchor):
                        replied_since = True
                        break
        except Exception:  # noqa: BLE001 — history down = no re-arm, safe
            pass
        if replied_since:
            reveal.setdefault("first_sent_at", reveal["sent_at"])
            reveal["rounds"] = int(reveal.get("rounds") or 1) + 1
            reveal["sent_at"] = now.isoformat()
            reveal.pop("followup_sent_at", None)
            ints["site_reveal"] = reveal
            _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                {"integration_settings": ints})
            print(f"  [reveal-stamp] revision round {reveal['rounds']} "
                  f"re-armed for {slug} — fresh 2-day wait")
            return
        # FOLLOW-UP STAMP (Santino 2026-09-20): a second link-bearing send
        # 12h+ after the anchor with no reply is the one follow-up nudge.
        # Stamped once per round; the board's silence-release counts 2
        # quiet days from HERE.
        if not reveal.get("followup_sent_at"):
            if (now - anchor).total_seconds() >= 12 * 3600:
                reveal["followup_sent_at"] = now.isoformat()
                ints["site_reveal"] = reveal
                _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                    {"integration_settings": ints})
                print(f"  [reveal-stamp] follow-up recorded for {slug}")
        return  # same-round resends never restart the clock
    m = re.search(r"https?://\S*rankai-" + re.escape(slug)
                  + r"\.pages\.dev\S*", body)
    ints["site_reveal"] = {
        "sent_at": now.isoformat(),
        "url": (m.group(0) if m else f"https://rankai-{slug}.pages.dev"),
    }
    _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
        {"integration_settings": ints})
    print(f"  [reveal-stamp] preview reveal recorded for {slug}")


def _reveal_followup_due(company: dict | None,
                         history: list[dict] | None = None) -> bool:
    """True when the site reveal went out 2+ days ago, the client never
    replied, and the one follow-up hasn't been sent — the cooldown
    carve-out that makes silence-release mean 'ignored two touches'."""
    ints = (company or {}).get("integration_settings") or {}
    reveal = ints.get("site_reveal") or {}
    if not reveal.get("sent_at") or reveal.get("followup_sent_at"):
        return False
    try:
        sent = datetime.fromisoformat(
            str(reveal["sent_at"]).replace("Z", "+00:00"))
    except ValueError:
        return False
    if (datetime.now(timezone.utc) - sent).days < 2:
        return False
    for m in history or []:
        if (m.get("direction") == "in" and m.get("when")
                and m["when"] > sent):
            return False  # they replied — the normal reply flow owns this
    return True


_ACK_PROMISE_RE = re.compile(
    r"\b(we'?ll get|we'?re (?:getting|adding|updating|submitting|removing)|"
    r"we'?ll (?:add|update|remove|fix|change|handle|take care)|"
    r"i'?ll (?:get|pass|flag|add|update)|flagging\b|"
    r"getting (?:that|this|it|your) (?:updated|changed|fixed|added|removed))",
    re.I)


def _capture_acknowledged_work(company: dict | None, contact: dict | None,
                               body: str) -> None:
    """Monica promised action -> a capture note exists, always. Pairs the
    outbound promise with the client's newest inbound so whoever executes
    (dev agent tonight, or Santino) sees the actual request verbatim."""
    cid = str((company or {}).get("id") or "")
    if not (cid and body) or not _ACK_PROMISE_RE.search(body):
        return
    # The feedback router may already have filed real work for this — a
    # second note would be noise. 2-hour overlap window, monica-authored.
    recent = _sb("GET", "/rest/v1/marketing_ops_notes"
                 f"?company_id=eq.{cid}&author=eq.monica&status=eq.open"
                 "&select=body,created_at&order=created_at.desc&limit=5") or []
    now = datetime.now(timezone.utc)
    for n in recent:
        try:
            age = (now - datetime.fromisoformat(
                str(n["created_at"]).replace("Z", "+00:00"))).total_seconds()
        except ValueError:
            continue
        if age < 7200 and ("[DEV]" in (n.get("body") or "")
                           or "[TODO-PROPOSED]" in (n.get("body") or "")
                           or "[MONICA-ACK]" in (n.get("body") or "")):
            return
    inbound = ""
    try:
        if contact and contact.get("id"):
            hist = fetch_history(contact["id"], 6)
            ins = [m for m in hist if m.get("direction") == "in"
                   and (m.get("body") or "").strip()]
            if ins:
                inbound = str(ins[-1].get("body") or "")[:300]
    except Exception:  # noqa: BLE001
        pass
    _sb("POST", "/rest/v1/marketing_ops_notes",
        {"company_id": cid, "status": "open", "author": "monica",
         "body": ("[MONICA-ACK] EXECUTION NEEDED — Monica acknowledged work "
                  f"to the client.\nClient said: \"{inbound}\"\n"
                  f"Monica replied: \"{body[:300]}\"\n"
                  "Route it: convert to a [DEV] task or do it, then resolve "
                  "this note. Her words and reality must match.")},
        prefer="return=minimal")
    print("  [ack-net] capture note filed (promise detected)")


def send_message(contact: dict, channel: str, body: str,
                 subject: str | None = None,
                 company: dict | None = None,
                 reply_to: str | None = None,
                 human_hold_exempt: bool = False,
                 email_msg_id: str | None = None) -> dict:
    """Deliver via GHL POST /conversations/messages. CANARY GATE lives HERE.

    The recipient (contact phone for SMS, contact email for Email) must be on
    the CONCIERGE_ALLOWLIST or this function raises SendBlocked. There is no
    override. Callers decide dry-run/--send; this function is the last line.

    LINK GATE (2026-08-04): when `company` is given, every URL of ours in the
    body is fetched first — a stale one is healed from marketing_sites and an
    unhealable one raises SendBlocked rather than mailing a client a dead
    link (FireDEX's Bob: "The link does not work"). Pass company on every
    client-facing send; the ops pings to Santino's own cell don't need it.

    reply_to (2026-08-05) identifies the CLIENT message this answers. It is
    stamped into the cross-process outbox so a second pass can tell that this
    exact message was already answered, whatever words it would have used.
    """
    if os.environ.get("CONCIERGE_PAUSED", "").strip() in ("1", "true", "yes"):
        raise SendBlocked("CONCIERGE_PAUSED is set — Santino paused all "
                          "concierge sending 2026-07-29. Unset it in .env / "
                          "the workflow env to resume.")
    held = company_hold((company or {}).get("id"))
    if held:
        raise SendBlocked(f"HOLD on this client — {held}")
    # CROSS-PROCESS SEND LOCK (Jared 2026-09-15: the webhook composer and a
    # second pass composed 13 seconds apart and the client got the same
    # confirmation twice; per-contact locks were per-process only). One
    # ops_kv row per contact, 45s TTL: whoever writes it first sends, the
    # other composer blocks and re-evaluates next cycle with fresh history.
    _lock_key = f"send-lock:{contact.get('id')}"
    try:
        _lk = kv_get(_lock_key)
        if isinstance(_lk, dict) and _lk.get("at"):
            _age = (datetime.now(timezone.utc)
                    - datetime.fromisoformat(_lk["at"])).total_seconds()
            if _age < 45:
                raise SendBlocked(
                    f"another composer holds the send lock for this contact "
                    f"({_age:.0f}s old) — skipping to avoid a double text; "
                    "anything owed re-evaluates next cycle")
        kv_set(_lock_key, {"at": datetime.now(timezone.utc).isoformat()})
    except SendBlocked:
        raise
    except Exception:  # noqa: BLE001 — a kv hiccup must never block sending
        pass
    # STALE-COMPOSE GUARD (Jared 2026-09-15, second incident: a composer
    # that started before another's send finished landed 66s later with
    # pre-send context — "you're done" followed by "send the filing" one
    # minute apart). After taking the lock, look at the thread ONE more
    # time: if ANY outbound landed in the last 120s, this draft was
    # composed against a thread that has since spoken — abort and let the
    # next cycle recompose with fresh history. Manual/exempt sends skip
    # (operators layer messages deliberately).
    if not human_hold_exempt and contact.get("id") not in (
            OPS_PING_CONTACT_ID, ADVICE_CONTACT_ID):
        try:
            _recent = fetch_history(contact["id"], 3)
            for _m in _recent:
                if _m.get("direction") != "out" or not _m.get("when"):
                    continue
                _age_s = (datetime.now(timezone.utc)
                          - _m["when"]).total_seconds()
                if _age_s < 120:
                    raise SendBlocked(
                        f"an outbound landed {_age_s:.0f}s ago — this draft "
                        "was composed against an older thread; recompose "
                        "next cycle with fresh history (stale-compose guard)")
                break
        except SendBlocked:
            raise
        except Exception:  # noqa: BLE001 — guard must never block on API errors
            pass
    # HUMAN QUIET WINDOW (Santino 2026-08-18): never talk over a human. Ops
    # pings go to Santino himself, not a client thread; send_now passes the
    # exemption because the click is the human speaking.
    if (not human_hold_exempt
            and contact.get("id") not in (OPS_PING_CONTACT_ID,
                                          ADVICE_CONTACT_ID)):
        hold = human_reply_hold(contact["id"])
        if hold:
            raise SendBlocked(hold)
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
    # LINK GATE \u2014 heal or refuse. Nothing of ours leaves unfetched.
    # TOPIC BAN \u2014 an off-limits subject never leaves on any path.
    if company is not None:
        body, dead = verify_outbound_links(company, body)
        if dead:
            raise SendBlocked(dead)
        banned = topic_ban_violation(company.get("id"), body)
        if banned:
            raise SendBlocked(banned)
        # LAUNCHED-CLAIM — a "your site is live" needs the cutover stamp.
        live_claim = site_live_claim_violation(company, body)
        if live_claim:
            raise SendBlocked(live_claim)
        # SITE-SHOWS CLAIM — "it shows <address> on the site" must be true
        # in the page's VISIBLE text (DISS/Addi 2026-09-24).
        shows_claim = site_shows_claim_violation(company, body)
        if shows_claim:
            raise SendBlocked(shows_claim)
        # ACTION-CLAIM — present-progressive vapor ("we're getting Chris
        # added now", Scott/BCP 2026-09-23) never leaves: no lane composes
        # that wording after real execution; only unexecuted promises do.
        if re.search(r"\b(?:we'?re?|i'?m|we are|i am)\s+getting\b"
                     r"[^.!?\n]{0,60}\b(?:added|updated|removed|changed|"
                     r"set up|sorted|handled|taken care of)\b"
                     r"|\bconsider it (?:done|handled)\b", body, re.I):
            raise SendBlocked(
                "ACTION-CLAIM: body promises an account action is being "
                "done ('getting X added/handled') — Monica must either "
                "verifiably execute or say she is passing it to Santino, "
                "never claim in-progress work (Chris Pappas 2026-09-23).")
        # INTERNAL LEAK — last line, same standing as the topic ban.
        leak = internal_leak_violation(body, fetch_internal_work(company["id"]),
                                       company)
        if leak:
            raise SendBlocked(leak)
        # FILE REQUESTS — hub link only, never email.
        filereq = file_request_violation(body)
        if filereq:
            raise SendBlocked(filereq)
        # WRONG NAME — the greeting must match the person on file for
        # THIS thread (Ashley/DryCor 2026-09-16).
        wrongname = wrong_name_violation(company, contact, body)
        if wrongname:
            raise SendBlocked(wrongname)
        # LOCKED NAME — Monica never renegotiates a confirmed business
        # name (ACS 2026-09-19). A sanctioned name change updates the
        # chosen record FIRST (the FF correction pattern), after which a
        # draft stating the new canonical passes this guard naturally.
        lockviol = locked_name_violation(company, body)
        if lockviol:
            raise SendBlocked(lockviol)
    # Device wording is fixed in place rather than blocked (see
    # soften_device_assumption): a desktop client should not be told to "tap".
    body = soften_device_assumption(body)
    payload: dict = {"type": "SMS" if channel == "sms" else "Email",
                     "contactId": contact["id"]}
    if channel == "sms":
        payload["message"] = body
        # THE 805 IS THE SENDER, HARDCODED (Santino 2026-08-10: "just have
        # her only send from the 805 from now on"). The env-var approach
        # burned us twice in one day: the GitHub secret held the pre-reversal
        # toll-free for 3 days of sends, and the Railway worker's env held it
        # even after the secret was fixed (Kyle's 855 reply). One sender,
        # one place, no environment can quietly disagree.
        payload["fromNumber"] = "+18053293449"
        env_from = os.environ.get("CONCIERGE_FROM_NUMBER", "").strip()
        if env_from and env_from != "+18053293449":
            print(f"  NOTE: CONCIERGE_FROM_NUMBER={env_from} ignored — "
                  "the 805 is hardcoded per Santino 2026-08-10.",
                  file=sys.stderr)
    else:
        payload["subject"] = subject or f"Your {BRAND_NAME} setup"
        payload["html"] = body.replace("\n", "<br>")
        # IN-THREAD EMAIL (2026-08-20, evolution 2d): when we know which
        # email we're answering, ask GHL to send it as a reply in that
        # thread. Unsupported/rejected combos fall back to a plain email
        # below — threading is best-effort, delivery is not.
        if email_msg_id:
            payload["emailReplyMode"] = "reply"
            payload["emailMessageId"] = email_msg_id
    try:
        try:
            result = _ghl("POST", "/conversations/messages", body=payload)
        except RuntimeError as e:
            if (email_msg_id and channel == "email"
                    and "DND" not in str(e)):
                print(f"  [email-thread] reply-mode send failed "
                      f"({str(e)[:80]}) — retrying as a plain email",
                      file=sys.stderr)
                payload.pop("emailReplyMode", None)
                payload.pop("emailMessageId", None)
                result = _ghl("POST", "/conversations/messages", body=payload)
            else:
                raise
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
    try:
        _sb("DELETE", f"/rest/v1/ops_kv?k=eq.{_lock_key}")
    except Exception:  # noqa: BLE001
        pass
    # Ops pings to Santino's own cell are not client threads and need no
    # sent-id bookkeeping; everything else must be recorded (see
    # sent_id_regression_check).
    if contact.get("id") not in (OPS_PING_CONTACT_ID, ADVICE_CONTACT_ID):
        _CLIENT_SENDS["sent"] += 1
        # CROSS-PROCESS OUTBOX (2026-08-05, Reign double-send): stamped here,
        # the one place every client send passes through, the instant it
        # lands — GHL's own history is minutes behind and cost Jerrott two
        # contradicting texts.
        note_outbound((company or {}).get("id"), body, reply_to)
        # PREVIEW-REVEAL SENT STAMP (Santino 2026-09-20, FIX Restoration:
        # the board's silence-release counted 2 days from the ask ROW's
        # creation — seeded at build — so a client who was never sent his
        # site promoted to "Ready to launch" on pure silence. The durable
        # truth is THIS moment: a successful client send whose body carries
        # their preview URL. Stamped once; the board's silence clock starts
        # here and nowhere else.)
        try:
            _stamp_preview_reveal(company, body, contact)
        except Exception as _e:  # noqa: BLE001 — stamping never breaks a send
            print(f"  [reveal-stamp] {str(_e)[:80]}")
        # ACKNOWLEDGMENT NET (Santino 2026-09-21, Alfredo's address +
        # Addi's removals: Monica said "we'll get it updated" / "flagging
        # for removal now" and NOTHING captured the work). Any client send
        # that promises action files a capture note pairing the client's
        # triggering message — unless the feedback router already filed a
        # [DEV]/[TODO-PROPOSED] for this company in the last 2 hours.
        # Monica's words and the work queue can no longer diverge.
        try:
            _capture_acknowledged_work(company, contact, body)
        except Exception as _e:  # noqa: BLE001 — the net never breaks a send
            print(f"  [ack-net] {str(_e)[:80]}")
        # DURABLE machine-sent marks (2026-09-14, the Mike/Tony instant-reply
        # poisoning): the state-blob ledger races across processes, so a
        # concurrent run can clobber freshly recorded ids and this send then
        # reads as HUMAN (local GHL keys stamp Santino's userId) — blocking
        # the webhook replies for an hour per thread. One ops_kv row per id
        # has no race; the human detectors check it as the second source.
        for _k in ("messageId", "emailMessageId"):
            _mid = (result or {}).get(_k)
            if _mid and isinstance(_mid, str):
                try:
                    kv_set(f"machine-sent:{_mid}",
                           {"at": datetime.now(timezone.utc).isoformat()})
                except Exception:  # noqa: BLE001 — marks are best-effort
                    pass
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

WHO YOU ARE — HARD RULE, no exceptions (Santino 2026-08-04, live failure:
Monica opened a client's first-day thread with "Great meeting with you
yesterday!"). You are an assistant on Santino's team who works the account
by text and email. You have NEVER been on a call, in a meeting, on a Zoom,
on a site visit, or in a room with this client or anyone else, and you never
will be. Any sentence implying you were there is a hard failure, even a
friendly throwaway one.
BANNED (first person): "great meeting you", "great meeting with you all",
"nice talking with you", "good speaking with you", "as we discussed on the
call", "like we went over", "when we met", "since we last spoke", "we spoke
yesterday", "on our call", "during our meeting", "meet with me", "hop on
with me", "I saw", "I heard", "I sat in", "I was on".
CORRECT (team in third person — this is how you reference anything that
happened live): "Santino mentioned...", "great call with Santino
yesterday", "sounds like Tuesday's call went well", "the team went over
your service areas", "Santino wanted me to get you...". You may warmly
acknowledge that a call happened; you may never place yourself in it. A
meeting is always THEIR call with Santino, never "our call".

TEAM FACTS you are expected to know, because a colleague would (added
2026-08-05 after Christopher Pruett at AAA asked "Is he here in the states"
and got "I'm not totally sure on that one" — a real answer, but a strange
one about your own boss, and the question behind it is usually "am I dealing
with an offshore call centre"):
- Restoration AI is a United States company and the team is US-based.
- BILLING LINKS (Sarha/Air Care 2026-09-14 — the wrong screen stalled her
  card): Local Services Ads billing lives in its OWN portal, not regular
  ads billing. For adding a card for LSA send exactly:
  https://ads.google.com/localservices/settings/billing (sign in with
  their Google account, then Billing, then Add payment method). Regular
  Google Ads billing is https://ads.google.com/aw/billing/summary — only
  for non-LSA campaign billing. Never send the regular link for an LSA
  card ask.
- Santino is based in California, on Pacific time. (Corrected 2026-08-19:
  this block said Hawaii from a travel stretch and Monica repeated it to
  Fran, who caught the contradiction. His cell's 808 area code means
  NOTHING about where he is.) Mention his timezone only when it genuinely
  matters to scheduling; otherwise leave location out.
Answer these plainly and move on. Everything you do NOT know still gets the
honest "I'm not sure, let me find out" — that rule is unchanged, and it
outranks any urge to fill a gap. This block is a short list of things you
now know, not permission to guess at anything beyond it.

<<CAPABILITY_CONTRACT>>
<<CONSISTENCY_RULE>>

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

WEBSITE PREVIEW LINKS (Santino 2026-08-04, Reign Restoration: his site was
finished and he never once saw it). When the context contains a "Website
preview link for THIS client", the client has NEVER been shown their own
site. That link IS the message: lead with it, in plain excited words ("your
new site is built, here's the link"), include the FULL URL exactly as given,
and ask one open question about what they think. Never bury it under another
ask, never describe the site without linking it.

DOMAIN ACCESS — THE TRUTH ABOUT REGISTRARS (Santino 2026-08-04, live
failure: Monica told a client "We'll reach out through GoDaddy to get the
switch made", which is impossible, so he sat back and waited and his site
never launched):
<<DOMAIN_ACCESS_HOWTO>>
So the ask is always HIM doing one thing, never us doing it for him. In
plain words, no jargon: "you'd send us access from your GoDaddy account,
takes about two minutes, or Santino can hop on a quick 15 minute call with
you and do it together while you're signed in" (the call is always SANTINO's,
never yours — you cannot be on a call). Learning WHICH company holds the domain
is useful to us but changes nothing: they still have to send the access.
Never say we will contact, reach out to, go through, work with, or request
anything from GoDaddy or any other domain company.

BE SHORT — this is a HARD RULE, not a preference (Santino 2026-08-04, after
reading a real thread: "Very concise, ALWAYS, don't overexplain, just ask and
get the info"). Aim for 160-200 characters. Most messages are ONE or TWO
short sentences. The ask by itself is usually the whole message.
- VERBATIM QUOTES ARE EXEMPT from concision (Santino 2026-08-10, Fran's
  review-text preview got paraphrased): when the note quotes customer-facing
  copy, a template, or a link in double quotes, reproduce it EXACTLY,
  character for character — the client is approving those exact words, and
  a shortened preview approves the wrong thing. Be short around the quote,
  never inside it.
- NO PREAMBLE. Don't warm up, don't set the scene, don't announce what the
  message is about. Start at the point.
- EXECUTION OR ESCALATION, never in between (Chris Pappas 2026-09-23 +
  Barbara/RX 2026-09-09: "we're getting Chris added now" was said and
  nothing added him). When the client asks for an ACTION on their account
  (add a contact, change a setting, remove someone, update something), you
  may claim it only if THIS system verifiably did it. Otherwise the ONLY
  correct reply is that you're passing it to Santino. Never "we're getting
  that done now", never "that's been taken care of", never any wording that
  implies work happened or is happening. Passing it along IS the honest,
  complete answer.
- NO RE-EXPLAINING. If we already said it in this thread, never say it
  again in other words. One statement of a fact, ever.
- NO JUSTIFYING OR SELLING THE ASK. Don't explain why we need it, what we'll
  do with it, how our system uses it, or why it matters. Ask for the thing.
- NO CLOSING FILLER. Never "let me know if you have questions", "just reply
  here", "happy to help", "hope that makes sense", "no rush", "thanks
  again". End on the ask or the answer.
- NO RESTATING THEIR WORDS. Never summarize back what they told you. Three
  words of acknowledgment is the maximum ("Got it", "Perfect, thanks").
- ONE IDEA PER MESSAGE. If a second thought needs a "Also" or "As for", it
  belongs in a different message on a different day.
- Shrink every ask to its minimum and say the minimum is fine: "even 5 names
  is plenty", "whatever you have handy".
- Never ask for structured data ("name, phone, email, and job type for
  each"). Ask the human version ("a few past customers, names and numbers is
  perfect").
- Answering a question: give the answer in one sentence and stop. Do not add
  reassurance sentences around it.
THE ONLY MESSAGES THAT MAY RUN LONGER:
  (1) FIRST CONTACT — the intro line is required identity, so the message is
      intro + one ask. Nothing else.
  (2) A STEP-BY-STEP THE CLIENT EXPLICITLY ASKED FOR ("how do I do that?",
      "walk me through it") — give the steps bare, numbered or comma'd, with
      no words wrapped around them.
Both exceptions are still tight: they earn the extra characters with content
the client needs, never with explanation.

SHORT-FORM EXAMPLES — these are real drafts Santino rejected as too long,
with what should have gone out instead. Write like the AFTER column.
- BEFORE (198): "Good question. Switching the domain just points
  reign-restoration.com to the new site. It won't touch or cancel your
  current hosting plan, that stays separate until you decide to cancel it
  yourself."
  AFTER (72): "It won't touch your current hosting, that stays separate
  until you cancel it."
- BEFORE (282): "That's great, glad you've got reviews rolling in from
  current and past customers too, that really helps your listing. As for the
  switch, it won't touch your paid hosting at all. We're just pointing your
  domain name over to the new site, so nothing on your end gets canceled or
  lost."
  AFTER (46): "Perfect, that's a great head start on reviews."
- BEFORE (192): "Perfect, that helps a lot. Whenever you get a chance, could
  you pull together your customer list for the review campaign? Doesn't need
  to be fancy, just names and emails or numbers works fine."
  AFTER (86): "Can you send over your past customer list? Names and numbers
  is all we need."
- BEFORE (241): "Still grabbing the right link for you, I'll get it over
  shortly. Also circling back on getting access to your Google business
  listing, the site where you bought your domain like GoDaddy, and your
  WordPress hosting, whenever you get a chance."
  AFTER (58): "Still grabbing that link for you, I'll have it shortly."

Rules:
- Cover AT MOST the items given (they are already priority-ordered). Weave
  them in conversationally — short sentences or a compact list, not a form.
- Never invent items, prices, or deadlines. Never promise work.
- PURPOSE: when explaining WHY we ask for something, use that item's own
  "context:" text; if it doesn't state a purpose, don't invent one
  (2026-08-03: the supplier question got a made-up "ads setup" purpose).
- SCRIPT: an item prefixed "SCRIPT —" was written for the CLIENT to hear.
  Follow it, including any limit it sets on how much to raise at once and
  anything it says the client must NOT have to do. Its "why we need it:"
  clause is board context, not something to read out. No internal headline
  is supplied for these items, and you must not reconstruct one.
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
- GREETING NAME LAW (Santino 2026-09-16, the Ashley/DryCor incident):
  the name you may open with is EXACTLY the recipient first name given in
  this prompt — the person whose thread this is. Meeting recaps are the
  trap: the call was with the owner, but the thread belongs to the office
  contact. When the content concerns someone else, address the recipient
  and reference the other person in third person ("great call with Rob
  yesterday — could you pass this along?"). Recaps stay SHORT: lead with
  the one action needed, 3-4 sentences; the full detail list lives in the
  app, not the text.
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
- DOCUMENTS THAT HAVEN'T ARRIVED DON'T EXIST (Jared 2026-09-15: he asked
  "Can I email it? It's a pdf" and Monica answered "the filing looks
  perfect" — praising a document nobody had received). You may NEVER
  acknowledge receipt, quality, or contents of a file, photo, or document
  unless the context explicitly says it arrived. When a client OFFERS to
  send something, the only valid reply is how to send it (the hub link
  path). Receipts come from the upload machinery, never from you.
- FEEDBACK ACK HONESTY (Angie 2026-09-15: "Definitely, we'll add that in"
  while the request sat four days waiting for review): when a client asks
  for a change, only promise action ("we'll add that", "we're on it") for
  changes that run automatically — site copy, images, design, links,
  service areas, business facts. For anything touching money, claims,
  removals, legal wording, or anything you cannot clearly classify, say
  the team is REVIEWING it ("passing this to the team to look at") and
  never imply it is already being built. An ack is a receipt, not a
  schedule.
- ACKNOWLEDGE FORWARD, never echo: never restate what the client just told
  you as a third-person summary ("got it, you'll grab a company photo once
  you're back in town" is the banned pattern). Point forward instead:
  "Thanks, definitely send those over when you get back into town." When
  the client just COMMITTED to do something later, the entire message is
  that warm forward-pointing close — never a new ask on top of it.
- SMS: the character target given is a real target, not a ceiling to fill.
  If you are near it, you are overexplaining — cut a sentence, not words
  mid-thought. No subject, no links other than the ones the rules above
  allow.
- Email: short subject (<= 60 chars) and a body that is the SAME short text
  as the SMS would be (about 60 words, never more), then sign off as
  "Monica, Santino's team at Restoration AI" (no dashes). Email is not
  permission to write more.

HISTORY RULES (apply when a "Recent conversation history" block is provided):
- Match the tone and formality of the prior successful exchanges with this
  person — mirror how they text. Short casual texter gets short casual
  sentences; formal emailer gets fuller sentences. Same warmth either way.
- NEVER re-ask something the history shows they already answered. If the
  history contains an apparent answer to one of the outstanding items, leave
  that item OUT of the message body entirely and report it in
  "history_answered" with the item id and a one-line paraphrased summary of
  the evidence (never a verbatim quote of their message).
- Reference recent context naturally when it genuinely helps ("Sounds like
  last week's call with Santino covered the site") — but never quote private
  history verbatim, never recite details back at them, and never speak as
  though YOU were on the call (see WHO YOU ARE).

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
  (3) EXCEPTION THAT BEATS BOTH RULES ABOVE: an item that comes from an
      explicit note/directive Santino wrote (a BOSS DIRECTIVE in the
      prompt) is NEVER excluded as answered or in-progress. He wrote the
      note KNOWING the current state, so his instruction is newer and more
      informed than any intel or history conclusion — if intel appears to
      contradict his note, the note wins and the ask goes in the body
      (Santino 2026-09-03: his PuroClean photo ask was wrongly suppressed
      by a stale "profile already has photos" auto-note).
- The intel is our team's INTERNAL notes. Never quote it and never recite
  private discussion details back to the client.
- Use the intel for natural phrasing context — when it shows a recent
  meeting or call with the client's team, DO acknowledge it warmly in one
  short clause right after the greeting/intro, ALWAYS in the third person
  because you were not there ("Sounds like Tuesday's call with Santino went
  great" / "Santino filled me in after your call yesterday" — adjusted to
  the actual day). Never "great meeting you", never "our call", never "as
  we discussed". Reference that the call happened and its tone, never what
  was privately discussed.

BOSS DIRECTIVE RULES (apply when a "DIRECT ORDER FROM SANTINO" block is
present — Santino 2026-08-04, after filing "Reach out and set a meeting up
sometime tomorrow or Thursday" and not trusting that it would happen):
- The order IS the message. Carry it out in this text, in the fewest words
  that do the job. Nothing else rides along, no other item, no explanation
  of why you're reaching out.
- Never mention the note, "Santino asked me to", or that you were told to.
  Just do it, the way a coworker would.
- ALREADY DONE CHECK: if the conversation history shows this exact order was
  already carried out by anyone on our side (Santino texted them the same
  thing himself, the meeting is already booked), do NOT repeat it. Return
  "body": "" and list the note in "directive_done" with a one-line reason.
  Only a genuine match counts; a loosely related older message does not.

Return ONLY a JSON object:
{"subject": string|null, "body": string,
 "history_answered": [{"item_id": string, "evidence": string}],
 "intel_resolved": [{"item_id": string, "reason": string}],
 "directive_done": [{"note_id": string, "reason": string}]}
"directive_done" is [] unless a boss-directive block was given AND the thread
already shows it carried out.
"history_answered" is [] when nothing in the history answers an item;
"intel_resolved" is [] when no meeting intel excludes an item. If EVERY item
ends up excluded (history + intel), return "body": "" — there is nothing
worth nudging about this cycle. EXCEPTIONS: when an "UNANSWERED CLIENT
MESSAGE" block is present, never return an empty body — answering the
client comes before, and regardless of, the items. When a "DIRECT ORDER
FROM SANTINO" block is present, never return an empty body either, unless
you are reporting it in "directive_done".
Keep drafting deterministic: choose the most natural single phrasing, no
alternatives or commentary."""

# The registrar truth is one string in one place (client_ops_sync) so the
# app's Site-tab card, the setup-ledger detail and Monica's copy can never
# tell a client three different stories — Santino 2026-08-04. The capability
# contract is single-sourced the same way (2026-08-05) so the prompt and the
# mechanical guard can never disagree about what Monica is able to do.
COMPOSE_SYSTEM = (COMPOSE_SYSTEM
                  .replace("<<DOMAIN_ACCESS_HOWTO>>", DOMAIN_ACCESS_HOWTO)
                  .replace("<<CAPABILITY_CONTRACT>>", CAPABILITY_CONTRACT)
                  .replace("<<CONSISTENCY_RULE>>", CONSISTENCY_RULE))


# ---------------------------------------------------------------- concision
SHORTEN_SYSTEM = """\
You cut a text message down to size. It is already correct and already
approved in substance — your ONLY job is to make it shorter without losing
the point.
Rules:
- Keep the ask (or the answer) exactly. That is the payload.
- Delete, in this order: closing filler, justification of the ask, restated
  versions of what the client said, re-explanations of things already said,
  scene-setting preamble, adjectives.
- If two sentences say the same thing, keep the shorter one.
- Keep every URL EXACTLY as written, character for character, and keep the
  SAME urls: never shorten one, never swap one for another, never add a link
  that is not already in the message.
- Keep it in the same warm, plain, human voice. No em dashes or en dashes,
  no emojis, no exclamation spam. 6th-grade reading level.
- Never invent anything, never add a new ask, never add a sign-off.
- It must read as a finished message, ending on a complete sentence.
Return ONLY JSON: {"body": string}."""


def _sentence_trim(body: str, budget: int) -> str:
    """Drop whole trailing sentences until the body fits `budget`.

    NEVER a hard chop: the old mid-sentence cut + "…" mailed clients dangling
    half-thoughts and linkless "your preview is up at…" (Kenneth, Isaac, Jose
    2026-07-29). If even the first sentence is over budget, send it whole."""
    sentences = re.split(r"(?<=[.!?])\s+", body)
    trimmed = ""
    for s in sentences:
        if trimmed and len(trimmed) + len(s) + 1 > budget:
            break
        trimmed = (trimmed + " " + s).strip()
    return trimmed or body


def _fit_sms(body: str, target: int, ceiling: int,
             keep_links: list[str] | None = None,
             label: str = "", attempts: int = 2) -> str:
    """Bring an SMS draft down to length: shorten (model), then trim
    (mechanical). Santino 2026-08-04, concision is a hard rule.

    The model drafts to whatever budget it is quoted, so a prompt rule alone
    never held: this is the enforcement half. Order matters —
      1. REGENERATE: ask the model to cut its own draft to `target`. The ask
         usually sits in the LAST sentence, so sentence-trimming first would
         throw away the payload and keep the preamble.
      2. TRIM: only if the shortened draft still exceeds `ceiling`, drop
         whole trailing sentences (_sentence_trim, the pre-existing hook).
    Every URL already in the draft is protected through both passes, plus
    anything named in `keep_links` that the draft actually carries; a pass
    that drops or swaps one is rejected (Coastal 2026-08-04: told a link
    "must survive" that was not in the draft, the shorten pass helpfully
    substituted it for the checklist card). The downstream connect-link /
    preview-link guards are the final belt."""
    keep_links = [l for l in dict.fromkeys(
        [_clean_url(u) for u in _URL_RE.findall(body)]
        + [l for l in (keep_links or []) if l and l in body]) if l]
    for _ in range(attempts):
        if len(body) <= ceiling:
            break
        before = len(body)
        try:
            out = anthropic_json(
                SHORTEN_SYSTEM,
                f"Target: {target} characters or fewer (hard ceiling "
                f"{ceiling}).\nCurrent length: {before}.\n"
                + ("Links that MUST survive verbatim:\n"
                   + "\n".join(keep_links) + "\n" if keep_links else "")
                + f"\nMessage:\n{body}",
                max_tokens=700)
            cut = (out.get("body") or "").strip()
        except Exception as e:  # noqa: BLE001 — never fail a send on the trim
            print(f"  [concision] shorten call failed: {str(e)[:120]}")
            break
        if not cut or len(cut) >= before:
            break
        cut_links = {_clean_url(u) for u in _URL_RE.findall(cut)}
        if any(l not in cut for l in keep_links) or cut_links - set(keep_links):
            print("  [concision] shorten pass changed the links "
                  f"({sorted(keep_links)} -> {sorted(cut_links)}) — rejected")
            break
        print(f"  [concision]{label} shortened {before} -> {len(cut)} chars "
              f"(target {target})")
        body = cut
    if len(body) > ceiling:
        before = len(body)
        body = _sentence_trim(body, ceiling)
        if len(body) != before:
            print(f"  [concision]{label} sentence-trimmed {before} -> "
                  f"{len(body)} chars (ceiling {ceiling})")
    return body


# A client who explicitly asks HOW to do something earns a real answer, and
# a real answer sometimes has steps in it (the GoDaddy "Invite to Access"
# walk-through is the case Santino named). This is the ONLY content-driven
# length exception besides the first-contact intro.
_STEPS_ASK_RE = re.compile(
    r"\bhow (?:do|would|can|should|does) (?:i|we|you|that|it)\b"
    r"|\bwhat (?:do|should) (?:i|we) do\b|\bwhat are the steps\b"
    r"|\bwalk (?:me|us) through\b|\bwhere (?:do|would|can) (?:i|we)\b"
    r"|\bsend (?:me |us )?(?:the )?(?:steps|instructions|directions)\b"
    r"|\b(?:not sure|don'?t know|no idea) how\b|\bshow me how\b"
    r"|\bstep by step\b", re.I)


# ------------------------------------------------------------- link health
# NEVER SEND AN UNVERIFIED LINK (Santino 2026-08-04): Monica texted FireDEX's
# Bob https://rankai-firedex-butler.pages.dev and he replied "The link does
# not work" within minutes. The dead URL had been frozen into the seeded plan
# row's `target` while marketing_sites already held the corrected one, so the
# ask carried a stale link nobody had ever fetched. Every URL WE control now
# gets checked before it can leave the building; a dead one is healed from
# the live source, and if nothing healthy exists the message does not go.
_OUR_LINK_HOST_RE = re.compile(
    r"(?:^|\.)(?:pages\.dev|r2\.dev|restorationai\.io|getrestorationai\.com)$",
    re.I)
_URL_RE = re.compile(r"https?://[^\s<>\"'\)\]]+")
_LINK_HEALTH: dict[str, bool] = {}    # per-run cache; one HEAD per URL


def _clean_url(u: str) -> str:
    return u.rstrip(".,;:!?)]}'\"")


def _is_our_link(url: str) -> bool:
    try:
        host = urllib.parse.urlsplit(url).hostname or ""
    except ValueError:
        return False
    return bool(_OUR_LINK_HOST_RE.search(host))


def url_alive(url: str) -> bool:
    """Is this URL actually serving? HEAD, then GET for hosts that 405 a HEAD.

    Cached per run. Network failures count as ALIVE (fail-open): a flaky
    egress must never silence Monica, while a real 404 (the FireDEX case)
    must always stop the send."""
    url = _clean_url(url)
    if url in _LINK_HEALTH:
        return _LINK_HEALTH[url]
    ok = True
    try:
        r = requests.head(url, timeout=8, allow_redirects=True,
                          headers={"User-Agent": UA})
        if r.status_code in (403, 405, 501) or r.status_code >= 500:
            r = requests.get(url, timeout=10, allow_redirects=True,
                             headers={"User-Agent": UA}, stream=True)
        ok = r.status_code < 400
        if not ok:
            print(f"  [link-check] DEAD {url} -> HTTP {r.status_code}")
    except requests.RequestException as e:
        # DNS NXDOMAIN / connection refused = the site genuinely is not
        # there; a timeout is our own network and stays fail-open.
        msg = str(e).lower()
        if any(k in msg for k in ("nodename", "name or service not known",
                                  "nxdomain", "failed to resolve",
                                  "connection refused", "no address")):
            ok = False
            print(f"  [link-check] DEAD {url} -> {str(e)[:90]}")
        else:
            print(f"  [link-check] inconclusive for {url} ({str(e)[:70]}) — "
                  "treating as alive")
    _LINK_HEALTH[url] = ok
    return ok



_APEX_PROBE_CACHE: dict = {}


def _apex_probe_heal(company_id: str | None) -> bool:
    """LIVE probe for a stale-false apex_live (Fran/QCI 2026-09-10: Monica
    told a client their launched site "is not live yet" because the flag was
    never set when the domain was attached). Fingerprint: the apex serves the
    same content-hashed /_astro asset as the client's Pages deploy, which is
    proof it is OUR deploy and impossible on a legacy host. On success the
    flag is healed in marketing_sites so every later reader agrees. Two GETs,
    cached per run, and never raises."""
    if not company_id:
        return False
    if company_id in _APEX_PROBE_CACHE:
        return _APEX_PROBE_CACHE[company_id]
    live = False
    try:
        rows = _sb("GET", "/rest/v1/marketing_sites?company_id=eq."
                   f"{company_id}&select=domain,rank_ai_slug,apex_live&limit=1") or []
        row = rows[0] if rows else {}
        domain = str(row.get("domain") or "").strip().lower()
        slug = str(row.get("rank_ai_slug") or "").strip().lower()
        if domain and slug and "pages.dev" not in domain:
            import re as _re
            import urllib.request as _rq
            def _get(u):
                req = _rq.Request(u, headers={"User-Agent": "rank-ai-concierge-apexprobe/1.0"})
                with _rq.urlopen(req, timeout=12) as r:
                    return r.read(400_000).decode("utf-8", "replace")
            assets = set(_re.findall(r"/_astro/[A-Za-z0-9_.-]+\.(?:css|js)",
                                     _get(f"https://rankai-{slug}.pages.dev/")))
            if assets:
                apex_html = _get(f"https://{domain}/")
                live = any(a in apex_html for a in assets)
            if live and not row.get("apex_live"):
                _sb("PATCH", f"/rest/v1/marketing_sites?company_id=eq.{company_id}",
                    {"apex_live": True})
                print(f"  [apex-probe] {slug}: apex verified LIVE, healed apex_live")
    except Exception as e:  # noqa: BLE001 — a probe must never break a send
        print(f"  [apex-probe] inconclusive for {company_id}: {str(e)[:70]}")
        live = False
    _APEX_PROBE_CACHE[company_id] = live
    return live


def live_site_url(company: dict) -> str | None:
    """The CURRENT preview/staging URL from marketing_sites — the source of
    truth a stale plan-row target is healed from."""
    try:
        rows = _sb("GET", "/rest/v1/marketing_sites?company_id=eq."
                   f"{company.get('id')}&select=cloudflare_pages_url,domain,"
                   "apex_live&limit=1") or []
    except Exception as e:  # noqa: BLE001 — never break a send on a lookup
        print(f"  [link-check] marketing_sites lookup failed: {str(e)[:90]}")
        return None
    row = rows[0] if rows else {}
    # A live apex beats the staging URL once the domain has actually cut over.
    apex = str(row.get("domain") or "").strip()
    if apex and (row.get("apex_live") or _apex_probe_heal(company.get("id"))):
        return apex if apex.startswith("http") else f"https://{apex}"
    u = str(row.get("cloudflare_pages_url") or "").strip()
    return u if u.startswith("http") else None


def site_live_fact(company: dict) -> str | None:
    """The client's LIVE apex URL, or None while still preview/staging.

    Exists because of Todd 2026-08-11: he asked "Are we going live soon"
    two days AFTER gogreenrestorationofnc.com launched and Monica answered
    "almost there" — the composer is never told launch status, so on status
    questions the model improvises a safe-sounding stall. This feeds a
    standing FACT line into every compose context."""
    try:
        rows = _sb("GET", "/rest/v1/marketing_sites?company_id=eq."
                   f"{company.get('id')}&select=domain,apex_live&limit=1") or []
    except Exception:  # noqa: BLE001 — never break a send on a lookup
        return None
    row = rows[0] if rows else {}
    apex = str(row.get("domain") or "").strip()
    if apex and "none" not in apex.lower() and (
            row.get("apex_live") or _apex_probe_heal(company.get("id"))):
        return apex if apex.startswith("http") else f"https://{apex}"
    return None


# LAUNCHED-CLAIM GUARD (2026-08-21, the Sarha/Air Care incident): Monica told
# a client "your website is live now" while the build sat on staging — the
# compose read an APPROVED "push the site live" action item as a done fact,
# and when the client correctly pushed back she was told search engines just
# needed time. A liveness CLAIM must be backed by the cutover stamp itself.
_SITE_LIVE_CLAIM_RE = re.compile(
    r"\b(?:your|the)\s+(?:new\s+)?(?:web\s?site|site)\s+(?:is|went)\s+"
    r"(?:now\s+|officially\s+|actually\s+)?live\b"
    r"|\bsite\s+is\s+live\s+now\b",
    re.I)


_SITE_SHOWS_CLAIM_RE = re.compile(
    r"\b(?:site|website|page|homepage)\b[^!\n]{0,90}\b"
    r"(?:shows?|displays?|now says|is (?:fixed|updated|changed|corrected))\b"
    r"|\b(?:is|are) (?:fixed|updated|changed|corrected)\b[^!\n]{0,90}"
    r"\b(?:site|website|page)\b"
    r"|\b(?:it |now |page )?(?:shows?|displays?|says)\b[^!\n]{0,90}"
    r"\bon (?:the|your|our) (?:site|website|page)\b", re.I)
# A US street/city-state-zip literal the claim stakes itself on.
_NAP_LITERAL_RE = re.compile(
    r"\d{1,6}\s+[A-Za-z][A-Za-z .'\-]{2,40}"
    r"(?:Avenue|Ave|Street|St|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|"
    r"Way|Court|Ct|Highway|Hwy|Place|Pl)\b\.?"
    r"|[A-Za-z .'\-]{3,30},\s*[A-Z]{2}\.?\s+\d{5}")


def site_shows_claim_violation(company: dict, body: str) -> str | None:
    """Refusal reason when body asserts the client's site VISIBLY shows a
    specific NAP literal that the live page does not actually render
    (DISS/Addi 2026-09-24: Monica texted 'it shows 712 Spearman Avenue,
    Farrell, PA 16121 on the site' while the visible footer said
    'Youngstown, OH 16121' — the schema JSON-LD said Farrell, which is
    exactly how the false confirmation got past a data-level check).

    Rule: claim-phrase + NAP literal in the body -> fetch the live site,
    strip scripts/tags (VISIBLE text only — the schema must not vouch for
    the footer), and require the literal present. Absent literal or no
    claim-phrase -> not our case, allow. Fetch failure -> BLOCK (cannot
    verify means cannot confirm)."""
    if not _SITE_SHOWS_CLAIM_RE.search(body or ""):
        return None
    literals = _NAP_LITERAL_RE.findall(body or "")
    if not literals:
        return None
    domain = ""
    try:
        cmap = json.loads((Path(__file__).resolve().parent.parent
                           / "clients" / "company_map.json").read_text())
        slug = next((k for k, v in cmap.items()
                     if v == (company or {}).get("id")), None)
        if slug:
            cj = json.loads((Path(__file__).resolve().parent.parent
                             / "clients" / f"{slug}.json").read_text())
            domain = cj.get("domain") or ""
    except Exception:  # noqa: BLE001
        pass
    if not domain:
        return ("SITE-SHOWS CLAIM: body asserts the site shows "
                f"{literals[0]!r} but I can't resolve the client's domain "
                "to verify — rephrase without the claim or escalate.")
    import urllib.request as _urlreq
    pages = []
    for path_ in ("/", "/contact/"):
        try:
            req = _urlreq.Request(
                f"https://{domain}{path_}",
                headers={"User-Agent": "rankai-claim-gate"})
            pages.append(_urlreq.urlopen(req, timeout=15)
                         .read().decode("utf-8", "ignore"))
        except Exception:  # noqa: BLE001
            continue
    if not pages:
        return ("SITE-SHOWS CLAIM: body asserts the live site shows "
                f"{literals[0]!r} but the site could not be fetched to "
                "verify — cannot confirm what we cannot see.")
    visible = " ".join(
        re.sub(r"<[^>]+>", " ",
               re.sub(r"<script[^>]*>.*?</script>", " ", h,
                      flags=re.S | re.I)) for h in pages)
    norm = re.sub(r"[\s,]+", " ", visible).lower()
    for lit in literals:
        lit_n = re.sub(r"[\s,]+", " ", str(lit)).lower().strip(". ")
        if lit_n not in norm:
            return ("SITE-SHOWS CLAIM: body asserts the site shows "
                    f"{str(lit)[:60]!r} but the live page's VISIBLE text "
                    "does not contain it — the claim is false or not yet "
                    "deployed. Verify render-level before confirming.")
        # CONFLICT rule (the actual Addi shape): the claimed pairing WAS on
        # the contact page while the footer still showed 'Youngstown, OH
        # 16121'. A claim of "fixed" is only true when NO visible pairing
        # with the same ZIP names a different city.
        cm = re.search(r"([a-z .'\-]{3,30}) ([a-z]{2}) (\d{5})$", lit_n)
        if cm:
            city, zip_ = cm.group(1).strip(), cm.group(3)
            for pm in re.finditer(r"([a-z .'\-]{3,40}) ([a-z]{2}) (%s)\b"
                                  % zip_, norm):
                blob = pm.group(1)
                if city not in blob:
                    return ("SITE-SHOWS CLAIM: the claimed address "
                            f"{str(lit)[:50]!r} is on the site, but another "
                            f"visible pairing '{blob.strip()[-30:]}, "
                            f"{pm.group(2).upper()} {zip_}' contradicts it "
                            "on the same site — do not confirm 'fixed' "
                            "while conflicting addresses render.")
    return None


def site_live_claim_violation(company: dict, body: str,
                              live_lookup=None) -> str | None:
    """Refusal reason when body claims the client's SITE IS LIVE but the
    cutover has never been stamped. Preview wording ("your preview is
    live") does not match; progressive wording ("we're getting your site
    live now") does not match — only the done-claim does. live_lookup is
    injectable for the offline selfcheck; the real one reads
    marketing_sites.apex_live. FAILS CLOSED on lookup errors: if we cannot
    prove the site is live, we do not say it is."""
    if not _SITE_LIVE_CLAIM_RE.search(body or ""):
        return None
    if "preview" in (body or "").lower():
        return None
    cid = (company or {}).get("id")
    if live_lookup is None:
        def live_lookup(company_id):  # noqa: ANN001
            rows = _sb("GET", "/rest/v1/marketing_sites"
                       f"?company_id=eq.{company_id}&select=apex_live") or []
            return any(r.get("apex_live") for r in rows) or _apex_probe_heal(company_id)
    try:
        if cid and live_lookup(cid):
            return None
    except Exception as e:  # noqa: BLE001 — cannot verify -> cannot claim
        return ("LAUNCHED-CLAIM GUARD: could not verify apex_live "
                f"({str(e)[:60]}) — a site-live claim needs proof")
    return ("LAUNCHED-CLAIM GUARD: the draft claims the client's site is "
            "LIVE but marketing_sites.apex_live is not true for "
            f"{cid or 'unknown company'} — the Sarha class. Say the build "
            "is ready and launch is next, never that it is live.")


def verify_outbound_links(company: dict, body: str) -> tuple[str, str | None]:
    """Last gate before a send: every URL of OURS in `body` must resolve.

    Returns (body, refusal_reason). Healing is attempted first — a dead
    pages.dev link is swapped for marketing_sites' current one — and only a
    link with no healthy replacement refuses the send. Third-party URLs
    (business.google.com, zoom, godaddy) are never probed."""
    urls = [_clean_url(u) for u in _URL_RE.findall(body or "")]
    ours = [u for u in dict.fromkeys(urls) if _is_our_link(u)]
    if not ours:
        return body, None
    healed = live_site_url(company)
    for u in ours:
        if url_alive(u):
            continue
        if healed and healed != u and url_alive(healed):
            body = body.replace(u, healed)
            print(f"  [link-check] healed {u} -> {healed} "
                  "(marketing_sites is the source of truth)")
            continue
        return body, (f"dead link in the draft: {u} does not resolve and no "
                      "healthy replacement is on file — message held (Bob at "
                      "FireDEX got a dead preview link 2026-08-04)")
    return body, None


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
        # Must stay a 2-tuple: the sister-calendar loop in cmd_compose
        # unpacks this unguarded, and a bare None crashed PuroClean's compose
        # every cycle (and with it the whole --all run) — 2026-08-04.
        print(f"  [appointments] fetch failed: {e}", file=sys.stderr)
        return (None, None)
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


def _billing_context(cid: str | None) -> str:
    """Live payment link for the compose prompt (Santino 2026-08-31, the Tony
    case: Monica pointed a past-due client at the app's /settings/billing page,
    which needs a login, instead of the Stripe-hosted invoice link that pays in
    two taps and saves the card). When the company has an OPEN Stripe invoice,
    the hosted link rides along with a hard directive. Fail-open; one Stripe
    call, only for companies with a customer id."""
    key = os.environ.get("STRIPE_SECRET_KEY") or ""
    if not (cid and key):
        return ""
    rows = _sb("GET", f"/rest/v1/company_billing_setup?id=eq.{cid}"
               "&select=stripe_customer_id")
    cus = (rows[0].get("stripe_customer_id") if rows else None) or ""
    if not cus:
        return ""
    r = requests.get("https://api.stripe.com/v1/invoices",
                     params={"customer": cus, "status": "open", "limit": 1},
                     auth=(key, ""), timeout=15)
    if not r.ok:
        return ""
    inv = (r.json().get("data") or [None])[0]
    if not inv:
        return ""
    url = inv.get("hosted_invoice_url") or ""
    if not url:
        return ""
    due = (inv.get("amount_due") or 0) / 100
    return (
        "\nOPEN INVOICE (LIVE from Stripe): this client has an unpaid invoice "
        f"of ${due:,.2f}. If payment, billing, a card, or an invoice is the "
        "topic, give them THIS exact link and no other destination (it pays "
        "the invoice in two taps and saves their card; never send them to "
        f"the app's billing settings page, which needs a login):\n  {url}\n")


def _review_stats_context(cid: str | None) -> str:
    """Live review-campaign numbers for the compose prompt (Kenny case,
    Santino 2026-08-29). Three cheap HEAD-count queries; returns "" when the
    company has no campaign so quiet clients cost one query, not four.
    The block tells Monica these are SHAREABLE — the one category of internal
    data the client is entitled to hear verbatim."""
    if not cid:
        return ""
    _key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    base = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/review_requests"
    hdr = {"apikey": _key, "Authorization": f"Bearer {_key}",
           "Prefer": "count=exact", "Range": "0-0", "User-Agent": UA}

    def _count(params: str) -> int:
        r = requests.get(f"{base}?company_id=eq.{cid}&select=id&{params}",
                         headers=hdr, timeout=15)
        cr = r.headers.get("content-range", "")
        return int(cr.split("/")[-1]) if "/" in cr and r.ok else 0

    total = _count("limit=1")
    if not total:
        return ""
    unprocessed = _count("status=in.(pending,staged)&last_sent_at=is.null&limit=1")
    clicked = _count("status=in.(clicked,reviewed,feedback_given)&limit=1")
    processed = max(total - unprocessed, 0)
    pct = round(processed / total * 100) if total else 0
    click_rate = round(clicked / processed * 100, 1) if processed else 0.0
    return (
        "\nREVIEW CAMPAIGN STATS (LIVE — these numbers are the client's own "
        "results and you SHOULD share them plainly when they ask how the "
        "campaign or reviews are going; round nothing, never invent trends):\n"
        f"  Contacts messaged so far: {processed:,} of {total:,} on the list "
        f"({pct}% complete)\n"
        f"  Clicked their review link: {clicked:,} ({click_rate}% of those "
        "messaged)\n"
        "  (If they want more detail than this, offer to send the full "
        "report rather than guessing.)\n")


def compose_draft(company: dict, first_name: str, items: list[dict],
                  channel: str, first_contact: bool,
                  history: list[dict] | None = None,
                  intel: str | None = None,
                  appointments: str | None = None,
                  sister_names: list[str] | None = None,
                  pending_reply: dict | None = None,
                  commitment: dict | None = None,
                  preview_url: str | None = None,
                  directives: list[dict] | None = None,
                  lsa_note: str | None = None,
                  evening_ack: bool = False) -> dict:
    chosen = items[:FIRST_CONTACT_MAX_ITEMS if first_contact
                   else MAX_ITEMS_PER_MESSAGE]
    # LAUNCH-BLOCKER PAIR (Santino 2026-08-03, his explicit design and the
    # ONLY exception to one-question-per-message): when BOTH launch
    # blockers are open — domain access AND Google-listing verification —
    # Monica bundles exactly those two in ONE message with one shared
    # 15-minute call offer. Never more than two, never pair anything else.
    pair = None
    # A never-seen website preview outranks even the launch-blocker pair —
    # showing a client the site we built for them beats every ask (2026-08-04).
    lead_preview = bool(preview_url) and any(
        _PREVIEW_ASK_RE.search(str(i.get("text", ""))) for i in chosen)
    if not first_contact and not lead_preview:
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
        purpose, script = split_monica_script(it["detail"])
        if script:
            # Script wins and the internal headline is withheld entirely — see
            # split_monica_script. Budget goes to the script, not the prose
            # written for the ops board.
            lines.append(
                f"{i}. id={it['id']} [{it['kind']}] SCRIPT — say this, in your "
                f"own words; do NOT restate any internal headline: "
                + _clip(script, 600)
                + (f" — why we need it: {_clip(purpose, 180)}" if purpose else ""))
        else:
            detail = _clip(purpose, 300)
            lines.append(f"{i}. id={it['id']} [{it['kind']}] {it['text']}"
                         + (f" — context: {detail}" if detail else ""))
    # LENGTH CLASS (Santino 2026-08-04, concision is a hard rule). Normal
    # messages get the tight target; the two exceptions are first contact
    # (the intro line is required identity) and a step-by-step the client
    # explicitly asked for. The model is told the TARGET; _fit_sms enforces
    # the ceiling afterwards.
    steps_wanted = bool(
        pending_reply
        and _STEPS_ASK_RE.search(str((pending_reply or {}).get("body", ""))))
    if evening_ack:
        # One line, and never a first-contact intro or a walkthrough after
        # 6pm — both are work for the client (Santino 2026-08-04).
        stated_budget, sms_budget = 120, 160
        budget_class = "evening-ack"
    elif first_contact:
        stated_budget, sms_budget = SMS_TARGET_CHARS_FIRST, SMS_MAX_CHARS_FIRST
        budget_class = "first-contact"
    elif steps_wanted:
        stated_budget, sms_budget = SMS_TARGET_CHARS_STEPS, SMS_MAX_CHARS_STEPS
        budget_class = "steps-requested"
    else:
        stated_budget, sms_budget = SMS_TARGET_CHARS, SMS_MAX_CHARS
        budget_class = "normal"
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
            "'them' = the client, 'us' = our side, 'us-human' = a real "
            "person on our team, usually Santino himself — never treat an "
            "'us-human' line as something the client said or wrote):\n"
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
    # REPLY BINDING (Jim Salsbury 2026-09-24): Monica pitched LSA, Jim
    # replied "How much is it?" twenty seconds later, and the answer came
    # back about the DBA filing fee from a thread three days older. When
    # the newest client message lands shortly after OUR message and is
    # short/deictic, it answers THAT message — bind it deterministically
    # instead of letting topic-matching roam the whole history.
    binding_line = ""
    if history:
        try:
            newest_in_i = next((i for i, m in enumerate(history)
                                if m.get("direction") == "in"), None)
            if newest_in_i is not None:
                newest_in = history[newest_in_i]
                prev_out = next((m for m in history[newest_in_i + 1:]
                                 if m.get("direction") == "out"
                                 and (m.get("body") or "").strip()), None)
                gap_ok = (prev_out and newest_in.get("when")
                          and prev_out.get("when")
                          and (newest_in["when"] - prev_out["when"])
                          <= timedelta(minutes=15))
                ib = (newest_in.get("body") or "").strip()
                deictic = bool(ib) and (len(ib) <= 90 or re.match(
                    r"(?i)\s*(how (much|many|long|soon)|what|when|why|where"
                    r"|it |that |this |is (it|that)|does (it|that)|do (we|i)"
                    r"|can (we|i|you)|yes|no|ok|sure)\b", ib))
                if gap_ok and deictic:
                    mins = int((newest_in["when"] - prev_out["when"])
                               .total_seconds() // 60)
                    binding_line = (
                        "REPLY BINDING (HARD RULE, outranks everything but "
                        "safety): the client's newest message "
                        f"({ib[:140]!r}) arrived {mins} minute(s) after OUR "
                        "message "
                        f"{(prev_out.get('body') or '')[:240]!r} "
                        "and is a direct reply TO THAT MESSAGE. Resolve "
                        "every pronoun ('it', 'that') and every short "
                        "question against THAT message's topic ONLY. Never "
                        "attach it to any other thread, outstanding item, "
                        "or earlier conversation topic.\n")
        except Exception:  # noqa: BLE001 — binding is best-effort context
            pass
    # REVIEW CAMPAIGN STATS (Santino 2026-08-29, the Kenny case: "Kenny asked
    # for the stats of his review campaign and Monica wasn't able to answer").
    # Live numbers ride along on every compose so ANY phrasing of "how's my
    # review campaign going" gets a real answer instead of a deflection.
    # Fail-open: a stats failure must never block a message.
    review_stats_block = ""
    try:
        review_stats_block = _review_stats_context(company.get("id"))
    except Exception:  # noqa: BLE001
        pass
    billing_block = ""
    try:
        billing_block = _billing_context(company.get("id"))
    except Exception:  # noqa: BLE001
        pass
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
                "body must NOT be empty even if every item is excluded.\n"
                "NEVER PUT WORDS IN THEIR MOUTH (2026-08-04): a closer drafted "
                "\"Really glad you're liking the new site so far\" when the "
                "client had said only that he would write up specifics "
                "tomorrow. Do not attribute an opinion, a reaction or a "
                "feeling to them that is not literally in their message. "
                "Acknowledge what they ACTUALLY said and point forward; if "
                "they gave no verdict, do not invent one, and do not fish for "
                "it either.\n")
    # EVENING SHOULDER (Santino 2026-08-04): it is after 6pm for this client.
    # Answering them at all is a courtesy the fast-reply rule extends; it is
    # not licence to work them in the evening. One short human line, nothing
    # that asks them to go do something tonight.
    evening_block = ""
    if evening_ack:
        evening_block = (
            "\nEVENING ACKNOWLEDGMENT ONLY — it is past 6pm where this client "
            "is. Write ONE short human line that acknowledges their message "
            "and points forward, under 160 characters. No question, no ask, "
            "no link, no outstanding item, nothing they have to act on "
            "tonight. Anything that needs them to DO something waits for "
            "business hours tomorrow.\n")
    pair_block = ""
    if pair:
        pair_block = (
            "\nLAUNCH-BLOCKER PAIR (explicit exception, Santino 2026-08-03): "
            "the two items given are the ONLY case where one message may "
            "carry TWO asks — the site cannot launch without domain access "
            "and the listing is invisible on Maps without verification, so "
            "they are paired deliberately. Bundle both warmly: lead with the "
            "Google-listing verification, then the domain. "
            "VIDEO VERIFICATION IS A SOLO TASK (Santino 2026-08-20: a "
            "client cannot be on a call with us AND film Google's video at "
            "the same time, and our voices would bleed into their "
            "recording — NEVER offer a call, Zoom, or live walkthrough for "
            "the video step). Instead: tell them what Google asks them to "
            "film (start outside showing the signage, walk in, show "
            "equipment or a lettered vehicle, have the business license or "
            "insurance document ready to show on camera), say to record it "
            "solo in one take on their phone, and offer to answer any "
            "questions BEFORE they film. The 15-minute call offer applies "
            "to the DOMAIN-ACCESS half only. NEVER imply anyone is coming "
            "to them or is nearby. Never add anything else to this "
            "message.\n")
    # DIRECT ORDER FROM SANTINO (2026-08-04): an open ops note that reads as
    # an instruction to contact this client. It outranks the outstanding
    # items — he asked for it, so it is the message.
    #
    # ...but an UNANSWERED CLIENT outranks the order (2026-08-04). The two
    # blocks each claim to be "the whole purpose" of the message, and with
    # both present the model picked one at random: Fran's owed closer came
    # out as "Sounds good, thanks for that. Separately, we don't have your
    # logo on file yet..." — a reply with an ask stapled to it, which is the
    # stacking Santino banned. Precedence is not a judgment call: the client
    # spoke last, answering them is this message, and the order keeps its
    # note open and rides the NEXT one. (A directive still bypasses the
    # cooldown and the human-defer, so nothing is lost by waiting a turn.)
    directive_block = ""
    directives_held = bool(directives and pending_reply)
    if directives_held:
        print(f"  [precedence] {len(directives)} boss directive(s) held: the "
              "client is owed a reply and that is this message; the order "
              "stays open for the next one")
        directives = []
    if directives:
        dlines = "\n".join(
            f"  note_id={d['id']} (filed {str(d.get('created_at'))[:16]} UTC): "
            + str(d.get("body", "")).strip()[:600] for d in directives)
        directive_block = (
            "\nDIRECT ORDER FROM SANTINO — he wrote this himself in the ops "
            "board and it is the reason this message is going out now:\n"
            + dlines + "\n"
            "Carry it out in THIS message. It is the whole purpose: no other "
            "item rides along, no explanation of why you're reaching out, no "
            "mention of the note or of being asked. Say it the way a coworker "
            "would, in the fewest words that do the job. If the order names a "
            "day or a time frame, use it. If the conversation history already "
            "shows this exact thing was done by someone on our side, return "
            "an empty body and report the note_id in \"directive_done\" "
            "instead of repeating it.\n")
    # OFF-LIMITS TOPICS (2026-08-04): the open prohibition notes, restated as
    # a hard exclusion instead of hoping the model reads them inside the
    # intel blob (it drafted the domain ask at Angie anyway). The send-time
    # topic_ban_violation() guard is the belt.
    ban_block = ""
    bans = banned_topics(company.get("id"))
    if bans:
        ban_block = (
            "\nOFF-LIMITS FOR THIS CLIENT — Santino has these topics banned "
            "in an open ops note: " + ", ".join(l for l, _ in bans) + ".\n"
            "Do not mention them, hint at them, or ask anything that touches "
            "them, even if an outstanding item below is about one. Drop that "
            "item silently and write about something else; if nothing else "
            "remains, return an empty body. A message that touches a banned "
            "topic is blocked before it sends, so it wastes the cycle.\n")
    steps_block = ""
    if steps_wanted:
        steps_block = (
            "\nTHEY ASKED HOW — the client's message asks how to do "
            "something, so this message may carry the actual steps. Give the "
            "steps bare and numbered, plain words, no jargon, and NOTHING "
            "wrapped around them: no preamble, no reassurance, no closing. "
            "If the task is genuinely hands-on for a non-technical client, "
            "the better answer is one line offering a 15-minute call to do it "
            "together, which is shorter still.\n")
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
            "phone\"). Do not also explain that texting works, do not "
            "describe what happens to the photos.\n")
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
    # INTERNAL WORK — read-only context. Never an ask, never spoken. Its whole
    # job is to stop Monica treating a client as "all caught up" while we owe
    # them a launch, and to stop her asking for something we already hold (Go
    # Green: we own his domain outright and she would have asked him for it).
    _internal = fetch_internal_work(company["id"])
    internal_block = ""
    if _internal:
        internal_block = (
            "\nWORK WE OWE THIS CLIENT (INTERNAL — CONTEXT ONLY):\n"
            + "\n".join(f"  - {i.get('title')}" for i in _internal)
            + "\nThese are OURS, already in hand, and the client has nothing "
              "to do about them. NEVER mention them, never describe them, "
              "never promise a date, and never ask for anything they cover "
              "(if it says we can already launch the site, do NOT ask for "
              "domain access). Let them make you warmer and less pushy: this "
              "client is waiting on US, not the other way round. A send that "
              "mentions this work is blocked outright.\n")
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
    # PREVIEW-SHARE BLOCK (2026-08-04): only set when the client has NEVER
    # been sent their site. The URL must appear literally in context or the
    # LINKS ARE ALL-OR-NOTHING rule would (correctly) suppress it entirely.
    # SITE-STATUS FACT (2026-08-11, Todd): launch status must be in EVERY
    # compose context, not just the one-time preview share — otherwise a
    # "when do we go live?" gets an improvised stall two days post-launch.
    live_url = site_live_fact(company)
    creds_on_file = credentials_fact(company)
    status_block = ""
    if creds_on_file:
        status_block += (
            f"\nFACT: credentials already ON FILE for this client: "
            f"{creds_on_file}. NEVER ask the client for any of these "
            "numbers again; if relevant, confirm we have them.\n")
    if live_url:
        status_block = (
            f"\nFACT: this client's website is ALREADY LIVE at {live_url} "
            "(their real domain, launched). If they ask when they go live, "
            "about site status, or anything similar: tell them it is live, "
            "include that exact URL, and name what is still in progress from "
            "the items instead of vague reassurance. Never say the site is "
            "coming soon, almost there, or being finished.\n")
    preview_block = ""
    if lead_preview:
        preview_block = (
            f"\nWebsite preview link for THIS client: {preview_url}\n"
            "This client has NEVER seen their new website. That link is the "
            "whole point of this message: lead with it, include the FULL URL "
            "exactly as written above, sound genuinely pleased to be handing "
            "it over, and ask ONE open question about what they think. Do "
            "not pair it with any other ask, and do not mention the site "
            "without including the link.\n")
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
            f"Channel: {channel} (LENGTH TARGET: {stated_budget} characters "
            f"or fewer, class={budget_class}"
            + (", and the email body is the same short text plus the sign-off"
               if channel == "email" else "")
            + ". This is a target to come in UNDER, not a quota to fill. A "
            "one-sentence message is a good message.)\n"
            f"FIRST CONTACT: {'yes' if first_contact else 'no'}\n"
            + binding_line
            + name_line
            + sister_block
            + (f"Intro line to open with, exactly: \"{intro}\"\n"
               if first_contact else "")
            + history_block
            + intel_block
            + review_stats_block
            + billing_block
            + appt_block
            + ban_block
            + directive_block
            + (lsa_note or "")
            + pending_block
            + evening_block
            + steps_block
            + pair_block
            + commit_block
            + preview_block
            + status_block
            + domain_block
            + photo_block
            + internal_block
            + connect_block
            + f"Outstanding items (priority order, cover all of these and "
            f"nothing else):\n" + "\n".join(lines))
    draft = anthropic_json(COMPOSE_SYSTEM, user)
    body = (draft.get("body") or "").strip()
    # CONCISION GUARD (Santino 2026-08-04): shorten (model) then trim
    # (mechanical). Links stay verbatim through both passes.
    if channel == "sms" and body:
        body = _fit_sms(body, stated_budget, sms_budget,
                        keep_links=[preview_url if lead_preview else "",
                                    connect_link or "", photo_link or ""],
                        label=f" [{budget_class}]")

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

    # PREVIEW-LINK GUARD (2026-08-04, the belt to the prompt's brace): the
    # whole point of this message is the client seeing their site. If the
    # draft (or the budget trim) lost the URL, put it back as its own
    # complete sentence — a linkless "your site is ready" wastes the touch
    # exactly the way Reign's first week did.
    if lead_preview and body and preview_url not in body:
        body = body.rstrip()
        if body[-1:] not in ".!?":
            body += "."
        body += f" Here it is: {preview_url}"
        print("  [preview-share] draft dropped the preview URL — appended it")

    def _flags(key):
        return [f for f in (draft.get(key) or [])
                if isinstance(f, dict) and f.get("item_id")]

    done_ids = {str(d["id"]) for d in (directives or [])}
    directive_done = [f for f in (draft.get("directive_done") or [])
                      if isinstance(f, dict)
                      and str(f.get("note_id")) in done_ids]
    return {"subject": (draft.get("subject") or None), "body": body,
            "items": chosen, "history_answered": _flags("history_answered"),
            "intel_resolved": _flags("intel_resolved"),
            "directive_done": directive_done,
            # HELD, not carried out: this send answered the client instead, so
            # the order must stay OPEN. Without this the one-shot resolve
            # below would close a directive Monica never actually delivered.
            "directives_held": directives_held}


def _companies_with_items(state: dict | None = None) -> list[str]:
    ids = {r["company_id"] for r in fetch_pending_intake()}
    ids |= {r["company_id"] for r in fetch_open_asks()}
    # A boss directive is reason enough to compose even with an empty item
    # list: Santino's "Reach out and set a meeting up" order (ProRestoration,
    # 2026-08-04) must never depend on there happening to be an open ask.
    ids |= set(_companies_with_directives())
    # ...and so is an OWED REPLY (2026-08-04). This roster is the entire input
    # to the `compose --all` pass, so a client we owe a message but have no
    # open ask for was invisible to the backstop: the inbound engine would arm
    # awaiting_reply and nothing would ever come read it. That is the "always
    # the last message" rule silently failing on exactly the clients who are
    # furthest along — the ones with nothing left to ask.
    for cid, cs in (state or {}).get("companies", {}).items():
        if cs.get("awaiting_reply") or cs.get("pending_commitment"):
            ids.add(cid)
    return sorted(i for i in ids if i)


def cmd_compose(args) -> int:
    if getattr(args, "all", False):
        # SAME-OWNER MERGE (Santino 2026-07-28): All Pro + ProRestoration share
        # one owner (Jack, one phone, one GHL contact) — composing per company
        # would text the same person twice back-to-back. Group companies by
        # their resolved messaging target; one merged message per human.
        cids = _companies_with_items(load_state())
        companies = fetch_companies(cids)
        # Suspended-account payment ladder rides every slot (its own per-step
        # stamps dedupe; a quiet fleet costs one GET).
        try:
            n = suspension_dunning(load_state(),
                                   dry_run=not getattr(args, "send", False))
            if n:
                print(f"[suspension] {n} dunning action(s) this slot")
        except Exception as e:  # noqa: BLE001 — the ladder never kills compose
            print(f"[suspension] warn: {str(e)[:120]}")
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
            # suspension_skip: Suspended accounts hear ONLY the payment
            # ladder — normal nurture would undercut the dunning message.
            if str(companies[group[0]].get("status") or "").lower() == "suspended":
                print(f"  skipping {companies[group[0]].get('name', group[0])}: "
                      "account Suspended — payment ladder owns this thread")
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
    if owed_reply_channel(args.channel, cs, contact) != args.channel:
        args.channel = "email"
        print("Reply-in-channel: the owed client message arrived by email — "
              "answering by email (2d)")
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
    #
    # DEFERRED RE-CHECK (Santino 2026-08-04): this call is where a reason
    # armed hours ago gets re-validated against the live thread — refreshed if
    # the client has spoken again, cleared if anything already advanced the
    # thread. The draft below is always written fresh from that result, so a
    # message held overnight is recomposed in the morning, never replayed.
    armed_before = bool(cs.get("awaiting_reply"))
    pending = pending_client_message(cs, history, state)
    if pending:
        label = ("answered our question" if pending["kind"] == "answer"
                 else "waiting on a reply")
        print(f"Client {label}: {pending['body'][:90]!r} "
              "(cooldown/nudge-cap bypassed — this send is a reply, not a nudge)")
        try:
            record_service_disclaimers(company, pending)
        except Exception as _e:  # noqa: BLE001 — recording never blocks a reply
            print(f"  [svc-disclaim] {str(_e)[:80]}")
        if pending.get("recheck"):
            print(f"  [re-check] {pending['recheck']}")
    elif cs.get("awaiting_reply") is None and armed_before:
        print("  [re-check] the reply we owed is no longer owed — the thread "
              "moved on since it was armed; nothing to send for it")
    # OPEN COMMITMENT (Santino 2026-08-02: "I'll walk you through it" must
    # actually happen): a promise made in an ack is owed like a reply —
    # same bypass, and the draft is forced to deliver it. Expires at 7 days
    # (by then the thread has moved on; don't dredge up stale promises).
    dropped = revalidate_commitment(cs, history, state,
                                    evidence=_evidence_slice(intel))
    if dropped:
        print(f"  [re-check] {dropped}")
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
    # BOSS DIRECTIVES (Santino 2026-08-04): an open ops note ordering Monica
    # to contact this client. Fetched for the primary AND any merged sister,
    # so an order filed on either half of a same-owner pair still lands.
    directives = open_boss_directives(args.company)
    for scid in merge_with:
        directives += open_boss_directives(scid)
    # Never ask a client for access we already hold, or can take ourselves.
    items, directives, lsa_note = access_ask_guard(
        company, items, directives, dry_run=not args.send)
    if directives:
        print(f"Boss directive(s) open: {len(directives)} — "
              + "; ".join(str(d.get("body", ""))[:70] for d in directives))
        print("  (cooldown, nudge cap and the human-defer window are all "
              "bypassed — acting on his order is not a nudge)")
    owed = bool(pending or commitment or directives)
    items, hold = promise_hold(
        items, overdue_commitments([args.company] + merge_with) if items else [])
    if hold:
        print(f"PROMISE HOLD: {hold}")
        if not owed:
            print(f"{company['name']}: nudge skipped (promise-hold) — replies "
                  "and our own deliveries still go, asks wait.")
            return 0
    if not items and not owed:
        print(f"{company['name']}: nothing outstanding — no message needed.")
        return 0

    # Never talk over a human: newest outbound not sent by the concierge and
    # <12h old means Santino (or someone on the team) is mid-conversation.
    # HIS OWN DIRECTIVE OVERRIDES HIS OWN DEFER (Santino 2026-08-04): he
    # filed "Reach out and set a meeting up sometime tomorrow or Thursday"
    # on ProRestoration at 19:58, then texted Angie himself at 22:23 — which
    # correctly armed the 12h defer and would have buried his own order until
    # the next morning. He asked for the outreach, so it is not an
    # interruption. Any OTHER client's human conversation still defers
    # exactly as before; the bypass is scoped to the company that carries the
    # directive, and the draft is told to stand down if the thread already
    # shows the order was carried out.
    defer_reason = human_conversation_deferral(history, state)
    if defer_reason and directives:
        print(f"\n[human-defer overridden by Santino's own directive: "
              f"{defer_reason}]")
        defer_reason = None
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
        # REVEAL FOLLOW-UP CARVE-OUT (Santino 2026-09-20): after the site
        # preview goes out, exactly ONE follow-up rides at the 2-day mark —
        # earlier than the normal cooldown — so the board's silence-release
        # ("2 quiet days AFTER the follow-up") means the client ignored two
        # touches, not one. The unlinked-preview guard forces the follow-up
        # to carry the link, which is what stamps followup_sent_at.
        followup_due = _reveal_followup_due(company, history)
        if followup_due:
            print("  [reveal-followup] preview sent 2d+ ago, no reply, no "
                  "follow-up yet — cooldown carve-out for one nudge")
        gate = cadence_check(cs, company, contact,
                             boss_override=bool(directives),
                             client_waiting=owed or followup_due,
                             reply_to=(pending or {}).get("at"))
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
        if followup_due:
            # DETERMINISTIC (DryCor 2026-09-22): the LLM's already-answered
            # discernment excluded the preview item as "we already sent this
            # exact link" — which is TRUE and is also exactly what the one
            # follow-up nudge is supposed to do. The two-touch flow never
            # progressed and the card sat at "follow-up due" forever. The
            # nudge is policy, not judgment — send it without the model.
            _sr = ((company.get("integration_settings") or {})
                   .get("site_reveal") or {})
            _url = str(_sr.get("url") or "").strip()
            if _url:
                _nm = str((contact or {}).get("firstName") or "").strip()
                body = ((f"Hey {_nm}, " if _nm else "Hey, ")
                        + "just circling back on your new website preview: "
                        + _url
                        + " Any thoughts or changes you'd like? If it looks "
                          "good, say the word and we'll get it ready to go "
                          "live.")
                try:
                    _res = send_message(contact, "sms", body,
                                        company=company)
                    record_sent_message(state, _res)
                    save_state(state, dry_run=False)
                    print("  [reveal-followup] one-nudge follow-up SENT "
                          "(deterministic)")
                except SendBlocked as e:
                    print(f"  [reveal-followup] BLOCKED: {str(e)[:100]}")
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
                     "lead with offering a quick 15-minute call WITH SANTINO this week to knock "
                     "everything out together (you are never on the call yourself: ask what time "
                     "works, do not promise a specific slot), and "
                     f"include this link to a picture of their setup checklist: {card_url} . "
                     "Keep individual asks brief; the call is the main CTA.")
            print(f"[ladder] escalation active — checklist card: {card_url}")
    # SHOW THEM THE SITE FIRST (2026-08-04): re-rank the website-preview ask
    # against the real thread — never sent => it leads this message.
    preview_url = boost_preview_share(company, items, history)
    # ALWAYS sort (Santino 2026-08-06). boost_preview_share returns None once
    # the link has already been sent — but it still stamps _rank 4 on the share
    # ask to demote it. Sorting only when it returned a URL meant that demotion
    # was never applied: items kept source order and the already-seen "take a
    # look at your preview" nudge beat the domain ask, which ranks 1 as a launch
    # blocker. HomeLyft sat at build_status=preview_ready with
    # domain_access_status=none, having already been sent the link, and the next
    # message queued was another preview nudge instead of the one thing standing
    # between them and going live. Affects every client past the preview share.
    items.sort(key=ask_rank)
    draft = compose_draft(company, first, items, args.channel, first_contact,
                          history=history, intel=intel, appointments=appts,
                          sister_names=sister_names, pending_reply=pending,
                          commitment=commitment, preview_url=preview_url,
                          directives=directives, lsa_note=lsa_note,
                          evening_ack=evening_ack_only(
                              company, contact,
                              reply_to=(pending or {}).get("at")))
    # A directive the thread shows was ALREADY carried out (Santino texted
    # them the same thing himself) is closed instead of repeated.
    if draft.get("directive_done"):
        done_ids = {str(f.get("note_id")) for f in draft["directive_done"]}
        already = [d for d in directives if str(d["id"]) in done_ids]
        for f in draft["directive_done"]:
            print(f"[directive already handled by a human: "
                  f"{str(f.get('reason'))[:120]}]")
        if args.send:
            resolve_directives(already, why="already done by a human")
        directives = [d for d in directives if str(d["id"]) not in done_ids]
        # The bypass the directive granted dies with it: if nothing else is
        # owed, this send goes back under the normal cooldown.
        owed = bool(pending or commitment or directives)
    print("\n" + "=" * 62)
    if draft["subject"] and args.channel == "email":
        print(f"Subject: {draft['subject']}")
    print(draft["body"])
    print("=" * 62)
    print(f"({len(draft['body'])} chars, channel={args.channel})")
    # OUTBOUND GUARD: grounding (a DONE-claim must trace to the ledger),
    # persona (Monica never attended anything), registrar truth (we can
    # never fetch domain access ourselves) and the capability contract (she
    # cannot call, book, visit or promise a deadline). Better a blocked send
    # than a lie to a client (Flood Fixers "review request is already out"
    # 2026-08-02; Reign "great meeting with you" + "we'll reach out through
    # GoDaddy" 2026-08-04; Coastal "I'll give you a call shortly" 2026-08-05).
    grounding = outbound_guard(draft["body"], _evidence_slice(intel))
    if grounding:
        print(f"GUARD WARNING: {grounding}")
        if honest_substitute(grounding, (pending or {}).get("body")):
            print(f"  [--send would substitute: {CALL_HANDOFF_REPLY!r} and "
                  "ping Santino to place the call]")

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
                           boss_override=bool(directives),
                           client_waiting=owed,
                           reply_to=(pending or {}).get("at"))
    if reason:
        print(f"\nSEND REFUSED (cadence): {reason}", file=sys.stderr)
        return 0
    if not contact:
        print("\nSEND REFUSED: no GHL contact resolved", file=sys.stderr)
        return 1
    # LINK GATE (2026-08-04): heal a stale URL from marketing_sites, and
    # never mail a client a link that does not resolve.
    draft["body"], dead_link = verify_outbound_links(company, draft["body"])
    if dead_link:
        print(f"\nSEND REFUSED (link check): {dead_link}", file=sys.stderr)
        append_escalation(company, None,
                          f"held a message with a dead link: {dead_link}",
                          False, ping=True)
        return 0
    banned = topic_ban_violation(company.get("id"), draft["body"])
    if banned:
        print(f"\nSEND REFUSED (topic ban): {banned}", file=sys.stderr)
        append_escalation(company, None, f"off-limits topic in a draft: "
                          f"{banned}", False)
        return 0
    if grounding:
        # CAPABILITY SUBSTITUTION (2026-08-05): a blocked call promise is not
        # just refused, it is REPLACED with the true version — a human calls,
        # we ask for the window — and Santino is pinged so somebody dials.
        # Silence would leave the client waiting exactly like the lie did.
        swap = honest_substitute(grounding, (pending or {}).get("body"))
        if swap:
            print(f"\nGUARD SUBSTITUTION: {grounding}\n  -> {swap!r}")
            draft["body"] = swap
            draft["subject"] = draft.get("subject") or "Quick call"
            escalate_call_request(company, None, (pending or {}).get("body"),
                                  dry_run=False)
            grounding = None
        else:
            print(f"\nSEND REFUSED (outbound guard): {grounding}",
                  file=sys.stderr)
            append_escalation(company, None,
                              f"outbound guard blocked a send: {grounding}",
                              False)
            return 0
    # Hard duplicate guard (Santino 2026-08-02: two team-photo asks landed
    # one minute apart; 2026-08-05: two Reign texts a minute apart that
    # contradicted each other). Checked against the cross-process outbox AND
    # the thread, immediately before the send, so a second pass in another
    # process stays silent.
    reply_key = _reply_key(pending)
    dup = repeats_recent_outbound(company.get("id"), draft["body"], history,
                                  evidence=_evidence_slice(intel),
                                  reply_to=reply_key,
                                  boss_directive=bool(directives))
    if dup:
        print(f"\nSEND REFUSED (duplicate guard): {dup}", file=sys.stderr)
        if "CONTRADICT" in dup:
            append_escalation(company, None,
                              f"held a message that contradicted what we "
                              f"already told them: {dup}", False, ping=True)
        return 0
    channel_used = args.channel
    # Answering an email: thread it (Re: subject + in-thread reply id).
    subject_out = draft["subject"]
    email_thread_id = None
    _owed = cs.get("awaiting_reply") or {}
    if args.channel == "email" and _owed.get("channel") == "email":
        subject_out = _re_subject(_owed.get("email_subject")) or subject_out
        email_thread_id = _owed.get("email_msg_id")
    try:
        result = send_message(contact, args.channel, draft["body"],
                              subject_out, company=company,
                              reply_to=reply_key,
                              email_msg_id=email_thread_id)
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
                                      draft["subject"], company=company)
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
    # One-shot boss directives are acted on by THIS send — resolve them so
    # the cadence bypass they grant can't keep firing on every future compose
    # (they'd otherwise stay open until Santino manually hit Done,
    # re-bypassing the cooldown hourly). Standing CONSTRAINT notes ("Do NOT
    # mention the domain to Angie") are never directives and are never
    # touched here: they stay open and keep riding into compose as intel.
    if draft.get("directives_held"):
        print("  [directive] left OPEN — this message was the client's reply, "
              "not the order; it goes out on the next pass")
    else:
        resolve_directives(directives)
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
    directives = open_boss_directives(company_id)
    items, directives, lsa_note = access_ask_guard(
        company, items, directives, dry_run=True)
    owed = bool(pending or commitment or directives)
    # A boss directive overrides his own human-defer (see cmd_compose).
    gate = ((None if directives else human_conversation_deferral(history, state))
            or cadence_check(cs, company, contact,
                             boss_override=bool(directives),
                             client_waiting=owed,
                             reply_to=(pending or {}).get("at")))
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
    preview_url = boost_preview_share(company, items, history)
    # ALWAYS sort (Santino 2026-08-06). boost_preview_share returns None once
    # the link has already been sent — but it still stamps _rank 4 on the share
    # ask to demote it. Sorting only when it returned a URL meant that demotion
    # was never applied: items kept source order and the already-seen "take a
    # look at your preview" nudge beat the domain ask, which ranks 1 as a launch
    # blocker. HomeLyft sat at build_status=preview_ready with
    # domain_access_status=none, having already been sent the link, and the next
    # message queued was another preview nudge instead of the one thing standing
    # between them and going live. Affects every client past the preview share.
    items.sort(key=ask_rank)
    draft = compose_draft(company, first, items, channel, first_contact,
                          history=history, intel=intel, appointments=appts,
                          pending_reply=pending, commitment=commitment,
                          preview_url=preview_url, directives=directives,
                          lsa_note=lsa_note,
                          evening_ack=evening_ack_only(
                              company, contact,
                              reply_to=(pending or {}).get("at")))
    # The preview shows what a REAL send would do, so it must show the guard
    # verdict too (2026-08-05): a draft the guard would block, or replace with
    # the call handoff, should never look clean in the app.
    guard = outbound_guard(draft["body"], _evidence_slice(intel))
    swap = honest_substitute(guard, (pending or {}).get("body"))
    return {"company": company.get("name"), "channel": channel, "gate": gate,
            "draft": swap or draft["body"], "subject": draft.get("subject"),
            "guard": guard, "guard_substituted": bool(swap),
            "items": [i["text"] for i in draft.get("items", [])]}


# ---------------------------------------------------------------- send now
def send_now(company_id: str, channel: str = "sms") -> dict:
    """One explicit human click on the previewed draft = authorization
    (Santino 2026-08-03, right after loving the Crew preview: "Send now").
    Runs the SAME compose as the preview, then delivers — with
    boss-directive semantics, exactly like an open [FROM SANTINO] note:

      BYPASSED : cooldown + nudge cap (the click IS the authorization),
                 business hours (NOT hard-blocked — the response carries
                 local_time/in_business_hours so the UI confirms first),
                 the 60-min human quiet window (the click IS the human
                 speaking).
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
    channel = owed_reply_channel(channel, cs, contact)   # 2d: email owed -> email
    first_contact = not cs.get("first_contacted")
    history = fetch_history(contact["id"])
    if first_contact and any(
            m.get("direction") != "in"
            and "this is monica" in str(m.get("body") or "").lower()
            for m in history):
        first_contact = False
    pending = pending_client_message(cs, history, state)
    commitment = cs.get("pending_commitment") or None
    directives = open_boss_directives(company_id)
    items, directives, lsa_note = access_ask_guard(
        company, items, directives, dry_run=False)   # send_now is a real send
    if not items and not (pending or commitment or directives):
        return {**base, "sent": False,
                "reason": "nothing outstanding — no message to send"}
    intel = load_meeting_intel(company)
    appts_res = fetch_upcoming_appointments(contact["id"], tz_key)
    appts = appts_res[0] if isinstance(appts_res, tuple) else None
    preview_url = boost_preview_share(company, items, history)
    # ALWAYS sort (Santino 2026-08-06). boost_preview_share returns None once
    # the link has already been sent — but it still stamps _rank 4 on the share
    # ask to demote it. Sorting only when it returned a URL meant that demotion
    # was never applied: items kept source order and the already-seen "take a
    # look at your preview" nudge beat the domain ask, which ranks 1 as a launch
    # blocker. HomeLyft sat at build_status=preview_ready with
    # domain_access_status=none, having already been sent the link, and the next
    # message queued was another preview nudge instead of the one thing standing
    # between them and going live. Affects every client past the preview share.
    items.sort(key=ask_rank)
    draft = compose_draft(company, first, items, channel, first_contact,
                          history=history, intel=intel, appointments=appts,
                          pending_reply=pending, commitment=commitment,
                          preview_url=preview_url, directives=directives,
                          lsa_note=lsa_note,
                          evening_ack=evening_ack_only(
                              company, contact,
                              reply_to=(pending or {}).get("at")))
    if draft.get("directive_done"):
        done_ids = {str(f.get("note_id")) for f in draft["directive_done"]}
        resolve_directives([d for d in directives if str(d["id"]) in done_ids],
                           why="already done by a human")
        directives = [d for d in directives if str(d["id"]) not in done_ids]
    body = draft["body"]
    if not body:
        return {**base, "sent": False,
                "reason": "compose produced nothing (every item excluded "
                          "by history/meeting intel)"}
    body, dead_link = verify_outbound_links(company, body)
    if dead_link:
        return {**base, "sent": False, "body": body,
                "reason": f"link check: {dead_link}"}
    banned = topic_ban_violation(company_id, body)
    if banned:
        return {**base, "sent": False, "body": body,
                "reason": f"topic ban: {banned}"}
    grounding = outbound_guard(body, _evidence_slice(intel))
    if grounding:
        # Same substitution as the scheduled path: a blocked call promise is
        # replaced by the true one and Santino is pinged (2026-08-05).
        swap = honest_substitute(grounding, (pending or {}).get("body"))
        if not swap:
            return {**base, "sent": False, "body": body,
                    "reason": f"outbound guard: {grounding}"}
        print(f"  [guard substitution] {grounding}\n    -> {swap!r}")
        body = swap
        draft["subject"] = draft.get("subject") or "Quick call"
        escalate_call_request(company, None, (pending or {}).get("body"),
                              dry_run=False)
    reply_key = _reply_key(pending)
    dup = repeats_recent_outbound(company_id, body, history,
                                  evidence=_evidence_slice(intel),
                                  reply_to=reply_key,
                                  boss_directive=bool(directives))
    if dup:
        return {**base, "sent": False, "body": body,
                "reason": f"duplicate guard: {dup}"}
    channel_used = channel
    # Answering an email: thread it (Re: subject + in-thread reply id).
    _owed_now = cs.get("awaiting_reply") or {}
    subject_now = draft["subject"]
    email_thread_now = None
    if channel == "email" and _owed_now.get("channel") == "email":
        subject_now = _re_subject(_owed_now.get("email_subject")) or subject_now
        email_thread_now = _owed_now.get("email_msg_id")
    try:
        try:
            result = send_message(contact, channel, body, subject_now,
                                  company=company, reply_to=reply_key,
                                  human_hold_exempt=True,
                                  email_msg_id=email_thread_now)
        except SendBlocked as e:
            # same DND fallback as the scheduled compose path
            if ("DND active" in str(e) and channel == "sms"
                    and (contact.get("email") or "").strip()):
                result = send_message(contact, "email", body,
                                      draft["subject"], company=company,
                                      reply_to=reply_key,
                                      human_hold_exempt=True)
                channel_used = "email"
            else:
                raise
    except SendBlocked as e:
        # A blocked send used to end here as a return value nobody read, which
        # is how DISS Restoration went unmessaged from signup with a finished
        # site waiting (Santino, 2026-08-05). A HOLD is deliberate and stays
        # quiet; anything else means a real client is unreachable and has to
        # reach the board. Once per company+reason, so it cannot spam.
        reason = str(e)
        if "HOLD on this client" not in reason:
            try:
                if intel_flag_once(state, f"send-block:{company_id}:{channel}"):
                    _sb("POST", "/rest/v1/marketing_ops_notes",
                        {"company_id": company_id, "status": "open",
                         "body": (
                             f"[TODO-SANTINO] CANNOT REACH "
                             f"{company.get('name')} — a message was composed "
                             f"and could not be delivered.\n\n{reason}\n\n"
                             f"Monica had something to say to this client and "
                             f"no way to say it. Until this is cleared they "
                             f"hear nothing from us, however many items sit "
                             f"on their board.")},
                        prefer="return=minimal")
            except Exception as note_err:  # noqa: BLE001 — never mask the block
                print(f"  [send-block] could not file card: {note_err}",
                      file=sys.stderr)
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
    if not draft.get("directives_held"):
        resolve_directives(directives)  # one-shot: satisfied by this send
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

DOMAIN ACCESS IS NOT ANSWERED BY NAMING THE REGISTRAR (Santino 2026-08-04):
"yes it's with GoDaddy, I've got all the information" tells us WHERE the
domain lives. It does not give us access, and the item stays open. Only a
statement that they SENT the invite / added us / handed over the login
("just sent the invite", "you should have access now", "added
setup@restorationai.io") answers a domain-access item. Put the registrar
name in "value" with a free_text match ONLY if an item actually asks which
company holds the domain; otherwise report it in "analysis.summary" and
leave the access item unmatched.

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

SATISFIED BY CONVERSATION (Santino 2026-08-04, live failure: a client
replied "Ive already had all my customer leave reviews, even past clients
from a previous company" and the customer-list item stayed pending, so
Monica asked for the list anyway two messages later). When an inbound reply
amounts to "already handled" / "not needed" / "doesn't apply to me" for an
OPEN item, that item is answered by the conversation itself. Report it in
"satisfied_by_conversation" with the item id, the client's own words
verbatim in "quote", and a one-line "reason".
STRICT — only CLEAR, PRESENT-TENSE statements qualify:
  YES: "already did that", "we've got all of those", "everyone's already
       left one", "we don't have any of those", "that doesn't apply to us",
       "no need, it's handled", "we don't use one".
  NO : "I'll get to it", "let me pull that together", "give me a few days",
       "working on it", "I think we might have", "probably", anything that
       promises FUTURE action or hedges. Those keep the item open — they are
       commitments, not answers.
An item that is genuinely answered with a VALUE (a license number, a yes/no,
an emailed export) belongs in "matches", not here. Use
"satisfied_by_conversation" only when the answer is that there is nothing
for us to collect. When unsure, leave it out — a wrongly closed item is
invisible, a re-ask is merely annoying.

CLIENT FEEDBACK THAT IMPLIES WORK ON OUR SIDE (Santino 2026-08-05, the
structural gap). On 08-04 Greg Arianoff sent four screenshots of our own
service images back with PPE corrections, and Jerrott Gray said the Reign
preview was "not ready to go live", wanted it "dark moody and expensive
looking", and asked why the service area left out Dallas. Every one of those
was received, classified and answered — and then went nowhere, because
nothing in the system turns "the client said something actionable" into
queued work. Report every such statement in "client_feedback", one entry per
distinct change. This is a THIRD kind of thing:
  - a QUESTION is answered with words                    -> needs_answer
  - an ASK OF THEM is something they still owe us        -> matches / items
  - FEEDBACK is something WE have to go change           -> client_feedback
A message can be two at once. "Is there a reason the service area dosnt
include dallas?" is a question AND feedback: answer them, and add the cities.
Fields per entry:
  "category": one of
     imagery      an image is wrong: wrong uniform or PPE, wrong vehicle,
                  wrong gear, distorted or obviously-AI people, wrong scene,
                  wrong region
     design       look and feel: too light or too dark, colours, layout,
                  "feels cheap", "make it modern", fonts, spacing
     brand        logo, brand colour, vehicle livery or decals, name usage
     service_area cities or areas to add or remove
     copy         wording on the site: headlines, body text, descriptions
     facts        a business fact on the site is wrong: phone, address,
                  hours, services they do or don't do, staff, licence
     site_links   links on the site: add or fix social profile links or
                  icons (Facebook, Instagram, LinkedIn), external links,
                  footer links (Angie 2026-09-10: her Facebook/Instagram
                  ask sat four days as unclassified)
     rejection    they turned the preview down without saying what to change
     other        actionable, but none of the above
  "what":  the change WE must make, in our words, one line, specific enough
           that a build agent could start on it. Never "fix the images" —
           name which images and what is wrong with them.
  "where": which page, section or asset, or "site-wide".
  "quote": their exact words, verbatim, typos included. Never paraphrase:
           it is the evidence for the work AND it is read back to them when
           the work is done.
  "confidence": "high" when a build agent could START on it without asking
           THEM anything else. It does not mean they were polite, complete or
           technically precise, and working out which file to change is the
           build agent's job, not yours. Calibrated on real messages:
             high   "The company vehicles need to be black."
             high   "The yellow need to to match the logo color" — their logo
                    is on file, that is enough to start
             high   "Is there a reason the service area dosnt include
                    dallas?" — a question in form, a change in substance
             high   "This guy is distorted" — they are looking at one of our
                    images and it is wrong; regenerating it needs nothing
                    from them
             medium "the pictures could be better", "can you make it pop",
                    "something feels off about the top of the page" — we
                    would have to ask them what they mean
             low    they gesture at dissatisfaction with no object at all
           Anything below high is routed to a human instead of run, so the
           cost of "medium" is a delay, not a mistake. Do not use it as
           politeness.
  "complaint": true when the message reads as unhappiness with US (our
           service, the money, the relationship, cancelling), not as a
           correction of the work. A blunt correction ("this guy is
           distorted", "I think you went overboard") is NOT a complaint, it
           is a client doing their job. Getting this wrong in the cautious
           direction just means Santino reads it first.
BUSINESS-FACT CHANGES ARE FEEDBACK even when nothing is "wrong" and even
when the site is never mentioned (Alfredo/ACS 2026-09-21: "change my
address to..." was acknowledged and then executed by nobody). A request to
change the business address, phone, hours, service areas, or people
(remove someone from a campaign or a list) is category "brand" or
"service_area" work on OUR side — it ripples to the site, the records, and
the campaigns whether or not they say the word "website".
PHONE NUMBERS (Santino 2026-09-28, TDI/Rob): phone requests are no longer
held for a human. You decide, so decide carefully. Our sites show TRACKING
numbers by design: every visible number forwards to the client's real line
and tells us where the call came from, and which one a visitor sees depends
on how they arrived (Google, Bing, an ad, their metro). So:
  - They think the number shown is WRONG, unknown, or "not ours" and give
    no instruction ("the number on the site is wrong", "whose number is
    this?") -> NOT feedback. That is a tracking line doing its job. Answer
    it: it is a tracking number that forwards straight to them and records
    where the call came from, and invite them to call it to confirm.
  - They INSTRUCT a change: they name the number(s) and/or the placement
    ("put our office lines under each address in the footer: 916-966-2601,
    ...", "use 850-555-0100 in the header", "remove 916-314-8955 from the
    footer", "our main number changed to ...") -> feedback, category
    "facts", confidence "high". Put every number verbatim in "what" with
    exactly where it goes, and say whether it replaces the MAIN number or is
    an additional listed line. This holds even after we explained tracking
    numbers to them: once they tell us what they want, we do it.
  - A layout/design complaint that merely mentions the phone ("the phone
    number wraps on mobile", "make the call button bigger") -> feedback in
    its own category, and "what" must end with "(do not change which
    number is displayed)". This is the case that once overwrote a tracking
    line (Frontline 2026-09-12); saying so in "what" keeps it from repeating.
NOT feedback: compliments, approvals ("go ahead and launch it"), questions
about how something works, anything about their Google listing / reviews /
ads / billing, and anything they are going to do themselves.
"client_feedback" is [] for the large majority of messages.

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

If the reply asks to SET UP / SCHEDULE a NEW call or meeting, or proposes
a specific time for one ("can we hop on a call tomorrow?", "11am EST
tomorrow good for you?", "let's schedule a call next week"), set "booking"
with their words about timing as the preference — the booking flow offers
real open slots (or books their proposed time when it is genuinely free)
and confirms only after the calendar write succeeds. This is DIFFERENT
from a bare "call me" / "give me a call" with no scheduling intent: that
stays a call request handled by escalation, never booking. Do not also
set escalate for a booking ask.

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
A REQUEST FOR A PHONE CALL IS ALWAYS needs_santino (Santino 2026-08-05):
"call me", "give me a call when you get a minute", "can we talk", "when can
you call". Monica has no phone, so a human must place that call — set
needs_answer AND needs_santino true, and make suggested_reply the handoff:
"Got it, I'll pass this along to Santino right now. What's the best time to
reach you?" Never "Santino will call you" (Santino 2026-08-18: Monica never
commits him to a call, she passes it along and he decides), never a
specific time, and never Monica placing the call herself.

FULL ANALYSIS — required for EVERY message, even pure acknowledgments
(the boss's spec 2026-08-02: every inbound gets analyzed — does it need a
response, does it need escalation, and what should the response be):
"analysis": {
  "summary": one plain line saying what the client is saying or needs,
  "response_needed": "none" | "acknowledge" | "answer" | "answer_by_boss",
  "suggested_reply": the exact reply Monica should send, or null when
                     response_needed is "none"}
suggested_reply rules — Monica's voice: warm, and SHORT (Santino
2026-08-04, hard rule): aim 160-200 characters, never over 260. One or two
short sentences. No preamble, no re-explaining what we already said, no
justifying the ask, no closing filler, no restating their words back. The
ask or the answer is the whole message.
Plain 6th-grade words, NEVER em or en dashes (use a comma or period), no
emojis, no canned filler ("Perfect, thanks for getting back to me" is
banned). Respond to what they SAID. When they are stuck ("I don't know how
to..."), do the FIRST STEP of the walk-through right now: ask ONE simple
question that unblocks them (customer list example: "Where do your
previous customer contacts live?" — plain words, no system menus; a
review campaign needs the FULL list, hundreds of contacts, so never
suggest a screenshot). For a non-technical client (Santino 2026-08-02:
"someone like Todd, definitely just recommend a meeting"), the next move
after that one question is a short call WITH SANTINO to do it together —
offer it and ask what time works, don't text a multi-step walkthrough at
them. You cannot be on that call and you cannot book it: ask for their
window so a human sets it.
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
- PERSONA (hard rule, 2026-08-04): Monica is not a person and has never
  attended a call, meeting or site visit. NEVER write "great meeting you",
  "nice talking with you", "as we discussed on the call", "when we met",
  "on our call", "meet with me", "I saw", "I heard". Reference the team in
  the third person instead: "Santino mentioned...", "great call with
  Santino yesterday", "the team went over it". A call is always THEIR call
  with Santino, never "our call".
- REGISTRAR TRUTH (hard rule, 2026-08-04): <<DOMAIN_ACCESS_TRUTH>>
  If they name their domain company, that is useful but changes nothing:
  the reply thanks them and asks THEM to send the access (GoDaddy:
  account.godaddy.com/access, Invite to Access, send it to
  <<DOMAIN_ACCESS_INVITE_EMAIL>>), or offers a 15-minute call with Santino
  to do it together while they are signed in.
<<CAPABILITY_CONTRACT>>
<<CONSISTENCY_RULE>>
Only promise a follow-up when the answer genuinely needs research we
cannot do in this text, and say specifically what you will come back with.
When response_needed is "answer" and the open items / history / intel
contain the answer, give it plainly; otherwise write a specific holding
line. NEVER promise anything that will not actually happen.

Return ONLY JSON:
{"matches": [{"item_id": "<id from the list>", "value": "<extracted answer>",
              "answer_type": "license|yes_no|free_text|customer_list"}],
 "intel_resolved": [{"item_id": "<id from the list>", "reason": string}],
 "satisfied_by_conversation": [{"item_id": "<id from the list>",
                                "quote": "<their words, verbatim>",
                                "reason": string}],
 "client_feedback": [{"category": "imagery|design|brand|service_area|copy|
                                   facts|rejection|other",
                      "what": string, "where": string,
                      "quote": "<their words, verbatim>",
                      "confidence": "high|medium|low",
                      "complaint": bool}],
 "ack": bool,
 "needs_answer": bool,
 "needs_santino": bool,
 "analysis": {"summary": string,
              "response_needed": "none|acknowledge|answer|answer_by_boss",
              "suggested_reply": string|null},
 "reschedule": {"requested": bool, "preference": string}|null,
 "booking": {"requested": bool, "preference": string}|null,
 "escalate": bool,
 "escalate_reason": string|null,
 "sentiment": "positive|neutral|negative"}
"intel_resolved" is [] when no meeting intel is provided or none applies.
"satisfied_by_conversation" is [] unless the reply clearly says an item is
already handled or does not apply.
"client_feedback" is [] unless the reply says something WE built is wrong,
missing or should be different.
Match at most the items clearly answered. When in doubt, do not match — set
escalate true with a reason instead."""

REPLY_SYSTEM = """\
You are Monica from Santino's team at Restoration AI, replying after a
client answered something. Voice: warm, brief, human. NEVER use em dashes or en
dashes; use a comma or a period instead.
- ATTRIBUTION — WHICH conversation is this reply about? (ACS 2026-09-19,
  live failure: the client sent website revision feedback with screenshots
  of his own preview site; Monica read it through the rename conversation
  and proposed changing a locked business name he never questioned.)
  Interpret every client statement relative to (a) the message of OURS it
  most plausibly answers and (b) any image tags in the history: a
  screenshot of the client's own website means they are talking about the
  WEBSITE; a photo of a filing means the DBA; a statement right after a
  proposed name means the name. "We don't do mold" after a name containing
  mold is name feedback; the same words with a site screenshot is a site
  correction. Take the statement at face value and ONLY about the exact
  services they named, never extend it to other services. If, after the
  images and the last exchange, it is genuinely unclear which workstream
  they mean, ask one short question ("Is that about the website or the
  name?") instead of guessing.
- LOCKED NAMES ARE FINAL: once a business name has been confirmed and the
  client told to file it, NEVER propose a different name string yourself.
  If their message makes the locked name look wrong, acknowledge, say the
  team will review it, and stop — a human decides name changes.
- BE SHORT — hard rule (Santino 2026-08-04). One or two short sentences,
  160-200 characters. No preamble, no re-explaining anything already said in
  the thread, no justifying the ask, no closing filler ("let me know if you
  have questions", "happy to help"), no restating their words back at them.
  Answer or ask, then stop. Example of the right size: "Got it. Can you send
  over your past customer list? Names and numbers is all we need."
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
  account settings) and the client reads non-technical, offer a short
  call WITH SANTINO to do it together instead of text steps (Santino
  2026-08-02). You are never on that call and you cannot book it: ask
  what time works and a human sets it up.
- If nothing remains, close warmly ("that's everything we needed").
- GROUNDING: never claim our work is already done (sent / out / posted /
  live). You see only the thread, not the ledger — speak forward ("we're
  getting that set up now"), never "is already out" (2026-08-02).
- PERSONA (hard rule, 2026-08-04): you are not a person and have never been
  on a call, in a meeting or on a site visit. NEVER "great meeting you",
  "nice talking with you", "as we discussed on the call", "when we met",
  "on our call", "meet with me", "I saw", "I heard". Say it in the third
  person: "Santino mentioned...", "great call with Santino yesterday".
- REGISTRAR TRUTH (hard rule, 2026-08-04): <<DOMAIN_ACCESS_TRUTH>>
  Naming the domain company is not access. Thank them, then ask THEM to
  send it (GoDaddy: account.godaddy.com/access, Invite to Access, to
  <<DOMAIN_ACCESS_INVITE_EMAIL>>) or offer a 15-minute call with Santino
  to do it together.
- FILE DESTINATION TRUTH (hard rule, 2026-09-18, Alfredo asked "Let me
  have an email" for his customer list and the answer needed a human):
  when the client asks WHERE or HOW to send us a file, list, or photos
  (including "what's your email" / "let me have an email"), the answer
  is ALWAYS their hub upload link, provided in context as "Hub upload
  link". Reply with the link itself, plainly: it goes straight into
  their account and is easier than email. NEVER give an email address
  for a file (the outbound guard blocks it and a human has to step in).
  If the context says no hub link is on file, say the team is sending
  their upload link over shortly, nothing else.
<<CAPABILITY_CONTRACT>>
<<CONSISTENCY_RULE>>
SMS-length: aim 200 chars, never over 260. No emojis.
Return ONLY JSON: {"body": string}."""

# Same single-source substitution as COMPOSE_SYSTEM (2026-08-04 registrar
# truth, 2026-08-05 capability contract).
for _name in ("CLASSIFY_SYSTEM", "REPLY_SYSTEM"):
    globals()[_name] = (globals()[_name]
                        .replace("<<DOMAIN_ACCESS_TRUTH>>", DOMAIN_ACCESS_TRUTH)
                        .replace("<<DOMAIN_ACCESS_INVITE_EMAIL>>",
                                 DOMAIN_ACCESS_INVITE_EMAIL)
                        .replace("<<CAPABILITY_CONTRACT>>",
                                 CAPABILITY_CONTRACT)
                        .replace("<<CONSISTENCY_RULE>>", CONSISTENCY_RULE))


def _tracked_contacts(state: dict) -> dict[str, str]:
    """contact_id -> company_id for every company we've engaged (incl. canary)."""
    out = {}
    for cid, cs in state.get("companies", {}).items():
        if cs.get("ghl_contact_id"):
            out[cs["ghl_contact_id"]] = cid
    return out


def _company_for_contact(contact_id: str, state: dict) -> str | None:
    """company_id for an inbound contact, or None for a true stranger.

    The tracked map holds ONE contact per company (the primary messaging
    target) — but companies have several real people (Addi at DISS texted
    a team photo on 2026-09-10 and was silently IGNORED because only her
    colleague was tracked). Before ignoring anyone, match the contact's
    email/phone against the company records, then their email DOMAIN
    (colleagues on a company domain belong to that company)."""
    cid = _tracked_contacts(state).get(contact_id)
    if cid:
        return cid
    try:
        c = (_ghl("GET", f"/contacts/{contact_id}") or {}).get("contact") or {}
    except Exception:  # noqa: BLE001
        return None
    email = (c.get("email") or "").strip().lower()
    phone = re.sub(r"\D", "", c.get("phone") or "")[-10:]
    if not email and not phone:
        return None
    companies = fetch_companies()
    for co_id, co in companies.items():
        ints = co.get("integration_settings") or {}
        if isinstance(ints, str):
            try:
                ints = json.loads(ints)
            except (ValueError, TypeError):
                ints = {}
        cards = ints.get("contacts") or []
        emails = [str(co.get("email") or "")] + \
                 [str(k.get("email") or "") for k in cards]
        phones = [str(co.get("phone") or "")] + \
                 [str(k.get("phone") or k.get("cell") or "") for k in cards]
        if email and email in [e.lower() for e in emails if e]:
            return co_id
        if phone and any(re.sub(r"\D", "", p)[-10:] == phone
                         for p in phones if p):
            return co_id
    # domain-level email match, freemail excluded
    if email and "@" in email:
        dom = email.split("@", 1)[1]
        if dom not in ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
                       "aol.com", "icloud.com", "me.com", "msn.com"):
            for co_id, co in companies.items():
                ce = str(co.get("email") or "").lower()
                if "@" in ce and ce.split("@", 1)[1] == dom:
                    return co_id
    return None


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
            # INTERNAL SENDER MAP (2b): an "inbound" row carrying a GHL
            # userId is our own external-mailbox send synced back by GHL,
            # never a client message. Skip it here so neither the webhook
            # nor the poll ever answers Santino as if he were the client
            # (Bobby 08-19: Monica thanked him for Santino's own words).
            if is_internal_sender(msg):
                continue
            if msg.get("messageType") not in ("TYPE_SMS", "TYPE_EMAIL"):
                continue
            body = (msg.get("body") or "").strip()
            attachments = msg.get("attachments") or []
            # Inbound emails are SHELLS in the conversation feed (body AND
            # attachments null) — the content sits behind the email endpoint.
            # fetch_history got this hydration on 08-24 (Jaziel), but THIS
            # collector kept dropping them as empty: Bob Olson's 2026-09-08
            # 11pm reply about the flag photos vanished right here. Hydrate
            # BEFORE the empty-drop check.
            if (not body or not attachments) \
                    and msg.get("messageType") == "TYPE_EMAIL":
                # 2026-09-24 (DISS/Addi): hydrate on missing ATTACHMENTS
                # too, not just missing body — an email WITH text whose
                # images sat behind the endpoint reached media-ingest with
                # zero attachments and false-pinged "couldn't auto-file".
                email_ids = (((msg.get("meta") or {}).get("email") or {})
                             .get("messageIds") or [])
                if email_ids:
                    try:
                        full = _ghl("GET", "/conversations/messages/email/"
                                    f"{email_ids[0]}") or {}
                        e = full.get("emailMessage", full)
                        raw = re.sub(r"<[^>]+>", " ", e.get("body") or "")
                        body = body or re.sub(r"\s+", " ", raw).strip()
                        attachments = attachments or (e.get("attachments") or [])
                    except Exception as err:  # noqa: BLE001
                        print(f"    [email-hydrate] failed: {str(err)[:80]}")
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
            entry = {"id": msg["id"], "body": body, "ts": ts,
                     "conversation_id": conv["id"],
                     "attachments": attachments,
                     "channel": "sms" if msg["messageType"] == "TYPE_SMS"
                     else "email"}
            if msg["messageType"] == "TYPE_EMAIL":
                # Threading crumbs for reply-in-channel (2d): subject for
                # the Re: line, provider message id for a true in-thread
                # reply via emailReplyMode.
                em = (msg.get("meta") or {}).get("email") or {}
                if em.get("subject"):
                    entry["email_subject"] = em["subject"]
                ids = em.get("messageIds") or []
                if ids:
                    entry["email_msg_id"] = ids[-1]
            messages.append(entry)
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


def _classify_texted_image(jpeg_bytes: bytes, msg_text: str) -> str | None:
    """What IS this image a client just texted? Returns job_photo /
    screenshot / document / brand, or None when the call fails (callers
    fall back to the aspect-ratio heuristic). Born from Jimmy / California
    Restoration West 2026-08-28: two cropped screenshots of a Squarespace
    invite error were filed as job photos and thanked with "queued for your
    Google profile" — aspect ratio alone cannot tell a cropped screenshot
    from a job photo, but one look can."""
    try:
        import base64
        out = anthropic_json(
            "You classify a single image a home-services client texted to "
            "their marketing agency. Reply with ONE JSON object: "
            '{"class": "job_photo" | "screenshot" | "document" | "brand"}. '
            "job_photo = real-world photo of work, damage, equipment, crew, "
            "vehicles or property. screenshot = any phone/computer UI, app, "
            "error message, settings page or website capture, INCLUDING a "
            "photo of a monitor/laptop/phone whose screen shows a website "
            "or app (a photographed screen is a screenshot, not a job "
            "photo). document = a "
            "photo/scan of paperwork (insurance, license, bill, form, "
            "letter). brand = logo, color palette, font sample or business "
            "card.",
            "Accompanying text from the client (may be empty): "
            + (msg_text or "(none)")[:400],
            max_tokens=600,
            images=[{"media_type": "image/jpeg",
                     "data": base64.b64encode(jpeg_bytes).decode()}])
        c = str(out.get("class") or "").strip().lower()
        return c if c in ("job_photo", "screenshot", "document", "brand") else None
    except Exception:  # noqa: BLE001 — classification is best-effort
        return None


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
           "failed": 0, "contact_cards": [], "brand_refs": 0, "documents": 0}
    cid = company["id"]
    # BRAND CONTEXT (Sarha / Air Care 2026-08-11): she texted 8 color-picker
    # screenshots saying "these specific colors and fonts" — they were filed
    # as JOB PHOTOS (portrait-shaped, so the screenshot net missed them), fed
    # the GBP poster, and NO brand record existed anywhere; the site would
    # have built in default colors, Todd's colors incident all over again.
    # When the accompanying words are about brand/colors/fonts/logo, every
    # image in the burst goes to brand/refs/ and a [DEV] extraction task is
    # filed so the nightly agent writes the actual values into plan-input.
    brand_context = bool(re.search(
        r"\bcolou?rs?\b|\bfonts?\b|\blogo\b|\bbrand(ing)?\b|\bbusiness\s+cards?\b",
        (msg.get("body") or ""), re.I))
    # EDIT CONTEXT (Angie / All Pro 2026-09-14): she texted photos OF her
    # screen showing website edits she wanted ("edit on the All Pro
    # plumbing website... can you move that") and the burst was filed as
    # content photos + thanked with "queued for your Google profile"; she
    # had to correct us twice ("I am showing examples to change", "Not to
    # add those photos"). When the words are edit-requests about the
    # site/profile, every image in the burst is REFERENCE material ->
    # job-photos/inbox/ (quarantine), never the GBP/content lane. Beats
    # the vision classifier AND its aspect-ratio fallback, both of which
    # can misread a photo of a monitor as business photography.
    edit_context = bool(re.search(
        r"\b(website|web\s*site|site|page|homepage|header|banner|button|profile)\b",
        (msg.get("body") or ""), re.I)) and bool(re.search(
        r"\b(edit|change|move|swap|remove|fix|adjust|instead|example|examples"
        r"|smaller|bigger|larger|tiny)\b",
        (msg.get("body") or ""), re.I))
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
                cls = None if (brand_context or edit_context) \
                    else _classify_texted_image(body, msg.get("body") or "")
                if brand_context or cls == "brand":
                    path, kind = f"{cid}/brand/refs/sms-{stamp}.jpg", "brand_refs"
                elif edit_context:
                    path, kind = f"{cid}/job-photos/inbox/sms-{stamp}.jpg", "screenshots"
                elif cls == "screenshot":
                    path, kind = f"{cid}/job-photos/inbox/sms-{stamp}.jpg", "screenshots"
                elif cls == "document":
                    # paperwork (insurance, licenses, bills) — never GBP media
                    path, kind = f"{cid}/docs/inbox/sms-{stamp}.jpg", "documents"
                    # Clients answer the EIN ask with a photo of the CP-575 /
                    # W-9 as often as with digits (Santino 2026-09-04) —
                    # read the number off the document right here.
                    _maybe_capture_ein_from_document(company, raw, dry_run)
                elif cls == "job_photo":
                    path, kind = f"{cid}/job-photos/sms-{stamp}.jpg", "photos"
                elif h and w / h < 0.5:             # classifier failed: screenshot-shaped
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
    if out["brand_refs"] and not dry_run:
        try:
            slug = company_slug(cid) or company.get("name") or cid
            _sb("POST", "/rest/v1/marketing_ops_notes", {
                "company_id": cid, "author": "concierge", "status": "open",
                "body": (f"[DEV] BRAND REFS from client text ({slug}), "
                         f"{out['brand_refs']} image(s) in branding/{cid}/brand/refs/ "
                         f"— client's words: {(msg.get('body') or '')[:200]!r}. "
                         "TASK: read the images, extract the exact brand "
                         "colors (hex) and font names, write them into "
                         f"clients/{slug}/plan-input.json brand.colors / "
                         "brand.fonts with a source note. Do NOT guess from "
                         "memory; the images are the truth.")})
        except Exception as e:  # noqa: BLE001 — the files are safe either way
            print(f"    [media] brand-refs task not filed: {e}", file=sys.stderr)
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


# ---- SATISFIED BY CONVERSATION (Santino 2026-08-04) ------------------------
# Jerrott Gray replied "Ive already had all my customer leave reviews. Even
# past clients from a previous company." — a complete answer to the open
# customer-list item. Nothing recorded it, so the item stayed `pending` and
# Monica asked him for the list anyway. General rule now: an inbound that
# amounts to "already handled / not needed / doesn't apply" ANSWERS the item,
# with the client's own words kept as the answer.
#
# Two locks, because a wrongly-closed item is invisible while a re-ask is
# merely annoying: the classifier must nominate it AND this mechanical test
# must agree. A future-tense commitment ("I'll get to it") fails the second
# lock every time — that is a promise, not an answer.
_SATISFIED_RE = re.compile(
    r"\b(?:already\s+(?:have|had|has|got|gotten|did|done|sent|handled|"
    r"asked|left|covered|taken care)"
    r"|(?:we|i|they|everyone|everybody|all)\s+(?:have\s+)?already\b"
    r"|no\s+need\b|don'?t\s+need\b|doesn'?t\s+(?:apply|matter)\b"
    r"|not\s+applicable\b|nothing\s+to\s+(?:send|share|add)\b"
    r"|(?:we|i)\s+don'?t\s+(?:have|use|do|offer|run|carry)\b"
    r"|(?:that'?s|it'?s|those\s+are|we'?re)\s+(?:all\s+)?"
    r"(?:done|handled|covered|set|good|taken\s+care\s+of)\b"
    r"|taken\s+care\s+of\b|all\s+set\b)", re.I)

# Anything that defers the thing to the future is a commitment, never an
# answer — these veto the close outright.
_FUTURE_COMMIT_RE = re.compile(
    r"\b(?:i'?ll|i\s+will|we'?ll|we\s+will|going\s+to|gonna|let\s+me|"
    r"give\s+me|working\s+on\s+it|trying\s+to|once\s+i|when\s+i\s+"
    r"(?:get|have|can)|later|tomorrow|next\s+week|this\s+week(?:end)?|"
    r"in\s+a\s+(?:bit|few)|shortly|soon|by\s+(?:monday|tuesday|wednesday|"
    r"thursday|friday))\b", re.I)

# Hedges — "I think we might have" is not a clear statement.
_HEDGE_RE = re.compile(
    r"\b(?:i\s+think|maybe|probably|might|not\s+sure|pretty\s+sure|"
    r"i\s+guess|should\s+be|kind\s+of|sort\s+of)\b", re.I)


def conversation_satisfies(text: str) -> tuple[bool, str]:
    """Mechanical second lock on a satisfied-by-conversation close.

    Returns (ok, why). Only a clear, present-tense "already handled / not
    needed / doesn't apply" passes; future commitments and hedges never do."""
    t = (text or "").strip()
    if not t:
        return False, "empty message"
    if _FUTURE_COMMIT_RE.search(t):
        m = _FUTURE_COMMIT_RE.search(t)
        return False, (f"reads as a future commitment ({m.group(0)!r}), not a "
                       "completed state — the item stays open")
    if _HEDGE_RE.search(t):
        m = _HEDGE_RE.search(t)
        return False, f"hedged ({m.group(0)!r}) — not a clear statement"
    m = _SATISFIED_RE.search(t)
    if not m:
        return False, ("no clear already-handled / not-needed / doesn't-apply "
                       "statement in the message")
    return True, f"clear completed-state statement ({m.group(0)!r})"


# The review campaign is the one place where "already handled" changes
# STRATEGY, not just status: a client whose whole back catalogue has already
# been asked has nothing left for the reactivation drip, but the FORWARD list
# (new customers as jobs close) is still worth having. This note lands open on
# the Ops Attention board and rides into every later compose via the ops-notes
# block of load_meeting_intel, so the next mention reframes instead of
# re-asking cold.
_REVIEW_ITEM_RE = re.compile(
    r"customer list|past[- ]customer|review campaign|reviews?\b", re.I)


def _review_strategy_note(company: dict, item_text: str, quote: str,
                          who: str, dry_run: bool) -> None:
    body = (
        "[REVIEW-STRATEGY] Their review back-catalogue is ALREADY HARVESTED. "
        f"{who} told us: \"{quote[:200]}\" (closing the open item "
        f"\"{item_text[:80]}\"). What this changes: the reactivation drip has "
        "nothing to reactivate, so do NOT enrol a past-customer list and do "
        "NOT re-ask for one cold. The list that still has value is the "
        "FORWARD one, new customers as jobs close, so the review request goes "
        "out automatically from then on. MONICA: if the customer list comes "
        "up again, reframe it that way in plain words (\"since your past "
        "customers have already left reviews, the piece worth setting up is "
        "the new ones as jobs wrap up\"), never as a fresh ask for the old "
        "list.")
    if dry_run:
        print(f"    [dry-run] would file ops note: {body[:110]}...")
        return
    try:
        _sb("POST", "/rest/v1/marketing_ops_notes",
            {"company_id": company.get("id"), "body": body, "status": "open"},
            prefer="return=minimal")
        print("    [review-strategy] ops note filed — future mentions reframe "
              "forward instead of re-asking")
    except Exception as e:  # noqa: BLE001 — a note must never kill the poll
        print(f"    [review-strategy] note failed: {str(e)[:90]}")


def close_satisfied_by_conversation(company: dict, item: dict, quote: str,
                                    reason: str, who: str, when: str,
                                    dry_run: bool) -> bool:
    """Record an open item as answered BY THE CONVERSATION: the client's own
    words become the answer, with attribution and timestamp. Returns True when
    it closed. Always logged (print + escalation digest + work log) so Santino
    can see exactly what auto-closed and why."""
    ok, why = conversation_satisfies(quote)
    if not ok:
        print(f"    [satisfied?] NOT closing {item['text'][:50]!r}: {why}")
        append_escalation(
            company, None,
            f"possible answer-by-conversation on {item['text'][:70]!r} "
            f"({quote[:100]!r}) was NOT auto-closed: {why}. Check the thread "
            "and close it by hand if the client really meant it.",
            dry_run, ping=False)
        return False
    value = (f"satisfied by conversation {when[:10]}: {who} said "
             f"\"{quote[:220]}\" — {reason[:120]}")
    print(f"    SATISFIED-BY-CONVERSATION {item['text'][:55]!r} <- "
          f"{quote[:70]!r} ({why})")
    if item["kind"] == "intake":
        apply_answer(item["id"], value, dry_run)
    else:
        resolve_plan_row(item["id"], dry_run, answer=value)
    append_escalation(
        company, None,
        f"AUTO-CLOSED by the client's own words: {item['text'][:80]!r} — "
        f"{who} said \"{quote[:120]}\". Recorded as the answer; Monica will "
        "not ask again. Reopen it in the app if that was wrong.",
        dry_run, ping=False)
    if not dry_run:
        try:
            from work_log import work_log
            work_log(company.get("id"), "intake", "satisfied-by-conversation",
                     f"Closed {item['text'][:60]!r} from the client's reply",
                     evidence={"quote": quote[:300], "who": who, "when": when,
                               "item_kind": item["kind"], "item_id": item["id"],
                               "reason": reason[:200]},
                     actor="monica",
                     source="client_concierge.py satisfied_by_conversation")
        except Exception as e:  # noqa: BLE001 — the ledger never blocks a close
            print(f"    [work-log] warn: {str(e)[:90]}")
    if _REVIEW_ITEM_RE.search(item["text"]):
        _review_strategy_note(company, item["text"], quote, who, dry_run)
    return True


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

DO NOT GUESS BETWEEN CLIENTS. Several open questions are often near-identical
("the client wants a call", "no reply after N nudges"), and a generic answer
like "tell them I'm in and out of meetings and will call as soon as I can"
fits all of them equally. Picking one at random sends a real client a message
about someone else's situation. Set "ambiguous": true whenever the reply could
plausibly answer more than one of the open questions AND does not identify
which client it is about (by company name, person's name, or an unmistakable
detail from that question). When you set it, "index" is ignored.

Only pick an index when the reply is tied to ONE question — because he named
the client, named the person, or answered something only that question asked.

Return ONLY JSON: {"index": <int index of the question answered, or null if
his reply clearly is not an answer to any of them>, "ambiguous": <true|false>,
"instruction": "<his directive, restated as a clear instruction, keeping any
links exactly>"}"""

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


# PHASE 3 — PROPOSE, THEN ACT (Santino 2026-08-08).
#
# "Once she creates those tasks she should put them in the app, then reach out
# to me to ask if she should start on them. She can list out all the tasks she
# created in a single message for a single client and keep it concise."
#
# The extraction half already worked: Bob Olson's 2026-08-08 call produced NINE
# [TODO-PROPOSED] notes within a second of each other. What did not exist was
# anyone telling Santino. Nine rows appeared on a board he had no reason to
# open, and the gate that was supposed to hold them ("Approve = machine") is
# only a gate if he knows there is something to approve.
#
# ONE text per client, listing what was captured, asking whether to start.
# Nothing is executed by this function: [TODO-PROPOSED] still requires his
# Approve click to become [DEV], which is the existing, proven gate. This adds
# the missing half, notification, rather than a parallel mechanism.
_PROPOSAL_TAG = "[TODO-PROPOSED]"


PROPOSALS_PER_RUN = 3       # never turn a backlog into a text storm


def propose_call_tasks(dry_run: bool, per_run: int = PROPOSALS_PER_RUN) -> list[str]:
    """Text Santino one summary per client with unannounced proposed tasks.

    CAPPED, because the first dry run found 44 unannounced tasks across TEN
    clients — every call we have ever transcribed. Uncapped this would have
    sent ten texts in one burst, which is how an alerting channel gets muted,
    and a muted channel is worse than no channel. Oldest client first so the
    backlog drains in order instead of the newest call always winning.
    """
    out: list[str] = []
    seen = kv_get("proposal-batches") or {}
    rows = _sb("GET", "/rest/v1/marketing_ops_notes?status=eq.open"
               "&select=id,company_id,body,created_at"
               "&order=created_at.desc&limit=300") or []
    by_co: dict[str, list[dict]] = {}
    for r in rows:
        if str(r.get("body") or "").startswith(_PROPOSAL_TAG):
            by_co.setdefault(r["company_id"], []).append(r)

    sent = 0
    # Oldest call first: a client waiting since last week outranks today's.
    for cid, notes in sorted(by_co.items(),
                             key=lambda kv: min(n["created_at"] for n in kv[1])):
        if sent >= per_run:
            out.append(f"(capped at {per_run} proposals this run; "
                       f"{len(by_co) - sent} client(s) still queued)")
            break
        already = set(seen.get(cid, []))
        fresh = [n for n in notes if str(n["id"]) not in already]
        if not fresh:
            continue
        co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=id,name") or [{}])[0]
        name = co.get("name") or cid

        # First line of each note after the tag+header is the task itself.
        def _task(body: str) -> str:
            for ln in str(body).splitlines():
                ln = ln.strip()
                if ln and not ln.startswith(_PROPOSAL_TAG) and "THEY SAID" not in ln:
                    return ln
            return ""
        # Truncate each task: Reign's is a full paragraph of internal
        # directive text, and one long note would eat the whole SMS budget.
        tasks = [t[:110] for t in (_task(n["body"]) for n in fresh) if t][:8]
        if not tasks:
            continue
        # PLAIN STRUCTURED TEXT, NOT PROSE (Santino 2026-08-08, on seeing the
        # first batch land as run-on paragraphs on his phone). humanize_boss_sms
        # is written to rewrite notes INTO prose, one line per client, which is
        # right for a heads-up and exactly wrong for a checklist he has to read
        # and answer item by item. A list is already human — it does not need
        # rewriting, and rewriting it destroyed the only thing that made it
        # scannable.
        raw = (f"{name}: {len(tasks)} task(s) from the call, logged in the app.\n\n"
               + "\n".join(f"- {t}" for t in tasks)
               + "\n\nWant me to start on these?")
        if dry_run:
            out.append(f"{name}: [dry-run] would propose {len(tasks)} task(s)")
            out.append("    " + raw.replace("\n", "\n    "))
            sent += 1          # the cap must be visible in a dry run too,
            continue           # or the preview lies about what a real run does
        body = raw[:1200]   # sent verbatim; see the note above
        try:
            send_message({"id": ADVICE_CONTACT_ID, "phone": ADVICE_PHONE},
                         "sms", body)
            seen[cid] = list(already | {str(n["id"]) for n in fresh})
            kv_set("proposal-batches", seen)
            # REGISTER WITH THE ADVICE LOOP, or his reply lands nowhere.
            # Santino 2026-08-08: "if it sends me three messages at a time,
            # how will it discern which one I'm responding to?" The matcher
            # already answers that — it ties a reply to one open question by
            # company name, person or an unmistakable detail, and marks it
            # AMBIGUOUS rather than guessing when it cannot tell (a wrong
            # guess sends a real client someone else's answer). But it can
            # only match against questions it knows about, so a proposal has
            # to be one of them.
            reqs = _advice_requests()
            reqs.append({"company_id": cid, "company_name": name,
                         "reason": f"proposed {len(tasks)} task(s) from the "
                                   f"call: {'; '.join(tasks)[:240]}",
                         "kind": "task-proposal",
                         "asked_at": datetime.now(timezone.utc).isoformat(),
                         "status": "open"})
            kv_set("advice-requests", reqs)
            out.append(f"{name}: proposed {len(tasks)} task(s) to Santino")
            sent += 1
        except SendBlocked as e:
            out.append(f"{name}: proposal SMS blocked: {e}")
    return out


# REPLY-TO-APPROVE (Santino 2026-08-09).
#
# Until now a reply was ACKNOWLEDGED but never IMPLEMENTED. He texted "Yes add
# fire to go greens site", Monica said "Got it", filed a [FROM SANTINO] note,
# marked it resolved — and the actual task stayed [TODO-PROPOSED], so nothing
# built it. Acknowledged and implemented are different things and only the
# first was wired.
#
# THE HARD CASE IS THE PARTIAL REPLY, which is why this is not a blanket flip.
# His Go Green answer was a clean yes. His HomeLyft answer approved most of
# seven tasks while cancelling one ("we're already past August 5th so we don't
# need to send the AI reception set-up"). Flipping everything on that reply
# would have approved the very task he had just cancelled.
#
# So: flip ALL only on an unmistakable blanket yes with no carve-out anywhere
# in the sentence. Anything else stays put and comes back for itemising. The
# cost of asking twice is a text; the cost of guessing is doing work the boss
# just told us not to do.
_APPROVE_ALL_RE = re.compile(
    r"^\s*(yes|yep|yeah|yup|ok|okay|sure|approved?|go ahead|do it|do them|"
    r"do them all|start|start on (them|these)|all good|sounds good|"
    r"please do|go for it)\b", re.I)
_CARVE_OUT_RE = re.compile(
    r"\b(except|but not|don'?t|do not|skip|hold off|not the|no need|"
    r"leave|other than|besides|apart from|instead|already)\b", re.I)


def approval_verdict(reply: str) -> str:
    """'all' | 'partial' | 'none' — what a reply authorises."""
    r = (reply or "").strip()
    if not r:
        return "none"
    if _CARVE_OUT_RE.search(r):
        return "partial"          # something is being excluded; itemise it
    if _APPROVE_ALL_RE.search(r):
        return "all"
    return "none"


def apply_task_approval(company_id: str, reply: str, dry_run: bool) -> list[str]:
    """Flip a company's [TODO-PROPOSED] notes to [DEV] when the reply says so."""
    out: list[str] = []
    verdict = approval_verdict(reply)
    rows = _sb("GET", "/rest/v1/marketing_ops_notes?status=eq.open"
               f"&company_id=eq.{urllib.parse.quote(company_id)}"
               "&select=id,body") or []
    proposed = [r for r in rows
                if str(r.get("body") or "").startswith("[TODO-PROPOSED]")]
    if not proposed:
        return out
    if verdict != "all":
        out.append(f"{company_id}: reply is {verdict!r} — {len(proposed)} "
                   "task(s) left proposed; needs itemising, not a blanket flip")
        return out
    for r in proposed:
        body = str(r["body"]).replace("[TODO-PROPOSED]", "[DEV]", 1)
        # The stale "WHY THIS NEEDS YOUR OK" block argues against the approval
        # to whichever agent reads the note next. Strip it on conversion.
        body = re.sub(r"WHY THIS NEEDS YOUR OK:.*?(?=\nORIGIN:)", "", body,
                      flags=re.S)
        if not dry_run:
            _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{r['id']}",
                {"body": body})
        out.append(f"{company_id}: approved -> [DEV]: "
                   f"{body.splitlines()[1][:60] if len(body.splitlines())>1 else ''}")
    return out


_ADD_CONTACT_RE = re.compile(
    r"\badd\b[^.!?\n]{0,60}\b(?:to (?:this|the) (?:text )?thread"
    r"|as (?:a |the )?(?:point of )?contact|to (?:the|our|my) account)\b",
    re.I)
_PHONE_IN_TEXT_RE = re.compile(
    r"\(?\b(\d{3})\)?[\s.\-]{0,2}(\d{3})[\s.\-]{0,2}(\d{4})\b")


def add_secondary_contact(company: dict, first: str, last: str,
                          phone: str, email: str = "",
                          role: str = "secondary",
                          dry_run: bool = False) -> dict | None:
    """The Chris Pappas tool (Santino 2026-09-24): a client asks to add a
    person to their account/thread. Creates the GHL contact and appends a
    NON-preferred card to integration_settings.contacts — which is what
    both the app's contact panel and the canary allowlist read. Returns
    the card, or None on failure (caller escalates instead of claiming)."""
    digits = re.sub(r"\D", "", phone)[-10:]
    if len(digits) != 10:
        return None
    pretty = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    card = {"first_name": (first or "").strip().title(),
            "last_name": (last or "").strip().title(),
            "cell": pretty, "email": (email or "").strip().lower(),
            "role": role, "preferred": False,
            "added_by": "concierge", "added_at":
            datetime.now(timezone.utc).isoformat()}
    if dry_run:
        print(f"    [dry-run] would add secondary contact {card}")
        return card
    try:
        res = _ghl("POST", "/contacts/", body={
            "locationId": _loc(),
            "firstName": card["first_name"], "lastName": card["last_name"],
            "phone": "+1" + digits,
            **({"email": card["email"]} if card["email"] else {})})
        card["ghl_contact_id"] = ((res or {}).get("contact") or {}).get("id")
    except Exception as e:  # noqa: BLE001 — duplicate contact etc.
        err = str(e)
        m = re.search(r'"contactId"\s*:\s*"([A-Za-z0-9]+)"', err)
        if m:
            card["ghl_contact_id"] = m.group(1)   # already existed — fine
        else:
            print(f"    add_secondary_contact GHL warn: {err[:100]}")
    try:
        ints = company.get("integration_settings") or {}
        if isinstance(ints, str):
            ints = json.loads(ints)
        cards = ints.get("contacts") or []
        if not any(re.sub(r"\D", "", str(c.get("cell") or ""))[-10:] == digits
                   for c in cards):
            cards.append(card)
            ints["contacts"] = cards
            _sb("PATCH", f"/rest/v1/companies?id=eq.{company['id']}",
                body={"integration_settings": ints})
            # A DB-side normalizer can flip preferred onto the NEW card
            # (observed live on the first Chris Pappas add: Scott lost
            # preferred to Chris within a minute). Verify + restore.
            try:
                chk = _sb("GET", "/rest/v1/companies?id=eq."
                          f"{company['id']}&select=integration_settings")[0]
                cints = chk.get("integration_settings") or {}
                ccards = cints.get("contacts") or []
                mine = next((c for c in ccards
                             if re.sub(r"\D", "", str(c.get("cell") or ""))
                             [-10:] == digits), None)
                if mine and mine.get("preferred"):
                    others_preferred = [c for c in ccards
                                        if c is not mine
                                        and c.get("preferred")]
                    if not others_preferred:
                        mine["preferred"] = False
                        prev = next((c for c in ccards if c is not mine), None)
                        if prev:
                            prev["preferred"] = True
                        _sb("PATCH", "/rest/v1/companies?id=eq."
                            f"{company['id']}",
                            body={"integration_settings": cints})
                        print("    preferred-flag flip healed (new card "
                              "must never steal preferred)")
            except Exception as e:  # noqa: BLE001
                print(f"    preferred verify warn: {str(e)[:80]}")
        print(f"    secondary contact ADDED: {card['first_name']} "
              f"{card['last_name']} {pretty} (ghl "
              f"{card.get('ghl_contact_id') or '?'})")
        return card
    except Exception as e:  # noqa: BLE001
        print(f"    add_secondary_contact card warn: {str(e)[:100]}")
        return None


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
    # .get(), not [] — the ack path builds a SYNTHETIC message for the
    # conversational turn ({body, channel, at}, no GHL id) and a KeyError
    # here killed the whole ack (found by the poisoned dry-run, 2026-08-05).
    block = (f"\n## {stamp} — {company.get('name', '?')} ({company.get('id', '?')})\n"
             + (f"- Channel: {msg.get('channel', '?')}  "
                f"Message id: {msg.get('id', '-')}\n"
                f"- Reply: {str(msg.get('body', ''))[:400]!r}\n" if msg else "")
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


# NEW-BOOKING flow (Santino 2026-09-12, the Fran/QCI incident 09-10: "11am
# EST tomorrow good for you?" got a yes from Monica with no calendar behind
# it and no appointment created; a human caught it). Design: Monica NEVER
# asserts a time herself. The flow offers REAL free slots from the Live
# Support calendar (or books the client's proposed time when it is genuinely
# free), and the confirmation text is code-generated AFTER the calendar
# write returns an appointment id. Hard floor: nothing books less than
# BOOKING_MIN_NOTICE_HOURS out, regardless of what GHL's calendar allows
# (the calendar's own allowBookingAfter was loosened to 6h on 09-11 for the
# public link; this floor must not depend on that setting).
LIVE_SUPPORT_CALENDAR_ID = "BhEoJmoyowCaOpALMn61"
BOOKING_ASSIGNED_USER_ID = "xTuHtBz8G7Z4fyhAJ9kJ"   # Santino
BOOKING_MIN_NOTICE_HOURS = 6

BOOKING_TIME_SYSTEM = """\
You read a client's words about WHEN they want a call, resolving against
the current datetime given. Two separate things to extract:
1. proposed_iso: a SPECIFIC day+time ("Tomorrow at 11am" / "Friday 2pm").
   "sometime next week" / "afternoon works" / "whenever" are NOT specific.
2. preferred_date: the DAY they named even without a time ("tomorrow",
   "Wednesday", "later this week" -> null, "next Monday" -> that date).
   Will 2026-09-14: "can we move to tomorrow" got offers scattered across
   the week because the day preference was thrown away — never again.
A bare clock time is in the CLIENT's timezone (given). Return ONLY JSON:
{"proposed_iso": "YYYY-MM-DDTHH:MM:SS<offset> or null",
 "preferred_date": "YYYY-MM-DD or null",
 "confidence": "high"|"low"}
Never guess: ambiguous -> null for that field."""

BOOKING_OFFER_SYSTEM = """\
You are Monica, texting a client of the marketing agency who asked to set
up a call. Offer the slot options given (their local time) the way a busy
human texts (Santino 2026-09-14, the Will exchange: "I have 11 am and
1 pm tomorrow if either of those work better" is the voice — his casual
two-liner beat a formal paragraph). Rules, all hard: at most 2 short
sentences; compress times naturally ("tomorrow at 11am or 1pm",
"Wednesday at noon"), never spell out full dates like "September 16 at
12:00 PM" for days this week; no em dashes; never promise who attends or
say you will call; never invent times not in the list; if their stated
preference cannot be met, say so in a few words first.
Return ONLY JSON: {"body": "<the SMS>"}"""


RESCHEDULE_OFFER_SYSTEM = """\
You are Monica from Santino's team at Restoration AI, replying to a client
who asked to move an upcoming call. Voice: a busy human texting, not a
scheduler-bot (Santino 2026-09-14, the Will fix: "I have 11 am and 1 pm
tomorrow if either of those work better" is the voice).
NEVER use em dashes or en dashes; use a comma or a period instead.
Confirm moving is no problem in 2-4 words, then offer the provided slots
compressed naturally: "tomorrow at 11am or 1pm", "Wednesday at noon".
Never spell full dates like "September 16 at 12:00 PM" for days within
the week. When the input says the slots match the client's requested day,
NEVER offer other days. CONCISE (hard rule, Santino 2026-08-04): 2 short
sentences, <= 200 chars, no emojis, no corporate filler, no closing line.
You are NOT on that call and never will be (2026-08-05): move it, confirm
it, and stop. Never "talk to you then", "see you then", or anything that
puts you in the room. The call is theirs with Santino.
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


def _day_offers(slots: list[str], date_str: str) -> list[str]:
    """Up to 3 business-hour slots ON the client's requested day (Will
    2026-09-14: 'tomorrow' must produce tomorrow's times, never a scatter
    across the week)."""
    day = [s for s in slots
           if str(datetime.fromisoformat(s).date()) == date_str
           and 8 <= datetime.fromisoformat(s).hour < 18]
    if len(day) <= 3:
        return day
    # spread across the day: earliest, closest-to-noon, latest
    noon = min(day, key=lambda s: abs(datetime.fromisoformat(s).hour - 12))
    picks = [day[0]]
    if noon not in picks:
        picks.append(noon)
    if day[-1] not in picks:
        picks.append(day[-1])
    return sorted(picks)


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
    offers, day_matched = [], False
    if (preference or "").strip():
        now_loc = datetime.now(timezone.utc).astimezone(ZoneInfo(tz))
        try:
            parsed = anthropic_json(
                BOOKING_TIME_SYSTEM,
                f"Current datetime: {now_loc.strftime('%A %Y-%m-%d %H:%M %Z')} "
                f"(client timezone {tz}).\nClient words: {preference[:300]}")
        except Exception as e:  # noqa: BLE001
            parsed = {}
            print(f"    reschedule time-parse failed ({str(e)[:80]})")
        # exact free time proposed -> MOVE IT, one confirmation, done
        if parsed.get("proposed_iso") and parsed.get("confidence") == "high":
            try:
                want_dt = datetime.fromisoformat(str(parsed["proposed_iso"]))
                match = next((s for s in slots
                              if abs((datetime.fromisoformat(s) - want_dt)
                                     .total_seconds()) < 900), None)
            except ValueError:
                match = None
            if match and not dry_run:
                from datetime import timedelta as _td
                start_loc = datetime.fromisoformat(match).astimezone(
                    ZoneInfo(GHL_LOCATION_TZ))
                try:
                    _ghl("PUT", "/calendars/events/appointments/"
                         + appt["id"],
                         body={"startTime": start_loc.strftime("%Y-%m-%dT%H:%M:%S%z"),
                               "endTime": (start_loc + _td(minutes=60)).strftime("%Y-%m-%dT%H:%M:%S%z"),
                               "calendarId": appt["calendarId"]})
                    body = f"No problem, you're moved to {_fmt_slot(match)}."
                    res = send_message(contact, "sms", body, company=company)
                    record_sent_message(state, res)
                    append_escalation(company, None,
                                      f"FYI (no action needed): call MOVED to "
                                      f"{_fmt_slot(match)} at the client's "
                                      "request", dry_run)
                    print(f"    RESCHEDULED directly -> {match}")
                    return
                except Exception as e:  # noqa: BLE001 — fall through to offers
                    print(f"    direct move failed ({str(e)[:80]})")
        if parsed.get("preferred_date"):
            offers = _day_offers(slots, str(parsed["preferred_date"]))
            day_matched = bool(offers)
    if not offers:
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
                           + ("These slots ARE on the client's requested day.\n"
                              if day_matched else "")
                           + f"Slot options (their local time): {', '.join(labels)}")
    body = _fit_sms((draft.get("body") or "").strip(), 220, 260,
                    label=" [reschedule]")
    print(f"    RESCHEDULE OFFER ({len(body)} chars) -> {body!r}")
    # The reschedule flow is a SEND PATH like any other and was the one that
    # never ran the guard (2026-08-05): a "talk to you then" here is the same
    # false-attendance claim the persona guard exists to stop.
    grounding = outbound_guard(body, None)
    if grounding:
        print(f"    RESCHEDULE OFFER BLOCKED (outbound guard): {grounding}")
        append_escalation(company, None,
                          f"reschedule offer blocked by the outbound guard "
                          f"({grounding}) — the client asked to move their "
                          f"call and needs a human to answer", dry_run,
                          ping=True)
        return
    if dry_run:
        print(f"    [dry-run] offers: {labels}")
        return
    res = send_message(contact, "sms", body, company=company)
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
            # "Talk to you then!" used to ride along here — Monica is not on
            # that call and never will be (capability contract, 2026-08-05).
            confirm = f"You're all set, moved to {_fmt_slot(picked)}."
            res = send_message(contact, "sms", confirm, company=company)
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


def _create_appointment(contact_id: str, start_local, duration_min: int,
                        title: str) -> str | None:
    """POST a new appointment on the Live Support calendar. start_local is
    an aware datetime in GHL_LOCATION_TZ. Returns the appointment id or
    None on failure — the CALLER decides what to tell the client, and no
    confirmation text may exist without this id (the whole point)."""
    from datetime import timedelta
    end_local = start_local + timedelta(minutes=duration_min)
    try:
        res = _ghl("POST", "/calendars/events/appointments", body={
            "calendarId": LIVE_SUPPORT_CALENDAR_ID,
            "locationId": os.environ["GHL_LOCATION_ID"],
            "contactId": contact_id,
            "startTime": start_local.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "endTime": end_local.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "title": title,
            "appointmentStatus": "confirmed",
            "assignedUserId": BOOKING_ASSIGNED_USER_ID,
            "ignoreFreeSlotValidation": True,
        })
        return (res or {}).get("id")
    except RuntimeError as e:
        print(f"    booking POST failed: {str(e)[:120]}")
        return None


def _booking_slot_floor(slots: list[str], tz: str) -> list[str]:
    """Drop anything closer than BOOKING_MIN_NOTICE_HOURS from now."""
    from zoneinfo import ZoneInfo
    from datetime import timedelta
    floor = datetime.now(timezone.utc) + timedelta(hours=BOOKING_MIN_NOTICE_HOURS)
    out = []
    for s in slots:
        try:
            if datetime.fromisoformat(s) >= floor.astimezone(ZoneInfo(tz)):
                out.append(s)
        except ValueError:
            continue
    return out


def handle_booking_request(company: dict, contact: dict, preference: str,
                           state: dict, dry_run: bool) -> None:
    """A client wants to SET UP a new call (Fran class). Book their proposed
    time when it is genuinely free and >= the notice floor; otherwise offer
    real free slots. Confirmation text is generated ONLY after the calendar
    write returns an id — Monica never asserts a time on her own."""
    from zoneinfo import ZoneInfo
    tz, _src = resolve_timezone(company, contact)
    existing = _upcoming_appointment(contact["id"])
    if existing:
        # They already have a call on the books: point at it instead of
        # double-booking; a move is the reschedule flow's job.
        cur = datetime.strptime(existing["startTime"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=ZoneInfo(GHL_LOCATION_TZ)).astimezone(ZoneInfo(tz))
        body = (f"You already have a call on the calendar for "
                f"{_fmt_slot(cur.isoformat())}. Want to keep that, or move it?")
        print(f"    BOOKING ASK but appointment exists -> {body!r}")
        if not dry_run:
            res = send_message(contact, "sms", body, company=company)
            record_sent_message(state, res)
        return
    slots = _booking_slot_floor(
        _free_slots(LIVE_SUPPORT_CALENDAR_ID, tz), tz)
    first = contact_first_name(contact, company)
    # Did they propose a SPECIFIC time?
    proposed = None
    out = {}
    if (preference or "").strip():
        now_loc = datetime.now(timezone.utc).astimezone(ZoneInfo(tz))
        try:
            out = anthropic_json(
                BOOKING_TIME_SYSTEM,
                f"Current datetime: {now_loc.strftime('%A %Y-%m-%d %H:%M %Z')} "
                f"(client timezone {tz}).\nClient words: {preference[:300]}")
            if out.get("proposed_iso") and out.get("confidence") == "high":
                proposed = datetime.fromisoformat(str(out["proposed_iso"]))
        except Exception as e:  # noqa: BLE001
            print(f"    booking time-parse failed ({str(e)[:80]})")
    if proposed is not None and proposed.tzinfo is not None:
        # book it ONLY if it matches a real free slot past the floor
        match = next((s for s in slots
                      if abs((datetime.fromisoformat(s) - proposed)
                             .total_seconds()) < 900), None)
        if match:
            if dry_run:
                print(f"    [dry-run] would BOOK {match} for {first}")
                return
            start_loc = datetime.fromisoformat(match).astimezone(
                ZoneInfo(GHL_LOCATION_TZ))
            appt_id = _create_appointment(
                contact["id"], start_loc, 30,
                f"{first} - LIVE Support Call")
            if appt_id:
                confirm = f"You're all set for {_fmt_slot(match)}."
                res = send_message(contact, "sms", confirm, company=company)
                record_sent_message(state, res)
                append_escalation(company, None,
                                  f"FYI (no action needed): call BOOKED for "
                                  f"{_fmt_slot(match)} at the client's request "
                                  f"(appointment {appt_id})", dry_run)
                print(f"    BOOKED {match} ({appt_id})")
                return
            # write failed -> fall through to offering slots (never confirm)
    offers = []
    if proposed is not None and not offers:
        # nearest real slots to what they wanted
        parsed = sorted(slots, key=lambda s: abs(
            (datetime.fromisoformat(s) - proposed).total_seconds()))
        for s in parsed:
            if not any(datetime.fromisoformat(o).date()
                       == datetime.fromisoformat(s).date() for o in offers):
                offers.append(s)
            if len(offers) == 3:
                break
    if not offers and out.get("preferred_date"):
        # they named a DAY without a time: offer that day's slots
        offers = _day_offers(slots, str(out["preferred_date"]))
    if not offers:
        # no specific time proposed: one business-hours slot per DAY so the
        # client picks a day first, not three slots on the same afternoon
        for s in slots:
            dt = datetime.fromisoformat(s)
            if not (8 <= dt.hour < 18):
                continue
            if any(datetime.fromisoformat(o).date() == dt.date()
                   for o in offers):
                continue
            offers.append(s)
            if len(offers) == 3:
                break
    if not offers:
        append_escalation(company, None,
                          "asked to set up a call but no free slots within "
                          f"{BOOKING_MIN_NOTICE_HOURS}h-8d — needs a human",
                          dry_run, ping=True)
        return
    labels = [_fmt_slot(o) for o in offers]
    draft = anthropic_json(
        BOOKING_OFFER_SYSTEM,
        f"Client first name: {first}\n"
        f"Their stated preference: {preference or 'unspecified'}\n"
        + ("Their exact proposed time was NOT open.\n" if proposed is not None
           else "")
        + f"Slot options (their local time): {', '.join(labels)}")
    body = _fit_sms((draft.get("body") or "").strip(), 220, 260,
                    label=" [booking]")
    grounding = outbound_guard(body, None)
    if grounding:
        print(f"    BOOKING OFFER BLOCKED (outbound guard): {grounding}")
        append_escalation(company, None,
                          f"booking offer blocked by the outbound guard "
                          f"({grounding}) — client wants a call, needs a human",
                          dry_run, ping=True)
        return
    print(f"    BOOKING OFFER ({len(body)} chars) -> {body!r}")
    if dry_run:
        print(f"    [dry-run] offers: {labels}")
        return
    res = send_message(contact, "sms", body, company=company)
    record_sent_message(state, res)
    cs = company_state(state, company["id"])
    cs["pending_booking"] = {
        "tz": tz, "offered": offers, "duration_min": 30,
        "at": datetime.now(timezone.utc).isoformat()}


def handle_booking_reply(company: dict, contact: dict, msg: dict,
                         state: dict, dry_run: bool) -> bool:
    """Consume the client's pick from a pending new-booking offer. Returns
    True when the message belonged to this flow."""
    from zoneinfo import ZoneInfo
    cs = company_state(state, company["id"])
    pend = cs.get("pending_booking")
    if not pend:
        return False
    labels = [f"{o} = {_fmt_slot(o)}" for o in pend["offered"]]
    result = anthropic_json(RESCHEDULE_PICK_SYSTEM,
                            "Offered slots:\n" + "\n".join(labels)
                            + f"\n\nClient reply: {msg['body'][:400]}")
    picked = result.get("picked")
    if picked and picked in pend["offered"]:
        if dry_run:
            print(f"    [dry-run] would BOOK picked {picked}")
            cs.pop("pending_booking", None)
            return True
        start_loc = datetime.fromisoformat(picked).astimezone(
            ZoneInfo(GHL_LOCATION_TZ))
        appt_id = _create_appointment(
            contact["id"], start_loc, pend.get("duration_min", 30),
            f"{contact_first_name(contact, company)} - LIVE Support Call")
        if not appt_id:
            append_escalation(company, msg,
                              f"client picked {picked} but the booking POST "
                              "FAILED — book manually", dry_run, ping=True)
            return True
        confirm = f"You're all set for {_fmt_slot(picked)}."
        res = send_message(contact, "sms", confirm, company=company)
        record_sent_message(state, res)
        cs.pop("pending_booking", None)
        append_escalation(company, None,
                          f"FYI (no action needed): call booked for "
                          f"{_fmt_slot(picked)} (appointment {appt_id})",
                          dry_run)
        print(f"    BOOKED (pick) -> {picked} ({appt_id})")
        return True
    if result.get("counter"):
        cs.pop("pending_booking", None)
        handle_booking_request(company, contact, result["counter"],
                               state, dry_run)
        return True
    return False


# ---------------------------------------------------------------------------
# PROFILE RENAME CONVERSATIONS (Santino 2026-09-12). Monica runs the whole
# GBP-rename decision by text so no meeting is needed: preframe pitch ->
# candidate options quoted VERBATIM from marketing_gbp_suggestions -> natural
# confirmation (never "reply YES", clients believe Monica is human) ->
# DBA instructions bound to the exact string -> human verifies the filing.
# The flow only ever STARTS from our pitch (rename-pitch CLI); client replies
# are consumed here while the per-company rename_convo state is live.
# Writes on confirm: suggestion status=chosen + integration_settings.
# rename_intent.decision=rename + an ops note QUOTING the client's words
# (the consent trail). The citations gate (brightlocal.rename_gate) and the
# app's Profile Rename card read the SAME stores, so the conversation, the
# app buttons and the gate can never disagree. NOTHING here touches Google:
# the GBP change stays a separate, human-sequenced step after citations.

# PLUMBING PUSHBACK (Santino 2026-09-29, Michael/Katofsky said "I don't
# do plumbing" and Monica dropped it on the spot): ONE educational
# pushback with a clear recommendation, then respect the answer.
RENAME_PLUMBING_PUSHBACK = """\
PLUMBING PUSHBACK RULE: when a client says no to plumbing in the name the
FIRST time (e.g. "I don't do plumbing"), do NOT drop it immediately. In
one short, warm message: explain they don't have to do plumbing work, the
word just puts them in front of the "emergency plumber" searches people
make when a pipe bursts (the water damage job they actually want), they
can refer pure plumbing jobs out, and say we strongly recommend keeping
it. Then ask if they'd like to keep it or go without. If they still say
no after that, respect it immediately and move on with the best
non-plumbing option; never raise it again in that conversation.
EXCEPTION: skip the pushback entirely (no plumbing talk at all) when an
ops note / meeting intel for this client says Santino decided NO plumbing
for them (e.g. RestoPros 2026-09-29: profile flagged twice before), or
the client already said no once earlier in the thread."""

RENAME_TRUTH = """\
WHY WE SUGGEST PROFILE RENAMES (knowledge, never recite wholesale):
Google's local ranking leans heavily on the words in the business name.
A name that contains what people actually type (water damage restoration,
24/7 emergency) outranks a bare brand name for those searches. To do it
durably the name must be REAL: the client files a DBA / trade name with
their state for the exact string, it goes on their citations and site
first, and only then does the Google profile get its ONE name change.
Renames are never pushed by us without that sequence; a keyworded name
without paperwork behind it is how profiles get suspended.
PLUMBING (restoration clients only, house stance Santino 2026-09-18/26):
plumbing search volume is bigger than restoration volume, and people with
a burst pipe search "emergency plumber" first, so a plumbing term in the
name is the #1 recommendation. The client does NOT have to do plumbing
repairs: the name puts them in front of that search, they take the water
damage job and refer the pure plumbing work out (which makes plumbers
start sending restoration jobs back). Google does not check licenses for
names; the only risk is a competitor reporting it, which is very unlikely,
and the worst case is the word gets removed. Still mention the license
question honestly if they ask.
STEPS in client language: 1) pick the name, 2) they file the DBA for
exactly that string, 3) we update citations and the website, 4) we make
the one-time Google profile change, 5) if Google asks to re-verify, we
handle it with them. Steps 3-5 are ours; only step 2 is theirs.
Q&A KNOWLEDGE BASE (Santino 2026-09-14 — answer these consistently):
Q "Can we pick one name now and change it later?" A: No. The DBA, every
citation, and Google's trust in the profile all bind to ONE exact
string; changing later means refiling, re-doing citations, and risking
re-verification. THE FORK to offer instead: if the thing blocking the
better name (a plumbing partner, a license) is realistic within a few
weeks, WAIT and do it once with the stronger name; if it is far off or
uncertain, lock the best available name now and never look back. Ask
which situation they are in.
Q "& or 'and'?" A: 'and' by default; whatever the STATE APPROVES on the
DBA becomes the canonical form everywhere.
Q "Will Google make us re-verify after the change?" A: Possibly, and we
plan for it: by the time we change the name, the DBA, website, and
listings all prove it, so a re-verification is winnable.
Q "I already have a DBA (e.g. KCS Restore), why do I need all the extra
words / another filing?" (Michael/Katofsky 2026-09-29) A: Google only lets
a profile show the business's REAL name. "KCS Restore" is real; "KCS
Restore - 24/7 Emergency Water and Fire Damage Restoration" is not, until
it is filed. Without the filing, Google treats the extra words as keyword
stuffing and can suspend the profile. Filing the full phrase makes it
your registered name, so Google has to accept it. Their existing DBA is
the base; the new filing is that same brand plus the phrase.
Q "Isn't it just a description of my services? I already own the name."
A: To you and me yes, but Google judges the name field by the paperwork,
not intent. Descriptions belong in the description; only a registered
name can carry those words in the NAME field, which is the part Google
ranks most heavily for emergency searches. That's the whole point.
Q "Why does the name matter so much?" A: The business name is one of the
strongest local ranking signals. A profile named for what people type
(24/7 emergency, water damage) shows up for those searches ahead of
profiles with a bare brand name. It's the single biggest lever we have.
Q "What is a DBA, do I need a lawyer?" A: A simple trade-name filing
with the state, usually online in minutes, no lawyer needed.
Q "Why the word Emergency?" A: It is what people type in urgent moments
and it is policy-safe once the DBA makes it the registered name.
Q "Do I need an actual location / a city business license?" (Tony
2026-09-14) A: No new location and no city business license. The rename
does not touch where the business operates or its licensing; the DBA is
a county or state trade-name registration for the NAME only, and the
profile keeps its existing address/service area. The only license that
ever comes up is service-specific advertising (like plumbing in the
name, which needs a plumbing license or licensed partner); names built
from services they already legally perform need nothing extra.
Q "Should we put our city in the name?" (DryCor/Tampa 2026-09-15,
refined same day) A: Only if the city is in the PAPERWORK. Two valid
architectures, and multi-location clients must pick BEFORE the first DBA
files (one-name-forever cuts both ways):
  A) ONE uniform name on every location — reviews and citations
     concentrate, one DBA, Google differentiates by address. For
     single-location clients with no expansion plans.
  B) Franchise pattern ("Brand of Tampa - ...") — HOUSE DEFAULT for
     expansion-track clients (Santino 2026-09-15; entity rule updated
     2026-09-28): near-fully-separate profiles per location (own email,
     phone, address, LSA account, max map real estate). By default the
     client's existing LLC files one geo-DBA per location for that exact
     name (no new LLC needed; see docs/EXPANSION-SYSTEM.md), each with
     its own citation set. The per-location DBA is what
     makes the geo-name policy-bulletproof.
A bare city tag without the registration is the policy risk. Never
present this fork as settled; it is a Santino-level strategy decision
for any client with expansion plans.
Q "Should we change the address and the name at the same time?" (Jared
2026-09-15) A: Never together. Each core edit can trigger re-verification;
stacked edits multiply scrutiny. Sequence: address change and verification
first (it usually has a real-world deadline), name change after, on top of
citations that already carry BOTH the new name and new address.
Q "Do you do press releases / BBB / the chamber?" (evidence stack,
2026-09-15) A: Yes as part of the rename rollout: we handle the press
release (it announces the new name with a "formerly known as" line the
same week as the Google change), the BBB business profile, and the
industry listings their certifications unlock (IICRC firm listing is
free with certification). The local Chamber of Commerce is a paid
membership (roughly 200 to 600 a year) that the client buys for their
main city if they want it — we set the listing up once they join.
Q "Can I make my own tracking numbers?" (self-serve, 2026-09-15) A: Yes
— Reports, then Calls, then Tracking Numbers: name it (Postcards,
Billboard), pick an area code, optionally set where it forwards, and
the number is live immediately. 20 numbers are included; more bill at
cost.
Q "Can you send that as a spreadsheet / a file?" A: Never offer or
promise spreadsheets or file attachments (Santino 2026-09-14, the TDI
sitemap spreadsheet: hard to produce, harder to deliver by text).
Deliverables are LINKS: the live page, the sitemap URL, the client hub.
If they insist on a file, say the team will follow up with it and file
an ops note — do not promise a timeline."""

_RENAME_SERVICE_LABELS = {
    "mold": "Mold Remediation", "plumbing": "Plumbing Services",
    "fire": "Fire Damage Restoration", "storm": "Storm Damage Restoration",
    "water damage": "Water Damage Restoration", "sewage": "Sewage Cleanup",
    "carpet": "Carpet Cleaning", "asbestos": "Asbestos Abatement",
    "biohazard": "Biohazard Cleanup", "leak detection": "Leak Detection",
}


def _company_vertical(company: dict) -> str:
    slug = company_slug(company.get("id") or "")
    if slug:
        try:
            rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
            return (rec.get("vertical") or "restoration").strip().lower()
        except Exception:  # noqa: BLE001
            pass
    return "restoration"


# COVERAGE CHECK (Santino 2026-09-12, Crew/roofing miss): "Roofing
# contractor" was a live GBP category AND Roofing Services was in his
# selected services, yet no candidate named roofing — the seeding pass
# keyed on restoration search terms and never cross-checked the two
# stores we already hold. This check runs at the pitch chokepoint: any
# high-volume term present in companies.services OR the GBP categories
# but absent from every candidate is a loud warning before Monica opens
# the conversation.
# Two tiers: BLOCKING = the top-volume lanes that always deserve a name
# slot when the client actually sells them (a missed one is the Crew
# roofing failure). ADVISORY = real services that rarely merit name real
# estate — surfaced as a note, never a refusal, or every client would
# flag sewage and the gate would become noise.
_COVERAGE_TERMS: list[tuple[str, str, bool]] = [
    # (stem in services/categories, stem in candidate names, blocking)
    ("roof", "roof", True), ("plumb", "plumb", True),
    ("mold", "mold", True), ("water damage", "water", True),
    ("fire", "fire", True),
    ("storm", "storm", False), ("sewage", "sewage", False),
    ("carpet clean", "carpet", False), ("asbestos", "asbestos", False),
    ("biohazard", "biohazard", False),
]


def _company_services(company: dict) -> list[str]:
    """companies.services — fetch_companies doesn't select the column, so
    read it directly (it is the single selected-services store)."""
    svcs = company.get("services")
    if isinstance(svcs, list):
        return [str(s) for s in svcs]
    try:
        co = (_sb("GET", f"/rest/v1/companies?id=eq.{company['id']}"
                  "&select=services") or [{}])[0]
        got = co.get("services")
        return [str(s) for s in got] if isinstance(got, list) else []
    except Exception:  # noqa: BLE001
        return []


def _rename_coverage_gaps(company: dict,
                          cands: list[dict]) -> tuple[list[str], list[str]]:
    """High-volume terms the client sells (selected services) or Google
    already lists (GBP categories) that NO name candidate mentions."""
    hay = [" ".join(_company_services(company)).lower()]
    try:
        prof = (_sb("GET", "/rest/v1/marketing_gbp_profiles?company_id="
                    f"eq.{company['id']}"
                    "&select=primary_category,additional_categories&limit=1")
                or [{}])[0]
        cats = ([prof.get("primary_category") or ""]
                + list(prof.get("additional_categories") or []))
        hay.append(" ".join(str(c) for c in cats).lower())
    except Exception:  # noqa: BLE001 — categories are best-effort
        pass
    blob = " | ".join(hay)
    names = " ".join(_norm_name(c["item"]) for c in cands)
    # RULE-OUT store (Santino 2026-09-18: the app must be able to resolve a
    # coverage refusal natively). A lane recorded in
    # rename_intent.name_ruled_out was CONSIDERED for the name and excluded
    # on purpose — it stays a service, it just doesn't block the pitch.
    ruled_out = set(((company.get("integration_settings") or {})
                     .get("rename_intent") or {}).get("name_ruled_out") or [])
    blocking, advisory = [], []
    for sell_stem, name_stem, blocks in _COVERAGE_TERMS:
        if sell_stem in blob and name_stem not in names:
            if sell_stem in ruled_out:
                advisory.append(f"{sell_stem} (ruled out of naming)")
                continue
            (blocking if blocks else advisory).append(sell_stem)
    return blocking, advisory


def _rename_candidates(company_id: str) -> list[dict]:
    """Open + chosen name candidates, best first. VERBATIM strings only —
    a name may never be composed in-conversation (registered-name law)."""
    rows = _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id="
               f"eq.{company_id}&item_type=eq.name&status=neq.dismissed"
               "&select=item,reason,confidence,status"
               "&order=confidence.desc") or []
    return rows


def _norm_name(s: str) -> str:
    # Dash normalization (Amin 09-13 typed an EN dash pasting the name
    # back) + &/and equivalence (DISS 09-14: the transcript said "and",
    # the researched candidate said "&", and the mismatch minted a
    # near-duplicate chosen row): every dash variant reads as a hyphen,
    # "&" reads as "and". The STORED candidate string stays canonical.
    s = re.sub(r"[‐-―−]", "-", str(s or ""))
    s = re.sub(r"\s*&\s*", " and ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def _merge_rename_intent(company_id: str, patch: dict,
                         dry_run: bool) -> None:
    if dry_run:
        print(f"    [dry-run] rename_intent <- {patch}")
        return
    co = (_sb("GET", f"/rest/v1/companies?id=eq.{company_id}"
              "&select=integration_settings") or [{}])[0]
    ints = co.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except (ValueError, TypeError):
            ints = {}
    ri = dict(ints.get("rename_intent") or {})
    ri.update(patch)
    ints["rename_intent"] = ri
    _sb("PATCH", f"/rest/v1/companies?id=eq.{company_id}",
        {"integration_settings": ints})


def _choose_candidate(company_id: str, item: str, dry_run: bool) -> None:
    if dry_run:
        print(f"    [dry-run] suggestion CHOSEN <- {item!r}")
        return
    _sb("PATCH", f"/rest/v1/marketing_gbp_suggestions?company_id="
        f"eq.{company_id}&item_type=eq.name&item=eq."
        f"{urllib.parse.quote(item)}", {"status": "chosen"})


def _apply_service_answer(company_id: str, term: str, offers: bool,
                          dry_run: bool) -> str:
    """Mirror of the app's clarifyTerm: yes writes companies.services (the
    single selected-services store, AI Dispatcher reads it too), no
    dismisses every non-chosen candidate naming the term."""
    term = term.strip().lower()
    if offers:
        label = _RENAME_SERVICE_LABELS.get(term) or term.title()
        if dry_run:
            return f"[dry-run] services += {label}"
        co = (_sb("GET", f"/rest/v1/companies?id=eq.{company_id}"
                  "&select=services") or [{}])[0]
        svcs = co.get("services") if isinstance(co.get("services"), list) else []
        if not any(term.split()[0] in str(s).lower() for s in svcs):
            _sb("PATCH", f"/rest/v1/companies?id=eq.{company_id}",
                {"services": svcs + [label]})
        return f"services += {label}"
    if dry_run:
        return f"[dry-run] dismiss candidates naming {term!r}"
    rows = _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id="
               f"eq.{company_id}&item_type=eq.name&select=item,status") or []
    doomed = [r["item"] for r in rows
              if term in str(r.get("item", "")).lower()
              and (r.get("status") or "") != "chosen"]
    for item in doomed:
        _sb("PATCH", f"/rest/v1/marketing_gbp_suggestions?company_id="
            f"eq.{company_id}&item_type=eq.name&item=eq."
            f"{urllib.parse.quote(item)}", {"status": "dismissed"})
    return f"dismissed {len(doomed)} candidate(s) naming {term!r}"


# Santino's preframe, verbatim (2026-09-12) — the pitch never opens with a
# bare "want a new name?".
RENAME_PITCH_BODY = (
    "We've been doing research and have determined a few different profile "
    "names that we believe are going to really help increase your visibility "
    "for high-intent jobs. Want me to send over what we came up with?")


def _rename_options_body(company: dict, cands: list[dict],
                         vertical: str,
                         notes: list[str] | None = None) -> str:
    """The options text: candidate strings QUOTED VERBATIM, numbered, with
    the plumbing license question and any service clarifications riding the
    same message. Deterministic on purpose — no model may rewrite a name.
    `notes` = per-conversation talking points set at pitch time (Santino
    2026-09-12, Dry Bros: Amin was lukewarm on mold before hearing it is a
    top-intent Illinois search term — the ponder-point rides the options)."""
    svc_hay = " ".join(_company_services(company)).lower()
    top = [c for c in cands if (c.get("status") or "") != "dismissed"][:3]
    lines = ["Here's what we like best, based on what people in your area "
             "actually search:"]
    for i, c in enumerate(top, 1):
        lines.append(f"{i}. {c['item']}")
    extras = []
    plumb = any("plumb" in _norm_name(c["item"]) for c in top)
    if plumb and vertical == "restoration":
        extras.append(
            "One note on the plumbing option: to advertise plumbing in the "
            "name you'd need a plumbing license connected to the business, "
            "either yours or a licensed partner you work with. Is that "
            "something you have or would be open to setting up?")
    if svc_hay:
        seen = set()
        for c in top:
            nm = _norm_name(c["item"])
            for phrase, key in (("mold", "mold"), ("sewage", "sewage"),
                                ("biohazard", "biohazard"),
                                ("asbestos", "asbestos"),
                                ("leak detection", "leak")):
                if phrase in nm and key not in svc_hay and phrase not in seen:
                    seen.add(phrase)
                    extras.append(f"Quick check: one of these mentions "
                                  f"{phrase}. Is that a service you plan on "
                                  "offering?")
    extras.extend(n.strip() for n in (notes or []) if n.strip())
    closer = ("Any of these feel right? Happy to walk through the thinking "
              "or tweak one.")
    return "\n".join(lines + [""] + extras + [closer]).replace("\n\n\n", "\n\n")


RENAME_REPLY_SYSTEM = """\
You are Monica from Santino's team at Restoration AI, mid-conversation with
a client about renaming their Google Business Profile. Warm, brief, human.
NEVER use em dashes or en dashes; use a comma or a period. Never sound
robotic, never say "reply YES" or similar; the client believes they are
texting a person and that must stay true.
<<RENAME_TRUTH>>
You are given the conversation stage, the candidate names ON RECORD, and
the client's message. Read what the client is doing and answer with JSON:
{"read": "interested|confirmed|declined|question|service_answer|dba_update|
          handoff|unrelated",
 "confirmed_name": string|null,
 "service_answers": [{"term": string, "offers": bool}],
 "reply": string|null,
 "reason": string}
- "interested": they want to see the options (or asked for them again).
- "confirmed": they clearly committed to ONE candidate. confirmed_name MUST
  be that candidate's EXACT string copied from the list, never retyped,
  never a paraphrase. A vague positive ("sounds good") with more than one
  candidate on the table is NOT confirmed, it is "question" — ask which one.
  EXCEPTION: when Monica's previous message proposed ONE specific name and
  they reply with a bare yes/agreement (or paste that same name back),
  that IS "confirmed" with confirmed_name = that exact name. Never re-ask
  someone to pick a name they just agreed to.
  THE EXCEPTION IS NARROW (Alfredo 2026-09-15: his "Cool / I like it"
  praised a name Monica RETRACTED seconds later, and the flow locked a
  different name he never picked): it applies ONLY when Monica's LATEST
  message proposed exactly one name. If her latest message offers a
  numbered choice ("reply 1 or 2") or lists several names, a bare positive
  is NEVER confirmed — it is "question", ask which. An agreement that
  arrived BEFORE a correction or a new set of options confirms nothing.
- "declined": they clearly do not want a rename at all.
- SERVICE-TERM OBJECTION (Santino 2026-09-14, the Frontline mold case):
  when they reject a name BECAUSE of a specific service word ("I don't
  want mold in my name"), that is NOT "declined" — it is "question", and
  your reply asks ONE clarifying question: which services do they most
  want to be found for? Their answer drives the next suggestion (the
  research volumes pick the strongest replacement term). Never just drop
  the term and guess a substitute without asking.
- "service_answer": they answered a service or license question (plumbing,
  mold, sewage...). Fill service_answers; term is the lowercase service
  word, offers is their answer. If they ALSO picked a name, use "confirmed"
  and still fill service_answers.
- "dba_update": they say the DBA/trade name is filed or they sent the
  paperwork. A message that is ONLY a photo (or a photo placeholder
  note) while the stage is awaiting_dba is "dba_update" — the photo is
  almost certainly the filing.
- "handoff": a RENAME-topic message that is angry, confused beyond text,
  or asking for Santino/a call about the rename.
- "unrelated": the message is about anything OTHER than the rename
  (website, billing, jobs, scheduling, photos...). Another system answers
  those; never use handoff for an off-topic message.
"reply" is your next text for question/service_answer/handoff reads (<=280
chars, no emojis); null for every other read (the system sends those).
When they ask for YOUR recommendation or best pick, GIVE it: name the
top candidate on the list (highest confidence) and its "why" in plain
words. We already did the research; never bounce the question back at
them, never answer a recommendation ask with another question.
QUOTE THE NUMBERS (Santino 2026-09-14, the DISS flood case): when they
ask why, doubt a term, or propose an alternative, cite the actual search
volumes from the candidate reasons ("mold remediation pulls about 2,900
searches a month in Pennsylvania, water damage about 1,000") — real
stats build trust and let them decide well. Only numbers present in the
reasons; never invent one.
INFORMED-CONSENT CHECK (Santino 2026-09-14): when the name they are
settling on OMITS the highest-volume term in the research, send ONE
transparency message before locking: the full numbers including what
they are passing up, framed as "just want you to have this data before
we commit", never as pushback. If the omitted term is plumbing, ALWAYS
pair its number with the license requirement in the same breath. One
check per decision — after they reaffirm, commit and never relitigate.
Rename conversations go to the PRIMARY contact only, never broadcast to
multiple people at the company.
Answer questions ONLY from the knowledge above; anything outside it is
"handoff". Never claim any step is already done."""
RENAME_REPLY_SYSTEM = RENAME_REPLY_SYSTEM.replace(
    "<<RENAME_TRUTH>>", RENAME_TRUTH + "\n" + RENAME_PLUMBING_PUSHBACK)

# ---- Rename Conversation v2 (Santino 2026-09-26, Greg/PuroClean) ----------
# "Number 2 probably best ... Any results on hoarding cleanup?" locked the
# name, recorded the hedge as consent, and dropped both questions. Law:
# HEDGE IS NOT CONSENT, QUESTIONS COME FIRST, objections get the playbook
# once (informed choice, never pressure twice).

_HEDGE_RE = re.compile(
    r"\b(probably|maybe|leaning|i think|possibly|might|likely|not sure|"
    r"i guess|perhaps)\b", re.I)
_PLUMBING_OBJ_RE = re.compile(r"plumb|licen[cs]e", re.I)
_QUESTION_TERM_RE = re.compile(
    r"\b([a-z]+(?:\s[a-z]+)?)\s+(cleanup|remediation|removal|restoration|"
    r"cleaning|repair|testing|abatement)\b", re.I)

# Client-facing essence, Santino's framing 2026-09-26. Two accurate risk
# channels, "very unlikely" explicit, ask-forgiveness stance, and the
# plumber-intent leverage story. No em dashes anywhere (house law; the
# send chokepoint strips them too).
PLUMBING_NAME_PLAYBOOK = (
    "A plumbing license is not required to put plumbing words in a Google "
    "Business Profile name. Google does not check licenses for names. The "
    "real risk is another company reporting the listing, and that is very "
    "unlikely. If a report went to Google, the worst case is the name gets "
    "reverted. If it went to the state contractors board, the worst case "
    "is a citation: you drop the word and pay a small fine. Clients "
    "generally take that trade because the extra business is pennies on "
    "the dollar against the risk; we move with ask forgiveness, not ask "
    "permission. And the bigger point: people with a burst pipe search "
    "for an emergency plumber when what they really need is water damage "
    "restoration. The plumber gets the call first and hands the job to a "
    "restoration company second. With plumbing in the listing name you "
    "get those calls first, which also gives you jobs to hand TO "
    "plumbers, so referral relationships start flowing your direction.")

RENAME_LEANING_SYSTEM = """\
You are Monica, the client concierge, mid-conversation about renaming the
client's Google Business Profile. The client just gave a TENTATIVE pick
(hedged, or with open questions). Your job, in ONE short SMS:
1. Answer EVERY question they asked, directly, first. When search volumes
   are provided below, cite them plainly; NEVER invent a number. If no
   data is provided for something they asked, say you'll pull the numbers
   and follow up, honestly.
2. If an OBJECTION PLAYBOOK is provided, work its substance in naturally,
   once. Never argue twice; after this message their choice stands.
3. End with exactly ONE short lock-in question that quotes their tentative
   pick VERBATIM in double quotes.
Rules: plain SMS under 900 characters, warm and human, no em dashes, no
emoji, no bullet lists, never claim an action was taken, never pressure.
Return JSON only: {"message": "..."}"""


def _extract_questions(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+", text or "")
            if s.strip().endswith("?")]


def _svc_volume(company: dict, term: str):
    """Statewide monthly search volume for one term, or None (fail-open)."""
    try:
        from gbp_name_suggest import load_dfs_creds
        from rename_autoseed import STATE_FULL
        st = (company.get("state") or "").strip()
        if not st:
            return None
        u, p = load_dfs_creds()
        r = requests.post(
            "https://api.dataforseo.com/v3/keywords_data/google_ads/"
            "search_volume/live", auth=(u, p),
            json=[{"keywords": [term.lower()], "language_code": "en",
                   "location_name":
                       f"{STATE_FULL.get(st.upper(), st)},United States"}],
            timeout=60)
        for tk in r.json().get("tasks") or []:
            for res in tk.get("result") or []:
                return res.get("search_volume") or 0
    except Exception:  # noqa: BLE001 — volumes are best-effort
        return None
    return None


def _rename_leaning_reply(company, contact, msg, pend, cands, item,
                          questions, hedged, state, dry_run) -> bool:
    """Answer-first reply for a hedged pick or a pick carrying questions.
    Sets stage back to options with pend['leaning'] so a clean unhedged
    yes afterwards locks the name through the normal confirm path."""
    body_txt = msg.get("body") or ""
    playbook = ""
    if (_PLUMBING_OBJ_RE.search(body_txt)
            and any("plumbing" in c["item"].lower() for c in cands)):
        playbook = PLUMBING_NAME_PLAYBOOK
    vols = []
    for m in _QUESTION_TERM_RE.finditer(" ".join(questions)):
        term = f"{m.group(1)} {m.group(2)}".lower()
        v = _svc_volume(company, term)
        if v is not None:
            vols.append(f"{term}: {v:,} searches/mo statewide")
    cand_lines = "\n".join(
        f"- {c['item']}"
        + (f"\n  research: {_clip(str(c.get('reason') or ''), 200)}"
           if c.get("reason") else "") for c in cands)
    result = anthropic_json(
        RENAME_LEANING_SYSTEM,
        f"Their tentative pick: {item}\n"
        f"Client message: {body_txt[:600]}\n"
        f"Their questions: {questions or '(none, hedged pick)'}\n"
        f"Search volumes pulled for their questions: "
        f"{'; '.join(vols) if vols else '(none available)'}\n"
        + (f"OBJECTION PLAYBOOK:\n{playbook}\n" if playbook else "")
        + f"Candidates on record:\n{cand_lines}")
    reply = str((result or {}).get("message") or "").strip()
    if not reply:
        reply = (f'Good questions, let me pull exact numbers and get right '
                 f'back to you. Meanwhile, want me to pencil in "{item}"?')
    reply = re.sub(r"\s*[\u2014\u2013]\s*", ", ", reply)
    for q in questions:
        keys = re.findall(r"[a-z]{5,}", q.lower())
        key = max(keys, key=len) if keys else ""
        if key and key not in reply.lower():
            print(f"    RENAME leaning: reply may not cover {key!r} "
                  f"(question: {q[:60]!r})")
    if "?" not in reply[-140:]:
        reply += f' Want me to lock in "{item}"?'
    sent = _rename_send(company, contact, reply, state, dry_run,
                        "leaning", pend)
    if sent and pend is not None:
        pend["stage"] = "options"
        pend["leaning"] = item
        pend.pop("chosen", None)
        _rename_save(company["id"], pend, dry_run)
        print(f"    RENAME leaning: answered first, lock-in pending on "
              f"{item!r} (hedged={bool(hedged)}, "
              f"questions={len(questions)})")
    return True




# 2B: DBA DOCUMENT INTAKE (Santino 2026-09-12). When the filing paperwork
# arrives as a texted photo, vision reads the document, extracts the
# registered trade name, and compares it to the CHOSEN candidate string.
# EXACT (normalized) match -> auto-write rename_intent.dba_filed +
# dba_name — the same string-bound shape brightlocal.rename_gate checks,
# so the citations gate clears itself with zero clicks. Mismatch -> the
# escalation carries both strings side by side (the client filed the
# wrong name = the exact failure the gate exists to catch). A text CLAIM
# without a document never auto-marks anything.
DBA_EXTRACT_SYSTEM = """\
You are reading a photo a client texted, expected to be a DBA / trade
name / assumed business name filing (state or county registration
paperwork, a certificate, or a filing confirmation page or email).
Return ONLY JSON:
{"is_dba_document": bool,
 "dba_related": bool,
 "document_kind": string,
 "registered_name": string|null,
 "state": string|null,
 "filed_on": "YYYY-MM-DD"|null,
 "confidence": "high|medium|low"}
is_dba_document is TRUE only for the actual filing document: the
recorded/stamped registration, certificate, or an official filing
confirmation that SHOWS the registered trade name. registered_name is
the EXACT trade name string on that document, copied character for
character including punctuation like hyphens, ampersands and slashes.
null when unreadable.
dba_related is TRUE for paperwork that is part of a DBA filing journey
but does NOT prove the recorded name: certified-mail or postage
receipts for an envelope to a county clerk or Secretary of State,
payment receipts for filing fees, unstamped or blank application
forms, photos of the envelope itself. document_kind is a short plain
name for what the photo shows, e.g. "certified-mail receipt",
"filing fee receipt", "unstamped application form".
Both are false for job photos, screenshots of anything else, or
unrelated paperwork."""


def _dba_chosen_name(pend: dict | None, cands: list[dict]) -> str | None:
    return (pend or {}).get("chosen") or next(
        (c["item"] for c in cands
         if (c.get("status") or "") == "chosen"), None)


def _dba_extract(company: dict, images: list[dict]) -> dict | None:
    """Vision-read a candidate DBA document. None = not readable as one."""
    try:
        doc = anthropic_json(DBA_EXTRACT_SYSTEM,
                             f"The business is {company.get('name')}. "
                             "Read the attached document.", images=images)
    except Exception as e:  # noqa: BLE001
        print(f"    DBA vision extract failed ({str(e)[:80]})")
        return None
    if doc.get("is_dba_document") and doc.get("registered_name"):
        return doc
    if doc.get("dba_related"):
        # Kin paperwork (mailing receipt, fee receipt, blank form): the
        # caller sends the what-comes-next reply instead of silence.
        return doc
    return None


def _dba_related_reply(company: dict, contact: dict, doc: dict,
                       source: str, state: dict, dry_run: bool,
                       pend: dict | None = None) -> str:
    """Jim/CRW 2026-09-21: he texted the certified-mail receipt for his
    county filing and the only response was the generic upload ack, so he
    believed he was done while the stage sat waiting on a certificate he
    did not know he owed. DBA-related paperwork that is NOT the recorded
    document gets a reply that names what arrived and what still clears
    the gate. dba_verified stays unset."""
    kind = str(doc.get("document_kind") or "paperwork").strip() or "paperwork"
    body = (f"Got it, thank you! That looks like the {kind}, so the "
            "filing is in motion. The piece that clears us to start is "
            "the recorded copy that comes back showing the exact name. "
            "Text a photo of that when it lands and we'll take it from "
            "there.")
    _rename_send(company, contact, body, state, dry_run, "dba-related")
    append_escalation(
        company, None,
        f"DBA-RELATED document from {source}: reads as {kind!r}, not the "
        "recorded certificate. Client was told exactly what to send "
        "next; dba_verified stays unset.", dry_run)
    if pend is not None:
        pend.setdefault("notes", []).append(
            f"{datetime.now(timezone.utc).date().isoformat()}: {kind} "
            "received (not the certificate); awaiting the recorded copy")
        _rename_save(company["id"], pend, dry_run)
    return "related"


def _dba_store(company_id: str, image_b64: str, dry_run: bool) -> str | None:
    """Keep a durable copy of the verified filing at docs/dba/verified-*.jpg
    (the 'verified-' prefix marks a SYSTEM write: the upload sweep must
    never re-verify our own copy). Returns the public URL."""
    path = (f"{company_id}/docs/dba/verified-"
            f"{int(datetime.now(timezone.utc).timestamp())}.jpg")
    if dry_run:
        print(f"    [dry-run] would store filing copy -> branding/{path}")
        return f"(dry-run) branding/{path}"
    try:
        sb_url = os.environ["SUPABASE_URL"].rstrip("/")
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        r = requests.post(
            f"{sb_url}/storage/v1/object/branding/{path}",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "image/jpeg"},
            data=base64.b64decode(image_b64), timeout=60)
        r.raise_for_status()
        return f"{sb_url}/storage/v1/object/public/branding/{path}"
    except Exception as e:  # noqa: BLE001 — the link is nice-to-have
        print(f"    DBA copy store failed ({str(e)[:80]})")
        return None


def _dba_apply(company: dict, contact: dict, chosen: str, doc: dict,
               doc_url: str | None, source: str, state: dict,
               dry_run: bool) -> str:
    """Shared outcome for every DBA arrival lane (texted, emailed, hub
    upload): exact match auto-clears the citations gate, mismatch holds it
    with both strings side by side. Returns 'match' or 'mismatch'."""
    reg = str(doc["registered_name"]).strip()
    filed_on = doc.get("filed_on")
    if _norm_name(reg) == _norm_name(chosen):
        _merge_rename_intent(company["id"], {
            "dba_filed": True, "dba_name": reg,
            "dba_filed_at": filed_on,
            "dba_doc_url": doc_url,
            "dba_verified": "vision_auto",
            "dba_verified_at": datetime.now(timezone.utc).isoformat()},
            dry_run)
        append_escalation(
            company, None,
            f"DBA VERIFIED from {source}: {reg!r} matches the chosen name "
            f"(filed {filed_on or 'date unreadable'}"
            + (f"; document: {doc_url}" if doc_url else "")
            + "). Citations gate is CLEAR — the citation order can run, "
            "then the GBP change.", dry_run, ping=True)
        body = ("Got it, the filing looks perfect. That's everything we "
                "need from you. We'll start rolling the new name out "
                "across your listings and handle the Google update from "
                "here. I'll keep you posted.")
        _rename_send(company, contact, body, state, dry_run, "dba-verified")
        return "match"
    append_escalation(
        company, None,
        f"DBA MISMATCH from {source}: document reads {reg!r} but the "
        f"chosen name is {chosen!r}"
        + (f" (document: {doc_url})" if doc_url else "")
        + ". Monica asked them to check; verify the document by eye "
        "before anything runs.", dry_run, ping=True)
    body = (f"Thanks for sending that over. One thing, the filing reads "
            f"\"{reg}\" but the name we're setting up is \"{chosen}\". "
            "Those need to match exactly for Google. Can you double "
            "check the filing on your end?")
    _rename_send(company, contact, body, state, dry_run, "dba-mismatch")
    return "mismatch"


def _verify_dba_document(company: dict, contact: dict, msg: dict,
                         pend: dict, cands: list[dict], state: dict,
                         dry_run: bool) -> str | None:
    """Texted/emailed lane: vision-verify a filing from the message's
    images. Returns 'match' / 'mismatch' when handled, None when there is
    no readable DBA document (caller falls back to the ask-for-photo
    path)."""
    chosen = _dba_chosen_name(pend, cands)
    if not chosen:
        return None
    images = _vision_blocks(msg.get("attachments"))
    if not images and msg.get("messageType") == "TYPE_EMAIL":
        # Emailed filings arrive as inline images, not attachments
        images = _email_inline_vision(msg)
    if not images:
        return None
    doc = _dba_extract(company, images)
    if not doc:
        return None
    if not doc.get("is_dba_document"):
        return _dba_related_reply(company, contact, doc,
                                  "a texted photo", state, dry_run, pend)
    doc_url = _dba_store(company["id"], images[0]["data"], dry_run)
    verdict = _dba_apply(company, contact, chosen, doc, doc_url,
                         "a texted filing photo", state, dry_run)
    if verdict == "match":
        pend["stage"] = "dba_verified"
        _rename_save(company["id"], pend, dry_run)
    return verdict


def _verify_dba_upload(company: dict, contact: dict, rel: str,
                       state: dict, dry_run: bool) -> str:
    """Hub-tile lane: a file landed in branding/{cid}/docs/dba/ via the
    red DBA tile; the 10-minute upload sweep routes it here instead of the
    generic thank-you. Downloads the object, vision-verifies, and runs the
    same match/mismatch outcome as the texted lane."""
    cid = company["id"]
    # ALREADY-VERIFIED DEDUPE (Jared 2026-09-15: he re-uploaded the same
    # filing after a thread mixup and got the full "filing looks perfect"
    # confirmation twice, 20 minutes apart). Once dba_verified is set, any
    # further DBA upload is filed quietly — no second confirmation text.
    _ri = ((company.get("integration_settings") or {})
           .get("rename_intent") or {})
    if _ri.get("dba_verified"):
        print(f"    [dba] {cid}: already verified "
              f"({_ri.get('dba_verified_at', '?')}) — duplicate upload "
              "filed silently, no re-confirmation")
        return "already_verified"
    sb_url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    try:
        r = requests.get(
            f"{sb_url}/storage/v1/object/branding/{cid}/{rel}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=60)
        r.raise_for_status()
        if rel.lower().endswith(".pdf"):
            # PDFs go straight through as a document block (DVC's recorded
            # FFN certificate, 2026-09-22).
            images = [{"media_type": "application/pdf",
                       "data": base64.b64encode(r.content).decode()}]
        else:
            from io import BytesIO
            from PIL import Image
            img = Image.open(BytesIO(r.content)).convert("RGB")
            w, h = img.size
            if max(w, h) > 1568:
                s = 1568 / max(w, h)
                img = img.resize((round(w * s), round(h * s)))
            buf = BytesIO()
            img.save(buf, "JPEG", quality=80)
            images = [{"media_type": "image/jpeg",
                       "data": base64.b64encode(buf.getvalue()).decode()}]
    except Exception as e:  # noqa: BLE001
        append_escalation(company, None,
                          f"a file arrived on the DBA upload tile "
                          f"({rel}) but could not be read — check it by "
                          f"eye ({str(e)[:80]})", dry_run, ping=True)
        return "unreadable"
    cands = _rename_candidates(cid)
    chosen = _dba_chosen_name(None, cands)
    if not chosen:
        append_escalation(company, None,
                          f"a DBA document was uploaded ({rel}) but NO name "
                          "is chosen on the Profile Rename card — decide "
                          "the name, then verify the filing by eye",
                          dry_run, ping=True)
        return "no_chosen"
    doc = _dba_extract(company, images)
    if not doc:
        append_escalation(company, None,
                          f"the DBA-tile upload ({rel}) does not read as a "
                          "DBA filing — check it by eye and mark the "
                          "Citations card manually if it is one",
                          dry_run, ping=True)
        return "unreadable"
    if not doc.get("is_dba_document"):
        return _dba_related_reply(company, contact, doc,
                                  "the hub DBA upload", state, dry_run)
    doc_url = f"{sb_url}/storage/v1/object/public/branding/{cid}/{rel}"
    return _dba_apply(company, contact, chosen, doc, doc_url,
                      "the hub DBA upload", state, dry_run)


RENAME_PITCH_EMAIL_SUBJECT = "A visibility idea for your Google listing"


def _rename_send(company: dict, contact: dict, body: str, state: dict,
                 dry_run: bool, label: str, pend: dict | None = None,
                 channel: str = "sms", operator: bool = False) -> bool:
    grounding = outbound_guard(body, None)
    if grounding:
        print(f"    RENAME {label} BLOCKED (outbound guard): {grounding}")
        append_escalation(company, None,
                          f"rename {label} blocked by the outbound guard "
                          f"({grounding})", dry_run, ping=True)
        return False
    # VERBATIM DEDUPE (Alfredo 2026-09-15/18: the confirm body went out
    # twice 13s apart, then replayed word-for-word 3 days later when an
    # unrelated question was misread). The same rename text never goes to
    # the same client twice in a row, whatever branch produced it.
    if pend is not None and (pend.get("last_outbound") or "")[:400] == body[:400]:
        print(f"    RENAME {label} SKIPPED (verbatim repeat of last outbound)")
        return False
    print(f"    RENAME {label} ({len(body)} chars) -> {body!r}")
    # Conversation memory (Amin 09-13: "Yes" after a specific proposal got
    # "which name did you mean?"): the last outbound rides the state so the
    # next classify sees what Monica just said.
    if pend is not None:
        pend["last_outbound"] = body[:400]
        _rename_save(company["id"], pend, dry_run)
    if dry_run:
        return True
    try:
        # channel/operator (2026-09-18 app pitch button): email rides the
        # same body + laws; an operator click is the human speaking, so it
        # is exempt from the talk-over-a-human window (send_now precedent).
        res = send_message(
            contact, channel, body,
            subject=RENAME_PITCH_EMAIL_SUBJECT if channel == "email" else None,
            company=company, human_hold_exempt=operator)
        record_sent_message(state, res)
    except SendBlocked as e:
        # Writes/pings already happened; a held text must not kill the
        # sweep or the inbound pass (quiet window, allowlist, hold).
        print(f"    RENAME {label} send BLOCKED: {str(e)[:120]}")
        append_escalation(company, None,
                          f"rename {label} text could not be delivered "
                          f"({str(e)[:100]}) — send it by hand if needed",
                          dry_run)
        return False
    return True


def _rename_kv(cid: str) -> str:
    return f"rename-convo:{cid}"


def _rename_state(cid: str) -> dict | None:
    """Rename-conversation state lives in its OWN kv key (2026-09-13
    incident: it briefly lived inside the monolithic concierge-state blob,
    and a concurrent 10-min upload sweep's read-modify-write clobbered it
    within 30 minutes of the Dry Bros pitch — Amin's 'Yes plz' then got a
    generic reply instead of the options). A dedicated key can't be
    clobbered by whole-state savers."""
    v = kv_get(_rename_kv(cid))
    return v if isinstance(v, dict) and v.get("stage") not in (None, "closed") else None


def _rename_save(cid: str, pend: dict | None, dry_run: bool) -> None:
    if dry_run:
        return
    kv_set(_rename_kv(cid), pend if pend else {"stage": "closed"})


def handle_rename_reply(company: dict, contact: dict, msg: dict,
                        state: dict, dry_run: bool) -> bool:
    """Consume a client message inside a live rename conversation. Returns
    True when the message belonged to this flow."""
    pend = _rename_state(company["id"]) or (
        company_state(state, company["id"]).get("rename_convo"))
    if not pend:
        return False
    cands = _rename_candidates(company["id"])
    if not cands:
        # Empty candidates INSIDE a live conversation is a repair case, not
        # an exit (ACS/Alfredo 2026-09-15: "we don't do mold" dismissed all
        # four options, the flow silently closed itself mid-conversation and
        # the card went blank while the client was still engaged). Keep the
        # state, escalate for a re-seed, and let the message flow onward so
        # the composer can still answer naturally.
        if (pend or {}).get("stage") in ("pitched", "options", "confirmed"):
            append_escalation(
                company, msg,
                "rename conversation is LIVE but every name candidate was "
                "dismissed (likely a service objection) — re-seed corrected "
                "candidates now, the client is mid-conversation", dry_run,
                ping=True)
            return False
        _rename_save(company["id"], None, dry_run)
        return False
    # Trivial burst noise ("!?", "??", "ok" alone with a real message right
    # behind it) must never earn its own reply — Amin 09-13: a two-message
    # burst got two disjointed answers and Monica read as forgetful.
    body_txt = (msg.get("body") or "").strip()
    # A bare digit is NEVER noise after a numbered options list — it IS the
    # answer (Mike/Arch 2026-09-14: he picked "2" two minutes after the
    # options text and the trivial-burst filter ate his selection).
    is_option_pick = bool(re.fullmatch(r"[1-9]", body_txt)) and (
        str((pend or {}).get("stage")) == "options"
        or bool(re.search(r"\n\s*2[\.\)]", str((pend or {}).get("last_outbound") or ""))))
    if (pend and not msg.get("attachments") and not is_option_pick and
            len(re.sub(r"[^A-Za-z0-9]", "", body_txt)) <= 2):
        print(f"    RENAME: consuming trivial burst fragment {body_txt!r}")
        return True
    # AWAITING-DBA ATTACHMENT FAST-PATH (Jim/CRW 2026-09-21: his
    # certified-mail receipt arrived as an attachment-only text, the LLM
    # read never routed it to the DBA lane, and the only reply was the
    # generic upload ack — he believed he was done). While we wait on the
    # DBA, any texted image is FIRST tried as DBA paperwork,
    # deterministically; non-paperwork photos fall through to the normal
    # read.
    if (pend and str(pend.get("stage")) == "awaiting_dba"
            and msg.get("attachments")):
        verdict = _verify_dba_document(company, contact, msg, pend,
                                       cands, state, dry_run)
        if verdict:
            return True
    vertical = _company_vertical(company)
    # Reasons + confidence ride along so Monica can ANSWER "what's your
    # best pick?" from the research instead of bouncing the question back
    # (Amin 09-13: "Let me know what ur best pick is" got a deflection).
    cand_lines = "\n".join(
        f"- {c['item']}"
        + (f" [confidence {c.get('confidence')}]" if c.get("confidence") else "")
        + (" (already chosen)" if (c.get("status") or "") == "chosen" else "")
        + (f"\n  why: {_clip(str(c.get('reason') or ''), 180)}"
           if c.get("reason") else "")
        for c in cands)
    result = anthropic_json(
        RENAME_REPLY_SYSTEM,
        f"Company: {company.get('name')}\n"
        f"Vertical: {vertical}\n"
        f"Conversation stage: {pend.get('stage')}\n"
        f"Monica's previous message: "
        f"{_clip(str(pend.get('last_outbound') or '(none on record)'), 380)}\n"
        f"Candidate names ON RECORD:\n{cand_lines}\n\n"
        f"Client message: {(msg.get('body') or '')[:600]}")
    read = (result.get("read") or "").strip().lower()
    if read == "unrelated":
        return False
    # Service/license answers apply on ANY read that carries them.
    for sa in (result.get("service_answers") or []):
        term = str(sa.get("term") or "").strip().lower()
        if not term:
            continue
        if term == "plumbing" and vertical != "restoration":
            continue
        note = _apply_service_answer(company["id"], term,
                                     bool(sa.get("offers")), dry_run)
        print(f"    RENAME service answer: {term} -> "
              f"{'yes' if sa.get('offers') else 'no'} ({note})")
    quote_txt = (msg.get("body") or "").strip()[:300]
    if read == "confirmed":
        # ALREADY CONFIRMED — IDEMPOTENT (Alfredo 2026-09-18: with the
        # convo at awaiting_dba, his "Are you the ones making AI YouTube
        # videos on my behalf?" was misread as a fresh confirmation and the
        # 3-day-old confirm text replayed verbatim). Once a name is chosen
        # and DBA instructions are out, a re-read of "confirmed" writes
        # nothing and sends nothing; the message flows to the normal
        # composer, which can actually answer what they said.
        if pend.get("stage") in ("awaiting_dba", "dba_verified") and pend.get("chosen"):
            print("    RENAME confirm re-read ignored (stage "
                  f"{pend['stage']}, chosen already locked) — passing "
                  "message to the normal composer")
            return False
        want = _norm_name(result.get("confirmed_name"))
        # A clean short yes after a LEANING exchange locks the pending pick
        # (v2: the leaning reply promised exactly this).
        if not want and pend.get("leaning") and len(quote_txt.split()) <= 8 \
                and re.search(r"\b(yes|yep|yeah|lock|confirmed|go with|"
                              r"sounds good|do it|let'?s do)\b",
                              quote_txt, re.I):
            want = _norm_name(pend["leaning"])
        match = next((c for c in cands if _norm_name(c["item"]) == want), None)
        if not match:
            # CLIENT-AUTHORED NAME (Amin 09-13 proposed his own variant):
            # a full name in THEIR words containing their brand is consent,
            # not a mismatch — it becomes a real candidate row (same as the
            # app's custom-name input) and the flow proceeds string-bound
            # on it. Anything short/brandless still gets the re-ask.
            proposed = re.sub(r"[‐-―−]", "-",
                              str(result.get("confirmed_name") or "")).strip()
            brand_word = (company.get("name") or "").split()[0].lower()
            if (len(proposed.split()) >= 5 and brand_word
                    and brand_word in proposed.lower()):
                if not dry_run:
                    _sb("POST", "/rest/v1/marketing_gbp_suggestions", {
                        "company_id": company["id"], "item_type": "name",
                        "item": proposed, "source": "client_conversation",
                        "verdict": "ADD", "confidence": 0.7,
                        "auto_safe": False, "status": "open",
                        "reason": ("Client proposed this exact wording by "
                                   f"text: \"{quote_txt}\"")})
                match = {"item": proposed}
                print(f"    RENAME client-authored candidate: {proposed!r}")
            else:
                # String-bound law: no exact candidate match, no write.
                body = ("Just so I lock in the right one, which of the "
                        "names I sent should we go with? I want it exact "
                        "before we start the paperwork.")
                _rename_send(company, contact, body, state, dry_run, "re-ask", pend)
                return True
        # v2 GATE (Santino 2026-09-26): hedge or open questions = NOT
        # consent. Answer first, then one clean lock-in.
        _qs = _extract_questions(msg.get("body") or "")
        _hedged = bool(_HEDGE_RE.search(quote_txt))
        if _qs or _hedged:
            return _rename_leaning_reply(company, contact, msg, pend,
                                         cands, match["item"], _qs,
                                         _hedged, state, dry_run)
        _choose_candidate(company["id"], match["item"], dry_run)
        _merge_rename_intent(company["id"], {
            "decision": "rename",
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "source": "monica_sms",
            "consent_quote": quote_txt}, dry_run)
        append_escalation(
            company, None,
            f"PROFILE RENAME CONFIRMED by text: {match['item']!r}. Client's "
            f"words: \"{quote_txt}\". DBA instructions sent; verify the "
            "filing when it comes in, then mark DBA filed on the Citations "
            "card (citations run before the GBP change).", dry_run, ping=True)
        body = (f"Perfect, we'll move forward with \"{match['item']}\". "
                "The next step is on your side: file a DBA (trade name) "
                "with the state for exactly that name, letter for letter. "
                "Once it's filed, text us a photo of the paperwork and "
                "we'll take it from there. Is that something you can get "
                "started on this week?")
        _rename_send(company, contact, body, state, dry_run, "confirm", pend)
        pend["stage"] = "awaiting_dba"
        pend["chosen"] = match["item"]
        _rename_save(company["id"], pend, dry_run)
        return True
    if read == "declined":
        _merge_rename_intent(company["id"], {
            "decision": "keep",
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "source": "monica_sms",
            "consent_quote": quote_txt}, dry_run)
        append_escalation(
            company, None,
            f"profile rename DECLINED by text (\"{quote_txt}\") — "
            "rename_intent set to keep, citations unblocked under the "
            "current name", dry_run)
        body = ("No problem at all, we'll keep your current name. "
                "Everything else stays right on track.")
        _rename_send(company, contact, body, state, dry_run, "decline")
        _rename_save(company["id"], None, dry_run)
        return True
    if read == "interested":
        body = _rename_options_body(company, cands, vertical,
                                    pend.get("notes"))
        _rename_send(company, contact, body, state, dry_run, "options", pend)
        pend["stage"] = "options"
        _rename_save(company["id"], pend, dry_run)
        return True
    if read == "dba_update":
        if msg.get("attachments"):
            verdict = _verify_dba_document(company, contact, msg, pend,
                                           cands, state, dry_run)
            if verdict:
                return True
            # attachment present but unreadable as a DBA doc — human eyes
            append_escalation(
                company, msg,
                "client sent what looks like the DBA but vision could not "
                "verify it — check docs/inbox and mark the Citations card "
                "by hand", dry_run, ping=True)
            return True
        append_escalation(
            company, None,
            f"client says the DBA is FILED (\"{quote_txt}\") — verify the "
            "certificate, then mark DBA filed on the Citations card so "
            "citations can run", dry_run, ping=True)
        body = ("Awesome. Can you text over a photo of the filing so we "
                "have it on record? Then we'll get everything rolling.")
        _rename_send(company, contact, body, state, dry_run, "dba-ask", pend)
        return True
    if read == "handoff":
        append_escalation(
            company, msg,
            "rename conversation needs a human "
            f"({(result.get('reason') or '')[:120]})", dry_run, ping=True)
        return True
    # question / service_answer: the model's own short reply, guarded.
    body = _fit_sms((result.get("reply") or "").strip(), 240, 300,
                    label=" [rename]")
    if body:
        _rename_send(company, contact, body, state, dry_run, "reply", pend)
    pend["last_at"] = datetime.now(timezone.utc).isoformat()
    _rename_save(company["id"], pend, dry_run)
    return True


def cmd_rename_pitch(args) -> int:
    """Open the rename conversation for ONE company (Dry Bros pilot,
    2026-09-12). Dry run prints the opener; --send delivers + arms the
    reply flow."""
    state = load_state()
    dry_run = not getattr(args, "send", False)
    companies = fetch_companies([args.company])
    company = companies.get(args.company)
    if not company:
        print(f"ERROR: no company {args.company}")
        return 1
    if company_inactive(company):
        print(f"ERROR: {company.get('name')} is not active")
        return 1
    cands = _rename_candidates(args.company)
    # HOLD placeholders (TDI 2026-09-18): research can deliberately park a
    # client with a "(rename on hold)" row whose reason documents why (TDI:
    # mid-identity-transition + suppressed services). Those rows are state,
    # not options — pitching one would text the client our internal note.
    holds = [c for c in cands
             if "(rename on hold)" in str(c.get("item", "")).lower()
             or str(c.get("reason", "")).strip().upper().startswith("HOLD")]
    cands = [c for c in cands if c not in holds]
    if holds and not cands:
        why = str(holds[0].get("reason") or "no reason recorded")
        print(f"RENAME ON HOLD: {why[:220]}")
        return 1
    if not cands:
        print("ERROR: no name candidates on record — seed them first "
              "(rank-ai-gbp-rename)")
        return 1
    if any((c.get("status") or "") == "chosen" for c in cands):
        print("NOTE: a name is already chosen — nothing to pitch")
        return 0
    target = messaging_target(company)
    contact_id = target.get("ghl_contact_id") or linked_contact_id(company)
    if not contact_id:
        print("ERROR: no GHL contact for this company")
        return 1
    contact_payload = None
    try:
        data = _ghl("GET", f"/contacts/{contact_id}")
        contact_payload = (data or {}).get("contact") or data
    except Exception:  # noqa: BLE001
        pass
    hours = business_hours_check(company, contact_payload)
    if hours and not dry_run:
        print(f"HELD (quiet hours): {hours}")
        return 1
    if hours:
        print(f"  (note: a --send right now would be held: {hours})")
    contact = {"id": contact_id,
               "phone": (target.get("cell")
                         or (contact_payload or {}).get("phone")),
               "email": (target.get("email")
                         or (contact_payload or {}).get("email"))}
    print(f"pitching {company.get('name')} "
          f"({len(cands)} candidate(s), vertical "
          f"{_company_vertical(company)}):")
    for c in cands[:4]:
        print(f"  - [{c.get('confidence')}] {c['item']}")
    blocking, advisory = _rename_coverage_gaps(company, cands)
    if advisory:
        print(f"  (coverage note: {', '.join(advisory)} sold but unnamed — "
              "usually fine, minor lanes)")
    if blocking:
        print(f"  !! COVERAGE GAP: {', '.join(blocking)} — sold as a "
              "service or live as a GBP category, but NO candidate names "
              "it. Seed a candidate (or rule it out) before pitching.")
        if not getattr(args, "force", False):
            print("  refusing to pitch an incomplete slate "
                  "(--force overrides)")
            return 1
    notes = [n for n in (getattr(args, "note", None) or []) if n.strip()]
    # PRIMARY-CATEGORY NUDGE (Santino 2026-09-18, QCI "General contractor"
    # discovery): a restoration company whose GBP primary category is not
    # Water damage restoration service is competing in the wrong map pack,
    # and the rename conversation is the natural moment to say so. Data-
    # driven from the synced profile, so it never fires falsely; the client
    # agreeing becomes an escalation (Monica passes it along, never claims
    # the flip herself).
    if _company_vertical(company) == "restoration":
        try:
            _prof = (_sb("GET", "/rest/v1/marketing_gbp_profiles?company_id="
                         f"eq.{company['id']}&select=primary_category&limit=1")
                     or [{}])[0]
            _cur = str(_prof.get("primary_category") or "").strip()
            if _cur and _cur.lower() != "water damage restoration service":
                notes.append(
                    f"We also noticed the profile's primary category is set "
                    f"to '{_cur}'. We recommend switching it to 'Water damage "
                    "restoration service', it is the single biggest lever for "
                    "showing up when people search for water damage help "
                    "nearby. Say the word and we will handle the switch.")
                print(f"  (auto-note: primary category '{_cur}' -> "
                      "recommending Water damage restoration service)")
        except Exception:  # noqa: BLE001 — the nudge must never block a pitch
            pass
    if notes or dry_run:
        preview = _rename_options_body(company, cands,
                                       _company_vertical(company), notes)
        print(f"  options text that would follow ({len(preview)} chars):")
        for ln in preview.splitlines():
            print(f"    | {ln}")
    if not _rename_send(company, contact, RENAME_PITCH_BODY, state,
                        dry_run, "pitch",
                        channel=getattr(args, "channel", "sms") or "sms",
                        operator=getattr(args, "operator", False)):
        return 1
    if not dry_run:
        _rename_save(company["id"], {
            "stage": "pitched", "notes": notes,
            "at": datetime.now(timezone.utc).isoformat()}, dry_run)
        save_state(state, dry_run)   # sent-id bookkeeping only
        print("rename conversation ARMED (own kv key, clobber-proof)")
    return 0


# Vision for inbound analysis (Santino 2026-08-02: Angie texted a
# screenshot of a browser warning; Monica couldn't see it and Santino had
# to answer manually). Cost guard: only the first VISION_MAX_IMAGES images
# per message, videos/documents skipped, big images downscaled + JPEG
# re-encoded before the base64 ride to the model.
VISION_MAX_IMAGES = 2


def _email_inline_vision(msg: dict) -> list[dict]:
    """Inline <img> images from a GHL email message -> vision blocks.
    GHL serves them behind the API bearer, so plain downloads 403."""
    try:
        mid = (((msg.get("meta") or {}).get("email") or {}).get("messageIds")
               or [None])[0]
        if not mid:
            return []
        em = _ghl("GET", f"/conversations/messages/email/{mid}")
        body = (em.get("emailMessage") or em).get("body") or ""
        srcs = re.findall(r'<img[^>]+src="(https?://[^"]+)"', body)[:VISION_MAX_IMAGES]
        out: list[dict] = []
        for u in srcs:
            try:
                r = requests.get(u, timeout=45, headers={
                    "Authorization": f"Bearer {os.environ['GHL_API_KEY']}",
                    "Version": GHL_VERSION})
                if not r.ok or len(r.content) < 8000:
                    continue  # tracking pixels / tiny signature marks
                from io import BytesIO
                from PIL import Image
                img = Image.open(BytesIO(r.content)).convert("RGB")
                w, h = img.size
                if max(w, h) > 1568:
                    sc = 1568 / max(w, h)
                    img = img.resize((round(w * sc), round(h * sc)))
                buf = BytesIO()
                img.save(buf, "JPEG", quality=80)
                import base64 as _b64
                out.append({"media_type": "image/jpeg",
                            "data": _b64.b64encode(buf.getvalue()).decode()})
            except Exception:  # noqa: BLE001
                continue
        return out
    except Exception:  # noqa: BLE001
        return []


_ATT_TAG_KEY = "attachment-vision-tags"
_ATT_TAG_CACHE: dict = {}
_ATT_TAG_LOADED = [False]


def attachment_vision_tags(urls: list | None) -> str | None:
    """One human-readable line per inbound image, so the composer SEES what
    the client sent (ACS 2026-09-19: "We don't do the rebuild" arrived WITH
    a screenshot of our own preview site's FAQ, circled — text-only history
    rendered it "[sent 1 photo attachment]", Monica read the words through
    the rename lens and proposed unlocking a locked name). Each URL is
    classified ONCE ever (ops_kv cache), so history replays are free.
    Returns e.g. "images: screenshot of the client's own preview website
    (FAQ section about rebuild, circled in red)" or None."""
    imgs = [u for u in (urls or [])
            if str(u).rsplit(".", 1)[-1].lower()
            not in ("mp4", "mov", "m4v", "mpg4", "avi", "vcf", "csv")]
    if not imgs:
        return None
    if not _ATT_TAG_LOADED[0]:
        try:
            _ATT_TAG_CACHE.update(kv_get(_ATT_TAG_KEY) or {})
        except Exception:  # noqa: BLE001
            pass
        _ATT_TAG_LOADED[0] = True
    import hashlib
    keys = [hashlib.sha1(str(u).encode()).hexdigest()[:16] for u in imgs]
    fresh = [u for u, k in zip(imgs, keys) if k not in _ATT_TAG_CACHE]
    if fresh:
        blocks = _vision_blocks(fresh)
        if blocks:
            try:
                out = anthropic_json(
                    "You classify images a client texted to their marketing "
                    "agency, for a conversation transcript. For EACH image, "
                    "one sentence: what it is and what it shows. If it is a "
                    "website screenshot, say whose site it appears to be "
                    "(browser address bar, logo, branding — e.g. 'the "
                    "client's own preview website (rankai-*.pages.dev)' vs "
                    "a third-party or competitor site), which section/page "
                    "is visible, and any client markup (circles, arrows). "
                    "If it is a document (DBA filing, W9, invoice), name "
                    "it. If a photo of real-world work, say so plainly.",
                    'Return STRICT JSON: {"images": [{"line": str}]} — one '
                    f"entry per image, {len(blocks)} image(s) attached, in "
                    "order.", max_tokens=800, images=blocks)
                lines = [str(x.get("line") or "").strip()
                         for x in (out.get("images") or [])]
            except Exception as e:  # noqa: BLE001 — vision never blocks history
                print(f"    [att-vision] failed ({str(e)[:60]})")
                lines = []
            it = iter(lines)
            changed = False
            for u, k in zip(imgs, keys):
                if k in _ATT_TAG_CACHE or u not in fresh:
                    continue
                ln = next(it, "")
                if ln:
                    _ATT_TAG_CACHE[k] = {"line": ln[:300], "at":
                                         datetime.now(timezone.utc).isoformat()}
                    changed = True
            if changed:
                try:
                    while len(_ATT_TAG_CACHE) > 500:
                        _ATT_TAG_CACHE.pop(next(iter(_ATT_TAG_CACHE)))
                    kv_set(_ATT_TAG_KEY, _ATT_TAG_CACHE)
                except Exception:  # noqa: BLE001
                    pass
    tags = [(_ATT_TAG_CACHE.get(k) or {}).get("line") for k in keys]
    tags = [t for t in tags if t]
    return ("images: " + "; ".join(tags)) if tags else None


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


def _ein_ask_pending(company: dict) -> bool:
    """True when we asked this client for their EIN and still lack one."""
    try:
        cid = company["id"]
        setup = (_sb("GET", f"/rest/v1/company_phone_setup?id=eq.{cid}"
                     "&select=business_ein") or [None])[0]
        if not setup or setup.get("business_ein"):
            return False
        return bool(_sb("GET", "/rest/v1/marketing_ops_notes?"
                        f"company_id=eq.{cid}&body=like.*EIN-ASK-{cid}*"
                        "&select=id&limit=1"))
    except Exception:  # noqa: BLE001
        return False


def _write_captured_ein(company: dict, ein: str, source: str,
                        dry_run: bool) -> None:
    """One write path for every EIN capture (text or document): both stores
    (phone setup = compliance pipeline, companies.ein = the app's Business
    Verification card) + one activity line. companies.ein only fills a
    blank, never overwrites a human entry."""
    cid = company["id"]
    print(f"  [ein-capture] {company.get('name')}: EIN {ein} "
          f"captured from {source}" + (" [dry-run]" if dry_run else ""))
    if dry_run:
        return
    _sb("PATCH", f"/rest/v1/company_phone_setup?id=eq.{cid}",
        {"business_ein": ein}, prefer="return=minimal")
    _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}&ein=is.null",
        {"ein": ein}, prefer="return=minimal")
    _sb("POST", "/rest/v1/marketing_work_log", {
        "company_id": cid, "actor": "concierge",
        "category": "compliance", "action": "ein-captured",
        "detail": f"EIN {ein} captured from {source}; toll-free "
                  "verification submits on the next watch cycle"},
        prefer="return=minimal")


def _maybe_capture_ein_from_document(company: dict, jpeg_bytes: bytes,
                                     dry_run: bool) -> None:
    """Clients answer the EIN ask with a photo of the IRS CP-575 / W-9 as
    often as with typed digits — read the number off the document. Gated
    exactly like the text capture (we asked + still missing). Never fatal."""
    try:
        if not _ein_ask_pending(company):
            return
        import base64 as _b64
        out = anthropic_json(
            "You read one photographed/scanned business document. Find the "
            "US federal EIN (Employer Identification Number, 9 digits, "
            'usually formatted XX-XXXXXXX). Reply ONE JSON object: '
            '{"ein": "XX-XXXXXXX"} or {"ein": null} if no EIN is clearly '
            "visible. Never guess digits.",
            "Extract the EIN if present.",
            max_tokens=600,
            images=[{"media_type": "image/jpeg",
                     "data": _b64.b64encode(jpeg_bytes).decode()}])
        m = _EIN_RE.search(str(out.get("ein") or ""))
        if not m:
            return
        ein = f"{m.group(1)}-{m.group(2)}"
        if ein.startswith("00"):
            return
        _write_captured_ein(company, ein, "a document they sent", dry_run)
    except Exception as e:  # noqa: BLE001
        print(f"  [ein-capture-doc] failed: {str(e)[:120]}")


_EIN_RE = re.compile(r"\b(\d{2})[- ]?(\d{7})\b")


def _maybe_email_lookback(company: dict, msgs: list[dict], dry_run: bool) -> None:
    """SMS says "I already emailed it" -> search the mailbox history for that
    client's past mail, file what we find (attachments, EIN), and leave a
    note so the reply thread can say "found it" instead of re-asking
    (Santino 2026-09-05; Fran Carlo case). Never fatal."""
    try:
        blob = " ".join(str(m.get("body") or "") for m in msgs)[:1500]
        import email_intake  # lazy: email_intake imports this module at load
        if not email_intake._CLAIM_RE.search(blob):
            return
        verdict = anthropic_json(email_intake.CLAIM_SYSTEM, blob)
        if not verdict.get("claim"):
            return
        print(f"  [{company.get('name')}] says they emailed it — searching "
              "mailbox history")
        notes = email_intake.email_lookback(
            company["id"], company, verdict.get("keywords") or [], dry_run)
        if notes and not dry_run:
            _sb("POST", "/rest/v1/marketing_ops_notes",
                {"company_id": company["id"], "status": "open",
                 "body": "[EMAIL-LOOKBACK] Client said they emailed it; found "
                         "and filed: " + " | ".join(notes)[:800]},
                prefer="return=minimal")
    except Exception as e:  # noqa: BLE001
        print(f"  (email lookback errored: {str(e)[:100]})")



def _maybe_capture_credentials(company: dict, msgs: list[dict], dry_run: bool) -> None:
    """Images a client sends often ARE the answer (Michael Oren 2026-09-10:
    his IICRC Certified Firm certificate photo got a generic "Got it, thanks"
    three times while Monica kept re-asking for the number in text). Every
    NEW inbound image runs through vision once; credential identifiers
    (IICRC firm/tech numbers, state licenses, EINs, insurance certs) are
    stored on companies.integration_settings.certifications, which composes
    read as a standing FACT so the question can never come back. Each
    attachment is scanned exactly once (vision_seen ledger). Never fatal."""
    try:
        import hashlib
        urls: list[str] = []
        for m in msgs:
            if m.get("direction") != "inbound":
                continue
            for u in (m.get("attachments") or []):
                ext = str(u).rsplit(".", 1)[-1].lower()
                if ext in ("jpg", "jpeg", "png", "webp", "heic", "gif"):
                    urls.append(str(u))
        if not urls:
            return
        cid = company["id"]
        co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}"
                  "&select=integration_settings") or [{}])[0]
        ints = co.get("integration_settings") or {}
        if isinstance(ints, str):
            ints = json.loads(ints)
        certs = ints.setdefault("certifications", {})
        seen = ints.setdefault("vision_seen", [])
        todo = []
        for u in urls:
            h = hashlib.md5(u.encode()).hexdigest()[:16]
            if h not in seen:
                todo.append((u, h))
        if not todo:
            return
        changed = False
        for u, h in todo[:4]:   # cost cap per run
            blocks = _vision_blocks([u])
            seen.append(h)
            changed = True
            if not blocks:
                continue
            try:
                out = anthropic_json(
                    "You read a photo a home-services business owner texted "
                    "to their marketing team. Extract any credential "
                    "identifiers visible: certification numbers, license or "
                    "registration numbers, EINs, insurance policy numbers. "
                    "Reply ONLY with JSON: {\"credentials\": [{\"kind\": "
                    "one of iicrc_firm|iicrc_tech|state_license|ein|"
                    "insurance|other, \"label\": what the document is, "
                    "\"number\": the identifier exactly as printed, "
                    "\"holder\": the name it is issued to or null, "
                    "\"valid_through\": YYYY-MM-DD or null}]}. Empty list "
                    "if the photo has no credential document.",
                    "Extract credential identifiers from this photo.",
                    max_tokens=1200, images=blocks)
            except Exception as e:  # noqa: BLE001 — one bad image never stops the pass
                print(f"  [cred-capture] vision failed for {u[-24:]}: {str(e)[:80]}")
                continue
            for cred in (out.get("credentials") or []):
                num = str(cred.get("number") or "").strip()
                kind = str(cred.get("kind") or "other").strip() or "other"
                if not num:
                    continue
                key = kind if kind != "other" else re.sub(
                    r"[^a-z0-9]+", "_", str(cred.get("label") or "other").lower())[:40]
                if (certs.get(key) or {}).get("number") == num:
                    continue
                entry = {"number": num, "label": cred.get("label"),
                         "holder": cred.get("holder"),
                         "valid_through": cred.get("valid_through"),
                         "source": "client photo (vision capture)",
                         "captured_at": datetime.now(timezone.utc).isoformat()}
                if dry_run:
                    print(f"  [cred-capture] would store {key}: {num}")
                    continue
                certs[key] = entry
                print(f"  [cred-capture] stored {key}: {num} "
                      f"({cred.get('label')})")
        if changed and not dry_run:
            ints["vision_seen"] = seen[-100:]
            _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                {"integration_settings": ints})
    except Exception as e:  # noqa: BLE001
        print(f"  [cred-capture] failed: {str(e)[:120]}")


def credentials_fact(company: dict) -> str | None:
    """Standing compose FACT line listing credentials already on file, so
    Monica never asks for a number a client already sent (the Michael Oren
    rule). Reads the same store _maybe_capture_credentials writes."""
    try:
        ints = company.get("integration_settings") or {}
        if isinstance(ints, str):
            ints = json.loads(ints)
        certs = ints.get("certifications") or {}
        parts = [f"{k.replace('_', ' ')} number {v.get('number')}"
                 for k, v in certs.items() if v.get("number")]
        return "; ".join(parts) if parts else None
    except Exception:  # noqa: BLE001
        return None


def _maybe_capture_ein(company: dict, msgs: list[dict], dry_run: bool) -> None:
    """Toll-free auto-registration loop (Santino 2026-09-03): when we've
    asked a client for their EIN (an EIN-ASK-{cid} marker note exists) and
    their phone setup still lacks one, scan their inbound texts for it and
    write it to the account. tollfree_autoreg.py's watch cycle then submits
    the Twilio verification automatically. Never fatal — a capture failure
    must not break inbound processing."""
    try:
        cid = company["id"]
        setup = (_sb("GET", f"/rest/v1/company_phone_setup?id=eq.{cid}"
                     "&select=business_ein") or [None])[0]
        if not setup or setup.get("business_ein"):
            return
        asked = _sb("GET", "/rest/v1/marketing_ops_notes?"
                    f"company_id=eq.{cid}&body=like.*EIN-ASK-{cid}*"
                    "&select=id&limit=1")
        if not asked:
            return
        for m in msgs:
            hit = _EIN_RE.search(str(m.get("body") or ""))
            if not hit:
                continue
            ein = f"{hit.group(1)}-{hit.group(2)}"
            if ein.startswith("00"):
                continue
            _write_captured_ein(company, ein, "their text message", dry_run)
            return
    except Exception as e:  # noqa: BLE001
        print(f"  [ein-capture] failed: {str(e)[:120]}")


# Inbound URLs -> backlink tracker (Santino 2026-09-08: Rob Carpenter sent
# his RIA and Chamber listing links by SMS on consecutive days; Monica acked
# "we'll keep it on file" both times but nothing stored them — both needed
# manual capture). Domain fragment -> marketing_backlinks target_key.
_BACKLINK_DOMAIN_MAP = {
    "restorationindustry.org": "ria",
    "chamber": "chamber",           # rosevillechamber.com, vegaschamber.com...
    "iicrc": "iicrc",
    "candrmagazine.com": "cr-magazine",
    "restorationandremediation.com": "rr-magazine",
    "contractorconnection.com": "contractor-connection",
}
_URL_RE = re.compile(r"https?://[^\s<>\"']+")


def _maybe_capture_backlinks(company: dict, msgs: list[dict], dry_run: bool) -> None:
    """When a client texts/emails a link to one of their backlink-target
    listings (RIA profile, chamber directory page...), file it on the
    matching marketing_backlinks row so 'we'll keep it on file' is true.
    The daily checker flips the row live once the page links their domain.
    Never fatal."""
    try:
        cid = company["id"]
        for m in msgs:
            for url in _URL_RE.findall(str(m.get("body") or "")):
                host = url.split("/")[2].lower() if url.count("/") >= 2 else ""
                key = next((k for frag, k in _BACKLINK_DOMAIN_MAP.items()
                            if frag in host), None)
                if not key:
                    continue
                row = (_sb("GET", "/rest/v1/marketing_backlinks?"
                           f"company_id=eq.{cid}&target_key=eq.{key}"
                           "&select=id,status,url") or [None])[0]
                if not row or row.get("url"):  # no target row / already filed
                    continue
                if dry_run:
                    print(f"  [backlink-capture] would file {key}: {url}")
                    continue
                _sb("PATCH", f"/rest/v1/marketing_backlinks?id=eq.{row['id']}",
                    {"url": url,
                     "status": ("requested" if row.get("status") == "target"
                                else row.get("status")),
                     "note": "Listing link sent in by the client; the daily "
                             "checker flips this live once the page links "
                             "their site."})
                print(f"  [backlink-capture] filed {key} for {cid}: {url}")
    except Exception as e:  # noqa: BLE001
        print(f"  [backlink-capture] failed: {str(e)[:120]}")


# Review-list opt-outs (Santino 2026-09-09, RX/Barbara incident: Roy asked
# to remove a review-campaign recipient, Monica answered "pulling Barbara
# off the list now" with no tool behind the words, and the final drip step
# fired a week later). This hook IS the tool: detect the ask, resolve the
# person, execute the opt-out in the review engine, VERIFY it, and only
# then file the [FOR MONICA] directive containing words she may say. An
# unresolvable target (no phone, ambiguous first name — RX had THREE
# Barbaras) never guesses: it asks for name+number and pings Santino.
_OPTOUT_INTENT_RE = re.compile(
    r"(?i)\b(remove\b.{0,40}\bfrom|take\b.{0,40}\boff|off\s+the\s+list|"
    r"stop\s+(?:send|text|contact)\w*|no\s+more\s+(?:text|message)\w*|"
    r"opt\s*[- ]?out|unsubscribe|don'?t\s+(?:send|text))")
# The unresolved path pings Santino, so it needs this second signal too —
# a resolved person is its own confirmation, loose phrasing alone is not.
_OPTOUT_CONTEXT_RE = re.compile(
    r"(?i)\b(lists?|texts?|texting|messages?|campaigns?|reviews?)\b")
_OPTOUT_PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b")


def _optout_do(contact_row: dict, dry_run: bool) -> bool:
    """Opt one contact out of the review engine and VERIFY the write.
    True only when the re-read shows opted_out on the contact AND on every
    review_requests row. False (never an exception) otherwise."""
    ct_id = contact_row["id"]
    if dry_run:
        print(f"  [optout] would opt out {contact_row.get('name')} "
              f"({contact_row.get('phone')})")
        return True
    _sb("PATCH", f"/rest/v1/review_requests?contact_id=eq.{ct_id}",
        {"opted_out": True, "next_send_at": None})
    _sb("PATCH", f"/rest/v1/contacts?id=eq.{ct_id}", {"opted_out": True})
    ct = (_sb("GET", f"/rest/v1/contacts?id=eq.{ct_id}&select=opted_out")
          or [{}])[0]
    rrs = _sb("GET", f"/rest/v1/review_requests?contact_id=eq.{ct_id}"
              "&select=opted_out") or []
    ok = bool(ct.get("opted_out")) and all(r.get("opted_out") for r in rrs)
    print(f"  [optout] {contact_row.get('name')} "
          f"({contact_row.get('phone')}): "
          f"{'DONE and verified' if ok else 'VERIFY FAILED'}")
    return ok


def _optout_directive(cid: str, marker: str, body: str,
                      dry_run: bool) -> None:
    """File a [FOR MONICA] directive once (marker-deduped, open notes only)."""
    if _sb("GET", "/rest/v1/marketing_ops_notes?"
           f"company_id=eq.{cid}&body=like.*{marker}*"
           "&status=not.eq.resolved&select=id&limit=1"):
        return
    if dry_run:
        print(f"  [optout] would file directive {marker}")
        return
    _sb("POST", "/rest/v1/marketing_ops_notes",
        {"company_id": cid, "body": body, "author": "optout-hook",
         "status": "open"})


def _maybe_execute_optout(company: dict, msgs: list[dict],
                          dry_run: bool) -> None:
    """When an inbound client message asks to remove someone from the
    review texts, actually remove them, verified, before anyone answers.
    Never fatal — a failure here must not break inbound processing (the
    unresolved path still escalates, so the ask can't silently die)."""
    try:
        cid = company["id"]
        text = " ".join(str(m.get("body") or "") for m in msgs)
        if not _OPTOUT_INTENT_RE.search(text):
            return
        sender_last10 = ""
        for m in msgs:
            frm = str(m.get("from") or m.get("contact_phone") or "")
            digits = re.sub(r"\D", "", frm)
            if len(digits) >= 10:
                sender_last10 = digits[-10:]
        # 1) phones named in the message that belong to a stored contact
        targets: dict[str, dict] = {}
        for raw in _OPTOUT_PHONE_RE.findall(text):
            last10 = re.sub(r"\D", "", raw)[-10:]
            if len(last10) != 10 or last10 == sender_last10:
                continue
            for row in _sb("GET", "/rest/v1/contacts?"
                           f"client_id=eq.{cid}&phone=like.*{last10}"
                           "&select=id,name,phone,opted_out") or []:
                targets[row["id"]] = row
        # 2) no phone matched: try a UNIQUE name match among this client's
        # enrolled contacts (full-name or single-token, case-insensitive)
        ambiguous = False
        if not targets:
            enrolled = _sb("GET", "/rest/v1/contacts?"
                           f"client_id=eq.{cid}&select=id,name,phone,"
                           "opted_out&limit=1000") or []
            low = text.lower()
            words = set(re.findall(r"[a-z]+", low))
            stop = {"the", "and", "her", "him", "them", "please", "stop",
                    "send", "sending", "texts", "list", "from", "remove",
                    "customer", "more", "any"}
            def _toks(r):
                return [t for t in re.findall(
                    r"[a-z]+", str(r.get("name") or "").strip().lower())
                    if len(t) >= 3 and t not in stop]
            def _full_hit(r):
                name = str(r.get("name") or "").strip().lower()
                return _toks(r) and len(name) >= 5 and name in low
            # a full-name match beats first-name-token matches: "take
            # Barbara Hess off" is Hess alone, not all three Barbaras
            hits = [r for r in enrolled if _full_hit(r)]
            if not hits:
                hits = [r for r in enrolled
                        if any(t in words for t in _toks(r))]
            if len(hits) == 1:
                targets[hits[0]["id"]] = hits[0]
            elif len(hits) > 1:
                ambiguous = True
        if targets:
            for row in targets.values():
                if _optout_do(row, dry_run):
                    toks = str(row.get("name") or "").split()
                    first = toks[0] if toks else "they"
                    _optout_directive(
                        cid, f"OPTOUT-{row['id']}",
                        f"[FOR MONICA] OPTOUT-{row['id']} done and "
                        f"verified: {row.get('name')} ({row.get('phone')}) "
                        "is permanently removed from the review text list. "
                        "Confirm it to the client in one short line, e.g. "
                        f"'Done, {first} is off the review list for good, "
                        "verified on our end.' Nothing else.", dry_run)
                else:
                    append_escalation(
                        company, msgs[-1] if msgs else None,
                        f"OPT-OUT VERIFY FAILED for {row.get('name')} "
                        f"({row.get('phone')}) — remove by hand NOW: "
                        f"{text[:150]!r}", dry_run, ping=True)
            return
        # 3) unresolved: never guess, never confirm — ask + ping Santino
        # (only with the second context signal, so a loose "don't send the
        # invoice yet" can never generate a false opt-out escalation)
        if not _OPTOUT_CONTEXT_RE.search(text):
            return
        digest = hashlib.sha1(text[:200].encode()).hexdigest()[:8]
        _optout_directive(
            cid, f"OPTOUT-ASK-{digest}",
            f"[FOR MONICA] OPTOUT-ASK-{digest} a removal was requested but "
            f"the person could not be identified"
            + (" (several contacts share that name)" if ambiguous else "")
            + ". Ask for their full name and mobile number in one short "
            "line. Do NOT say anyone was removed.", dry_run)
        append_escalation(
            company, msgs[-1] if msgs else None,
            "OPT-OUT REQUEST could not be auto-resolved"
            + (" (multiple name matches)" if ambiguous else "")
            + f" — identify and remove by hand: {text[:150]!r}",
            dry_run, ping=True)
    except Exception as e:  # noqa: BLE001
        print(f"  [optout] failed: {str(e)[:120]}")


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

    Returns {"processed", "matched", "awaiting", "escalated", "queued",
    "feedback_seen"} ("queued" = site-work tasks routed to the dev-agent
    inbox, "feedback_seen" = client_feedback blocks the classifier found;
    both 08-05, and both are what the heartbeat records)."""
    company_id = company["id"]
    out = {"processed": 0, "matched": 0, "awaiting": False, "escalated": 0,
           "queued": 0, "feedback_seen": 0}
    handled = set(state.get("handled_msg_ids") or [])
    msgs = [m for m in msgs if m["id"] not in handled]
    if msgs:
        _maybe_capture_ein(company, msgs, dry_run)
        _maybe_capture_credentials(company, msgs, dry_run)
        _maybe_capture_backlinks(company, msgs, dry_run)
        _maybe_execute_optout(company, msgs, dry_run)
        _maybe_email_lookback(company, msgs, dry_run)
    if not msgs:
        return out
    open_items = gather_items(company_id)
    # Last ~10 history messages disambiguate short replies ("yes",
    # "the second one") against what was actually asked.
    history = fetch_history(contact_id, max_msgs=CLASSIFY_HISTORY_MSGS)
    history_block = (
        f"\n\nRecent conversation history (newest first; 'them' = the "
        f"client, 'us' = our side, 'us-human' = a real person on our team, "
        f"usually Santino — an 'us-human' line is never the client "
        f"speaking) — use it to disambiguate short "
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
        # DURABLE CLAIM FIRST (2026-08-05): the in-memory ledger below is not
        # written until the end of the run, so it cannot stop a second pass
        # that starts while this one is still debouncing.
        if not claim_inbound_message(msg["id"], dry_run):
            print(f"    [already claimed by another pass — skipping "
                  f"{msg['id']}]")
            _record_handled(state, msg["id"])
            continue
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
                # ANY successfully-filed kind is HANDLED (Santino 2026-09-24:
                # screenshots and documents that ingested fine still pinged
                # his cell "couldn't auto-file" — RT Olson's proof screenshot
                # was classified, stored, and escalated anyway). Monica sees
                # what arrived (the vision tag rides the composer's history)
                # and answers it herself. Escalate ONLY when ingest produced
                # nothing at all.
                filed = (media["photos"] + media["videos"]
                         + media.get("screenshots", 0)
                         + media.get("documents", 0)
                         + media.get("brand_refs", 0))
                if filed:
                    n = media["photos"] + media["videos"]
                    if media.get("screenshots") or media.get("documents"):
                        msg["body"] = (
                            "(the client sent "
                            f"{media.get('screenshots', 0)} screenshot(s)/"
                            f"{media.get('documents', 0)} document(s) with "
                            "no message — the images are attached and "
                            "already filed on our side. If it is a "
                            "screenshot of a problem or an error, analyze "
                            "the image and answer the problem it shows; if "
                            "it is paperwork, confirm receipt and what "
                            "happens next. Never say it failed to file.)")
                    else:
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
        # ADD-CONTACT fast path (Chris Pappas 2026-09-23: "add Chris Pappas
        # to this text thread ... 910-448-2930" got "we're getting Chris
        # added now" and NOTHING executed). Deterministic: request-shape +
        # a phone number in the text -> actually add the card, then confirm
        # the DONE state truthfully. No phone/no name -> normal flow (the
        # composer's contract makes it a pass-to-Santino).
        try:
            _acm = _ADD_CONTACT_RE.search(msg.get("body") or "")
            _phm = _PHONE_IN_TEXT_RE.search(msg.get("body") or "")
            _nm = re.search(r"\badd\s+([A-Z][A-Za-z'\-]+)"
                            r"(?:\s+([A-Z][A-Za-z'\-]+))?",
                            msg.get("body") or "")
            if _acm and _phm and _nm:
                _card = add_secondary_contact(
                    company, _nm.group(1), _nm.group(2) or "",
                    "".join(_phm.groups()),
                    dry_run=dry_run)
                if _card:
                    _fn = _card["first_name"]
                    if not dry_run:
                        send_message(contact_for_flow, "sms",
                                     f"Done, {_fn} is added as a contact "
                                     "on your account.",
                                     company=company,
                                     reply_to=msg.get("id"))
                    else:
                        print(f"    [dry-run] would confirm {_fn} added")
                    continue
        except SendBlocked as _sb_e:
            print(f"    add-contact confirm blocked: {_sb_e}")
            continue
        except Exception as _e:  # noqa: BLE001 — fall through to normal flow
            print(f"    add-contact fast path warn: {str(_e)[:90]}")
        if handle_reschedule_reply(company, contact_for_flow, msg,
                                   state, dry_run):
            continue
        if handle_booking_reply(company, contact_for_flow, msg,
                                state, dry_run):
            continue
        if handle_rename_reply(company, contact_for_flow, msg,
                               state, dry_run):
            continue
        # purpose= comes from the item's help_text: WHY-questions must be
        # answered from it, never invented (Curt/Home Pride 2026-08-03:
        # Monica said the supplier question was "for the ads setup" when
        # its stated purpose is the supplier/dealer listing-links program).
        # A MONICA: script replaces the internal headline here too — at 110/140
        # chars the script was always cut off entirely, so a re-ask on this
        # path spoke the ops-board wording every time.
        def _item_line(it):
            purpose, script = split_monica_script(it.get("detail"))
            head = (f"- id={it['id']} kind={it['kind']} "
                    f"type={it['field_type']} ")
            if script:
                return (head + f"script={_clip(script, 320)!r}"
                        + (f" purpose={_clip(purpose, 120)!r}" if purpose else ""))
            return (head + f"q={_clip(it['text'], 110)!r}"
                    + (f" purpose={_clip(purpose, 140)!r}" if purpose else ""))

        item_list = "\n".join(_item_line(it) for it in open_items) or "(none)"
        # Vision: the analysis SEES what they texted (screenshots, photos).
        vision = (_vision_blocks(msg.get("attachments"))
                  if msg.get("attachments") else [])
        # Emails carry screenshots INLINE in the HTML body, not in the
        # attachments array (Bobby Olson 2026-09-05: "It says Robert" +
        # an inline screenshot that named a different company's drip).
        if not vision and msg.get("messageType") == "TYPE_EMAIL":
            vision = _email_inline_vision(msg)
            if vision:
                print(f"    [vision] {len(vision)} inline email image(s) attached")
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
        # Computed here, ahead of every early `continue` below: a request for
        # a phone call must never be swallowed as an ack or a "none" verdict
        # (2026-08-05). Monica cannot dial, so this always reaches a human.
        call_ask = client_asked_for_a_call(msg["body"])
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
        # SATISFIED BY CONVERSATION (2026-08-04): the reply says an open item
        # is already handled / not needed / doesn't apply. Record the client's
        # own words as the answer so nothing ever re-asks it, and log the
        # close so Santino can audit (or reverse) it. Double-locked —
        # conversation_satisfies() must agree with the classifier.
        for flag in result.get("satisfied_by_conversation") or []:
            it = next((i for i in open_items
                       if i["id"] == flag.get("item_id")), None)
            if not it or it["id"] in matched_ids:
                continue
            quote = str(flag.get("quote") or "").strip() or msg["body"][:300]
            if close_satisfied_by_conversation(
                    company, it, quote, str(flag.get("reason") or ""),
                    who=contact_first_name(contact_payload, company),
                    when=msg["ts"].isoformat(), dry_run=dry_run):
                matched_ids.add(it["id"])
                # A satisfied item is closed, not answered TO us: it must not
                # trigger the answer-follow-through reply ("thanks for the
                # list") — the turn's normal handling covers the response.
                turn["intel"].add(it["id"])
        out["matched"] += len(matched_ids)
        turn["matched"] |= matched_ids
        # CLIENT FEEDBACK -> WORK (Santino 2026-08-05). The reply says
        # something we BUILT is wrong. Route it to the dev-agent inbox now,
        # before any of the early `continue`s below: a message can be a pure
        # ack for reply purposes and still carry a correction, and the
        # correction must not depend on whether we owed them a text.
        # route_feedback decides auto ([DEV], runs tonight, no clicks) vs
        # ask-Santino ([TODO-PROPOSED]); see scripts/feedback_router.py.
        # EMAIL-CLAIM TRIPWIRE (Phase 2.1, Santino 2026-09-22): a text
        # saying "I emailed it" starts a 2h clock. The polled mailboxes
        # normally ingest it (the lookback handles history); the watchdog
        # alarm fires only when NOTHING arrives — the client emailed an
        # address we don't poll, or a typo swallowed it.
        try:
            _b = msg.get("body") or ""
            if (re.search(r"\bemailed\b|\b(sent|forwarded|send)\b[^.]{0,40}"
                          r"\bemail\b|\bemail\b[^.]{0,30}\b(sent|over)\b",
                          _b, re.I)
                    and not re.search(
                        r"\b(tomorrow|tonight|later|next week|in the "
                        r"morning)\b|'ll send|will send|going to send",
                        _b, re.I)):
                _claims = kv_get("email-claim-watch") or {}
                cidk = str(company.get("id"))
                if cidk not in _claims:
                    _claims[cidk] = {
                        "at": datetime.now(timezone.utc).isoformat(),
                        "quote": (msg.get("body") or "")[:200]}
                    if not dry_run:
                        kv_set("email-claim-watch", _claims)
                    print("    [email-claim] watch armed (2h) — text says "
                          "an email was sent")
        except Exception:  # noqa: BLE001 — tripwire never breaks a poll
            pass
        fbs = result.get("client_feedback") or []
        out["feedback_seen"] = out.get("feedback_seen", 0) + len(fbs)
        if fbs:
            try:
                from feedback_router import route_feedback
                routed = route_feedback(
                    company, fbs,
                    who=contact_first_name(contact_payload, company),
                    when=msg["ts"].isoformat(), dry_run=dry_run,
                    escalate=lambda r: append_escalation(
                        company, msg, r, dry_run, ping=False))
                if routed:
                    out["queued"] = out.get("queued", 0) + len(routed)
            except Exception as e:  # noqa: BLE001 — queuing never kills a poll
                print(f"    [feedback] router unavailable ({str(e)[:90]}) — "
                      "escalating so it is not lost")
                append_escalation(
                    company, msg,
                    "client feedback needing site work could not be queued "
                    f"automatically: {str(fbs)[:300]}", dry_run, ping=False)
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
        if (result.get("ack") or resp_need == "none") and not matched_ids \
                and not call_ask:
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
        bkg = result.get("booking") or {}
        if bkg.get("requested"):
            handle_booking_request(company, contact_for_flow,
                                   bkg.get("preference") or "",
                                   state, dry_run)
            continue
        negative = result.get("sentiment") == "negative"
        needs_answer = (bool(result.get("needs_answer"))
                        or resp_need in ("answer", "answer_by_boss")
                        or "?" in (msg["body"] or ""))
        needs_santino = (bool(result.get("needs_santino"))
                         or resp_need == "answer_by_boss")
        answers_ours = (not matched_ids and not needs_answer
                        and _replies_to_our_question(contact_for_flow, msg))
        if answers_ours:
            needs_answer = True
            print("    answers OUR last question (one-off offer/ask) — "
                  "owed the follow-through")
        # BEING ASKED FOR A CALL IS A needs_santino EVENT BY DEFINITION
        # (Santino 2026-08-05, Tony/Coastal: "Call me when u have a minute"
        # classified as an ordinary question and Monica promised the call
        # herself). Nothing in this system can dial a phone, so this never
        # depends on the classifier noticing: the reply becomes the handoff,
        # and Santino is texted the same second so a human actually calls.
        if call_ask:
            needs_answer = True
            needs_santino = True
            if not turn.get("call_ask_escalated"):
                escalate_call_request(company, msg, msg["body"], dry_run)
                turn["call_ask_escalated"] = True
            if not (suggested and "santino" in suggested.lower()):
                suggested = CALL_HANDOFF_REPLY
            print("    CALL REQUEST — handing to Santino; reply is the "
                  "handoff, never a promise to dial")
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
                or (not result.get("matches") and not had_cards
                    and not matched_ids and not answers_ours)):
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

    # PROOF OF LIFE for the classify stage (2026-08-05). Stamped here, after
    # phase 1 and before any of phase 2's early returns, so it records what
    # we SAW regardless of what we decided to send. `inputs` = messages
    # classified, `outputs` = feedback blocks the classifier found in them:
    # a run of inbound messages that never yields a single feedback block is
    # how a broken classifier would look, and silence_watch cards it.
    try:
        from heartbeat import stamp
        stamp("inbound-classify", inputs=out["processed"],
              outputs=out.get("feedback_seen", 0), dry_run=dry_run,
              queued=out.get("queued", 0), company=company.get("name"))
    except Exception as e:  # noqa: BLE001 — bookkeeping never blocks a reply
        print(f"    [heartbeat] warn: {str(e)[:90]}")

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
                                      "channel": channel, "kind": kind,
                                      **_email_thread_fields(turn["last_msg"])}
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
        # Hub link rides every inline reply (2026-09-18, Alfredo: "Let me
        # have an email" was unanswerable because this context had no link
        # for the FILE DESTINATION TRUTH rule to point at).
        hub = photo_upload_link(company)
        reply = anthropic_json(
            REPLY_SYSTEM,
            f"Client first name: {contact_first_name(None, company)}\n"
            f"Hub upload link (for any file/list/photo sends): "
            f"{hub or 'none on file'}\n"
            f"They just said (one burst, oldest first): {combined}\n{nxt}")
        body_out = (reply.get("body") or "").strip()
        # Concision is a hard rule on EVERY path, not just compose
        # (Santino 2026-08-04).
        body_out = _fit_sms(body_out, SMS_TARGET_CHARS, SMS_MAX_CHARS,
                            label=" [inline-reply]")
        print(f"    reply draft ({len(body_out)} chars): {body_out!r}")
        # Inline replies carry no ledger context: any DONE-claim about
        # reviews/posts/requests is unsupported by construction — the
        # compose backstop (which has the ledger) takes over instead. The
        # persona, registrar and capability halves need no context at all.
        grounding = outbound_guard(body_out, None)
        if grounding:
            print(f"    GUARD WARNING: {grounding}")
            # A blocked CALL promise is replaced, not dropped: the client
            # asked for a call and deserves the true answer now (2026-08-05).
            swap = honest_substitute(grounding, combined)
            if swap:
                print(f"    GUARD SUBSTITUTION -> {swap!r}")
                body_out = swap
                escalate_call_request(company, turn["last_msg"], combined,
                                      dry_run)
                grounding = None
        if do_send and body_out:
            if grounding:
                print("    SEND SKIPPED (outbound guard) — the compose "
                      "backstop carries the follow-through with ledger "
                      "context")
                return out
            # Send window enforced on EVERY send path (client's local tz).
            # This is a REPLY to turn["last_msg"], so it may use the
            # fast-reply/shoulder allowance; quiet hours still refuse.
            hours_reason = business_hours_check(company, contact_payload,
                                                reply_to=stamp_at)
            if hours_reason:
                print(f"    SEND FLAGGED: {hours_reason} — reply not "
                      f"sent this cycle")
                append_escalation(company, turn["last_msg"], hours_reason,
                                  dry_run)
                return out
            reply_key = _reply_key({"at": stamp_at})
            dup = repeats_recent_outbound(company_id, body_out, history,
                                          reply_to=reply_key)
            if dup:
                print(f"    SEND SKIPPED: {dup} — the compose backstop "
                      "carries the follow-through")
                return out
            target = messaging_target(company)
            contact = {"id": contact_id,
                       "phone": target.get("cell") or company.get("phone"),
                       "email": target.get("email") or company.get("email")}
            # Email inline reply: thread into the email being answered (2d).
            _th = (_email_thread_fields(turn["last_msg"])
                   if channel == "email" else {})
            try:
                sent = send_message(contact, channel, body_out,
                                    _re_subject(_th.get("email_subject")),
                                    company=company, reply_to=reply_key,
                                    email_msg_id=_th.get("email_msg_id"))
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
                                      "channel": channel, "kind": "question",
                                      **_email_thread_fields(turn["last_msg"])}
        out["awaiting"] = True
        print("    [awaiting_reply set — next compose answers this, "
              "cooldown bypassed]")
        if compose_next:
            print("    [holding ack skipped — immediate compose follows "
                  "with the real answer]")
            return out
        _maybe_send_ack(state, company, contact_id,
                        {"body": combined, "channel": channel,
                         "at": stamp_at},
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
    #
    # THE CLOSER IS OWED, NOT ATTEMPTED (Santino 2026-08-04, Fran/Quality
    # Contracting): at 19:00 his time he wrote "I'll take time tomorrow to
    # write up specifics. Thank you" — substantive, no answer needed, so it
    # landed here. _maybe_send_ack then refused on business hours (9-18
    # America/New_York) and returned having written NOTHING: no flag, no
    # escalation, no trace. Every other owed-reply path arms
    # awaiting_reply BEFORE it tries to send; this one did not, so the only
    # thing standing between Fran and silence was pending_client_message's
    # live-thread fallback — which any later outbound (a workflow blast,
    # Santino's own text, a review-campaign SMS) would have voided, losing
    # the last word for good. Arm the flag FIRST, exactly like the
    # needs_answer path: kind "closer" is voided by any newer outbound
    # (ours included — then we already closed), so this can never
    # double-send, and the next in-hours compose delivers it.
    cs_reset["awaiting_reply"] = {"body": combined, "at": stamp_at,
                                  "channel": channel, "kind": "closer",
                                  **_email_thread_fields(turn["last_msg"])}
    print("    [awaiting_reply kind=closer — we owe the last word; the "
          "next in-hours pass delivers it if this one can't]")
    _maybe_send_ack(state, company, contact_id,
                    {"body": combined, "channel": channel,
                     "at": stamp_at},
                    contact_payload, do_send, dry_run, history=history,
                    needs_answer=False, needs_santino=False,
                    suggested=turn["suggested"], closer=True)
    # A DELIVERED closer pops its own flag (see _maybe_send_ack) — then
    # nothing is owed and the webhook must NOT compose on top of it, which
    # is exactly the race the old code avoided by never setting the flag at
    # all. A flag that SURVIVED means the closer was refused (business
    # hours, guard, duplicate) and the reply is still owed: let the
    # immediate compose try, and the scheduled passes keep trying after.
    out["awaiting"] = bool(cs_reset.get("awaiting_reply"))
    return out


# ---------------------------------------------------------------- uploads (2e)
# Client-upload path prefixes (inside branding/{cid}/) that deserve a
# thank-you text. Everything else in the bucket is SYSTEM-written (review-qr,
# generated art, reports) and must never trigger a "thanks for the upload".
_UPLOAD_KINDS = (
    # job-photos/inbox/ = quarantined screenshots (see ingest_inbound_media):
    # they must NEVER get the "queued for your Google profile" receipt —
    # Jimmy's Squarespace-error screenshots were thanked as job photos
    # (2026-08-28). Order matters: the inbox rule must sit above the
    # job-photos/ prefix it shadows.
    ("job-photos/inbox/", None),
    # job-photos/posted/ = gbp.py's media-import rider copying the photos
    # ALREADY ON the client's Google listing into our rotation — system
    # writes, never a client upload (Jim/CRW 2026-09-09: connecting his GBP
    # imported 11 listing photos and he was thanked for "11 photos" he
    # never sent; "I didnt que any photos. ?").
    ("job-photos/posted/", None),
    # Quarantined screenshots must never be thanked as content "photos in
    # the queue for your Google profile" (Angie/All Pro 2026-09-14: her
    # website-edit example shots got the content-photo receipt and she had
    # to write back "Not to add those photos").
    ("job-photos/inbox/", "screenshot"),
    ("job-photos/", "photo"),
    ("job-videos/", "video"),
    ("team/", "photo"),
    ("brand/logo", "logo"),
    ("docs/brand-kit/", "brand kit"),
    # Category-specific receipts (Santino 2026-09-06): the ack names what
    # the button they used says it is — still zero LLM.
    ("docs/customerlist/", "customer list"),
    ("docs/customer-lists/", "customer list"),
    ("docs/legal/", "legal docs"),
    ("docs/insurance/", "insurance docs"),
    ("docs/license", "license docs"),
    # DBA lane (2B, 2026-09-13): verified- copies are OUR system writes
    # (never re-verified, never acked); everything else in docs/dba/ came
    # off the hub's red DBA tile and gets vision-verified instead of the
    # generic thank-you — upload_event routes it to _verify_dba_upload.
    ("docs/dba/verified-", None),
    ("docs/dba/", "dba"),
    ("docs/", "file"),
)
_UPLOAD_ACK_MAX_PATHS = 500      # rolling dedupe ledger per company
_UPLOAD_PENDING_MAX_H = 48       # drop a burst we could not ack for 2 days


def _upload_kind(rel_path: str) -> str | None:
    """Classify a path RELATIVE to the company folder, or None for system
    artifacts (the review QR lives at brand/review-qr.png — ours)."""
    for prefix, kind in _UPLOAD_KINDS:
        if rel_path.startswith(prefix):
            return kind          # kind=None => quarantined, no ack
    return None


def _upload_ack_text(counts: dict) -> str:
    """One warm, deterministic thank-you for a whole burst. No LLM: the
    message is a receipt, and receipts must never hallucinate. Keeps to one
    SMS segment for the common cases."""
    parts = []
    for kind in ("photo", "video", "screenshot", "logo", "brand kit",
                 "customer list",
                 "legal docs", "insurance docs", "license docs", "file"):
        n = counts.get(kind) or 0
        if not n:
            continue
        if kind == "logo":
            parts.append("the logo" if n == 1 else f"{n} logo files")
        elif kind in ("brand kit", "legal docs", "insurance docs",
                      "license docs"):
            parts.append(f"the {kind}" + (" files" if kind == "brand kit" else ""))
        elif kind == "customer list":
            parts.append("your customer list")
        else:
            parts.append(f"the {kind}" if n == 1 else f"{n} {kind}s")
    if not parts:
        return ""
    what = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    got = f"Got {what}, thank you!"
    media_n = (counts.get("photo") or 0) + (counts.get("video") or 0)
    shot_n = counts.get("screenshot") or 0
    if media_n and shot_n:
        # Mixed burst: only the real photos are content; never promise the
        # screenshots to Google (Angie/All Pro 2026-09-14).
        return (f"{got} The photos are queued for your Google profile and "
                "website, and we're reviewing the screenshots now.")
    if shot_n:
        return f"{got} We're taking a look now."
    if media_n:
        pronoun = "It's" if media_n == 1 and len(parts) == 1 else "They're"
        return (f"{got} {pronoun} in the queue for your Google profile "
                "and website.")
    if counts.get("logo") or counts.get("brand kit"):
        return f"{got} We'll get it onto your site and profiles."
    if counts.get("customer list"):
        return f"{got} We're loading it in for your review campaign."
    # "Passing this along to the team" retired 2026-09-06 (Santino: "we ARE
    # the team") — a receipt says received + being incorporated, period.
    return f"{got} It's received and being incorporated."



_PHOTO_ROUTE_SYSTEM = """A client uploaded this image under a generic
"documents" category. Decide where it belongs for a damage-restoration
marketing pipeline. Reply JSON only:
{"route": "job_photos"|"keep_docs", "why": "<6 words>"}
job_photos = real photography: job sites, crews, equipment, branded
vehicles/fleet, team, finished work, before/after.
keep_docs = anything document-like: scans, screenshots of paperwork,
certificates, forms, ID cards, insurance paperwork, or images you cannot
confidently call business photography."""


def _route_misfiled_photos(cid: str, rels: list[str], dry_run: bool) -> list[str]:
    """Images uploaded under docs/other (the "Other" button) get a vision
    look and, when they are clearly real photos, move to job-photos/ so the
    GBP drain + site imagery can use them (Laura/DryCor 2026-09-06: 12
    fleet/job photos sat dead in docs/other). Document-ish images STAY in
    docs — and even a misroute is caught later by the GBP drain's quality
    gate, which holds document scans. Returns rels (possibly rewritten) so
    the ack text counts them as photos."""
    out = []
    for rel in rels:
        if not (rel.startswith("docs/other/")
                and rel.lower().endswith((".jpg", ".jpeg", ".png", ".heic", ".webp"))):
            out.append(rel)
            continue
        try:
            img = requests.get(
                f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1/object/"
                f"branding/{cid}/{rel}",
                headers={"apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
                         "Authorization": "Bearer "
                         + os.environ["SUPABASE_SERVICE_ROLE_KEY"]},
                timeout=45).content
            if len(img) > 4_500_000:
                out.append(rel)
                continue
            import base64 as _b64
            media = "image/png" if rel.lower().endswith(".png") else "image/jpeg"
            v = anthropic_json(_PHOTO_ROUTE_SYSTEM, "Route this image.",
                               images=[{"media_type": media,
                                        "data": _b64.b64encode(img).decode()}])
            if v.get("route") != "job_photos":
                out.append(rel)
                continue
            new_rel = "job-photos/" + rel.rsplit("/", 1)[-1]
            if not dry_run:
                requests.post(
                    f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1/object/move",
                    headers={"apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
                             "Authorization": "Bearer "
                             + os.environ["SUPABASE_SERVICE_ROLE_KEY"],
                             "Content-Type": "application/json"},
                    json={"bucketId": "branding",
                          "sourceKey": f"{cid}/{rel}",
                          "destinationKey": f"{cid}/{new_rel}"}, timeout=30)
            print(f"    [route] {rel} -> {new_rel} ({v.get('why', '')})")
            out.append(new_rel)
        except Exception:  # noqa: BLE001 — routing is best-effort
            out.append(rel)
    return out


def upload_event(objects: list | None, do_send: bool = True) -> dict:
    """UPLOAD ACKNOWLEDGMENTS (2026-08-20, Monica email evolution 2e — the
    Robert's-logo class: he uploaded his logo 08-17 and heard nothing).

    Fed by Railway POST /upload-event, which the pg_cron job
    'upload-event-sweep' hits every 10 minutes with the branding-bucket
    objects created in the last ~11. The sweep window IS the burst debounce
    (a 10-photo upload collapses into one batch -> ONE text), the rolling
    acked-paths ledger dedupes the overlap minute and cron retries, and
    hours-gated bursts persist as upload_ack_pending so the NEXT sweep
    delivers them (dropped after 48h, logged, never half-forgotten).
    Every send gate applies inside send_message (canary allowlist, company
    hold, human quiet window); business hours use the reply shoulder — an
    upload is client activity happening right now.

    Ledger: every acked burst writes a work_log 'uploads-received' row.
    Incorporation is tracked by the pinned marketing_action_plan rows the
    upload functions already create (logo/customer list/brand kit);
    upload_stranded_check() below flags any of those left 'planned' 72h+."""
    state = load_state()
    dry_run = not do_send
    now = datetime.now(timezone.utc)
    # 1) fold fresh objects into per-company pendings
    per_company: dict[str, list[str]] = {}
    for o in objects or []:
        name = str((o or {}).get("name") or "")
        cid, _, rel = name.partition("/")
        if not (cid.startswith("CO-") and rel):
            continue
        if _upload_kind(rel):
            per_company.setdefault(cid, []).append(rel)
    for cid in list(per_company):
        per_company[cid] = _route_misfiled_photos(
            cid, per_company[cid], dry_run=not do_send)
    # DBA-tile arrivals (2B): peel them off BEFORE the ack fold — they get
    # vision verification + their own Monica message, never the generic
    # thank-you. Rolling dedupe mirrors the ack ledger.
    dba_by_company: dict[str, list[str]] = {}
    for cid in list(per_company):
        cs = company_state(state, cid)
        seen = set(cs.get("dba_processed_paths") or [])
        # A DBA doc is one when the TILE says so OR the FILENAME does
        # (Rachelle/DVC 2026-09-21: the recorded Clark County FFN
        # certificate arrived through the generic hub docs area as
        # 'DVC FEN Firm Name ....pdf' and only got the generic thank-you —
        # nothing read the registered name).
        def _is_dba(rel: str) -> bool:
            if _upload_kind(rel) == "dba":
                return True
            base = rel.rsplit("/", 1)[-1].lower()
            return (rel.startswith("docs/") and base.endswith(".pdf")
                    and bool(re.search(
                        r"\b(dba|fen|ffn|fictitious|assumed[ _-]?name|"
                        r"firm[ _-]?name|trade[ _-]?name)\b", base)))
        dba = [r for r in per_company[cid]
               if _is_dba(r) and r not in seen]
        if dba or any(_is_dba(r) for r in per_company[cid]):
            per_company[cid] = [r for r in per_company[cid]
                                if not _is_dba(r)]
        if dba:
            dba_by_company[cid] = dba
            cs["dba_processed_paths"] = (
                (cs.get("dba_processed_paths") or []) + dba)[-100:]
    for cid, rels in dba_by_company.items():
        companies_dba = fetch_companies([cid])
        company = companies_dba.get(cid)
        if not company or company_inactive(company):
            continue
        target = messaging_target(company)
        contact_id = (target.get("ghl_contact_id")
                      or linked_contact_id(company))
        contact = {"id": contact_id, "phone": target.get("cell"),
                   "email": target.get("email")}
        for rel in rels:
            verdict = _verify_dba_upload(company, contact, rel,
                                         state, not do_send)
            print(f"  [dba-upload] {company.get('name')}: {rel} -> {verdict}")
    for cid, rels in per_company.items():
        cs = company_state(state, cid)
        acked = set(cs.get("upload_acked_paths") or [])
        pend = cs.get("upload_ack_pending") or {"paths": [], "at": now.isoformat()}
        fresh = [r for r in rels
                 if r not in acked and r not in set(pend["paths"])]
        if fresh:
            pend["paths"] = (pend["paths"] + fresh)[-_UPLOAD_ACK_MAX_PATHS:]
            pend.setdefault("at", now.isoformat())
            cs["upload_ack_pending"] = pend
    # 2) attempt every pending burst (fresh AND held-over) — one text each
    out = {"acked": 0, "held": 0, "dropped": 0}
    pending_cids = [cid for cid, c in (state.get("companies") or {}).items()
                    if (c.get("upload_ack_pending") or {}).get("paths")]
    if not pending_cids:
        save_state(state, dry_run)
        return out
    companies = fetch_companies(pending_cids)
    for cid in pending_cids:
        cs = company_state(state, cid)
        pend = cs.get("upload_ack_pending") or {}
        rels = pend.get("paths") or []
        company = companies.get(cid)
        first_at = pend.get("at") or now.isoformat()
        age_h = (now - datetime.fromisoformat(first_at)).total_seconds() / 3600
        if not company or company_inactive(company):
            cs.pop("upload_ack_pending", None)   # muted account: no ack ever
            continue
        if age_h > _UPLOAD_PENDING_MAX_H:
            out["dropped"] += 1
            cs.pop("upload_ack_pending", None)
            print(f"  [upload-ack] {company.get('name')}: burst of "
                  f"{len(rels)} could not be acked for {age_h:.0f}h — "
                  "dropped (gates never opened)")
            continue
        counts: dict[str, int] = {}
        for r in rels:
            k = _upload_kind(r) or "file"
            counts[k] = counts.get(k, 0) + 1
        text = _upload_ack_text(counts)
        target = messaging_target(company)
        contact_id = (target.get("ghl_contact_id")
                      or linked_contact_id(company))
        if not (text and contact_id):
            cs.pop("upload_ack_pending", None)
            continue
        contact_payload = None
        try:
            data = _ghl("GET", f"/contacts/{contact_id}")
            contact_payload = (data or {}).get("contact") or data
        except Exception:  # noqa: BLE001 — hours check falls back to company tz
            pass
        hours = business_hours_check(company, contact_payload,
                                     reply_to=first_at)
        if hours:
            out["held"] += 1
            print(f"  [upload-ack] {company.get('name')}: held ({hours})")
            continue
        contact = {"id": contact_id,
                   "phone": (target.get("cell")
                             or (contact_payload or {}).get("phone")),
                   "email": (target.get("email")
                             or (contact_payload or {}).get("email"))}
        # SISTER-COMPANY DEDUPE (2026-08-22, Bobby's double thank-you): the
        # email intake files one email's attachments under EVERY matched
        # sister company (RT Olson + Dry County share bob@'s thread), so two
        # bursts produced two identical acks in one conversation. One
        # identical ack per contact is enough: if the thread already carries
        # this exact text in its recent outbound, mark the burst acked
        # without sending again.
        try:
            recent = fetch_history(contact_id, max_msgs=8)
            if any(m["direction"] == "out" and (m.get("body") or "").strip() == text.strip()
                   for m in recent):
                cs["upload_acked_paths"] = (list(cs.get("upload_acked_paths") or [])
                                            + rels)[-_UPLOAD_ACK_MAX_PATHS:]
                cs.pop("upload_ack_pending", None)
                out["acked"] += 1
                print(f"  [upload-ack] {company.get('name')}: identical ack "
                      "already in the thread (sister company) — marked acked, "
                      "not re-sent")
                continue
        except Exception:  # noqa: BLE001 — dedupe is best-effort
            pass
        if dry_run:
            print(f"  [upload-ack] [dry-run] {company.get('name')}: {text!r}")
            out["acked"] += 1
            continue
        try:
            sent = send_message(contact, "sms", text, company=company)
        except SendBlocked as e:
            out["held"] += 1
            print(f"  [upload-ack] {company.get('name')}: blocked ({e}) — "
                  "burst stays pending for the next sweep")
            continue
        record_sent_message(state, sent)
        acked = set(cs.get("upload_acked_paths") or [])
        cs["upload_acked_paths"] = (list(acked) + rels)[-_UPLOAD_ACK_MAX_PATHS:]
        cs.pop("upload_ack_pending", None)
        out["acked"] += 1
        print(f"  [upload-ack] {company.get('name')}: acked "
              f"{len(rels)} upload(s) -> {text!r}")
        try:
            from work_log import work_log
            work_log(cid, "intake", "uploads-received",
                     f"Acked {len(rels)} client upload(s): "
                     + ", ".join(f"{v} {k}(s)" for k, v in counts.items()),
                     evidence={"paths": rels[:20]}, actor="monica",
                     source="client_concierge.py upload_event")
        except Exception as e:  # noqa: BLE001 — ledger never blocks the ack
            print(f"  [work-log] warn: {str(e)[:100]}")
    # daily stranded pass rides the sweep (state-flagged, so the 10-min
    # cadence costs one date compare)
    today = now.strftime("%Y-%m-%d")
    if state.get("upload_stranded_checked") != today:
        state["upload_stranded_checked"] = today
        try:
            n = upload_stranded_check(dry_run, state=state)
            if n:
                print(f"  [upload-stranded] {n} pinned upload row(s) "
                      "sitting planned 72h+ — cards filed")
        except Exception as e:  # noqa: BLE001 — watchdog never kills acks
            print(f"  [upload-stranded] warn: {str(e)[:100]}")
    save_state(state, dry_run)
    return out


def upload_stranded_check(dry_run: bool = False,
                          state: dict | None = None) -> int:
    """NEVER STRANDED (2e): a pinned upload action row still 'planned' after
    72h means a client's artifact was received and then sat unused (the
    Robert's-logo failure with a paper trail). Files ONE Ops Attention card
    per row, re-filed at most every 7 days while it stays planned (first
    live run 08-20 found NINE logos sitting planned 7-31 days — without the
    dedupe those become daily duplicates). Ran daily from the /upload-event
    sweep (state-flagged so 10-min calls stay cheap)."""
    # Logo rows are EXCLUDED here (2026-08-21): logo_stranded_check.py
    # auto-verifies/auto-resolves them and files [DEV] cards for the rest —
    # Santino never gets a logo card again. This check keeps watching the
    # OTHER upload classes (customer list, brand kit).
    rows = _sb("GET", "/rest/v1/marketing_action_plan"
               "?status=eq.planned&pinned=is.true&title=ilike.*uploaded*"
               "&title=not.ilike.Logo*"
               "&select=company_id,title,updated_at,source_run_at") or []
    flagged = 0
    now = datetime.now(timezone.utc)
    seen = state.setdefault("upload_stranded_flagged", {}) \
        if state is not None else {}
    for r in rows:
        ts = r.get("updated_at") or r.get("source_run_at")
        try:
            age_h = (now - datetime.fromisoformat(
                str(ts).replace("Z", "+00:00"))).total_seconds() / 3600
        except (TypeError, ValueError):
            continue
        if age_h < 72:
            continue
        dedupe_key = f"{r['company_id']}:{r.get('title')}"
        last = seen.get(dedupe_key)
        if last:
            try:
                if (now - datetime.fromisoformat(last)).days < 7:
                    continue
            except (TypeError, ValueError):
                pass
        seen[dedupe_key] = now.isoformat()
        flagged += 1
        company = fetch_companies([r["company_id"]]).get(r["company_id"]) \
            or {"id": r["company_id"], "name": r["company_id"]}
        append_escalation(
            company, None,
            f"[UPLOAD-STRANDED] '{r.get('title')}' has sat planned for "
            f"{age_h/24:.0f} days — the client sent this and it was never "
            "applied. Apply it (or mark the action row done).",
            dry_run)
    return flagged


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
    company_id = _company_for_contact(contact_id, state)
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
        # RE-READ AFTER SLEEPING (2026-08-05): the snapshot taken before the
        # debounce is minutes old by now, and saving it back at the end of
        # the run would clobber whatever another pass wrote in the meantime
        # (that lost update is half of how Jerrott got two contradicting
        # texts). The durable claim below is the other half.
        state.clear()
        state.update(load_state())
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


def promote_scheduled_notes() -> None:
    """Cloud-side note scheduling (Santino 2026-09-03): a note inserted with
    status='scheduled' and a send_after timestamp is invisible to every
    reader (they all filter status=eq.open) until a cloud cycle promotes it
    here. This replaces one-shot launchd jobs on Santino's Mac — the queue
    lives in Supabase and any cycle (Railway 30-min or the GH workflow)
    promotes on time, laptop closed or not."""
    # Z-form timestamp — an isoformat "+00:00" offset reads as a space in the
    # query string and 400s the PATCH
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = _sb("PATCH",
               "/rest/v1/marketing_ops_notes?status=eq.scheduled"
               f"&send_after=lte.{now}&select=id,company_id",
               {"status": "open"}) or []
    for r in rows:
        print(f"[scheduled-note promoted to open: {r['id']} "
              f"({r.get('company_id')})]")


def cmd_inbound(args) -> int:
    if not args.poll:
        print("inbound: pass --poll", file=sys.stderr)
        return 1
    dry_run = not args.send
    if not dry_run:
        promote_scheduled_notes()
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
                # AMBIGUOUS: ask, never guess (Santino 2026-08-06). Three asks
                # were open within five minutes — AAA Carpet Care ("CALL
                # REQUESTED"), MCC/Jeff Sibley ("no reply after 4 nudges") and
                # Quality Contracting/Fran. His "I'm in and out of meetings,
                # will call as soon as I can" was meant for FRAN, but it fits
                # all three word-for-word, so the matcher handed it to AAA and
                # then MCC. Jeff Sibley got told Santino would return a message
                # he never sent, and Fran never got the one thing he was owed.
                # A wrong client is worse than a second question.
                if match.get("ambiguous") and len(open_reqs) > 1:
                    names = ", ".join(str(r.get("company_name") or "?") for r in open_reqs)
                    print(f"  [advice] AMBIGUOUS reply — not guessing between: {names}")
                    if not dry_run and args.send:
                        try:
                            send_message({"id": ADVICE_CONTACT_ID, "phone": ADVICE_PHONE}, "sms",
                                         "Which one is that for? I have open questions on: "
                                         f"{names}. Reply with the name and I'll take it from there.")
                        except SendBlocked as e:
                            print(f"    ambiguity check-back blocked: {e}")
                    continue
                if idx is None or not (0 <= int(idx) < len(open_reqs)) or not instr:
                    continue
                req = open_reqs[int(idx)]
                print(f"  [advice] Santino answered re {req.get('company_name')}: {instr[:100]}")
                if not dry_run:
                    _sb("POST", "/rest/v1/marketing_ops_notes", body={
                        "company_id": req["company_id"],
                        "body": f"[FROM SANTINO via SMS] {instr} "
                                f"(answering: {req.get('reason', '')[:120]})"})
                    # REPLY-TO-APPROVE. Filing the directive is not the same as
                    # doing the work: his "Yes add fire to go greens site" was
                    # acknowledged and the task stayed [TODO-PROPOSED], so
                    # nothing built it. Convert on a blanket yes; a partial
                    # reply is reported and left alone rather than approving
                    # the task he just cancelled.
                    if req.get("kind") == "task-proposal":
                        for ln in apply_task_approval(
                                req["company_id"], m.get("body", ""), dry_run=False):
                            print(f"    [approve] {ln}")
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

    # ------------------------------------------------------------------
    # ACK SLA SWEEP (Santino 2026-09-03, the Jonathan case): the guarantee
    # layer over the best-effort ack machinery above. Any substantive
    # client message still owed a reply after ACK_SLA_MINUTES gets a safe
    # holding line NO MATTER which soft guard swallowed the original
    # attempt (intel suppression, quiet-window timing, compose skips).
    # Hard gates still apply inside send_message (canary allowlist, holds,
    # paused). One SLA ack per client message, keyed in company state.
    # ------------------------------------------------------------------
    ACK_SLA_MINUTES = 90
    try:
        by_company = {}
        for c_id, comp_id in tracked.items():
            if c_id != OPS_PING_CONTACT_ID:
                by_company.setdefault(comp_id, c_id)
        for comp_id, c_id in by_company.items():
            company = companies.get(comp_id)
            if not company or company_inactive(company):
                continue
            cs = company_state(state, comp_id)
            history = fetch_history(c_id, max_msgs=25)
            owed = pending_client_message(cs, history, state)
            if not owed:
                continue
            at = owed.get("at")
            at_dt = at if hasattr(at, "strftime") else None
            if at_dt is None and at:
                try:
                    at_dt = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
                except ValueError:
                    at_dt = None
            if at_dt and at_dt.tzinfo is None:
                at_dt = at_dt.replace(tzinfo=timezone.utc)
            if not at_dt or (run_start - at_dt).total_seconds() < ACK_SLA_MINUTES * 60:
                continue
            key = _reply_key(owed)
            if cs.get("ack_sla_sent") == key:
                continue
            body = ("Got it, thanks for flagging this. We're on it and will "
                    "follow up with you shortly.")
            print(f"  [ack-SLA] {company.get('name')}: reply owed for "
                  f">{ACK_SLA_MINUTES}min ({str(owed.get('body'))[:60]!r}) — "
                  "sending the holding line")
            if dry_run:
                continue
            try:
                contact_payload = {"id": c_id,
                                   "phone": (company.get("phone") or ""),
                                   "email": company.get("email")}
                sent = send_message(contact_payload, owed.get("channel") or "sms",
                                    body, company=company, reply_to=key)
                record_sent_message(state, sent)
                cs["ack_sla_sent"] = key
            except SendBlocked as e:
                print(f"  [ack-SLA] blocked ({str(e)[:100]}) — retry next poll")
            except Exception as e:  # noqa: BLE001 — SLA sweep must never kill the poll
                print(f"  [ack-SLA] failed ({str(e)[:100]})")
    except Exception as e:  # noqa: BLE001
        print(f"  [ack-SLA] sweep errored ({str(e)[:100]})")

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


# YES/NO TO OUR OWN QUESTION (Santino 2026-09-27, Ashley/DryCor): a one-off
# offer ("Want the callers' numbers so you can reach back out?") is not one
# of Monica's open asks, so Ashley's bare "Yes please" matched nothing, had no
# "?", and was filed to the digest instead of answered. A short affirmative /
# negative arriving right after OUR outbound that ended in a question IS an
# answer we owe follow-through on; compose then acts on it with the thread +
# [CONTEXT] notes (which carry what was offered).
_SHORT_ANSWER_RE = re.compile(
    r"^\s*(?:yes|yeah|yea|yep|yup|sure|please|ok(?:ay)?|definitely|absolutely"
    r"|of course|go ahead|do it|that works|sounds good|no|nope|nah|not now"
    r"|no thanks)\b", re.I)


def _replies_to_our_question(contact: dict | None, msg: dict) -> bool:
    body = (msg.get("body") or "").strip()
    if not contact or len(body) > 80 or not _SHORT_ANSWER_RE.search(body):
        return False
    at = msg.get("ts") or msg.get("when")
    try:
        hist = fetch_history(contact["id"], 8)
    except Exception:  # noqa: BLE001 — never blocks inbound handling
        return False
    for m in hist:                      # newest first
        if m.get("direction") != "out":
            continue
        if at and m.get("when") and m["when"] > at:
            continue
        return "?" in (m.get("body") or "")
    return False


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
PERSONA (hard rule, 2026-08-04): you are not a person and have never been on
a call, in a meeting or on a site visit — never "great meeting you", "nice
talking with you", "as we discussed on the call", "when we met", "on our
call", "meet with me", "I saw", "I heard". Third person only: "Santino
mentioned...", "great call with Santino yesterday".
REGISTRAR TRUTH (hard rule, 2026-08-04): we can never get access to a
client's domain ourselves — no registrar offers that. Never say we will
reach out to, contact or go through GoDaddy (or any domain company). The
client sends us access, or they do it with Santino on a short call.
<<CAPABILITY_CONTRACT>>
<<CONSISTENCY_RULE>>
BE SHORT — hard rule (Santino 2026-08-04): ONE short sentence is the target,
two is the maximum, under 160 characters. No preamble, no re-explaining, no
justifying, no closing filler, no restating their words. "Give me a second,
grabbing the right link for you." is a complete, good text.
Return ONLY JSON: {"body": string}."""

ACK_SYSTEM = (ACK_SYSTEM
              .replace("<<CAPABILITY_CONTRACT>>", CAPABILITY_CONTRACT)
              .replace("<<CONSISTENCY_RULE>>", CONSISTENCY_RULE))

# COMMITMENT FOLLOW-THROUGH (Santino 2026-08-02: the ack drafted "I'll walk
# you through it" and nobody ever walked him through anything). Any promise
# that slips into a sent ack is captured here and queued as
# cs["pending_commitment"] — the next compose MUST deliver it (see the OPEN
# COMMITMENT block in compose_draft). General rule: never promise what the
# pipeline won't deliver; prefer doing the first step in the ack itself.
#
# "WE" COUNTS TOO (Santino 2026-08-04): the pattern only ever matched "I'll",
# but Monica speaks for the team — she told Greg Arianoff "we'll take a look
# and make sure it's showing linked on our end too" and nothing was recorded,
# so the promise evaporated exactly the way this block exists to prevent.
_PROMISE_RE = re.compile(
    r"\b(?:i|we)(?:['’]ll| will)\s+(?:walk you|get (?:right )?back|find out|"
    r"check|look into|take a look|make sure|send (?:you|over|it)|follow up|"
    r"get you|dig|circle back|ask santino|talk to santino|"
    r"have (?:an answer|that|it))", re.I)


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
    # An ack/closer is BY DEFINITION a reply, so it may use the fast-reply
    # window and the evening shoulder (Santino 2026-08-04: Fran's 19:00 text
    # deserved a two-second "sounds good", not next-day silence). Quiet hours
    # still refuse, and the caller has already armed awaiting_reply so a
    # refusal here defers rather than drops.
    window = business_hours_check(company, contact_payload,
                                  reply_to=msg.get("at"))
    if window:
        print(f"    [ack skipped: {window}]")
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
    # A holding line is the shortest message Monica ever sends: one sentence.
    text = _fit_sms(text, 160, 200, label=" [ack]")
    print(f"    ack draft ({len(text)} chars): {text!r}")
    grounding = outbound_guard(text, None)
    if grounding:
        # THE TONY PATH (2026-08-05). His "Call me when u have a minute" came
        # in as a needs_answer holding line and the ack drafted "Got it, I'll
        # give you a call shortly." Blocking it silently would leave him with
        # nothing; substitute the true version and ping Santino to dial.
        swap = honest_substitute(grounding, body)
        if not swap:
            print(f"    [ack blocked by outbound guard: {grounding}]")
            return
        print(f"    [ack guard substitution: {grounding}]\n"
              f"    -> {swap!r}")
        text = swap
        escalate_call_request(company, msg, body, dry_run)
    reply_key = _reply_key(msg)
    dup = repeats_recent_outbound(company.get("id"), text, history or [],
                                  reply_to=reply_key)
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
        sent = send_message(contact, msg.get("channel") or "sms", text,
                            company=company, reply_to=reply_key)
        record_sent_message(state, sent)
        acks[contact_id] = today
        if closer:
            # The last word just went out — disarm the owed-closer flag the
            # caller armed, so no compose re-closes an exchange we already
            # closed (2026-08-04).
            cs.pop("awaiting_reply", None)
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
# ---------------------------------------------------------------- selfcheck
# Offline regression cases for the two classifiers that decide whether Monica
# ACTS on a note and whether a message is too long. No network, no API keys —
# `python3 scripts/client_concierge.py selfcheck` runs in a second and is the
# fastest way to prove a prompt/regex edit did not move the boundaries.
_DIRECTIVE_CASES: list[tuple[str, str, bool]] = [
    # (body, author, is_directive)
    ("Reach out and set a meeting up sometime tomorrow or Thursday.",
     "santino", True),                       # the note that started this
    ("Monica: ask them for the original files instead", "santino", True),
    ("Still waiting on their YouTube connection — make it a priority",
     "santino", True),                       # the app's own placeholder
    ("Please follow up on the insurance certificate", "santino", True),
    ("Need Quality Contracting's logo. Ask for a clean file via the hub.",
     "santino", True),
    ("[FOR MONICA] Ask TRG to add contact@restorationai.io as a MANAGER",
     "santino", True),
    ("[FROM SANTINO] Reply to Angie by SMS", "santino", True),
    ("[SEND-PREVIEW] Approved by Santino: text the client their preview",
     "santino", True),
    # constraints and context — must NEVER grant a cadence bypass
    ("Do NOT mention prorestorationca.com, the domain, or registrar access "
     "to Angie in ANY message.", "santino", False),
    ("Do NOT ask Jose to confirm services or about wanting LSA.",
     "santino", False),
    ("Greg provided his review campaign list already", "santino", False),
    ("Wants to add MICRO Certified to hero section badges", "santino", False),
    ("We have outreach to Brian regarding access to the domain and are just "
     "waiting for his response. Called Multiple times. Have now sent an "
     "email.", "santino", False),
    ("FLAG (app bug, dev task): Ops Attention 'Address now' lands on a "
     "spinner", "claude (bug report from Santino)", False),
    # machine tags in other lanes
    ("[LSA-INTENT] YES — set from Ops Attention.", "santino", False),
    ("[DEV] rebuild the hero section", "santino", False),
    ("[TODO-SANTINO] decide on the LSA cleanup", "santino", False),
    ("[CONTACT RECEIVED] Ed Barnes, +18055551212", "santino", False),
    ("Client sent a case study via webhook: queued for the content engine",
     "webhook", False),
]


# CAPABILITY CONTRACT regression cases (Santino 2026-08-05, Tony/Coastal).
# (text, must_be_blocked). The PASS half is load-bearing: the sanctioned
# rewrites, Santino's own domain-access copy and ordinary good drafts must
# survive, or the guard just silences Monica instead of making her honest.
_CAPABILITY_CASES: list[tuple[str, bool]] = [
    # the live failure, verbatim
    ("Got it, I'll give you a call shortly.", True),
    ("I'll call you in a few minutes.", True),
    ("Let me hop on a quick call with you.", True),
    ("I'll ring you this afternoon.", True),
    ("I'll get on the phone with you today.", True),
    ("I can give you a call after lunch if that's easier.", True),
    ("Give me a call when you have a minute.", True),
    ("Feel free to call me at 805 329 3449.", True),
    ("We'll give you a call tomorrow.", True),
    ("I'll get you on Santino's calendar for Thursday.", True),
    ("I'll book a call for you.", True),
    ("I'll send you a calendar invite.", True),
    ("Santino will call you at 3pm today.", True),
    # the 08-05 sanctioned reply, banned verbatim on 08-18 (Tony Mendez):
    # Monica never commits Santino to a call
    ("Got it, Santino will give you a call. What's the best time to reach "
     "you?", True),
    # video verification is a SOLO task — live-help offers banned 08-20
    ("Want to get that Google verification video walkthrough knocked out? "
     "Santino can hop on a quick 15 minute call, you just hold the phone.",
     True),
    ("We can knock out the video verification together on a video call.",
     True),
    ("Santino will give you a call today, what number is best?", True),
    ("He'll give you a ring once he's free.", True),
    ("I'll have Santino call you.", True),
    ("I'll have your site live by end of day.", True),
    ("We'll have that fixed within the hour.", True),
    ("I'll swing by the shop tomorrow.", True),
    ("Talk to you then!", True),
    ("See you Thursday.", True),
    ("I'll log into your GoDaddy and get it switched.", True),
    # the sanctioned rewrites and normal copy — never blocked
    (CALL_HANDOFF_REPLY, False),
    ("Got it, I'm passing this along to Santino right now.", False),
    ("Here's what Google asks you to film for the video verification: start "
     "outside at your signage, walk in, and show your equipment. Record it "
     "solo in one take. Happy to answer any questions before you film.",
     False),
    ("Want me to find a time with Santino? What time works?", False),
    ("You'd send us access from your GoDaddy account, takes about two "
     "minutes, or Santino can hop on a quick 15 minute call with you and do "
     "it together while you're signed in.", False),
    ("Want to grab a quick 15 minute call with Santino this week to knock "
     "it out?", False),
    ("Still grabbing that link for you, I'll have it shortly.", False),
    ("Can you send over your past customer list? Names and numbers is all "
     "we need.", False),
    ("You're all set, moved to Thursday Aug 6 at 10:00 AM.", False),
    ("Talk soon.", False),
    ("I'll check on that and get right back to you.", False),
    ("We're getting Steve added now.", False),
    ("Your new site is built, here's the link.", False),
    ("Sounds like Tuesday's call with Santino went great.", False),
]

# INTERNAL SENDER MAP cases (2026-08-20, the Bobby misattribution): raw GHL
# rows -> is this OUR side despite the direction field? The first case is the
# live failure verbatim: Santino's send from the external Gmail, synced back
# by GHL as direction=inbound WITH his workspace userId stamped on it.
_INTERNAL_SENDER_CASES: list[tuple[dict, bool]] = [
    ({"direction": "inbound", "messageType": "TYPE_EMAIL",
      "userId": "xTuHtBz8G7Z4fyhAJ9kJ",
      "body": "These are perfect. We'll add them in for ya"}, True),
    # human-answered inbound call: a person on our team spoke, counts as ours
    ({"direction": "inbound", "messageType": "TYPE_CALL",
      "userId": "xTuHtBz8G7Z4fyhAJ9kJ", "body": ""}, True),
    # Santino texting from the GHL app (ordinary human outbound)
    ({"direction": "outbound", "messageType": "TYPE_SMS",
      "userId": "xTuHtBz8G7Z4fyhAJ9kJ", "body": "On it, give me an hour"},
     True),
    # a REAL client reply — sms and email, no userId — must stay the client
    ({"direction": "inbound", "messageType": "TYPE_SMS",
      "body": "Sounds good, thanks"}, False),
    ({"direction": "inbound", "messageType": "TYPE_EMAIL",
      "body": "These look great, when do we go live?"}, False),
    # Monica's own API send: ours, but not a HUMAN row (userId absent)
    ({"direction": "outbound", "messageType": "TYPE_SMS",
      "body": "Quick update on your site build."}, False),
]

# Inbound messages that ARE a request for a phone call (always needs_santino)
# and near-misses that are not.
_CALL_REQUEST_CASES: list[tuple[str, bool]] = [
    ("Call me when u have a minute", True),          # Tony, verbatim
    ("give me a call when you get a sec", True),
    ("Can we talk?", True),
    ("when can you call me", True),
    ("What's a good time to talk?", True),
    ("Can you hop on a quick call today?", True),
    ("I'll call you later today", False),            # HE is calling US
    ("Just got off a call with my adjuster", False),
    ("Yes its with GoDaddy", False),
    ("Sounds good, thanks", False),
]


def cmd_selfcheck(_args) -> int:
    fails = 0
    print("capability contract (Monica cannot call, book, visit or promise "
          "a clock):")
    for text, want_blocked in _CAPABILITY_CASES:
        # the FULL guard, so a sanctioned rewrite must clear persona and
        # registrar too, not just the capability half
        got = bool(outbound_guard(text, None)) if not want_blocked \
            else bool(capability_violation(text))
        ok = got == want_blocked
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} "
              f"{'BLOCK' if got else 'pass ':<5} {text[:62]!r}")
    print("\npreview mentions carry a URL or don't exist (Jimmy 08-28):")
    for text, want_blocked in [
        ("When you get a chance, take a look at your new website preview and let us know your thoughts.", True),
        ("Your new site is built! Here's the preview of your website: https://staging.rankai-x.pages.dev/ - what do you think?", False),
        ("The team's already started on your website, more soon.", False),
        ("Quick update on your site build.", False),
    ]:
        got = bool(unlinked_preview_invite(text))
        ok = got == want_blocked
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} "
              f"{'BLOCK' if got else 'pass ':<5} {text[:62]!r}")

    print("\nupload instructions never point at pages.dev (Rob/TDI 08-31):")
    for text, want_blocked in [
        ("Robert, still need your logo to get your business listings built out. Upload it here: https://rankai-tdi-builders.pages.dev", True),
        ("Send your logo here, works from your phone: https://restorationai.io/logo/tdi-builders", False),
        ("Your new site preview is live: https://staging.rankai-tdi-builders.pages.dev/ - take a look!", False),
        ("Can you attach the file here: https://rankai-x.pages.dev/upload", True),
    ]:
        got = bool(upload_to_preview_link(text))
        ok = got == want_blocked
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} "
              f"{'BLOCK' if got else 'pass ':<5} {text[:62]!r}")

    print("\nboss prohibition topics match the asks they own:")
    for topic, sample_ask, want in [
        ("google-connect", "ASK CLIENT: connect their Google account", True),
        ("site-share", "Share the website preview with the owner", True),
        ("google-connect", "Send over the insurance certificate", False),
    ]:
        got = bool(_ASK_TOPIC_RES[topic].search(sample_ask))
        ok = got == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {topic:15} {sample_ask[:44]!r}")

    print("\nquarantined screenshots never get the photo-queued receipt:")
    for path, want in [
        ("job-photos/inbox/sms-123.jpg", None),
        ("job-photos/sms-123.jpg", "photo"),
        ("docs/inbox/sms-123.jpg", "file"),
    ]:
        got = _upload_kind(path)
        ok = got == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {str(got):<6} {path}")

    print("\ncall requests are needs_santino by definition:")
    for text, want in _CALL_REQUEST_CASES:
        got = client_asked_for_a_call(text)
        ok = got == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {str(got):<5} {text[:62]!r}")
    print("\ninternal sender map (a userId row is OURS whatever the "
          "direction field says):")
    for row, want in _INTERNAL_SENDER_CASES:
        got = is_internal_sender(row)
        ok = got == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {'ours ' if got else 'them ':<5} "
              f"{row['direction']}/{row['messageType']} "
              f"{(row.get('body') or '(no body)')[:44]!r}")
    # the map must actually be WIRED into both ingest surfaces, not just exist
    import inspect
    wired = [
        ("history renders an internal 'inbound' email as us-human",
         "us-human (email): These are perfect" in format_history([{
             "when": datetime.now(timezone.utc),
             "direction": ("out" if is_internal_sender(
                 _INTERNAL_SENDER_CASES[0][0]) else "in"),
             "channel": "email", "user_id": "xTuHtBz8G7Z4fyhAJ9kJ",
             "body": "These are perfect. We'll add them in for ya"}])),
        ("fetch_inbound_since source guards on is_internal_sender",
         "if is_internal_sender(msg):" in
         inspect.getsource(fetch_inbound_since)),
        ("fetch_history source routes internal rows to 'out'",
         "is_internal_sender(msg)" in inspect.getsource(fetch_history)),
    ]
    for label, ok in wired:
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")

    print("\nreply-in-channel (2d): email questions get email answers, "
          "in thread:")
    _owes_email = {"awaiting_reply": {"channel": "email",
                                      "email_subject": "Website feedback",
                                      "email_msg_id": "KabR1LjwiEwSYrnNZ6MZ"}}
    rc_cases = [
        ("owed email -> compose answers by email",
         owed_reply_channel("sms", _owes_email, {"email": "k@x.com"})
         == "email"),
        ("owed sms stays sms",
         owed_reply_channel(
             "sms", {"awaiting_reply": {"channel": "sms"}},
             {"email": "k@x.com"}) == "sms"),
        ("proactive nudge (nothing owed) keeps the sms default",
         owed_reply_channel("sms", {}, {"email": "k@x.com"}) == "sms"),
        ("no email on file -> never upgraded",
         owed_reply_channel("sms", _owes_email, {"email": ""}) == "sms"),
        ("an explicit email request is untouched",
         owed_reply_channel(
             "email", {"awaiting_reply": {"channel": "sms"}},
             {"email": "k@x.com"}) == "email"),
        ("subject gains Re:",
         _re_subject("Website feedback") == "Re: Website feedback"),
        ("an existing Re: is kept, not doubled",
         _re_subject("Re: Website feedback") == "Re: Website feedback"),
        ("no subject -> no forced Re: line",
         _re_subject(None) is None),
        ("email inbounds carry threading crumbs",
         _email_thread_fields({"email_subject": "S", "email_msg_id": "M"})
         == {"email_subject": "S", "email_msg_id": "M"}),
        ("sms inbounds carry none",
         _email_thread_fields({"body": "hi", "channel": "sms"}) == {}),
        ("compose is wired",
         "owed_reply_channel" in inspect.getsource(cmd_compose)),
        ("send_now is wired",
         "owed_reply_channel" in inspect.getsource(send_now)),
        ("send_message threads email replies",
         "emailReplyMode" in inspect.getsource(send_message)),
        ("inbound fetch captures the crumbs",
         "email_msg_id" in inspect.getsource(fetch_inbound_since)),
        ("suspension ladder rides compose --all",
         "suspension_dunning(" in inspect.getsource(cmd_compose)),
        ("suspended accounts skip normal nurture",
         "suspension_skip" in inspect.getsource(cmd_compose)),
        ("dunning: one step per slot, 48h apart",
         "last_send_at" in inspect.getsource(suspension_dunning)
         and "timedelta(hours=48)" in inspect.getsource(suspension_dunning)),
        ("dunning: 3 human message steps end at day 7",
         [d for _, d, _ in _suspension_messages("x", "y")] == [0, 3, 7]),
        ("dunning: no em dashes in client copy",
         all("—" not in b for _, _, b in _suspension_messages("x", "y"))),
        ("day-30 takedown fails safe to an URGENT card",
         "site_down_blocked_at" in inspect.getsource(suspension_dunning)
         and "URGENT" in inspect.getsource(_suspension_site_down)),
    ]
    for label, ok in rc_cases:
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")

    print("\nupload acks (2e): client uploads get one thank-you, system "
          "artifacts never do:")
    up_cases = [
        ("job photo is a client upload",
         _upload_kind("job-photos/1755-abc.jpg") == "photo"),
        ("hub team photo counts as a photo",
         _upload_kind("team/team-photo.jpg") == "photo"),
        ("logo upload classifies as logo",
         _upload_kind("brand/logo-1755.png") == "logo"),
        ("brand kit beats the generic docs bucket",
         _upload_kind("docs/brand-kit/kit.zip") == "brand kit"),
        ("customer list (docs) is a file",
         _upload_kind("docs/other/customers.xlsx") == "file"),
        ("our review QR is SYSTEM — never acked",
         _upload_kind("brand/review-qr.png") is None),
        ("photo burst ack names the count and the destination",
         _upload_ack_text({"photo": 12})
         == "Got 12 photos, thank you! They're in the queue for your "
            "Google profile and website."),
        ("a single photo reads singular",
         _upload_ack_text({"photo": 1})
         == "Got the photo, thank you! It's in the queue for your "
            "Google profile and website."),
        ("single logo ack reads naturally",
         _upload_ack_text({"logo": 1})
         == "Got the logo, thank you! We'll get it onto your site and "
            "profiles."),
        ("mixed burst folds into ONE message",
         _upload_ack_text({"photo": 3, "file": 1}).startswith(
             "Got 3 photos and the file, thank you!")),
        ("empty burst -> no message",
         _upload_ack_text({}) == ""),
        ("acks stay in one SMS segment",
         all(len(_upload_ack_text(c)) <= 160 for c in
             ({"photo": 10}, {"logo": 1}, {"brand kit": 3},
              {"file": 2}, {"photo": 4, "video": 2, "file": 1}))),
        ("upload_event dedupes via the acked-paths ledger",
         "upload_acked_paths" in inspect.getsource(upload_event)),
        ("hours-gated bursts persist for the next sweep",
         "upload_ack_pending" in inspect.getsource(upload_event)),
        ("stranded watchdog rides the sweep daily",
         "upload_stranded_check" in inspect.getsource(upload_event)),
    ]
    for label, ok in up_cases:
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")

    print("\nlaunched-claim guard: 'your site is live' needs the cutover "
          "stamp:")
    _co = {"id": "CO-TEST"}
    _not_live = lambda cid: False    # noqa: E731
    _is_live = lambda cid: True      # noqa: E731
    def _boom(cid):
        raise RuntimeError("db down")
    lc_cases = [
        ("the Sarha message verbatim is blocked when not live",
         site_live_claim_violation(_co,
             "Good news, your website is live now at https://aircarerestoration.com/.",
             _not_live) is not None),
        ("'your new site went live' is blocked when not live",
         site_live_claim_violation(_co, "Your new site went live today!",
                                   _not_live) is not None),
        ("the same claim PASSES once apex_live is true",
         site_live_claim_violation(_co,
             "Good news, your website is live now.", _is_live) is None),
        ("preview wording never trips it",
         site_live_claim_violation(_co,
             "Your preview site is live at staging, take a look.",
             _not_live) is None),
        ("progressive wording never trips it",
         site_live_claim_violation(_co,
             "We're getting your website live now, we'll confirm the moment "
             "it's up.", _not_live) is None),
        ("ordinary copy never trips it",
         site_live_claim_violation(_co,
             "Quick update on the review campaign.", _not_live) is None),
        ("lookup failure FAILS CLOSED (cannot verify -> cannot claim)",
         site_live_claim_violation(_co, "Your website is live now.",
                                   _boom) is not None),
        ("send_message is wired",
         "site_live_claim_violation(company, body)"
         in inspect.getsource(send_message)),
    ]
    for label, ok in lc_cases:
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")
    print("\nblocked call promise is SUBSTITUTED, not dropped:")
    tony_reason = capability_violation("Got it, I'll give you a call shortly.")
    subs = [
        ("the live failure is blocked", bool(tony_reason)),
        ("it substitutes the handoff",
         honest_substitute(tony_reason, "Call me when u have a minute")
         == CALL_HANDOFF_REPLY),
        ("the handoff itself survives the full guard",
         outbound_guard(CALL_HANDOFF_REPLY, None) is None),
        ("the handoff fits one SMS", len(CALL_HANDOFF_REPLY) <= 160),
        ("a non-call violation has no canned answer (refuse + escalate)",
         honest_substitute(capability_violation(
             "I'll have your site live by end of day."), "when will it be up?")
         is None),
        ("the prompt contract reaches every drafting path",
         all("cannot make phone calls" in p.lower()
             or "YOU CANNOT, EVER" in p
             for p in (COMPOSE_SYSTEM, REPLY_SYSTEM, ACK_SYSTEM,
                       CLASSIFY_SYSTEM))),
    ]
    for label, ok in subs:
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")

    # THE REIGN PAIR (Santino 2026-08-05): two messages a minute apart that
    # contradicted each other, plus "Will do, talk soon." twice four seconds
    # apart. Offline: recent_outbounds() has no KV here, so these exercise
    # the history half of the guard — the outbox half adds the same rows from
    # another process.
    print("\nsecond pass never contradicts or repeats the first:")
    now_r = datetime.now(timezone.utc)
    said_done = ("Glad you liked the about photo. The van logos are already "
                 "matched to your real logo on the staging preview, take "
                 "another look when you can.")
    promised = ("Good to hear you liked the about photo. We'll get the "
                "vehicle logos matched up so they look consistent across "
                "all the trucks.")

    def _hist(*rows):
        return [{"direction": d, "body": b, "id": i,
                 "when": now_r - timedelta(minutes=mins)}
                for d, b, i, mins in rows]

    def _with_outbox(rows, fn):
        """Run fn with the cross-process outbox stubbed (selfcheck is
        offline; the real one reads ops_kv)."""
        real = globals()["recent_outbounds"]
        globals()["recent_outbounds"] = lambda *_a, **_k: rows
        try:
            return fn()
        finally:
            globals()["recent_outbounds"] = real

    reign = _hist(("out", said_done, "ours-A", 1),
                  ("in", "I did like the about photo that was made prior.",
                   "them-1", 3))
    spoke_between = _hist(
        ("in", "Sounds good, what about the service area?", "them-2", 1),
        ("out", said_done, "ours-A", 4))
    ledger = ("- (2026-08-05) client-feedback-fix: the van logos on every "
              "vehicle image now match the real logo, live on staging")
    pair_cases = [
        ("the contradicting second message is blocked",
         "CONTRADICT" in (repeats_recent_outbound(
             None, promised, reign) or "")),
        ("the exact-duplicate closer is blocked",
         bool(repeats_recent_outbound(
             None, "Will do, talk soon.",
             _hist(("out", "Will do, talk soon.", "ours-B", 0))))),
        ("a second send with no client reply in between is blocked",
         bool(repeats_recent_outbound(
             None, "One more thing about your service area.",
             _hist(("out", said_done, "ours-A", 2))))),
        ("...but a reply AFTER the client spoke again goes out",
         repeats_recent_outbound(
             None, "Dallas, Plano and Frisco are all in there now.",
             spoke_between) is None),
        ("...and a normal nudge days later goes out",
         repeats_recent_outbound(
             None, "Can you send over your past customer list?",
             _hist(("out", said_done, "ours-A", 3000))) is None),
        # the OUTBOX half, with the KV stubbed: the other process's send is
        # invisible to GHL history but still stops this one
        ("answering the same client message twice is blocked",
         "already answered" in (_with_outbox(
             [{"body": said_done, "when": now_r - timedelta(minutes=1),
               "reply_to": "at:2026-08-05T15:52:24+00:00"}],
             lambda: repeats_recent_outbound(
                 None, "Completely different wording, same subject entirely.",
                 [], reply_to="at:2026-08-05T15:52:24+00:00")) or "")),
        ("the work ledger alone blocks a future promise",
         "CONTRADICTS the work ledger" in (repeats_recent_outbound(
             None, promised, [], evidence=ledger) or "")),
        # BOSS-DIRECTIVE BYPASS (Todd 2026-08-11): Santino's exact words may
        # pair done work with future work; only the contradiction nets yield.
        ("a boss directive sails past the contradiction nets",
         repeats_recent_outbound(
             None, promised, [], evidence=ledger,
             boss_directive=True) is None),
        ("...but a boss directive still cannot double-send verbatim",
         bool(repeats_recent_outbound(
             None, "Will do, talk soon.",
             _hist(("out", "Will do, talk soon.", "ours-B", 0)),
             boss_directive=True))),
        ("topics match across differently worded messages",
         bool(message_topics(said_done) & message_topics(promised))),
        ("a finished commitment is dropped, not re-delivered",
         bool(revalidate_commitment(
             {"pending_commitment": {
                 "promise": "We'll get the van logos matched up.",
                 "at": (now_r - timedelta(hours=2)).isoformat()}},
             [], {"sent_message_ids": []}, evidence=ledger))),
        ("the reply key is stable across paths",
         _reply_key({"at": "2026-08-05T15:52:24+00:00"})
         == _reply_key({"at": "2026-08-05T15:52:24+00:00", "id": "abc"})),
        ("build-queue cards are never spoken as instructions",
         "OUR paperwork" in CONSISTENCY_RULE
         and "INTERNAL WORK QUEUE" in Path(__file__).read_text()),
    ]
    for label, ok in pair_cases:
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")

    print("\ndirective classifier:")
    for body, author, want in _DIRECTIVE_CASES:
        got = is_boss_directive({"body": body, "author": author})
        ok = got == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {str(got):<5} {body[:64]!r}")
    print("\nlength constants:")
    checks = [
        ("normal target under 210", SMS_TARGET_CHARS <= 210),
        ("normal ceiling under 280", SMS_MAX_CHARS <= 280),
        ("first-contact leaves room for the intro",
         SMS_TARGET_CHARS_FIRST >= len(INTRO_TEMPLATE.format(
             first="Christopher", name=ASSISTANT_NAME, brand=BRAND_NAME)) + 60),
        ("ceilings above targets",
         SMS_MAX_CHARS > SMS_TARGET_CHARS
         and SMS_MAX_CHARS_FIRST > SMS_TARGET_CHARS_FIRST
         and SMS_MAX_CHARS_STEPS > SMS_TARGET_CHARS_STEPS),
    ]
    for label, ok in checks:
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")
    print("\nsentence trim never cuts mid-sentence:")
    body = ("First sentence here. Second sentence is longer than the rest. "
            "Third one trails off.")
    trimmed = _sentence_trim(body, 40)
    ok = trimmed.endswith(".") and len(trimmed) <= max(40, len(body.split(". ")[0]) + 1)
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {trimmed!r}")
    print("\nsteps exception fires only on an explicit how-question:")
    for text, want in [("How do I do that?", True),
                       ("Walk me through it", True),
                       ("I don't know how to export that", True),
                       ("Yes its with GoDaddy", False),
                       ("Sounds good, thanks", False)]:
        got = bool(_STEPS_ASK_RE.search(text))
        ok = got == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {str(got):<5} {text!r}")

    # OWED CLOSER SURVIVES (Santino 2026-08-04, Fran/Quality Contracting).
    # "I'll take time tomorrow to write up specifics. Thank you" arrived at
    # 19:00 his time; the closer was refused on business hours and vanished
    # without a trace. It must now be an armed flag that a later pass finds,
    # while still being impossible to double-send.
    print("\nowed closer survives an out-of-hours refusal:")
    fran = "I'll take time tomorrow to write up specifics.  Thank you"
    now_ = datetime.now(timezone.utc)
    stamp = (now_ - timedelta(hours=2)).isoformat()
    st_ = {"sent_message_ids": ["ours-1"]}

    def _closer_cs():
        return {"awaiting_reply": {"body": fran, "at": stamp,
                                   "channel": "sms", "kind": "closer"}}

    closer_cases = [
        ("substantive sign-off is not a bare ack", not _bare_ack(fran)),
        ("armed flag is still owed when nothing followed",
         (pending_client_message(_closer_cs(), [], st_) or {}).get("kind")
         == "closer"),
        # ours voids it — we already got the last word, never send twice
        ("OUR OWN newer outbound voids it",
         pending_client_message(
             _closer_cs(),
             [{"direction": "out", "id": "ours-1", "when": now_,
               "channel": "sms", "body": "Sounds good, whenever you're ready."}],
             st_) is None),
        ("a HUMAN newer outbound voids it too",
         pending_client_message(
             _closer_cs(),
             [{"direction": "out", "id": "santino-x", "when": now_,
               "channel": "sms", "body": "Talk tomorrow."}], st_) is None),
        # a question flag must KEEP the old asymmetry: our holding ack is not
        # the answer, so it may not void the flag
        ("question flag still survives our own holding ack",
         (pending_client_message(
             {"awaiting_reply": {"body": "why is it suspended?", "at": stamp,
                                 "channel": "sms", "kind": "question"}},
             [{"direction": "out", "id": "ours-1", "when": now_,
               "channel": "sms", "body": "Let me look into that."}],
             st_) or {}).get("kind") == "question"),
        # the compose --all roster must SEE a company we owe a reply to even
        # when it has no open ask left
        ("owed reply puts a company on the compose roster",
         "CO-owed" in {c for c, s in
                       {"CO-owed": _closer_cs(), "CO-quiet": {}}.items()
                       if s.get("awaiting_reply") or s.get("pending_commitment")}),
    ]
    for label, ok in closer_cases:
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")

    # SEND WINDOW (Santino 2026-08-04). Replies get the shoulder hours; nudges
    # never do; quiet hours stop everything. Hours are simulated by pinning a
    # fake company timezone and reading the gate's verdict at each local hour.
    print("\nsend window (quiet 21-07 / business 9-18 / shoulder replies):")
    real_now = datetime.now(timezone.utc)

    def verdict(local_hour: int, *, minutes_old=None):
        """Allowed? at `local_hour` client-local, for a reply that old (or a
        nudge when minutes_old is None)."""
        tz = ZoneInfo("UTC")
        target = real_now.replace(hour=local_hour % 24, minute=30)
        # business_hours_check reads the clock, so evaluate its pure logic
        # against a constructed local time instead of monkeypatching time.
        hour = target.astimezone(tz).hour
        if hour >= QUIET_HOUR_START or hour < QUIET_HOUR_END:
            return "quiet"
        if BUSINESS_HOUR_START <= hour < BUSINESS_HOUR_END:
            return "allowed"
        if minutes_old is None:
            return "refused"
        if minutes_old <= FAST_REPLY_MINUTES:
            return "allowed"
        return "allowed" if hour >= BUSINESS_HOUR_END else "refused"

    window_cases = [
        # Fran's actual case: 19:00 local, replying two minutes after his text
        ("19:00 fast reply (2 min) sends", verdict(19, minutes_old=2) == "allowed"),
        ("19:00 evening ack (90 min) still sends",
         verdict(19, minutes_old=90) == "allowed"),
        ("19:00 unprompted nudge refused", verdict(19) == "refused"),
        ("08:00 fast reply (2 min) sends", verdict(8, minutes_old=2) == "allowed"),
        # morning shoulder has no ack extension: last night's message waits
        ("08:00 stale reply (600 min) refused",
         verdict(8, minutes_old=600) == "refused"),
        ("08:00 unprompted nudge refused", verdict(8) == "refused"),
        ("02:00 fast reply BLOCKED by quiet hours",
         verdict(2, minutes_old=1) == "quiet"),
        ("22:00 fast reply BLOCKED by quiet hours",
         verdict(22, minutes_old=1) == "quiet"),
        ("13:00 nudge sends normally", verdict(13) == "allowed"),
        ("quiet floor and business window do not overlap",
         QUIET_HOUR_END <= BUSINESS_HOUR_START
         and BUSINESS_HOUR_END <= QUIET_HOUR_START),
    ]
    for label, ok in window_cases:
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")

    # DEFERRED RE-CHECK: a reason held overnight is re-validated, not replayed.
    print("\ndeferred reasons are re-checked, never replayed:")
    old_at = (now_ - timedelta(hours=12))
    newer_msg = {"direction": "in", "id": "in-2", "when": now_ - timedelta(minutes=5),
                 "channel": "sms", "body": "Actually, scratch that, here are the specifics."}
    refreshed = pending_client_message(
        {"awaiting_reply": {"body": fran, "at": old_at.isoformat(),
                            "channel": "sms", "kind": "closer"}},
        [newer_msg], st_) or {}
    commit_cs = {"pending_commitment": {"promise": "I'll find out and get right back to you.",
                                        "at": old_at.isoformat()}}
    recheck_cases = [
        ("a newer client message REPLACES the armed body",
         refreshed.get("body") == newer_msg["body"]),
        ("the refreshed reason reports why", bool(refreshed.get("recheck"))),
        ("the fast-reply clock resets to the NEWER message",
         _as_utc(refreshed.get("at")) == newer_msg["when"]),
        ("a human answering voids the open commitment",
         bool(revalidate_commitment(
             commit_cs,
             [{"direction": "out", "id": "santino-y", "when": now_,
               "channel": "sms", "body": "Talked to them, all set."}], st_))
         and commit_cs.get("pending_commitment") is None),
        ("our own outbound does NOT void the commitment (we still owe it)",
         revalidate_commitment(
             {"pending_commitment": {"promise": "p", "at": old_at.isoformat()}},
             [{"direction": "out", "id": "ours-1", "when": now_,
               "channel": "sms", "body": "one sec"}], st_) is None),
        # Jim/CRW 2026-09-28 replay: the holding line promised the number,
        # our own correction delivered it, Sunday "delivered" it again.
        ("Jim: our own SUBSTANTIVE follow-through voids the commitment",
         bool(revalidate_commitment(
             {"pending_commitment": {"promise": "I'll get you the exact number "
                                     "so you're not caught off guard, one sec.",
                                     "at": old_at.isoformat()}},
             [{"direction": "out", "id": "mkt-2", "when": now_, "machine": True,
               "channel": "sms", "body": "My mistake Jimmy, there's no setup "
               "fee, you only pay per lead, usually 25 to 95 dollars."}], st_))),
        ("Jim: our own substantive answer voids an owed QUESTION",
         pending_client_message(
             {"awaiting_reply": {"body": "How much is it?", "at": stamp,
                                 "channel": "sms", "kind": "question"}},
             [{"direction": "out", "id": "mkt-3", "when": now_, "machine": True,
               "channel": "sms", "body": "No setup fee, you only pay per lead, "
               "usually 25 to 95 dollars with a weekly cap."}], st_) is None),
        ("...but our holding line still leaves the question owed",
         (pending_client_message(
             {"awaiting_reply": {"body": "How much is it?", "at": stamp,
                                 "channel": "sms", "kind": "question"}},
             [{"direction": "out", "id": "mkt-4", "when": now_, "machine": True,
               "channel": "sms", "body": "I'll get you the exact number, one sec."}],
             st_) or {}).get("kind") == "question"),
        # 2026-09-04 regression: API sends wear Santino's userId + an appId
        ("an API send (marketplace appId) is a machine row, never a human",
         _is_machine_row({"userId": "u1", "source": "app",
                          "meta": {"marketplace": {"appId": "a1"}}})
         and not _is_machine_row({"userId": "u1", "source": "app", "meta": None})
         and _is_machine_row({"userId": "u1", "source": "workflow"})),
    ]
    for label, ok in recheck_cases:
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")

    # ---- access asks are classified to the RIGHT guard (Santino 2026-08-05)
    # These regexes decide whether a client gets asked for access we already
    # hold. Every incident so far — Curt, Greg, Jaziel, Angie — was a
    # classification failure, not a judgement failure, so the vocabulary is
    # pinned here with the real sentences that went out.
    print("\naccess asks route to the right guard "
          "(ads/LSA link vs GBP seat vs connect):")

    def _gbp_kind(t: str) -> str:
        if _GBP_ASK_NOT_RE.search(t):
            return "none"
        if _GBP_CONNECT_ASK_RE.search(t):
            return "connect"
        return "mgr" if _GBP_MGR_ASK_RE.search(t) else "none"

    access_cases = [
        # (text, is_ads_ask, gbp_kind)
        ("have Isaac approve Google's request to let us manage their "
         "Local Services Ads", True, "none"),
        ("Can you accept the Google Ads manager access invite for account "
         "304-178-5923?", True, "none"),
        ("Can you have Jack add contact@restorationai.io as a Manager on "
         "your Google Business Profile? Settings, then People and access",
         False, "mgr"),
        ("ASK CLIENT: connect their Google account so we can manage the "
         "Business Profile, reviews and rankings", False, "connect"),
        ("ASK CLIENT: confirm they actually offer 12 services listed on "
         "their Google profile", False, "none"),
        ("ASK CLIENT: Fran needs to verify their Google listing — it is "
         "invisible on Maps until then", False, "none"),
        ("ASK CLIENT: send us access to their domain (crew3r.com) so the "
         "new site can go live", False, "none"),
        ("[DOMAIN-ACCESS-UNVERIFIED] crew3r.com was marked 'access "
         "confirmed' by hand, but no registrar access invite has ever "
         "reached setup@restorationai.io", False, "none"),
        ("Finished job photos for the Google Business Profile", False, "none"),
        ("ASK CLIENT: do they want Local Services Ads, the Google "
         "Guaranteed listings at the top of search?", False, "none"),
        ("Their manager link is already ACTIVE, do not ask them to accept "
         "the invite again", False, "none"),
    ]
    for text, want_ads, want_gbp in access_cases:
        got_ads, got_gbp = _is_lsa_ask(text), _gbp_kind(text)
        ok = (got_ads == want_ads and got_gbp == want_gbp)
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} "
              f"ads={str(got_ads):<5} gbp={got_gbp:<7} {text[:52]!r}")
    # An ask can never belong to both guards — that is how one of them ends
    # up silently undoing the other's decision.
    both = [t for t, _a, _g in access_cases
            if _is_lsa_ask(t) and _gbp_kind(t) != "none"]
    fails += bool(both)
    print(f"  {'ok  ' if not both else 'FAIL'} no ask matches both guards")

    # ---- internal work never leaks into a client message ------------------
    print("\ninternal work is read-only — a draft that describes it is held:")
    _open = [{"title": "PUSH THE SITE LIVE: gogreenrestorationofnc.com"}]
    leak_cases = [
        # (draft, internal work open?, should be blocked)
        ("We're pushing your site live tonight.", True, True),
        ("Your nameservers are already pointing at Cloudflare.", True, True),
        ("I'll get the MCC access sorted.", True, True),
        # ...the same words with NO internal work open are not evidence.
        ("We're pushing your site live tonight.", False, False),
        # ...and ordinary, true client language must still go out.
        ("Your new site is live at https://crew3r.com.", True, False),
        ("Thanks Todd, we'll take a look at those photos.", True, False),
        ("Can you send your logo when you get a minute?", True, False),
    ]
    for draft, has_work, want_block in leak_cases:
        got = internal_leak_violation(draft, _open if has_work else [])
        ok = bool(got) == want_block
        fails += (not ok)
        print(f"  {'ok  ' if ok else 'FAIL'} internal={str(has_work):<5} "
              f"blocked={str(bool(got)):<5} {draft[:52]!r}")
    # ...the client's OWN preview link is the preview-share flow doing its
    # job, never a leak (2026-09-19: ACS + DryCor reveals both held) — but
    # ANOTHER client's pages.dev link is still one.
    _co = {"rank_ai_slug": "aldredo-moreno"}
    own = internal_leak_violation(
        "Your new site is up: https://rankai-aldredo-moreno.pages.dev "
        "What do you think?", _open, _co)
    other = internal_leak_violation(
        "See https://rankai-drycor-restore.pages.dev", _open, _co)
    fails += bool(own) + (not other)
    print(f"  {'ok  ' if not own else 'FAIL'} own preview link passes "
          "with internal work open")
    print(f"  {'ok  ' if other else 'FAIL'} someone else's pages.dev "
          "link still holds")

    # ---- a locked business name is never renegotiated by Monica ----------
    print("\nlocked-name guard (ACS 2026-09-19):")
    _LOCKED_NAME_CACHE["CO-selftest"] = (
        "ACS Enterprise - 24/7 Emergency Water Damage Restoration, "
        "Carpet and Air Duct Cleaning")
    _co = {"id": "CO-selftest"}
    lock_cases = [
        # Monica's actual bad send: proposes a DIFFERENT quoted name
        ('Since you don\'t do carpet or duct work, let\'s drop those from '
         'the name. New fit: "ACS Enterprise - Water Damage Restoration & '
         'Sewage Cleanup." Want to lock that in?', True),
        # renegotiation phrasing without quotes still holds
        ("Happy to rework the name if you want something shorter.", True),
        # restating the LOCKED name letter for letter passes
        ('The exact name to file is "ACS Enterprise - 24/7 Emergency Water '
         'Damage Restoration, Carpet and Air Duct Cleaning", letter for '
         'letter.', False),
        # ordinary copy with a hyphen does not trip net A
        ("Your new site is up - take a look and tell us what you think.",
         False),
    ]
    for draft, want_block in lock_cases:
        got = locked_name_violation(_co, draft)
        ok = bool(got) == want_block
        fails += (not ok)
        print(f"  {'ok  ' if ok else 'FAIL'} blocked={str(bool(got)):<5} "
              f"{draft[:56]!r}")
    _LOCKED_NAME_CACHE.pop("CO-selftest", None)

    # ---- file requests are hub-link-only and device-neutral ---------------
    print("\nfile requests: never email, never assume a phone:")
    file_cases = [
        ("Just email it to setup@restorationai.io when you get a chance.", True),
        ("Send the list to contact@restorationai.io", True),
        ("Reply to this message with the file attached", True),
        # ...the hub link is the whole point and must always pass.
        ("Upload it here, no login needed: https://restorationai.io/hub/x/y", False),
        ("Can you send your logo when you get a minute?", False),
        # ...and a registrar ACCESS INVITE goes to an email BY DESIGN
        # (Jerrott 2026-08-11: the GoDaddy answer was shredded twice).
        ("Sign in at account.godaddy.com/access, click Invite to Access, and "
         "send the invite to setup@restorationai.io", False),
        ("In GoDaddy, add delegate access for setup@restorationai.io", False),
    ]
    for draft, want_block in file_cases:
        got = file_request_violation(draft)
        ok = bool(got) == want_block
        fails += (not ok)
        print(f"  {'ok  ' if ok else 'FAIL'} blocked={str(bool(got)):<5} {draft[:56]!r}")
    # ---- reply-to-approve: a blanket yes converts, a partial one does not --
    print("\nreply-to-approve: only an unmistakable yes flips the tasks:")
    approve_cases = [
        ("Yes add fire to go greens site", "all"),
        ("yes", "all"),
        ("Go ahead", "all"),
        ("do them all", "all"),
        # ...the HomeLyft reply. Approves most, cancels one. A blanket flip
        # here would have approved the exact task he just cancelled.
        ("We're already past August 5th so we don't need to send the AI "
         "reception set-up to Josiah.", "partial"),
        ("Yes but not the customer list one", "partial"),
        ("Do these except the last one", "partial"),
        # ...and a question is not an approval at all.
        ("What was the date that the calendar invite is supposed to be for?", "none"),
        ("", "none"),
    ]
    for reply, want in approve_cases:
        got = approval_verdict(reply)
        ok = got == want
        fails += (not ok)
        print(f"  {'ok  ' if ok else 'FAIL'} {got:<8} (want {want:<8}) {reply[:46]!r}")

    softened = [
        ("Tap Upload Photos and add it from your phone.",
         "Click Upload Photos and add it from your phone or computer."),
    ]
    for raw, want in softened:
        got = soften_device_assumption(raw)
        ok = got == want
        fails += (not ok)
        print(f"  {'ok  ' if ok else 'FAIL'} softened -> {got!r}")

    # ---- send-time revalidation (2026-08-12): a seeded ask whose derived
    # check is already satisfied is dropped + auto-resolved at compose time;
    # anything the checker doesn't recognize is kept. Seed matching is a pure
    # function; the filter behavior runs with the checker stubbed (selfcheck
    # is offline — the real checks hit Supabase/storage).
    print("\nsend-time revalidation: seed matching + the compose filter:")
    import ask_revalidate as _ar
    from client_ops_sync import action_key as _akey
    _cid, _slug = "CO-SELFCHECK", "acme-restoration"
    reval_cases = [
        ("logo seed matches",
         _ar.seed_kind(_cid, _slug,
                       _akey(_cid, f"citations-logo-{_slug}")) == "logo"),
        ("nap seed matches",
         _ar.seed_kind(_cid, _slug,
                       _akey(_cid, f"citations-nap-{_slug}")) == "nap"),
        ("preview seed matches (the one LITERAL action_key)",
         _ar.seed_kind(_cid, _slug,
                       f"site-preview-feedback-{_slug}") == "preview"),
        ("domain-access seed matches",
         _ar.seed_kind(_cid, _slug,
                       _akey(_cid, f"domain-access-{_slug}")) == "domain"),
        ("domain-verify seed matches",
         _ar.seed_kind(_cid, _slug,
                       _akey(_cid, f"domain-verify-{_slug}")) == "domain"),
        ("an unrelated seed is nobody's",
         _ar.seed_kind(_cid, _slug,
                       _akey(_cid, f"gbp-verify-{_slug}")) is None),
        ("no slug means no opinion",
         _ar.seed_kind(_cid, None, "site-preview-feedback-x") is None),
        ("ask_still_valid has no opinion on an unknown seed",
         _ar.ask_still_valid(_cid, {"id": "x", "action_key": "not-a-seed",
                                    "rank_ai_slug": _slug}) is None),
    ]

    def _stub_valid(cid, row):
        if row["id"] == "stale-1":
            row["_stale_reason"] = "stubbed: already satisfied"
            return False
        return None

    _resolved: list = []
    _real_valid, _real_resolve = _ar.ask_still_valid, _ar.resolve_stale
    _ar.ask_still_valid = _stub_valid
    _ar.resolve_stale = lambda row_id, why, dry: _resolved.append(row_id)
    try:
        _kept = filter_already_satisfied(
            {"id": _cid},
            [{"kind": "plan", "id": "stale-1",
              "text": "Confirm the crew roster"},
             {"kind": "plan", "id": "fresh-1",
              "text": "Confirm the crew roster"},
             {"kind": "intake", "id": "int-1",
              "text": "Confirm the crew roster"}],
            dry_run=True)
    finally:
        _ar.ask_still_valid, _ar.resolve_stale = _real_valid, _real_resolve
    reval_cases += [
        ("a stale plan ask is dropped from compose",
         all(i["id"] != "stale-1" for i in _kept)),
        ("...and auto-resolved with the reason", _resolved == ["stale-1"]),
        ("an unknown-seed plan ask is kept",
         any(i["id"] == "fresh-1" for i in _kept)),
        ("intake items are never revalidated here",
         any(i["id"] == "int-1" for i in _kept)),
    ]
    for label, ok in reval_cases:
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")

    # ---- promise hold (2026-09-29, Katofsky): an overdue promise of OURS
    # silences client-owed nudges; replies still go. Pure-function check.
    print("\npromise hold: overdue promise of ours => no client-owed nudges:")
    _asks = [{"kind": "intake", "id": "a1", "text": "Send your customer list"}]
    _od = [{"id": "p1", "what": "Send name options", "due_at":
            "2026-09-22T21:00:00+00:00", "owner": "santino"}]
    _k1, _r1 = promise_hold(list(_asks), _od)
    _k2, _r2 = promise_hold(list(_asks), [])
    _k3, _r3 = promise_hold([], _od)
    for label, ok in [
        ("overdue promise drops the client-owed asks", _k1 == [] and bool(_r1)),
        ("...with a promise-hold skip reason", str(_r1).startswith("promise-hold")),
        ("no overdue promise leaves asks untouched", _k2 == _asks and _r2 is None),
        ("nothing to nudge = no hold noise (a reply path stays clean)",
         _k3 == [] and _r3 is None),
        ("lookup with no company ids is empty, never an error",
         overdue_commitments([]) == []),
    ]:
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")

    print(f"\n{'ALL GREEN' if not fails else str(fails) + ' FAILURE(S)'}")
    return 1 if fails else 0


def _revision_batches_complete(dry_run: bool, state: dict,
                               sent_log: dict) -> None:
    """AUTO REVISION LOOP (Santino 2026-09-22, FFS/Will: four finished
    batches sat on staging behind a human review gate for hours while
    Will heard nothing). Client-REQUESTED revisions close themselves:
    when a company's client-feedback [DEV] notes all resolve (and at
    least one resolved in the last 48h), the site auto-promotes to the
    branch the client sees and Monica sends the look-again message. The
    human gate remains only where it belongs: agent-initiated changes,
    confirm-first items, launches and spend."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    rows = _sb("GET", "/rest/v1/marketing_ops_notes"
               "?body=ilike.*CLIENT FEEDBACK*"
               "&body=ilike.*%5BDEV%5D*"
               "&select=company_id,status,created_at&limit=500") or []
    by_co: dict = {}
    for r in rows:
        by_co.setdefault(r["company_id"], []).append(r)
    for cid, notes in by_co.items():
        if any(n.get("status") == "open" for n in notes):
            continue
        recent = [n for n in notes if n.get("created_at")
                  and (now - datetime.fromisoformat(
                      str(n["created_at"]).replace("Z", "+00:00"))
                      ) < timedelta(hours=48)]
        if not recent:
            continue
        tag = f"rev:{cid}:{max(str(n['created_at']) for n in recent)[:16]}"
        if tag in sent_log:
            continue
        slug = _company_slug(cid)
        if not slug:
            continue
        comps = fetch_companies([cid])
        company = comps.get(cid)
        if not company or company_inactive(company):
            continue
        contact = resolve_contact(company)
        if not contact:
            continue
        tz_name, _s = resolve_timezone(company, contact)
        try:
            from zoneinfo import ZoneInfo
            hr = datetime.now(ZoneInfo(tz_name)).hour
        except Exception:  # noqa: BLE001
            hr = datetime.now(timezone.utc).hour - 7
        if not (9 <= hr < 19):
            print(f"  [rev-loop] {slug}: complete but {hr}:xx local — "
                  "next run")
            continue
        ints = (company.get("integration_settings") or {})
        if isinstance(ints, str):
            try:
                ints = json.loads(ints)
            except json.JSONDecodeError:
                ints = {}
        url = str((ints.get("site_reveal") or {}).get("url")
                  or f"https://rankai-{slug}.pages.dev").strip()
        if dry_run:
            print(f"  [rev-loop dry-run] {slug}: would promote + notify")
            continue
        import subprocess as _sp
        from render_sweep import deploy_branch
        br = deploy_branch(slug)
        rc = _sp.run([sys.executable,
                      str(Path(__file__).parent / "build_site.py"),
                      "sync-deploy", "--slug", slug, "--branch", br,
                      "--allow-dirty"], capture_output=True, text=True)
        if rc.returncode != 0:
            print(f"  [rev-loop] {slug}: promote FAILED — no notify "
                  f"({rc.stdout[-120:]})")
            continue
        nm = str(contact.get("firstName") or "").strip()
        body = ((f"Hey {nm}, " if nm else "Hey, ")
                + "the changes you asked for are in. Take another look "
                + f"here: {url} and tell us what you think.")
        try:
            res = send_message(contact, "sms", body, company=company)
            record_sent_message(state, res)
            sent_log[tag] = now.isoformat()
            kv_set("doc-complete-sent", sent_log)
            print(f"  [rev-loop] {slug}: promoted to {br} + client "
                  "notified")
        except SendBlocked as e:
            print(f"  [rev-loop] {slug}: notify BLOCKED "
                  f"({str(e)[:80]}) — next run retries")


def cmd_docs_complete(args) -> int:
    """Phase 2.2 (Santino 2026-09-22): the revision loop closes itself.
    Phase 1 files an emailed doc's items as grouped notes carrying the
    marker '(emailed doc <fname>)'. When EVERY note wearing that marker
    has resolved AND the company's dev queue is drained, Monica tells the
    client the updates are in, with the preview link — which re-arms the
    reveal clock (fresh 2d wait -> one nudge -> Ready to Launch). One
    send per doc, ever; business hours in the client's timezone."""
    dry_run = not args.send
    rows = _sb("GET", "/rest/v1/marketing_ops_notes"
               "?body=ilike.*%28emailed%20doc%20*"
               "&select=company_id,body,status&limit=500") or []
    by_doc: dict = {}
    for r in rows:
        m = re.search(r"\(emailed doc ([^)]{1,120})\)", r.get("body") or "")
        if not m:
            continue
        key = (r["company_id"], m.group(1).strip())
        by_doc.setdefault(key, []).append(r.get("status") or "open")
    sent_log = kv_get("doc-complete-sent") or {}
    state = load_state()
    if not by_doc:
        print("docs-complete: no doc-sourced task groups on file")
    for (cid, fname), statuses in by_doc.items():
        tag = f"{cid}:{fname}"
        if tag in sent_log:
            continue
        if any(s == "open" for s in statuses):
            print(f"  {fname} ({cid}): {statuses.count('open')} group(s) "
                  "still open — waiting")
            continue
        dev_open = _sb("GET", "/rest/v1/marketing_ops_notes"
                       f"?company_id=eq.{cid}&status=eq.open"
                       "&body=ilike.*%5BDEV%5D*&select=id&limit=1") or []
        if dev_open:
            print(f"  {fname} ({cid}): doc groups resolved but dev queue "
                  "still has open work — waiting for the drain")
            continue
        comps = fetch_companies([cid])
        company = comps.get(cid)
        if not company or company_inactive(company):
            continue
        contact = resolve_contact(company)
        if not contact:
            continue
        tz_name, _src = resolve_timezone(company, contact)
        try:
            from zoneinfo import ZoneInfo
            hr = datetime.now(ZoneInfo(tz_name)).hour
        except Exception:  # noqa: BLE001
            hr = datetime.now(timezone.utc).hour - 7
        if not (9 <= hr < 19):
            print(f"  {fname} ({cid}): complete, but it is {hr}:xx for "
                  "them — next run sends")
            continue
        ints = (company.get("integration_settings") or {})
        if isinstance(ints, str):
            try:
                ints = json.loads(ints)
            except json.JSONDecodeError:
                ints = {}
        url = str((ints.get("site_reveal") or {}).get("url") or "").strip()
        if not url:
            slug = _company_slug(cid)
            url = f"https://rankai-{slug}.pages.dev" if slug else ""
        if not url:
            continue
        nm = str(contact.get("firstName") or "").strip()
        body = ((f"Hey {nm}, " if nm else "Hey, ")
                + "we went through your list and the updates are in. "
                + f"Take another look here: {url} and tell us what you "
                  "think.")
        if dry_run:
            print(f"  [dry-run] would send to {cid}: {body}")
            continue
        try:
            res = send_message(contact, "sms", body, company=company)
            record_sent_message(state, res)
            sent_log[tag] = datetime.now(timezone.utc).isoformat()
            kv_set("doc-complete-sent", sent_log)
            print(f"  SENT updates-are-in for {fname} -> {cid}")
        except SendBlocked as e:
            print(f"  BLOCKED for {cid}: {str(e)[:100]}")
    _revision_batches_complete(dry_run, state, sent_log)
    if not dry_run:
        save_state(state, dry_run=False)
    return 0


def cmd_watchdog(_args) -> int:
    """Directive-latency alarm (Santino 2026-09-04). Sarha's LSA ask and
    Jimmy's launch text both sat OPEN for hours with nothing telling anyone
    which guard held them. There are NO numeric send caps — silence comes
    from guards firing on stale context, or slot handoffs dropping a company
    from rotation. This makes that state loud: any open [FROM SANTINO]/
    [FOR MONICA]/[SEND-PREVIEW] note older than 2 hours is listed and
    emailed to ops. Runs in every CI slot, even when the send pass defers
    to another Monica."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    rows = _sb("GET", "/rest/v1/marketing_ops_notes?status=eq.open"
               f"&created_at=lt.{cutoff}&select=id,company_id,body,created_at"
               "&order=created_at.asc&limit=200") or []
    stuck = [r for r in rows if any(
        r["body"].lstrip().startswith(t) for t in _DIRECTIVE_TAGS)]
    if not stuck:
        print("watchdog: no directives older than 2h — clean")
        return 0
    companies = fetch_companies(sorted({r["company_id"] for r in stuck
                                        if r.get("company_id")}))
    lines = []
    for r in stuck:
        c = companies.get(r.get("company_id") or "", {})
        age_h = "?"
        try:
            ts = re.sub(r"\.\d+", "", r["created_at"]).replace(" ", "T")
            if ts.endswith("+00"):
                ts += ":00"
            age_h = f"{(datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds() / 3600:.1f}"
        except (ValueError, TypeError):
            pass
        lines.append(f"- {c.get('name') or r.get('company_id')}: unsent for "
                     f"{age_h}h: {r['body'][:140]!r} (note {r['id']})")
    report = (f"{len(stuck)} DIRECTIVE(S) STUCK UNSENT >2h:\n"
              + "\n".join(lines))
    print(report)
    key = os.environ.get("SENDGRID_API_KEY")
    if key:
        try:
            requests.post("https://api.sendgrid.com/v3/mail/send", timeout=20,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={"personalizations": [{"to": [{"email": "contact@restorationai.io"}]}],
                      "from": {"email": "no-reply@restorationai.io",
                               "name": "Rank AI Watchdog"},
                      "subject": f"[Rank AI] {len(stuck)} Monica directive(s) stuck unsent >2h",
                      "content": [{"type": "text/plain", "value": report}]})
            print("watchdog: alert email sent")
        except Exception as e:  # noqa: BLE001
            print(f"watchdog: email failed ({str(e)[:80]})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("selfcheck", help="offline regression cases (no network)")

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

    # ONE MONICA PER SLOT (Santino 2026-08-11, "there are two Monicas"): the
    # 16:07 slot fired three times — Railway dispatch at 15:55 and 16:07,
    # then GitHub's own cron an hour late at 17:07 — and every client with an
    # open ask got each pass's independently-worded copy of the same text.
    # The runs-API dedupe on the Railway side can't see a cron that arrives
    # late, so the lock lives here, across ALL trigger sources: exit 0 =
    # acquired (run may proceed), exit 1 = another Monica ran too recently.
    pr = sub.add_parser("rename-pitch", help="open the profile-rename "
                        "conversation for one company (Monica)")
    pr.add_argument("--company", required=True, help="company id (CO-…)")
    pr.add_argument("--send", action="store_true",
                    help="actually deliver + arm the reply flow")
    pr.add_argument("--note", action="append", default=[],
                    help="talking point to ride the options text "
                         "(repeatable)")
    pr.add_argument("--force", action="store_true",
                    help="pitch despite a coverage gap warning")
    pr.add_argument("--channel", choices=("sms", "email"), default="sms",
                    help="delivery channel for the opening pitch")
    pr.add_argument("--operator", action="store_true",
                    help="operator-initiated (app button): exempt from the "
                         "human quiet window, like send_now")

    sub.add_parser("watchdog", help="loud alarm for directives stuck unsent "
                   ">2h (Sarha/Jimmy class silence, 2026-09-04)")
    pdc = sub.add_parser("docs-complete",
                         help="Phase 2.2: when every task from an emailed "
                              "revision doc resolves, tell the client the "
                              "updates are in (re-arms the reveal clock)")
    pdc.add_argument("--send", action="store_true")
    pl = sub.add_parser("runlock", help="acquire the daily-pass slot lock")
    pl.add_argument("--window-minutes", type=int, default=100,
                    help="skip if a pass started within this many minutes "
                         "(default 100 — under the 3.5h slot spacing)")

    args = ap.parse_args()

    if args.cmd == "runlock":
        now = datetime.now(timezone.utc)
        held = kv_get("concierge-run-lock") or {}
        try:
            started = datetime.fromisoformat(str(held.get("started_at")))
        except (TypeError, ValueError):
            started = None
        if started:
            age_min = (now - started).total_seconds() / 60
            if age_min < args.window_minutes:
                print(f"runlock: NOT acquired — a pass started {age_min:.0f} "
                      f"min ago (window {args.window_minutes})")
                return 1
        kv_set("concierge-run-lock", {"started_at": now.isoformat()})
        print("runlock: acquired")
        return 0
    if args.cmd == "selfcheck":
        return cmd_selfcheck(args)      # offline: no env, no network
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
              "go out on GHL's location default, which is not guaranteed to "
              "be the concierge sender. Set CONCIERGE_FROM_NUMBER="
              "+18053293449 before any real send.",
              file=sys.stderr)
    ret = {"status": cmd_status, "compose": cmd_compose,
           "inbound": cmd_inbound, "canary": cmd_canary,
           "watchdog": cmd_watchdog, "rename-pitch": cmd_rename_pitch,
           "docs-complete": cmd_docs_complete,
           "selfcheck": cmd_selfcheck}[args.cmd](args)
    if args.cmd in ("compose", "inbound", "rename-pitch"):
        flush_ops_pings(dry_run=not getattr(args, "send", False))
    sent_id_regression_check()
    return ret


if __name__ == "__main__":
    sys.exit(main())
