#!/usr/bin/env python3
"""conflict_marker_guard.py — never let git conflict markers reach main.

2026-09-30 incident: an automated `git pull --rebase --autostash` inside the
client-ops-sync job hit a stash-pop conflict on files the run itself had
rewritten (clients/_ops/last-sync.json, 7 photo-manifest.json files). git
leaves `<<<<<<< Updated upstream ... >>>>>>> Stashed changes` in the working
tree and still exits 0, and the next `git add clients/ && git commit`
shipped them. From then on every ops-sync run crashed on line 1 reading its
own state file, which silently stopped onboarding (Restoration Resource's
first GBP sync), bootstraps and every nightly lane.

Run this before every automated `git add`/commit and after every
autostash pull. For each file containing markers:
  - JSON: rebuild it from one side of every hunk, preferring the LOCAL side
    ("Stashed changes" / the run's own fresh output), then upstream; keep
    the first variant that parses.
  - anything else: restore the committed version (git checkout HEAD -- f);
    the run's local edit to that file is dropped, never half-merged.
Also drops a leftover autostash entry once its file is resolved.

Exit 0 always (it is a cleaner, not a gate) unless --strict, which exits 1
when anything had to be repaired.

Usage: python3 scripts/conflict_marker_guard.py [--strict] [paths...]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARK = re.compile(r"^(<<<<<<< |>>>>>>> )", re.M)
HUNK = re.compile(r"^<<<<<<< [^\n]*\n(.*?)^=======\n(.*?)^>>>>>>> [^\n]*\n",
                  re.S | re.M)
DEFAULT_PATHS = ["clients", "sites", "scripts", "templates", "docs", "portfolio"]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True).stdout


def candidates(paths: list[str]) -> list[str]:
    """Modified, staged or untracked files under paths (markers only ever
    appear in files the working tree touched)."""
    out = _git("status", "--porcelain", "--untracked-files=all", "--", *paths)
    files = []
    for line in out.splitlines():
        f = line[3:].strip().strip('"')
        if " -> " in f:
            f = f.split(" -> ", 1)[1]
        p = ROOT / f
        if p.is_file() and p.stat().st_size < 20_000_000:
            files.append(f)
    return files


def _resolve_json(text: str) -> str | None:
    for side in (2, 1):      # 2 = local/stashed side, 1 = upstream
        t = text
        for _ in range(5):   # nested hunks resolve outside-in
            t2 = HUNK.sub(lambda m: m.group(side), t)
            if t2 == t:
                break
            t = t2
        if MARK.search(t):
            continue
        try:
            json.loads(t)
            return t
        except ValueError:
            continue
    return None


def main() -> int:
    strict = "--strict" in sys.argv
    paths = [a for a in sys.argv[1:] if not a.startswith("--")] or DEFAULT_PATHS
    fixed = []
    for f in candidates(paths):
        p = ROOT / f
        try:
            text = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if not MARK.search(text):
            continue
        if f.endswith(".json"):
            good = _resolve_json(text)
            if good is not None:
                p.write_text(good)
                fixed.append(f"{f} (json resolved)")
                continue
        tracked = _git("ls-files", "--", f).strip()
        if tracked:
            _git("checkout", "HEAD", "--", f)
            fixed.append(f"{f} (restored committed version)")
        else:
            p.unlink()
            fixed.append(f"{f} (untracked, removed)")
    if fixed:
        _git("reset", "-q")            # unstage anything half-merged
        print("conflict_marker_guard: repaired " + "; ".join(fixed))
        # an autostash that conflicted stays in the stash list; it's
        # been applied by hand above, so drop it
        import os
        if os.environ.get("CI") and "autostash" in _git("stash", "list").lower():
            _git("stash", "drop", "-q")
    return 1 if (strict and fixed) else 0


if __name__ == "__main__":
    sys.exit(main())
