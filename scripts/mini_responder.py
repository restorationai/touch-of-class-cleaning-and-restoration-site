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
            return "~", "DBA not filed/verified yet — routed to Santino"
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
    return "~", "routed to Santino (judgment call)"


def _route_human(need_id: str, f: dict) -> None:
    body = (f"MINI NEED {need_id} ({f.get('client', '?')}): "
            f"{f.get('question') or f.get('for') or 'see mini-needs.md'} "
            "— answer in clients/_ops/mini-needs.md or tell Claude.")
    _sb("POST", "/rest/v1/marketing_ops_notes",
        {"company_id": None, "author": "mini-responder", "status": "open",
         "body": body[:900]}, prefer="return=minimal")
    # TEXT SANTINO (2026-09-30): routed needs used to land ONLY as a
    # company-less ops note, which the daily digest never shows, so the
    # Mini's "URGENT before 11:30" sweep question sat unanswered two days
    # while the sweep put tracking numbers on live listings. One SMS per
    # routed need; a failed text never breaks the responder.
    q = re.sub(r"\s+", " ", f.get("question") or f.get("for") or "")
    sms = (f"MINI NEEDS YOU ({f.get('client', '?')}): {q[:420]}"
           + (" ..." if len(q) > 420 else "")
           + " Reply to Claude or answer in mini-needs.md.")
    try:
        from client_concierge import send_message, OPS_PING_CONTACT_ID, OPS_PING_CELL
        send_message({"id": OPS_PING_CONTACT_ID, "phone": OPS_PING_CELL}, "sms", sms[:640])
        print(f"  {need_id}: texted Santino")
    except Exception as e:  # noqa: BLE001
        print(f"  {need_id}: SMS failed: {str(e)[:100]}")


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
