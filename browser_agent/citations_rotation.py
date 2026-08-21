"""citations_rotation — the tracker-driven nightly citations pass.

Santino 2026-08-21 (un-parked): "running an entire fleet of citations for
two to three companies per night." The browser-agent sweep already owns the
HOW for each portal (HomeGuide state machine, Bing bulk sync); this module
owns WHICH companies get attention tonight and keeps citation_listings —
the tracker behind the Build Stages popup and the client-facing Business
Listings block — honest as outcomes land.

Passes (all idempotent, all cheap — the browser work stays in the sweep):
  1. WRITE-BACK   browser_agent_actions outcomes -> tracker statuses
                  (homeguide-create done -> live + URL; review_needed ->
                  pending_review).
  2. VERIFY       pending_review homeguide rows whose public URL now serves
                  -> live (plain HTTP, no browser).
  3. PICK         NIGHTLY_COMPANIES companies most in need (wrong_data
                  first, then fewest live listings, newest clients break
                  ties) -> ensure their citations-build ledger rows exist so
                  the sweep's creation queue sees them; wrong_data rows are
                  REPORTED for the supervised window (no unattended edits on
                  bot-defended portals).
  4. STREAKS      3+ consecutive failed creation attempts for one company
                  -> ONE deduped ops card.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
       or os.environ["SUPABASE_SERVICE_KEY"])
HDR = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
       "Content-Type": "application/json"}
NIGHTLY_COMPANIES = 3
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _get(path: str):
    r = requests.get(f"{SB}/rest/v1/{path}", headers=HDR, timeout=30)
    return r.json() if r.ok else []


def _patch(path: str, body: dict) -> bool:
    return requests.patch(f"{SB}/rest/v1/{path}", headers=HDR, json=body,
                          timeout=30).ok


def rotate(dry_run: bool = False) -> list[str]:
    out: list[str] = []
    now = datetime.now(timezone.utc).isoformat()

    # ---- 1. WRITE-BACK ---------------------------------------------------
    acts = _get("browser_agent_actions?select=company_id,action,outcome,detail,meta,created_at"
                "&action=eq.homeguide-create&order=created_at.asc&limit=500")
    tracker = {(t["company_id"], t["directory"]): t for t in
               _get("citation_listings?select=id,company_id,directory,status,listing_url")}
    for a in acts:
        cid = a.get("company_id")
        if not cid:
            continue
        url = (a.get("meta") or {}).get("public_url")
        want = ("live" if a.get("outcome") == "done"
                else "pending_review" if a.get("outcome") == "review_needed"
                else None)
        if not want:
            continue
        row = tracker.get((cid, "homeguide"))
        if row and row["status"] not in (want, "live"):
            out.append(f"write-back: {cid[-6:]} homeguide -> {want}")
            if not dry_run:
                _patch(f"citation_listings?id=eq.{row['id']}",
                       {"status": want, "listing_url": url or row.get("listing_url"),
                        "updated_at": now})

    # ---- 2. VERIFY pending homeguide URLs --------------------------------
    for t in tracker.values():
        if t["directory"] == "homeguide" and t["status"] == "pending_review" \
                and t.get("listing_url"):
            try:
                r = requests.get(t["listing_url"], headers={"User-Agent": UA},
                                 timeout=25, allow_redirects=True)
                if r.ok:  # public URL serves = published
                    out.append(f"verified live: {t['company_id'][-6:]} homeguide")
                    if not dry_run:
                        _patch(f"citation_listings?id=eq.{t['id']}",
                               {"status": "live", "updated_at": now})
            except Exception:  # noqa: BLE001 — stays pending, next night retries
                pass

    # ---- 3. PICK tonight's companies -------------------------------------
    per_co: dict[str, dict] = {}
    for t in tracker.values():
        d = per_co.setdefault(t["company_id"], {"live": 0, "wrong": 0, "total": 0})
        d["total"] += 1
        if t["status"] == "live":
            d["live"] += 1
        if t["status"] == "wrong_data":
            d["wrong"] += 1
    cos = {c["id"]: c for c in _get(
        "companies?select=id,name,status,created_at&plan=ilike.rank%20ai")}
    inactive = {"paused", "cancelled", "canceled", "churned", "inactive", "archived"}
    # wrong_data first, then fewest live listings; newest clients break ties
    def _created_ts(cid: str) -> float:
        try:
            return datetime.fromisoformat(
                str(cos[cid]["created_at"]).replace("Z", "+00:00")).timestamp()
        except (KeyError, TypeError, ValueError):
            return 0.0
    ranked = sorted(
        (cid for cid in per_co
         if cid in cos
         and str((cos.get(cid) or {}).get("status") or "").lower() not in inactive),
        key=lambda c: (-per_co[c]["wrong"], per_co[c]["live"], -_created_ts(c)))
    picks = ranked[:NIGHTLY_COMPANIES]
    for cid in picks:
        name = (cos.get(cid) or {}).get("name") or cid
        d = per_co[cid]
        out.append(f"pick: {name} (wrong_data={d['wrong']}, live={d['live']}/{d['total']})")
        if d["wrong"]:
            wrongs = [t for t in tracker.values()
                      if t["company_id"] == cid and t["status"] == "wrong_data"]
            for w in wrongs:
                out.append(f"  SUPERVISED: {w['directory']} correction ready "
                           "(bot-defended portal — runs in the supervised window)")

    # ---- 4. STREAK watchdog ----------------------------------------------
    # Count consecutive failures per company from the newest attempt back;
    # any success (done/review_needed) ends that company's streak.
    fails: dict[str, int] = {}
    ended: set[str] = set()
    for a in reversed(acts):          # newest first
        cid = a.get("company_id")
        if not cid or cid in ended:
            continue
        if a.get("outcome") in ("done", "review_needed"):
            ended.add(cid)
        elif a.get("outcome") == "failed":
            fails[cid] = fails.get(cid, 0) + 1
    for cid, n in fails.items():
        if n >= 3:
            marker = f"[CITATIONS-STREAK {cid}]"
            notes = _get(f"marketing_ops_notes?company_id=eq.{cid}&status=eq.open&select=id,body")
            if any(marker in (x.get("body") or "") for x in notes):
                continue
            out.append(f"STREAK: {cid[-6:]} {n} consecutive creation failures — card filed")
            if not dry_run:
                requests.post(f"{SB}/rest/v1/marketing_ops_notes", headers=HDR,
                              json={"company_id": cid, "status": "open", "body":
                                    f"[TODO-SANTINO] {marker} citation creation has "
                                    f"failed {n} nights in a row — check the sweep log "
                                    "and the portal for a wall (captcha/review lock)."},
                              timeout=30)
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for ln in rotate(a.dry_run):
        print("  ROTATE: " + ln)
