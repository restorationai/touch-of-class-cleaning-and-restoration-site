#!/usr/bin/env python3
"""repo_git_guard.py — the ONE safe way for automation to pull/push the monorepo.

WHY (2026-08-18 incident): cutover_execute's commit-pull-push side effect ran
mid-session against unpushed local commits, its `pull --rebase` hit conflicts,
and it walked away leaving a stranded rebase-merge: the session's commits were
orphaned, 48 content files were later committed WITH raw conflict markers, and
a client site shipped a 404 hero. At least four scripts carried the same
unguarded dance (content_writer, cutover_execute, ads_provision,
case_study_intake).

Rules enforced by safe_sync():
  1. NEVER touch a repo that is mid-rebase or mid-merge — that state belongs
     to whoever created it.
  2. NEVER pull when the working tree still has changes beyond what the
     caller just committed — a dirty tree means a session (human or agent) is
     actively working; the caller's commit stays local and rides the
     session's next push instead.
  3. If the pull fails or leaves conflict state anyway: ABORT the rebase
     immediately (restore the pre-pull world), skip the push, say so loudly.
     A skipped push is retried by the next run; a stranded rebase corrupts
     everything that follows.

Usage (replaces inline pull/push in automation scripts):
    from repo_git_guard import safe_sync
    safe_sync(ROOT, actor="cutover_execute")   # -> bool (pushed or not)
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _run(args: list[str], cwd, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True,
                          text=True, timeout=timeout)


def repo_busy(root) -> str | None:
    """A reason this repo must not be synced right now, or None."""
    git = Path(root) / ".git"
    if (git / "rebase-merge").exists() or (git / "rebase-apply").exists():
        return "a rebase is in progress"
    if (git / "MERGE_HEAD").exists():
        return "a merge is in progress"
    return None


def safe_sync(root, actor: str = "automation") -> bool:
    """Pull-rebase-push the monorepo ONLY when it is safe. Returns True when
    the push happened. Never raises; never leaves conflict state behind."""
    try:
        return _safe_sync(root, actor)
    except Exception as e:  # noqa: BLE001 — a guard must never crash a caller
        try:
            _run(["git", "rebase", "--abort"], root)
        except Exception:  # noqa: BLE001
            pass
        print(f"  [{actor}] repo sync errored (non-fatal, next run retries): "
              f"{str(e)[:160]}")
        return False


def _safe_sync(root, actor: str) -> bool:
    busy = repo_busy(root)
    if busy:
        print(f"  [{actor}] repo sync SKIPPED: {busy} — not touching it")
        return False
    dirty = _run(["git", "status", "--porcelain"], root).stdout.strip()
    if dirty:
        print(f"  [{actor}] repo sync SKIPPED: working tree has other "
              f"changes ({len(dirty.splitlines())} path(s)) — a session is "
              "active; this commit stays local and rides the session's push")
        return False
    pull = _run(["git", "pull", "--rebase", "--autostash",
                 "origin", "main"], root)
    if pull.returncode != 0 or repo_busy(root):
        _run(["git", "rebase", "--abort"], root)
        print(f"  [{actor}] pull hit conflicts — rebase ABORTED cleanly, "
              f"push skipped (next run retries): "
              f"{(pull.stdout + pull.stderr)[-160:]}")
        return False
    push = _run(["git", "push", "origin", "main"], root)
    if push.returncode != 0:
        print(f"  [{actor}] push failed (non-fatal, next run retries): "
              f"{push.stderr[-160:]}")
        return False
    return True
