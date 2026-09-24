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


def _seed_photo_ask(cid: str, slug: str, dry: bool) -> None:
    """Image-before-activation ask, now systemic (Santino 2026-09-20,
    HomeLyft: 'is this part of the system already?'). A campaign that is
    otherwise READY (list staged + sender approved) but has no review MMS
    image gets ONE Monica ask: team photo (converts better) or start
    without. Activation stays a human decision either way."""
    img = (_sb("GET", f"/rest/v1/dynamic_images?company_id=eq.{cid}"
               "&category=eq.review&select=base_image_url&limit=1")
           or [{}])[0]
    if str(img.get("base_image_url") or "").strip():
        return  # image already on file
    ak = f"review-photo-{slug}"
    dup = _sb("GET", f"/rest/v1/marketing_action_plan?company_id=eq.{cid}"
              f"&action_key=eq.{ak}&select=id&limit=1",
              prefer="return=representation") or []
    if dup:
        return
    if dry:
        print(f"  [dry-run] would seed review-photo ask for {slug}")
        return
    _sb("POST", "/rest/v1/marketing_action_plan", [{
        "company_id": cid, "rank_ai_slug": slug, "action_key": ak,
        "action_type": "client_input", "status": "planned",
        "priority": 2, "impact": "medium", "effort": "low",
        "title": "Team photo for the review texts, or start without?",
        "rationale": "Their review campaign is otherwise ready (list "
                     "staged, sender approved) but no review MMS image is "
                     "on file. Review texts convert measurably better with "
                     "a real team photo attached (sent on touches 1 and 3 "
                     "with the customer's name overlaid). Ask if they have "
                     "one to send over (their upload link works), or "
                     "whether we should start without it. Their answer "
                     "gates ACTIVATION, which stays a human step."}])
    print(f"  seeded review-photo ask for {slug}")


def _harvest_ein_from_docs(cid: str) -> str | None:
    """Last-resort EIN hunt through the client's uploaded documents
    (Santino 2026-09-20: 'always look through their uploaded files to see
    if any contain an EIN'). PDFs only for now — W9s/COIs carry it in the
    text layer. Best-effort: any failure just returns None."""
    import io
    import os
    import requests as rq
    try:
        import pypdf
    except ImportError:
        return None
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    H = {"apikey": key, "Authorization": f"Bearer {key}"}
    names: list[str] = []
    for prefix in (f"{cid}/docs", f"{cid}/compliance", f"{cid}/uploads"):
        try:
            r = rq.post(f"{url}/storage/v1/object/list/branding",
                        headers=H, json={"prefix": prefix, "limit": 40},
                        timeout=30)
            for o in (r.json() if r.ok else []):
                n = (o or {}).get("name") or ""
                if n.lower().endswith(".pdf"):
                    names.append(f"{prefix}/{n}")
        except Exception:  # noqa: BLE001
            continue
    import re as _re
    for path in names[:10]:
        try:
            f = rq.get(f"{url}/storage/v1/object/branding/{path}",
                       headers=H, timeout=60)
            if not f.ok or len(f.content) > 8_000_000:
                continue
            reader = pypdf.PdfReader(io.BytesIO(f.content))
            text = " ".join((pg.extract_text() or "")
                            for pg in reader.pages[:4])
            m = _re.search(r"\b(\d{2})\s*[-–]\s*(\d{7})\b", text)
            if m:
                ein = f"{m.group(1)}-{m.group(2)}"
                print(f"    EIN harvested from {Path(path).name}: {ein}")
                return ein
        except Exception:  # noqa: BLE001
            continue
    return None


def seed_readiness_asks(dry: bool, only_cid: str | None) -> None:
    """B2: a list on file + no approved sender -> ask ONLY for what we
    genuinely don't hold. Order of truth (Santino 2026-09-20, the DryCor
    lesson — 22 clients had EINs on the companies row that never reached
    the compliance store): company_phone_setup -> companies.ein (the
    Connect tab's store, auto-backfilled here) -> the client's uploaded
    documents (PDF text harvest) -> only then a Monica ask."""
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
            _seed_photo_ask(cid, slug, dry)
            continue  # sender ready — only the image question remains
        missing = []
        if not ph.get("business_ein"):
            co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}"
                      "&select=ein,legal_business_name,name&limit=1")
                  or [{}])[0]
            ein = (co.get("ein") or "").strip() or None
            if not ein and not dry:
                ein = _harvest_ein_from_docs(cid)
                if ein:
                    _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                        {"ein": ein})
            if ein:
                if not dry:
                    _sb("PATCH", f"/rest/v1/company_phone_setup?id=eq.{cid}",
                        {"business_ein": ein,
                         "legal_business_name":
                             (co.get("legal_business_name")
                              or co.get("name") or "").strip()})
                print(f"  {slug}: EIN found on record ({ein[:2]}-***) — "
                      "backfilled, no ask needed")
            else:
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


_PHOTO_ASKED_KV = "review-photo-asked"   # {cid: iso of the DELIVERED ask}


def photo_timeout_sweep(dry: bool, only_cid: str | None) -> None:
    """Santino 2026-09-20: 'if they don't answer the photo question, after
    2 days we just mark their account as no photo and begin their
    campaign.' The clock runs from the DELIVERED ask found in the real
    thread (the FIX reveal lesson: never from row seeding). A client reply
    of any kind stops the clock — a human handles their answer. Activation
    goes through review_enroll --activate-staged, whose sender preflight
    is hard, so an unready sender can never auto-start."""
    open_asks = _sb("GET", "/rest/v1/marketing_action_plan?status=eq.planned"
                    "&action_key=like.review-photo-*"
                    "&select=id,company_id,action_key",
                    prefer="return=representation") or []
    if only_cid:
        open_asks = [a for a in open_asks if a["company_id"] == only_cid]
    if not open_asks:
        return
    import client_concierge as cc
    cc.load_env()
    asked = ((_sb("GET", f"/rest/v1/ops_kv?k=eq.{_PHOTO_ASKED_KV}&select=v")
              or [{}])[0].get("v") or {})
    smap = slug_map()
    changed = False
    for ask in open_asks:
        cid = ask["company_id"]
        slug = smap.get(cid) or cid
        comp = cc.fetch_companies([cid]).get(cid)
        contact = cc.resolve_contact(comp) if comp else None
        if not contact:
            continue
        try:
            hist = cc.fetch_history(contact["id"])
        except Exception:  # noqa: BLE001
            continue
        asked_at = None
        if asked.get(cid):
            asked_at = datetime.fromisoformat(asked[cid])
        else:
            for m in hist:
                b = (m.get("body") or "").lower()
                if (m.get("direction") == "out" and m.get("when")
                        and "photo" in b
                        and ("review" in b or "/hub/" in b
                             or "upload" in b)):
                    asked_at = m["when"]
                    break
            if asked_at:
                asked[cid] = asked_at.isoformat()
                changed = True
        if not asked_at:
            continue  # ask seeded but Monica hasn't delivered it yet
        replied = any(m.get("direction") == "in" and m.get("when")
                      and m["when"] > asked_at for m in hist)
        if replied:
            continue  # their answer is in play — humans own it
        age_d = (datetime.now(timezone.utc) - asked_at).total_seconds() / 86400
        # POLICY v2 (Santino 2026-09-24): 3 quiet days -> ONE follow-up
        # nudge -> 2 more quiet days -> activate without a photo. (v1 was
        # a single 2-day clock straight to activation; HomeLyft's selfie
        # arrived on day 2.5, after the campaign had already auto-started.)
        fu_key = cid + ":fu"
        fu_at = None
        if asked.get(fu_key):
            try:
                fu_at = datetime.fromisoformat(asked[fu_key])
            except (ValueError, TypeError):
                fu_at = None
        if fu_at is None:
            if age_d < 3:
                print(f"  photo-clock {slug}: asked {age_d:.1f}d ago — "
                      "waiting (follow-up at 3d)")
                continue
            print(f"  photo-clock {slug}: {age_d:.1f}d silent — sending the "
                  "one follow-up nudge")
            if not dry:
                try:
                    body = ("Quick nudge on the team photo for your review "
                            "messages, any picture of you or the crew "
                            "works. If we don't hear back in the next "
                            "couple days we'll start your review campaign "
                            "without one so it keeps moving.")
                    cc.send_message(contact, "sms", body, company=comp)
                    asked[fu_key] = datetime.now(timezone.utc).isoformat()
                    changed = True
                except Exception as se:  # noqa: BLE001 — SendBlocked etc.
                    print(f"    follow-up blocked ({str(se)[:90]}) — clock "
                          "holds, retried next sweep")
            continue
        fu_age_d = (datetime.now(timezone.utc) - fu_at).total_seconds() / 86400
        if fu_age_d < 2:
            print(f"  photo-clock {slug}: follow-up {fu_age_d:.1f}d ago — "
                  "waiting (activate at 2d)")
            continue
        print(f"  photo-timeout {slug}: {age_d:.1f}d silent incl. follow-up "
              "— marking no-photo and activating")
        if dry:
            continue
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "review_enroll.py"),
             "--slug", slug, "--activate-staged"],
            capture_output=True, text=True, timeout=600)
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:]
        if r.returncode != 0:
            _note_once(cid, f"photo-timeout-activate:{cid}",
                       f"[REVIEWS] {slug}: 2-day photo silence but "
                       f"auto-activation refused: "
                       f"{tail[0][:140] if tail else '?'} — activate by "
                       "hand once the blocker clears.", dry)
            continue
        co_ints = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}"
                       "&select=integration_settings") or [{}])[0]
        ints = co_ints.get("integration_settings") or {}
        ints["review_photo"] = {"decision": "none",
                                "via": "2-day silence on the photo ask",
                                "at": datetime.now(timezone.utc).isoformat()}
        _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
            {"integration_settings": ints})
        _sb("PATCH", f"/rest/v1/marketing_action_plan?id=eq.{ask['id']}",
            {"status": "done",
             "rationale": "2 days of silence on the photo question — "
                          "account marked no-photo and the campaign "
                          "auto-started (Santino policy 2026-09-20). A "
                          "photo can still be added later; touches 1/3 "
                          "pick it up."})
        print(f"    {tail[0][:120] if tail else 'activated'}")
        try:
            from work_log import work_log
            work_log(cid, "reviews", "campaign-auto-started",
                     "Review campaign started without a team photo after "
                     "2 quiet days on the photo question.",
                     evidence={"result": tail[0][:160] if tail else ""},
                     source="review_list_stage.py")
        except Exception:  # noqa: BLE001
            pass
    if changed and not dry:
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": _PHOTO_ASKED_KV, "v": asked},
            prefer="resolution=merge-duplicates")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--company")
    a = ap.parse_args()
    stage_pins(a.dry_run, a.company)
    seed_readiness_asks(a.dry_run, a.company)
    try:
        photo_timeout_sweep(a.dry_run, a.company)
    except Exception as e:  # noqa: BLE001 — the timeout leg never blocks staging
        print(f"  photo-timeout sweep error: {str(e)[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
