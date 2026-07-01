#!/usr/bin/env python3
"""Google AI Overviews tracker — is the client cited in Google's AI Overview?

Google shows AI Overviews mainly for INFORMATIONAL queries (cost / process /
how-to), where the cited references are often restoration-company blogs — a real
"get cited" opportunity that is distinct from the map pack (geo-grid, commercial)
and the chat LLMs (ai_search_scan). For each query this calls
serp/google/organic/live/advanced with load_async_ai_overview, finds the
`ai_overview` item, and records whether the client's domain is among its
references.

Rows are written to marketing_ai_search_scans with engine='google_ai', so they
appear in the app's AI Search tab (cyan "Google AI" chip) next to
ChatGPT/Gemini/Perplexity/Claude — no app change needed. Writes by default;
--dry-run to preview. ~$0.004-0.006 per query.

Usage:
  python3 scripts/google_aio_scan.py --slug narestco --dry-run
  python3 scripts/google_aio_scan.py --slug narestco
  python3 scripts/google_aio_scan.py --all
"""
from __future__ import annotations
import argparse, base64, json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import geogrid_scan as gs                                   # load_dfs_creds()
from geogrid_store import COMPANY_MAP
from ai_search_scan import client_identity, _domain, DIRECTORY_DOMAINS, _sb_insert

SERP_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"

# Evergreen informational queries that reliably trigger a (national) AI Overview
# AND commonly cite restoration companies — the real "get cited" opportunity.
GENERIC_INFO = [
    "how much does mold removal cost",
    "does homeowners insurance cover water damage",
    "is black mold dangerous to your health",
    "what to do after water damage in your home",
    "how to get rid of black mold",
    "does water damage cause mold",
    "signs of water damage in walls",
]


def _auth() -> str:
    u, p = gs.load_dfs_creds()
    return base64.b64encode(f"{u}:{p}".encode()).decode()


def build_queries(ident: dict) -> list[dict]:
    """Informational queries most likely to (a) trigger an AI Overview and
    (b) cite restoration companies: national cost questions (per service) + evergreen
    how-to. AI Overviews are a national/informational surface — local ("in {city}")
    queries return the map pack, not an AIO — so these are tracked nationally."""
    svcs = [s.replace("-", " ") for s in ident.get("services", [])[:3]]

    out: list[dict] = []
    for svc in svcs:
        out.append({"query": f"how much does {svc} cost", "location": "", "region": "United States"})
    for q in GENERIC_INFO:
        out.append({"query": q, "location": "", "region": "United States"})

    seen, dedup = set(), []
    for q in out:
        k = q["query"].lower()
        if k not in seen:
            seen.add(k); dedup.append(q)
    return dedup


def scan_query(auth: str, keyword: str, region: str):
    body = [{"keyword": keyword, "language_code": "en", "location_name": region,
             "depth": 10, "load_async_ai_overview": True}]
    req = urllib.request.Request(SERP_URL, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    task = (resp.get("tasks") or [{}])[0]
    cost = float(task.get("cost") or 0.0)
    items = ((task.get("result") or [{}])[0] or {}).get("items") or []
    aio = next((it for it in items if it.get("type") == "ai_overview"), None)
    return aio, cost


def run_for(slug: str, auth: str, dry_run: bool) -> float:
    cid = COMPANY_MAP.get(slug)
    if not cid:
        sys.stderr.write(f"  skip {slug}: no company_id\n"); return 0.0
    ident = client_identity(slug)
    domain = ident.get("domain") or ""
    queries = build_queries(ident)
    now = datetime.now(timezone.utc).isoformat()
    print(f"\n=== Google AI Overviews — {slug} ({domain or '?'}) — {len(queries)} queries ===")
    if dry_run:
        for q in queries:
            print(f"  {q['query']}")
        print("  (dry-run — no API calls, no writes)")
        return 0.0

    rows, spend, aio_count = [], 0.0, 0
    for q in queries:
        try:
            aio, cost = scan_query(auth, q["query"], q["region"])
        except Exception as e:
            sys.stderr.write(f"  WARN '{q['query']}': {str(e)[:100]}\n"); continue
        spend += cost
        if not aio:
            print(f"  (no AI Overview)  {q['query']}"); continue
        aio_count += 1
        refs = aio.get("references") or []
        ref_domains = [d for d in (_domain(r.get("url") or r.get("domain") or "") for r in refs) if d]
        cited = bool(domain) and domain in ref_domains
        rank = (ref_domains.index(domain) + 1) if cited else None
        sources = [{"domain": d, "directory": d in DIRECTORY_DOMAINS} for d in ref_domains]
        rows.append({
            "company_id": cid, "rank_ai_slug": slug, "engine": "google_ai",
            "query": q["query"], "location": q["location"], "cited": cited,
            "client_rank": rank, "competitors": None, "cited_sources": sources,
            "answer_excerpt": (aio.get("markdown") or "")[:600], "scanned_at": now,
        })
        print(f"  [{'CITED #' + str(rank) if cited else 'not cited'}]  {q['query']}  ({len(ref_domains)} sources)")

    print(f"  AI Overviews present: {aio_count}/{len(queries)} | cost ${spend:.3f}")
    if rows:
        _sb_insert(rows)
        print(f"  wrote {len(rows)} rows to marketing_ai_search_scans (engine=google_ai)")
    return spend


def main() -> int:
    ap = argparse.ArgumentParser(description="Track Google AI Overview citations")
    ap.add_argument("--slug", help="Run one client")
    ap.add_argument("--all", action="store_true", help="Every client in company_map.json")
    ap.add_argument("--dry-run", action="store_true", help="Preview queries; no API calls or writes")
    args = ap.parse_args()
    if not args.slug and not args.all:
        ap.error("pass --slug <slug> or --all")
    auth = _auth()
    total = 0.0
    for slug in (list(COMPANY_MAP.keys()) if args.all else [args.slug]):
        try:
            total += run_for(slug, auth, args.dry_run)
        except Exception as e:
            sys.stderr.write(f"  FAIL {slug}: {str(e)[:150]}\n")
    print(f"\nTotal DataForSEO spend: ${total:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
