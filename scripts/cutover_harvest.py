#!/usr/bin/env python3
"""cutover_harvest.py — 301-map an old client site BEFORE we cut its domain over.

The problem this kills: when a client's existing domain flips to our new build,
every URL on their old site dies. TRG and Crew got HAND-BUILT redirect maps
(sites/restoration-groups/public/_redirects, 940 pages); nobody else does, and
whatever rankings/backlinks the old site earned evaporate at cutover. This
script makes the map automatic, so having redirects staged is the default
state and cutover is always safe.

Commands:
    harvest --slug X [--domain D]
        Inventory the OLD site while it is still alive. Sources (all
        fail-soft): sitemap.xml / sitemap index (a few thousand URLs max),
        else a shallow same-host crawl from the homepage (depth 3, ~500),
        plus DataForSEO Backlinks "domain_pages_summary" (ONE paid call —
        ranks which URLs actually have inbound links) and GSC top pages when
        the agency token can see the old property. Writes
        clients/{slug}/cutover/url-inventory.json. Idempotent — re-runs
        refresh it.

    map --slug X [--apply] [--no-commit]
        Enumerate the NEW site's real routes from sites/{slug}/src (services,
        service-areas hubs + nested city-service pages, blog, fixed pages,
        legal, dedicated .astro pages; lp/ is noindex and excluded), match
        old paths to them (exact/slug heuristics first, then ONE
        claude-sonnet-5 call for the remainder), and with --apply MERGE the
        result into sites/{slug}/public/_redirects — every existing rule is
        preserved and wins over ours; new rules append under a dated comment
        block. Never maps to a route that doesn't exist; backlinked/GSC URLs
        get a specific target whenever one is plausible; the rest go to "/".
        Stays under the Cloudflare Pages 2000-static-redirect cap. Writes a
        cutover_prep summary into clients/{slug}.json so the app/boards can
        surface readiness, and commits the touched files (skip with
        --no-commit — CI does, so the files ride the nightly commit step).

    check --all
        Table of clients whose real domain currently serves something that
        is NOT our site (probe: our builds serve /llms.txt starting with "#"
        and containing the domain — same convention as
        client_ops_sync/setup_ledger) and whose cutover_prep is missing or
        stale (>30 days). Those are pending-cutover clients needing a
        harvest.

    auto [--limit N] [--no-commit]
        check + harvest + map --apply for each pending client (default cap
        3/run to bound the DataForSEO spend). This is the nightly entry in
        .github/workflows/client-ops-sync.yml — redirects on a preview site
        are harmless, so staging them early costs nothing.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

UA = {"User-Agent": "Mozilla/5.0 (compatible; RankAI-cutover-harvest; "
                    "+https://restorationai.io)"}
TIMEOUT = 15
SITEMAP_CAP = 3000          # "follow up to a few thousand URLs"
CRAWL_CAP = 500
CRAWL_DEPTH = 3
TITLE_FETCH_CAP = 200       # titles help the mapper; don't hammer the old site
DFS_PAGES_LIMIT = 100       # one paid call, top pages by backlinks
CF_STATIC_REDIRECT_CAP = 2000
STALE_DAYS = 30
CLAUDE_MODEL = "claude-sonnet-5"

# paths that are assets, not pages — redirecting them wastes rule quota
ASSET_EXT = re.compile(
    r"\.(jpe?g|png|gif|webp|svg|ico|css|js|mjs|json|xml|txt|pdf|zip|gz|mp4|"
    r"mp3|woff2?|ttf|eot|map|webmanifest)$", re.I)
PAGE_EXT = re.compile(r"\.(html?|php|aspx?)$", re.I)

# old-site page names that map 1:1 onto the template's fixed routes
KNOWN_FIXED = {
    "contact": "/contact/", "contact-us": "/contact/", "contactus": "/contact/",
    "about": "/about/", "about-us": "/about/", "aboutus": "/about/",
    "our-story": "/about/", "our-team": "/about/", "team": "/about/",
    "services": "/services/", "our-services": "/services/",
    "service-areas": "/service-areas/", "service-area": "/service-areas/",
    "areas-we-serve": "/service-areas/", "locations": "/service-areas/",
    "blog": "/blog/", "news": "/blog/", "resources": "/blog/",
    "reviews": "/reviews/", "testimonials": "/reviews/",
    "privacy": "/privacy/", "privacy-policy": "/privacy/",
    "terms": "/terms/", "terms-of-service": "/terms/",
    "terms-and-conditions": "/terms/",
    "accessibility": "/accessibility/", "sitemap": "/",
    "emergency": "/emergency/", "certifications": "/certifications/",
    "gallery": "/", "portfolio": "/", "faq": "/", "faqs": "/",
    "home": "/", "index": "/",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def client_record(slug: str) -> dict:
    p = ROOT / "clients" / f"{slug}.json"
    if not p.exists():
        sys.exit(f"ERROR: no client record clients/{slug}.json")
    return json.loads(p.read_text())


def save_client_record(slug: str, rec: dict) -> None:
    p = ROOT / "clients" / f"{slug}.json"
    p.write_text(json.dumps(rec, indent=2) + "\n")


def resolve_domain(slug: str, override: str | None) -> str:
    """--domain flag > clients/{slug}.json domain > prior cutover_prep/inventory."""
    if override:
        return norm_domain(override)
    rec = client_record(slug)
    for cand in (rec.get("domain"), (rec.get("cutover_prep") or {}).get("domain")):
        if cand and not str(cand).endswith(".invalid"):
            return norm_domain(cand)
    inv = inventory_path(slug)
    if inv.exists():
        d = json.loads(inv.read_text()).get("domain")
        if d:
            return d
    sys.exit(f"ERROR: {slug} has no domain on record — pass --domain")


def norm_domain(d: str) -> str:
    d = re.sub(r"^https?://", "", (d or "").strip().lower()).strip("/ ")
    return d[4:] if d.startswith("www.") else d


def inventory_path(slug: str) -> Path:
    return ROOT / "clients" / slug / "cutover" / "url-inventory.json"


def norm_path(url_or_path: str) -> str | None:
    """Canonical path: leading /, no query/fragment, no trailing slash (except /)."""
    try:
        parts = urlsplit(url_or_path)
    except ValueError:
        return None
    path = parts.path or "/"
    if len(path) > 200:
        return None
    if not path.startswith("/"):
        path = "/" + path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/") or "/"
    return path


def same_host(url: str, domain: str) -> bool:
    try:
        host = urlsplit(url).netloc.lower()
    except ValueError:
        return False
    host = host.split(":")[0]
    return host in (domain, f"www.{domain}")


def http_get(url: str, timeout: int = TIMEOUT) -> requests.Response | None:
    try:
        r = requests.get(url, timeout=timeout, headers=UA, allow_redirects=True)
        return r if r.ok else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# harvest — sources
# ---------------------------------------------------------------------------

def _sitemap_locs(xml_text: str) -> tuple[list[str], list[str]]:
    """Return (child_sitemaps, page_urls) from one sitemap document."""
    try:
        root = ET.fromstring(xml_text.encode() if isinstance(xml_text, str) else xml_text)
    except ET.ParseError:
        return [], []
    tag = root.tag.lower()
    locs = [el.text.strip() for el in root.iter()
            if el.tag.lower().endswith("}loc") and el.text and el.text.strip()]
    if tag.endswith("sitemapindex"):
        return locs, []
    return [], locs


def harvest_sitemap(domain: str) -> list[str]:
    """All page URLs from sitemap.xml / index variants, capped."""
    candidates = [f"https://{domain}/sitemap.xml",
                  f"https://{domain}/sitemap_index.xml",
                  f"https://{domain}/wp-sitemap.xml",
                  f"https://{domain}/sitemap-index.xml"]
    robots = http_get(f"https://{domain}/robots.txt", timeout=10)
    if robots is not None:
        for line in robots.text.splitlines():
            if line.lower().startswith("sitemap:"):
                candidates.insert(0, line.split(":", 1)[1].strip())
    urls: list[str] = []
    seen_maps: set[str] = set()
    queue: list[str] = []
    # first candidate that parses as a sitemap wins; alternates are ignored
    for cand in candidates:
        if not cand or cand in seen_maps:
            continue
        seen_maps.add(cand)
        resp = http_get(cand)
        if resp is None:
            continue
        children, pages = _sitemap_locs(resp.text)
        if not children and not pages:
            continue
        urls.extend(pages)
        queue = children
        break
    while queue and len(urls) < SITEMAP_CAP:
        sm = queue.pop(0)
        if sm in seen_maps:
            continue
        seen_maps.add(sm)
        resp = http_get(sm)
        if resp is None:
            continue
        children, pages = _sitemap_locs(resp.text)
        queue.extend(children)
        urls.extend(pages)
    return urls[:SITEMAP_CAP]


class _LinkTitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and len(self.title) < 300:
            self.title += data


def parse_page(url: str) -> tuple[list[str], str]:
    resp = http_get(url)
    if resp is None or "html" not in (resp.headers.get("content-type") or ""):
        return [], ""
    p = _LinkTitleParser()
    try:
        p.feed(resp.text[:800_000])
    except Exception:
        pass
    return p.links, re.sub(r"\s+", " ", p.title).strip()


def harvest_crawl(domain: str) -> dict[str, str]:
    """Shallow same-host BFS from the homepage. Returns {path: title}."""
    start = f"https://{domain}/"
    found: dict[str, str] = {}
    frontier = [start]
    seen: set[str] = set()
    for _depth in range(CRAWL_DEPTH):
        next_frontier: list[str] = []
        for url in frontier:
            path = norm_path(url)
            if path is None or path in seen:
                continue
            seen.add(path)
            links, title = parse_page(url)
            found[path] = title
            if len(found) >= CRAWL_CAP:
                return found
            for href in links:
                absu = urljoin(url, href.split("#")[0])
                if not same_host(absu, domain):
                    continue
                p2 = norm_path(absu)
                if p2 and p2 not in seen and not ASSET_EXT.search(p2):
                    next_frontier.append(f"https://{domain}{p2}")
        frontier = next_frontier
        if not frontier:
            break
    return found


def load_dfs_creds_soft() -> tuple[str, str] | None:
    """geogrid_scan.load_dfs_creds sys.exits on failure; harvest must not."""
    import os
    u, p = os.environ.get("DATAFORSEO_USERNAME"), os.environ.get("DATAFORSEO_PASSWORD")
    if u and p:
        return u, p
    cfg_path = Path.home() / ".claude.json"
    if not cfg_path.exists():
        return None
    try:
        cfg = json.loads(cfg_path.read_text())
    except Exception:
        return None
    found: dict = {}

    def walk(o):
        if isinstance(o, dict):
            if "DATAFORSEO_USERNAME" in o and "DATAFORSEO_PASSWORD" in o:
                found["u"], found["p"] = o["DATAFORSEO_USERNAME"], o["DATAFORSEO_PASSWORD"]
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(cfg)
    return (found["u"], found["p"]) if "u" in found else None


def harvest_backlinks(domain: str) -> dict[str, dict]:
    """ONE DataForSEO Backlinks call: top pages of the domain by backlinks.

    Endpoint per existing repo usage style (authority_targets.py / lead_audit.py
    POST live tasks): /v3/backlinks/domain_pages_summary/live — the paid
    Backlinks API, so exactly one call, capped rows.
    Returns {path: {backlinks, referring_domains}}.
    """
    creds = load_dfs_creds_soft()
    if not creds:
        print("  backlinks: no DataForSEO creds — skipped")
        return {}
    import base64
    auth = base64.b64encode(f"{creds[0]}:{creds[1]}".encode()).decode()
    body = [{"target": domain, "limit": DFS_PAGES_LIMIT,
             "order_by": ["backlinks,desc"], "exclude_internal_backlinks": True}]
    try:
        r = requests.post(
            "https://api.dataforseo.com/v3/backlinks/domain_pages_summary/live",
            data=json.dumps(body), timeout=90,
            headers={"Authorization": "Basic " + auth,
                     "Content-Type": "application/json"})
        d = r.json()
    except Exception as e:
        print(f"  backlinks: DFS call failed ({e}) — skipped")
        return {}
    task = (d.get("tasks") or [{}])[0]
    if task.get("status_code") not in (20000,):
        print(f"  backlinks: DFS status {task.get('status_code')} "
              f"{task.get('status_message')} — skipped")
        return {}
    items = ((task.get("result") or [{}])[0] or {}).get("items") or []
    out: dict[str, dict] = {}
    for it in items:
        raw = it.get("url") or it.get("page_address") or it.get("page") or ""
        if raw.startswith("http"):
            if not same_host(raw, domain):
                continue
        elif not raw.startswith("/"):
            continue
        path = norm_path(raw)
        if not path:
            continue
        bl = int(it.get("backlinks") or 0)
        rd = int(it.get("referring_domains") or 0)
        if bl <= 0:
            continue
        cur = out.setdefault(path, {"backlinks": 0, "referring_domains": 0})
        cur["backlinks"] += bl
        cur["referring_domains"] = max(cur["referring_domains"], rd)
    print(f"  backlinks: {len(out)} page(s) with inbound links "
          f"(cost ~${float(task.get('cost') or 0):.4f})")
    return out


def harvest_gsc(slug: str, domain: str) -> dict[str, int]:
    """Top pages by clicks from GSC, if the agency token can see the property."""
    try:
        from gsc_client import GSCClient
        client = GSCClient(slug, domain)
        svc = client._ensure_service()
    except Exception as e:
        print(f"  gsc: unavailable ({e}) — skipped")
        return {}
    from datetime import date
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=180)).isoformat()
    try:
        rows = svc.searchanalytics().query(siteUrl=client.site_url, body={
            "startDate": start, "endDate": end,
            "dimensions": ["page"], "rowLimit": 250,
        }).execute().get("rows", [])
    except Exception as e:
        print(f"  gsc: query failed ({str(e)[:120]}) — skipped")
        return {}
    out: dict[str, int] = {}
    for row in rows:
        url = (row.get("keys") or [""])[0]
        if not same_host(url, domain):
            continue
        path = norm_path(url)
        clicks = int(row.get("clicks") or 0)
        if path and clicks > 0:
            out[path] = out.get(path, 0) + clicks
    print(f"  gsc: {len(out)} page(s) with clicks")
    return out


def cmd_harvest(slug: str, domain_override: str | None) -> int:
    domain = resolve_domain(slug, domain_override)
    print(f"harvest {slug} — old site https://{domain}/")

    entries: dict[str, dict] = {}   # path -> record

    def add(path: str, source: str, title: str = "") -> None:
        if ASSET_EXT.search(path):
            return
        rec = entries.setdefault(path, {
            "url": f"https://{domain}{path}", "path": path, "title": "",
            "backlinks": 0, "referring_domains": 0, "gsc_clicks": 0,
            "source": []})
        if source not in rec["source"]:
            rec["source"].append(source)
        if title and not rec["title"]:
            rec["title"] = title

    # (a) sitemap
    sm_urls = harvest_sitemap(domain)
    for u in sm_urls:
        if same_host(u, domain):
            p = norm_path(u)
            if p:
                add(p, "sitemap")
    print(f"  sitemap: {sum(1 for e in entries.values() if 'sitemap' in e['source'])} URL(s)")

    # (b) shallow crawl when no sitemap answered
    if not entries:
        crawled = harvest_crawl(domain)
        for p, title in crawled.items():
            add(p, "crawl", title)
        print(f"  crawl: {len(crawled)} URL(s) (no sitemap found)")

    # (c) DataForSEO backlinks top pages
    for p, bl in harvest_backlinks(domain).items():
        add(p, "backlinks")
        entries[p]["backlinks"] = bl["backlinks"]
        entries[p]["referring_domains"] = bl["referring_domains"]

    # (d) GSC top pages
    for p, clicks in harvest_gsc(slug, domain).items():
        add(p, "gsc")
        entries[p]["gsc_clicks"] = clicks

    # titles help the semantic mapper — fetch a bounded batch for pages that
    # matter (backlinked / traffic first, then the rest)
    untitled = [e for e in entries.values() if not e["title"] and e["path"] != "/"]
    untitled.sort(key=lambda e: (-(e["backlinks"] + e["gsc_clicks"])))
    to_fetch = untitled[:TITLE_FETCH_CAP]
    if to_fetch:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futs = {pool.submit(parse_page, e["url"]): e for e in to_fetch}
            for fut in concurrent.futures.as_completed(futs):
                try:
                    _links, title = fut.result()
                except Exception:
                    title = ""
                if title:
                    futs[fut]["title"] = title
        print(f"  titles: fetched for {sum(1 for e in to_fetch if e['title'])}"
              f"/{len(to_fetch)} page(s)")

    rows = sorted(entries.values(),
                  key=lambda e: (-(e["backlinks"]), -(e["gsc_clicks"]), e["path"]))
    for r in rows:
        r["source"] = ",".join(r["source"])
    out = {
        "domain": domain,
        "harvested_at": now_iso(),
        "counts": {
            "total": len(rows),
            "sitemap": sum(1 for r in rows if "sitemap" in r["source"]),
            "crawl": sum(1 for r in rows if "crawl" in r["source"]),
            "backlinked": sum(1 for r in rows if r["backlinks"] > 0),
            "gsc": sum(1 for r in rows if r["gsc_clicks"] > 0),
        },
        "urls": rows,
    }
    invp = inventory_path(slug)
    invp.parent.mkdir(parents=True, exist_ok=True)
    invp.write_text(json.dumps(out, indent=1) + "\n")

    rec = client_record(slug)
    prep = rec.get("cutover_prep") or {}
    prep.update({"domain": domain, "harvested_at": out["harvested_at"],
                 "url_count": out["counts"]["total"],
                 "backlinked_count": out["counts"]["backlinked"]})
    rec["cutover_prep"] = prep
    save_client_record(slug, rec)

    print(f"  wrote {invp.relative_to(ROOT)}: {out['counts']['total']} URLs "
          f"({out['counts']['backlinked']} backlinked, {out['counts']['gsc']} with GSC clicks)")
    return 0


# ---------------------------------------------------------------------------
# map — enumerate new routes, match, merge _redirects
# ---------------------------------------------------------------------------

def enumerate_routes(slug: str) -> list[str]:
    """Every real route the NEW site will serve. lp/ is noindex — excluded."""
    src = ROOT / "sites" / slug / "src"
    if not src.exists():
        sys.exit(f"ERROR: sites/{slug}/src not found — site not scaffolded")
    routes = {"/"}

    def md_slugs(sub: str) -> list[str]:
        d = src / "content" / sub
        return sorted(p.stem for p in d.glob("*.md")) if d.exists() else []

    # fixed pages via [fixed].astro (all pages except home/blog-index) + hubs
    for s in md_slugs("pages"):
        if s == "home":
            continue
        routes.add("/blog/" if s == "blog-index" else f"/{s}/")
    for s in md_slugs("services"):
        routes.add(f"/services/{s}/")
    for s in md_slugs("serviceAreas"):
        routes.add(f"/service-areas/{s}/")
    for s in md_slugs("locations"):        # {area}__{service}.md
        if "__" in s:
            area, service = s.split("__", 1)
            routes.add(f"/service-areas/{area}/{service}/")
    for s in md_slugs("blog"):
        routes.add("/blog/")
        routes.add(f"/blog/{s}/")
    # legal routes come from each entry's `ref` frontmatter ([legal].astro)
    legal_dir = src / "content" / "legal"
    if legal_dir.exists():
        for p in legal_dir.glob("*.md"):
            m = re.search(r'^ref:\s*"?([a-z0-9-]+)"?', p.read_text(), re.M)
            routes.add(f"/{(m.group(1) if m else p.stem)}/")
    # dedicated static .astro pages at the top level (certifications, emergency,
    # reviews, ...) — skip dynamic ([x]), index, 404 and the lp/ tree entirely
    pages = src / "pages"
    if pages.exists():
        for p in pages.glob("*.astro"):
            if p.stem in ("index", "404") or p.stem.startswith("["):
                continue
            routes.add(f"/{p.stem}/")
    return sorted(routes)


def _route_lookup(routes: list[str]) -> dict[str, str]:
    """normalized (no trailing slash) -> canonical route"""
    return {(r.rstrip("/") or "/"): r for r in routes}


def _last_segment(path: str) -> str:
    segs = [s for s in path.split("/") if s]
    return segs[-1] if segs else ""


def _strip_page_ext(path: str) -> str:
    return PAGE_EXT.sub("", path) or "/"


def heuristic_match(path: str, routes: list[str]) -> str | None:
    """Conservative tiers only — anything fuzzy goes to the model instead."""
    lookup = _route_lookup(routes)
    p = _strip_page_ext(path).lower()
    # 1. the path already exists on the new site
    if p in lookup:
        return lookup[p]
    seg = _last_segment(p)
    # 2. well-known fixed page names
    if seg in KNOWN_FIXED:
        target = KNOWN_FIXED[seg]
        return target if target in routes or target == "/" else None
    # 3. unique last-segment match against route last-segments
    matches = [r for r in routes if _last_segment(r.rstrip("/")) == seg and seg]
    if len(matches) == 1:
        return matches[0]
    return None


def _loose_json_obj(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in model response: " + text[:200])
    s = m.group(0)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", s))


def claude_match(unmatched: list[dict], routes: list[str]) -> dict[str, str]:
    """ONE claude-sonnet-5 call: batch old path+title -> best new route or "/"."""
    if not unmatched:
        return {}
    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception as e:
        print(f"  claude: unavailable ({e}) — unmatched URLs fall back to /")
        return {}
    batch = unmatched[:1000]
    payload = {
        "new_site_routes": routes,
        "old_urls": [{"path": u["path"], "title": u.get("title") or "",
                      "important": bool(u.get("backlinks") or u.get("gsc_clicks"))}
                     for u in batch],
    }
    system = (
        "You build 301 redirect maps for restoration-contractor websites whose "
        "domain is being cut over to a rebuilt site. Map each old URL path to "
        "the single best route on the NEW site.\n"
        "Rules:\n"
        "- The target MUST be copied exactly from new_site_routes, or \"/\".\n"
        "- Prefer the most specific plausible target: a city+service page beats "
        "a service page when the city matches; a service page beats /services/; "
        "a closely-related blog post beats /blog/.\n"
        "- URLs marked important:true carry backlinks or search traffic and MUST "
        "get a specific target whenever any plausible match exists.\n"
        "- Use \"/\" only when nothing on the new site plausibly matches.\n"
        "- Common synonyms: flood/flooded/water-removal/extraction/drying -> "
        "water-damage-restoration; mold/mould/remediation/testing -> mold pages; "
        "fire/smoke/soot -> fire-damage-restoration; storm/wind/hail -> "
        "storm-damage-restoration; rebuild/reconstruction/remodel -> "
        "general-contracting; contents/pack-out -> contents-restoration.\n"
        "Return ONLY a JSON object mapping every old path to its target route. "
        "No commentary."
    )
    try:
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        raw = _loose_json_obj(text)
    except Exception as e:
        print(f"  claude: call failed ({str(e)[:160]}) — unmatched URLs fall back to /")
        return {}
    valid = set(routes) | {"/"}
    out: dict[str, str] = {}
    for k, v in raw.items():
        if isinstance(v, str):
            v = v if v.endswith("/") or v == "/" else v + "/"
            out[k] = v if v in valid else "/"
    print(f"  claude: mapped {len(out)}/{len(batch)} remainder URL(s) "
          f"in one {CLAUDE_MODEL} call")
    return out


def parse_redirects(text: str) -> set[str]:
    """Source paths already claimed by existing rules (existing rule wins)."""
    claimed: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            claimed.add(parts[0])
    return claimed


def count_rules(text: str) -> int:
    return sum(1 for ln in text.splitlines()
               if ln.strip() and not ln.strip().startswith("#"))


def cmd_map(slug: str, apply: bool, commit: bool) -> int:
    invp = inventory_path(slug)
    if not invp.exists():
        sys.exit(f"ERROR: run harvest first — no {invp.relative_to(ROOT)}")
    inv = json.loads(invp.read_text())
    urls = inv.get("urls") or []
    routes = enumerate_routes(slug)
    print(f"map {slug} — {len(urls)} old URLs vs {len(routes)} new routes")

    mapping: dict[str, dict] = {}   # old path -> {target, how, priority}
    unmatched: list[dict] = []
    exists_already = 0
    for u in urls:
        path = u["path"]
        if path == "/":
            continue
        hit = heuristic_match(path, routes)
        if hit is not None:
            norm_hit = hit.rstrip("/") or "/"
            norm_old = _strip_page_ext(path).lower().rstrip("/") or "/"
            if norm_hit == norm_old:
                exists_already += 1      # same URL exists on the new site
                continue
            mapping[path] = {"target": hit, "how": "heuristic", "rec": u}
        else:
            unmatched.append(u)

    model_map = claude_match(unmatched, routes)
    for u in unmatched:
        target = model_map.get(u["path"], "/")
        mapping[u["path"]] = {
            "target": target,
            "how": "claude" if u["path"] in model_map else "fallback-home",
            "rec": u,
        }

    n_specific = sum(1 for m in mapping.values() if m["target"] != "/")
    n_home = len(mapping) - n_specific
    important = [m for m in mapping.values()
                 if (m["rec"].get("backlinks") or m["rec"].get("gsc_clicks"))]
    imp_home = sum(1 for m in important if m["target"] == "/")
    print(f"  mapped {len(mapping)} paths: {n_specific} specific, {n_home} -> / "
          f"(unchanged-on-new-site: {exists_already})")
    if important:
        print(f"  backlinked/GSC URLs: {len(important)} total, "
              f"{len(important) - imp_home} specific, {imp_home} -> /")

    # persist the mapping artifact either way (review + idempotent re-runs)
    map_out = {
        "generated_at": now_iso(), "domain": inv.get("domain"),
        "routes": len(routes),
        "map": {p: {"target": m["target"], "how": m["how"]}
                for p, m in sorted(mapping.items())},
    }
    (invp.parent / "redirect-map.json").write_text(json.dumps(map_out, indent=1) + "\n")

    if not apply:
        for p, m in list(sorted(mapping.items()))[:20]:
            print(f"    {p} -> {m['target']} ({m['how']})")
        print("  (dry run — use --apply to merge into public/_redirects)")
        return 0

    # --- merge into sites/{slug}/public/_redirects -------------------------
    red_path = ROOT / "sites" / slug / "public" / "_redirects"
    red_path.parent.mkdir(parents=True, exist_ok=True)
    existing = red_path.read_text() if red_path.exists() else ""
    claimed = parse_redirects(existing)
    budget = CF_STATIC_REDIRECT_CAP - count_rules(existing)

    # priority: backlinks desc, clicks desc, specific-target before "/"
    ordered = sorted(
        mapping.items(),
        key=lambda kv: (-(kv[1]["rec"].get("backlinks") or 0),
                        -(kv[1]["rec"].get("gsc_clicks") or 0),
                        kv[1]["target"] == "/", kv[0]))
    lines: list[str] = []
    added = dropped = 0
    for path, m in ordered:
        variants = [path] if path == "/" else [path, path + "/"]
        variants = [v for v in variants if v not in claimed]
        if not variants:
            continue
        if budget - len(variants) < 0:
            dropped += 1
            continue
        for v in variants:
            lines.append(f"{v} {m['target']} 301")
            claimed.add(v)
            budget -= 1
        added += 1
    if lines:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        block = (f"# cutover harvest {stamp} — auto 301 map from "
                 f"{inv.get('domain')} ({added} old URLs; generated by "
                 f"scripts/cutover_harvest.py, existing rules preserved)\n"
                 + "\n".join(lines) + "\n")
        new_text = existing
        if new_text and not new_text.endswith("\n"):
            new_text += "\n"
        if new_text:
            new_text += "\n"
        new_text += block
        red_path.write_text(new_text)
    # readiness metric that survives idempotent re-runs: how many of the
    # mapped old paths the merged file now covers (not just added-this-run)
    covered = sum(1 for p in mapping
                  if p in claimed or (p != "/" and p + "/" in claimed))
    print(f"  _redirects: +{added} paths ({len(lines)} rules incl. trailing-slash "
          f"variants), {dropped} dropped for the {CF_STATIC_REDIRECT_CAP}-rule cap, "
          f"total now {count_rules(red_path.read_text())} rules, "
          f"{covered}/{len(mapping)} mapped paths covered")

    # --- cutover_prep summary on the client record --------------------------
    rec = client_record(slug)
    prep = rec.get("cutover_prep") or {}
    prep.update({
        "domain": inv.get("domain"),
        "harvested_at": inv.get("harvested_at"),
        "url_count": (inv.get("counts") or {}).get("total", len(urls)),
        "backlinked_count": (inv.get("counts") or {}).get("backlinked", 0),
        "redirects_added": covered,
        "mapped_at": now_iso(),
    })
    rec["cutover_prep"] = prep
    save_client_record(slug, rec)

    if commit:
        files = [f"clients/{slug}.json", f"clients/{slug}/cutover",
                 f"sites/{slug}/public/_redirects"]
        try:
            subprocess.run(["git", "add", *files], cwd=ROOT, check=True,
                           capture_output=True)
            r = subprocess.run(
                ["git", "commit", "-m",
                 f"cutover_harvest: {slug} 301 map staged "
                 f"({added} redirects from {inv.get('domain')})\n\n"
                 "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"],
                cwd=ROOT, capture_output=True, text=True)
            print("  committed" if r.returncode == 0
                  else f"  commit skipped: {r.stdout.strip() or r.stderr.strip()}")
        except Exception as e:
            print(f"  commit failed (non-fatal): {e}")
    return 0


# ---------------------------------------------------------------------------
# check / auto
# ---------------------------------------------------------------------------

def probe_domain(domain: str, slug: str | None = None) -> str:
    """OURS / OTHER / DOWN — the /llms.txt liveness convention.

    Same lesson as client_ops_sync's launch check: a 200 is not enough
    (prorestorationca.com soft-404s everything) and a homepage string match is
    not enough (homelyft.net is the client's OWN old site). But the ledger's
    domain-in-body test is ALSO not enough here, in both directions:
      - Wix/builder OLD sites now auto-generate llms.txt naming their own
        domain (reign-restoration.com, dissrestoration.com,
        transformation-remodeling.com all do) — domain-in-body says OURS on
        sites we never built;
      - TRG's real deployed llms.txt references its pre-cutover domain (the
        stale domain-after-scaffold bug) — domain-in-body says OTHER on a
        site that IS ours.
    The authoritative signature is the repo's own copy: what we deploy is
    sites/{slug}/public/llms.txt, so a served body whose head matches ours is
    our build, and anything else is not.
    """
    try:
        resp = requests.get(f"https://{domain}/llms.txt", timeout=12,
                            allow_redirects=True, headers=UA)
    except Exception:
        return "DOWN"
    body = (resp.text or "").lstrip()
    if not (resp.ok and body.startswith("#") and not body.startswith("<")):
        return "OTHER"
    if slug:
        local = ROOT / "sites" / slug / "public" / "llms.txt"
        if local.exists():
            ours = local.read_text().lstrip()
            if ours[:80] and body[:80] == ours[:80]:
                return "OURS"
            return "OTHER"
    # no scaffolded site in the repo -> it cannot be our build; fall back to
    # the ledger convention only as a last resort for repos checked out
    # without sites/ (CI shallow paths etc.)
    if (ROOT / "sites").exists():
        return "OTHER"
    return "OURS" if f"https://{domain}/" in body else "OTHER"


def _prep_age_days(prep: dict) -> float | None:
    ts = (prep or {}).get("harvested_at")
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def pending_cutover_clients() -> list[dict]:
    """[{slug, domain, serving, prep_age, pending}] for every real-domain client."""
    rows = []
    for p in sorted((ROOT / "clients").glob("*.json")):
        if p.name == "company_map.json":
            continue
        try:
            rec = json.loads(p.read_text())
        except Exception:
            continue
        slug = rec.get("slug") or p.stem
        domain = rec.get("domain") or (rec.get("cutover_prep") or {}).get("domain")
        if not domain or str(domain).endswith(".invalid"):
            continue
        domain = norm_domain(domain)
        serving = probe_domain(domain, slug)
        age = _prep_age_days(rec.get("cutover_prep") or {})
        stale = age is None or age > STALE_DAYS
        rows.append({
            "slug": slug, "domain": domain, "serving": serving,
            "prep_age": age,
            "pending": serving == "OTHER" and stale,
        })
    return rows


def cmd_check() -> int:
    rows = pending_cutover_clients()
    if not rows:
        print("no clients with a real domain attached")
        return 0
    w = max(len(r["slug"]) for r in rows) + 2
    wd = max(len(r["domain"]) for r in rows) + 2
    print(f"{'client':<{w}}{'domain':<{wd}}{'serving':<9}{'harvest':<14}pending-cutover")
    for r in rows:
        age = ("never" if r["prep_age"] is None
               else f"{r['prep_age']:.0f}d ago")
        flag = "YES — needs harvest" if r["pending"] else ""
        if r["serving"] == "OTHER" and not r["pending"]:
            flag = "prepared"
        print(f"{r['slug']:<{w}}{r['domain']:<{wd}}{r['serving']:<9}{age:<14}{flag}")
    n = sum(1 for r in rows if r["pending"])
    print(f"\n{n} client(s) pending cutover with an unharvested/stale old site")
    return 0


def cmd_auto(limit: int, commit: bool) -> int:
    rows = [r for r in pending_cutover_clients() if r["pending"]][:limit]
    if not rows:
        print("auto: nothing pending")
        return 0
    for r in rows:
        print(f"\n=== auto: {r['slug']} ({r['domain']}) ===")
        try:
            cmd_harvest(r["slug"], r["domain"])
            cmd_map(r["slug"], apply=True, commit=commit)
        except SystemExit as e:
            print(f"  auto: {r['slug']} aborted ({e}) — continuing")
        except Exception as e:
            print(f"  auto: {r['slug']} failed ({e}) — continuing")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harvest", help="inventory the old site before cutover")
    h.add_argument("--slug", required=True)
    h.add_argument("--domain", help="override clients/{slug}.json domain")

    m = sub.add_parser("map", help="generate + merge the 301 map")
    m.add_argument("--slug", required=True)
    m.add_argument("--apply", action="store_true",
                   help="merge into sites/{slug}/public/_redirects")
    m.add_argument("--no-commit", action="store_true",
                   help="write files but let a later commit step pick them up")

    c = sub.add_parser("check", help="list pending-cutover clients")
    c.add_argument("--all", action="store_true", default=True)

    a = sub.add_parser("auto", help="check + harvest + map --apply (nightly)")
    a.add_argument("--limit", type=int, default=3)
    a.add_argument("--no-commit", action="store_true")

    args = ap.parse_args()
    if args.cmd == "harvest":
        return cmd_harvest(args.slug, args.domain)
    if args.cmd == "map":
        return cmd_map(args.slug, apply=args.apply, commit=not args.no_commit)
    if args.cmd == "check":
        return cmd_check()
    if args.cmd == "auto":
        return cmd_auto(args.limit, commit=not args.no_commit)
    return 2


if __name__ == "__main__":
    sys.exit(main())
