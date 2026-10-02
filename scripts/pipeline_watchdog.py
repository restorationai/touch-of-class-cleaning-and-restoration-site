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
4. REPORT      ONE open [PIPELINE ALERT] card per alert key, refreshed in
               place every run; the card auto-resolves when the condition
               clears and reopens on relapse (reconcile_notes). Only a
               brand-new condition texts Santino.

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
    "lsa-lead-review.yml", "site-regression-watch.yml",
    "index-watch.yml", "geogrid-scan.yml",
    # onboarding lanes (2026-10-01: both died silently for days)
    "bootstrap-new-clients.yml", "site-build.yml",
]
HEARTBEATS = {"heartbeat:parity": 8, "heartbeat:service-bank": 8,
              "heartbeat:ai-scan": 5, "heartbeat:lsa-lead-review": 2,
              "heartbeat:client-followups": 2}
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
    # 12h cooldown (2026-09-29): every watchdog pass re-dispatched while the
    # beat was stale, so 3 weekly-maintenance runs overlapped today and ~10
    # on 09-28. One heal per 12h; the stamp lives in ops_kv.
    key = "self-heal:ai-scan"
    last = ((_sb("GET", f"/rest/v1/ops_kv?k=eq.{key}&select=v") or [{}])[0]
            .get("v") or {}).get("at")
    if last and NOW - datetime.fromisoformat(last) < timedelta(hours=12):
        return f"already dispatched {last[:16]}Z (12h cooldown)"
    tok = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GH_PAT", "")
    _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
        {"k": key, "v": {"at": NOW.isoformat()}},
        prefer="resolution=merge-duplicates,return=minimal")
    r = requests.post(
        f"https://api.github.com/repos/{REPO}/actions/workflows/weekly-maintenance.yml/dispatches",
        headers={"Authorization": f"token {tok}"},
        json={"ref": "main"}, timeout=30)
    return "dispatched" if r.status_code == 204 else f"dispatch failed {r.status_code}"


def check_conflict_markers() -> list[str]:
    """Git conflict markers committed to main (09-30: an autostash conflict
    shipped them into clients/_ops/last-sync.json and every ops-sync run
    crashed for hours, silently stalling onboarding). One alert listing the
    files; scripts/conflict_marker_guard.py is the fix."""
    import subprocess
    try:
        r = subprocess.run(["git", "grep", "-l", "-E",
                            "^(<<<<<<<|>>>>>>>) (Updated upstream|Stashed changes|HEAD)",
                            "--", "clients", "sites", "scripts", "templates"],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    except Exception:  # noqa: BLE001
        return []
    files = [f for f in r.stdout.split() if f]
    if not files:
        return []
    return [f"git conflict markers committed in {len(files)} file(s): "
            f"{', '.join(files[:6])} — automated runs reading them will crash; "
            "run scripts/conflict_marker_guard.py and commit"]


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


INDEX_WATCH_MAX_DAYS = 8


def _age_days(iso) -> float | None:
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (NOW - d).total_seconds() / 86400
    except (ValueError, TypeError):
        return None


def check_index_watch() -> list[str]:
    """Per-site heartbeat for the weekly Google index check (2026-10-01).
    The old bulk step timed out alphabetically for seven weeks and six live
    sites went unchecked with no alert. index_watchdog stamps ops_kv
    'index-watch:{slug}' on every attempt (attempted_at / attempt_note) and
    on every success (checked_at). Any live site whose last SUCCESSFUL check
    is older than 8 days alerts, with the last attempt's reason. A site that
    went live under 8 days ago and was never checked yet gets grace."""
    try:
        from index_watchdog import live_slugs  # noqa: PLC0415
        slugs = live_slugs()
    except Exception as e:  # noqa: BLE001
        return [f"index-watch: live-site list failed ({str(e)[:80]}), heartbeat unchecked"]
    sites = {r.get("rank_ai_slug"): r for r in (_sb(
        "GET", "/rest/v1/marketing_sites?select=rank_ai_slug,apex_completed_at,"
        "domain_ns_live_at,gsc_property_url") or [])}
    kv = {r["k"]: (r.get("v") or {}) for r in (_sb(
        "GET", "/rest/v1/ops_kv?k=like.index-watch:*&select=k,v") or [])}
    issues = []
    for slug in slugs:
        v = kv.get("index-watch:" + slug) or {}
        age = _age_days(v.get("checked_at"))
        if age is not None and age <= INDEX_WATCH_MAX_DAYS:
            continue
        if age is None:
            ms = sites.get(slug) or {}
            live_age = _age_days(ms.get("apex_completed_at") or ms.get("domain_ns_live_at"))
            if live_age is not None and live_age <= INDEX_WATCH_MAX_DAYS:
                continue
        why = v.get("attempt_note") or (
            "no attempt recorded (index-watch.yml did not reach it)"
            if not v.get("attempted_at") else "last attempt sampled nothing")
        if not (sites.get(slug) or {}).get("gsc_property_url"):
            why += "; no gsc_property_url in marketing_sites (run gsc_register.py --slug)"
        issues.append(
            f"index-watch {slug}: Google index check stale "
            + ("(never succeeded)" if age is None else f"({int(age)}d since last success)")
            + f" - {why}")
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
    # ilike, not eq.Active (2026-10-01 audit): DISS Restoration's row says
    # 'active' (lowercase) and was invisible to every SLA below while the
    # scheduler (case-insensitive) kept posting for it.
    comps = {c["id"]: c for c in _sb(
        "GET", "/rest/v1/companies?status=ilike.active&select=id,name,created_at") or []}
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
    # active clients only (2026-09-29: an inactive CO-… row surfaced by id)
    stale_by = Counter(r["company_id"] for r in stale if r["company_id"] in comps)
    # Access-blocked clients (gbp_auto_apply's ledger: no OAuth, listing not
    # in the connected account, suspended/unverified) can't be cleared by any
    # rerun, so they are not "apply broken" (2026-09-29: 297 of 338 stale
    # items were these). One summary line instead, naming the real blocker.
    blocked = ((_sb("GET", "/rest/v1/ops_kv?k=eq.gbp-auto-apply-blocked&select=v")
                or [{}])[0].get("v") or {})
    for cid, n in stale_by.most_common():
        if cid in blocked:
            continue
        nm = (comps.get(cid) or {}).get("name") or cid
        issues.append(f"optimizer SLA: {nm} has {n} auto-safe item(s) open "
                      ">7 days — the nightly apply is not clearing them")
        if sum(1 for i in issues if i.startswith("optimizer SLA:")) >= 5:
            break
    held = sorted((comps.get(c) or {}).get("name") or c
                  for c in stale_by if c in blocked)
    if held:
        issues.append(f"optimizer blocked on Google access: {len(held)} client(s) "
                      f"({', '.join(held)}) — fix their Google connection/listing "
                      "access; the nightly apply cannot reach them")

    # PER-CLIENT CADENCE SLA (Santino 2026-09-17: "twice per week per
    # client... a full-sweep metric breaks as we acquire clients rapidly").
    # Judged individually: every active client with a scaffolded blog and
    # material to post (queued or banked items) must show >= 2 posts in the
    # trailing 8 days. No fleet averages — growth can never dilute one
    # client's promise invisibly.
    fleet_last = None      # newest published_at across every judged client
    fleet_judged = 0
    for mp_dir in glob.glob(str(ROOT / "sites/*/src/content/blog")):
        slugc = Path(mp_dir).parent.parent.parent.name
        # Active clients only (2026-09-29: dead mcc-restoration kept filing
        # a weekly 'cadence SLA' card for a site we no longer post to).
        if inv.get(slugc) not in comps:
            continue
        qf2 = ROOT / "clients" / slugc / "content-queue.json"
        if not qf2.exists():
            issues.append(f"cadence SLA: {slugc} has a blog but NO content-queue.json "
                          "- the writer can never post for it")
            continue
        try:
            q2 = json.loads(qf2.read_text())
        except Exception as e:  # noqa: BLE001
            # 2026-10-01 audit: a conflict-marked queue (tdi-builders 09-24)
            # used to be skipped here in silence while it crashed the whole
            # content-daily plan. Unreadable state is itself the alert.
            issues.append(f"cadence SLA: {slugc} content-queue.json is unreadable "
                          f"({str(e)[:80]}); fix the JSON (conflict markers?)")
            continue
        items2 = q2.get("items") or []
        material = any(i.get("status") in ("queued", "banked") for i in items2)
        recent = 0
        for mp in glob.glob(mp_dir + "/*.md"):
            m = re.search(r'published_at:\s*"?(\d{4}-\d{2}-\d{2})', Path(mp).read_text())
            if not m:
                continue
            if fleet_last is None or m.group(1) > fleet_last:
                fleet_last = m.group(1)
            if (NOW.date() - datetime.fromisoformat(m.group(1)).date()).days <= 8:
                recent += 1
        fleet_judged += 1
        if recent < 2:
            issues.append(f"cadence SLA: {slugc} published {recent}/2 posts "
                          "in the last 8 days (promise: 2 per week)"
                          + ("" if material else "; queue is EMPTY, System 1 refill is not landing"))
    # FLEET STALL (2026-10-01 audit): the per-client 8-day window needs ~6
    # days to notice an engine that stopped for EVERYONE (09-24..09-28: the
    # content-daily plan crashed and every run still went green). The engine
    # posts each client every 2 days, so a fleet with no post in 3 days is
    # down, whatever the workflow conclusions say.
    if fleet_judged >= 3 and fleet_last:
        gap = (NOW.date() - datetime.fromisoformat(fleet_last).date()).days
        if gap >= 3:
            issues.append(f"content engine stalled fleet-wide: no blog post published for "
                          f"ANY client in {gap} days (last {fleet_last}); check the "
                          "content-daily plan/write jobs")

    # CONTENT SLA (C1)
    for qf in glob.glob(str(ROOT / "clients/*/content-queue.json")):
        slug = Path(qf).parent.name
        if inv.get(slug) not in comps:
            continue  # active clients only (see cadence SLA)
        try:
            q = json.loads(Path(qf).read_text())
        except Exception:
            continue  # already reported by the cadence SLA above
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


def check_geogrid() -> list[str]:
    """MAP RANKINGS (Santino 2026-10-01: "feels like the system is broken").
    For ten days every map scan stored 0-found, fleet runs were killed
    partway every month, configured radii/keywords were never scanned, and
    nothing said so. Outcome checks, one card per problem class:

      coverage   an active client has configured (keyword x city x radius)
                 combos with no scan in 35 days (or that hit the 3-failure
                 monthly cap), judged after the first 3 days of a month and
                 for clients older than 3 days
      images     a client's latest map image is missing or does not serve
      zero       every home-grid scan of a client found nothing (a listing
                 identity / centering problem, not a ranking)"""
    try:
        import geogrid_coverage as gc  # noqa: PLC0415
        roster = gc.active_roster()
        comps = {c["id"]: c for c in _sb(
            "GET", "/rest/v1/companies?select=id,created_at") or []}
    except Exception as e:  # noqa: BLE001
        return [f"geogrid watchdog failed — {str(e)[:100]}"]
    cmap = gc.company_map()
    incomplete, broken, zero = [], [], []
    for slug in roster:
        cid = cmap.get(slug)
        try:
            age = (NOW - datetime.fromisoformat(str(
                (comps.get(cid) or {}).get("created_at")).replace("Z", "+00:00"))).days
        except (TypeError, ValueError):
            age = 999
        try:
            cov = gc.coverage(slug)
        except Exception as e:  # noqa: BLE001
            incomplete.append(f"{slug} (unreadable: {str(e)[:40]})")
            continue
        gap = len(cov["missing"]) + len(cov["stale"])
        if gap and age >= 3 and NOW.day >= 4:
            capped = sum(1 for v in gc.failures(slug).values()
                         if int((v or {}).get("count") or 0) >= gc.MAX_FAILS_PER_MONTH)
            incomplete.append(f"{slug} {len(cov['present'])}/{cov['expected']}"
                              + (f" ({capped} gave up after 3 failures)" if capped else ""))
        latest = [c["scan"] for c in cov["present"]]
        bad = gc.broken_images(latest) if latest else []
        if bad:
            broken.append(f"{slug} {len(bad)}/{len(latest)}")
        home = cov["present"] and [c for c in cov["present"]
                                   if c["label"] == gc.load_config(slug)[1][0]["label"]]
        if home and all(not c["scan"].get("found_points") for c in home):
            zero.append(f"{slug} ({len(home)} home grids)")
    issues = []
    if incomplete:
        issues.append("geogrid coverage incomplete — configured map scans missing or "
                      f"older than 35 days for {len(incomplete)} client(s): "
                      + "; ".join(incomplete[:15])
                      + ". The daily geogrid-scan lane retries due combos; check its "
                      "plan log and ops_kv geogrid-failures:* for the errors")
    if broken:
        issues.append("geogrid images broken — latest map image missing or not "
                      f"serving for {len(broken)} client(s): " + "; ".join(broken[:15])
                      + ". The app falls back to drawing the stored points")
    if zero:
        issues.append("geogrid zero-found home grids — every home-city map found "
                      f"nothing for {len(zero)} client(s): " + "; ".join(zero[:15])
                      + ". Usually the listing identity (place_id/name) or the grid "
                      "center, not a real ranking; check plan-input brand + home city lat/lng")
    return issues


ONBOARD_WINDOW_DAYS = 30


def check_onboarding() -> list[str]:
    """NEW-CLIENT JOURNEY (Santino 2026-10-01: "is your watcher watching all
    of our systems, especially for the newer clients: new site builds and
    automatic outreach regarding the profile renames?"). Every lane below
    failed silently that week: bootstrap cancelled for days, sites built
    then lost, the rename pitch parked on a dev card, a hand-sent preview
    unrecorded. One card per stalled step, per client, for clients in
    their first 30 days (Active, Rank AI plan, paid):

      bootstrap   paid > 6h with no rank-ai slug (no client files)
      site        bootstrapped > 2d with no built site in the repo
      reveal      past the reveal day (10d, or preview_reveal_on) with no
                  preview shown (not apex-live, no site-preview-feedback row)
      rename      kickoff mined > 2d, name options exist, no pitch sent /
                  no rename conversation / no decision; or a pitch entry
                  stuck (queued/held > 24h, failed, refused)
      google      kickoff mined > 3d and no Google grant AND no Profile
                  Planner plan (nothing will ever create or manage the GBP)
    """
    import json as _json
    issues: list[str] = []
    since = (NOW - timedelta(days=ONBOARD_WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        comps = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
                    f"&created_at=gte.{since}&select=id,name,created_at,integration_settings") or []
    except Exception as e:  # noqa: BLE001
        return [f"onboarding watchdog failed — {str(e)[:100]}"]
    if not comps:
        return []
    ids = ",".join(c["id"] for c in comps)
    paid = {r["company_id"] for r in _sb(
        "GET", f"/rest/v1/billing_invoices?company_id=in.({ids})&select=company_id") or []}
    sites = {r["company_id"]: r for r in _sb(
        "GET", f"/rest/v1/marketing_sites?company_id=in.({ids})"
        "&select=company_id,rank_ai_slug,apex_live,scaffolded_at") or []}
    previews = {r["company_id"] for r in _sb(
        "GET", f"/rest/v1/marketing_action_plan?company_id=in.({ids})"
        "&action_key=like.site-preview-feedback-*&select=company_id") or []}
    grants = {r["client_id"] for r in _sb(
        "GET", f"/rest/v1/user_integrations?client_id=in.({ids})&provider=eq.google"
        "&select=client_id") or []}
    kick = {}
    for r in _sb("GET", f"/rest/v1/marketing_ops_notes?company_id=in.({ids})"
                 "&body=ilike.*CALL%20COMMITMENT*&select=company_id,created_at"
                 "&order=created_at.asc") or []:
        kick.setdefault(r["company_id"], r["created_at"])
    names = {}
    for r in _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=in.({ids})"
                 "&item_type=eq.name&select=company_id,status") or []:
        names.setdefault(r["company_id"], set()).add(r.get("status"))
    queue = ((_sb("GET", "/rest/v1/ops_kv?k=eq.rename-pitch-queue&select=v") or [{}])[0]
             .get("v") or {})
    convos = {r["k"].split(":", 1)[1] for r in _sb(
        "GET", "/rest/v1/ops_kv?k=like.rename-convo:*&select=k") or []}
    inv = slug_map()
    rows: dict[str, list[str]] = {}

    def flag(kind: str, text: str) -> None:
        rows.setdefault(kind, []).append(text)

    for co in comps:
        cid, nm = co["id"], (co.get("name") or co["id"]).strip()
        age_h = (_age_days(co.get("created_at")) or 0) * 24
        slug = inv.get(cid)
        ints = co.get("integration_settings") or {}
        if cid in paid and not slug and age_h > 6:
            flag("bootstrap", f"{nm} ({age_h / 24:.1f}d, paid, no client files)")
            continue
        if not slug:
            continue
        if age_h > 48 and not (ROOT / "sites" / slug / "src").is_dir():
            flag("site", f"{slug} ({age_h / 24:.0f}d old, no site in the repo)")
        site = sites.get(cid) or {}
        if site and not site.get("apex_live") and cid not in previews:
            reveal = None
            try:
                rec = _json.loads((ROOT / "clients" / f"{slug}.json").read_text())
                if rec.get("preview_reveal_on"):
                    reveal = datetime.fromisoformat(str(rec["preview_reveal_on"])[:10]
                                                    + "T23:59:00+00:00")
            except (OSError, ValueError):
                pass
            sc = site.get("scaffolded_at")
            if not reveal and sc:
                reveal = datetime.fromisoformat(str(sc).replace("Z", "+00:00")) + timedelta(days=11)
            if reveal and NOW > reveal:
                flag("reveal", f"{slug} (reveal was due {reveal:%m-%d})")
        k_at = kick.get(cid)
        k_age = _age_days(k_at) if k_at else None
        q = queue.get(cid) or {}
        if q.get("status") in ("failed", "refused", "error"):
            flag("rename", f"{slug} pitch {q.get('status')}: {str(q.get('detail'))[:80]}")
        elif q.get("status") in ("queued", "held") and (_age_days(q.get("at")) or 0) > 1:
            flag("rename", f"{slug} pitch stuck '{q.get('status')}' since {str(q.get('at'))[:10]} (ops worker down?)")
        elif (k_age or 0) > 2 and names.get(cid) == {"open"} and cid not in convos \
                and not q and not ints.get("rename_intent"):
            flag("rename", f"{slug} kickoff {str(k_at)[:10]}, name options ready, no pitch sent")
        # HOME CITY = REGISTERED ADDRESS (Santino 2026-10-02; Touch of Class
        # was built for Richardson TX from a city field reading "Ri")
        try:
            _pi = _json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
            _prim = next((a for a in _pi.get("service_areas") or [] if a.get("primary")), {})
            _reg = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=city") or [{}])[0].get("city") or ""
            if _prim and _reg and _prim.get("city", "").strip().lower() != _reg.strip().lower():
                flag("areas", f"{slug} site home city '{_prim.get('city')}' but registered address city '{_reg.strip()}'")
        except (OSError, ValueError):
            pass
        if (k_age or 0) > 3 and cid not in grants and not ints.get("gbp_plan"):
            flag("google", f"{slug} (no Google connection and no Profile Planner plan)")
    labels = {
        "bootstrap": "paid client never bootstrapped (no slug/files): run bootstrap-new-clients or client_ops_sync --bootstrap-only",
        "site": "new client has no site built: check site-build.yml runs / ops_kv auto-site-build:*",
        "reveal": "site preview overdue: past the reveal day and never shown to the client",
        "rename": "profile-rename outreach stalled: pitch not sent or stuck in rename-pitch-queue",
        "areas": "site home city does not match the registered business address (fix the address or rebuild the city list from the wizard territory)",
        "google": "new client with no way to get a Google profile: connect their Google or draft a Profile Planner plan",
    }
    for kind, items in rows.items():
        issues.append(f"onboarding {kind} — {labels[kind]}: " + "; ".join(items[:12]))
    return issues


def alert_key(issue: str) -> str:
    """Stable identity of an alert condition, independent of the numbers in
    it. Digits stripped (2026-09-19: '0/2 posts' -> '1/2 posts' minted a NEW
    key daily); workflow + heartbeat alerts key on the workflow / heartbeat
    name alone (2026-09-29: 'failure/failure' vs 'failure/cancelled' were two
    keys for one dead pipeline)."""
    head = issue.split("\u2014")[0].strip()
    m = re.match(r"^([\w.-]+\.ya?ml):", head)
    if m:
        return "wd-alert:wf:" + m.group(1)
    m = re.match(r"^(heartbeat:[\w-]+):", head)
    if m:
        return "wd-alert:" + m.group(1)
    m = re.match(r"^index-watch ([\w-]+):", head)  # one card per site (10-01)
    if m:
        return "wd-alert:index-watch:" + m.group(1)
    return "wd-alert:" + re.sub(r"[^a-z]+", "-", head.lower())[:60]


def _stamp(issue: str) -> str:
    return (f"[PIPELINE ALERT] {issue}\n(still true as of "
            f"{NOW.strftime('%Y-%m-%d %H:%M')} UTC; this card refreshes in "
            "place and auto-resolves when the condition clears)")


def check_site_guards() -> list[str]:
    """Live-site regressions + blocked production deploys (Santino
    2026-09-29: "we don't want these sites getting reverted"). The per-client
    site_regression_watch.py jobs keep ops_kv site-fingerprint/{slug} with an
    open `regression`; deploy_guard.py keeps deploy-guard-block/{slug} while a
    site's production deploy is refused. Both file their own cards the
    moment they happen; this re-states them so the daily pass keeps those
    cards open instead of auto-clearing them."""
    issues = []
    try:
        rows = _sb("GET", "/rest/v1/ops_kv?or=(k.like.site-fingerprint/*,"
                   "k.like.deploy-guard-block/*)&select=k,v",
                   prefer="return=representation") or []
    except Exception as e:  # noqa: BLE001
        return [f"site guard check failed: {str(e)[:80]}"]
    for r in sorted(rows, key=lambda x: x["k"]):
        v = r.get("v") or {}
        if r["k"].startswith("deploy-guard-block/"):
            if v.get("issue"):
                issues.append(v["issue"])
        elif (v.get("regression") or {}).get("issue"):
            issues.append(v["regression"]["issue"])
    return issues


def text_santino(fresh: list[str]) -> None:
    """ONE SMS per run for brand-new alert cards only (2026-09-17: "not only
    Ops Attention but also a text"). Same ops-ping path the credit canary
    uses; a failed text never kills the caller."""
    if not fresh:
        return
    heads = [i.split(" — ")[0] for i in fresh[:4]]
    body = (f"PIPELINE ALERT ({len(fresh)} new): " + "; ".join(heads)
            + ("; +more" if len(fresh) > 4 else "")
            + ". Details in the app's Errors tab.")
    try:
        from client_concierge import (send_message, OPS_PING_CONTACT_ID,
                                      OPS_PING_CELL)
        send_message({"id": OPS_PING_CONTACT_ID, "phone": OPS_PING_CELL},
                     "sms", body[:640])
        print("  -> alert SMS sent")
    except Exception as e:  # noqa: BLE001
        print(f"  -> alert SMS failed: {str(e)[:100]}")


def reconcile_notes(issues: list[str], scope: str | None = None) -> list[str]:
    """ONE open note per alert key, refreshed in place (Santino 2026-09-29:
    2,489 open notes, the same 'cadence SLA' card stacked weekly per client).

    - condition true + open card exists  -> PATCH its body (newest kept,
      any older duplicates of the same key resolved). No SMS.
    - condition true + card auto-cleared by us < 7d ago -> REOPEN it. No SMS.
    - condition true + human resolved it < 7d ago -> respect that (quiet).
    - condition true + nothing           -> file a new card (+ SMS, fresh).
    - open card whose key is NOT in this run's issues -> the condition
      cleared: resolve it (marked auto_cleared so a relapse reopens it).
    Returns the list of FRESH issues (the only ones that text Santino).

    scope (2026-09-29, site guards): ONE alert key. Only the card with that
    key is refreshed or cleared, so a per-client job can own its one card
    without touching (or auto-clearing) anyone else's."""
    now_iso = NOW.isoformat().replace("+00:00", "Z")
    open_notes = _sb("GET", "/rest/v1/marketing_ops_notes?status=eq.open"
                     "&author=eq.pipeline_watchdog&company_id=is.null"
                     "&select=id,body,created_at&order=created_at.desc"
                     "&limit=1000", prefer="return=representation") or []
    by_key: dict[str, list[dict]] = {}
    for n in open_notes:
        b = (n.get("body") or "").split("\n(still true as of")[0]
        b = b.replace("[PIPELINE ALERT]", "", 1).strip()
        k = alert_key(b)
        if scope and k != scope:
            continue
        by_key.setdefault(k, []).append(n)   # newest first
    current: dict[str, str] = {}
    for issue in issues:
        k = alert_key(issue)
        if scope and k != scope:
            continue
        current.setdefault(k, issue)
    fresh: list[str] = []

    def _resolve(ids: list[str]) -> None:
        for i in ids:
            _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{i}",
                {"status": "resolved", "resolved_at": now_iso})

    def _kv_put(key: str, v: dict) -> None:
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k", {"k": key, "v": v},
            prefer="resolution=merge-duplicates")

    for key, issue in current.items():
        print(f"  !! {issue}")
        notes = by_key.get(key) or []
        seen = ((_sb("GET", f"/rest/v1/ops_kv?k=eq.{key}&select=v")
                 or [{}])[0].get("v") or {})
        if notes:
            keep, dupes = notes[0], notes[1:]
            _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{keep['id']}",
                {"body": _stamp(issue)})
            _resolve([d["id"] for d in dupes])
            _kv_put(key, {"at": seen.get("at") or NOW.isoformat(),
                          "note_id": keep["id"]})
            continue
        at = seen.get("at")
        recent = bool(at) and (NOW - datetime.fromisoformat(at)).days < 7
        if recent and seen.get("auto_cleared") and seen.get("note_id"):
            _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{seen['note_id']}",
                {"status": "open", "resolved_at": None, "body": _stamp(issue)})
            _kv_put(key, {"at": at, "note_id": seen["note_id"]})
            print("     (relapse: reopened the auto-cleared card)")
            continue
        if recent:
            continue  # a human resolved it this week; stay quiet
        row = _sb("POST", "/rest/v1/marketing_ops_notes",
                  {"company_id": None, "status": "open",
                   "author": "pipeline_watchdog", "body": _stamp(issue)},
                  prefer="return=representation") or [{}]
        fresh.append(issue)
        _kv_put(key, {"at": NOW.isoformat(), "note_id": (row[0] or {}).get("id")})
    cleared = 0
    for key, notes in by_key.items():
        if key in current:
            continue
        _resolve([n["id"] for n in notes])
        seen = ((_sb("GET", f"/rest/v1/ops_kv?k=eq.{key}&select=v")
                 or [{}])[0].get("v") or {})
        _kv_put(key, {"at": seen.get("at") or NOW.isoformat(),
                      "note_id": notes[0]["id"], "auto_cleared": True})
        cleared += len(notes)
    if cleared:
        print(f"  cleared: {cleared} card(s) whose condition no longer holds")
    return fresh


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    issues = (check_workflows() + check_conflict_markers() + check_heartbeats() + check_coverage()
              + check_index_watch()
              + check_site_area_gap() + check_citation_stall()
              + check_lsa_leads()
              + check_stuck_lead_audits()
              + check_email_claims()
              + check_nap_parity()
              + check_site_guards()
              + check_geogrid()
              + check_onboarding())
    if not issues:
        print("pipeline watchdog: ALL SYSTEMS ALIVE")
    fresh = [] if a.dry_run else reconcile_notes(issues)
    if a.dry_run:
        for issue in issues:
            print(f"  !! {issue}  [key {alert_key(issue)}]")
    # SMS to Santino (2026-09-17: "not only Ops Attention but also a text —
    # I don't really view Ops Attention"). One text per run, NEW issues only
    # (the 7-day dedupe above already keeps repeats quiet).
    if not a.dry_run:
        text_santino(fresh)
    print(f"pipeline watchdog: {len(issues)} issue(s), {len(fresh)} new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
