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
import json
import os
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


def gather_content(slug: str) -> dict:
    cdir = ROOT / "clients" / slug
    q = cdir / "content-queue.json"
    queued = 0
    if q.exists():
        queued = sum(1 for i in json.loads(q.read_text()).get("items", []) if i.get("status") == "queued")
    bank = cdir / "keyword-bank.json"
    uncovered = []
    if bank.exists():
        for k in json.loads(bank.read_text()).get("keywords", []):
            if k.get("priority") == 1 and not k.get("covered_by"):
                uncovered.append(k.get("keyword"))
    return {"queued": queued, "uncovered": uncovered}


def gather_audit(slug: str) -> dict:
    rec = ROOT / "clients" / f"{slug}.json"
    if not rec.exists():
        return {}
    return json.loads(rec.read_text()).get("audit", {}) or {}


# ----------------------------------------------------------------- build + rank
def build_actions(geo: list[dict], content: dict, audit: dict) -> list[dict]:
    acts: list[dict] = []

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

    # Content: thin queue -> research; uncovered priority-1 -> write posts.
    if content["queued"] < 3:
        acts.append({
            "action_type": "keyword_research", "assigned_system": "s1",
            "title": "Refill the content queue (keyword research)",
            "rationale": f"Only {content['queued']} priority-1 posts queued — System 2 will run dry.",
            "target": None, "impact": "medium", "effort": "low",
        })
    for kw in content["uncovered"][:3]:
        acts.append({
            "action_type": "blog_post", "assigned_system": "s2",
            "title": f"Publish a blog post targeting '{kw}'",
            "rationale": "Priority-1 keyword with no page covering it yet.",
            "target": kw, "impact": "medium", "effort": "low",
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

    acts.sort(key=lambda a: (IMPACT_RANK.get(a["impact"], 9), EFFORT_RANK.get(a["effort"], 9)))
    for i, a in enumerate(acts, 1):
        a["priority"] = i
    return acts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        print("ERROR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required (rank-ai/.env).", file=sys.stderr)
        return 1
    company_id = company_id_for(args.slug)
    if not company_id:
        print(f"ERROR: no company_id for slug '{args.slug}'.", file=sys.stderr)
        return 1

    geo = gather_geogrid(company_id)
    content = gather_content(args.slug)
    audit = gather_audit(args.slug)
    actions = build_actions(geo, content, audit)
    now = datetime.now(timezone.utc).isoformat()

    print(f"\n=== Strategist plan — {args.slug} ({company_id}) ===")
    print(f"signals: {len(geo)} weak geo cells | {content['queued']} queued posts | "
          f"{len(content['uncovered'])} uncovered kw | audit={audit.get('last_audit_verdict','?')}\n")
    for a in actions:
        print(f"  [{a['priority']}] ({a['impact']}/{a['effort']}) {a['assigned_system']:6} {a['title']}")
        print(f"        why: {a['rationale']}")
    if not actions:
        print("  (no actions — client is in good shape on the signals checked)")

    if args.dry_run:
        print("\n(dry-run — nothing written)")
        return 0

    # Replace this company's prior 'planned' rows, then insert the fresh plan.
    _sb("DELETE", "/rest/v1/marketing_action_plan?status=eq.planned&company_id=eq." +
        urllib.parse.quote(company_id))
    if actions:
        rows = [{
            "company_id": company_id, "rank_ai_slug": args.slug, "priority": a["priority"],
            "action_type": a["action_type"], "title": a["title"], "rationale": a["rationale"],
            "target": a.get("target"), "assigned_system": a["assigned_system"],
            "impact": a["impact"], "effort": a["effort"], "status": "planned",
            "source_run_at": now,
        } for a in actions]
        _sb("POST", "/rest/v1/marketing_action_plan", rows)
    print(f"\nWrote {len(actions)} action(s) to marketing_action_plan for {args.slug}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
