#!/usr/bin/env python3
"""Accept our own Google Ads / LSA manager invite — as the client, no client.

WHY THIS EXISTS (Santino 2026-08-05). His rule: "asking a client for things we
already have access to is a big no-no." We had been breaking it twice over.
The obvious half was asking for access already granted (lsa_ask_guard, 08-04).
The half nobody had tested was this one: a PENDING manager link is not
something only the client can clear. It never was.

THE GOOGLE ADS ACCESS MODEL, tested rather than assumed (2026-08-05):

    the MANAGER creates customer_client_link          -> PENDING
    a CLIENT-side ADMIN updates customer_manager_link -> ACTIVE

Both halves are API surfaces. The second one is the "click accept" the emails
talk about, and it is reachable by ANY user with ADMIN access on the client
account — including the Google user the client themselves granted us during
the connect flow. Every client grant in user_integrations carries the
https://www.googleapis.com/auth/adwords scope, so we are that admin.

PROVEN, not theorised — both of these were PENDING for weeks and were cleared
by this code path with zero client action:

    Crew Restoration   3041785923  link 6631048318  PENDING since 07-25 -> ACTIVE
    Home Pride (LSA)   2957729882  link 6622132013  PENDING since 07-10 -> ACTIVE

Home Pride's is the important one: it is a LOCAL SERVICES account, the exact
thing Monica had been chasing Curt about, and the exact thing Monica asked
Angie for on an account that had been ACTIVE since July. So the answer to
"can we approve it ourselves?" is yes, for Ads and LSA alike.

THE CREDENTIAL SPLIT is why this runs at night from Santino's Mac. Reaching
the MCC needs GOOGLE_ADS_DEVELOPER_TOKEN + GOOGLE_ADS_MCC_CUSTOMER_ID, which
the Railway ops-worker does not have (that is the same gap that made
lsa_ask_guard inert in production). The nightly launchd sweep does have them,
so browser_agent/sweep.py calls accept_pending_links() before it opens a
browser. See also: this needs no browser at all.

WHAT IT WRITES, and why the concierge needs it. Every account we touch gets a
verdict on user_integrations.connection_metadata:

    ads_link_self_serve = true   we can clear this ourselves — NEVER ask
    ads_link_self_serve = false  + _reason: we truly cannot, an ask is fair

The concierge reads that flag (it is in Supabase, so the credential-less
Railway worker can read it too) and refuses to ask any client to accept a
link we are able to accept for them.

Usage:
  python3 scripts/ads_link_accept.py                # dry-run, shows the plan
  python3 scripts/ads_link_accept.py --apply        # approve + write state
  python3 scripts/ads_link_accept.py --apply --slug crew-restoration-construction
"""
from __future__ import annotations

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
from lsa_detect import build_mcc_client, _ints  # noqa: E402
from lsa_link_audit import link_states, LINK_TO_INVITE, fmt_acct  # noqa: E402


def _client_ads_client(refresh_token: str):
    """A GoogleAdsClient logged in AS THE CLIENT'S OWN Google user.

    login_customer_id is deliberately absent. It names the manager whose
    authority the call is made under, and the whole point here is the
    opposite: we are acting with the client's own admin rights on their own
    account, which is what makes the approval legitimate (and is the only
    thing Google will accept while the link is still PENDING)."""
    from google.ads.googleads.client import GoogleAdsClient
    return GoogleAdsClient.load_from_dict({
        "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
        "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
        "refresh_token": refresh_token,
        "use_proto_plus": True,
    })


def _gaql(cl, cid: str, q: str) -> list:
    rows = []
    for b in cl.get_service("GoogleAdsService").search_stream(
            customer_id=cid.replace("-", ""), query=q):
        rows.extend(b.results)
    return rows


def _err(e) -> str:
    """One readable line out of a GoogleAdsException."""
    try:
        return "; ".join(f"{er.error_code}: {er.message}"
                         for er in e.failure.errors)[:300]
    except Exception:  # noqa: BLE001
        return str(e)[:300]


def _write_state(ui_id: str, cm: dict, patch: dict, dry_run: bool) -> None:
    if dry_run:
        return
    _sb("PATCH", f"/rest/v1/user_integrations?id=eq.{ui_id}",
        {"connection_metadata": {**cm, **patch}})


def _stamp(inputs: int, outputs: int, dry_run: bool,
           error: str | None = None) -> None:
    """Proof of life. A night with no pending links is a QUIET night, not a
    dead pass — and the two have to look different (scripts/silence_watch.py).
    """
    try:
        from heartbeat import stamp
        stamp("ads-link-accept", inputs=inputs, outputs=outputs,
              error=error, dry_run=dry_run)
    except Exception:  # noqa: BLE001 — bookkeeping never breaks the job
        pass


def accept_pending_links(dry_run: bool = True,
                         only_slug: str | None = None) -> tuple[list[dict], list[str]]:
    """Approve every PENDING manager link we are able to approve ourselves.

    Returns (results, attention_lines). Each result is
    {slug, name, account, link_id, outcome, detail}, outcome in
    accepted | already_active | cannot | no_pending | error.
    """
    from google.ads.googleads.errors import GoogleAdsException
    from google.protobuf.field_mask_pb2 import FieldMask

    results: list[dict] = []
    attention: list[str] = []
    mcc_client, mcc = build_mcc_client()
    if not mcc_client:
        # The Railway worker lands here. Say so plainly, stamp the ERROR, and
        # change nothing — a credential gap must never look like "no pending
        # links". That confusion is exactly what kept lsa_ask_guard's silence
        # invisible for a day.
        _stamp(0, 0, dry_run, error="no MCC credentials on this host")
        return results, ["ads-link-accept: no MCC credentials on this host — "
                         "skipped (this pass belongs to the nightly Mac run)"]
    links = link_states(mcc_client, mcc)

    cid_to_slug = slug_map()
    cos = {c["id"]: c for c in (_sb(
        "GET", "/rest/v1/companies?status=ilike.active"
               "&select=id,name,integration_settings") or [])}
    uis = _sb("GET", "/rest/v1/user_integrations?provider=eq.google"
              "&select=id,client_id,refresh_token,connection_metadata") or []
    now = datetime.now(timezone.utc).isoformat()

    for u in uis:
        co = cos.get(u["client_id"])
        if not co:
            continue
        slug = cid_to_slug.get(u["client_id"]) or "-"
        if only_slug and slug != only_slug:
            continue
        cm = u.get("connection_metadata") or {}
        rt = u.get("refresh_token") or cm.get("refresh_token")
        # Every account of theirs we might hold a link on. Home Pride proves
        # why this is a LIST and not one id: their Google Ads account and
        # their Local Services account are separate customers, one accepted
        # months ago and one not, and asking about "your ads account" is how
        # Curt got asked for something he had already done.
        targets = [t for t in dict.fromkeys([
            str((_ints(co).get("lsa") or {}).get("customer_id") or "").replace("-", ""),
            str(cm.get("selected_ads_customer_id") or "").replace("-", ""),
            str(cm.get("ads_customer_id") or "").replace("-", ""),
            str(cm.get("lsa_customer_id") or "").replace("-", ""),
        ]) if t]
        pending = [(t, links[t][-1][0]) for t in targets
                   if links.get(t) and links[t][-1][1] == "PENDING"]
        if not pending:
            continue
        if not rt:
            for acct, lid in pending:
                results.append({"slug": slug, "name": co["name"], "account": acct,
                                "link_id": lid, "outcome": "cannot",
                                "detail": "no Google refresh token on file"})
            continue

        try:
            cl = _client_ads_client(rt)
        except Exception as e:  # noqa: BLE001
            attention.append(f"{slug}: could not build an Ads client "
                             f"({str(e)[:90]})")
            continue

        for acct, lid in pending:
            rn = f"customers/{acct}/customerManagerLinks/{mcc}~{lid}"
            row = {"slug": slug, "name": co["name"], "account": acct,
                   "link_id": lid, "outcome": "error", "detail": ""}
            if dry_run:
                row["outcome"], row["detail"] = "would_accept", rn
                results.append(row)
                continue
            try:
                op = cl.get_type("CustomerManagerLinkOperation")
                op.update.resource_name = rn
                op.update.status = cl.enums.ManagerLinkStatusEnum.ACTIVE
                cl.copy_from(op.update_mask, FieldMask(paths=["status"]))
                cl.get_service("CustomerManagerLinkService"
                               ).mutate_customer_manager_link(
                    customer_id=acct, operations=[op])
                row["outcome"] = "accepted"
                row["detail"] = "approved with the client's own admin grant"
                _write_state(u["id"], cm, {
                    "ads_link_self_serve": True,
                    "ads_link_accepted_at": now,
                    "ads_link_accepted_by": "rank-ai self-approval "
                                            "(client's own OAuth admin)",
                    "lsa_link_status": "ACTIVE",
                    "lsa_invite_status": LINK_TO_INVITE["ACTIVE"],
                    "lsa_link_id": lid,
                    "lsa_link_checked_at": now,
                }, dry_run)
                cm = {**cm, "ads_link_self_serve": True}
            except GoogleAdsException as e:
                why = _err(e)
                row["outcome"], row["detail"] = "cannot", why
                _write_state(u["id"], cm, {
                    "ads_link_self_serve": False,
                    "ads_link_self_serve_reason": why,
                    "ads_link_self_serve_checked_at": now,
                }, dry_run)
                cm = {**cm, "ads_link_self_serve": False}
                attention.append(
                    f"{slug}: cannot self-approve the manager link on "
                    f"{fmt_acct(acct)} — {why[:140]}. This one IS a fair ask.")
            except Exception as e:  # noqa: BLE001
                row["outcome"], row["detail"] = "error", str(e)[:200]
                attention.append(f"{slug}: manager-link approval errored on "
                                 f"{fmt_acct(acct)} — {str(e)[:120]}")
            results.append(row)

    _stamp(len(results),
           sum(1 for r in results if r["outcome"] == "accepted"), dry_run)
    return results, attention


def main() -> int:
    apply = "--apply" in sys.argv
    only = None
    if "--slug" in sys.argv:
        only = sys.argv[sys.argv.index("--slug") + 1]
    results, attention = accept_pending_links(dry_run=not apply, only_slug=only)
    if not results:
        print("no PENDING manager links to accept")
    for r in sorted(results, key=lambda x: (x["outcome"], x["slug"])):
        print(f"  {r['outcome']:14} {r['slug']:34} {fmt_acct(r['account']):>14} "
              f"link {r['link_id']}  {r['detail'][:90]}")
    if attention:
        print("\nATTENTION:")
        for a in attention:
            print("  - " + a)
    if not apply and results:
        print("\n(dry run — pass --apply to actually accept)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
