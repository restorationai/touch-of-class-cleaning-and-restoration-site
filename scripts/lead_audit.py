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
import urllib.error
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
              "biohazard": 4000, "reconstruction": 12000,
              # non-restoration verticals audited for competitive intel — keep
              # tickets honest per trade or the one-job floor overstates
              "plumbing": 650,
              # decks, fences, patios, outdoor structures. The paid funnel
              # takes home-services leads who are not restoration at all
              # (Jose Mendoza / Ed's Construction Services, 2026-08-04), and
              # forcing them onto "reconstruction" made the report tell a deck
              # builder his upside was "one full insured loss per month,
              # mitigation plus rebuild and contents". Ticket is grounded in
              # his own published pricing: $22-32/sq ft, so a 300-400 sq ft
              # deck runs roughly $6,600-$12,800.
              "carpentry": 9000}
DEFAULT_TICKET = 4500
# Floor for the shown revenue range on restoration audits (Santino 2026-07-28:
# "minimum of 14,500 to 19,000 per month" — one full water-loss project/month,
# mitigation + rebuild + contents). Non-restoration trades floor at one job.
RESTORATION_FLOOR = (14500, 19000)
NON_RESTORATION_VERTICALS = {"plumbing", "carpentry"}

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


# Lead-site fetches must survive WAF/bot filtering: some hosts 403 the polite
# audit UA — or Railway's datacenter egress IP outright — while serving real
# browsers fine (peakshieldroofing.com killed Isaac Gomez's audit in 1.2s with
# a 403 on 2026-07-31, so his nurture SMS merged EMPTY grade/teaser fields).
BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_BLOCKED_CODES = {401, 403, 405, 406, 409, 429, 500, 503}


class SiteDownError(RuntimeError):
    """The lead's website is genuinely unreachable: DNS does not resolve, or
    nothing accepts a TCP connection on 443/80. GHL messages these leads
    'your site isn't even up' — so this must NEVER be raised when the site
    answered with ANY HTTP status (a WAF 403 means the site is UP; falsely
    telling a lead their working site is down would be embarrassing)."""


def _site_is_down(domain):
    """Definitive probe: True only when DNS fails or neither 443 nor 80
    accepts a TCP connection. A bot-blocking WAF still accepts the TCP
    connection, so blocked-but-alive sites always return False."""
    import socket
    for host in (domain, "www." + domain):
        for port in (443, 80):
            try:
                with socket.create_connection((host, port), timeout=8):
                    return False
            except OSError:
                continue
    return True


def _get_site_html(url, timeout=25):
    """Fetch a lead's page; on a blocked/refused status retry once with full
    browser headers before giving up."""
    try:
        return _http_get(url, timeout=timeout).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code not in _BLOCKED_CODES:
            raise
    return _http_get(url, timeout=timeout, headers=BROWSER_HEADERS).decode("utf-8", "ignore")


def _fetch_text_via_dfs(url, js=False):
    """Last resort when the site blocks our server IP entirely (WAF / IP
    reputation): pull the page through DataForSEO's crawler, which fetches
    from different egress IPs. Returns PLAIN TEXT (not HTML) — enough to
    profile the business; link discovery is skipped. Costs ~$0.0002.

    js=True renders the page in a real browser first (~$0.0015, ~20s). Needed
    for client-side-rendered sites whose server HTML is an empty app shell —
    see the ProfileIncompleteError recovery in run_audit."""
    if not urllib.parse.urlparse(url).path:
        url += "/"   # DFS content_parsing returns 0 items for a bare domain URL
    items, _cost, task = _dfs(
        "https://api.dataforseo.com/v3/on_page/content_parsing/live",
        [{"url": url, "enable_javascript": bool(js)}], _dfs_auth(),
        timeout=180 if js else 90)
    if task.get("status_code") and int(task["status_code"]) >= 40000:
        raise RuntimeError("content_parsing: " + str(task.get("status_message")))
    if not items:
        raise RuntimeError("content_parsing returned no items for " + url)

    out = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("text", "title") and isinstance(v, str):
                    out.append(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)

    walk(items[0].get("page_content") or {})
    txt = re.sub(r"\s+", " ", " ".join(out)).strip()
    if len(txt) < 200:
        raise RuntimeError("content_parsing text too thin ({} chars)".format(len(txt)))
    return txt


def _html_to_text(raw):
    txt = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    txt = html_mod.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


# Domain-parking landers are "no real website", not a crawl failure. GoDaddy's
# parking app (proservrestoration.com, Virgil Santa 2026-08-14) serves a
# 114-byte shell that JS-bounces / -> /lander, and the lander itself is a JS
# app with ZERO extractable text — even DataForSEO's browser render returns
# no items, so no length threshold or JS retry can save it.
_PARKED_MARKERS = ("parking-lander", 'ap:"parking"', "lander_system",
                   "wsimg.com/parking", "sedoparking", "parkingcrew",
                   "this domain is for sale", "domain is parked",
                   "hugedomains.com", "dan.com/buy-domain", "afternic.com",
                   "godaddy.com/forsale", "launching soon")


def _parked_page(raw):
    low = (raw or "").lower()
    return any(m in low for m in _PARKED_MARKERS)


def _js_redirect_target(raw, base_url):
    """Redirect target of a tiny JS/meta bounce page (same host only)."""
    if not raw or len(raw) > 4000:
        return None
    m = (re.search(r'window\.location(?:\.href)?\s*=\s*["\']([^"\']+)["\']', raw)
         or re.search(r'(?i)http-equiv=["\']refresh["\'][^>]*url=([^"\'>\s]+)', raw))
    if not m:
        return None
    nxt = urllib.parse.urljoin(base_url, m.group(1).strip())
    if _norm_domain(nxt) != _norm_domain(base_url):
        return None
    return nxt


class ProfileIncompleteError(RuntimeError):
    """The site text we fetched carries no services or no service cities, so
    Claude could not build a profile without inventing facts. Raised so the
    caller can escalate to a JavaScript-rendered re-crawl (see fetch_site)."""


# "Restoration 1 of Hartland" / "PuroClean of East Las Vegas" — the funnel
# captures the lead's OWN franchise name even when they submit the corporate
# root as their website. The root is a national brand with hundreds of
# locations and names no single city, so the profiler fails with no cities
# (restoration1.com killed Russ Burley's audit 2026-08-04; puroclean.com killed
# Gregory Arianoff's 2026-07-19). Their own page usually lives at
# /{locality-slug} on the same domain, which the start_url mechanism already
# knows how to profile.
_FRANCHISE_OF = re.compile(r"(?i)\bof\s+(?:the\s+)?(.+)$")


def franchise_start_urls(domain, business_name):
    """Candidate franchise-location page URLs derived from the lead's business
    name. Returns [] when the name carries no ' of {locality}' suffix."""
    m = _FRANCHISE_OF.search((business_name or "").strip())
    if not m:
        return []
    locality = m.group(1).strip()
    if not locality or len(locality) > 40:
        return []
    slug = re.sub(r"[^a-z0-9]+", "-", locality.lower()).strip("-")
    if not slug:
        return []
    out = ["https://{}/{}".format(domain, slug)]
    if "-" in slug:
        out.append("https://{}/{}".format(domain, slug.replace("-", "")))
    return out


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

def fetch_site(domain, start_url=None, force_js=False):
    """Homepage + up to 4 about/service pages, as plain text.

    start_url: when the lead submitted a PAGE on a shared domain (franchise
    sites like puroclean.com/eastlasvegas), profile from THAT page — the
    domain root is the corporate brand, not their business — and prefer
    links inside the same subtree.

    force_js: skip the raw fetch and render the page in a real browser via
    DataForSEO. Used only as a retry after the raw HTML profiled empty."""
    pages = {}
    base = "https://" + domain
    target = start_url or base
    if force_js:
        pages["homepage"] = _fetch_text_via_dfs(target, js=True)[:15000]
        # Links in a client-rendered app are in-app routes with no server HTML
        # worth fetching; the rendered homepage carries the content.
        return pages
    raw = None
    try:
        raw = _get_site_html(target)
    except Exception as e_direct:
        if not start_url:
            try:
                raw = _get_site_html("http://" + domain)
            except Exception:
                raw = None
        if raw is None:
            # Direct fetch blocked (WAF 403 on our server IP, etc.) — pull the
            # text through DataForSEO's crawler so the audit still completes.
            try:
                try:
                    pages["homepage"] = _fetch_text_via_dfs(target)[:15000]
                except Exception:
                    # blocked AND client-rendered: render it in a browser
                    pages["homepage"] = _fetch_text_via_dfs(target, js=True)[:15000]
            except Exception:
                # Classify before giving up: an HTTPError means the site
                # ANSWERED (it is up — Isaac Gomez's WAF 403, 2026-07-31, must
                # stay a plain failure). Only a no-response failure PLUS a
                # failed TCP probe on 443/80 counts as the site being down.
                if not isinstance(e_direct, urllib.error.HTTPError) and _site_is_down(domain):
                    raise SiteDownError(
                        "the website {} is not reachable at all (no DNS answer or "
                        "nothing accepting connections on 443/80) — the site looks "
                        "genuinely down, not just blocking crawlers".format(domain)
                    ) from e_direct
                raise e_direct
            sys.stderr.write("  fetch_site: direct fetch blocked ({}) — used "
                             "DataForSEO crawler fallback\n".format(str(e_direct)[:100]))
            return pages
    txt = _html_to_text(raw)
    if len(txt) < 300:
        # Tiny shell page: follow ONE same-host JS/meta redirect. GoDaddy
        # parked domains serve a near-empty shell that bounces / -> /lander.
        nxt = _js_redirect_target(raw, target)
        if nxt:
            try:
                raw2 = _get_site_html(nxt)
                if _parked_page(raw2) or len(_html_to_text(raw2)) > len(txt):
                    raw = raw2
                    txt = _html_to_text(raw)
            except Exception:
                pass
    if _parked_page(raw) and len(txt) < 400:
        raise SiteDownError(
            "{} serves a domain-parking/placeholder page, not a real "
            "website".format(domain))
    pages["homepage"] = txt[:15000]

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
            pages[u] = _html_to_text(_get_site_html(u))[:8000]
        except Exception:
            continue
    return pages


PROFILE_SYSTEM = """You extract a structured business profile from website text for a local-SEO audit.
Return ONLY a JSON object (no prose, no markdown fences) with exactly these keys:
{
 "business_name": str,           // the customer-facing brand name
 "phone": str|null,
 "vertical": str,                // one of: water, fire, mold, storm, biohazard, reconstruction,
                                 // plumbing, carpentry. Pick the RESTORATION vertical only when
                                 // the business actually does damage restoration. A deck/fence or
                                 // general outdoor-construction contractor is "carpentry"; a
                                 // plumber is "plumbing". Never force a non-restoration trade
                                 // onto a restoration vertical.
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
                     "enum": ["water", "fire", "mold", "storm", "biohazard", "reconstruction",
                              "plumbing", "carpentry"]},
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
        raise ProfileIncompleteError("profile incomplete: services/cities missing")
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
# Step 1c — profile fallback chain (tier b: Google listing, tier c: form data)
# The audit must ALWAYS complete: when the lead's site can't be profiled
# (parked domain, JS app the crawlers extract nothing from, WAF, SSL breakage)
# we profile the business from its own Google listing, and as a last resort
# from nothing but the form fields. Virgil Santa (proservrestoration.com,
# 2026-08-14): parked GoDaddy domain killed the audit and his nurture SMS
# merged empty fields.
# ---------------------------------------------------------------------------

_FREE_MAIL = {"gmail.com", "yahoo.com", "aol.com", "hotmail.com",
              "outlook.com", "icloud.com", "msn.com", "live.com",
              "att.net", "comcast.net", "protonmail.com", "me.com"}

_US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

# NANP area code -> (principal city, full state). Fallback geography only —
# close-enough beats nothing when the form is all we have.
_AREA_CODES = {
    "205": ("Birmingham", "Alabama"), "251": ("Mobile", "Alabama"), "256": ("Huntsville", "Alabama"),
    "334": ("Montgomery", "Alabama"), "659": ("Birmingham", "Alabama"), "938": ("Huntsville", "Alabama"),
    "907": ("Anchorage", "Alaska"),
    "480": ("Mesa", "Arizona"), "520": ("Tucson", "Arizona"), "602": ("Phoenix", "Arizona"),
    "623": ("Phoenix", "Arizona"), "928": ("Flagstaff", "Arizona"),
    "479": ("Fort Smith", "Arkansas"), "501": ("Little Rock", "Arkansas"), "870": ("Jonesboro", "Arkansas"),
    "209": ("Stockton", "California"), "213": ("Los Angeles", "California"), "279": ("Sacramento", "California"),
    "310": ("Los Angeles", "California"), "323": ("Los Angeles", "California"), "341": ("Oakland", "California"),
    "408": ("San Jose", "California"), "415": ("San Francisco", "California"), "424": ("Los Angeles", "California"),
    "442": ("Oceanside", "California"), "510": ("Oakland", "California"), "530": ("Redding", "California"),
    "559": ("Fresno", "California"), "562": ("Long Beach", "California"), "619": ("San Diego", "California"),
    "626": ("Pasadena", "California"), "628": ("San Francisco", "California"), "650": ("San Mateo", "California"),
    "657": ("Anaheim", "California"), "661": ("Bakersfield", "California"), "669": ("San Jose", "California"),
    "707": ("Santa Rosa", "California"), "714": ("Anaheim", "California"), "747": ("Burbank", "California"),
    "760": ("Oceanside", "California"), "805": ("Ventura", "California"), "818": ("Burbank", "California"),
    "820": ("Ventura", "California"), "831": ("Salinas", "California"), "840": ("San Bernardino", "California"),
    "858": ("San Diego", "California"), "909": ("San Bernardino", "California"), "916": ("Sacramento", "California"),
    "925": ("Concord", "California"), "949": ("Irvine", "California"), "951": ("Riverside", "California"),
    "303": ("Denver", "Colorado"), "719": ("Colorado Springs", "Colorado"), "720": ("Denver", "Colorado"),
    "970": ("Fort Collins", "Colorado"), "983": ("Denver", "Colorado"),
    "203": ("Bridgeport", "Connecticut"), "475": ("Bridgeport", "Connecticut"),
    "860": ("Hartford", "Connecticut"), "959": ("Hartford", "Connecticut"),
    "302": ("Wilmington", "Delaware"),
    "202": ("Washington", "District of Columbia"), "771": ("Washington", "District of Columbia"),
    "239": ("Fort Myers", "Florida"), "305": ("Miami", "Florida"), "321": ("Orlando", "Florida"),
    "352": ("Gainesville", "Florida"), "386": ("Daytona Beach", "Florida"), "407": ("Orlando", "Florida"),
    "448": ("Pensacola", "Florida"), "561": ("West Palm Beach", "Florida"), "656": ("Orlando", "Florida"),
    "689": ("Orlando", "Florida"), "727": ("St. Petersburg", "Florida"), "754": ("Fort Lauderdale", "Florida"),
    "772": ("Port St. Lucie", "Florida"), "786": ("Miami", "Florida"), "813": ("Tampa", "Florida"),
    "850": ("Tallahassee", "Florida"), "863": ("Lakeland", "Florida"), "904": ("Jacksonville", "Florida"),
    "941": ("Sarasota", "Florida"), "954": ("Fort Lauderdale", "Florida"),
    "229": ("Albany", "Georgia"), "404": ("Atlanta", "Georgia"), "470": ("Atlanta", "Georgia"),
    "478": ("Macon", "Georgia"), "678": ("Atlanta", "Georgia"), "706": ("Augusta", "Georgia"),
    "762": ("Augusta", "Georgia"), "770": ("Atlanta", "Georgia"), "912": ("Savannah", "Georgia"),
    "943": ("Atlanta", "Georgia"),
    "808": ("Honolulu", "Hawaii"),
    "208": ("Boise", "Idaho"), "986": ("Boise", "Idaho"),
    "217": ("Springfield", "Illinois"), "224": ("Elgin", "Illinois"), "309": ("Peoria", "Illinois"),
    "312": ("Chicago", "Illinois"), "331": ("Aurora", "Illinois"), "618": ("Belleville", "Illinois"),
    "630": ("Aurora", "Illinois"), "708": ("Cicero", "Illinois"), "773": ("Chicago", "Illinois"),
    "779": ("Rockford", "Illinois"), "815": ("Rockford", "Illinois"), "847": ("Elgin", "Illinois"),
    "872": ("Chicago", "Illinois"),
    "219": ("Hammond", "Indiana"), "260": ("Fort Wayne", "Indiana"), "317": ("Indianapolis", "Indiana"),
    "463": ("Indianapolis", "Indiana"), "574": ("South Bend", "Indiana"), "765": ("Muncie", "Indiana"),
    "812": ("Evansville", "Indiana"), "930": ("Evansville", "Indiana"),
    "319": ("Cedar Rapids", "Iowa"), "515": ("Des Moines", "Iowa"), "563": ("Davenport", "Iowa"),
    "641": ("Mason City", "Iowa"), "712": ("Sioux City", "Iowa"),
    "316": ("Wichita", "Kansas"), "620": ("Dodge City", "Kansas"), "785": ("Topeka", "Kansas"),
    "913": ("Kansas City", "Kansas"),
    "270": ("Bowling Green", "Kentucky"), "364": ("Bowling Green", "Kentucky"), "502": ("Louisville", "Kentucky"),
    "606": ("Ashland", "Kentucky"), "859": ("Lexington", "Kentucky"),
    "225": ("Baton Rouge", "Louisiana"), "318": ("Shreveport", "Louisiana"), "337": ("Lafayette", "Louisiana"),
    "504": ("New Orleans", "Louisiana"), "985": ("Houma", "Louisiana"),
    "207": ("Portland", "Maine"),
    "240": ("Rockville", "Maryland"), "301": ("Silver Spring", "Maryland"), "410": ("Baltimore", "Maryland"),
    "443": ("Baltimore", "Maryland"), "667": ("Baltimore", "Maryland"),
    "339": ("Boston", "Massachusetts"), "351": ("Lowell", "Massachusetts"), "413": ("Springfield", "Massachusetts"),
    "508": ("Worcester", "Massachusetts"), "617": ("Boston", "Massachusetts"), "774": ("Worcester", "Massachusetts"),
    "781": ("Boston", "Massachusetts"), "857": ("Boston", "Massachusetts"), "978": ("Lowell", "Massachusetts"),
    "231": ("Muskegon", "Michigan"), "248": ("Troy", "Michigan"), "269": ("Kalamazoo", "Michigan"),
    "313": ("Detroit", "Michigan"), "517": ("Lansing", "Michigan"), "586": ("Warren", "Michigan"),
    "616": ("Grand Rapids", "Michigan"), "679": ("Detroit", "Michigan"), "734": ("Ann Arbor", "Michigan"),
    "810": ("Flint", "Michigan"), "906": ("Marquette", "Michigan"), "947": ("Troy", "Michigan"),
    "989": ("Saginaw", "Michigan"),
    "218": ("Duluth", "Minnesota"), "320": ("St. Cloud", "Minnesota"), "507": ("Rochester", "Minnesota"),
    "612": ("Minneapolis", "Minnesota"), "651": ("St. Paul", "Minnesota"), "763": ("Brooklyn Park", "Minnesota"),
    "952": ("Bloomington", "Minnesota"),
    "228": ("Gulfport", "Mississippi"), "601": ("Jackson", "Mississippi"), "662": ("Tupelo", "Mississippi"),
    "769": ("Jackson", "Mississippi"),
    "314": ("St. Louis", "Missouri"), "417": ("Springfield", "Missouri"), "557": ("St. Louis", "Missouri"),
    "573": ("Columbia", "Missouri"), "636": ("O'Fallon", "Missouri"), "660": ("Sedalia", "Missouri"),
    "816": ("Kansas City", "Missouri"),
    "406": ("Billings", "Montana"),
    "308": ("Grand Island", "Nebraska"), "402": ("Omaha", "Nebraska"), "531": ("Omaha", "Nebraska"),
    "702": ("Las Vegas", "Nevada"), "725": ("Las Vegas", "Nevada"), "775": ("Reno", "Nevada"),
    "603": ("Manchester", "New Hampshire"),
    "201": ("Jersey City", "New Jersey"), "551": ("Jersey City", "New Jersey"), "609": ("Trenton", "New Jersey"),
    "640": ("Trenton", "New Jersey"), "732": ("New Brunswick", "New Jersey"), "848": ("New Brunswick", "New Jersey"),
    "856": ("Camden", "New Jersey"), "862": ("Newark", "New Jersey"), "908": ("Elizabeth", "New Jersey"),
    "973": ("Newark", "New Jersey"),
    "505": ("Albuquerque", "New Mexico"), "575": ("Las Cruces", "New Mexico"),
    "212": ("New York", "New York"), "315": ("Syracuse", "New York"), "332": ("New York", "New York"),
    "347": ("New York", "New York"), "516": ("Hempstead", "New York"), "518": ("Albany", "New York"),
    "585": ("Rochester", "New York"), "607": ("Binghamton", "New York"), "631": ("Islip", "New York"),
    "646": ("New York", "New York"), "680": ("Syracuse", "New York"), "716": ("Buffalo", "New York"),
    "718": ("New York", "New York"), "838": ("Albany", "New York"), "845": ("Poughkeepsie", "New York"),
    "914": ("Yonkers", "New York"), "917": ("New York", "New York"), "929": ("New York", "New York"),
    "934": ("Islip", "New York"),
    "252": ("Greenville", "North Carolina"), "336": ("Greensboro", "North Carolina"),
    "704": ("Charlotte", "North Carolina"), "743": ("Greensboro", "North Carolina"),
    "828": ("Asheville", "North Carolina"), "910": ("Fayetteville", "North Carolina"),
    "919": ("Raleigh", "North Carolina"), "980": ("Charlotte", "North Carolina"),
    "984": ("Raleigh", "North Carolina"),
    "701": ("Fargo", "North Dakota"),
    "216": ("Cleveland", "Ohio"), "220": ("Newark", "Ohio"), "234": ("Akron", "Ohio"),
    "283": ("Cincinnati", "Ohio"), "326": ("Dayton", "Ohio"), "330": ("Akron", "Ohio"),
    "380": ("Columbus", "Ohio"), "419": ("Toledo", "Ohio"), "440": ("Parma", "Ohio"),
    "513": ("Cincinnati", "Ohio"), "567": ("Toledo", "Ohio"), "614": ("Columbus", "Ohio"),
    "740": ("Newark", "Ohio"), "937": ("Dayton", "Ohio"),
    "405": ("Oklahoma City", "Oklahoma"), "539": ("Tulsa", "Oklahoma"), "572": ("Oklahoma City", "Oklahoma"),
    "580": ("Lawton", "Oklahoma"), "918": ("Tulsa", "Oklahoma"),
    "458": ("Eugene", "Oregon"), "503": ("Portland", "Oregon"), "541": ("Eugene", "Oregon"),
    "971": ("Portland", "Oregon"),
    "215": ("Philadelphia", "Pennsylvania"), "223": ("Lancaster", "Pennsylvania"),
    "267": ("Philadelphia", "Pennsylvania"), "272": ("Scranton", "Pennsylvania"),
    "412": ("Pittsburgh", "Pennsylvania"), "445": ("Philadelphia", "Pennsylvania"),
    "484": ("Allentown", "Pennsylvania"), "570": ("Scranton", "Pennsylvania"),
    "610": ("Allentown", "Pennsylvania"), "717": ("Lancaster", "Pennsylvania"),
    "724": ("Pittsburgh", "Pennsylvania"), "814": ("Erie", "Pennsylvania"),
    "878": ("Pittsburgh", "Pennsylvania"),
    "401": ("Providence", "Rhode Island"),
    "803": ("Columbia", "South Carolina"), "839": ("Columbia", "South Carolina"),
    "843": ("Charleston", "South Carolina"), "854": ("Charleston", "South Carolina"),
    "864": ("Greenville", "South Carolina"),
    "605": ("Sioux Falls", "South Dakota"),
    "423": ("Chattanooga", "Tennessee"), "615": ("Nashville", "Tennessee"), "629": ("Nashville", "Tennessee"),
    "731": ("Jackson", "Tennessee"), "865": ("Knoxville", "Tennessee"), "901": ("Memphis", "Tennessee"),
    "931": ("Clarksville", "Tennessee"),
    "210": ("San Antonio", "Texas"), "214": ("Dallas", "Texas"), "254": ("Killeen", "Texas"),
    "281": ("Houston", "Texas"), "325": ("Abilene", "Texas"), "346": ("Houston", "Texas"),
    "361": ("Corpus Christi", "Texas"), "409": ("Beaumont", "Texas"), "430": ("Tyler", "Texas"),
    "432": ("Midland", "Texas"), "469": ("Dallas", "Texas"), "512": ("Austin", "Texas"),
    "682": ("Fort Worth", "Texas"), "713": ("Houston", "Texas"), "726": ("San Antonio", "Texas"),
    "737": ("Austin", "Texas"), "806": ("Lubbock", "Texas"), "817": ("Fort Worth", "Texas"),
    "830": ("New Braunfels", "Texas"), "832": ("Houston", "Texas"), "903": ("Tyler", "Texas"),
    "915": ("El Paso", "Texas"), "936": ("Conroe", "Texas"), "940": ("Denton", "Texas"),
    "945": ("Dallas", "Texas"), "956": ("Laredo", "Texas"), "972": ("Dallas", "Texas"),
    "979": ("College Station", "Texas"),
    "385": ("Salt Lake City", "Utah"), "435": ("St. George", "Utah"), "801": ("Salt Lake City", "Utah"),
    "802": ("Burlington", "Vermont"),
    "276": ("Bristol", "Virginia"), "434": ("Lynchburg", "Virginia"), "540": ("Roanoke", "Virginia"),
    "571": ("Arlington", "Virginia"), "703": ("Arlington", "Virginia"), "757": ("Virginia Beach", "Virginia"),
    "804": ("Richmond", "Virginia"),
    "206": ("Seattle", "Washington"), "253": ("Tacoma", "Washington"), "360": ("Vancouver", "Washington"),
    "425": ("Bellevue", "Washington"), "509": ("Spokane", "Washington"), "564": ("Vancouver", "Washington"),
    "304": ("Charleston", "West Virginia"), "681": ("Charleston", "West Virginia"),
    "262": ("Waukesha", "Wisconsin"), "274": ("Milwaukee", "Wisconsin"), "414": ("Milwaukee", "Wisconsin"),
    "534": ("Eau Claire", "Wisconsin"), "608": ("Madison", "Wisconsin"), "715": ("Eau Claire", "Wisconsin"),
    "920": ("Green Bay", "Wisconsin"),
    "307": ("Cheyenne", "Wyoming"),
}


def _digits10(phone):
    d = re.sub(r"\D", "", phone or "")
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d if len(d) == 10 else ""


def _area_from_phone(phone):
    """(city, full state) for the lead's phone area code, or None."""
    d = _digits10(phone)
    return _AREA_CODES.get(d[:3]) if d else None


def reverse_geocode(lat, lng):
    """(city, state) for a coordinate — Maps SERP items sometimes carry only
    lat/lng (no address_info) for small listings."""
    url = ("https://nominatim.openstreetmap.org/reverse?format=json&zoom=10"
           "&lat={}&lon={}".format(lat, lng))
    try:
        d = json.loads(_http_get(url, timeout=20))
        a = d.get("address") or {}
        city = a.get("city") or a.get("town") or a.get("village") or a.get("county")
        state = a.get("state")
        if city and state:
            return str(city), str(state)
    except Exception:
        pass
    return None


# longest-first greedy segmentation vocabulary for smashed-together domains
# ("proservrestoration" -> "pro serv restoration")
_DOMAIN_VOCAB = sorted(
    ["restoration", "restorations", "remediation", "reconstruction", "construction",
     "contracting", "contractors", "contractor", "waterproofing", "mitigation",
     "emergency", "cleaning", "cleanup", "plumbing", "roofing", "services",
     "service", "restore", "masters", "master", "damage", "water", "flood",
     "storm", "house", "home", "mold", "fire", "tech", "serv", "pro", "dry",
     "llc", "inc", "the", "and", "usa"],
    key=len, reverse=True)


def _domain_words(domain):
    """Best-effort human name from a domain label: 'proservrestoration.com'
    -> 'pro serv restoration'. Hyphens split for free; concatenated labels are
    segmented greedily against a small industry vocabulary; unknown runs of
    characters are kept as-is."""
    label = (domain or "").split(".")[0]
    label = re.sub(r"[^a-z0-9-]", "", label.lower())
    parts = []
    for chunk in label.split("-"):
        i, buf = 0, ""
        while i < len(chunk):
            hit = next((w for w in _DOMAIN_VOCAB if chunk.startswith(w, i)), None)
            if hit:
                if buf:
                    parts.append(buf)
                    buf = ""
                parts.append(hit)
                i += len(hit)
            else:
                buf += chunk[i]
                i += 1
        if buf:
            parts.append(buf)
    return " ".join(p for p in parts if p and p not in ("www",))


DEFAULT_RESTO_SERVICES = ["water damage restoration", "fire damage restoration",
                          "mold remediation"]

_CAT_SERVICES = [
    ("water damage", "water damage restoration", "water"),
    ("fire damage", "fire damage restoration", "fire"),
    ("mold", "mold remediation", "mold"),
    ("storm", "storm damage restoration", "storm"),
    ("biohazard", "biohazard cleanup", "biohazard"),
    ("crime victim", "biohazard cleanup", "biohazard"),
    ("building restoration", "damage restoration", "water"),
    ("waterproof", "waterproofing", "water"),
    ("plumb", "plumbing", "plumbing"),
    ("carpet clean", "carpet cleaning", "water"),
    ("general contractor", "general contracting", "reconstruction"),
    ("remodel", "remodeling", "reconstruction"),
    ("roof", "roofing", "carpentry"),
    ("deck", "deck building", "carpentry"),
    ("fence", "fence building", "carpentry"),
]


def _services_from_categories(cats, name_hint=""):
    """(services, vertical) from GBP categories. When the business NAME says
    restoration but the categories don't (miscategorized GBP — itself a
    finding), lead with the standard restoration set so the ranking checks
    track the searches that actually bring this business jobs."""
    services, vertical = [], None
    for cat in cats:
        cl = (cat or "").lower()
        for pat, svc, vert in _CAT_SERVICES:
            if pat in cl and svc not in services:
                services.append(svc)
                vertical = vertical or vert
    hint = (name_hint or "").lower()
    resto_hint = any(w in hint for w in ("restor", "water damage", "flood", "mitigat"))
    if resto_hint and vertical not in ("water", "fire", "mold", "storm"):
        services = DEFAULT_RESTO_SERVICES + [s for s in services if s not in DEFAULT_RESTO_SERVICES]
        vertical = "water"
    if not services:
        primary = (cats[0] or "").lower().replace(" service", "").strip() if cats else ""
        services = [primary] if primary else list(DEFAULT_RESTO_SERVICES)
        vertical = vertical or "water"
    return services[:5], vertical or "water"


def profile_from_listing(auth, domain, business_name, lead_phone, area_hint):
    """Tier-b profiler: build the profile from the business's own Google
    listing when the website can't be profiled. Identity bar is deliberately
    high — a candidate is accepted only when its listing links the audited
    domain, matches the lead's phone, or matches the searched name almost
    exactly (never profile a stranger: the Coastal Treetenders lesson,
    2026-07-26). area_hint = (city, state) from the phone's area code biases
    the Maps query toward the lead's real market — a US-wide name search for
    'Pro Serv Restoration' surfaces same-named companies in other states.

    Returns (prof, gbp_dict, dfs_cost); raises when no confident match."""
    cost = 0.0
    names = []
    if (business_name or "").strip():
        names.append(business_name.strip())
    dw = _domain_words(domain)
    if dw and len(dw) >= 6 and dw.lower() not in [n.lower() for n in names]:
        names.append(dw)
    if not names:
        raise RuntimeError("no business-name candidate (no form business name, no domain words)")
    want_dom = (domain or "").lower()
    want_dom = want_dom[4:] if want_dom.startswith("www.") else want_dom
    lead_digits = _digits10(lead_phone)

    queries = []
    for nm in names[:2]:
        if area_hint:
            queries.append("{} {} {}".format(nm, area_hint[0], area_hint[1])[:200])
        queries.append(nm[:200])
    best, best_score = None, 0.0
    for kw in queries:
        try:
            items, c, _ = _dfs(DFS_MAPS, [{"keyword": kw, "location_code": 2840,
                                           "language_code": "en", "device": "desktop"}], auth)
            cost += c
        except Exception as e:
            sys.stderr.write("  listing query '{}': {}\n".format(kw[:40], str(e)[:120]))
            continue
        for it in items:
            if not isinstance(it, dict) or not it.get("title"):
                continue
            it_dom = str(it.get("domain") or "").lower()
            it_dom = it_dom[4:] if it_dom.startswith("www.") else it_dom
            if want_dom and it_dom == want_dom:
                s = 1.0
            elif lead_digits and _digits10(it.get("phone")) == lead_digits:
                s = 1.0
            else:
                s = max(_name_match(n, it.get("title")) for n in names)
                if it_dom and want_dom and it_dom != want_dom:
                    s -= 0.35
                region = ((it.get("address_info") or {}).get("region") or "")
                if area_hint and region and region.lower() == area_hint[1].lower():
                    s += 0.05
            if s > best_score:
                best, best_score = it, s
        if best_score >= 0.9:
            break
    if not best or best_score < 0.75:
        raise RuntimeError("no confident Google-listing match for {!r} (best score {:.2f})".format(
            names[0], best_score))

    ainfo = best.get("address_info") or {}
    city, state = ainfo.get("city"), ainfo.get("region")
    if not (city and state):
        m = re.search(r",\s*([A-Za-z .'-]+),\s*([A-Z]{2})\b", best.get("address") or "")
        if m:
            city, state = m.group(1).strip(), m.group(2)
    if not (city and state) and best.get("latitude") and best.get("longitude"):
        got = reverse_geocode(best["latitude"], best["longitude"])
        if got:
            city, state = got
    if not (city and state) and area_hint:
        city, state = area_hint
    if not (city and state):
        raise RuntimeError("listing matched but no city/state could be determined")
    if len(str(state)) == 2:
        state = _US_STATES.get(str(state).upper(), str(state))

    cats = [best.get("category") or ""] + list(best.get("additional_categories") or [])
    services, vertical = _services_from_categories(
        cats, "{} {}".format(best.get("title") or "", domain or ""))
    rd = best.get("rating") or {}
    gbp = {"found": True, "title": best.get("title"),
           "place_id": best.get("place_id"),
           "cid": str(best.get("cid")) if best.get("cid") is not None else None,
           "rating": rd.get("value"), "reviews": rd.get("votes_count"),
           "address": best.get("address")}
    prof = {"business_name": best.get("title"), "phone": best.get("phone"),
            "vertical": vertical, "services": services,
            "cities": [{"city": str(city), "state": str(state)}],
            "gbp_query": best.get("title")}
    return prof, gbp, cost


def profile_from_form(domain, name, email, phone, business_name=None):
    """Tier-c profiler (last resort): nothing but the form fields. Business
    name from the form / email domain / site domain words; city from the
    phone's area code; default restoration service set."""
    bn = (business_name or "").strip()
    if not bn:
        edom = (email or "").rsplit("@", 1)[-1].strip().lower() if "@" in (email or "") else ""
        src = edom if (edom and edom not in _FREE_MAIL) else (domain or edom)
        words = _domain_words(src)
        if words:
            bn = " ".join(w.upper() if w in ("llc", "usa", "inc") else w.capitalize()
                          for w in words.split())
    if not bn:
        raise RuntimeError("no business name derivable from the form data")
    area = _area_from_phone(phone)
    if not area:
        raise RuntimeError("no service city derivable (unknown phone area code: {})".format(
            phone or "no phone"))
    city, state = area
    return {"business_name": bn, "phone": phone or None, "vertical": "water",
            "services": list(DEFAULT_RESTO_SERVICES),
            "cities": [{"city": city, "state": state}],
            "gbp_query": "{} {}".format(bn, city)}


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
    # REVENUE FLOOR (Santino 2026-07-28, raised same day): click-math on a
    # small market's 9 tracked keywords produced ranges like $500-$1,100/mo,
    # below our own $997 fee, and it undersells reality (these companies also
    # do mold, rebuilds, packouts, contents; single fire losses run to six
    # figures). Restoration floor = one full water-loss PROJECT per month
    # (mitigation + rebuild, insured losses routinely deep five figures):
    # $14,500-$19,000, Santino's number. Non-restoration trades keep an
    # honest one-job floor. The floor is an explicitly STATED assumption,
    # never silent inflation: methodology text always discloses it.
    if vertical in NON_RESTORATION_VERTICALS:
        floor_low, floor_high = ticket, ticket * 2
        floor_note = ("winning just ONE additional {} job per month at an average ticket "
                      "of ${:,}").format(vertical, ticket)
        # A deck builder has no insured losses, so the six-figure fire-loss
        # caveat below would be nonsense on his report.
        tail = " Real tickets vary widely with job size and materials."
    else:
        floor_low = max(ticket, RESTORATION_FLOOR[0])
        floor_high = max(ticket * 2, RESTORATION_FLOOR[1])
        floor_note = ("winning roughly one full {} loss per month, mitigation plus rebuild "
                      "and contents, which for insured losses routinely runs well into five "
                      "figures").format(vertical)
        tail = (" Real tickets vary widely, and a single large fire loss can exceed $100,000.")
    if tracked == 0 or mid < 200:
        return {"low": floor_low, "high": floor_high, "ticket": ticket,
                "missed_clicks": int(round(missed_clicks)),
                "methodology": ("Tracked search volume in this market is too thin for click-by-click math, "
                                "so this range shows the most conservative yardstick instead: the value of "
                                + floor_note + "." + tail)}
    low = int(round(mid * 0.6, -2))
    high = int(round(mid * 1.4, -2))
    methodology = ("Estimate = monthly Google search volume for the {} tracked keywords x the standard "
                   "click-through-rate curve for Google positions (a top-3 listing captures roughly 18% "
                   "of searches; page 2 captures almost none) x a 10% booked-job rate x an average {} "
                   "job ticket of ${:,}. Shown as a range because real close rates and tickets vary."
                   ).format(tracked, vertical, ticket)
    if low < floor_low:
        low, high = floor_low, max(high, floor_high)
        methodology += (" The keyword click-math understates markets like this one, where much of the "
                        "demand never types the tracked phrases, so the shown range floors at the value "
                        "of " + floor_note + ".")
    return {"low": low, "high": high, "ticket": ticket,
            "missed_clicks": int(round(missed_clicks)),
            "methodology": methodology}


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
7. The audit data may include "website_status". When its "status" is "no_website" or
   "unreadable", the website itself is the single most important finding: lead the verdict
   and summary with it in plain language ("no_website" = there is no real working website at
   their address, only a parked or placeholder page, or nothing answering at all;
   "unreadable" = the site loads for a person but the automated readers Google and AI
   assistants use get nothing from it). Make game_plan step 1 about launching or fixing a
   website those tools can read, and let the grade reflect it: no better than D when status
   is "no_website" and no better than C when "unreadable", lower when rankings and map
   visibility are also weak. Do not describe HOW this audit was compiled (the report template
   explains that). When status is "ok", never mention website readability at all.

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


def _website_alert_section(domain, site_status, site_note=None):
    """Prominent first section for degraded audits: the lead's website is
    unreachable or unreadable by the automated tools Google and AI use. Plain
    language, sales-honest, no em dashes (house rule)."""
    dom = _esc(domain) if domain else "your business"
    note = (site_note or "").lower()
    if site_status == "no_website":
        h2 = "There is no working website for Google or AI to read"
        if not domain:
            p1 = ("No website was on file for your business, so the automated readers "
                  "Google and AI assistants rely on have nothing to read at all.")
        elif "resolve" in note or "reachable" in note or "connections" in note:
            p1 = ("We checked {} the same way Google and the AI assistants do, with "
                  "automated readers. The address did not answer at all: it does not "
                  "load a website for anyone, human or robot.").format(dom)
        else:
            p1 = ("We checked {} the same way Google and the AI assistants do, with "
                  "automated readers. They did not find a real website there: the address "
                  "serves a parked or placeholder page with no services, no cities, and no "
                  "way to tell what your business does.").format(dom)
    else:
        h2 = "Your website is unreadable to the tools Google and AI use"
        p1 = ("{} loads for a human visitor, but the automated readers Google and AI "
              "assistants rely on came back with nothing they could use: no services and "
              "no cities. A site those tools cannot read cannot rank for the searches "
              "that bring jobs, and AI assistants cannot quote or recommend it.").format(dom)
    p2 = ("This is the number one finding in this report. Every result below was measured "
          "from your Google Business Profile and live Google results, which do not depend "
          "on your website.")
    return ('<section><div class="kicker">Your Website</div>\n<h2>{}</h2>\n'
            '<p>{}</p>\n<p>{}</p></section>'.format(_esc(h2), p1, p2))


def build_html(audit_id, prof, domain, copy, rankings, geogrid, ai_results, mappack, money,
               site_status="ok", site_note=None, skipped=None):
    tpl = TEMPLATE.read_text()
    S = []

    # Degraded-website alert leads the report — it is the #1 finding
    if site_status in ("no_website", "unreadable"):
        S.append(_website_alert_section(domain, site_status, site_note))

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

    # Checks that could not run report themselves as such instead of vanishing
    if skipped:
        S.append('<section><div class="kicker">Coverage</div>'
                 '<h2>Checks we could not run this time</h2>'
                 '<p>Some automated checks could not be completed for this audit: {}. '
                 'They are left out above rather than guessed at.</p></section>'.format(
                     _esc(", ".join(skipped))))

    grade = (copy.get("grade") or "C").upper()[:1]
    gclass = "g-good" if grade in ("A", "B") else ("g-warn" if grade == "C" else "g-bad")
    today = dt.datetime.now(dt.timezone.utc).strftime("%B %d, %Y")
    out = (tpl.replace("{{TITLE}}", _esc("{} — AI Visibility Audit".format(prof["business_name"])))
              .replace("{{BUSINESS_NAME}}", _esc(prof["business_name"]))
              .replace("{{DOMAIN}}", _esc(domain or "no website on file"))
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
    MAP PACK LEADS (Santino 2026-07-28): the pack is where local jobs get
    decided and it is what we sell; organic is the supporting bullet.
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
    # 1) Map-pack standing first, whenever we have pack data
    ranked = sorted([(p.get("client_rank"), p.get("city")) for p in (mappack or [])
                     if p.get("client_rank")])
    if ranked and ranked[0][0] > 3:
        best, city = ranked[0]
        held = (", and " + " and ".join(leaders[:2]) + " hold them") if leaders else ""
        bullets.append(("Map pack:",
                        "You sit #{} in the {} map pack. The 3 spots above the fold get "
                        "the calls{}.".format(best, city, held)))
    elif not ranked and mappack and leaders and len(bullets) < 2:
        bullets.append(("Map pack gap:",
                        " and ".join(leaders[:2]) + " hold the top map spots in your "
                        "cities. You're not in the pack."))
    # 2) Organic gap second
    positions = [r.get("position") for r in (rankings or []) if r.get("position")]
    if len(bullets) < 2:
        if rankings and not positions:
            lead_txt = " and ".join(leaders[:2]) if leaders else "Your competitors"
            bullets.append(("Ranking gap:", lead_txt + " hold the top spots. "
                            "You're not in the top 20 for any search we tracked."))
        elif positions and min(positions) > 3:
            bullets.append(("Ranking gap:",
                            "Your best Google position is #{}. Customers rarely scroll past "
                            "the top 3.".format(min(positions))))
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


def render_invisibility_card(business_name, city=None):
    """Failure-path media (Santino 2026-08-16): when an audit FAILS the nurture
    SMS still merges audit_teaser_image_url, so the failed branch needs valid,
    personalized media. This card sells the finding itself: a mock Google
    results frame ("water damage restoration near me" in a search bar), three
    greyed redacted competitor rows, then the lead's business struck through
    and marked "Not found in search results", plus a bold verdict. Same brand
    look as make_teaser_image (petrol blue, Poppins, white card, yellow name
    highlight, Restoration AI footer). Pure PIL, deterministic, bundled fonts:
    renders anywhere the API runs, with ONLY a business name (city optional).
    No em dashes anywhere on the card."""
    from PIL import Image, ImageDraw, ImageFont
    RED = (220, 38, 38)
    RED_DK = (185, 28, 28)
    S = 2
    W, H = 1080 * S, 1350 * S
    img = Image.new("RGB", (W, H), (241, 245, 249))
    d = ImageDraw.Draw(img)

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
        f = ImageFont.truetype(FB, size * S)
        x = LX
        for ch in text:
            dc.text((x, y), ch, font=f, fill=BLUE)
            x += dc.textlength(ch, font=f) + 3 * S
        return y + 34 * S

    LX = 52 * S
    RX = CARD_W - 52 * S
    CW = RX - LX

    # ---- header: report-style title + THEIR name on the yellow highlight ----
    name = _strip_dashes((business_name or "Your Business").strip())
    title_w = CW - 170 * S              # clear the badge column top right
    f_title = fit("ONLINE VISIBILITY CHECK", FB, 46, 30, title_w)
    dc.text((LX, 54 * S), "ONLINE VISIBILITY CHECK", font=f_title, fill=INK)
    f_name = fit(name, FB, 36, 25, title_w - 32 * S)
    nmw = dc.textlength(name, font=f_name)
    dc.rounded_rectangle([LX - 6 * S, 128 * S, LX + nmw + 22 * S, 186 * S],
                         radius=10 * S, fill=(254, 246, 189))
    dc.text((LX + 8 * S, 135 * S), name, font=f_name, fill=INK)
    dc.line([LX, 214 * S, RX, 214 * S], fill=(226, 232, 240), width=S)

    # ---- badge top right (the teaser's grade badge slot): a red "?" ----
    bs = 136 * S
    bx0, by0 = RX - bs, 44 * S
    dc.rounded_rectangle([bx0, by0, bx0 + bs, by0 + bs], radius=22 * S,
                         fill=(254, 242, 242), outline=RED, width=4 * S)
    f_q = ImageFont.truetype(FB, 84 * S)
    qw = dc.textlength("?", font=f_q)
    dc.text((bx0 + (bs - qw) / 2, by0 + 10 * S), "?", font=f_q, fill=RED)
    f_lab = ImageFont.truetype(FS, 13 * S)
    lab = "NOT FOUND"
    lw = dc.textlength(lab, font=f_lab)
    dc.text((bx0 + (bs - lw) / 2, by0 + bs + 13 * S), lab, font=f_lab, fill=MUTED)

    # ---- verdict block is anchored to the card bottom; measure it first ----
    head = "We couldn't find your business online"
    f_vh = ImageFont.truetype(FB, 36 * S)
    vh_lines = wrap(head, f_vh, CW)[:2]
    where = "in {} ".format(city.strip()) if (city or "").strip() else ""
    sub = ("When homeowners {}search for water damage help, "
           "your competitors get the call.").format(where)
    f_vs = ImageFont.truetype(FR, 23 * S)
    vs_lines = wrap(_strip_dashes(sub), f_vs, CW)[:3]
    vh = 34 * S + len(vh_lines) * 48 * S + 10 * S + len(vs_lines) * 32 * S
    verdict_top = CARD_H - 40 * S - vh

    # ---- the mock search-results frame fills everything in between ----
    y = kicker(214 * S + 38 * S, "WHAT HOMEOWNERS SEE")
    fy0, fy1 = y, verdict_top - 38 * S
    dc.rounded_rectangle([LX, fy0, RX, fy1], radius=18 * S,
                         fill=(248, 250, 252), outline=(226, 232, 240), width=2 * S)
    pad = 28 * S
    ix0, ix1 = LX + pad, RX - pad

    # search bar: pill, magnifier glass, the query
    ph = 56 * S
    py = fy0 + pad
    dc.rounded_rectangle([ix0, py, ix1, py + ph], radius=ph // 2,
                         fill=(255, 255, 255), outline=(203, 213, 225), width=2 * S)
    mcx, mcy, mr = ix0 + 30 * S, py + ph // 2 - 3 * S, 10 * S
    dc.ellipse([mcx - mr, mcy - mr, mcx + mr, mcy + mr],
               outline=(100, 116, 139), width=3 * S)
    dc.line([mcx + mr - 2 * S, mcy + mr - 2 * S, mcx + mr + 7 * S, mcy + mr + 7 * S],
            fill=(100, 116, 139), width=3 * S)
    query = "water damage restoration near me"
    f_qr = fit(query, FM, 25, 18, ix1 - (ix0 + 58 * S) - 20 * S)
    dc.text((ix0 + 58 * S, py + (ph - f_qr.size) / 2 - 2 * S), query, font=f_qr, fill=INK)
    y = py + ph
    if (city or "").strip():
        f_cy = ImageFont.truetype(FR, 20 * S)
        dc.text((ix0 + 6 * S, y + 12 * S), "Showing results near " + city.strip(),
                font=f_cy, fill=MUTED)
        y += 42 * S

    # the lead's row: tinted, outlined, name struck through, "Not found" label
    hl_h = 106 * S
    hy1 = fy1 - pad
    hy0 = hy1 - hl_h
    dc.rounded_rectangle([ix0, hy0, ix1, hy1], radius=14 * S,
                         fill=(254, 242, 242), outline=RED, width=3 * S)
    f_x = ImageFont.truetype(FB, 34 * S)
    dc.text((ix0 + 26 * S, hy0 + 18 * S), "×", font=f_x, fill=RED)
    nx = ix0 + 78 * S
    f_hn = fit(name, FS, 28, 18, ix1 - nx - 26 * S)
    hnw = dc.textlength(name, font=f_hn)
    nty = hy0 + 20 * S
    dc.text((nx, nty), name, font=f_hn, fill=INK)
    dc.line([nx - 4 * S, nty + f_hn.size * 0.58, nx + hnw + 6 * S, nty + f_hn.size * 0.58],
            fill=RED, width=4 * S)
    f_nf = ImageFont.truetype(FS, 21 * S)
    dc.text((nx, hy0 + 60 * S), "Not found in search results", font=f_nf, fill=RED_DK)

    # 3 greyed competitor rows, spread evenly between search bar and lead row
    rows_top = y + 24 * S
    rows_bot = hy0 - 20 * S
    row_h = 74 * S
    n_rows = 3
    gap = (rows_bot - rows_top - n_rows * row_h) // max(n_rows - 1, 1)
    gap = min(max(gap, 10 * S), 44 * S)   # capped, block centered in the frame
    block_h = n_rows * row_h + (n_rows - 1) * gap
    ry = rows_top + max(0, (rows_bot - rows_top - block_h) // 2)
    for i in range(n_rows):
        av_r = 22 * S
        acx, acy = ix0 + 8 * S + av_r, ry + row_h // 2
        dc.ellipse([acx - av_r, acy - av_r, acx + av_r, acy + av_r],
                   fill=(226, 232, 240))
        tx = ix0 + 8 * S + 2 * av_r + 22 * S
        tw = int((ix1 - tx) * (0.52 - 0.06 * i))
        dc.rounded_rectangle([tx, ry + 8 * S, tx + tw, ry + 26 * S],
                             radius=9 * S, fill=(148, 163, 184))
        lw1 = int((ix1 - tx) * 0.86)
        dc.rounded_rectangle([tx, ry + 36 * S, tx + lw1, ry + 48 * S],
                             radius=6 * S, fill=(222, 228, 236))
        lw2 = int((ix1 - tx) * (0.64 + 0.05 * i))
        dc.rounded_rectangle([tx, ry + 56 * S, tx + lw2, ry + 68 * S],
                             radius=6 * S, fill=(226, 232, 240))
        ry += row_h + gap

    # ---- verdict ----
    y = kicker(verdict_top, "THE VERDICT")
    for line in vh_lines:
        dc.text((LX, y), line, font=f_vh, fill=INK)
        y += 48 * S
    y += 10 * S
    for line in vs_lines:
        dc.text((LX, y), line, font=f_vs, fill=MUTED)
        y += 32 * S

    # paste card through rounded mask, footer on the bg (same as the teaser)
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
            "visibility_grade": None,   # alias: Santino's SMS templates use this key
            # complete | degraded_no_website | degraded_unreadable_website | failed
            # — the GHL workflow branches its messaging on this field, so it is
            # written on EVERY outcome (the failure path writes 'failed').
            "audit_status": None}
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
                   report_url, teaser_url, log, cities=None, contact_id=None,
                   audit_status=None):
    """Find-or-create the lead's GHL contact; write the audit URLs + cities +
    grade to custom fields + a note. cities is a human phrase ("Memphis and
    Cincinnati") for SMS merge-field personalization. Best-effort: any failure
    logs and moves on (the report itself is already safe on R2).

    contact_id: when the caller already knows the GHL contact (staff-booked
    appointment webhook), write to it directly — the email/phone search below
    finds nothing for contacts with no phone and can hit the wrong duplicate."""
    for q in ([] if contact_id else [email, phone]):
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
    if audit_status:
        payload_fields.append({"id": fields["audit_status"], "field_value": str(audit_status)})
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
             body={"body": "AUDIT READY (grade {g}, status {s}) for {d}\nReport: {r}\nTeaser image: {t}".format(
                 g=grade, s=audit_status or "complete", d=domain or "no website",
                 r=report_url, t=teaser_url)})
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

def _run_audit(website, name, email, phone, audit_id=None, email_mode="all", progress=None,
               business_name=None, place_id=None, cid=None, sales_mode=False,
               ghl_contact_id=None):
    """Full pipeline. email_mode: 'all' | 'internal' (notify only) | 'none'.
    business_name/place_id/cid: optional GBP identity already confirmed by the
    prospect in the stepper — used to pin the listing instead of re-guessing.
    sales_mode: funnel-triggered pre-meeting audit — generates the teaser image
    and delivers report/teaser URLs to the lead's GHL contact (custom fields +
    note) instead of emailing the lead. Returns {report_url, grade, ...}.
    ghl_contact_id: deliver to this exact contact instead of searching by
    email/phone (staff-booked appointment webhook already knows it).

    GRACEFUL DEGRADATION (2026-08-16): an audit must ALWAYS complete. Site
    problems never crash the run; profiling falls back site text -> Google
    listing -> form data, the report leads with the website problem, and
    audit_status records the outcome: 'complete', 'degraded_no_website'
    (dead/parked/no site), or 'degraded_unreadable_website' (site up but the
    automated readers extract nothing)."""
    def log(msg):
        print("  [{}] {}".format(dt.datetime.now().strftime("%H:%M:%S"), msg))
        if progress:
            try:
                progress(msg)
            except Exception:
                pass

    audit_id = audit_id or uuid.uuid4().hex[:12]
    domain = _norm_domain(website)
    site_status, site_note = "ok", None   # ok | unreadable | no_website
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain):
        domain = ""
        site_status = "no_website"
        site_note = "no usable website address was submitted"

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

    if domain and not _resolves(domain) and not _resolves("www." + domain):
        # Repair a mangled "www" label BEFORE falling back to the email domain.
        # Monique Curchy typed ww.rapidreliefrestoration.net (2026-08-05) — one
        # missing w. The old order tried only `ww.…` and `www.ww.…`, both dead,
        # then reached for the email domain, which was gmail.com and therefore
        # unusable, so a lead whose site was UP and returning 200 got tagged
        # "website down" and received no report at all. Strip a first label that
        # is just a run of w's (ww, wwww, w) and retry the real domain.
        parts = domain.split(".")
        if len(parts) > 2 and re.match(r"^w{1,4}$", parts[0]):
            repaired = ".".join(parts[1:])
            if _resolves(repaired) or _resolves("www." + repaired):
                log("domain {} looks like a mistyped www — using {} instead".format(domain, repaired))
                domain = repaired

    if domain and not _resolves(domain) and not _resolves("www." + domain):
        alt = (email or "").rsplit("@", 1)[-1].strip().lower() if "@" in (email or "") else ""
        if alt and alt not in _FREE_MAIL and alt != domain and _resolves(alt):
            log("domain {} does not resolve — using email domain {} instead".format(domain, alt))
            domain = alt
        else:
            # DNS-level dead (NXDOMAIN on domain, www + no email-domain
            # fallback) — the strongest "website down" signal there is
            # (Robert Gibson's content-restoration.com, 2026-07-30). No longer
            # fatal: the audit continues from the Google listing / form data.
            site_status = "no_website"
            site_note = ("the submitted website {} does not resolve (dead domain "
                         "or a typo in the form)".format(domain))
            log("site: " + site_note)
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

    log("audit {} for {} started".format(audit_id, domain or "(no website)"))

    # 1. site -> profile (tier a), with graceful degradation: site problems
    # classify the run instead of crashing it.
    prof, u, gbp_seed = None, None, None
    profile_source = "site"
    pages = {}
    if domain and site_status == "ok":
        try:
            pages = fetch_site(domain, start_url)
        except SiteDownError as e:
            site_status, site_note = "no_website", str(e)
            log("site: " + site_note)
        except Exception as e:
            # WAF-blocked, SSL breakage, timeouts — the site may be fine for
            # humans but our readers (and Google's) get nothing.
            site_status, site_note = "unreadable", str(e)[:200]
            log("site fetch failed ({}) — continuing without site text".format(str(e)[:120]))
    if pages:
        try:
            prof, u = profile_site(client, start_url or domain, pages)
        except ProfileIncompleteError:
            # The raw server HTML held no services or no cities. Two known
            # causes, each with its own cheap recovery, both failure-path only.
            # Recovery 1 — franchise root: the lead submitted the corporate
            # domain but the funnel knows their location ("Restoration 1 of
            # Hartland"), whose own page is /hartland on the same domain.
            if not start_url:
                for cand in franchise_start_urls(domain, business_name):
                    try:
                        cand_pages = fetch_site(domain, cand)
                        prof, u = profile_site(client, cand, cand_pages)
                    except Exception:
                        continue
                    start_url, pages = cand, cand_pages
                    log("franchise-root recovery: profiled {} instead of the corporate root".format(cand))
                    break
            # Recovery 2 — client-rendered site: a clean 200 whose every word
            # of business content is painted by JavaScript (Jose Mendoza's
            # eds-construction-services.com, 2026-08-04). Render in a browser
            # and profile that (~$0.0015). The render itself can also fail —
            # "content_parsing returned no items" killed Virgil Santa's audit
            # on 2026-08-14 because this fetch was OUTSIDE the try.
            if prof is None:
                log("profile came back empty from the raw HTML — retrying with a "
                    "JavaScript-rendered crawl (client-side-rendered site?)")
                try:
                    pages = fetch_site(domain, start_url, force_js=True)
                    prof, u = profile_site(client, start_url or domain, pages)
                    log("JS-rendered retry succeeded ({} chars)".format(len(pages.get("homepage") or "")))
                except ProfileIncompleteError:
                    # A clean 200 that names no service and no city after a
                    # full JS render is a PARKED/PLACEHOLDER page (Monique
                    # Curchy's rapidreliefrestoration.net, 2026-08-06): the
                    # honest "no real website yet" case.
                    site_status = "no_website"
                    site_note = ("{} resolves and returns 200 but is a placeholder/parked "
                                 "page (no services, no cities after a JavaScript render)"
                                 ).format(domain)
                    log("site: " + site_note)
                except SiteDownError as e:
                    site_status, site_note = "no_website", str(e)
                    log("site: " + site_note)
                except Exception as e:
                    site_status, site_note = "unreadable", str(e)[:200]
                    log("JS-rendered retry failed ({}) — site is unreadable to "
                        "automated readers".format(str(e)[:120]))
        except Exception as e:
            # Non-site failure (e.g. a model hiccup) — fall through to the
            # listing profiler rather than dying; site_status stays as-is.
            log("site profiling failed ({}) — falling back to the Google "
                "listing".format(str(e)[:120]))
    # Tier b — the business's own Google listing (name+area biased, identity
    # verified by domain/phone/near-exact name).
    if prof is None:
        try:
            prof, gbp_seed, c = profile_from_listing(
                auth, domain, business_name, phone, _area_from_phone(phone))
            costs["dataforseo"] += c
            profile_source = "gbp_listing"
            log("profiled from the Google listing: {} | {} | {}".format(
                prof["business_name"], prof["services"][0],
                ["{}, {}".format(c0["city"], c0["state"]) for c0 in prof["cities"]]))
        except Exception as e:
            errors.append("profile_listing: " + str(e)[:150])
            log("listing profiling failed: " + str(e)[:150])
    # Tier c — form data alone (business name from form/email/domain words,
    # city from the phone's area code, default restoration services).
    if prof is None:
        try:
            prof = profile_from_form(domain, name, email, phone, business_name)
            profile_source = "form"
            log("profiled from form data alone: {} in {}, {}".format(
                prof["business_name"], prof["cities"][0]["city"], prof["cities"][0]["state"]))
        except Exception as e:
            errors.append("profile_form: " + str(e)[:120])
    if prof is None:
        raise RuntimeError(
            "could not profile the business from its site, its Google listing, or the "
            "form data" + (" (site: {})".format(site_note) if site_note else ""))
    if u:
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
    if not gbp.get("found") and gbp_seed:
        # tier-b profiling already identity-matched the listing — reuse it
        gbp = gbp_seed
        log("gbp: seeded from the tier-b listing match: {}".format(gbp.get("title")))
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
    if domain:
        try:
            rankings, c = run_rankings(auth, domain, service, cities)
            costs["dataforseo"] += c
            log("rankings: {} queries, {} ranked".format(
                len(rankings), sum(1 for r in rankings if r["position"])))
        except Exception as e:
            errors.append("rankings: " + str(e)[:150])
    else:
        errors.append("rankings skipped: no website to rank")

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
    audit_status = {"ok": "complete",
                    "unreadable": "degraded_unreadable_website",
                    "no_website": "degraded_no_website"}[site_status]
    skipped = []
    if not rankings:
        skipped.append("Google search ranking checks")
    if not [g for g in geogrid if g.get("image_url")]:
        skipped.append("the Google Maps heat map")
    if not [r for r in ai_results if r.get("engine") == "chatgpt"]:
        skipped.append("AI assistant answer checks")
    if not ([p for p in mappack if p.get("competitors")] and gbp.get("found")):
        skipped.append("the review comparison")
    if not money:
        skipped.append("the revenue estimate")
    data = {"business": {k: prof.get(k) for k in
                         ("business_name", "phone", "vertical", "services", "cities")},
            "domain": domain or None, "gbp": gbp, "rankings": rankings, "geogrid": geogrid,
            "ai_search": ai_results, "map_pack": mappack, "revenue_estimate": money,
            "search_volumes": vols}
    if site_status != "ok":
        data["website_status"] = {"status": site_status, "note": site_note,
                                  "profiled_from": profile_source}
    copy, u = generate_report_copy(client, data)
    usages.append(u)
    html_out = build_html(audit_id, prof, domain, copy, rankings, geogrid, ai_results,
                          mappack, money, site_status=site_status, site_note=site_note,
                          skipped=skipped)

    # 8. host on R2
    report_key = "{}/{}/report.html".format(PREFIX, audit_id)
    if not r2_put(BUCKET, report_key, html_out.encode(), "text/html; charset=utf-8"):
        raise RuntimeError("R2 upload of report failed")
    report_url = "{}/{}".format(PUBLIC_BASE, report_key)
    costs["claude"] = _claude_cost(usages)
    r2_put(PRIVATE_BUCKET, "{}/{}/audit.json".format(PREFIX, audit_id),
           json.dumps({"audit_id": audit_id, "requested_by": {"name": name, "email": email, "phone": phone},
                       "data": data, "copy": copy, "costs": costs, "errors": errors,
                       "audit_status": audit_status, "profile_source": profile_source,
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
                           cities=cities_phrase, contact_id=ghl_contact_id,
                           audit_status=audit_status)
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
Business: {b}<br>Grade: {g}<br>Status: {st}<br>Report: <a href="{u}">{u}</a><br>
Costs: DFS ${dc:.2f} + Claude ${cc:.2f}<br>Errors: {err}</div>""".format(
            n=_esc(name), e=_esc(email), p=_esc(phone), d=_esc(domain or "(no website)"),
            b=_esc(prof["business_name"]), g=_esc(copy.get("grade")), u=report_url,
            st=_esc(audit_status),
            dc=costs["dataforseo"], cc=costs["claude"], err=_esc("; ".join(errors) or "none"))
        send_email(NOTIFY_EMAIL, "[Rank AI lead] {} — audit {}".format(domain, copy.get("grade")), notif)

    # 10. lead log
    try:
        append_lead_jsonl({"audit_id": audit_id, "created_at": _now_iso(), "name": name,
                           "email": email, "phone": phone, "domain": domain,
                           "business_name": prof["business_name"], "grade": copy.get("grade"),
                           "report_url": report_url, "audit_status": audit_status,
                           "profile_source": profile_source})
    except Exception as e:
        errors.append("lead_log: " + str(e)[:120])

    return {"audit_id": audit_id, "report_url": report_url, "grade": copy.get("grade"),
            "teaser_url": teaser_url,
            "business_name": prof["business_name"], "domain": domain,
            "audit_status": audit_status, "profile_source": profile_source,
            "costs": costs, "errors": errors}


def run_audit(website, name, email, phone, audit_id=None, email_mode="all", progress=None,
              business_name=None, place_id=None, cid=None, sales_mode=False,
              ghl_contact_id=None):
    """Public entry point: _run_audit plus the guarantee that EVERY attempt
    lands in leads.jsonl. Virgil Santa's crashed audit (2026-08-14) left no
    trace in the lead log because the log write sat at the end of the happy
    path; now a failure appends its own row (audit_status='failed') before
    re-raising so the caller's failure handling still runs."""
    audit_id = audit_id or uuid.uuid4().hex[:12]
    try:
        return _run_audit(website, name, email, phone, audit_id=audit_id,
                          email_mode=email_mode, progress=progress,
                          business_name=business_name, place_id=place_id, cid=cid,
                          sales_mode=sales_mode, ghl_contact_id=ghl_contact_id)
    except Exception as e:
        try:
            append_lead_jsonl({"audit_id": audit_id, "created_at": _now_iso(),
                               "name": name, "email": email, "phone": phone,
                               "domain": _norm_domain(website),
                               "business_name": business_name, "grade": None,
                               "report_url": None, "audit_status": "failed",
                               "error": str(e)[:300]})
        except Exception:
            pass
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Rank AI free-audit pipeline")
    ap.add_argument("--url", default="", help="lead's website (may be omitted: no-website audit)")
    ap.add_argument("--name", default="")
    ap.add_argument("--email", required=True)
    ap.add_argument("--phone", default="")
    ap.add_argument("--audit-id")
    ap.add_argument("--email-mode", choices=["all", "internal", "none"], default="all")
    ap.add_argument("--business-name", default="")
    ap.add_argument("--ghl-contact-id", default="")
    ap.add_argument("--sales-mode", action="store_true",
                    help="funnel mode: teaser image + GHL field delivery, no lead email")
    args = ap.parse_args()
    t0 = time.time()
    res = run_audit(args.url, args.name, args.email, args.phone,
                    audit_id=args.audit_id, email_mode=args.email_mode,
                    business_name=args.business_name or None,
                    sales_mode=args.sales_mode,
                    ghl_contact_id=args.ghl_contact_id or None)
    print("\n== DONE in {:.0f}s ==".format(time.time() - t0))
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
