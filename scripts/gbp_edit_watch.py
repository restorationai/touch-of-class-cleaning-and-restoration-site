#!/usr/bin/env python3
"""gbp_edit_watch.py — watch a Google Business Profile edit until Google
accepts (or rejects) it, then tell Santino what to do next.

Santino 2026-09-30 (DryCor): the name was recased DRYCOR RESTORE -> DryCor
Restore because LSA refused a phone change on an all-caps name. The edit sits
"under review" (getGoogleUpdated pendingMask) until Google clears it, and the
next step (call LSA to switch the phone) waits on that moment.

State: ops_kv "gbp-edit-watch" = {id: {company_id, location, field, expected,
next_step, since, status}}. A watch resolves ONCE:
  accepted  pendingMask no longer has the field AND Google's value == expected
            -> open [TODO-SANTINO] note carrying next_step + work-log line
  rejected  not pending, but Google's value != expected -> [TODO-SANTINO]
  stuck     still pending after 72h -> one [TODO-SANTINO] nudge (keeps watching)

CLI:
  add --company CO-.. --location locations/.. --field title --expected "X" --next "..."
  check [--dry-run]      (hourly: .github/workflows/gbp-edit-watch.yml)
  list
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import requests  # noqa: E402
import client_concierge as cc  # noqa: E402
import gbp  # noqa: E402

KV = "gbp-edit-watch"
STUCK_H = 72


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _note(cid: str, body: str) -> None:
    cc._sb("POST", "/rest/v1/marketing_ops_notes",
           {"company_id": cid, "author": "gbp-edit-watch", "status": "open",
            "body": body[:1900]}, prefer="return=minimal")


def check(dry: bool) -> int:
    state = cc.kv_get(KV) or {}
    live = {k: w for k, w in state.items() if w.get("status") in ("watching", "stuck")}
    if not live:
        print("no open watches")
    for k, w in live.items():
        tok = gbp.get_access_token(w["company_id"])
        H = {"Authorization": f"Bearer {tok}"}
        f = w["field"]
        r = requests.get(f"https://mybusinessbusinessinformation.googleapis.com/v1/"
                         f"{w['location']}:getGoogleUpdated", params={"readMask": f},
                         headers=H, timeout=30)
        if not r.ok:
            print(f"{k}: read failed {r.status_code} {r.text[:120]}")
            continue
        d = r.json()
        pending = f in (d.get("pendingMask") or "").split(",")
        google = (d.get("location") or {}).get(f)
        age_h = (_now() - datetime.fromisoformat(w["since"])).total_seconds() / 3600
        print(f"{k}: google={google!r} pending={pending} age={age_h:.1f}h")
        if pending:
            if age_h > STUCK_H and w["status"] != "stuck":
                w["status"] = "stuck"
                if not dry:
                    _note(w["company_id"], f"[TODO-SANTINO] GBP edit still UNDER REVIEW after "
                          f"{age_h:.0f}h: {f} -> {w['expected']!r} (Google still shows {google!r}). "
                          "Consider Business Profile support. Watch continues.")
            continue
        if google == w["expected"]:
            w["status"] = "accepted"
            msg = (f"[TODO-SANTINO] GBP edit ACCEPTED by Google: {f} is now {google!r} "
                   f"(submitted {w['since'][:16]}Z, {age_h:.0f}h). NEXT: {w.get('next_step') or 'none'}")
        else:
            w["status"] = "rejected"
            msg = (f"[TODO-SANTINO] GBP edit NOT accepted: {f} asked {w['expected']!r}, "
                   f"Google shows {google!r} and nothing is pending. Check the profile.")
        w["resolved_at"] = _now().isoformat()
        print("  ->", w["status"])
        if not dry:
            _note(w["company_id"], msg)
            try:
                from work_log import work_log
                if w["status"] == "accepted":
                    work_log(w["company_id"], "gbp", "gbp-edit-accepted",
                             f"Google approved the update to your Business Profile {f}: {google}",
                             actor="automation", source="gbp_edit_watch")
            except Exception as e:  # noqa: BLE001
                print(f"  [work-log] warn: {str(e)[:100]}")
    if not dry:
        cc.kv_set(KV, state)
        try:
            from heartbeat import stamp
            stamp("gbp-edit-watch", inputs=len(live),
                  outputs=sum(1 for w in live.values() if w.get("resolved_at")))
        except Exception:  # noqa: BLE001
            pass
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--company", required=True)
    a.add_argument("--location", required=True)
    a.add_argument("--field", default="title")
    a.add_argument("--expected", required=True)
    a.add_argument("--next", default="")
    c = sub.add_parser("check")
    c.add_argument("--dry-run", action="store_true")
    sub.add_parser("list")
    x = ap.parse_args()
    cc.load_env()
    if x.cmd == "add":
        state = cc.kv_get(KV) or {}
        k = hashlib.sha1(f"{x.location}|{x.field}|{x.expected}".encode()).hexdigest()[:10]
        state[k] = {"company_id": x.company, "location": x.location, "field": x.field,
                    "expected": x.expected, "next_step": x.next,
                    "since": _now().isoformat(), "status": "watching"}
        cc.kv_set(KV, state)
        print("watching", k)
        return 0
    if x.cmd == "list":
        print(json.dumps(cc.kv_get(KV) or {}, indent=2))
        return 0
    return check(x.dry_run)


if __name__ == "__main__":
    sys.exit(main())
