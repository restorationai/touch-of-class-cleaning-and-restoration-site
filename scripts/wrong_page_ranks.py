#!/usr/bin/env python3
"""wrong_page_ranks.py — the monthly "wrong page ranks" check (SEO queue #4).

THE IDEA (from the structure-audit methodology our stack was built on): find
queries where Google ranks us at positions 5-30 but the RANKING PAGE is the
homepage or a blog post instead of the dedicated money page (service page or
city-service page). Each hit is either an internal-linking fix (the money
page exists but the wrong page outranks it) or a build gap (no money page
exists for a query with real demand). Fixing these is the cheapest ranking
win available: the demand is proven by our own impressions.

DATA: Google Search Console Search Analytics (query+page, last 28 days) via
the agency OAuth token gsc_setup.py provisioned. Free, and it is our own
measured demand, not a third-party estimate.

CLASSIFICATION per (query, page) row @ position 5-30 with impressions >=
MIN_IMPRESSIONS:
  - the page is / or /blog/* AND the query names a service we offer
    (optionally + a city we serve):
      * a matching /services/x/ or /service-areas/city/x/ page EXISTS
          -> WRONG_PAGE (link/anchor fix: point internal links + anchors at
             the money page)
      * no matching page
          -> BUILD_GAP (candidate for the content queue)
  - everything else is ignored (right page ranking, or non-service query).

OUTPUT: clients/{slug}/seo/wrong-page-ranks-YYYY-MM.md (full table) + one
summary line per client on stdout; --notes files ONE consolidated
[TODO-SANTINO] ops note per client when hits exist (deduped by month marker).

Usage:
  python3 scripts/wrong_page_ranks.py --slug narestco
  python3 scripts/wrong_page_ranks.py --all [--notes]
Runs monthly from monthly-reports.yml.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS = ROOT / "clients"
sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import requests  # noqa: E402
from gsc_setup import _load_credentials  # noqa: E402
from index_watchdog import live_slugs, load_record, company_id_for  # noqa: E402

MIN_IMPRESSIONS = 20

# Research-intent markers: a BLOG post ranking for a query carrying these is
# the RIGHT page (that is what the blog is for) — only money-intent queries
# stuck on the homepage/blog are findings. (Live-test lesson, narestco:
# "average insurance payout for water damage" ranking the payout blog post
# is a win, not a wrong page.)
_INFO_MARKERS = {"how", "what", "why", "when", "should", "average", "vs",
                 "diy", "tips", "signs", "payout", "claim", "much", "long",
                 "who", "can", "does", "guide"}
POS_LO, POS_HI = 5.0, 30.0
ROW_LIMIT = 2500
MONTH = date.today().strftime("%Y-%m")

# generic filler that appears inside queries but never identifies a service
_STOP = {"near", "me", "best", "top", "company", "companies", "services",
         "service", "cost", "price", "the", "in", "for", "a", "of", "and"}
# tokens that never indicate an unserved locality
_NON_LOCALITY = _STOP | {"emergency", "house", "home", "residential",
                         "commercial", "24", "7", "local", "pro",
                         "professional", "expert", "experts",
                         "ut", "ca", "wa", "nv", "tx", "fl", "nj", "pa",
                         "sd", "nc", "ms", "ma", "utah", "california",
                         "washington", "nevada", "texas", "florida"}


def _tok(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in _STOP}


def _plan_input(slug: str) -> dict:
    for c in (CLIENTS / slug / "plan" / "plan-input.json",
              CLIENTS / slug / "plan-input.json"):
        if c.exists():
            try:
                return json.loads(c.read_text())
            except json.JSONDecodeError:
                pass
    return {}


def _service_index(slug: str) -> tuple[dict, dict, str | None]:
    """(service_slug -> tokens, city_slug -> tokens, primary_city_slug)."""
    pi = _plan_input(slug)
    svc, city = {}, {}
    primary = next((a.get("slug") for a in pi.get("service_areas") or []
                    if isinstance(a, dict) and a.get("primary")), None)
    for s in pi.get("services") or []:
        sslug = s.get("slug") if isinstance(s, dict) else str(s)
        name = (s.get("display_name") if isinstance(s, dict) else None) or \
            sslug.replace("-", " ")
        svc[sslug] = _tok(name) | _tok(sslug.replace("-", " "))
    for a in pi.get("service_areas") or []:
        aslug = a.get("slug") if isinstance(a, dict) else str(a)
        cname = (a.get("city") if isinstance(a, dict) else None) or aslug
        city[aslug] = _tok(cname)
    return svc, city, primary


def _site_paths(slug: str) -> set[str]:
    """Every content path the built site actually has (from src/content)."""
    site = ROOT / "sites" / slug / "src" / "content"
    out: set[str] = set()
    for coll, prefix in (("services", "/services/"),
                         ("serviceAreas", "/service-areas/")):
        d = site / coll
        if d.is_dir():
            for f in d.glob("*.md"):
                out.add(prefix + f.stem + "/")
    d = site / "locations"
    if d.is_dir():
        for f in d.glob("*.md"):
            if "__" in f.stem:
                a, s = f.stem.split("__", 1)
                out.add(f"/service-areas/{a}/{s}/")
    return out


def fetch_rows(token: str, prop: str) -> list[dict]:
    end = date.today() - timedelta(days=2)     # GSC data lags ~2 days
    start = end - timedelta(days=28)
    r = requests.post(
        "https://www.googleapis.com/webmasters/v3/sites/"
        + requests.utils.quote(prop, safe="") + "/searchAnalytics/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"startDate": start.isoformat(), "endDate": end.isoformat(),
              "dimensions": ["query", "page"], "rowLimit": ROW_LIMIT},
        timeout=60)
    if r.status_code == 403:
        return []          # property not accessible — report upstream
    r.raise_for_status()
    return r.json().get("rows", [])


def classify(slug: str, rows: list[dict]) -> list[dict]:
    svc_idx, city_idx, primary_city = _service_index(slug)
    paths = _site_paths(slug)
    hits = []
    for row in rows:
        pos = row.get("position", 0)
        imp = row.get("impressions", 0)
        if not (POS_LO <= pos <= POS_HI) or imp < MIN_IMPRESSIONS:
            continue
        query, page = row["keys"][0], row["keys"][1]
        path = "/" + page.split("/", 3)[-1] if page.count("/") >= 3 else "/"
        if not (path == "/" or path.startswith("/blog/")):
            continue                        # a money page is ranking — fine
        q = _tok(query)
        raw_words = set(re.findall(r"[a-z0-9]+", query.lower()))
        if path.startswith("/blog/") and raw_words & _INFO_MARKERS:
            continue        # research query on a blog post = the right page
        m_svc = max(svc_idx.items(),
                    key=lambda kv: len(kv[1] & q) / (len(kv[1]) or 1),
                    default=(None, set()))
        if not m_svc[0] or len(m_svc[1] & q) / (len(m_svc[1]) or 1) < 0.5:
            continue                        # query doesn't name a service
        m_city = next((c for c, toks in city_idx.items()
                       if toks and toks <= q), None)
        # tokens the service match didn't consume, minus generic/state
        # words: leftovers on a city-less match usually NAME AN UNSERVED
        # TOWN — that is expansion demand, not a linking bug (Home Pride
        # live-test: 50+ "fire damage restoration {town} ut" queries from
        # towns outside the 12-area ring, all ranking the homepage).
        leftover = q - m_svc[1] - _NON_LOCALITY
        if not m_city and leftover:
            hits.append({
                "query": query, "impressions": imp,
                "position": round(pos, 1), "ranking_page": path,
                "expected_page": f"(unserved area: {' '.join(sorted(leftover))})",
                "kind": "AREA_DEMAND",
            })
            continue
        if m_city and m_city == primary_city:
            # HOME-CITY RULE (2026-08-18 architecture): the home page targets
            # "{trade} in {home city}" and the main service page targets
            # "{service} in {home city}"; there IS no home-city service-area
            # page by design. "/" ranking a home-city query is correct —
            # never re-recommend the cannibal pages we removed.
            if path == "/":
                continue
            expected = f"/services/{m_svc[0]}/"
        elif m_city:
            expected = f"/service-areas/{m_city}/{m_svc[0]}/"
        else:
            expected = f"/services/{m_svc[0]}/"
        hits.append({
            "query": query, "impressions": imp, "position": round(pos, 1),
            "ranking_page": path, "expected_page": expected,
            "kind": "WRONG_PAGE" if expected in paths else "BUILD_GAP",
        })
    hits.sort(key=lambda h: -h["impressions"])
    return hits


def report(slug: str, hits: list[dict], prop: str) -> Path:
    out = CLIENTS / slug / "seo"
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"wrong-page-ranks-{MONTH}.md"
    lines = [f"# Wrong-page ranks — {slug} — {MONTH}",
             f"Property: {prop} | window: last 28d | "
             f"filter: pos {POS_LO:g}-{POS_HI:g}, impressions >= {MIN_IMPRESSIONS}",
             ""]
    if not hits:
        lines.append("No hits: every qualifying service query already ranks "
                     "with its money page.")
    else:
        lines += ["| query | imp | pos | ranking page | expected page | kind |",
                  "|---|---|---|---|---|---|"]
        lines += [f"| {h['query']} | {h['impressions']} | {h['position']} "
                  f"| {h['ranking_page']} | {h['expected_page']} | {h['kind']} |"
                  for h in hits]
        demand = {}
        for h in hits:
            if h["kind"] == "AREA_DEMAND":
                key = h["expected_page"]
                d = demand.setdefault(key, {"imp": 0, "n": 0})
                d["imp"] += h["impressions"]
                d["n"] += 1
        if demand:
            lines += ["", "## Unserved-area demand (ring-expansion candidates)",
                      "", "| area tokens | queries | impressions |", "|---|---|---|"]
            for k, d in sorted(demand.items(), key=lambda kv: -kv[1]["imp"]):
                lines.append(f"| {k} | {d['n']} | {d['imp']} |")
        lines += ["", "WRONG_PAGE = money page exists; strengthen internal "
                  "links/anchors toward it.",
                  "BUILD_GAP = no money page; content-queue candidate.",
                  "AREA_DEMAND = real impressions from a town outside the "
                  "configured ring; consider adding it to the service areas."]
    p.write_text("\n".join(lines) + "\n")
    return p


def file_note(slug: str, hits: list[dict]) -> str:
    import os
    cid = company_id_for(slug)
    if not cid:
        return "no company id"
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_SERVICE_KEY"))
    hdr = {"apikey": key, "Authorization": f"Bearer {key}",
           "Content-Type": "application/json"}
    marker = f"[WRONG-PAGE-RANKS {MONTH}]"
    existing = requests.get(
        f"{url}/rest/v1/marketing_ops_notes?company_id=eq.{cid}"
        f"&status=eq.open&select=id,body", headers=hdr, timeout=30).json()
    if any(marker in (n.get("body") or "") for n in existing):
        return "note exists"
    top = hits[:5]
    body = (f"[TODO-SANTINO] {marker} {len(hits)} service quer"
            f"{'y' if len(hits) == 1 else 'ies'} rank at pos 5-30 with the "
            "WRONG page (homepage/blog instead of the money page). Top:\n"
            + "\n".join(f"- \"{h['query']}\" ({h['impressions']} imp, pos "
                        f"{h['position']}) ranks {h['ranking_page']} — "
                        f"expected {h['expected_page']} [{h['kind']}]"
                        for h in top)
            + f"\nFull table: clients/{slug}/seo/wrong-page-ranks-{MONTH}.md")
    requests.post(f"{url}/rest/v1/marketing_ops_notes", headers=hdr,
                  json={"company_id": cid, "status": "open", "body": body},
                  timeout=30)
    return "note filed"


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--notes", action="store_true",
                    help="file one consolidated ops note per client with hits")
    args = ap.parse_args()

    creds = _load_credentials()
    token = creds.token
    slugs = [args.slug] if args.slug else live_slugs()
    total = 0
    for slug in slugs:
        rec = load_record(slug)
        prop = ((rec.get("gsc") or {}).get("property_url")
                or (f"sc-domain:{rec['domain']}" if rec.get("domain") else None))
        if not prop:
            print(f"  {slug}: no GSC property — skipped")
            continue
        rows = fetch_rows(token, prop)
        if not rows:
            print(f"  {slug}: no GSC rows (not provisioned / no data yet)")
            continue
        hits = classify(slug, rows)
        p = report(slug, hits, prop)
        wrong = sum(1 for h in hits if h["kind"] == "WRONG_PAGE")
        gaps = sum(1 for h in hits if h["kind"] == "BUILD_GAP")
        demand = sum(1 for h in hits if h["kind"] == "AREA_DEMAND")
        note = file_note(slug, hits) if (args.notes and hits) else "-"
        print(f"  {slug}: {len(rows)} rows -> {wrong} wrong-page, "
              f"{gaps} build-gap, {demand} area-demand "
              f"({p.name}, note: {note})")
        total += len(hits)
    print(f"\n{total} total hit(s) across {len(slugs)} client(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
