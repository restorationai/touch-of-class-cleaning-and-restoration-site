#!/usr/bin/env python3
"""Phase 1 — the demand-driven AI-search query engine.

Answers "which services should we chase in AI search, ranked by how much people
ACTUALLY ask AI about them?" using DataForSEO's AI-optimization data:

  * ai_keyword_data/keywords_search_volume  -> real AI search volume per keyword
    (this is how we discovered mold removal ~16k/mo vs water damage ~1.1k/mo).
  * llm_mentions/top_domains                -> the sources AI pulls from for the
    client's top service -> get-listed / content-placement targets.

Writes the ranked opportunities into marketing_action_plan so they appear in the
app (AI Search tab) where a manager can prioritize them:
  * action_type='ai_keyword'  -> "Target '<kw>' in AI search — N searches/mo"
  * action_type='get_listed'  -> AI-source domains to earn a mention on

Idempotent via action_key (matches the app's SHA-1 scheme). Dry-run by default.

Usage:
  python3 scripts/ai_keyword_planner.py --slug narestco           # dry-run
  python3 scripts/ai_keyword_planner.py --slug narestco --write   # to Action Plan
  python3 scripts/ai_keyword_planner.py --all --write             # monthly cron
"""
from __future__ import annotations
import argparse, base64, hashlib, json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import geogrid_scan as gs
from geogrid_store import sb_client, COMPANY_MAP

DFS = "https://api.dataforseo.com"

# High-value restoration search terms to always price-check, so we catch demand
# even when it isn't an exact service name on the client's record.
CORE_KEYWORDS = [
    "water damage restoration", "water damage restoration near me", "water damage repair",
    "mold removal", "mold remediation", "black mold removal",
    "fire damage restoration", "smoke damage restoration",
    "flood cleanup", "basement flood cleanup", "sewage cleanup",
    "storm damage restoration", "emergency water damage restoration",
    "24 hour water damage restoration", "ceiling water damage repair",
    "crawl space water damage", "burst pipe cleanup", "biohazard cleanup",
]

# Don't propose getting "listed" on these — infra, competitors handled elsewhere.
JUNK_SOURCES = {"vertexaisearch.cloud.google.com", "google.com", "gstatic.com", "bing.com",
                "en.wikipedia.org", "wikipedia.org", "servpro.com", "puroclean.com",
                "servicemasterrestore.com", "youtube.com", "amazon.com"}


def _auth() -> str:
    u, p = gs.load_dfs_creds()
    return base64.b64encode(f"{u}:{p}".encode()).decode()


def _post(path: str, body: list) -> dict:
    req = urllib.request.Request(DFS + path, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Basic {_auth()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def action_key(action_type: str, target: str) -> str:
    return hashlib.sha1(f"{action_type}|{target}".encode()).hexdigest()[:16]


def candidate_keywords(services: list[str]) -> list[str]:
    seen, out = set(), []
    for kw in [*(s.lower().strip() for s in services or []), *CORE_KEYWORDS]:
        if kw and kw not in seen:
            seen.add(kw); out.append(kw)
    return out[:80]  # keywords_search_volume allows up to 1000; we stay lean


def ai_volumes(keywords: list[str]) -> dict[str, dict]:
    """keyword -> {volume, trend} using AI search volume + its 12-mo history."""
    resp = _post("/v3/ai_optimization/ai_keyword_data/keywords_search_volume/live",
                 [{"keywords": keywords, "language_code": "en", "location_name": "United States"}])
    out: dict[str, dict] = {}
    for task in resp.get("tasks") or []:
        for res in task.get("result") or []:
            for it in (res.get("items") or []) if isinstance(res, dict) else []:
                if not isinstance(it, dict) or "keyword" not in it:
                    continue
                vol = it.get("ai_search_volume")
                if not vol:
                    continue
                # ai_monthly_searches is a list of {year, month, ai_search_volume}.
                months = sorted(it.get("ai_monthly_searches") or [],
                                key=lambda m: (m.get("year", 0), m.get("month", 0)))
                trend = ""
                if len(months) >= 4:
                    recent = months[-1].get("ai_search_volume") or 0
                    prior = months[-4].get("ai_search_volume") or 0
                    if recent > prior * 1.1:
                        trend = " ▲ rising"
                    elif recent < prior * 0.9:
                        trend = " ▼ cooling"
                out[it["keyword"].lower()] = {"volume": int(vol), "trend": trend}
    return out


def top_source_domains(service: str) -> list[dict]:
    """Domains AI pulls from for a service -> get-listed / placement targets."""
    resp = _post("/v3/ai_optimization/llm_mentions/top_domains/live",
                 [{"target": [{"keyword": service}], "platform": "chat_gpt",
                   "location_name": "United States", "language_code": "en", "items_list_limit": 10}])
    doms: dict[str, int] = {}
    for task in resp.get("tasks") or []:
        for res in task.get("result") or []:
            tot = (res or {}).get("total") or {}
            for group in ("sources_domain", "search_results_domain"):
                for el in tot.get(group) or []:
                    dom = (el.get("key") or "").lower().replace("www.", "")
                    if dom and dom not in JUNK_SOURCES:
                        doms[dom] = doms.get(dom, 0) + int(el.get("mentions") or 0)
    return [{"domain": d, "mentions": m} for d, m in sorted(doms.items(), key=lambda x: -x[1])[:8]]


def tracked_keywords(sb, cid: str) -> set[str]:
    r = (sb.table("marketing_ai_search_scans").select("query")
         .eq("company_id", cid).order("scanned_at", desc=True).limit(300).execute())
    return {(row.get("query") or "").lower() for row in (r.data or [])}


def build(slug: str, write: bool, sb=None) -> None:
    sb = sb or sb_client()
    cid = COMPANY_MAP.get(slug)
    if not cid:
        sys.stderr.write(f"  skip {slug}: no company_id in company_map.json\n")
        return
    comp = (sb.table("companies").select("services").eq("id", cid).limit(1).execute().data or [{}])[0]
    services = comp.get("services") or []
    print(f"client: {slug}  company_id: {cid}  services: {len(services)}\n")

    vols = ai_volumes(candidate_keywords(services))
    if not vols:
        print("  no AI search-volume data returned."); return
    ranked = sorted(vols.items(), key=lambda kv: -kv[1]["volume"])
    tracked = tracked_keywords(sb, cid)

    print("AI SEARCH DEMAND — your services ranked by how often people ask AI:")
    opps = []
    for kw, d in ranked:
        is_tracked = any(kw in q for q in tracked)
        flag = "tracked" if is_tracked else "NOT tracked"
        print(f"  {d['volume']:>7,}/mo{d['trend']:<10}  {kw:36} [{flag}]")
        opps.append({"keyword": kw, **d, "tracked": is_tracked})

    # Source targets from the single highest-demand service.
    top_kw = ranked[0][0]
    try:
        sources = top_source_domains(top_kw)
    except Exception as e:
        sys.stderr.write(f"  top_domains failed: {e}\n"); sources = []
    if sources:
        print(f"\nAI-source domains for '{top_kw}' (get listed / earn a mention):")
        for s in sources:
            print(f"  {s['mentions']:>4} mentions  {s['domain']}")

    if not write:
        print(f"\n(dry-run) {len(opps)} keyword opportunities. Re-run with --write to add to the Action Plan.")
        return

    existing = {r["action_key"] for r in (sb.table("marketing_action_plan").select("action_key")
                .eq("company_id", cid).execute().data or []) if r.get("action_key")}
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    # Top keyword opportunities (skip ones already tracked or tiny volume).
    for i, o in enumerate([o for o in opps if not o["tracked"] and o["volume"] >= 100][:10]):
        key = action_key("ai_keyword", o["keyword"])
        if key in existing:
            continue
        vol = o["volume"]
        sb.table("marketing_action_plan").insert({
            "company_id": cid, "rank_ai_slug": slug, "action_type": "ai_keyword",
            "assigned_system": "s1", "title": f"Target “{o['keyword']}” in AI search",
            "rationale": f"{vol:,} AI searches/mo{o['trend']} — not yet tracked. High-demand topic to create content for and track.",
            "target": o["keyword"], "impact": "high" if vol >= 3000 else "medium" if vol >= 500 else "low",
            "effort": "medium", "status": "planned", "pinned": False,
            "priority": 1 if vol >= 3000 else 2 if vol >= 500 else 3,
            "action_key": key, "source_run_at": now,
        }).execute()
        added += 1
    # AI-source get-listed targets.
    for s in sources:
        key = action_key("get_listed", s["domain"])
        if key in existing:
            continue
        sb.table("marketing_action_plan").insert({
            "company_id": cid, "rank_ai_slug": slug, "action_type": "get_listed",
            "assigned_system": "s3", "title": f"Get listed on {s['domain']}",
            "rationale": f"AI pulls from {s['domain']} for “{top_kw}” ({s['mentions']} mentions) — earn a listing/mention there.",
            "target": s["domain"], "impact": "medium", "effort": "low", "status": "planned",
            "pinned": False, "priority": 2, "action_key": key, "source_run_at": now,
        }).execute()
        added += 1
    print(f"\nwrote {added} new opportunities to the Action Plan ({len(existing)} items already existed).")

    # Work ledger (fail-open): one run-summary line item per client per
    # research pass — the Action Plan rows above are recommendations, not a
    # record that the research itself happened.
    from work_log import work_log
    work_log(cid, "keyword-research", "ai-demand-refresh",
             f"Keyword research refresh: {len(opps)} keywords analyzed for AI "
             f"search demand; {added} new high-opportunity topic(s) added to "
             f"the marketing plan.",
             evidence={"slug": slug, "keywords_analyzed": len(opps),
                       "opportunities_added": added,
                       "top_keyword": ranked[0][0] if ranked else None},
             source="ai_keyword_planner.py")


def main() -> int:
    ap = argparse.ArgumentParser(description="Demand-driven AI-search keyword planner")
    ap.add_argument("--slug", help="Run one client")
    ap.add_argument("--all", action="store_true", help="Every client in company_map.json (for the cron)")
    ap.add_argument("--write", action="store_true", help="Upsert opportunities into marketing_action_plan")
    args = ap.parse_args()
    if not args.slug and not args.all:
        ap.error("pass --slug <slug> or --all")
    sb = sb_client()
    for slug in (list(COMPANY_MAP.keys()) if args.all else [args.slug]):
        try:
            build(slug, args.write, sb=sb)
        except Exception as e:
            sys.stderr.write(f"  FAIL {slug}: {str(e)[:160]}\n")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
