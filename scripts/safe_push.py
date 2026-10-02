#!/usr/bin/env python3
"""safe_push.py — commit + push from automation without losing work to a
rebase conflict.

2026-10-02: the nightly render sweep failed four runs in a row. Each run
rendered pages, committed, then `git pull --rebase` hit a content conflict
in clients/{slug}.json (another job had stamped the same client record),
left the checkout mid-rebase on a detached HEAD, the push failed, and the
next step crashed reading the conflicted JSON. The rendered pages were lost
every time.

On a rebase conflict this resolves instead of dying:
  JSON files   3-way merge per key (base / upstream / ours): a key changed
               on one side takes that side; changed on both, ours wins
               (the commit being applied is the fresher write).
  other files  upstream wins for that file (our edit to it is dropped and
               reported, never half-merged).
then continues the rebase and pushes, retrying up to 4 times.

    python3 scripts/safe_push.py -m "message" path [path ...]
    from safe_push import commit_and_push
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _git(*a: str, check: bool = False) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "GIT_EDITOR": "true"})
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(a)}: {r.stderr.strip()[:300]}")
    return r


def _merge(base, up, ours):
    if isinstance(base, dict) and isinstance(up, dict) and isinstance(ours, dict):
        out = {}
        for k in list(up.keys()) + [k for k in ours if k not in up]:
            b, u, o = base.get(k, None), up.get(k, None), ours.get(k, None)
            if k not in ours and k in base:      # we deleted it
                if u == b:
                    continue
                out[k] = u
                continue
            if k not in up and k in base:        # they deleted it
                if o == b:
                    continue
                out[k] = o
                continue
            out[k] = _merge(b, u, o) if k in up and k in ours else (u if k in up else o)
        return out
    if ours == base:
        return up
    return ours


def _show(stage: int, path: str):
    r = _git("show", f":{stage}:{path}")
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def _resolve_rebase() -> list[str]:
    """During a stopped rebase: :1 base, :2 upstream (HEAD), :3 our commit."""
    notes = []
    for path in _git("diff", "--name-only", "--diff-filter=U").stdout.split():
        if path.endswith(".json"):
            b, u, o = _show(1, path), _show(2, path), _show(3, path)
            if u is not None and o is not None:
                merged = _merge(b if b is not None else {}, u, o)
                (ROOT / path).write_text(json.dumps(merged, indent=2) + "\n")
                _git("add", path)
                notes.append(f"{path}: merged per key")
                continue
        _git("checkout", "--ours", "--", path)   # rebase: --ours = upstream
        _git("add", path)
        notes.append(f"{path}: kept upstream (our edit dropped)")
    return notes


def commit_and_push(paths: list[str], msg: str, tries: int = 4) -> bool:
    _git("add", "--", *paths)
    if _git("diff", "--cached", "--quiet").returncode == 0:
        return True
    _git("commit", "-m", msg, check=True)
    for _ in range(tries):
        r = _git("pull", "--rebase", "--autostash")
        guard = 0
        while (ROOT / ".git" / "rebase-merge").exists() or (ROOT / ".git" / "rebase-apply").exists():
            for n in _resolve_rebase():
                print(f"  safe_push: {n}")
            _git("rebase", "--continue")
            guard += 1
            if guard > 10:
                _git("rebase", "--abort")
                break
        subprocess.run([sys.executable, str(ROOT / "scripts" / "conflict_marker_guard.py")],
                       cwd=ROOT, capture_output=True)
        if _git("push").returncode == 0:
            return True
    print("  safe_push: push failed after retries", file=sys.stderr)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message", required=True)
    ap.add_argument("paths", nargs="+")
    a = ap.parse_args()
    return 0 if commit_and_push(a.paths, a.message) else 1


if __name__ == "__main__":
    sys.exit(main())
