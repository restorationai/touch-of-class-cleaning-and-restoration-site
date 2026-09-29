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
import time
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

# Each engine -> (DataForSEO provider path segment, model_name). All use the same
# /ai_optimization/{provider}/llm_responses/live shape with web_search=true.
ENGINES = {
    "chatgpt":    ("chat_gpt",   "gpt-4o"),
    "gemini":     ("gemini",     "gemini-2.5-flash"),
    "perplexity": ("perplexity", "sonar"),
    "claude":     ("claude",     "claude-haiku-4-5"),   # tracked by default for fuller coverage
}
DEFAULT_ENGINES = ["chatgpt", "gemini", "perplexity", "claude"]
LLM_URL = "https://api.dataforseo.com/v3/ai_optimization/{provider}/llm_responses/live"
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


DEAD_PREFIXES = ("mcc-restoration", "mold-solutionz")   # dead clients, never scanned


def _unscannable(slug: str) -> str | None:
    """Reason this client can't produce money queries (else None)."""
    if slug.startswith(DEAD_PREFIXES):
        return "dead client"
    rec = ROOT / "clients" / f"{slug}.json"
    pi = ROOT / "clients" / slug / "plan-input.json"
    if not rec.exists() or not pi.exists():
        return "no client record / plan-input.json yet"
    try:
        p = json.loads(pi.read_text())
    except Exception:  # noqa: BLE001
        return "unreadable plan-input.json"
    if not (p.get("services") and p.get("service_areas")):
        return "plan-input has no services/service_areas yet"
    return None


def client_identity(slug: str) -> dict:
    rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
    pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
    brand = pi.get("brand", {})
    domain = (rec.get("domain") or "").replace("www.", "").lower()
    return {"domain": domain, "name": (brand.get("display_name") or "").lower(),
            "services": pi.get("services", []), "areas": pi.get("service_areas", [])}


def money_queries(ident: dict, limit: int) -> list[dict]:
    """Up to `limit` money questions spanning top services x top cities.
    Interleaved (city-major) so the set covers multiple locations rather than
    exhausting one city first. Returns dicts: {query, city, state, location}."""
    svc_labels = [s.replace("-", " ") for s in ident["services"][:4]]
    areas = ident["areas"]
    primary = next((a for a in areas if a.get("primary")), areas[0] if areas else None)
    others = [a for a in areas if not a.get("primary")]
    cities = [c for c in ([primary] + others) if c][:4]
    if not (svc_labels and cities):
        return []

    # Build a city-major grid: for each service, walk every city, so early rows
    # already span locations.
    qs: list[dict] = []
    seen: set[str] = set()

    def add(query: str, c: dict):
        if query not in seen:
            seen.add(query)
            qs.append({"query": query, "city": c["city"], "state": c["state"],
                       "location": f"{c['city']}, {c['state']}"})

    # Anchor with the primary service x primary city, then ONE emergency-phrasing
    # query — how a panicked homeowner actually asks an AI assistant ("my house just
    # flooded... who should I call"). Added early so it survives --limit truncation;
    # the strategist's citation-trend diff treats these as top-value queries.
    p = cities[0]
    add(f"best {svc_labels[0]} company in {p['city']}, {p['state']}", p)
    all_svcs = " ".join(ident["services"])
    if "water" in all_svcs or "flood" in all_svcs:
        add(f"my house just flooded in {p['city']}, {p['state']} — who should I call?", p)
    elif "roof" in all_svcs:
        add(f"my roof is leaking right now in {p['city']}, {p['state']} — who should I call?", p)

    for svc in svc_labels:
        for c in cities:
            add(f"best {svc} company in {c['city']}, {c['state']}", c)
    # one "near me" for the primary service/city (how people actually ask AI)
    if cities:
        add(f"{svc_labels[0]} near me in {cities[0]['city']}, {cities[0]['state']}", cities[0])

    return qs[:limit]


def detect_rank(answer: str, brand_name: str, domain: str) -> int | None:
    """Approximate the client's position in the AI's recommendation.
    1 = top pick; N = listed Nth; None = cited but position unclear (or not cited).
    Heuristics: ordered list entries first, then a 'the best … is X' headline."""
    if not answer:
        return None
    low = answer.lower()
    bn = (brand_name or "").lower().strip()
    droot = (domain or "").split(".")[0].lower()
    def hit(text: str) -> bool:
        t = text.lower()
        return bool((bn and bn in t) or (droot and len(droot) > 3 and droot in t))
    # numbered/bulleted list entries: "1. Name", "1) Name", "**1. Name**", "- **Name**"
    import re as _re
    numbered = _re.findall(r'(?m)^\s*\*{0,2}(\d+)[.)]\s*\*{0,2}([^\n*]{2,90})', answer)
    for num, text in numbered:
        if hit(text):
            return int(num)
    bullets = _re.findall(r'(?m)^\s*[-*•]\s*\*{0,2}([^\n*]{2,90})', answer)
    for i, text in enumerate(bullets, 1):
        if hit(text):
            return i
    # headline pattern: "the best … is X" / brand named in the first ~180 chars
    if bn and bn in low[:180]:
        return 1
    return None


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


def run_query(auth: str, engine: str, query: str) -> dict:
    provider, model = ENGINES[engine]
    body = [{"user_prompt": query[:500], "model_name": model, "web_search": True,
             "max_output_tokens": 800}]
    req = urllib.request.Request(LLM_URL.format(provider=provider), data=json.dumps(body).encode(),
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


def fetch_custom_queries(cid: str, cap: int = 5) -> list[dict]:
    """Operator/client-added queries from the app (guard-railed service x city).
    Returns up to `cap` as {query, location} to merge into the scan."""
    try:
        url = (os.environ["SUPABASE_URL"].rstrip("/") +
               "/rest/v1/marketing_ai_search_custom_queries?select=query,location&company_id=eq." +
               urllib.parse.quote(cid) + "&order=created_at.asc&limit=" + str(cap))
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        req = urllib.request.Request(url, headers={"apikey": key, "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()) or []
    except Exception as e:
        print(f"  (custom queries unavailable: {e})", file=sys.stderr)
        return []


def _sb_insert(rows: list[dict]) -> None:
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/marketing_ai_search_scans"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req = urllib.request.Request(url, data=json.dumps(rows).encode(), method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    urllib.request.urlopen(req)


# Skip tiny ad-hoc runs (validation/tests) so the trend stays clean.
HISTORY_MIN_ROWS = 5


def _sb_history(rows: list[dict], cid: str, slug: str, now: str) -> None:
    """One rollup snapshot per scan run -> marketing_ai_search_history (the trend source)."""
    if len(rows) < HISTORY_MIN_ROWS:
        return
    cited = sum(1 for r in rows if r["cited"])
    top = sum(1 for r in rows if r.get("client_rank") == 1)
    by_engine: dict = {}
    for r in rows:
        e = by_engine.setdefault(r["engine"], {"cited": 0, "total": 0})
        e["total"] += 1
        e["cited"] += 1 if r["cited"] else 0
    snap = {
        "company_id": cid, "rank_ai_slug": slug, "scanned_at": now,
        "total": len(rows), "cited": cited, "top_picks": top,
        "visibility_pct": round(100 * cited / len(rows)) if rows else 0,
        "by_engine": by_engine,
    }
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/marketing_ai_search_history"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req = urllib.request.Request(url, data=json.dumps(snap).encode(), method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"})
    try:
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"  (history snapshot skipped: {e})", file=sys.stderr)


def run_for(slug: str, auth: str, limit: int, engines: list[str], dry_run: bool) -> float:
    cid = company_id_for(slug)
    if not cid:
        print(f"  skip {slug}: no company_id", file=sys.stderr); return 0.0
    ident = client_identity(slug)
    queries = money_queries(ident, limit)
    # merge guard-railed custom queries (service x city) added in the app
    seen_q = {q["query"].lower() for q in queries}
    for c in fetch_custom_queries(cid):
        if c.get("query") and c["query"].lower() not in seen_q:
            queries.append({"query": c["query"], "city": "", "state": "",
                            "location": c.get("location") or ""})
            seen_q.add(c["query"].lower())
    now = datetime.now(timezone.utc).isoformat()
    rows, spend = [], 0.0
    print(f"\n=== AI-search scan — {slug} ({cid}) — {len(queries)} queries x {len(engines)} engines ===")
    if dry_run:
        for q in queries:
            print(f"  [{q['location']}] {q['query']}")
        print(f"  (dry-run — would query {len(engines)} engine(s): {', '.join(engines)}; no API calls, no writes)")
        return 0.0
    for engine in engines:
        eng_cited = 0
        for q in queries:
            try:
                r = run_query(auth, engine, q["query"])
            except urllib.error.HTTPError as e:
                print(f"  ! [{engine}] {q['query'][:46]}: HTTP {e.code}", file=sys.stderr); continue
            spend += float(r["cost"])
            ans_l = r["answer"].lower()
            cited = (ident["domain"] and ident["domain"] in r["domains"]) or \
                    (ident["name"] and ident["name"] in ans_l)
            eng_cited += 1 if cited else 0
            rank = detect_rank(r["answer"], ident["name"], ident["domain"]) if cited else None
            sources = [{"domain": d, "directory": any(d.endswith(x) for x in DIRECTORY_DOMAINS)}
                       for d in r["domains"][:12]]
            rows.append({
                "company_id": cid, "rank_ai_slug": slug, "engine": engine, "query": q["query"],
                "location": q["location"], "cited": bool(cited), "client_rank": rank,
                "competitors": None, "cited_sources": sources,
                "answer_excerpt": r["answer"][:600], "scanned_at": now,
            })
        print(f"  {engine:11} cited {eng_cited}/{len(queries)}")
    print(f"  spend: ${spend:.3f} | cited in {sum(1 for x in rows if x['cited'])}/{len(rows)} (all engines)")
    if not dry_run and rows:
        _sb_insert(rows)
        _sb_history(rows, cid, slug, now)
        print(f"  stored {len(rows)} rows.")
    return spend


def main() -> int:
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--slug")
    grp.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=10, help="max money queries per client (cost control)")
    ap.add_argument("--engines", default=",".join(DEFAULT_ENGINES),
                    help=f"comma-separated engines. available: {','.join(ENGINES)}")
    ap.add_argument("--dry-run", action="store_true")
    # B1 SHARDING (2026-09-17): the fleet run NEVER finished inside the
    # 20-minute step budget — it died mid-alphabet every week since early
    # August, so late-roster clients (RestorationXpress...) had frozen
    # history and the app showed stale 0%s. A shard scans N clients from a
    # durable ops_kv cursor and stops early on the wall-clock budget;
    # Mon+Thu shards of 19 = full fleet every week, every run completing.
    ap.add_argument("--shard", type=int, default=0,
                    help="scan N clients from the saved cursor (0 = all, old behavior)")
    ap.add_argument("--budget-min", type=int, default=0,
                    help="stop early after this many minutes (cursor saves progress)")
    args = ap.parse_args()
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        print("ERROR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required.", file=sys.stderr); return 1
    engines = [e.strip() for e in args.engines.split(",") if e.strip() in ENGINES]
    if not engines:
        print(f"ERROR: no valid engines. available: {','.join(ENGINES)}", file=sys.stderr); return 1
    u, p = load_dfs_creds()
    auth = base64.b64encode(f"{u}:{p}".encode()).decode()
    all_slugs = sorted(json.loads((ROOT / "clients" / "company_map.json").read_text())) \
        if args.all else [args.slug]
    if args.all:
        # 2026-09-29: heartbeat:ai-scan froze on 09-18. Stalest-first put
        # never-scannable clients (dead mold-solutionz, restopros with no
        # plan-input, clients with 0 services/areas) at the FRONT of every
        # shard forever; the first missing file raised FileNotFoundError and
        # killed the whole shard before the heartbeat stamp. Only scannable
        # clients enter the shard now.
        keep = []
        for sl in all_slugs:
            why = _unscannable(sl)
            if why:
                print(f"  skip {sl}: {why}", file=sys.stderr)
            else:
                keep.append(sl)
        all_slugs = keep
    if args.all and args.shard:
        # B3 self-healing order (Santino 2026-09-17: "why not just auto run
        # a new scan?"): every shard scans the STALEST clients first —
        # never-scanned clients lead, then oldest history ascending. An
        # overdue client is therefore always at the front of the very next
        # run; staleness cures itself by construction, no cursor to lose,
        # no manual trigger, no per-visit cost stampede from the app.
        cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
        last: dict[str, str] = {}
        try:
            import urllib.request as _u
            k = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
            req = _u.Request(os.environ["SUPABASE_URL"].rstrip("/")
                             + "/rest/v1/marketing_ai_search_history"
                             "?select=company_id,scanned_at"
                             "&order=scanned_at.desc&limit=2000",
                             headers={"apikey": k, "Authorization": f"Bearer {k}"})
            with _u.urlopen(req, timeout=30) as r:
                for row in json.loads(r.read() or b"[]"):
                    last.setdefault(row["company_id"], row["scanned_at"])
        except Exception as e:
            print(f"  (history fetch failed, alphabetical order: {e})", file=sys.stderr)
        slugs = sorted(all_slugs,
                       key=lambda sl: last.get(cmap.get(sl, ""), ""))[:args.shard]
        print(f"shard: {len(slugs)} stalest client(s) "
              f"({slugs[0]}: last {last.get(cmap.get(slugs[0], ''), 'never')[:10] or 'never'} ...)")
    else:
        slugs = all_slugs
    total, done = 0.0, 0
    t0 = time.monotonic()
    for s in slugs:
        if args.budget_min and (time.monotonic() - t0) > args.budget_min * 60:
            print(f"  budget reached after {done} client(s) — cursor saves the rest")
            break
        try:
            total += run_for(s, auth, args.limit, engines, args.dry_run)
        except Exception as e:  # noqa: BLE001 — one client never kills the shard
            print(f"  {s}: scan failed ({type(e).__name__}: {str(e)[:160]})",
                  file=sys.stderr)
            continue
        done += 1
    if args.all and args.shard and not args.dry_run:
        _sb_set_kv("heartbeat:ai-scan",
                   {"at": datetime.now(timezone.utc).isoformat(),
                    "scanned": done})
    print(f"\nTOTAL DataForSEO spend: ${total:.3f} ({done} client(s))")
    return 0


def _sb_get_kv(key: str) -> dict | None:
    import urllib.request as _u
    k = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req = _u.Request(os.environ["SUPABASE_URL"].rstrip("/")
                     + f"/rest/v1/ops_kv?k=eq.{key}&select=v",
                     headers={"apikey": k, "Authorization": f"Bearer {k}"})
    with _u.urlopen(req, timeout=20) as r:
        rows = json.loads(r.read() or b"[]")
    return rows[0]["v"] if rows else None


def _sb_set_kv(key: str, val: dict) -> None:
    import urllib.request as _u
    k = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req = _u.Request(os.environ["SUPABASE_URL"].rstrip("/")
                     + "/rest/v1/ops_kv?on_conflict=k", method="POST",
                     data=json.dumps({"k": key, "v": val}).encode(),
                     headers={"apikey": k, "Authorization": f"Bearer {k}",
                              "Content-Type": "application/json",
                              "Prefer": "resolution=merge-duplicates"})
    with _u.urlopen(req, timeout=20) as r:
        r.read()


if __name__ == "__main__":
    raise SystemExit(main())
