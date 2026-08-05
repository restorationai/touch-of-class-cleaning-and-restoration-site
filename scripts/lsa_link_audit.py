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
    INACTIVE  was accepted, later came apart         -> they DID accept once
    REFUSED   client declined
    (absent)  no invite was ever sent from our MCC

CANCELED and INACTIVE are not interchangeable and the difference decides the
tone of the ask: a CANCELED predecessor only means an old invite email went
dead, while INACTIVE means they really did accept once. Telling a client
"you accepted before, sorry" off a CANCELED row would be a false apology.

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
                  "CANCELED": "canceled", "REFUSED": "refused",
                  "INACTIVE": "unlinked"}


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


def fmt_acct(a: str) -> str:
    return f"{a[:3]}-{a[3:6]}-{a[6:]}" if len(a) == 10 and a.isdigit() else (a or "-")


def _ts(s) -> float | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def created_estimator(anchors: list[tuple[int, float]]):
    """link_id -> approximate creation date.

    customer_client_link carries no timestamp, but manager_link_id is issued
    roughly sequentially Google-wide, so our own recorded lsa_invite_at values
    calibrate a line through it. Rates observed 21k-32k ids/hour, so treat the
    output as +/- a couple of days — enough to tell "he accepted that one
    months ago" from "that went out last night", which is the whole question
    when a client says "I already did this".
    """
    if len(anchors) < 2:
        return lambda _lid: None
    n = len(anchors)
    sx = sum(a for a, _ in anchors)
    sy = sum(t for _, t in anchors)
    sxx = sum(a * a for a, _ in anchors)
    sxy = sum(a * t for a, t in anchors)
    den = n * sxx - sx * sx
    if not den:
        return lambda _lid: None
    m = (n * sxy - sx * sy) / den
    b = (sy - m * sx) / n

    def est(lid: int):
        try:
            return datetime.fromtimestamp(m * lid + b, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    return est


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
        # OTHER accounts of theirs that we are ALSO linked to. This is the
        # column that decides apology vs nudge: Curt Eddy answered "I think I
        # already did this a long time ago" because he HAD — for Home Pride's
        # Google Ads account (2347693633, ACTIVE since ~May), while the
        # pending invite is for their separate Local Services account.
        other = [(a, links[a][-1][1], nm) for a, nm in
                 ((sel, cm.get("selected_ads_account_name") or "Google Ads"),)
                 if a and a != target and a in links]
        rows.append((co["name"], target, status, link_id,
                     cm.get("lsa_invite_status"), u, cm, cur, other))

    # Calibrate link-id -> date from the invites whose send time we recorded.
    # Only accounts with exactly ONE link are trustworthy anchors: a resend
    # creates a second link but the app never restamps lsa_invite_at, so on a
    # resent account that timestamp describes the CANCELED predecessor.
    anchors = []
    for _n, _a, status, link_id, _w, _u, cm, cur, _o in rows:
        t = _ts(cm.get("lsa_invite_at"))
        if link_id and t and status == "PENDING" and len(cur or []) == 1:
            anchors.append((link_id, t))
    est = created_estimator(sorted(set(anchors)))

    def created(link_id, cm, exact_ok) -> str:
        if not link_id:
            return "-"
        t = _ts(cm.get("lsa_invite_at"))
        if exact_ok and t:
            return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
        d = est(link_id)
        return f"~{d:%Y-%m-%d}" if d else "?"

    w = max((len(r[0]) for r in rows), default=10)
    print(f"{'client':{w}}  {'lsa account':>14}  {'MCC LINK':<10} "
          f"{'created':<11} {'prior link on this account':<28} also linked")
    for name, acct, status, link_id, _was, _u, cm, cur, other in sorted(rows):
        exact = len(cur or []) == 1 and status == "PENDING"
        prior = " ".join(f"{s}" for _i, s in (cur or [])[:-1]) or "—"
        if prior != "—":
            prior += f" (~{est((cur or [])[0][0]):%Y-%m-%d})" if est((cur or [])[0][0]) else ""
        also = ", ".join(f"{fmt_acct(a)} {st} ({nm})" for a, st, nm in other) or "—"
        print(f"{name:{w}}  {fmt_acct(acct):>14}  {status:<10} "
              f"{created(link_id, cm, exact):<11} {prior:<28} {also}")
    print("\ncreated: exact where we recorded the send; ~ = interpolated from "
          "the manager_link_id sequence (+/- a couple of days).")

    if mismatches:
        print("\nIDENTITY MISMATCH — detection stored an account we were "
              "never invited to, while the client's own selected account IS "
              "linked:")
        for co, _u, stored, sel in mismatches:
            print(f"  {co['name']}: lsa.customer_id={stored} -> should be {sel}")

    now = datetime.now(timezone.utc).isoformat()
    if apply:
        n = 0
        # UNPACK BY LENGTH, NOT BY HABIT (2026-08-05). e26a8181 added a ninth
        # column ("also linked") to every row and updated the print loop but
        # not this one, so `--apply` had been raising ValueError on its first
        # iteration ever since — silently, because every caller runs it with
        # `|| true`. This is the ONLY writer of connection_metadata's link
        # state, and the concierge's ask guard now reads that state when it
        # cannot reach the Ads API (the Railway worker never can), so a
        # crash here means Monica asking clients for access we already hold.
        for name, _acct, status, link_id, was, u, cm, _cur, _other in rows:
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
        # The link state also belongs on the company row, where the app and
        # the ledger read integration_settings.lsa. RestorationXpress had an
        # ACTIVE link recorded in user_integrations and NOTHING in
        # integration_settings, so anything reading only the company row saw
        # an unreconciled account (Santino, 2026-08-05).
        n2 = 0
        for name, acct, status, link_id, _was, u, _cm, _cur, _other in rows:
            co = cos.get(u["client_id"])
            if not co or status == "NO INVITE":
                continue
            ints = _ints(co)
            lsa = dict(ints.get("lsa") or {})
            if (lsa.get("link_status") == status
                    and lsa.get("link_id") == link_id):
                continue
            lsa.update({"customer_id": lsa.get("customer_id") or acct,
                        "link_status": status, "link_id": link_id,
                        "invite_status": LINK_TO_INVITE.get(status),
                        "link_checked_at": now})
            ints["lsa"] = lsa
            _sb("PATCH", f"/rest/v1/companies?id=eq.{co['id']}",
                {"integration_settings": ints})
            print(f"  reconciled {name}: integration_settings.lsa.link_status "
                  f"-> {status}")
            n2 += 1
        print(f"{n2} company row(s) reconciled")

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
