#!/usr/bin/env python3
"""mini_report_watch.py — surface the Mini's Problems/Flags to humans.

Santino 2026-09-27: the Crew zip mismatch sat in Mini flags since 08-15
because nothing READ the reports — the dot only tracks heartbeat
freshness, not content. Daily (client-ops-sync): parse the newest
clients/_ops/mini-reports/DAILY-*.md, take every bullet under
"## Problems" and "## Flags", and file each NEW one as an open
ops-attention note (marketing_ops_notes, author mini-watch). Dedupe via
ops_kv mini-report-seen (hash per bullet) so an item pings exactly once.
Fail-open: a parse error never breaks the sync.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")
from client_ops_sync import _sb  # noqa: E402

REPORTS = ROOT / "clients" / "_ops" / "mini-reports"
KV = "mini-report-seen"


def main() -> int:
    dailies = sorted(REPORTS.glob("DAILY-*.md"))
    if not dailies:
        print("mini-report-watch: no daily reports")
        return 0
    latest = dailies[-1]
    text = latest.read_text()
    items: list[str] = []
    for section in ("Problems", "Flags"):
        m = re.search(rf"##\s*{section}(.*?)(?=\n## |\Z)", text, re.S)
        if not m:
            continue
        for line in m.group(1).splitlines():
            line = line.strip()
            if line.startswith("- ") and len(line) > 8:
                items.append(f"[{section.lower()[:-1]}] {line[2:]}")
    if not items:
        print(f"mini-report-watch: {latest.name} clean")
        return 0
    rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{KV}&select=v") or []
    seen = (rows[0].get("v") if rows else {}) or {}
    new = 0
    for it in items:
        h = hashlib.sha256(it.encode()).hexdigest()[:16]
        if h in seen:
            continue
        body = (f"MINI REPORT ({latest.name}): {it[:400]} — review; the "
                "Mini cannot resolve this alone.")
        _sb("POST", "/rest/v1/marketing_ops_notes",
            {"company_id": None, "author": "mini-watch", "status": "open",
             "body": body}, prefer="return=minimal")
        seen[h] = latest.name
        new += 1
        print(f"  filed: {it[:90]}")
    _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
        {"k": KV, "v": seen}, prefer="resolution=merge-duplicates")
    print(f"mini-report-watch: {latest.name} — {new} new item(s) surfaced, "
          f"{len(items) - new} already seen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
