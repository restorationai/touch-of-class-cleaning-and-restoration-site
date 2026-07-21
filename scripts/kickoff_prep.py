#!/usr/bin/env python3
"""Kickoff-prep: after a sales demo closes and a kickoff call gets booked,
read the Fathom transcript of that demo, extract what Santino told the
client to have ready, and send ONE friendly SMS + email via GHL/SendGrid.

Fired by a GHL webhook (POST /kickoff-prep on the Railway API) the moment
the kickoff appointment is booked. The booking happens MID-CALL, so the
recording/transcript lands on Fathom 15-60 minutes later — the endpoint
spawns a thread that polls Fathom until the meeting appears, then composes
and sends. Single send, deduped with the 'kickoff-prep-sent' contact tag.

Tone rules (Santino, 2026-07-20): warm and light, never framed as required,
always includes a no-stress line so nobody feels they must reschedule, no
em dashes anywhere, one text + one email, exactly once.

Manual run:  python3 scripts/kickoff_prep.py --contact <ghl_contact_id>
Env: FATHOM_API_KEY, ANTHROPIC_API_KEY, GHL_* (via lead_audit), SENDGRID_API_KEY.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import lead_audit as la  # noqa: E402  _ghl, _claude, claude_json, send_email

FATHOM_API = "https://api.fathom.ai/external/v1"
DONE_TAG = "kickoff-prep-sent"

COMPOSE_SYSTEM = """\
You write a kickoff-call prep reminder for Restoration AI. You get the
transcript of a sales call Santino (the host) just had with a new client,
the client's first name, and when their kickoff call is scheduled.

STEP 1 — extract: list ONLY the things Santino explicitly asked the client
to provide, prepare, or have ready for the kickoff (e.g. a customer list,
zip codes, photos, documents). Ignore things Santino will do himself and
things that will be done together ON the call. If Santino asked for nothing,
return found_asks=false.

STEP 1b — scheduling: you receive NEXT CALL. If it says BOOKED, reference
that time naturally. If it says NOT BOOKED, scan the transcript for an
explicitly agreed next-call date AND time. Only if both are unambiguous,
set agreed_datetime_iso (ISO 8601 with utc offset, the CLIENT's timezone)
and reference that time in the messages. Otherwise set agreed_datetime_iso
to null and END both messages by asking them to reply with what day works,
referencing whatever was loosely floated on the call, e.g. "Once you've had
a chance to check your schedule, let me know what day next week works and
I'll lock in our call."

STEP 2 — write one SMS and one matching email, first person from Santino:
- Warm, casual, sounds like a person texting. 6th-8th grade reading level.
- You receive MEETING DATE and TODAY. Refer to the meeting correctly:
  "today" only if they match, "yesterday" if the meeting was the day before,
  otherwise "the other day". Never say "today" for a past-day meeting.
- NEVER frame anything as required. Always include one line making clear
  that if a piece or two is not ready, it is no stress and the call still
  happens and will still be productive. Never suggest rescheduling.
- Reference the kickoff time naturally, the way it was agreed on the call.
- NEVER use an em dash or a spaced en dash. Use commas or periods.
- NEVER say "just reply here" or any variant of it. End like a person would
  ("Talk soon", "See you then"). The email MAY invite replying with files.
- When naming the client's company or brand, use EXACTLY the CRM spelling
  provided (transcripts mishear brand names, e.g. "PureClean" for PuroClean).
- SMS: plain text, max 550 characters, no links.
- Email: email_subject short and plain; email_html is a simple inline-styled
  <div> (font-family Arial, font-size 15px, color #1f2937, max-width 560px)
  that mirrors the SMS with a short <ul> for the items, invites them to
  reply to the email with any files or lists, signed "Santino" then
  "Restoration AI" on the next line.

Return ONLY JSON:
{"found_asks": bool, "items": [str], "sms": str,
 "email_subject": str, "email_html": str, "agreed_datetime_iso": str|null}"""

COMPOSE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "found_asks": {"type": "boolean"},
        "items": {"type": "array", "items": {"type": "string"}},
        "sms": {"type": "string"},
        "email_subject": {"type": "string"},
        "email_html": {"type": "string"},
        "agreed_datetime_iso": {"type": ["string", "null"]},
    },
    "required": ["found_asks", "items", "sms", "email_subject", "email_html",
                 "agreed_datetime_iso"],
}


def _log(msg):
    print("  [kickoff-prep {}] {}".format(
        dt.datetime.now().strftime("%H:%M:%S"), msg))


def _fathom_meetings(created_after_iso, include_transcript=True):
    q = urllib.parse.urlencode({
        "created_after": created_after_iso,
        "include_transcript": "true" if include_transcript else "false",
        "limit": 20})
    req = urllib.request.Request(
        FATHOM_API + "/meetings?" + q,
        headers={"X-Api-Key": os.environ["FATHOM_API_KEY"]})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("items", [])


def _matches(meeting, email, name, company=""):
    """The client is usually NOT a calendar invitee on these GHL-booked Zoom
    calls (Fathom only lists Santino) — but they ARE a transcript speaker.
    Match on invitee email, then speaker display names, then the title.
    Zoom display names are often first-name-only ("Gregory") or junk
    ("iPhone"), so a first-name speaker match is accepted when the transcript
    corroborates it: last name, a company word, or their email domain."""
    email = (email or "").lower()
    tokens = [t for t in (name or "").lower().split() if len(t) > 2]
    for inv in (meeting.get("calendar_invitees") or []):
        if isinstance(inv, str):
            inv = {"email": inv}
        if email and (inv.get("email") or "").lower() == email:
            return True
        iname = (inv.get("name") or "").lower()
        if tokens and all(t in iname for t in tokens):
            return True
    speakers = set()
    for seg in (meeting.get("transcript") or []):
        sp = seg.get("speaker")
        nm = (sp.get("display_name") if isinstance(sp, dict) else sp) or ""
        if nm:
            speakers.add(nm.lower().strip())
    if tokens and any(all(t in s for t in tokens) for s in speakers):
        return True
    first = tokens[0] if tokens else ""
    if len(first) >= 4 and any(s == first or s.startswith(first + " ")
                               for s in speakers):
        text = _transcript_text(meeting).lower()
        corro = set(tokens[1:])
        corro |= {w for w in re.split(r"[^a-z0-9]+", (company or "").lower())
                  if len(w) >= 5}
        dom = email.split("@")[-1].split(".")[0] if "@" in email else ""
        if len(dom) >= 5 and dom not in ("gmail", "yahoo", "outlook",
                                         "hotmail", "icloud"):
            corro.add(dom)
        if any(c in text for c in corro):
            return True
    title = (meeting.get("title") or "").lower()
    return bool(tokens) and all(t in title for t in tokens)


def _transcript_text(meeting):
    parts = []
    for seg in (meeting.get("transcript") or []):
        sp = seg.get("speaker")
        sp = (sp.get("display_name") if isinstance(sp, dict) else sp) or "?"
        parts.append("{}: {}".format(sp, seg.get("text") or ""))
    return "\n".join(parts)[:80000]


def find_demo(email, name, company="", lookback_hours=12):
    since = (dt.datetime.now(dt.timezone.utc)
             - dt.timedelta(hours=lookback_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for m in _fathom_meetings(since):
        if _matches(m, email, name, company):
            text = _transcript_text(m)
            if len(text) > 500:      # transcript actually landed
                return m, text
    return None, ""


def _book_kickoff(contact_id, start_iso, name):
    """Create the kickoff appointment when the call explicitly agreed a time.
    Best-effort: booking failure never blocks the messages."""
    try:
        cal = os.environ.get("KICKOFF_CALENDAR_ID", "DcoatVel3rEw01lKoGlA")
        r = la._ghl("POST", "/calendars/events/appointments", params={}, body={
            "calendarId": cal,
            "locationId": os.environ.get("GHL_LOCATION_ID"),
            "contactId": contact_id,
            "startTime": start_iso,
            "title": "{} - Kick Off Call".format(name or "Client"),
            "appointmentStatus": "confirmed",
            "ignoreFreeSlotValidation": True,
        })
        return r.get("id") or (r.get("event") or {}).get("id") or "created"
    except Exception as e:
        _log("auto-book failed: {}".format(str(e)[:200]))
        return None


def run(contact_id, appt_time="", poll_minutes=10, max_attempts=30, dry_run=False,
        lookback_hours=12):
    """Poll Fathom for the demo with this contact, then send SMS + email once."""
    contact = la._ghl("GET", "/contacts/{}".format(contact_id)).get("contact") or {}
    tags = [t.lower() for t in (contact.get("tags") or [])]
    if DONE_TAG in tags:
        _log("contact {} already has {} — skipping".format(contact_id, DONE_TAG))
        return {"skipped": "already sent"}
    email = contact.get("email") or ""
    phone = contact.get("phone") or ""
    # Duplicate-contact guard: people sometimes sign up under a different
    # email than their existing GHL contact, creating two records for one
    # human. If ANY contact sharing this phone already got the reminder,
    # stand down — one text per person, not per contact row.
    if phone:
        try:
            res = la._ghl("GET", "/contacts/", params={"query": phone})
            for c2 in (res.get("contacts") or []):
                if c2.get("id") != contact_id and DONE_TAG in [
                        (t or "").lower() for t in (c2.get("tags") or [])]:
                    _log("duplicate contact {} already received kickoff-prep — skipping".format(c2.get("id")))
                    return {"skipped": "duplicate contact already sent"}
        except Exception:
            pass
    first = contact.get("firstName") or "there"
    name = "{} {}".format(contact.get("firstName") or "",
                          contact.get("lastName") or "").strip()
    _log("contact: {} <{}> {}".format(name, email, phone))

    company = contact.get("companyName") or ""
    meeting, text = None, ""
    for attempt in range(max_attempts):
        meeting, text = find_demo(email, name, company, lookback_hours)
        if meeting:
            break
        if attempt + 1 >= max_attempts:
            break
        _log("no transcript yet (attempt {}/{}) — sleeping {} min".format(
            attempt + 1, max_attempts, poll_minutes))
        time.sleep(poll_minutes * 60)
    if not meeting:
        _log("gave up: no Fathom meeting found for {}".format(name))
        la.send_email(la.NOTIFY_EMAIL, "[kickoff-prep] no demo found for " + name,
                      "<p>No Fathom meeting matched {} &lt;{}&gt; within {} attempts. "
                      "No message was sent.</p>".format(name, email, max_attempts))
        return {"error": "no meeting found"}
    _log("demo: {} ({})".format(meeting.get("title"), meeting.get("url")))

    meeting_date = (meeting.get("recording_start_time")
                    or meeting.get("created_at") or "")[:10]
    next_call = ("BOOKED: " + appt_time) if appt_time else (
        "NOT BOOKED: no appointment exists yet, follow the scheduling rules")
    user = ("CLIENT FIRST NAME: {}\nCLIENT COMPANY (CRM spelling): {}\n"
            "NEXT CALL: {}\nMEETING DATE: {}\nTODAY: {}\n\n"
            "SALES CALL TRANSCRIPT:\n{}").format(
        first, company or "unknown", next_call, meeting_date or "unknown",
        dt.date.today().isoformat(), text)
    copy, _ = la.claude_json(la._claude(), COMPOSE_SYSTEM, user,
                             max_tokens=2000, schema=COMPOSE_SCHEMA)
    if not copy.get("found_asks"):
        _log("no explicit asks in transcript — not sending")
        la.send_email(la.NOTIFY_EMAIL, "[kickoff-prep] no asks found for " + name,
                      "<p>Transcript reviewed ({}) but Santino asked for nothing "
                      "explicit, so no reminder was sent.</p>".format(
                          meeting.get("title")))
        return {"skipped": "no asks found"}
    _log("asks: {}".format(copy.get("items")))

    if dry_run:
        print(json.dumps(copy, indent=1))
        return {"dry_run": True, "copy": copy}

    booked = None
    if not appt_time and copy.get("agreed_datetime_iso"):
        booked = _book_kickoff(contact_id, copy["agreed_datetime_iso"], name)
        _log("auto-booked kickoff: {}".format(booked))

    sms_ok = email_ok = False
    try:
        r = la._ghl("POST", "/conversations/messages", params={}, body={
            "type": "SMS", "contactId": contact_id, "message": copy["sms"]})
        sms_ok = bool(r.get("messageId"))
    except Exception as e:
        _log("sms failed: {}".format(str(e)[:150]))
    if email:
        email_ok = la.send_email(email, copy["email_subject"], copy["email_html"])

    # dedupe tag (merge with existing)
    try:
        la._ghl("PUT", "/contacts/{}".format(contact_id), params={},
                body={"tags": (contact.get("tags") or []) + [DONE_TAG]})
    except Exception as e:
        _log("tagging failed: {}".format(str(e)[:150]))

    la.send_email(la.NOTIFY_EMAIL,
                  "[kickoff-prep] sent to {} (sms={} email={})".format(
                      name, sms_ok, email_ok),
                  "<p><b>Items:</b> {}</p><p><b>SMS:</b> {}</p>"
                  "<p><b>Auto-booked:</b> {}</p><p>Demo: {}</p>".format(
                      ", ".join(copy.get("items") or []), copy["sms"],
                      booked or "no (no explicit time agreed)",
                      meeting.get("url")))
    _log("done: sms={} email={}".format(sms_ok, email_ok))
    return {"sent": True, "sms": sms_ok, "email": email_ok,
            "items": copy.get("items")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--contact", required=True, help="GHL contact id")
    ap.add_argument("--appt-time", default="", help="e.g. 'tomorrow at 5'")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-wait", action="store_true",
                    help="single Fathom check, no polling")
    ap.add_argument("--lookback-hours", type=int, default=12,
                    help="how far back to search Fathom (manual reruns)")
    args = ap.parse_args()
    res = run(args.contact, appt_time=args.appt_time,
              max_attempts=1 if args.no_wait else 30, dry_run=args.dry_run,
              lookback_hours=args.lookback_hours)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
