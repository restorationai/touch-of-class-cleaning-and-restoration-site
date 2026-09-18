#!/usr/bin/env python3
"""rename_pitch_worker.py — executes app-initiated rename pitches
(Santino 2026-09-18: "I don't know how to initiate this manually without
asking you... maybe from the build stages rename card").

The app's Build Stages RENAME tab writes a request into ops_kv
`rename-pitch-queue` (one entry per company: {slug, company_id, channel,
note, requested_by, at, status}). This worker, riding the Railway
ops-worker loop every 60s, executes each queued request through the ONE
lawful chokepoint — `client_concierge.py rename-pitch --send --operator`
— so every law (canary allowlist, quiet hours, coverage-gap gate,
link gate, em-dash scrub, clobber-proof conversation arming) applies
identically to an app click and a CLI run.

Entry states the card renders:
  queued   click received, sends on the next tick
  held     quiet hours at the client's local time — retried every 30 min
           until their morning opens the window (quiet-hours law: queue
           for their morning, never drop)
  sent     delivered + reply flow armed (stage flips to `outreach` on the
           next rename_pipeline derive)
  refused  the coverage-gap gate blocked an incomplete slate — fix the
           candidates, then click again
  failed   3 attempts errored — detail carries the tail, ops note filed

CLI: python3 scripts/rename_pitch_worker.py [--dry-run]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from client_ops_sync import _sb  # noqa: E402

KV_KEY = "rename-pitch-queue"
HELD_RETRY_MIN = 30      # quiet-hours retries: every 30 min, not every tick
MAX_ATTEMPTS = 3
PRUNE_DAYS = 7           # finished entries fall off the card after a week


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _kv_get() -> dict:
    rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{KV_KEY}&select=v") or []
    return (rows[0].get("v") if rows else {}) or {}


def _kv_set(v: dict) -> None:
    _sb("POST", "/rest/v1/ops_kv?on_conflict=k", {"k": KV_KEY, "v": v},
        prefer="resolution=merge-duplicates")


def _run_pitch(entry: dict) -> tuple[str, str]:
    """Execute one pitch through the concierge CLI. -> (status, detail)."""
    cmd = [sys.executable, str(ROOT / "scripts" / "client_concierge.py"),
           "rename-pitch", "--company", entry["company_id"],
           "--send", "--operator",
           "--channel", entry.get("channel") or "sms"]
    for n in entry.get("note") or []:
        cmd += ["--note", n]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                       cwd=str(ROOT))
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 0:
        return "sent", ""
    if "HELD (quiet hours)" in out:
        return "held", "their quiet hours — retrying until morning"
    if "COVERAGE GAP" in out:
        gap = next((ln.strip().lstrip("! ") for ln in out.splitlines()
                    if "COVERAGE GAP" in ln), "coverage gap")
        return "refused", gap[:300]
    if "BLOCKED" in out or "SendBlocked" in out:
        blk = next((ln.strip() for ln in out.splitlines()
                    if "BLOCKED" in ln), "send blocked")
        return "error", blk[:300]
    tail = "\n".join(out.strip().splitlines()[-3:])[:300]
    return "error", tail or f"exit {r.returncode}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    q = _kv_get()
    if not q:
        return 0
    changed = False
    any_sent = False
    for cid, entry in list(q.items()):
        st = entry.get("status")
        if st in ("sent", "refused", "failed"):
            done_at = entry.get("finished_at") or entry.get("at")
            try:
                if done_at and (_now() - datetime.fromisoformat(done_at)
                                ).days >= PRUNE_DAYS:
                    del q[cid]
                    changed = True
            except Exception:  # noqa: BLE001
                pass
            continue
        if st == "held":
            last = entry.get("last_try")
            try:
                if last and (_now() - datetime.fromisoformat(last)
                             ) < timedelta(minutes=HELD_RETRY_MIN):
                    continue
            except Exception:  # noqa: BLE001
                pass
        if st not in ("queued", "held"):
            continue
        label = entry.get("slug") or cid
        if a.dry_run:
            print(f"  {label}: would pitch via "
                  f"{entry.get('channel') or 'sms'} [dry-run]")
            continue
        entry["last_try"] = _now().isoformat()
        try:
            status, detail = _run_pitch(entry)
        except Exception as e:  # noqa: BLE001
            status, detail = "error", str(e)[:300]
        if status == "error":
            entry["attempts"] = int(entry.get("attempts") or 0) + 1
            if entry["attempts"] >= MAX_ATTEMPTS:
                status = "failed"
                _sb("POST", "/rest/v1/marketing_ops_notes",
                    {"company_id": cid, "status": "open",
                     "author": "rename_pitch_worker",
                     "body": f"[RENAME] app-initiated pitch FAILED after "
                             f"{MAX_ATTEMPTS} attempts: {detail}"},
                    prefer="return=minimal")
            else:
                status = "queued"   # transient — retry next tick
        entry["status"] = status
        entry["detail"] = detail
        if status in ("sent", "refused", "failed"):
            entry["finished_at"] = _now().isoformat()
        q[cid] = entry
        changed = True
        any_sent = any_sent or status == "sent"
        print(f"  {label}: {status}" + (f" ({detail})" if detail else ""))
    if changed and not a.dry_run:
        _kv_set(q)
    if any_sent and not a.dry_run:
        # refresh the derived stage map so the card flips to `outreach`
        # within seconds of the send, not at the next 30-min derive
        subprocess.run([sys.executable,
                        str(ROOT / "scripts" / "rename_pipeline.py")],
                       capture_output=True, timeout=300, cwd=str(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
