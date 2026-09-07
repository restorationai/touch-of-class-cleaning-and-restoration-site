#!/usr/bin/env python3
"""backlink_tracker.py — monthly per-client backlink + Domain Rating snapshot.

The measurement half of the backlink program (Santino 2026-09-06): every
press release, citation batch, directory listing and podcast feed should show
up as MOVEMENT a client can see. One row per client per month in
marketing_backlink_snapshots, rendered on the app's Reports tab.

Sources:
  - DataForSEO Backlinks summary (existing account): total backlinks +
    referring domains. ~$0.02/query — pennies fleet-wide.
  - Ahrefs free Domain Rating endpoint (AHREFS_API_KEY): the DR number
    clients recognize. Skipped gracefully until the key exists. Display of
    DR anywhere client-facing must carry "Domain Rating by Ahrefs"
    (license requirement).

Self-gating: skips a client whose latest snapshot is younger than 28 days,
so a daily cron tick yields monthly snapshots (progress_report.py pattern).

Usage:
  python3 scripts/backlink_tracker.py            # all live-domain clients
  python3 scripts/backlink_tracker.py --slug X   # one client (gate ignored)
  python3 scripts/backlink_tracker.py --dry-run
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")
import requests  # noqa: E402

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HDR = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
       "Content-Type": "application/json"}


def _dfs_auth() -> str:
    import geogrid_scan as gs  # env OR ~/.claude.json MCP creds fallback
    u, p = gs.load_dfs_creds()
    return base64.b64encode(f"{u}:{p}".encode()).decode()


def dfs_summary(auth: str, domain: str) -> tuple[int | None, int | None, float]:
    """(backlinks, referring_domains, cost) from Backlinks summary."""
    r = requests.post(
        "https://api.dataforseo.com/v3/backlinks/summary/live",
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/json"},
        json=[{"target": domain, "internal_list_limit": 1,
               "include_subdomains": True}], timeout=60).json()
    task = (r.get("tasks") or [{}])[0]
    cost = float(task.get("cost") or 0.0)
    res = ((task.get("result") or [{}])[0]) or {}
    return res.get("backlinks"), res.get("referring_domains"), cost


def ahrefs_dr(domain: str) -> float | None:
    key = os.environ.get("AHREFS_API_KEY")
    if not key:
        return None
    try:
        r = requests.get(
            "https://api.ahrefs.com/v3/public/domain-rating-free",
            params={"target": domain},
            headers={"Authorization": f"Bearer {key}"}, timeout=30).json()
        return (r.get("domain_rating") or {}).get("domain_rating")
    except Exception as e:  # noqa: BLE001
        print(f"    (ahrefs DR failed: {str(e)[:80]})")
        return None


def latest_snapshot_age(cid: str) -> int | None:
    rows = requests.get(
        f"{SB}/rest/v1/marketing_backlink_snapshots?company_id=eq.{cid}"
        "&select=captured_at&order=captured_at.desc&limit=1",
        headers=HDR, timeout=20).json()
    if not rows:
        return None
    return (date.today() - date.fromisoformat(rows[0]["captured_at"])).days


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    inactive = {"paused", "suspended", "cancelled", "canceled", "churned",
                "inactive", "archived"}
    statuses = {c["id"]: str(c.get("status") or "").lower() for c in
                requests.get(f"{SB}/rest/v1/companies?select=id,status",
                             headers=HDR, timeout=30).json()}
    auth = _dfs_auth()
    total_cost, wrote = 0.0, 0
    slugs = [args.slug] if args.slug else sorted(cmap.keys())
    for slug in slugs:
        cid = cmap.get(slug)
        if not cid or statuses.get(cid) in inactive:
            continue
        try:
            rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
        except (OSError, json.JSONDecodeError):
            continue
        domain = str(rec.get("domain") or "").strip()
        if not domain or domain.lower() == "none" or domain.endswith(".invalid"):
            continue
        if not rec.get("cut_over_at"):
            continue  # pre-launch domains still point at the OLD site's profile
        if not args.slug:
            age = latest_snapshot_age(cid)
            if age is not None and age < 28:
                continue
        bl, rd, cost = dfs_summary(auth, domain)
        dr = ahrefs_dr(domain)
        total_cost += cost
        print(f"  {slug} ({domain}): backlinks={bl} ref_domains={rd} "
              f"DR={dr if dr is not None else 'n/a (no key)'} (${cost:.3f})")
        if args.dry_run:
            continue
        requests.post(
            f"{SB}/rest/v1/marketing_backlink_snapshots"
            "?on_conflict=company_id,captured_at",
            headers={**HDR, "Prefer": "resolution=merge-duplicates,return=minimal"},
            json={"company_id": cid, "domain": domain, "backlinks": bl,
                  "referring_domains": rd, "domain_rating": dr,
                  "source": {"dfs_cost": cost}}, timeout=20)
        wrote += 1
    print(f"backlink tracker: {wrote} snapshot(s), ${total_cost:.2f} DFS spend")
    return 0


if __name__ == "__main__":
    sys.exit(main())
