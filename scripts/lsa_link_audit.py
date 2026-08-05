#!/usr/bin/env python3
"""lsa_link_audit.py — who has actually ACCEPTED our MCC access invite.

Sending the Local Services / Ads access invite is easy (the app's
lsa-request-access edge function POSTs a PENDING customerClientLink from
MCC 2018844125). Knowing whether the client ever CLICKED ACCEPT was not:
nothing read the link back, so `connection_metadata.lsa_invite_status`
stayed "invited" forever and Monica could neither retire the ask nor
confirm it. On 2026-08-04 Greg Arianoff (PuroClean East Las Vegas) said
"Google should be linked" and we had no way to check — this is that check.

Ground truth is `customer_client_link` on the manager account:

    PENDING   invite sent, client has NOT accepted   -> the ask stays open
    ACTIVE    accepted, we can manage the account    -> retire the ask
    CANCELED  withdrawn (every resend cancels the    -> superseded by the
              old pending link before re-creating)      newer link id
    REFUSED   client declined
    (absent)  no invite was ever sent from our MCC

Per company we check the two account ids we might care about: the one the
client picked during the connect flow (connection_metadata
.selected_ads_customer_id) and the one detection stored
(integration_settings.lsa.customer_id). When those disagree AND the stored
one has no link while the selected one does, detection grabbed the wrong
account (see the "WHOSE ACCOUNT IS IT" note in lsa_detect.py) — reported
as MISMATCH, and rewritten only under --fix-identity.

Usage:
  python3 scripts/lsa_link_audit.py                 # table only
  python3 scripts/lsa_link_audit.py --apply         # + write lsa_invite_status
  python3 scripts/lsa_link_audit.py --apply --fix-identity
"""
from __future__ import annotations

import json
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

from client_ops_sync import _sb  # noqa: E402
from ads_manager import gaql  # noqa: E402
from lsa_detect import build_mcc_client, _ints  # noqa: E402

# invite_status vocabulary already in connection_metadata ("invited",
# "accepted" — see National Restoration Construction) kept as-is.
LINK_TO_INVITE = {"ACTIVE": "accepted", "PENDING": "invited",
                  "CANCELED": "canceled", "REFUSED": "refused"}


def link_states(client, mcc: str) -> dict[str, list[tuple[int, str]]]:
    """client_customer id -> [(manager_link_id, status), ...] oldest first.

    A resend leaves the old CANCELED row behind, so only the highest link id
    describes the account's current state.
    """
    rows = gaql(client, mcc, """
        SELECT customer_client_link.client_customer,
               customer_client_link.manager_link_id,
               customer_client_link.status
        FROM customer_client_link""")
    out: dict[str, list[tuple[int, str]]] = {}
    for r in rows:
        li = r.customer_client_link
        out.setdefault(li.client_customer.split("/")[-1], []).append(
            (int(li.manager_link_id), li.status.name))
    return {k: sorted(v) for k, v in out.items()}


def main() -> int:
    apply = "--apply" in sys.argv
    fix_identity = "--fix-identity" in sys.argv

    client, mcc = build_mcc_client()
    if not client:
        print("no MCC credentials — cannot audit")
        return 1
    links = link_states(client, mcc)
    print(f"MCC {mcc}: {len(links)} account(s) with a manager link\n")

    cos = {c["id"]: c for c in (_sb(
        "GET", "/rest/v1/companies?status=ilike.active"
               "&select=id,name,integration_settings") or [])}
    uis = _sb("GET", "/rest/v1/user_integrations?provider=eq.google"
              "&select=id,client_id,connection_metadata") or []

    rows, mismatches = [], []
    for u in uis:
        co = cos.get(u["client_id"])
        if not co:
            continue
        cm = u.get("connection_metadata") or {}
        sel = str(cm.get("selected_ads_customer_id")
                  or cm.get("ads_customer_id") or "").replace("-", "")
        stored = str((_ints(co).get("lsa") or {}).get("customer_id")
                     or "").replace("-", "")
        target = stored or sel
        # Detection wrote an account we were never invited to while the
        # client's own selected account IS linked -> detection was wrong.
        if stored and sel and stored != sel and stored not in links and sel in links:
            mismatches.append((co, u, stored, sel))
            target = sel
        cur = links.get(target)
        status = cur[-1][1] if cur else "NO INVITE"
        link_id = cur[-1][0] if cur else None
        rows.append((co["name"], target, status, link_id,
                     cm.get("lsa_invite_status"), u, cm, cur))

    w = max((len(r[0]) for r in rows), default=10)
    print(f"{'client':{w}}  {'lsa account':>12}  {'MCC LINK':<10} "
          f"{'link id':<11} stored status  history")
    for name, acct, status, link_id, was, _u, _cm, cur in sorted(rows):
        hist = " ".join(f"{i}:{s}" for i, s in (cur or [])) or "-"
        print(f"{name:{w}}  {acct or '-':>12}  {status:<10} "
              f"{str(link_id or '-'):<11} {str(was or '-'):<14} {hist}")

    if mismatches:
        print("\nIDENTITY MISMATCH — detection stored an account we were "
              "never invited to, while the client's own selected account IS "
              "linked:")
        for co, _u, stored, sel in mismatches:
            print(f"  {co['name']}: lsa.customer_id={stored} -> should be {sel}")

    now = datetime.now(timezone.utc).isoformat()
    if apply:
        n = 0
        for name, acct, status, link_id, was, u, cm, _cur in rows:
            want = LINK_TO_INVITE.get(status)
            if not want or (was == want and cm.get("lsa_link_id") == link_id):
                continue
            cm = {**cm, "lsa_invite_status": want, "lsa_link_status": status,
                  "lsa_link_id": link_id, "lsa_link_checked_at": now}
            _sb("PATCH", f"/rest/v1/user_integrations?id=eq.{u['id']}",
                {"connection_metadata": cm})
            print(f"  wrote {name}: lsa_invite_status {was!r} -> {want!r}")
            n += 1
        print(f"\n{n} integration row(s) updated")

    if fix_identity:
        for co, _u, stored, sel in mismatches:
            ints = _ints(co)
            lsa = dict(ints.get("lsa") or {})
            lsa.update({"customer_id": sel, "corrected_from": stored,
                        "corrected_at": now})
            ints["lsa"] = lsa
            _sb("PATCH", f"/rest/v1/companies?id=eq.{co['id']}",
                {"integration_settings": ints})
            print(f"  fixed {co['name']}: lsa.customer_id {stored} -> {sel}")

    if not (apply or fix_identity):
        print("\n(read-only — pass --apply and/or --fix-identity to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
