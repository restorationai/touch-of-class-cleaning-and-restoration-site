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
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
GBP_RULES = ROOT / "GBP" / "rank-ai-gbp-best-practices.md"

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


def _sb_patch(table: str, match: str, body: dict) -> None:
    r = requests.patch(
        f"{SB_URL}/rest/v1/{table}?{match}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"},
        data=json.dumps(body))
    r.raise_for_status()


def _sb_delete(table: str, match: str) -> None:
    r = requests.delete(
        f"{SB_URL}/rest/v1/{table}?{match}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Prefer": "return=minimal"})
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


def _dfs_auth():
    """DataForSEO basic-auth (user, pass): env first, else ~/.claude.json (the MCP creds)."""
    u = os.environ.get("DATAFORSEO_USERNAME") or DFS_USER
    p = os.environ.get("DATAFORSEO_PASSWORD") or DFS_PASS
    if u and p:
        return (u, p)
    cfg_path = Path.home() / ".claude.json"
    if not cfg_path.exists():
        return None
    def walk(o):
        if isinstance(o, dict):
            if "DATAFORSEO_USERNAME" in o and "DATAFORSEO_PASSWORD" in o:
                return o["DATAFORSEO_USERNAME"], o["DATAFORSEO_PASSWORD"]
            for v in o.values():
                r = walk(v)
                if r:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = walk(v)
                if r:
                    return r
    return walk(json.loads(cfg_path.read_text()))


def review_aggregate(brand: dict) -> dict:
    """Rating + review count via DataForSEO business listings (no GBP v4 needed)."""
    auth = _dfs_auth()
    if not (auth and brand.get("lat")):
        return {}
    try:
        payload = [{"title": brand.get("display_name"),
                    "location_coordinate": f"{brand['lat']},{brand['lng']},10", "limit": 5}]
        r = requests.post("https://api.dataforseo.com/v3/business_data/business_listings/search/live",
                          auth=auth, json=payload, timeout=40)
        items = r.json()["tasks"][0]["result"][0]["items"]
        want = str(brand.get("google_cid") or "")
        for it in items:
            if not want or str(it.get("cid")) == want:
                rt = it.get("rating") or {}
                return {"rating": rt.get("value"), "review_count": rt.get("votes_count")}
    except Exception:
        pass
    return {}


def sync_reviews(slug: str, depth: int = 50, timeout_s: int = 240) -> str:
    """Pull individual reviews via the DataForSEO Google Reviews task API (read-only,
    no GBP v4 needed) and upsert into marketing_gbp_reviews. Task-based (~1-3 min)."""
    import datetime as dt
    import hashlib
    import time
    cid = company_id_for(slug)
    pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
    brand = pi.get("brand", {})
    areas = pi.get("service_areas", [])
    city = next((a.get("city") for a in areas if a.get("primary")), areas[0].get("city") if areas else "")
    auth = _dfs_auth()
    if not (cid and auth and brand.get("display_name")):
        return f"{slug}: skip reviews (missing creds / company_id / name)"
    kw = f"{brand['display_name']} {city}".strip()
    tp = requests.post("https://api.dataforseo.com/v3/business_data/google/reviews/task_post",
                       auth=auth, json=[{"keyword": kw, "location_name": "United States",
                                         "language_name": "English", "depth": depth, "sort_by": "newest"}], timeout=40)
    t = tp.json()["tasks"][0]
    if t.get("status_code") != 20100:
        return f"{slug}: reviews task not created ({t.get('status_message')})"
    tid = t["id"]
    items, waited = None, 0
    while waited < timeout_s:
        time.sleep(12); waited += 12
        g = requests.get(f"https://api.dataforseo.com/v3/business_data/google/reviews/task_get/{tid}",
                         auth=auth, timeout=40).json()["tasks"][0]
        if g.get("status_code") == 20000 and g.get("result"):
            items = g["result"][0].get("items") or []
            break
    if items is None:
        return f"{slug}: reviews task still queued after {timeout_s}s (retry later)"
    rows, latest = [], None
    for rv in items:
        ts = rv.get("timestamp")
        rid = hashlib.md5(f"{rv.get('profile_name')}|{ts}|{(rv.get('review_text') or '')[:60]}".encode()).hexdigest()[:20]
        oa = rv.get("owner_answer")
        reply = oa.get("text") if isinstance(oa, dict) else oa
        rows.append({"company_id": cid, "review_id": rid, "reviewer_name": rv.get("profile_name"),
                     "star_rating": (rv.get("rating") or {}).get("value"), "comment": rv.get("review_text"),
                     "create_time": ts, "reply_comment": reply, "source": "dataforseo",
                     "synced_at": dt.datetime.now(dt.timezone.utc).isoformat()})
        if ts and (latest is None or ts > latest):
            latest = ts
    _sb_upsert("marketing_gbp_reviews", rows, on_conflict="company_id,review_id")
    if latest:
        requests.patch(f"{SB_URL}/rest/v1/marketing_gbp_profiles?company_id=eq.{cid}",
                       headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                                "Content-Type": "application/json", "Prefer": "return=minimal"},
                       data=json.dumps({"last_review_at": latest}))
    return f"{slug}: {len(rows)} reviews synced (latest {latest[:10] if latest else '?'})"


def cmd_reviews(args) -> int:
    for slug in _clients(args):
        print("  " + sync_reviews(slug))
    return 0


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
# Writes (the "Add now" execution) — add free-form services to the GBP listing
# --------------------------------------------------------------------------- #
def add_services(slug: str, services: list) -> str:
    """Add free-form services to the client's GBP (Business Information API patch).
    Reads the current serviceItems, appends new ones under the primary category,
    PATCHes serviceItems (full list), then reads back to confirm. Idempotent:
    skips services already on the listing (case-insensitive)."""
    cid = company_id_for(slug)
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    token = get_access_token(cid) if cid else None
    if not (token and brand.get("place_id")):
        return f"{slug}: skip (no token / place_id)"
    loc = find_location(token, brand["place_id"])
    if not loc:
        return f"{slug}: skip (no GBP location)"
    primary_cat = (loc.get("categories", {}).get("primaryCategory") or {}).get("name")
    if not primary_cat:
        return f"{slug}: skip (no primary category to attach services to)"
    existing = loc.get("serviceItems", [])
    have = {((s.get("freeFormServiceItem", {}) or {}).get("label", {}) or {}).get("displayName", "").strip().lower()
            for s in existing if "freeFormServiceItem" in s}
    new_list, added = list(existing), []
    for svc in services:
        if svc.strip().lower() in have:
            continue
        new_list.append({"freeFormServiceItem": {"category": primary_cat,
                                                  "label": {"displayName": svc.strip()}}})
        added.append(svc.strip())
    if not added:
        return f"{slug}: nothing to add (all already on the listing)"
    r = requests.patch(f"{INFO_API}/{loc['name']}?updateMask=serviceItems",
                       headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                       data=json.dumps({"serviceItems": new_list}))
    if not r.ok:
        return f"{slug}: PATCH failed {r.status_code}: {r.text[:200]}"
    # read back to confirm
    back = find_location(token, brand["place_id"])
    now_have = {((s.get("freeFormServiceItem", {}) or {}).get("label", {}) or {}).get("displayName", "").strip().lower()
                for s in back.get("serviceItems", []) if "freeFormServiceItem" in s}
    confirmed = [s for s in added if s.lower() in now_have]
    return f"{slug}: added {len(confirmed)}/{len(added)} -> {confirmed} (listing now has {len(back.get('serviceItems', []))} services)"


def cmd_add_services(args) -> int:
    print("  " + add_services(args.slug, args.service))
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


# --------------------------------------------------------------------------- #
# AI optimizer — grounded in the client's CONFIRMED services (companies.services /
# negative_services) + the best-practices ruleset, classify every live category,
# service, and reconciliation gap into KEEP / ADD / REMOVE / MERGE / NEEDS-REVIEW.
# --------------------------------------------------------------------------- #
def declared_services(cid: str) -> tuple[list, list]:
    """The client's CONFIRMED do / do-not-do lists from the app (companies table —
    the 'Services & Area' tab). This is ground truth."""
    rows = _sb(f"companies?id=eq.{cid}&select=services,negative_services")
    if not rows:
        return [], []
    r = rows[0]
    return (r.get("services") or []), (r.get("negative_services") or [])


def _anthropic_json(system: str, user: str) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY in rank-ai/.env")
    r = requests.post(ANTHROPIC_API, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
        data=json.dumps({"model": ANTHROPIC_MODEL, "max_tokens": 16384,
                         "system": system, "messages": [{"role": "user", "content": user}]}))
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json().get("content", []))
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def _matches(term: str, pool: list) -> bool:
    """Loose membership: normalized substring match against a confirmed list."""
    n = _norm(term)
    return bool(n) and any(n == _norm(p) or n in _norm(p) or _norm(p) in n for p in pool)


def optimize(slug: str) -> dict:
    """Audit the live GBP against confirmed services + the best-practices ruleset.
    Returns {summary, items[]} and upserts items to marketing_gbp_suggestions."""
    cid = company_id_for(slug)
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    place = brand.get("place_id")
    token = get_access_token(cid) if cid else None
    if not (cid and place and token):
        return {"slug": slug, "error": "missing company_id / place_id / GBP token"}
    loc = find_location(token, place)
    if not loc:
        return {"slug": slug, "error": f"no GBP location for place_id {place}"}
    g = summarize(loc)
    do, dont = declared_services(cid)
    site = site_services(slug)

    payload = {
        "business": loc.get("title"), "primary_category": g["primary_category"],
        "additional_categories": g["additional_categories"],
        "live_gbp_services": g["services"], "website_service_pages": site,
        "confirmed_services": do, "negative_services": dont,
    }
    rules = GBP_RULES.read_text()
    instruction = (
        "Audit this Google Business Profile against the rules. Produce items of THREE "
        "kinds:\n"
        "1) GBP categories+services: classify EVERY item in additional_categories and "
        "live_gbp_services (item_type 'category'/'service', source 'gbp').\n"
        "2) Missing GBP services: for each confirmed_service not on the GBP, emit "
        "item_type 'service', source 'confirmed', verdict ADD.\n"
        "3) Website pages: for each confirmed_service that has NO matching "
        "website_service_page (after collapsing synonyms/duplicates — do NOT request a "
        "page for something an existing page already covers), emit item_type 'page', "
        "source 'confirmed', verdict ADD, reason naming the service. These become "
        "'Create page' actions. Only suggest pages for services the client genuinely "
        "offers and that are distinct enough to deserve their own page.\n\n"
        "Return STRICT JSON only: {\"items\":[{\"item\":str,\"item_type\":\"category\"|"
        "\"service\"|\"page\",\"source\":\"gbp\"|\"site\"|\"confirmed\",\"verdict\":\"KEEP\""
        "|\"ADD\"|\"REMOVE\"|\"MERGE\"|\"NEEDS-REVIEW\",\"reason\":str,\"confidence\":num,"
        "\"canonical\":str|null}]}. canonical = the item to merge into (MERGE only). "
        "Keep each reason under 12 words. Do not apply auto_safe; just classify.\n\n"
        f"DATA:\n{json.dumps(payload, indent=2)}")
    result = _anthropic_json(rules, instruction)
    items = result.get("items", [])

    # Deterministic guardrail overrides the model on the non-negotiables.
    for it in items:
        term, vtype = it.get("item", ""), it.get("item_type")
        if _matches(term, dont):
            it["verdict"], it["confidence"] = "REMOVE", max(it.get("confidence", 0), 0.95)
            it["reason"] = "Client declared they do NOT offer this (negative_services)."
        it["auto_safe"] = bool(
            it.get("verdict") in ("ADD", "MERGE", "REMOVE")
            and vtype not in ("category", "page")  # pages fan out 13x; categories high-stakes
            and float(it.get("confidence", 0)) >= 0.85
            and (_matches(term, do) or _matches(term, dont)))

    rows = [{
        "company_id": cid, "item": it.get("item"), "item_type": it.get("item_type"),
        "source": it.get("source"), "verdict": it.get("verdict"), "reason": it.get("reason"),
        "confidence": it.get("confidence"), "canonical": it.get("canonical"),
        "auto_safe": it.get("auto_safe", False), "status": "open",
    } for it in items if it.get("item")]
    if rows:
        _sb_delete("marketing_gbp_suggestions", f"company_id=eq.{cid}&status=eq.open")
        _sb_upsert("marketing_gbp_suggestions", rows, on_conflict="company_id,item_type,item")
    from collections import Counter
    by_verdict = Counter(it.get("verdict") for it in items)
    return {"slug": slug, "summary": dict(by_verdict),
            "auto_safe": sum(1 for it in items if it.get("auto_safe")), "items": items}


def cmd_optimize(args) -> int:
    for slug in _clients(args):
        r = optimize(slug)
        if r.get("error"):
            print(f"  {slug}: skip ({r['error']})")
            continue
        print(f"  {slug}: {r['summary']} | {r['auto_safe']} auto-safe")
        for it in r["items"]:
            if it["verdict"] != "KEEP":
                flag = "AUTO" if it.get("auto_safe") else "review"
                print(f"     [{it['verdict']:<12}] ({flag}) {it['item']} — {it['reason']}")
    return 0


# --------------------------------------------------------------------------- #
# "Create page" execution — drain the marketing_page_requests queue into the
# client's plan-input (the canonical services list the build pipeline reads), so
# the next re-plan + rebuild scaffolds, renders, and deploys a page per service.
# --------------------------------------------------------------------------- #
def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def service_to_slug(display: str) -> str:
    """Map a GBP service display name to a catalog service slug if one matches
    (by normalized name), else a fresh slug from the display name."""
    cat = json.loads((ROOT / "templates" / "restoration" / "services.json").read_text())
    for s in cat["services"]:
        if _norm(s.get("display_name", s["slug"])) == _norm(display):
            return s["slug"]
    return _slugify(display)


def _slug_for_company(cid: str) -> str | None:
    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    for slug, c in cmap.items():
        if c == cid:
            return slug
    return None


SENSITIVE_HINTS = ("biohazard", "trauma", "hoarding", "crime", "death", "sewage",
                   "blood", "unattended", "suicide", "meth")


def ensure_catalog_entry(slug: str, display_name: str) -> bool:
    """Make sure the restoration services catalog has this service so plan_site won't
    reject it (plan_site dies on slugs not in the catalog). Clients declare services the
    template doesn't have yet; append a minimal VALID entry. Returns True if added."""
    cat_path = ROOT / "templates" / "restoration" / "services.json"
    cat = json.loads(cat_path.read_text())
    if any(s["slug"] == slug for s in cat["services"]):
        return False
    name = display_name.strip()
    entry = {
        "slug": slug, "display_name": name,
        "short_name": " ".join(name.split()[:3]),
        "primary_intent": "local_specialty",      # valid intent (passed through as search_intent)
        "secondary_keywords": [], "tier": "adjacent", "priority": 5,
    }
    if any(h in name.lower() for h in SENSITIVE_HINTS):
        entry["content_guardrails"] = "sensitive"  # trauma/biohazard/hoarding need careful copy
    cat["services"].append(entry)
    cat_path.write_text(json.dumps(cat, indent=2) + "\n")
    return True


def _run(cmd: list) -> tuple:
    import subprocess
    p = subprocess.run(["python3"] + cmd, cwd=str(ROOT), capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)


def build_client_pages(slug: str) -> tuple:
    """Safe incremental build+deploy after new services land in plan-input:
    regenerate the plan, write ONLY the new page files (never the destructive full
    scaffold), render the unrendered pages (best-effort — a single transient page
    failure must not block deploying the rest), then sync-deploy to production. The
    DEPLOY is the success gate; unrendered stragglers self-heal on the next run.
    Returns (ok, message)."""
    # 1. plan + 2. write only-new page files — these must succeed.
    for cmd in (["scripts/plan_site.py", "generate", "--slug", slug],
                ["scripts/build_site.py", "add-pages", "--slug", slug]):
        rc, log = _run(cmd)
        if rc != 0:
            return False, f"BUILD FAILED at `{cmd[0].split('/')[-1]} {cmd[1]}` -> ...{log.strip()[-400:]}"

    # 3. render (best-effort): retry once for transient failures; render is idempotent
    #    and skips already-rendered pages, so the retry only re-attempts the failures.
    rc, _ = _run(["scripts/build_site.py", "render", "--slug", slug])
    if rc != 0:
        rc, _ = _run(["scripts/build_site.py", "render", "--slug", slug])
    render_note = "" if rc == 0 else " (note: a page failed to render twice — it stays a placeholder and retries next run)"

    # 4. deploy what rendered — the gate. 13 good pages beat deploying nothing over 1 straggler.
    rcd, logd = _run(["scripts/build_site.py", "sync-deploy", "--slug", slug, "--branch", "main"])
    if rcd != 0:
        return False, f"BUILD FAILED at `sync-deploy` -> ...{logd.strip()[-400:]}"
    return True, "built + deployed (plan -> add-pages -> render -> sync-deploy main)" + render_note


def create_pages(slug_filter: str | None = None, build: bool = False) -> list[str]:
    """Consume queued page requests: add each service slug to the client's
    plan-input.json (deduped) and mark the request 'building'. With build=True, run the
    safe incremental build+deploy chain and mark the requests 'built'/'error'."""
    import datetime as dt
    rows = _sb("marketing_page_requests?status=eq.queued&select=id,company_id,service")
    out = []
    by_slug: dict[str, list] = {}
    for r in rows:
        slug = _slug_for_company(r["company_id"])
        if not slug or (slug_filter and slug != slug_filter):
            continue
        by_slug.setdefault(slug, []).append(r)

    for slug, reqs in by_slug.items():
        pi_path = ROOT / "clients" / slug / "plan-input.json"
        pi = json.loads(pi_path.read_text())
        services = pi.get("services", [])
        added, new_catalog = [], []
        for r in reqs:
            sslug = service_to_slug(r["service"])
            if ensure_catalog_entry(sslug, r["service"]):
                new_catalog.append(sslug)
            if sslug not in services:
                services.append(sslug)
                added.append(sslug)
            _sb_patch("marketing_page_requests", f"id=eq.{r['id']}",
                      {"status": "building", "slug": slug, "service_slug": sslug})
        if added:
            pi["services"] = services
            pi_path.write_text(json.dumps(pi, indent=2) + "\n")
        msg = (f"{slug}: queued {len(reqs)} page(s); +{len(added)} new service(s) in plan-input "
               f"{added or '(all already present)'}")
        if new_catalog:
            msg += f"; +{len(new_catalog)} new catalog entr(ies): {new_catalog}"
        out.append(msg)

        if build:
            ok, msg = build_client_pages(slug)
            out.append(f"  build: {msg}")
            patch = {"status": "built", "built_at": dt.datetime.now(dt.timezone.utc).isoformat()} \
                if ok else {"status": "error", "error": msg[:500]}
            for r in reqs:
                _sb_patch("marketing_page_requests", f"id=eq.{r['id']}", patch)

    if not out:
        out.append("no queued page requests")
    return out


def cmd_create_pages(args) -> int:
    for line in create_pages(args.slug if not args.all else None, build=args.build):
        print("  " + line)
    if not args.build:
        print("  -> staged into plan-input. Re-run with --build (or the gbp-pages workflow) to deploy.")
    return 0


def main() -> int:
    if not (SB_URL and SB_KEY and G_CID and G_SECRET):
        print("ERROR: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GOOGLE_OAUTH_CLIENT_ID, "
              "GOOGLE_OAUTH_CLIENT_SECRET must be set in rank-ai/.env", file=sys.stderr)
        return 1
    ap = argparse.ArgumentParser(description="Google Business Profile module")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("read", "reconcile", "sync", "reviews"):
        p = sub.add_parser(name)
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--slug")
        g.add_argument("--all", action="store_true")
    pa = sub.add_parser("add-services")
    pa.add_argument("--slug", required=True)
    pa.add_argument("--service", action="append", required=True, help="repeat for multiple")
    pc = sub.add_parser("create-pages")
    gc = pc.add_mutually_exclusive_group(required=True)
    gc.add_argument("--slug")
    gc.add_argument("--all", action="store_true")
    pc.add_argument("--build", action="store_true",
                    help="Also run the safe incremental build+deploy (plan→add-pages→render→sync-deploy)")
    po = sub.add_parser("optimize")
    go = po.add_mutually_exclusive_group(required=True)
    go.add_argument("--slug")
    go.add_argument("--all", action="store_true")
    args = ap.parse_args()
    return {"read": cmd_read, "reconcile": cmd_reconcile, "sync": cmd_sync,
            "reviews": cmd_reviews, "add-services": cmd_add_services,
            "create-pages": cmd_create_pages, "optimize": cmd_optimize}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
