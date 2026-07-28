#!/usr/bin/env python3
"""Call-tracking provisioning (Santino 2026-07-28).

Buys a local Twilio number per client per source (gbp / website), points its
Voice webhook at the rank-ai API's TwiML endpoint (straight-through dial, NO
whisper; recording with the short caller disclosure only in all-party consent
states — the API decides from the company's state), and stores the mapping in
companies.integration_settings.call_tracking.

The canonical number policy: the REAL number stays on all citations and as
the GBP additional phone; tracking numbers go on the website and as the GBP
primary only (gbp.py set-phone does that swap separately, human-triggered).

Usage:
  python3 scripts/call_tracking.py provision --slug restorationxpress --source gbp
  python3 scripts/call_tracking.py provision --slug restorationxpress --source website
  python3 scripts/call_tracking.py list --slug restorationxpress
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb, slug_map  # noqa: E402

API_BASE = "https://rank-ai-api-production.up.railway.app"


def _tw(method: str, path: str, params: dict | None = None) -> dict:
    sid = os.environ["TWILIO_ACCOUNT_SID"]
    token = os.environ["TWILIO_AUTH_TOKEN"]
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/{path}"
    data = urllib.parse.urlencode(params or {}).encode() if method == "POST" else None
    if method == "GET" and params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Basic " + base64.b64encode(
            f"{sid}:{token}".encode()).decode()})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def provision(slug: str, source: str) -> str:
    inv = {s: c for c, s in slug_map().items()}
    cid = inv.get(slug)
    if not cid:
        return f"{slug}: no company mapping"
    co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}"
              "&select=phone,integration_settings", prefer="return=representation")
          or [{}])[0]
    ints = co.get("integration_settings") or {}
    if isinstance(ints, str):
        ints = json.loads(ints)
    ct = ints.setdefault("call_tracking", {})
    if ct.get(source, {}).get("number"):
        return f"{slug}/{source}: already provisioned {ct[source]['number']}"
    real = re.sub(r"\D", "", co.get("phone") or "")
    area = real[-10:-7] if len(real) >= 10 else ""
    # local number in the client's own area code; fall back to any local
    found = []
    if area:
        found = _tw("GET", "AvailablePhoneNumbers/US/Local.json",
                    {"AreaCode": area, "PageSize": 3}).get("available_phone_numbers", [])
    if not found:
        found = _tw("GET", "AvailablePhoneNumbers/US/Local.json",
                    {"InRegion": "US", "PageSize": 3}).get("available_phone_numbers", [])
    if not found:
        return f"{slug}/{source}: no numbers available (area {area})"
    number = found[0]["phone_number"]
    bought = _tw("POST", "IncomingPhoneNumbers.json", {
        "PhoneNumber": number,
        "FriendlyName": f"rankai-{slug}-{source}",
        "VoiceUrl": f"{API_BASE}/call-tracking/twiml/{cid}/{source}",
        "VoiceMethod": "POST",
    })
    ct[source] = {"number": bought["phone_number"], "sid": bought["sid"],
                  "provisioned_at": bought.get("date_created")}
    _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}", {"integration_settings": ints})
    return (f"{slug}/{source}: provisioned {bought['phone_number']} "
            f"-> forwards to +1{real[-10:]}")


def list_numbers(slug: str) -> str:
    inv = {s: c for c, s in slug_map().items()}
    cid = inv.get(slug)
    co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=integration_settings",
              prefer="return=representation") or [{}])[0]
    ints = co.get("integration_settings") or {}
    if isinstance(ints, str):
        ints = json.loads(ints)
    return json.dumps(ints.get("call_tracking") or {}, indent=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("provision")
    p.add_argument("--slug", required=True)
    p.add_argument("--source", choices=["gbp", "website"], required=True)
    l_ = sub.add_parser("list")
    l_.add_argument("--slug", required=True)
    a = ap.parse_args()
    if a.cmd == "provision":
        print(provision(a.slug, a.source))
    else:
        print(list_numbers(a.slug))
    return 0


if __name__ == "__main__":
    sys.exit(main())
