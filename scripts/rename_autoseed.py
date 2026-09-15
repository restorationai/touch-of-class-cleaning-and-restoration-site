#!/usr/bin/env python3
"""rename_autoseed.py — GBP connects, research follows, cards populate.

Santino 2026-09-15 (Flood and Fire Solutions kickoff, live on the call):
"once the GBP is connected, the profile name change isn't visible... we
need to make this automatic. Same thing with the location scout." Until
now both surfaces waited for a manual research pass (rename card) or the
weekly maintenance run (Location Scout) — a client connected mid-meeting
saw empty panels.

WHAT THIS DOES (rides call-intel.yml every 30 min, so worst-case ~30 min
from connect to populated card):

  RENAME  every Active company with a Google integration whose
          connection_metadata carries a selected_location_id and with ZERO
          open item_type='name' rows in marketing_gbp_suggestions gets the
          house candidate set seeded deterministically:
            1. aggressive plumbing-first (0.91, license-gate wording) —
               house stance 2026-09-12 for water-damage clients
            2. top covered service terms w/ 24/7 Emergency prefix (0.90)
            3. conservative two-term fallback (0.80)
          Volumes come from one DataForSEO google_ads search_volume call
          scoped to the client's STATE (the same pools the manual seeds
          quote), and every reason carries its numbers (volumes-in-reasons
          law). SERVICE COVERAGE LAW: a term never enters a candidate
          unless the matching service is on the company row — no mold for
          non-mold shops (Frontline/Flood-and-Fire precedent). Verticals
          outside restoration/plumbing are SKIPPED with a log line —
          those stay manual (Arch-style custom research).

  SCOUT   the same newly-connected companies get location_scout.py --slug
          invoked once (best-effort) so the Locations panel isn't empty
          until the weekly run.

Idempotent: a company with ANY name suggestion rows (open, chosen or
dismissed) is never re-seeded — dismissals are decisions, not gaps.

CLI: python3 scripts/rename_autoseed.py [--dry-run] [--slug SLUG]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import requests  # noqa: E402

from client_ops_sync import _sb, slug_map  # noqa: E402
from gbp_name_suggest import load_dfs_creds  # noqa: E402

# keyword -> service-name fragments that must appear in companies.services
# for the term to be usable in a candidate.
TERMS = {
    "water damage restoration": ("water damage",),
    "mold remediation": ("mold",),
    "fire damage restoration": ("fire",),
    "sewage cleanup": ("sewage",),
    "storm damage restoration": ("storm",),
    "emergency plumber": (),           # license-gated, never coverage-gated
    "emergency plumbing": (),
    "basement flooding": ("water damage", "water cleanup"),
}
RESTORATION_MARKERS = ("water", "fire", "sewage", "storm", "mold", "plumb")


def _volumes(state: str) -> dict[str, int]:
    u, p = load_dfs_creds()
    r = requests.post(
        "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live",
        auth=(u, p),
        json=[{"keywords": list(TERMS), "language_code": "en",
               "location_name": f"{state},United States"}], timeout=90)
    r.raise_for_status()
    out: dict[str, int] = {}
    for t in r.json().get("tasks") or []:
        for res in t.get("result") or []:
            out[res["keyword"]] = res.get("search_volume") or 0
    return out


def _covered(term: str, services_l: str) -> bool:
    frags = TERMS[term]
    return (not frags) or any(f in services_l for f in frags)


# two-letter -> full state name for DFS location_name
STATE_FULL = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona",
              "AR": "Arkansas", "CA": "California", "CO": "Colorado",
              "CT": "Connecticut", "DE": "Delaware", "FL": "Florida",
              "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
              "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
              "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
              "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
              "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
              "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
              "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
              "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
              "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
              "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
              "SC": "South Carolina", "SD": "South Dakota",
              "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
              "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
              "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}


def seed_company(co: dict, dry_run: bool) -> bool:
    cid, name = co["id"], (co.get("name") or "").strip()
    services_l = " ".join(co.get("services") or []).lower()
    state = (co.get("state") or "").strip()
    if not (name and state):
        print(f"  [{cid}] missing name/state — skipped")
        return False
    if not any(m in services_l for m in RESTORATION_MARKERS):
        print(f"  [{cid}] {name}: non-restoration vertical — manual research")
        return False
    vols = _volumes(STATE_FULL.get(state.upper(), state))
    return _seed_with_vols(co, vols, dry_run)


def _seed_with_vols(co, vols, dry_run) -> bool:
    cid, name = co["id"], (co.get("name") or "").strip()
    services_l = " ".join(co.get("services") or []).lower()
    base = name.split(" - ")[0].strip()
    vol_note = ", ".join(f"{k} {v:,}/mo" for k, v in
                         sorted(vols.items(), key=lambda kv: -kv[1]) if v)
    plumb = max(vols.get("emergency plumber", 0),
                vols.get("emergency plumbing", 0))
    ranked = sorted(((t, v) for t, v in vols.items()
                     if t not in ("emergency plumber", "emergency plumbing")
                     and _covered(t, services_l) and v),
                    key=lambda kv: -kv[1])
    if not ranked:
        print(f"  [{cid}] {name}: no covered terms with volume — skipped")
        return False
    top = [t.title() for t, _ in ranked[:2]]
    water_first = vols.get("water damage restoration", 0)
    rows = []
    if plumb:
        rows.append({
            "confidence": 0.91,
            "item": f"{base} - 24/7 Emergency Plumbing & {top[0]}",
            "reason": ("AGGRESSIVE FIRST OPTION (house stance 2026-09-12 "
                       "for water-damage clients): the state plumbing pool "
                       f"is {plumb:,}/mo, the biggest urgent-intent demand "
                       "a restoration name can capture. HARD GATE: "
                       "advertising plumbing in the name requires a "
                       "plumbing license connected to the business or a "
                       "licensed partner — ask before committing. State "
                       f"pools (DataForSEO): {vol_note}.")})
    if len(top) >= 2:
        mid_item = f"{base} - 24/7 Emergency {top[0]} & {top[1]}"
    else:
        mid_item = f"{base} - 24/7 Emergency {top[0]}"
    rows.append({
        "confidence": 0.9,
        "item": mid_item,
        "reason": (f"Top searched terms the business actually performs "
                   f"(service-coverage checked). State pools (DataForSEO): "
                   f"{vol_note}.")})
    cons = (f"{base} - {top[0]}"
            + (f" & {top[1]}" if len(top) >= 2 else ""))
    rows.append({
        "confidence": 0.8,
        "item": cons,
        "reason": (f"Conservative fallback, shortest usable form. "
                   f"State pools (DataForSEO): {vol_note}.")})
    for r in rows:
        print(f"  [{cid}] {name}: {r['confidence']} {r['item']}")
        if dry_run:
            continue
        _sb("POST", "/rest/v1/marketing_gbp_suggestions",
            {"company_id": cid, "item_type": "name", "source": "autoseed",
             "verdict": "ADD", "status": "open", **r},
            prefer="return=minimal")
    _ = water_first  # noqa: F841
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--slug")
    a = ap.parse_args()
    inv = {c: s for s, c in {s: c for c, s in slug_map().items()}.items()}
    gi = _sb("GET", "/rest/v1/user_integrations?provider=eq.google"
             "&select=client_id,connection_metadata") or []
    connected = {r["client_id"] for r in gi
                 if (r.get("connection_metadata") or {}).get(
                     "selected_location_id")}
    seeded_rows = _sb("GET", "/rest/v1/marketing_gbp_suggestions"
                      "?item_type=eq.name&select=company_id") or []
    has_names = {r["company_id"] for r in seeded_rows}
    comps = _sb("GET", "/rest/v1/companies?status=eq.Active"
                "&select=id,name,state,services") or []
    n = 0
    for co in comps:
        cid = co["id"]
        slug = inv.get(cid)
        if a.slug and slug != a.slug:
            continue
        if cid not in connected or cid in has_names:
            continue
        try:
            if seed_company(co, a.dry_run):
                n += 1
                # Location Scout for the same fresh client (best-effort;
                # weekly maintenance remains the backstop).
                if slug and not a.dry_run:
                    subprocess.run(
                        [sys.executable, "scripts/location_scout.py",
                         "--slug", slug], cwd=ROOT, timeout=300,
                        capture_output=True)
        except Exception as e:  # noqa: BLE001 — one client never kills the sweep
            print(f"  [{cid}] seed failed: {str(e)[:120]}")
    print(f"rename autoseed: {n} client(s) seeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
