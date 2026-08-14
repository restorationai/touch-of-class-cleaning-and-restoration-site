#!/usr/bin/env python3
"""ads_account_create.py — one-click Google Ads account creation (Santino 2026-08-14).

Creates a fresh Google Ads account for a client UNDER OUR MANAGER (MCC
2018844125) via CustomerService.create_customer_client — the exact call that
created All Pro Plumbing's 7479958991 on 08-14. The new account is auto-linked
to the MCC (no invite dance), which is what unlocks Local Services Ads setup
for clients who have no Ads account at all.

Refusal guards — this script REFUSES to create when ANY surface already shows
an account for the company, because a silent second account is exactly the
kind of mess the Build Stages board exists to prevent:
  1. companies.integration_settings.ads.customer_id   (we already created one)
  2. companies.integration_settings.lsa.customer_id   (lsa_detect.py found one)
  3. user_integrations provider=google connection_metadata
     selected_ads_customer_id / ads_customer_id / lsa_customer_id — the same
     detection surfaces mcc_link.py / ads_link_accept.py read. Our own MCC id
     is ignored here. `--force` overrides ONLY this surface (FireDEX case:
     their old account 4757653674 is DEACTIVATED and Bob asked for a
     recreate — a deliberate human call, never the app button's).

On success:
  * integration_settings.ads = {customer_id, created_at, created_by, note}
    (same shape as All Pro's hand-stamped block)
  * one marketing_work_log line: "Google Ads account created (XXX-XXX-XXXX)
    to unlock Local Services Ads setup"
  * a final machine-readable line for api/runner.py:  RESULT {"customer_id": ...}

Credentials — resolution order (matches ads_manager.build_ads_client):
  * clients/narestco/.ads-token.json (the agency MCC OAuth token, local Mac)
  * env fallback: GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET /
    GOOGLE_ADS_REFRESH_TOKEN (Railway — token files are gitignored and never
    deploy). Missing refresh token on Railway = clear error, nothing created.

Usage:
  python3 scripts/ads_account_create.py --company CO-1783443032282           # dry-run
  python3 scripts/ads_account_create.py --company CO-1783443032282 --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb, slug_map  # noqa: E402
from ads_manager import build_ads_client, token_path  # noqa: E402
from work_log import work_log  # noqa: E402

# The agency MCC OAuth token lives in this client dir on the Mac (the same
# credential yesterday's All Pro creation used). Railway has no token files.
MCC_TOKEN_SLUG = "narestco"

# State -> IANA time zone for the new account (primary tz per state; the
# account tz only drives reporting day boundaries, so the dominant zone is
# fine). Fallback: America/Los_Angeles.
STATE_TZ = {
    "AL": "America/Chicago", "AK": "America/Anchorage", "AZ": "America/Phoenix",
    "AR": "America/Chicago", "CA": "America/Los_Angeles", "CO": "America/Denver",
    "CT": "America/New_York", "DC": "America/New_York", "DE": "America/New_York",
    "FL": "America/New_York", "GA": "America/New_York", "HI": "Pacific/Honolulu",
    "ID": "America/Boise", "IL": "America/Chicago", "IN": "America/New_York",
    "IA": "America/Chicago", "KS": "America/Chicago", "KY": "America/New_York",
    "LA": "America/Chicago", "ME": "America/New_York", "MD": "America/New_York",
    "MA": "America/New_York", "MI": "America/Detroit", "MN": "America/Chicago",
    "MS": "America/Chicago", "MO": "America/Chicago", "MT": "America/Denver",
    "NE": "America/Chicago", "NV": "America/Los_Angeles", "NH": "America/New_York",
    "NJ": "America/New_York", "NM": "America/Denver", "NY": "America/New_York",
    "NC": "America/New_York", "ND": "America/Chicago", "OH": "America/New_York",
    "OK": "America/Chicago", "OR": "America/Los_Angeles", "PA": "America/New_York",
    "RI": "America/New_York", "SC": "America/New_York", "SD": "America/Chicago",
    "TN": "America/Chicago", "TX": "America/Chicago", "UT": "America/Denver",
    "VT": "America/New_York", "VA": "America/New_York", "WA": "America/Los_Angeles",
    "WV": "America/New_York", "WI": "America/Chicago", "WY": "America/Denver",
}
# Prod state values are messy ("Pa", "South Dakota", "ca", "New York") —
# normalize full names to the abbrev before the tz lookup.
STATE_NAMES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
    "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE",
    "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR",
    "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
    "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
    "WASHINGTON DC": "DC", "DISTRICT OF COLUMBIA": "DC",
}


def die(msg: str, code: int = 2) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def state_tz(state: str | None) -> tuple[str, str]:
    """(abbrev-or-raw, tz). Unknown/empty state -> America/Los_Angeles."""
    s = (state or "").strip().upper()
    if len(s) > 2:
        s = STATE_NAMES.get(s, s[:2])
    return s, STATE_TZ.get(s, "America/Los_Angeles")


def dashed(cid: str) -> str:
    """1234567890 -> 123-456-7890 (Google's display format)."""
    c = str(cid).replace("-", "")
    return f"{c[:3]}-{c[3:6]}-{c[6:]}" if len(c) == 10 else str(cid)


def existing_account_evidence(company_id: str, ints: dict, mcc: str) -> list[str]:
    """Every surface that already shows an Ads/LSA account for this company.
    Ordered: integration_settings first (hard refusals), then the
    user_integrations detection trio (--force-able)."""
    evidence: list[str] = []
    ads_cid = (ints.get("ads") or {}).get("customer_id")
    if ads_cid:
        evidence.append(f"integration_settings.ads.customer_id = {ads_cid}")
    lsa_cid = (ints.get("lsa") or {}).get("customer_id")
    if lsa_cid:
        evidence.append(f"integration_settings.lsa.customer_id = {lsa_cid}")
    uis = _sb("GET", "/rest/v1/user_integrations"
              f"?client_id=eq.{company_id}&provider=eq.google"
              "&select=status,connection_metadata",
              prefer="return=representation") or []
    for u in uis:
        cm = u.get("connection_metadata") or {}
        for key in ("selected_ads_customer_id", "ads_customer_id", "lsa_customer_id"):
            val = str(cm.get(key) or "").replace("-", "")
            if val and val != mcc:
                evidence.append(
                    f"user_integrations({u.get('status')}).{key} = {val}")
    return evidence


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--company", required=True, help="companies.id (CO-...)")
    ap.add_argument("--apply", action="store_true",
                    help="actually create the account (default: dry-run)")
    ap.add_argument("--force", action="store_true",
                    help="override ONLY the user_integrations detection guard "
                         "(deliberate recreate of a dead account); never "
                         "overrides an integration_settings ads/lsa id")
    args = ap.parse_args()

    mcc = (os.environ.get("GOOGLE_ADS_MCC_CUSTOMER_ID") or "").replace("-", "")
    if not mcc:
        die("GOOGLE_ADS_MCC_CUSTOMER_ID unset — source rank-ai/.env "
            "(or set it on the Railway service).")

    rows = _sb("GET", f"/rest/v1/companies?id=eq.{args.company}"
               "&select=id,name,city,state,integration_settings",
               prefer="return=representation") or []
    if not rows:
        die(f"Company not found: {args.company}")
    co = rows[0]
    name = (co.get("name") or "").strip()
    if not name:
        die(f"{args.company} has no name — refusing to create a nameless account.")
    ints = co.get("integration_settings") or {}
    if isinstance(ints, str):
        ints = json.loads(ints)

    # ---- refusal guards --------------------------------------------------
    evidence = existing_account_evidence(co["id"], ints, mcc)
    hard = [e for e in evidence if e.startswith("integration_settings")]
    soft = [e for e in evidence if not e.startswith("integration_settings")]
    if hard or (soft and not args.force):
        lines = "\n  ".join(hard + soft)
        hint = ("" if hard else
                "\nIf that account is dead and the client wants a fresh one, "
                "that is a deliberate human call: re-run with --force.")
        die(f"{name} ({co['id']}) already shows a Google Ads / LSA account — "
            f"refusing to create a second one:\n  {lines}{hint}")
    if soft and args.force:
        print(f"  --force: overriding detection guard ({'; '.join(soft)})")

    st, tz = state_tz(co.get("state"))
    print(f"\n  {name} ({co['id']})")
    print(f"  city/state: {co.get('city') or '?'}, {st or '?'}  ->  time zone {tz}")
    print(f"  MCC: {mcc}  currency: USD")

    if not args.apply:
        print(f"\n  [dry-run] would create Google Ads account "
              f"\"{name}\" under MCC {mcc} ({tz}). Re-run with --apply.")
        return 0

    # ---- credentials (clear error beats build_ads_client's auth hint) ----
    if not token_path(MCC_TOKEN_SLUG).exists() and not (
            os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
            and os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
            and os.environ.get("GOOGLE_ADS_REFRESH_TOKEN")):
        die("No MCC Ads credential on this host: clients/narestco/"
            ".ads-token.json is absent and GOOGLE_ADS_REFRESH_TOKEN is unset. "
            "One-time manual fix (Railway rank-ai-api service): add the "
            "GOOGLE_ADS_REFRESH_TOKEN env var (value = refresh_token inside "
            "clients/narestco/.ads-token.json on the Mac). Nothing was created.")

    client = build_ads_client(MCC_TOKEN_SLUG, login_as_mcc=True)
    svc = client.get_service("CustomerService")
    customer = client.get_type("Customer")
    customer.descriptive_name = name
    customer.currency_code = "USD"
    customer.time_zone = tz
    try:
        resp = svc.create_customer_client(customer_id=mcc, customer_client=customer)
    except Exception as e:  # GoogleAdsException included — one readable line
        detail = getattr(getattr(e, "failure", None), "errors", None)
        msg = ("; ".join(f"{er.error_code}: {er.message}" for er in detail)
               if detail else str(e))
        die(f"Google Ads create_customer_client failed: {msg[:400]}")
    new_id = resp.resource_name.split("/")[-1]
    print(f"  created: customers/{new_id} (auto-linked under MCC {mcc})")

    # ---- stamp integration_settings.ads (re-read first: creation is slow
    # enough for a concurrent writer to have touched the blob) -------------
    fresh = (_sb("GET", f"/rest/v1/companies?id=eq.{co['id']}"
                 "&select=integration_settings",
                 prefer="return=representation") or [{}])[0]
    ints = fresh.get("integration_settings") or {}
    if isinstance(ints, str):
        ints = json.loads(ints)
    ints["ads"] = {
        "customer_id": new_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "ads_account_create.py",
        "note": f"Created under MCC {mcc} for LSA onboarding; "
                "auto-linked as manager.",
    }
    _sb("PATCH", f"/rest/v1/companies?id=eq.{co['id']}",
        {"integration_settings": ints})
    print("  stamped integration_settings.ads")

    work_log(co["id"], "routine", "ads_account_create",
             f"Google Ads account created ({dashed(new_id)}) to unlock "
             "Local Services Ads setup",
             evidence={"customer_id": new_id, "mcc": mcc, "time_zone": tz},
             source="ads_account_create.py")

    slug = slug_map().get(co["id"])
    print(f"  work_log line written ({slug or co['id']})")
    print(f"\nRESULT {json.dumps({'customer_id': new_id})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
