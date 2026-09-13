#!/usr/bin/env python3
"""gameplan_dispatch.py — the game plan executes itself (4b, 2026-09-13).

Santino: "I don't want to have to review the game plan in a client's
account every time and tell you to manually execute it."

The monthly analyzer publishes Game Plan steps into marketing_action_plan
(client_analyzer.emit_gameplan). This script is the bridge that makes the
AUTO steps run without anyone asking:

  DISPATCH   every gameplan_step row with status=planned and an automatic
             assigned_system (anything but 'manual') becomes a [DEV] note —
             the nightly dev agent's inbox (dev_inbox.py, dev-agent.yml:
             2:07am PT nightly + 1:07pm PT weekdays). The row flips to
             'approved', which the app renders as Queued. The note carries
             the step's action_key so completion can be traced.
  SWEEP      dispatched rows complete THEMSELVES: when the dev agent
             resolves the note (dev_inbox done — which also writes the
             work_log evidence and the client-facing summary line), the
             matching row flips to 'done'. No human clicks; Done always
             means the work verifiably ran.

Manual steps are untouched: they stay visible with the admin-only
"Completed" button in the app.

Cron: rides client-ops-sync (daily) — dispatch is idempotent (planned ->
approved gates re-dispatch; note ids are remembered in ops_kv).

CLI:
    python3 scripts/gameplan_dispatch.py            # dispatch + sweep, all
    python3 scripts/gameplan_dispatch.py --dry-run
    python3 scripts/gameplan_dispatch.py --slug narestco
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from client_ops_sync import _sb, slug_map  # noqa: E402

# Hands-off clients: no work of any kind, including dispatched tasks.
HANDS_OFF_SLUGS = {"paul-davis-charleston", "go-green-restoration-of-nc",
                   "kenneth-w-talbot-jr"}


def _kv_get(k: str):
    rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{k}&select=v") or []
    return rows[0]["v"] if rows else None


def _kv_set(k: str, v) -> None:
    _sb("POST", "/rest/v1/ops_kv?on_conflict=k", {"k": k, "v": v},
        prefer="resolution=merge-duplicates")


def dispatch(dry_run: bool, only_slug: str | None) -> int:
    inv = {c: s for s, c in
           {s: c for c, s in slug_map().items()}.items()}  # cid -> slug
    rows = _sb("GET", "/rest/v1/marketing_action_plan"
               "?action_type=eq.gameplan_step&status=eq.planned"
               "&assigned_system=neq.manual"
               "&select=id,company_id,rank_ai_slug,action_key,title,"
               "rationale,assigned_system,impact") or []
    n = 0
    for r in rows:
        slug = r.get("rank_ai_slug") or inv.get(r["company_id"]) or "?"
        if only_slug and slug != only_slug:
            continue
        if slug in HANDS_OFF_SLUGS:
            continue
        body = (f"[DEV] {slug}: {r['title']}\n\n"
                f"WHY: {r.get('rationale') or '(see game plan)'}\n\n"
                f"This is game-plan step {r['action_key']} "
                f"(system: {r.get('assigned_system')}, "
                f"impact: {r.get('impact') or '?'}). Execute it end to end "
                "(the usual guards apply: verify from the outside, commit "
                "your work, client-safe language in the client line). "
                "Resolving this note auto-completes the client's Action "
                "Plan row.")
        print(f"  dispatch {slug} / {r['action_key']}: {r['title'][:70]}")
        if dry_run:
            n += 1
            continue
        note = _sb("POST", "/rest/v1/marketing_ops_notes",
                   {"company_id": r["company_id"], "body": body,
                    "status": "open", "author": "gameplan"},
                   prefer="return=representation")
        note_id = (note or [{}])[0].get("id")
        if not note_id:
            print("    !! note insert failed — row stays planned")
            continue
        _kv_set(f"gameplan-dispatch:{r['action_key']}:{r['company_id']}",
                {"note_id": note_id,
                 "at": datetime.now(timezone.utc).isoformat()})
        _sb("PATCH", f"/rest/v1/marketing_action_plan?id=eq.{r['id']}",
            {"status": "approved",
             "updated_at": datetime.now(timezone.utc).isoformat()})
        n += 1
    return n


def sweep(dry_run: bool, only_slug: str | None) -> int:
    rows = _sb("GET", "/rest/v1/marketing_action_plan"
               "?action_type=eq.gameplan_step&status=eq.approved"
               "&assigned_system=neq.manual"
               "&select=id,company_id,rank_ai_slug,action_key,title") or []
    n = 0
    for r in rows:
        if only_slug and (r.get("rank_ai_slug") or "") != only_slug:
            continue
        kv = _kv_get(f"gameplan-dispatch:{r['action_key']}:{r['company_id']}")
        if not (isinstance(kv, dict) and kv.get("note_id")):
            continue
        note = (_sb("GET", f"/rest/v1/marketing_ops_notes"
                    f"?id=eq.{kv['note_id']}&select=status") or [{}])[0]
        if (note.get("status") or "open") == "open":
            continue
        # note resolved by dev_inbox done (work_log evidence written there)
        print(f"  complete {r.get('rank_ai_slug')} / {r['action_key']}: "
              f"{r['title'][:70]}")
        if dry_run:
            n += 1
            continue
        _sb("PATCH", f"/rest/v1/marketing_action_plan?id=eq.{r['id']}",
            {"status": "done",
             "updated_at": datetime.now(timezone.utc).isoformat()})
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--slug")
    a = ap.parse_args()
    d = dispatch(a.dry_run, a.slug)
    s = sweep(a.dry_run, a.slug)
    print(f"gameplan dispatch: {d} step(s) -> dev inbox, "
          f"{s} completed from evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
