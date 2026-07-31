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

A second mode, 'listicles', finds LISTICLE/AGGREGATOR pages ("best water damage
restoration in Seattle" roundups on expertise.com, threebestrated.com, Yelp
collections, local news, ...) ranking in the client's cities and checks whether
the client is already featured. These pages are what ChatGPT/Perplexity quote
when asked "who's the best X in Y" — getting placed on them is the highest-ROI
AI-visibility move after directories.

Usage:
  python3 scripts/authority_targets.py --slug narestco           # dry-run (print)
  python3 scripts/authority_targets.py --slug narestco --write   # upsert to plan
  python3 scripts/authority_targets.py --slug narestco --mode listicles
  python3 scripts/authority_targets.py --all --write --mode all  # monthly cron
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

# Universal directories every restoration business should be listed on. Seeds a
# baseline Get-Listed list even for a brand-new client with no AI-search data yet.
# HomeAdvisor is deliberately NOT here (Santino 2026-07-31): it has no free
# listing tier — ~$300/yr membership + per-lead fees — so it's a paid lead-gen
# decision for the client, never a baseline citation ask. (Angi's basic profile
# claim IS free; only Angi Ads/Leads cost money.)
CORE_DIRECTORIES = ["yelp.com", "bbb.org", "angi.com", "thumbtack.com",
                    "facebook.com", "nextdoor.com", "yellowpages.com", "mapquest.com", "houzz.com"]

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
    # "lst:" namespace: survives strategist's weekly planned-row refresh (it only
    # deletes its own unprefixed keys).
    return "lst:" + hashlib.sha1(f"{action_type}|{target}".encode()).hexdigest()[:16]


def build(slug: str, write: bool, sb=None) -> list[dict]:
    sb = sb or sb_client()
    cid = COMPANY_MAP.get(slug)
    if not cid:
        sys.stderr.write(f"  skip {slug}: no company_id in company_map.json\n")
        return []
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
    # 1) Core directories — always seeded so even a data-less new client has a list.
    for j, dom in enumerate(CORE_DIRECTORIES):
        targets[dom] = {"domain": dom, "kind": "directory", "score": 80 - j,
                        "reason": "Core directory every restoration business should be listed on."}
    # 2) Directories AI actually cites for this client — boosted with proof.
    for dom, n in directories.most_common():
        if dom in JUNK:
            continue
        if dom in targets:
            targets[dom]["score"] = 100 + n * 5
            targets[dom]["reason"] = f"AI assistants cite {dom} for your services — get listed there."
        else:
            targets[dom] = {"domain": dom, "kind": "directory", "score": 100 + n * 5,
                            "reason": f"AI assistants cite {dom} for your services — get listed there."}
    # 3) Authority-link domains from the national link-gap.
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


# ----------------------------------------------------------------------------
# Mode: listicles — "best {service} {city}" SERP roundup/aggregator pages
# ----------------------------------------------------------------------------

SERP_PATH = "/v3/serp/google/organic/live/advanced"

# Known aggregator/listicle domains → placement action hint.
LISTICLE_HINTS = {
    "expertise.com":       "Expertise.com — free application",
    "threebestrated.com":  "ThreeBestRated — application",
    "yelp.com":            "Yelp collection — improve Yelp profile (reviews, photos, categories)",
    "angi.com":            "Angi — free profile claim only (Ads/Leads cost money)",
    "angieslist.com":      "Angi — free profile claim only (Ads/Leads cost money)",
    "bbb.org":             "BBB — accreditation + A+ profile",
    "porch.com":           "Porch — claim/complete profile",
    "thumbtack.com":       "Thumbtack — pro profile + reviews",
    "houzz.com":           "Houzz — pro profile + project photos",
    "homeadvisor.com":     "HomeAdvisor — PAID ONLY (~$300/yr + per-lead); client's call, not a citation",
    "yellowpages.com":     "YellowPages — claim listing",
    "nextdoor.com":        "Nextdoor — business page + neighbor recommendations",
    "birdeye.com":         "Birdeye directory — profile via reviews platform",
    "homeguide.com":       "HomeGuide — free pro application",
    "prontopro.com":       "ProntoPro — pro application",
    "cleanup.com":         "Cleanup.com — directory application",
}

# Domains that rank for "best X in Y" but are single restoration companies
# (or generic infra), not placeable roundups.
_COMPANY_TOKENS = ("restoration", "restor", "damage", "flood", "mold", "waterdry",
                   "drying", "rooter", "plumb", "servpro", "puroclean", "servicemaster",
                   "911restoration", "belfor", "pauldavis", "rainbow", "steamatic",
                   "carpet", "cleanpro", "flooded", "rytech")


def _looks_like_company(dom: str) -> bool:
    d = dom.replace("-", "").replace(".", "")
    return any(t in d for t in _COMPANY_TOKENS)


def _listicle_hint(dom: str, url: str, title: str) -> str | None:
    """Return an action hint if this SERP result is a placeable listicle/aggregator,
    else None. Heuristic tail: 'best'/'top' in the title on a non-restoration-company
    domain, with a list marker (a count, 'companies', 'services', 'near'), reads as
    a roundup (local news / magazine / blog) — pitch it."""
    if "yelp.com/biz/" in url:
        return None  # single-business Yelp page, not a placeable collection
    for known, hint in LISTICLE_HINTS.items():
        if dom == known or dom.endswith("." + known):
            return hint
    t = (title or "").lower()
    is_roundup = (("best" in t or "top " in t or t.startswith("top"))
                  and (any(c.isdigit() for c in t) or "companies" in t
                       or "services" in t or " near " in t or " in " in t))
    if is_roundup and not _looks_like_company(dom):
        return "news/blog roundup — pitch for inclusion (PR/outreach)"
    return None


def _serp(query: str) -> list[dict]:
    """Top-20 organic results for a query (client cities are baked into the query
    text, so a national location is fine and avoids location_name resolution)."""
    resp = _post(SERP_PATH, [{"keyword": query, "language_code": "en",
                              "location_name": "United States", "depth": 20}])
    out = []
    for it in _items(resp):
        if it.get("type") != "organic":
            continue
        out.append({"rank": it.get("rank_group") or it.get("rank_absolute") or 0,
                    "domain": (it.get("domain") or "").lower().replace("www.", ""),
                    "url": it.get("url") or "",
                    "title": it.get("title") or "",
                    "snippet": it.get("description") or ""})
    return out


def _listicle_queries(plan: dict) -> list[str]:
    """Top 2 services x top 3 cities (primary city first) x 2 phrasings."""
    areas = plan.get("service_areas") or []
    areas = sorted(areas, key=lambda a: not a.get("primary"))  # stable: primary first
    cities = [a["city"] for a in areas[:3]]
    svcs = [s.replace("-", " ") for s in (plan.get("services") or [])[:2]]
    qs = []
    for svc in svcs:
        for city in cities:
            qs.append(f"best {svc} {city}")
            qs.append(f"best {svc} companies in {city}")
    return qs


def listicles(slug: str, write: bool, sb=None) -> list[dict]:
    """Find listicle placement targets for one client; print a table, store a JSON
    copy under clients/{slug}/authority/, and (with --write) upsert into
    marketing_action_plan (action_type='listicle', idempotent via action_key)."""
    client_dir = ROOT / "clients" / slug
    plan_path = client_dir / "plan-input.json"
    rec_path = ROOT / "clients" / f"{slug}.json"
    if not plan_path.exists() or not rec_path.exists():
        sys.stderr.write(f"  skip {slug}: missing plan-input.json or client record\n")
        return []
    plan = json.loads(plan_path.read_text())
    rec = json.loads(rec_path.read_text())
    domain = (rec.get("domain") or "").lower().replace("www.", "")
    brand = plan.get("brand") or {}
    names = [n.lower() for n in (brand.get("display_name"), brand.get("short_name"),
                                 rec.get("display_name")) if n]

    queries = _listicle_queries(plan)
    print(f"listicles: {slug} ({domain}) — {len(queries)} SERP queries")
    targets: dict[str, dict] = {}   # keyed by URL
    for q in queries:
        try:
            results = _serp(q)
        except Exception as e:
            sys.stderr.write(f"  SERP failed '{q}': {str(e)[:100]}\n")
            continue
        for r in results:
            dom = r["domain"]
            if not dom or dom == domain:
                continue
            hint = _listicle_hint(dom, r["url"], r["title"])
            if not hint:
                continue
            hay = (r["title"] + " " + r["snippet"]).lower()
            present = (domain and domain in hay) or any(n in hay for n in names)
            prev = targets.get(r["url"])
            if prev:  # keep best rank; presence is sticky across queries
                prev["rank"] = min(prev["rank"], r["rank"])
                prev["client_present"] = prev["client_present"] or present
                prev.setdefault("queries", []).append(q)
                continue
            targets[r["url"]] = {"url": r["url"], "domain": dom, "rank": r["rank"],
                                 "title": r["title"], "client_present": present,
                                 "action_hint": hint, "queries": [q]}

    ranked = sorted(targets.values(), key=lambda t: (t["client_present"], t["rank"]))
    print("\nLISTICLE PLACEMENT TARGETS:")
    print(f"{'#':>2} {'rank':>4} {'present':>7}  {'domain':28} action hint / url")
    for i, t in enumerate(ranked, 1):
        print(f"{i:2} {t['rank']:4} {'yes' if t['client_present'] else 'no':>7}  "
              f"{t['domain']:28} {t['action_hint']}")
        print(f"{'':17}{t['url'][:110]}")

    # JSON copy under clients/{slug}/authority/ (local state, like audit-runs/).
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    out_dir = client_dir / "authority"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "listicle-targets.json"
    out_path.write_text(json.dumps({"slug": slug, "domain": domain, "generated_at": now,
                                    "queries": queries, "targets": ranked}, indent=2) + "\n")
    print(f"\nstored {len(ranked)} targets → {out_path.relative_to(ROOT)}")

    if not write:
        print("(dry-run) re-run with --write to add missing placements to the Action Plan.")
        return ranked

    # Upsert into the Action Plan — only pages where the client is NOT yet present.
    sb = sb or sb_client()
    cid = COMPANY_MAP.get(slug)
    if not cid:
        sys.stderr.write(f"  skip plan write for {slug}: no company_id in company_map.json\n")
        return ranked
    existing = {r["action_key"] for r in (sb.table("marketing_action_plan").select("action_key")
                .eq("company_id", cid).execute().data or []) if r.get("action_key")}
    added = 0
    for i, t in enumerate(r for r in ranked if not r["client_present"]):
        key = action_key("listicle", t["url"])
        if key in existing:
            continue
        sb.table("marketing_action_plan").insert({
            "company_id": cid, "rank_ai_slug": slug, "action_type": "listicle",
            "assigned_system": "s3",
            "title": f"Get featured: {t['domain']} roundup (rank {t['rank']})",
            "rationale": (f"Ranks #{t['rank']} for '{t['queries'][0]}' and the client is not "
                          f"mentioned. {t['action_hint']}. {t['url']}"),
            "target": t["url"], "impact": "high" if t["rank"] <= 5 else "medium",
            "effort": "medium", "status": "planned", "pinned": False,
            "priority": min(5, 1 + i // 5), "action_key": key, "source_run_at": now,
        }).execute()
        added += 1
    print(f"wrote {added} new listicle actions to the plan.")
    return ranked


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a client's Get-Listed authority targets")
    ap.add_argument("--slug", help="Run one client")
    ap.add_argument("--all", action="store_true", help="Run every client in company_map.json (for the monthly cron)")
    ap.add_argument("--write", action="store_true", help="Upsert targets into marketing_action_plan")
    ap.add_argument("--mode", choices=["get-listed", "listicles", "all"], default="get-listed",
                    help="get-listed (default) = directories + link-gap; listicles = SERP roundup "
                         "placement targets; all = both (monthly cron)")
    args = ap.parse_args()
    if not args.slug and not args.all:
        ap.error("pass --slug <slug> or --all")
    sb = sb_client() if (args.mode in ("get-listed", "all") or args.write) else None
    slugs = list(COMPANY_MAP.keys()) if args.all else [args.slug]
    for slug in slugs:
        if args.mode in ("get-listed", "all"):
            try:
                build(slug, args.write, sb=sb)
            except Exception as e:
                sys.stderr.write(f"  FAIL {slug}: {str(e)[:160]}\n")
        if args.mode in ("listicles", "all"):
            try:
                listicles(slug, args.write, sb=sb)
            except Exception as e:
                sys.stderr.write(f"  FAIL listicles {slug}: {str(e)[:160]}\n")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
