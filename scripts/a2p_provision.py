#!/usr/bin/env python3
"""a2p_provision.py — A2P 10DLC state machine (CRW pilot 2026-09-18).

Drives one client from nothing to a registered local sender:

  stage subaccount_created -> customer_profile -> profile_submitted
        -> a2p_trust -> brand_submitted -> (sync watches brand)
        -> campaign_submitted -> (sync watches campaign) -> approved

State lives in company_phone_setup.a2p_state (jsonb). Each invocation
performs the NEXT possible step and stops — safe to re-run; the
twice-daily sender_compliance_sync will drive it once the pilot proves
the chain. Secondary customer profiles + A2P trust bundles are created
in the MASTER TrustHub under our approved ISV primary profile
("Restoration AI LLC"); the brand + campaign live in the client's
subaccount.

CLI: python3 scripts/a2p_provision.py --company CO-... [--step N]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import os  # noqa: E402
import requests  # noqa: E402
from client_ops_sync import _sb  # noqa: E402

MASTER = (os.environ["TWILIO_MASTER_ACCOUNT_SID"],
          os.environ["TWILIO_MASTER_AUTH_TOKEN"])
TRUSTHUB = "https://trusthub.twilio.com/v1"
# Twilio's public policy SIDs: secondary customer profile + US A2P profile.
SECONDARY_POLICY = "RNdfbf3fae0e1107f8aded0e7cead80bf5"
# NOTE (CRW pilot): RN806dd6cd... is the STARTER profile policy — looks
# primary, is not, and the evaluator rejects it as "bundle is null". The
# true Primary Customer Profile policy is RN64336418...
PRIMARY_POLICY = "RN6433641899984f951173ef1738c3bdd0"


def _primary_profile_sid() -> str:
    """Our approved ISV primary profile — the secondary must link to it
    (CRW eval: 'Primary customer profile bundle is null')."""
    r = requests.get(f"{TRUSTHUB}/CustomerProfiles", auth=MASTER,
                     params={"PageSize": 50}, timeout=30).json()
    for cp in r.get("results") or []:
        if (cp.get("policy_sid") == PRIMARY_POLICY
                and cp.get("status") == "twilio-approved"):
            return cp["sid"]
    raise RuntimeError("no approved primary customer profile found")


def _e164(raw: str) -> str:
    d = "".join(ch for ch in str(raw) if ch.isdigit())
    if len(d) == 10:
        d = "1" + d
    return "+" + d if d else ""
A2P_POLICY = "RNb0d4771c2c98518d916a3d4cd70a8f8b"
NOTIFY_EMAIL = "setup@restorationai.io"


def _post(url: str, data: dict, auth=MASTER) -> dict:
    r = requests.post(url, auth=auth, data=data, timeout=60)
    body = r.json() if r.text else {}
    if not r.ok:
        raise RuntimeError(f"{url.split('/v1/')[-1]}: {r.status_code} "
                           f"{str(body.get('message') or body)[:200]}")
    return body


def _save(cid: str, st: dict) -> None:
    _sb("PATCH", f"/rest/v1/company_phone_setup?id=eq.{cid}", {"a2p_state": st})


def run(cid: str) -> int:
    row = _sb("GET", f"/rest/v1/company_phone_setup?id=eq.{cid}"
              "&select=a2p_state,twilio_subaccount_sid,twilio_auth_token,"
              "agent_phone_1,twilio_phone_number_sid,business_ein,"
              "legal_business_name,legal_business_address")[0]
    co = _sb("GET", f"/rest/v1/companies?id=eq.{cid}"
             "&select=name,website,email,phone,account_owner_name")[0]
    st = row.get("a2p_state") or {}
    stage = st.get("stage") or "subaccount_created"
    addr = row["legal_business_address"]
    addr = json.loads(addr) if isinstance(addr, str) else addr
    legal = row["legal_business_name"].strip()
    website = str(co.get("website") or "")
    if website and not website.startswith("http"):
        website = "https://" + website.strip().lower()
    owner = str(co.get("account_owner_name") or "Owner").split()
    first, last = owner[0], (owner[-1] if len(owner) > 1 else "Owner")
    print(f"== {co['name'].strip()} | stage: {stage}")

    if stage == "subaccount_created":
        cp = _post(f"{TRUSTHUB}/CustomerProfiles", {
            "FriendlyName": legal, "Email": NOTIFY_EMAIL,
            "PolicySid": SECONDARY_POLICY})
        st.update(stage="customer_profile", customer_profile_sid=cp["sid"])
        _save(cid, st)
        print("  customer profile:", cp["sid"])

    elif stage == "customer_profile":
        cp_sid = st["customer_profile_sid"]
        biz = _post(f"{TRUSTHUB}/EndUsers", {
            "FriendlyName": f"{legal} business info",
            "Type": "customer_profile_business_information",
            "Attributes": json.dumps({
                "business_name": legal,
                "business_identity": "direct_customer",
                # Per-client override (Davis 2026-10-01 is "Davis Construction
                # Inc.", a corporation): a wrong entity type fails the brand.
                "business_type": st.get("business_type") or "Limited Liability Corporation",
                "business_industry": "CONSTRUCTION",
                "business_registration_identifier": "EIN",
                "business_registration_number": row["business_ein"],
                "business_regions_of_operation": "USA_AND_CANADA",
                "website_url": website,
            })})
        rep = _post(f"{TRUSTHUB}/EndUsers", {
            "FriendlyName": f"{legal} rep",
            "Type": "authorized_representative_1",
            "Attributes": json.dumps({
                "first_name": first, "last_name": last,
                "email": str(co.get("email") or NOTIFY_EMAIL).strip(),
                "phone_number": _e164(co.get("phone") or ""),
                "business_title": "Owner", "job_position": "CEO",
            })})
        ad = _post(f"https://api.twilio.com/2010-04-01/Accounts/{MASTER[0]}/Addresses.json", {
            "CustomerName": legal, "Street": addr["line1"], "City": addr["city"],
            "Region": addr["state"], "PostalCode": addr["zip"],
            "IsoCountry": addr.get("country", "US"), "FriendlyName": legal})
        doc = _post(f"{TRUSTHUB}/SupportingDocuments", {
            "FriendlyName": f"{legal} address", "Type": "customer_profile_address",
            "Attributes": json.dumps({"address_sids": ad["sid"]})})
        for ent in (biz["sid"], rep["sid"], doc["sid"], _primary_profile_sid()):
            _post(f"{TRUSTHUB}/CustomerProfiles/{cp_sid}/EntityAssignments",
                  {"ObjectSid": ent})
        ev = _post(f"{TRUSTHUB}/CustomerProfiles/{cp_sid}/Evaluations",
                   {"PolicySid": SECONDARY_POLICY})
        if ev.get("status") != "compliant":
            fails = [r2 for r2 in ev.get("results") or []
                     if not r2.get("passed")]
            raise RuntimeError("profile not compliant: "
                               + json.dumps(fails)[:400])
        _post(f"{TRUSTHUB}/CustomerProfiles/{cp_sid}",
              {"Status": "pending-review"})
        st.update(stage="profile_submitted")
        _save(cid, st)
        print("  profile submitted for review (compliant)")

    elif stage == "profile_submitted":
        cp_sid = st["customer_profile_sid"]
        r = requests.get(f"{TRUSTHUB}/CustomerProfiles/{cp_sid}",
                         auth=MASTER, timeout=30).json()
        print("  profile status:", r.get("status"))
        if r.get("status") != "twilio-approved":
            return 0
        st.update(stage="profile_approved")
        _save(cid, st)
        run(cid)   # fall through to the next step immediately
        return 0

    elif stage == "profile_approved":
        cp_sid = st["customer_profile_sid"]
        tp = _post(f"{TRUSTHUB}/TrustProducts", {
            "FriendlyName": f"{legal} A2P", "Email": NOTIFY_EMAIL,
            "PolicySid": A2P_POLICY})
        eu = _post(f"{TRUSTHUB}/EndUsers", {
            "FriendlyName": f"{legal} a2p info",
            "Type": "us_a2p_messaging_profile_information",
            "Attributes": json.dumps({"company_type": "private"})})
        _post(f"{TRUSTHUB}/TrustProducts/{tp['sid']}/EntityAssignments",
              {"ObjectSid": eu["sid"]})
        _post(f"{TRUSTHUB}/TrustProducts/{tp['sid']}/EntityAssignments",
              {"ObjectSid": cp_sid})
        ev = _post(f"{TRUSTHUB}/TrustProducts/{tp['sid']}/Evaluations",
                   {"PolicySid": A2P_POLICY})
        if ev.get("status") != "compliant":
            raise RuntimeError("a2p bundle not compliant: "
                               + json.dumps(ev.get("results"))[:300])
        _post(f"{TRUSTHUB}/TrustProducts/{tp['sid']}", {"Status": "pending-review"})
        st.update(stage="a2p_trust", trust_product_sid=tp["sid"])
        _save(cid, st)
        print("  a2p trust bundle submitted:", tp["sid"])

    elif stage == "a2p_trust":
        sub = (row["twilio_subaccount_sid"], row["twilio_auth_token"])
        tp = requests.get(f"{TRUSTHUB}/TrustProducts/{st['trust_product_sid']}",
                          auth=MASTER, timeout=30).json()
        print("  trust bundle status:", tp.get("status"))
        if tp.get("status") != "twilio-approved":
            return 0
        br = _post("https://messaging.twilio.com/v1/a2p/BrandRegistrations", {
            "CustomerProfileBundleSid": st["customer_profile_sid"],
            "A2PProfileBundleSid": st["trust_product_sid"]}, auth=sub)
        st.update(stage="brand_submitted", brand_sid=br["sid"])
        _save(cid, st)
        print("  brand submitted:", br["sid"])

    elif stage == "brand_submitted":
        sub = (row["twilio_subaccount_sid"], row["twilio_auth_token"])
        br = requests.get("https://messaging.twilio.com/v1/a2p/BrandRegistrations/"
                          + st["brand_sid"], auth=sub, timeout=30).json()
        print("  brand status:", br.get("status"),
              "| failure:", br.get("failure_reason"))
        if br.get("status") != "APPROVED":
            return 0
        svc = _post("https://messaging.twilio.com/v1/Services", {
            "FriendlyName": f"{legal} Review Campaign",
            "InboundRequestUrl": os.environ["SUPABASE_URL"].rstrip("/")
            + "/functions/v1/twilio-inbound-review-optout",
            "UseInboundWebhookOnNumber": "false"}, auth=sub)
        # The LOCAL number bought for this registration (a2p_state.number_sid).
        # twilio_phone_number_sid can be the client's toll-free line (Davis),
        # which must never be pulled into a 10DLC messaging service.
        _post(f"https://messaging.twilio.com/v1/Services/{svc['sid']}/PhoneNumbers",
              {"PhoneNumberSid": st.get("number_sid") or row["twilio_phone_number_sid"]},
              auth=sub)
        camp = _post(f"https://messaging.twilio.com/v1/Services/{svc['sid']}"
                     "/Compliance/Usa2p", {
            "BrandRegistrationSid": st["brand_sid"],
            "UsAppToPersonUsecase": "LOW_VOLUME",
            "Description": "Review requests and appointment/service updates "
                           "to existing customers of this restoration company.",
            "MessageFlow": "Customers opt in verbally during service calls "
                           "and via written consent on service agreements; "
                           "they text STOP to opt out at any time.",
            "MessageSamples": [
                f"Hi, this is {legal}. Thanks for letting us help with your "
                "restoration project. Would you mind sharing a quick review? "
                "Reply STOP to opt out.",
                f"{legal}: Thanks again for your business. Here is the review "
                "link we mentioned. Reply STOP to opt out.",
            ],
            "HasEmbeddedLinks": "true", "HasEmbeddedPhone": "false",
            "SubscriberOptIn": "true", "AgeGated": "false",
            "DirectLending": "false"}, auth=sub)
        st.update(stage="campaign_submitted", service_sid=svc["sid"],
                  campaign_sid=camp.get("sid"))
        _save(cid, st)
        print("  messaging service + campaign submitted:", svc["sid"])

    elif stage == "campaign_submitted":
        sub = (row["twilio_subaccount_sid"], row["twilio_auth_token"])
        c = requests.get(f"https://messaging.twilio.com/v1/Services/"
                         f"{st['service_sid']}/Compliance/Usa2p",
                         auth=sub, timeout=30).json()
        for camp in c.get("compliance") or []:
            print("  campaign status:", camp.get("campaign_status"))
            if str(camp.get("campaign_status")).upper() == "VERIFIED":
                st.update(stage="approved")
                _save(cid, st)
                _sb("PATCH", f"/rest/v1/company_phone_setup?id=eq.{cid}",
                    {"compliance_status": "approved"})
                print("  >> A2P COMPLETE — sender is registered and live")
        return 0

    else:
        print("  stage:", stage, "— nothing to do")
    return 0


def advance_all() -> int:
    """Hourly business-hours advance (Santino 2026-09-19: profile approvals
    can land in minutes — twice daily left CRW approved-but-parked for
    hours). Only clients mid-chain; quiet when there are none."""
    from datetime import datetime, timezone
    h = datetime.now(timezone.utc).hour
    if not (13 <= h <= 23):   # ~6am-4pm PT: Twilio reviews land in business hours
        return 0
    mids = _sb("GET", "/rest/v1/company_phone_setup"
               "?select=id,a2p_state&a2p_state=not.is.null") or []
    for m in mids:
        stg = (m.get("a2p_state") or {}).get("stage")
        if stg in (None, "approved"):
            continue
        try:
            run(m["id"])
        except Exception as e:  # noqa: BLE001 — one client never stops the loop
            print(f"  {m['id']}: {str(e)[:120]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company")
    ap.add_argument("--advance-all", action="store_true")
    a = ap.parse_args()
    if a.advance_all:
        return advance_all()
    if not a.company:
        ap.error("--company or --advance-all required")
    return run(a.company)


if __name__ == "__main__":
    sys.exit(main())
