#!/usr/bin/env python3
"""
Rank AI — Master Scheduler (v1, interactive-first).

The single entry point for "what's due across all clients" and "run what's due".
Loops over active clients, checks each of the 4 SEO systems against its schedule
default, and either:

  - runs the script-driven systems directly (System 2 content_writer, System 4
    Layer 1 refresh_scorer), or
  - prints the exact skill invocation to paste into Claude Code for the
    agent-driven systems (System 1 keyword-researcher, System 3 onsite-audit,
    System 4 Layer 2 refresh-recommender).

This is v1 — designed to be run interactively from a Claude Code session.
A future v2 will wrap it in a launchd / cron job that invokes the Claude CLI
non-interactively for the agent-driven systems.

Usage:
  python3 scripts/master_scheduler.py status                      # everything
  python3 scripts/master_scheduler.py status --slug narestco      # one client
  python3 scripts/master_scheduler.py run-due --slug narestco     # run what's due
  python3 scripts/master_scheduler.py run-due --all               # all clients
  python3 scripts/master_scheduler.py force-run --slug narestco --system 3

Schedule defaults (cadence_days):
  System 1 (keyword-researcher):     30
  System 2 (content-writer):          7
  System 3 (onsite-audit):           30
  System 4 (refresh-recommender):    30

A system is "due" if last_run_at is null OR (now - last_run_at) >= cadence_days.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent

# Prompt files used in headless (CI) mode — paths relative to ROOT
HEADLESS_PROMPT_MAP = {
    1: "templates/restoration/prompts/keyword-researcher.md",
    3: "templates/restoration/prompts/onsite-audit.md",
    4: "templates/restoration/prompts/refresh-recommender.md",
}

# DataForSEO tools each system needs in headless mode
HEADLESS_ALLOWED_TOOLS = {
    1: (
        "Bash,Read,Write,Edit,Glob,Grep,WebFetch,"
        "mcp__dataforseo__dataforseo_labs_google_keyword_ideas,"
        "mcp__dataforseo__dataforseo_labs_google_related_keywords,"
        "mcp__dataforseo__dataforseo_labs_bulk_keyword_difficulty,"
        "mcp__dataforseo__dataforseo_labs_search_intent,"
        "mcp__dataforseo__ai_optimization_chat_gpt_scraper,"
        "mcp__dataforseo__ai_optimization_keyword_data_search_volume"
    ),
    3: (
        "Bash,Read,Write,Edit,Glob,Grep,WebFetch,"
        "mcp__dataforseo__on_page_lighthouse,"
        "mcp__dataforseo__on_page_instant_pages,"
        "mcp__dataforseo__on_page_content_parsing"
    ),
    4: "Bash,Read,Write,Edit,Glob,Grep,WebFetch",
}

SCHEDULE_DEFAULTS = {
    1: {"name": "keyword-researcher",     "cadence_days": 30, "driver": "agent"},
    2: {"name": "content-writer",         "cadence_days":  3, "driver": "script"},
    3: {"name": "onsite-audit",           "cadence_days": 30, "driver": "agent"},
    4: {"name": "refresh-recommender",    "cadence_days": 30, "driver": "split"},  # L1 script, L2 agent
}


# -----------------------------------------------------------------------------
# Client discovery + status accessors
# -----------------------------------------------------------------------------


def load_clients(slug_filter: str | None = None) -> list[dict]:
    out = []
    for path in sorted((ROOT / "clients").glob("*.json")):
        c = json.loads(path.read_text())
        if c.get("status") != "active":
            continue
        if slug_filter and c.get("slug") != slug_filter:
            continue
        out.append(c)
    return out


def last_run_at(client: dict, system: int) -> datetime | None:
    """Return the last run time for a given system on this client, or None."""
    slug = client["slug"]
    if system == 1:
        # System 1 stores per-seed timestamps in keyword-bank.json
        bank_path = ROOT / "clients" / slug / "keyword-bank.json"
        if not bank_path.exists():
            return None
        bank = json.loads(bank_path.read_text())
        seeds = bank.get("seeds_researched", [])
        if not seeds:
            return None
        latest = max(s.get("last_researched", "") for s in seeds)
        return _parse_iso(latest) if latest else None
    if system == 2:
        # System 2 stores last write timestamp in content-queue items
        q_path = ROOT / "clients" / slug / "content-queue.json"
        if not q_path.exists():
            return None
        q = json.loads(q_path.read_text())
        written = [i.get("written_at") for i in q.get("items", []) if i.get("status") == "written" and i.get("written_at")]
        return max(_parse_iso(w) for w in written) if written else None
    if system == 3:
        return _parse_iso(client.get("audit", {}).get("last_audit_at"))
    if system == 4:
        # Layer 2 last_run_at is the canonical timestamp for the system
        return _parse_iso(client.get("refresh", {}).get("last_run_at"))
    raise ValueError(f"Unknown system {system}")


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except ValueError:
        return None


def is_due(client: dict, system: int) -> tuple[bool, str]:
    """Return (due, reason)."""
    last = last_run_at(client, system)
    cadence = SCHEDULE_DEFAULTS[system]["cadence_days"]
    if last is None:
        return True, "never run"
    age = datetime.now(timezone.utc) - last
    if age >= timedelta(days=cadence):
        return True, f"last run {age.days}d ago (cadence {cadence}d)"
    return False, f"last run {age.days}d ago (next due in {cadence - age.days}d)"


def can_run_directly(client: dict, system: int) -> bool:
    """System 3 and System 4 prefer apex (cutover complete). System 2 needs queue."""
    if system == 3:
        return client.get("audit") is not None or client.get("build_status") in ("pushed_main", "pushed_staging", "live")
    if system == 2:
        # System 2 needs queued items
        q_path = ROOT / "clients" / client["slug"] / "content-queue.json"
        if not q_path.exists():
            return False
        q = json.loads(q_path.read_text())
        return any(i.get("status") == "queued" for i in q.get("items", []))
    return True


# -----------------------------------------------------------------------------
# Runners
# -----------------------------------------------------------------------------


def run_script(cmd: list[str], cwd: Path = ROOT) -> int:
    """Run a script-driven system. Streams output, returns exit code."""
    print(f"\n    $ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(cwd))


def emit_agent_prompt(system: int, slug: str) -> str:
    """Return the prompt the user should paste into Claude Code to run this system."""
    skill = f"rank-ai-{SCHEDULE_DEFAULTS[system]['name']}"
    return f"/{skill} slug={slug}"


def _write_mcp_config() -> Path:
    """Write a temporary DataForSEO MCP config for headless runs. Returns path."""
    config = {
        "mcpServers": {
            "dataforseo": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "dataforseo-mcp-server"],
                "env": {
                    "DATAFORSEO_USERNAME": os.environ.get("DATAFORSEO_USERNAME", ""),
                    "DATAFORSEO_PASSWORD": os.environ.get("DATAFORSEO_PASSWORD", ""),
                    "ENABLED_MODULES": (
                        "SERP,KEYWORDS_DATA,ONPAGE,DATAFORSEO_LABS,BACKLINKS,"
                        "DOMAIN_ANALYTICS,BUSINESS_DATA,CONTENT_ANALYSIS,AI_OPTIMIZATION"
                    ),
                },
            }
        }
    }
    path = Path("/tmp/rank-ai-mcp-headless.json")
    path.write_text(json.dumps(config))
    return path


def run_agent_headless(system: int, slug: str) -> int:
    """Invoke `claude -p` for an agent-driven system in CI / headless mode.

    Reads the per-system prompt file from the repo, prepends client context,
    and passes the full prompt to the Claude CLI with the appropriate MCP
    server config and allowed-tools list.
    """
    name = SCHEDULE_DEFAULTS[system]["name"]
    prompt_rel = HEADLESS_PROMPT_MAP.get(system)
    if not prompt_rel:
        print(f"    No headless prompt defined for System {system}")
        return 1
    prompt_path = ROOT / prompt_rel
    if not prompt_path.exists():
        print(f"    Prompt file not found: {prompt_path}")
        return 1

    mcp_config = _write_mcp_config()
    preamble = (
        f"You are a headless CI agent for Rank AI. "
        f"The repository root is your working directory. "
        f"Run completely end-to-end without pausing for user input. "
        f"If a non-critical step fails, log the error and continue.\n\n"
        f"Client slug: {slug}\n\n"
        f"Full methodology to follow:\n\n"
    )
    full_prompt = preamble + prompt_path.read_text()

    cmd = [
        "claude", "-p", full_prompt,
        "--mcp-config", str(mcp_config),
        "--allowed-tools", HEADLESS_ALLOWED_TOOLS[system],
    ]
    print(f"    [headless] claude -p  System {system} ({name}) for {slug} ...")
    return subprocess.call(cmd, cwd=str(ROOT))


# -----------------------------------------------------------------------------
# Subcommands
# -----------------------------------------------------------------------------


def cmd_status(args) -> int:
    clients = load_clients(args.slug)
    if not clients:
        print("No active clients found.")
        return 0
    print(f"Master Scheduler — status — {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
    for c in clients:
        slug = c["slug"]; name = c.get("display_name", slug)
        cutover = c.get("apex_cutover", {}).get("completed_at")
        print(f"=== {slug} — {name}")
        print(f"    apex_cutover:    {cutover or 'NOT CUT OVER (staging only)'}")
        print(f"    build_status:    {c.get('build_status')}")
        for sys_id in (1, 2, 3, 4):
            due, reason = is_due(c, sys_id)
            sched = SCHEDULE_DEFAULTS[sys_id]
            marker = "DUE  " if due else "ok   "
            print(f"    [{marker}] System {sys_id} ({sched['name']:21}) — {reason}")
        print()
    return 0


def cmd_run_due(args) -> int:
    clients = load_clients(args.slug if not args.all else None)
    if not clients:
        print("No active clients to process.")
        return 0
    any_action = False
    for c in clients:
        slug = c["slug"]
        print(f"\n=== {slug} ===")
        for sys_id in (1, 2, 3, 4):
            due, reason = is_due(c, sys_id)
            if not due:
                print(f"  System {sys_id}: {reason}")
                continue
            sched = SCHEDULE_DEFAULTS[sys_id]
            print(f"  System {sys_id} ({sched['name']}): DUE — {reason}")
            if not can_run_directly(c, sys_id):
                print(f"    SKIP — prerequisites not met (e.g., empty queue or no plan)")
                continue
            any_action = True
            if sys_id == 1:
                if args.headless:
                    rc = run_agent_headless(1, slug)
                    if rc != 0:
                        print(f"    FAILED with rc={rc}")
                else:
                    print(f"    Agent-driven. Paste into Claude Code:")
                    print(f"      {emit_agent_prompt(1, slug)}")
            elif sys_id == 2:
                if args.dry_run:
                    print(f"    DRY-RUN: would invoke content_writer next-post for {slug}")
                else:
                    rc = run_script(["python3", str(ROOT / "scripts" / "content_writer.py"),
                                     "next-post", "--slug", slug, "--branch", "main"])
                    if rc != 0:
                        print(f"    FAILED with rc={rc}")
            elif sys_id == 3:
                if args.headless:
                    rc = run_agent_headless(3, slug)
                    if rc != 0:
                        print(f"    FAILED with rc={rc}")
                else:
                    print(f"    Agent-driven. Paste into Claude Code:")
                    print(f"      {emit_agent_prompt(3, slug)}")
            elif sys_id == 4:
                # Layer 1 (script)
                if args.dry_run:
                    print(f"    DRY-RUN: would run refresh_scorer for {slug}")
                else:
                    rc = run_script(["python3", str(ROOT / "scripts" / "refresh_scorer.py"),
                                     "--slug", slug])
                    if rc != 0:
                        print(f"    Layer 1 FAILED with rc={rc} — skipping Layer 2 prompt")
                        continue
                # Layer 2 (agent)
                if args.headless:
                    rc2 = run_agent_headless(4, slug)
                    if rc2 != 0:
                        print(f"    Layer 2 FAILED with rc={rc2}")
                else:
                    print(f"    Layer 2 is agent-driven. Paste into Claude Code:")
                    print(f"      {emit_agent_prompt(4, slug)}")
    if not any_action:
        print("\nNothing due across all checked clients.")
    return 0


def cmd_force_run(args) -> int:
    clients = load_clients(args.slug)
    if not clients:
        print(f"Client not found: {args.slug}")
        return 1
    c = clients[0]
    slug = c["slug"]
    sys_id = args.system
    sched = SCHEDULE_DEFAULTS[sys_id]
    print(f"FORCE-RUN System {sys_id} ({sched['name']}) on {slug}")
    if sys_id == 2:
        return run_script(["python3", str(ROOT / "scripts" / "content_writer.py"),
                           "next-post", "--slug", slug, "--branch", args.branch])
    if sys_id == 4:
        rc = run_script(["python3", str(ROOT / "scripts" / "refresh_scorer.py"),
                         "--slug", slug])
        if rc == 0:
            if getattr(args, 'headless', False):
                return run_agent_headless(4, slug)
            print(f"\nLayer 1 done. Paste this into Claude Code to finish Layer 2:")
            print(f"  {emit_agent_prompt(4, slug)}")
        return rc
    # Agent-driven
    if getattr(args, 'headless', False):
        return run_agent_headless(sys_id, slug)
    print(f"Agent-driven system. Paste into Claude Code:")
    print(f"  {emit_agent_prompt(sys_id, slug)}")
    return 0


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="master_scheduler",
        description="Rank AI master scheduler — what's due across all clients?")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("status", help="Show what's due per client per system")
    ps.add_argument("--slug", help="Limit to one client")
    ps.set_defaults(func=cmd_status)

    pr = sub.add_parser("run-due", help="Run all due systems for one or all clients")
    pr.add_argument("--slug", help="One client")
    pr.add_argument("--all", action="store_true", help="All active clients")
    pr.add_argument("--dry-run", action="store_true", help="Print actions, don't execute")
    pr.add_argument("--headless", action="store_true",
                    help="CI mode: invoke claude -p for agent-driven systems instead of printing prompts")
    pr.set_defaults(func=cmd_run_due)

    pf = sub.add_parser("force-run", help="Force-run one system on one client regardless of schedule")
    pf.add_argument("--slug", required=True)
    pf.add_argument("--system", type=int, choices=[1, 2, 3, 4], required=True)
    pf.add_argument("--branch", default="main", help="Branch for System 2 deploy (default: main)")
    pf.add_argument("--headless", action="store_true",
                    help="CI mode: invoke claude -p for agent-driven systems")
    pf.set_defaults(func=cmd_force_run)

    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.cmd == "run-due" and not (args.slug or args.all):
        print("Either --slug or --all is required for run-due.", file=sys.stderr)
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
