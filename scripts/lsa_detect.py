#!/usr/bin/env python3
"""lsa_detect.py — LSA auto-detection (queue #5, Santino 2026-07-31).

The ledger's "Wants LSA — setup not started" item relied on a MANUAL
integration_settings.lsa.setup_done flag, so already-live LSA clients kept
showing as not-started (Flood Fixers, found 07-30). This closes the loop with
two detection modes, both writing the same lsa block:

  A. MCC walk (needs agency MCC creds — env refresh token or a local
     .ads-token.json): every sub-account is checked for Local Services
     campaigns, then matched to a company via
     clients/_agency/lsa-account-map.json (manual overrides for accounts
     Google returns nameless) -> user_integrations ads_customer_id ->
     existing lsa.customer_id -> slug -> name tokens.
  B. Per-company tokens (CI-friendly — runs off user_integrations refresh
     tokens like ads_sync.py): each company's own Google user lists its
     accessible Ads accounts; an LSA campaign found there IS that company's
     (no matching heuristics needed).

Matched + campaign found -> integration_settings.lsa gains
  {customer_id, detected, detected_at, campaign_status, campaigns}
setup_ledger treats a customer_id as setup-done, so the ledger row flips on
the next sweep. Detection only ever FILLS the lsa block — never clears one.

Usage: python3 scripts/lsa_detect.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import re
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
from ads_manager import build_ads_client, gaql, token_path  # noqa: E402

LSA_Q = """SELECT campaign.id, campaign.name, campaign.status FROM campaign
           WHERE campaign.advertising_channel_type = 'LOCAL_SERVICES'
             AND campaign.status != 'REMOVED'"""
STOP = {"llc", "inc", "restoration", "construction", "services", "service",
        "the", "of", "and", "co", "company", "24/7", "247"}


def _tokens(name: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", (name or "").lower())
            if t not in STOP and len(t) > 2}


def _ints(co: dict) -> dict:
    ints = co.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except Exception:
            ints = {}
    return ints


def _campaigns(rows) -> list[dict]:
    return [{"id": str(r.campaign.id), "name": r.campaign.name,
             "status": r.campaign.status.name} for r in rows]


USED_ACCOUNTS: set = set()  # one LSA account belongs to exactly one business


def write_lsa(cos: list, company_id: str, acid: str, campaigns: list[dict],
              how: str, dry: bool, results: list) -> None:
    if acid in USED_ACCOUNTS:
        # A shared agency Google grant can "see" another client's LSA account
        # (ProRestoration listed Home Pride's 2407662739 on the first run) —
        # never let two companies claim the same account.
        print(f"  skip {acid} for {company_id}: already claimed by another client")
        return
    co = next((c for c in cos if c["id"] == company_id), None)
    if not co:
        return
    USED_ACCOUNTS.add(acid)
    ints = _ints(co)
    lsa = ints.get("lsa") or {}
    enabled = any(cp["status"] == "ENABLED" for cp in campaigns)
    # Compare the whole block, not just the id (Santino 2026-08-04): the
    # id-only test meant campaign drift NEVER got written once an account was
    # known — after lsa_link_audit corrected PuroClean's customer_id, the
    # next run still matched on id and left another franchise's campaign list
    # sitting in the record.
    changed = (str(lsa.get("customer_id") or "") != acid
               or not lsa.get("detected")
               or lsa.get("campaigns") != campaigns[:5]
               or lsa.get("campaign_status") != (
                   "ENABLED" if enabled else campaigns[0]["status"]))
    lsa.update({"customer_id": acid, "detected": True,
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "campaign_status": "ENABLED" if enabled else campaigns[0]["status"],
                "campaigns": campaigns[:5]})
    ints["lsa"] = lsa
    co["integration_settings"] = ints  # keep the in-memory copy current
    results.append((company_id, co.get("name", "?"), acid, how, enabled))
    if not dry and changed:
        _sb("PATCH", f"/rest/v1/companies?id=eq.{company_id}",
            {"integration_settings": ints})


def build_mcc_client():
    """A GoogleAdsClient logged in as the agency MCC, or (None, None).

    The one place that knows how to reach the manager account. Order:
    clients/_mcc/.ads-token.json -> GOOGLE_OAUTH_*/GOOGLE_ADS_REFRESH_TOKEN env
    (both handled by build_ads_client) -> any client's own .ads-token.json,
    which works because every one of those grants is an MCC-admin Google user.
    Shared with lsa_link_audit.py so both walk the MCC the same way.
    """
    mcc = (os.environ.get("GOOGLE_ADS_MCC_CUSTOMER_ID") or "").replace("-", "")
    if not mcc:
        print("MCC mode: GOOGLE_ADS_MCC_CUSTOMER_ID not set — skipped")
        return None, None
    if (token_path("_mcc").exists()
            or os.environ.get("GOOGLE_ADS_REFRESH_TOKEN")):
        try:
            return build_ads_client("_mcc", login_as_mcc=True), mcc
        except SystemExit:
            pass
    tok = next(iter(sorted((ROOT / "clients").glob("*/.ads-token.json"))), None)
    if not tok:
        print("MCC mode: no creds (env or token file) — skipped")
        return None, None
    return build_ads_client(tok.parent.name, login_as_mcc=True), mcc


def detect_via_mcc(cos: list, dry: bool, results: list, done: set) -> None:
    client, mcc = build_mcc_client()
    if not client:
        return

    kids = gaql(client, mcc, """
        SELECT customer_client.id, customer_client.descriptive_name,
               customer_client.manager, customer_client.status
        FROM customer_client""")
    subs = [(str(r.customer_client.id), r.customer_client.descriptive_name or "")
            for r in kids
            if not r.customer_client.manager
            and r.customer_client.status.name == "ENABLED"
            and str(r.customer_client.id) != mcc]
    print(f"MCC {mcc}: {len(subs)} enabled sub-accounts")

    manual = {}
    map_path = ROOT / "clients" / "_agency" / "lsa-account-map.json"
    if map_path.exists():
        manual = {k: v for k, v in json.loads(map_path.read_text()).items()
                  if not k.startswith("_")}
    uis = _sb("GET", "/rest/v1/user_integrations?provider=eq.google"
              "&select=client_id,connection_metadata") or []
    ads_id_to_company = {}
    for u in uis:
        # selected_ads_customer_id is what the connect flow actually writes
        # (the account the CLIENT picked as theirs); ads_customer_id is the
        # older key. Either one is a hard, client-asserted identity match.
        for key in ("ads_customer_id", "selected_ads_customer_id"):
            acid = str((u.get("connection_metadata") or {}).get(key)
                       or "").replace("-", "")
            if acid:
                ads_id_to_company[acid] = u["client_id"]

    unmatched = []
    for acid, name in subs:
        try:
            rows = gaql(client, acid, LSA_Q)
        except Exception as e:
            print(f"  skip {acid} ({name[:40]}): {str(e)[:90]}")
            continue
        if not rows:
            continue
        if not name:
            try:
                cr = gaql(client, acid,
                          "SELECT customer.descriptive_name FROM customer")
                name = cr[0].customer.descriptive_name if cr else ""
            except Exception:
                pass

        company_id, how = manual.get(acid), "manual map"
        if not company_id:
            company_id, how = ads_id_to_company.get(acid), "ads_customer_id"
        if not company_id:
            for c in cos:
                if str((_ints(c).get("lsa") or {}).get("customer_id")
                       or "").replace("-", "") == acid:
                    company_id, how = c["id"], "existing lsa.customer_id"
                    break
        if not company_id:
            an = re.sub(r"[^a-z0-9]", "", name.lower())
            for co_id, slug in slug_map().items():
                s = re.sub(r"[^a-z0-9]", "", slug)
                if an and (an == s or an in s or s in an):
                    company_id, how = co_id, f"slug={slug}"
                    break
        if not company_id:
            at = _tokens(name)
            best = max(cos, key=lambda c: len(_tokens(c["name"]) & at), default=None)
            if best and _tokens(best["name"]) and at and (
                    len(_tokens(best["name"]) & at) >= 2
                    or _tokens(best["name"]) <= at or at <= _tokens(best["name"])):
                company_id, how = best["id"], f"name~{best['name'][:30]}"
        if not company_id:
            unmatched.append((acid, name, _campaigns(rows)))
            continue
        if company_id not in done:
            write_lsa(cos, company_id, acid, _campaigns(rows), how, dry, results)
            done.add(company_id)

    for acid, name, camps in unmatched:
        print(f"  UNMATCHED LSA account {acid} '{name[:50]}' "
              f"{[c['name'][:40] for c in camps][:2]} — add it to "
              f"clients/_agency/lsa-account-map.json")


def detect_via_company_tokens(cos: list, dry: bool, results: list, done: set) -> None:
    dev = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
    ocid = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    osec = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not (dev and ocid and osec):
        print("per-company mode: missing GOOGLE_ADS_DEVELOPER_TOKEN/OAUTH env — skipped")
        return
    try:
        from google.ads.googleads.client import GoogleAdsClient
    except ImportError:
        print("per-company mode: google-ads library missing — skipped")
        return
    uis = _sb("GET", "/rest/v1/user_integrations?provider=in.(google,google_ads)"
              "&select=client_id,refresh_token,connection_metadata") or []
    for u in uis:
        company_id = u.get("client_id")
        if not company_id or company_id in done:
            continue
        rt = u.get("refresh_token") or (u.get("connection_metadata") or {}).get("refresh_token")
        if not rt:
            continue
        try:
            cl = GoogleAdsClient.load_from_dict({
                "developer_token": dev, "client_id": ocid, "client_secret": osec,
                "refresh_token": rt, "use_proto_plus": True})
            svc = cl.get_service("CustomerService")
            accessible = [rn.split("/")[-1]
                          for rn in svc.list_accessible_customers().resource_names][:10]
        except Exception:
            continue  # stale grant / not an Ads user — fine
        # WHOSE ACCOUNT IS IT (Santino 2026-08-04). A client's Google login
        # routinely reaches OTHER businesses' Ads accounts — Greg Arianoff's
        # also reaches "PuroClean of The Big Island" (a different franchise),
        # The Restoration Group's reaches "LSA: 911 Restoration of Manhattan".
        # First-LSA-account-wins claimed both as theirs on 07-31, so the
        # ledger tracked a stranger's LSA account. Two guards now:
        #   1. the account the CLIENT picked in the connect flow
        #      (selected_ads_customer_id) is checked FIRST, and
        #   2. any other account must share a name token with the company
        #      before we claim it. Nameless accounts (Google returns "" for
        #      plenty of LSA accounts) still pass — that is the common case.
        cm = u.get("connection_metadata") or {}
        sel = str(cm.get("selected_ads_customer_id")
                  or cm.get("ads_customer_id") or "").replace("-", "")
        ordered = ([sel] if sel in accessible else []) \
            + [a for a in accessible if a != sel]
        co = next((c for c in cos if c["id"] == company_id), None)
        want = _tokens((co or {}).get("name", ""))
        for acid in ordered:
            try:
                rows = gaql(cl, acid, LSA_Q)
            except Exception:
                continue  # manager accounts 400 on metrics-free queries too
            if not rows:
                continue
            if acid != sel and want:
                try:
                    nr = gaql(cl, acid, "SELECT customer.descriptive_name FROM customer")
                    nm = (nr[0].customer.descriptive_name or "") if nr else ""
                except Exception:
                    nm = ""
                if _tokens(nm) and not (_tokens(nm) & want):
                    print(f"  skip {acid} '{nm[:44]}' for "
                          f"{(co or {}).get('name', company_id)}: LSA account "
                          "name matches no part of this client's name")
                    continue
            write_lsa(cos, company_id, acid, _campaigns(rows),
                      "own token", dry, results)
            done.add(company_id)
            break


def main() -> int:
    dry = "--dry-run" in sys.argv
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active"
              "&select=id,name,integration_settings") or []
    results: list = []
    done: set = set()
    detect_via_mcc(cos, dry, results, done)
    detect_via_company_tokens(cos, dry, results, done)
    print(f"\nDetected LSA for {len(results)} client(s):")
    for company_id, name, acid, how, enabled in results:
        print(f"  {name[:36]:38} <- ads {acid} [{how}] "
              f"{'ENABLED' if enabled else 'not enabled'}"
              f"{' (dry-run: not written)' if dry else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
