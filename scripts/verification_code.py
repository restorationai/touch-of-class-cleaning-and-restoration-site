#!/usr/bin/env python3
"""verification_code.py — fetch a 2FA / verification code WE received, by
ourselves, the moment a login asks for one.

Santino 2026-09-27 (Apple Podcasts on the Mini): "make sure that, moving
forward, either you or it would recognize this and automatically retrieve that
code." The first relay watched ONE GHL thread, but Apple texts every code from
a DIFFERENT sender number (+12057938166 in Aug, +14084189454 on 09-27), so each
code opened a new conversation and the relay never saw it.

This is sender-agnostic. It checks, newest first:
  1. every GHL conversation (agency line, the ..49 / 805 number) whose latest
     inbound message arrived after --since and reads like a verification code
  2. ops_kv verification-codes:* rows (codes the Railway catcher grabbed on
     client Twilio tracking numbers — api/main.py _verification_code)

Usage (the Mini runs this right after it clicks "send code"):
  python3 scripts/verification_code.py wait --since <unix epoch of the request> \
      [--match apple] [--timeout 300]
Prints `CODE <digits> FROM <sender> AT <iso>` and exits 0, or exits 1 on timeout.
Codes are single-use and expire in minutes; never commit them anywhere.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import client_concierge as cc  # noqa: E402

CODE_RE = re.compile(r"(?<![\d-])(\d{4,8})(?![\d-])")
WORDS_RE = re.compile(r"\b(code|verification|verify|passcode|one[- ]time|otp)\b", re.I)


def _ms_to_dt(v) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(v) / 1000, timezone.utc)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            return None


def _from_ghl(since: datetime, match: str | None) -> tuple | None:
    loc = os.environ["GHL_LOCATION_ID"]
    hits = []
    for q in ("code", "verification"):
        r = cc._ghl("GET", "/conversations/search", params={
            "locationId": loc, "query": q, "limit": 15,
            "sort": "desc", "sortBy": "last_message_date"}) or {}
        for c in r.get("conversations", []):
            at = _ms_to_dt(c.get("lastMessageDate"))
            body = str(c.get("lastMessageBody") or "")
            if not at or at <= since or not WORDS_RE.search(body):
                continue
            if match and match.lower() not in body.lower():
                continue
            m = CODE_RE.search(body)
            if m:
                hits.append((at, m.group(1), c.get("phone") or c.get("contactName"), body))
    return max(hits) if hits else None


def _from_kv(since: datetime, match: str | None) -> tuple | None:
    hits = []
    for k, v in (cc.kv_prefix("verification-codes:") or {}).items():
        for row in (v if isinstance(v, list) else [v]):
            if not isinstance(row, dict):
                continue
            at = _ms_to_dt(row.get("at") or row.get("received_at") or row.get("ts"))
            body = str(row.get("body") or "")
            code = row.get("code") or (CODE_RE.search(body).group(1)
                                       if CODE_RE.search(body) else None)
            if not (at and code) or at <= since:
                continue
            if match and match.lower() not in (body + str(row.get("from", ""))).lower():
                continue
            hits.append((at, str(code), row.get("from") or k, body))
    return max(hits) if hits else None


def cmd_wait(a) -> int:
    since = datetime.fromtimestamp(a.since, timezone.utc)
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        for src in (_from_ghl, _from_kv):
            try:
                hit = src(since, a.match)
            except Exception as e:  # noqa: BLE001 — keep polling
                print(f"  ({src.__name__} error: {str(e)[:80]})", file=sys.stderr)
                hit = None
            if hit:
                at, code, sender, _body = hit
                print(f"CODE {code} FROM {sender} AT {at.isoformat()}")
                return 0
        time.sleep(a.interval)
    print("NO CODE before timeout", file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wait")
    w.add_argument("--since", type=float, required=True,
                   help="unix epoch when the code was requested")
    w.add_argument("--match", help="substring the text must contain, e.g. apple")
    w.add_argument("--timeout", type=int, default=300)
    w.add_argument("--interval", type=int, default=6)
    w.set_defaults(func=cmd_wait)
    a = ap.parse_args()
    cc.load_env()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
