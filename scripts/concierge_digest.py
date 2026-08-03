#!/usr/bin/env python3
"""Morning push for Santino (2026-07-30: "regarding number four, add a push").

Emails a compact digest of the last 24h of concierge activity — new
escalations (things ONLY a human can do) plus send/blocked counts — to
contact@restorationai.io via SendGrid. Sends NOTHING when there is nothing
to say: a quiet morning means no email.

Runs from the client-concierge workflow's morning pass.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb  # noqa: E402

TO = "contact@restorationai.io"
FROM = "contact@restorationai.io"


def main() -> int:
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    esc = _sb("GET", "/rest/v1/concierge_escalations"
              f"?created_at=gte.{since}&select=company_name,reason,created_at"
              "&order=created_at.desc") or []
    notes = _sb("GET", "/rest/v1/marketing_ops_notes"
                f"?created_at=gte.{since}&status=eq.open"
                "&select=company_id,body&order=created_at.desc") or []
    # Only auto-generated notes are digest-worthy; skip Santino's own.
    sys_notes = [n for n in notes if (n.get("body") or "").startswith("[")]

    if not esc and not sys_notes:
        print("digest: nothing new in 24h — no email sent")
        return 0

    # ONCE PER UTC DAY (2026-08-03): the Railway ops-worker now dispatches
    # BOTH daily concierge slots with mode=daily, which satisfies the
    # workflow's digest condition on the 19:37 run too — without this guard
    # Santino would get the same digest twice a day.
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        rows = _sb("GET", "/rest/v1/ops_kv?k=eq.concierge-digest-sent&select=v",
                   prefer="return=representation") or []
        if rows and rows[0].get("v") == today:
            print("digest: already sent today — skipping")
            return 0
    except Exception as e:  # noqa: BLE001 — the guard must never eat the digest
        print(f"digest: dedupe check failed ({str(e)[:80]}) — sending anyway")

    lines = ["Monica's overnight digest — needs a human:\n"]
    for e in esc[:15]:
        lines.append(f"• {e.get('company_name') or '?'}: {(e.get('reason') or '')[:220]}")
    if len(esc) > 15:
        lines.append(f"…and {len(esc) - 15} more in Ops Attention.")
    if sys_notes:
        lines.append("\nNew system notes:")
        for n in sys_notes[:8]:
            lines.append(f"• {(n.get('body') or '')[:180]}")
    lines.append("\nFull detail: app → Ops Attention.")
    body = "\n".join(lines)

    key = os.environ.get("SENDGRID_API_KEY", "")
    if not key:
        print("digest: SENDGRID_API_KEY missing"); return 1
    r = requests.post("https://api.sendgrid.com/v3/mail/send", timeout=30,
                      headers={"Authorization": f"Bearer {key}",
                               "Content-Type": "application/json"},
                      json={"personalizations": [{"to": [{"email": TO}]}],
                            "from": {"email": FROM, "name": "Monica (Rank AI)"},
                            "subject": f"Monica digest — {len(esc)} escalation(s) need you",
                            "content": [{"type": "text/plain", "value": body}]})
    print("digest email:", r.status_code)
    if r.status_code in (200, 202):
        try:
            _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
                {"k": "concierge-digest-sent", "v": today,
                 "updated_at": datetime.now(timezone.utc).isoformat()},
                prefer="resolution=merge-duplicates,return=minimal")
        except Exception as e:  # noqa: BLE001
            print(f"digest: dedupe stamp failed ({str(e)[:80]})")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
