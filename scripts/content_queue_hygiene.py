#!/usr/bin/env python3
"""content_queue_hygiene.py — C3 (Santino 2026-09-17: "23 queued posts is
too long... if they change their strategy they'd wait for 23 posts").

Keeps every client's content queue SHALLOW: at most MAX_QUEUED items in
'queued' status. Overflow moves to 'banked' — still on file, visible to
planners, re-promoted automatically when the queue has room — so a
strategy change lands within days (the next seeds reflect CURRENT
strategy) instead of behind a month-deep backlog.

Keep order (best 6): prioritized items first (strategist pins + app
target-terms — client-driven work is never demoted), then the seeder's
rotation item, then newest first. Re-promotion order: banked items come
back newest-first only while the queue is under the cap, so fresh
strategy always outranks old backlog.

Rides content-daily BEFORE the writer. CLI:
    python3 scripts/content_queue_hygiene.py [--dry-run]
"""
from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_QUEUED = 6


def keep_rank(item: dict) -> tuple:
    src = str(item.get("source") or "")
    client_driven = (item.get("prioritized")
                     or src.startswith("app target-term"))
    return (
        0 if client_driven else
        1 if src == "best-of-seeder" else 2,
        # within a class: newest first
        "" if not item.get("queued_at") else "",
    )


def hygiene(qpath: Path, dry: bool) -> str | None:
    q = json.loads(qpath.read_text())
    items = q.get("items") or []
    queued = [i for i in items if i.get("status") == "queued"]
    banked = [i for i in items if i.get("status") == "banked"]
    changed = False

    if len(queued) > MAX_QUEUED:
        ordered = sorted(
            queued,
            key=lambda i: (keep_rank(i)[0], str(i.get("queued_at") or "")),
        )
        # keep: all class-0 (client-driven, never demoted) + fill to cap
        keep = [i for i in ordered if keep_rank(i)[0] == 0]
        rest = [i for i in ordered if keep_rank(i)[0] != 0]
        rest.sort(key=lambda i: str(i.get("queued_at") or ""), reverse=True)
        keep += rest[: max(0, MAX_QUEUED - len(keep))]
        keep_ids = {id(i) for i in keep}
        demoted = 0
        for i in queued:
            if id(i) not in keep_ids:
                i["status"] = "banked"
                i["banked_at"] = datetime.now(timezone.utc).isoformat()
                demoted += 1
        changed = demoted > 0
        result = f"trimmed {demoted} to bank (kept {len(keep)})"
    elif len(queued) < MAX_QUEUED and banked:
        room = MAX_QUEUED - len(queued)
        banked.sort(key=lambda i: str(i.get("queued_at") or ""), reverse=True)
        promoted = 0
        for i in banked[:room]:
            i["status"] = "queued"
            i.pop("banked_at", None)
            promoted += 1
        changed = promoted > 0
        result = f"promoted {promoted} from bank"
    else:
        return None

    if changed and not dry:
        qpath.write_text(json.dumps(q, indent=2) + "\n")
    return result + (" [dry-run]" if dry else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for qf in sorted(glob.glob(str(ROOT / "clients/*/content-queue.json"))):
        slug = Path(qf).parent.name
        try:
            r = hygiene(Path(qf), a.dry_run)
        except Exception as e:  # noqa: BLE001
            print(f"  {slug}: ERROR {str(e)[:100]}")
            continue
        if r:
            print(f"  {slug}: {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
