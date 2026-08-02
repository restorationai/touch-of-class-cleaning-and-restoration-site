#!/usr/bin/env python3
"""Invite the agency Google account as MANAGER on every client GBP.

Why (2026-08-01): Bing Places' GBP-import copies only listings the agency
Google user (contact@restorationai.io) directly manages — 5 of 19 clients.
Every other client's GBP is connected via THEIR own Google user, whose token
we hold. This sends a manager invitation from each client's own account to
the agency account; the browser agent (or a human) accepts them at
business.google.com, after which Bing's import/sync sees every listing.

Idempotent: skips clients whose admins already include the agency email or
where an invite is already pending (API returns ALREADY_EXISTS).

Usage: python3 scripts/gbp_admin_invite.py [--dry-run]
"""
from __future__ import annotations

import json
import sys
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
ACCT_MGMT = "https://mybusinessaccountmanagement.googleapis.com/v1"


def main() -> int:
    dry = "--dry-run" in sys.argv
    smap = slug_map()
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
              "&select=id,name") or []
    invited, skipped = [], []
    for co in cos:
        cid, slug = co["id"], smap.get(co["id"])
        if not slug:
            continue
        tok = gbp.get_access_token(cid)
        if not tok:
            skipped.append((slug, "no google token"))
            continue
        place = gbp._place_id_from_connection(cid)
        try:
            brand = json.loads((ROOT / "clients" / slug / "plan-input.json")
                               .read_text()).get("brand", {})
            place = brand.get("place_id") or place
        except Exception:
            pass
        if not place:
            skipped.append((slug, "no place_id"))
            continue
        loc = gbp.find_location(tok, place)
        if not loc:
            skipped.append((slug, "no GBP location"))
            continue
        loc_name = loc["name"] if loc["name"].startswith("locations/") \
            else "locations/" + loc["name"].split("locations/")[-1]

        # Already an admin? (invitations show up here too once accepted)
        r = requests.get(f"{ACCT_MGMT}/{loc_name}/admins",
                         headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        if r.ok and any(AGENCY_EMAIL in json.dumps(a).lower()
                        for a in (r.json().get("admins") or [])):
            skipped.append((slug, "already admin"))
            continue

        if dry:
            invited.append((slug, "[dry-run]"))
            continue
        r = requests.post(f"{ACCT_MGMT}/{loc_name}/admins",
                          headers={"Authorization": f"Bearer {tok}",
                                   "Content-Type": "application/json"},
                          json={"admin": AGENCY_EMAIL, "role": "MANAGER"},
                          timeout=30)
        if r.ok:
            invited.append((slug, "invited"))
        elif "ALREADY_EXISTS" in r.text or r.status_code == 409:
            skipped.append((slug, "invite already pending"))
        else:
            skipped.append((slug, f"HTTP {r.status_code}: {r.text[:80]}"))
    print(f"\nINVITED ({len(invited)}):")
    for s, note in invited:
        print(f"  {s}: {note}")
    print(f"SKIPPED ({len(skipped)}):")
    for s, note in skipped:
        print(f"  {s}: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
