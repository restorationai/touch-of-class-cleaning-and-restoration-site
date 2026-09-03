#!/usr/bin/env python3
"""stripe_reconcile.py — nightly Stripe-vs-app payment record self-heal.

Why this exists (2026-09-03): the stripe-webhook's invoice handler had a
delivery race — invoice.payment_succeeded arriving before
checkout.session.completed created the billing row was dropped WITH a 200,
so Stripe never retried and the payment record was lost forever. Eleven
active clients (every signup since early August) had zero billing_invoices
rows: the auto-build payment gate wrongly blocked their websites and their
app Billing tab showed nothing. The webhook now 500s so Stripe retries,
but webhooks are inherently lossy (outages, expired retries, next bug).
This sweep is the guarantee: every night, ask Stripe for the truth and
backfill whatever our records are missing.

For each company_billing_setup row with a REAL Stripe customer id (cus_*):
  1. list that customer's PAID invoices from Stripe (newest 25)
  2. any invoice with no billing_invoices row gets one, same shape the
     webhook writes (company_id, stripe_invoice_id, amount_paid_cents,
     billing_type, description, invoice_pdf_url, status)
  3. print one line per backfill — client_ops_sync captures stdout into the
     daily digest, so every heal is visible, never silent
Junk customer ids (anything not cus_*) are reported, never queried.

Usage:
    python3 scripts/stripe_reconcile.py            # heal
    python3 scripts/stripe_reconcile.py --dry-run  # report only
Env: STRIPE_SECRET_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
Wired into client-ops-sync.yml (daily) right after the baseline passes.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SB = (os.environ.get("SUPABASE_URL") or "").rstrip("/") + "/rest/v1"
SB_H = {"apikey": os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
        "Authorization": "Bearer " + os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
        "Content-Type": "application/json"}
STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY", "")


def sb_get(path: str, params: dict) -> list:
    r = requests.get(SB + path, headers=SB_H, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not (STRIPE_KEY and os.environ.get("SUPABASE_URL")):
        print("stripe-reconcile: STRIPE_SECRET_KEY / SUPABASE env missing — skipped")
        return 0

    setups = sb_get("/company_billing_setup",
                    {"select": "id,stripe_customer_id",
                     "stripe_customer_id": "not.is.null"})
    healed = junk = checked = 0
    for s in setups:
        cid, cust = s["id"], (s.get("stripe_customer_id") or "").strip()
        if not cust:
            continue
        if not cust.startswith("cus_"):
            junk += 1
            print(f"  stripe-reconcile: {cid} has a NON-STRIPE customer id "
                  f"({cust!r}) — fix or mark billing_vetted")
            continue
        checked += 1
        try:
            inv = requests.get("https://api.stripe.com/v1/invoices",
                               params={"customer": cust, "status": "paid",
                                       "limit": 25},
                               auth=(STRIPE_KEY, ""), timeout=30).json()
        except Exception as e:  # noqa: BLE001 — one customer never kills the sweep
            print(f"  stripe-reconcile: {cid} Stripe fetch failed ({str(e)[:80]})")
            continue
        for i in inv.get("data", []):
            have = sb_get("/billing_invoices",
                          {"stripe_invoice_id": f"eq.{i['id']}", "select": "id",
                           "limit": "1"})
            if have:
                continue
            if args.dry_run:
                print(f"  stripe-reconcile: {cid} WOULD backfill {i['id']} "
                      f"(${i['amount_paid']/100:.2f})")
                continue
            r = requests.post(SB + "/billing_invoices",
                              headers={**SB_H, "Prefer": "return=minimal"},
                              json={"company_id": cid,
                                    "stripe_invoice_id": i["id"],
                                    "amount_paid_cents": i["amount_paid"],
                                    "billing_type": "subscription",
                                    "description": "Backfilled by nightly Stripe reconciliation",
                                    "invoice_pdf_url": i.get("hosted_invoice_url") or i.get("invoice_pdf"),
                                    "status": "paid"}, timeout=30)
            if r.status_code in (200, 201):
                healed += 1
                print(f"  stripe-reconcile: {cid} BACKFILLED {i['id']} "
                      f"(${i['amount_paid']/100:.2f}) — webhook missed it")
            else:
                print(f"  stripe-reconcile: {cid} insert failed {r.status_code} "
                      f"{r.text[:80]}")
    print(f"stripe-reconcile: {checked} customer(s) checked, {healed} invoice(s) "
          f"backfilled, {junk} junk id(s) flagged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
