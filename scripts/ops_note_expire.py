#!/usr/bin/env python3
"""ops_note_expire.py - nightly auto-expire for MACHINE ops notes.

WHY (Santino 2026-09-29): Ops Attention hit 2,489 open notes / 757 "Today"
items and became unusable. Machine writers (analyzer, preview pipeline,
stage checker, dev-agent handbacks, email intake, Monica acks) filed cards
that nothing ever closed, and several re-filed identical cards every run.
The one-time triage (clients/_ops/ops-triage-2026-09-29.json) cleared the
backlog; this pass keeps it clear, with the SAME rules, every night.

RULES (per leading tag; everything not listed is NEVER touched):
  [ANALYZER <date>]      newest card per client stays open, older weeks resolve
  [PREVIEW PIPELINE]     newest per client
  [STAGE:<board>:...]    newest per client + board
  [TODO-SANTINO]         14-day TTL; near-identical bodies per client collapse
  [TODO-PROPOSED]          to the newest; dev-agent handbacks that say the work
                           was already done / duplicate / no action needed
                           resolve; "Review: dev agent finished" rows resolve
                           after 3 days (the agent already did the work)
  [CLIENT EMAIL]         7-day TTL (intake records; the email itself is kept)
  [MONICA-ACK]           7-day TTL
  [DEV]                  dedupe only (identical body per client, newest kept)
  [PIPELINE ALERT]       pipeline_watchdog cards are reconciled by the
                           watchdog itself (one per key, auto-resolve on
                           clear); other writers' alerts: 5-day TTL
NEVER touched: untagged notes (Santino's instructions to Monica), [FROM
SANTINO], [FOR MONICA], [CONTEXT], [LSA-INTENT], [SUSPENSION], [HEADS-UP],
[CALL ALERT HELD], [CONTACT RECEIVED], [FLAG], [PROMISE...], and any tag not
in the rule list above.

Rides client-ops-sync daily (before pipeline_watchdog).
CLI: python3 scripts/ops_note_expire.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from client_ops_sync import _sb  # noqa: E402

TTL_DAYS = {"TODO-SANTINO": 14, "TODO-PROPOSED": 14, "CLIENT EMAIL": 7,
            "MONICA-ACK": 7}
REVIEW_ROW_DAYS = 3
FOREIGN_ALERT_DAYS = 5

# A dev-agent handback whose REASON says there was nothing to do.
_NOOP_START = re.compile(
    r"^\s*(ALREADY|DUPLICATE|False (positive|alarm)|No (site )?(work|action|change))",
    re.I)
_NOOP_ANY = re.compile(
    r"no site (work|change)s?( made| needed)?|exact re-?file|duplicate "
    r"(service_ripple|of the)|false (positive|alarm)|no action needed|"
    r"nothing to (do|change)", re.I)


def tag_of(body: str) -> str:
    m = re.match(r"^\s*\[([^\]]+)\]", body or "")
    if not m:
        return ""
    t = m.group(1)
    if t.startswith("ANALYZER"):
        return "ANALYZER"
    if t.startswith("STAGE:"):
        return "STAGE"
    return t


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", (s or "").lower())).strip()


def fetch_open() -> list[dict]:
    out: list[dict] = []
    off = 0
    while True:
        rows = _sb("GET", "/rest/v1/marketing_ops_notes?status=eq.open"
                   "&select=id,company_id,body,author,created_at"
                   f"&order=created_at.desc&limit=1000&offset={off}",
                   prefer="return=representation") or []
        out += rows
        if len(rows) < 1000:
            return out
        off += 1000


def plan(notes: list[dict], now: datetime) -> dict[str, tuple[str, str]]:
    """id -> (tag, reason). `notes` must be newest-first."""
    res: dict[str, tuple[str, str]] = {}

    def age(n: dict) -> float:
        ts = datetime.fromisoformat(str(n["created_at"]).replace("Z", "+00:00"))
        return (now - ts).total_seconds() / 86400

    seen: set = set()
    for n in notes:
        body = n.get("body") or ""
        t = tag_of(body)
        cid = n.get("company_id")
        if not t:
            continue
        if t == "ANALYZER":
            k = ("an", cid)
            if k in seen:
                res[n["id"]] = (t, "superseded by a newer analyzer card")
            seen.add(k)
        elif t == "PREVIEW PIPELINE":
            k = ("pp", cid)
            if k in seen:
                res[n["id"]] = (t, "older preview-pipeline card")
            seen.add(k)
        elif t == "STAGE":
            board = body.split(":", 2)[1] if body.count(":") >= 2 else ""
            k = ("st", cid, board)
            if k in seen:
                res[n["id"]] = (t, f"older stage card ({board})")
            seen.add(k)
        elif t == "PIPELINE ALERT":
            if n.get("author") != "pipeline_watchdog" and age(n) > FOREIGN_ALERT_DAYS:
                res[n["id"]] = (t, f"alert older than {FOREIGN_ALERT_DAYS}d")
        elif t in ("CLIENT EMAIL", "MONICA-ACK"):
            if age(n) > TTL_DAYS[t]:
                res[n["id"]] = (t, f"older than {TTL_DAYS[t]}d")
        elif t == "DEV":
            k = ("dev", cid, "ripple" if "[SERVICE RIPPLE] custom pages needed" in body
                 else _norm(body[:200]))
            if k in seen:
                res[n["id"]] = (t, "duplicate [DEV] card")
            seen.add(k)
        elif t in ("TODO-SANTINO", "TODO-PROPOSED"):
            if age(n) > TTL_DAYS[t]:
                res[n["id"]] = (t, f"older than {TTL_DAYS[t]}d")
                continue
            rest = body.split("]", 1)[1].strip()
            if rest.startswith("Review: dev agent finished"):
                if age(n) > REVIEW_ROW_DAYS:
                    res[n["id"]] = (t, "dev agent finished it; review window passed")
                continue
            if rest.startswith("Dev agent NEEDS INPUT:"):
                reason = rest[len("Dev agent NEEDS INPUT:"):].split("(task was:")[0]
                if _NOOP_START.search(reason) or _NOOP_ANY.search(reason[:300]):
                    res[n["id"]] = (t, "handback says already done / no action")
                    continue
                m = re.search(r"\(task was: (.*?)\)", rest)
                k = ("ni", cid, _norm(m.group(1)) if m else _norm(reason[:160]))
            else:
                k = (t, cid, _norm(rest[:160]))
            if k in seen:
                res[n["id"]] = (t, "near-identical duplicate of a newer note")
            seen.add(k)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    notes = fetch_open()
    res = plan(notes, now)
    by_tag = Counter(t for t, _ in res.values())
    print(f"ops note expire: {len(notes)} open, {len(res)} to resolve "
          + (", ".join(f"{t}={c}" for t, c in by_tag.most_common()) or ""))
    if a.dry_run or not res:
        return 0
    ids = list(res)
    stamp = now.isoformat().replace("+00:00", "Z")
    for i in range(0, len(ids), 100):
        chunk = ",".join(ids[i:i + 100])
        _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=in.({chunk})&status=eq.open",
            {"status": "resolved", "resolved_at": stamp})
    try:
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": "ops-note-expire", "v": {"at": stamp, "resolved": len(res),
                                           "by_tag": dict(by_tag)}},
            prefer="resolution=merge-duplicates")
    except Exception as e:  # noqa: BLE001 - the stamp is informational
        print(f"  (kv stamp failed: {str(e)[:80]})")
    print(f"ops note expire: resolved {len(res)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
