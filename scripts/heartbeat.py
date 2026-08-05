#!/usr/bin/env python3
"""heartbeat.py — proof of life for automations that are supposed to produce work.

WHY THIS EXISTS (Santino 2026-08-05). On 08-05 the client-feedback loop was
declared dead because an inbox listing was empty. It was not dead: Jerrott's
text landed in GHL at 14:46:00 and three [DEV] tasks were filed at 14:48:13.
The check simply happened in the two minutes between. Nothing in the system
could answer the only question that mattered — "when did this thing last SEE
an input, and when did it last PRODUCE an output?" — so an absence of work
was indistinguishable from an absence of a pipeline.

That is the same failure shape as gbp_admin_invite (built, wired, never
scheduled) and lsa_ask_guard (running, but credential-less, so it always
returned "no opinion"). All three were invisible because a system that
produces nothing looks exactly like a system with nothing to do.

A heartbeat is one row per system in ops_kv:

    heartbeat/{system} = {
      "system": str,
      "last_run_at":    when the code last executed at all,
      "last_output_at": when it last actually PRODUCED something,
      "totals": {"runs": n, "inputs": n, "outputs": n},
      "runs": [{"at", "inputs", "outputs", ...}]   # last 40, newest last
    }

`inputs` is how many candidate things the pass saw; `outputs` is how many
artifacts it created. Both matter: zero outputs with zero inputs is a quiet
day, zero outputs with live inputs is a broken system. scripts/silence_watch.py
turns the second case into a card.

Fail-open by contract: a heartbeat may never break the job it measures. Every
write swallows its own exception and prints one short line.

CLI:
  python3 scripts/heartbeat.py list              # every heartbeat, freshest first
  python3 scripts/heartbeat.py show <system>     # one system's recent runs
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote as _q

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KEY_PREFIX = "heartbeat/"
MAX_RUNS = 40


def _sb(*a, **kw):
    from client_ops_sync import _sb as sb  # lazy: importing needs env
    return sb(*a, **kw)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read(system: str) -> dict:
    """One system's heartbeat, {} when it has never run (or on any error —
    an unreadable heartbeat is reported as unknown, never as healthy)."""
    try:
        rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{_q(KEY_PREFIX + system)}"
                   "&select=v", prefer="return=representation") or []
        return (rows[0].get("v") or {}) if rows else {}
    except Exception as e:  # noqa: BLE001
        print(f"  [heartbeat] read {system} failed: {str(e)[:100]}")
        return {}


def read_all() -> dict[str, dict]:
    try:
        rows = _sb("GET", f"/rest/v1/ops_kv?k=like.{_q(KEY_PREFIX)}*"
                   "&select=k,v", prefer="return=representation") or []
        return {r["k"][len(KEY_PREFIX):]: (r.get("v") or {}) for r in rows}
    except Exception as e:  # noqa: BLE001
        print(f"  [heartbeat] read_all failed: {str(e)[:100]}")
        return {}


def stamp(system: str, *, inputs: int = 0, outputs: int = 0,
          error: str | None = None, dry_run: bool = False, **extra) -> None:
    """Record one pass. `inputs` = candidates seen, `outputs` = artifacts made.

    Never raises. Never blocks. A dry run stamps nothing — a rehearsal must
    not make a dead system look alive."""
    if dry_run:
        return
    try:
        hb = read(system) or {}
        run = {"at": _now(), "inputs": int(inputs), "outputs": int(outputs)}
        if error:
            run["error"] = str(error)[:300]
        for k, v in extra.items():
            if v is not None:
                run[k] = v
        runs = [r for r in (hb.get("runs") or []) if isinstance(r, dict)]
        runs.append(run)
        totals = hb.get("totals") or {}
        payload = {
            "system": system,
            "last_run_at": run["at"],
            "last_input_at": run["at"] if inputs else hb.get("last_input_at"),
            "last_output_at": run["at"] if outputs else hb.get("last_output_at"),
            "last_error": run.get("error") or None,
            "totals": {"runs": int(totals.get("runs") or 0) + 1,
                       "inputs": int(totals.get("inputs") or 0) + int(inputs),
                       "outputs": int(totals.get("outputs") or 0) + int(outputs)},
            "runs": runs[-MAX_RUNS:],
        }
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": KEY_PREFIX + system, "v": payload, "updated_at": _now()},
            prefer="resolution=merge-duplicates,return=minimal")
    except Exception as e:  # noqa: BLE001 — bookkeeping never breaks the job
        print(f"  [heartbeat] {system}: not recorded ({str(e)[:100]})")


def age_hours(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600


def main() -> int:
    from client_concierge import load_env
    load_env()
    argv = sys.argv[1:]
    if argv and argv[0] == "show" and len(argv) > 1:
        hb = read(argv[1])
        print(json.dumps(hb, indent=1))
        return 0 if hb else 1
    hbs = read_all()
    if not hbs:
        print("no heartbeats recorded yet")
        return 1
    rows = sorted(hbs.items(),
                  key=lambda kv: str(kv[1].get("last_run_at") or ""),
                  reverse=True)
    print(f"{'system':<22} {'last run':<17} {'last output':<17} runs/in/out")
    for name, hb in rows:
        t = hb.get("totals") or {}
        print(f"{name:<22} {str(hb.get('last_run_at'))[:16]:<17} "
              f"{str(hb.get('last_output_at'))[:16]:<17} "
              f"{t.get('runs', 0)}/{t.get('inputs', 0)}/{t.get('outputs', 0)}"
              + (f"  ERROR {str(hb.get('last_error'))[:60]}"
                 if hb.get("last_error") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
