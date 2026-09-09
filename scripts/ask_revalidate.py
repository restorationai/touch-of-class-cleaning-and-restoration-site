#!/usr/bin/env python3
"""Send-time revalidation of seeded client asks (Santino 2026-08-12).

The ledger passes seed client_input asks from derived checks (no logo in the
branding bucket, empty companies-row NAP, preview never shared, no domain
access) and RETIRE them the same way — but the ledger sweeps every ~4h, so an
ask can sit satisfied-but-open for hours between passes. The concierge's
compose path calls ask_still_valid() at SEND TIME: it re-runs the exact
derived check that seeded the row, using setup_ledger's own helper functions
(imported, never copied), so the checker and the seeder can never disagree.

    ask_still_valid(company_id, plan_row) -> bool | None
        False -> the ask is STALE (the seed condition is already satisfied);
                 the reason is stashed on plan_row["_stale_reason"]
        True  -> still needed, ask away
        None  -> unknown seed type — this module has no opinion

Covered seeds (the four derived-check asks setup_ledger maintains):
    citations-logo-{slug}       logo already in the branding bucket / repo
    citations-nap-{slug}        phone + address present on the companies row
    site-preview-feedback-{slug} the preview window is verifiably behind us
    domain-access-{slug} /      domain access already granted (with the
    domain-verify-{slug}        false-green evidence guard) or ns already live

FAIL DIRECTION: every error path returns True (keep the ask). A wrongly
dropped ask is invisible forever; a wrongly kept one is merely re-asked —
same policy as the ledger's own retire logic.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from client_ops_sync import _sb, action_key, slug_map  # noqa: E402

# domain_access_status values that mean the ask is answered — the app board's
# ACCESS_GRANTED set (BuildStagesBoard.tsx). delegate_granted/creds_provided
# additionally require the ledger's mailbox evidence not to contradict them.
_ACCESS_GRANTED = {"granted", "creds_provided", "ns_live", "delegate_granted"}


def seed_kind(company_id: str | None, slug: str | None,
              ak: str | None) -> str | None:
    """Which derived check seeded a row with this action_key, or None.

    Pure function (no network) so selfcheck can pin it offline. The ledger's
    seeds hash through client_ops_sync.action_key(); the preview-share ask is
    the one seed written with a LITERAL key (setup_ledger's preview-share
    heal and ensure_auto_site_build both use f"site-preview-feedback-{slug}").
    """
    if not (company_id and slug and ak):
        return None
    if ak == f"site-preview-feedback-{slug}":
        return "preview"
    if ak.startswith("site-build-blocked-logo"):
        return "logo"
    return {
        action_key(company_id, f"citations-logo-{slug}"): "logo",
        action_key(company_id, f"citations-nap-{slug}"): "nap",
        action_key(company_id, f"domain-access-{slug}"): "domain",
        action_key(company_id, f"domain-verify-{slug}"): "domain",
    }.get(ak)


_LOGO_ASK_TITLE = __import__("re").compile(
    r"(?i)\b(send|upload|share|provide)\b.{0,40}\blogo\b|"
    r"\blogo\b.{0,40}\b(send|upload|share|provide)\b")


def check_kind_by_title(title: str) -> str | None:
    """Fallback identity for asks whose key the map doesn't know (ACS
    2026-09-09: the signup audit seeds logo asks under hashed keys, and
    Aldredo got re-asked for a logo the wizard had already uploaded —
    revalidation returned None on the unknown key). Title text is the
    stable signal across every seeding lane."""
    if title and _LOGO_ASK_TITLE.search(title):
        return "logo"
    return None


def _row_identity(company_id: str, plan_row: dict) -> tuple[str | None, str | None]:
    """(action_key, slug) for the row — from the dict when present, else one
    lookup by id (the concierge's fetch_open_asks doesn't select action_key)."""
    ak = plan_row.get("action_key")
    slug = plan_row.get("rank_ai_slug")
    if not ak:
        rows = _sb("GET", "/rest/v1/marketing_action_plan"
                   f"?id=eq.{plan_row.get('id')}"
                   "&select=action_key,rank_ai_slug&limit=1",
                   prefer="return=representation") or []
        if rows:
            ak = rows[0].get("action_key")
            slug = slug or rows[0].get("rank_ai_slug")
    if not slug:
        slug = slug_map().get(company_id)
    return ak, slug


# ---------------------------------------------------------------- the checks
def _logo_satisfied(cid: str, slug: str) -> str | None:
    """The citations-logo seed condition, re-run: setup_ledger's
    _citations_readiness counts a repo logo OR a branding-bucket logo as
    'we hold it' (Curt/Home Pride 2026-08-08: never ask for what we have)."""
    from setup_ledger import SITES_DIR, _bucket_logo_files
    imgdir = SITES_DIR / slug / "public" / "images"
    if (imgdir / "logo.png").exists() or (imgdir / "logo.webp").exists():
        return f"logo already in the site repo (sites/{slug}/public/images/)"
    files = _bucket_logo_files(cid)
    if files:
        return f"logo already in the branding bucket ({files[-1]})"
    return None


def _nap_satisfied(cid: str) -> str | None:
    """The citations-nap seed condition, re-run: same phone_ok/addr_ok
    derivation as setup_ledger._citations_readiness (address counts as
    present with either a street address or city + ZIP)."""
    rows = _sb("GET", f"/rest/v1/companies?id=eq.{cid}"
               "&select=phone,address,city,postal_code&limit=1",
               prefer="return=representation") or []
    co = rows[0] if rows else {}
    phone_ok = bool((co.get("phone") or "").strip())
    addr_ok = bool((co.get("address") or "").strip()) or bool(
        (co.get("city") or "").strip() and (co.get("postal_code") or "").strip())
    if phone_ok and addr_ok:
        return "companies-row NAP is complete (phone + address on file)"
    return None


def _preview_satisfied(cid: str) -> str | None:
    """The preview-share ask is behind us ONLY when the site is LIVE on the
    real domain (apex_live) — the 'preview' no longer exists as a concept
    and the launch/announcement flow owns the next contact.

    Two near-misses that deliberately do NOT count:
    - build_status=pushed_main: the OPEN preview ask is exactly the
      client-sign-off gate ensure_internal_launch_tasks reads; resolving it
      here would fabricate a sign-off the client never gave and unlock the
      launch seeder (dry-county/mcc/quality-contracting were all in this
      state on 2026-08-12).
    - the link merely having been SENT: boost_preview_share keeps a
      sent-but-unanswered ask alive as a feedback nudge (rank 11) on
      purpose."""
    rows = _sb("GET", f"/rest/v1/marketing_sites?company_id=eq.{cid}"
               "&select=apex_live&limit=1",
               prefer="return=representation") or []
    site = rows[0] if rows else {}
    if site.get("apex_live") is True:
        return "site is LIVE on the real domain — the preview window is over"
    return None


def _domain_satisfied(cid: str) -> str | None:
    """domain-access / domain-verify seeds: stale once access is verifiably
    in hand. Uses setup_ledger._domain_access_row for the status and keeps
    the Crew false-green guard: a delegate_granted/creds_provided that the
    agency mailbox could NOT back up (ledger evidence access_in_hand=False)
    does not silence the ask (Santino 2026-08-05)."""
    from setup_ledger import _domain_access_row
    da = _domain_access_row(cid) or {}
    status = str(da.get("domain_access_status") or "").lower()
    if status not in _ACCESS_GRANTED:
        return None
    if status in ("delegate_granted", "creds_provided"):
        led = _sb("GET", "/rest/v1/marketing_setup_ledger"
                  f"?company_id=eq.{cid}&item_key=eq.domain-access"
                  "&select=evidence&limit=1",
                  prefer="return=representation") or []
        ev = (led[0] if led else {}).get("evidence") or {}
        if ev.get("access_in_hand") is False:
            return None  # human assertion with no invite — ask stays alive
    return f"domain access already in hand (status={status})"


def ask_still_valid(company_id: str, plan_row: dict) -> bool | None:
    """Re-run the derived check that seeded this client_input plan row.

    False = stale (satisfied — reason on plan_row['_stale_reason']),
    True = still needed, None = not a seed this module knows. Never raises
    past itself: any error keeps the ask (see FAIL DIRECTION above)."""
    try:
        ak, slug = _row_identity(company_id, plan_row)
        kind = seed_kind(company_id, slug, ak)
        if kind is None:
            kind = check_kind_by_title(
                str(plan_row.get("title") or plan_row.get("text") or ""))
        if kind is None:
            return None
        why = {
            "logo": lambda: _logo_satisfied(company_id, slug),
            "nap": lambda: _nap_satisfied(company_id),
            "preview": lambda: _preview_satisfied(company_id),
            "domain": lambda: _domain_satisfied(company_id),
        }[kind]()
        if why:
            plan_row["_stale_reason"] = why
            return False
        return True
    except Exception:  # noqa: BLE001 — never drop an ask on an error
        return True


def resolve_stale(row_id: str, why: str, dry_run: bool) -> None:
    """Resolve a stale ask and leave the reason on the row (appended to the
    rationale, same survival trick as the concierge's resolve_plan_row — but
    labelled as what it is: a machine check, not a client answer)."""
    if dry_run:
        print(f"    [dry-run] would resolve stale ask {str(row_id)[:8]}: {why}")
        return
    body: dict = {"status": "resolved"}
    try:
        rows = _sb("GET", f"/rest/v1/marketing_action_plan?id=eq.{row_id}"
                   "&select=rationale", prefer="return=representation") or []
        old = str((rows[0] if rows else {}).get("rationale") or "")
        stamp = datetime.now(timezone.utc).date()
        body["rationale"] = (old + f"\n\nAUTO-RESOLVED ({stamp}) by send-time "
                             f"revalidation: {why}").strip()
    except Exception:  # noqa: BLE001 — bookkeeping never blocks the resolve
        pass
    _sb("PATCH", f"/rest/v1/marketing_action_plan?id=eq.{row_id}", body,
        prefer="return=minimal")


def main() -> int:
    """CLI: report what ask_still_valid would do to every OPEN client ask."""
    from client_ops_sync import load_env
    load_env()
    rows = _sb("GET", "/rest/v1/marketing_action_plan"
               "?action_type=eq.client_input&status=eq.planned"
               "&select=id,company_id,rank_ai_slug,title,action_key",
               prefer="return=representation") or []
    sm = slug_map()
    n_stale = n_valid = n_unknown = 0
    for r in sorted(rows, key=lambda r: sm.get(r.get("company_id"), "~")):
        verdict = ask_still_valid(r.get("company_id"), r)
        label = sm.get(r.get("company_id")) or r.get("company_id")
        if verdict is False:
            n_stale += 1
            print(f"  STALE  {label}: {r.get('title', '')[:70]!r} — "
                  f"{r.get('_stale_reason')}")
        elif verdict is True:
            n_valid += 1
            print(f"  valid  {label}: {r.get('title', '')[:70]!r}")
        else:
            n_unknown += 1
    print(f"\n  {len(rows)} open ask(s): {n_stale} stale, {n_valid} still "
          f"valid, {n_unknown} unknown-seed (untouched)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
