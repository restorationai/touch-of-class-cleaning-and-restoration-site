#!/usr/bin/env python3
"""
gsc_sync.py — Google Search Console performance sync (the app's "Analytics" tab).

Pulls Search Analytics (clicks / impressions / CTR / position) for each client via
the verified GSC property and stores it in Supabase for the app to display:
  - marketing_gsc_daily   : daily site totals (90d) -> month-over-month trend
  - marketing_gsc_queries : top queries (28d) + a `striking` flag (page-1/2 boundary,
                            real demand) — the highest-ROI content opportunities
  - marketing_gsc_pages   : top pages (28d)

Auth: the shared agency GSC token (.gsc-agency-token.json) via gsc_client.GSCClient.
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.

    python3 scripts/gsc_sync.py --slug homepriderestorationandcleaning
    python3 scripts/gsc_sync.py --all
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
load_dotenv(ROOT / ".env")

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# "Striking distance": ranking on the page-1/page-2 boundary with real demand — a
# small content/refresh push converts these to page-one traffic.
STRIKING_MIN_POS, STRIKING_MAX_POS, STRIKING_MIN_IMPR = 8.0, 20.0, 10


def _sb_upsert(table: str, rows: list, on_conflict: str) -> None:
    if not rows:
        return
    r = requests.post(f"{SB_URL}/rest/v1/{table}?on_conflict={on_conflict}",
                      headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                               "Content-Type": "application/json",
                               "Prefer": "resolution=merge-duplicates,return=minimal"},
                      data=json.dumps(rows))
    r.raise_for_status()


def _sb_delete(table: str, company_id: str) -> None:
    requests.delete(f"{SB_URL}/rest/v1/{table}?company_id=eq.{company_id}",
                    headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                             "Prefer": "return=minimal"}).raise_for_status()


def company_id_for(slug: str) -> str | None:
    rec = ROOT / "clients" / f"{slug}.json"
    if rec.exists():
        cid = json.loads(rec.read_text()).get("company_id")
        if cid:
            return cid
    cmap = ROOT / "clients" / "company_map.json"
    return json.loads(cmap.read_text()).get(slug) if cmap.exists() else None


def domain_for(slug: str) -> str | None:
    rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
    return rec.get("domain") or (rec.get("gsc", {}) or {}).get("property_url", "").replace("sc-domain:", "") or None


def _query(svc, site_url: str, start: str, end: str, dims: list, limit: int = 25000) -> list:
    return svc.searchanalytics().query(siteUrl=site_url, body={
        "startDate": start, "endDate": end, "dimensions": dims, "rowLimit": limit,
    }).execute().get("rows", [])


def sync(slug: str) -> str:
    from gsc_client import GSCClient
    cid = company_id_for(slug)
    domain = domain_for(slug)
    if not (cid and domain):
        return f"{slug}: skip (missing company_id / domain)"
    rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
    prop = (rec.get("gsc", {}) or {}).get("property_url")
    client = GSCClient(slug, domain, property_url=prop)
    if not client.is_configured(slug):
        return f"{slug}: skip (GSC not configured / not verified)"
    svc = client._ensure_service()
    site = client.site_url
    today = dt.date.today()
    d90, d28 = (today - dt.timedelta(days=90)).isoformat(), (today - dt.timedelta(days=28)).isoformat()
    end = today.isoformat()

    # 1) Daily site totals (90d) for the trend. NOTE: marketing_gsc_daily pre-existed
    #    with total_*/avg_* column names + a UNIQUE(company_id,date) — write to those.
    daily = [{
        "company_id": cid, "date": r["keys"][0],
        "total_clicks": int(r["clicks"]), "total_impressions": int(r["impressions"]),
        "avg_ctr": round(r["ctr"], 4), "avg_position": round(r["position"], 1),
    } for r in _query(svc, site, d90, end, ["date"])]
    _sb_upsert("marketing_gsc_daily", daily, "company_id,date")

    # 2) Top queries (28d) + striking flag. Replace the snapshot each run.
    qrows = _query(svc, site, d28, end, ["query"], limit=200)
    queries = []
    striking_n = 0
    for r in qrows:
        pos, impr = r["position"], int(r["impressions"])
        striking = (STRIKING_MIN_POS <= pos <= STRIKING_MAX_POS) and impr >= STRIKING_MIN_IMPR
        striking_n += int(striking)
        queries.append({
            "company_id": cid, "query": r["keys"][0][:500],
            "clicks": int(r["clicks"]), "impressions": impr,
            "ctr": round(r["ctr"], 4), "position": round(pos, 1), "striking": striking,
        })
    _sb_delete("marketing_gsc_queries", cid)
    _sb_upsert("marketing_gsc_queries", queries, "company_id,query")

    # 3) Top pages (28d).
    prows = _query(svc, site, d28, end, ["page"], limit=100)
    pages = [{
        "company_id": cid, "page": r["keys"][0][:1000],
        "clicks": int(r["clicks"]), "impressions": int(r["impressions"]),
        "ctr": round(r["ctr"], 4), "position": round(r["position"], 1),
    } for r in prows]
    _sb_delete("marketing_gsc_pages", cid)
    _sb_upsert("marketing_gsc_pages", pages, "company_id,page")

    return (f"{slug}: {len(daily)}d totals, {len(queries)} queries "
            f"({striking_n} striking), {len(pages)} pages")


def _clients(args) -> list:
    if args.all:
        return list(json.loads((ROOT / "clients" / "company_map.json").read_text()).keys())
    return [args.slug]


def main() -> int:
    if not (SB_URL and SB_KEY):
        print("ERROR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required.", file=sys.stderr)
        return 1
    ap = argparse.ArgumentParser(description="Google Search Console performance sync")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    args = ap.parse_args()
    for slug in _clients(args):
        try:
            print("  " + sync(slug))
        except Exception as e:  # one client's GSC issue must not abort the run
            print(f"  {slug}: ERROR ({type(e).__name__}: {str(e)[:160]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
