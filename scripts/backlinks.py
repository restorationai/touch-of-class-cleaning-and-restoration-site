#!/usr/bin/env python3
"""backlinks.py — vendor/association backlink targets (queue build, Santino
2026-07-31: "make it dynamic based on the category the company selects").

The Noah Igler playbook's highest-value gap: supplier/association backlinks
(the Trane-installer pattern). Each active Rank AI client gets a per-category
target list in marketing_backlinks; the app's Connect tab renders it next to
the business listings (client-visible progress, team-workable statuses).

Statuses: target (nothing yet) -> requested (outreach made, human sets) ->
live (checker CONFIRMED a link/mention at the saved URL). 'na' = doesn't
apply to this client (e.g. equipment brand they don't run) — human-set only.

Commands:
    seed [--slug X]     upsert the category target set for active Rank AI
                        clients (ignore-duplicates: never clobbers statuses)
    check [--slug X]    fetch saved URLs for non-live rows; a link to the
                        client's domain flips status -> live (with evidence);
                        a name-only mention is recorded but not promoted

Wired into client-ops-sync.yml daily after lsa_detect.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
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

# Per-vertical target sets. Every client currently maps to 'restoration';
# new industries add a key here and category_for() learns to route them.
CATEGORY_TARGETS: dict[str, list[tuple[str, str, str, str]]] = {
    # (target_key, label, kind, note)
    "restoration": [
        ("iicrc", "IICRC Certified Firm locator", "association",
         "Free with the certification they already hold — the single most "
         "authoritative restoration link there is."),
        ("ria", "RIA member directory", "association",
         "Restoration Industry Association membership listing."),
        ("chamber", "Local Chamber of Commerce", "local",
         "Paid membership the owner signs off on; the best NAP + backlink "
         "combo available locally."),
        ("contractor-connection", "Contractor Connection", "tpa",
         "TPA network profile — applies when they're enrolled."),
        # Trimmed 2026-09-06 (Santino): the vendor/supplier testimonial
        # targets (Dri-Eaz, Phoenix, XPOWER, B-Air, Injectidry, Aramsco,
        # Jon-Don) never converted — replaced with the industry press pair.
        ("rr-magazine", "R&R Magazine", "press",
         "Restoration & Remediation (restorationandremediation.com) — "
         "contributed article or company feature earns the link."),
        ("cr-magazine", "C&R Magazine", "press",
         "Cleaning & Restoration, RIA's magazine (candrmagazine.com) — "
         "member article contribution."),
    ],
}


def category_for(co: dict) -> str:
    """Vertical for a company. All current clients are restoration; when the
    wizard category lands in companies, route on it here."""
    del co
    return "restoration"


def _companies(slug: str | None) -> list[dict]:
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
              "&select=id,name,website") or []
    if slug:
        smap = slug_map()
        cos = [c for c in cos if smap.get(c["id"]) == slug]
    return cos


def cmd_seed(slug: str | None) -> int:
    cos = _companies(slug)
    total = 0
    for co in cos:
        cat = category_for(co)
        rows = [{"company_id": co["id"], "target_key": k, "label": label,
                 "kind": kind, "category": cat, "note": note}
                for k, label, kind, note in CATEGORY_TARGETS.get(cat, [])]
        if not rows:
            continue
        # ignore-duplicates: reseeding must never clobber human statuses/URLs
        _sb("POST", "/rest/v1/marketing_backlinks?on_conflict=company_id,target_key",
            rows, prefer="resolution=ignore-duplicates,return=minimal")
        total += len(rows)
    print(f"seeded {total} target rows across {len(cos)} client(s)")
    return 0


def _norm_domain(d: str | None) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://", "", d).strip("/ ")
    return d[4:] if d.startswith("www.") else d


def cmd_check(slug: str | None) -> int:
    cos = {c["id"]: c for c in _companies(slug)}
    if not cos:
        print("no matching companies")
        return 0
    ids = ",".join(f'"{c}"' for c in cos)
    rows = _sb("GET", "/rest/v1/marketing_backlinks?status=in.(target,requested)"
               f"&url=not.is.null&company_id=in.({ids})"
               "&select=id,company_id,target_key,url,status") or []
    now = datetime.now(timezone.utc).isoformat()
    flipped = 0
    for r in rows:
        co = cos.get(r["company_id"])
        if not co or not (r.get("url") or "").startswith("http"):
            continue
        dom = _norm_domain(co.get("website"))
        name = (co.get("name") or "").strip()
        try:
            resp = requests.get(r["url"], timeout=25, headers={
                "User-Agent": "Mozilla/5.0 (rank-ai backlink check)"})
            html = resp.text[:800_000] if resp.ok else ""
        except Exception:
            html = ""
        linked = bool(dom) and dom in html.lower()
        mentioned = bool(name) and name.lower() in html.lower()
        patch = {"last_checked_at": now,
                 "evidence": {"linked": linked, "mentioned": mentioned,
                              "checked_url": r["url"]}}
        if linked:
            patch["status"] = "live"
            flipped += 1
            print(f"  LIVE: {r['target_key']} for {co['name'][:30]} "
                  f"(domain found on page)")
        _sb("PATCH", f"/rest/v1/marketing_backlinks?id=eq.{r['id']}", patch)
    print(f"checked {len(rows)} URL(s), {flipped} flipped to live")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("seed", "check"):
        p = sub.add_parser(name)
        p.add_argument("--slug")
    a = ap.parse_args()
    return {"seed": cmd_seed, "check": cmd_check}[a.cmd](a.slug)


if __name__ == "__main__":
    sys.exit(main())
