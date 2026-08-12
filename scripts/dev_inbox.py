#!/usr/bin/env python3
"""Dev-agent inbox — the approved [DEV] work queue (Santino 2026-07-30).

The nightly dev agent (a headless Claude Code run, .github/workflows/
dev-agent.yml) uses this to read its inbox and close out finished tasks.
[DEV] notes are created by: Santino's note composer (Site build tag), the
Fathom call listener's approved proposals, ad-hoc ops work, and — since
2026-08-05 — the concierge itself, when a client's own message says
something we built is wrong (scripts/feedback_router.py).

CLOSING THE LOOP (2026-08-05). A client-originated task is not finished when
the deploy is green. It is finished when the CLIENT knows. `done` therefore
files two things for a client-feedback task instead of one:
  * the usual [TODO-SANTINO] Review row, so Santino eyeballs the result, and
  * a [FROM SANTINO] directive telling Monica to text them that it is fixed,
    with the link — the message we had been writing by hand all night
    ("Made it dark and moody with black vehicles, take another look").
[FROM SANTINO] is a directive tag in client_concierge, so it bypasses the
cadence cooldown and goes out on the next pass instead of waiting for a
nudge slot. Both halves also land in marketing_work_log, so the client's
monthly report shows the request, the work and the reply as one story.

MONTHLY SUMMARY LINE (2026-08-11). Every `done` also lands one row in
marketing_work_log, which scripts/monthly_summary.py compiles into the
client's Monthly Summary tab in the app. The row's detail is the
`--client-line` when given — a sentence written FOR THE CLIENT (no file
names, no tool names, no jargon) — else a mechanically cleaned version of
the technical summary. Pass --client-line every time; the fallback is a
net, not a voice.

Commands:
    list                    open [DEV] notes as JSON (id, company_id, slug,
                            task, origin) — `origin` is non-null when the
                            task came from a client's own words
    count                   just the number (workflow gate — skip run when 0)
    done --id X --summary "what was done" [--client-line "plain sentence"]
                            [--link URL] [--no-notify]
                            resolve the note + file the [TODO-SANTINO] review
                            row + one client-readable marketing_work_log line;
                            for client-feedback tasks also file the
                            [FROM SANTINO] note that tells the client
    punt --id X --reason "why it could not be done safely"
                            resolve the note + file a question row instead
                            (a waiting client is named in the row)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb, slug_map  # noqa: E402
from feedback_router import (compose_done_directive, parse_origin,  # noqa: E402
                             site_status)


INBOX_PAGE = 1000


def open_devs() -> list[dict]:
    # EXPLICIT page + a loud warning when it fills (2026-08-05). The query
    # had no limit, so it inherited PostgREST's server cap — and with
    # created_at.asc the rows that fall off the end are the NEWEST ones, i.e.
    # a client's just-queued task would go missing from the inbox while
    # sitting perfectly well in the table. "Queued but invisible" is the same
    # failure as "never queued" to everyone downstream.
    notes = _sb("GET", "/rest/v1/marketing_ops_notes?status=eq.open"
                "&select=id,company_id,body,created_at"
                f"&order=created_at.asc&limit={INBOX_PAGE}") or []
    if len(notes) >= INBOX_PAGE:
        print(f"WARNING: {INBOX_PAGE}+ open ops notes — the inbox page is "
              "full and the newest tasks may be cut off. Raise INBOX_PAGE.",
              file=sys.stderr)
    smap = slug_map()
    out = []
    for n in notes:
        if not n["body"].startswith("[DEV]"):
            continue
        out.append({"id": n["id"], "company_id": n["company_id"],
                    "slug": smap.get(n["company_id"]),
                    "task": n["body"][len("[DEV]"):].strip(),
                    "origin": parse_origin(n["body"]),
                    "created_at": n["created_at"]})
    return out


def _note(company_id: str, body: str) -> None:
    _sb("POST", "/rest/v1/marketing_ops_notes",
        {"company_id": company_id, "body": body})


_CODE_FILE_RE = re.compile(
    r"\b(?:sites|scripts|clients|src|templates|workers)/[\w./-]+"
    r"|\b[\w-]+\.(?:py|ts|tsx|js|mjs|json|md|astro|yml|sql)\b")


def _plainify(text: str) -> str:
    """Fallback client-readable cleanup for an engineer-written summary:
    strip code ticks, file paths, bracket tags, URLs and em dashes. A real
    --client-line always beats this."""
    t = re.sub(r"`+", "", str(text or ""))
    t = re.sub(r"\[[A-Z][A-Z -]*\]", "", t)
    t = _CODE_FILE_RE.sub("", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\s*[—–]\s*", ", ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,;:")
    return t[:180]


def _log(company_id: str, action: str, detail: str, evidence: dict) -> None:
    """Ledger line, fail-open — bookkeeping never blocks the close-out."""
    try:
        from work_log import work_log
        work_log(company_id, "site", action, detail, evidence=evidence,
                 actor="dev-agent", source="dev_inbox.py")
    except Exception as e:  # noqa: BLE001
        print(f"  [work-log] warn: {str(e)[:90]}")


def close_the_loop(company_id: str, origin: dict, summary: str,
                   link: str | None) -> None:
    """File the [FROM SANTINO] note that sends the client their answer.

    Best-effort by design: the work is already done and already reviewable,
    so a failure here must not fail the task close-out. It prints loudly
    instead, and the [TODO-SANTINO] row (filed either way) is the backstop."""
    try:
        slug = origin.get("slug")
        if not link:
            _, _, link = site_status(company_id, slug)
        body = compose_done_directive(origin, summary, link)
        _note(company_id, body)
        who = origin.get("who") or "the client"
        print(f"loop closed: [FROM SANTINO] filed — Monica tells {who} it is "
              f"done{' with ' + link if link else ''}")
        _log(company_id, "client-feedback-notified",
             f"Told {who} their website change was done: {summary[:140]}",
             {"who": who, "quote": (origin.get("quote") or "")[:300],
              "link": link, "category": origin.get("cat")})
    except Exception as e:  # noqa: BLE001
        print(f"WARNING: could not file the client notification ({e}). The "
              "review row is filed, so tell them by hand.", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("count")
    pd = sub.add_parser("done")
    pd.add_argument("--id", required=True)
    pd.add_argument("--summary", required=True)
    pd.add_argument("--client-line", default="",
                    help="the same fact in words the CLIENT reads in their "
                         "monthly summary: no file names, no jargon, no "
                         "internal tool names (falls back to a cleaned "
                         "version of --summary)")
    pd.add_argument("--link", default="",
                    help="the URL to hand the client (defaults to the site's "
                         "current apex or preview URL)")
    pd.add_argument("--no-notify", action="store_true",
                    help="skip the client notification — use ONLY when the "
                         "change is not yet visible to them")
    pp = sub.add_parser("punt")
    pp.add_argument("--id", required=True)
    pp.add_argument("--reason", required=True)
    a = ap.parse_args()

    if a.cmd == "list":
        print(json.dumps(open_devs(), indent=1))
        return 0
    if a.cmd == "count":
        print(len(open_devs()))
        return 0

    rows = _sb("GET", f"/rest/v1/marketing_ops_notes?id=eq.{a.id}"
               "&select=id,company_id,body") or []
    if not rows:
        print(f"ERROR: note {a.id} not found", file=sys.stderr)
        return 1
    note = rows[0]
    origin = parse_origin(note["body"])
    now = datetime.now(timezone.utc).isoformat()
    _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{a.id}",
        {"status": "resolved", "resolved_at": now})
    if a.cmd == "done":
        _note(note["company_id"],
              f"[TODO-SANTINO] Review: dev agent finished — {a.summary} "
              f"(task was: {note['body'][:120]}) Hit Done after you eyeball it."
              + (f" CLIENT WAITING: {origin.get('who')} asked for this, and "
                 "Monica has been told to tell them it is done." if origin
                 else ""))
        print("resolved + review row filed")
        # One client-readable ledger line per completed task — this is what
        # the app's Monthly Summary tab shows the client (monthly_summary.py
        # prefers evidence.client_line over the technical detail).
        client_line = a.client_line.strip() or _plainify(a.summary)
        if origin:
            _log(note["company_id"], "client-feedback-done",
                 f"Made the website change {origin.get('who') or 'the client'} "
                 f"asked for: {client_line[:140]}",
                 {"quote": (origin.get("quote") or "")[:300],
                  "category": origin.get("cat"), "note_id": a.id,
                  "summary": a.summary[:200], "client_line": client_line})
            if a.no_notify:
                print("client notification SKIPPED (--no-notify) — the "
                      "review row still names them as waiting")
            else:
                close_the_loop(note["company_id"], origin, client_line,
                               a.link.strip() or None)
        else:
            _log(note["company_id"], "dev-task-done",
                 f"Website work completed: {client_line[:150]}",
                 {"note_id": a.id, "summary": a.summary[:200],
                  "client_line": client_line})
    else:
        _note(note["company_id"],
              f"[TODO-SANTINO] Dev agent NEEDS INPUT: {a.reason} "
              f"(task was: {note['body'][:120]})"
              + (f" A CLIENT IS WAITING ON THIS: {origin.get('who')} said "
                 f"\"{(origin.get('quote') or '')[:120]}\" — they have not "
                 "been told anything yet." if origin else ""))
        print("resolved + needs-input row filed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
