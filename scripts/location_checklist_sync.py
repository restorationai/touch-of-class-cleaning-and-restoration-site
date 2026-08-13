#!/usr/bin/env python3
"""location_checklist_sync.py — the launch checklist's client asks (second-office
program, Santino 2026-08-13: "each step is both a task and a record").

Every company_locations row that is not yet 'live' carries a launch checklist
in its `checklist` jsonb column (written by the app's LocationsPanel; shape in
app-work migration 20260813200000): dba -> address -> gbp_created ->
verification -> live -> site_pages -> citations -> hub, each step an object
with a `done` flag plus that step's facts.

Three of those steps can only move when the CLIENT does something:

  dba           send a photo of the DBA filing for the new location
  address       what's the registered address? a lease or utility bill helps
  verification  complete Google's video/postcard verification (owner-only)

This script walks every non-live location and seeds ONE idempotent
marketing_action_plan `client_input` ask per location — for the EARLIEST
undone step that needs client input — via client_ops_sync.insert_plan_row
(find-or-create by action_key, pinned, title refreshed in place). Steps that
are our work (gbp_created, site_pages, citations, hub) never generate an ask;
because asks only fire when a client step is the earliest UNDONE step,
"verification only after gbp_created" falls out naturally, and a belt-and-
braces guard enforces it anyway.

One ask at a time per location: seeding step N retires the open asks for
every other client step of that location, and a step completing retires its
own ask on the next sweep — the same seed-key retire pattern setup_ledger
uses (PATCH status=planned -> resolved by action_key). Monica picks the asks
up natively from marketing_action_plan; nothing here touches
client_concierge.py.

Column-derived truth so we never ask for what we already hold: a row with a
street address counts as address-done even if nobody ticked the box, a row
with a gbp_location_id counts as gbp_created-done, status 'live' counts as
live-done.

Usage:
    python3 scripts/location_checklist_sync.py             # real run
    python3 scripts/location_checklist_sync.py --dry-run   # print only

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (rank-ai/.env or CI secrets).
Runs daily from .github/workflows/client-ops-sync.yml.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from client_ops_sync import _sb, action_key, insert_plan_row, load_env, slug_map

# The full sequence, in launch order (mirrors the app's CHECKLIST_STEPS).
STEP_ORDER = ["dba", "address", "gbp_created", "verification", "live",
              "site_pages", "citations", "hub"]
# The steps only the client can move.
CLIENT_STEPS = ("dba", "address", "verification")


def _step_done(row: dict, step: str) -> bool:
    """Checklist truth first, then cheap column-derived truth."""
    st = ((row.get("checklist") or {}).get(step)) or {}
    if st.get("done"):
        return True
    if step == "address" and (row.get("address") or "").strip():
        return True
    if step == "gbp_created" and (row.get("gbp_location_id") or st.get("location_id")):
        return True
    if step == "live" and row.get("status") == "live":
        return True
    return False


def _retire(cid: str, seed: str, dry_run: bool) -> None:
    """Same pattern as setup_ledger: an open ask resolves itself when its
    step no longer needs the client (or another step's ask takes the slot)."""
    if dry_run:
        return
    _sb("PATCH", "/rest/v1/marketing_action_plan"
        f"?company_id=eq.{cid}&action_key=eq.{action_key(cid, seed)}"
        "&status=eq.planned", {"status": "resolved"})


def _ask_for(step: str, label: str) -> tuple[str, str]:
    """(title, rationale) for one client step. Client-facing wording rules:
    plain words, no em dashes, one question."""
    if step == "dba":
        return (
            f"ASK CLIENT: send a photo of the DBA filing for the new "
            f"{label} location",
            f"They are opening a second office in {label} and the first "
            "record we need on file is the DBA (doing-business-as) "
            "registration for the new location. MONICA: one plain question. "
            "If they have already filed it, a photo of the stamped filing "
            "texted back is perfect. If they have not filed yet, ask what "
            "name they plan to register it under so we can line everything "
            "up (Google listing, website pages, directories) to match it "
            "exactly.")
    if step == "address":
        return (
            f"ASK CLIENT: what's the registered address for the new "
            f"{label} location? A lease or utility bill photo helps",
            f"Their DBA for the {label} office is recorded and the next "
            "thing Google requires for the new listing is a real street "
            "address. MONICA: ask what's the registered address for the new "
            "location, and mention that a photo of a lease or utility bill "
            "helps because Google's verification usually asks for proof the "
            "business operates there. A texted photo is fine. Until we have "
            "the address in writing we cannot create the Google listing.")
    return (
        f"ASK CLIENT: complete Google's verification for the new {label} "
        "listing",
        f"The Google Business Profile for their {label} office exists but "
        "Google will only show it once the OWNER completes verification "
        "(usually a short video walkthrough or a mailed postcard code). We "
        "cannot do this step for them. MONICA: ask them to finish the "
        "verification Google is prompting for on the new listing and to "
        "tell us which method Google offered, so we know when to expect it "
        "to go live.")


def sync_location(row: dict, slug: str | None, dry_run: bool) -> str | None:
    """Seed/keep the one open ask for this location. Returns the step asked
    for (or None when no client step is the earliest undone one)."""
    cid, loc_id = row["company_id"], row["id"]
    label = (row.get("label") or row.get("city") or "the new location").strip()

    earliest = next((s for s in STEP_ORDER if not _step_done(row, s)), None)
    ask_step = earliest if earliest in CLIENT_STEPS else None
    # Belt and braces: never ask for verification before the profile exists.
    if ask_step == "verification" and not _step_done(row, "gbp_created"):
        ask_step = None

    # One ask at a time per location + auto-retire on completion.
    for s in CLIENT_STEPS:
        if s != ask_step:
            _retire(cid, f"loc-{loc_id}-{s}", dry_run)

    if not ask_step:
        print(f"  {label} ({slug or cid}): no client ask "
              f"(earliest undone: {earliest or 'none, all steps done'})")
        return None

    title, rationale = _ask_for(ask_step, label)
    created = insert_plan_row(
        cid, slug, f"loc-{loc_id}-{ask_step}",
        title=title, rationale=rationale,
        action_type="client_input", target=None,
        impact="high", effort="low", dry_run=dry_run)
    print(f"  {label} ({slug or cid}): {ask_step} ask "
          f"{'seeded' if created else 'already open'}")
    return ask_step


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would happen; write nothing")
    args = ap.parse_args()
    load_env()

    rows = _sb("GET", "/rest/v1/company_locations?status=neq.live&select=*"
               "&order=company_id", prefer="return=representation") or []
    if not rows:
        print("No non-live locations — nothing to do.")
        return 0

    smap = slug_map()
    print(f"{len(rows)} non-live location(s):")
    for row in rows:
        sync_location(row, smap.get(row["company_id"]), args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
