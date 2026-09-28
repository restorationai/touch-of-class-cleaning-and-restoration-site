#!/usr/bin/env python3
"""gbp_planner_areas.py — resolve a GBP Profile Planner's service areas to
Google place IDs (queue #21, 2026-09-27).

Google rejects a serviceArea write whose placeInfos carry only a placeName
(MISSING_STOREFRONT_ADDRESS_OR_SAB on validateOnly, and the 09-18 parity
postmortem showed name-only writes can silently erase areas). The app's
gbp-planner edge function has no Geocoding key, so it resolves areas from
two stores only: the live profile's own placeIds, and the shared ops_kv
'geocode-place-ids' cache the Parity Engine maintains. This script fills
that cache for every planned area the planner reports as unresolved.

    python3 scripts/gbp_planner_areas.py --slug kenneth-w-talbot-jr
    python3 scripts/gbp_planner_areas.py --company-id CO-1788898034500

Read-only toward Google Business Profile; writes only the geocode cache.
Then press "Refresh draft" (or save) in the planner so it re-reads the cache.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gbp  # noqa: E402  (company_id_for, _sb)
import gbp_parity  # noqa: E402  (_resolve_place: Geocoding API + ops_kv cache)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--company-id")
    args = ap.parse_args()
    cid = args.company_id or (gbp.company_id_for(args.slug) if args.slug else None)
    if not cid:
        print("need --slug or --company-id", file=sys.stderr)
        return 2
    rows = gbp._sb(f"companies?id=eq.{cid}&select=integration_settings")
    plan = ((rows or [{}])[0].get("integration_settings") or {}).get("gbp_plan") or {}
    areas = plan.get("service_areas") or []
    if not areas:
        print(f"{cid}: no planned service areas (run Refresh draft in the planner first)")
        return 1
    bad = 0
    for name in areas:
        city, _, state = str(name).rpartition(",")
        if not city:
            # e.g. "Chicago Metropolitan Area": only valid when the live
            # profile already carries its placeId (the planner uses that).
            print(f"  -- {name}: not 'City, ST', skipped (planner uses the live profile's place ID if it has one)")
            continue
        hit = gbp_parity._resolve_place(city.strip(), state.strip())
        if hit:
            print(f"  ok {name} -> {hit['placeName']} ({hit['placeId']})")
        else:
            print(f"  !! {name}: no Google place found")
            bad += 1
    print(f"{cid}: {len(areas) - bad}/{len(areas)} areas resolved into ops_kv geocode-place-ids")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
