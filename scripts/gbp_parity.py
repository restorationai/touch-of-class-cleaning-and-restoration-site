#!/usr/bin/env python3
"""gbp_parity.py — the Parity Engine (P1-P3, Santino 2026-09-17).

One nightly pass that keeps every client's Google Business Profile and
website provably in sync, both directions, services AND locations:

P1 LEDGER    Per client: services on site / on GBP / missing each way,
             areas on site / on GBP / missing each way, one parity %.
             Mirrored to ops_kv 'parity-ledger' (app + digest read it)
             and printed. You cannot keep what you cannot see.

P2 SERVICES  GBP service with no site page  -> page request auto-queued
             (the existing create-pages drain builds it). Site service
             with no GBP entry -> ADD suggestion inserted (the A2 nightly
             batch applies it). Junk phrases never queue pages — only
             names matching the restoration catalog count as real.

P3 LOCATIONS Google caps service areas at 20 per profile. The engine
             maintains the GBP list as the CLOSEST 20 candidate cities,
             ranked by distance from the profile's real pin. Candidates =
             site cities + current GBP areas + FILL-TO-20 from the Census
             Gazetteer (every US place w/ coordinates, data/2023_Gaz_*),
             so a client with only 8 site cities still runs a maxed-out
             profile (Santino: "maximize those 20"). A closer city
             displaces the farthest. GBP writes go through a validateOnly
             preflight. Site-side gaps (target cities with no site page)
             are REPORTED in the ledger; auto-building those pages is
             gated behind --apply-site (render cost) and capped.

Heartbeat: every completed run stamps ops_kv 'heartbeat:parity' — the
pipeline watchdog (D1) red-flags a stale stamp, so a dead parity engine
announces itself.

CLI:
    python3 scripts/gbp_parity.py --slug X --dry-run
    python3 scripts/gbp_parity.py --all --apply          # nightly
    python3 scripts/gbp_parity.py --all --apply --apply-site --max-new-cities 1
"""
from __future__ import annotations

import argparse
import json
import os
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import requests  # noqa: E402
import gbp  # noqa: E402
from client_ops_sync import _sb, slug_map  # noqa: E402
from gbp_auto_apply import _catalog_terms, is_protected, _norm  # noqa: E402

GAZ = ROOT / "data" / "2023_Gaz_place_national.txt"
MAX_AREAS = 20


def _dist_mi(a, b) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return 3959 * 2 * math.asin(math.sqrt(h))


_GAZ_CACHE: list | None = None


def gazetteer_state(state: str) -> list[dict]:
    """[{name, state, lat, lng}] for one state from the Census file."""
    global _GAZ_CACHE
    if _GAZ_CACHE is None:
        _GAZ_CACHE = []
        with open(GAZ, encoding="utf-8", errors="replace") as f:
            next(f)
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) < 12:
                    continue
                raw = p[3].strip()
                name = re.sub(r"\s+(city|town|village|CDP|borough|municipality)$",
                              "", raw, flags=re.I)
                try:
                    _GAZ_CACHE.append({"state": p[0].strip(), "name": name,
                                       "cdp": raw.endswith("CDP"),
                                       "sqmi": float(p[8]),
                                       "lat": float(p[10]), "lng": float(p[11])})
                except ValueError:
                    continue
    return [g for g in _GAZ_CACHE if g["state"] == state.upper()]


def _city_key(c: str) -> str:
    return _norm(re.sub(r",\s*[A-Z]{2}$", "", c))


_COUNTY_CACHE_KEY = "fcc-county-cache"
_county_cache: dict | None = None


def _county_of(lat: float, lng: float) -> str | None:
    """County name for a coordinate via the FCC census API, cached forever
    in ops_kv (a place does not change counties)."""
    global _county_cache
    if _county_cache is None:
        rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{_COUNTY_CACHE_KEY}&select=v") or []
        _county_cache = (rows[0].get("v") if rows else {}) or {}
    key = f"{round(lat, 4)},{round(lng, 4)}"
    if key in _county_cache:
        return _county_cache[key] or None
    try:
        r = requests.get("https://geo.fcc.gov/api/census/area",
                         params={"lat": lat, "lon": lng, "format": "json"},
                         timeout=15)
        county = ((r.json().get("results") or [{}])[0].get("county_name")
                  or None)
    except Exception:  # noqa: BLE001 — unknown county = unbounded (fail open)
        return None
    _county_cache[key] = county
    _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
        {"k": _COUNTY_CACHE_KEY, "v": _county_cache},
        prefer="resolution=merge-duplicates")
    return county


def _norm_county(name: str) -> str:
    n = str(name or "").lower().strip()
    return n[:-7] if n.endswith(" county") else n


def wizard_boundary(cid: str) -> tuple[set, set] | None:
    """(declared county names, declared city names) from the onboarding
    wizard's companies.service_areas (Santino 2026-09-19: "make sure the
    service areas from the onboarding wizard get connected"). None when the
    client never filled the wizard — discovery then stays radius-only."""
    co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}"
              "&select=service_areas") or [{}])[0]
    raw = co.get("service_areas")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
    if not raw:
        return None
    counties, cities = set(), set()
    for a in raw:
        if a.get("county"):
            counties.add(_norm_county(a["county"]))
        for c in (a.get("cities") or []):
            cities.add(_norm(str(c)))
    return (counties, cities) if (counties or cities) else None


def location_plan(slug: str, cid: str) -> dict | None:
    """Target closest-20 area list + gaps, or None when geo data missing."""
    pi_p = ROOT / "clients" / slug / "plan-input.json"
    if not pi_p.exists():
        return None
    pi = json.loads(pi_p.read_text())
    brand = pi.get("brand") or {}
    lat, lng = brand.get("lat"), brand.get("lng")
    if not (lat and lng):
        return None
    state = next((a.get("state") for a in pi.get("service_areas") or []
                  if a.get("state")), None) or (brand.get("state") or "")
    if not state:
        return None
    pin = (float(lat), float(lng))

    site_cities = [(a["city"], a["state"]) for a in pi.get("service_areas") or []
                   if a.get("city")]
    prof = (_sb("GET", f"/rest/v1/marketing_gbp_profiles?company_id=eq.{cid}"
                "&select=service_areas") or [{}])[0]
    gbp_areas = [str(x) for x in (prof.get("service_areas") or [])]

    # CONGRUENCE BOUNDARY (2026-09-19): the onboarding wizard's declared
    # counties/cities bound gazetteer DISCOVERY — radius alone may never
    # invent an area outside what the client told us they serve. Explicitly
    # declared cities (wizard lists, plan-input client-declared entries) and
    # places already on the site/GBP enter as candidates regardless — facts
    # and existing state are never discovery.
    boundary = wizard_boundary(cid)
    _rejected: list[str] = []

    def _in_boundary(g: dict) -> bool:
        if boundary is None:
            return True
        counties, cities = boundary
        if _norm(g["name"]) in cities:
            return True
        county = _county_of(g["lat"], g["lng"])
        if county is None:
            return True  # fail open — unknown county never blocks silently
        ok = _norm_county(county) in counties
        if not ok and g["name"] not in _rejected:
            _rejected.append(g["name"])
        return ok

    # Candidate pool: site cities + current GBP areas + gazetteer places
    # within 30 miles, all resolved to coordinates via the gazetteer.
    gaz = gazetteer_state(state)
    by_name = {}
    for g in gaz:
        by_name.setdefault(_norm(g["name"]), g)
    cands: dict[str, dict] = {}

    def add(city: str, st: str, source: str):
        k = _city_key(city)
        if k in cands:
            cands[k]["sources"].add(source)
            return
        g = by_name.get(k)
        if not g:
            return  # no coordinates -> cannot rank; skipped (rare)
        d = _dist_mi(pin, (g["lat"], g["lng"]))
        cands[k] = {"city": g["name"], "state": st or g["state"],
                    "mi": round(d, 1), "sources": {source}}

    for c, st in site_cities:
        add(c, st, "site")
    for area in gbp_areas:
        m = re.match(r"(.+?),\s*([A-Z]{2})", area)
        if m and m.group(2).upper() == state.upper():
            add(m.group(1), m.group(2), "gbp")
        elif m:
            # out-of-state / far region on the profile (the RX Lee County
            # class) — keep it visible in the plan as a displacement target
            k = _city_key(area)
            cands[k] = {"city": m.group(1), "state": m.group(2), "mi": 9999.0,
                        "sources": {"gbp"}}
    for g in gaz:
        # Fill-to-20 candidates must be REAL cities a customer would name —
        # incorporated places of meaningful size. Tiny CDP pockets
        # (Boulevard Gardens, 0.3 sqmi) would otherwise crowd out
        # Hollywood-class cities on pure distance.
        if g.get("cdp") and g.get("sqmi", 0) < 3.0:
            continue
        if g.get("sqmi", 0) < 1.5:
            continue
        d = _dist_mi(pin, (g["lat"], g["lng"]))
        if d <= 30:
            if _in_boundary(g):
                add(g["name"], g["state"], "gazetteer")

    # SPARSE-MARKET WIDENING (ACS/West Texas 2026-09-19): a 30-mile ring in
    # Midland-Odessa yields 11 candidates, so the profile can never reach
    # its 20 slots and cities the client actually serves (Alfredo named
    # Monahans on the sales call) sit outside the ring. When the pool is
    # short of 20, widen in 10-mile steps to at most 60 miles — dense
    # metros never trigger this (they fill at 30), rural clients get the
    # real trade area they drive.
    ring = 30
    while len(cands) < 20 and ring < 60:
        ring += 10
        for g in gaz:
            if g.get("cdp") and g.get("sqmi", 0) < 3.0:
                continue
            if g.get("sqmi", 0) < 1.5:
                continue
            d = _dist_mi(pin, (g["lat"], g["lng"]))
            if d <= ring and _in_boundary(g):
                add(g["name"], g["state"], "gazetteer")

    if boundary is not None and _rejected:
        print(f"    boundary: {len(_rejected)} gazetteer place(s) outside "
              f"declared counties skipped: {', '.join(_rejected[:6])}"
              + (" ..." if len(_rejected) > 6 else ""))

    # HOME-COUNTY KEEP: a county area already on the profile that contains
    # the pin (e.g. Broward County for a Davie pin) is broad coverage worth
    # its slot — it stays pinned at the head of the list; out-of-market
    # counties (Lee County from a Davie pin) still get displaced.
    pinned = []
    try:
        # FCC census-area lookup: free, returns the county for a lat/lng.
        r = requests.get("https://geo.fcc.gov/api/census/area",
                         params={"lat": pin[0], "lon": pin[1],
                                 "format": "json"}, timeout=10)
        cname = ((r.json().get("results") or [{}])[0].get("county_name") or "")
        home_county = _norm(cname.replace(" County", ""))
    except Exception:
        home_county = ""
    for area in list(gbp_areas):
        m = re.match(r"(.+?) County,\s*([A-Z]{2})", area)
        if m and home_county and _norm(m.group(1)) == home_county:
            pinned.append({"city": f"{m.group(1)} County", "state": m.group(2),
                           "mi": 0.0, "sources": {"gbp", "home-county"}})
            cands.pop(_city_key(area), None)
    # DEMAND-WEIGHTED TIEBREAK (Santino 2026-09-17, "suggestion A"):
    # distance stays primary, but within the same ~1.5-mile band the BIGGER
    # place wins the slot (land area as the size proxy — instant, no API).
    # Still fully deterministic: band -> size desc -> name, so re-runs can
    # never churn the list.
    def _size(c):
        g = by_name.get(_city_key(c["city"]))
        return (g or {}).get("sqmi", 0.0)
    ranked = sorted(cands.values(),
                    key=lambda c: (round(c["mi"] / 1.5), -_size(c), c["city"]))
    target = (pinned + ranked)[:MAX_AREAS]
    target_set = {_city_key(f"{c['city']}")
                  for c in target}
    gbp_set = {_city_key(a) for a in gbp_areas}
    site_set = {_city_key(c) for c, _ in site_cities}
    return {
        "target": target,
        "gbp_areas": gbp_areas,
        "to_add": [c for c in target if _city_key(c["city"]) not in gbp_set],
        "to_drop": [a for a in gbp_areas if _city_key(a) not in target_set],
        "site_missing": [c for c in target
                         if _city_key(c["city"]) not in site_set
                         and not c["city"].endswith(" County")],
    }


# placeId resolution (2026-09-18 WIPE POSTMORTEM): name-only placeInfos
# returned 200 on some profiles and then resolved to NOTHING server-side —
# RestorationXpress's 14 areas were silently erased by a write Google
# acknowledged. Every place we write now carries a geocoded placeId, and
# the write path has two hard guards: never send fewer real places than
# the profile already has, and read the serviceArea BACK after the write —
# a shrunken result restores the pre-write set immediately.
GEO_KEY_PATH = ROOT / ".secrets" / "geocoding-key"
_GEO_CACHE_KEY = "geocode-place-ids"
_geo_cache: dict | None = None


def _geo_key() -> str:
    if os.environ.get("GEOCODING_API_KEY"):
        return os.environ["GEOCODING_API_KEY"]
    if GEO_KEY_PATH.exists():
        return GEO_KEY_PATH.read_text().strip()
    return ""


def _resolve_place(city: str, state: str) -> dict | None:
    """-> {placeName, placeId} via the Geocoding API, cached in ops_kv."""
    global _geo_cache
    if _geo_cache is None:
        rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{_GEO_CACHE_KEY}&select=v") or []
        _geo_cache = (rows[0].get("v") if rows else {}) or {}
    key = f"{city}, {state}"
    if key in _geo_cache:
        return _geo_cache[key] or None
    api_key = _geo_key()
    if not api_key:
        return None
    try:
        r = requests.get("https://maps.googleapis.com/maps/api/geocode/json",
                         params={"address": key, "components": "country:US",
                                 "key": api_key}, timeout=20)
        res = (r.json().get("results") or [{}])[0]
        hit = ({"placeName": res["formatted_address"].removesuffix(", USA"),
                "placeId": res["place_id"]}
               if res.get("place_id") else None)
    except Exception:  # noqa: BLE001 — resolution failure = skip this city
        return None    # (NOT cached, so a transient error retries next run)
    _geo_cache[key] = hit
    _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
        {"k": _GEO_CACHE_KEY, "v": _geo_cache},
        prefer="resolution=merge-duplicates")
    return hit


def write_service_area(slug: str, cid: str, target: list[dict]) -> str:
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    token = gbp.get_access_token(cid)
    place = brand.get("place_id") or gbp._place_id_from_connection(cid)
    if not (token and place):
        return "skip (no token/place)"
    loc = gbp.find_location(token, place)
    if not loc:
        return "skip (no location)"
    prev_sa = dict(loc.get("serviceArea") or {})
    prev_places = ((prev_sa.get("places") or {}).get("placeInfos") or [])
    infos, unresolved = [], []
    for c in target:
        hit = _resolve_place(c["city"], c["state"])
        if hit and hit["placeId"] not in {i.get("placeId") for i in infos}:
            infos.append(hit)
        elif not hit:
            unresolved.append(c["city"])
    if unresolved:
        print(f"    (geocode skipped: {', '.join(unresolved[:5])}"
              + (" ..." if len(unresolved) > 5 else "") + ")")
    # IDEMPOTENT: identical placeId set = nothing to do. Without this every
    # nightly rewrote all ~24 profiles with the same data (churn Google may
    # read as instability).
    if infos and {i["placeId"] for i in infos} == {
            pi.get("placeId") for pi in prev_places}:
        return f"in sync ({len(infos)} places)"
    # GUARD 1: never write a set smaller than what the profile holds now.
    if not infos or len(infos) < len(prev_places):
        return (f"refused (would shrink {len(prev_places)} -> {len(infos)} "
                "places — resolve more cities first)")
    sa = dict(prev_sa)
    sa.setdefault("businessType", "CUSTOMER_LOCATION_ONLY"
                  if not loc.get("storefrontAddress")
                  else "CUSTOMER_AND_BUSINESS_LOCATION")
    sa["places"] = {"placeInfos": infos}
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    v = requests.patch(f"{gbp.INFO_API}/{loc['name']}"
                       "?updateMask=serviceArea&validateOnly=true",
                       headers=hdrs, data=json.dumps({"serviceArea": sa}),
                       timeout=60)
    if v.status_code != 200:
        return f"validate failed {v.status_code}: {v.text[:140]}"
    r = requests.patch(f"{gbp.INFO_API}/{loc['name']}?updateMask=serviceArea",
                       headers=hdrs, data=json.dumps({"serviceArea": sa}),
                       timeout=60)
    if r.status_code != 200:
        return f"failed {r.status_code}: {r.text[:140]}"
    # GUARD 2: trust nothing — read it back. A 200 that resolved to fewer
    # places than we wrote is exactly the RX wipe; restore the old set.
    try:
        chk = requests.get(f"{gbp.INFO_API}/{loc['name']}?readMask=serviceArea",
                           headers=hdrs, timeout=60).json()
        got = ((chk.get("serviceArea") or {}).get("places") or {}).get("placeInfos") or []
    except Exception:  # noqa: BLE001
        got = None
    if got is not None and len(got) < len(infos):
        if prev_places:
            requests.patch(f"{gbp.INFO_API}/{loc['name']}?updateMask=serviceArea",
                           headers=hdrs,
                           data=json.dumps({"serviceArea": prev_sa}), timeout=60)
        return (f"WIPE GUARD: wrote {len(infos)} but Google kept "
                f"{len(got)} — restored previous {len(prev_places)}")
    return f"updated ({len(infos)} places, verified)"


def service_parity(slug: str, cid: str, terms: list[str], apply: bool) -> dict:
    prof = (_sb("GET", f"/rest/v1/marketing_gbp_profiles?company_id=eq.{cid}"
                "&select=reconcile_gbp_without_page,reconcile_site_without_gbp")
            or [{}])[0]
    gbp_no_page = [s for s in (prof.get("reconcile_gbp_without_page") or [])
                   if is_protected(s, terms)]  # real services only, junk never pages
    site_no_gbp = list(prof.get("reconcile_site_without_gbp") or [])
    out = {"pages_queued": 0, "gbp_adds_staged": 0,
           "gbp_without_page": gbp_no_page, "site_without_gbp": site_no_gbp}
    if not apply:
        return out
    existing = _sb("GET", f"/rest/v1/marketing_page_requests?company_id=eq.{cid}"
                   "&select=service,status") or []
    # ANY existing row blocks a re-insert: the table is unique on
    # (company_id, service), and a row in a status outside the old filter
    # 409'd the whole client on the first fleet outing (Arch 2026-09-18).
    have = {_norm(r.get("service", "")) for r in existing}
    for svc in gbp_no_page[:5]:  # cap per night — the drain builds+deploys each
        if _norm(svc) in have:
            continue
        try:
            _sb("POST", "/rest/v1/marketing_page_requests",
                {"company_id": cid, "service": svc, "status": "queued"},
                prefer="return=minimal")
            out["pages_queued"] += 1
        except Exception as e:  # noqa: BLE001 — one dup must not kill the client
            print(f"    page queue skip ({svc}): {str(e)[:80]}")
    sugg = _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
               "&item_type=eq.service&select=item,status") or []
    known = {_norm(s["item"]) for s in sugg}
    for svc in site_no_gbp:
        if _norm(svc) in known:
            continue
        _sb("POST", "/rest/v1/marketing_gbp_suggestions",
            {"company_id": cid, "item": svc, "item_type": "service",
             "status": "open", "verdict": "ADD", "auto_safe": True,
             "source": "parity", "confidence": 0.9,
             "reason": "site page exists with no matching GBP service (parity engine)"},
            prefer="return=minimal")
        out["gbp_adds_staged"] += 1
    return out




def _active_cids() -> set:
    """Companies the engines may touch. Cancelled/departed clients (Mold
    Solutionz class, dead 09-09) must never be staged, applied, or written
    to — 70 of its suggestions were sitting open because nothing filtered."""
    return {c["id"] for c in _sb(
        "GET", "/rest/v1/companies?status=eq.Active&select=id") or []}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply-site", action="store_true",
                    help="also append missing target cities to plan-input (render cost)")
    ap.add_argument("--max-new-cities", type=int, default=1)
    a = ap.parse_args()
    apply = a.apply and not a.dry_run
    terms = _catalog_terms()
    inv = {s: c for c, s in slug_map().items()}
    slugs = [a.slug] if a.slug else sorted(inv)
    ledger: dict = {}
    active = _active_cids()

    for slug in slugs:
        cid = inv.get(slug)
        if not cid or cid not in active:
            continue
        try:
            lp = location_plan(slug, cid)
            sp = service_parity(slug, cid, terms, apply)
        except Exception as e:  # noqa: BLE001
            print(f"{slug}: ERROR {str(e)[:140]}")
            continue
        if lp is None and not (sp["gbp_without_page"] or sp["site_without_gbp"]):
            continue
        print(f"\n== {slug}")
        entry: dict = {"services": {
            "gbp_without_page": len(sp["gbp_without_page"]),
            "site_without_gbp": len(sp["site_without_gbp"]),
            "pages_queued": sp["pages_queued"],
            "gbp_adds_staged": sp["gbp_adds_staged"]}}
        if sp["gbp_without_page"]:
            print(f"  services: {len(sp['gbp_without_page'])} real GBP service(s) "
                  f"lack a site page (queued {sp['pages_queued']} tonight)")
        if sp["site_without_gbp"]:
            print(f"  services: {len(sp['site_without_gbp'])} site service(s) "
                  f"missing on GBP -> staged {sp['gbp_adds_staged']} ADD(s)")
        if lp:
            n_target = len(lp["target"])
            print(f"  areas: GBP has {len(lp['gbp_areas'])}/{MAX_AREAS}; target "
                  f"closest-{n_target}: +{len(lp['to_add'])} / -{len(lp['to_drop'])}")
            if lp["to_add"]:
                print("    add: " + ", ".join(f"{c['city']} ({c['mi']}mi)"
                                              for c in lp["to_add"][:8]))
            if lp["to_drop"]:
                print("    drop (too far): " + ", ".join(lp["to_drop"][:6]))
            if lp["site_missing"]:
                print(f"    site pages missing for {len(lp['site_missing'])} "
                      "target cities: "
                      + ", ".join(c["city"] for c in lp["site_missing"][:8]))
            entry["areas"] = {"gbp": len(lp["gbp_areas"]),
                              "target": n_target,
                              "to_add": len(lp["to_add"]),
                              "to_drop": len(lp["to_drop"]),
                              "site_missing": len(lp["site_missing"])}
            if apply and (lp["to_add"] or lp["to_drop"]):
                msg = write_service_area(slug, cid, lp["target"])
                print(f"    GBP serviceArea -> {msg}")
                entry["areas"]["write"] = msg
            if apply and a.apply_site and lp["site_missing"]:
                pi_p = ROOT / "clients" / slug / "plan-input.json"
                pi = json.loads(pi_p.read_text())
                for c in lp["site_missing"][:a.max_new_cities]:
                    pi.setdefault("service_areas", []).append(
                        {"city": c["city"], "state": c["state"],
                         "slug": re.sub(r"[^a-z0-9]+", "-",
                                        f"{c['city']} {c['state']}".lower()).strip("-")})
                    print(f"    site: appended {c['city']} to plan-input "
                          "(next build ripples the pages)")
                pi_p.write_text(json.dumps(pi, indent=2) + "\n")
        ledger[cid] = entry

    if not a.dry_run and not a.slug:
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": "parity-ledger",
             "v": {"clients": ledger,
                   "at": datetime.now(timezone.utc).isoformat()}},
            prefer="resolution=merge-duplicates")
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": "heartbeat:parity",
             "v": {"at": datetime.now(timezone.utc).isoformat()}},
            prefer="resolution=merge-duplicates")
        print(f"\nparity ledger mirrored ({len(ledger)} client(s)) + heartbeat stamped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
