#!/usr/bin/env python3
"""Fathom → meeting intel + board work.

Polls the Fathom API for new recordings, matches each client-facing meeting
to a Rank AI client, distills the Fathom summary into concierge meeting
intel, drops a note on the client's GHL contact, and turns what the client
ASKED FOR on the call into work on the Today board.

The point: the Client Concierge composes nudges from this intel — after this
sync a client is never re-asked something they already answered on a call —
and every commitment made on the call becomes a trackable card within the
hour, instead of living in Santino's head until someone re-listens.

WHERE THE INTEL LIVES (the trap, 2026-08-05). Until 2026-07-12 intel was
written to clients/_ops/meeting-intel/{slug}.md. The Railway migration
(e9362053) moved it to Supabase ops_kv under `meeting-intel/{slug}` because
the worker's filesystem is disposable. Those repo files have not changed
since and they never will — a stale directory listing is NOT evidence that
this job stopped. Read the KV (or `python3 scripts/fathom_sync.py status`).
client_concierge.load_meeting_intel() merges both sources, so the old files
are still honoured as history.

CALL -> WORK (rebuilt 2026-08-05). The first version of this pass emitted
[DEV-PROPOSED]/[TODO-PROPOSED] off the summary alone, capped at 5, with a
"dev vs Santino" split guessed by the model. Two problems, both real on
2026-08-04: it under-captured (RestorationXpress asked for 6 things and 4
landed; HomeLyft asked for 9 and 4 landed), and it routed by GUESSING rather
than by risk, so a request to rewrite live copy could be filed as an
auto-runnable dev task. It now reads Fathom's own action items as well as
the summary, and routes every WEBSITE item through the same gate the inbound
concierge uses (scripts/feedback_router.risk_verdict): pixels and paint run
themselves, WORDS and FACTS stop at Santino. Non-site commitments (accounts,
listings, ads, calls) file as [TODO-PROPOSED]. Anything the CLIENT owes us
is not a card at all — it belongs in the intel the concierge nudges from.

SILENCE IS A FAILURE MODE. Every run stamps a heartbeat in ops_kv, and
`watch` turns silence into a card: a client meeting that produced no work,
or a sync that has not completed in hours, is exactly the stall nobody
noticed between 2026-07-12 and 2026-08-05.

Commands:
    sync [--send] [--backfill N] [--since YYYY-MM-DD] [--reprocess]
                                   poll + process. Default dry-run (prints
                                   what it would write); --send writes intel,
                                   GHL notes, board work and state.
                                   --backfill N mines the N most recent
                                   meetings on first run.
                                   --since re-mines meetings recorded on or
                                   after a date even if already processed
                                   (with --reprocess the superseded cards
                                   from the earlier pass are retired first).
    watch [--send] [--days N]      loud failure path: file a card when
                                   meetings exist but no work came out of
                                   them, or when the sync itself has stalled.
    status                         what the last run did, per client.

State: ops_kv `fathom-sync-state` (processed recording ids; the repo file
clients/_ops/fathom-sync-state.json is a pre-KV seed only).
Heartbeat: ops_kv `fathom-sync-heartbeat`.
Env: FATHOM_API_KEY + the concierge's env. Railway ops-worker: every 30 min.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from client_concierge import (  # noqa: E402
    ROOT, _sb, anthropic_json, fetch_companies, kv_get, kv_set, load_env,
)


def sb_insert_note(company_id: str, body: str) -> None:
    _sb("POST", "/rest/v1/marketing_ops_notes",
        body={"company_id": company_id, "body": body})

STATE_PATH = ROOT / "clients" / "_ops" / "fathom-sync-state.json"
INTEL_DIR = ROOT / "clients" / "_ops" / "meeting-intel"
FATHOM_API = "https://api.fathom.ai/external/v1"
HEARTBEAT_KEY = "fathom-sync-heartbeat"
WATCH_KEY = "fathom-watch-state"

MATCH_SYSTEM = """\
You match a meeting recording to one of our restoration-industry clients.
You get the client roster (slug, company name, owner) and the meeting's
title + summary opening. Sales calls with NEW prospects (anyone not on the
roster), internal team meetings, and vendor calls match NOTHING.
Return ONLY JSON: {"slug": "<roster slug>"|null, "why": string}"""

DISTILL_SYSTEM = """\
You distill a meeting summary into INTERNAL onboarding intel for our client
concierge (an assistant that texts clients about missing setup items). Output
tight markdown for the intel file:

### <YYYY-MM-DD> — <meeting title> (auto-synced from Fathom)
- FACTS: hard facts learned (license numbers, domains, emails, who owns what,
  decisions made). One per line.
- ANSWERED/IN-PROGRESS: setup items this meeting answered or that are now in
  motion on either side — the concierge must NOT re-ask these. Be explicit.
- ASK NEXT: anything the client agreed to send/do (so the concierge nudges
  for exactly that, in plain words).
- APPOINTMENTS: any future call/meeting scheduled, with date+time+tz.
Omit empty sections. No preamble. Facts only — never invent.
Return ONLY JSON: {"intel": string, "ghl_note": string}
ghl_note = 3-6 plain sentences for the client's CRM record (what was covered,
what's next), no markdown, no links."""

# Call -> WORK (Santino 2026-07-30, rebuilt 2026-08-05). The listener turns
# call content into trackable work. Auto-EXECUTION straight off a call is
# still too fragile to hand a machine wholesale, so WEBSITE items go through
# the same risk gate as inbound client feedback (feedback_router.risk_verdict:
# imagery/design/brand/service-area can run themselves; copy, facts, claims
# and pricing stop at Santino's Approve button), and everything else is
# proposed for a human.
EXTRACT_SYSTEM = """\
You read one client meeting (an AI summary plus Fathom's own action items)
and extract the WORK IT CREATED FOR US. Nothing else.

Each item goes in one of two lanes:

- "site" = a change to the CLIENT'S WEBSITE that a build agent could make.
  Give it a category, exactly one of:
    imagery      photos/illustrations on the site
    design       look, feel, colours, layout, theme
    brand        logo, livery, brand assets
    service_area which cities/towns/areas the site claims to serve
    copy         the WORDS on a page (headlines, paragraphs, CTAs)
    facts        business facts (phone, address, hours, services, licence)
    rejection    they turned the site down without saying what to change
    other        site work that fits none of the above
- "ops" = work we own that is NOT a website edit: Google/GBP/LSA/Ads account
  work, listings and citations, call tracking, review campaigns, scheduling a
  call, sending something to the client.

STRICT RULES
- Only what was EXPLICITLY asked for or committed to. Ideas floated, maybes,
  "we could eventually" and general discussion are NOT items.
- Skip anything the CLIENT owes US (their homework: they will send a list,
  they will upload photos, they will get their IT to grant access). Those are
  handled elsewhere; they are not our work.
- Skip anything the summary says is already DONE.
- One item per distinct ask. Do not merge two asks into one line, and do not
  split one ask into two.
- "what" is imperative and concrete enough to act on without the recording.
- "where" names the page/section/asset when the meeting did ("service area
  page", "homepage hero", "site-wide"); "" when it did not.
- "quote" is the closest VERBATIM line from the summary or action item that
  proves the ask. Never invent it.
- "confidence" is "high" only when the ask is unambiguous and the wording
  leaves nothing to interpret.
- Up to 12 items. An empty list is a fine answer for a check-in call.

Also return "who": the CLIENT-SIDE person who asked, as the summary names
them (first name is fine). Never us. "" when the summary does not say.

Return ONLY JSON:
{"who": string,
 "items": [{"lane": "site"|"ops", "category": string, "what": string,
            "where": string, "quote": string,
            "confidence": "high"|"medium"|"low"}]}
For lane "ops" set category to "" (it is unused)."""

# Non-site commitments read as a task, not as a JSON blob — same shape as the
# feedback router's cards so the Today board looks consistent. The trailer is
# deliberately NOT feedback_router.ORIGIN_MARK: parse_origin() must not match
# it, or dev_inbox would text the client "the change you asked for is done"
# after we merely created a Bing listing.
MEETING_MARK = "ORIGIN: meeting-commitment"


def load_state() -> dict:
    state = kv_get("fathom-sync-state")
    if state is None and STATE_PATH.exists():   # one-time seed from pre-kv file
        state = json.loads(STATE_PATH.read_text())
    return state or {"processed": {}, "initialized_at": None}


def _fathom_keys() -> list[str]:
    """Santino's key + every rep's own (Aldredo/ACS 2026-09-08: his onboarding
    call was recorded ONLY under Levi's Fathom, so the ops pipeline never saw
    it — no intel, no auto-booked follow-up). FATHOM_SALES_API_KEYS is the
    same comma-list the sales flow uses."""
    keys = [os.environ.get("FATHOM_API_KEY", "")]
    keys += (os.environ.get("FATHOM_SALES_API_KEYS") or "").split(",")
    return [k.strip() for k in keys if k.strip()]


def fathom_meetings(limit: int = 25) -> list[dict]:
    """Recent recordings across EVERY configured Fathom account, newest
    first, with summary AND action items; each tagged with the key that can
    fetch its transcript.

    Fathom's own action items are the richer signal: its notetaker catches
    asks the prose summary compresses away (2026-08-04 HomeLyft: 9 action
    items against a summary that yielded 4 tasks), and each one carries an
    assignee, which is how we tell OUR work from the client's homework.
    """
    items: list[dict] = []
    for key in _fathom_keys():
        try:
            r = requests.get(f"{FATHOM_API}/meetings",
                             params={"include_summary": "true",
                                     "include_action_items": "true",
                                     "limit": limit},
                             headers={"X-Api-Key": key}, timeout=60)
            r.raise_for_status()
            for m in r.json().get("items", []):
                m["_api_key"] = key
                items.append(m)
        except Exception as e:  # noqa: BLE001 — one dead key must not blind the sync
            sys.stderr.write(f"  fathom key …{key[-4:]} failed: {str(e)[:100]}\n")
    items.sort(key=lambda m: m.get("recording_start_time") or "", reverse=True)
    return items


def action_items_text(m: dict) -> str:
    """Fathom's action items as prompt input, assignee included."""
    lines = []
    for ai in (m.get("action_items") or []):
        desc = str(ai.get("description") or "").strip()
        if not desc:
            continue
        who = ((ai.get("assignee") or {}).get("name") or "").strip()
        done = " [already completed]" if ai.get("completed") else ""
        lines.append(f"- {desc}" + (f"  (assigned to: {who})" if who else "")
                     + done)
    return "\n".join(lines)


def meeting_when(m: dict) -> str:
    return (m.get("recording_start_time") or m.get("created_at") or "")[:10]


def roster(companies: dict) -> tuple[str, dict]:
    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    slug_by_cid = {cid: slug for slug, cid in cmap.items()}
    lines, by_slug = [], {}
    for cid, co in companies.items():
        slug = slug_by_cid.get(cid)
        if not slug:
            continue
        contacts = ((co.get("integration_settings") or {}).get("contacts")) or []
        people = "; ".join(
            f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
            + (f" <{c.get('email')}>" if c.get("email") else "")
            for c in contacts if c.get("first_name") or c.get("email"))
        lines.append(f"- slug={slug}  company=\"{co.get('name')}\"  "
                     f"people=\"{people}\"")
        by_slug[slug] = co
    return "\n".join(lines), by_slug


def ghl_contact_for(company: dict) -> str | None:
    contacts = ((company.get("integration_settings") or {}).get("contacts")) or []
    for c in contacts:
        if c.get("ghl_contact_id"):
            return c["ghl_contact_id"]
    return (company.get("integration_settings") or {}).get("ghl_contact_id")


def add_ghl_note(contact_id: str, body: str) -> None:
    from client_concierge import _ghl
    _ghl("POST", f"/contacts/{contact_id}/notes", body={"body": body})


# --------------------------------------------------------------- call -> work
def compose_ops_note(item: dict, *, company_name: str, slug: str,
                     who: str, title: str, when: str, url: str | None) -> str:
    """A non-website commitment, written as a task a human can act on."""
    where = str(item.get("where") or "").strip()
    lines = [
        f"[TODO-PROPOSED] CALL COMMITMENT from {who} at {company_name}, "
        f"{when}:",
        str(item.get("what") or "").strip(),
    ]
    if where:
        lines.append(f"WHERE: {where}")
    if item.get("quote"):
        lines.append(f'THEY SAID: "{str(item["quote"]).strip()}"')
    lines.append(f"CALL: {title}" + (f" — {url}" if url else ""))
    lines.append("This is account/listing/outreach work, not a website edit, "
                 "so no build agent can take it unattended. Approve to queue "
                 "it, dismiss if it is already handled.")
    lines.append(f"{MEETING_MARK} | who={who} | slug={slug} | when={when}"
                 + (f" | call={url}" if url else ""))
    return "\n".join(lines)


def supersede_old_proposals(company_id: str, title: str, when: str,
                            dry_run: bool) -> int:
    """Retire cards the FIRST-GENERATION extractor filed for this recording.

    Only ever touches notes carrying that generation's exact marker
    ("(from call: {title}, {when}"), so re-mining a call replaces its cards
    instead of stacking a second, differently-worded copy beside them.

    NEVER touches a card Santino has already ACTED ON. The app's Approve
    button rewrites [DEV-PROPOSED]/[TODO-PROPOSED] to [DEV] in place, so a
    re-mine that retired those would silently un-approve queued dev work and
    then re-file it as a fresh proposal — the machine overruling the human.
    Only still-awaiting-approval proposals are superseded.
    """
    marker = f"(from call: {title}, {when}"
    try:
        from feedback_router import _recent_notes
        rows = _recent_notes(company_id, days=45)
    except Exception as e:  # noqa: BLE001
        print(f"    ! could not look up superseded cards: {str(e)[:90]}")
        return 0
    n = 0
    for r in rows:
        body = str(r.get("body") or "").lstrip()
        if r.get("status") != "open" or marker not in body:
            continue
        if not body.startswith(("[DEV-PROPOSED]", "[TODO-PROPOSED]")):
            print(f"    keeping (already acted on): {body[:80]}")
            continue
        n += 1
        if dry_run:
            print(f"    [dry-run] would retire superseded card: {body[:90]}")
            continue
        try:
            _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{r['id']}",
                {"status": "resolved",
                 "resolved_at": datetime.now(timezone.utc).isoformat()})
            print(f"    superseded (re-mined): {body[:80]}")
        except Exception as e:  # noqa: BLE001
            print(f"    ! could not retire {str(r['id'])[:8]}: {str(e)[:80]}")
            n -= 1
    return n


def route_meeting_work(company: dict, slug: str, m: dict, *, title: str,
                       when: str, summary_md: str, dry_run: bool) -> dict:
    """Turn one call into board work. Returns a small per-lane tally.

    WEBSITE items go through feedback_router (the risk gate decides [DEV] vs
    [TODO-PROPOSED]); everything else is proposed for a human. Fail-open:
    intel and the GHL note have already landed by the time this runs, so an
    extraction failure costs cards, never the whole sync.
    """
    tally = {"site_auto": 0, "site_proposed": 0, "ops": 0, "skipped": 0,
             "error": None}
    ai_text = action_items_text(m)
    ext = anthropic_json(
        EXTRACT_SYSTEM,
        f"Client: {company.get('name')} (slug {slug})\n"
        f"Meeting: {title} on {when}\n\n"
        f"Fathom action items:\n{ai_text or '(none)'}\n\n"
        f"Summary:\n{summary_md[:9000]}",
        max_tokens=6000)
    # WHO ASKED. calendar_invitees is useless here — every Fathom recording
    # lists only Santino, so reading it would file the client's own request
    # under our name and Monica would later tell them "you asked us to…"
    # about something Santino said. The extractor names them; the client's
    # first stored contact is the fallback.
    who = str(ext.get("who") or "").strip()
    if not who:
        contacts = ((company.get("integration_settings") or {})
                    .get("contacts")) or []
        who = str((contacts[0] or {}).get("first_name") or "").strip() \
            if contacts else ""
    who = f"{who} (on the {when} call)" if who else \
        f"{company.get('name')} (on the {when} call)"
    items = [i for i in (ext.get("items") or []) if isinstance(i, dict)][:12]
    site = [i for i in items if str(i.get("lane") or "").lower() == "site"]
    ops = [i for i in items if str(i.get("lane") or "").lower() != "site"]
    print(f"    extracted {len(items)} item(s): {len(site)} site, "
          f"{len(ops)} ops")

    if site:
        from feedback_router import route_feedback
        res = route_feedback(
            company,
            [{"category": i.get("category") or "other",
              "what": i.get("what"), "where": i.get("where"),
              "quote": i.get("quote") or i.get("what"),
              "confidence": i.get("confidence") or "low"} for i in site],
            who=who, when=when, dry_run=dry_run, limit=12)
        tally["site_auto"] = sum(1 for r in res if r.get("tag") == "[DEV]")
        tally["site_proposed"] = sum(1 for r in res
                                     if r.get("tag") == "[TODO-PROPOSED]")
        tally["skipped"] += len(site) - len(res)

    for item in ops:
        what = str(item.get("what") or "").strip()
        if not what:
            tally["skipped"] += 1
            continue
        try:
            # `what` is what makes this dedupe work at all: Fathom's action
            # items are frequently compound, so one verbatim quote can back
            # three separate commitments (DISS, 2026-08-04). Quote-only
            # matching would have filed the first and swallowed the rest —
            # and, because ops cards carry the MEETING marker rather than the
            # feedback one, the check never matched anything either way.
            from feedback_router import already_queued
            dupe = already_queued(company["id"],
                                  str(item.get("quote") or what), what)
        except Exception:  # noqa: BLE001
            dupe = None
        if dupe:
            print(f"    already on the board as {str(dupe)[:8]} — "
                  f"not filing again ({what[:60]!r})")
            tally["skipped"] += 1
            continue
        body = compose_ops_note(item, company_name=company.get("name") or slug,
                                slug=slug, who=who, title=title, when=when,
                                url=m.get("url"))
        if dry_run:
            print(f"    [dry-run] would file OPS card: {what[:90]}")
            tally["ops"] += 1
            continue
        sb_insert_note(company["id"], body)
        tally["ops"] += 1
        print(f"    filed [TODO-PROPOSED] ops card: {what[:80]}")
        try:
            from work_log import work_log
            work_log(company["id"], "outreach", "call-commitment-queued",
                     f"On the {when} call {company.get('name')} asked for "
                     f"this and it went on the board the same day: "
                     f"{what[:140]}",
                     evidence={"quote": str(item.get("quote") or "")[:300],
                               "call": m.get("url"), "title": title},
                     actor="fathom-sync",
                     source="fathom_sync.route_meeting_work")
        except Exception as e:  # noqa: BLE001
            print(f"    [work-log] warn: {str(e)[:90]}")
    return tally


RECAP_SYSTEM = """\
You write the post-meeting recap TEXT MESSAGE a marketing agency sends its
client an hour or so after a call. Warm, plain, human. HARD RULES:
- Never use em dashes or en dashes. No emojis. No corporate cliches.
- 350-550 characters total. Plain sentences and simple bullets using "-".
- Structure: one short opener that references the call naturally; then
  "Here's what we're on:" with up to 4 of OUR commitments in the client's
  words (no file names, no jargon); then, ONLY if the client owes things,
  "When you get a chance:" with up to 3 of THEIR items; then close with
  EXACTLY this sentence: "Let me know if there's anything else we may have missed!"
- Commitments must come from the provided summary. Never invent, never
  promise dates, never say a change is DONE.
Return ONLY JSON: {"sms": "..."}"""


def recap_contact(company: dict) -> dict | None:
    """Preferred contact card -> the dict send_message needs."""
    ints = company.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except (ValueError, TypeError):
            ints = {}
    cards = ints.get("contacts") or []
    card = next((c for c in cards if c.get("preferred")), cards[0] if cards else None)
    phone = (card or {}).get("cell") or (card or {}).get("phone") or company.get("phone")
    # The chosen card's OWN GHL contact id — ghl_contact_for returns the
    # first card's id, which routed Josiah's recap into Terry's thread
    # (HomeLyft 2026-09-04: phone from the preferred card, id from another).
    gid = (card or {}).get("ghl_contact_id") or ghl_contact_for(company)
    if not (gid and phone):
        return None
    return {"id": gid, "phone": phone, "email": (card or {}).get("email") or company.get("email")}


def send_meeting_recap(company: dict, slug: str, m: dict, *, title: str,
                       when: str, summary_md: str, dry_run: bool,
                       state: dict) -> None:
    """The recap SMS (Santino 2026-09-03): what we're on / what we need /
    "anything we missed?". Sent via the concierge pipe so every guard
    (allowlist, quiet window, holds, link gate) applies. A quiet-window
    block right after the call is EXPECTED and good - the 30-min Railway
    cycle retries until it lands, so the recap arrives about an hour after
    the meeting instead of during Santino's goodbye text."""
    rid = str(m.get("recording_id"))
    recaps = state.setdefault("recaps", {})
    if recaps.get(rid) == "sent":
        return
    # never recap stale meetings (backfills / --since re-mining)
    try:
        _w = datetime.fromisoformat(when.replace("Z", "+00:00"))
        if _w.tzinfo is None:
            _w = _w.replace(tzinfo=timezone.utc)
        age_h = (datetime.now(timezone.utc) - _w).total_seconds() / 3600
    except (ValueError, TypeError):
        age_h = 999
    if age_h > 30:
        recaps[rid] = "too-old"
        return
    contact = recap_contact(company)
    if not contact:
        recaps[rid] = "no-contact"
        print("    recap: no sendable contact — skipped")
        return
    try:
        out = anthropic_json(
            RECAP_SYSTEM,
            f"Client: {company.get('name')}\nMeeting: {title} on {when}\n\n"
            f"Action items:\n{action_items_text(m) or '(none)'}\n\n"
            f"Summary:\n{summary_md[:7000]}")
        sms = (out.get("sms") or "").strip()
        if not (200 <= len(sms) <= 700) or "\u2014" in sms or "—" in sms:
            recaps[rid] = "compose-rejected"
            print(f"    recap: compose rejected ({len(sms)} chars)")
            return
    except Exception as e:  # noqa: BLE001
        print(f"    recap compose failed ({str(e)[:80]}) — retry next cycle")
        return
    if dry_run:
        print(f"    [dry-run] recap SMS would send:\n      {sms[:300]}")
        return
    try:
        import client_concierge as cc
        cc.send_message(contact, "sms", sms, company=company)
        recaps[rid] = "sent"
        print(f"    recap SENT to {contact['phone']}")
    except Exception as e:  # noqa: BLE001 — quiet window/holds: retry next cycle
        print(f"    recap blocked ({str(e)[:110]}) — retrying next cycle")


# ---------------------------------------------------------------- auto-booking

LIVE_SUPPORT_CAL = "BhEoJmoyowCaOpALMn61"     # Restoration AI - LIVE Support Call
FOLLOWUP_CAL = "uZ7whcPD6NFDqcSu0hCf"         # Restoration AI - Follow Up Calendar
CONFLICT_SCAN_CALS = (LIVE_SUPPORT_CAL, FOLLOWUP_CAL,
                      "47qZ23NkTjsoyUhIKZPV",  # Santino personal
                      "DcoatVel3rEw01lKoGlA", "f6zNXUVXpPVdZtlknNNF")  # kickoffs
GHL_ASSIGNED_USER = os.environ.get("GHL_ASSIGNED_USER_ID", "xTuHtBz8G7Z4fyhAJ9kJ")

BOOKING_SYSTEM = """\
You read the END of a call transcript between a marketing agency (Santino)
and a client, deciding whether a SPECIFIC follow-up meeting time was
verbally CONFIRMED BY BOTH SIDES.

Rules:
- Book ONLY a concrete, mutually confirmed day+time. Relative references
  ("Friday of next week, same time", "tomorrow at 2") ARE concrete: resolve
  them against the provided call start datetime. "Sometime next week",
  "I'll send you times", or an unanswered proposal are NOT agreements.
- "Same time" means the same clock time as this call's start.
- A bare clock time ("1 PM") is in the CLIENT's timezone unless the words
  say otherwise.
- Tentative language followed by a firm pin-down and acknowledgment
  ("let's do Friday, same time" ... "Cool") IS confirmed.
Return ONLY JSON:
{"agreed": true|false,
 "start_iso": "YYYY-MM-DDTHH:MM:SS-07:00 or null",
 "quote": "the exact exchange you relied on (both speakers), or null",
 "confidence": "high"|"low"}
start_iso must carry the correct UTC offset for the timezone you resolved.
Never guess: if the day or time is ambiguous, agreed=false."""


def _ghl_api(method: str, path: str, body=None):
    r = requests.request(
        method, f"https://services.leadconnectorhq.com{path}", json=body,
        headers={"Authorization": f"Bearer {os.environ['GHL_API_KEY']}",
                 "Version": "2021-07-28"}, timeout=30)
    r.raise_for_status()
    return r.json() if r.content else {}


def fathom_transcript_tail(rid: str, chars: int = 9000,
                           api_key: str | None = None) -> str:
    r = requests.get(f"{FATHOM_API}/recordings/{rid}/transcript",
                     headers={"X-Api-Key": api_key
                              or os.environ["FATHOM_API_KEY"]},
                     timeout=60)
    r.raise_for_status()
    lines = []
    for seg in r.json().get("transcript") or []:
        who = ((seg.get("speaker") or {}).get("display_name") or "?")
        lines.append(f"{who}: {seg.get('text') or ''}")
    return "\n".join(lines)[-chars:]


def _overlap_is_same_client(events: list, contact: dict, company: dict) -> bool:
    """True when an overlapping calendar event belongs to THIS client —
    matched by contact id or by any client-name token pair in the title."""
    tokens = set()
    ints = company.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except (ValueError, TypeError):
            ints = {}
    for c in ints.get("contacts") or []:
        full = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
        if len(full) > 4:
            tokens.add(full.lower())
    for k in ("account_owner_name", "name"):
        v = str(company.get(k) or "").strip()
        if len(v) > 4:
            tokens.add(v.lower())
    for e in events:
        if e.get("contactId") == contact.get("id"):
            return True
        t = str(e.get("title") or "").lower()
        if any(tok in t for tok in tokens):
            return True
    return False


def book_agreed_followup(company: dict, slug: str, m: dict, *, title: str,
                         dry_run: bool, state: dict) -> None:
    """Verbal scheduling agreements become real appointments (Santino
    2026-09-04, Josiah + Scott cases). Concrete mutually-confirmed times
    only; timezone resolved against the call's own start; conflicts checked
    against the REAL calendars (round-robin availability lies); confirmed
    Rank AI clients land on the Live Support Call calendar, everyone else
    on the Follow Up calendar. Idempotent per recording."""
    rid = str(m.get("recording_id"))
    bookings = state.setdefault("bookings", {})
    if bookings.get(rid):
        return
    start_raw = m.get("recording_start_time") or m.get("created_at") or ""
    try:
        call_start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        if call_start.tzinfo is None:
            call_start = call_start.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        bookings[rid] = "no-start-time"
        return
    if (datetime.now(timezone.utc) - call_start).total_seconds() > 30 * 3600:
        bookings[rid] = "too-old"
        return
    contact = recap_contact(company)
    if not contact:
        bookings[rid] = "no-contact"
        return
    client_tz = "unknown"
    try:
        cd = _ghl_api("GET", f"/contacts/{contact['id']}")
        client_tz = ((cd.get("contact") or {}).get("timezone")
                     or (cd.get("contact") or {}).get("timeZone") or "unknown")
    except Exception:  # noqa: BLE001
        pass
    try:
        tail = fathom_transcript_tail(rid, api_key=m.get("_api_key"))
    except Exception as e:  # noqa: BLE001 — transcript lags recording; retry
        print(f"    booking: transcript not ready ({str(e)[:60]}) — next cycle")
        return
    if not tail.strip():
        bookings[rid] = "no-transcript"
        return
    pt = call_start.astimezone(timezone(timedelta(hours=-7)))
    try:
        out = anthropic_json(
            BOOKING_SYSTEM,
            f"Call start: {pt.strftime('%A %Y-%m-%d %H:%M')} Pacific Time "
            f"({call_start.isoformat()}).\n"
            f"Client: {company.get('name')} — client timezone: {client_tz}.\n\n"
            f"End of transcript:\n{tail}")
    except Exception as e:  # noqa: BLE001
        print(f"    booking: extract failed ({str(e)[:80]}) — next cycle")
        return
    if not (out.get("agreed") and out.get("start_iso")
            and out.get("confidence") == "high" and out.get("quote")):
        bookings[rid] = "no-agreement"
        print("    booking: no confirmed follow-up time on this call")
        return
    try:
        target = datetime.fromisoformat(str(out["start_iso"]))
        assert target.tzinfo is not None
    except (ValueError, AssertionError):
        bookings[rid] = "bad-iso"
        return
    now = datetime.now(timezone.utc)
    if not (now + timedelta(hours=1) <= target <= now + timedelta(days=45)):
        bookings[rid] = "window-rejected"
        print(f"    booking: {target.isoformat()} outside sane window — skipped")
        return
    if not (6 <= target.hour <= 21):
        bookings[rid] = "odd-hour"
        print(f"    booking: {target.isoformat()} is an odd hour — flagged, not booked")
        if dry_run:
            return
        sb_insert_note(company["id"],
                       f"[TODO-SANTINO] The {title} call agreed on a follow-up "
                       f"at {out['start_iso']} which looks like an odd hour. "
                       f"Quote: {str(out.get('quote'))[:200]}. Book by hand.")
        return
    # duplicate: an existing non-cancelled appointment within 90 min?
    try:
        evs = _ghl_api("GET", f"/contacts/{contact['id']}/appointments"
                       ).get("events") or []
        for e in evs:
            st = str(e.get("startTime") or "")
            if not st or e.get("appointmentStatus") == "cancelled":
                continue
            try:
                est = datetime.fromisoformat(st.replace(" ", "T"))
                if est.tzinfo is None:
                    est = est.replace(tzinfo=timezone(timedelta(hours=-7)))
            except ValueError:
                continue
            if abs((est - target).total_seconds()) <= 90 * 60:
                bookings[rid] = "already-booked"
                print(f"    booking: appointment already exists at {st} — done")
                return
    except Exception:  # noqa: BLE001
        pass
    # conflict: anything real on Santino's calendars overlapping the slot?
    s_ms = int((target - timedelta(minutes=15)).timestamp() * 1000)
    e_ms = int((target + timedelta(minutes=45)).timestamp() * 1000)
    loc = os.environ["GHL_LOCATION_ID"]
    for cal in CONFLICT_SCAN_CALS:
        try:
            evs = _ghl_api("GET", f"/calendars/events?locationId={loc}"
                           f"&calendarId={cal}&startTime={s_ms}&endTime={e_ms}"
                           ).get("events") or []
        except Exception:  # noqa: BLE001
            continue
        live = [e for e in evs if e.get("appointmentStatus") != "cancelled"]
        if not live:
            continue
        # An overlapping event for THIS client is a duplicate (someone —
        # possibly a human — already booked it), not a conflict. Clients can
        # have multiple GHL contacts (Josiah 2026-09-04: appointments on one,
        # concierge card on another), so match by contact OR by name.
        if _overlap_is_same_client(live, contact, company):
            bookings[rid] = "already-booked"
            print(f"    booking: '{live[0].get('title')}' already on the "
                  "calendar for this client — done")
            return
        bookings[rid] = "conflict"
        print(f"    booking: CONFLICT with '{live[0].get('title')}' — flagged")
        if not dry_run:
            sb_insert_note(company["id"],
                           f"[TODO-SANTINO] {company.get('name')} verbally agreed "
                           f"to a follow-up at {out['start_iso']} on the {title} "
                           f"call, but that slot conflicts with "
                           f"'{live[0].get('title')}'. Quote: "
                           f"{str(out.get('quote'))[:200]}. Rebook by hand.")
        return
    is_client = ((company.get("plan") or "").strip().lower() == "rank ai"
                 and str(company.get("status") or "").strip().lower()
                 not in ("inactive", "cancelled", "canceled", "suspended",
                         "paused"))
    cal_id = LIVE_SUPPORT_CAL if is_client else FOLLOWUP_CAL
    dur_min = 30 if is_client else 15
    ints = company.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except (ValueError, TypeError):
            ints = {}
    card = next((c for c in (ints.get("contacts") or []) if c.get("preferred")),
                None) or {}
    who = (f"{card.get('first_name', '')} {card.get('last_name', '')}".strip()
           or company.get("account_owner_name") or company.get("name"))
    appt_title = (f"{who} - LIVE Support Call" if is_client
                  else f"{who} - Follow Up Call")
    if dry_run:
        print(f"    [dry-run] would BOOK {appt_title} at {out['start_iso']} "
              f"on {'Live Support' if is_client else 'Follow Up'} calendar\n"
              f"      quote: {str(out.get('quote'))[:180]}")
        return
    try:
        res = _ghl_api("POST", "/calendars/events/appointments", {
            "calendarId": cal_id, "locationId": loc,
            "contactId": contact["id"],
            "startTime": out["start_iso"],
            "endTime": (target + timedelta(minutes=dur_min)).isoformat(),
            "title": appt_title, "assignedUserId": GHL_ASSIGNED_USER,
            "appointmentStatus": "confirmed",
            "ignoreFreeSlotValidation": True,
        })
        bookings[rid] = "booked"
        print(f"    booking: BOOKED {appt_title} at {out['start_iso']} "
              f"({res.get('id')})")
    except Exception as e:  # noqa: BLE001
        print(f"    booking failed ({str(e)[:110]}) — flagged for a human")
        sb_insert_note(company["id"],
                       f"[TODO-SANTINO] Could not auto-book the follow-up "
                       f"{company.get('name')} agreed to at {out['start_iso']} "
                       f"({title} call). Book by hand. Error: {str(e)[:120]}")
        bookings[rid] = "book-failed"


def write_heartbeat(run: dict, dry_run: bool) -> None:
    """The proof-of-life `watch` reads. Never fails the run."""
    if dry_run:
        return
    try:
        hb = kv_get(HEARTBEAT_KEY) or {}
        runs = [r for r in (hb.get("runs") or []) if isinstance(r, dict)]
        runs.append(run)
        kv_set(HEARTBEAT_KEY, {
            "last_run_at": run["at"],
            "last_ok_at": run["at"] if not run.get("error")
            else hb.get("last_ok_at"),
            "last_work_at": run["at"] if run.get("cards")
            else hb.get("last_work_at"),
            "runs": runs[-40:],
        })
    except Exception as e:  # noqa: BLE001 — a heartbeat must never break a run
        print(f"  [heartbeat] warn: not recorded ({str(e)[:100]})")


def cmd_sync(args) -> int:
    dry_run = not args.send
    state = load_state()
    first_run = state.get("initialized_at") is None
    meetings = fathom_meetings()
    companies = fetch_companies()
    roster_text, by_slug = roster(companies)

    if first_run:
        state["initialized_at"] = datetime.now(timezone.utc).isoformat()
        if not args.backfill:
            # baseline: mark everything current as seen; only future syncs
            for m in meetings:
                state["processed"][str(m.get("recording_id"))] = "baseline"
            print(f"first run: baselined {len(meetings)} existing meeting(s)"
                  " — only NEW recordings will be mined (use --backfill N to"
                  " mine recent ones now)")
            if not dry_run:
                kv_set("fathom-sync-state", state)
            return 0
        meetings = meetings[:args.backfill]

    # --since re-opens meetings we already processed. Used to backfill a
    # window after a change to how calls become work; --reprocess also retires
    # the cards the earlier pass filed for those calls so the board shows one
    # correct list, never two overlapping ones.
    def due(m: dict) -> bool:
        rid = str(m.get("recording_id"))
        if rid not in state["processed"]:
            return True
        return bool(args.since and meeting_when(m) >= args.since
                    and state["processed"][rid] not in ("unmatched", "baseline"))

    new = [m for m in meetings if due(m)]
    print(f"fathom sync: {len(new)} meeting(s) to process"
          + (f" (re-mining from {args.since})" if args.since else "")
          + (" [DRY RUN]" if dry_run else ""))
    run = {"at": datetime.now(timezone.utc).isoformat(), "meetings": 0,
           "matched": 0, "cards": 0, "clients": [], "error": None,
           "dry_run": dry_run}
    for m in reversed(new):  # oldest first
        rid = str(m.get("recording_id"))
        title = m.get("title") or m.get("meeting_title") or "?"
        summary_md = ((m.get("default_summary") or {})
                      .get("markdown_formatted") or "")
        when = meeting_when(m)
        print(f"\n--- {when} {title!r} (recording {rid})")
        run["meetings"] += 1
        if not summary_md:
            print("    no summary yet — leaving for next run")
            continue
        # ONE BAD MEETING MUST NOT COST THE WHOLE RUN (2026-08-05). The state
        # write used to sit after the loop, so a single model/API error threw
        # away every meeting mined before it and the next pass re-filed their
        # cards as duplicates. Each meeting now stands alone and commits its
        # own state the moment it succeeds.
        try:
            match = anthropic_json(
                MATCH_SYSTEM,
                f"Roster:\n{roster_text}\n\nMeeting title: {title}\n"
                f"Summary opening:\n{summary_md[:1200]}")
            slug = match.get("slug")
            if not slug or slug not in by_slug:
                print(f"    unmatched ({match.get('why', '?')[:90]}) — skipping forever")
                state["processed"][rid] = "unmatched"
                save_state(state, dry_run)
                continue
            company = by_slug[slug]
            print(f"    matched -> {slug} ({company.get('name')})")
            run["matched"] += 1

            distilled = anthropic_json(
                DISTILL_SYSTEM,
                f"Client: {company.get('name')} (slug {slug})\n"
                f"Meeting: {title} on {when}\nFathom URL: {m.get('url')}\n\n"
                f"Fathom action items:\n{action_items_text(m) or '(none)'}\n\n"
                f"Summary:\n{summary_md[:9000]}")
            intel = (distilled.get("intel") or "").strip()
            note = (distilled.get("ghl_note") or "").strip()
            if not intel:
                print("    distill produced nothing — skipping")
                state["processed"][rid] = "empty"
                save_state(state, dry_run)
                continue

            already_done = state["processed"].get(rid) not in (None, "unmatched",
                                                               "baseline")
            kv_key = f"meeting-intel/{slug}"
            block = f"\n\n{intel}\n_(source: Fathom {m.get('url')}, auto-synced)_\n"
            if already_done:
                print("    intel + GHL note already written on the first pass "
                      "— re-mining the work items only")
            elif dry_run:
                print(f"    [dry-run] would append to kv {kv_key}:\n{intel[:500]}")
                if note:
                    print(f"    [dry-run] would add GHL note: {note[:200]}")
            else:
                cur = kv_get(kv_key) or {}
                content = cur.get("content", "") if isinstance(cur, dict) else str(cur)
                kv_set(kv_key, {"content": (content + block).strip()})
                print(f"    intel appended -> ops_kv {kv_key}")
                cid = ghl_contact_for(company)
                if cid and note:
                    try:
                        add_ghl_note(cid, f"[Auto from Fathom] {title} ({when}): {note}")
                        print(f"    GHL note added on contact {cid}")
                    except RuntimeError as e:
                        print(f"    ! GHL note failed: {e}", file=sys.stderr)

            if already_done and args.reprocess:
                supersede_old_proposals(company["id"], title, when, dry_run)
            tally = route_meeting_work(company, slug, m, title=title, when=when,
                                       summary_md=summary_md, dry_run=dry_run)
            cards = tally["site_auto"] + tally["site_proposed"] + tally["ops"]
            run["cards"] += cards
            run["clients"].append({"slug": slug, "rid": rid, "when": when,
                                   "title": title, "cards": cards, **tally})
            print(f"    board: {tally['site_auto']} auto [DEV], "
                  f"{tally['site_proposed']} site proposals, "
                  f"{tally['ops']} ops proposals")
            if not already_done:
                send_meeting_recap(company, slug, m, title=title, when=when,
                                   summary_md=summary_md, dry_run=dry_run,
                                   state=state)
                book_agreed_followup(company, slug, m, title=title,
                                     dry_run=dry_run, state=state)
            state["processed"][rid] = slug
            save_state(state, dry_run)
        except Exception as e:  # noqa: BLE001 — one meeting, not the run
            run["error"] = f"{rid}: {str(e)[:200]}"
            print(f"    !! FAILED on this meeting ({str(e)[:160]}) — left "
                  "unprocessed for the next run", file=sys.stderr)

    write_heartbeat(run, dry_run)
    print(f"\nrun: {run['meetings']} meeting(s), {run['matched']} matched to "
          f"clients, {run['cards']} board card(s)"
          + (f", ERROR {run['error']}" if run["error"] else ""))
    return 1 if run["error"] and not run["cards"] else 0


def save_state(state: dict, dry_run: bool) -> None:
    if not dry_run:
        kv_set("fathom-sync-state", state)


def produced_work(company_id: str, m: dict, days: int = 7) -> bool:
    """Did this recording actually put anything on the board?

    Asked of the BOARD, not of the heartbeat: cards filed before the
    heartbeat existed (or by an earlier generation of this script) still
    count as work, and a watchdog that cried wolf over them would be
    switched off within a week. Recognises every generation's marker.
    """
    title = m.get("title") or m.get("meeting_title") or "?"
    when = meeting_when(m)
    start = str(m.get("recording_start_time") or m.get("created_at") or "")[:19]
    try:
        from feedback_router import ORIGIN_MARK, _recent_notes
        rows = _recent_notes(company_id, days=days)
    except Exception as e:  # noqa: BLE001 — unknown state is not an alarm
        print(f"  [watch] note lookup failed for {company_id}: {str(e)[:90]}")
        return True
    marks = (f"(from call: {title}", f"{MEETING_MARK}", ORIGIN_MARK)
    for r in rows:
        # Filed after the call started, carrying a call-to-work marker, and
        # naming this call's date: that is this meeting's output.
        if str(r.get("created_at") or "")[:19] < start:
            continue
        body = str(r.get("body") or "")
        if any(mk in body for mk in marks) and when in body:
            return True
    return False


# ------------------------------------------------------------------ the alarm
# WHY THIS EXISTS (Santino 2026-08-05). "Meetings aren't becoming tasks" was
# reported three weeks after the last file landed in clients/_ops/meeting-intel
# — a directory this job stopped writing on 2026-07-12 when state moved to
# Supabase. The job was in fact alive, but NOTHING WOULD HAVE SAID SO EITHER
# WAY. A pipeline whose only failure signal is a human noticing an absence is
# not monitored. This is the signal: silence becomes a card.
def cmd_watch(args) -> int:
    dry_run = not args.send
    hb = kv_get(HEARTBEAT_KEY) or {}
    state = load_state()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=args.days)).strftime("%Y-%m-%d")
    alarms: list[tuple[str, str, dict | None]] = []   # (kind, reason, company)

    # 1. Is the job running at all?
    last_ok = hb.get("last_ok_at") or hb.get("last_run_at")
    age_h = None
    if last_ok:
        try:
            age_h = (now - datetime.fromisoformat(
                str(last_ok).replace("Z", "+00:00"))).total_seconds() / 3600
        except ValueError:
            age_h = None
    if last_ok is None:
        alarms.append(("dead", "the Fathom sync has never recorded a "
                       "completed run (no heartbeat in ops_kv) — the "
                       "meeting-to-task pipeline may not be running at all",
                       None))
    elif age_h is not None and age_h > args.max_age_hours:
        alarms.append(("dead", f"the Fathom sync has not completed a run in "
                       f"{age_h:.1f}h (expected every 30 min on the Railway "
                       f"ops-worker) — last clean run {str(last_ok)[:16]}",
                       None))
    for r in (hb.get("runs") or [])[-3:]:
        if r.get("error"):
            alarms.append(("error", "the Fathom sync errored on a meeting and "
                           f"left it unprocessed: {str(r['error'])[:160]}",
                           None))
            break

    # 2. Did recent client meetings actually produce work?
    companies = fetch_companies()
    _roster_text, by_slug = roster(companies)
    try:
        meetings = fathom_meetings(limit=25)
    except Exception as e:  # noqa: BLE001
        print(f"fathom API unreachable: {str(e)[:140]}")
        meetings = []
        alarms.append(("dead", f"the Fathom API is not answering "
                       f"({str(e)[:120]}) — no meeting can become a task "
                       "while this is true", None))
    silent: list[tuple[str, dict]] = []
    for m in meetings:
        rid, when = str(m.get("recording_id")), meeting_when(m)
        if when < cutoff:
            continue
        slug = state["processed"].get(rid)
        if slug in (None, "unmatched", "baseline", "empty"):
            continue
        company = by_slug.get(slug)
        if not company or produced_work(company["id"], m, days=args.days + 2):
            continue
        silent.append((m.get("title") or "?", {"company": company, "rid": rid,
                                               "when": when, "slug": slug}))
    for title, meta in silent:
        alarms.append(("silent", f"we met {meta['company'].get('name')} on "
                       f"{meta['when']} ({title}) and the call produced NO "
                       "work on the board — either nothing was asked for, or "
                       "the extraction is failing silently. Re-mine it: "
                       f"python3 scripts/fathom_sync.py sync --send --since "
                       f"{meta['when']} --reprocess", meta["company"]))

    if not alarms:
        print(f"fathom watch: green — last clean run "
              f"{str(last_ok)[:16] if last_ok else '?'}"
              + (f" ({age_h:.1f}h ago)" if age_h is not None else "")
              + f", {len([1 for r in (hb.get('runs') or []) if r.get('cards')])}"
                " of the last runs produced cards")
        return 0

    # One card per kind per UTC day: a stall lasts days and must not stack a
    # new card every pass (the concierge digest would drown).
    ws = kv_get(WATCH_KEY) or {}
    today = now.strftime("%Y-%m-%d")
    fired = 0
    for kind, reason, company in alarms:
        key = f"{kind}:{company.get('id') if company else 'fleet'}"
        if ws.get(key) == today:
            print(f"fathom watch: {kind} already reported today — {reason[:80]}")
            continue
        print(f"fathom watch: {kind.upper()} — {reason}")
        if dry_run:
            print("  [dry-run] would file the card")
            continue
        target = company or _fleet_company(by_slug)
        if not target:
            print("  ! no company to file against — card skipped")
            continue
        try:
            sb_insert_note(target["id"],
                           f"[TODO-SANTINO] MEETING-TO-TASK PIPELINE: {reason}")
            from client_concierge import append_escalation
            append_escalation(target, None, f"Fathom sync: {reason[:300]}",
                              dry_run=False, ping=(kind == "dead"))
            ws[key] = today
            fired += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ! could not file the card: {str(e)[:120]}")
    if fired and not dry_run:
        kv_set(WATCH_KEY, ws)
    return 0


def _fleet_company(by_slug: dict) -> dict | None:
    """Where a fleet-level alarm gets filed: there is no agency row in
    marketing_companies, so the card lands on the most recently touched
    client rather than nowhere at all."""
    for slug in ("restorationxpress", "narestco"):
        if slug in by_slug:
            return by_slug[slug]
    return next(iter(by_slug.values()), None)


def cmd_status(_args) -> int:
    hb = kv_get(HEARTBEAT_KEY) or {}
    state = load_state()
    print(f"heartbeat: last run {str(hb.get('last_run_at'))[:19]}  "
          f"last clean {str(hb.get('last_ok_at'))[:19]}  "
          f"last work {str(hb.get('last_work_at'))[:19]}")
    print(f"processed recordings: {len(state.get('processed') or {})} "
          f"(since {str(state.get('initialized_at'))[:10]})")
    print("\nrecent runs (newest last):")
    for r in (hb.get("runs") or [])[-12:]:
        cl = ", ".join(f"{c['slug']}:{c['cards']}" for c in (r.get("clients") or []))
        print(f"  {str(r.get('at'))[:19]}  meetings={r.get('meetings')} "
              f"matched={r.get('matched')} cards={r.get('cards')}"
              + (f"  [{cl}]" if cl else "")
              + (f"  ERROR {str(r.get('error'))[:80]}" if r.get("error") else "")
              + ("  (dry run)" if r.get("dry_run") else ""))
    intel = {}
    try:
        from client_concierge import kv_prefix
        intel = kv_prefix("meeting-intel/")
    except Exception as e:  # noqa: BLE001
        print(f"  (intel lookup failed: {str(e)[:80]})")
    print(f"\nmeeting intel in ops_kv: {len(intel)} client file(s) "
          "— clients/_ops/meeting-intel/*.md is the pre-2026-07-12 archive "
          "and is expected to be frozen")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("sync")
    ps.add_argument("--send", action="store_true",
                    help="write intel + GHL notes + board work + state "
                         "(default: dry run)")
    ps.add_argument("--backfill", type=int, default=0,
                    help="on first run, also mine the N most recent meetings")
    ps.add_argument("--since", default="",
                    help="re-mine meetings recorded on/after YYYY-MM-DD even "
                         "if already processed")
    ps.add_argument("--reprocess", action="store_true",
                    help="with --since: retire the cards the earlier pass "
                         "filed for those calls before filing the new ones")
    pw = sub.add_parser("watch")
    pw.add_argument("--send", action="store_true",
                    help="file the cards (default: dry run)")
    pw.add_argument("--days", type=int, default=3,
                    help="how far back a silent meeting still counts")
    pw.add_argument("--max-age-hours", type=float, default=6.0,
                    help="how long without a clean run counts as stalled")
    sub.add_parser("status")
    args = ap.parse_args()
    load_env()
    for k in ("FATHOM_API_KEY", "ANTHROPIC_API_KEY", "SUPABASE_URL"):
        if not os.environ.get(k):
            print(f"ERROR: missing env {k}", file=sys.stderr)
            return 1
    return {"sync": cmd_sync, "watch": cmd_watch,
            "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
