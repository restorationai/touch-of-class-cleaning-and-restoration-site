#!/usr/bin/env python3
"""Send a CI failure alert email via SendGrid.

Called from GitHub Actions with `if: failure()` so it only runs when an
earlier step in the job has already failed.

Usage:
    python3 scripts/notify_failure.py \
        --subject  "Rank AI CI failure: weekly-maintenance run #42" \
        --run-url  "https://github.com/restorationai/Rank-AI-Pipeline/actions/runs/123456"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"
FROM_EMAIL = "no-reply@restorationai.io"
FROM_NAME = "Rank AI Bot"
TO_EMAIL = "contact@restorationai.io"


def send(subject: str, run_url: str, api_key: str, extra_body: str | None = None) -> None:
    detail = f"{extra_body.strip()}\n\n" if extra_body else ""
    body = (
        f"A Rank AI automated job failed and needs your attention.\n\n"
        f"Run: {run_url}\n"
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"{detail}"
        f"Open the link above, click the failed step, and check the logs.\n\n"
        f"-- Rank AI Bot"
    )

    payload = {
        "personalizations": [{"to": [{"email": TO_EMAIL}], "subject": subject}],
        "from": {"email": FROM_EMAIL, "name": FROM_NAME},
        "content": [{"type": "text/plain", "value": body}],
    }

    req = urllib.request.Request(
        SENDGRID_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Alert sent to {TO_EMAIL} (HTTP {resp.status})")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        print(f"SendGrid error {exc.code}: {detail}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a CI failure alert via SendGrid")
    parser.add_argument("--subject", required=True, help="Email subject line")
    parser.add_argument("--run-url", required=True, help="GitHub Actions run URL")
    parser.add_argument("--body", help="Optional extra detail (e.g. a failure summary) included in the email body")
    args = parser.parse_args()

    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        print("ERROR: SENDGRID_API_KEY env var not set", file=sys.stderr)
        sys.exit(1)

    send(args.subject, args.run_url, api_key, extra_body=args.body)


if __name__ == "__main__":
    main()
