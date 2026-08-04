#!/usr/bin/env python3
"""
Rank AI — Geo-grid bi-weekly cron (System: local map rankings).

Every 2 weeks, for each active client that has a geo-grid config, scans every
(keyword × city) and writes a NEW scan row + its points to Supabase, renders a
static PNG, and uploads it to R2. Scans are never overwritten — the accumulating
history is exactly what powers the dashboard's "Compare" (before/after) view.

Config per client (same files the report builder reads):
    clients/{slug}/geogrid-keywords.txt   one keyword per line
    clients/{slug}/geogrid-cities.json    [{"label","lat","lng"}, ...]

A client with neither file is skipped. Runs on Railway (railway.geogrid-cron.toml),
schedule "every 2 weeks". Reuses scan_and_store() — the same unit of work the
POST /geogrid/scan endpoint uses.

Usage:
    python3 scripts/geogrid_cron.py                 # all configured clients
    python3 scripts/geogrid_cron.py --slug narestco # one client
    python3 scripts/geogrid_cron.py --dry-run       # list the work, scan nothing
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from geogrid_store import COMPANY_MAP, sb_client, scan_and_store  # noqa: E402


def load_config(slug: str) -> tuple[list[str], list[dict]]:
    kw_f = ROOT / "clients" / slug / "geogrid-keywords.txt"
    ct_f = ROOT / "clients" / slug / "geogrid-cities.json"
    keywords = [ln.strip() for ln in kw_f.read_text().splitlines() if ln.strip()] if kw_f.exists() else []
    cities = json.loads(ct_f.read_text()) if ct_f.exists() else []
    return keywords, cities


def run_client(sb, slug: str, dry_run: bool) -> dict:
    keywords, cities = load_config(slug)
    if not keywords or not cities:
        print(f"  [{slug}] SKIP — no geogrid-keywords.txt / geogrid-cities.json")
        return {"slug": slug, "scans": 0, "cost": 0.0, "skipped": True}

    # Per-city radius list (Santino 2026-07-26: 9.5mi standard, 15mi wide view
    # for metro home cities). "miles_list" on a city entry; absent = [9.5].
    pairs = [(kw, c, m) for kw in keywords for c in cities
             for m in (c.get("miles_list") or [9.5])]
    print(f"  [{slug}] {len(keywords)} keywords × {len(cities)} cities/radii = {len(pairs)} scans")
    if dry_run:
        for kw, c, m in pairs:
            print(f"      WOULD scan: '{kw}' @ {c['label']} ({m}mi)")
        return {"slug": slug, "scans": len(pairs), "cost": 0.0, "skipped": False, "dry": True}

    scans, cost, fails = 0, 0.0, 0
    for kw, c, m in pairs:
        try:
            row = scan_and_store(sb, slug, kw, c, miles=m)
            scans += 1
            cost += float(row.get("cost_usd") or 0.0)
            print(f"      ok: '{kw}' @ {c['label']} | avg={row.get('avg_rank')} "
                  f"top3={row.get('pct_in_top3')}% found={row.get('found_points')}/{row.get('total_points')}")
        except Exception as e:
            fails += 1
            sys.stderr.write(f"      FAIL: '{kw}' @ {c['label']} ({m}mi): {str(e)[:200]}\n")
        time.sleep(1)  # gentle pacing between scans
    print(f"  [{slug}] done — {scans} scans, {fails} failed, ${cost:.2f}")
    return {"slug": slug, "scans": scans, "cost": cost, "fails": fails, "skipped": False}


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank AI geo-grid bi-weekly cron")
    ap.add_argument("--slug", help="Run a single client (default: all configured)")
    ap.add_argument("--dry-run", action="store_true", help="List the work, scan nothing")
    args = ap.parse_args()

    slugs = [args.slug] if args.slug else list(COMPANY_MAP.keys())
    # ACCOUNT-STATUS GATE (Santino 2026-08-04: Mold Solutionz paused — it has
    # geo-grid config + a company_map entry, so the cron would have kept
    # burning DataForSEO spend on a cancelled client). companies.status is
    # the pause button's single source of truth; local clients/*.json status
    # is not updated by the app. Fail-open: if the status read errors, keep
    # the full roster rather than silently skipping paying clients.
    try:
        rows = (sb_client().table("companies")
                .select("id,status")
                .in_("id", [COMPANY_MAP[s] for s in slugs if s in COMPANY_MAP])
                .execute().data or [])
        inactive = {"paused", "cancelled", "canceled", "churned", "inactive",
                    "archived"}
        bad = {r["id"] for r in rows
               if str(r.get("status") or "").strip().lower() in inactive}
        for s in [s for s in slugs if COMPANY_MAP.get(s) in bad]:
            print(f"  [{s}] SKIP — account paused/cancelled (companies.status)")
            slugs.remove(s)
    except Exception as e:  # noqa: BLE001 — gate must never kill the cron
        print(f"  [status-gate] check failed ({str(e)[:80]}) — running full roster")
    mode = "DRY RUN" if args.dry_run else "RUN"
    print(f"geogrid_cron — {mode} — {len(slugs)} client(s): {', '.join(slugs)}")

    sb = None if args.dry_run else sb_client()
    total_scans, total_cost = 0, 0.0
    for slug in slugs:
        r = run_client(sb, slug, args.dry_run)
        total_scans += r["scans"]
        total_cost += r["cost"]

    print(f"\nDone. {total_scans} scans across {len(slugs)} client(s). DataForSEO spend: ${total_cost:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
