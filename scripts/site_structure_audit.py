#!/usr/bin/env python3
"""site_structure_audit.py — per-site report on the site-structure policy.

Policy: scripts/site_structure.py (Santino 2026-09-30). Per site:

  homepage   the homepage services strip vs the pinned core
             (plan-input homepage_services -> src/data/homepage-services.json):
             wired in index.astro? mirror in sync? pinned slugs with no page?
  dupes      same-service clusters with 2+ live pages that are neither merged
             (service_merge.py) nor a recorded kept pair (with volumes)
  gbp        GBP services with no decision in clients/{slug}/gbp-service-map.json
             (held / mapped to a page that no longer exists / new_page not built;
             --live also pulls the listing and counts services missing from the map)
  our work   homepage before/after sliders ("Our Work": BeforeAfterSection +
             work.ts pairs) and the separate /case-studies/ section + nav link

Usage:
  python3 scripts/site_structure_audit.py            # fleet table
  python3 scripts/site_structure_audit.py --slug prorestoration -v
  python3 scripts/site_structure_audit.py --live     # + live GBP listing check
  python3 scripts/site_structure_audit.py --json out.json
Exit code 0 always (report, not a gate).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_structure as ss  # noqa: E402


def audit_homepage(slug: str) -> dict:
    site = ss.SITES / slug
    idx = site / "src" / "pages" / "index.astro"
    text = idx.read_text() if idx.exists() else ""
    pinned = ss.homepage_services(slug)
    pages = ss.service_pages(slug)
    data = site / "src" / "data" / "homepage-services.json"
    mirror = json.loads(data.read_text()) if data.exists() else None
    issues = []
    if not pinned:
        issues.append("no homepage_services pinned in plan-input")
    if "homepageServices" not in text:
        issues.append("index.astro not wired to homepage-services.json")
    expect = [s for s in pinned if s in pages][:ss.HOMEPAGE_MAX]
    if mirror is not None and mirror != expect:
        issues.append("homepage-services.json out of sync with plan-input")
    missing = [s for s in pinned if s not in pages]
    if missing:
        issues.append(f"pinned without a page: {missing}")
    shown = mirror if mirror else sorted(pages, key=lambda s: -pages[s]["priority"])[:6]
    return {"pinned": pinned, "shown": shown, "issues": issues}


def audit_gbp(slug: str, live: bool) -> dict:
    m = ss.load_map(slug)
    pages = ss.service_pages(slug)
    counts: dict = {}
    unmapped = []
    for label, e in m["gbp_services"].items():
        v = e.get("verdict")
        counts[v] = counts.get(v, 0) + 1
        if v == "held":
            unmapped.append(label)
        elif v == "mapped" and e.get("page") not in pages:
            unmapped.append(f"{label} (-> missing page {e.get('page')})")
        elif v == "new_page":
            unmapped.append(f"{label} (new page pending)")
    out = {"total": len(m["gbp_services"]), "counts": counts, "unmapped": unmapped}
    if live:
        try:
            import gbp_service_map
            labels = gbp_service_map.gbp_services_for(slug) or []
            known = {ss.norm(k) for k in m["gbp_services"]}
            fresh = [l for l in labels if ss.norm(l) not in known]
            out["live_total"] = len(labels)
            out["not_in_map"] = fresh
            out["unmapped"] += [f"{l} (not in map)" for l in fresh]
        except Exception as e:  # noqa: BLE001
            out["live_error"] = str(e)[:120]
    return out


def audit_our_work(slug: str) -> dict:
    site = ss.SITES / slug
    idx = site / "src" / "pages" / "index.astro"
    text = idx.read_text() if idx.exists() else ""
    work = site / "src" / "data" / "work.ts"
    pairs = work.read_text().count("beforeSrc:") if work.exists() else 0
    header = site / "src" / "components" / "Header.astro"
    htext = header.read_text() if header.exists() else ""
    cs_nav = len(re.findall(r'href="/case-studies/"[^>]*>\s*Case Studies\s*<', htext))
    missing_imgs = []
    if work.exists():
        for src in re.findall(r'(?:before|after)Src:\s*"([^"]+)"', work.read_text()):
            if src.startswith("/") and not (site / "public" / src.lstrip("/")).exists():
                missing_imgs.append(src)
    return {"slider_wired": "<BeforeAfterSection" in text, "pairs": pairs,
            "missing_images": missing_imgs,
            "case_studies_page": (site / "src" / "pages" / "case-studies" / "index.astro").exists(),
            "case_studies_nav_links": cs_nav}


def audit(slug: str, live: bool) -> dict:
    m = ss.load_map(slug)
    return {"slug": slug,
            "homepage": audit_homepage(slug),
            "duplicates": [{"cluster": c["name"], "canonical": c["canonical"], "open": c["open"]}
                           for c in ss.pending_duplicates(slug)],
            "merged": {k: v.get("into") for k, v in m.get("merged", {}).items()},
            "kept_pairs": [(k["a"], k["b"]) for k in m.get("kept_pairs", [])],
            "gbp": audit_gbp(slug, live),
            "our_work": audit_our_work(slug),
            "redirects": ss.normalize_redirects(ss.SITES / slug / "public" / "_redirects", apply=False)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--live", action="store_true", help="pull each live GBP listing too")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    slugs = [a.slug] if a.slug else ss.live_slugs()
    rows = [audit(s, a.live) for s in slugs
            if ss.service_pages(s) and (ss.SITES / s / "src" / "pages" / "index.astro").exists()]
    print(f"{'site':44} {'home':>5} {'dupes':>5} {'merged':>6} {'kept':>4} "
          f"{'gbp':>4} {'unmap':>5} {'B/A':>4} {'CS':>3} {'301s':>5}")
    tot = {"home_bad": 0, "dupes": 0, "merged": 0, "kept": 0, "gbp": 0, "unmapped": 0}
    for r in rows:
        h, g, w = r["homepage"], r["gbp"], r["our_work"]
        home = "ok" if not h["issues"] else "FIX"
        ba = f"{w['pairs']}" if w["slider_wired"] else "off"
        if w["missing_images"]:
            ba += "!"
        cs = "ok" if w["case_studies_page"] and w["case_studies_nav_links"] else "-"
        rd = r["redirects"]
        red = "CAP!" if rd["over_cap"] else ("ORDER" if rd["changed"] and rd["dynamic"] else "ok")
        print(f"{r['slug']:44} {home:>5} {len(r['duplicates']):>5} {len(r['merged']):>6} "
              f"{len(r['kept_pairs']):>4} {g['total']:>4} {len(g['unmapped']):>5} {ba:>4} {cs:>3} {red:>5}")
        tot["home_bad"] += bool(h["issues"])
        tot["dupes"] += len(r["duplicates"])
        tot["merged"] += len(r["merged"])
        tot["kept"] += len(r["kept_pairs"])
        tot["gbp"] += g["total"]
        tot["unmapped"] += len(g["unmapped"])
        if a.verbose or h["issues"] or r["duplicates"]:
            for i in h["issues"]:
                print(f"    homepage: {i}")
            if a.verbose:
                print(f"    homepage shows: {h['shown']}")
            for d in r["duplicates"]:
                print(f"    duplicate: {d['cluster']}: {d['open']} vs canonical {d['canonical']}")
        if a.verbose:
            for u in g["unmapped"]:
                print(f"    gbp unmapped: {u}")
            for k, v in r["merged"].items():
                print(f"    merged: {k} -> {v}")
            if w["missing_images"]:
                print(f"    before/after images missing: {w['missing_images']}")
    print(f"\n{len(rows)} sites | homepage issues: {tot['home_bad']} | open duplicate clusters: "
          f"{tot['dupes']} | merged pages: {tot['merged']} | kept pairs: {tot['kept']} | "
          f"GBP services mapped: {tot['gbp']} ({tot['unmapped']} without a decision)")
    print("301s = _redirects health (ORDER = a static rule after a dynamic one, which Cloudflare drops past 100; CAP! = over 2,000 static / 100 dynamic)")
    print("B/A = before/after pairs on the homepage 'Our Work' slider (off = not wired, "
          "0 = wired but no pairs yet, ! = image missing); CS = /case-studies/ page + nav link")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
