#!/usr/bin/env python3
"""keyword_truth.py — search terms backed by real data, never vibes
(Santino 2026-09-02: "I want to make sure it's backed by real data...
are there any tools we can use to get 100% confidence?").

Two data sources, two subcommands:

  gbp-terms [--slug X | --all]
      Business Profile Performance API searchkeywords/impressions/monthly:
      the ACTUAL terms people typed on Google/Maps before finding each
      client's profile, with monthly impression counts. Upserts
      marketing_gbp_search_terms (one row per company+month+keyword) and
      prints each client's top terms. The strongest possible evidence for
      which keywords deserve geo-grid slots.

  planner --geo "Tacoma, WA" [--vertical restoration] [--seed "kw1,kw2"]
      Google Keyword Planner (Ads API generateKeywordIdeas): Google's own
      monthly search volumes for the vertical's candidate terms in that
      metro, plus related-idea discovery. The "100% confidence" volume
      source. Prints a ranked table and writes
      clients/_ops/keyword-canon/{vertical}--{geo-slug}.json.

Auth: GBP terms ride each client's stored Google connection (same tokens
gbp.py uses). Planner rides any adwords-scoped connection + the agency
developer token, addressed through the MCC.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:  # noqa: BLE001
    pass

import gbp  # noqa: E402  (token + location helpers)

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
HDR = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
       "Content-Type": "application/json"}
ADS = "https://googleads.googleapis.com/v24"
MCC = (os.environ.get("GOOGLE_ADS_MCC_CUSTOMER_ID") or "2018844125").replace("-", "")
DEV = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "")

VERTICAL_SEEDS = {
    "restoration": [
        "water damage restoration", "water damage repair", "flood damage restoration",
        "flood cleanup", "water removal", "water cleanup", "basement flood cleanup",
        "water mitigation", "water extraction", "fire damage restoration",
        "smoke damage restoration", "mold remediation", "mold removal",
        "sewage cleanup", "storm damage repair", "biohazard cleanup",
        "restoration company", "emergency water damage"],
    "plumbing": [
        "plumber", "plumbing company", "emergency plumber", "drain cleaning",
        "water heater repair", "water heater installation", "burst pipe repair",
        "sewer line repair", "leak detection", "repipe", "clogged drain",
        "toilet repair", "slab leak repair"],
    "hvac": [
        "hvac repair", "ac repair", "air conditioning repair", "hvac company",
        "furnace repair", "heating repair", "ac installation", "hvac installation",
        "emergency ac repair", "heat pump repair", "duct cleaning"],
    "environmental": [
        "mold testing", "mold inspection", "asbestos testing", "asbestos removal",
        "asbestos abatement", "lead testing", "lead abatement", "lead paint removal",
        "air quality testing", "environmental testing", "mold assessment"],
}


def _clients(slug: str | None):
    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    if slug:
        return {slug: cmap[slug]} if slug in cmap else {}
    return cmap


# ------------------------------------------------------------- gbp-terms
def fetch_gbp_terms(slug: str, cid: str, months: int = 6) -> str:
    tok = gbp.get_access_token(cid)
    if not tok:
        return f"{slug}: no Google token"
    brand = {}
    try:
        brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    except Exception:  # noqa: BLE001
        pass
    place = brand.get("place_id") or gbp._place_id_from_connection(cid)
    loc = gbp.find_location(tok, place or "")
    if not loc:
        conn_place = gbp._place_id_from_connection(cid)
        if conn_place and conn_place != place:
            loc = gbp.find_location(tok, conn_place)
    if not loc:
        return f"{slug}: no GBP location"
    loc_id = loc["name"].split("/")[-1]
    end = dt.date.today().replace(day=1) - dt.timedelta(days=1)   # last full month
    start = (end.replace(day=1) - dt.timedelta(days=months * 31)).replace(day=1)
    url = (f"https://businessprofileperformance.googleapis.com/v1/locations/{loc_id}"
           f"/searchkeywords/impressions/monthly"
           f"?monthlyRange.start_month.year={start.year}&monthlyRange.start_month.month={start.month}"
           f"&monthlyRange.end_month.year={end.year}&monthlyRange.end_month.month={end.month}")
    rows, page = [], None
    while True:
        u = url + (f"&pageToken={page}" if page else "")
        r = requests.get(u, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        if not r.ok:
            return f"{slug}: API {r.status_code} {r.text[:80]}"
        data = r.json()
        for k in data.get("searchKeywordsCounts", []):
            iv = k.get("insightsValue") or {}
            # value = exact count; threshold = "fewer than N" (privacy floor)
            count = int(iv.get("value") or iv.get("threshold") or 0)
            rows.append({"keyword": k.get("searchKeyword", "").lower(), "impressions": count})
        page = data.get("nextPageToken")
        if not page:
            break
    if not rows:
        return f"{slug}: 0 terms returned"
    month_key = end.replace(day=1).isoformat()
    payload = [{"company_id": cid, "month": month_key, "keyword": r["keyword"],
                "impressions": r["impressions"],
                "synced_at": dt.datetime.now(dt.timezone.utc).isoformat()}
               for r in rows]
    up = requests.post(
        f"{SB_URL}/rest/v1/marketing_gbp_search_terms?on_conflict=company_id,month,keyword",
        headers=HDR | {"Prefer": "resolution=merge-duplicates,return=minimal"},
        json=payload, timeout=60)
    top = sorted(rows, key=lambda r: -r["impressions"])[:8]
    tops = ", ".join(f"{r['keyword']}({r['impressions']})" for r in top)
    return f"{slug}: {len(rows)} terms stored ({'ok' if up.ok else up.status_code}) | top: {tops}"


# --------------------------------------------------------------- planner
def _ads_token() -> str | None:
    """Any adwords-scoped connection token (the agency-linked ones work)."""
    rows = requests.get(
        f"{SB_URL}/rest/v1/user_integrations?provider=eq.google"
        f"&select=client_id,refresh_token,connection_metadata", headers=HDR, timeout=30).json()
    for row in rows:
        md = row.get("connection_metadata") or {}
        if "adwords" not in str(md.get("scopes") or ""):
            continue
        tok = gbp.get_access_token(row["client_id"])
        if tok:
            return tok
    return None


def _geo_id(tok: str, geo: str) -> tuple[str, str] | None:
    r = requests.post(f"{ADS}/geoTargetConstants:suggest",
                      headers={"Authorization": f"Bearer {tok}", "developer-token": DEV,
                               "Content-Type": "application/json"},
                      json={"locale": "en", "countryCode": "US",
                            "locationNames": {"names": [geo]}}, timeout=30)
    if not r.ok:
        print(f"  geo suggest failed: {r.status_code} {r.text[:120]}", file=sys.stderr)
        return None
    for s in r.json().get("geoTargetConstantSuggestions", []):
        g = s.get("geoTargetConstant") or {}
        if g.get("resourceName"):
            return g["resourceName"], f"{g.get('name')}, {g.get('canonicalName', '')}"
    return None


def planner(geo: str, vertical: str, extra_seed: list[str]) -> int:
    tok = _ads_token()
    if not tok or not DEV:
        print("no adwords-scoped token or developer token available")
        return 1
    hit = _geo_id(tok, geo)
    if not hit:
        return 1
    geo_rn, geo_name = hit
    seeds = list(dict.fromkeys(VERTICAL_SEEDS.get(vertical, []) + extra_seed))
    # generateKeywordIdeas caps seed lists; chunk by 10
    ideas: dict[str, dict] = {}
    for i in range(0, len(seeds), 10):
        body = {
            "language": "languageConstants/1000",
            "geoTargetConstants": [geo_rn],
            "keywordSeed": {"keywords": seeds[i:i + 10]},
            "includeAdultKeywords": False,
            "pageSize": 400,
        }
        r = requests.post(f"{ADS}/customers/{MCC}:generateKeywordIdeas",
                          headers={"Authorization": f"Bearer {tok}", "developer-token": DEV,
                                   "login-customer-id": MCC, "Content-Type": "application/json"},
                          json=body, timeout=60)
        if not r.ok:
            print(f"  planner call failed: {r.status_code} {r.text[:200]}")
            return 1
        for res in r.json().get("results", []):
            kw = res.get("text", "").lower()
            m = res.get("keywordIdeaMetrics") or {}
            vol = int(m.get("avgMonthlySearches") or 0)
            cur = ideas.get(kw)
            if not cur or vol > cur["volume"]:
                ideas[kw] = {"volume": vol,
                             "competition": m.get("competition"),
                             "seed": kw in seeds}
    ranked = sorted(ideas.items(), key=lambda kv: -kv[1]["volume"])
    print(f"\nKEYWORD PLANNER — {vertical} @ {geo_name.strip(', ')} "
          f"(Google's own monthly volumes)\n")
    print(f"{'term':40} {'vol/mo':>8}  {'comp':10} seed")
    shown = 0
    for kw, m in ranked:
        if m["volume"] == 0 and not m["seed"]:
            continue
        print(f"{kw[:40]:40} {m['volume']:>8,}  {str(m['competition'] or ''):10} {'*' if m['seed'] else ''}")
        shown += 1
        if shown >= 40:
            break
    out_dir = ROOT / "clients" / "_ops" / "keyword-canon"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", geo.lower()).strip("-")
    out = out_dir / f"{vertical}--{slug}.json"
    out.write_text(json.dumps({
        "vertical": vertical, "geo": geo_name, "pulled_at":
        dt.datetime.now(dt.timezone.utc).isoformat(),
        "terms": [{"term": k, **v} for k, v in ranked if v["volume"] > 0 or v["seed"]],
    }, indent=1))
    print(f"\nwrote {out.relative_to(ROOT)} ({len(ranked)} ideas)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gbp-terms")
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    p = sub.add_parser("planner")
    p.add_argument("--geo", required=True, help='e.g. "Tacoma, WA"')
    p.add_argument("--vertical", default="restoration",
                   choices=sorted(VERTICAL_SEEDS))
    p.add_argument("--seed", default="", help="comma-separated extra terms")
    a = ap.parse_args()
    if a.cmd == "gbp-terms":
        if not a.slug and not a.all:
            ap.error("pass --slug or --all")
        for slug, cid in _clients(a.slug).items():
            try:
                print("  " + fetch_gbp_terms(slug, cid))
            except Exception as e:  # noqa: BLE001
                print(f"  {slug}: ERROR {str(e)[:100]}")
        return 0
    return planner(a.geo, a.vertical, [s.strip() for s in a.seed.split(",") if s.strip()])


if __name__ == "__main__":
    sys.exit(main())
