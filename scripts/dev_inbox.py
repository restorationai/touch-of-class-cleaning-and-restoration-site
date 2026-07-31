#!/usr/bin/env python3
"""Dev-agent inbox — the approved [DEV] work queue (Santino 2026-07-30).

The nightly dev agent (a headless Claude Code run, .github/workflows/
dev-agent.yml) uses this to read its inbox and close out finished tasks.
[DEV] notes are created by: Santino's note composer (Site build tag), the
Fathom call listener's approved proposals, and ad-hoc ops work.

Commands:
    list                    open [DEV] notes as JSON (id, company_id, slug, task)
    count                   just the number (workflow gate — skip run when 0)
    done --id X --summary " what was done"
                            resolve the note + file the [TODO-SANTINO] review
                            row so Santino sees the result in Today
    punt --id X --reason "why it could not be done safely"
                            resolve the note + file a question row instead
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb, slug_map  # noqa: E402


def open_devs() -> list[dict]:
    notes = _sb("GET", "/rest/v1/marketing_ops_notes?status=eq.open"
                "&select=id,company_id,body,created_at&order=created_at.asc") or []
    smap = slug_map()
    out = []
    for n in notes:
        if not n["body"].startswith("[DEV]"):
            continue
        out.append({"id": n["id"], "company_id": n["company_id"],
                    "slug": smap.get(n["company_id"]),
                    "task": n["body"][len("[DEV]"):].strip(),
                    "created_at": n["created_at"]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("count")
    pd = sub.add_parser("done")
    pd.add_argument("--id", required=True)
    pd.add_argument("--summary", required=True)
    pp = sub.add_parser("punt")
    pp.add_argument("--id", required=True)
    pp.add_argument("--reason", required=True)
    a = ap.parse_args()

    if a.cmd == "list":
        print(json.dumps(open_devs(), indent=1))
        return 0
    if a.cmd == "count":
        print(len(open_devs()))
        return 0

    rows = _sb("GET", f"/rest/v1/marketing_ops_notes?id=eq.{a.id}"
               "&select=id,company_id,body") or []
    if not rows:
        print(f"ERROR: note {a.id} not found", file=sys.stderr)
        return 1
    note = rows[0]
    now = datetime.now(timezone.utc).isoformat()
    _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{a.id}",
        {"status": "resolved", "resolved_at": now})
    if a.cmd == "done":
        _sb("POST", "/rest/v1/marketing_ops_notes", {
            "company_id": note["company_id"],
            "body": f"[TODO-SANTINO] Review: dev agent finished — {a.summary} "
                    f"(task was: {note['body'][:120]}) Hit Done after you eyeball it."})
        print("resolved + review row filed")
    else:
        _sb("POST", "/rest/v1/marketing_ops_notes", {
            "company_id": note["company_id"],
            "body": f"[TODO-SANTINO] Dev agent NEEDS INPUT: {a.reason} "
                    f"(task was: {note['body'][:120]})"})
        print("resolved + needs-input row filed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
