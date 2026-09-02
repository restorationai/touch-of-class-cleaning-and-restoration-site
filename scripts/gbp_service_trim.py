#!/usr/bin/env python3
"""
gbp_service_trim.py -- execute APPROVED "dead weight services" cards
(System: GBP).

gbp_site_parity.py seeds ONE consolidated SUGGESTION card per client
(marketing_action_plan, seed key gbp-parity-trim) listing the GBP services
with no matching site page and no search demand. The card is a human
decision: nothing is removed until someone flips it to 'approved' in the
app. This script is the missing executor for that approval:

  1. Find approved gbp-parity-trim cards (action_key is the sha256 seed hash,
     recomputed here per company so an approved card can never be confused
     with any other gbp_fix card).
  2. Parse the exact service names out of the card's rationale. The seeder
     writes one line per service in a fixed shape:
         - "Odor Control & Deodorization" (0/mo, Duplicate of Odor Control)
     Only lines matching that shape are trusted; a card whose rationale
     yields no names is refused.
  3. Exact-match each name against the LIVE listing's serviceItems display
     names (gbp._item_name; whitespace-stripped, case-sensitive). If ANY
     named service has no exact match, the whole card is refused -- nothing
     is partially executed -- and a [TODO-SANTINO] ops note is filed so a
     human reconciles the card with the listing.
  4. Remove ONLY the matched items via the full-list PATCH minus the trims
     (validateOnly preflight first, updateMask=serviceItems). Every other
     item travels untouched -- order, descriptions, structured/free-form
     shape. Categories are NEVER touched.
  5. Re-read the listing and verify the count dropped by exactly the number
     removed and none of the trimmed names remain.
  6. Log ONE plain-English marketing_gbp_changes row + one marketing_work_log
     line, and flip the card to 'resolved' with an executed note appended to
     its rationale.

Paused/cancelled clients are skipped (same companies.status vocabulary as
gbp._clients). Dry-run is the default; nothing is written without --apply.

Usage:
    python3 scripts/gbp_service_trim.py --all                 # dry-run report
    python3 scripts/gbp_service_trim.py --all --apply         # weekly cron
    python3 scripts/gbp_service_trim.py --company CO-1786411719310 --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gbp  # noqa: E402 -- token/location/log helpers (import only, never edited)
from client_ops_sync import _sb as ops_sb  # noqa: E402
from client_ops_sync import action_key  # noqa: E402
from gbp_service_rebalance import _load_location  # noqa: E402
from work_log import work_log  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

TRIM_SEED = "gbp-parity-trim"   # gbp_site_parity.seed_trim_card's action_key seed
# The exact line shape seed_trim_card writes: - "Name" (12/mo, reason)
SERVICE_LINE = re.compile(r'^\s*-\s+"(.+?)"\s+\(\d+/mo', re.M)
INACTIVE = {"paused", "cancelled", "canceled", "churned", "inactive", "archived", "suspended"}


# --------------------------------------------------------------------------- #
# approved-card discovery
# --------------------------------------------------------------------------- #
def approved_cards(company: str | None) -> list[dict]:
    """Approved marketing_action_plan rows whose action_key IS this company's
    gbp-parity-trim key (recomputed, never pattern-matched on title text)."""
    q = ("/rest/v1/marketing_action_plan?status=eq.approved"
         "&action_type=eq.gbp_fix"
         "&select=id,company_id,rank_ai_slug,target,title,rationale,action_key")
    if company:
        q += f"&company_id=eq.{company}"
    rows = ops_sb("GET", q, prefer="return=representation") or []
    return [r for r in rows
            if r.get("action_key") == action_key(r["company_id"], TRIM_SEED)]


def parse_services(rationale: str) -> list[str]:
    """The exact service names from the card body, deduped, order kept."""
    out, seen = [], set()
    for name in SERVICE_LINE.findall(rationale or ""):
        n = name.strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def company_status(cid: str) -> str:
    rows = gbp._sb(f"companies?id=eq.{cid}&select=status")
    return str((rows[0].get("status") if rows else "") or "").strip().lower()


def card_slug(card: dict) -> str | None:
    slug = card.get("rank_ai_slug")
    if slug:
        return slug
    target = str(card.get("target") or "")
    if target.startswith("gbp:"):
        return target[4:] or None
    return None


# --------------------------------------------------------------------------- #
# refusal path: [TODO-SANTINO] ops note, deduped per card while one is open
# --------------------------------------------------------------------------- #
def file_blocked_note(card: dict, slug: str, reason: str, apply: bool) -> None:
    cid = card["company_id"]
    short_id = card["id"][:8]
    body = (
        f"[TODO-SANTINO] GBP SERVICE TRIM BLOCKED for {slug} "
        f"(approved card {short_id}): {reason} Nothing was removed. "
        "Reconcile the card with the live listing (Edit profile > Services), "
        "then re-run: python3 scripts/gbp_service_trim.py "
        f"--company {cid} --apply")
    if not apply:
        print(f"     [dry-run] would file ops note: {body[:110]}...")
        return
    try:
        existing = ops_sb(
            "GET", "/rest/v1/marketing_ops_notes"
            f"?company_id=eq.{cid}&status=eq.open"
            f"&body=like.*card%20{short_id}*&select=id",
            prefer="return=representation") or []
        if existing:
            print(f"     blocked note already open ({existing[0]['id'][:8]})")
            return
        ops_sb("POST", "/rest/v1/marketing_ops_notes",
               {"company_id": cid, "body": body, "status": "open",
                "author": "gbp_service_trim"})
        print("     [TODO-SANTINO] ops note filed")
    except Exception as e:  # noqa: BLE001 -- the refusal itself must not crash the run
        print(f"     warn: blocked-note insert failed ({str(e)[:100]})")


# --------------------------------------------------------------------------- #
# per-card execution
# --------------------------------------------------------------------------- #
def execute_card(card: dict, apply: bool) -> str:
    cid = card["company_id"]
    slug = card_slug(card)
    if not slug:
        return f"{cid}: skip (card {card['id'][:8]} carries no slug/target)"
    st = company_status(cid)
    if st in INACTIVE:
        return f"{slug}: skip (account {st})"

    names = parse_services(card.get("rationale") or "")
    print(f"  [{slug}] card {card['id'][:8]}: {len(names)} service(s) named: {names}")
    if not names:
        file_blocked_note(card, slug,
                          "the card rationale contains no parseable "
                          '- "Service" (N/mo ...) lines.', apply)
        return f"{slug}: REFUSED (no parseable service names on the card)"

    cid2, token, place, loc, err = _load_location(slug)
    if err:
        file_blocked_note(card, slug, f"cannot reach the listing ({err}).", apply)
        return f"{slug}: REFUSED ({err})"
    items = json.loads(json.dumps(loc.get("serviceItems", [])))
    before = len(items)

    # exact display-name match only -- no fuzzing on a destructive write
    matched_idx: list[int] = []
    unmatched: list[str] = []
    for name in names:
        hits = [i for i, it in enumerate(items)
                if gbp._item_name(it).strip() == name]
        if not hits:
            unmatched.append(name)
        matched_idx.extend(hits)
    if unmatched:
        file_blocked_note(
            card, slug,
            "these approved service name(s) have no exact match on the live "
            f"listing: {unmatched} (listing has {before} items).", apply)
        return f"{slug}: REFUSED (unmatched: {unmatched})"

    matched_idx = sorted(set(matched_idx))
    keep = [it for i, it in enumerate(items) if i not in matched_idx]
    removed = [gbp._item_name(items[i]).strip() for i in matched_idx]
    print(f"     listing has {before} items; removing {len(matched_idx)} "
          f"({len(names)} distinct name(s)) -> {len(keep)}")
    if not keep:
        file_blocked_note(card, slug,
                          "executing it would remove EVERY service on the "
                          f"listing ({before} items).", apply)
        return f"{slug}: REFUSED (would empty the services list)"
    if not apply:
        return (f"{slug}: DRY RUN -- would remove {len(matched_idx)} item(s) "
                f"({before} -> {len(keep)}). Re-run with --apply.")

    # validateOnly preflight, then the real PATCH (rebalance's exact pattern);
    # categories are never in the updateMask, so they cannot change.
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = json.dumps({"serviceItems": keep})
    r = requests.patch(f"{gbp.INFO_API}/{loc['name']}?updateMask=serviceItems&validateOnly=true",
                       headers=hdrs, data=body, timeout=60)
    if not r.ok:
        return f"{slug}: preflight failed {r.status_code}: {r.text[:300]}"
    print("     validateOnly preflight: OK")
    r = requests.patch(f"{gbp.INFO_API}/{loc['name']}?updateMask=serviceItems",
                       headers=hdrs, data=body, timeout=60)
    if not r.ok:
        return f"{slug}: PATCH failed {r.status_code}: {r.text[:300]}"

    # re-read verify: exact count drop, none of the trimmed names remain
    back = gbp.find_location(token, place) or {}
    back_items = back.get("serviceItems", [])
    back_names = {gbp._item_name(it).strip() for it in back_items}
    leftovers = [n for n in removed if n in back_names]
    if len(back_items) != len(keep) or leftovers:
        return (f"{slug}: PATCH accepted but verification mismatch -- read "
                f"back {len(back_items)} items (expected {len(keep)}), "
                f"still present: {leftovers}")
    print(f"     verify: {len(back_items)} items on the listing, trims gone")

    n = len(matched_idx)
    summary = (f"Removed {n} unused service{'s' if n != 1 else ''} "
               "from your Google listing")
    gbp.log_change(cid, "service_trim", summary, actor="optimizer",
                   meta={"removed": removed, "before": before,
                         "after": len(back_items), "card_id": card["id"],
                         "source": "gbp_service_trim.py"})
    work_log(cid, "gbp", "service-trim",
             f"Removed {n} unused service{'s' if n != 1 else ''} from your "
             "Google listing after your approval: " + ", ".join(removed) + ".",
             evidence={"removed": removed, "before": before,
                       "after": len(back_items), "card_id": card["id"]},
             actor="automation", source="gbp_service_trim.py")

    note = (f"\n\n[EXECUTED {date.today().isoformat()} by gbp_service_trim.py] "
            f"Removed {n} service item{'s' if n != 1 else ''} from the live "
            f"listing ({', '.join(removed)}); {before} -> {len(back_items)} items.")
    ops_sb("PATCH", f"/rest/v1/marketing_action_plan?id=eq.{card['id']}",
           {"status": "resolved",
            "rationale": (card.get("rationale") or "") + note})
    print("     card resolved with executed note")
    return (f"{slug}: APPLIED -- removed {n} item(s), listing {before} -> "
            f"{len(back_items)}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true",
                   help="every approved gbp-parity-trim card fleet-wide")
    g.add_argument("--company", metavar="CO-...",
                   help="one company's approved card")
    ap.add_argument("--apply", action="store_true",
                    help="write to Google + resolve the card (default: dry run)")
    args = ap.parse_args()

    cards = approved_cards(None if args.all else args.company)
    if not cards:
        print("No approved gbp-parity-trim cards to execute.")
        return 0
    print(f"{len(cards)} approved trim card(s) "
          f"({'APPLY' if args.apply else 'DRY RUN'})")
    for card in cards:
        try:
            print("  " + execute_card(card, args.apply))
        except Exception as e:  # noqa: BLE001 -- one client must never abort the fleet
            print(f"  {card.get('rank_ai_slug') or card['company_id']}: ERROR "
                  f"({type(e).__name__}: {str(e)[:200]}) -- skipped")
    return 0  # non-fatal by contract: the weekly cron must not die on one card


if __name__ == "__main__":
    sys.exit(main())
