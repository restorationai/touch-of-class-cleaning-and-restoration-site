#!/usr/bin/env python3
"""
strategist.py — Rank AI System 0 (read-only v1).

For one client, gathers the signals we already collect (geo-grid local rankings,
content-queue depth + uncovered priority-1 keywords, onsite-audit verdict), ranks
the highest-impact next actions by impact/effort, and writes a prioritized plan to
the Supabase `marketing_action_plan` table (which the app's "What we're working on"
card reads). It does NOT execute anything — each action is routed to the system that
would do it (blog_post->S2, gbp_post->GBP, negative_keyword->ads, etc.).

Usage:
    python3 scripts/strategist.py --slug homepriderestorationandcleaning
    python3 scripts/strategist.py --slug narestco --dry-run   # print, don't write

Env (rank-ai/.env): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

IMPACT_RANK = {"high": 0, "medium": 1, "low": 2}
EFFORT_RANK = {"low": 0, "medium": 1, "high": 2}


def company_id_for(slug: str) -> str | None:
    rec = ROOT / "clients" / f"{slug}.json"
    if rec.exists():
        cid = json.loads(rec.read_text()).get("company_id")
        if cid:
            return cid
    cmap = ROOT / "clients" / "company_map.json"
    if cmap.exists():
        return json.loads(cmap.read_text()).get(slug)
    return None


def _sb(method: str, path: str, body=None):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "Prefer": "return=minimal",
    })
    with urllib.request.urlopen(req) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


# ---------------------------------------------------------------- signal gather
def gather_geogrid(company_id: str) -> list[dict]:
    """Most-recent scan per (keyword, city); flag cells the client is losing."""
    q = ("/rest/v1/marketing_geogrid_scans?company_id=eq." + urllib.parse.quote(company_id) +
         "&select=keyword,city_label,avg_rank,pct_in_top3,scanned_at&order=scanned_at.desc")
    rows = _sb("GET", q) or []
    seen, weak = set(), []
    for r in rows:
        k = (r["keyword"], r["city_label"])
        if k in seen:
            continue
        seen.add(k)
        pct = float(r["pct_in_top3"] or 0)
        avg = r["avg_rank"]
        if pct < 25 or avg is None:          # not in the local pack across most of the grid
            weak.append({"keyword": r["keyword"], "city": r["city_label"],
                         "pct_in_top3": pct, "avg_rank": avg})
    # worst first: lowest pct_in_top3
    weak.sort(key=lambda w: w["pct_in_top3"])
    return weak


TRANSACTIONAL_INTENTS = ("transactional", "commercial")


def _is_local_tx(kw: dict) -> bool:
    """Local + buy-intent = a real lead driver (someone hiring in a city we serve)."""
    return bool(kw.get("city_modifier")) and (kw.get("intent") in TRANSACTIONAL_INTENTS)


def gather_content(slug: str, company_id: str | None = None) -> dict:
    cdir = ROOT / "clients" / slug
    q = cdir / "content-queue.json"
    queued = 0
    if q.exists():
        queued = sum(1 for i in json.loads(q.read_text()).get("items", []) if i.get("status") == "queued")

    bank = cdir / "keyword-bank.json"
    uncovered = []          # priority-1 uncovered, each: {keyword, intent, city, local_tx}
    local_tx_total = 0
    if bank.exists():
        for k in json.loads(bank.read_text()).get("keywords", []):
            if _is_local_tx(k):
                local_tx_total += 1
            if k.get("priority") == 1 and not k.get("covered_by"):
                uncovered.append({
                    "keyword": k.get("keyword"), "intent": k.get("intent"),
                    "city": k.get("city_modifier"), "local_tx": _is_local_tx(k),
                })

    # Honor operator overrides from the app's Keyword Bank (marketing_keywords.status):
    # drop dismissed keywords, and float queued ones to the front.
    if company_id:
        rows = _sb("GET", "/rest/v1/marketing_keywords?company_id=eq." +
                   urllib.parse.quote(company_id) +
                   "&select=keyword,status&status=in.(queued,dismissed)") or []
        dismissed = {r["keyword"] for r in rows if r.get("status") == "dismissed"}
        queued_kw = {r["keyword"] for r in rows if r.get("status") == "queued"}
        uncovered = [u for u in uncovered if u["keyword"] not in dismissed]
        # queued first, then local-transactional before generic informational
        uncovered.sort(key=lambda u: (0 if u["keyword"] in queued_kw else 1,
                                      0 if u["local_tx"] else 1))
    else:
        uncovered.sort(key=lambda u: 0 if u["local_tx"] else 1)

    # how many service areas have NO local-transactional coverage at all
    n_areas = 0
    pi = cdir / "plan-input.json"
    if pi.exists():
        n_areas = len(json.loads(pi.read_text()).get("service_areas", []))

    return {"queued": queued, "uncovered": uncovered,
            "local_tx_total": local_tx_total, "n_areas": n_areas}


def gather_ai_search(company_id: str) -> dict:
    """Latest AI-search scan per (engine, query); flag money questions where the
    client is NOT cited by the AI assistant — a top strategic priority."""
    q = ("/rest/v1/marketing_ai_search_scans?company_id=eq." + urllib.parse.quote(company_id) +
         "&select=engine,query,cited,cited_sources,scanned_at&order=scanned_at.desc")
    rows = _sb("GET", q) or []
    seen, latest = set(), []
    for r in rows:
        k = (r.get("engine"), r.get("query"))
        if k in seen:
            continue
        seen.add(k)
        latest.append(r)
    total = len(latest)
    missing = []
    for r in latest:
        if r.get("cited"):
            continue
        # competitor domains the AI cited instead (skip directories)
        comps = [s.get("domain") for s in (r.get("cited_sources") or [])
                 if s.get("domain") and not s.get("directory")][:3]
        missing.append({"query": r["query"], "engine": r.get("engine") or "chatgpt",
                        "competitors": comps})
    cited = total - len(missing)
    return {"total": total, "cited": cited, "missing": missing}


def gather_audit(slug: str) -> dict:
    rec = ROOT / "clients" / f"{slug}.json"
    if not rec.exists():
        return {}
    return json.loads(rec.read_text()).get("audit", {}) or {}


def gather_gbp(company_id: str) -> dict:
    """Open GBP optimizer suggestions + review recency → strategic signals. Backed by
    scripts/gbp.py optimize (marketing_gbp_suggestions) and the synced profile. All
    items are one-click-applicable in the app's Marketing > Locations panel."""
    rows = _sb("GET", "/rest/v1/marketing_gbp_suggestions?company_id=eq." +
               urllib.parse.quote(company_id) +
               "&status=eq.open&select=verdict,item_type,item,auto_safe,reason") or []

    def is_negative(r: dict) -> bool:  # set by gbp.py's deterministic guardrail
        return "do not offer" in (r.get("reason") or "").lower()

    removes = [r for r in rows if r.get("verdict") == "REMOVE"]
    negatives = [r for r in removes if is_negative(r)]
    add_services = [r for r in rows if r.get("verdict") == "ADD" and r.get("item_type") == "service"]
    pages = [r for r in rows if r.get("item_type") == "page"]          # ADD (confirmed, no page)
    merges = [r for r in rows if r.get("verdict") == "MERGE"]

    prof = _sb("GET", "/rest/v1/marketing_gbp_profiles?company_id=eq." +
               urllib.parse.quote(company_id) + "&select=last_review_at,review_count,rating") or []
    p = prof[0] if prof else {}
    return {
        "removes": removes, "negatives": negatives, "add_services": add_services,
        "pages": pages, "merges": merges,
        "cleanup_n": len(merges) + (len(removes) - len(negatives)),
        "last_review_at": p.get("last_review_at"), "review_count": p.get("review_count"),
    }


def _names(items: list, n: int = 3) -> str:
    shown = ", ".join((r.get("item") or "") for r in items[:n])
    return shown + ("…" if len(items) > n else "")


def gather_gsc(company_id: str) -> list[dict]:
    """Striking-distance queries from Google Search Console (marketing_gsc_queries,
    populated by scripts/gsc_sync.py): real impressions, ranking on the page-1/2 edge.
    The highest-ROI content/refresh opportunities — a small push wins page-one traffic."""
    rows = _sb("GET", "/rest/v1/marketing_gsc_queries?company_id=eq." +
               urllib.parse.quote(company_id) +
               "&striking=is.true&order=impressions.desc&limit=8"
               "&select=query,impressions,position,clicks") or []
    return rows


def gather_alerts(slug: str, content: dict, ai: dict, audit: dict, gbp: dict | None = None) -> list[dict]:
    """Account-health flags that need a human's attention (not routine work).
    Two sources: (1) auto-derived from the signals we already gathered, and
    (2) operator-set flags in clients/{slug}.json['ops_alerts'] (e.g. narestco LSA)."""
    alerts: list[dict] = []

    # (1) Operator-set ops alerts — highest signal (a human flagged it).
    rec = ROOT / "clients" / f"{slug}.json"
    if rec.exists():
        for a in (json.loads(rec.read_text()).get("ops_alerts") or []):
            if (a.get("status") or "open").lower() != "open":
                continue
            alerts.append({
                "title": a.get("title") or "Account needs attention",
                "rationale": a.get("detail") or "",
                "target": a.get("key") or a.get("title"),
                "severity": (a.get("severity") or "high").lower(),
                "system": a.get("system") or "manual",
            })

    # (2) Auto-derived flags from the signals.
    if (audit.get("last_audit_verdict") or "").lower() == "red":
        alerts.append({"title": "Site health is critical (red audit)",
                       "rationale": f"Latest onsite audit verdict is red ({audit.get('last_audit_at','')}).",
                       "target": "audit_red", "severity": "high", "system": "s3"})
    if content.get("queued", 1) == 0:
        alerts.append({"title": "Content queue is empty",
                       "rationale": "No posts queued — publishing will stop until the queue is refilled.",
                       "target": "queue_empty", "severity": "high", "system": "s1"})
    if ai.get("total", 0) > 0 and ai.get("cited", 0) == 0:
        alerts.append({"title": "Invisible in AI search",
                       "rationale": f"Not recommended in any of {ai['total']} AI money questions scanned.",
                       "target": "ai_invisible", "severity": "high", "system": "s2"})

    # GBP correctness: services the business declared it does NOT offer are live on the
    # listing — a trust problem and a suspension risk. Highest-signal GBP issue.
    if gbp and gbp.get("negatives"):
        alerts.append({
            "title": "Incorrect services on your Google Business Profile",
            "rationale": f"{len(gbp['negatives'])} service(s) the business declared it does NOT offer "
                         f"are live on the GBP ({_names(gbp['negatives'])}). These mislead customers and "
                         f"risk a listing suspension — remove them in Marketing → Locations (one click).",
            "target": "gbp_negatives", "severity": "high", "system": "gbp"})
    return alerts


# ----------------------------------------------------------------- build + rank
def build_actions(geo: list[dict], content: dict, audit: dict, ai: dict | None = None,
                  alerts: list[dict] | None = None, gbp: dict | None = None,
                  gsc: list[dict] | None = None) -> list[dict]:
    acts: list[dict] = []
    ai = ai or {"missing": []}
    gbp = gbp or {}
    gsc = gsc or []

    # Alerts: account-health flags surfaced as a "Needs Attention" section in the app.
    # action_type='alert' so the UI can split them from routine actions.
    for al in (alerts or []):
        acts.append({
            "action_type": "alert", "assigned_system": al.get("system", "manual"),
            "title": al["title"], "rationale": al.get("rationale", ""),
            "target": al.get("target"),
            "impact": al.get("severity", "high"), "effort": "low", "is_alert": True,
        })

    # AI search: money questions where AI assistants don't recommend the client.
    # High strategic priority — this is where buyers increasingly start.
    for m in ai["missing"][:4]:
        instead = (" AI recommends " + ", ".join(m["competitors"]) + " instead."
                   if m.get("competitors") else "")
        acts.append({
            "action_type": "ai_visibility", "assigned_system": "s2",
            "title": f"Get cited by AI for “{m['query']}”",
            "rationale": f"{m['engine'].title()} does not recommend this business for "
                         f"“{m['query']}”.{instead} Publish/strengthen a page answering "
                         f"this question with citable facts, reviews, and local detail.",
            "target": m["query"], "impact": "high", "effort": "medium",
        })

    # Geo-grid: one action per weak keyword (its worst city), capped.
    by_kw = {}
    for w in geo:
        by_kw.setdefault(w["keyword"], w)        # geo already sorted worst-first
    for kw, w in list(by_kw.items())[:5]:
        acts.append({
            "action_type": "gbp_post", "assigned_system": "gbp",
            "title": f"Win the local pack for '{kw}' in {w['city']}",
            "rationale": f"Geo-grid: only {w['pct_in_top3']:.0f}% of the grid ranks top-3 for "
                         f"'{kw}' in {w['city']} — losing local visibility.",
            "target": f"{kw} | {w['city']}", "impact": "high", "effort": "medium",
        })

    # Content — weighted for LEAD GEN:
    #   local-transactional gaps (drive calls) = HIGH; generic informational = LOW (support).
    if content["queued"] < 3:
        acts.append({
            "action_type": "keyword_research", "assigned_system": "s1",
            "title": "Refill the content queue (keyword research)",
            "rationale": f"Only {content['queued']} priority-1 posts queued — System 2 will run dry.",
            "target": None, "impact": "medium", "effort": "low",
        })

    # Thin local coverage -> targeted local-transactional research (the real call driver).
    if content.get("n_areas", 0) and content.get("local_tx_total", 0) < content["n_areas"]:
        acts.append({
            "action_type": "keyword_research", "assigned_system": "s1",
            "title": "Research local-transactional keywords for the service areas",
            "rationale": f"Only {content.get('local_tx_total',0)} local buy-intent keywords across "
                         f"{content['n_areas']} service areas — too thin to drive local calls. "
                         f"Run keyword research focused on '{{service}} {{city}}' terms.",
            "target": None, "impact": "high", "effort": "low",
        })

    uncovered = content["uncovered"]
    local_tx = [u for u in uncovered if u.get("local_tx")]
    informational = [u for u in uncovered if not u.get("local_tx")]
    # local-transactional pages = HIGH impact (someone hiring in a city we serve)
    for u in local_tx[:4]:
        acts.append({
            "action_type": "blog_post", "assigned_system": "s2",
            "title": f"Publish a local page targeting '{u['keyword']}'",
            "rationale": f"Local buy-intent keyword ({u['city']}) with no page yet — direct lead driver.",
            "target": u["keyword"], "impact": "high", "effort": "low",
        })
    # generic informational = LOW impact supporting content (authority/AI-citation, not direct calls)
    for u in informational[:2]:
        acts.append({
            "action_type": "blog_post", "assigned_system": "s2",
            "title": f"Publish a blog post targeting '{u['keyword']}'",
            "rationale": "Informational keyword with no page yet — supporting content for "
                         "authority/AI citation (not a direct lead driver).",
            "target": u["keyword"], "impact": "low", "effort": "low",
        })

    # GSC striking distance: queries ranking on the page-1/2 edge with real demand.
    # A focused refresh of the ranking page converts these to page-one traffic (high
    # impact, low effort). Cap so they don't crowd out the rest of the plan.
    for q in gsc[:3]:
        acts.append({
            "action_type": "gsc_striking", "assigned_system": "s2",
            "title": f"Push '{q['query']}' onto page one",
            "rationale": f"Ranks position {q.get('position')} for '{q['query']}' with "
                         f"{q.get('impressions')} impressions in 28 days (striking distance). "
                         f"Strengthen the ranking page (depth, internal links, FAQ, freshness) "
                         f"to break into the top results.",
            "target": q["query"], "impact": "high", "effort": "low",
        })

    # GBP optimizer: confirmed-service gaps + listing cleanup + review velocity.
    # Each is one-click-applicable in the app's Marketing > Locations panel (or auto-
    # built by the gbp-maintenance pipeline for pages). Aggregated, not per-service.
    if gbp.get("add_services"):
        acts.append({
            "action_type": "gbp_add_services", "assigned_system": "gbp",
            "title": f"Add {len(gbp['add_services'])} confirmed service(s) to your Business Profile",
            "rationale": f"Services the business offers but are missing from the GBP "
                         f"({_names(gbp['add_services'])}). Apply in Marketing → Locations (vetted, one click).",
            "target": "gbp_add_services", "impact": "medium", "effort": "low",
        })
    if gbp.get("pages"):
        acts.append({
            "action_type": "gbp_create_pages", "assigned_system": "gbp",
            "title": f"Create {len(gbp['pages'])} website page(s) for confirmed services",
            "rationale": f"Confirmed services with no crawlable page ({_names(gbp['pages'])}) — a local-ranking "
                         f"and GBP↔site consistency gap. Approve in Marketing → Locations; the pipeline "
                         f"builds + deploys them.",
            "target": "gbp_create_pages", "impact": "medium", "effort": "medium",
        })
    if gbp.get("cleanup_n"):
        acts.append({
            "action_type": "gbp_cleanup", "assigned_system": "gbp",
            "title": f"Clean up {gbp['cleanup_n']} duplicate/off-brand service(s) on your GBP",
            "rationale": "Duplicate and off-brand service labels bloat the listing and dilute relevance. "
                         "Merge/remove them in Marketing → Locations (one click).",
            "target": "gbp_cleanup", "impact": "low", "effort": "low",
        })
    last = gbp.get("last_review_at")
    if last:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(last.replace("Z", "+00:00"))).days
        except Exception:
            age = 0
        if age >= 45:
            acts.append({
                "action_type": "gbp_reviews", "assigned_system": "gbp",
                "title": "Get fresh Google reviews",
                "rationale": f"No new Google review since {str(last)[:10]} ({age} days). Review velocity is a "
                             f"strong local-ranking and trust signal — run a review-request campaign.",
                "target": "gbp_reviews", "impact": "medium", "effort": "low",
            })

    # Audit: amber/red -> fix.
    verdict = (audit.get("last_audit_verdict") or "").lower()
    if verdict in ("amber", "red"):
        acts.append({
            "action_type": "audit_fix", "assigned_system": "s3",
            "title": f"Resolve {verdict} site-health issues",
            "rationale": f"Latest onsite audit verdict is {verdict} ({audit.get('last_audit_at','')}).",
            "target": None, "impact": "high" if verdict == "red" else "medium", "effort": "medium",
        })

    # Alerts first (most severe), then routine actions by impact/effort.
    acts.sort(key=lambda a: (0 if a.get("is_alert") else 1,
                             IMPACT_RANK.get(a["impact"], 9), EFFORT_RANK.get(a["effort"], 9)))
    for i, a in enumerate(acts, 1):
        a["priority"] = i
        a.pop("is_alert", None)
        # stable identity so re-runs don't resurrect a dismissed action or lose a pin
        a["action_key"] = hashlib.sha1(
            f"{a['action_type']}|{a.get('target') or ''}".encode()).hexdigest()[:16]
    return acts


def _parse_city_anchor(slug: str, target: str) -> str | None:
    """For an ai_visibility query like 'best X company in Saratoga Springs, UT',
    map the city to a service_area slug so the content writer localizes it."""
    if " in " not in (target or ""):
        return None
    city = target.rsplit(" in ", 1)[1].split(",")[0].strip().lower()
    try:
        pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
    except Exception:
        return None
    for a in pi.get("service_areas", []):
        if (a.get("city") or "").strip().lower() == city:
            return a.get("slug")
    return None


def sync_content_queue(slug: str, company_id: str) -> int:
    """Make pinned content actions (blog_post / ai_visibility / ai_keyword) into
    prioritized content-queue items so System 2 writes them next. Find-or-create by
    keyword (case-insensitive); never touches already-written/live items. Safe + idempotent."""
    rows = _sb("GET", "/rest/v1/marketing_action_plan?company_id=eq." +
               urllib.parse.quote(company_id) +
               "&pinned=is.true&action_type=in.(blog_post,ai_visibility,ai_keyword)"
               "&status=in.(planned,in_progress)&select=action_type,target,title") or []
    pinned = [r for r in rows if r.get("target")]
    if not pinned:
        return 0

    qpath = ROOT / "clients" / slug / "content-queue.json"
    queue = json.loads(qpath.read_text()) if qpath.exists() else {"items": []}
    items = queue.setdefault("items", [])
    by_kw = {(i.get("primary_keyword") or "").strip().lower(): i for i in items}

    # rich data from the keyword bank when the target is a researched keyword
    bank = {}
    bpath = ROOT / "clients" / slug / "keyword-bank.json"
    if bpath.exists():
        for k in json.loads(bpath.read_text()).get("keywords", []):
            bank[(k.get("keyword") or "").strip().lower()] = k

    now = datetime.now(timezone.utc).isoformat()
    touched = 0
    for r in pinned:
        kw = r["target"].strip()
        key = kw.lower()
        existing = by_kw.get(key)
        if existing:
            if existing.get("status") == "queued" and not existing.get("prioritized"):
                existing["prioritized"] = True
                touched += 1
            continue  # already covered/written or already prioritized — leave it

        b = bank.get(key, {})
        item = {
            "id": f"{now[:10]}-pin-" + re.sub(r"[^a-z0-9]+", "-", key)[:48].strip("-"),
            "status": "queued", "queued_at": now, "prioritized": True,
            "source": "strategist-pin",
            "primary_keyword": kw,
            "intent": b.get("intent") or ("commercial" if r["action_type"] in ("ai_visibility", "ai_keyword") else "informational"),
            "volume": b.get("volume"), "kd": b.get("kd"),
            "target_word_count": 1500,
        }
        anchor = _parse_city_anchor(slug, kw)
        if anchor:
            item["city_anchor"] = anchor
        if r["action_type"] in ("ai_visibility", "ai_keyword"):
            item["notes"] = ("Pinned from AI Search. Write an honest, locally-specific guide that "
                             "positions this business on verifiable strengths (certifications, license, "
                             "response time, reviews) — NOT a self-ranking 'best companies' list.")
        items.append(item)
        by_kw[key] = item
        touched += 1

    if touched:
        qpath.write_text(json.dumps(queue, indent=2))
    return touched


def run_for(slug: str, dry_run: bool) -> int:
    company_id = company_id_for(slug)
    if not company_id:
        print(f"  skip '{slug}': no company_id", file=sys.stderr)
        return 1

    geo = gather_geogrid(company_id)
    content = gather_content(slug, company_id)
    audit = gather_audit(slug)
    ai = gather_ai_search(company_id)
    gbp = gather_gbp(company_id)
    gsc = gather_gsc(company_id)
    alerts = gather_alerts(slug, content, ai, audit, gbp)
    actions = build_actions(geo, content, audit, ai, alerts, gbp, gsc)
    now = datetime.now(timezone.utc).isoformat()

    ai_summary = f"{ai['cited']}/{ai['total']} AI-cited" if ai["total"] else "no AI scan"
    gbp_summary = (f"{len(gbp['add_services'])} add / {len(gbp['pages'])} pages / "
                   f"{gbp['cleanup_n']} cleanup / {len(gbp['negatives'])} negatives")
    print(f"\n=== Strategist plan — {slug} ({company_id}) ===")
    print(f"signals: {len(alerts)} alerts | {len(geo)} weak geo cells | {content['queued']} queued posts | "
          f"{len(content['uncovered'])} uncovered kw | {ai_summary} | gbp[{gbp_summary}] | "
          f"{len(gsc)} gsc striking | audit={audit.get('last_audit_verdict','?')}\n")
    for a in actions:
        print(f"  [{a['priority']}] ({a['impact']}/{a['effort']}) {a['assigned_system']:6} {a['title']}")
        print(f"        why: {a['rationale']}")
    if not actions:
        print("  (no actions — client is in good shape on the signals checked)")

    if dry_run:
        print("\n(dry-run — nothing written)")
        return 0

    # Persist, honoring operator overrides:
    #  - rows the operator DISMISSED, or that are pinned / in_progress / done, SURVIVE
    #    and are not re-created (we never resurrect a dismissed action).
    #  - all other 'planned' rows are refreshed (cleared + re-inserted with new ranking).
    cq = "/rest/v1/marketing_action_plan?company_id=eq." + urllib.parse.quote(company_id)
    existing = _sb("GET", cq + "&select=action_key,status,pinned") or []
    survive = {r["action_key"] for r in existing
               if r.get("action_key") and (r["status"] in ("dismissed", "done", "in_progress") or r["pinned"])}

    _sb("DELETE", cq + "&status=eq.planned&pinned=is.false")   # clear refreshable rows

    inserts = [{
        "company_id": company_id, "rank_ai_slug": slug, "priority": a["priority"],
        "action_type": a["action_type"], "title": a["title"], "rationale": a["rationale"],
        "target": a.get("target"), "assigned_system": a["assigned_system"],
        "impact": a["impact"], "effort": a["effort"], "status": "planned",
        "action_key": a["action_key"], "source_run_at": now,
    } for a in actions if a["action_key"] not in survive]
    if inserts:
        _sb("POST", "/rest/v1/marketing_action_plan", inserts)
    print(f"\nUpserted plan for {slug}: {len(inserts)} planned, "
          f"{len(actions) - len(inserts)} left untouched (dismissed/pinned/in-progress).")

    # Pull-forward wiring: pinned content actions become prioritized content-queue
    # items so System 2 writes them next. The one safe auto-exec (content only).
    synced = sync_content_queue(slug, company_id)
    if synced:
        print(f"  content-queue: {synced} pinned item(s) queued/prioritized for System 2.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--slug", help="one client")
    grp.add_argument("--all", action="store_true", help="every active client (clients/company_map.json)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        print("ERROR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required.", file=sys.stderr)
        return 1

    if args.all:
        cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
        rc = 0
        for slug in cmap:
            rc |= run_for(slug, args.dry_run)
        return rc
    return run_for(args.slug, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
