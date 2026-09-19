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
  System 1 (keyword-researcher):     14
  System 2 (content-writer):          3
  System 3 (onsite-audit):           30
  System 4 (refresh-recommender):    30

A system is "due" if last_run_at is null OR (now - last_run_at) >= cadence_days.
System 1 is ALSO demand-driven: it becomes due whenever a client's content queue
drops below QUEUE_LOW_THRESHOLD, so the queue is refilled on need, not just on the
calendar (the producer/consumer fix — System 2 drains ~2/week, so a pure 14-day
refill could still trend dry between runs).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file() -> None:
    """Fail-soft .env loader (local runs). Never overrides existing env vars —
    CI keeps injecting secrets via the workflow env blocks."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_load_env_file()

# Prompt files used in headless (CI) mode — paths relative to the CLIENT'S
# vertical template dir (templates/{vertical}/...). Resolved per client via
# scripts/verticals.py at run time; hardcoding templates/restoration here
# caused the davis-construction incident.
HEADLESS_PROMPT_MAP = {
    1: "prompts/keyword-researcher.md",
    3: "prompts/onsite-audit.md",
    4: "prompts/refresh-recommender.md",
}

# DataForSEO tools each system needs in headless mode.
# `mcp__dataforseo` (bare server grant, allows every tool the server exposes)
# rides along with the named tools: the 08-26 CI probe showed the npx-latest
# dataforseo-mcp-server now exposes a generic `api_request` tool the agents
# reach for, and the old per-tool names silently stopped matching — every
# DataForSEO call was permission-DENIED, which is why System 1 refills
# stopped landing fleet-wide while nothing errored.
HEADLESS_ALLOWED_TOOLS = {
    1: (
        "Bash,Read,Write,Edit,Glob,Grep,WebFetch,"
        "mcp__dataforseo,"
        "mcp__dataforseo__dataforseo_labs_google_keyword_ideas,"
        "mcp__dataforseo__dataforseo_labs_google_related_keywords,"
        "mcp__dataforseo__dataforseo_labs_bulk_keyword_difficulty,"
        "mcp__dataforseo__dataforseo_labs_search_intent,"
        "mcp__dataforseo__ai_optimization_chat_gpt_scraper,"
        "mcp__dataforseo__ai_optimization_keyword_data_search_volume"
    ),
    3: (
        "Bash,Read,Write,Edit,Glob,Grep,WebFetch,"
        "mcp__dataforseo,"
        "mcp__dataforseo__on_page_lighthouse,"
        "mcp__dataforseo__on_page_instant_pages,"
        "mcp__dataforseo__on_page_content_parsing"
    ),
    4: "Bash,Read,Write,Edit,Glob,Grep,WebFetch",
}

SCHEDULE_DEFAULTS = {
    # 0 runs FIRST so the seeded best-of item is written by System 2 in the
    # SAME Mon/Thu run. 14d cadence = ~2 best-of posts/month/client, rotating
    # the city x service matrix (scripts/best_of_seeder.py).
    0: {"name": "best-of-seeder",         "cadence_days": 14, "driver": "script"},
    1: {"name": "keyword-researcher",     "cadence_days": 14, "driver": "agent"},
    # 2 (not 3): the Mon+Thu crons are nominally 3 days apart, but GitHub cron start
    # times jitter by up to ~2h, so a strict >=3d check made Thursday runs land at
    # ~2d22h and skip the post (observed Jun 18 + Jun 25). 2 days keeps Mon->Thu and
    # Thu->Mon both reliably due while still preventing double-posts within one day.
    2: {"name": "content-writer",         "cadence_days":  2, "driver": "script"},
    3: {"name": "onsite-audit",           "cadence_days": 30, "driver": "agent"},
    4: {"name": "refresh-recommender",    "cadence_days": 30, "driver": "split"},  # L1 script, L2 agent
}

# Demand-driven queue management for System 1 (the producer/consumer fix).
# System 2 drains ~2 posts/week; a fixed calendar refill alone trends the queue dry.
#   - QUEUE_LOW_THRESHOLD: System 1 becomes "due" when queued items < this, regardless
#     of the 14-day calendar. run-due processes System 1 before System 2, so a low queue
#     is refilled and consumed in the SAME Mon/Thu run (no dead week). The keyword
#     researcher's own per-seed 30-day cooldown still prevents re-researching a seed.
#   - QUEUE_ALERT_THRESHOLD: after a run, any active client still below this gets an
#     email alert (catches the silent case where the refill failed or ran out of seeds).
QUEUE_LOW_THRESHOLD = 4
QUEUE_ALERT_THRESHOLD = 2


# -----------------------------------------------------------------------------
# Client discovery + status accessors
# -----------------------------------------------------------------------------


# Statuses that mean "stop working for them". Everything else is a client we
# are delivering to (2026-08-06).
#
# WHY THIS CHANGED: load_clients required the literal string "active", and only
# 6 of 22 client records carry it. The rest sat at "onboarding" (9), "pending"
# (4) or "live" (1) — including PuroClean, whose status is literally `live`, and
# nine clients with a built site and 8+ published posts. Every one of them was
# silently excluded from ALL FIVE systems: no content, no keyword research, no
# audits, no refresh. That is what "17 clients with zero AI-citation posts"
# actually meant — not an idle System 0, an empty client list.
#
# Same shape video_cron.active_clients() already uses, and the same reason: the
# app's pause button writes companies.status in Supabase and never touches the
# local file, so the DB is authoritative for departure and the local status is
# only a hint. Fail OPEN on the DB read — never stop a paying client's systems
# because of an API hiccup.
DEPARTED = {"archived", "churned", "paused", "cancelled", "canceled", "inactive", "suspended"}


def _db_departed_ids() -> set:
    try:
        if not os.environ.get("SUPABASE_URL"):
            return set()
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"],
                           os.environ["SUPABASE_SERVICE_ROLE_KEY"])
        rows = sb.table("companies").select("id,status").execute().data or []
        return {r["id"] for r in rows
                if str(r.get("status") or "").strip().lower() in DEPARTED}
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"  companies status lookup failed: {str(e)[:120]}\n")
        return set()


def load_clients(slug_filter: str | None = None) -> list[dict]:
    out = []
    db_departed = _db_departed_ids()
    cmap = {}
    try:
        cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    except Exception:
        pass
    for path in sorted((ROOT / "clients").glob("*.json")):
        if path.stem == "company_map":
            continue
        c = json.loads(path.read_text())
        if str(c.get("status") or "").strip().lower() in DEPARTED:
            continue
        if (c.get("company_id") or cmap.get(path.stem)) in db_departed:
            continue
        if slug_filter and c.get("slug") != slug_filter:
            continue
        out.append(c)
    return out


def last_run_at(client: dict, system: int) -> datetime | None:
    """Return the last run time for a given system on this client, or None."""
    slug = client["slug"]
    if system == 0:
        # System 0 derives from the queue: newest best-of item it ever seeded
        q_path = ROOT / "clients" / slug / "content-queue.json"
        if not q_path.exists():
            return None
        q = json.loads(q_path.read_text())
        items = q if isinstance(q, list) else q.get("items", [])
        stamps = [i.get("queued_at") for i in items
                  if i.get("source") == "best-of-seeder" and i.get("queued_at")]
        return _parse_iso(max(stamps)) if stamps else None
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
        # "published" = written + live-URL verified (content_writer verification step)
        written = [i.get("written_at") for i in q.get("items", [])
                   if i.get("status") in ("written", "published") and i.get("written_at")]
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


def queued_count(client: dict) -> int:
    """Number of items still waiting to be written for this client."""
    q_path = ROOT / "clients" / client["slug"] / "content-queue.json"
    if not q_path.exists():
        return 0
    try:
        q = json.loads(q_path.read_text())
    except (json.JSONDecodeError, OSError):
        return 0
    return sum(1 for i in q.get("items", []) if i.get("status") == "queued")


def is_due(client: dict, system: int) -> tuple[bool, str]:
    """Return (due, reason)."""
    # System 1 is demand-driven as well as calendar-driven: if the content queue is
    # running low, refill it now regardless of the 14-day cadence. Because run-due
    # processes System 1 before System 2, the refill is consumed in the same pass.
    if system == 1:
        qc = queued_count(client)
        if qc < QUEUE_LOW_THRESHOLD:
            return True, f"queue low ({qc} queued < {QUEUE_LOW_THRESHOLD})"
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


def _call_with_timeout(cmd: list[str], cwd: Path, env=None,
                       timeout_s: int = 900, label: str = "") -> int:
    """subprocess with a hard wall-clock cap (2026-08-26).

    Root cause of the weekly-maintenance 2-hour deaths + the fleet-wide
    content stall since ~08-04: `claude -p` invocations (and their npx MCP
    server children) occasionally never exit, and subprocess.call waited
    forever — one hung client killed content for EVERY client after it,
    and the end-of-job commit step never ran, discarding even the posts
    that WERE written. A hang now skips ONE job. start_new_session +
    killpg takes the orphaned MCP server down with the parent."""
    import signal
    print(f"\n    $ {' '.join(cmd[:3])}{' ...' if len(cmd) > 3 else ''}  (cap {timeout_s // 60}m)")
    proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, start_new_session=True)
    try:
        return proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        print(f"    !! TIMEOUT after {timeout_s // 60}m — killing "
              f"{label or cmd[0]} process group, moving to the next job")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:  # noqa: BLE001 — group may already be gone
            proc.kill()
        proc.wait()
        return 124


def run_script(cmd: list[str], cwd: Path = ROOT) -> int:
    """Run a script-driven system. Streams output, returns exit code."""
    return _call_with_timeout(cmd, cwd, timeout_s=900)


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
    # Per-client vertical resolution (fail-loud): templates/{vertical}/{prompt_rel}.
    # SystemExit is caught so one client's missing vertical asset marks THIS
    # system failed (non-zero, alert fires) without killing other clients' runs.
    import verticals  # local sibling module (scripts/)
    try:
        prompt_path = verticals.resolve_template(slug, prompt_rel)
    except SystemExit:
        print(f"    System {system} ({name}) BLOCKED for {slug}: vertical template "
              f"resolution failed (see ERROR above).")
        return 1
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
    # Fresh CI runners cold-start the npx MCP server; give it 2 min to connect
    # instead of the default (audits were aborting on "still connecting").
    env = {**os.environ, "MCP_TIMEOUT": "120000"}
    # 30m not 20m: the 08-26 catch-up run showed real, healthy content jobs
    # taking 23-27 minutes wall clock — a 1200s cap kills legitimate posts
    # mid-write. The cap exists for HANGS, so it sits above the slowest
    # observed honest job, not the average one.
    return _call_with_timeout(cmd, ROOT, env=env, timeout_s=1800,
                              label=f"S{system} {slug}")


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
        wanted = tuple(int(x) for x in str(getattr(args, "systems", "") or "").split(",")
                       if x.strip().isdigit()) or (0, 1, 2, 3, 4)
        for sys_id in wanted:
            due, reason = is_due(c, sys_id)
            sched = SCHEDULE_DEFAULTS[sys_id]
            marker = "DUE  " if due else "ok   "
            print(f"    [{marker}] System {sys_id} ({sched['name']:21}) — {reason}")
        print()
    return 0


def send_alert_email(subject: str, body: str) -> bool:
    """Send an ops alert via SendGrid (same from/to as scripts/notify_failure.py).
    No-op (returns False) when SENDGRID_API_KEY is unset, e.g. local runs."""
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        print("    (SENDGRID_API_KEY unset — skipping email alert)")
        return False
    payload = {
        "personalizations": [{"to": [{"email": "contact@restorationai.io"}], "subject": subject}],
        "from": {"email": "no-reply@restorationai.io", "name": "Rank AI Bot"},
        "content": [{"type": "text/plain", "value": body}],
    }
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"    Alert emailed to contact@restorationai.io (HTTP {resp.status})")
        return True
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        detail = exc.read().decode(errors="replace") if isinstance(exc, urllib.error.HTTPError) else str(exc)
        print(f"    SendGrid alert failed: {detail}", file=sys.stderr)
        return False


def alert_starved_queues(clients: list[dict]) -> None:
    """Post-run safety net: email ops about any active client whose queue is still
    critically low AFTER the refill pass. Catches the silent failure the GH Actions
    if:failure() step misses (System 1 errored, ran out of fresh seeds, or coverage
    consumed every candidate). Re-reads the queue from disk to reflect this run."""
    starved = [(c["slug"], queued_count(c)) for c in clients
               if queued_count(c) < QUEUE_ALERT_THRESHOLD]
    if not starved:
        return
    lines = "\n".join(f"  - {slug}: {n} queued" for slug, n in starved)
    body = (
        "These active clients have a near-empty content queue AFTER the latest "
        "scheduler run, so System 2 will have nothing to publish next cycle:\n\n"
        f"{lines}\n\n"
        "Likely cause: System 1 (keyword-researcher) failed, ran out of fresh seeds "
        "(all within their per-seed 30-day cooldown), or coverage consumed every "
        "candidate.\n\nAction: check the latest weekly-maintenance run logs, or force a "
        "refill:\n  python3 scripts/master_scheduler.py force-run --slug <slug> --system 1 --headless\n\n"
        "-- Rank AI Bot"
    )
    print(f"\n  ALERT: {len(starved)} client(s) with starved queue — emailing ops.")
    send_alert_email(
        subject=f"[Rank AI] {len(starved)} client(s) with empty content queue",
        body=body,
    )


def cmd_list_due(args) -> int:
    """JSON array of slugs due for any of --systems (per-client fan-out:
    the content-daily matrix runs ONE isolated job per due client, so
    fleet growth adds parallel jobs instead of queue depth — Santino
    2026-09-19: "per-client basis, not bulk")."""
    import json as _json
    wanted = tuple(int(x) for x in str(getattr(args, "systems", "") or "").split(",")
                   if x.strip().isdigit()) or (0, 2)
    out = []
    for c in load_clients(None):
        for sys_id in wanted:
            due, _ = is_due(c, sys_id)
            if due and can_run_directly(c, sys_id):
                out.append(c["slug"])
                break
    print(_json.dumps(sorted(set(out))))
    return 0


def cmd_run_due(args) -> int:
    clients = load_clients(args.slug if not args.all else None)
    if not clients:
        print("No active clients to process.")
        return 0
    if args.all:
        # STALENESS-FIRST (2026-09-05, the narestco starvation): the workflow
        # step has a 60-minute budget and alphabetical order meant aaa->crew
        # consumed it EVERY run, so d-z clients never got a System 2 turn
        # (narestco: 9 days without a post while the scheduler looked green).
        # Hungriest-first means a truncated run always feeds whoever waited
        # longest, and rotation emerges naturally.
        def _hunger(c: dict):
            try:
                lr = last_run_at(c, 2)
            except Exception:  # noqa: BLE001
                lr = None
            return lr or datetime(1970, 1, 1, tzinfo=timezone.utc)

        clients = sorted(clients, key=_hunger)
        print("run-due order (staleness-first): "
              + ", ".join(c["slug"] for c in clients[:8]) + ", ...")
    any_action = False
    for c in clients:
        slug = c["slug"]
        print(f"\n=== {slug} ===")
        wanted = tuple(int(x) for x in str(getattr(args, "systems", "") or "").split(",")
                       if x.strip().isdigit()) or (0, 1, 2, 3, 4)
        for sys_id in wanted:
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
            if sys_id == 0:
                if args.dry_run:
                    print(f"    DRY-RUN: would invoke best_of_seeder for {slug}")
                else:
                    rc = run_script(["python3", str(ROOT / "scripts" / "best_of_seeder.py"),
                                     "--slug", slug])
                    if rc != 0:
                        print(f"    FAILED with rc={rc}")
            elif sys_id == 1:
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
                # Deterministic layer: write tiered SEO fixes/proposals into the
                # app's action plan (marketing_action_plan). Code-verified checks,
                # idempotent, and never resurrects a user-dismissed row. Runs every
                # cadence regardless of agent/headless mode.
                if not args.dry_run:
                    rc_det = run_script(["python3", str(ROOT / "scripts" / "seo_audit_actions.py"),
                                         "--slug", slug])
                    if rc_det != 0:
                        print(f"    seo_audit_actions FAILED with rc={rc_det}")
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
    # Email ops if any client is still starved after the refill pass. Only in headless
    # (CI) runs so local/interactive invocations don't send mail.
    if getattr(args, "headless", False):
        alert_starved_queues(clients)
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
# Coverage gate — is every marketing system actually running for every client?
# -----------------------------------------------------------------------------

COVERAGE_QUEUE_WARN = 3          # queued items below this → WARN
COVERAGE_AUDIT_MAX_DAYS = 45     # onsite audit older than this → MISS
COVERAGE_GEOGRID_MAX_DAYS = 21   # newest geo-grid scan older than this → MISS
COVERAGE_AI_MAX_DAYS = 14        # newest AI-search scan older than this → MISS
COVERAGE_NAP_MAX_DAYS = 35       # nap-audit.json older than this → MISS (monthly cadence + slack)


def _company_map() -> dict:
    try:
        return json.loads((ROOT / "clients" / "company_map.json").read_text())
    except Exception:
        return {}


def _sb_select(table: str, params: list[tuple[str, str]]) -> list | None:
    """Supabase PostgREST read. None = creds missing or request failed
    (callers report UNKNOWN instead of MISS so we don't false-alarm)."""
    sb = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (sb and key):
        return None
    req = urllib.request.Request(
        f"{sb}/rest/v1/{table}?{urllib.parse.urlencode(params)}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:  # noqa: BLE001
        print(f"    [warn] Supabase read {table} failed: {str(e)[:120]}", file=sys.stderr)
        return None


def _latest_by_company(table: str, ts_col: str, company_ids: list[str]) -> dict | None:
    """Return {company_id: latest_ts (datetime)} for a Supabase table, or None
    when Supabase is unreachable."""
    if not company_ids:
        return {}
    rows = _sb_select(table, [
        ("company_id", f"in.({','.join(company_ids)})"),
        ("select", f"company_id,{ts_col}"),
        ("order", f"{ts_col}.desc"),
        ("limit", "2000"),
    ])
    if rows is None:
        return None
    out: dict = {}
    for r in rows:
        cid = r.get("company_id")
        ts = _parse_iso(r.get(ts_col))
        if cid and ts and cid not in out:
            out[cid] = ts
    return out


def cmd_coverage(args) -> int:
    """Check every ACTIVE client has every marketing system running. Prints a
    table; exit 1 when any client has a MISSING system (CI flags it)."""
    clients = load_clients(getattr(args, "slug", None))
    if not clients:
        print("No active clients found.")
        return 0
    now = datetime.now(timezone.utc)
    cmap = _company_map()
    company_ids = [cmap.get(c["slug"]) or c.get("company_id") for c in clients]
    company_ids = [cid for cid in company_ids if cid]

    geogrid_latest = _latest_by_company("marketing_geogrid_scans", "scanned_at", company_ids)
    ai_latest = _latest_by_company("marketing_ai_search_scans", "scanned_at", company_ids)
    gbp_rows = _sb_select("marketing_gbp_profiles", [
        ("company_id", f"in.({','.join(company_ids)})"),
        ("select", "company_id"),
    ]) if company_ids else []
    gbp_companies = {r["company_id"] for r in gbp_rows} if gbp_rows is not None else None

    failures: list[str] = []   # "slug: what is missing"
    warnings: list[str] = []

    def cell(status: str, detail: str = "") -> str:
        return f"{status}({detail})" if detail else status

    header = (f"{'CLIENT':32} {'VERTICAL':18} {'QUEUE':10} {'KW-BANK':10} {'AUDIT<=45d':12} "
              f"{'GEOGRID<=21d':14} {'GBP-PROFILE':12} {'AI-SCAN<=14d':12} {'NAP<=35d':15}")
    print(f"Coverage gate — {now.isoformat(timespec='seconds')}\n")
    print(header)
    print("-" * len(header))

    for c in clients:
        slug = c["slug"]
        cid = cmap.get(slug) or c.get("company_id")
        row: list[str] = []

        # 0. vertical set + templates/{vertical}/prompts/content-writer.md exists
        vertical = c.get("vertical")
        if not vertical:
            row.append(cell("MISS", "unset"))
            failures.append(f"{slug}: no \"vertical\" field in clients/{slug}.json — "
                            f"pipeline can't resolve templates (davis incident guard)")
        elif not (ROOT / "templates" / vertical / "prompts" / "content-writer.md").exists():
            row.append(cell("MISS", vertical[:8]))
            failures.append(f"{slug}: vertical={vertical} but templates/{vertical}/prompts/"
                            f"content-writer.md does not exist — build the {vertical} assets")
        else:
            row.append(cell("OK", vertical[:12]))

        # 1. content queue depth
        qc = queued_count(c)
        if qc == 0:
            row.append(cell("MISS", "0"))
            failures.append(f"{slug}: content queue is EMPTY (System 1 refill not landing)")
        elif qc < COVERAGE_QUEUE_WARN:
            row.append(cell("WARN", str(qc)))
            warnings.append(f"{slug}: content queue low ({qc} < {COVERAGE_QUEUE_WARN})")
        else:
            row.append(cell("OK", str(qc)))

        # 2. keyword bank exists + size
        bank_path = ROOT / "clients" / slug / "keyword-bank.json"
        if not bank_path.exists():
            row.append("MISS")
            failures.append(f"{slug}: keyword-bank.json missing (System 1 never ran)")
        else:
            try:
                bank = json.loads(bank_path.read_text())
                n_kw = len(bank.get("keywords", []))
            except (json.JSONDecodeError, OSError):
                n_kw = 0
            if n_kw == 0:
                row.append(cell("WARN", "0"))
                warnings.append(f"{slug}: keyword bank exists but has 0 keywords")
            else:
                row.append(cell("OK", str(n_kw)))

        # 3. onsite audit within 45d
        audit_at = _parse_iso((c.get("audit") or {}).get("last_audit_at"))
        if audit_at is None:
            row.append("MISS")
            failures.append(f"{slug}: no onsite audit on record (System 3 never ran)")
        else:
            age = (now - audit_at).days
            if age > COVERAGE_AUDIT_MAX_DAYS:
                row.append(cell("MISS", f"{age}d"))
                failures.append(f"{slug}: onsite audit is {age}d old (max {COVERAGE_AUDIT_MAX_DAYS}d)")
            else:
                row.append(cell("OK", f"{age}d"))

        # 4. geo-grid: configs exist AND a scan within 21d in Supabase
        kw_file = ROOT / "clients" / slug / "geogrid-keywords.txt"
        city_file = ROOT / "clients" / slug / "geogrid-cities.json"
        if not (kw_file.exists() and city_file.exists()):
            missing = [p.name for p in (kw_file, city_file) if not p.exists()]
            row.append(cell("MISS", "cfg"))
            failures.append(f"{slug}: geo-grid config missing ({', '.join(missing)})")
        elif not cid:
            row.append(cell("MISS", "no-cid"))
            failures.append(f"{slug}: no company_id mapping — geo-grid scans can't be verified")
        elif geogrid_latest is None:
            row.append(cell("UNKNOWN", "no-sb"))
            warnings.append(f"{slug}: geo-grid scan freshness unknown (Supabase unreachable)")
        else:
            ts = geogrid_latest.get(cid)
            age = (now - ts).days if ts else None
            if ts is None:
                row.append(cell("MISS", "none"))
                failures.append(f"{slug}: no geo-grid scans in Supabase")
            elif age > COVERAGE_GEOGRID_MAX_DAYS:
                row.append(cell("MISS", f"{age}d"))
                failures.append(f"{slug}: newest geo-grid scan is {age}d old (max {COVERAGE_GEOGRID_MAX_DAYS}d)")
            else:
                row.append(cell("OK", f"{age}d"))

        # 5. GBP profile row exists
        if not cid:
            row.append(cell("MISS", "no-cid"))
            failures.append(f"{slug}: no company_id mapping — GBP profile can't be verified")
        elif gbp_companies is None:
            row.append(cell("UNKNOWN", "no-sb"))
            warnings.append(f"{slug}: GBP profile unknown (Supabase unreachable)")
        elif cid not in gbp_companies:
            row.append("MISS")
            failures.append(f"{slug}: no row in marketing_gbp_profiles (GBP sync never ran)")
        else:
            row.append("OK")

        # 6. AI-search scan within 14d
        if not cid:
            row.append(cell("MISS", "no-cid"))
            failures.append(f"{slug}: no company_id mapping — AI-search scans can't be verified")
        elif ai_latest is None:
            row.append(cell("UNKNOWN", "no-sb"))
            warnings.append(f"{slug}: AI-search scan freshness unknown (Supabase unreachable)")
        else:
            ts = ai_latest.get(cid)
            age = (now - ts).days if ts else None
            if ts is None:
                row.append(cell("MISS", "none"))
                failures.append(f"{slug}: no AI-search scans in Supabase")
            elif age > COVERAGE_AI_MAX_DAYS:
                row.append(cell("MISS", f"{age}d"))
                failures.append(f"{slug}: newest AI-search scan is {age}d old (max {COVERAGE_AI_MAX_DAYS}d)")
            else:
                row.append(cell("OK", f"{age}d"))

        # 7. NAP audit: nap-audit.json fresh (<=35d) AND zero unresolved mismatches
        nap_path = ROOT / "clients" / slug / "nap-audit.json"
        if not nap_path.exists():
            row.append(cell("MISS", "never"))
            failures.append(f"{slug}: NAP audit never ran (clients/{slug}/nap-audit.json missing "
                            f"— run scripts/nap_audit.py --slug {slug})")
        else:
            try:
                nap = json.loads(nap_path.read_text())
            except (json.JSONDecodeError, OSError):
                nap = {}
            nap_at = _parse_iso(nap.get("checked_at"))
            n_mismatch = len(nap.get("mismatches") or [])
            nap_age = (now - nap_at).days if nap_at else None
            if nap_at is None or nap_age > COVERAGE_NAP_MAX_DAYS:
                row.append(cell("MISS", "stale" if nap_at else "never"))
                failures.append(f"{slug}: NAP audit is "
                                f"{f'{nap_age}d old' if nap_at else 'undated'} "
                                f"(max {COVERAGE_NAP_MAX_DAYS}d)")
            elif n_mismatch:
                row.append(cell("MISS", "mismatch"))
                failures.append(f"{slug}: {n_mismatch} unresolved NAP mismatch(es) — "
                                f"see clients/{slug}/nap-audit.json")
            else:
                row.append(cell("OK", f"{nap_age}d"))

        print(f"{slug:32} {row[0]:18} {row[1]:10} {row[2]:10} {row[3]:12} {row[4]:14} "
              f"{row[5]:12} {row[6]:12} {row[7]:15}")

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")
    if failures:
        print("\nMISSING systems (coverage gate FAILED):")
        for f_ in failures:
            print(f"  - {f_}")
        print(f"\n{len(failures)} gap(s) across {len(clients)} active client(s). Exit 1.")
        return 1
    print(f"\nAll systems covered for {len(clients)} active client(s).")
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
    pr.add_argument("--systems", default="",
                    help="Comma-separated system ids to run (e.g. 0,2). Empty = all.")
    pr.set_defaults(func=cmd_run_due)

    pl = sub.add_parser("list-due", help="JSON slugs due for --systems (matrix fan-out)")
    pl.add_argument("--systems", default="0,2")
    pl.set_defaults(func=cmd_list_due)

    pf = sub.add_parser("force-run", help="Force-run one system on one client regardless of schedule")
    pf.add_argument("--slug", required=True)
    pf.add_argument("--system", type=int, choices=[1, 2, 3, 4], required=True)
    pf.add_argument("--branch", default="main", help="Branch for System 2 deploy (default: main)")
    pf.add_argument("--headless", action="store_true",
                    help="CI mode: invoke claude -p for agent-driven systems")
    pf.set_defaults(func=cmd_force_run)

    pc = sub.add_parser("coverage",
                        help="Check every active client has every marketing system running "
                             "(vertical, queue, keyword bank, audit, geo-grid, GBP, AI-search, NAP). "
                             "Exit 1 on gaps.")
    pc.add_argument("--slug", help="Limit to one client")
    pc.set_defaults(func=cmd_coverage)

    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.cmd == "run-due" and not (args.slug or args.all):
        print("Either --slug or --all is required for run-due.", file=sys.stderr)
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
