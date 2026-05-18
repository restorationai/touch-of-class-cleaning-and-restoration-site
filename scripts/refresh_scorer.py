#!/usr/bin/env python3
"""
Rank AI — System 4 Layer 1: Refresh Scorer (sitemap-only v1)

For one Rank AI client, score every URL in the site's sitemap on age. Output
clients/{slug}/refresh-candidates.json for the Layer-2 Claude prompt to
classify into per-URL refresh actions.

This v1 uses SITEMAP + PAGE-LEVEL date extraction only. It does NOT query
Google Search Console for indexing flags — that capability is deferred to v2
when GSC OAuth is set up. The script has clean hook points (`gsc_inspect`)
that v2 can fill in without changing the rest of the flow.

Flags surfaced today:
  - stale_12mo: latest publish/modify date is 365+ days old
  - aging:      305-364 days old (approaching stale)

Flags deferred to v2 (GSC integration):
  - not_indexed:    GSC reports the URL is not indexed
  - index_warning:  GSC reports a partial issue (alternate canonical, soft 404, etc.)

Usage:
  python3 scripts/refresh_scorer.py --slug narestco
  python3 scripts/refresh_scorer.py --slug narestco --max-urls 200
  python3 scripts/refresh_scorer.py --slug narestco --include-pattern /blog/
  python3 scripts/refresh_scorer.py --slug narestco --force-origin https://staging.rankai-narestco.pages.dev

Output:
  clients/{slug}/refresh-candidates.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()


ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (compatible; rank-ai/refresh-scorer; +https://restorationai.io)"
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

STALE_DAYS = 365
AGING_DAYS = 305


# -----------------------------------------------------------------------------
# Client + topology
# -----------------------------------------------------------------------------


def load_client(slug: str) -> dict:
    path = ROOT / "clients" / f"{slug}.json"
    if not path.exists():
        sys.stderr.write(f"ERROR: client record not found at {path}\n")
        sys.exit(1)
    c = json.loads(path.read_text())
    if c.get("status") != "active":
        sys.stderr.write(f"ERROR: client {slug} is not active (status={c.get('status')})\n")
        sys.exit(1)
    return c


def determine_origin(c: dict, force: str | None) -> tuple[str, str]:
    """Return (origin, source) — source is 'apex', 'staging', or 'forced'."""
    if force:
        return force.rstrip("/"), "forced"
    if c.get("apex_cutover", {}).get("completed_at"):
        return f"https://{c['domain']}", "apex"
    return f"https://staging.rankai-{c['slug']}.pages.dev", "staging"


# -----------------------------------------------------------------------------
# Sitemap discovery + expansion
# -----------------------------------------------------------------------------


def fetch_text(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
        return r.read().decode("utf-8", errors="replace")


def discover_sitemaps(origin: str) -> list[str]:
    """Find sitemap URL(s) by trying robots.txt + common paths.

    Returns only sitemap URLs that actually fetch successfully. The robots.txt
    Sitemap: directive often points to the canonical/production URL even when
    you're auditing a staging origin — so we validate every candidate and fall
    through to origin-relative paths if the canonical one 404s.
    """
    origin = origin.rstrip("/")
    candidates: list[str] = []
    try:
        robots = fetch_text(f"{origin}/robots.txt")
        for line in robots.splitlines():
            if line.lower().startswith("sitemap:"):
                candidates.append(line.split(":", 1)[1].strip())
    except Exception:
        pass
    # Always also try origin-relative fallbacks (de-dupe at the end)
    for path in ["/sitemap-index.xml", "/sitemap.xml", "/sitemap-0.xml"]:
        candidates.append(f"{origin}{path}")
    # Validate: keep only URLs that respond 200
    found: list[str] = []
    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        try:
            fetch_text(c, timeout=10)
            found.append(c)
            # Once we find one working sitemap on this origin, stop trying alternates
            if c.startswith(origin):
                break
        except Exception:
            continue
    return found


def rewrite_to_origin(url: str, origin: str) -> str:
    """Replace the scheme+host of `url` with `origin`. Used when a staging
    sitemap embeds production URLs that don't resolve on the staging origin.
    """
    m = re.match(r"^https?://[^/]+(/.*)$", url)
    if not m:
        return url
    return origin.rstrip("/") + m.group(1)


def expand_sitemap(url: str, origin: str | None = None, depth: int = 0) -> list[dict]:
    """Return list of {loc, lastmod} dicts. Follows sitemap index files (depth ≤ 3).

    If `origin` is given, child sitemap URLs that point to a different host are
    rewritten to use `origin` (so a staging mirror works even when the sitemap
    has the production hostname baked in by Astro / Next / etc).
    """
    if depth > 3:
        return []
    try:
        body = fetch_text(url)
    except Exception as e:
        # Try rewriting to origin if first attempt failed
        if origin and depth > 0:
            alt = rewrite_to_origin(url, origin)
            if alt != url:
                try:
                    body = fetch_text(alt)
                    sys.stderr.write(f"INFO: rewrote {url} -> {alt}\n")
                except Exception as e2:
                    sys.stderr.write(f"WARN: failed to fetch {url} (also {alt}): {e2}\n")
                    return []
            else:
                sys.stderr.write(f"WARN: failed to fetch {url}: {e}\n")
                return []
        else:
            sys.stderr.write(f"WARN: failed to fetch {url}: {e}\n")
            return []
    body = re.sub(r"<\?xml[^>]+\?>", "", body)
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        sys.stderr.write(f"WARN: failed to parse {url}: {e}\n")
        return []
    tag = root.tag.lower().split("}")[-1]
    out: list[dict] = []
    if tag == "sitemapindex":
        for sm in root.findall("sm:sitemap", SITEMAP_NS):
            loc = sm.findtext("sm:loc", default="", namespaces=SITEMAP_NS).strip()
            if loc:
                out.extend(expand_sitemap(loc, origin=origin, depth=depth + 1))
    elif tag == "urlset":
        for u in root.findall("sm:url", SITEMAP_NS):
            loc = u.findtext("sm:loc", default="", namespaces=SITEMAP_NS).strip()
            if not loc:
                continue
            # If we're auditing a staging mirror, rewrite each URL to the staging origin
            if origin and not loc.startswith(origin):
                loc = rewrite_to_origin(loc, origin)
            lastmod = u.findtext("sm:lastmod", default="", namespaces=SITEMAP_NS).strip() or None
            out.append({"loc": loc, "lastmod": lastmod})
    return out


# -----------------------------------------------------------------------------
# Per-URL date extraction
# -----------------------------------------------------------------------------


ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_iso(s: str) -> dt.date | None:
    if not s:
        return None
    m = ISO_DATE_RE.search(s)
    if not m:
        return None
    try:
        return dt.date.fromisoformat(m.group(0))
    except ValueError:
        return None


def extract_dates_from_html(html: str) -> dict:
    """Pull date-related signals from rendered HTML. Best-effort, never raises."""
    out = {
        "json_ld_date_published": None,
        "json_ld_date_modified": None,
        "article_modified_time": None,
        "time_published": None,
        "time_updated": None,
    }
    # JSON-LD blocks
    for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
                         html, flags=re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if "datePublished" in item:
                out["json_ld_date_published"] = item["datePublished"]
            if "dateModified" in item:
                out["json_ld_date_modified"] = item["dateModified"]
    # article:modified_time meta
    m = re.search(r'<meta\s+property=["\']article:modified_time["\']\s+content=["\']([^"\']+)',
                  html, flags=re.IGNORECASE)
    if m:
        out["article_modified_time"] = m.group(1)
    # <time datetime="...">
    for m in re.finditer(r'<time[^>]+datetime=["\']([^"\']+)', html, flags=re.IGNORECASE):
        d = m.group(1)
        if not out["time_published"]:
            out["time_published"] = d
        else:
            out["time_updated"] = d
    return out


def best_date(sitemap_lastmod: str | None, html_dates: dict) -> tuple[dt.date | None, str]:
    """Pick the most authoritative date and report its source."""
    candidates = [
        ("json_ld_date_modified", html_dates.get("json_ld_date_modified")),
        ("article_modified_time", html_dates.get("article_modified_time")),
        ("json_ld_date_published", html_dates.get("json_ld_date_published")),
        ("time_updated", html_dates.get("time_updated")),
        ("time_published", html_dates.get("time_published")),
        ("sitemap_lastmod", sitemap_lastmod),
    ]
    for source, raw in candidates:
        d = parse_iso(raw or "")
        if d:
            return d, source
    return None, "none"


# -----------------------------------------------------------------------------
# GSC hook (v2 — activated when per-client token + OAuth client secret exist)
# -----------------------------------------------------------------------------


_GSC_CLIENT_CACHE: dict[str, object] = {}


def gsc_inspect(url: str, slug: str | None = None, domain: str | None = None) -> dict | None:
    """Inspect a URL via Google Search Console if configured for this client.

    v1 behavior (no GSC token present): returns None — caller treats as
    "indexing flags unavailable" and proceeds with sitemap-only scoring.

    v2 behavior (per-client OAuth token present): returns a normalized dict:
      {"index_status": "PASS" | "FAIL" | "PARTIAL" | "UNKNOWN",
       "coverage_state": "<verbatim GSC string>",
       "last_crawl_time": "<iso>" or None,
       "fetched_at": "<iso>"}

    Activation: see docs/system-4-v2-activation.md.
    """
    if not slug or not domain:
        return None
    try:
        from gsc_client import GSCClient  # local import to avoid hard dep in v1
    except ImportError:
        return None
    if not GSCClient.is_configured(slug):
        return None
    client = _GSC_CLIENT_CACHE.get(slug)
    if client is None:
        client = GSCClient(slug=slug, domain=domain)
        _GSC_CLIENT_CACHE[slug] = client
    try:
        return client.inspect(url)
    except Exception as e:
        sys.stderr.write(f"WARN: GSC inspect failed for {url}: {e}\n")
        return None


# -----------------------------------------------------------------------------
# Main flow
# -----------------------------------------------------------------------------


def score(c: dict, *, origin: str, origin_source: str, max_urls: int,
          include_pattern: str | None) -> dict:
    slug = c["slug"]
    print(f"==> Refresh scorer (v1, sitemap-only) for {slug}")
    print(f"    Origin:   {origin} ({origin_source})")
    print(f"    Max URLs: {max_urls}")
    if include_pattern:
        print(f"    Include filter: {include_pattern}")

    sitemaps = discover_sitemaps(origin)
    if not sitemaps:
        sys.stderr.write(f"ERROR: no sitemap discovered at {origin}\n")
        sys.exit(2)
    print(f"[1/3] Discovered {len(sitemaps)} sitemap(s): {sitemaps}")

    all_urls: list[dict] = []
    for sm in sitemaps:
        all_urls.extend(expand_sitemap(sm, origin=origin))
    # dedupe by loc
    seen = {}
    for u in all_urls:
        seen[u["loc"]] = u
    all_urls = list(seen.values())
    if include_pattern:
        all_urls = [u for u in all_urls if include_pattern in u["loc"]]
    all_urls = all_urls[:max_urls]
    print(f"      {len(all_urls)} URL(s) after dedupe + filter + cap")

    today = dt.date.today()
    candidates: list[dict] = []
    inspected = 0
    fetched_html = 0
    failed_html = 0

    print(f"[2/3] Extracting dates per URL...")
    for u in all_urls:
        loc = u["loc"]
        lastmod = u.get("lastmod")
        # Fetch HTML for richer date extraction (skip if URL doesn't look like a real page)
        html_dates: dict = {}
        if loc.endswith("/") or loc.endswith(".html") or "/" in loc.rsplit("/", 1)[-1] == False:
            try:
                html = fetch_text(loc, timeout=15)
                html_dates = extract_dates_from_html(html)
                fetched_html += 1
            except Exception as e:
                sys.stderr.write(f"WARN: page fetch failed for {loc}: {e}\n")
                failed_html += 1
        chosen, source = best_date(lastmod, html_dates)
        age_days = (today - chosen).days if chosen else None

        flags: list[str] = []
        if age_days is not None:
            if age_days >= STALE_DAYS:
                flags.append("stale_12mo")
            elif age_days >= AGING_DAYS:
                flags.append("aging")

        # GSC hook (v1 returns None; v2 returns indexing flags when configured)
        gsc = gsc_inspect(loc, slug=slug, domain=c.get("domain"))
        if gsc:
            if gsc.get("index_status") == "FAIL":
                flags.append("not_indexed")
            elif gsc.get("index_status") == "PARTIAL":
                flags.append("index_warning")

        candidates.append({
            "url": loc,
            "date": chosen.isoformat() if chosen else None,
            "date_source": source,
            "age_days": age_days,
            "flags": flags,
            "sitemap_lastmod": lastmod,
            "html_dates": html_dates,
            "gsc": gsc,
        })
        inspected += 1

    print(f"      Inspected: {inspected}  (html fetched: {fetched_html}, failed: {failed_html})")

    # Summarize flag distribution
    flag_counts: dict[str, int] = {}
    for c0 in candidates:
        for f in c0["flags"]:
            flag_counts[f] = flag_counts.get(f, 0) + 1

    print(f"[3/3] Flag summary:")
    if not flag_counts:
        print(f"      No flags — all URLs are fresh.")
    else:
        for f, n in sorted(flag_counts.items(), key=lambda x: -x[1]):
            print(f"      {f:15} {n}")

    # Detect whether any candidate actually got GSC data (proves v2 is active for this client)
    gsc_enabled = any(c0.get("gsc") for c0 in candidates)
    return {
        "schema_version": 1,
        "slug": slug,
        "origin": origin,
        "origin_source": origin_source,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "stale_threshold_days": STALE_DAYS,
        "aging_threshold_days": AGING_DAYS,
        "gsc_enabled": gsc_enabled,
        "v1_notes": [
            "v1 = sitemap + page-level date extraction. No GSC indexing flags."
            if not gsc_enabled else
            "v2 active: per-URL GSC indexing flags included.",
            "See docs/system-4-v2-activation.md for GSC v2 setup.",
        ],
        "inspected_count": inspected,
        "fetched_html_count": fetched_html,
        "failed_html_count": failed_html,
        "flag_counts": flag_counts,
        "candidates": candidates,
    }


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank AI System 4 — Refresh Scorer (sitemap-only v1)")
    ap.add_argument("--slug", required=True, help="Client slug (e.g. narestco)")
    ap.add_argument("--max-urls", type=int, default=120, help="Cap on URLs to inspect")
    ap.add_argument("--include-pattern", help="Only inspect URLs containing this substring")
    ap.add_argument("--force-origin", help="Override origin URL (debugging)")
    args = ap.parse_args()

    c = load_client(args.slug)
    origin, source = determine_origin(c, args.force_origin)
    state = score(c, origin=origin, origin_source=source,
                  max_urls=args.max_urls, include_pattern=args.include_pattern)
    out_path = ROOT / "clients" / args.slug / "refresh-candidates.json"
    write_atomic(out_path, state)
    print(f"\n==> Wrote {out_path}")
    print(f"    Candidates: {len(state['candidates'])}")
    print(f"    Layer 2 ('refresh-recommender') reads this and produces refresh-queue.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
