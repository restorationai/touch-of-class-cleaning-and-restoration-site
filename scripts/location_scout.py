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

ROOT = Path(__file__).resolve().parents[1]
CLIENTS_DIR = ROOT / "clients"

# A pin's realistic ranking radius when we have no scan to measure. The low end
# of the published range on purpose: recommending an office too close is the
# expensive mistake, recommending one slightly too far is not.
DEFAULT_REACH_MI = 4.0

# Two offices closer than this cannibalise each other. Kept a touch above the
# reach so the radii tile rather than stack.
MIN_SEPARATION_MI = 6.0

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


def scout(slug: str) -> dict:
    data = load_client(slug)
    brand = data["plan"].get("brand") or {}
    company_id = data["rec"].get("company_id") or brand.get("company_id")
    pin = (brand.get("lat"), brand.get("lng"))
    if not pin[0]:
        raise SystemExit(f"{slug}: no brand.lat/lng in plan-input.json — cannot scout without a pin")

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
        rows.append({"city": city, "state": state, "lat": ll[0], "lng": ll[1],
                     "distance_mi": round(d, 1),
                     "covered": d <= effective_reach,
                     "primary": bool(a.get("primary"))})

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
    seats: list = []
    claimed: set = set()
    while True:
        best = None
        for cand in uncovered:
            if cand["city"] in claimed:
                continue
            if haversine_mi(pin[0], pin[1], cand["lat"], cand["lng"]) < MIN_SEPARATION_MI:
                continue                      # too close to the office they have
            if any(haversine_mi(s["lat"], s["lng"], cand["lat"], cand["lng"]) < MIN_SEPARATION_MI
                   for s in seats):
                continue                      # too close to a seat already taken
            covers = [o for o in uncovered
                      if o["city"] not in claimed
                      and haversine_mi(cand["lat"], cand["lng"], o["lat"], o["lng"]) <= effective_reach]
            score = (len(covers), -cand["distance_mi"])
            if best is None or score > best[0]:
                best = (score, cand, covers)
        if not best:
            break
        _, cand, covers = best
        for o in covers:
            claimed.add(o["city"])
        seats.append({"seat_city": cand["city"], "state": cand["state"],
                      "lat": cand["lat"], "lng": cand["lng"],
                      "distance_from_pin_mi": cand["distance_mi"],
                      "covers_count": len(covers),
                      "would_cover": sorted(o["city"] for o in covers)})

    return {"slug": slug, "company_id": company_id,
            "pin": {"lat": pin[0], "lng": pin[1],
                    "city": brand.get("city"), "state": brand.get("state")},
            "measured_reach": reach, "effective_reach_mi": effective_reach,
            "reach_source": "measured (geo-grid top-3)" if measured > 0 else
                            f"default {DEFAULT_REACH_MI}mi (no top-3 placements on record)",
            "areas": rows, "recommended_offices": seats,
            "orphans": [r["city"] for r in uncovered if r["city"] not in claimed]}


def render(res: dict, top_n: int = DEFAULT_TOP_N) -> None:
    pin = res["pin"]
    print(f"\nLOCATION SCOUT — {res['slug']}")
    print(f"  current pin: {pin.get('city')}, {pin.get('state')}  ({pin['lat']:.4f}, {pin['lng']:.4f})")
    print(f"  ranking reach in use: {res['effective_reach_mi']} mi  [{res['reach_source']}]")
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
          f"  [>= {MIN_SEPARATION_MI}mi apart, no overlap]")
    if not shortlist:
        print("    none — every target area is already inside the current pin's reach")
    for i, s in enumerate(shortlist, 1):
        print(f"    {i}. {s['seat_city']}, {s['state']}  "
              f"({s['distance_from_pin_mi']}mi out) — covers {s['covers_count']} target town(s)")
        print(f"       {', '.join(s['would_cover'])}")
    rest = res["recommended_offices"][top_n:]
    if rest:
        print(f"\n    also viable, lower coverage: "
              + ", ".join(f"{s['seat_city']} ({s['covers_count']})" for s in rest[:8]))
    if res["orphans"]:
        print(f"\n  NOT COVERED even by the above: {', '.join(res['orphans'])}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=DEFAULT_TOP_N, help="how many offices to shortlist")
    a = ap.parse_args()
    res = scout(a.slug)
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        render(res, a.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
