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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verticals  # noqa: E402 — per-client vertical → template resolution (fail-loud)

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
    cat = json.loads(verticals.resolve_template(slug, "services.json").read_text())
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


def sync_reviews_v4(slug: str, token: str | None = None, loc: dict | None = None) -> str:
    """Authoritative review sync straight from the GBP v4 API for connected
    clients. The DFS task sync above stays as the unconnected-client fallback,
    but it was never scheduled (the app showed reviews frozen at June 19) and
    its md5 ids can't be matched to v4 reviewIds — so this REPLACES the
    company's rows wholesale instead of upserting alongside them."""
    import datetime as dt
    cid = company_id_for(slug)
    if not cid:
        return f"{slug}: no company_id"
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    token = token or (get_access_token(cid) if cid else None)
    if not token:
        return f"{slug}: no token"
    loc = loc or find_location(token, brand.get("place_id", ""))
    if not loc:
        return f"{slug}: no GBP location"
    acct = _g(f"{ACCT_API}/accounts", token)["accounts"][0]["name"]
    star = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    rows, page, total, avg = [], None, None, None
    while True:
        d = _g(f"https://mybusiness.googleapis.com/v4/{acct}/{loc['name']}/reviews"
               f"?pageSize=50" + (f"&pageToken={page}" if page else ""), token)
        total = d.get("totalReviewCount", total)
        avg = d.get("averageRating", avg)
        for rv in d.get("reviews", []):
            reply = rv.get("reviewReply") or {}
            rows.append({
                "company_id": cid, "review_id": rv["reviewId"],
                "reviewer_name": (rv.get("reviewer") or {}).get("displayName"),
                "star_rating": star.get(rv.get("starRating", ""), None),
                "comment": rv.get("comment"), "create_time": rv.get("createTime"),
                "reply_comment": reply.get("comment") or None,
                "reply_time": reply.get("updateTime") or None,
                "source": "gbp-v4", "synced_at": now})
        page = d.get("nextPageToken")
        if not page or len(rows) >= 500:
            break
    if not rows:
        return f"{slug}: 0 reviews on GBP"
    hdrs = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
    requests.delete(f"{SB_URL}/rest/v1/marketing_gbp_reviews?company_id=eq.{cid}",
                    headers=hdrs, timeout=30)
    _sb_upsert("marketing_gbp_reviews", rows, on_conflict="company_id,review_id")
    latest = max((r.get("create_time") or "" for r in rows), default="") or None
    patch = {"last_review_at": latest}
    if total is not None:
        patch["review_count"] = total
    if avg is not None:
        patch["rating"] = round(float(avg), 1)
    requests.patch(f"{SB_URL}/rest/v1/marketing_gbp_profiles?company_id=eq.{cid}",
                   headers={**hdrs, "Content-Type": "application/json",
                            "Prefer": "return=minimal"},
                   data=json.dumps(patch), timeout=30)
    return (f"{slug}: {len(rows)} reviews (v4), profile {avg}/{total}, "
            f"latest {(latest or '?')[:10]}")


def import_gbp_media(slug: str, cap: int = 40) -> str:
    """Import the client's existing GBP photo library into
    branding/{cid}/job-photos/posted/ as gbp-{mediaKey}.jpg. Two consumers:
    the app's Photos tab (lists exactly that folder) and gbp_post's LRU
    rotation (recycles posted/ when no fresh crew uploads exist) — fixes
    NaRestCo re-posting its single July 1 crew photo on every Google post.
    Lands in posted/ (NOT the root) because gbp_photos.py drains the root UP
    to the GBP — importing to the root would re-upload the client's own
    photos back to their profile as duplicates. Skips PROFILE/COVER/LOGO
    shots and anything we ourselves published (supabase sourceUrl)."""
    import urllib.request as _rq
    cid = company_id_for(slug)
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    token = get_access_token(cid) if cid else None
    if not token:
        return f"{slug}: no token"
    loc = find_location(token, brand.get("place_id", ""))
    if not loc:
        return f"{slug}: no GBP location"
    acct = _g(f"{ACCT_API}/accounts", token)["accounts"][0]["name"]
    hdrs = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}

    def _names(sub):
        r = requests.post(f"{SB_URL}/storage/v1/object/list/branding",
                          headers={**hdrs, "Content-Type": "application/json"},
                          json={"prefix": f"{cid}/job-photos/{sub}", "limit": 1000},
                          timeout=30)
        return [f["name"] for f in (r.json() or [])
                if isinstance(f, dict) and f.get("id")]

    # rotation renames recycled files to r{ts}_{base} — compare stripped basenames
    have = {re.sub(r"^r\d+_", "", n) for n in _names("") + _names("posted/")}
    imported, scanned, page = 0, 0, None
    while imported < cap:
        d = _g(f"https://mybusiness.googleapis.com/v4/{acct}/{loc['name']}/media"
               + (f"?pageToken={page}" if page else ""), token)
        for m in d.get("mediaItems", []):
            scanned += 1
            if m.get("mediaFormat") != "PHOTO":
                continue
            cat = (m.get("locationAssociation") or {}).get("category", "")
            if cat in ("PROFILE", "COVER", "LOGO"):
                continue
            if "supabase" in (m.get("sourceUrl") or ""):
                continue
            fname = "gbp-" + m["name"].split("/")[-1][:48] + ".jpg"
            if fname in have:
                continue
            url = m.get("googleUrl") or m.get("sourceUrl")
            if not url:
                continue
            if "googleusercontent.com" in url:
                base, sep, tail = url.rpartition("=")
                url = (base if sep and re.match(r"^[swh]\d+", tail) else url) + PHOTOS_MAX_DIM
            try:
                data = _rq.urlopen(url, timeout=60).read()
                up = requests.post(
                    f"{SB_URL}/storage/v1/object/branding/{cid}/job-photos/posted/{fname}",
                    headers={**hdrs, "Content-Type": "image/jpeg"}, data=data, timeout=60)
                if up.status_code in (200, 201):
                    imported += 1
                    have.add(fname)
            except Exception as e:
                print(f"   ! {fname}: {str(e)[:80]}")
            if imported >= cap:
                break
        page = d.get("nextPageToken")
        if not page:
            break
    return f"{slug}: {imported} GBP photo(s) imported into rotation ({scanned} scanned)"


def cmd_reviews(args) -> int:
    for slug in _clients(args):
        try:
            out = sync_reviews_v4(slug)
        except Exception as e:
            out = f"{slug}: v4 failed ({str(e)[:100]})"
        if "no token" in out or "v4 failed" in out:
            out += " -> DFS fallback: " + sync_reviews(slug)
        print("  " + out)
    return 0


def cmd_media_import(args) -> int:
    for slug in _clients(args):
        try:
            print("  " + import_gbp_media(slug))
        except Exception as e:
            print(f"  {slug}: ERROR ({str(e)[:120]})")
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
    # Best-effort riders on the scheduled sync: fresh reviews (v4 overrides the
    # DFS aggregate written above) + any new GBP photos into the post rotation.
    extras = []
    for fn in (lambda: sync_reviews_v4(slug, token=token, loc=loc),
               lambda: import_gbp_media(slug)):
        try:
            extras.append(fn())
        except Exception as e:  # riders never fail the profile sync
            extras.append(f"rider error: {str(e)[:100]}")
    return (f"{slug}: profile synced (rating {agg.get('rating')}/{agg.get('review_count')}) + "
            f"{len(rows)} days of insights\n    " + "\n    ".join(extras))


def cmd_sync(args) -> int:
    failures = 0
    for slug in _clients(args):
        try:
            print("  " + sync(slug))
        except Exception as e:  # one client must never abort a scheduled --all run
            failures += 1
            print(f"  {slug}: ERROR ({type(e).__name__}: {str(e)[:200]}) — skipped")
    if failures:
        print(f"  ({failures} client(s) errored and were skipped — see above)")
    return 0  # non-fatal: a client error shouldn't fail the scheduled run


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
    last = ""
    for attempt in (1, 2):  # retry once: transient empty/non-JSON or overload happens
        r = requests.post(ANTHROPIC_API, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            data=json.dumps({"model": ANTHROPIC_MODEL, "max_tokens": 16384,
                             "system": system, "messages": [{"role": "user", "content": user}]}))
        if r.status_code in (429, 500, 503, 529):  # overloaded/rate-limited — retry
            last = f"HTTP {r.status_code}"
            continue
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        if not text:
            last = "empty response"
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Model sometimes reasons out loud before the JSON despite the
            # strict-JSON instruction (narestco's negative_services reliably
            # triggers this). Salvage the outermost {...} block before failing.
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            last = f"non-JSON: {text[:120]!r}"
    raise RuntimeError(f"Anthropic did not return valid JSON after 2 tries ({last})")


def _matches(term: str, pool: list) -> bool:
    """Loose membership: normalized substring match against a confirmed list."""
    n = _norm(term)
    return bool(n) and any(n == _norm(p) or n in _norm(p) or _norm(p) in n for p in pool)


def _norm_service(term: str) -> str:
    """Normalize a service item for whole-phrase comparison. Handles structured
    GBP ids ('job_type_id:mold_remediation' -> same key as 'Mold Remediation')."""
    t = re.sub(r"^job_type_id:", "", (term or "").strip())
    return _norm(t.replace("_", " "))


def _matches_exact(term: str, pool: list) -> bool:
    """Strict membership: whole-phrase equality on the normalized string. Only this
    justifies a forced REMOVE — substring hits (e.g. 'plumbing' inside 'Plumbing
    Leak Water Cleanup') are too loose to auto-act on."""
    n = _norm_service(term)
    return bool(n) and any(n == _norm_service(p) for p in pool)


def _geogrid_summary(cid: str) -> list:
    """Compact geo-grid picture for the optimizer payload: per tracked keyword,
    the latest scan's avg rank / top-3 share plus the previous scan's for
    trend. Grid movement is the ground truth the suggestions should chase."""
    scans = _sb(f"marketing_geogrid_scans?company_id=eq.{cid}"
                f"&order=scanned_at.desc&limit=16"
                f"&select=keyword,city_label,avg_rank,pct_in_top3,scanned_at")
    by_kw: dict = {}
    for s in scans:
        by_kw.setdefault(s["keyword"], []).append(s)
    out = []
    for kw, runs in by_kw.items():
        cur, prev = runs[0], (runs[1] if len(runs) > 1 else None)
        out.append({
            "keyword": kw, "city": cur.get("city_label"),
            "scanned": (cur.get("scanned_at") or "")[:10],
            "avg_rank": cur.get("avg_rank"), "pct_top3": cur.get("pct_in_top3"),
            "prev_avg_rank": prev.get("avg_rank") if prev else None,
            "prev_pct_top3": prev.get("pct_in_top3") if prev else None,
        })
    return out


def _propose_new_categories(cid: str, token: str, g: dict, do: list,
                            dont: list, geo: list) -> list:
    """Propose NEW GBP categories (the audit only classifies ones already on
    the listing). Model suggests names grounded in confirmed services + grid
    weakness; each candidate is validated against Google's REAL category
    taxonomy and only exact matches survive — the gcid rides in `canonical`
    so the app can apply it with one click. Never auto_safe: category changes
    are the highest-stakes GBP edit (re-verification risk)."""
    existing = {str(g.get("primary_category") or "").lower()} | {
        str(c).lower() for c in (g.get("additional_categories") or [])}
    sysmsg = (
        "You suggest ADDITIONAL Google Business Profile categories for a local "
        "restoration company. Only suggest categories that plausibly exist in "
        "Google's fixed GBP category taxonomy and that the business genuinely "
        "serves per its confirmed services. Skip anything matching "
        "negative_services. Max 4. Return ONLY JSON: {\"candidates\": "
        "[{\"name\": str, \"reason\": str (under 12 words), \"confidence\": num}]}")
    user = json.dumps({
        "existing_categories": sorted(existing),
        "confirmed_services": do[:15], "negative_services": dont,
        "geo_grid_ranking": geo[:6]}, indent=1)
    out = _anthropic_json(sysmsg, "Propose categories.\n\nDATA:\n" + user)
    rows = []
    for cand in (out.get("candidates") or [])[:4]:
        name = str(cand.get("name") or "").strip()
        if not name or name.lower() in existing:
            continue
        try:
            # Taxonomy validation. The categories filter only accepts a SINGLE
            # token (multi-word 400s, quoted is silently ignored) — so search
            # on the longest word and exact-match the full name locally.
            tok = max(name.split(), key=len)
            r = requests.get(f"{INFO_API}/categories",
                             params={"regionCode": "US", "languageCode": "en-US",
                                     "view": "BASIC", "pageSize": 100,
                                     "filter": f"displayName={tok}"},
                             headers={"Authorization": f"Bearer {token}"}, timeout=30)
            match = next((c for c in r.json().get("categories", [])
                          if c.get("displayName", "").lower() == name.lower()), None)
        except Exception:
            match = None
        if not match:
            continue
        rows.append({
            "company_id": cid, "item": match["displayName"], "item_type": "category",
            "source": "confirmed", "verdict": "ADD",
            "reason": (cand.get("reason") or "Matches a confirmed service line.")
                      + " Verified against Google's category list.",
            "confidence": min(float(cand.get("confidence") or 0.7), 0.9),
            "canonical": match["name"],  # categories/gcid:... — the app applies via this
            "auto_safe": False, "status": "open"})
    return rows


def _suggest_description(cid: str, slug: str, loc: dict, g: dict,
                         do: list, dont: list, token: str) -> dict | None:
    """AI business-description pass. Empty description on Google -> write and
    push immediately (the one case where automatic can't make anything worse).
    Existing description -> generate a candidate; if the model judges it a real
    improvement, park it as an open 'description' suggestion for one-click
    approval in the app's Locations tab. Claims-safe by construction: the model
    only sees confirmed services/areas — never credentials — and is forbidden
    from inventing any. Returns a suggestion row or None."""
    cur = ((loc.get("profile") or {}).get("description") or "").strip()
    pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
    areas = pi.get("service_areas", [])
    primary = next((a for a in areas if a.get("primary")), areas[0] if areas else {})
    sysmsg = (
        "You write the Google Business Profile business description for a local "
        "restoration company. Hard rules:\n"
        "- 600 to 730 characters total. The FIRST 240 characters must stand alone "
        "(Google truncates there behind 'More') and carry the city plus the core "
        "services.\n"
        "- Natural, confident, human voice. No keyword stuffing, no ALL CAPS, no "
        "em dashes.\n"
        "- NEVER mention licenses, certifications, insurance status, years in "
        "business, awards, or guarantees unless they appear in the data given.\n"
        "- Google policy: no URLs, no phone numbers, no prices or promotions.\n"
        "- Mention the primary city naturally; weave in the highest-value services "
        "without cataloguing every one.\n"
        'Return ONLY JSON: {"description": str, "better_than_current": bool, '
        '"reason": str}. reason under 12 words; judge better_than_current on '
        "clarity, local relevance, and coverage of what they actually offer.")
    user = json.dumps({
        "business": loc.get("title") or slug,
        "primary_category": g.get("primary_category"),
        "primary_city": f"{primary.get('city', '')}, {primary.get('state', '')}".strip(", "),
        "service_areas": [a.get("city") for a in areas if a.get("city")][:8],
        "confirmed_services": do[:12], "never_mention_offering": dont,
        "current_description": cur or "(none)"}, indent=1)
    out = _anthropic_json(sysmsg, "Write the description.\n\nDATA:\n" + user)
    desc = (out.get("description") or "").replace("—", ", ").replace("–", ", ").strip()
    if not desc or len(desc) > 750:
        return None
    hdrs = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json", "Prefer": "return=minimal"}
    if not cur:
        r = requests.patch(f"{INFO_API}/{loc['name']}?updateMask=profile.description",
                           headers={"Authorization": f"Bearer {token}",
                                    "Content-Type": "application/json"},
                           json={"profile": {"description": desc}}, timeout=30)
        if r.status_code == 200:
            requests.patch(f"{SB_URL}/rest/v1/marketing_gbp_profiles?company_id=eq.{cid}",
                           headers=hdrs, data=json.dumps({"description": desc}), timeout=30)
            print(f"   description: was empty -> wrote and pushed ({len(desc)} chars)")
        else:
            print(f"   description: auto-push failed HTTP {r.status_code}: {r.text[:120]}")
        return None
    if not out.get("better_than_current"):
        return None
    return {"company_id": cid, "item": "business-description", "item_type": "description",
            "source": "gbp", "verdict": "ADD",
            "reason": desc,  # the proposed text itself; the app renders from here
            "confidence": 0.8, "canonical": None, "auto_safe": False, "status": "open"}


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

    try:  # grid movement is the outcome the suggestions should chase
        geo = _geogrid_summary(cid)
    except Exception:
        geo = []
    payload = {
        "business": loc.get("title"), "primary_category": g["primary_category"],
        "additional_categories": g["additional_categories"],
        "live_gbp_services": g["services"], "website_service_pages": site,
        "confirmed_services": do, "negative_services": dont,
        "geo_grid_ranking": geo,
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
        "Keep each reason under 12 words. Do not apply auto_safe; just classify. "
        "geo_grid_ranking shows live map-pack position per keyword (avg_rank, share of "
        "grid cells in the top 3, and the previous scan for trend) — when a weak or "
        "declining keyword maps to a service/page item, prioritize it and cite the grid "
        "position in the reason.\n\n"
        f"DATA:\n{json.dumps(payload, indent=2)}")
    result = _anthropic_json(rules, instruction)
    items = result.get("items", [])

    # Structured (job_type_id) services the model classified KEEP — a free-form
    # REMOVE of the same normalized service contradicts them and must never
    # auto-execute (e.g. free-form "Mold Remediation" vs job_type_id:mold_remediation).
    structured_keeps = {
        _norm_service(it.get("item", "")) for it in items
        if it.get("verdict") == "KEEP" and str(it.get("item", "")).startswith("job_type_id")}

    # Deterministic guardrail overrides the model on the non-negotiables.
    for it in items:
        term, vtype = it.get("item", ""), it.get("item_type")
        if _matches_exact(term, dont):
            # Whole-phrase match on a declared negative -> forced REMOVE.
            it["verdict"], it["confidence"] = "REMOVE", max(it.get("confidence", 0), 0.95)
            it["reason"] = "Client declared they do NOT offer this (negative_services)."
        elif _matches(term, dont):
            # Substring-only (fuzzy) hit — too loose to auto-remove ('plumbing' in
            # 'Plumbing Leak Water Cleanup'). Surface for a human, never auto-act.
            it["verdict"] = "NEEDS-REVIEW"
            it["confidence"] = min(float(it.get("confidence", 0) or 0), 0.6)
            it["reason"] = "Fuzzy match to a negative_services entry — verify before removing."
        if (it.get("verdict") == "REMOVE"
                and not str(term).startswith("job_type_id")
                and _norm_service(term) in structured_keeps):
            # Conflict: the structured equivalent is KEEP — never auto-remove.
            it["verdict"] = "NEEDS-REVIEW"
            it["confidence"] = min(float(it.get("confidence", 0) or 0), 0.6)
            it["reason"] = "Conflicts with a KEEP on the structured (job_type_id) equivalent."
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

    # NEW-category proposals (Santino 2026-07-25): the audit above only
    # classifies categories ALREADY on the listing; this proposes missing
    # ones, taxonomy-validated, gcid in `canonical`, never auto_safe.
    try:
        rows.extend(_propose_new_categories(cid, token, g, do, dont, geo))
    except Exception as e:
        print(f"   category proposal pass failed: {str(e)[:120]}")

    # Description pass (Santino 2026-07-24: the Locations editor must be
    # AI-recommended, not edit-your-own). Empty on Google -> written and pushed
    # automatically (nothing to overwrite = nothing to break). Existing ->
    # parked as an open suggestion the app approves with one click. Flows
    # through the settled-keys filter below, so a dismissal sticks.
    try:
        drow = _suggest_description(cid, slug, loc, g, do, dont, token)
        if drow:
            rows.append(drow)
    except Exception as e:  # advisory pass; never blocks the audit
        print(f"   description pass failed: {str(e)[:120]}")
    if rows:
        _sb_delete("marketing_gbp_suggestions", f"company_id=eq.{cid}&status=eq.open")
        # Never resurrect suggestions a human already settled: upserting with
        # status='open' on (company_id,item_type,item) would flip dismissed/applied
        # rows back to open. Exclude those keys so human decisions stick.
        settled = _sb(f"marketing_gbp_suggestions?company_id=eq.{cid}"
                      f"&status=in.(dismissed,applied)&select=item,item_type")
        settled_keys = {(s.get("item_type"), s.get("item")) for s in settled}
        rows = [r for r in rows if (r["item_type"], r["item"]) not in settled_keys]
    if rows:
        _sb_upsert("marketing_gbp_suggestions", rows, on_conflict="company_id,item_type,item")
    from collections import Counter
    by_verdict = Counter(it.get("verdict") for it in items)
    return {"slug": slug, "summary": dict(by_verdict),
            "auto_safe": sum(1 for it in items if it.get("auto_safe")), "items": items}


def cmd_optimize(args) -> int:
    failures = 0
    for slug in _clients(args):
        try:
            r = optimize(slug)
        except Exception as e:  # one client must never abort the whole --all run
            failures += 1
            print(f"  {slug}: ERROR ({type(e).__name__}: {str(e)[:200]}) — skipped")
            continue
        if r.get("error"):
            print(f"  {slug}: skip ({r['error']})")
            continue
        print(f"  {slug}: {r['summary']} | {r['auto_safe']} auto-safe")
        for it in r["items"]:
            if it["verdict"] != "KEEP":
                flag = "AUTO" if it.get("auto_safe") else "review"
                print(f"     [{it['verdict']:<12}] ({flag}) {it['item']} — {it['reason']}")
    if failures:
        print(f"  ({failures} client(s) errored and were skipped — see above)")
    return 0  # non-fatal: a client error shouldn't fail the scheduled run


# --------------------------------------------------------------------------- #
# "Create page" execution — drain the marketing_page_requests queue into the
# client's plan-input (the canonical services list the build pipeline reads), so
# the next re-plan + rebuild scaffolds, renders, and deploys a page per service.
# --------------------------------------------------------------------------- #
def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def service_to_slug(display: str, client_slug: str) -> str:
    """Map a GBP service display name to a catalog service slug if one matches
    (by normalized name), else a fresh slug from the display name. Catalog is
    the CLIENT's vertical catalog (templates/{vertical}/services.json)."""
    cat = json.loads(verticals.resolve_template(client_slug, "services.json").read_text())
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


def ensure_catalog_entry(slug: str, display_name: str, client_slug: str) -> bool:
    """Make sure the CLIENT'S VERTICAL services catalog has this service so plan_site
    won't reject it (plan_site dies on slugs not in the catalog). Clients declare
    services the template doesn't have yet; append a minimal VALID entry to
    templates/{vertical}/services.json. Returns True if added."""
    cat_path = verticals.resolve_template(client_slug, "services.json")
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


def _sh(cmd: list) -> tuple:
    """Run a raw (non-python) command from the repo root."""
    import subprocess
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
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

    # 4. commit first — sync-deploy does a `git subtree split` over COMMITTED history, so
    #    the new pages (+ plan/catalog changes) must be committed or they (a) won't be in
    #    the push and (b) make the tree dirty, which sync-deploy refuses.
    _sh(["git", "add", "clients", "sites", "templates"])
    _sh(["git", "commit", "-m", f"gbp: build pages for {slug} [automated]"])  # no-op if nothing staged

    # 5. deploy what rendered — the gate. 13 good pages beat deploying nothing over 1 straggler.
    rcd, logd = _run(["scripts/build_site.py", "sync-deploy", "--slug", slug, "--branch", "main"])
    if rcd != 0:
        return False, f"BUILD FAILED at `sync-deploy` -> ...{logd.strip()[-400:]}"
    return True, "built + deployed (plan -> add-pages -> render -> commit -> sync-deploy main)" + render_note


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
            sslug = service_to_slug(r["service"], slug)
            if ensure_catalog_entry(sslug, r["service"], slug):
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


PHOTOS_MAX_DIM = "=s2560"  # googleusercontent size suffix: long edge 2560px


def cmd_photos(args) -> int:
    """Download every GBP photo on the client's connected account to
    clients/{slug}/gbp-photos/{location}/NNN-{category}.jpg for site use.
    Idempotent: existing files are skipped (name = position + category)."""
    import urllib.request as _rq
    for slug in _clients(args):
        cid = company_id_for(slug)
        token = get_access_token(cid) if cid else None
        if not token:
            print(f"\n## {slug}: no business.manage token — connect this client's GBP")
            continue
        accts = _g(f"{ACCT_API}/accounts", token).get("accounts", [])
        pulled = 0
        for a in accts:
            locs = _g(f"{INFO_API}/{a['name']}/locations?readMask=name,title"
                      "&pageSize=100", token).get("locations", [])
            for l in locs:
                loc_slug = re.sub(r"[^a-z0-9]+", "-", l["title"].lower()).strip("-")
                dest = ROOT / "clients" / slug / "gbp-photos" / loc_slug
                media = _g(f"https://mybusiness.googleapis.com/v4/{a['name']}"
                           f"/{l['name']}/media", token)
                items = [m for m in media.get("mediaItems", [])
                         if m.get("mediaFormat") == "PHOTO"]
                print(f"\n## {slug} / {l['title']}: {len(items)} photo(s)")
                for i, m in enumerate(items):
                    cat = (m.get("locationAssociation") or {}).get(
                        "category", "PHOTO").lower()
                    out = dest / f"{i:03d}-{cat}.jpg"
                    if out.exists():
                        continue
                    url = m.get("googleUrl") or m.get("sourceUrl")
                    if not url:
                        continue
                    if "googleusercontent.com" in url:
                        # normalize any baked-in size suffix (=s640 etc.) to full-size
                        base, sep, tail = url.rpartition("=")
                        url = (base if sep and re.match(r"^[swh]\d+", tail) else url) + PHOTOS_MAX_DIM
                    dest.mkdir(parents=True, exist_ok=True)
                    try:
                        out.write_bytes(_rq.urlopen(url, timeout=60).read())
                        pulled += 1
                    except Exception as e:
                        print(f"   ! {out.name}: {e}")
                print(f"   -> {dest} ({len(list(dest.glob('*.jpg')) if dest.exists() else [])} on disk)")
        print(f"\n{slug}: {pulled} new photo(s) downloaded")
    return 0


def main() -> int:
    if not (SB_URL and SB_KEY and G_CID and G_SECRET):
        print("ERROR: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GOOGLE_OAUTH_CLIENT_ID, "
              "GOOGLE_OAUTH_CLIENT_SECRET must be set in rank-ai/.env", file=sys.stderr)
        return 1
    ap = argparse.ArgumentParser(description="Google Business Profile module")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("read", "reconcile", "sync", "reviews", "photos", "media-import"):
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
            "reviews": cmd_reviews, "photos": cmd_photos, "media-import": cmd_media_import,
            "add-services": cmd_add_services,
            "create-pages": cmd_create_pages, "optimize": cmd_optimize}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
