#!/usr/bin/env python3
"""Agency MANAGER access on every client GBP — invite AND accept, on a schedule.

Why this exists (2026-08-01): Bing Places' GBP import copies only the
listings the agency Google user (contact@restorationai.io) directly manages.
Every client whose GBP is connected through THEIR own Google user is invisible
to Bing until the agency account is added as a manager on the location.

Why it was rebuilt (2026-08-04): the 08-01 version was a MANUAL one-off with
no cron and no scheduler entry, so Reign — who connected Google on 08-03 —
had no invite, therefore no Bing listing, and every future client would have
repeated that silently. It also mis-reported: EVERY client came back
"HTTP 400/404" because the two Google error shapes were never decoded.

THE TWO GOOGLE ERROR SHAPES, decoded (both were being printed raw):

  400 INVALID_ARGUMENT + fieldViolations[0].description
      "This admin has already been invited."
      -> we ALREADY have access (accepted manager) or an invite is
         outstanding. Not a failure. Idempotent no-op.

  404 NOT_FOUND on POST .../admins
      -> the OAuth grant we hold for that client is only a MANAGER on the
         location, and Google does not let a manager add other admins. It is
         NOT a missing location and NOT a transient error. The only fix is
         off-API: the OWNER must add contact@restorationai.io themselves.
         Affected today: HomeLyft, ProRestoration, PuroClean East Las Vegas
         (their grants come from Josiah / Shana / PuroClean corporate, all
         managers). These surface as attention lines, never as silent skips.

ACCEPTED vs PENDING, decoded: while an invitation is outstanding the admins
list carries the invitee's EMAIL ("contact@restorationai.io",
pendingInvitation: true); once accepted Google swaps it for the DISPLAY NAME
("Santino Velci"), so an email match can never prove acceptance. The stable
identity is the ACCOUNT ID — accounts/107860484526695269803 is the agency
account, verified 2026-08-04 across Home Pride / NaRestCo / QCI / Crew.

ACCEPTANCE IS AN API CALL, not a browser click (2026-08-04). The agency's own
GBP account exposes its inbox of invitations:
    GET  /v1/accounts/{agency}/invitations
    POST /v1/accounts/{agency}/invitations/{id}:accept
so the invite->accept loop closes itself with no Gmail step and no browser
profile. Reign's invite was accepted this way on 2026-08-04.

Idempotence: state is re-derived from Google on every run (the admins list is
authoritative) — nothing depends on local bookkeeping. A per-client memo in
ops_kv 'gbp-manager-access' caches confirmed managers for MANAGER_RECHECK_DAYS
so the daily pass stays cheap, and gives the rest of the system (the Bing
card, the ops digest) a readable answer to "do we hold this GBP?".

Scheduled: scripts/client_ops_sync.py ensure_gbp_manager_access() runs it in
the daily 14:00 UTC ops pass (workflow client-ops-sync.yml, itself dispatched
by scripts/ops_scheduler.py). New clients don't wait for that pass — the
POST /gbp-first-sync webhook (api/main.py), which the Google-connect edge
function fires the moment a client connects, invites + accepts inline.

Usage: python3 scripts/gbp_admin_invite.py [--dry-run] [--slug SLUG]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb, slug_map  # noqa: E402
import gbp  # noqa: E402

AGENCY_EMAIL = "contact@restorationai.io"
# The agency's GBP account id. This — not the email — is what an ACCEPTED
# manager entry carries (see the module docstring). Verified 2026-08-04.
AGENCY_ACCOUNT_ID = "107860484526695269803"
ACCT_MGMT = "https://mybusinessaccountmanagement.googleapis.com/v1"
KV_KEY = "gbp-manager-access"
# A confirmed manager is re-verified weekly, not daily — access does not
# evaporate on its own, and the daily pass has 20 clients to get through.
MANAGER_RECHECK_DAYS = 7

# States, in the order they progress:
#   manager        agency account is an accepted MANAGER  -> Bing can import
#   pending        invitation outstanding                 -> accept() closes it
#   owner_must_add our grant is manager-only (404)        -> off-API ask
#   none           no access, invite not sent yet
#   unknown        we could not evaluate (no token/place_id/location)


# --------------------------------------------------------------- agency token
_AGENCY_TOKEN: list = []  # [token, expires_at] — one refresh per process


def agency_token() -> str | None:
    """Access token for the AGENCY Google account itself (not a client's).

    Several user_integrations rows are agency grants — they resolve to
    accounts/107860484526695269803. Any one of them is the agency's own token,
    which is what the invitations inbox requires. We identify it by asking
    Google, never by guessing from the slug."""
    if _AGENCY_TOKEN and _AGENCY_TOKEN[1] > datetime.now(timezone.utc):
        return _AGENCY_TOKEN[0]
    rows = _sb("GET", "/rest/v1/user_integrations?provider=eq.google"
               "&select=client_id,refresh_token,connection_metadata",
               prefer="return=representation") or []
    import os
    cid_, sec_ = (os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
                  os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""))
    for row in rows:
        rt = (row.get("refresh_token")
              or (row.get("connection_metadata") or {}).get("refresh_token"))
        if not rt:
            continue
        try:
            tr = requests.post("https://oauth2.googleapis.com/token", timeout=30,
                               data={"client_id": cid_, "client_secret": sec_,
                                     "refresh_token": rt,
                                     "grant_type": "refresh_token"})
            if not tr.ok:
                continue
            tok = tr.json()["access_token"]
            ar = requests.get(f"{ACCT_MGMT}/accounts", timeout=30,
                              headers={"Authorization": f"Bearer {tok}"})
            if not ar.ok:
                continue
            if any(a.get("name", "").endswith(AGENCY_ACCOUNT_ID)
                   for a in (ar.json().get("accounts") or [])):
                _AGENCY_TOKEN[:] = [tok, datetime.now(timezone.utc)
                                    + timedelta(minutes=45)]
                return tok
        except Exception:  # noqa: BLE001 — try the next grant
            continue
    return None


# ------------------------------------------------------------------ inspection
def _location_for(cid: str, slug: str, tok: str) -> str | None:
    """'locations/{id}' for this client's GBP, or None."""
    place = gbp._place_id_from_connection(cid)
    try:
        brand = json.loads((ROOT / "clients" / slug / "plan-input.json")
                           .read_text()).get("brand", {})
        place = brand.get("place_id") or place
    except Exception:
        pass
    if not place:
        return None
    loc = gbp.find_location(tok, place)
    if not loc:
        return None
    return "locations/" + loc["name"].split("locations/")[-1]


def agency_state(admins: list[dict]) -> str:
    """'manager' | 'pending' | 'none' from a location's admins list."""
    for a in admins:
        if AGENCY_ACCOUNT_ID in (a.get("account") or ""):
            return "manager"
    for a in admins:
        if AGENCY_EMAIL in (a.get("admin") or "").lower():
            return "pending"
    return "none"


def _invite_error(resp) -> str:
    """Decode Google's two failure shapes into something a human can act on."""
    try:
        err = resp.json().get("error", {})
        viol = (err.get("details") or [{}])[0].get("fieldViolations") or []
        desc = (viol[0].get("description") if viol else "") or ""
    except Exception:  # noqa: BLE001
        desc = ""
    if resp.status_code == 400 and "already been invited" in desc.lower():
        return "already"
    if resp.status_code == 404:
        return "owner_must_add"
    return f"http_{resp.status_code}"


# ------------------------------------------------------------------ acceptance
def accept_pending_invitations(dry_run: bool = False) -> list[dict]:
    """Accept every invitation sitting in the agency account's inbox.

    Covers invites this script just sent AND any a client sent by hand — the
    reason nothing here needs a browser or a Gmail read."""
    tok = agency_token()
    if not tok:
        return [{"error": "no agency Google grant available — cannot accept "
                          "invitations (check user_integrations provider=google)"}]
    hdr = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    try:
        r = requests.get(f"{ACCT_MGMT}/accounts/{AGENCY_ACCOUNT_ID}/invitations",
                         headers=hdr, timeout=30)
        r.raise_for_status()
        invites = r.json().get("invitations") or []
    except Exception as e:  # noqa: BLE001
        return [{"error": f"invitations list failed: {str(e)[:120]}"}]
    out: list[dict] = []
    for inv in invites:
        tgt = inv.get("targetLocation") or {}
        rec = {"name": inv.get("name"), "location": tgt.get("locationName"),
               "place_id": tgt.get("placeId"), "role": inv.get("role")}
        if dry_run:
            rec["result"] = "would accept"
            out.append(rec)
            continue
        try:
            ar = requests.post(f"{ACCT_MGMT}/{inv['name']}:accept",
                               headers=hdr, json={}, timeout=30)
            rec["result"] = "accepted" if ar.ok else f"HTTP {ar.status_code}"
        except Exception as e:  # noqa: BLE001
            rec["result"] = f"error {str(e)[:80]}"
        out.append(rec)
    return out


# ----------------------------------------------------------------------- memo
def _load_memo() -> dict:
    try:
        rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{KV_KEY}&select=v",
                   prefer="return=representation") or []
        return (rows[0].get("v") or {}) if rows else {}
    except Exception:  # noqa: BLE001
        return {}


def _save_memo(memo: dict, dry_run: bool) -> None:
    if dry_run:
        return
    try:
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k", {"k": KV_KEY, "v": memo},
            prefer="resolution=merge-duplicates")
    except Exception as e:  # noqa: BLE001
        print(f"  [gbp-manager] memo write failed: {str(e)[:80]}")


def manager_slugs() -> set[str]:
    """Slugs where the agency is a confirmed GBP manager, per the memo.

    Read by the Bing side of the setup ledger: a client we do not manage on
    Google cannot appear in Bing's GBP import, and that is the honest reason
    to show on the card."""
    return {s for s, v in _load_memo().items()
            if (v or {}).get("state") == "manager"}


# ------------------------------------------------------------------- main pass
def ensure_agency_manager(dry_run: bool = False,
                          cid_to_slug: dict | None = None,
                          only_company_ids: list[str] | None = None,
                          force: bool = False) -> tuple[dict, list[str]]:
    """Invite + accept agency manager access fleet-wide. Idempotent.

    Returns ({slug: {state, note, changed}}, attention_lines)."""
    cid_to_slug = cid_to_slug or slug_map()
    memo = _load_memo()
    now = datetime.now(timezone.utc)
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
              "&select=id,name", prefer="return=representation") or []
    if only_company_ids:
        cos = [c for c in cos if c["id"] in set(only_company_ids)]
    results: dict[str, dict] = {}
    attention: list[str] = []
    sent_this_run = False

    for co in cos:
        cid, slug = co["id"], cid_to_slug.get(co["id"])
        if not slug:
            continue
        prev = memo.get(slug) or {}
        # Confirmed managers are re-verified weekly, not on every daily pass.
        if not force and prev.get("state") == "manager":
            try:
                seen = datetime.fromisoformat(
                    (prev.get("checked_at") or "").replace("Z", "+00:00"))
                if now - seen < timedelta(days=MANAGER_RECHECK_DAYS):
                    results[slug] = {"state": "manager", "changed": False,
                                     "cached": True,
                                     "note": "cached (verified "
                                             f"{str(prev.get('checked_at'))[:10]})"}
                    continue
            except ValueError:
                pass

        tok = gbp.get_access_token(cid)
        if not tok:
            results[slug] = {"state": "unknown", "changed": False,
                             "note": "no Google grant on file"}
            continue
        try:
            loc_name = _location_for(cid, slug, tok)
        except Exception as e:  # noqa: BLE001
            results[slug] = {"state": "unknown", "changed": False,
                             "note": f"location lookup failed ({str(e)[:60]})"}
            continue
        if not loc_name:
            results[slug] = {"state": "unknown", "changed": False,
                             "note": "no place_id / no GBP location"}
            continue

        hdr = {"Authorization": f"Bearer {tok}"}
        try:
            ar = requests.get(f"{ACCT_MGMT}/{loc_name}/admins", headers=hdr,
                              timeout=30)
            admins = ar.json().get("admins") or [] if ar.ok else []
        except Exception as e:  # noqa: BLE001
            results[slug] = {"state": "unknown", "changed": False,
                             "note": f"admins read failed ({str(e)[:60]})"}
            continue
        state = agency_state(admins)

        if state == "none":
            if dry_run:
                results[slug] = {"state": "none", "changed": False,
                                 "note": "WOULD invite", "location": loc_name}
                continue
            r = requests.post(f"{ACCT_MGMT}/{loc_name}/admins",
                              headers={**hdr, "Content-Type": "application/json"},
                              json={"admin": AGENCY_EMAIL, "role": "MANAGER"},
                              timeout=30)
            if r.ok:
                state, note, sent_this_run = "pending", "invited", True
            else:
                kind = _invite_error(r)
                if kind == "already":
                    # Google and the admins list disagree; Google wins.
                    state, note = "pending", "invite already outstanding"
                elif kind == "owner_must_add":
                    state = "owner_must_add"
                    note = ("our Google grant for this client is manager-only, "
                            "so Google refuses to let us add admins")
                    attention.append(
                        f"{slug}: GBP manager access NOT possible via API — the "
                        f"OWNER must add {AGENCY_EMAIL} as a manager at "
                        "business.google.com (until then this client cannot "
                        "appear in Bing's GBP import)")
                else:
                    state, note = "unknown", f"invite failed ({kind})"
            results[slug] = {"state": state, "changed": state != prev.get("state"),
                             "note": note, "location": loc_name}
        else:
            results[slug] = {"state": state,
                             "changed": state != prev.get("state"),
                             "note": {"manager": "already a manager",
                                      "pending": "invite outstanding"}[state],
                             "location": loc_name}

    # One acceptance sweep closes every outstanding invite, including the ones
    # just sent. Skipped only when nothing is pending and nothing was sent.
    accepted: list[dict] = []
    if any(v["state"] == "pending" for v in results.values()) or sent_this_run:
        accepted = accept_pending_invitations(dry_run)
        for a in accepted:
            if a.get("error"):
                attention.append(f"GBP invites: {a['error']}")
                continue
            print(f"  [gbp-manager] accept {a.get('location')}: {a.get('result')}")
        if not dry_run and any(a.get("result") == "accepted" for a in accepted):
            # Re-read the admins list for everything that was pending — an
            # accepted invite must show as 'manager', not stay hopeful.
            for slug, v in results.items():
                if v["state"] != "pending" or not v.get("location"):
                    continue
                cid = next((k for k, s in cid_to_slug.items() if s == slug), None)
                tok = gbp.get_access_token(cid) if cid else None
                if not tok:
                    continue
                try:
                    ar = requests.get(f"{ACCT_MGMT}/{v['location']}/admins",
                                      headers={"Authorization": f"Bearer {tok}"},
                                      timeout=30)
                    if ar.ok and agency_state(ar.json().get("admins") or []) == "manager":
                        v["state"], v["note"] = "manager", "invited and accepted"
                        v["changed"] = True
                except Exception:  # noqa: BLE001
                    pass

    # Memo + work log. A client-readable line only on a real transition — the
    # daily no-op pass must not manufacture "work".
    for slug, v in results.items():
        # A cached row was never re-checked this run — re-stamping checked_at
        # would make the weekly re-verification never come due, and would
        # overwrite the real note with "cached (...)".
        if v.get("cached"):
            continue
        if v["state"] in ("manager", "pending", "owner_must_add", "none"):
            memo[slug] = {"state": v["state"],
                          "checked_at": now.isoformat(),
                          "note": v.get("note")}
        if v.get("changed") and v["state"] == "manager" and not dry_run:
            cid = next((k for k, s in cid_to_slug.items() if s == slug), None)
            try:
                from work_log import work_log
                work_log(cid, "citations", "gbp-manager-access",
                         "Rank AI was added as a manager on your Google "
                         "Business Profile — this is what lets us publish your "
                         "listing to Bing Places and keep both in sync.",
                         evidence={"slug": slug, "role": "MANAGER",
                                   "agency_account": AGENCY_ACCOUNT_ID},
                         source="gbp_admin_invite.py")
            except Exception:  # noqa: BLE001 — fail-open
                pass
    _save_memo(memo, dry_run)

    pending_left = [s for s, v in results.items() if v["state"] == "pending"]
    if pending_left:
        attention.append("GBP manager invites still unaccepted: "
                         + ", ".join(sorted(pending_left)))
    return results, attention


def main() -> int:
    dry = "--dry-run" in sys.argv
    only = None
    if "--slug" in sys.argv:
        want = sys.argv[sys.argv.index("--slug") + 1]
        smap = slug_map()
        only = [cid for cid, s in smap.items() if s == want]
        if not only:
            print(f"{want}: not in the slug map")
            return 1
    results, attention = ensure_agency_manager(
        dry_run=dry, only_company_ids=only, force="--force" in sys.argv)
    order = ["manager", "pending", "owner_must_add", "none", "unknown"]
    for st in order:
        rows = {s: v for s, v in results.items() if v["state"] == st}
        if not rows:
            continue
        print(f"\n{st.upper()} ({len(rows)}):")
        for s, v in sorted(rows.items()):
            mark = " *" if v.get("changed") else "  "
            print(f" {mark}{s}: {v['note']}")
    if attention:
        print("\nATTENTION:")
        for a in attention:
            print("  - " + a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
