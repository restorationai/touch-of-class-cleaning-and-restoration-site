#!/usr/bin/env python3
"""
Rank AI — Free-audit lead magnet pipeline (rank.restorationai.io).

Takes a prospect's website + contact info and produces a hosted HTML visibility
report: business profile (Claude), Google organic positions (DataForSEO), a mini
5x5 geo-grid heat map (reuses geogrid_scan/geogrid_render), AI-search citations
(ChatGPT via DataForSEO LLM responses + Google AI Overviews), a GBP/reviews
comparison vs the local map pack, and honest revenue-range math. The report is
uploaded to R2 (restorationai-media bucket, lead-audits/ prefix, r2.dev public
URL), emailed to the requester via SendGrid, and the lead is appended to
lead-audits/leads.jsonl in R2 (no Rank AI house company exists in the app's
companies table, so contacts-table insert is intentionally skipped).

CLAIMS HONESTY: every stat quoted in the report's "Why this matters" snippets
must come from docs/audit-stats-library.md (passed verbatim to the generator).
Sections whose data step failed are omitted, never faked.

Standalone:
  python3 scripts/lead_audit.py --url robinsonrestore.com --name "Test" \
      --email contact@restorationai.io --phone "+15550000000" --email-mode internal

Also imported by api/main.py (POST /lead-audit runs run_audit in a thread).

Env: ANTHROPIC_API_KEY, DATAFORSEO_USERNAME/PASSWORD (or ~/.claude.json),
     CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_R2_API_TOKEN (or CLOUDFLARE_API_TOKEN),
     SENDGRID_API_KEY. Typical cost: ~$0.50-0.90 DataForSEO + ~$0.30 Claude.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import datetime as dt
import difflib
import html as html_mod
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import geogrid_scan as gs                      # noqa: E402  build_grid, rank_at_point, load_dfs_creds
from geogrid_render import render_png          # noqa: E402
from geogrid_store import r2_put               # noqa: E402
from ai_search_scan import run_query as ai_chat_query, _domain  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BUCKET = "restorationai-media"          # public (report.html + heat-map PNGs only)
PRIVATE_BUCKET = "rankai-leads-private"  # NOT publicly served — lead PII (audit.json, leads.jsonl)
PUBLIC_BASE = "https://pub-8020f9b4a75d4346b4d17d9e4bec7392.r2.dev"
PREFIX = "lead-audits"
BOOK_URL = "https://link.restorationai.io/widget/booking/5GoVLLz9HDn8Ik3RjFMB"
MODEL = "claude-opus-4-8"
NOTIFY_EMAIL = "contact@restorationai.io"
FROM_EMAIL = os.environ.get("SENDGRID_FROM", NOTIFY_EMAIL)
TEMPLATE = ROOT / "templates" / "lead-audit" / "report-template.html"
STATS_LIB = ROOT / "docs" / "audit-stats-library.md"

DFS_ORGANIC = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
DFS_MAPS = "https://api.dataforseo.com/v3/serp/google/maps/live/advanced"
DFS_VOLUME = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
DFS_LISTINGS = "https://api.dataforseo.com/v3/business_data/business_listings/search/live"

# avg ticket by vertical — used ONLY inside a clearly-labeled estimate range
AVG_TICKET = {"water": 4500, "fire": 15000, "mold": 3500, "storm": 6000,
              "biohazard": 4000, "reconstruction": 12000}
DEFAULT_TICKET = 4500

# organic CTR curve (share of clicks by position; Backlinko/AWR-style curve)
CTR = {1: 0.28, 2: 0.15, 3: 0.11, 4: 0.08, 5: 0.07,
       6: 0.05, 7: 0.04, 8: 0.03, 9: 0.03, 10: 0.02}
TOP3_BLEND = 0.18   # conservative blended CTR if you rank in the top 3


def ctr_for(pos):
    if pos is None:
        return 0.0
    if pos in CTR:
        return CTR[pos]
    if pos <= 20:
        return 0.01
    return 0.0


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _esc(s):
    return html_mod.escape(str(s or ""), quote=True)


def _norm_domain(url):
    url = (url or "").strip().lower()
    url = re.sub(r"^https?://", "", url)
    url = url.split("/")[0].split("?")[0]
    return url.replace("www.", "").strip()


def _http_get(url, timeout=25, headers=None):
    req = urllib.request.Request(url, headers=headers or {
        "User-Agent": "Mozilla/5.0 (Macintosh) RankAI-Audit/1.0 (+contact@restorationai.io)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _html_to_text(raw):
    txt = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    txt = html_mod.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def _dfs_auth():
    u, p = gs.load_dfs_creds()
    return base64.b64encode("{}:{}".format(u, p).encode()).decode()


def _dfs(url, body, auth, timeout=120):
    """POST one DataForSEO task; return (result_items, cost, raw_task)."""
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Basic " + auth, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    task = (d.get("tasks") or [{}])[0]
    cost = float(task.get("cost") or 0.0)
    result = (task.get("result") or [{}])[0] or {}
    return (result.get("items") or []), cost, task


# ---------------------------------------------------------------------------
# Claude (JSON generation)
# ---------------------------------------------------------------------------

def _claude():
    import anthropic
    return anthropic.Anthropic()


def _loose_json(text):
    """Parse a JSON object out of model text, tolerating fences, //-comments
    and trailing commas (models copy the comment style from schema examples)."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError("no JSON object in Claude response: " + text[:200])
    s = m.group(0)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # strip // comments that are OUTSIDE string literals, then trailing commas
    out, in_str, esc, i = [], False, False, 0
    while i < len(s):
        ch = s[i]
        if in_str:
            out.append(ch)
            esc = (ch == "\\" and not esc)
            if ch == '"' and not esc:
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str, esc = True, False
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < len(s) and s[i + 1] == "/":
            while i < len(s) and s[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    cleaned = re.sub(r",\s*([}\]])", r"\1", "".join(out))
    return json.loads(cleaned)


def claude_json(client, system, user, max_tokens=8000, schema=None):
    """One Claude call that must return a JSON object.

    Prefers structured outputs (output_config.format json_schema) when a schema
    is given; falls back to plain generation + lenient parsing if the installed
    SDK/model rejects the parameter."""
    kwargs = dict(model=MODEL, max_tokens=max_tokens, system=system,
                  messages=[{"role": "user", "content": user}])
    resp = None
    if schema is not None:
        try:
            resp = client.messages.create(
                output_config={"format": {"type": "json_schema", "schema": schema}}, **kwargs)
        except Exception as e:
            sys.stderr.write("  structured output unavailable ({}) — falling back\n".format(str(e)[:120]))
            resp = None
    if resp is None:
        resp = client.messages.create(**kwargs)
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude refused the request")
    text = "".join(b.text for b in resp.content if b.type == "text")
    usage = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}
    return _loose_json(text), usage


def _claude_cost(usages):
    # claude-opus-4-8: $5/M input, $25/M output
    tin = sum(u["in"] for u in usages)
    tout = sum(u["out"] for u in usages)
    return round(tin / 1e6 * 5.0 + tout / 1e6 * 25.0, 4)


# ---------------------------------------------------------------------------
# Step 1 — fetch + profile the site
# ---------------------------------------------------------------------------

def fetch_site(domain, start_url=None):
    """Homepage + up to 4 about/service pages, as plain text.

    start_url: when the lead submitted a PAGE on a shared domain (franchise
    sites like puroclean.com/eastlasvegas), profile from THAT page — the
    domain root is the corporate brand, not their business — and prefer
    links inside the same subtree."""
    pages = {}
    base = "https://" + domain
    if start_url:
        raw = _http_get(start_url).decode("utf-8", "ignore")
    else:
        try:
            raw = _http_get(base).decode("utf-8", "ignore")
        except Exception:
            raw = _http_get("http://" + domain).decode("utf-8", "ignore")  # may raise
    pages["homepage"] = _html_to_text(raw)[:15000]

    sub_prefix = urllib.parse.urlparse(start_url).path.rstrip("/").lower() if start_url else ""
    hrefs = re.findall(r'href=["\']([^"\'#]+)', raw)
    sub_picked, kw_picked, seen = [], [], set()
    for h in hrefs:
        full = urllib.parse.urljoin((start_url or base) + "/", h)
        host = _norm_domain(full)
        if host != domain:
            continue
        path = urllib.parse.urlparse(full).path.lower()
        if re.search(r"\.(png|jpe?g|gif|svg|webp|ico|pdf|css|js|xml|woff2?)$", path) or "/wp-content/" in path:
            continue
        key = path.rstrip("/")
        if not key or key in seen or key == sub_prefix:
            continue
        if sub_prefix and key.startswith(sub_prefix + "/"):
            seen.add(key)
            sub_picked.append(full)
        elif re.search(r"about|service|water|fire|mold|storm|restoration|area|location|contact", path):
            seen.add(key)
            kw_picked.append(full)
        if len(sub_picked) >= 4:
            break
    for u in (sub_picked + kw_picked)[:4]:
        try:
            pages[u] = _html_to_text(_http_get(u).decode("utf-8", "ignore"))[:8000]
        except Exception:
            continue
    return pages


PROFILE_SYSTEM = """You extract a structured business profile from website text for a local-SEO audit.
Return ONLY a JSON object (no prose, no markdown fences) with exactly these keys:
{
 "business_name": str,           // the customer-facing brand name
 "phone": str|null,
 "vertical": str,                // one of: water, fire, mold, storm, biohazard, reconstruction
 "services": [str],              // 2-5 plain-English service labels, most important first,
                                 // e.g. "water damage restoration"
 "cities": [{"city": str, "state": str}],  // up to 4 cities actually served, most important
                                 // first. "state" = FULL state name (e.g. "Washington").
 "gbp_query": str                // the exact name a customer would search on Google Maps
}
Rules: only use facts present in the text. If the site names one HQ city plus nearby areas,
put the HQ city first. Never invent cities or services."""


PROFILE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "business_name": {"type": "string"},
        "phone": {"type": ["string", "null"]},
        "vertical": {"type": "string",
                     "enum": ["water", "fire", "mold", "storm", "biohazard", "reconstruction"]},
        "services": {"type": "array", "items": {"type": "string"}},
        "cities": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"city": {"type": "string"}, "state": {"type": "string"}},
            "required": ["city", "state"]}},
        "gbp_query": {"type": "string"},
    },
    "required": ["business_name", "phone", "vertical", "services", "cities", "gbp_query"],
}


def profile_site(client, domain, pages):
    corpus = "\n\n".join("### {}\n{}".format(k, v) for k, v in pages.items())[:60000]
    user = "Website: {}\n\n{}".format(domain, corpus)
    prof, usage = claude_json(client, PROFILE_SYSTEM, user, max_tokens=2000,
                              schema=PROFILE_SCHEMA)
    prof["services"] = [s.strip().lower() for s in prof.get("services") or [] if s.strip()][:5]
    prof["cities"] = (prof.get("cities") or [])[:4]
    if not prof.get("services") or not prof.get("cities"):
        raise RuntimeError("profile incomplete: services/cities missing")
    return prof, usage


# ---------------------------------------------------------------------------
# Step 1b — geocode + GBP confirm
# ---------------------------------------------------------------------------

def geocode(city, state):
    q = urllib.parse.quote("{}, {}, USA".format(city, state))
    url = "https://nominatim.openstreetmap.org/search?format=json&limit=1&q=" + q
    try:
        d = json.loads(_http_get(url, timeout=20))
        if d:
            return float(d[0]["lat"]), float(d[0]["lon"])
    except Exception:
        pass
    return None


def _name_match(a, b):
    a, b = (a or "").lower().strip(), (b or "").lower().strip()
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def gbp_confirm(auth, gbp_query, business_name, lat, lng, domain=None):
    """Find the business's Maps listing near its primary city.

    A candidate whose listing links to the audited domain IS the business —
    that beats any name-similarity score. Name-only matches that link to a
    DIFFERENT domain are near-certainly someone else (2026-07-26: "Coastal
    Restoration Services" fuzzy-matched tree service "Coastal Treetenders"
    and the report told the lead to fix a stranger's profile name)."""
    def _strip(d):
        return d[4:] if d.startswith("www.") else d
    def _dom(it):
        return _strip(str(it.get("domain") or "").lower())
    want = _strip(str(domain or "").lower())
    # 14z first (the business is usually IN its primary city), then 11z — the
    # HQ pin can sit outside a tight viewport (callcrs.com 2026-07-26: listing
    # invisible at 14z Santa Maria, found at wider zoom).
    best, score, cost = None, 0.0, 0.0
    for zoom in ("14z", "11z"):
        body = [{"keyword": gbp_query[:200],
                 "location_coordinate": "{},{},{}".format(lat, lng, zoom),
                 "language_code": "en", "device": "desktop"}]
        items, c, _ = _dfs(DFS_MAPS, body, auth)
        cost += c
        for it in items:
            if not isinstance(it, dict):
                continue
            if want and _dom(it) == want:
                best, score = it, 1.0
                break
            s = max(_name_match(business_name, it.get("title")),
                    _name_match(gbp_query, it.get("title")))
            if want and _dom(it) and _dom(it) != want:
                s -= 0.35
            if s > score:
                best, score = it, s
        if best and score >= 0.55:
            break
    if best and score >= 0.55:
        rd = best.get("rating") or {}
        return {
            "found": True, "title": best.get("title"),
            "place_id": best.get("place_id"),
            "cid": str(best.get("cid")) if best.get("cid") is not None else None,
            "rating": rd.get("value"), "reviews": rd.get("votes_count"),
            "address": best.get("address"),
        }, cost
    # Fallback: the Maps SERP sometimes skips the exact listing (missed
    # "PuroClean of East Las Vegas" 2026-07-19 → report wrongly said no GBP).
    # Search the business-listings DB by brand word near the same coords;
    # stricter match bar since this net is wider.
    try:
        brand = (business_name or gbp_query).split()[0]
        items2, c2, _ = _dfs(DFS_LISTINGS, [{"title": brand[:50],
                             "location_coordinate": "{},{},15".format(lat, lng),
                             "limit": 20}], auth)
        cost += c2
        best2, score2 = None, 0.0
        for it in items2:
            if not isinstance(it, dict):
                continue
            if want and _dom(it) == want:
                best2, score2 = it, 1.0
                break
            s = max(_name_match(business_name, it.get("title")),
                    _name_match(gbp_query, it.get("title")))
            if want and _dom(it) and _dom(it) != want:
                s -= 0.35
            if s > score2:
                best2, score2 = it, s
        if best2 and score2 >= 0.75:
            rd = best2.get("rating") or {}
            return {
                "found": True, "title": best2.get("title"),
                "place_id": best2.get("place_id"),
                "cid": str(best2.get("cid")) if best2.get("cid") is not None else None,
                "rating": rd.get("value"), "reviews": rd.get("votes_count"),
                "address": best2.get("address"),
            }, cost
    except Exception as e:
        sys.stderr.write("  gbp listings fallback: {}\n".format(str(e)[:120]))
    return {"found": False}, cost


def gbp_by_id(auth, place_id=None, cid=None):
    """Fetch the chosen GBP listing directly by place_id/cid (stepper flow:
    the prospect already confirmed their listing, so skip name re-guessing)."""
    flt = None
    if place_id:
        flt = ["place_id", "=", place_id]
    elif cid:
        try:
            flt = ["cid", "=", int(cid)]
        except (TypeError, ValueError):
            flt = ["cid", "=", str(cid)]
    if not flt:
        return {"found": False}, 0.0
    items, cost, _ = _dfs(DFS_LISTINGS, [{"filters": [flt], "limit": 1}], auth)
    for it in items:
        if not isinstance(it, dict) or not it.get("title"):
            continue
        rd = it.get("rating") or {}
        return {
            "found": True, "title": it.get("title"),
            "place_id": it.get("place_id") or place_id,
            "cid": str(it.get("cid")) if it.get("cid") is not None else (str(cid) if cid else None),
            "rating": rd.get("value"), "reviews": rd.get("votes_count"),
            "address": it.get("address"),
        }, cost
    return {"found": False}, cost


# ---------------------------------------------------------------------------
# Step 2 — organic rankings
# ---------------------------------------------------------------------------

def organic_position(auth, keyword, domain, location_name):
    body = [{"keyword": keyword, "language_code": "en", "location_name": location_name,
             "depth": 20, "device": "desktop"}]
    try:
        items, cost, task = _dfs(DFS_ORGANIC, body, auth)
        if task.get("status_code") and int(task["status_code"]) >= 40000:
            raise RuntimeError(task.get("status_message") or "task error")
    except Exception:
        # location_name not in DFS DB -> retry at country level
        body[0]["location_name"] = "United States"
        items, cost, _ = _dfs(DFS_ORGANIC, body, auth)
    pos, top = None, []
    for it in items:
        if not isinstance(it, dict) or it.get("type") != "organic":
            continue
        d = _domain(it.get("url") or it.get("domain") or "")
        rank = it.get("rank_group")
        if len(top) < 3:
            top.append(d)
        if pos is None and d == domain:
            pos = rank
    return pos, top, cost


def run_rankings(auth, domain, service, cities):
    rows, cost = [], 0.0
    for c in cities[:3]:
        loc = "{},{},United States".format(c["city"], c["state"])
        for kw in ["{} {}".format(service, c["city"].lower()),
                   "{} company {}".format(service, c["city"].lower()),
                   "emergency {} {}".format(service, c["city"].lower())]:
            try:
                pos, top, q_cost = organic_position(auth, kw, domain, loc)
                cost += q_cost
                rows.append({"keyword": kw, "city": c["city"], "position": pos, "top3": top})
            except Exception as e:
                sys.stderr.write("  organic '{}' failed: {}\n".format(kw, str(e)[:120]))
    return rows, cost


# ---------------------------------------------------------------------------
# Step 3 — mini geo-grid (5x5) reusing geogrid machinery
# ---------------------------------------------------------------------------

def run_geogrid(auth, audit_id, business, service, cities_geo, grid=5, miles=6.0, zoom=12):
    """cities_geo: [{'city','state','lat','lng'}] (max 2). Returns (maps, cost)."""
    out, total_cost = [], 0.0
    biz = {"name": business["name"], "cid": business.get("cid"),
           "place_id": business.get("place_id")}
    for c in cities_geo[:2]:
        pts = gs.build_grid(c["lat"], c["lng"], grid, miles)
        results = [None] * len(pts)
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(gs.rank_at_point, auth, service, p, biz, zoom, 20): i
                    for i, p in enumerate(pts)}
            for fut in cf.as_completed(futs):
                results[futs[fut]] = fut.result()
        cost = sum(r["cost"] for r in results)
        total_cost += cost
        errored = sum(1 for r in results if (not r["found"]) and (r.get("cost") or 0) == 0.0)
        if errored > 0.4 * len(pts):
            sys.stderr.write("  geo-grid {} unreliable ({} errored) — skipping\n".format(c["city"], errored))
            continue
        found = [r for r in results if r["found"]]
        avg = round(sum(r["rank"] for r in found) / len(found), 1) if found else None
        top3 = round(100.0 * sum(1 for r in found if r["rank"] <= 3) / len(pts))
        img_url = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            render_png(results, tmp_path, size=(700, 700))
            key = "{}/{}/geogrid-{}.png".format(
                PREFIX, audit_id, re.sub(r"[^a-z0-9]+", "-", c["city"].lower()).strip("-"))
            if r2_put(BUCKET, key, tmp_path.read_bytes(), "image/png"):
                img_url = "{}/{}".format(PUBLIC_BASE, key)
            tmp_path.unlink()
        except Exception as e:
            sys.stderr.write("  geo-grid render/upload {}: {}\n".format(c["city"], str(e)[:120]))
        out.append({"city": c["city"], "avg_rank": avg, "pct_top3": top3,
                    "found": len(found), "points": len(pts), "image_url": img_url})
    return out, total_cost


# ---------------------------------------------------------------------------
# Step 4 — AI search (ChatGPT + Google AI Overviews)
# ---------------------------------------------------------------------------

def run_ai_search(auth, domain, name, service, cities):
    c1 = cities[0]
    queries = ["best {} company in {}, {}".format(service, c1["city"], c1["state"])]
    if len(cities) > 1:
        queries.append("best {} company in {}, {}".format(service, cities[1]["city"], cities[1]["state"]))
    if "water" in service or "flood" in service:
        queries.append("my house just flooded in {}, {} — who should I call?".format(c1["city"], c1["state"]))
    else:
        queries.append("emergency {} near me in {}, {}".format(service, c1["city"], c1["state"]))
    queries = queries[:3]

    results, cost = [], 0.0
    nm = (name or "").lower()
    for q in queries:
        # ChatGPT (web search)
        try:
            r = ai_chat_query(auth, "chatgpt", q)
            cost += float(r["cost"] or 0)
            cited = (domain in r["domains"]) or (nm and nm in r["answer"].lower())
            results.append({"engine": "chatgpt", "query": q, "cited": bool(cited),
                            "answer_excerpt": r["answer"][:900],
                            "sources": r["domains"][:8]})
        except Exception as e:
            sys.stderr.write("  chatgpt '{}': {}\n".format(q[:40], str(e)[:120]))
        # Google AI Overview
        try:
            body = [{"keyword": q[:120], "language_code": "en", "location_name": "United States",
                     "depth": 10, "load_async_ai_overview": True}]
            items, c, _ = _dfs(DFS_ORGANIC, body, auth)
            cost += c
            aio = next((it for it in items if isinstance(it, dict) and it.get("type") == "ai_overview"), None)
            if aio:
                refs = [_domain(r0.get("url") or r0.get("domain") or "") for r0 in (aio.get("references") or [])]
                refs = [r0 for r0 in refs if r0]
                results.append({"engine": "google_ai", "query": q,
                                "cited": domain in refs,
                                "answer_excerpt": (aio.get("markdown") or "")[:600],
                                "sources": refs[:8]})
            else:
                results.append({"engine": "google_ai", "query": q, "cited": None,
                                "answer_excerpt": "", "sources": [],
                                "note": "no AI Overview shown for this query"})
        except Exception as e:
            sys.stderr.write("  google_ai '{}': {}\n".format(q[:40], str(e)[:120]))
    return results, cost


# ---------------------------------------------------------------------------
# Step 5 — map-pack / reviews comparison
# ---------------------------------------------------------------------------

def run_mappack(auth, business_name, service, cities_geo):
    packs, cost = [], 0.0
    for c in cities_geo[:2]:
        try:
            body = [{"keyword": "{} {}".format(service, c["city"].lower()),
                     "location_coordinate": "{},{},12z".format(c["lat"], c["lng"]),
                     "language_code": "en", "device": "desktop"}]
            items, q_cost, _ = _dfs(DFS_MAPS, body, auth)
            cost += q_cost
            top, client_rank = [], None
            for it in items:
                if not isinstance(it, dict):
                    continue
                rank = it.get("rank_group")
                rd = it.get("rating") or {}
                row = {"title": it.get("title"), "rating": rd.get("value"),
                       "reviews": rd.get("votes_count"), "rank": rank}
                if _name_match(business_name, it.get("title")) >= 0.75:
                    client_rank = rank
                elif len(top) < 3:
                    top.append(row)
            packs.append({"city": c["city"], "competitors": top, "client_rank": client_rank})
        except Exception as e:
            sys.stderr.write("  mappack {}: {}\n".format(c["city"], str(e)[:120]))
    return packs, cost


# ---------------------------------------------------------------------------
# Step 6 — search volume + revenue math
# ---------------------------------------------------------------------------

def run_volumes(auth, keywords):
    body = [{"keywords": keywords[:20], "location_code": 2840, "language_code": "en"}]
    req = urllib.request.Request(DFS_VOLUME, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Basic " + _dfs_auth(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    task = (d.get("tasks") or [{}])[0]
    cost = float(task.get("cost") or 0.0)
    vols = {}
    for row in (task.get("result") or []):
        if isinstance(row, dict) and row.get("keyword"):
            vols[row["keyword"].lower()] = row.get("search_volume") or 0
    return vols, cost


def revenue_math(rankings, vols, vertical):
    ticket = AVG_TICKET.get(vertical, DEFAULT_TICKET)
    missed_clicks = 0.0
    tracked = 0
    for r in rankings:
        vol = vols.get(r["keyword"].lower(), 0) or 0
        if vol <= 0:
            continue
        tracked += 1
        gap = max(0.0, TOP3_BLEND - ctr_for(r["position"]))
        missed_clicks += vol * gap
    mid = missed_clicks * 0.10 * ticket
    if tracked == 0 or mid < 200:
        return None
    low = int(round(mid * 0.6, -2))
    high = int(round(mid * 1.4, -2))
    return {"low": low, "high": high, "ticket": ticket,
            "missed_clicks": int(round(missed_clicks)),
            "methodology": ("Estimate = monthly Google search volume for the {} tracked keywords x the standard "
                            "click-through-rate curve for Google positions (a top-3 listing captures roughly 18% "
                            "of searches; page 2 captures almost none) x a 10% booked-job rate x an average {} "
                            "job ticket of ${:,}. Shown as a range because real close rates and tickets vary."
                            ).format(tracked, vertical, ticket)}


# ---------------------------------------------------------------------------
# Step 7 — report generation (Claude writes copy into the locked template)
# ---------------------------------------------------------------------------

REPORT_SYSTEM = """You write the plain-English copy for a local-SEO visibility audit report sent to the
owner of a restoration company. You are given (a) the audit data collected from live APIs and
(b) a vetted statistics library. Voice: direct, specific, respectful — a sharp consultant, not
a hype marketer. 6th-10th grade reading level. Short sentences.

HARD RULES — these are non-negotiable:
1. NEVER invent data. Only reference numbers present in the audit data JSON.
2. Every "why" field in game_plan MUST quote ONE statistic taken verbatim (or near-verbatim,
   keeping the number and hedging intact) from the statistics library, and MUST name the source
   and date exactly as the library gives them, e.g. "... (OpenAI, Oct 2025)". No other numbers.
3. If a data section is empty/missing, do not mention it.
4. Never promise results; describe gaps and what fixing them typically does.
5. When naming competitors, only use names that literally appear in the audit data
   (map-pack competitor titles or AI answer excerpts).
6. NEVER use an em dash (—) or a spaced en dash anywhere. Use a comma, a colon, or
   two sentences instead.

Return ONLY a JSON object (no fences) with exactly these keys:
{
 "grade": "A"|"B"|"C"|"D"|"F",       // A=dominant everywhere; B=strong, small gaps; C=visible but
                                      // losing key queries; D=mostly invisible; F=absent everywhere
 "verdict": str,                      // ONE sentence, <=20 words, spoken to the owner
 "summary": str,                      // 2-3 sentences expanding the verdict, referencing 2-3 specific findings
 "rankings_intro": str,               // 1-2 sentences introducing the rankings table
 "city_cards": [{"city": str, "headline": str, "body": str}],  // one per city with ranking data;
                                      // headline <=8 words; body 2 sentences citing their actual positions
 "heatmap_caption": str,              // 1-2 sentences reading the heat map(s) for them (only if geogrid data)
 "ai_headline": str,                  // <=10 words; lead with ChatGPT when the data includes a
                                      // ChatGPT answer, e.g. "ChatGPT is recommending someone else"
 "ai_body": str,                      // 2-3 sentences: what we asked, whether they appeared, and WHO the
                                      // AI recommended instead (competitor names from the answer excerpts)
 "reviews_body": str,                 // 2-3 sentences comparing their rating/review count vs the top-3
                                      // map-pack competitors, with the actual numbers (only if data)
 "money_body": str,                   // 1-2 sentences framing the revenue range as an honest estimate
 "game_plan": [{"title": str, "body": str, "why": str}],  // EXACTLY 5 steps, ordered by impact,
                                      // specific to THIS business's gaps. body = 1-2 sentences of what
                                      // we'd do. why = stat per rule 2.
 "cost_of_inaction": str              // ONE sentence: what staying invisible costs, using only the
                                      // computed revenue range if present (else no dollar figures)
}"""


_STEP = {"type": "object", "additionalProperties": False,
         "properties": {"title": {"type": "string"}, "body": {"type": "string"},
                        "why": {"type": "string"}},
         "required": ["title", "body", "why"]}
REPORT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "grade": {"type": "string", "enum": ["A", "B", "C", "D", "F"]},
        "verdict": {"type": "string"},
        "summary": {"type": "string"},
        "rankings_intro": {"type": "string"},
        "city_cards": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"city": {"type": "string"}, "headline": {"type": "string"},
                           "body": {"type": "string"}},
            "required": ["city", "headline", "body"]}},
        "heatmap_caption": {"type": "string"},
        "ai_headline": {"type": "string"},
        "ai_body": {"type": "string"},
        "reviews_body": {"type": "string"},
        "money_body": {"type": "string"},
        "game_plan": {"type": "array", "items": _STEP},
        "cost_of_inaction": {"type": "string"},
    },
    "required": ["grade", "verdict", "summary", "rankings_intro", "city_cards",
                 "heatmap_caption", "ai_headline", "ai_body", "reviews_body",
                 "money_body", "game_plan", "cost_of_inaction"],
}


def generate_report_copy(client, data):
    stats = STATS_LIB.read_text() if STATS_LIB.exists() else ""
    user = ("AUDIT DATA JSON:\n{}\n\nSTATISTICS LIBRARY (the ONLY permitted stat source):\n{}"
            ).format(json.dumps(data, indent=1)[:45000], stats[:20000])
    return claude_json(client, REPORT_SYSTEM, user, max_tokens=8000, schema=REPORT_SCHEMA)


# ---------------------------------------------------------------------------
# HTML assembly (locked template — Claude strings are escaped on insert)
# ---------------------------------------------------------------------------

def _pos_cell(pos):
    if pos is None:
        return '<span class="pos p-bad">Not in top 20</span>'
    cls = "p-good" if pos <= 3 else ("p-warn" if pos <= 10 else "p-bad")
    return '<span class="pos {}">#{}</span>'.format(cls, pos)


def build_html(audit_id, prof, domain, copy, rankings, geogrid, ai_results, mappack, money):
    tpl = TEMPLATE.read_text()
    S = []

    # Rankings section
    if rankings:
        rows = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                _esc(r["keyword"]), _esc(r["city"]), _pos_cell(r["position"]))
            for r in rankings)
        cards = "".join(
            '<div class="citycard"><h3>{}</h3><div class="head">{}</div><p>{}</p></div>'.format(
                _esc(c.get("city")), _esc(c.get("headline")), _esc(c.get("body")))
            for c in (copy.get("city_cards") or []))
        S.append("""<section><div class="kicker">Google Search</div>
<h2>Where you rank for the searches that bring jobs</h2>
<p>{}</p>
<div class="tblwrap"><table><thead><tr><th>Search</th><th>Area</th><th>Your position</th></tr></thead>
<tbody>{}</tbody></table></div>
<p class="note">Live Google results checked from {} at report time. Positions move daily.</p>
{}</section>""".format(_esc(copy.get("rankings_intro")), rows,
                       _esc(", ".join(sorted(set(r["city"] for r in rankings)))), cards))

    # Geo-grid section
    grids = [g for g in (geogrid or []) if g.get("image_url")]
    if grids:
        figs = "".join(
            """<div class="map"><figure><img src="{}" alt="Map ranking heat map — {}">
<figcaption><b>{}</b> — avg map rank {} &middot; top-3 in {}% of the area</figcaption></figure></div>""".format(
                _esc(g["image_url"]), _esc(g["city"]), _esc(g["city"]),
                _esc(g["avg_rank"] if g["avg_rank"] is not None else "20+"), _esc(g["pct_top3"]))
            for g in grids)
        S.append("""<section><div class="kicker">Google Maps</div>
<h2>Your map visibility, block by block</h2>
<p>Each pin is a real Google Maps search run from that spot. Green means you're in the top 3
(the "map pack" customers actually call). Red means you don't show up there at all.</p>
<div class="maps">{}</div>
<div class="legend"><span><b style="background:#16a34a"></b>Top 3</span>
<span><b style="background:#eab308"></b>4&ndash;10</span>
<span><b style="background:#f97316"></b>11&ndash;20</span>
<span><b style="background:#dc2626"></b>Not found</span></div>
<p style="margin-top:12px">{}</p></section>""".format(figs, _esc(copy.get("heatmap_caption"))))

    # AI search section
    chat = [r for r in (ai_results or []) if r["engine"] == "chatgpt"]
    if chat:
        first = next((r for r in chat if not r["cited"]), chat[0])
        quote = (first.get("answer_excerpt") or "")[:340]
        S.append("""<section><div class="kicker">AI Search</div>
<h2>{}</h2>
<p>{}</p>
<div class="aiquote"><div class="q">&ldquo;{}&hellip;&rdquo;</div>
<div class="src">ChatGPT (with web search), asked: &ldquo;{}&rdquo;</div></div>
<p class="note">We asked ChatGPT and checked Google's AI Overviews for {} live buyer questions.
Cited in {} of {} AI answers.</p></section>""".format(
            _esc(copy.get("ai_headline")), _esc(copy.get("ai_body")),
            _esc(quote), _esc(first["query"]),
            len(set(r["query"] for r in (ai_results or []))),
            sum(1 for r in (ai_results or []) if r.get("cited")),
            sum(1 for r in (ai_results or []) if r.get("cited") is not None)))

    # Reviews section
    packs = [p for p in (mappack or []) if p.get("competitors")]
    if packs and prof.get("gbp", {}).get("found") and copy.get("reviews_body"):
        p0 = packs[0]
        gbp = prof["gbp"]
        rows = "<tr class=\"you\"><td><b>{}</b> (you)</td><td>{}</td><td>{}</td></tr>".format(
            _esc(prof["business_name"]),
            _esc(gbp.get("rating") if gbp.get("rating") is not None else "—"),
            _esc(gbp.get("reviews") if gbp.get("reviews") is not None else "—"))
        for cmp_ in p0["competitors"]:
            rows += "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                _esc(cmp_.get("title")), _esc(cmp_.get("rating") if cmp_.get("rating") is not None else "—"),
                _esc(cmp_.get("reviews") if cmp_.get("reviews") is not None else "—"))
        S.append("""<section><div class="kicker">Reputation</div>
<h2>Your reviews vs. the businesses winning the map pack</h2>
<p>{}</p>
<div class="tblwrap"><table><thead><tr><th>Business ({} map pack)</th><th>Rating</th><th>Reviews</th></tr></thead>
<tbody>{}</tbody></table></div></section>""".format(
            _esc(copy.get("reviews_body")), _esc(p0["city"]), rows))

    # Money section
    if money:
        S.append("""<section><div class="kicker">What it's worth</div>
<h2>Estimated revenue left on the table</h2>
<p>{}</p>
<div class="money"><div class="amt">${:,} &ndash; ${:,}</div><div class="per">per month, estimated range</div></div>
<p class="note">{}</p></section>""".format(
            _esc(copy.get("money_body")), money["low"], money["high"], _esc(money["methodology"])))

    # Game plan
    steps = (copy.get("game_plan") or [])[:5]
    if steps:
        blocks = "".join(
            """<div class="step"><div class="n">{}</div><div><h3>{}</h3><p>{}</p>
<div class="why"><b>Why this matters:</b> {}</div></div></div>""".format(
                i + 1, _esc(s.get("title")), _esc(s.get("body")), _esc(s.get("why")))
            for i, s in enumerate(steps))
        coi = _esc(copy.get("cost_of_inaction"))
        S.append("""<section><div class="kicker">The plan</div>
<h2>The 5-step game plan to fix this</h2>{}
<p style="margin-top:18px;font-weight:600;color:var(--ink)">{}</p></section>""".format(blocks, coi))

    grade = (copy.get("grade") or "C").upper()[:1]
    gclass = "g-good" if grade in ("A", "B") else ("g-warn" if grade == "C" else "g-bad")
    today = dt.datetime.now(dt.timezone.utc).strftime("%B %d, %Y")
    out = (tpl.replace("{{TITLE}}", _esc("{} — AI Visibility Audit".format(prof["business_name"])))
              .replace("{{BUSINESS_NAME}}", _esc(prof["business_name"]))
              .replace("{{DOMAIN}}", _esc(domain))
              .replace("{{GRADE_CLASS}}", gclass)
              .replace("{{GRADE}}", _esc(grade))
              .replace("{{VERDICT}}", _esc(copy.get("verdict")))
              .replace("{{DATE}}", today)
              .replace("{{SECTIONS}}",
                       '<section><div class="kicker">Summary</div><h2>What we found</h2><p>{}</p></section>\n'.format(
                           _esc(copy.get("summary"))) + "\n".join(S))
              .replace("{{CTA_URL}}", BOOK_URL)
              .replace("{{METHODOLOGY}}", _esc(money["methodology"]) if money else
                       "Rankings, map data and AI answers pulled live at report time.")
              .replace("{{YEAR}}", str(dt.datetime.now().year)))
    return out


# ---------------------------------------------------------------------------
# Step 8 — delivery: R2 hosting, email, lead log
# ---------------------------------------------------------------------------

def r2_get(bucket, key):
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    token = os.environ.get("CLOUDFLARE_R2_API_TOKEN") or os.environ.get("CLOUDFLARE_API_TOKEN")
    url = "https://api.cloudflare.com/client/v4/accounts/{}/r2/buckets/{}/objects/{}".format(
        account, bucket, urllib.parse.quote(key, safe=""))
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except Exception:
        return None


def append_lead_jsonl(lead):
    """Durable lead log in R2 (no Rank AI house company exists in the app DB)."""
    key = PREFIX + "/leads.jsonl"
    existing = r2_get(PRIVATE_BUCKET, key) or b""
    line = (json.dumps(lead) + "\n").encode()
    r2_put(PRIVATE_BUCKET, key, existing + line, "application/x-ndjson")


def send_sms(to_phone, body):
    """Text the report link via the agency estimate-SMS sender (same creds the
    client sites' /api/estimate path uses). Skips quietly when the three
    ESTIMATE_SMS_* env vars aren't set (e.g. toll-free still pending review)."""
    from_num = (os.environ.get("ESTIMATE_SMS_FROM") or "").strip()
    sid = (os.environ.get("ESTIMATE_SMS_SID") or "").strip()
    token = (os.environ.get("ESTIMATE_SMS_TOKEN") or "").strip()
    digits = re.sub(r"\D", "", to_phone or "")
    if not (from_num and sid and token):
        sys.stderr.write("  sms skipped (ESTIMATE_SMS_* env not set)\n")
        return False
    if len(digits) < 10:
        sys.stderr.write("  sms skipped (bad phone: {})\n".format(to_phone))
        return False
    to_e164 = "+" + digits if digits.startswith("1") and len(digits) == 11 else "+1" + digits[-10:]
    data = urllib.parse.urlencode({"From": from_num, "To": to_e164, "Body": body}).encode()
    req = urllib.request.Request(
        "https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json".format(sid),
        data=data, method="POST",
        headers={"Authorization": "Basic " + base64.b64encode("{}:{}".format(sid, token).encode()).decode(),
                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return 200 <= r.status < 300
    except Exception as e:
        sys.stderr.write("  sms to {} FAILED: {}\n".format(to_e164, str(e)[:150]))
        return False


# ---------------------------------------------------------------------------
# Sales-funnel mode: teaser image + GHL delivery (report goes to the TEAM, the
# lead gets a personalized "we found something" image in the nurture sequence)
# ---------------------------------------------------------------------------

GRADE_COLORS = {"A": (16, 163, 127), "B": (16, 163, 127),
                "C": (217, 119, 6), "D": (220, 38, 38), "F": (220, 38, 38)}
BLUE = (14, 88, 116)        # deep petrol (Santino's final pick over stock hues, 2026-07-20)
BLUE_LT = (20, 123, 165)    # gradient start
BLUE_DK = (10, 58, 82)      # gradient end
INK = (15, 23, 42)
MUTED = (100, 116, 139)

def _strip_dashes(s):
    """No em dashes anywhere in client-facing text (Santino's rule): turn a
    sentence-break dash into a period and capitalize what follows."""
    if not s:
        return s
    s = re.sub(r"\s*—\s*(\w)", lambda m: ". " + m.group(1).upper(), s)
    s = re.sub(r"\s+–\s+(\w)", lambda m: ". " + m.group(1).upper(), s)
    return s.replace("—", ", ")


def _google_bullets(gbp, rankings, mappack):
    """Compose the teaser's 'Google can't find you' bullets — bold label +
    consequence, max 2, every claim backed by the audit data or omitted.
    Competitor names come from the map-pack leaders (claims-honesty rule)."""
    bullets = []
    if not (gbp or {}).get("found"):
        bullets.append(("No Google Business Profile:",
                        "you can't appear in the map pack, where local jobs get decided."))
    leaders = []
    for p in (mappack or []):
        for comp in (p.get("competitors") or [])[:1]:
            t = (comp.get("title") or "").split(",")[0].strip()
            if t and t not in leaders:
                leaders.append(t)
    positions = [r.get("position") for r in (rankings or []) if r.get("position")]
    if rankings and not positions:
        lead_txt = " and ".join(leaders[:2]) if leaders else "Your competitors"
        bullets.append(("Ranking gap:", lead_txt + " hold the top spots. "
                        "You're not in the top 20 for any search we tracked."))
    elif positions and min(positions) > 3:
        bullets.append(("Ranking gap:",
                        "Your best Google position is #{}. Customers rarely scroll past "
                        "the top 3.".format(min(positions))))
    elif (len(bullets) < 2 and leaders
          and not any((p.get("client_rank") or 99) <= 3 for p in (mappack or []))):
        bullets.append(("Map pack gap:",
                        " and ".join(leaders[:2]) + " hold the top map spots in your cities."))
    return bullets[:2]


def make_teaser_image(business_name, issues_count, grade=None, money=None,
                      ai_cited=None, ai_total=None, ai_body=None, plan=None,
                      google_bullets=None):
    """FINAL teaser layout (Santino picked 'version B', 2026-07-19): PORTRAIT
    1080x1350 crop-of-the-report in brand blue. Header = big report title,
    business name on a soft yellow highlight, visibility grade badge top
    right. Then the light 'Google can't find you' box (x-bullets, bold label
    + consequence, real competitor names), the dark ChatGPT box (headline +
    the report's ai_body story + cited count), the gradient money box, and
    THE PLAN with step 1's headline bisected by the card edge. No em dashes.
    All content is real audit output; findings stay for the call."""
    from PIL import Image, ImageDraw, ImageFont
    S = 2
    W, H = 1080 * S, 1350 * S
    img = Image.new("RGB", (W, H), (241, 245, 249))
    d = ImageDraw.Draw(img)

    # card geometry — content is drawn on its own layer and pasted through a
    # rounded mask, so anything past the card bottom is cleanly clipped
    CX0, CY0 = 36 * S, 36 * S
    CX1, CY1 = W - 36 * S, H - 94 * S
    CARD_W, CARD_H = CX1 - CX0, CY1 - CY0
    d.rounded_rectangle([CX0 + 4 * S, CY0 + 7 * S, CX1 + 4 * S, CY1 + 7 * S],
                        radius=26 * S, fill=(203, 213, 225))
    card = Image.new("RGB", (CARD_W, CARD_H), (255, 255, 255))
    dc = ImageDraw.Draw(card)
    dc.rectangle([0, 0, CARD_W, 12 * S], fill=BLUE)   # top accent bar

    FB = str(ROOT / "assets" / "fonts" / "Poppins-Bold.ttf")
    FS = str(ROOT / "assets" / "fonts" / "Poppins-SemiBold.ttf")
    FM = str(ROOT / "assets" / "fonts" / "Poppins-Medium.ttf")
    FR = str(ROOT / "assets" / "fonts" / "Poppins-Regular.ttf")

    def fit(text, font_path, start, floor, max_w):
        size = start
        while size > floor:
            f = ImageFont.truetype(font_path, size * S)
            if dc.textlength(text, font=f) <= max_w:
                return f
            size -= 2
        return ImageFont.truetype(font_path, floor * S)

    def wrap(text, font, max_w):
        words, lines, cur = text.split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if dc.textlength(t, font=font) <= max_w:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def kicker(y, text, size=21):
        # small letter-spaced blue caps, like the report's section labels
        f = ImageFont.truetype(FB, size * S)
        x = LX
        for ch in text:
            dc.text((x, y), ch, font=f, fill=BLUE)
            x += dc.textlength(ch, font=f) + 3 * S
        return y + 34 * S

    LX = 52 * S                 # card-local (== 88px from image edge)
    RX = CARD_W - 52 * S
    CW = RX - LX

    # ---- header: big report title, THEIR name on a yellow highlight below so
    # it still pops in a phone message preview thumbnail ----
    title_w = CW - 170 * S              # clear the badge column top right
    f_title = fit("ONLINE VISIBILITY REPORT", FB, 46, 30, title_w)
    dc.text((LX, 54 * S), "ONLINE VISIBILITY REPORT", font=f_title, fill=INK)
    name = (business_name or "Your Business").strip()
    f_name = fit(name, FB, 36, 25, title_w - 32 * S)
    nmw = dc.textlength(name, font=f_name)
    dc.rounded_rectangle([LX - 6 * S, 128 * S, LX + nmw + 22 * S, 186 * S],
                         radius=10 * S, fill=(254, 246, 189))
    dc.text((LX + 8 * S, 135 * S), name, font=f_name, fill=INK)
    dc.line([LX, 214 * S, RX, 214 * S], fill=(226, 232, 240), width=S)

    # ---- grade badge, top right corner of the header ----
    g = (grade or "C").upper()[:1]
    gcol = GRADE_COLORS.get(g, (217, 119, 6))
    bs = 136 * S
    bx0, by0 = RX - bs, 44 * S
    tint = (240, 253, 244) if g in "AB" else (255, 251, 235) if g == "C" else (254, 242, 242)
    dc.rounded_rectangle([bx0, by0, bx0 + bs, by0 + bs], radius=22 * S,
                         fill=tint, outline=gcol, width=4 * S)
    f_grade = ImageFont.truetype(FB, 84 * S)
    gw = dc.textlength(g, font=f_grade)
    dc.text((bx0 + (bs - gw) / 2, by0 + 10 * S), g, font=f_grade, fill=gcol)
    f_lab = ImageFont.truetype(FS, 13 * S)
    lab = "VISIBILITY GRADE"
    lw = dc.textlength(lab, font=f_lab)
    dc.text((bx0 + (bs - lw) / 2, by0 + bs + 13 * S), lab, font=f_lab, fill=MUTED)

    y_after = 214 * S                     # header divider; sections flow below

    # ---- measure the flexible sections, then justify the gaps so step 1's
    # headline lands bisected exactly on the card's bottom edge ----
    money_h = (34 + 52 + 168) * S
    planhead_h = (34 + 46) * S
    row_anchor = CARD_H - 18 * S          # step-1 title top: edge cuts mid-letter

    # Google box: x-bullets, bold label + consequence (skipped if no bullets)
    gbullets = [(la_l, la_t) for la_l, la_t in (google_bullets or [])]
    gbox_h = 0
    bl_wrapped = []
    if gbullets:
        f_gh = ImageFont.truetype(FS, 27 * S)
        f_gl = ImageFont.truetype(FS, 22 * S)
        f_gb = ImageFont.truetype(FR, 22 * S)

        def wrap_rich(label, rest, max_w):
            words = ([(w, f_gl) for w in _strip_dashes(label).split()]
                     + [(w, f_gb) for w in _strip_dashes(rest).split()])
            lines, cur, cw_ = [], [], 0
            for w, fnt in words:
                ww = dc.textlength(w + " ", font=fnt)
                if cur and cw_ + ww > max_w:
                    lines.append(cur)
                    cur, cw_ = [], 0
                cur.append((w, fnt))
                cw_ += ww
            if cur:
                lines.append(cur)
            return lines[:3]

        bl_wrapped = [wrap_rich(l, t, CW - 100 * S) for l, t in gbullets]
        gbox_h = (24 * S + 38 * S + 14 * S
                  + sum(len(ls) * 31 * S + 12 * S for ls in bl_wrapped) + 10 * S)

    chip_lines = None
    body_lines = []
    f_ch = ImageFont.truetype(FS, 27 * S)
    f_cb = ImageFont.truetype(FR, 21 * S)
    if ai_total:
        head = ("ChatGPT is recommending someone else" if not ai_cited
                else "ChatGPT still recommends your competitors")
        chip_lines = wrap(head, f_ch, CW - 60 * S)[:2]
        sub = "Cited in {} of {} live AI answers across ChatGPT and Google.".format(
            int(ai_cited or 0), int(ai_total))
        f_cs = fit(sub, FS, 20, 16, CW - 60 * S)
        body_lines = wrap(_strip_dashes((ai_body or "").strip()), f_cb, CW - 60 * S)

        def _chip_h(nb):
            return (24 * S + len(chip_lines) * 38 * S
                    + ((12 * S + nb * 28 * S) if nb else 0)
                    + 12 * S + 24 * S + 24 * S)

        ngaps = 5 if gbullets else 4
        avail = row_anchor - y_after - money_h - planhead_h - gbox_h - ngaps * 28 * S
        keep = min(len(body_lines), 6)
        while keep > 2 and _chip_h(keep) > avail:
            keep -= 1
        if keep < len(body_lines):
            last = body_lines[keep - 1].rstrip(".,;")
            while dc.textlength(last + "…", font=f_cb) > CW - 60 * S and " " in last:
                last = last.rsplit(" ", 1)[0]
            body_lines = body_lines[:keep - 1] + [last + "…"]
        chip_h = _chip_h(len(body_lines))
    else:
        close = "Where is it going instead? We open the full report on your call."
        f_cl = ImageFont.truetype(FR, 24 * S)
        close_lines = wrap(close, f_cl, CW)
        chip_h = len(close_lines) * 36 * S

    base = ([40 * S] * 5) if gbullets else [44 * S, 44 * S, 46 * S, 40 * S]
    extra = row_anchor - y_after - gbox_h - chip_h - money_h - planhead_h - sum(base)
    gaps = [max(24 * S, b + extra // len(base)) for b in base]
    gi = 0

    y = y_after + gaps[gi]; gi += 1

    # ---- Google box (light, x-bullets with bold labels) ----
    if gbullets:
        dc.rounded_rectangle([LX, y, RX, y + gbox_h], radius=18 * S,
                             fill=(248, 250, 252), outline=(226, 232, 240), width=2 * S)
        dc.text((LX + 30 * S, y + 24 * S), "Google can't find you", font=f_gh, fill=INK)
        ty = y + 24 * S + 38 * S + 14 * S
        f_x = ImageFont.truetype(FB, 24 * S)
        for ls in bl_wrapped:
            dc.text((LX + 32 * S, ty - 2 * S), "×", font=f_x, fill=(220, 38, 38))
            for line in ls:
                x = LX + 66 * S
                for w, fnt in line:
                    dc.text((x, ty), w, font=fnt, fill=INK if fnt is f_gl else (71, 85, 105))
                    x += dc.textlength(w + " ", font=fnt)
                ty += 31 * S
            ty += 12 * S
        y += gbox_h + gaps[gi]; gi += 1

    # ---- ChatGPT chip (dark, like the report's quote box): headline, the
    # report's actual AI-search story, then the cited count ----
    if chip_lines is not None:
        dc.rounded_rectangle([LX, y, RX, y + chip_h], radius=18 * S, fill=(15, 23, 42))
        ty = y + 24 * S
        for line in chip_lines:
            dc.text((LX + 30 * S, ty), line, font=f_ch, fill=(255, 255, 255))
            ty += 38 * S
        if body_lines:
            ty += 12 * S
            for line in body_lines:
                dc.text((LX + 30 * S, ty), line, font=f_cb, fill=(203, 213, 225))
                ty += 28 * S
        dc.text((LX + 30 * S, ty + 12 * S), sub, font=f_cs, fill=(148, 163, 184))
    else:
        ty = y
        for line in close_lines:
            dc.text((LX, ty), line, font=f_cl, fill=MUTED)
            ty += 36 * S
    y += chip_h + gaps[gi]; gi += 1

    # ---- revenue: kicker + headline ABOVE the gradient box ----
    y = kicker(y, "WHAT IT'S WORTH")
    f_mh = fit("Estimated revenue left on the table", FB, 34, 26, CW)
    dc.text((LX, y), "Estimated revenue left on the table", font=f_mh, fill=INK)
    y += 52 * S

    box_h = 168 * S
    grad = Image.new("RGB", (64, 64))
    for gy in range(64):
        for gx in range(64):
            t = (gx + gy) / 126.0
            grad.putpixel((gx, gy), tuple(int(a + (b - a) * t) for a, b in zip(BLUE_LT, BLUE_DK)))
    grad = grad.resize((CW, box_h), Image.BILINEAR)
    gmask = Image.new("L", (CW, box_h), 0)
    ImageDraw.Draw(gmask).rounded_rectangle([0, 0, CW, box_h], radius=20 * S, fill=255)
    card.paste(grad, (LX, y), gmask)
    if money and money.get("low") is not None:
        amt = "${:,} – ${:,}".format(int(money["low"]), int(money["high"]))
        amt_sub = "per month, estimated range"
    else:
        amt = "{} fixable gaps found".format(max(int(issues_count or 0), 1))
        amt_sub = "each one is costing you calls"
    f_amt = fit(amt, FB, 62, 36, CW - 56 * S)
    aw = dc.textlength(amt, font=f_amt)
    dc.text(((CARD_W - aw) / 2, y + 30 * S), amt, font=f_amt, fill=(255, 255, 255))
    f_asub = ImageFont.truetype(FM, 21 * S)
    asw = dc.textlength(amt_sub, font=f_asub)
    dc.text(((CARD_W - asw) / 2, y + 112 * S), amt_sub, font=f_asub, fill=(219, 234, 254))
    y += box_h + gaps[gi]; gi += 1

    # ---- the plan: headline fully visible, step 1's own headline bisected by
    # the card edge so nothing is given away (top half of the letters only) ----
    y = kicker(y, "THE PLAN")
    f_ph = fit("The 5-step game plan to fix this", FB, 34, 26, CW)
    dc.text((LX, y), "The 5-step game plan to fix this", font=f_ph, fill=INK)

    steps = [s for s in (plan or []) if isinstance(s, dict) and s.get("title")]
    title = _strip_dashes((steps[0]["title"] if steps
                           else "Claim and build a Google Business Profile").strip())
    r = 21 * S
    ccy = row_anchor + 17 * S
    dc.ellipse([LX, ccy - r, LX + 2 * r, ccy + r], fill=BLUE)
    f_n = ImageFont.truetype(FB, 22 * S)
    nw = dc.textlength("1", font=f_n)
    dc.text((LX + r - nw / 2, ccy - 15 * S), "1", font=f_n, fill=(255, 255, 255))
    f_t = fit(title, FS, 27, 21, CW - 64 * S)
    dc.text((LX + 64 * S, row_anchor + 2 * S), title, font=f_t, fill=INK)

    # paste card through rounded mask (clips overflow), then footer on the bg
    mask = Image.new("L", (CARD_W, CARD_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, CARD_W, CARD_H], radius=26 * S, fill=255)
    img.paste(card, (CX0, CY0), mask)
    d.rounded_rectangle([CX0, CY0, CX1, CY1], radius=26 * S, outline=(226, 232, 240), width=S)

    foot = "Prepared by Restoration AI  •  restorationai.io"
    f_foot = ImageFont.truetype(FS, 20 * S)
    fw = d.textlength(foot, font=f_foot)
    d.text(((W - fw) / 2, H - 66 * S), foot, font=f_foot, fill=(120, 134, 156))

    img = img.resize((1080, 1350), Image.LANCZOS)
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _ghl(method, path, params=None, body=None, add_loc=True):
    key = os.environ.get("GHL_API_KEY")
    loc = os.environ.get("GHL_LOCATION_ID")
    if not (key and loc):
        raise RuntimeError("GHL_API_KEY / GHL_LOCATION_ID not set")
    q = dict(params or {})
    if add_loc and "/locations/" not in path:
        q.setdefault("locationId", loc)
    url = "https://services.leadconnectorhq.com{}".format(path)
    if q:
        url += "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + key, "Version": "2021-07-28",
                                          "Content-Type": "application/json", "Accept": "application/json",
                                          "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def _ghl_custom_field_ids():
    """Resolve (create if missing) the audit custom fields. Cached per run."""
    loc = os.environ.get("GHL_LOCATION_ID")
    want = {"audit_report_url": None, "audit_teaser_image_url": None,
            "audit_cities": None, "audit_grade": None,
            "visibility_grade": None}   # alias: Santino's SMS templates use this key
    existing = _ghl("GET", "/locations/{}/customFields".format(loc), params={}) or {}
    for f in existing.get("customFields", []):
        k = (f.get("fieldKey") or f.get("name") or "").split(".")[-1].lower()
        if k in want:
            want[k] = f.get("id")
    for name, fid in list(want.items()):
        if not fid:
            made = _ghl("POST", "/locations/{}/customFields".format(loc), params={},
                        body={"name": name, "dataType": "TEXT"})
            want[name] = (made.get("customField") or made).get("id")
    return want


def deliver_to_ghl(name, email, phone, domain, business_name, grade,
                   report_url, teaser_url, log, cities=None):
    """Find-or-create the lead's GHL contact; write the audit URLs + cities +
    grade to custom fields + a note. cities is a human phrase ("Memphis and
    Cincinnati") for SMS merge-field personalization. Best-effort: any failure
    logs and moves on (the report itself is already safe on R2)."""
    contact_id = None
    for q in [email, phone]:
        if not q:
            continue
        try:
            res = _ghl("GET", "/contacts/", params={"query": q})
            if res.get("contacts"):
                contact_id = res["contacts"][0]["id"]
                break
        except Exception as e:
            log("ghl search failed: " + str(e)[:100])
    fields = _ghl_custom_field_ids()
    payload_fields = [
        {"id": fields["audit_report_url"], "field_value": report_url},
        {"id": fields["audit_teaser_image_url"], "field_value": teaser_url},
    ]
    if cities:
        payload_fields.append({"id": fields["audit_cities"], "field_value": cities})
    if grade:
        payload_fields.append({"id": fields["audit_grade"], "field_value": str(grade)})
        payload_fields.append({"id": fields["visibility_grade"], "field_value": str(grade)})
    if contact_id:
        _ghl("PUT", "/contacts/{}".format(contact_id), params={},
             body={"customFields": payload_fields})
    else:
        parts = (name or "").split()
        made = _ghl("POST", "/contacts/", params={}, body={
            "firstName": parts[0] if parts else "", "lastName": " ".join(parts[1:]),
            "email": email or None, "phone": phone or None,
            "companyName": business_name or domain,
            "tags": ["opdigital-audit"], "source": "opdigital funnel audit",
            "locationId": os.environ.get("GHL_LOCATION_ID"),
            "customFields": payload_fields})
        contact_id = (made.get("contact") or {}).get("id")
    if contact_id:
        _ghl("POST", "/contacts/{}/notes".format(contact_id), params={},
             body={"body": "AUDIT READY (grade {g}) for {d}\nReport: {r}\nTeaser image: {t}".format(
                 g=grade, d=domain, r=report_url, t=teaser_url)})
    # (No ops SMS by design — the GHL workflow automation owns notifications;
    # the internal SendGrid notify email still fires via email_mode='internal'.)
    log("ghl delivery done (contact {})".format(contact_id or "NOT FOUND/CREATED"))
    return contact_id


def send_email(to_addr, subject, html_body):
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        sys.stderr.write("  email skipped (no SENDGRID_API_KEY): {}\n".format(subject))
        return False
    payload = {"personalizations": [{"to": [{"email": to_addr}]}],
               "from": {"email": FROM_EMAIL, "name": "Rank AI"},
               "subject": subject,
               "content": [{"type": "text/html", "value": html_body}]}
    req = urllib.request.Request("https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return 200 <= r.status < 300
    except Exception as e:
        sys.stderr.write("  email to {} FAILED: {}\n".format(to_addr, str(e)[:150]))
        return False


def _lead_email_html(prof, domain, report_url, copy):
    return """<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:560px;margin:0 auto;color:#0f172a">
<h2 style="letter-spacing:-.01em">Your Rank AI audit for {dom} is ready</h2>
<p>We ran {biz} through live Google Search, Google Maps and AI-assistant checks. Grade: <b>{grade}</b>.</p>
<p style="color:#334155">{verdict}</p>
<p style="margin:26px 0"><a href="{url}" style="background:#4f46e5;color:#fff;text-decoration:none;font-weight:700;padding:13px 26px;border-radius:10px;display:inline-block">View your full audit report</a></p>
<p style="font-size:13px;color:#64748b">Questions? Just reply to this email, or book a free strategy call:
<a href="{book}">{book}</a></p>
<p style="font-size:12px;color:#94a3b8">Rank AI — by Restoration AI &middot; contact@restorationai.io</p>
</div>""".format(dom=_esc(domain), biz=_esc(prof["business_name"]),
                 grade=_esc(copy.get("grade")), verdict=_esc(copy.get("verdict")),
                 url=report_url, book=BOOK_URL)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_audit(website, name, email, phone, audit_id=None, email_mode="all", progress=None,
              business_name=None, place_id=None, cid=None, sales_mode=False):
    """Full pipeline. email_mode: 'all' | 'internal' (notify only) | 'none'.
    business_name/place_id/cid: optional GBP identity already confirmed by the
    prospect in the stepper — used to pin the listing instead of re-guessing.
    sales_mode: funnel-triggered pre-meeting audit — generates the teaser image
    and delivers report/teaser URLs to the lead's GHL contact (custom fields +
    note) instead of emailing the lead. Returns {report_url, grade, ...}."""
    def log(msg):
        print("  [{}] {}".format(dt.datetime.now().strftime("%H:%M:%S"), msg))
        if progress:
            try:
                progress(msg)
            except Exception:
                pass

    audit_id = audit_id or uuid.uuid4().hex[:12]
    domain = _norm_domain(website)
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain):
        raise ValueError("invalid website: " + str(website))

    # Leads typo their own domain in the form (ameritibe.com for
    # ameritribe.com, 2026-07-22) — a dead hostname must not kill the audit.
    # If the typed domain doesn't resolve but their EMAIL domain does, use it.
    def _resolves(host):
        import socket
        try:
            socket.getaddrinfo(host, 443)
            return True
        except OSError:
            return False

    _FREE_MAIL = {"gmail.com", "yahoo.com", "aol.com", "hotmail.com",
                  "outlook.com", "icloud.com", "msn.com", "live.com",
                  "att.net", "comcast.net", "protonmail.com", "me.com"}
    if not _resolves(domain) and not _resolves("www." + domain):
        alt = (email or "").rsplit("@", 1)[-1].strip().lower() if "@" in (email or "") else ""
        if alt and alt not in _FREE_MAIL and alt != domain and _resolves(alt):
            log("domain {} does not resolve — using email domain {} instead".format(domain, alt))
            domain = alt
        else:
            raise ValueError(
                "the submitted website {} does not resolve (likely a typo in "
                "the form) and no usable email-domain fallback exists".format(domain))
    # franchise/shared-domain support: profile from the submitted PAGE, not
    # the domain root (puroclean.com/eastlasvegas is a business; puroclean.com
    # is a corporation with 400 locations)
    m_path = re.match(r"^(?:https?://)?[^/?#]+(/[^?#]*)", (website or "").strip())
    sub_path = (m_path.group(1).rstrip("/") if m_path else "")
    start_url = "https://" + domain + sub_path if sub_path else None
    errors = []
    costs = {"dataforseo": 0.0, "claude": 0.0}
    usages = []
    auth = _dfs_auth()
    client = _claude()

    log("audit {} for {} started".format(audit_id, domain))

    # 1. site -> profile
    pages = fetch_site(domain, start_url)
    prof, u = profile_site(client, start_url or domain, pages)
    usages.append(u)
    service = prof["services"][0]
    cities = prof["cities"]
    log("profile: {} | {} | cities {}".format(
        prof["business_name"], service, [c["city"] for c in cities]))

    # geocode
    cities_geo = []
    for c in cities:
        ll = geocode(c["city"], c["state"])
        time.sleep(1.1)  # nominatim rate courtesy
        if ll:
            cities_geo.append({"city": c["city"], "state": c["state"], "lat": ll[0], "lng": ll[1]})
    if not cities_geo:
        raise RuntimeError("could not geocode any service city")

    # GBP confirm — pinned by id when the prospect already picked their listing
    gbp = {"found": False}
    if place_id or cid:
        try:
            gbp, c = gbp_by_id(auth, place_id=place_id, cid=cid)
            costs["dataforseo"] += c
            log("gbp (pinned by id): {}".format(gbp))
        except Exception as e:
            errors.append("gbp_by_id: " + str(e)[:150])
        if not gbp.get("found"):
            # id lookup missed (listings DB lag) — trust the confirmed identity anyway
            gbp = {"found": True, "title": business_name or prof["business_name"],
                   "place_id": place_id, "cid": str(cid) if cid else None,
                   "rating": None, "reviews": None, "address": None}
            log("gbp: listings lookup missed; pinning ids from stepper selection")
    if not gbp.get("found"):
        try:
            gbp, c = gbp_confirm(auth, business_name or prof.get("gbp_query") or prof["business_name"],
                                 prof["business_name"], cities_geo[0]["lat"], cities_geo[0]["lng"],
                                 domain=domain)
            costs["dataforseo"] += c
            log("gbp: {}".format(gbp))
        except Exception as e:
            errors.append("gbp_confirm: " + str(e)[:150])
    prof["gbp"] = gbp

    # 2. organic rankings
    rankings = []
    try:
        rankings, c = run_rankings(auth, domain, service, cities)
        costs["dataforseo"] += c
        log("rankings: {} queries, {} ranked".format(
            len(rankings), sum(1 for r in rankings if r["position"])))
    except Exception as e:
        errors.append("rankings: " + str(e)[:150])

    # 3. mini geo-grid (needs a found GBP to match the listing)
    geogrid = []
    if gbp.get("found"):
        try:
            geogrid, c = run_geogrid(
                auth, audit_id,
                {"name": prof["business_name"], "cid": gbp.get("cid"), "place_id": gbp.get("place_id")},
                service, cities_geo)
            costs["dataforseo"] += c
            log("geogrid: {}".format([(g["city"], g["avg_rank"], str(g["pct_top3"]) + "%") for g in geogrid]))
        except Exception as e:
            errors.append("geogrid: " + str(e)[:150])
    else:
        errors.append("geogrid skipped: GBP listing not confirmed")

    # 4. AI search
    ai_results = []
    try:
        ai_results, c = run_ai_search(auth, domain, prof["business_name"], service, cities)
        costs["dataforseo"] += c
        log("ai-search: cited {}/{}".format(
            sum(1 for r in ai_results if r.get("cited")),
            sum(1 for r in ai_results if r.get("cited") is not None)))
    except Exception as e:
        errors.append("ai_search: " + str(e)[:150])

    # 5. map pack / reviews
    mappack = []
    try:
        mappack, c = run_mappack(auth, prof["business_name"], service, cities_geo)
        costs["dataforseo"] += c
    except Exception as e:
        errors.append("mappack: " + str(e)[:150])

    # 6. volumes + revenue math
    money = None
    vols = {}
    try:
        vols, c = run_volumes(auth, [r["keyword"] for r in rankings])
        costs["dataforseo"] += c
        money = revenue_math(rankings, vols, prof.get("vertical") or "water")
        log("money: {}".format({k: money[k] for k in ("low", "high")} if money else None))
    except Exception as e:
        errors.append("volumes: " + str(e)[:150])

    # 7. report copy + HTML
    data = {"business": {k: prof.get(k) for k in
                         ("business_name", "phone", "vertical", "services", "cities")},
            "domain": domain, "gbp": gbp, "rankings": rankings, "geogrid": geogrid,
            "ai_search": ai_results, "map_pack": mappack, "revenue_estimate": money,
            "search_volumes": vols}
    copy, u = generate_report_copy(client, data)
    usages.append(u)
    html_out = build_html(audit_id, prof, domain, copy, rankings, geogrid, ai_results, mappack, money)

    # 8. host on R2
    report_key = "{}/{}/report.html".format(PREFIX, audit_id)
    if not r2_put(BUCKET, report_key, html_out.encode(), "text/html; charset=utf-8"):
        raise RuntimeError("R2 upload of report failed")
    report_url = "{}/{}".format(PUBLIC_BASE, report_key)
    costs["claude"] = _claude_cost(usages)
    r2_put(PRIVATE_BUCKET, "{}/{}/audit.json".format(PREFIX, audit_id),
           json.dumps({"audit_id": audit_id, "requested_by": {"name": name, "email": email, "phone": phone},
                       "data": data, "copy": copy, "costs": costs, "errors": errors,
                       "created_at": _now_iso()}, indent=1).encode(),
           "application/json")
    log("report: " + report_url)

    # 8b. sales-funnel extras: teaser image + GHL contact delivery
    teaser_url = None
    if sales_mode:
        try:
            n_fixes = len(copy.get("game_plan") or []) or 5
            png = make_teaser_image(prof["business_name"], n_fixes, copy.get("grade"),
                                    money=money,
                                    ai_cited=sum(1 for r in ai_results if r.get("cited")),
                                    ai_total=sum(1 for r in ai_results if r.get("cited") is not None),
                                    ai_body=copy.get("ai_body"),
                                    plan=copy.get("game_plan"),
                                    google_bullets=_google_bullets(gbp, rankings, mappack))
            teaser_key = "{}/{}/teaser.png".format(PREFIX, audit_id)
            r2_put(BUCKET, teaser_key, png, "image/png")
            teaser_url = "{}/{}".format(PUBLIC_BASE, teaser_key)
            log("teaser: " + teaser_url)
        except Exception as e:
            errors.append("teaser: " + str(e)[:150])
            log("teaser FAILED: " + str(e)[:150])
        try:
            city_names = [c["city"] for c in cities][:3]
            cities_phrase = (" and ".join([", ".join(city_names[:-1]), city_names[-1]])
                             if len(city_names) > 2 else " and ".join(city_names))
            deliver_to_ghl(name, email, phone, domain, prof["business_name"],
                           copy.get("grade"), report_url, teaser_url or report_url, log,
                           cities=cities_phrase)
        except Exception as e:
            errors.append("ghl_delivery: " + str(e)[:150])
            log("ghl delivery FAILED: " + str(e)[:150])

    # 9. delivery
    if email_mode in ("all",):
        send_email(email, "Your Rank AI audit for {}".format(domain),
                   _lead_email_html(prof, domain, report_url, copy))
        if phone:
            send_sms(phone, "Rank AI: your free visibility audit for {} is ready (grade {}). "
                            "View it here: {}".format(domain, copy.get("grade"), report_url))
    if email_mode in ("all", "internal"):
        notif = """<div style="font-family:monospace;font-size:13px">
<b>NEW LEAD — free audit requested</b><br><br>
Name: {n}<br>Email: {e}<br>Phone: {p}<br>Website: {d}<br>
Business: {b}<br>Grade: {g}<br>Report: <a href="{u}">{u}</a><br>
Costs: DFS ${dc:.2f} + Claude ${cc:.2f}<br>Errors: {err}</div>""".format(
            n=_esc(name), e=_esc(email), p=_esc(phone), d=_esc(domain),
            b=_esc(prof["business_name"]), g=_esc(copy.get("grade")), u=report_url,
            dc=costs["dataforseo"], cc=costs["claude"], err=_esc("; ".join(errors) or "none"))
        send_email(NOTIFY_EMAIL, "[Rank AI lead] {} — audit {}".format(domain, copy.get("grade")), notif)

    # 10. lead log
    try:
        append_lead_jsonl({"audit_id": audit_id, "created_at": _now_iso(), "name": name,
                           "email": email, "phone": phone, "domain": domain,
                           "business_name": prof["business_name"], "grade": copy.get("grade"),
                           "report_url": report_url})
    except Exception as e:
        errors.append("lead_log: " + str(e)[:120])

    return {"audit_id": audit_id, "report_url": report_url, "grade": copy.get("grade"),
            "teaser_url": teaser_url,
            "business_name": prof["business_name"], "domain": domain,
            "costs": costs, "errors": errors}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Rank AI free-audit pipeline")
    ap.add_argument("--url", required=True)
    ap.add_argument("--name", default="")
    ap.add_argument("--email", required=True)
    ap.add_argument("--phone", default="")
    ap.add_argument("--audit-id")
    ap.add_argument("--email-mode", choices=["all", "internal", "none"], default="all")
    args = ap.parse_args()
    t0 = time.time()
    res = run_audit(args.url, args.name, args.email, args.phone,
                    audit_id=args.audit_id, email_mode=args.email_mode)
    print("\n== DONE in {:.0f}s ==".format(time.time() - t0))
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
