#!/usr/bin/env python3
"""Evening note-sync (6pm PT): push the day's Notion call-list notes to GHL.

The morning pipeline syncs notes written YESTERDAY; this evening pass gets
today's notes onto the GHL contact the same day (Santino 2026-07-14). Sync
only: no repaint, no email, no router. Safe to run any number of times —
dedupe is per contact+note-text — and it also captures "remove from list"
notes into the durable removed.json so tomorrow's list honors them.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_daily import seed_if_empty, BASE  # noqa: E402


def main() -> int:
    seed_if_empty()
    import daily_pipeline as D
    pid_file = BASE / "notion_page_id.txt"
    if not pid_file.exists():
        print("[notes-sync] no notion_page_id.txt yet — nothing to sync")
        return 0
    pid = pid_file.read_text().strip()
    D.log(f"=== Evening note-sync (page {pid[:12]}…) ===")
    D.sync_call_notes(pid)
    D.log("=== Evening note-sync done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
