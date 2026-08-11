#!/usr/bin/env python3
"""mcc_link.py — MCC-invite self-accept, seen and done from the CLIENT's side.

Sister script to ads_link_accept.py (2026-08-05), which walks the MCC's
customer_client_link view and needs full MCC credentials. This one needs only
what every connected client already gave us: their own OAuth grant (the
connect flow requests https://www.googleapis.com/auth/adwords alongside
business.manage) plus our developer token. It asks each client's Google user
"which Ads accounts can you see, and which managers are linked to them?" —
the customer_manager_link view — and can flip a PENDING link to OUR manager
account to ACTIVE with the client's own admin rights. That IS the "click
accept in the email" the invites talk about; no client action needed.

SAFETY RAILS (all enforced in code, not convention):
  * only links whose manager_customer is OUR MCC (GOOGLE_ADS_MCC_CUSTOMER_ID)
    are ever eligible for accept — links to any other manager are reported,
    never touched;
  * only status=PENDING links are mutated, only to ACTIVE — we never create
    links, never cancel, never touch any other field or service;
  * the MCC's own customer id is never a mutation target;
  * login-customer-id on every call is the CLIENT's OWN customer id (their
    auth context), never the MCC;
  * accept --all is a dry run unless --apply is passed, and --apply runs a
    validateOnly probe before the real mutate.

Tokens from wizard-flow-era clients may lack the adwords scope; those are
probed via oauth2 tokeninfo, skipped gracefully, and listed in the report.

Usage:
  python3 scripts/mcc_link.py status --all [--company CO-...]
  python3 scripts/mcc_link.py accept --all [--apply] [--company CO-...]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import os  # noqa: E402  (after load_dotenv on purpose)

from client_ops_sync import _sb, slug_map  # noqa: E402

# v24 = the installed google-ads library's default (client.py
# _VALID_API_VERSIONS[0]). v21 was observed mid-brownout on 2026-08-11:
# identical calls flip-flopping between success and UNSUPPORTED_VERSION.
ADS_API = "https://googleads.googleapis.com/v24"
ADWORDS_SCOPE = "https://www.googleapis.com/auth/adwords"
TIMEOUT = 30
RETRIES = 3  # Google frontends time out sporadically from this LAN


def _req(method: str, url: str, **kw):
    """requests.request with a couple of retries on transport-level failures.
    HTTP error statuses are NOT retried — callers read those."""
    for attempt in range(RETRIES):
        try:
            return requests.request(method, url, timeout=TIMEOUT, **kw)
        except (requests.Timeout, requests.ConnectionError):
            if attempt == RETRIES - 1:
                raise
            time.sleep(3 * (attempt + 1))  # wifi blips outlive instant retries
    raise RuntimeError("unreachable")

LINK_QUERY = """SELECT customer_manager_link.manager_customer,
       customer_manager_link.status,
       customer_manager_link.resource_name
FROM customer_manager_link"""


def fmt_acct(a: str) -> str:
    return f"{a[:3]}-{a[3:6]}-{a[6:]}" if len(a) == 10 and a.isdigit() else (a or "-")


def our_mcc() -> str:
    """Our manager customer id, from the same env var every ads script uses
    (ads_manager.py, lsa_detect.py, ads_link_accept.py). Never guessed."""
    mcc = (os.environ.get("GOOGLE_ADS_MCC_CUSTOMER_ID") or "").replace("-", "")
    if not (len(mcc) == 10 and mcc.isdigit()):
        sys.exit("GOOGLE_ADS_MCC_CUSTOMER_ID is not set (or malformed) — "
                 "refusing to guess which manager account is ours.")
    return mcc


# ------------------------------------------------------------------ oauth side
def refresh_access_token(refresh_token: str) -> tuple[str | None, str]:
    """(access_token, error). Same token endpoint gbp.py uses."""
    r = _req("POST", "https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    })
    if not r.ok:
        return None, f"token refresh failed ({r.status_code}: {r.text[:120]})"
    return r.json().get("access_token"), ""


def has_adwords_scope(access_token: str) -> tuple[bool, str]:
    """(has_scope, scopes_or_error) via the oauth2 tokeninfo probe."""
    r = _req("POST", "https://oauth2.googleapis.com/tokeninfo",
             data={"access_token": access_token})
    if not r.ok:
        return False, f"tokeninfo failed ({r.status_code})"
    scopes = r.json().get("scope", "")
    return ADWORDS_SCOPE in scopes.split(), scopes


# --------------------------------------------------------------- ads REST side
def _ads_headers(access_token: str, login_cid: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {access_token}",
         "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"]}
    if login_cid:
        # The CLIENT's own customer id — their auth context, never the MCC.
        h["login-customer-id"] = login_cid
    return h


def _ads_err(resp) -> str:
    try:
        j = resp.json()
        j = j[0] if isinstance(j, list) and j else j
        err = j.get("error", {})
        details = err.get("details", [{}])
        codes = []
        for d in details:
            for e in d.get("errors", []):
                code = e.get("errorCode", {})
                codes.append(next(iter(code.values()), "?") if code else "?")
        return (f"{err.get('status', resp.status_code)}"
                + (f" [{', '.join(codes)}]" if codes else "")
                + f": {err.get('message', '')[:160]}")
    except Exception:  # noqa: BLE001
        return f"{resp.status_code}: {resp.text[:160]}"


def list_accessible_customers(access_token: str) -> tuple[list[str], str]:
    r = _req("GET", f"{ADS_API}/customers:listAccessibleCustomers",
             headers=_ads_headers(access_token))
    if not r.ok:
        return [], _ads_err(r)
    return [rn.split("/")[-1] for rn in r.json().get("resourceNames", [])], ""


def manager_links(access_token: str, cid: str) -> tuple[list[dict], str]:
    """All customer_manager_link rows on account cid, as the client."""
    r = _req("POST", f"{ADS_API}/customers/{cid}/googleAds:searchStream",
             headers=_ads_headers(access_token, login_cid=cid),
             json={"query": LINK_QUERY})
    if not r.ok:
        return [], _ads_err(r)
    links = []
    for chunk in (r.json() or []):
        for res in chunk.get("results", []):
            cml = res.get("customerManagerLink", {})
            links.append({
                "manager": (cml.get("managerCustomer") or "").split("/")[-1],
                "status": cml.get("status", "UNSPECIFIED"),
                "resource_name": cml.get("resourceName", ""),
            })
    return links, ""


def accept_link(access_token: str, cid: str, resource_name: str,
                validate_only: bool) -> str:
    """Flip one PENDING customer_manager_link to ACTIVE. '' on success."""
    body = {"operations": [{"update": {"resourceName": resource_name,
                                       "status": "ACTIVE"},
                            "updateMask": "status"}],
            "validateOnly": validate_only}
    r = _req("POST", f"{ADS_API}/customers/{cid}/customerManagerLinks:mutate",
             headers=_ads_headers(access_token, login_cid=cid),
             json=body)
    return "" if r.ok else _ads_err(r)


# ------------------------------------------------------------------- gathering
def google_integrations(only_company: str | None) -> list[dict]:
    """One work item per company that has a provider=google row."""
    cos = {c["id"]: c for c in (_sb(
        "GET", "/rest/v1/companies?select=id,name,status") or [])}
    uis = _sb("GET", "/rest/v1/user_integrations?provider=eq.google"
                     "&select=id,client_id,refresh_token,connection_metadata"
                     "&order=created_at.asc") or []
    names = slug_map()
    by_company: dict[str, dict] = {}
    for u in uis:
        cid = u.get("client_id")
        if not cid or (only_company and cid != only_company):
            continue
        rt = u.get("refresh_token") or (u.get("connection_metadata") or {}).get("refresh_token")
        # keep the first row that actually has a refresh token
        if cid in by_company and not (rt and not by_company[cid]["refresh_token"]):
            continue
        co = cos.get(cid) or {}
        by_company[cid] = {
            "company_id": cid,
            "slug": names.get(cid) or "-",
            "name": co.get("name") or "?",
            "co_status": co.get("status") or "?",
            "refresh_token": rt,
        }
    return sorted(by_company.values(), key=lambda x: x["slug"])


def survey(only_company: str | None) -> tuple[list[dict], list[dict], str]:
    """(clients, skipped, mcc). Each client dict gains accounts=[{cid, links,
    error}] where links are customer_manager_link rows seen as that client."""
    mcc = our_mcc()
    clients, skipped = [], []
    for item in google_integrations(only_company):
        if not item["refresh_token"]:
            skipped.append({**item, "why": "no Google refresh token on file"})
            continue
        try:
            _survey_one(item, mcc, clients, skipped)
        except Exception as e:  # noqa: BLE001 — one client never kills the run
            skipped.append({**item, "why": f"error: {str(e)[:140]}"})
    return clients, skipped, mcc


def _survey_one(item: dict, mcc: str, clients: list, skipped: list) -> None:
    token, err = refresh_access_token(item["refresh_token"])
    if not token:
        skipped.append({**item, "why": err})
        return
    ok, _scopes = has_adwords_scope(token)
    if not ok:
        skipped.append({**item, "why": "token lacks adwords scope "
                        "(wizard-flow grant)"})
        return
    cids, err = list_accessible_customers(token)
    if err:
        skipped.append({**item, "why": f"listAccessibleCustomers: {err}"})
        return
    accounts = []
    for cid in cids:
        if cid == mcc:
            # A shared/agency-admin grant can "see" our own MCC. Never
            # query-report or mutate ourselves through a client row.
            continue
        links, lerr = manager_links(token, cid)
        accounts.append({"cid": cid, "links": links, "error": lerr})
    clients.append({**item, "token": token, "accounts": accounts})


# --------------------------------------------------------------------- actions
def cmd_status(only_company: str | None) -> int:
    clients, skipped, mcc = survey(only_company)
    print(f"our MCC: {fmt_acct(mcc)}\n")
    for c in clients:
        print(f"{c['slug']}  {c['name']}  ({c['company_id']}, {c['co_status']})")
        if not c["accounts"]:
            print("    no accessible non-MCC Ads accounts")
        for a in c["accounts"]:
            if a["error"]:
                print(f"    {fmt_acct(a['cid'])}: unreadable — {a['error']}")
                continue
            ours = [l for l in a["links"] if l["manager"] == mcc]
            other = [l for l in a["links"] if l["manager"] != mcc]
            if not a["links"]:
                print(f"    {fmt_acct(a['cid'])}: no manager links")
            for l in ours:
                print(f"    {fmt_acct(a['cid'])}: OUR MCC link {l['status']}"
                      f"  ({l['resource_name']})")
            for l in other:
                print(f"    {fmt_acct(a['cid'])}: other manager "
                      f"{fmt_acct(l['manager'])} {l['status']} (not ours — "
                      f"never touched)")
        print()
    _print_skipped(skipped)
    return 0


def cmd_accept(only_company: str | None, apply: bool) -> int:
    clients, skipped, mcc = survey(only_company)
    print(f"our MCC: {fmt_acct(mcc)}  mode: {'APPLY' if apply else 'DRY RUN'}\n")
    todo, seen = [], set()
    for c in clients:
        for a in c["accounts"]:
            for l in a["links"]:
                # THE safety gate: our MCC as manager, PENDING, and never the
                # MCC's own account as the target. Dedupe by resource_name —
                # two clients sharing a Google user can both see one link.
                if (l["manager"] == mcc and l["status"] == "PENDING"
                        and a["cid"] != mcc
                        and l["resource_name"] not in seen):
                    seen.add(l["resource_name"])
                    todo.append((c, a["cid"], l))
    if not todo:
        print("no PENDING links to our MCC — nothing to accept")
        _print_skipped(skipped)
        return 0
    for c, cid, l in todo:
        tag = f"{c['slug']:32} {fmt_acct(cid):>14}  {l['resource_name']}"
        if not apply:
            print(f"  would accept  {tag}")
            continue
        err = accept_link(c["token"], cid, l["resource_name"], validate_only=True)
        if err:
            print(f"  REJECTED (validateOnly)  {tag}\n      {err}")
            continue
        err = accept_link(c["token"], cid, l["resource_name"], validate_only=False)
        if err:
            print(f"  FAILED  {tag}\n      {err}")
            continue
        print(f"  accepted  {tag}")
    if not apply:
        print("\n(dry run — pass --apply to actually accept)")
    _print_skipped(skipped)
    return 0


def _print_skipped(skipped: list[dict]) -> None:
    if not skipped:
        return
    print("skipped:")
    for s in skipped:
        print(f"  {s['slug']:32} ({s['company_id']}, {s['co_status']}) — {s['why']}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("status", "accept"):
        sp = sub.add_parser(name)
        sp.add_argument("--all", action="store_true",
                        help="all companies with a google integration")
        sp.add_argument("--company", help="one company id (CO-...)")
        if name == "accept":
            sp.add_argument("--apply", action="store_true",
                            help="actually mutate (default: dry run)")
    args = p.parse_args()
    if not args.all and not args.company:
        p.error("pass --all or --company CO-...")
    only = None if args.all else args.company
    if args.cmd == "status":
        return cmd_status(only)
    return cmd_accept(only, apply=getattr(args, "apply", False))


if __name__ == "__main__":
    sys.exit(main())
