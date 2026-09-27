#!/usr/bin/env python3
"""meeting_debrief.py — the post-meeting watcher (Santino 2026-08-29).

After every Fathom-recorded meeting with a KNOWN client, read the whole
call, extract what was actually promised or decided, and file each item
straight into the existing ops lanes — no approval step, per Santino:
  - "[FOR MONICA] ..."   client-facing asks / follow-ups Monica delivers
  - "[DEV] ..."          site/build changes for the nightly dev agent
  - "[TODO-SANTINO] ..." things only Santino can do
plus one "[MEETING-DEBRIEF]" recap note per meeting so Reports shows the
work. Every filed item quotes the moment it came from, so nothing is
invented (unquotable = not filed).

Client matching is deliberately conservative: the meeting must match an
ACTIVE company by attendee email, attendee phone, or company-name-in-title.
Unmatched meetings are skipped and listed, never guessed.

State: ops_kv key 'meeting_debrief_cursor' (ISO timestamp of newest
processed meeting). Idempotent: a meeting is processed once.

Usage:
  python3 scripts/meeting_debrief.py --dry-run     # show what would file
  python3 scripts/meeting_debrief.py               # file for real
  python3 scripts/meeting_debrief.py --meeting-url https://fathom.video/calls/X  # one meeting
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
FATHOM = os.environ.get("FATHOM_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-5"
CURSOR_KEY = "meeting_debrief_cursor"


def sb(method: str, path: str, body=None, prefer=None):
    headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
               "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    r = requests.request(method, f"{SB_URL}/rest/v1/{path}",
                         headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json() if r.text else None


def get_cursor() -> str | None:
    try:
        rows = sb("GET", f"ops_kv?k=eq.{CURSOR_KEY}&select=v")
        return (rows[0]["v"] or {}).get("ts") if rows else None
    except Exception:  # noqa: BLE001
        return None


def set_cursor(ts: str) -> None:
    sb("POST", "ops_kv?on_conflict=k", {"k": CURSOR_KEY, "v": {"ts": ts}},
       prefer="resolution=merge-duplicates,return=minimal")


def fathom_get(path: str, params: dict | None = None) -> dict:
    r = requests.get(f"https://api.fathom.ai/external/v1/{path}",
                     headers={"X-Api-Key": FATHOM}, params=params or {},
                     timeout=60)
    r.raise_for_status()
    return r.json()


_OUR_DOMAINS = ("restorationai.io", "getrestorationai.com")
_OUR_COMPANY_RE = re.compile(r"^\s*(test\b|rank\s*ai\b|restoration\s*ai\b)", re.I)


def load_client_index():
    """(emails, phones, names) -> company_id for ACTIVE companies only.

    Our OWN identities are excluded — the first dry-run matched every
    meeting to the internal "Test (Rank AI)" company because Santino is an
    invitee on all of them. Prospects with no client row simply don't match
    (by design: confirmed clients only)."""
    companies = sb("GET", "companies?status=ilike.active&select=id,name,email,phone")
    companies = [c for c in companies
                 if not _OUR_COMPANY_RE.match(c.get("name") or "")]
    by_email, by_phone, names = {}, {}, []
    for c in companies:
        em = (c.get("email") or "").strip().lower()
        if em and not em.endswith(_OUR_DOMAINS):
            by_email[em] = c["id"]
        digits = re.sub(r"\D", "", c.get("phone") or "")[-10:]
        if digits:
            by_phone[digits] = c["id"]
        names.append((c["name"].strip().lower(), c["id"], c["name"].strip()))
    # clients/*.json contact names — meetings are often titled with the
    # PERSON ("Rob Carpenter - Kick Off Call"), the client joins by link so
    # no invitee email exists, and the company name never appears (TDI
    # 2026-08-31). Full contact names become title-match candidates too.
    try:
        cmap = json.loads((Path(__file__).resolve().parent.parent
                           / "clients" / "company_map.json").read_text())
        for slug, cid in cmap.items():
            if cid not in {c["id"] for c in companies}:
                continue
            try:
                cj = json.loads((Path(__file__).resolve().parent.parent
                                 / "clients" / f"{slug}.json").read_text())
                nm = ((cj.get("contact") or {}).get("name") or "").strip()
                if len(nm) > 6:
                    names.append((nm.lower(), cid, nm))
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    # contacts carry the humans (owners, office managers)
    contacts = sb("GET", "contacts?select=client_id,email,phone&limit=5000")
    active_ids = {c["id"] for c in companies}
    for ct in contacts:
        cid = ct.get("client_id")
        if cid not in active_ids:
            continue
        cem = (ct.get("email") or "").strip().lower()
        if cem and not cem.endswith(_OUR_DOMAINS):
            by_email.setdefault(cem, cid)
        digits = re.sub(r"\D", "", ct.get("phone") or "")[-10:]
        if digits:
            by_phone.setdefault(digits, cid)
    return by_email, by_phone, names


def match_company(meeting: dict, by_email, by_phone, names) -> str | None:
    for inv in (meeting.get("calendar_invitees") or meeting.get("invitees") or []):
        em = (inv.get("email") or "").strip().lower() if isinstance(inv, dict) else str(inv).lower()
        if em and em in by_email:
            return by_email[em]
    title = (meeting.get("title") or meeting.get("meeting_title") or "").lower()
    for lowname, cid, _ in names:
        if len(lowname) > 6 and lowname in title:
            return cid
    return None


def transcript_text(meeting: dict) -> str:
    t = meeting.get("transcript")
    if isinstance(t, list):
        return "\n".join(
            f"{(s.get('speaker') or {}).get('display_name', '?')}: {s.get('text', '')}"
            if isinstance(s.get("speaker"), dict) else f"{s.get('speaker', '?')}: {s.get('text', '')}"
            for s in t)
    if isinstance(t, str):
        return t
    return ""


def extract_items(company_name: str, tx: str) -> list[dict]:
    system = (
        "You are the post-meeting debrief agent for Rank AI, a restoration-"
        "industry marketing agency. From this call transcript with client "
        f"{company_name}, extract ONLY commitments and decisions that were "
        "explicitly made on the call. Reply with one JSON object: "
        '{"items": [{"lane": "monica"|"dev"|"santino", "body": "...", '
        '"quote": "verbatim words from the call that back this item"}]}. '
        "Lanes: monica = a message/ask/follow-up to send the CLIENT (missing "
        "materials, confirmations, reminders about things THEY owe). dev = a "
        "website or build change WE promised. santino = something only the "
        "agency owner can do (calls, billing, account access, strategy). "
        "Rules: an item without a supporting verbatim quote must be omitted; "
        "never invent commitments; skip pleasantries and things already "
        "completed during the call itself; 6 items maximum, fewer is better.")
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=180, headers={
        "x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"},
        json={"model": MODEL, "max_tokens": 4000, "system": system,
              "messages": [{"role": "user", "content": tx[:180000]}]})
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json().get("content", [])
                   if b.get("type") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    items = json.loads(m.group(0)).get("items", []) if m else []
    return [i for i in items
            if i.get("lane") in ("monica", "dev", "santino")
            and i.get("body") and i.get("quote")]


LANE_TAG = {"monica": "[FOR MONICA]", "dev": "[DEV]", "santino": "[TODO-SANTINO]"}


def file_items(cid: str, meeting: dict, items: list[dict], dry: bool) -> None:
    url = meeting.get("url") or meeting.get("share_url") or ""
    when = (meeting.get("created_at") or meeting.get("started_at") or "")[:10]
    for it in items:
        body = (f"{LANE_TAG[it['lane']]} {it['body'].strip()}\n"
                f"(from the {when} call{f' — {url}' if url else ''}; "
                f"they said: \"{it['quote'][:180]}\")")
        if dry:
            print(f"    would file -> {body[:160]}")
        else:
            sb("POST", "marketing_ops_notes",
               {"company_id": cid, "body": body, "status": "open"},
               prefer="return=minimal")
    recap = (f"[MEETING-DEBRIEF] {when} call processed"
             f"{f' ({url})' if url else ''}: {len(items)} action item(s) filed "
             "automatically to their lanes.")
    if dry:
        print(f"    would file -> {recap}")
    else:
        sb("POST", "marketing_ops_notes",
           {"company_id": cid, "body": recap, "status": "resolved"},
           prefer="return=minimal")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--meeting-url", help="process just this fathom.video/calls/... url")
    args = ap.parse_args()
    if not (FATHOM and SB_URL and SB_KEY and ANTHROPIC_KEY):
        print("missing FATHOM_API_KEY / SUPABASE / ANTHROPIC env")
        return 1

    cursor = get_cursor()
    params = {"include_transcript": "true", "limit": 20}
    if args.meeting_url:
        pass  # filter below
    elif cursor:
        params["created_after"] = cursor
    else:
        # FIRST RUN: never trawl history — auto-filing [FOR MONICA] items for
        # weeks-old calls would have Monica messaging clients about stale
        # promises. Start from the last 36 hours only.
        from datetime import datetime, timedelta, timezone
        params["created_after"] = (datetime.now(timezone.utc)
                                   - timedelta(hours=36)).isoformat()
    data = fathom_get("meetings", params)
    meetings = data.get("items", [])
    if args.meeting_url:
        meetings = [m for m in meetings
                    if args.meeting_url in (m.get("url") or "")]
    if not meetings:
        print("no new meetings")
        return 0

    by_email, by_phone, names = load_client_index()
    newest = cursor or ""
    for m in sorted(meetings, key=lambda x: x.get("created_at") or ""):
        title = m.get("title") or m.get("meeting_title") or "?"
        created = m.get("created_at") or ""
        newest = max(newest, created)
        cid = match_company(m, by_email, by_phone, names)
        if not cid:
            print(f"  skip (no client match): {title} {created[:16]}")
            continue
        tx = transcript_text(m)
        if len(tx) < 400:
            print(f"  skip (no transcript): {title}")
            continue
        comp = sb("GET", f"companies?id=eq.{cid}&select=name")[0]["name"].strip()
        print(f"== {comp}: {title} {created[:16]}")
        try:
            items = extract_items(comp, tx)
        except Exception as e:  # noqa: BLE001
            print(f"    extraction failed: {str(e)[:120]}")
            continue
        file_items(cid, m, items, args.dry_run)
        print(f"    {len(items)} item(s) {'(dry-run)' if args.dry_run else 'filed'}")
    if not args.dry_run and newest:
        set_cursor(newest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
