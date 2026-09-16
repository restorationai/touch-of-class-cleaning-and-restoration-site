#!/usr/bin/env python3
"""
provision_agency_tollfree.py — provision ONE agency-wide toll-free SMS sender.

Why: /api/estimate on every client site texts the client when a lead submits.
Today that rides each client's own call-tracking number; the agency toll-free
gives every site a single verified sender (Pages secret ESTIMATE_SMS_FROM +
ESTIMATE_SMS_SID/ESTIMATE_SMS_TOKEN) with no per-client Twilio dependency.

REQUIRED CREDS (not in .env yet — operator action):
  Add to rank-ai/.env from twilio.com/console (master/parent account, top-right
  "Account SID" + "Auth Token" on the console dashboard):
    TWILIO_MASTER_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    TWILIO_MASTER_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  For `verify`, also add (E.164 — Twilio requires a business contact phone):
    AGENCY_CONTACT_PHONE=+1xxxxxxxxxx

Subcommands (run in order):
  create   Create (or reuse) the "Ignite Systems" subaccount under the master
           account, search available toll-free numbers (833/844/855/866/877/888),
           purchase ONE, and record everything to clients/_agency/tollfree.json.
  verify   Submit the Toll-Free Verification (Twilio Messaging Compliance API)
           for the purchased number using Restoration AI LLC legal data (IRS
           CP575A). Verification SID recorded to the same JSON.
  status   Poll the verification status (PENDING_REVIEW / IN_REVIEW /
           TWILIO_APPROVED / TWILIO_REJECTED).

Usage:
  python3 scripts/provision_agency_tollfree.py create [--dry-run]
  python3 scripts/provision_agency_tollfree.py verify
  python3 scripts/provision_agency_tollfree.py status

After TWILIO_APPROVED: set Pages secrets on all client sites —
  ESTIMATE_SMS_FROM  = purchased number (E.164)
  ESTIMATE_SMS_SID   = subaccount SID   (from tollfree.json)
  ESTIMATE_SMS_TOKEN = subaccount auth token (from tollfree.json)

State file: clients/_agency/tollfree.json (subaccount SID/token, number SID,
number, verification SID, statuses). Do not commit real tokens to a public repo
— this monorepo is private, matching existing practice for client records.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "clients" / "_agency" / "tollfree.json"

TWILIO_API = "https://api.twilio.com/2010-04-01"
TWILIO_MESSAGING = "https://messaging.twilio.com/v1"
SUBACCOUNT_NAME = "Ignite Systems"
TOLLFREE_PREFIXES = ["833", "844", "855", "866", "877", "888"]

# --- Toll-Free Verification legal data (Restoration AI LLC, IRS CP575A) -----
BUSINESS = {
    "BusinessName": "Restoration AI LLC",
    "BusinessType": "PRIVATE_PROFIT",
    # EIN digits-only: the hyphenated form is a known auto-reject trigger for
    # "End Business Details Must Be Accurate and Complete" (first submission
    # HH2a1acd... rejected 2026-07; resubmitted 2026-09-16).
    "BusinessRegistrationNumber": "414181094",
    "BusinessRegistrationIdentifier": "EIN",
    "BusinessRegistrationAuthority": "EIN",
    "BusinessRegistrationCountry": "US",
    "BusinessWebsite": "https://restorationai.io",
    "BusinessStreetAddress": "7465 Bella Vista Road",
    "BusinessCity": "Atascadero",
    "BusinessStateProvinceRegion": "CA",
    "BusinessPostalCode": "93422",
    "BusinessCountry": "US",
    "BusinessContactFirstName": "Santino",
    "BusinessContactLastName": "Velci",
    "BusinessContactEmail": "contact@restorationai.io",
    # BusinessContactPhone is required by Twilio: supplied at runtime via env
    # AGENCY_CONTACT_PHONE (E.164, Santino's direct line) — not hardcoded here.
    "NotificationEmail": "contact@restorationai.io",
}
BUSINESS_EIN = "41-4181094"  # noted for records; Twilio TF verification does not take EIN directly
USE_CASE = {
    "UseCaseCategories": "ACCOUNT_NOTIFICATIONS",
    "UseCaseSummary": (
        "Transactional lead notifications to our business clients: when a visitor "
        "submits a free-estimate request on the client's website, we alert the "
        "client business owner by SMS. Recipients are our contracted clients who "
        "opt in during onboarding."
    ),
    "OptInType": "WEB_FORM",
    "MessageVolume": "100",
    "ProductionMessageSample": (
        "New estimate request: Jane D. (555) 201-4477, Federal Way — water damage "
        "in basement. Reply STOP to opt out."
    ),
    # Placeholder — Twilio review may request a dedicated opt-in screenshot; see note printed by `verify`.
    "OptInImageUrls": "https://restorationai.io/sms-consent/",
}


def master_creds() -> tuple[str, str]:
    sid = os.environ.get("TWILIO_MASTER_ACCOUNT_SID", "").strip()
    tok = os.environ.get("TWILIO_MASTER_AUTH_TOKEN", "").strip()
    if not sid or not tok:
        sys.exit(
            "ERROR: TWILIO_MASTER_ACCOUNT_SID / TWILIO_MASTER_AUTH_TOKEN not set.\n"
            "Add them to rank-ai/.env from twilio.com/console (master account dashboard),\n"
            "then re-run:  set -a && source .env && set +a && python3 scripts/provision_agency_tollfree.py ..."
        )
    return sid, tok


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
    print(f"  state -> {STATE_PATH.relative_to(ROOT)}")


def _die(prefix: str, r: requests.Response) -> None:
    sys.exit(f"ERROR: {prefix} HTTP {r.status_code}: {r.text[:400]}")


# --- create ------------------------------------------------------------------

def find_or_create_subaccount(sid: str, tok: str) -> dict:
    """Reuse the 'Ignite Systems' subaccount if it exists, else create it."""
    r = requests.get(
        f"{TWILIO_API}/Accounts.json",
        params={"FriendlyName": SUBACCOUNT_NAME},
        auth=(sid, tok),
    )
    if not r.ok:
        _die("list subaccounts", r)
    accounts = [a for a in r.json().get("accounts", []) if a.get("status") != "closed"]
    if accounts:
        acct = accounts[0]
        print(f"  reusing subaccount {acct['sid']} ({acct['friendly_name']})")
        return acct
    r = requests.post(
        f"{TWILIO_API}/Accounts.json",
        data={"FriendlyName": SUBACCOUNT_NAME},
        auth=(sid, tok),
    )
    if not r.ok:
        _die("create subaccount", r)
    acct = r.json()
    print(f"  created subaccount {acct['sid']} ({acct['friendly_name']})")
    return acct


def search_tollfree(sub_sid: str, sub_tok: str) -> dict:
    """Search available toll-free numbers, preferring 833 -> 888 order."""
    for prefix in TOLLFREE_PREFIXES:
        r = requests.get(
            f"{TWILIO_API}/Accounts/{sub_sid}/AvailablePhoneNumbers/US/TollFree.json",
            params={"Contains": f"{prefix}*******", "SmsEnabled": "true", "PageSize": 5},
            auth=(sub_sid, sub_tok),
        )
        if not r.ok:
            print(f"  warn: search {prefix} HTTP {r.status_code}")
            continue
        nums = r.json().get("available_phone_numbers", [])
        if nums:
            n = nums[0]
            print(f"  found {n['phone_number']} ({prefix})")
            return n
    sys.exit("ERROR: no toll-free numbers available in any prefix (833/844/855/866/877/888)")


def cmd_create(dry_run: bool) -> None:
    sid, tok = master_creds()
    state = load_state()

    print("== subaccount ==")
    acct = find_or_create_subaccount(sid, tok)
    sub_sid, sub_tok = acct["sid"], acct["auth_token"]
    state.update({
        "subaccount_sid": sub_sid,
        "subaccount_auth_token": sub_tok,
        "subaccount_friendly_name": acct.get("friendly_name", SUBACCOUNT_NAME),
    })

    if state.get("phone_number_sid"):
        print(f"== number already purchased: {state.get('phone_number')} ({state['phone_number_sid']}) — skipping purchase ==")
        save_state(state)
        return

    print("== search toll-free ==")
    candidate = search_tollfree(sub_sid, sub_tok)
    if dry_run:
        print(f"  [dry-run] would purchase {candidate['phone_number']}")
        save_state(state)
        return

    print("== purchase ==")
    r = requests.post(
        f"{TWILIO_API}/Accounts/{sub_sid}/IncomingPhoneNumbers.json",
        data={
            "PhoneNumber": candidate["phone_number"],
            "FriendlyName": "Rank AI estimate notifications (agency)",
        },
        auth=(sub_sid, sub_tok),
    )
    if not r.ok:
        _die("purchase number", r)
    num = r.json()
    state.update({
        "phone_number": num["phone_number"],
        "phone_number_sid": num["sid"],
        "purchased_at": datetime.now(timezone.utc).isoformat(),
    })
    save_state(state)
    print(f"\n  PURCHASED  {num['phone_number']}")
    print(f"  Number SID     {num['sid']}")
    print(f"  Subaccount SID {sub_sid}")
    print("\n  Next: python3 scripts/provision_agency_tollfree.py verify")


# --- verify ------------------------------------------------------------------

def cmd_verify() -> None:
    master_creds()  # fail fast with the same guidance if env missing
    state = load_state()
    sub_sid = state.get("subaccount_sid")
    sub_tok = state.get("subaccount_auth_token")
    num_sid = state.get("phone_number_sid")
    if not (sub_sid and sub_tok and num_sid):
        sys.exit("ERROR: run `create` first (need subaccount + purchased number in clients/_agency/tollfree.json)")

    contact_phone = os.environ.get("AGENCY_CONTACT_PHONE", "").strip()
    if not contact_phone:
        sys.exit(
            "ERROR: AGENCY_CONTACT_PHONE not set (required by Twilio as BusinessContactPhone).\n"
            "Add it to rank-ai/.env as E.164, e.g. AGENCY_CONTACT_PHONE=+15551234567"
        )

    params = dict(BUSINESS)
    params.update(USE_CASE)
    params["BusinessContactPhone"] = contact_phone
    params["TollfreePhoneNumberSid"] = num_sid
    # Additional context Twilio reviewers see:
    params["AdditionalInformation"] = (
        f"EIN {BUSINESS_EIN} (IRS CP575A). Recipients are contracted business "
        "clients of Restoration AI LLC (B2B). Each client opts in by adding "
        "their own number in the Lead Notifications panel of their dashboard "
        "at app.restorationai.io, which displays the consent disclosure. Full "
        "program disclosure: https://restorationai.io/sms-consent/"
    )

    print("== submit Toll-Free Verification ==")
    r = requests.post(
        f"{TWILIO_MESSAGING}/Tollfree/Verifications",
        data=params,
        auth=(sub_sid, sub_tok),
    )
    if not r.ok:
        _die("submit verification", r)
    v = r.json()
    state.update({
        "verification_sid": v.get("sid"),
        "verification_status": v.get("status"),
        "verification_submitted_at": datetime.now(timezone.utc).isoformat(),
    })
    save_state(state)
    print(f"  submitted: {v.get('sid')}  status={v.get('status')}")
    print(
        "\n  NOTE: OptInImageUrls currently points at https://restorationai.io/terms as a\n"
        "  placeholder. Twilio review may request a dedicated screenshot of the opt-in\n"
        "  (the client-onboarding form where the client agrees to SMS lead alerts).\n"
        "  If rejected for that reason, host a screenshot and resubmit."
    )
    print("\n  Poll with: python3 scripts/provision_agency_tollfree.py status")


# --- status ------------------------------------------------------------------

def cmd_status() -> None:
    state = load_state()
    sub_sid = state.get("subaccount_sid")
    sub_tok = state.get("subaccount_auth_token")
    ver_sid = state.get("verification_sid")
    if not (sub_sid and sub_tok):
        sys.exit("ERROR: no subaccount recorded — run `create` first")

    if ver_sid:
        r = requests.get(f"{TWILIO_MESSAGING}/Tollfree/Verifications/{ver_sid}", auth=(sub_sid, sub_tok))
        if not r.ok:
            _die("fetch verification", r)
        vers = [r.json()]
    else:
        r = requests.get(f"{TWILIO_MESSAGING}/Tollfree/Verifications", auth=(sub_sid, sub_tok))
        if not r.ok:
            _die("list verifications", r)
        vers = r.json().get("verifications", [])
        if not vers:
            sys.exit("No verifications found — run `verify` first")

    for v in vers:
        status = v.get("status")
        print(f"  {v.get('sid')}  status={status}")
        if v.get("rejection_reason"):
            print(f"    rejection: {v['rejection_reason']}")
        if v.get("sid") == ver_sid or len(vers) == 1:
            state["verification_status"] = status
    save_state(state)
    if state.get("verification_status") == "TWILIO_APPROVED":
        print(
            "\n  APPROVED — set Pages secrets on every client site:\n"
            f"    ESTIMATE_SMS_FROM  = {state.get('phone_number')}\n"
            f"    ESTIMATE_SMS_SID   = {state.get('subaccount_sid')}\n"
            "    ESTIMATE_SMS_TOKEN = (subaccount auth token from clients/_agency/tollfree.json)"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Agency toll-free SMS sender provisioning")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("create", help="create/reuse subaccount + purchase ONE toll-free number")
    pc.add_argument("--dry-run", action="store_true", help="search but do not purchase")
    sub.add_parser("verify", help="submit Toll-Free Verification for the purchased number")
    sub.add_parser("status", help="poll verification status")
    a = ap.parse_args()

    if a.cmd == "create":
        cmd_create(a.dry_run)
    elif a.cmd == "verify":
        cmd_verify()
    elif a.cmd == "status":
        cmd_status()


if __name__ == "__main__":
    main()
