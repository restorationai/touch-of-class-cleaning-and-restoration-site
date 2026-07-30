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
    return 0 if r.status_code in (200, 202) else 1


if __name__ == "__main__":
    sys.exit(main())
