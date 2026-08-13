#!/usr/bin/env python3
"""water_cleanup_rollout.py -- ONE-SHOT fleet rollout of "Water Cleanup"
(System: GBP + Site, approved by Santino 2026-08).

Why: "water cleanup" is the colloquial high-volume term homeowners actually
type instead of "water damage restoration" -- Roto-Rooter is renaming whole
listings to "...Plumbing & Water Cleanup" on the same evidence. It is the SAME
work our water-damage clients already do, so the label is truthful for every
restoration client; this pass just puts the term people search on the listing
and gives it a dedicated page.

Per targeted client (ACTIVE, restoration vertical or water-damage services on
file; plumbing-only clients like rt-olson excluded; paused skipped by the
same companies.status gate as every gbp --all pass):

  1. VOLUMES  one DataForSEO google_ads search_volume call per client for
     "water cleanup" + "water damage cleanup" scoped to the client's metro
     (US national fallback). Recorded in the report; never a gate -- the term
     is truthful regardless of what a small metro under-reports.
  2. GBP      add "Water Cleanup" as a free-form service unless a case/
     phrasing-insensitive variant is already on the listing ("Water Clean Up",
     "Water Clean-Up Services", ...). Adds go through gbp.add_services --
     the capped path (validateOnly preflight + per-category cap spill), which
     also logs the plain-English marketing_gbp_changes row per confirmed add.
  3. SITE     queue a "Water Cleanup" page via marketing_page_requests
     (status 'queued', exact existing queue shape) unless the site already
     has a water-cleanup page (sites/{slug}/src/content/services/), the slug
     is already staged in plan-input, or an equivalent request is already
     queued/building/built/dismissed. The Monday gbp-maintenance drain
     (gbp.py create-pages --build) turns the queue into real pages -- this
     script never builds pages itself.

Dry-run is the default; nothing is written without --apply.

Usage:
    python3 scripts/water_cleanup_rollout.py --all              # dry-run report
    python3 scripts/water_cleanup_rollout.py --all --apply
    python3 scripts/water_cleanup_rollout.py --slug narestco --apply

New clients do NOT need this script again: "Water Cleanup" is seeded in the
canonical restoration catalog (templates/restoration/services.json) and rides
the normal onboarding/GBP passes going forward.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import gbp  # noqa: E402 -- roster gate, reconcile, add_services, SB REST (import only, never edited)
from gbp_name_suggest import metro_location, search_volumes  # noqa: E402

SERVICE_NAME = "Water Cleanup"
KEYWORDS = ["water cleanup", "water damage cleanup"]

# Phrasing-insensitive presence: lowercase, drop the word "service(s)", strip
# everything non-alphanumeric. "Water Clean Up" / "Water Clean-Up Services"
# / "WATER CLEANUP" all squash to "watercleanup". gbp._norm is unusable here:
# it strips the word "cleanup" itself.
PRESENT_FORMS = {"watercleanup"}
# A dedicated page under either phrasing counts as coverage -- do not queue a
# near-duplicate page next to an existing water-damage-cleanup one.
PAGE_FORMS = {"watercleanup", "waterdamagecleanup"}

# Water-damage evidence: plan-input service slugs...
WATER_PLAN_SLUGS = {"water-damage-restoration", "flood-damage-restoration",
                    "basement-flooding-cleanup", "water-cleanup"}
# ...or the client's confirmed do-list in the app (companies.services strings).
WATER_DECLARED_HINTS = ("water damage", "water extraction", "water removal",
                        "water cleanup", "water mitigation", "flood")


def _squash(text: str) -> str:
    t = re.sub(r"\bservices?\b", " ", (text or "").lower())
    return re.sub(r"[^a-z0-9]+", "", t)


# --------------------------------------------------------------------------- #
# roster + targeting
# --------------------------------------------------------------------------- #
def roster(args) -> list[str]:
    """Same companies.status gate as every other gbp --all pass."""
    return gbp._clients(SimpleNamespace(all=args.all, slug=args.slug))


def companies_meta(slugs: list[str]) -> dict:
    """{slug: companies row} in one read (name/status/industry/metro/services)."""
    cids = {s: gbp.company_id_for(s) for s in slugs}
    ids = ",".join(f'"{c}"' for c in cids.values() if c)
    rows = gbp._sb(f"companies?id=in.({ids})"
                   "&select=id,name,status,industry,city,state,services") if ids else []
    by_id = {r["id"]: r for r in rows}
    return {s: by_id.get(c) for s, c in cids.items()}


def plan_services(slug: str) -> list[str]:
    pi = ROOT / "clients" / slug / "plan-input.json"
    if not pi.exists():
        return []
    try:
        return json.loads(pi.read_text()).get("services") or []
    except json.JSONDecodeError:
        return []


def target_check(slug: str, meta: dict | None) -> str | None:
    """None when the client is a rollout target, else the plain skip reason.
    Target = restoration vertical (companies.industry, falling back to the
    repo client record's vertical) WITH water-damage work on file (plan-input
    services or the app's confirmed services list). A non-restoration client
    still qualifies when water-damage work is on file (the rt-olson clause:
    plumbing-only stays out UNLESS they already do water damage)."""
    if not meta:
        return "no companies row (not an active account)"
    industry = [str(x).lower() for x in (meta.get("industry") or [])]
    vertical = None
    rec_path = ROOT / "clients" / f"{slug}.json"
    if rec_path.exists():
        try:
            vertical = json.loads(rec_path.read_text()).get("vertical")
        except json.JSONDecodeError:
            pass
    restoration = any("restoration" in x for x in industry) or vertical == "restoration"

    declared = [str(x).lower() for x in (meta.get("services") or [])]
    water = (bool(WATER_PLAN_SLUGS & set(plan_services(slug)))
             or any(h in d for h in WATER_DECLARED_HINTS for d in declared))
    if not water:
        return ("restoration client but no water-damage service on file "
                "(plan-input + confirmed services)") if restoration else \
               "not restoration and no water-damage service on file"
    return None


# --------------------------------------------------------------------------- #
# volumes (one DataForSEO call per client, metro-scoped, national fallback)
# --------------------------------------------------------------------------- #
def volumes_for(meta: dict) -> tuple[dict, str]:
    creds = gbp._dfs_auth()
    if not creds:
        return {k: 0 for k in KEYWORDS}, "unavailable (no DataForSEO creds)"
    auth = base64.b64encode(f"{creds[0]}:{creds[1]}".encode()).decode()
    loc = metro_location(meta.get("city"), meta.get("state"))
    try:
        vols, label = search_volumes(auth, KEYWORDS, loc)
    except Exception as e:  # noqa: BLE001 -- volumes inform the report, never gate it
        return {k: 0 for k in KEYWORDS}, f"unavailable ({str(e)[:60]})"
    return vols, label


# --------------------------------------------------------------------------- #
# GBP: add unless a phrasing variant already sits on the listing
# --------------------------------------------------------------------------- #
def gbp_step(slug: str, apply: bool) -> str:
    rec = gbp.reconcile(slug)
    if rec.get("error"):
        return f"skip ({rec['error']})"
    labels = [gbp._svc_label(s) for s in rec.get("gbp", {}).get("services", [])]
    hit = next((l for l in labels if _squash(l) in PRESENT_FORMS), None)
    if hit:
        return f'already present as "{hit}"'
    if not apply:
        return "would add"
    # capped path: validateOnly preflight + per-category spill + read-back
    # confirm + one marketing_gbp_changes row per confirmed add, all inside.
    msg = gbp.add_services(slug, [SERVICE_NAME])
    body = msg.split(": ", 1)[-1]
    return f"added ({body})" if " added " in f" {body}" else f"FAILED ({body})"


# --------------------------------------------------------------------------- #
# SITE: queue the page unless already covered
# --------------------------------------------------------------------------- #
def page_step(slug: str, cid: str | None, apply: bool) -> str:
    svc_dir = ROOT / "sites" / slug / "src" / "content" / "services"
    if svc_dir.is_dir():
        for f in sorted(svc_dir.glob("*.md")):
            if _squash(f.stem) in PAGE_FORMS:
                return f"covered (page exists: {f.name})"
    if any(_squash(s) in PAGE_FORMS for s in plan_services(slug)):
        return "covered (already staged in plan-input)"
    if not cid:
        return "skip (no company_id -- cannot queue)"
    rows = gbp._sb(f"marketing_page_requests?company_id=eq.{cid}&select=service,status")
    for r in rows:
        if _squash(str(r.get("service", ""))) in PAGE_FORMS and \
                r.get("status") in ("queued", "building", "built", "dismissed"):
            return f"covered (request already {r['status']}: \"{r['service']}\")"
    if not svc_dir.is_dir():
        # pre-site client: the drain would attempt a build with no scaffold.
        # The catalog seed + onboarding passes give them the term at build time.
        return "skip (no built site yet -- catalog seed covers it at build time)"
    if not apply:
        return "would queue"
    requests.post(
        f"{gbp.SB_URL}/rest/v1/marketing_page_requests",
        headers={"apikey": gbp.SB_KEY, "Authorization": f"Bearer {gbp.SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"},
        data=json.dumps({"company_id": cid, "service": SERVICE_NAME,
                         "status": "queued"}),
        timeout=30).raise_for_status()
    return "queued"


# --------------------------------------------------------------------------- #
# CLI + fleet report
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true",
                    help="write GBP adds + queue pages (default: dry-run report)")
    args = ap.parse_args()

    slugs = roster(args)
    meta = companies_meta(slugs)
    results = []
    for slug in slugs:
        m = meta.get(slug)
        print(f"\n## {slug}" + (f" ({m['name']})" if m and m.get("name") else ""))
        skip = target_check(slug, m)
        if skip:
            print(f"   SKIP -- {skip}")
            results.append({"slug": slug, "skip": skip})
            continue
        try:
            vols, vol_label = volumes_for(m)
            print(f"   volumes [{vol_label}]: " + " | ".join(
                f'"{k}" {vols.get(k, 0)}/mo' for k in KEYWORDS))
            gbp_res = gbp_step(slug, args.apply)
            print(f"   GBP:  {gbp_res}")
            page_res = page_step(slug, gbp.company_id_for(slug), args.apply)
            print(f"   PAGE: {page_res}")
        except Exception as e:  # noqa: BLE001 -- one client must never abort the fleet
            print(f"   ERROR ({type(e).__name__}: {str(e)[:200]}) -- skipped")
            results.append({"slug": slug, "skip": f"ERROR {type(e).__name__}"})
            continue
        results.append({"slug": slug, "skip": None, "vol_label": vol_label,
                        "wc": vols.get(KEYWORDS[0], 0), "wdc": vols.get(KEYWORDS[1], 0),
                        "gbp": gbp_res, "page": page_res})

    print(f"\n{'=' * 100}")
    print(f"WATER CLEANUP ROLLOUT {'APPLIED' if args.apply else 'DRY-RUN'} "
          f'("{KEYWORDS[0]}" vs "{KEYWORDS[1]}" searches/mo, in-metro)')
    print(f"{'client':<40}{'wc':>6}{'wdc':>6}  {'GBP':<34}{'PAGE'}")
    for r in results:
        if r["skip"]:
            print(f"{r['slug']:<40} skip: {r['skip']}")
            continue
        print(f"{r['slug']:<40}{r['wc']:>6}{r['wdc']:>6}  "
              f"{r['gbp'][:32]:<34}{r['page']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
