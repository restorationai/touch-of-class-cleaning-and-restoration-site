#!/usr/bin/env python3
"""Citations discovery + NAP audit (Santino 2026-07-28, priority build).

For a client: take the CANONICAL business info (companies row — the app's
Business Information source-of-truth card), search each major directory for
their listing via DataForSEO SERP (site: queries), pre-populate the found
URLs into the app's Business Listings slots (user_integrations
provider='citations' connection_metadata.citation_urls — same keys the
Connect tab renders), and record a per-platform audit:

  found + phone matches      -> ok
  found + different phone    -> discrepancy (the Connect tab shows the diff)
  not found                  -> missing (amber slot in the app)

Phone extraction is best-effort (SERP snippet + page fetch where the
directory allows it); platforms that block bots still get URL discovery.
Results land in connection_metadata.nap_audit for the app to render.

Usage: citations_audit.py --slug crew-restoration-construction
       citations_audit.py --slug X --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb, slug_map  # noqa: E402
from lead_audit import _dfs, _dfs_auth  # noqa: E402

DFS_SERP = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"

# key -> (site: filter, human label). Keys MUST match the app's
# CITATION_PLATFORMS so prepopulated URLs land in the right slots.
PLATFORMS = {
    "yelp": ("yelp.com/biz", "Yelp"),
    "bbb": ("bbb.org", "BBB"),
    "angi": ("angi.com", "Angi"),
    "homeadvisor": ("homeadvisor.com", "HomeAdvisor"),
    "thumbtack": ("thumbtack.com", "Thumbtack"),
    "facebook": ("facebook.com", "Facebook"),
    "apple_maps": ("maps.apple.com", "Apple Maps"),
    "bing_places": ("bing.com/maps", "Bing Places"),
}

PHONE_RE = re.compile(r"\(?\b(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})\b")


def _norm_phone(s: str | None) -> str:
    d = re.sub(r"\D", "", s or "")
    return d[-10:] if len(d) >= 10 else d


def _page_phone(url: str) -> str | None:
    """Best-effort phone read from the listing page (many directories block
    bots — a None here means 'could not verify', never 'wrong')."""
    try:
        r = requests.get(url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"})
        if r.status_code != 200:
            return None
        m = PHONE_RE.search(r.text)
        return "".join(m.groups()) if m else None
    except Exception:
        return None


def audit(slug: str, dry_run: bool = False) -> str:
    inv = {s: c for c, s in slug_map().items()}
    cid = inv.get(slug)
    if not cid:
        return f"{slug}: no company mapping"
    co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}"
              "&select=name,phone,city,state", prefer="return=representation") or [{}])[0]
    name = (co.get("name") or "").strip()
    canon_phone = _norm_phone(co.get("phone"))
    city, state = (co.get("city") or "").strip(), (co.get("state") or "").strip()
    if not name:
        return f"{slug}: no company name"

    auth = _dfs_auth()
    results: dict = {}
    urls: dict = {}
    lines = [f"== {name} ({city}, {state}) — canonical phone {canon_phone or '?'}"]
    for key, (site, label) in PLATFORMS.items():
        q = f'site:{site} "{name}" {city}'
        try:
            items, cost, _ = _dfs(DFS_SERP, [{
                "keyword": q[:700], "location_code": 2840,
                "language_code": "en", "depth": 10}], auth)
        except Exception as e:
            results[key] = {"status": "error", "error": str(e)[:80]}
            continue
        organic = [i for i in items if isinstance(i, dict)
                   and i.get("type") == "organic" and i.get("url")]
        # NAME GUARD (first run: HomeAdvisor matched a different company and
        # Angi returned a category page): the business name's significant
        # tokens must appear in the result title/URL or it's not their listing.
        toks = {t for t in re.findall(r"[a-z]+", name.lower()) if len(t) > 3}
        def _is_theirs(it):
            hay = (str(it.get("title") or "") + " " + str(it.get("url") or "")).lower()
            need = min(2, len(toks)) or 1
            return sum(1 for t in toks if t in hay) >= need
        organic = [i for i in organic if _is_theirs(i)]
        if not organic:
            results[key] = {"status": "missing",
                            "checked_at": datetime.now(timezone.utc).isoformat()}
            lines.append(f"  {label:12s} NOT FOUND")
            continue
        best = organic[0]
        url = best["url"]
        urls[key] = url
        # phone: SERP snippet first, page fetch second
        snippet = " ".join(str(best.get(k) or "") for k in ("description", "title"))
        m = PHONE_RE.search(snippet)
        phone = "".join(m.groups()) if m else _page_phone(url)
        entry = {"status": "found", "url": url,
                 "checked_at": datetime.now(timezone.utc).isoformat()}
        if phone:
            entry["phone_found"] = phone
            entry["phone_matches"] = (phone == canon_phone) if canon_phone else None
            if canon_phone and phone != canon_phone:
                entry["status"] = "discrepancy"
                lines.append(f"  {label:12s} DISCREPANCY: shows {phone}, canonical {canon_phone}  {url[:60]}")
            else:
                lines.append(f"  {label:12s} ok ({phone})  {url[:60]}")
        else:
            lines.append(f"  {label:12s} found (phone unverifiable)  {url[:60]}")
        results[key] = entry

    if not dry_run:
        rows = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                   "&provider=eq.citations&select=id,connection_metadata",
                   prefer="return=representation") or []
        if rows:
            md = rows[0].get("connection_metadata") or {}
            existing_urls = md.get("citation_urls") or {}
            # never clobber a URL a human already entered
            merged = {**urls, **{k: v for k, v in existing_urls.items() if v}}
            md["citation_urls"] = merged
            md["nap_audit"] = results
            _sb("PATCH", f"/rest/v1/user_integrations?id=eq.{rows[0]['id']}",
                {"connection_metadata": md})
        else:
            _sb("POST", "/rest/v1/user_integrations", {
                "client_id": cid, "provider": "citations", "status": "active",
                "connection_metadata": {"citation_urls": urls, "nap_audit": results}})
    found = sum(1 for r in results.values() if r.get("status") in ("found", "discrepancy"))
    disc = sum(1 for r in results.values() if r.get("status") == "discrepancy")
    lines.append(f"  -> {found}/{len(PLATFORMS)} found, {disc} discrepancy(ies)"
                 + (" [dry-run, not saved]" if dry_run else " [saved to app]"))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(audit(a.slug, a.dry_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
