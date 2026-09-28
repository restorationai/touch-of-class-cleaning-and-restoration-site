#!/usr/bin/env python3
"""monica_oneoff.py — the ONLY way Claude sends a one-off client text.

Santino 2026-09-27 (Rachelle, Desert Valley): a question texted outside
Monica's pipeline went out via the raw GHL key, which stamps Santino's
userId. Monica then read it as a HUMAN mid-conversation: her instant reply
to Rachelle's answer was held by the 60-min quiet window and the follow-up
by the 12h human-defer, and she had no idea what the question was about.

This wrapper fixes both halves:
  1. CONTEXT — right after a successful send, files a [CONTEXT] ops note on the company (rides into
     every compose, never read as an order to text) so Monica can answer
     the client's reply herself.
  2. SENT AS MONICA — delivers through cc.send_message (canary allowlist,
     link gate, machine-sent ledger) and records the id, so the human gates
     never mistake it for Santino.

Usage (dry run by default):
  python3 scripts/monica_oneoff.py --company CO-... --body "..." \
      --context "what we asked, why, and how to answer likely replies" \
      [--contact-id <ghl id>] [--channel sms|email] [--send]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import client_concierge as cc  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--context", required=True,
                    help="facts + how Monica should handle replies")
    ap.add_argument("--contact-id", help="GHL contact (default: company's)")
    ap.add_argument("--channel", default="sms", choices=("sms", "email"))
    ap.add_argument("--subject")
    ap.add_argument("--reply-to-email", metavar="GHL_MSG_ID",
                    help="GHL id of the client's email to answer IN its thread")
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()
    cc.load_env()

    if "—" in a.body or "–" in a.body:
        sys.exit("refusing: em/en dash in client copy")
    comp = cc.fetch_companies([a.company]).get(a.company)
    if not comp:
        sys.exit(f"unknown company {a.company}")
    contact = ({"id": a.contact_id, **(cc._ghl("GET", f"/contacts/{a.contact_id}")
                                       or {}).get("contact", {})}
               if a.contact_id else cc.resolve_contact(comp))
    if not contact:
        sys.exit("no contact resolved")
    who = contact.get("firstName") or contact.get("name") or contact["id"]
    note = f"[CONTEXT] One-off sent to {who}: \"{a.body}\" | {a.context}"
    print(f"to: {who} ({contact.get('phone') or contact.get('email')})\n"
          f"body: {a.body}\nnote: {note}")
    if not a.send:
        print("[dry run] nothing filed, nothing sent")
        return 0
    # Send FIRST: a blocked send (allowlist, send lock) must not leave a
    # context note behind, or a retry files a duplicate (DryCor 09-27).
    # Monica's reply path debounces 100s, so the note still lands first.
    r = cc.send_message(contact, a.channel, a.body, subject=a.subject,
                        company=comp, human_hold_exempt=True,
                        email_msg_id=a.reply_to_email)
    state = cc.load_state()
    cc.record_sent_message(state, r)
    cc.save_state(state, dry_run=False)
    cc._sb("POST", "/rest/v1/marketing_ops_notes",
           {"company_id": a.company, "author": "claude-macbook",
            "status": "open", "body": note[:1900]}, prefer="return=minimal")
    print("sent + context filed:", r.get("messageId") or r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
