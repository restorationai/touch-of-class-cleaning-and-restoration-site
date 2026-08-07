#!/usr/bin/env python3
"""location_scout.py — where a SECOND office would have to go to be worth it.

Phase 1: coverage inversion (Santino 2026-08-06).

THE PROBLEM THIS SOLVES
-----------------------
One Google Business Profile only ranks so far. Sterling Sky's testing and the
multi-location operators both put it at roughly 2-5 miles in a competitive
metro and 5-10 in a softer one, and NOTHING fixes that from where you stand:
service areas are cosmetic, reviews and links do not extend the radius. The
only lever is another pin.

So the question a client actually needs answered is not "which building" — they
will take whatever unit they can lease. It is "which TOWNS are far enough from
my current pin to be worth an office, and near enough to each other that one
office covers several of them". This produces that shortlist.

WHAT IT USES (deliberately nothing new)
---------------------------------------
  * clients/{slug}/plan-input.json  — the pin (brand.lat/lng) and the target
    service_areas the client already told us they want.
  * marketing_geogrid_scans/_points — the MEASURED reach, when a scan exists.
    Rather than assume 2-5 miles, read how far out the client actually still
    ranks. Coastal ranks nowhere in the top 3 across their own 9.5-mile grid,
    which is worth knowing before anyone signs a lease.
  * Free Nominatim geocoding for target towns (same helper the lead audit
    uses). No new API keys, no paid calls.

NON-OVERLAP
-----------
Two pins inside each other's radius compete with themselves and waste the
lease. Recommendations are clustered so that every proposed office sits at
least MIN_SEPARATION_MI from the existing pin and from every other
recommendation, and each one is credited with the target towns it would cover.

Usage:
    python3 scripts/location_scout.py --slug coastal-restoration-services
    python3 scripts/location_scout.py --slug narestco --json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from census_demand import demographics, demand_score, key_status, opportunity  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CLIENTS_DIR = ROOT / "clients"

# A pin's realistic ranking radius when we have no scan to measure. The low end
# of the published range on purpose: recommending an office too close is the
# expensive mistake, recommending one slightly too far is not.
DEFAULT_REACH_MI = 4.0

# Two offices closer than this cannibalise each other. It MUST equal the reach,
# not exceed it (fixed 2026-08-06). A fixed 6mi against a 4mi reach created a
# dead zone: any town 4-6mi from an accepted seat was too far to be covered by
# it and too close to be its own seat, so it vanished from the report entirely.
# Templeton sits 4.6mi from Paso Robles and 5.2mi from Atascadero, so taking
# Templeton silently deleted both — the two biggest markets in that corner.
# Circles exactly one reach apart are tangent: no overlap, no gap.
MIN_SEPARATION_MI = 6.0   # fallback only; the run uses the measured reach

# A "service area" further than this from the pin is a bad geocode, not a real
# target. Nominatim returned a Blacklake 2,421 miles from Santa Maria.
MAX_PLAUSIBLE_AREA_MI = 150.0

# Nobody opens seventeen offices. Rank the candidates and show the shortlist.
DEFAULT_TOP_N = 3

UA = {"User-Agent": "RankAI-LocationScout/1.0 (ops@restorationai.io)"}


def haversine_mi(a_lat, a_lng, b_lat, b_lng) -> float:
    R = 3958.8
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _sb(path: str):
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return []
    req = urllib.request.Request(url + path, headers={"apikey": key, "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except Exception:
        return []


def geocode(city: str, state: str) -> tuple | None:
    """Free Nominatim lookup. Rate-limited by courtesy sleep in the caller."""
    q = urllib.parse.urlencode({"q": f"{city}, {state}, USA", "format": "json", "limit": 1})
    req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}", headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            js = json.load(r)
        return (float(js[0]["lat"]), float(js[0]["lon"])) if js else None
    except Exception:
        return None


def measured_reach(company_id: str) -> dict:
    """How far the client ACTUALLY ranks, from the newest scan per keyword.

    Returns {keyword: {"top3_mi": x, "top10_mi": y, "avg_rank": z}}. A radius of
    0.0 means they never place that well anywhere on the grid — the honest and
    common answer, and the one that says a second pin is not the first problem.
    """
    scans = _sb(f"/rest/v1/marketing_geogrid_scans?select=*&company_id=eq.{company_id}"
                "&order=scanned_at.desc&limit=20")
    out: dict = {}
    for s in scans:
        kw = s.get("keyword") or "?"
        if kw in out:            # newest wins
            continue
        pts = _sb(f"/rest/v1/marketing_geogrid_points?select=lat,lng,rank,found&scan_id=eq.{s['id']}&limit=500")
        c_lat, c_lng = s.get("center_lat"), s.get("center_lng")
        top3 = top10 = 0.0
        for p in pts:
            if not p.get("found") or p.get("rank") is None:
                continue
            if c_lat is None or p.get("lat") is None:
                continue
            d = haversine_mi(c_lat, c_lng, p["lat"], p["lng"])
            if p["rank"] <= 3:
                top3 = max(top3, d)
            if p["rank"] <= 10:
                top10 = max(top10, d)
        out[kw] = {"top3_mi": round(top3, 1), "top10_mi": round(top10, 1),
                   "avg_rank": s.get("avg_rank"), "grid_mi": s.get("miles"),
                   "pct_top3": s.get("pct_in_top3")}
    return out


def load_client(slug: str) -> dict:
    plan = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text())
    rec_path = CLIENTS_DIR / f"{slug}.json"
    rec = json.loads(rec_path.read_text()) if rec_path.exists() else {}
    return {"plan": plan, "rec": rec}


def scout(slug: str, with_census: bool = True) -> dict:
    data = load_client(slug)
    brand = data["plan"].get("brand") or {}
    # clients/{slug}.json often has no company_id — clients/company_map.json is
    # the fallback the rest of the repo uses (gbp.company_id_for).
    company_id = data["rec"].get("company_id") or brand.get("company_id")
    if not company_id:
        cmap = CLIENTS_DIR / "company_map.json"
        if cmap.exists():
            try:
                company_id = json.loads(cmap.read_text()).get(slug)
            except Exception:
                pass
    # plan-input.json is hand-and-machine written, so the pin arrives as either
    # numbers or strings — narestco and restoration-groups both store "47.337"
    # and the haversine blew up with "must be real number, not str" (2026-08-06).
    def _f(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    pin = (_f(brand.get("lat")), _f(brand.get("lng")))
    if pin[0] is None or pin[1] is None:
        raise SystemExit(f"{slug}: no usable brand.lat/lng in plan-input.json "
                         f"(got {brand.get('lat')!r}/{brand.get('lng')!r}) — cannot scout without a pin")

    reach = measured_reach(company_id) if company_id else {}
    # Use the best MEASURED top-3 reach when we have one; otherwise the default.
    measured = max([v["top3_mi"] for v in reach.values()], default=0.0)
    effective_reach = measured if measured > 0 else DEFAULT_REACH_MI

    areas = data["plan"].get("service_areas") or []
    rows = []
    for a in areas:
        city, state = a.get("city"), a.get("state") or ""
        if not city:
            continue
        ll = geocode(city, state)
        time.sleep(1.1)                      # Nominatim courtesy
        if not ll:
            rows.append({"city": city, "state": state, "lat": None, "lng": None,
                         "distance_mi": None, "covered": None, "note": "could not geocode"})
            continue
        d = haversine_mi(pin[0], pin[1], ll[0], ll[1])
        # Nominatim happily returns a same-named place on another continent —
        # it put Coastal's "Blacklake" 2,421 miles away. A service area that
        # far is not a geocoding result, it is a wrong match; drop it rather
        # than let it become a recommended office.
        if d > MAX_PLAUSIBLE_AREA_MI:
            rows.append({"city": city, "state": state, "lat": None, "lng": None,
                         "distance_mi": None, "covered": None,
                         "note": f"geocoded {int(d)}mi away — wrong match, ignored"})
            continue
        # Phase 2: is this town worth serving, not just reachable? Silently None
        # without CENSUS_API_KEY, and the whole report falls back to geometry.
        demo = demographics(ll[0], ll[1]) if with_census else None
        rows.append({"city": city, "state": state, "lat": ll[0], "lng": ll[1],
                     "distance_mi": round(d, 1),
                     "covered": d <= effective_reach,
                     "primary": bool(a.get("primary")),
                     "demographics": demo,
                     "demand": demand_score(demo)})

    # Cluster the uncovered towns into offices. HIGHEST-COVERAGE first, not
    # farthest first: an office is worth its lease by how many target towns it
    # brings inside the radius, so the seat that covers five towns beats the one
    # that covers only itself. (The first pass sorted by distance and returned
    # seventeen single-town offices, which is not advice.)
    #
    # Every town is a candidate seat. Score it by how many still-unclaimed towns
    # fall within one reach, tie-break toward the closer one — a closer office is
    # cheaper to run and easier to staff. Then take seats greedily, skipping any
    # that sit within MIN_SEPARATION_MI of the existing pin or an accepted seat.
    uncovered = [r for r in rows if r.get("covered") is False]
    separation = effective_reach          # tangent, so nothing falls in a gap
    seats: list = []
    claimed: set = set()
    while True:
        best = None
        for cand in uncovered:
            if cand["city"] in claimed:
                continue
            if haversine_mi(pin[0], pin[1], cand["lat"], cand["lng"]) < separation:
                continue                      # too close to the office they have
            if any(haversine_mi(s["lat"], s["lng"], cand["lat"], cand["lng"]) < separation
                   for s in seats):
                continue                      # too close to a seat already taken
            covers = [o for o in uncovered
                      if o["city"] not in claimed
                      and haversine_mi(cand["lat"], cand["lng"], o["lat"], o["lng"]) <= effective_reach]
            # Rank by EXPECTED VALUE, not town-count (2026-08-06). Counting
            # towns and nudging with a quality score let Avila Beach — 1,365
            # people — outrank Orcutt at 31,284, and let Templeton (8,608)
            # take a seat that then blocked Paso Robles and Atascadero. An
            # office is worth its lease by the addressable market it reaches:
            # population x per-household quality, summed. Falls back to plain
            # town-count when there is no census data at all.
            opp = sum(opportunity(o.get("demographics")) for o in covers)
            weight = opp if opp > 0 else float(len(covers))
            score = (round(weight, 3), -cand["distance_mi"])
            if best is None or score > best[0]:
                best = (score, cand, covers)
        if not best:
            break
        _, cand, covers = best
        for o in covers:
            claimed.add(o["city"])
        seat_demand = [(o.get("demand") or {}).get("score") for o in covers]
        seat_demand = [x for x in seat_demand if x is not None]
        # The SEAT's own demographics understate the market badly when the seat
        # is a hamlet serving bigger neighbours — Ballard has 796 residents but
        # covers Solvang, Santa Ynez and Los Olivos. Sum the cluster.
        pops = [(o.get("demographics") or {}).get("population") for o in covers]
        pops = [p for p in pops if p]
        incs = [(o.get("demographics") or {}).get("median_household_income") for o in covers]
        incs = [i for i in incs if i]
        seats.append({"seat_city": cand["city"], "state": cand["state"],
                      "lat": cand["lat"], "lng": cand["lng"],
                      "distance_from_pin_mi": cand["distance_mi"],
                      "covers_count": len(covers),
                      "demand_weighted": round(best[0][0], 2),
                      "avg_demand": round(sum(seat_demand) / len(seat_demand), 1) if seat_demand else None,
                      "opportunity": round(sum(opportunity(o.get("demographics")) for o in covers), 1),
                      "seat_demographics": cand.get("demographics"),
                      "cluster_population": int(sum(pops)) if pops else None,
                      "cluster_median_income": int(sum(incs) / len(incs)) if incs else None,
                      "would_cover": sorted(o["city"] for o in covers)})

    return {"slug": slug, "company_id": company_id,
            "pin": {"lat": pin[0], "lng": pin[1],
                    "city": brand.get("city"), "state": brand.get("state")},
            "measured_reach": reach, "effective_reach_mi": effective_reach,
            "reach_source": "measured (geo-grid top-3)" if measured > 0 else
                            f"default {DEFAULT_REACH_MI}mi (no top-3 placements on record)",
            "areas": rows, "recommended_offices": seats,
            "orphans": [r["city"] for r in uncovered if r["city"] not in claimed]}


def save(res: dict) -> int:
    """Replace this company's shortlist in marketing_location_scout.

    The app cannot run this script — it needs geo-grid points, Nominatim and the
    Census ACS — so the CLI writes the result and the Locations tab reads it.
    Same split the geo-grid already uses. Replace rather than append: the table
    holds the CURRENT shortlist, not a history nobody opens.
    """
    cid = res.get("company_id")
    if not cid:
        print("  not saved: no company_id on the client record")
        return 0
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("  not saved: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
        return 0
    H = {"apikey": key, "Authorization": f"Bearer {key}",
         "Content-Type": "application/json", "Prefer": "return=minimal"}
    req = urllib.request.Request(
        f"{url}/rest/v1/marketing_location_scout?company_id=eq.{cid}",
        headers=H, method="DELETE")
    try:
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print(f"  not saved: could not clear previous run ({str(e)[:90]})")
        return 0
    rows = []
    for i, s_ in enumerate(res.get("recommended_offices") or [], 1):
        rows.append({
            "company_id": cid, "rank": i,
            "seat_city": s_["seat_city"], "state": s_.get("state"),
            "lat": s_.get("lat"), "lng": s_.get("lng"),
            "distance_from_pin_mi": s_.get("distance_from_pin_mi"),
            "covers_count": s_.get("covers_count"),
            "would_cover": s_.get("would_cover") or [],
            "avg_demand": s_.get("avg_demand"),
            "cluster_population": s_.get("cluster_population"),
            "cluster_median_income": s_.get("cluster_median_income"),
            "seat_demographics": s_.get("seat_demographics"),
            "effective_reach_mi": res.get("effective_reach_mi"),
            "reach_source": res.get("reach_source"),
        })
    if not rows:
        print("  saved: 0 recommendations (nothing outside the current reach)")
        return 0
    req = urllib.request.Request(f"{url}/rest/v1/marketing_location_scout",
                                 data=json.dumps(rows).encode(), headers=H, method="POST")
    try:
        urllib.request.urlopen(req, timeout=30)
        print(f"  saved {len(rows)} recommendation(s) to marketing_location_scout")
        return len(rows)
    except Exception as e:
        body = e.read().decode()[:200] if hasattr(e, "read") else str(e)[:200]
        print(f"  not saved: {body}")
        return 0


def render(res: dict, top_n: int = DEFAULT_TOP_N) -> None:
    pin = res["pin"]
    print(f"\nLOCATION SCOUT — {res['slug']}")
    print(f"  current pin: {pin.get('city')}, {pin.get('state')}  ({pin['lat']:.4f}, {pin['lng']:.4f})")
    print(f"  ranking reach in use: {res['effective_reach_mi']} mi  [{res['reach_source']}]")
    state, why = key_status()
    if state == "ok":
        print("  demand data: ON  (population, income, owner-occupancy, home value, housing age)")
    else:
        print(f"  demand data: OFF [{state}] — {why}")
        print("               ranking below is geometry only until that is fixed")
    if res["measured_reach"]:
        print("\n  MEASURED TODAY")
        for kw, m in res["measured_reach"].items():
            print(f"    {kw[:44]:<46} avg rank {str(m['avg_rank']):<6} "
                  f"top-3 out to {m['top3_mi']}mi, top-10 out to {m['top10_mi']}mi "
                  f"(grid {m['grid_mi']}mi)")
    print(f"\n  TARGET AREAS ({len(res['areas'])})")
    print(f"    {'CITY':<22} {'DIST':>7}  COVERED BY THE CURRENT PIN?")
    for r in sorted(res["areas"], key=lambda x: (x["distance_mi"] is None, x["distance_mi"] or 0)):
        d = f"{r['distance_mi']}mi" if r["distance_mi"] is not None else "  ?  "
        if r.get("covered") is None:
            verdict = r.get("note", "unknown")
        elif r["covered"]:
            verdict = "yes"
        else:
            verdict = "NO — outside the radius"
        star = " *" if r.get("primary") else ""
        print(f"    {r['city'][:21]:<22} {d:>7}  {verdict}{star}")
    shortlist = res["recommended_offices"][:top_n]
    print(f"\n  RECOMMENDED OFFICES — top {len(shortlist)} of {len(res['recommended_offices'])} viable"
          f"  [>= {res['effective_reach_mi']}mi apart, no overlap, ranked by addressable market]")
    if not shortlist:
        print("    none — every target area is already inside the current pin's reach")
    for i, s in enumerate(shortlist, 1):
        dem = (f", market {int(s['opportunity']):,}" if s.get("opportunity") else "") + \
              (f", quality {s['avg_demand']}/100" if s.get("avg_demand") is not None else "")
        print(f"    {i}. {s['seat_city']}, {s['state']}  "
              f"({s['distance_from_pin_mi']}mi out) — covers {s['covers_count']} target town(s){dem}")
        print(f"       {', '.join(s['would_cover'])}")
        g = s.get("seat_demographics") or {}
        def f(v, pre="", suf=""):
            return f"{pre}{v:,.0f}{suf}" if isinstance(v, (int, float)) else "n/a"
        if s.get("cluster_population") is not None:
            print(f"       cluster: {f(s['cluster_population'])} people across "
                  f"{s['covers_count']} town(s), avg income {f(s.get('cluster_median_income'), '$')}")
        if g:
            yr = g.get("median_year_built")
            print(f"       seat {s['seat_city']}: pop {f(g.get('population'))}"
                  f" | income {f(g.get('median_household_income'), '$')}"
                  f" | owner-occ {g.get('owner_occupied_pct') if g.get('owner_occupied_pct') is not None else 'n/a'}%"
                  f" | home {f(g.get('median_home_value'), '$')}"
                  f" | built {int(yr) if yr else 'n/a'}")
    rest = res["recommended_offices"][top_n:]
    if rest:
        print(f"\n    also viable, lower coverage: "
              + ", ".join(f"{s['seat_city']} ({s['covers_count']})" for s in rest[:8]))
    if res["orphans"]:
        print(f"\n  NOT COVERED even by the above: {', '.join(res['orphans'])}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", help="one client (omit with --all)")
    ap.add_argument("--all", action="store_true",
                    help="every client with a plan-input.json; implies --save")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=DEFAULT_TOP_N, help="how many offices to shortlist")
    ap.add_argument("--no-census", action="store_true", help="geometry only, skip demographics")
    ap.add_argument("--save", action="store_true", help="write the shortlist to marketing_location_scout for the app")
    a = ap.parse_args()
    if a.all:
        # Fleet run. Costs nothing but time: Nominatim, the Census ACS and the
        # Supabase reads are all free, so this is safe to schedule weekly. Each
        # client is isolated — one bad plan-input must not stop the rest.
        slugs = sorted(p.parent.name for p in CLIENTS_DIR.glob("*/plan-input.json"))
        print(f"location scout: {len(slugs)} client(s)\n")
        ok = fail = 0
        for slug in slugs:
            try:
                r = scout(slug, with_census=not a.no_census)
                n = save(r)
                print(f"  {slug:<38} {n} recommendation(s)")
                ok += 1
            except SystemExit as e:
                print(f"  {slug:<38} skipped — {str(e)[:70]}")
                fail += 1
            except Exception as e:  # noqa: BLE001
                print(f"  {slug:<38} FAILED — {type(e).__name__}: {str(e)[:60]}")
                fail += 1
        print(f"\ndone: {ok} scouted, {fail} skipped/failed")
        return 0
    if not a.slug:
        ap.error("--slug is required unless --all is given")
    res = scout(a.slug, with_census=not a.no_census)
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        render(res, a.top)
    if a.save:
        save(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
