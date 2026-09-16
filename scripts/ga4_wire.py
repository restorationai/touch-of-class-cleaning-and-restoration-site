#!/usr/bin/env python3
"""ga4_wire.py — E18 (Santino 2026-09-16): finish every client's GA4 wiring
automatically. The sites already fire `click_to_call` and `generate_lead`
sitewide (Analytics.astro delegated listeners); what always stayed manual
was the GA4-side half. This script closes it:

  1. KEY EVENTS: marks `click_to_call` + `generate_lead` as key events on
     the client's GA4 property (that is what Google Ads can import as
     conversions — without it the events are just rows in a report).
  2. GOOGLE ADS LINK: links the client's Ads account to the property
     (properties.googleAdsLinks) when we know their customer id
     (clients/{slug}.json brand.google_ads_customer_id). A link our
     Google user can't authorize outright surfaces as "pending Ads-side
     permission" instead of failing silently.

Property resolution: measurement id in sites/{slug}/src/lib/brand.ts →
data stream → property, via the Analytics Admin API. Auth: the same
service-account / refresh-token ladder as create_ga4.py.

Idempotent; rides client-ops-sync nightly so newly connected clients get
wired with zero manual steps. CLI:
    python3 scripts/ga4_wire.py [--slug X] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from create_ga4 import access_token  # noqa: E402


def oauth_token() -> str | None:
    """The agency-USER token (refresh-token flow), skipping the service
    account. Needed for googleAdsLinks: the link call must come from an
    identity that is ALSO an admin of the Ads account (our agency user is,
    via the MCC; the service account never can be — SAs cannot be Google
    Ads users, which is why link creation 403s under the SA)."""
    import os as _os
    import urllib.parse as _up
    rt = _os.environ.get("GOOGLE_ANALYTICS_REFRESH_TOKEN")
    cid = _os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    sec = _os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not (rt and cid and sec):
        return None
    body = _up.urlencode({"client_id": cid, "client_secret": sec,
                          "refresh_token": rt,
                          "grant_type": "refresh_token"}).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token",
                                 data=body, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("access_token")

ADMIN = "https://analyticsadmin.googleapis.com/v1beta"
KEY_EVENTS = ("click_to_call", "generate_lead")


def _api(tok: str, method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{ADMIN}/{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {tok}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def measurement_map(tok: str) -> dict[str, str]:
    """{measurementId -> properties/123} across our agency account."""
    out: dict[str, str] = {}
    page = ""
    while True:
        res = _api(tok, "GET", f"accountSummaries?pageSize=200{page}")
        for acct in res.get("accountSummaries", []):
            for prop in acct.get("propertySummaries", []):
                pid = prop["property"]
                try:
                    streams = _api(tok, "GET", f"{pid}/dataStreams")
                except Exception:
                    continue
                for st in streams.get("dataStreams", []):
                    mid = (st.get("webStreamData") or {}).get("measurementId")
                    if mid:
                        out[mid] = pid
        npt = res.get("nextPageToken")
        if not npt:
            break
        page = f"&pageToken={npt}"
    return out


def wire_property(tok: str, slug: str, prop: str, ads_id: str,
                  dry: bool) -> list[str]:
    notes: list[str] = []
    existing = {k.get("eventName") for k in
                _api(tok, "GET", f"{prop}/keyEvents").get("keyEvents", [])}
    for ev in KEY_EVENTS:
        if ev in existing:
            continue
        if dry:
            notes.append(f"would mark key event {ev}")
            continue
        _api(tok, "POST", f"{prop}/keyEvents",
             {"eventName": ev, "countingMethod": "ONCE_PER_EVENT"})
        notes.append(f"key event {ev} MARKED")
    if ads_id:
        digits = re.sub(r"\D", "", ads_id)
        links = _api(tok, "GET", f"{prop}/googleAdsLinks") \
            .get("googleAdsLinks", [])
        if any(re.sub(r"\D", "", l.get("customerId") or "") == digits
               for l in links):
            pass  # already linked
        elif dry:
            notes.append(f"would link Ads account {ads_id}")
        else:
            try:
                link_tok = oauth_token() or tok
                _api(link_tok, "POST", f"{prop}/googleAdsLinks",
                     {"customerId": digits,
                      "adsPersonalizationEnabled": True})
                notes.append(f"Ads account {ads_id} LINKED")
            except urllib.error.HTTPError as e:
                msg = e.read().decode()[:120]
                notes.append(f"Ads link pending Ads-side permission "
                             f"({e.code}: {msg})")
    return notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    tok = access_token()
    mmap = measurement_map(tok)

    slugs = ([a.slug] if a.slug else
             sorted(p.stem for p in (ROOT / "clients").glob("*.json")
                    if p.stem != "company_map"))
    wired = 0
    for slug in slugs:
        bt = ROOT / "sites" / slug / "src" / "lib" / "brand.ts"
        if not bt.exists():
            continue
        m = re.search(r'ga4MeasurementId: "(G-[A-Z0-9]+)"', bt.read_text())
        if not m:
            continue
        prop = mmap.get(m.group(1))
        if not prop:
            print(f"{slug}: {m.group(1)} not found under our GA account")
            continue
        rec = {}
        try:
            rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
        except Exception:
            pass
        ads_id = ((rec.get("brand") or {}).get("google_ads_customer_id")
                  or rec.get("google_ads_customer_id") or "")
        try:
            notes = wire_property(tok, slug, prop, ads_id, a.dry_run)
        except Exception as e:  # noqa: BLE001 — one client never stops the fleet
            print(f"{slug}: ERROR {str(e)[:120]}")
            continue
        if notes:
            wired += 1
            print(f"{slug}: " + "; ".join(notes))
    print(f"ga4-wire: {wired} client(s) changed"
          f"{' [dry-run]' if a.dry_run else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
