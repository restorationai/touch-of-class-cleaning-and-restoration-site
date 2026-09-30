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
CLIENTS_DIR = ROOT / "clients"
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb, slug_map  # noqa: E402

API_BASE = "https://rank-ai-api-production.up.railway.app"


def _tw(method: str, path: str, params: dict | None = None) -> dict:
    sid = (os.environ.get("TWILIO_MASTER_ACCOUNT_SID")
           or os.environ["TWILIO_ACCOUNT_SID"])
    token = (os.environ.get("TWILIO_MASTER_AUTH_TOKEN")
             or os.environ["TWILIO_AUTH_TOKEN"])
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/{path}"
    data = urllib.parse.urlencode(params or {}).encode() if method == "POST" else None
    if method == "GET" and params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Basic " + base64.b64encode(
            f"{sid}:{token}".encode()).decode()})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        return json.loads(body) if body.strip() else {}


def provision(slug: str, source: str) -> str:
    inv = {s: c for c, s in slug_map().items()}
    cid = inv.get(slug)
    if not cid:
        return f"{slug}: no company mapping"
    co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}"
              "&select=phone,state,integration_settings", prefer="return=representation")
          or [{}])[0]
    ints = co.get("integration_settings") or {}
    if isinstance(ints, str):
        ints = json.loads(ints)
    ct = ints.setdefault("call_tracking", {})
    if ct.get(source, {}).get("number"):
        return f"{slug}/{source}: already provisioned {ct[source]['number']}"
    real = re.sub(r"\D", "", co.get("phone") or "")
    area = real[-10:-7] if len(real) >= 10 else ""
    # METRO SOURCES (TDI 2026-09-22): source 'metro_916' buys IN area 916 —
    # multi-region clients show a local number per metro on that metro's
    # pages. The number the source names always wins the locality ladder.
    m_metro = re.fullmatch(r"metro_(\d{3})", source)
    if m_metro:
        area = m_metro.group(1)
    state = (co.get("state") or "").strip()
    st = state.upper()[:2] if len(state) <= 2 else {
        "FLORIDA": "FL", "UTAH": "UT", "CALIFORNIA": "CA", "SOUTH DAKOTA": "SD",
        "NORTH CAROLINA": "NC", "SOUTH CAROLINA": "SC", "NEVADA": "NV",
        "MASSACHUSETTS": "MA", "PENNSYLVANIA": "PA", "NEW JERSEY": "NJ",
    }.get(state.upper(), state.upper()[:2])
    # Locality ladder (Santino 2026-07-28: same COUNTY, not just same state):
    # 1) client's own area code, 2) within 25 miles of their location,
    # 3) anywhere in their state. Never out of state.
    lat = lng = None
    pi = CLIENTS_DIR / slug / "plan-input.json"
    if pi.exists():
        b = (json.loads(pi.read_text()).get("brand") or {})
        lat, lng = b.get("lat"), b.get("lng")
    found = []
    if area:
        found = _tw("GET", "AvailablePhoneNumbers/US/Local.json",
                    {"AreaCode": area, "PageSize": 3}).get("available_phone_numbers", [])
    if not found and lat and lng:
        found = _tw("GET", "AvailablePhoneNumbers/US/Local.json",
                    {"NearLatLong": f"{lat},{lng}", "Distance": 25,
                     "PageSize": 3}).get("available_phone_numbers", [])
    if not found and st:
        found = _tw("GET", "AvailablePhoneNumbers/US/Local.json",
                    {"InRegion": st, "PageSize": 3}).get("available_phone_numbers", [])
    if not found:
        return f"{slug}/{source}: no numbers available (area {area}, state {st}) — manual pick needed"
    number = found[0]["phone_number"]
    bought = _tw("POST", "IncomingPhoneNumbers.json", {
        "PhoneNumber": number,
        "FriendlyName": f"rankai-{slug}-{source}",
        "VoiceUrl": f"{API_BASE}/call-tracking/twiml/{cid}/{source}",
        "VoiceMethod": "POST",
        "SmsUrl": f"{API_BASE}/call-tracking/sms/{cid}/{source}",
        "SmsMethod": "POST",
    })
    ct[source] = {"number": bought["phone_number"], "sid": bought["sid"],
                  "provisioned_at": bought.get("date_created")}
    _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}", {"integration_settings": ints})
    out = (f"{slug}/{source}: provisioned {bought['phone_number']} "
           f"-> forwards to +1{real[-10:]}")
    # AUTO-FLIP (Santino 2026-09-09): a gbp tracking number goes live on the
    # profile the moment forwarding verifies — 12 clients had numbers sitting
    # provisioned-but-never-flipped because the flip was a separate manual
    # step. gbp.set_phone no-ops safely when the GBP isn't connected yet;
    # gbp.py sync's backstop picks those up after connect.
    if source == "gbp":
        if verify_forwarding(cid, source):
            try:
                import gbp
                out += " | " + gbp.set_phone(slug)
            except Exception as e:  # noqa: BLE001 — flip failure never
                out += f" | auto-flip failed: {str(e)[:80]}"  # kills provision
        else:
            out += " | forwarding check FAILED — GBP flip held"
    return out


# facebook/instagram dropped from the standard set 2026-09-11 (Santino):
# organic-social numbers never earned real calls fleet-wide and the monthly
# spend wasn't justified; existing ones were released the same day (RT Olson
# keeps his — BDA actively works Meta there). "meta_ads" exists as an
# on-demand source for clients running paid Meta (provision explicitly).
ALL_SOURCES = ("website", "gbp", "google_ads", "yelp", "chatgpt", "gemini",
               "bing")


def provision_all(slug: str) -> list[str]:
    """The FULL tracking set for one client (standard for every new client,
    Santino 2026-09-10): website + gbp + the seven attribution channels,
    then publish the site DNI map. Idempotent per source."""
    out = [provision(slug, s) for s in ALL_SOURCES]
    try:
        import dni_sync
        dni_sync.sync(slug)
        out.append(f"{slug}: DNI map published")
    except Exception as e:  # noqa: BLE001
        out.append(f"{slug}: DNI map publish failed: {str(e)[:80]}")
    return out


def verify_forwarding(cid: str, source: str = "gbp") -> bool:
    """POST the number's live TwiML route and confirm it dials the client's
    real line (companies.phone). The automated replacement for the old
    'human test call' gate — same check, no human in the loop."""
    try:
        co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=phone",
                  prefer="return=representation") or [{}])[0]
        real = re.sub(r"\D", "", co.get("phone") or "")[-10:]
        if not real:
            return False
        req = urllib.request.Request(
            f"{API_BASE}/call-tracking/twiml/{cid}/{source}",
            data=b"", method="POST")
        twiml = urllib.request.urlopen(req, timeout=20).read().decode()
        m = re.search(r">(\+?[\d]+)</Dial>", twiml)
        return bool(m) and re.sub(r"\D", "", m.group(1))[-10:] == real
    except Exception:  # noqa: BLE001 — fail closed: no verify, no flip
        return False


def replace_area(slug: str, area: str, release_old: bool = True) -> list[str]:
    """Swap every tracking number to a new area code (Kenny/Veterans
    2026-09-30: 337 -> 850, "still routed to you"). Buys the new number with
    the same webhooks, points call_tracking.{source} at it (forward_to and
    other per-source settings carry over), republishes the DNI map, then
    releases the old number. The real line is untouched."""
    inv = {s: c for c, s in slug_map().items()}
    cid = inv.get(slug)
    if not cid:
        return [f"{slug}: no company mapping"]
    co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=integration_settings",
              prefer="return=representation") or [{}])[0]
    ints = co.get("integration_settings") or {}
    ct = ints.get("call_tracking") or {}
    out, to_release = [], []
    for source, entry in sorted(ct.items()):
        old = entry.get("number") or ""
        if not old or re.sub(r"\D", "", old)[-10:-7] == area:
            continue
        found = _tw("GET", "AvailablePhoneNumbers/US/Local.json",
                    {"AreaCode": area, "PageSize": 3}).get("available_phone_numbers", [])
        if not found:
            out.append(f"{slug}/{source}: no {area} numbers available, kept {old}")
            continue
        bought = _tw("POST", "IncomingPhoneNumbers.json", {
            "PhoneNumber": found[0]["phone_number"],
            "FriendlyName": f"rankai-{slug}-{source}",
            "VoiceUrl": f"{API_BASE}/call-tracking/twiml/{cid}/{source}",
            "VoiceMethod": "POST",
            "SmsUrl": f"{API_BASE}/call-tracking/sms/{cid}/{source}",
            "SmsMethod": "POST"})
        entry.update(number=bought["phone_number"], sid=bought["sid"],
                     provisioned_at=bought.get("date_created"),
                     replaced={"number": old, "sid": entry.get("sid"),
                               "reason": f"area code swap to {area}"})
        entry.pop("gbp_swapped_at", None)
        to_release.append((source, old, entry["replaced"]["sid"]))
        out.append(f"{slug}/{source}: {old} -> {bought['phone_number']}")
        # save after every buy so a crash never orphans a paid number
        _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}", {"integration_settings": ints})
    try:
        import dni_sync
        dni_sync.sync(slug)
        out.append(f"{slug}: DNI map republished")
    except Exception as e:  # noqa: BLE001
        out.append(f"{slug}: DNI map publish failed ({str(e)[:80]}), old numbers KEPT")
        release_old = False
    if release_old:
        for source, old, sid in to_release:
            if not sid:
                continue
            try:
                _tw("DELETE", f"IncomingPhoneNumbers/{sid}.json")
                out.append(f"{slug}/{source}: released {old}")
            except Exception as e:  # noqa: BLE001
                out.append(f"{slug}/{source}: release of {old} failed ({str(e)[:60]})")
    try:
        from work_log import work_log
        work_log(cid, "calls", "tracking-area-swap",
                 f"Your tracking phone numbers now use the local {area} area code "
                 "and still ring straight to you.",
                 evidence={"changes": out}, actor="claude")
    except Exception:  # noqa: BLE001
        pass
    return out


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
    p.add_argument("--source", required=True,
                   help="one of %s or metro_<areacode> (e.g. metro_916)"
                        % (ALL_SOURCES,))
    pa = sub.add_parser("provision-all")
    pa.add_argument("--slug", required=True)
    ra = sub.add_parser("replace-area")
    ra.add_argument("--slug", required=True)
    ra.add_argument("--area", required=True)
    ra.add_argument("--keep-old", action="store_true")
    l_ = sub.add_parser("list")
    l_.add_argument("--slug", required=True)
    a = ap.parse_args()
    if a.cmd == "provision":
        print(provision(a.slug, a.source))
    elif a.cmd == "provision-all":
        for line in provision_all(a.slug):
            print(line)
    elif a.cmd == "replace-area":
        for line in replace_area(a.slug, a.area, release_old=not a.keep_old):
            print(line)
    else:
        print(list_numbers(a.slug))
    return 0


if __name__ == "__main__":
    sys.exit(main())
