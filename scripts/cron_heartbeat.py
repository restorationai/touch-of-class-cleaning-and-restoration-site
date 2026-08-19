#!/usr/bin/env python3
"""cron_heartbeat.py — the scheduler's own pulse (build queue #5).

WHY: pg_cron failures are silent by default. The Twilio-suspension week
proved the pattern: a scheduled job stops (or starts failing) and nothing
tells anyone until a client notices. This check reads the database's own
cron ledger through public.cron_heartbeat() (SECURITY DEFINER over cron.job
+ cron.job_run_details, service_role only, created 2026-08-19) and alarms
two ways:
  - SILENT: a known job has not RUN within its threshold
  - FAILING: a job's most recent run status is 'failed'

Alerts = one open marketing_ops_notes card per condition per day (marker
[CRON-{SILENT|FAILED} {job} {date}]) on the ops/canary company, so they ride
the existing digest + Ops Attention surfaces. Unknown jobnames are reported
as info only (new jobs should be added to THRESHOLDS deliberately).

Runs from client-ops-sync.yml every pass. CLI: python3 scripts/cron_heartbeat.py
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import requests  # noqa: E402

# jobname -> max minutes since last run before it counts as SILENT.
# Generous multiples of each schedule so a single slow pass never pages.
# billing_monthly_reset is deliberately absent: UNSCHEDULED 2026-08-19 after
# this very check caught it failing daily since June 10 (71 fails) — it wrote
# the pre-migration column free_usage_amount with hardcoded plan amounts; the
# Stripe webhook (stripe-webhook/index.ts) has owned cycle resets via
# free_usage_allowance -> company_wallets.free_balance since the June billing
# migration, so the job was a dead duplicate, not a repair candidate.
THRESHOLDS = {
    "twilio-tollfree-sync": 3 * 60,               # hourly
    "invoke-dispatch-review-requests": 45,        # every 10 min
    "booking-backstop": 120,                      # every 30 min
}
OPS_COMPANY = "CO-1782880883337"   # Test (Rank AI) — existing system-note home


def _sb():
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_SERVICE_KEY"))
    return url, {"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"}


def _note(url: str, hdr: dict, marker: str, body: str) -> str:
    open_notes = requests.get(
        f"{url}/rest/v1/marketing_ops_notes?company_id=eq.{OPS_COMPANY}"
        f"&status=eq.open&select=body", headers=hdr, timeout=30).json()
    if any(marker in (n.get("body") or "") for n in open_notes):
        return "exists"
    requests.post(f"{url}/rest/v1/marketing_ops_notes", headers=hdr,
                  json={"company_id": OPS_COMPANY, "status": "open",
                        "body": body}, timeout=30)
    return "filed"


def main() -> int:
    url, hdr = _sb()
    r = requests.post(f"{url}/rest/v1/rpc/cron_heartbeat", headers=hdr,
                      json={}, timeout=30)
    r.raise_for_status()
    rows = r.json()
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    problems = 0
    seen = set()
    for row in rows:
        job = row["jobname"]
        seen.add(job)
        last = row.get("last_run")
        if last:
            # pg timestamps carry variable fractional digits; py3.9's
            # fromisoformat needs exactly 3 or 6 — normalize to 6
            norm = re.sub(r"\.(\d+)",
                          lambda m: "." + m.group(1)[:6].ljust(6, "0"), last)
            age_min = (now - datetime.fromisoformat(norm)).total_seconds() / 60
        else:
            age_min = float("inf")
        limit = THRESHOLDS.get(job)
        if limit is None:
            print(f"  info: unlisted cron job '{job}' (schedule "
                  f"{row.get('schedule')}) — add to THRESHOLDS deliberately")
            continue
        if age_min > limit:
            problems += 1
            marker = f"[CRON-SILENT {job} {today}]"
            res = _note(url, hdr, marker,
                        f"[TODO-SANTINO] {marker} scheduled job '{job}' has "
                        f"not run for {age_min/60:.1f}h (threshold "
                        f"{limit/60:.1f}h; schedule {row.get('schedule')}). "
                        "pg_cron may be stalled or the job was dropped — "
                        "check cron.job_run_details.")
            print(f"  SILENT: {job} last ran {age_min/60:.1f}h ago ({res})")
        elif (row.get("last_status") or "").lower() == "failed":
            problems += 1
            marker = f"[CRON-FAILED {job} {today}]"
            res = _note(url, hdr, marker,
                        f"[TODO-SANTINO] {marker} scheduled job '{job}' ran "
                        f"on time but its latest run FAILED ({last}). Check "
                        "cron.job_run_details return_message.")
            print(f"  FAILED: {job} latest run failed ({res})")
        else:
            print(f"  ok: {job} ({age_min:.0f} min ago, "
                  f"{row.get('last_status')})")
    for job in THRESHOLDS:
        if job not in seen:
            problems += 1
            marker = f"[CRON-SILENT {job} {today}]"
            res = _note(url, hdr, marker,
                        f"[TODO-SANTINO] {marker} expected cron job '{job}' "
                        "is MISSING from cron.job entirely.")
            print(f"  MISSING: {job} ({res})")
    print(f"{problems} problem(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
