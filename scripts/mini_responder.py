#!/usr/bin/env python3
"""mini_responder.py — answer the Mac Mini's structured Needs automatically.

Santino 2026-09-27: the Mini parks tasks and asks for inputs; waiting for a
human session to answer them stalls work for hours. This runs in GitHub
Actions the moment the Mini pushes clients/_ops/mini-needs.md (plus a
3x/day backstop), fulfills the MECHANICAL, allowlisted request types with
verified data, commits the answers, and fires the Mini's trigger so its
next 5-minute poll picks the work back up. Judgment calls go to Santino's
ops attention feed. Deterministic — no LLM, never sends to clients, never
edits the Mini's standing orders.

Need line format (the Mini writes these; see docs/MINI-OPERATOR.md):
  - [ ] NEED-<id> | type=<type> | client=<slug> | <key=value ...> | for=<task>

Types:
  fetch-doc    path=<branding bucket path>  -> file committed to
                                               clients/<slug>/docs/<name>
  dba-name     (none)                       -> filed DBA string, verbatim
  company-nap  (none)                       -> name/address/phone/website
  human        question=<text>              -> routed to Santino (ops note)
Anything else is treated as `human`.

Line state after handling: [x] fulfilled (answer appended after ->),
[~] routed to Santino, [!] failed (reason after ->).
"""
from __future__ import annotations

import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")
import os  # noqa: E402

import requests  # noqa: E402

from client_ops_sync import _sb, slug_map  # noqa: E402

NEEDS = ROOT / "clients" / "_ops" / "mini-needs.md"
LOG = ROOT / "clients" / "_ops" / "mini-responder-log.md"
TRIGGER = ROOT / "clients" / "_ops" / "mini-trigger"
LINE_RE = re.compile(r"^- \[ \] (NEED-[\w-]+)\s*\|(.*)$")


def _fields(rest: str) -> dict:
    out = {}
    for part in rest.split("|"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _cid(slug: str) -> str | None:
    return next((c for c, s in slug_map().items() if s == slug), None)


def _company(cid: str) -> dict:
    rows = _sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=name,phone,"
               "address,city,state,postal_code,website,integration_settings") or []
    return rows[0] if rows else {}


def fulfill(ntype: str, f: dict) -> tuple[str, str]:
    """-> (state, answer). state in x / ~ / !"""
    slug = f.get("client", "")
    cid = _cid(slug) if slug else None
    if ntype == "fetch-doc":
        path = f.get("path", "").removeprefix("branding/")
        if not (cid and path.startswith(cid + "/")):
            return "!", "path must be branding/<this client's company id>/..."
        sb = os.environ["SUPABASE_URL"].rstrip("/")
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        r = requests.get(f"{sb}/storage/v1/object/branding/"
                         f"{urllib.parse.quote(path)}",
                         headers={"apikey": key, "Authorization": f"Bearer {key}"},
                         timeout=60)
        if r.status_code != 200:
            return "!", f"not found in bucket ({r.status_code})"
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", path.rsplit("/", 1)[-1])
        dest = ROOT / "clients" / slug / "docs" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return "x", f"repo:{dest.relative_to(ROOT)}"
    if ntype == "dba-name":
        if not cid:
            return "!", "unknown client slug"
        ints = _company(cid).get("integration_settings") or {}
        ri = ints.get("rename_intent") or {}
        if not (ri.get("dba_filed") and ri.get("dba_name")):
            return "~", "DBA not filed/verified yet — routed to Claude"
        chosen = _sb("GET", "/rest/v1/marketing_gbp_suggestions?company_id=eq."
                     f"{cid}&item_type=eq.name&status=eq.chosen&select=item") or []
        name = chosen[0]["item"] if chosen else ri["dba_name"]
        return "x", f"verbatim: {name} (dba_verified={ri.get('dba_verified')})"
    if ntype == "company-nap":
        if not cid:
            return "!", "unknown client slug"
        c = _company(cid)
        return "x", (f"{c.get('name')} | {c.get('address')}, {c.get('city')}, "
                     f"{c.get('state')} {c.get('postal_code')} | REAL phone "
                     f"{c.get('phone')} | {c.get('website')}")
    return "~", "routed to Claude (judgment call)"


def _route_human(need_id: str, f: dict) -> None:
    body = (f"MINI NEED {need_id} ({f.get('client', '?')}): "
            f"{f.get('question') or f.get('for') or 'see mini-needs.md'} "
            "— routed to the Claude mini-needs agent first.")
    _sb("POST", "/rest/v1/marketing_ops_notes",
        {"company_id": None, "author": "mini-responder", "status": "open",
         "body": body[:900]}, prefer="return=minimal")
    # CLAUDE FIRST (Santino 2026-09-30: "you try to answer. If not, you
    # forward the question to me, then I respond to you, and you give it
    # back to the Mini"). Routed needs are answered by the headless
    # mini-needs agent (scripts/mini_needs_agent.md, next workflow step);
    # only IT texts Santino (scripts/ask_santino.py), never the Mini path.


def apply_santino_answers(lines: list) -> int:
    """Santino's texted answers (ops_kv santino-answers, written by
    client_concierge.handle_boss_reply) -> ANSWER lines under their needs."""
    queue = []
    try:
        rows = _sb("GET", "/rest/v1/ops_kv?k=eq.santino-answers&select=v") or []
        queue = (rows[0].get("v") if rows else None) or []
    except Exception as e:  # noqa: BLE001
        print(f"  santino-answers read failed: {str(e)[:100]}")
    done, left = 0, []
    for q in queue:
        idx = next((i for i, l in enumerate(lines) if l.startswith("- [")
                    and f"{q.get('need')} " in l + " "), None)
        if idx is None:
            left.append(q)
            continue
        lines[idx] = re.sub(r"^- \[.\]", "- [x]", lines[idx], count=1)
        lines.insert(idx + 1, f"  - ANSWER (Santino via text {str(q.get('at'))[:16]}Z, "
                              f"{q.get('code')}): {q.get('answer')}")
        done += 1
    if done:
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": "santino-answers", "v": left,
             "updated_at": datetime.now(timezone.utc).isoformat()},
            prefer="resolution=merge-duplicates,return=minimal")
    return done


def main() -> int:
    if not NEEDS.exists():
        print("mini-responder: no needs file")
        return 0
    lines = NEEDS.read_text().splitlines()
    changed, fulfilled, routed = False, 0, 0
    log = []
    for i, line in enumerate(lines):
        m = LINE_RE.match(line)
        if not m:
            continue
        need_id, rest = m.group(1), m.group(2)
        f = _fields(rest)
        ntype = f.get("type", "human")
        try:
            state, ans = fulfill(ntype, f)
        except Exception as e:  # noqa: BLE001 — one need never kills the run
            state, ans = "!", f"error: {str(e)[:120]}"
        if state == "~":
            _route_human(need_id, f)
            routed += 1
        elif state == "x":
            fulfilled += 1
        lines[i] = line.replace("- [ ]", f"- [{state}]", 1) + f" -> {ans}"
        changed = True
        log.append(f"{need_id} [{state}] {ntype} {f.get('client', '')}: {ans[:140]}")
    texted = apply_santino_answers(lines)
    if texted:
        changed = True
        fulfilled += texted
        log.append(f"{texted} answer(s) from Santino by text written back")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if not changed:
        print("mini-responder: no open needs")
        return 0
    NEEDS.write_text("\n".join(lines) + "\n")
    with LOG.open("a") as fh:
        fh.write(f"\n## {stamp} — {fulfilled} fulfilled, {routed} routed\n")
        fh.writelines(f"- {l}\n" for l in log)
    if fulfilled:
        TRIGGER.write_text(f"responder-{int(time.time())}\n")
    print(f"mini-responder: {fulfilled} fulfilled, {routed} routed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
