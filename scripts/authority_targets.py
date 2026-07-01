#!/usr/bin/env python3
"""Build a client's "Get Listed" list — the sites where getting listed / linked
lifts BOTH map-pack + organic rankings (backlinks) AND AI-search citations.

Why this shape (validated against DataForSEO for a local restoration client):
  * Classic link-gap vs *local* competitors yields almost nothing — local shops
    have thin backlink profiles. So we run the gap vs strong NATIONAL players
    (servpro / puroclean / servicemaster) which actually have referring domains.
  * The highest-value local signal is CITATIONS — the directories/authority
    domains AI assistants already cite for the client's queries (we already store
    these in marketing_ai_search_scans.cited_sources). If AI recommends a site and
    the client isn't on it, that's a get-listed opportunity.

Outputs ranked items into marketing_action_plan (action_type='get_listed') so they
appear in the Action Plan tab. Idempotent via action_key (matches the app scheme).
Dry-run by default.

Usage:
  python3 scripts/authority_targets.py --slug narestco           # dry-run (print)
  python3 scripts/authority_targets.py --slug narestco --write   # upsert to plan
"""
from __future__ import annotations
import argparse, base64, hashlib, json, sys, urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import geogrid_scan as gs           # load_dfs_creds()
from geogrid_store import sb_client, COMPANY_MAP

# Strong national restoration brands — they have real backlink profiles, so the
# link-gap against them surfaces authority domains worth pursuing.
NATIONAL_SEEDS = ["servpro.com", "puroclean.com", "servicemasterrestore.com",
                  "servprofire.com", "911restoration.com"]

# Known directories/aggregators (citation targets, not "competitors").
DIRECTORIES = {"yelp.com", "bbb.org", "homeadvisor.com", "angi.com", "angieslist.com",
               "thumbtack.com", "nextdoor.com", "yellowpages.com", "mapquest.com",
               "facebook.com", "houzz.com", "porch.com", "buildzoom.com", "expertise.com",
               "reddit.com", "trustpilot.com", "manta.com", "chamberofcommerce.com"}

# Search/AI infrastructure and non-actionable domains — never a "get listed" target.
JUNK = {"vertexaisearch.cloud.google.com", "google.com", "gstatic.com", "googleusercontent.com",
        "bing.com", "duckduckgo.com", "search.brave.com", "wikipedia.org"}

DFS = "https://api.dataforseo.com"


def _auth() -> str:
    u, p = gs.load_dfs_creds()
    return base64.b64encode(f"{u}:{p}".encode()).decode()


def _post(path: str, body: list) -> dict:
    req = urllib.request.Request(DFS + path, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Basic {_auth()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _items(resp: dict) -> list:
    task = (resp.get("tasks") or [{}])[0]
    if task.get("status_code") != 20000:
        sys.stderr.write(f"  DFS warn: {task.get('status_message')}\n")
    return ((task.get("result") or [{}])[0] or {}).get("items") or []


def client_domain(sb, slug: str) -> str:
    cid = COMPANY_MAP.get(slug)
    if cid:
        r = sb.table("companies").select("website").eq("id", cid).limit(1).execute()
        w = (r.data or [{}])[0].get("website") or ""
        d = w.replace("https://", "").replace("http://", "").replace("www.", "").strip("/").split("/")[0]
        if d:
            return d
    return f"{slug}.com"


def cited_sources(sb, cid: str) -> tuple[Counter, Counter]:
    """Return (directory_hits, authority_hits) domain counters from our AI data."""
    r = (sb.table("marketing_ai_search_scans").select("cited_sources")
         .eq("company_id", cid).order("scanned_at", desc=True).limit(300).execute())
    directories, authority = Counter(), Counter()
    for row in r.data or []:
        for s in row.get("cited_sources") or []:
            d = (s.get("domain") or "").lower().replace("www.", "")
            if not d or d in JUNK:
                continue
            (directories if (s.get("directory") or d in DIRECTORIES) else authority)[d] += 1
    return directories, authority


def link_gap(client: str) -> list[dict]:
    """Referring domains linking to national competitors but not the client."""
    targets = {str(i + 1): d for i, d in enumerate(NATIONAL_SEEDS)}
    resp = _post("/v3/backlinks/domain_intersection/live",
                 [{"targets": targets, "exclude_targets": [client], "limit": 25, "order_by": ["1.rank,desc"]}])
    out = []
    for it in _items(resp):
        di = it.get("domain_intersection") or {}
        dom = di.get("domain")
        if dom:
            out.append({"domain": dom.lower().replace("www.", ""), "rank": di.get("rank") or 0})
    return out


def action_key(action_type: str, target: str) -> str:
    return hashlib.sha1(f"{action_type}|{target}".encode()).hexdigest()[:16]


def build(slug: str, write: bool) -> list[dict]:
    sb = sb_client()
    cid = COMPANY_MAP.get(slug)
    if not cid:
        sys.exit(f"No company_id for slug '{slug}'")
    domain = client_domain(sb, slug)
    print(f"client: {slug}  domain: {domain}  company_id: {cid}\n")

    directories, authority = cited_sources(sb, cid)
    try:
        gap = link_gap(domain)
    except Exception as e:
        sys.stderr.write(f"  link_gap failed: {e}\n")
        gap = []

    # Get-listed targets = directories AI cites (fast wins that feed AI + local)
    # and real authority-link domains from the national link-gap. Non-directory
    # cited domains are COMPETITORS (you can't "get listed" on them) — shown
    # separately as context, never as actions.
    targets: dict[str, dict] = {}
    for dom, n in directories.most_common():
        targets[dom] = {"domain": dom, "kind": "directory", "score": 100 + n * 5,
                        "reason": f"AI assistants cite {dom} for your services — get listed there."}
    for dom, rank in sorted(gap, key=lambda x: -x["rank"])[:20]:
        if dom in targets or dom == domain or dom in JUNK:
            continue
        targets[dom] = {"domain": dom, "kind": "authority_link", "score": min(90, 40 + rank // 100),
                        "reason": f"{dom} links to national restoration brands but not you — earn a link/mention."}

    ranked = sorted(targets.values(), key=lambda t: -t["score"])
    print("GET LISTED — actionable targets:")
    for i, t in enumerate(ranked, 1):
        print(f"{i:2}. [{t['kind']:14}] {t['domain']:30} — {t['reason']}")
    if authority:
        print("\nCompetitors AI prefers (context, not actions): " +
              ", ".join(d for d, _ in authority.most_common(8)))

    if not write:
        print(f"\n(dry-run) {len(ranked)} targets. Re-run with --write to add to the Action Plan.")
        return ranked

    # Upsert into the Action Plan (skip ones already present by action_key).
    existing = {r["action_key"] for r in (sb.table("marketing_action_plan").select("action_key")
                .eq("company_id", cid).execute().data or []) if r.get("action_key")}
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    for i, t in enumerate(ranked):
        key = action_key("get_listed", t["domain"])
        if key in existing:
            continue
        sb.table("marketing_action_plan").insert({
            "company_id": cid, "rank_ai_slug": slug, "action_type": "get_listed",
            "assigned_system": "s3", "title": f"Get listed on {t['domain']}",
            "rationale": t["reason"], "target": t["domain"],
            "impact": "high" if t["kind"] == "directory" else "medium", "effort": "low",
            "status": "planned", "pinned": False, "priority": min(5, 1 + i // 5),
            "action_key": key, "source_run_at": now,
        }).execute()
        added += 1
    print(f"\nwrote {added} new get-listed actions to the plan ({len(existing)} already existed).")
    return ranked


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a client's Get-Listed authority targets")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--write", action="store_true", help="Upsert targets into marketing_action_plan")
    args = ap.parse_args()
    build(args.slug, args.write)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
