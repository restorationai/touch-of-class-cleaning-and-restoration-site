#!/usr/bin/env python3
"""client_analyzer.py — the biweekly results analyzer.

Santino 2026-08-22: "not only making sure our software is working correctly
but actually making sure we are getting positive results for our clients."
This is that pivot as a tool: for one client (or the fleet) it pulls every
performance surface we track, separates real trends from anomalies, lays
our own efforts alongside, and produces a plain-language verdict with a
prioritized what-to-do-next — seeded into the ops queue, not just prose.

Surfaces:
  GSC        marketing_gsc_daily/queries (14d vs prior 14d, ANOMALY-TRIMMED:
             days > 5x the window median are flagged and excluded from the
             trend — the Home Pride Aug 3-7 impression explosion made raw
             week-over-week read as an 85% crash)
  GBP        marketing_gbp_daily actions + impressions, review count/rating
  Maps       marketing_geogrid_scans latest vs previous per keyword/city
  Citations  citation_listings by status
  Calls      marketing_tracked_calls in-window counts
  Efforts    work_log line items in the window (what WE did)
  Open work  wrong-page findings + open ops notes

Output: clients/{slug}/analyzer/analysis-{date}.md + an [ANALYZER] ops note
carrying the verdict + top recommendations. Narrative by claude-sonnet from
the computed numbers only (the model never invents metrics).

CLI:
    python3 scripts/client_analyzer.py --slug restorationxpress
    python3 scripts/client_analyzer.py --all          # active fleet
    python3 scripts/client_analyzer.py --slug X --days 14 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import requests

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
       or os.environ["SUPABASE_SERVICE_KEY"])
HDR = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
       "Content-Type": "application/json"}
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-6"


def _get(path: str):
    r = requests.get(f"{SB}/rest/v1/{path}", headers=HDR, timeout=30)
    return r.json() if r.ok else []


def _slug_map() -> dict:
    return json.loads((ROOT / "clients" / "company_map.json").read_text())


# ------------------------------------------------------------------ windows
def _trim_anomalies(rows: list[dict], key: str) -> tuple[list[dict], list[dict]]:
    """Split rows into (normal, anomalous) — anomalous = value > 5x the
    median of non-zero values. Keeps trends honest around Google's broad-
    match testing spikes."""
    vals = [r.get(key) or 0 for r in rows]
    nz = [v for v in vals if v > 0]
    if len(nz) < 4:
        return rows, []
    med = statistics.median(nz)
    if med <= 0:
        return rows, []
    normal, weird = [], []
    for r in rows:
        (weird if (r.get(key) or 0) > 5 * med else normal).append(r)
    return normal, weird


def _sum(rows: list[dict], key: str) -> int:
    return sum(int(r.get(key) or 0) for r in rows)


def analyze(slug: str, days: int = 14) -> dict:
    smap = _slug_map()
    cid = smap.get(slug)
    if not cid:
        raise SystemExit(f"unknown slug {slug}")
    today = datetime.now(timezone.utc).date()
    cur_from = (today - timedelta(days=days)).isoformat()
    prev_from = (today - timedelta(days=2 * days)).isoformat()

    m: dict = {"slug": slug, "company_id": cid, "window_days": days,
               "generated_at": datetime.now(timezone.utc).isoformat()}

    # ---- GSC --------------------------------------------------------------
    gsc = _get(f"marketing_gsc_daily?company_id=eq.{cid}&date=gte.{prev_from}"
               "&select=date,total_clicks,total_impressions,avg_position&order=date")
    cur = [r for r in gsc if r["date"] >= cur_from]
    prev = [r for r in gsc if r["date"] < cur_from]
    cur_n, cur_anom = _trim_anomalies(cur, "total_impressions")
    prev_n, prev_anom = _trim_anomalies(prev, "total_impressions")
    m["gsc"] = {
        "clicks": _sum(cur, "total_clicks"), "clicks_prev": _sum(prev, "total_clicks"),
        "impressions_trimmed": _sum(cur_n, "total_impressions"),
        "impressions_prev_trimmed": _sum(prev_n, "total_impressions"),
        "anomalous_days": [r["date"] for r in cur_anom + prev_anom],
        "anomalous_impressions_excluded": _sum(cur_anom, "total_impressions")
        + _sum(prev_anom, "total_impressions"),
    }
    qs = _get(f"marketing_gsc_queries?company_id=eq.{cid}"
              "&select=query,clicks,impressions,position,striking"
              "&order=impressions.desc&limit=25")
    m["gsc"]["striking_distance"] = [q["query"] for q in qs if q.get("striking")][:8]
    m["gsc"]["top_queries"] = [
        {"q": q["query"], "clicks": q["clicks"], "impr": q["impressions"],
         "pos": round(float(q.get("position") or 0), 1)} for q in qs[:10]]

    # ---- GBP --------------------------------------------------------------
    gbp = _get(f"marketing_gbp_daily?company_id=eq.{cid}&date=gte.{prev_from}"
               "&select=date,call_clicks,website_clicks,direction_requests,"
               "impressions_desktop_maps,impressions_mobile_maps,"
               "impressions_desktop_search,impressions_mobile_search&order=date")
    gcur = [r for r in gbp if r["date"] >= cur_from]
    gprev = [r for r in gbp if r["date"] < cur_from]

    def _imp(rows):
        return sum(_sum(rows, k) for k in (
            "impressions_desktop_maps", "impressions_mobile_maps",
            "impressions_desktop_search", "impressions_mobile_search"))
    m["gbp"] = {
        "actions": {k: (_sum(gcur, k), _sum(gprev, k))
                    for k in ("call_clicks", "website_clicks", "direction_requests")},
        "impressions": (_imp(gcur), _imp(gprev)),
    }
    prof = _get(f"marketing_gbp_profiles?company_id=eq.{cid}"
                "&select=title,synced_at&limit=1")
    m["gbp"]["profile"] = prof[0] if prof else None

    # ---- Maps grid --------------------------------------------------------
    scans = _get(f"marketing_geogrid_scans?company_id=eq.{cid}"
                 "&select=scanned_at,keyword,city_label,avg_rank,pct_in_top3"
                 "&order=scanned_at.desc&limit=60")
    latest: dict[tuple, dict] = {}
    previous: dict[tuple, dict] = {}
    for s in scans:
        k = (s.get("keyword"), s.get("city_label"))
        if k not in latest:
            latest[k] = s
        elif k not in previous:
            previous[k] = s
    grid = []
    for k, s in latest.items():
        p = previous.get(k)
        grid.append({"keyword": k[0], "city": k[1],
                     "avg_rank": s.get("avg_rank"), "pct_top3": s.get("pct_in_top3"),
                     "prev_avg_rank": (p or {}).get("avg_rank"),
                     "scanned": str(s.get("scanned_at"))[:10]})
    m["maps"] = sorted(grid, key=lambda g: (g["avg_rank"] or 99))[:12]

    # ---- Citations --------------------------------------------------------
    cits = _get(f"citation_listings?company_id=eq.{cid}&select=directory,status,kind")
    by_status: dict[str, int] = {}
    for c in cits:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    m["citations"] = {"by_status": by_status, "total": len(cits)}
    nap = _get(f"user_integrations?client_id=eq.{cid}&provider=eq.citations"
               "&select=nap_audit:connection_metadata->nap_audit&limit=1")
    audit = (nap[0].get("nap_audit") if nap else None) or {}
    m["citations"]["audit_missing"] = [k for k, v in audit.items()
                                      if (v or {}).get("status") == "missing"][:15]

    # ---- Calls ------------------------------------------------------------
    calls = _get(f"marketing_tracked_calls?company_id=eq.{cid}"
                 f"&started_at=gte.{prev_from}&select=started_at,duration_seconds,source")
    ccur = [c for c in calls if str(c.get("started_at"))[:10] >= cur_from]
    cprev = [c for c in calls if str(c.get("started_at"))[:10] < cur_from]
    m["calls"] = {"current": len(ccur), "previous": len(cprev),
                  "current_over_60s": len([c for c in ccur
                                           if (c.get("duration_seconds") or 0) > 60])}

    # ---- Our efforts ------------------------------------------------------
    work = _get(f"marketing_work_log?company_id=eq.{cid}&created_at=gte.{cur_from}"
                "&select=category,action,summary&order=created_at.desc&limit=100")
    if isinstance(work, dict):
        work = []
    eff: dict[str, int] = {}
    for w in work:
        eff[w.get("category") or "other"] = eff.get(w.get("category") or "other", 0) + 1
    m["efforts"] = {"by_category": eff, "count": len(work),
                    "recent": [str(w.get("summary"))[:90] for w in work[:12]]}

    # ---- Open work --------------------------------------------------------
    seo_dir = ROOT / "clients" / slug / "seo"
    wrong_pages = []
    if seo_dir.exists():
        for f in sorted(seo_dir.glob("wrong-page*"), reverse=True)[:1]:
            wrong_pages.append(f.name)
    notes = _get(f"marketing_ops_notes?company_id=eq.{cid}&status=eq.open"
                 "&select=body&limit=20")
    m["open_work"] = {"wrong_page_reports": wrong_pages,
                      "open_notes": len(notes),
                      "note_heads": [str(n.get("body"))[:70] for n in notes[:6]]}
    return m


NARRATIVE_PROMPT = """You are the results analyst for a local-SEO agency serving restoration companies. Below is the computed metrics JSON for one client over a {days}-day window vs the prior window. Write the biweekly analysis in EXACTLY this structure, in plain language a non-technical business owner-operator agency founder can act on. NEVER invent numbers not present in the JSON. Note anomalous_days were excluded from impression trends (Google broad-match testing spikes) and say so briefly if any exist. No em dashes anywhere. Be honest when something is flat or down; never spin.

## Verdict
Two or three sentences: are results improving, flat, or declining, and the single most important reason why.

## What the numbers say
Bullet per surface (Google search, Google profile, map rankings, calls, citations): the real trend after anomaly trimming, with the numbers.

## What we did in this window
Summarize the efforts from the JSON in one short paragraph. If effort was thin, say so.

## Do next (prioritized)
The 3 highest-impact actions in priority order, each one line with WHY. Only actions supported by the data (missing citations, striking-distance queries, weak grid cities, junk photos, etc.).

After the internal analysis, write =====CLIENT===== on its own line, then a CLIENT-FACING version addressed to the business owner (you/your). Same honesty about trends, but constructive and free of agency-internal critique (never mention our logging, internal queues, or that effort was thin — translate that into what happens next instead). Structure: "## How your online presence is performing" (2-3 sentences), "## The numbers" (same surfaces, owner-friendly), "## What we're working on next" (the same 3 priorities, framed as our plan for them). No em dashes.

<metrics>
{metrics}
</metrics>"""


def narrate(m: dict) -> str:
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 2000,
              "messages": [{"role": "user", "content": NARRATIVE_PROMPT.format(
                  days=m["window_days"], metrics=json.dumps(m, default=str))}]},
        timeout=240)
    r.raise_for_status()
    return "".join(p.get("text", "") for p in r.json().get("content", []))


def run(slug: str, days: int, dry_run: bool) -> str:
    m = analyze(slug, days)
    full = narrate(m)
    body, _, client_body = full.partition("=====CLIENT=====")
    body = body.strip()
    client_body = client_body.strip()
    out_dir = ROOT / "clients" / slug / "analyzer"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = out_dir / f"analysis-{stamp}.md"
    path.write_text(f"# {slug} — biweekly analyzer — {stamp}\n\n" + body
                    + ("\n\n---\n\n# CLIENT-FACING VERSION\n\n" + client_body
                       if client_body else "")
                    + "\n\n---\n\n```json\n" + json.dumps(m, indent=1, default=str)
                    + "\n```\n")
    print(f"wrote {path.relative_to(ROOT)}")
    if not dry_run:
        verdict = body.split("## What the numbers say")[0].replace("## Verdict", "").strip()
        do_next = body.split("## Do next (prioritized)")[-1].strip()[:700]
        requests.post(f"{SB}/rest/v1/marketing_ops_notes", headers=HDR, json={
            "company_id": m["company_id"], "status": "open",
            "body": (f"[ANALYZER {stamp}] {verdict[:400]}\n\nDO NEXT:\n{do_next}"
                     f"\n\nFull report: clients/{slug}/analyzer/analysis-{stamp}.md")},
            timeout=30)
        print("ops note filed")
        if client_body:
            # Client-facing copy -> the app's Reports > Analysis tab (RLS
            # scoped read). The internal version above NEVER ships there.
            client_verdict = client_body.split("## The numbers")[0] \
                .replace("## How your online presence is performing", "").strip()
            requests.post(f"{SB}/rest/v1/marketing_analyzer_reports",
                          headers={**HDR, "Prefer": "return=minimal"}, json={
                              "company_id": m["company_id"],
                              "period_days": days,
                              "verdict": client_verdict[:500],
                              "body_md": client_body,
                              "metrics": {k: m[k] for k in
                                          ("gsc", "gbp", "maps", "citations", "calls")
                                          if k in m}},
                          timeout=30)
            print("client report published to the app")
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--if-due", action="store_true",
                    help="skip clients analyzed in the last 12 days (the "
                         "weekly cron + this flag = biweekly per client)")
    a = ap.parse_args()
    if a.all:
        smap = _slug_map()
        cos = {c["id"]: c for c in _get("companies?select=id,status&plan=ilike.rank%20ai")}
        inact = {"paused", "cancelled", "canceled", "churned", "inactive", "archived"}
        cutoff = (datetime.now(timezone.utc) - timedelta(days=12)).isoformat()
        recent = set()
        if a.if_due:
            recent = {r["company_id"] for r in _get(
                f"marketing_analyzer_reports?created_at=gte.{cutoff}"
                "&select=company_id")}
        for slug, cid in smap.items():
            st = str((cos.get(cid) or {}).get("status") or "").lower()
            if st in inact or cid not in cos:
                continue
            if a.if_due and cid in recent:
                print(f"{slug}: analyzed <12 days ago — skipped")
                continue
            try:
                run(slug, a.days, a.dry_run)
            except Exception as e:  # noqa: BLE001
                print(f"{slug}: FAILED {str(e)[:100]}")
        return 0
    if not a.slug:
        ap.error("--slug or --all")
    print(run(a.slug, a.days, a.dry_run)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
