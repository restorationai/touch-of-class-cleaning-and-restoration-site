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


def check_nap_parity() -> list[str]:
    """Visible footer NAP vs schema PostalAddress vs GBP (DISS/Addi
    2026-09-24: the footer paired the street with the MARKETING city —
    'Youngstown, OH 16121' for a Farrell PA office — while the same page's
    JSON-LD said Farrell. The client caught it; Monica and Claude both
    confirmed from the schema and called the client wrong.)

    Rule (ZIP-anchored, low false-positive): any visible 'City, ST 12345'
    whose ZIP matches the schema postalCode but whose city/state disagrees
    with addressLocality/addressRegion = the footer-pairing bug. Plus: GBP
    profile city != schema city = cross-surface NAP drift."""
    issues = []
    import urllib.request
    for p in sorted((ROOT / "clients").glob("*.json")):
        if p.stem == "company_map":
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        if not d.get("cut_over_at") or not d.get("domain"):
            continue
        try:
            req = urllib.request.Request(
                f"https://{d['domain']}/", headers={"User-Agent": "rankai-watchdog"})
            html = urllib.request.urlopen(req, timeout=15).read().decode(
                "utf-8", "ignore")
        except Exception:  # noqa: BLE001
            continue        # unreachable site is its own (existing) alarm
        m = re.search(r'"addressLocality"\s*:\s*"([^"]+)"\s*,\s*'
                      r'"addressRegion"\s*:\s*"([^"]+)"\s*,\s*'
                      r'"postalCode"\s*:\s*"([^"]+)"', html)
        if not m:
            continue
        s_city, s_state, s_zip = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        visible = re.sub(r"<script[^>]*>.*?</script>", " ", html,
                         flags=re.S | re.I)
        visible = re.sub(r"<[^>]+>", " ", visible)
        for vm in re.finditer(r"([A-Za-z .'\-]{3,40}),\s*([A-Z]{2})\s+(\d{5})",
                              visible):
            v_blob, v_state, v_zip = (vm.group(1).strip(), vm.group(2),
                                      vm.group(3))
            # The visible capture may swallow the street tail into the
            # "city" group — only alarm when the schema city is absent
            # from the whole pairing (or the state flat-out disagrees).
            if v_zip == s_zip and (
                    s_city.lower() not in v_blob.lower()
                    or v_state.upper() != s_state.upper()):
                issues.append(
                    f"NAP mismatch: {p.stem} page shows '{v_blob}, {v_state} "
                    f"{v_zip}' but schema says '{s_city}, {s_state} {s_zip}' "
                    "— footer/marketing-city pairing bug")
                break
        try:
            cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
        except Exception:  # noqa: BLE001
            cmap = {}
        cid = cmap.get(p.stem) or ""
        if cid:
            try:
                prof = _sb("GET", "/rest/v1/marketing_gbp_profiles"
                           f"?company_id=eq.{cid}&select=address") or []
                gaddr = (prof[0].get("address") or "") if prof else ""
                if gaddr and s_city.lower() not in gaddr.lower():
                    issues.append(
                        f"NAP drift: {p.stem} GBP address '{gaddr[:60]}' does "
                        f"not contain the site's schema city '{s_city}'")
            except Exception:  # noqa: BLE001
                pass
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


def check_email_claims() -> list[str]:
    """Phase 2.1 (Santino 2026-09-22): a client TEXTED that they emailed
    something. The concierge armed a 2h watch; if no [CLIENT EMAIL] intake
    note has appeared for that company since, the mail likely went to an
    address we don't poll — alert instead of letting it vanish."""
    from datetime import datetime, timedelta, timezone
    try:
        rows = _sb("GET", "/rest/v1/ops_kv?k=eq.email-claim-watch&select=v") or []
    except Exception as e:  # noqa: BLE001
        return [f"email-claim check failed: {str(e)[:80]}"]
    claims = (rows[0].get("v") if rows else {}) or {}
    if not claims:
        return []
    now = datetime.now(timezone.utc)
    issues, keep = [], {}
    for cid, c in claims.items():
        try:
            at = datetime.fromisoformat(str(c.get("at")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if now - at < timedelta(hours=2):
            keep[cid] = c
            continue
        since = at.strftime("%Y-%m-%dT%H:%M:%SZ")
        got = _sb("GET", "/rest/v1/marketing_ops_notes"
                  f"?company_id=eq.{cid}"
                  f"&created_at=gt.{since}"
                  "&body=ilike.*CLIENT EMAIL*&select=id&limit=1") or []
        if not got:
            issues.append(
                f"email claimed but never arrived: {cid} texted "
                f"\"{str(c.get('quote'))[:120]}\" at {str(c.get('at'))[:16]} "
                "and no client email was ingested in 2h+ — they may have "
                "emailed an address we don't poll; ask where they sent it")
    try:
        _sb("PATCH", "/rest/v1/ops_kv?k=eq.email-claim-watch", {"v": keep})
    except Exception:  # noqa: BLE001
        pass
    return issues


def check_stuck_lead_audits() -> list[str]:
    """Shane Dodson 2026-09-21: Railway deploys kill in-flight audit
    threads, the job row stays 'running' forever, the lead's GHL fields
    never populate, and the timed sales SMS goes out with blank merge
    fields + an invalid media URL. A lead_audit 'running' for 2+ hours is
    dead — flag it loudly (5 sat silent, oldest since 09-11)."""
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)
              ).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        rows = _sb("GET", "/rest/v1/marketing_jobs?type=eq.lead_audit"
                   "&status=eq.running"
                   f"&started_at=lt.{cutoff}"
                   "&select=id,params,started_at") or []
    except Exception as e:  # noqa: BLE001
        return [f"lead-audit stuck-job check failed: {str(e)[:80]}"]
    issues = []
    for r in rows:
        p = r.get("params") or {}
        issues.append(
            "lead audit STUCK: job for "
            f"{p.get('name') or p.get('email') or r['id']} "
            f"({p.get('domain') or 'no domain'}) has been 'running' since "
            f"{str(r.get('started_at'))[:16]} — the thread is dead "
            "(deploy restart); re-run it and deliver the GHL fields "
            "before the sales sequence fires blanks")
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
              + check_lsa_leads()
              + check_stuck_lead_audits()
              + check_email_claims()
              + check_nap_parity())
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
