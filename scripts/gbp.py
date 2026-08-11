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
    python3 scripts/gbp.py read          --slug narestco
    python3 scripts/gbp.py reconcile     --slug narestco
    python3 scripts/gbp.py reconcile     --all
    python3 scripts/gbp.py descriptions  --slug narestco [--apply]   # per-service descriptions

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
import claims_lint  # noqa: E402 — brand-truth gate for generated copy
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


def _place_id_from_connection(company_id: str | None) -> str | None:
    """place_id from the company's OWN google connection (the OAuth exchange
    auto-selects it). Repo plan-input.json can lag behind a connect — e.g.
    go-green 2026-07-27: connected w/ location selected, first sync skipped
    on the stale brand block. Never read another company's row here."""
    if not company_id:
        return None
    rows = _sb("user_integrations?provider=eq.google&select=connection_metadata"
               f"&client_id=eq.{company_id}")
    for row in rows or []:
        md = row.get("connection_metadata") or {}
        if md.get("place_id"):
            return md["place_id"]
    return None


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
    """Find the location matching the client's place_id across all managed accounts.

    A falsy place_id means the client has no Google connection of its own. It must
    never be matched: `get_access_token` falls back to an agency token that manages
    every client location, and a location whose metadata carries no placeId would
    satisfy `None == None` and hand back a STRANGER's listing. Found 2026-08-05 —
    aaa-water-damage (zero google rows) was resolving to "ProBrite Gen", a Houston
    business, and every read and write for AAA was aimed at it.
    """
    if not place_id:
        return None
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
    place_id = brand.get("place_id") or _place_id_from_connection(cid)
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


def log_change(cid: str | None, change_type: str, summary: str,
               actor: str = "automation", meta: dict | None = None) -> None:
    """Change-log (Santino 2026-07-31): every GBP change we make lands in
    marketing_gbp_changes — client-visible proof of work in Reports and the
    source for monthly summaries. Best-effort; never fails the change."""
    if not cid:
        return
    try:
        requests.post(
            f"{SB_URL}/rest/v1/marketing_gbp_changes",
            headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            data=json.dumps({"company_id": cid, "change_type": change_type,
                             "summary": summary[:300], "actor": actor,
                             "meta": meta or {}}), timeout=15)
    except Exception:
        pass


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
    try:
        series_list = _g(url, token).get("multiDailyMetricTimeSeries", [])
    except requests.HTTPError as e:
        # 403 on unverified/limited listings (go-green 2026-07-27) — insights
        # are a nice-to-have; never let them kill the whole first sync
        sys.stderr.write(f"  insights unavailable ({str(e)[:80]}) — continuing\n")
        return daily
    for series in series_list:
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
    # same fallback sync() uses — auto-built plan-inputs have no place_id
    place = brand.get("place_id") or _place_id_from_connection(cid)
    loc = find_location(token, place or "")
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


def _stored_review_count(slug: str) -> int:
    """review_count already on the profile row — the cheap 'reviews exist' check."""
    cid = company_id_for(slug)
    rows = _sb(f"marketing_gbp_profiles?company_id=eq.{cid}&select=review_count") if cid else []
    return (rows[0].get("review_count") or 0) if rows else 0


def cmd_reviews(args) -> int:
    for slug in _clients(args):
        try:
            out = sync_reviews_v4(slug)
        except Exception as e:
            out = f"{slug}: v4 failed ({str(e)[:100]})"
        # DFS fallback also covers the v4 empty-{} account quirk (ProRestoration
        # 2026-08-04: v4 returns 200 {} on its personal-account connection while
        # the listing really shows 4.8/105) — but only when the profile row
        # proves reviews exist, so genuinely-zero listings never pay for a task.
        if ("no token" in out or "v4 failed" in out
                or ("0 reviews on GBP" in out and _stored_review_count(slug) > 0)):
            out += " -> DFS fallback: " + sync_reviews(slug)
        print("  " + out)
    return 0


def set_phone(slug: str) -> str:
    """Call-tracking phone swap (Santino 2026-07-28): tracking number becomes
    the GBP PRIMARY phone, the real number moves to additionalPhones — the
    Google-supported attribution pattern; citations keep the real number.
    Reads the number from integration_settings.call_tracking.gbp (set by
    scripts/call_tracking.py). Run ONLY after a human test call confirms
    forwarding works."""
    cid = company_id_for(slug)
    co = _sb(f"companies?id=eq.{cid}&select=phone,integration_settings")
    if not co:
        return f"{slug}: no company row"
    ints = co[0].get("integration_settings") or {}
    if isinstance(ints, str):
        ints = json.loads(ints)
    tracking = ((ints.get("call_tracking") or {}).get("gbp") or {}).get("number")
    real = co[0].get("phone") or ""
    if not tracking:
        return f"{slug}: no gbp tracking number provisioned — run call_tracking.py first"
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    place = brand.get("place_id") or _place_id_from_connection(cid)
    token = get_access_token(cid) if cid else None
    if not (token and place):
        return f"{slug}: skip (no token / place_id)"
    loc = find_location(token, place)
    if not loc:
        return f"{slug}: no GBP location"
    body = {"phoneNumbers": {"primaryPhone": tracking,
                             "additionalPhones": [real] if real else []}}
    r = requests.patch(f"{INFO_API}/{loc['name']}?updateMask=phoneNumbers",
                       headers={"Authorization": f"Bearer {token}",
                                "Content-Type": "application/json"},
                       data=json.dumps(body), timeout=60)
    if not r.ok:
        return f"{slug}: PATCH failed {r.status_code}: {r.text[:200]}"
    log_change(cid, "phone",
               "Call-tracking number set as primary phone on the Google listing",
               actor="agency")
    return (f"{slug}: GBP primary phone -> {tracking} (tracking), "
            f"real {real} moved to additional")


def cmd_set_phone(args) -> int:
    for slug in _clients(args):
        print("  " + set_phone(slug))
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
    place = brand.get("place_id") or _place_id_from_connection(cid)
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
    def _reviews_rider() -> str:
        out = sync_reviews_v4(slug, token=token, loc=loc)
        # v4 can answer 200 {} for some connections (ProRestoration 2026-08-04:
        # personal-account token, listing really 4.8/105) — when the DFS
        # aggregate proves reviews exist, pull them via the DFS task instead so
        # the app's review list doesn't sit empty under a 105-review header.
        if "0 reviews on GBP" in out and (agg.get("review_count") or 0) > 0:
            out += " -> DFS fallback: " + sync_reviews(slug)
        return out
    extras = []
    for fn in (_reviews_rider,
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
    place = brand.get("place_id") or _place_id_from_connection(cid)
    if not (token and place):
        return f"{slug}: skip (no token / place_id)"
    loc = find_location(token, place)
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
    for s in confirmed:
        log_change(cid, "service_add", f"Service added to Google listing: {s}",
                   actor="optimizer")
    return f"{slug}: added {len(confirmed)}/{len(added)} -> {confirmed} (listing now has {len(back.get('serviceItems', []))} services)"


def cmd_add_services(args) -> int:
    print("  " + add_services(args.slug, args.service))
    return 0


def _svc_label(item: str) -> str:
    """Human display label for a suggestion item ('job_type_id:mold_removal'
    -> 'Mold Removal'; free-form names pass through)."""
    s = str(item or "").strip()
    if s.startswith("job_type_id:"):
        return s[len("job_type_id:"):].replace("_", " ").title()
    return s


def apply_confirmed_services(cid: str, answer: str = "",
                             dry_run: bool = False) -> dict:
    """A client gave a clear YES to the GBP service sanity-check — APPLY it
    (Santino 2026-08-03 policy change: "If Curt says yes, why not just add it
    automatically? Waiting for my approval doesn't seem necessary — they've
    already confirmed"). No approval click. What happens:

      1. Open NEEDS-REVIEW service suggestions become client-confirmed:
         rows already ON the listing (source 'gbp') flip to KEEP + status
         'applied' (nothing to change on Google — the client just confirmed
         they belong); rows NOT on the listing flip to source 'confirmed'
         verdict ADD and ride the apply below.
      2. Every open confirmed/ADD SERVICE is written to the GBP listing NOW
         via add_services() — which records each add in
         marketing_gbp_changes — and its suggestion row flips to 'applied'
         with the confirmation stamped in the reason: done-with-evidence,
         visible on the board, never hidden. If the GBP write FAILS the rows
         stay open (nothing is recorded that didn't happen).
      3. Every open confirmed/ADD PAGE is queued into
         marketing_page_requests (status 'queued'); the gbp-maintenance
         workflow's create-pages --build drains the queue into plan-input ->
         render -> deploy. Rows flip to 'applied' (= queued for build).
      4. CATEGORY changes are NEVER auto-applied (highest-stakes GBP edit,
         re-verification risk) — NEEDS-REVIEW categories flip to
         confirmed/ADD but STAY OPEN for the app's one-click approval.
      5. The strategist board cards ("Add N confirmed service(s)…" /
         "Create N website page(s)…") flip to done with evidence appended,
         and the whole movement lands in marketing_work_log.

    Mixed/negative answers never reach this function — the caller
    (client_concierge.route_confirmed_services) escalates those for manual
    mapping. Returns a summary dict."""
    import datetime as dt
    import urllib.parse
    slug = _slug_for_company(cid)
    out: dict = {"company_id": cid, "slug": slug, "kept": [], "added": [],
                 "pages_queued": [], "categories_pending": [], "errors": []}
    if not slug:
        out["errors"].append("no pipeline slug for this company")
        return out
    stamp = dt.date.today().isoformat()
    confirm_note = f"Client confirmed by SMS {stamp}" + \
        (f": {answer.strip()[:120]}" if answer.strip() else "")

    # 1. NEEDS-REVIEW service/category rows -> client-confirmed shapes.
    nr = _sb(f"marketing_gbp_suggestions?company_id=eq.{cid}"
             "&status=eq.open&verdict=eq.NEEDS-REVIEW"
             "&item_type=in.(service,category)&select=item,item_type,source,reason")
    for row in nr:
        item = row["item"]
        enc = urllib.parse.quote(str(item), safe="")
        match = (f"company_id=eq.{cid}&item_type=eq.{row['item_type']}"
                 f"&item=eq.{enc}&status=eq.open")
        if row["item_type"] == "category":
            body = {"source": "confirmed", "verdict": "ADD",
                    "reason": f"{confirm_note} — category changes need the "
                              "one-click approval (never auto-applied)"}
            out["categories_pending"].append(_svc_label(item))
        elif row.get("source") == "gbp":
            # already on the listing; the confirmation settles it as KEEP
            body = {"source": "confirmed", "verdict": "KEEP",
                    "status": "applied",
                    "reason": f"{confirm_note} — already on the listing, kept"}
            out["kept"].append(_svc_label(item))
        else:
            body = {"source": "confirmed", "verdict": "ADD",
                    "reason": confirm_note}
        if dry_run:
            print(f"    [dry-run] would flip NEEDS-REVIEW {row['item_type']} "
                  f"{item!r} -> {body}")
        else:
            _sb_patch("marketing_gbp_suggestions", match, body)

    # 2. open confirmed/ADD services -> the GBP listing, right now.
    adds = _sb(f"marketing_gbp_suggestions?company_id=eq.{cid}"
               "&status=eq.open&verdict=eq.ADD&item_type=eq.service"
               "&source=eq.confirmed&select=item,reason")
    labels = [_svc_label(r["item"]) for r in adds]
    if labels:
        if dry_run:
            print(f"    [dry-run] would add {len(labels)} service(s) to the "
                  f"GBP: {labels}")
            out["added"] = labels
        else:
            msg = add_services(slug, labels)   # logs marketing_gbp_changes
            print(f"    [svc-apply] {msg}")
            ok = ("added" in msg or "nothing to add" in msg)
            if not ok:
                out["errors"].append(f"GBP write failed — rows left open: "
                                     f"{msg[:200]}")
            else:
                out["added"] = labels
                for r in adds:
                    enc = urllib.parse.quote(str(r["item"]), safe="")
                    _sb_patch("marketing_gbp_suggestions",
                              f"company_id=eq.{cid}&item_type=eq.service"
                              f"&item=eq.{enc}&status=eq.open",
                              {"status": "applied",
                               "reason": f"{str(r.get('reason') or '')[:120]}"
                                         f" — auto-applied {stamp} "
                                         "(client confirmed)"})

    # 3. open confirmed/ADD pages -> the page-build queue.
    pages = _sb(f"marketing_gbp_suggestions?company_id=eq.{cid}"
                "&status=eq.open&verdict=eq.ADD&item_type=eq.page"
                "&source=eq.confirmed&select=item,reason")
    if pages:
        existing = _sb(f"marketing_page_requests?company_id=eq.{cid}"
                       "&select=service,status")
        have = {str(r.get("service", "")).strip().lower() for r in existing
                if r.get("status") in ("queued", "building", "built")}
        for r in pages:
            svc = _svc_label(r["item"])
            if svc.strip().lower() in have:
                queued_note = "already in the page queue"
            elif dry_run:
                print(f"    [dry-run] would queue page request: {svc!r}")
                out["pages_queued"].append(svc)
                continue
            else:
                requests.post(
                    f"{SB_URL}/rest/v1/marketing_page_requests",
                    headers={"apikey": SB_KEY,
                             "Authorization": f"Bearer {SB_KEY}",
                             "Content-Type": "application/json",
                             "Prefer": "return=minimal"},
                    data=json.dumps({"company_id": cid, "service": svc,
                                     "status": "queued"}),
                    timeout=30).raise_for_status()
                queued_note = f"auto-queued {stamp}"
            out["pages_queued"].append(svc)
            if not dry_run:
                enc = urllib.parse.quote(str(r["item"]), safe="")
                _sb_patch("marketing_gbp_suggestions",
                          f"company_id=eq.{cid}&item_type=eq.page"
                          f"&item=eq.{enc}&status=eq.open",
                          {"status": "applied",
                           "reason": f"{str(r.get('reason') or '')[:120]} — "
                                     f"page {queued_note} (client confirmed)"})

    # 4. board cards flip to done WITH the evidence (visible, never hidden).
    if not dry_run and (out["added"] or out["kept"] or out["pages_queued"]):
        try:
            cards = _sb(f"marketing_action_plan?company_id=eq.{cid}"
                        "&action_type=in.(gbp_add_services,gbp_create_pages)"
                        "&status=eq.planned&select=id,action_type,rationale")
            for card in cards:
                if card["action_type"] == "gbp_add_services":
                    if not out["added"]:
                        continue
                    ev = ("services added to the Google listing: "
                          + ", ".join(out["added"]))
                else:
                    if not out["pages_queued"]:
                        continue
                    ev = ("pages queued for build: "
                          + ", ".join(out["pages_queued"]))
                _sb_patch("marketing_action_plan", f"id=eq.{card['id']}",
                          {"status": "done",
                           "rationale": (str(card.get("rationale") or "")
                                         + f"\n\nAUTO-APPLIED {stamp} (client "
                                           f"confirmed by SMS) — {ev}.")})
        except Exception as e:  # noqa: BLE001 — bookkeeping never blocks the apply
            out["errors"].append(f"board-card flip failed: {str(e)[:120]}")

    # 5. work ledger.
    if not dry_run:
        try:
            sys.path.insert(0, str(ROOT / "scripts"))
            from work_log import work_log
            if out["added"]:
                work_log(cid, "gbp", "services-applied",
                         "Added {} service(s) to the Google Business Profile "
                         "after the owner confirmed them by text: {}.".format(
                             len(out["added"]), ", ".join(out["added"])),
                         evidence={"services": out["added"],
                                   "answer": answer[:200]},
                         actor="automation", source="gbp.py apply_confirmed_services")
            if out["pages_queued"]:
                work_log(cid, "site", "pages-queued",
                         "Queued {} website page(s) for confirmed services: "
                         "{}.".format(len(out["pages_queued"]),
                                      ", ".join(out["pages_queued"])),
                         evidence={"pages": out["pages_queued"]},
                         actor="automation", source="gbp.py apply_confirmed_services")
        except Exception as e:  # noqa: BLE001
            print(f"    [work-log] warn: {str(e)[:100]}")
    return out


# --------------------------------------------------------------------------- #
# Per-service DESCRIPTIONS — every service item on the listing gets a short
# claims-safe description (max 300 chars, Google's cap). Field shapes verified
# against the live API 2026-08-11 (narestco read):
#   structuredServiceItem.description        (sibling of serviceTypeId)
#   freeFormServiceItem.label.description    (sibling of displayName)
# Copy is grounded in the client's OWN service pages when one exists, and the
# claims_lint truth table gates every credential/availability claim (davis
# once shipped "IICRC-certified 24/7" copy it had no right to — never again).
# Existing descriptions are NEVER overwritten; items are never dropped or
# reordered; categories are never touched.
# --------------------------------------------------------------------------- #
DESC_MODEL = "claude-sonnet-5"
DESC_MAX_CHARS = 300  # Business Information API cap on service descriptions


def _item_desc(item: dict) -> str:
    if "structuredServiceItem" in item:
        return (item["structuredServiceItem"].get("description") or "").strip()
    return (((item.get("freeFormServiceItem") or {}).get("label") or {})
            .get("description") or "").strip()


def _item_name(item: dict) -> str:
    if "structuredServiceItem" in item:
        return _svc_label(item["structuredServiceItem"].get("serviceTypeId", ""))
    return (((item.get("freeFormServiceItem") or {}).get("label") or {})
            .get("displayName") or "")


def _set_item_desc(item: dict, desc: str) -> None:
    if "structuredServiceItem" in item:
        item["structuredServiceItem"]["description"] = desc
    else:
        item["freeFormServiceItem"]["label"]["description"] = desc


def _fit_desc(text: str) -> str:
    """Normalize a generated description: no em/en dashes, no emoji/exotic
    glyphs, single-spaced, hard-capped at DESC_MAX_CHARS on a clean boundary."""
    t = re.sub(r"\s*[—–]\s*", ", ", str(text or ""))
    t = (t.replace("“", '"').replace("”", '"')
          .replace("‘", "'").replace("’", "'"))
    t = t.encode("ascii", "ignore").decode()  # emoji and friends drop out
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > DESC_MAX_CHARS:
        cut = t[:DESC_MAX_CHARS]
        stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        if stop > 150:
            t = cut[:stop + 1]
        else:
            t = cut[:cut.rfind(" ")].rstrip(",;:. ") + "."
    return t


def _page_intros(slug: str) -> dict:
    """{_norm(page stem): intro paragraph} from the client's rendered service
    pages — the grounding source for description copy."""
    d = ROOT / "sites" / slug / "src" / "content" / "services"
    out: dict = {}
    if not d.exists():
        return out
    for md in sorted(d.glob("*.md")):
        try:
            _, body = claims_lint.split_frontmatter(md.read_text())
        except Exception:
            continue
        para = next((p.strip() for p in body.split("\n\n")
                     if p.strip() and not p.strip().startswith(("#", "-", "*", "!"))), "")
        key = _norm(md.stem.replace("-", " "))
        if para and key:
            out[key] = re.sub(r"\s+", " ", para)[:600]
    return out


def _intro_for(name: str, intros: dict) -> str | None:
    n = _norm(name)
    if not n:
        return None
    if n in intros:
        return intros[n]
    best = max((k for k in intros if k in n or n in k), key=len, default=None)
    return intros[best] if best else None


def _desc_allowed_claims(truth: dict) -> list[str]:
    """Only claims the brand truth table backs may appear in copy."""
    claims = []
    if truth["is_247"]:
        claims.append("24/7 / emergency availability")
    claims += [f"certification: {c}" for c in truth["certifications"]]
    if truth["licensed_ok"]:
        claims.append("licensed and insured")
    if truth["family_owned"]:
        claims.append("family owned")
    if truth["founded_year"]:
        claims.append(f"in business since {truth['founded_year']}")
    if truth["response_minutes"]:
        claims.append(f"{truth['response_minutes']}-minute response")
    return claims


def _city_pool(areas: list) -> tuple[str, list[str]]:
    """Primary city + up to 6 rotation cities from service_areas. plan-input
    carries no population figures, so zip-code/neighborhood counts are the
    size proxy (Seattle's 8 zips outrank Kirkland's 2) — the heavier metro
    areas lead the rotation."""
    primary = next((a for a in areas if a.get("primary")), areas[0] if areas else {})
    others = [a for a in areas if a.get("city") and a is not primary]
    others.sort(key=lambda a: (len(a.get("zip_codes") or []),
                               len(a.get("neighborhoods") or [])), reverse=True)
    return (primary.get("city") or "", [a["city"] for a in others[:6]])


def _city_rotation(n: int, primary: str, others: list[str]) -> list[list[str]]:
    """Deterministic 1-2 city assignment per service: the primary city stays
    the most frequent, the big nearby cities spread evenly across the set,
    no description ever gets more than 2 cities, and no two ADJACENT services
    carry the same city set (repetition reads as boilerplate/stuffing)."""
    if not primary:
        return [[] for _ in range(n)]
    if not others:
        return [[primary] for _ in range(n)]
    if len(others) == 1:
        pats = [[primary, others[0]], [others[0]], [primary]]
        return [pats[j % 3] for j in range(n)]
    k = 0

    def draw() -> str:
        nonlocal k
        c = others[k % len(others)]
        k += 1
        return c

    out: list[list[str]] = []
    for j in range(n):
        r = j % 4
        if r == 0 or r == 3:
            out.append([primary, draw()])
        elif r == 1:
            out.append([draw(), draw()])
        else:
            out.append([draw()])
    return out


def _recent_desc_names(cid: str | None, hours: float) -> set[str]:
    """Lowercased service names whose descriptions WE wrote in the last
    `hours`, per the marketing_gbp_changes evidence trail (actor optimizer,
    change_type service_description). The refresh path may ONLY ever touch
    these — client-authored or pre-existing text is off limits."""
    import datetime as dt
    if not cid:
        return set()
    since = (dt.datetime.now(dt.timezone.utc)
             - dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = _sb(f"marketing_gbp_changes?company_id=eq.{cid}"
               "&change_type=eq.service_description&actor=eq.optimizer"
               f"&changed_at=gte.{since}&select=meta")
    names: set[str] = set()
    for row in rows:
        for n in ((row.get("meta") or {}).get("services") or []):
            names.add(str(n).strip().lower())
    return names


def service_descriptions(slug: str, apply: bool = False,
                         refresh_recent: float | None = None) -> str:
    """Generate (and with apply=True, PATCH) descriptions for every service
    item on the listing that is missing one. ONE model call per client.
    refresh_recent=N instead re-generates ONLY items whose description WE
    wrote within the last N hours (marketing_gbp_changes is the evidence) —
    a narrow rewrite path so a prompt upgrade can reach our own fresh copy
    without ever touching client-authored or long-standing text."""
    cid = company_id_for(slug)
    pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
    brand = pi.get("brand", {})
    token = get_access_token(cid) if cid else None
    place = brand.get("place_id") or _place_id_from_connection(cid)
    if not (token and place):
        return f"{slug}: skip (no token / place_id)"
    loc = find_location(token, place)
    if not loc:
        return f"{slug}: skip (no GBP location)"
    items = loc.get("serviceItems", [])
    if not items:
        return f"{slug}: no service items on the listing"
    if refresh_recent:
        ours = _recent_desc_names(cid, refresh_recent)
        targets = [(i, it) for i, it in enumerate(items)
                   if _item_desc(it) and _item_name(it).strip().lower() in ours]
        if not targets:
            return (f"{slug}: no descriptions of ours from the last "
                    f"{refresh_recent:g}h — nothing to refresh")
    else:
        targets = [(i, it) for i, it in enumerate(items) if not _item_desc(it)]
        if not targets:
            return f"{slug}: all {len(items)} service descriptions already set"

    truth = claims_lint.load_truth(slug)
    intros = _page_intros(slug)
    areas = pi.get("service_areas", [])
    primary_city, other_cities = _city_pool(areas)
    rotation = _city_rotation(len(targets), primary_city, other_cities)
    claims = _desc_allowed_claims(truth)
    sysmsg = (
        "You write per-service descriptions for a local company's Google "
        "Business Profile services list. Hard rules for EVERY description:\n"
        f"- Maximum {DESC_MAX_CHARS} characters; aim for 180 to 280. One to two "
        "sentences of plain, confident language.\n"
        "- Name the service naturally. Each service carries its own `cities` "
        "list (1 or 2 cities): weave EXACTLY those city names into the copy so "
        "it reads naturally, e.g. 'serving Tacoma and Federal Way homeowners'. "
        "Never mention cities that are not in that service's list, and never "
        "write a bare comma-run of city names (Google treats city stuffing as "
        "spam). Loose regional phrases (the state, 'the surrounding area') are "
        "fine as color.\n"
        "- No em dashes, no emoji, no ALL CAPS, no keyword stuffing, no "
        "superlative spam (best, #1, top-rated).\n"
        "- NEVER claim licenses, certifications (IICRC, EPA, ...), insurance "
        "status, 24/7 or emergency availability, response times, years in "
        "business, awards, or guarantees unless the claim appears in "
        "allowed_claims. When allowed_claims is empty, make no such claims at all.\n"
        "- Google policy: no URLs, no phone numbers, no prices or promotions.\n"
        "- When page_intro is given, ground the description in it; never invent "
        "capabilities beyond the service name.\n"
        'Return ONLY JSON: {"descriptions": {"<key>": "<description>", ...}} '
        "with one entry per service key.")
    user = json.dumps({
        "business": loc.get("title") or brand.get("display_name") or slug,
        "state": next((a.get("state") for a in areas if a.get("state")), ""),
        "allowed_claims": claims,
        "services": [{"key": str(i), "name": _item_name(it),
                      "cities": rotation[j],
                      "page_intro": _intro_for(_item_name(it), intros)}
                     for j, (i, it) in enumerate(targets)],
    }, indent=1)
    out = _anthropic_json(sysmsg, "Write the descriptions.\n\nDATA:\n" + user,
                          model=DESC_MODEL)
    raw = {str(k): v for k, v in (out.get("descriptions") or {}).items()}

    mode = ("refresh" if refresh_recent else "apply") if apply else "dry-run"
    pool = [c for c in [primary_city] + other_cities if c]
    accepted: dict[int, str] = {}
    for j, (i, it) in enumerate(targets):
        name = _item_name(it)
        desc = _fit_desc(raw.get(str(i), ""))
        if len(desc) < 40:
            print(f"     [skip] {name}: model returned no usable description")
            continue
        # City-stuffing guard: a description naming more than 2 metro cities
        # never ships, no matter what the model did with its assignment.
        mentioned = [c for c in pool
                     if re.search(rf"\b{re.escape(c)}\b", desc, re.I)]
        if len(mentioned) > 2:
            print(f"     [skip] {name}: {len(mentioned)} cities mentioned "
                  f"(max 2) — dropped")
            continue
        # Truth gate: an error-severity claims violation never ships. Try the
        # deterministic sanitizer once, then drop the description entirely.
        if any(v["severity"] == "error" for v in claims_lint.lint_text(desc, truth)):
            desc = _fit_desc(claims_lint.sanitize_claims_text(desc, truth))
        if len(desc) < 40 or any(v["severity"] == "error"
                                 for v in claims_lint.lint_text(desc, truth)):
            print(f"     [skip] {name}: unbacked claim survived sanitizing — dropped")
            continue
        accepted[i] = desc
        print(f"     [{mode}] {name} ({len(desc)} ch) "
              f"[{' + '.join(rotation[j]) or 'no city'}]: {desc}")
    if not accepted:
        return f"{slug}: 0/{len(targets)} descriptions generated ({len(items)} items)"
    if not apply:
        return (f"{slug}: DRY RUN — {len(accepted)}/{len(targets)} "
                f"descriptions ready ({len(items)} items total). Re-run with --apply.")

    # PATCH: same list, same order, only description fields added.
    new_list = json.loads(json.dumps(items))
    for i, desc in accepted.items():
        _set_item_desc(new_list[i], desc)
    r = requests.patch(f"{INFO_API}/{loc['name']}?updateMask=serviceItems",
                       headers={"Authorization": f"Bearer {token}",
                                "Content-Type": "application/json"},
                       data=json.dumps({"serviceItems": new_list}), timeout=60)
    if not r.ok:
        return f"{slug}: PATCH failed {r.status_code}: {r.text[:200]}"
    back = find_location(token, place) or {}
    back_items = back.get("serviceItems", [])
    still = sum(1 for it in back_items if not _item_desc(it))
    verb = "rewritten (city rotation)" if refresh_recent else "written"
    log_change(cid, "service_description",
               f"Descriptions {verb} for {len(accepted)} service(s) on the Google listing",
               actor="optimizer",
               meta={"services": [_item_name(items[i]) for i in accepted]})
    if refresh_recent:
        return (f"{slug}: descriptions refreshed for {len(accepted)}/{len(targets)} "
                f"recently-written service(s) ({still} of {len(back_items)} "
                f"items still missing any description)")
    return (f"{slug}: descriptions added to {len(accepted)}/{len(targets)} service(s) "
            f"— missing before {len(targets)}, after {still} "
            f"(listing has {len(back_items)} services)")


def cmd_descriptions(args) -> int:
    failures = 0
    for slug in _clients(args):
        try:
            print("  " + service_descriptions(slug, apply=args.apply,
                                              refresh_recent=args.refresh_recent))
        except Exception as e:  # one client must never abort a scheduled --all run
            failures += 1
            print(f"  {slug}: ERROR ({type(e).__name__}: {str(e)[:200]}) — skipped")
    if failures:
        print(f"  ({failures} client(s) errored and were skipped — see above)")
    return 0  # non-fatal: a client error shouldn't fail the scheduled run


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _clients(args) -> list[str]:
    if args.all:
        cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
        # ACCOUNT-STATUS GATE (Santino 2026-08-04: Mold Solutionz paused —
        # its GBP is connected, so every --all maintenance pass would have
        # kept optimizing/posting for a cancelled client). companies.status
        # is the pause button's source of truth (mixed-case in prod).
        # Fail-open: if the read errors, run the full roster.
        try:
            inactive = {"paused", "cancelled", "canceled", "churned",
                        "inactive", "archived"}
            ids = ",".join(f'"{c}"' for c in cmap.values())
            bad = {r["id"] for r in _sb(f"companies?id=in.({ids})&select=id,status")
                   if str(r.get("status") or "").strip().lower() in inactive}
            for slug in [s for s, c in cmap.items() if c in bad]:
                print(f"  [{slug}] skipped — account paused/cancelled")
                cmap.pop(slug)
        except Exception as e:  # noqa: BLE001 — gate must never kill a cron
            print(f"  [status-gate] check failed ({str(e)[:80]}) — full roster")
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


def _anthropic_json(system: str, user: str, model: str | None = None) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY in rank-ai/.env")
    last = ""
    # claude-sonnet-4-6 rejects assistant prefill outright, so JSON-only is
    # enforced by instruction + a corrective retry (2026-07-28: the
    # variant-expansion ruleset tipped the model into prose twice in a row).
    messages = [{"role": "user", "content": user + "\n\nReply with ONLY the JSON object. "
                 "The very first character of your reply must be '{'. No preamble, no analysis."}]
    for attempt in (1, 2, 3):
        r = requests.post(ANTHROPIC_API, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            data=json.dumps({"model": model or ANTHROPIC_MODEL, "max_tokens": 16384,
                             "system": system, "messages": messages}))
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
            messages = messages[:1] + [
                {"role": "assistant", "content": text[:2000]},
                {"role": "user", "content": "That was not valid JSON. Send the complete JSON "
                 "object now, nothing else. First character must be '{'."}]
    raise RuntimeError(f"Anthropic did not return valid JSON after 3 tries ({last})")


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
    """Compact geo-grid picture for the optimizer payload: per tracked
    (keyword, GRID CITY), the latest scan's avg rank / top-3 share plus the
    previous scan of the SAME city for trend. Grouping must include the city:
    clients are scanned around multiple centers on the same day (NaRestCo:
    Federal Way + Tacoma), and keyword-only grouping mis-read the two cities
    as a time series ('7.55 -> 14.63 declining' that never happened)."""
    scans = _sb(f"marketing_geogrid_scans?company_id=eq.{cid}"
                f"&order=scanned_at.desc&limit=40"
                f"&select=keyword,city_label,avg_rank,pct_in_top3,scanned_at")
    by_key: dict = {}
    for s in scans:
        by_key.setdefault((s["keyword"], s.get("city_label")), []).append(s)
    out = []
    for (kw, city), runs in by_key.items():
        cur = runs[0]
        # previous = the most recent scan of this keyword+city from an EARLIER day
        prev = next((r for r in runs[1:]
                     if (r.get("scanned_at") or "")[:10] != (cur.get("scanned_at") or "")[:10]),
                    None)
        out.append({
            "keyword": kw, "grid_city": city,
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
            log_change(cid, "description",
                       f"Business description written ({len(desc)} chars — was empty)",
                       actor="optimizer")
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


def _suggest_247_hours(cid: str, loc: dict) -> dict | None:
    """Open 24 hours every day, or a suggestion. Google's 24-hour-day shape is
    openTime 00:00 (serialized as {}) -> closeTime 24:00 on the same day."""
    periods = (loc.get("regularHours") or {}).get("periods") or []
    allday = {p.get("openDay") for p in periods
              if (p.get("openTime") or {}).get("hours", 0) % 24 == 0
              and (p.get("openTime") or {}).get("minutes", 0) == 0
              and (p.get("closeTime") or {}).get("hours", 0) == 24}
    if len(allday) == 7:
        return None
    state = ("No business hours on Google" if not periods
             else f"Only {len(allday)}/7 days are 24-hour" if allday
             else "Hours are office-style, not 24/7")
    return {"company_id": cid, "item": "hours-24-7", "item_type": "hours",
            "source": "gbp", "verdict": "ADD",
            "reason": f"{state} — emergency searches happen at 2 AM; "
                      "show Open 24 hours all week.",
            "confidence": 0.95, "canonical": None, "auto_safe": False, "status": "open"}


def optimize(slug: str) -> dict:
    """Audit the live GBP against confirmed services + the best-practices ruleset.
    Returns {summary, items[]} and upserts items to marketing_gbp_suggestions."""
    cid = company_id_for(slug)
    brand = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text()).get("brand", {})
    place = brand.get("place_id") or _place_id_from_connection(cid)
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
        "geo_grid_ranking shows live map-pack position per keyword PER GRID CITY "
        "(avg_rank, share of grid cells in the top 3; prev_* = the same city's earlier "
        "scan, null until a second scan date exists — never call something 'declining' "
        "unless prev_* is present and worse). Different grid_city rows are different "
        "markets, not a trend. When a weak keyword+city maps to a service/page item, "
        "prioritize it and cite the grid position and city in the reason.\n\n"
        f"DATA:\n{json.dumps(payload, indent=2)}")
    result = _anthropic_json(rules, instruction)
    items = result.get("items", [])

    # Structured (job_type_id) services the model classified KEEP — a free-form
    # REMOVE of the same normalized service contradicts them and must never
    # auto-execute (e.g. free-form "Mold Remediation" vs job_type_id:mold_remediation).
    structured_keeps = {
        _norm_service(it.get("item", "")) for it in items
        if it.get("verdict") == "KEEP" and str(it.get("item", "")).startswith("job_type_id")}

    # MERGE guardrail (2026-07-26, evidence: Sterling Sky retests show service
    # labels move rankings for their exact phrasings): a MERGE only survives
    # when item and canonical are token-identical after stripping filler —
    # otherwise the label is a distinct query surface and gets KEEP. The model
    # over-merges no matter how the prompt is worded ("Hail Damage Restoration"
    # -> "Hail Damage Repair" is a rankings-costing deletion, not a dedupe).
    _FILLER = {"service", "services", "professional", "comprehensive", "expert",
               "and", "the", "of", "a", "for"}

    def _qtokens(s):
        s = str(s or "")
        if s.startswith("job_type_id:"):
            s = s[len("job_type_id:"):]
        return {t.rstrip("s") for t in re.findall(r"[a-z]+", s.replace("_", " ").lower())
                if t not in _FILLER}

    for it in items:
        if it.get("verdict") == "MERGE" and it.get("item_type") == "service":
            if _qtokens(it.get("item")) != _qtokens(it.get("canonical")):
                it["verdict"] = "KEEP"
                it["canonical"] = None
                it["reason"] = "Distinct query phrasing — kept (services rank for their exact wording)."
                it["confidence"] = 0.9

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

    # Hours pass (Santino 2026-07-30): restoration is an emergency trade — a
    # listing that isn't Open 24 hours all week loses the 2 AM "water damage
    # near me" search. Deterministic; the app's suggestion row applies it with
    # one Set 24/7 click. Dismissal sticks via the settled-keys filter (a
    # client who truly keeps office hours gets dismissed once, never nagged).
    hrow = _suggest_247_hours(cid, loc)
    if hrow:
        rows.append(hrow)
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
        # The model can emit the same (item_type, item) twice in one run —
        # Postgres 500s the upsert ("cannot affect row a second time").
        seen_keys: set = set()
        rows = [r for r in rows
                if (k := (r["item_type"], str(r["item"]).strip())) not in seen_keys
                and not seen_keys.add(k)]
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
    for name in ("read", "reconcile", "sync", "reviews", "photos", "media-import", "set-phone"):
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
    pdsc = sub.add_parser("descriptions")
    gd = pdsc.add_mutually_exclusive_group(required=True)
    gd.add_argument("--slug")
    gd.add_argument("--all", action="store_true")
    pdsc.add_argument("--apply", action="store_true",
                      help="PATCH the listing (default: dry-run print of proposed descriptions)")
    pdsc.add_argument("--refresh-recent", type=float, metavar="HOURS", default=None,
                      help="Re-generate ONLY descriptions we ourselves wrote in the last "
                           "N hours (per marketing_gbp_changes) — never touches "
                           "client-authored or pre-existing text")
    args = ap.parse_args()
    return {"read": cmd_read, "reconcile": cmd_reconcile, "sync": cmd_sync,
            "reviews": cmd_reviews, "photos": cmd_photos, "media-import": cmd_media_import,
            "set-phone": cmd_set_phone,
            "add-services": cmd_add_services,
            "create-pages": cmd_create_pages, "optimize": cmd_optimize,
            "descriptions": cmd_descriptions}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
