#!/usr/bin/env python3
"""rename_evidence.py — find WHERE the client approved their profile rename.

Santino 2026-09-30: marking a name "chosen" in the app is the approval, and
the system (not a person) should attach the proof: the Fathom call moment,
a GoHighLevel phone call (downloaded + transcribed), or a text/email where
the client said yes. Stored on the single rename record:

  companies.integration_settings.rename_intent.approval = {
    "status": "found" | "not_found",
    "via": "fathom" | "ghl_call" | "message",
    "url", "quote", "at", "source_id", "name", "checked_at", "found_by"}

Runs for every client with a CHOSEN name and no approval yet (or a
not_found older than 7 days): after rename_pipeline.py in call-intel.yml
(every 30 min; cheap once found). Transcripts of GHL calls are cached in
ops_kv call-transcript:{message_id} so a call is transcribed once.

Usage:
  python3 scripts/rename_evidence.py [--slug X] [--days 60] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import requests  # noqa: E402
import client_concierge as cc  # noqa: E402
from client_ops_sync import slug_map  # noqa: E402

GHL = "https://services.leadconnectorhq.com"
KEYWORDS = re.compile(r"\b(name|rename|renam|dba|d\.b\.a|trade name|fictitious|business profile|"
                      r"google (?:profile|listing)|title)\b", re.I)
MAX_CALLS = 6            # GHL calls transcribed per client per pass
MIN_CALL_S = 60
_MEETS: dict | None = None
FORCE = False

JUDGE = """You check whether a business owner APPROVED renaming their Google
Business Profile to a specific new name. You get the chosen name and excerpts
from calls and messages (newest first). Approval = the client clearly agreed
to that name (or a version with only trivial differences in capitalization,
"&" vs "and", punctuation), or agreed to the rename and then confirmed that
exact name. ALSO approval: the client agreed to the rename (on a call or in
writing), we (US) then sent the exact name, and the client acknowledged it
or asked for / proceeded with filing it (e.g. "Need the exact name for the
DBA please" followed by our exact name and their "Thank you"). Quote the
CLIENT's words, never ours, and the quote itself must show agreement to the
rename or the name (or asking to file it); a bare "thanks"/"ty"/"awesome"
alone is NOT enough, prefer the call or message where they actually said yes. Polite filler ("No worries!", "ok thanks") about
something else is NOT approval. Reply with ONLY JSON:
{"approved": true|false, "source_id": "<id of the excerpt>", "quote": "<the
client's own words, verbatim, max 240 chars>", "at": "<timestamp of that
excerpt>", "why": "<one short sentence>"}"""


def _ghl(method: str, path: str, **kw):
    return requests.request(method, GHL + path, timeout=120, headers={
        "Authorization": f"Bearer {os.environ['GHL_API_KEY']}", "Version": "2021-07-28"}, **kw)


STRONG = re.compile(r"\b(dba|d\.b\.a|rename|renaming|trade name|fictitious|business name|"
                    r"profile name|name change|change the name|new name|file (?:it|the name)|"
                    r"24/7)\b", re.I)


def _windows(text: str, width: int = 900, cap: int = 14000) -> str:
    """Rename talk first: windows around STRONG rename words, then the weaker
    'name/profile' words, merged and capped, so the judge reads the rename
    conversation, not the photo review (DryCor 09-15 lesson)."""
    spans = []
    for rx in (STRONG, KEYWORDS):
        for m in rx.finditer(text):
            spans.append((max(0, m.start() - width), min(len(text), m.end() + width), rx is STRONG))
    spans.sort(key=lambda x: (not x[2], x[0]))
    picked, total = [], 0
    for a, b, _ in spans:
        if any(a < pb and b > pa for pa, pb in picked):
            continue
        picked.append((a, b))
        total += b - a
        if total > cap:
            break
    picked.sort()
    return " ... ".join(text[a:b] for a, b in picked)


def fathom_excerpts(slug: str, since: datetime) -> list[dict]:
    import fathom_sync as fs
    st = cc.kv_get("fathom-sync-state") or {}
    rids = [rid for rid, s in (st.get("processed") or {}).items() if s == slug]
    global _MEETS
    if _MEETS is None:   # one fetch per pass, shared by every client
        _MEETS = {str(m.get("recording_id")): m for m in fs.fathom_meetings(
            limit=50, since=since.strftime("%Y-%m-%dT%H:%M:%SZ"))}
    meets = _MEETS
    out = []
    for rid in rids:
        m = meets.get(str(rid))
        if not m:
            continue
        try:
            segs = fs.fathom_transcript(rid, api_key=m.get("_api_key"))
        except Exception:  # noqa: BLE001
            continue
        text = "\n".join(f"{(s.get('speaker') or {}).get('display_name', '?')}: {s.get('text', '')}"
                         for s in segs)
        w = _windows(text)
        if w:
            out.append({"id": f"fathom:{rid}", "via": "fathom",
                        "url": m.get("share_url") or m.get("url") or f"https://fathom.video/calls/{rid}",
                        "at": fs.meeting_when(m), "text": w})
    return out


def _transcribe(audio: bytes) -> str:
    import call_intel
    with tempfile.TemporaryDirectory() as td:
        src, dst = os.path.join(td, "in.bin"), os.path.join(td, "out.mp3")
        open(src, "wb").write(audio)
        try:   # GHL WAVs run 30MB+; Whisper caps uploads at 25MB
            subprocess.run(["ffmpeg", "-v", "quiet", "-i", src, "-ac", "1", "-ar", "16000",
                            "-b:a", "32k", dst], check=True, timeout=180)
            audio = open(dst, "rb").read()
        except Exception:  # noqa: BLE001
            pass
    return (call_intel._whisper(audio).get("text") or "").strip()


def ghl_excerpts(contact_ids: list[str], since: datetime, dry: bool) -> list[dict]:
    loc = os.environ["GHL_LOCATION_ID"]
    out, calls = [], 0
    for cid in contact_ids:
        r = _ghl("GET", "/conversations/search", params={"locationId": loc, "contactId": cid})
        for conv in (r.json().get("conversations") or []) if r.ok else []:
            mr = _ghl("GET", f"/conversations/{conv['id']}/messages", params={"limit": 100})
            msgs = ((mr.json().get("messages") or {}).get("messages") or []) if mr.ok else []
            for m in msgs:
                at = m.get("dateAdded") or ""
                if at[:19] < since.strftime("%Y-%m-%dT%H:%M:%S"):
                    continue
                mt = m.get("messageType") or ""
                if mt == "TYPE_CALL" and calls < MAX_CALLS:
                    dur = int(((m.get("meta") or {}).get("call") or {}).get("duration") or 0)
                    if dur and dur < MIN_CALL_S:
                        continue
                    key = f"call-transcript:{m['id']}"
                    text = cc.kv_get(key)
                    if text is None and not dry:
                        a = _ghl("GET", f"/conversations/messages/{m['id']}/locations/{loc}/recording")
                        if a.ok and len(a.content) > 20_000:
                            calls += 1
                            try:
                                text = _transcribe(a.content)
                            except Exception as e:  # noqa: BLE001
                                print(f"  transcribe failed {m['id']}: {str(e)[:80]}")
                                text = ""
                            cc.kv_set(key, text)
                    w = _windows(text or "")
                    if w:
                        out.append({"id": f"ghl_call:{m['id']}", "via": "ghl_call", "at": at,
                                    "url": f"https://app.gohighlevel.com/v2/location/{loc}/conversations/conversations/{conv['id']}",
                                    "text": w})
                elif mt in ("TYPE_SMS", "TYPE_EMAIL"):
                    body = (m.get("body") or "").strip()
                    if not body and mt == "TYPE_EMAIL":   # email text lives on the email object
                        ids = ((m.get("meta") or {}).get("email") or {}).get("messageIds") or []
                        if ids:
                            er = _ghl("GET", f"/conversations/messages/email/{ids[-1]}")
                            em = (er.json().get("emailMessage") or {}) if er.ok else {}
                            body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", em.get("body") or "")).strip()
                            body = re.split(r"\bOn .{5,80} wrote:|-----Original Message", body)[0]
                    inbound = m.get("direction") == "inbound"
                    # our OUTBOUND lines only when they carry the rename (the
                    # "here is the exact name" message the client answers)
                    if body and (inbound or STRONG.search(body)):
                        out.append({"id": f"message:{m['id']}", "via": "message", "at": at,
                                    "who": "CLIENT" if inbound else "US (agency)",
                                    "url": f"https://app.gohighlevel.com/v2/location/{loc}/conversations/conversations/{conv['id']}",
                                    "text": body[:900]})
    return out


def check(cid: str, slug: str, days: int, dry: bool) -> dict | None:
    co = (cc._sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=name,integration_settings") or [{}])[0]
    ints = co.get("integration_settings") or {}
    ri = dict(ints.get("rename_intent") or {})
    if (ri.get("decision") or "") == "keep":
        return None
    chosen = cc._sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
                    "&item_type=eq.name&status=eq.chosen&select=item") or []
    if not chosen:
        return None
    name = chosen[0]["item"]
    ap = ri.get("approval") or {}
    if ap.get("status") == "found" and ap.get("name") == name and not FORCE:
        return None
    if ap.get("status") == "not_found" and ap.get("name") == name and \
            (ap.get("checked_at") or "") > (datetime.now(timezone.utc) - timedelta(days=7)).isoformat():
        return None
    # The strongest proof there is: the client FILED this exact name with the
    # state (document on file). Checked before any call/message search.
    norm = lambda x: re.sub(r"[^a-z0-9]+", " ", str(x).lower().replace("&", " and ")).strip()  # noqa: E731
    if ri.get("dba_doc_url") and ri.get("dba_name") and norm(ri["dba_name"]) == norm(name):
        result = {"status": "found", "via": "dba_filing", "name": name, "url": ri["dba_doc_url"],
                  "quote": f"Client filed this exact name as their DBA ({ri.get('dba_registration') or 'filing on file'})",
                  "at": ri.get("dba_filed_at"), "checked_at": datetime.now(timezone.utc).isoformat(),
                  "found_by": "rename_evidence"}
        print(f"{slug}: found dba_filing")
        if not dry:
            ri["approval"] = result
            ints["rename_intent"] = ri
            cc._sb("PATCH", f"/rest/v1/companies?id=eq.{cid}", {"integration_settings": ints},
                   prefer="return=minimal")
        return result
    since = datetime.now(timezone.utc) - timedelta(days=days)
    contacts = {c.get("ghl_contact_id") for c in (ints.get("contacts") or []) if c.get("ghl_contact_id")}
    if ints.get("ghl_contact_id"):
        contacts.add(ints["ghl_contact_id"])
    ex = fathom_excerpts(slug, since) + ghl_excerpts(sorted(contacts), since, dry)
    ex.sort(key=lambda e: e.get("at") or "", reverse=True)
    now = datetime.now(timezone.utc).isoformat()
    result = {"status": "not_found", "name": name, "checked_at": now, "found_by": "rename_evidence"}
    if ex:
        payload = "\n\n".join(f"[{e['id']} | {e['via']}{' | ' + e['who'] if e.get('who') else ''} | {e['at']}]\n{e['text']}"
                                for e in ex[:60])
        v = cc.anthropic_json(JUDGE, f"CHOSEN NAME: {name}\n\nEXCERPTS:\n{payload[:60000]}",
                              max_tokens=600)
        if v.get("approved"):
            src = next((e for e in ex if e["id"] == v.get("source_id")), None)
            result.update({"status": "found", "via": (src or {}).get("via"),
                           "url": (src or {}).get("url"), "source_id": v.get("source_id"),
                           "quote": (v.get("quote") or "")[:240], "at": v.get("at") or (src or {}).get("at"),
                           "why": v.get("why")})
    print(f"{slug}: {result['status']} {result.get('via') or ''} {result.get('quote', '')[:80]!r}")
    if not dry:
        ri["approval"] = result
        ints["rename_intent"] = ri
        cc._sb("PATCH", f"/rest/v1/companies?id=eq.{cid}", {"integration_settings": ints},
               prefer="return=minimal")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-check even when evidence exists")
    a = ap.parse_args()
    global FORCE
    FORCE = a.force
    cc.load_env()
    sm = slug_map()
    targets = [(c, s) for c, s in sm.items() if not a.slug or s == a.slug]
    for cid, slug in targets:
        try:
            check(cid, slug, a.days, a.dry_run)
        except Exception as e:  # noqa: BLE001 — one client never stops the pass
            print(f"{slug}: ERROR {str(e)[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
