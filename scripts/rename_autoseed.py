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
          house candidate set seeded deterministically.

          RENAME INTELLIGENCE v2 (Santino 2026-09-25; PuroClean LV + Arch
          reference cases — see docs/gbp-rename-candidates.md):
            1. PRIORITY LADDER, never raw volume: restoration names order
               lanes plumbing -> water -> fire; mold and the rest TRAIL
               even when their volume is higher (NV case: mold 480/mo
               outsearches water 320/mo, water still leads — identity
               beats volume). Volume only orders the trailing tier.
            2. BRAND COMPRESSION: strip non-identity filler ("of",
               "Group", legal suffixes, leading "The") from the stem
               before composing; every trim is listed in the reason.
            3. Existing laws hold: hard 90-char cap, "&" not "and",
               never 4+ terms, 24/7 free modifier, volumes in every
               reason (one DataForSEO call scoped to the client's STATE).
            4. COVERAGE-FIRST: lanes count as sold via companies.services
               OR live GBP categories, and the slate names every major
               lane so the pitch coverage gate passes by construction.
            5. Plumbing is UNCONDITIONAL for restoration slates (Santino
               09-25): no license-gate wording anywhere — the pitch
               conversation handles the license question.
          Verticals outside restoration/plumbing are SKIPPED with a log
          line — those stay manual (Arch-style custom research).

  SCOUT   the same newly-connected companies get location_scout.py --slug
          invoked once (best-effort) so the Locations panel isn't empty
          until the weekly run.

Idempotent: a company with ANY name suggestion rows (open, chosen or
dismissed) is never re-seeded — dismissals are decisions, not gaps.

CLI: python3 scripts/rename_autoseed.py [--dry-run] [--slug SLUG]
"""
from __future__ import annotations

import argparse
import re
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


_STEM_SUFFIX_RE = re.compile(r"[\s,]+(?:LLC|L\.L\.C\.|Inc\.?|Corp\.?|Co\.)$",
                             re.IGNORECASE)
# trailing tier: everything a restoration name may carry AFTER the ladder,
# ordered by state volume at compose time. Mold lives here BY DESIGN.
_TRAILING = ("mold remediation", "storm damage restoration",
             "sewage cleanup", "basement flooding")


def _compress_stem(base: str) -> tuple[str, list[str]]:
    """Brand compression (v2): strip non-identity filler, report the trims."""
    out, trims = base.strip(), []
    if _STEM_SUFFIX_RE.search(out):
        trims.append("legal suffix")
        out = _STEM_SUFFIX_RE.sub("", out).strip()
    if re.search(r"(?i)\s+Group$", out):
        trims.append("Group")
        out = re.sub(r"(?i)\s+Group$", "", out).strip()
    if re.match(r"(?i)^The\s+", out):
        trims.append("The")
        out = re.sub(r"(?i)^The\s+", "", out).strip()
    if re.search(r"(?i)\s+of\s+", out):
        trims.append("of")
        out = re.sub(r"(?i)\s+of\s+", " ", out).strip()
    return out, trims


def _narrow_geo(stem: str) -> str:
    """Metro narrowing (v2, the PuroClean 'East Las Vegas' -> 'Las Vegas'
    move): drop one directional/qualifier word to buy characters when a
    candidate would otherwise blow the 90-char cap."""
    return re.sub(r"(?i)\b(?:East|West|North|South|Greater|Central)\s+",
                  "", stem, count=1).strip()


def _seed_with_vols(co, vols, dry_run) -> bool:
    cid, name = co["id"], (co.get("name") or "").strip()
    services_l = " ".join(co.get("services") or []).lower()
    # Coverage haystack includes live GBP categories (coverage law: a lane
    # counts as sold via category even without a services row — the exact
    # gap that made the pitch worker refuse PuroClean's fire lane).
    try:
        prof = _sb("GET", "/rest/v1/marketing_gbp_profiles"
                   f"?company_id=eq.{cid}"
                   "&select=primary_category,additional_categories") or []
        for p in prof:
            cats = [p.get("primary_category") or ""]
            cats += [str(c) for c in (p.get("additional_categories") or [])]
            services_l += " " + " ".join(cats).lower()
    except Exception:  # noqa: BLE001 — coverage widening is best-effort
        pass
    stem_raw = name.split(" - ")[0].strip()
    stem, trims = _compress_stem(stem_raw)
    vol_note = ", ".join(f"{k} {v:,}/mo" for k, v in
                         sorted(vols.items(), key=lambda kv: -kv[1]) if v)
    trim_note = (f" Brand stem compressed ('{stem_raw}' -> '{stem}': "
                 f"dropped {', '.join(trims)})." if trims else "")

    water = _covered("water damage restoration", services_l)
    fire = _covered("fire damage restoration", services_l)
    trailing = sorted((t for t in _TRAILING
                       if _covered(t, services_l) and vols.get(t)),
                      key=lambda t: -vols[t])
    tail = trailing[0].title() if trailing else None

    rows: list[dict] = []

    def add(conf: float, item: str, why: str) -> None:
        # hard 90-char cap (LAW 2026-09-19) enforced at composition
        if len(item) <= 90 and all(r["item"] != item for r in rows):
            rows.append({"confidence": conf, "item": item,
                         "reason": (f"{why} State pools (DataForSEO): "
                                    f"{vol_note}.{trim_note}")})

    ladder_why = ("PRIORITY LADDER (v2, Santino 2026-09-25): plumbing "
                  "leads unconditionally for restoration, then water, "
                  "then fire; mold-class terms trail regardless of "
                  "volume — identity beats volume.")
    if water and fire:
        add(0.95, f"{stem} - 24/7 Emergency Plumbing, Water & Fire Damage "
                  f"Restoration", ladder_why)
        if tail:
            mc_why = ("MAX-COVERAGE name: water + fire + the top trailing "
                      "lane in one string; trailing seat is by design, "
                      "not volume.")
            mc = (f"{stem} - 24/7 Emergency Water & Fire Damage "
                  f"Restoration, {tail}")
            if len(mc) > 90 and _narrow_geo(stem) != stem:
                nstem = _narrow_geo(stem)
                mc = (f"{nstem} - 24/7 Emergency Water & Fire Damage "
                      f"Restoration, {tail}")
                mc_why += (f" Geo narrowed ('{stem}' -> '{nstem}') to fit "
                           "the 90-char cap.")
            add(0.9, mc, mc_why)
        add(0.85, f"{stem} - 24/7 Emergency Plumbing & Water Damage "
                  f"Restoration",
            "Two-term plumbing + water form: the two biggest "
            "urgent-intent pools a restoration name can carry.")
        add(0.8, f"{stem} - 24/7 Emergency Water & Fire Damage Restoration",
            "Category-true fallback: water + fire, no plumbing.")
    elif water:
        add(0.95, f"{stem} - 24/7 Emergency Plumbing & Water Damage "
                  f"Restoration", ladder_why)
        if tail:
            add(0.9, f"{stem} - 24/7 Emergency Water Damage Restoration "
                     f"& {tail}",
                "Water + top trailing lane; trailing seat by design.")
        add(0.8, f"{stem} - Water Damage Restoration"
                 + (f" & {tail}" if tail else ""),
            "Conservative fallback, shortest usable form.")
    else:
        if not trailing:
            print(f"  [{cid}] {name}: no covered lanes with volume — "
                  "skipped")
            return False
        t1 = trailing[0].title()
        t2 = trailing[1].title() if len(trailing) > 1 else None
        add(0.9, f"{stem} - 24/7 Emergency {t1}"
                 + (f" & {t2}" if t2 else ""),
            "Top covered lanes for a non-water restoration shop.")
        add(0.8, f"{stem} - {t1}" + (f" & {t2}" if t2 else ""),
            "Conservative fallback, shortest usable form.")
    if not rows:
        print(f"  [{cid}] {name}: nothing fit the 90-char cap — manual")
        return False
    for r in rows:
        print(f"  [{cid}] {name}: {r['confidence']} ({len(r['item'])}ch) "
              f"{r['item']}")
        if dry_run:
            continue
        _sb("POST", "/rest/v1/marketing_gbp_suggestions",
            {"company_id": cid, "item_type": "name", "source": "autoseed",
             "verdict": "ADD", "status": "open", **r},
            prefer="return=minimal")
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
