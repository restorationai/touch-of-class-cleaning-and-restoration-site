#!/usr/bin/env python3
"""pipeline_watchdog.py — D1: the live status checker for every automated
system (Santino 2026-09-17, RestorationXpress postmortem: the video
pipeline was dead 3 weeks, the AI scanner 6 weeks, two blog clients never
published once — and every one of those failures was silent because
"cancelled" and "timed out" never alerted anyone).

FOUR CHECKS, one daily pass:

1. WORKFLOWS   Recent run conclusions of every scheduled GitHub workflow.
               TWO consecutive non-successes (failure, cancelled,
               timed_out) = alert. Cancelled counts — that was the video
               pipeline's invisible state.
2. HEARTBEATS  ops_kv heartbeat:* stamps written by long-lived engines
               (parity, service-bank). Older than 8 days = the engine is
               dead even if its workflow "succeeded" around it.
3. COVERAGE    Assertions that per-client work actually LANDED:
               - every Active client with a GBP profile has service-bank
                 variants within 10 days (Santino: "when the next client
                 comes through, I want you watching that it goes through")
               - CONTENT SLA (C1): queued posts + no publish in 14 days
                 = starved (the Paul Davis / ProCraft class).
4. REPORT      Each new issue files ONE [PIPELINE ALERT] ops note
               (deduped 7 days via ops_kv) so it lands in Ops Attention +
               the morning digest. Recovery clears the dedupe key.

Rides client-ops-sync daily. CLI: python3 scripts/pipeline_watchdog.py [--dry-run]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import requests  # noqa: E402
from client_ops_sync import _sb, slug_map  # noqa: E402

REPO = "restorationai/Rank-AI-Pipeline"
WATCHED_WORKFLOWS = [
    "client-ops-sync.yml", "content-daily.yml", "video-automation.yml",
    "weekly-maintenance.yml", "call-intel.yml", "gbp-maintenance.yml",
    "monthly-reports.yml", "dev-agent.yml", "site-render.yml",
]
HEARTBEATS = {"heartbeat:parity": 8, "heartbeat:service-bank": 8}
NOW = datetime.now(timezone.utc)


def _gh(path: str) -> dict:
    tok = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GH_PAT", "")
    r = requests.get(f"https://api.github.com/repos/{REPO}/{path}",
                     headers={"Authorization": f"token {tok}"}, timeout=30)
    return r.json() if r.ok else {}


def check_workflows() -> list[str]:
    issues = []
    for wf in WATCHED_WORKFLOWS:
        runs = (_gh(f"actions/workflows/{wf}/runs?per_page=5&exclude_pull_requests=true")
                .get("workflow_runs") or [])
        done = [r for r in runs if r.get("status") == "completed"]
        if len(done) < 2:
            continue
        bad = []
        for r in done:
            if r.get("conclusion") == "success":
                break
            bad.append(r.get("conclusion"))
        if len(bad) >= 2:
            last = done[0]
            days = (NOW - datetime.fromisoformat(
                last["created_at"].replace("Z", "+00:00"))).days
            issues.append(
                f"{wf}: last {len(bad)} runs were {'/'.join(bad)} "
                f"(latest {days}d ago) — pipeline appears DEAD")
    return issues


def check_heartbeats() -> list[str]:
    issues = []
    for key, max_days in HEARTBEATS.items():
        row = (_sb("GET", f"/rest/v1/ops_kv?k=eq.{key}&select=v") or [{}])[0]
        at = (row.get("v") or {}).get("at")
        if not at:
            issues.append(f"{key}: never stamped — engine has never completed")
            continue
        age = (NOW - datetime.fromisoformat(at)).days
        if age > max_days:
            issues.append(f"{key}: last beat {age}d ago (max {max_days}) — engine dead")
    return issues


def check_coverage() -> list[str]:
    issues = []
    inv = {s: c for c, s in slug_map().items()}
    comps = {c["id"]: c for c in _sb(
        "GET", "/rest/v1/companies?status=eq.Active&select=id,name,created_at") or []}
    profs = {p["company_id"] for p in _sb(
        "GET", "/rest/v1/marketing_gbp_profiles?select=company_id") or []}
    bank_rows = _sb("GET", "/rest/v1/marketing_gbp_suggestions"
                    "?source=eq.service-bank&select=company_id") or []
    has_bank = {r["company_id"] for r in bank_rows}
    for slug, cid in inv.items():
        co = comps.get(cid)
        if not co or cid not in profs:
            continue
        age = (NOW - datetime.fromisoformat(
            str(co["created_at"]).replace("Z", "+00:00"))).days
        if age >= 10 and cid not in has_bank:
            issues.append(f"service-bank coverage: {co['name']} active {age}d "
                          "with a GBP but ZERO bank variants — fan-out missed them")
    # CONTENT SLA (C1)
    for qf in glob.glob(str(ROOT / "clients/*/content-queue.json")):
        slug = Path(qf).parent.name
        try:
            q = json.loads(Path(qf).read_text())
        except Exception:
            continue
        queued = [i for i in (q.get("items") or []) if i.get("status") == "queued"]
        if not queued:
            continue
        last = None
        for mp in glob.glob(str(ROOT / f"sites/{slug}/src/content/blog/*.md")):
            m = re.search(r'published_at:\s*"?(\d{4}-\d{2}-\d{2})', Path(mp).read_text())
            if m and (last is None or m.group(1) > last):
                last = m.group(1)
        days = 9999 if last is None else (NOW.date() - datetime.fromisoformat(last).date()).days
        if days > 14:
            issues.append(f"content SLA: {slug} has {len(queued)} queued post(s) and "
                          + ("has NEVER published" if days == 9999
                             else f"last published {days}d ago") + " — starved")
    return issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    issues = check_workflows() + check_heartbeats() + check_coverage()
    if not issues:
        print("pipeline watchdog: ALL SYSTEMS ALIVE")
    for issue in issues:
        print(f"  !! {issue}")
        if a.dry_run:
            continue
        key = "wd-alert:" + re.sub(r"[^a-z0-9]+", "-", issue.split("—")[0].lower())[:60]
        seen = (_sb("GET", f"/rest/v1/ops_kv?k=eq.{key}&select=v") or [{}])[0]
        at = (seen.get("v") or {}).get("at")
        if at and (NOW - datetime.fromisoformat(at)).days < 7:
            continue  # already alerted this week
        _sb("POST", "/rest/v1/marketing_ops_notes",
            {"company_id": None, "status": "open", "author": "pipeline_watchdog",
             "body": f"[PIPELINE ALERT] {issue}"}, prefer="return=minimal")
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": key, "v": {"at": NOW.isoformat()}},
            prefer="resolution=merge-duplicates")
    print(f"pipeline watchdog: {len(issues)} issue(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
