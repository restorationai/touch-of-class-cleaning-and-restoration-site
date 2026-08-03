#!/usr/bin/env python3
"""Always-on ops worker: runs the concierge loops on Railway.

One long-lived process replaces the four Mac launchd jobs:

    every  5 min   client_concierge.py inbound --poll --send   (SMS replies)
    every  5 min   email_intake.py poll --send                 (setup@ email)
    every 30 min   fathom_sync.py sync --send                  (meeting intel)
    every 60 min   client_concierge.py compose --all --send    (nudges;
                   per-client business-hours/cadence gates live in the script)

Each job runs as a subprocess so one crash never takes down the loop; output
goes to stdout (Railway log stream). State lives in Supabase (ops_kv +
concierge_escalations + Storage), so this container is fully disposable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent

# ---------------------------------------------------------------- gh dispatch
# GitHub's schedule trigger silently drops runs (2026-08-03: the 16:07 UTC
# client-concierge cron never fired — workflow active, file unchanged; known
# GitHub cron flakiness). Cron-critical workflows are therefore FIRED FROM
# HERE via workflow_dispatch at their intended times; GitHub's own cron stays
# on as backup. Dedupe: before dispatching we ask the GitHub API whether any
# run of the workflow was already created at/after the slot time (GitHub's
# cron beat us, or a previous worker process already dispatched) — if so we
# skip. Auth: GH_PAT (same secret the FastAPI service uses) or
# GITHUB_PERSONAL_ACCESS_TOKEN.
GH_REPO = os.environ.get("GH_REPO", "restorationai/Rank-AI-Pipeline")

WORKFLOW_DISPATCH_JOBS = [
    # (name, workflow file, ["HH:MM", ...] UTC, weekdays_only, inputs)
    ("concierge", "client-concierge.yml", ["16:07", "19:37"], True,
     {"mode": "daily"}),
]
# How long after a slot we still fire a missed dispatch (worker restarts).
DISPATCH_CATCHUP = timedelta(hours=3)


def _gh_token() -> str | None:
    return (os.environ.get("GH_PAT")
            or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or None)


def _gh(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        "https://api.github.com" + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + _gh_token(),
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "rank-ai-ops-scheduler"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def run_started_for_slot(workflow: str, slot: datetime) -> bool:
    """True when GitHub shows ANY run of `workflow` created at/after `slot`
    (minus a 2-min clock-skew grace) — GitHub's own cron fired, or another
    dispatch already went out. This is the dedupe that makes the worker-side
    dispatch safe to run alongside GitHub's cron."""
    since = (slot - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = _gh("GET", f"/repos/{GH_REPO}/actions/workflows/{workflow}/runs"
                      f"?created=%3E%3D{since}&per_page=5")
    return bool(data.get("workflow_runs"))


def dispatch_workflow(name: str, workflow: str, slot: datetime,
                      inputs: dict) -> None:
    """Fire one workflow_dispatch for the slot unless a run already started."""
    if not _gh_token():
        log(f"!!! dispatch {name}: no GH_PAT/GITHUB_PERSONAL_ACCESS_TOKEN "
            "in env — cannot dispatch (GitHub cron is the only trigger)")
        return
    try:
        if run_started_for_slot(workflow, slot):
            log(f"dispatch {name} {slot.strftime('%H:%M')}Z: a run already "
                "started this slot (GitHub cron or earlier dispatch) — skipping")
            return
        _gh("POST", f"/repos/{GH_REPO}/actions/workflows/{workflow}/dispatches",
            {"ref": "main", "inputs": inputs})
        log(f"dispatch {name} {slot.strftime('%H:%M')}Z: workflow_dispatch "
            f"fired ({workflow})")
    except urllib.error.HTTPError as e:
        log(f"!!! dispatch {name} failed: HTTP {e.code} "
            f"{e.read().decode()[:200]}")
    except Exception as e:  # noqa: BLE001 — the loop must survive
        log(f"!!! dispatch {name} failed: {e!r}")


def tick_workflow_dispatches(done: dict) -> None:
    """Called every loop tick: fire any due (and not-yet-handled) slot.
    `done` maps (name, date, "HH:MM") -> True for slots this process already
    handled; across restarts the GitHub-side run check is the dedupe."""
    now = datetime.now(timezone.utc)
    for name, workflow, slots, weekdays_only, inputs in WORKFLOW_DISPATCH_JOBS:
        if weekdays_only and now.weekday() >= 5:
            continue
        for hhmm in slots:
            key = (name, now.date(), hhmm)
            if done.get(key):
                continue
            hh, mm = (int(x) for x in hhmm.split(":"))
            slot = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if now < slot or now - slot > DISPATCH_CATCHUP:
                continue
            done[key] = True
            dispatch_workflow(name, workflow, slot, inputs)

# Daily jobs fire once per UTC day at/after the given HH:MM.
DAILY_JOBS = [
    # (name, "HH:MM" UTC, argv)  — 12:20 UTC = 5:20am PT
    ("callist", "12:20", [sys.executable, str(HERE / "callist" / "run_daily.py")]),
    # No-show / post-demo Fathom routing — ported off the Mac 2026-07-16 (it had
    # been left behind by the Railway migration and only ran when the Mac was awake).
    ("noshow", "13:00", [sys.executable, str(HERE / "callist" / "noshow_checker.py")]),
    # Nightly backstop: repo JSON state -> Supabase (all clients), so the app's
    # Content/Sites/Keywords views heal even when a post-publish sync fails.
    # (content_writer.py's inline sync is best-effort; this was the "nightly
    # cron" its comment promised but which never existed.)
    ("supabase-sync", "09:10", [sys.executable, str(HERE / "supabase_sync.py")]),
    # Weekly-per-client progress reports (baseline vs now) — self-gating: the
    # script skips any client whose last progress report is <6 days old or
    # whose baseline is <6 days old, so a daily tick yields weekly reports.
    ("progress", "15:00", [sys.executable, str(HERE / "progress_report.py"), "--all"]),
    # Daily all-systems pulse: one green/red email checking every system's
    # OUTCOME (sites up incl SSL, content/video cadence, GSC/GBP freshness,
    # worker alive, failed jobs). Built 2026-07-23 post-shipping-week.
    ("pulse", "14:45", [sys.executable, str(HERE / "systems_pulse.py")]),
]

JOBS = [
    # (name, interval seconds, argv)
    # Notes sync every 3h (was nightly 04:00Z): idempotent (contact+note-text
    # dedupe), and harvesting often means a "remove from list" note can't sit
    # unsynced long enough for the morning repaint to wipe it (2026-07-15 loss).
    ("callist-notes", 10800, [sys.executable,
                              str(HERE / "callist" / "run_notes_sync.py")]),
    ("inbound", 300, [sys.executable, str(HERE / "client_concierge.py"),
                      "inbound", "--poll", "--send"]),
    ("email", 300, [sys.executable, str(HERE / "email_intake.py"),
                    "poll", "--send"]),
    ("fathom", 1800, [sys.executable, str(HERE / "fathom_sync.py"),
                      "sync", "--send"]),
    ("nudge", 3600, [sys.executable, str(HERE / "client_concierge.py"),
                     "compose", "--all", "--send"]),
]

JOB_TIMEOUT = 15 * 60


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}] {msg}",
          flush=True)


def main() -> None:
    last_run = {name: 0.0 for name, _, _ in JOBS}
    daily_done: dict = {}
    dispatch_done: dict = {}
    log(f"ops worker up — jobs: "
        + ", ".join(f"{n}/{iv}s" for n, iv, _ in JOBS)
        + " | gh-dispatch: "
        + ", ".join(f"{n}@{'/'.join(s)}Z" for n, _, s, _, _
                    in WORKFLOW_DISPATCH_JOBS))
    while True:
        now = time.time()
        utc = datetime.now(timezone.utc)
        # Cron-critical GitHub workflows: fire workflow_dispatch at the
        # intended times (GitHub's own cron drops runs; it stays as backup).
        tick_workflow_dispatches(dispatch_done)
        for name, at, argv in DAILY_JOBS:
            if daily_done.get(name) == utc.date():
                continue
            hh, mm = at.split(":")
            if (utc.hour, utc.minute) >= (int(hh), int(mm)):
                daily_done[name] = utc.date()
                log(f"--- {name} (daily {at}Z) start")
                try:
                    r = subprocess.run(argv, timeout=90 * 60,
                                       capture_output=True, text=True)
                    if r.stdout:
                        print(r.stdout.strip()[-6000:], flush=True)
                    if r.returncode != 0:
                        log(f"!!! {name} exited {r.returncode}")
                        if r.stderr:
                            print(r.stderr.strip()[-2000:], file=sys.stderr, flush=True)
                except Exception as e:  # noqa: BLE001
                    log(f"!!! {name} crashed the runner: {e!r}")
                log(f"--- {name} done")
        for name, interval, argv in JOBS:
            if now - last_run[name] < interval:
                continue
            last_run[name] = now
            log(f"--- {name} start")
            try:
                r = subprocess.run(argv, timeout=JOB_TIMEOUT,
                                   capture_output=True, text=True)
                out = (r.stdout or "").strip()
                err = (r.stderr or "").strip()
                if out:
                    print(out, flush=True)
                if r.returncode != 0:
                    log(f"!!! {name} exited {r.returncode}")
                    if err:
                        print(err[-2000:], file=sys.stderr, flush=True)
                elif err:
                    # keep warnings visible but compact
                    tail = "\n".join(l for l in err.splitlines()
                                     if "Warning" not in l and "warn" not in l)
                    if tail.strip():
                        print(tail[-1000:], file=sys.stderr, flush=True)
                log(f"--- {name} done")
            except subprocess.TimeoutExpired:
                log(f"!!! {name} timed out after {JOB_TIMEOUT}s")
            except Exception as e:  # noqa: BLE001 — the loop must survive
                log(f"!!! {name} crashed the runner: {e!r}")
        time.sleep(20)


if __name__ == "__main__":
    main()
