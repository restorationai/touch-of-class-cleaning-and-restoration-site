#!/usr/bin/env python3
"""credit_canary.py — Anthropic credit-balance tripwire (2026-09-14).

Why: the API account silently ran out of credits at 9:07am PT on 09-14 and
every AI surface died at once — Monica composes, meeting debriefs, the dev
agent, email intake classification. Clients waited hours with zero replies
and nothing told Santino. Workflows failed, but CI-failure emails drown in
the inbox; the outage was only noticed when clients complained.

What: one cheap probe call (claude-haiku, 1 token). On the specific
"credit balance is too low" 400, SMS Santino's ops cell directly through
the GHL send path (which needs NO Anthropic credits). Dedupe: one alert
per 4h via ops_kv. When the probe succeeds after an alert was active, a
one-time "credits restored" SMS closes the loop and clears the state.

Rides call-intel.yml (every ~30 min), so worst-case detection lag is about
half an hour. Exit 0 always — the canary must never fail a workflow.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import requests  # noqa: E402

KV_KEY = "credit-canary-alert"
DEDUPE_HOURS = 4


def main() -> int:
    from client_ops_sync import _sb
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
                 "anthropic-version": "2023-06-01"},
        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1,
              "messages": [{"role": "user", "content": "."}]},
        timeout=30)
    low = r.status_code == 400 and "credit balance" in r.text.lower()
    rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{KV_KEY}&select=v") or []
    active = rows[0]["v"] if rows else None
    now = datetime.now(timezone.utc)

    def _sms(body: str) -> None:
        from client_concierge import (send_message, OPS_PING_CONTACT_ID,
                                      OPS_PING_CELL, SendBlocked)
        try:
            send_message({"id": OPS_PING_CONTACT_ID, "phone": OPS_PING_CELL},
                         "sms", body)
        except SendBlocked as e:
            print(f"canary sms blocked: {e}")

    if low:
        if active:
            try:
                age_h = (now - datetime.fromisoformat(active["at"])
                         ).total_seconds() / 3600
            except Exception:  # noqa: BLE001
                age_h = DEDUPE_HOURS + 1
            if age_h < DEDUPE_HOURS:
                print(f"credits still out (alerted {age_h:.1f}h ago)")
                return 0
        _sms("ALERT: the Anthropic API is out of credits. Monica, meeting "
             "follow-ups, the dev agent and email replies are ALL down "
             "until you top up at console.anthropic.com > Plans & Billing. "
             "Everything queued drains automatically once credits land.")
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": KV_KEY, "v": {"at": now.isoformat()}},
            prefer="resolution=merge-duplicates")
        print("credits OUT — alert sent")
        return 0

    if r.ok or r.status_code in (200, 429, 529):
        if active:
            _sms("Anthropic credits are back. Monica and the queued "
                 "follow-ups are draining now.")
            _sb("DELETE", f"/rest/v1/ops_kv?k=eq.{KV_KEY}")
            print("credits restored — recovery sent")
        else:
            print("credits ok")
        return 0

    print(f"canary inconclusive: HTTP {r.status_code} {r.text[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
