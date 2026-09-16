#!/usr/bin/env python3
"""tracking_number_billing.py — monthly wallet debit for self-serve
tracking numbers beyond the included 10 (Santino 2026-09-15: "10 included,
$2/mo per number after; accounting rides the wallet").

Counts ONLY numbers stamped created_by=self_serve in
integration_settings.call_tracking — the standard attribution set never
bills. Writes one credit_transactions row (type tracking_number_overage)
and decrements company_wallets.balance, exactly the shape the app's
wallet ledger renders. Idempotent per company per month via ops_kv.

Rides monthly-reports.yml. CLI:
    python3 scripts/tracking_number_billing.py [--dry-run]
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

from client_ops_sync import _sb  # noqa: E402

INCLUDED = 10
CENTS_PER_NUMBER = 200


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    comps = _sb("GET", "/rest/v1/companies?status=eq.Active"
                "&select=id,name,integration_settings") or []
    billed = 0
    for co in comps:
        ints = co.get("integration_settings") or {}
        ct = ints.get("call_tracking") or {}
        selfserve = [v for v in ct.values()
                     if isinstance(v, dict) and v.get("number")
                     and v.get("created_by") == "self_serve"]
        over = max(0, len(selfserve) - INCLUDED)
        if not over:
            continue
        guard = f"tn-overage:{co['id']}:{month}"
        if _sb("GET", f"/rest/v1/ops_kv?k=eq.{guard}&select=k"):
            continue
        total = over * CENTS_PER_NUMBER
        print(f"  {co.get('name', co['id'])}: {len(selfserve)} self-serve "
              f"numbers, {over} over -> ${total / 100:.2f}")
        if a.dry_run:
            billed += 1
            continue
        _sb("POST", "/rest/v1/credit_transactions", {
            "company_id": co["id"],
            "type": "tracking_number_overage",
            "quantity": over,
            "unit_price_cents": CENTS_PER_NUMBER,
            "total_cents": total,
            "description": (f"Custom tracking numbers: {over} beyond the "
                            f"included {INCLUDED} ({month})"),
            "created_by": None,
        }, prefer="return=minimal")
        w = (_sb("GET", f"/rest/v1/company_wallets?company_id=eq.{co['id']}"
                 "&select=balance") or [{}])[0]
        if w:
            _sb("PATCH", f"/rest/v1/company_wallets?company_id=eq.{co['id']}",
                {"balance": (w.get("balance") or 0) - total,
                 "updated_at": datetime.now(timezone.utc).isoformat()})
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": guard, "v": {"at": datetime.now(timezone.utc).isoformat(),
                               "over": over, "cents": total}},
            prefer="resolution=merge-duplicates")
        billed += 1
    print(f"tracking-number overage: {billed} client(s) "
          f"{'would be ' if a.dry_run else ''}billed for {month}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
