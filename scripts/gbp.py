#!/usr/bin/env python3
"""
gbp.py — Google Business Profile pipeline module (System: GBP).

Reads a client's live GBP via the now-enabled Business Profile APIs using the
business.manage token stored by the app's connect flow (user_integrations), and
RECONCILES the GBP's categories/services against the website's pages — the local-SEO
consistency lever (a GBP service/category with no dedicated, crawlable page ranks
worse; a site service missing from the GBP is a lost signal).

Auth: pulls the client's (or, fallback, any agency) 'google' refresh_token from
Supabase user_integrations, refreshes it with the shared OAuth client. The agency
account manages all client locations, so any business.manage token can read them;
we match the right location by the client's brand.place_id.

Commands:
    python3 scripts/gbp.py read       --slug narestco
    python3 scripts/gbp.py reconcile  --slug narestco
    python3 scripts/gbp.py reconcile  --all

Read-only for now (no writes). Update operations + strategist wiring come next.
Env (rank-ai/.env): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GOOGLE_OAUTH_CLIENT_ID,
GOOGLE_OAUTH_CLIENT_SECRET.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
G_CID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
G_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
DFS_USER = os.environ.get("DATAFORSEO_USERNAME") or os.environ.get("DATAFORSEO_LOGIN", "")
DFS_PASS = os.environ.get("DATAFORSEO_PASSWORD", "")

# Performance API daily metric -> marketing_gbp_daily column
PERF_METRICS = {
    "CALL_CLICKS": "call_clicks",
    "WEBSITE_CLICKS": "website_clicks",
    "BUSINESS_DIRECTION_REQUESTS": "direction_requests",
    "BUSINESS_CONVERSATIONS": "conversations",
    "BUSINESS_IMPRESSIONS_DESKTOP_MAPS": "impressions_desktop_maps",
    "BUSINESS_IMPRESSIONS_MOBILE_MAPS": "impressions_mobile_maps",
    "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH": "impressions_desktop_search",
    "BUSINESS_IMPRESSIONS_MOBILE_SEARCH": "impressions_mobile_search",
}

ACCT_API = "https://mybusinessaccountmanagement.googleapis.com/v1"
INFO_API = "https://mybusinessbusinessinformation.googleapis.com/v1"
LOC_READ_MASK = "name,title,categories,storefrontAddress,regularHours,profile,serviceItems,metadata,phoneNumbers,websiteUri"


# --------------------------------------------------------------------------- #
# Supabase (runtime REST — service role; uses requests to avoid the urllib WAF block)
# --------------------------------------------------------------------------- #
def _sb(path: str) -> list:
    r = requests.get(f"{SB_URL}/rest/v1/{path}",
                     headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    r.raise_for_status()
    return r.json()


def company_id_for(slug: str) -> str | None:
    rec = ROOT / "clients" / f"{slug}.json"
    if rec.exists():
        cid = json.loads(rec.read_text()).get("company_id")
        if cid:
            return cid
    cmap = ROOT / "clients" / "company_map.json"
    return json.loads(cmap.read_text()).get(slug) if cmap.exists() else None


def get_access_token(company_id: str) -> str | None:
    """Refresh a business.manage access token for this company. Falls back to any
    agency 'google' integration (the agency account manages every client location)."""
    rows = _sb(f"user_integrations?provider=eq.google&select=client_id,refresh_token,"
               f"connection_metadata&client_id=eq.{company_id}")
    if not rows:
        rows = _sb("user_integrations?provider=eq.google&select=client_id,refresh_token,"
                   "connection_metadata&limit=5")  # agency fallback
    for row in rows:
        rt = row.get("refresh_token") or (row.get("connection_metadata") or {}).get("refresh_token")
        if not rt:
            continue
        resp = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": G_CID, "client_secret": G_SECRET,
            "refresh_token": rt, "grant_type": "refresh_token"})
        if resp.ok:
            return resp.json()["access_token"]
    return None


# --------------------------------------------------------------------------- #
# GBP reads
# --------------------------------------------------------------------------- #
def _g(url: str, token: str) -> dict:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()


def find_location(token: str, place_id: str) -> dict | None:
    """Find the location matching the client's place_id across all managed accounts."""
    for acct in _g(f"{ACCT_API}/accounts", token).get("accounts", []):
        url = f"{INFO_API}/{acct['name']}/locations?readMask={LOC_READ_MASK}&pageSize=100"
        for loc in _g(url, token).get("locations", []):
            if (loc.get("metadata", {}) or {}).get("placeId") == place_id:
                return loc
    return None


def summarize(loc: dict) -> dict:
    cats = loc.get("categories", {}) or {}
    primary = (cats.get("primaryCategory") or {}).get("displayName")
    additional = [c.get("displayName") for c in cats.get("additionalCategories", [])]
    services = []
    for s in loc.get("serviceItems", []):
        # free-form or structured service
        label = (s.get("freeFormServiceItem", {}) or {}).get("label", {}).get("displayName")
        struct = (s.get("structuredServiceItem", {}) or {}).get("serviceTypeId")
        services.append(label or struct)
    return {
        "title": loc.get("title"),
        "website": loc.get("websiteUri"),
        "primary_category": primary,
        "additional_categories": [c for c in additional if c],
        "services": [s for s in services if s],
        "has_hours": bool(loc.get("regularHours")),
        "has_description": bool((loc.get("profile") or {}).get("description")),
        "description_len": len((loc.get("profile") or {}).get("description", "") or ""),
    }


# --------------------------------------------------------------------------- #
# Website reconciliation
# --------------------------------------------------------------------------- #
def _norm(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"\b(service|services|restoration|repair|cleanup|remediation|removal)\b", " ", t)
    return re.sub(r"[^a-z]+", " ", t).strip()


def site_services(slug: str) -> list[str]:
    """Service display names that have a dedicated page on the client's site."""
    pi = ROOT / "clients" / slug / "plan-input.json"
    if not pi.exists():
        return []
    services = json.loads(pi.read_text()).get("services", [])
    cat = json.loads((ROOT / "templates" / "restoration" / "services.json").read_text())
    by_slug = {s["slug"]: s.get("display_name", s["slug"]) for s in cat["services"]}
    return [by_slug.get(s, s) for s in services]


def reconcile(slug: str) -> dict:
    cid = company_id_for(slug)
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    place_id = brand.get("place_id")
    out = {"slug": slug, "company_id": cid, "place_id": place_id}
    if not place_id:
        out["error"] = "no brand.place_id (client GBP identity unknown)"
        return out
    token = get_access_token(cid)
    if not token:
        out["error"] = "no business.manage token (connect this client's GBP)"
        return out
    loc = find_location(token, place_id)
    if not loc:
        out["error"] = f"no GBP location found for place_id {place_id} on the connected account(s)"
        return out
    g = summarize(loc)
    out["gbp"] = g

    # GBP categories + services that the client offers (on the listing)
    gbp_terms = [g["primary_category"]] + g["additional_categories"] + g["services"]
    gbp_norm = {_norm(t): t for t in gbp_terms if t}
    site = site_services(slug)
    site_norm = {_norm(s): s for s in site if s}

    # GBP service/category with NO dedicated website page -> build a page
    out["gbp_without_page"] = sorted(
        orig for n, orig in gbp_norm.items()
        if n and not any(n in sn or sn in n for sn in site_norm))
    # Website service with NO GBP entry -> add it to the GBP
    out["site_without_gbp"] = sorted(
        orig for n, orig in site_norm.items()
        if n and not any(n in gn or gn in n for gn in gbp_norm))
    return out


# --------------------------------------------------------------------------- #
# Sync to Supabase (profile snapshot + daily insights for month-over-month)
# --------------------------------------------------------------------------- #
def _sb_upsert(table: str, rows: list, on_conflict: str) -> None:
    if not rows:
        return
    r = requests.post(
        f"{SB_URL}/rest/v1/{table}?on_conflict={on_conflict}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json",
                 "Prefer": "resolution=merge-duplicates,return=minimal"},
        data=json.dumps(rows))
    r.raise_for_status()


def get_insights(token: str, location_id: str, days: int = 90) -> dict:
    """Daily GBP performance metrics for the last `days` -> {date: {col: value}}.
    Stored daily so the app can compute ANY period delta (this month vs last)."""
    import datetime as dt
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    qs = "&".join(f"dailyMetrics={m}" for m in PERF_METRICS)
    qs += (f"&dailyRange.start_date.year={start.year}&dailyRange.start_date.month={start.month}"
           f"&dailyRange.start_date.day={start.day}&dailyRange.end_date.year={end.year}"
           f"&dailyRange.end_date.month={end.month}&dailyRange.end_date.day={end.day}")
    url = (f"https://businessprofileperformance.googleapis.com/v1/locations/{location_id}"
           f":fetchMultiDailyMetricsTimeSeries?{qs}")
    daily: dict = {}
    for series in _g(url, token).get("multiDailyMetricTimeSeries", []):
        for ts in series.get("dailyMetricTimeSeries", []):
            col = PERF_METRICS.get(ts.get("dailyMetric"))
            if not col:
                continue
            for p in ts.get("timeSeries", {}).get("datedValues", []):
                d = p.get("date") or {}
                if not d:
                    continue
                key = f"{d['year']:04d}-{d['month']:02d}-{d['day']:02d}"
                daily.setdefault(key, {})[col] = int(p.get("value", 0))
    return daily


def review_aggregate(brand: dict) -> dict:
    """Best-effort rating + review count via DataForSEO (no GBP v4 needed). Empty on failure."""
    if not (DFS_USER and DFS_PASS and brand.get("lat")):
        return {}
    try:
        payload = [{"title": brand.get("display_name"),
                    "location_coordinate": f"{brand['lat']},{brand['lng']},10", "limit": 5}]
        r = requests.post("https://api.dataforseo.com/v3/business_data/business_listings/search/live",
                          auth=(DFS_USER, DFS_PASS), json=payload, timeout=40)
        items = r.json()["tasks"][0]["result"][0]["items"]
        want = str(brand.get("google_cid") or "")
        for it in items:
            if not want or str(it.get("cid")) == want:
                rt = it.get("rating") or {}
                return {"rating": rt.get("value"), "review_count": rt.get("votes_count")}
    except Exception:
        pass
    return {}


def sync(slug: str) -> str:
    import datetime as dt
    cid = company_id_for(slug)
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    place = brand.get("place_id")
    token = get_access_token(cid) if cid else None
    if not (cid and place and token):
        return f"{slug}: skip (missing company_id / place_id / GBP token)"
    loc = find_location(token, place)
    if not loc:
        return f"{slug}: skip (no GBP location for place_id {place})"
    g = summarize(loc)
    rec = reconcile(slug)
    agg = review_aggregate(brand)
    addr = loc.get("storefrontAddress", {}) or {}
    address = ", ".join(filter(None, [
        " ".join(addr.get("addressLines", [])), addr.get("locality"),
        addr.get("administrativeArea"), addr.get("postalCode")]))
    phone = (loc.get("phoneNumbers", {}) or {}).get("primaryPhone")
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    _sb_upsert("marketing_gbp_profiles", [{
        "company_id": cid, "place_id": place, "location_name": loc.get("name"),
        "title": g["title"], "primary_category": g["primary_category"],
        "additional_categories": g["additional_categories"], "services": g["services"],
        "rating": agg.get("rating"), "review_count": agg.get("review_count"), "claimed": True,
        "address": address or None, "phone": phone, "website": g["website"],
        "has_hours": g["has_hours"], "description": (loc.get("profile") or {}).get("description"),
        "reconcile_gbp_without_page": rec.get("gbp_without_page"),
        "reconcile_site_without_gbp": rec.get("site_without_gbp"), "synced_at": now,
    }], on_conflict="company_id")

    daily = get_insights(token, loc["name"].split("/")[-1])
    rows = [{"company_id": cid, "date": d, **vals} for d, vals in daily.items()]
    _sb_upsert("marketing_gbp_daily", rows, on_conflict="company_id,date")
    return (f"{slug}: profile synced (rating {agg.get('rating')}/{agg.get('review_count')}) + "
            f"{len(rows)} days of insights")


def cmd_sync(args) -> int:
    for slug in _clients(args):
        print("  " + sync(slug))
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _clients(args) -> list[str]:
    if args.all:
        cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
        return list(cmap.keys())
    return [args.slug]


def cmd_read(args) -> int:
    for slug in _clients(args):
        cid = company_id_for(slug)
        token = get_access_token(cid) if cid else None
        if not token:
            print(f"\n## {slug}: no business.manage token — connect this client's GBP")
            continue
        brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
        loc = find_location(token, brand.get("place_id", ""))
        if not loc:
            print(f"\n## {slug}: no matching GBP location for place_id {brand.get('place_id')}")
            continue
        g = summarize(loc)
        print(f"\n## {slug} — {g['title']}  ({g['website']})")
        print(f"   primary category: {g['primary_category']}")
        print(f"   additional categories: {g['additional_categories'] or '(none)'}")
        print(f"   services on listing: {g['services'] or '(none)'}")
        print(f"   hours set: {g['has_hours']} | description: {g['description_len']} chars")
    return 0


def cmd_reconcile(args) -> int:
    for slug in _clients(args):
        r = reconcile(slug)
        print(f"\n## {slug}")
        if r.get("error"):
            print(f"   SKIP — {r['error']}")
            continue
        print(f"   GBP primary: {r['gbp']['primary_category']} | "
              f"{len(r['gbp']['additional_categories'])} more categories | "
              f"{len(r['gbp']['services'])} services")
        if r["gbp_without_page"]:
            print(f"   ⚠ GBP item with NO dedicated website page (build one): {r['gbp_without_page']}")
        if r["site_without_gbp"]:
            print(f"   ⚠ Website service NOT on the GBP (add to listing): {r['site_without_gbp']}")
        if not r["gbp_without_page"] and not r["site_without_gbp"]:
            print("   ✓ GBP categories/services and website pages are consistent")
    return 0


def main() -> int:
    if not (SB_URL and SB_KEY and G_CID and G_SECRET):
        print("ERROR: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GOOGLE_OAUTH_CLIENT_ID, "
              "GOOGLE_OAUTH_CLIENT_SECRET must be set in rank-ai/.env", file=sys.stderr)
        return 1
    ap = argparse.ArgumentParser(description="Google Business Profile module")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("read", "reconcile", "sync"):
        p = sub.add_parser(name)
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--slug")
        g.add_argument("--all", action="store_true")
    args = ap.parse_args()
    return {"read": cmd_read, "reconcile": cmd_reconcile, "sync": cmd_sync}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
