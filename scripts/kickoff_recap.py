#!/usr/bin/env python3
"""kickoff_recap.py — after a KICKOFF call completes, send ONE friendly recap.

Trigger: GHL workflow webhook when the kickoff-calendar appointment is marked
completed -> POST /kickoff-recap on the Railway API -> this script polls
Fathom for the recording, reads the transcript, and sends one SMS + email
recapping what was agreed and what happens next.

THE NO-SHOW RULE (Santino 2026-07-25): GHL sometimes auto-completes
appointments that never happened. If polling finds NO Fathom recording with
this contact, we do NOTHING — no message, just a quiet ops note. Silence is
the correct behavior for a phantom completion.

Voice: Monica (Santino's team at Restoration AI). No em dashes, no jargon,
warm and brief. Dedupe tag: kickoff-recap-sent.

Usage: python3 scripts/kickoff_recap.py --contact-id X [--lookback-hours 6]
       [--poll-minutes 10] [--max-attempts 12] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import lead_audit as la  # noqa: E402  _ghl, _claude, claude_json, send_email
from kickoff_prep import (  # noqa: E402
    _fathom_meetings, _log, _matches, _transcript_text)

DONE_TAG = "kickoff-recap-sent"

RECAP_SYSTEM = """\
You are Monica with Santino's team at Restoration AI, writing ONE short recap
message after a client's kickoff call with our team. You have the call
transcript. Never use em dashes or en dashes; use commas or periods.

Extract from the transcript:
- what WE committed to do next (site build, Google setup, campaigns, etc.)
- anything THEY agreed to send or do (keep it light, max 2 items)
- any concrete dates mentioned

Write:
- "sms": <= 450 chars. Open with their first name ("Hey {first}," style).
  Warm one-line thanks for the call, then 1-2 sentences on what we are doing
  now, then (only if the transcript shows they owe something) one gentle
  reminder with a "no stress" tone. Close naturally, no "just reply here".
- "email_subject": <= 60 chars, plain ("Quick recap of today's call").
- "email_html": short HTML email, same content slightly expanded (a short
  bulleted list of next steps is good). Sign off "Monica, Santino's team at
  Restoration AI".

HARD RULES: only claim commitments that are actually in the transcript.
Never invent dates or promises. No pricing. If the transcript shows the call
was a no-show or only voicemail/small talk, set "real_call" to false.

Return ONLY JSON:
{"real_call": bool, "we_do": [".."], "they_do": [".."],
 "sms": "..", "email_subject": "..", "email_html": ".."}"""

RECAP_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "real_call": {"type": "boolean"},
        "we_do": {"type": "array", "items": {"type": "string"}},
        "they_do": {"type": "array", "items": {"type": "string"}},
        "sms": {"type": "string"},
        "email_subject": {"type": "string"},
        "email_html": {"type": "string"},
    },
    "required": ["real_call", "we_do", "they_do", "sms",
                 "email_subject", "email_html"],
}


def find_kickoff(email, name, company="", lookback_hours=6):
    """Newest Fathom meeting matching this contact within the lookback."""
    import datetime as dt
    after = (dt.datetime.now(dt.timezone.utc)
             - dt.timedelta(hours=lookback_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for meeting in _fathom_meetings(after):
        if _matches(meeting, email, name, company):
            text = _transcript_text(meeting)
            if text and len(text) > 400:   # a real conversation, not a stub
                return meeting, text
    return None, None


def run(contact_id, poll_minutes=10, max_attempts=12, lookback_hours=6,
        dry_run=False):
    contact = la._ghl("GET", "/contacts/{}".format(contact_id)).get("contact") or {}
    tags = [t.lower() for t in (contact.get("tags") or [])]
    if DONE_TAG in tags:
        _log("already sent (tag) — skipping")
        return {"skipped": "already sent"}
    email = contact.get("email") or ""
    name = "{} {}".format(contact.get("firstName") or "",
                          contact.get("lastName") or "").strip()
    company = contact.get("companyName") or ""
    _log("contact: {} <{}>".format(name, email))

    meeting = text = None
    for attempt in range(1, max_attempts + 1):
        meeting, text = find_kickoff(email, name, company, lookback_hours)
        if meeting:
            break
        _log("no recording yet (attempt {}/{})".format(attempt, max_attempts))
        if attempt < max_attempts:
            time.sleep(poll_minutes * 60)

    if not meeting:
        # THE NO-SHOW RULE: auto-completed appointment with no recording ->
        # do nothing client-facing. Quiet ops note only.
        _log("no Fathom recording found — treating as phantom completion, "
             "no message sent")
        la.send_email(la.NOTIFY_EMAIL,
                      "[kickoff-recap] no recording for " + (name or contact_id),
                      "<p>Kickoff was marked completed but no Fathom recording "
                      "matched {} within {}h. No recap was sent (per the "
                      "no-show rule).</p>".format(name, lookback_hours))
        return {"skipped": "no recording — phantom completion"}

    _log("matched: {}".format(meeting.get("title")))
    user = ("CONTACT: {} <{}> company {}\n\nTRANSCRIPT:\n{}".format(
        name, email, company, text[:60000]))
    copy, _ = la.claude_json(la._claude(), RECAP_SYSTEM, user,
                             max_tokens=2000, schema=RECAP_SCHEMA)
    if not copy.get("real_call"):
        _log("transcript says not a real call — nothing to recap")
        return {"skipped": "not a real call"}

    if dry_run:
        print(json.dumps(copy, indent=1))
        return {"dry_run": True, "copy": copy}

    sms_ok = email_ok = False
    try:
        r = la._ghl("POST", "/conversations/messages", params={}, body={
            "type": "SMS", "contactId": contact_id, "message": copy["sms"]})
        sms_ok = bool(r.get("messageId"))
    except Exception as e:
        _log("sms failed: {}".format(str(e)[:150]))
    if email:
        email_ok = la.send_email(email, copy["email_subject"], copy["email_html"])

    try:
        la._ghl("PUT", "/contacts/{}".format(contact_id), params={},
                body={"tags": (contact.get("tags") or []) + [DONE_TAG]})
    except Exception as e:
        _log("tagging failed: {}".format(str(e)[:150]))

    la.send_email(la.NOTIFY_EMAIL,
                  "[kickoff-recap] sent to {} (sms={} email={})".format(
                      name, sms_ok, email_ok),
                  "<p><b>We do:</b> {}</p><p><b>They do:</b> {}</p>"
                  "<p><b>SMS:</b> {}</p><p>Call: {}</p>".format(
                      ", ".join(copy["we_do"]), ", ".join(copy["they_do"]) or "nothing",
                      copy["sms"], meeting.get("url")))
    _log("done: sms={} email={}".format(sms_ok, email_ok))
    return {"sent": True, "sms": sms_ok, "email": email_ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--contact-id", required=True)
    ap.add_argument("--poll-minutes", type=int, default=10)
    ap.add_argument("--max-attempts", type=int, default=12)
    ap.add_argument("--lookback-hours", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    out = run(args.contact_id, args.poll_minutes, args.max_attempts,
              args.lookback_hours, args.dry_run)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
