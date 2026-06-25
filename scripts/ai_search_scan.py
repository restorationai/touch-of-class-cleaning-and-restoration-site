#!/usr/bin/env python3
"""
ai_search_scan.py — AI-search visibility collector (DataForSEO ChatGPT LLM, web search).

For one client, runs the client's money queries through ChatGPT (with web search) and
records, per query: is the client cited?, which sources the answer cited (the GEO
optimization targets), and an excerpt. Stores to Supabase marketing_ai_search_scans
(the app's "AI Search" view reads it; the strategist weights it).

Cost: ~$0.05-0.08 per query (gpt-4o + web_search). Scoped to a few money queries per
client via --limit. Pay-as-you-go, no monthly minimum (unlike the LLM Mentions API).

Usage:
    python3 scripts/ai_search_scan.py --slug narestco            # one client
    python3 scripts/ai_search_scan.py --all --limit 6            # every active client
    python3 scripts/ai_search_scan.py --slug narestco --dry-run  # print, don't store

Env: DATAFORSEO_USERNAME/PASSWORD (or ~/.claude.json), SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass
from geogrid_scan import load_dfs_creds   # noqa: E402  reuse the DataForSEO creds loader

DFS_LLM_URL = "https://api.dataforseo.com/v3/ai_optimization/chat_gpt/llm_responses/live"
MODEL = "gpt-4o"
# Directory/aggregator domains that aren't competitors — useful as GEO targets, flagged separately.
DIRECTORY_DOMAINS = {"bbb.org", "yelp.com", "expertise.com", "angi.com", "thumbtack.com",
                     "reddit.com", "google.com", "facebook.com", "nextdoor.com", "houzz.com"}


def company_id_for(slug: str) -> str | None:
    rec = ROOT / "clients" / f"{slug}.json"
    if rec.exists():
        cid = json.loads(rec.read_text()).get("company_id")
        if cid:
            return cid
    cmap = ROOT / "clients" / "company_map.json"
    return json.loads(cmap.read_text()).get(slug) if cmap.exists() else None


def client_identity(slug: str) -> dict:
    rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
    pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
    brand = pi.get("brand", {})
    domain = (rec.get("domain") or "").replace("www.", "").lower()
    return {"domain": domain, "name": (brand.get("display_name") or "").lower(),
            "services": pi.get("services", []), "areas": pi.get("service_areas", [])}


def money_queries(ident: dict, limit: int) -> list[str]:
    svc_labels = [s.replace("-", " ") for s in ident["services"][:3]]
    areas = ident["areas"]
    primary = next((a for a in areas if a.get("primary")), areas[0] if areas else None)
    others = [a for a in areas if not a.get("primary")][:1]
    cities = [c for c in ([primary] + others) if c]
    qs = []
    for svc in svc_labels:
        for c in cities:
            qs.append(f"best {svc} company in {c['city']}, {c['state']}")
    if cities:
        qs.append(f"{svc_labels[0]} near me {cities[0]['city']} {cities[0]['state']}")
    # de-dup, cap
    seen, out = set(), []
    for q in qs:
        if q not in seen:
            seen.add(q); out.append(q)
    return out[:limit]


def _walk(obj, texts, urls):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "text" and isinstance(v, str):
                texts.append(v)
            if k in ("url", "domain") and isinstance(v, str):
                urls.append(v)
            _walk(v, texts, urls)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, texts, urls)


def _domain(u: str) -> str:
    try:
        host = urlparse(u if "://" in u else "https://" + u).netloc or u
    except Exception:
        host = u
    return host.replace("www.", "").lower().split("/")[0]


def run_query(auth: str, query: str) -> dict:
    body = [{"user_prompt": query[:500], "model_name": MODEL, "web_search": True,
             "max_output_tokens": 800}]
    req = urllib.request.Request(DFS_LLM_URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read())
    task = (d.get("tasks") or [{}])[0]
    res = (task.get("result") or [{}])[0]
    cost = d.get("cost") or 0
    texts, urls = [], []
    _walk(res.get("items", []), texts, urls)
    answer = " ".join(t.strip() for t in texts if t.strip())
    domains = []
    for u in urls:
        dmn = _domain(u)
        if dmn and "." in dmn and dmn not in domains:
            domains.append(dmn)
    return {"answer": answer, "domains": domains, "cost": cost}


def _sb_insert(rows: list[dict]) -> None:
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/marketing_ai_search_scans"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req = urllib.request.Request(url, data=json.dumps(rows).encode(), method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    urllib.request.urlopen(req)


def run_for(slug: str, auth: str, limit: int, dry_run: bool) -> float:
    cid = company_id_for(slug)
    if not cid:
        print(f"  skip {slug}: no company_id", file=sys.stderr); return 0.0
    ident = client_identity(slug)
    queries = money_queries(ident, limit)
    now = datetime.now(timezone.utc).isoformat()
    rows, spend = [], 0.0
    print(f"\n=== AI-search scan — {slug} ({cid}) — {len(queries)} queries ===")
    for q in queries:
        try:
            r = run_query(auth, q)
        except urllib.error.HTTPError as e:
            print(f"  ! {q[:50]}: HTTP {e.code}", file=sys.stderr); continue
        spend += float(r["cost"])
        ans_l = r["answer"].lower()
        cited = (ident["domain"] and ident["domain"] in r["domains"]) or \
                (ident["name"] and ident["name"] in ans_l)
        sources = [{"domain": d, "directory": any(d.endswith(x) for x in DIRECTORY_DOMAINS)}
                   for d in r["domains"][:12]]
        print(f"  [{'CITED' if cited else ' --- '}] {q}")
        rows.append({
            "company_id": cid, "rank_ai_slug": slug, "engine": "chatgpt", "query": q,
            "cited": bool(cited), "client_rank": None,
            "competitors": None, "cited_sources": sources,
            "answer_excerpt": r["answer"][:400], "scanned_at": now,
        })
    print(f"  spend: ${spend:.3f} | cited in {sum(1 for x in rows if x['cited'])}/{len(rows)}")
    if not dry_run and rows:
        _sb_insert(rows)
        print(f"  stored {len(rows)} rows.")
    return spend


def main() -> int:
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--slug")
    grp.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=6, help="max money queries per client (cost control)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        print("ERROR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required.", file=sys.stderr); return 1
    u, p = load_dfs_creds()
    auth = base64.b64encode(f"{u}:{p}".encode()).decode()
    slugs = list(json.loads((ROOT / "clients" / "company_map.json").read_text())) if args.all else [args.slug]
    total = 0.0
    for s in slugs:
        total += run_for(s, auth, args.limit, args.dry_run)
    print(f"\nTOTAL DataForSEO spend: ${total:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
