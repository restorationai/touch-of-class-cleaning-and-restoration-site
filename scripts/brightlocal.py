#!/usr/bin/env python3
"""brightlocal.py — Citation Builder fleet automation (Santino 2026-09-03).

The whole recipe was proven live tonight on our own location (campaign
996268: 10 credits drawn 500->490, campaign paid, 10 quality sites
auto-selected):

  1. POST /manage/v1/locations                 (NAP from clients/{slug}.json
                                                + companies row)
  2. POST /manage/v1/citation-builder          {location_id} -> campaign_id
  3. wait for lookup_status == 'complete'      (existing-citation lookup)
  4. PUT  /manage/v1/citation-builder/{id}/confirm
         {package_id: cb10|cb15|cb25|cb30|cb50|cb75|cb100, auto_select,
          citations[], publishers[], remove_duplicates, express, notes}
         -> pays with prepaid Quick credits (1 credit = 1 citation)
  5. GET  /manage/v1/citation-builder/{id}     -> citations_submission_status
         {ordered,to_do,submitted,pending,live,...} for progress polling

Auth: x-api-key header ONLY (BRIGHTLOCAL_API_KEY). One CB campaign per
location. Top-ups after the first order go via create-secondary-campaign
(not yet wired). Aggregator (publisher) submissions cost extra credits, we
default to none. developer.brightlocal.com docs are a JS-only SPA: render
with playwright, plain curl gets a stub.

Commands:
  audit                        fleet table: who has location/campaign/order
  setup   --slug X [--apply]   create location + campaign for one client
  order   --slug X --package cb25 [--express] [--apply]   spend credits
  status  [--slug X]           submission progress for ordered campaigns
State lives in clients/{slug}.json under "brightlocal":
  {location_id, campaign_id, ordered_at, package_id}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS = ROOT / "clients"
BASE = "https://api.brightlocal.com/manage/v1"
PACKAGES = ("cb10", "cb15", "cb25", "cb30", "cb50", "cb75", "cb100")

# BrightLocal business_category_id for restoration:
# 967 = "Water damage restoration service"
# (gcid:water_damage_restoration_service — verified via
# GET /business-categories/USA?query=water+damage 2026-09-03)
DEFAULT_CATEGORY_ID = 967

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


def _bl(method: str, path: str, body=None):
    req = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"x-api-key": os.environ["BRIGHTLOCAL_API_KEY"],
                 "Content-Type": "application/json",
                 # Cloudflare 403s the default Python-urllib UA (code 1010)
                 "User-Agent": "curl/8.4.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        raise RuntimeError(f"BrightLocal {method} {path} -> {e.code}: "
                           f"{detail}") from None


def load_client(slug: str) -> dict:
    return json.loads((CLIENTS / f"{slug}.json").read_text())


def save_client(slug: str, data: dict) -> None:
    (CLIENTS / f"{slug}.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def credits() -> int:
    return int(_bl("GET", "/citation-builder/credits").get("credits", 0))


def _brand_ts(slug: str) -> dict:
    """Canonical NAP source: sites/{slug}/src/lib/brand.ts (schema-grade —
    the canonical phone, never the DNI tracking number)."""
    p = ROOT / "sites" / slug / "src" / "lib" / "brand.ts"
    if not p.is_file():
        return {}
    src = p.read_text(errors="ignore")
    out = {}
    for key in ("displayName", "phone", "streetAddress", "primaryCity",
                "primaryState", "postalCode", "domain"):
        m = re.search(rf'^\s*{key}:\s*"([^"]*)"', src, re.M)
        if m:
            out[key] = m.group(1)
    return out


def nap_for(slug: str, c: dict) -> dict | None:
    """NAP payload: brand.ts first (canonical), client json fallback."""
    b = _brand_ts(slug)
    name = b.get("displayName") or c.get("display_name")
    phone = b.get("phone")
    line1 = b.get("streetAddress")
    city = b.get("primaryCity")
    region_code = b.get("primaryState")
    postcode = b.get("postalCode")
    website = b.get("domain") or c.get("domain")
    if not all([name, phone, line1, city, region_code, postcode, website]):
        return None
    return {
        "business_name": name,
        "country": "USA",
        "location_reference": slug[:50],
        "business_category_id": DEFAULT_CATEGORY_ID,
        "telephone": re.sub(r"[^\d]", "", phone)[-10:],
        "address": {
            "address1": line1, "city": city,
            "region": STATE_NAMES.get(region_code.upper(), region_code),
            "region_code": region_code.upper(),
            "postcode": postcode,
        },
        "urls": {"website_url": f"https://{website}"},
    }


def cmd_setup(args) -> int:
    slug = args.slug
    c = load_client(slug)
    bl = c.get("brightlocal") or {}
    if bl.get("campaign_id"):
        print(f"[{slug}] already set up: location {bl.get('location_id')}, "
              f"campaign {bl.get('campaign_id')}")
        return 0
    nap = nap_for(slug, c)
    if not nap:
        print(f"[{slug}] NAP incomplete in clients/{slug}.json — fix first")
        return 1
    print(f"[{slug}] {nap['business_name']} | {nap['address']['address1']}, "
          f"{nap['address']['city']}, {nap['address']['region_code']} "
          f"{nap['address']['postcode']} | {nap['telephone']} | "
          f"{nap['urls']['website_url']}")
    if not args.apply:
        print("  [dry-run] would create BrightLocal location + CB campaign")
        return 0
    if not bl.get("location_id"):
        res = _bl("POST", "/locations", nap)
        bl["location_id"] = res["location_id"]
        print(f"  location created: {bl['location_id']}")
    res = _bl("POST", "/citation-builder",
              {"location_id": bl["location_id"]})
    bl["campaign_id"] = res["campaign_id"]
    print(f"  campaign created: {bl['campaign_id']} (lookup runs async)")
    c["brightlocal"] = bl
    save_client(slug, c)
    return 0


def cmd_order(args) -> int:
    slug = args.slug
    if args.package not in PACKAGES:
        print(f"package must be one of {PACKAGES}")
        return 1
    c = load_client(slug)
    bl = c.get("brightlocal") or {}
    if not bl.get("campaign_id"):
        print(f"[{slug}] no campaign — run setup first")
        return 1
    if bl.get("ordered_at"):
        print(f"[{slug}] already ordered {bl.get('package_id')} at "
              f"{bl['ordered_at']} — top-ups need the secondary-campaign "
              "flow (unwired); refusing")
        return 1
    cid = bl["campaign_id"]
    detail = _bl("GET", f"/citation-builder/{cid}")
    if detail.get("lookup_status") != "complete":
        print(f"[{slug}] citation lookup still "
              f"{detail.get('lookup_status')} — try again in a few minutes")
        return 1
    bal = credits()
    cost = int(args.package[2:])
    print(f"[{slug}] campaign {cid}: ordering {args.package} "
          f"({cost} credits of {bal} available)"
          + (" EXPRESS" if args.express else ""))
    if bal < cost:
        print("  insufficient credits — refusing")
        return 1
    if not args.apply:
        print("  [dry-run] would confirm with credits")
        return 0
    picked: list[str] = []
    if args.pick_top:
        # Hand-pick: highest domain-authority SAB-supported sites first
        # (Santino 2026-09-03: we choose the sources, not their picker)
        avail = _bl("GET", f"/citation-builder/{cid}/citations").get("data") or []
        ranked = sorted(
            (a for a in avail if a.get("is_sab_supported") is not False),
            key=lambda a: -(a.get("domain_authority") or 0))
        picked = [a["domain"] for a in ranked[:cost]]
        print(f"  hand-picked top {len(picked)} by DA: "
              + ", ".join(picked[:8]) + (" ..." if len(picked) > 8 else ""))
        if len(picked) < cost:
            print(f"  only {len(picked)} SAB-suitable sites available — "
                  "refusing (drop the package size)")
            return 1
    publishers = [p.strip() for p in (args.publishers or "").split(",")
                  if p.strip()]
    _bl("PUT", f"/citation-builder/{cid}/confirm", {
        "package_id": args.package, "auto_select": not picked,
        "citations": picked, "publishers": publishers,
        "remove_duplicates": False, "express": bool(args.express),
        "notes": "Service-area business (SAB): hide the street address on "
                 "directories where possible.",
    })
    after = _bl("GET", f"/citation-builder/{cid}")["campaigns"][0]
    print(f"  paid: {after['paid']} | ordered: {after['citations_ordered']} "
          f"| credits left: {credits()}")
    bl["ordered_at"] = datetime.now(timezone.utc).isoformat()
    bl["package_id"] = args.package
    c["brightlocal"] = bl
    save_client(slug, c)
    cid = _company_id(slug)
    if cid:
        _work_log(cid, "citations-building",
                  f"Building {cost} new business listings for your company. "
                  "Each one will be listed here and in your Listings view "
                  "as it goes live over the next few weeks",
                  {"campaign_id": bl["campaign_id"],
                   "package_id": args.package, "credits_spent": cost})
    return 0


def _company_id(slug: str) -> str | None:
    try:
        cmap = json.loads((CLIENTS / "company_map.json").read_text())
        return cmap.get(slug)
    except (OSError, json.JSONDecodeError):
        return None


def _work_log(cid: str, action: str, detail: str, evidence=None) -> None:
    """One client-readable activity line — the same feed the app's activity
    view and monthly summaries read. Never fatal."""
    try:
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        req = urllib.request.Request(
            os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/marketing_work_log",
            data=json.dumps({
                "company_id": cid, "actor": "restoration-ai",
                "category": "citations", "action": action,
                "detail": detail, "evidence": evidence or {},
            }).encode(),
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "Prefer": "return=minimal"})
        urllib.request.urlopen(req, timeout=20)
    except Exception as e:  # noqa: BLE001
        print(f"  (work_log failed: {str(e)[:80]})")


def cmd_sync(_args) -> int:
    """Nightly: poll every ordered campaign's per-citation status; log every
    NEWLY LIVE citation to the activity feed and the app's Business Listings
    card (listings.record_listing). Idempotent via the synced_live ledger in
    clients/{slug}.json brightlocal state."""
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from listings import record_listing
    except ImportError:
        record_listing = None
    for f in sorted(CLIENTS.glob("*.json")):
        try:
            c = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(c, dict):
            continue
        bl = c.get("brightlocal") or {}
        if not bl.get("campaign_id") or not bl.get("ordered_at"):
            continue
        slug = f.stem
        cid = _company_id(slug)
        d = _bl("GET", f"/citation-builder/{bl['campaign_id']}")
        camp = d["campaigns"][0]
        synced = set(bl.get("synced_live") or [])
        new_live = []
        for cit in camp.get("citations") or []:
            if not isinstance(cit, dict):
                continue
            domain = cit.get("domain") or cit.get("site")
            status = str(cit.get("status") or "").lower()
            url = cit.get("url") or cit.get("live_url") or ""
            if domain and status in ("live", "updated") and domain not in synced:
                new_live.append((domain, url))
        if not new_live:
            continue
        print(f"[{slug}] {len(new_live)} newly live citation(s)")
        for domain, url in new_live:
            if cid:
                # record_listing writes BOTH the app Listings card entry and
                # its own client-readable work-ledger line; the plain
                # work_log is the no-URL fallback so the activity feed never
                # misses a live citation.
                logged = False
                if record_listing and url:
                    try:
                        logged = record_listing(cid, domain, url)
                    except Exception as e:  # noqa: BLE001
                        print(f"  (record_listing {domain}: {str(e)[:80]})")
                if not logged:
                    _work_log(cid, "citation-live",
                              f"New business listing built for you on {domain}"
                              + (f": {url}" if url else ""),
                              {"domain": domain, "url": url,
                               "campaign_id": bl["campaign_id"]})
            synced.add(domain)
        bl["synced_live"] = sorted(synced)
        c["brightlocal"] = bl
        save_client(slug, c)
    return 0


def cmd_status(args) -> int:
    for f in sorted(CLIENTS.glob("*.json")):
        if f.name in ("company_map.json",):
            continue
        try:
            c = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        bl = c.get("brightlocal") or {}
        if not bl.get("campaign_id"):
            continue
        if args.slug and f.stem != args.slug:
            continue
        d = _bl("GET", f"/citation-builder/{bl['campaign_id']}")
        camp = d["campaigns"][0]
        s = camp["citations_submission_status"]
        print(f"{f.stem:42} {camp['status']:8} "
              f"ordered={s['ordered']} submitted={s['submitted']} "
              f"pending={s['pending']} live={s['live']}")
    return 0


def cmd_audit(_args) -> int:
    print(f"credits available: {credits()}\n")
    rows = []
    for f in sorted(CLIENTS.glob("*.json")):
        try:
            c = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(c, dict) or not c.get("display_name"):
            continue
        bl = c.get("brightlocal") or {}
        nap_ok = nap_for(f.stem, c) is not None
        rows.append((f.stem, nap_ok, bl.get("location_id"),
                     bl.get("campaign_id"), bl.get("package_id")))
    for slug, nap_ok, loc, camp, pkg in rows:
        state = (f"ordered {pkg}" if pkg else "campaign ready" if camp
                 else "location only" if loc
                 else "NAP ready" if nap_ok else "NAP INCOMPLETE")
        print(f"  {slug:44} {state}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("audit")
    ps = sub.add_parser("setup")
    ps.add_argument("--slug", required=True)
    ps.add_argument("--apply", action="store_true")
    po = sub.add_parser("order")
    po.add_argument("--slug", required=True)
    po.add_argument("--package", required=True)
    po.add_argument("--express", action="store_true")
    po.add_argument("--pick-top", action="store_true",
                    help="hand-pick highest-DA SAB sites instead of "
                         "BrightLocal auto-select")
    po.add_argument("--publishers", default="",
                    help="comma list: dataaxle,neustar,foursquare,"
                         "gpsnetwork,ypnetwork")
    po.add_argument("--apply", action="store_true")
    pt = sub.add_parser("status")
    pt.add_argument("--slug")
    sub.add_parser("sync")
    args = ap.parse_args()
    if args.cmd == "setup":
        return cmd_setup(args)
    if args.cmd == "order":
        return cmd_order(args)
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "sync":
        return cmd_sync(args)
    return cmd_audit(args)


if __name__ == "__main__":
    sys.exit(main())
