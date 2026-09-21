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
HEARTBEATS = {"heartbeat:parity": 8, "heartbeat:service-bank": 8,
              "heartbeat:ai-scan": 5}
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


def _self_heal_ai_scan() -> str:
    """B3 (Santino 2026-09-17): a stale scan heartbeat doesn't just alert —
    it DISPATCHES a fresh weekly-maintenance run (which runs the sharded,
    stalest-first scanner). Auto-run instead of a label."""
    tok = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GH_PAT", "")
    r = requests.post(
        f"https://api.github.com/repos/{REPO}/actions/workflows/weekly-maintenance.yml/dispatches",
        headers={"Authorization": f"token {tok}"},
        json={"ref": "main"}, timeout=30)
    return "dispatched" if r.status_code == 204 else f"dispatch failed {r.status_code}"


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
            note = ""
            if key == "heartbeat:ai-scan":
                note = f"; self-heal: {_self_heal_ai_scan()}"
            issues.append(f"{key}: last beat {age}d ago (max {max_days}) — engine dead{note}")
    return issues


def check_site_area_gap() -> list[str]:
    """Site area pages lagging the GBP area set (Santino 2026-09-19, ACS:
    Google carried 16 areas while the site served 7 and nothing said so).
    gbp_parity writes ops_kv 'site-area-gap' {slug: {count, since}} nightly
    and its ripple (plan generate + add-pages + 3:07 render sweep) should
    drain any gap within ~2 nights. A gap older than 3 days means the
    ripple chain broke somewhere — alert with the client's name."""
    issues = []
    gaps = ((_sb("GET", "/rest/v1/ops_kv?k=eq.site-area-gap&select=v")
             or [{}])[0].get("v") or {})
    for slug, g in sorted(gaps.items()):
        since = g.get("since")
        if not since:
            continue
        age = (NOW.date() - datetime.fromisoformat(since).date()).days
        if age > 3:
            issues.append(
                f"site-area gap: {slug} site is missing {g.get('count')} "
                f"GBP area page(s), stuck {age}d — ripple/render sweep broke")
    return issues


def check_citation_stall() -> list[str]:
    """DBA verified but no citation order (Kenny + Heritage 2026-09-19: both
    sat in citations_building with nothing building — order placement is
    deliberately manual credit-spend, so the failure mode is silence).
    Alert-only: a human places the order; this just refuses to let the
    stage lie."""
    issues = []
    try:
        kv = ((_sb("GET", "/rest/v1/ops_kv?k=eq.rename-pipeline&select=v")
               or [{}])[0].get("v") or {})
    except Exception:  # noqa: BLE001
        return issues
    for cid, e in (kv.get("clients") or kv).items():
        if not isinstance(e, dict):
            continue
        slug = e.get("slug") or cid
        # dba_on_file = the honest stage for this exact state (2026-09-19
        # split); flag it once it lingers past 2 days. Keep the old
        # citations_building/no-order check as a belt-and-suspenders.
        if e.get("stage") == "dba_on_file":
            since = str(e.get("since") or "")[:10]
            try:
                age = (NOW.date()
                       - datetime.fromisoformat(since).date()).days
            except ValueError:
                age = 99
            if age >= 2:
                issues.append(
                    f"citation stall: {slug} DBA on file {age}d with no "
                    "citation order — click Order on the rename card")
            continue
        if e.get("stage") != "citations_building":
            continue
        try:
            bl = json.loads((ROOT / "clients" / f"{slug}.json")
                            .read_text()).get("brightlocal") or {}
        except Exception:  # noqa: BLE001
            bl = {}
        if not bl.get("ordered_at"):
            issues.append(
                f"citation stall: {slug} has a verified DBA but no citation "
                "order placed — stage says building, nothing is building "
                "(run brightlocal.py order)")
    return issues


def check_lsa_leads() -> list[str]:
    """A serving LSA with ZERO leads in 14 days (C, Santino 2026-09-20:
    'accounts that are live but aren't getting calls so we can know which
    accounts we should go in and check on'). Serving = ENABLED campaign
    with impressions in the last 7 days; unknown leads (field absent)
    never alerts — the detector hasn't measured yet."""
    issues = []
    try:
        cos = _sb("GET", "/rest/v1/companies?status=eq.Active"
                  "&select=name,lsa:integration_settings->lsa") or []
    except Exception:  # noqa: BLE001
        return issues
    for co in cos:
        lsa = co.get("lsa") or {}
        if str(lsa.get("campaign_status") or "").upper() != "ENABLED":
            continue
        if int((lsa.get("metrics_7d") or {}).get("impressions") or 0) <= 0:
            continue  # not provably serving
        leads = lsa.get("leads_14d")
        if not isinstance(leads, dict) or "total" not in leads:
            continue  # unmeasured is unknown, never zero
        if int(leads.get("total") or 0) == 0:
            issues.append(
                f"LSA silent: {str(co.get('name') or '?').strip()} is "
                "serving (impressions last 7d) but 0 leads in 14d — "
                "check budget/job types/ranking")
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
    # Eligibility check (2026-09-18 first pass): RT Olson (plumbing/HVAC,
    # 150 GBP services) and Arch (testing-only environmental) alerted as
    # "missed" when the restoration bank truthfully has NOTHING for them.
    # Only flag clients whose capabilities match at least one bank family.
    from gbp_service_bank import client_capabilities, load_bank
    try:
        bank = load_bank()
    except Exception:  # noqa: BLE001
        bank = {}
    from gbp_auto_apply import _norm
    for slug, cid in inv.items():
        co = comps.get(cid)
        if not co or cid not in profs:
            continue
        age = (NOW - datetime.fromisoformat(
            str(co["created_at"]).replace("Z", "+00:00"))).days
        if age < 10 or cid in has_bank:
            continue
        try:
            caps, on_gbp, plumbing_ok = client_capabilities(slug, cid)
        except Exception:  # noqa: BLE001
            caps, on_gbp, plumbing_ok = set(), set(), False
        eligible = False
        for base, fam in bank.items():
            if isinstance(fam, dict) and fam.get("license_gate") == "plumbing"                     and not plumbing_ok:
                continue
            if (base in caps or _norm(base.replace("-", " ")) in on_gbp
                    or any(_norm(base.replace("-", " ")) in g for g in on_gbp)):
                eligible = True
                break
        if eligible:
            issues.append(f"service-bank coverage: {co['name']} active {age}d "
                          "with a GBP but ZERO bank variants — fan-out missed them")
    # OPTIMIZER SLA (A4): auto-safe items are supposed to clear on the
    # NIGHTLY sweep — any client where they sit >7 days means the sweep is
    # skipping them (or dead), which is exactly how ~700 items piled up
    # invisibly before 09-17.
    stale = _sb("GET", "/rest/v1/marketing_gbp_suggestions?status=eq.open"
                # auto_safe only (2026-09-18): without this filter the SLA
                # counted human-review items and kept alerting on piles the
                # nightly apply had already cleared.
                "&auto_safe=is.true"
                "&item_type=in.(service,description)"
                # '+00:00' in an ISO stamp URL-decodes to a space and 400s (same
                # gotcha call_alerts hit) — always the Z form in query strings.
                f"&created_at=lt.{(NOW - timedelta(days=7)).isoformat().replace('+00:00', 'Z')}"
                "&select=company_id") or []
    from collections import Counter
    stale_by = Counter(r["company_id"] for r in stale)
    for cid, n in stale_by.most_common(5):
        nm = (comps.get(cid) or {}).get("name") or cid
        issues.append(f"optimizer SLA: {nm} has {n} auto-safe item(s) open "
                      ">7 days — the nightly apply is not clearing them")

    # PER-CLIENT CADENCE SLA (Santino 2026-09-17: "twice per week per
    # client... a full-sweep metric breaks as we acquire clients rapidly").
    # Judged individually: every active client with a scaffolded blog and
    # material to post (queued or banked items) must show >= 2 posts in the
    # trailing 8 days. No fleet averages — growth can never dilute one
    # client's promise invisibly.
    for mp_dir in glob.glob(str(ROOT / "sites/*/src/content/blog")):
        slugc = Path(mp_dir).parent.parent.parent.name
        qf2 = ROOT / "clients" / slugc / "content-queue.json"
        if not qf2.exists():
            continue
        try:
            q2 = json.loads(qf2.read_text())
        except Exception:
            continue
        material = any(i.get("status") in ("queued", "banked")
                       for i in (q2.get("items") or []))
        if not material:
            continue
        recent = 0
        for mp in glob.glob(mp_dir + "/*.md"):
            m = re.search(r'published_at:\s*"?(\d{4}-\d{2}-\d{2})', Path(mp).read_text())
            if m and (NOW.date() - datetime.fromisoformat(m.group(1)).date()).days <= 8:
                recent += 1
        if recent < 2:
            issues.append(f"cadence SLA: {slugc} published {recent}/2 posts "
                          "in the last 8 days (promise: 2 per week)")

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
        # C2 precision (2026-09-17): a client whose site has no scaffolded
        # blog CANNOT publish — that is "waiting on site build", not
        # "starved" (Paul Davis Charleston case). The SLA only judges
        # clients the writer could actually serve.
        if not (ROOT / f"sites/{slug}/src/content/blog").exists():
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
    issues = (check_workflows() + check_heartbeats() + check_coverage()
              + check_site_area_gap() + check_citation_stall()
              + check_lsa_leads())
    if not issues:
        print("pipeline watchdog: ALL SYSTEMS ALIVE")
    fresh: list[str] = []
    for issue in issues:
        print(f"  !! {issue}")
        if a.dry_run:
            continue
        # digits stripped (2026-09-19: '0/2 posts' -> '1/2 posts' minted a
        # NEW key daily, so one starved client stacked rows + SMS noise)
        key = "wd-alert:" + re.sub(
            r"[^a-z]+", "-", issue.split("—")[0].lower())[:60]
        seen = (_sb("GET", f"/rest/v1/ops_kv?k=eq.{key}&select=v") or [{}])[0]
        at = (seen.get("v") or {}).get("at")
        if at and (NOW - datetime.fromisoformat(at)).days < 7:
            continue  # already alerted this week
        fresh.append(issue)
        _sb("POST", "/rest/v1/marketing_ops_notes",
            {"company_id": None, "status": "open", "author": "pipeline_watchdog",
             "body": f"[PIPELINE ALERT] {issue}"}, prefer="return=minimal")
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": key, "v": {"at": NOW.isoformat()}},
            prefer="resolution=merge-duplicates")
    # SMS to Santino (2026-09-17: "not only Ops Attention but also a text —
    # I don't really view Ops Attention"). One text per run, NEW issues only
    # (the 7-day dedupe above already keeps repeats quiet). Same ops-ping
    # path the credit canary uses.
    if fresh and not a.dry_run:
        heads = [i.split(" — ")[0] for i in fresh[:4]]
        body = (f"PIPELINE ALERT ({len(fresh)} new): " + "; ".join(heads)
                + ("; +more" if len(fresh) > 4 else "")
                + ". Details in the app's Errors tab.")
        try:
            from client_concierge import (send_message, OPS_PING_CONTACT_ID,
                                          OPS_PING_CELL, SendBlocked)
            send_message({"id": OPS_PING_CONTACT_ID, "phone": OPS_PING_CELL},
                         "sms", body[:640])
            print("  -> alert SMS sent")
        except Exception as e:  # noqa: BLE001 — SMS failure never kills the run
            print(f"  -> alert SMS failed: {str(e)[:100]}")
    print(f"pipeline watchdog: {len(issues)} issue(s), {len(fresh)} new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
