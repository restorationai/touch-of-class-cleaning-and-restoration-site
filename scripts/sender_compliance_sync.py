#!/usr/bin/env python3
"""sender_compliance_sync.py — Twilio sender verification truth sync
(Santino 2026-09-18: "I want to know the status of the submission:
approved, pending, rejected... add that to display text" + the Dry1 Out
find: app said approved while the number is an UNREGISTERED LOCAL line
being 50% carrier-filtered).

Twice daily (ops-worker 13:05 + 21:05 UTC), for every client with a
Twilio subaccount + agent number:

  toll-free number  -> read the subaccount's Tollfree Verification record:
                       TWILIO_APPROVED -> approved
                       IN_REVIEW / PENDING_REVIEW -> pending
                       TWILIO_REJECTED -> rejected (+ rejection_reason)
                       no record -> not_started
  local number      -> compliance_type 'a2p_local'; approved ONLY if the
                       subaccount has a VERIFIED A2P campaign, else
                       not_started (corrects stale 'approved' rows).

Writes compliance_status / compliance_type / compliance_rejection_reason /
compliance_checked_at on company_phone_setup — the exact row the reviews
board renders. Read-only against Twilio; no submissions from here.

CLI: python3 scripts/sender_compliance_sync.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import os  # noqa: E402
import requests  # noqa: E402
from client_ops_sync import _sb  # noqa: E402

TF_PREFIXES = ("+1800", "+1833", "+1844", "+1855", "+1866", "+1877", "+1888")
STATUS_MAP = {
    "TWILIO_APPROVED": "approved",
    "IN_REVIEW": "pending",
    "PENDING_REVIEW": "pending",
    "TWILIO_REJECTED": "rejected",
}


def check_tollfree(sub_sid: str, sub_tok: str, number: str) -> tuple[str, str | None]:
    r = requests.get("https://messaging.twilio.com/v1/Tollfree/Verifications",
                     auth=(sub_sid, sub_tok), params={"PageSize": 50}, timeout=30)
    r.raise_for_status()
    recs = [v for v in (r.json().get("verifications") or [])
            if v.get("tollfree_phone_number") == number]
    if not recs:
        return "not_started", None
    recs.sort(key=lambda v: str(v.get("date_updated") or ""), reverse=True)
    v = recs[0]
    return (STATUS_MAP.get(str(v.get("status")), "pending"),
            (str(v.get("rejection_reason"))[:300]
             if v.get("rejection_reason") else None))


def check_a2p(sub_sid: str, sub_tok: str) -> str:
    """approved iff any messaging service in the subaccount has a VERIFIED
    UsAppToPerson campaign."""
    try:
        svcs = requests.get("https://messaging.twilio.com/v1/Services",
                            auth=(sub_sid, sub_tok), params={"PageSize": 20},
                            timeout=30).json().get("services") or []
        for s in svcs:
            c = requests.get(
                f"https://messaging.twilio.com/v1/Services/{s['sid']}/Compliance/Usa2p",
                auth=(sub_sid, sub_tok), timeout=30)
            for camp in (c.json().get("compliance") or []) if c.ok else []:
                if str(camp.get("campaign_status")).upper() == "VERIFIED":
                    return "approved"
    except Exception:  # noqa: BLE001 — unknown reads as not_started
        pass
    return "not_started"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rows = _sb("GET", "/rest/v1/company_phone_setup"
               "?select=id,twilio_subaccount_sid,twilio_auth_token,"
               "agent_phone_1,compliance_status,compliance_type"
               "&twilio_subaccount_sid=not.is.null") or []
    comps = {c["id"]: str(c["name"]).strip() for c in
             _sb("GET", "/rest/v1/companies?select=id,name") or []}
    changed = 0
    for r in rows:
        num = str(r.get("agent_phone_1") or "")
        sub, tok = r.get("twilio_subaccount_sid"), r.get("twilio_auth_token")
        if not (num and sub and tok):
            continue
        name = comps.get(r["id"], r["id"])
        try:
            if num.startswith(TF_PREFIXES):
                ctype = "tollfree"
                status, reason = check_tollfree(sub, tok, num)
            else:
                ctype = "a2p_local"
                status, reason = check_a2p(sub, tok), None
        except Exception as e:  # noqa: BLE001 — one client never stops the sweep
            print(f"  {name}: check failed ({str(e)[:80]})")
            continue
        patch = {"compliance_checked_at":
                 datetime.now(timezone.utc).isoformat()}
        if status != r.get("compliance_status"):
            patch["compliance_status"] = status
        if ctype != r.get("compliance_type"):
            patch["compliance_type"] = ctype
        patch["compliance_rejection_reason"] = reason
        if a.dry_run:
            if len(patch) > 1:
                print(f"  {name}: {r.get('compliance_status')} -> {status} "
                      f"({ctype}{', ' + reason if reason else ''}) [dry-run]")
            continue
        _sb("PATCH", f"/rest/v1/company_phone_setup?id=eq.{r['id']}", patch)
        if "compliance_status" in patch:
            changed += 1
            print(f"  {name}: {r.get('compliance_status')} -> {status}"
                  f" ({ctype}{'; ' + reason if reason else ''})")
    print(f"sender compliance sync: {len(rows)} checked, {changed} status change(s)")
    # A2P state machine advance (CRW pilot 2026-09-18): any client mid-chain
    # gets its next step attempted — profile approval flows to trust bundle,
    # brand, campaign, and finally compliance_status=approved, unattended.
    import subprocess
    mids = _sb("GET", "/rest/v1/company_phone_setup"
               "?select=id,a2p_state&a2p_state=not.is.null") or []
    for m in mids:
        stg = (m.get("a2p_state") or {}).get("stage")
        if stg in (None, "approved"):
            continue
        r2 = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "a2p_provision.py"),
             "--company", m["id"]],
            capture_output=True, text=True, timeout=300)
        tail = (r2.stdout or r2.stderr or "").strip().splitlines()
        if tail:
            print("  a2p:", tail[-1][:140])
    return 0


if __name__ == "__main__":
    sys.exit(main())
