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

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent

# Daily jobs fire once per UTC day at/after the given HH:MM.
DAILY_JOBS = [
    # (name, "HH:MM" UTC, argv)  — 12:20 UTC = 5:20am PT
    ("callist", "12:20", [sys.executable, str(HERE / "callist" / "run_daily.py")]),
    # Nightly backstop: repo JSON state -> Supabase (all clients), so the app's
    # Content/Sites/Keywords views heal even when a post-publish sync fails.
    # (content_writer.py's inline sync is best-effort; this was the "nightly
    # cron" its comment promised but which never existed.)
    ("supabase-sync", "09:10", [sys.executable, str(HERE / "supabase_sync.py")]),
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
    log(f"ops worker up — jobs: "
        + ", ".join(f"{n}/{iv}s" for n, iv, _ in JOBS))
    while True:
        now = time.time()
        utc = datetime.now(timezone.utc)
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
