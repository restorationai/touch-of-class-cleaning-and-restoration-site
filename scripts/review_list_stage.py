#!/usr/bin/env python3
"""review_list_stage.py — auto-stage uploaded customer lists (B1) + seed
review-readiness asks (B2). Santino 2026-09-20: "I always have to go to the
files, download it, and then upload it, and then stage it" — three lists were
sitting unloaded (HomeLyft's since Aug 24) behind a Monica message that said
"we're loading it in".

Hourly on the ops-worker. For every pinned "Customer list uploaded" plan row
still status=planned:

  1. Run review_enroll.py --staged --file storage:<target> — the proven
     loader (column auto-detect, phone normalization, dedupe, contacts
     upsert). STAGED rows are invisible to the dispatcher; the app's
     existing "Activate Review Campaign" button flips them live. Nothing
     here ever sends or schedules a send.
  2. Success -> pin status 'done' + a staged-count note in the rationale;
     the reviews board card flips from "list uploaded, not loaded" to
     "N staged (parked)" off the rows themselves.
  3. Unparseable (PDF, no phone column) -> pin stays planned and ONE
     ops-attention note is filed (deduped via ops_kv) so a human converts
     the file — never silent, never garbage-loaded.

B2 (same sweep, list presence = the trigger): a client with a list on file
but no approved sender gets the SPECIFIC missing-info ask seeded as a
client_input plan row for Monica — today that is the EIN + legal name that
toll-free/A2P verification needs (FIX). Deduped by action_key; the ask
retires through the normal answered-flow once the info lands.

CLI: python3 scripts/review_list_stage.py [--dry-run] [--company CO-...]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from client_ops_sync import _sb, slug_map  # noqa: E402

PARSEABLE = {".csv", ".xlsx", ".xls", ".txt", ".tsv"}
_NOTE_KV = "review-list-stage-notes"   # {pin_target_hash: iso} dedupe


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _note_once(cid: str, key: str, body: str, dry: bool) -> None:
    import hashlib
    h = hashlib.sha1(key.encode()).hexdigest()[:16]
    seen = ((_sb("GET", f"/rest/v1/ops_kv?k=eq.{_NOTE_KV}&select=v")
             or [{}])[0].get("v") or {})
    if h in seen:
        return
    if not dry:
        _sb("POST", "/rest/v1/marketing_ops_notes",
            {"company_id": cid, "status": "open",
             "author": "review_list_stage", "body": body},
            prefer="return=minimal")
        seen[h] = _now()
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": _NOTE_KV, "v": seen}, prefer="resolution=merge-duplicates")
    print(f"    note filed: {body[:100]}")


def stage_pins(dry: bool, only_cid: str | None) -> None:
    smap = slug_map()
    pins = _sb("GET", "/rest/v1/marketing_action_plan?pinned=eq.true"
               "&status=eq.planned&title=ilike.Customer%20list%20uploaded*"
               "&select=id,company_id,target,rationale",
               prefer="return=representation") or []
    if only_cid:
        pins = [p for p in pins if p["company_id"] == only_cid]
    print(f"review-list-stage: {len(pins)} unprocessed pin(s)")
    for p in pins:
        cid = p["company_id"]
        slug = smap.get(cid)
        target = str(p.get("target") or "")
        if not slug:
            print(f"  {cid}: no slug mapping — skipped")
            continue
        if not target.startswith("branding/"):
            print(f"  {slug}: target not in branding storage ({target[:60]})")
            continue
        obj = target[len("branding/"):]
        ext = Path(obj).suffix.lower()
        print(f"  {slug}: {Path(obj).name}")
        if ext not in PARSEABLE:
            _note_once(cid, f"unparseable:{target}",
                       f"[REVIEW LIST] {slug}: uploaded customer list "
                       f"'{Path(obj).name}' is {ext or 'extension-less'} — "
                       "auto-staging can't parse it. Convert to CSV/XLSX and "
                       "re-upload, or load by hand (review_enroll.py).", dry)
            continue
        if dry:
            print("    [dry-run] would run review_enroll --staged")
            continue
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "review_enroll.py"),
             "--slug", slug, "--file", f"storage:{obj}", "--staged"],
            capture_output=True, text=True, timeout=900)
        tail = "\n".join((r.stdout or "").strip().splitlines()[-4:])
        if r.returncode == 0:
            staged_line = next((ln for ln in (r.stdout or "").splitlines()
                                if "STAGED" in ln or "Nothing to enroll" in ln),
                               "staged")
            _sb("PATCH", f"/rest/v1/marketing_action_plan?id=eq.{p['id']}",
                {"status": "done",
                 "rationale": (str(p.get("rationale") or "")[:600]
                               + f"\n\nAUTO-STAGED {_now()[:10]}: "
                               + staged_line.strip()[:200])})
            print(f"    staged OK: {staged_line.strip()[:120]}")
            try:
                from work_log import work_log
                work_log(cid, "reviews", "list-staged",
                         "Customer list loaded into the review campaign as "
                         "staged contacts — nothing sends until the campaign "
                         "is activated.",
                         evidence={"file": Path(obj).name,
                                   "result": staged_line.strip()[:200]},
                         source="review_list_stage.py")
            except Exception:  # noqa: BLE001
                pass
        else:
            err_lines = (r.stderr or r.stdout or "").strip().splitlines()
            err = err_lines[-1] if err_lines else "unknown"
            if "no phone column" in err.lower():
                # The client's export lacks phone numbers (FIX 2026-09-20:
                # names + emails only). The review engine texts, so the
                # right move is asking THEM for a re-export — a specific
                # Monica ask, not a silent ops note.
                ak = f"review-list-phones-{slug}"
                dup = _sb("GET", "/rest/v1/marketing_action_plan"
                          f"?company_id=eq.{cid}&action_key=eq.{ak}"
                          "&select=id&limit=1",
                          prefer="return=representation") or []
                if not dup:
                    _sb("POST", "/rest/v1/marketing_action_plan", [{
                        "company_id": cid, "rank_ai_slug": slug,
                        "action_key": ak, "action_type": "client_input",
                        "status": "planned", "priority": 2,
                        "impact": "high", "effort": "low",
                        "title": "Customer list needs phone numbers — ask "
                                 "for a re-export that includes them",
                        "rationale": f"Their uploaded list "
                                     f"('{Path(obj).name}') has names and "
                                     "emails but NO phone column, and the "
                                     "review campaign runs on texting. Ask "
                                     "them to re-export the same list with "
                                     "phone numbers included, any format. "
                                     "The upload link they already have "
                                     "works; staging is automatic once it "
                                     "lands."}])
                    print(f"    seeded phone re-export ask for {slug}")
                _note_once(cid, f"nophones:{target}",
                           f"[REVIEW LIST] {slug}: '{Path(obj).name}' has "
                           "no phone column (names/emails only) — Monica "
                           "ask seeded for a re-export with phones.", dry)
            else:
                _note_once(cid, f"failed:{target}",
                           f"[REVIEW LIST] {slug}: auto-staging "
                           f"'{Path(obj).name}' failed: {err[:150]} — load "
                           "by hand (review_enroll.py) or fix the file.",
                           dry)
            print(f"    FAILED: {err[:160]}")


def seed_readiness_asks(dry: bool, only_cid: str | None) -> None:
    """B2: a list on file + no approved sender -> ask for what's missing."""
    smap = slug_map()
    pins = _sb("GET", "/rest/v1/marketing_action_plan?pinned=eq.true"
               "&title=ilike.Customer%20list%20uploaded*"
               "&select=company_id", prefer="return=representation") or []
    cids = sorted({p["company_id"] for p in pins})
    if only_cid:
        cids = [c for c in cids if c == only_cid]
    for cid in cids:
        slug = smap.get(cid) or cid
        ph = (_sb("GET", f"/rest/v1/company_phone_setup?id=eq.{cid}"
                  "&select=agent_phone_1,compliance_status,business_ein"
                  "&limit=1") or [{}])[0]
        if str(ph.get("compliance_status") or "") == "approved":
            continue  # sender ready — nothing to ask
        missing = []
        if not ph.get("business_ein"):
            missing.append("EIN")
        if not missing:
            continue  # info in hand; provisioning is our side, not an ask
        ak = f"review-sender-info-{slug}"
        dup = _sb("GET", f"/rest/v1/marketing_action_plan?company_id=eq.{cid}"
                  f"&action_key=eq.{ak}&select=id,status&limit=1",
                  prefer="return=representation") or []
        if dup:
            continue
        if dry:
            print(f"  [dry-run] would seed EIN ask for {slug}")
            continue
        _sb("POST", "/rest/v1/marketing_action_plan", [{
            "company_id": cid, "rank_ai_slug": slug, "action_key": ak,
            "action_type": "client_input", "status": "planned",
            "priority": 2, "impact": "high", "effort": "low",
            "title": "Need your EIN and exact legal business name to "
                     "register your review-texting number",
            "rationale": "Their customer list is in and staged, but carrier "
                         "registration for the texting number requires the "
                         "business EIN and the exact legal name as the IRS "
                         "has it (DISS lesson: mismatches get rejected). "
                         "Ask for both; the wizard/records take it from "
                         "there. The campaign cannot send until this "
                         "clears."}])
        print(f"  seeded EIN ask for {slug}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--company")
    a = ap.parse_args()
    stage_pins(a.dry_run, a.company)
    seed_readiness_asks(a.dry_run, a.company)
    return 0


if __name__ == "__main__":
    sys.exit(main())
