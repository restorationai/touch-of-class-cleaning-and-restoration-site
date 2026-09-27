#!/usr/bin/env python3
"""claude_config_backup.py — mirror Claude's skills + memory into the repo.

Santino 2026-09-27: "if anything happened to this computer, I would be
able to login on a new computer and pick up right where we left off."
The repo + app were already on GitHub, but the skills (~/.claude/skills),
custom commands, scheduled tasks and the cross-session memory lived ONLY
on this MacBook. This copies them into claude-config/ (plaintext, private
repo) after a FAIL-CLOSED secret scan: any real credential pattern aborts
the commit. Secrets themselves ride the encrypted vault
(scripts/secrets_backup.py) — never this folder.

  backup   mirror -> scan -> commit + push if anything changed
  restore  copy claude-config/ back into ~/.claude (fresh machine)

Runs daily via launchd (scripts/macbook/com.rankai.daily-backup.plist, 21:17 daily).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME_CLAUDE = Path.home() / ".claude"
PROJECT_KEY = "-Users-santino-Desktop-mywebsitecode-rank-ai"
DEST = ROOT / "claude-config"

# (source under ~/.claude, dest under claude-config/)
TREES = [
    ("skills", "skills"),
    ("commands", "commands"),
    ("scheduled-tasks", "scheduled-tasks"),
    (f"projects/{PROJECT_KEY}/memory", "memory"),
]

SECRET_RE = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{10,}|sbp_[a-f0-9]{20,}|AIza[0-9A-Za-z_-]{30,}"
    r"|ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,}|xox[bp]-[A-Za-z0-9-]{10,}"
    r"|SG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}|EAA[A-Za-z0-9]{40,}"
    r"|sk_live_[A-Za-z0-9]{10,}|rk_live_[A-Za-z0-9]{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY|\"refresh_token\"\s*:\s*\"1//)")


def _git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                          text=True).stdout


def mirror() -> None:
    for src_rel, dst_rel in TREES:
        src, dst = HOME_CLAUDE / src_rel, DEST / dst_rel
        if not src.exists():
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
            "__pycache__", ".DS_Store", "node_modules"))


def scan() -> list[str]:
    hits = []
    for f in DEST.rglob("*"):
        if not f.is_file() or f.stat().st_size > 2_000_000:
            continue
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        for m in SECRET_RE.finditer(text):
            hits.append(f"{f.relative_to(ROOT)}: {m.group(0)[:12]}...")
    return hits


def cmd_backup() -> int:
    mirror()
    hits = scan()
    if hits:
        print("SECRET SCAN FAILED — nothing committed. Remove these from the "
              "source files (put the secret in .env / the vault instead):")
        for h in hits:
            print("  " + h)
        return 1
    _git("add", "claude-config")
    if not _git("diff", "--cached", "--name-only", "--", "claude-config").strip():
        print("claude-config: no changes")
        return 0
    _git("commit", "-q", "-m", "claude-config: daily mirror of skills + "
         "memory + commands [automated]", "--", "claude-config")
    _git("pull", "-q", "--rebase", "--autostash", "origin", "main")
    _git("push", "-q", "origin", "main")
    print("claude-config: committed + pushed")
    return 0


def cmd_restore() -> int:
    for src_rel, dst_rel in TREES:
        src, dst = DEST / dst_rel, HOME_CLAUDE / src_rel
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print(f"restored {dst}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["backup", "restore"])
    a = ap.parse_args()
    return cmd_backup() if a.cmd == "backup" else cmd_restore()


if __name__ == "__main__":
    sys.exit(main())
