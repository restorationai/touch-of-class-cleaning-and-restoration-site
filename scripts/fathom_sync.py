#!/usr/bin/env python3
"""Fathom → meeting-intel auto-sync.

Polls the Fathom API for new recordings, matches each client-facing meeting
to a Rank AI client, distills the Fathom summary into concierge meeting
intel (clients/_ops/meeting-intel/{slug}.md), and drops a note on the
client's GHL contact so the whole team sees what was covered.

The point: the Client Concierge composes nudges from these intel files —
after this sync, a client is never re-asked something they already answered
on a call, within ~an hour of the recording landing.

Skips: meetings matching no client (sales calls with prospects, internal
team calls) are recorded in state as 'unmatched' and never retried.

Commands:
    sync [--send] [--backfill N]   poll + process. Default dry-run (prints
                                   what it would write); --send writes intel,
                                   GHL notes, and state. --backfill N looks
                                   at the last N meetings on first run
                                   (default 0 = only meetings after now).

State: clients/_ops/fathom-sync-state.json (processed recording ids).
Env: FATHOM_API_KEY + the concierge's env. launchd: io.restorationai.fathom-sync (hourly).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from client_concierge import (  # noqa: E402
    ROOT, anthropic_json, fetch_companies, load_env,
)

STATE_PATH = ROOT / "clients" / "_ops" / "fathom-sync-state.json"
INTEL_DIR = ROOT / "clients" / "_ops" / "meeting-intel"
FATHOM_API = "https://api.fathom.ai/external/v1"

MATCH_SYSTEM = """\
You match a meeting recording to one of our restoration-industry clients.
You get the client roster (slug, company name, owner) and the meeting's
title + summary opening. Sales calls with NEW prospects (anyone not on the
roster), internal team meetings, and vendor calls match NOTHING.
Return ONLY JSON: {"slug": "<roster slug>"|null, "why": string}"""

DISTILL_SYSTEM = """\
You distill a meeting summary into INTERNAL onboarding intel for our client
concierge (an assistant that texts clients about missing setup items). Output
tight markdown for the intel file:

### <YYYY-MM-DD> — <meeting title> (auto-synced from Fathom)
- FACTS: hard facts learned (license numbers, domains, emails, who owns what,
  decisions made). One per line.
- ANSWERED/IN-PROGRESS: setup items this meeting answered or that are now in
  motion on either side — the concierge must NOT re-ask these. Be explicit.
- ASK NEXT: anything the client agreed to send/do (so the concierge nudges
  for exactly that, in plain words).
- APPOINTMENTS: any future call/meeting scheduled, with date+time+tz.
Omit empty sections. No preamble. Facts only — never invent.
Return ONLY JSON: {"intel": string, "ghl_note": string}
ghl_note = 3-6 plain sentences for the client's CRM record (what was covered,
what's next), no markdown, no links."""


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"processed": {}, "initialized_at": None}


def fathom_meetings(limit: int = 25) -> list[dict]:
    r = requests.get(f"{FATHOM_API}/meetings",
                     params={"include_summary": "true", "limit": limit},
                     headers={"X-Api-Key": os.environ["FATHOM_API_KEY"]},
                     timeout=60)
    r.raise_for_status()
    return r.json().get("items", [])


def roster(companies: dict) -> tuple[str, dict]:
    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    slug_by_cid = {cid: slug for slug, cid in cmap.items()}
    lines, by_slug = [], {}
    for cid, co in companies.items():
        slug = slug_by_cid.get(cid)
        if not slug:
            continue
        contacts = ((co.get("integration_settings") or {}).get("contacts")) or []
        people = "; ".join(
            f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
            + (f" <{c.get('email')}>" if c.get("email") else "")
            for c in contacts if c.get("first_name") or c.get("email"))
        lines.append(f"- slug={slug}  company=\"{co.get('name')}\"  "
                     f"people=\"{people}\"")
        by_slug[slug] = co
    return "\n".join(lines), by_slug


def ghl_contact_for(company: dict) -> str | None:
    contacts = ((company.get("integration_settings") or {}).get("contacts")) or []
    for c in contacts:
        if c.get("ghl_contact_id"):
            return c["ghl_contact_id"]
    return (company.get("integration_settings") or {}).get("ghl_contact_id")


def add_ghl_note(contact_id: str, body: str) -> None:
    from client_concierge import _ghl
    _ghl("POST", f"/contacts/{contact_id}/notes", body={"body": body})


def cmd_sync(args) -> int:
    dry_run = not args.send
    state = load_state()
    first_run = state.get("initialized_at") is None
    meetings = fathom_meetings()
    companies = fetch_companies()
    roster_text, by_slug = roster(companies)

    if first_run:
        state["initialized_at"] = datetime.now(timezone.utc).isoformat()
        if not args.backfill:
            # baseline: mark everything current as seen; only future syncs
            for m in meetings:
                state["processed"][str(m.get("recording_id"))] = "baseline"
            print(f"first run: baselined {len(meetings)} existing meeting(s)"
                  " — only NEW recordings will be mined (use --backfill N to"
                  " mine recent ones now)")
            if not dry_run:
                STATE_PATH.write_text(json.dumps(state, indent=1))
            return 0
        meetings = meetings[:args.backfill]

    new = [m for m in meetings
           if str(m.get("recording_id")) not in state["processed"]]
    print(f"fathom sync: {len(new)} new meeting(s)"
          f"{' [DRY RUN]' if dry_run else ''}")
    for m in reversed(new):  # oldest first
        rid = str(m.get("recording_id"))
        title = m.get("title") or m.get("meeting_title") or "?"
        summary_md = ((m.get("default_summary") or {})
                      .get("markdown_formatted") or "")
        when = (m.get("recording_start_time") or m.get("created_at") or "")[:10]
        print(f"\n--- {when} {title!r} (recording {rid})")
        if not summary_md:
            print("    no summary yet — leaving for next run")
            continue

        match = anthropic_json(
            MATCH_SYSTEM,
            f"Roster:\n{roster_text}\n\nMeeting title: {title}\n"
            f"Summary opening:\n{summary_md[:1200]}")
        slug = match.get("slug")
        if not slug or slug not in by_slug:
            print(f"    unmatched ({match.get('why', '?')[:90]}) — skipping forever")
            state["processed"][rid] = "unmatched"
            continue
        company = by_slug[slug]
        print(f"    matched -> {slug} ({company.get('name')})")

        distilled = anthropic_json(
            DISTILL_SYSTEM,
            f"Client: {company.get('name')} (slug {slug})\n"
            f"Meeting: {title} on {when}\nFathom URL: {m.get('url')}\n\n"
            f"Summary:\n{summary_md[:9000]}")
        intel = (distilled.get("intel") or "").strip()
        note = (distilled.get("ghl_note") or "").strip()
        if not intel:
            print("    distill produced nothing — skipping")
            state["processed"][rid] = "empty"
            continue

        intel_path = INTEL_DIR / f"{slug}.md"
        block = f"\n\n{intel}\n_(source: Fathom {m.get('url')}, auto-synced)_\n"
        if dry_run:
            print(f"    [dry-run] would append to {intel_path.name}:\n{intel[:500]}")
            if note:
                print(f"    [dry-run] would add GHL note: {note[:200]}")
        else:
            INTEL_DIR.mkdir(parents=True, exist_ok=True)
            if not intel_path.exists():
                intel_path.write_text(f"# Meeting intel — {company.get('name')}\n")
            with intel_path.open("a") as f:
                f.write(block)
            print(f"    intel appended -> {intel_path}")
            cid = ghl_contact_for(company)
            if cid and note:
                try:
                    add_ghl_note(cid, f"[Auto from Fathom] {title} ({when}): {note}")
                    print(f"    GHL note added on contact {cid}")
                except RuntimeError as e:
                    print(f"    ! GHL note failed: {e}", file=sys.stderr)
        state["processed"][rid] = slug

    if not dry_run:
        STATE_PATH.write_text(json.dumps(state, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("sync")
    ps.add_argument("--send", action="store_true",
                    help="write intel + GHL notes + state (default: dry run)")
    ps.add_argument("--backfill", type=int, default=0,
                    help="on first run, also mine the N most recent meetings")
    args = ap.parse_args()
    load_env()
    for k in ("FATHOM_API_KEY", "ANTHROPIC_API_KEY", "SUPABASE_URL"):
        if not os.environ.get(k):
            print(f"ERROR: missing env {k}", file=sys.stderr)
            return 1
    return {"sync": cmd_sync}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
