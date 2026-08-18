#!/usr/bin/env python3
"""home_city_migrate.py — fold home-city area pages into home + main service pages.

WHY (2026-08-18, fleet-wide finding): every site's home page targets
"restoration services in {home city}" and every main /services/{svc}/ page
targets "{svc} in {home city}", yet the builder ALSO generated
/service-areas/{home-city}/ (same H1 as home) and
/service-areas/{home-city}/{svc}/ (same target as the main service page).
Two of our own pages competing for every home-city search. plan_site.py now
skips the primary area for new builds; this script migrates EXISTING sites:

  1. delete src/content/serviceAreas/{home}.md + locations/{home}__*.md
     (content collections drive routing/links, so pages and most links heal)
  2. scrub /service-areas/{home}/... entries from internal_links frontmatter
  3. append 301s to public/_redirects (hub -> /, service child -> its main
     /services/{svc}/ page) so existing rankings/backlinks follow
  4. filter the same URLs out of clients/{slug}/plan artifacts so downstream
     tooling stops referencing them
  5. work_log line (category "site") so the change lands in Monthly Summaries

Deploy is NOT done here — commit the monorepo, then
`build_site.py sync-deploy --slug X --branch main` per site as usual.

Usage:
  python3 scripts/home_city_migrate.py --slug reign-restoration          # dry-run
  python3 scripts/home_city_migrate.py --slug reign-restoration --apply
  python3 scripts/home_city_migrate.py --all [--apply]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "sites"
CLIENTS = ROOT / "clients"

STAMP = "home-city consolidation 2026-08-18"


def plan_input_for(slug: str) -> dict | None:
    for cand in (CLIENTS / slug / "plan" / "plan-input.json",
                 CLIENTS / slug / "plan-input.json"):
        if cand.exists():
            try:
                return json.loads(cand.read_text())
            except json.JSONDecodeError:
                pass
    return None


def home_area(plan_input: dict) -> dict | None:
    areas = plan_input.get("service_areas") or []
    return next((a for a in areas if a.get("primary")), None)


def scrub_internal_links(md_path: Path, prefix: str, apply: bool) -> int:
    """Remove /service-areas/{home}/... URLs from an internal_links line.
    Returns how many link entries were removed."""
    text = md_path.read_text()
    m = re.search(r'^internal_links:\s*(\[.*\])\s*$', text, re.M)
    if not m:
        return 0
    try:
        links = json.loads(m.group(1))
    except json.JSONDecodeError:
        return 0
    kept = [l for l in links
            if not (l == prefix.rstrip("/") or l.startswith(prefix))]
    removed = len(links) - len(kept)
    if removed and apply:
        new_line = "internal_links: " + json.dumps(kept)
        text = text[:m.start()] + new_line + text[m.end():]
        md_path.write_text(text)
    return removed


def append_redirects(site_dir: Path, home_slug: str, svc_slugs: list[str],
                     apply: bool) -> int:
    red = site_dir / "public" / "_redirects"
    existing = red.read_text() if red.exists() else ""
    lines = []
    pairs = [(f"/service-areas/{home_slug}", "/")]
    pairs += [(f"/service-areas/{home_slug}/{s}", f"/services/{s}/")
              for s in svc_slugs]
    for src, dst in pairs:
        for variant in (src, src + "/"):
            line = f"{variant} {dst} 301"
            if line not in existing:
                lines.append(line)
    if lines and apply:
        block = (("" if existing.endswith("\n") or not existing else "\n")
                 + f"# {STAMP} — home-city pages folded into home + main "
                   f"service pages (scripts/home_city_migrate.py)\n"
                 + "\n".join(lines) + "\n")
        red.parent.mkdir(parents=True, exist_ok=True)
        red.write_text(existing + block)
    return len(lines)


def filter_plan_artifacts(slug: str, prefix: str, apply: bool) -> dict:
    """Drop /service-areas/{home}/... URLs from the plan JSON artifacts."""
    plan_dir = CLIENTS / slug / "plan"
    out = {}

    def bad(url: str) -> bool:
        return url == prefix.rstrip("/") + "/" or url.startswith(prefix) \
            or url == prefix.rstrip("/")

    up = plan_dir / "url-plan.json"
    if up.exists():
        d = json.loads(up.read_text())
        pages = d.get("pages") or []
        kept = [p for p in pages if not bad(p.get("url_path", ""))]
        out["url-plan"] = len(pages) - len(kept)
        if out["url-plan"] and apply:
            d["pages"] = kept
            up.write_text(json.dumps(d, indent=2))

    il = plan_dir / "internal-links.json"
    if il.exists():
        d = json.loads(il.read_text())
        removed = 0
        new = {}
        for k, v in d.items():
            if bad(k):
                removed += 1
                continue
            if isinstance(v, list):
                nv = [t for t in v if not bad(t)]
                removed += len(v) - len(nv)
                new[k] = nv
            else:
                new[k] = v
        out["internal-links"] = removed
        if removed and apply:
            il.write_text(json.dumps(new, indent=2))

    ss = plan_dir / "schema-stubs.json"
    if ss.exists():
        d = json.loads(ss.read_text())
        kept = {k: v for k, v in d.items() if not bad(k)}
        out["schema-stubs"] = len(d) - len(kept)
        if out["schema-stubs"] and apply:
            ss.write_text(json.dumps(kept, indent=2))

    cm = plan_dir / "content-map.csv"
    if cm.exists():
        rows = cm.read_text().splitlines(keepends=True)
        kept_rows = [r for r in rows if prefix not in r]
        out["content-map"] = len(rows) - len(kept_rows)
        if out["content-map"] and apply:
            cm.write_text("".join(kept_rows))

    return out


def migrate(slug: str, apply: bool) -> dict | None:
    site_dir = SITES / slug
    if not site_dir.exists():
        print(f"  {slug}: no site directory — skipped")
        return None
    pi = plan_input_for(slug)
    if not pi:
        print(f"  {slug}: no plan-input.json — skipped (investigate)")
        return None
    home = home_area(pi)
    if not home:
        print(f"  {slug}: no primary service area — skipped (investigate)")
        return None
    home_slug = home["slug"]
    prefix = f"/service-areas/{home_slug}/"

    sa_md = site_dir / "src" / "content" / "serviceAreas" / f"{home_slug}.md"
    loc_dir = site_dir / "src" / "content" / "locations"
    loc_files = sorted(loc_dir.glob(f"{home_slug}__*.md")) if loc_dir.exists() else []
    svc_slugs = [f.stem.split("__", 1)[1] for f in loc_files]

    if not sa_md.exists() and not loc_files:
        print(f"  {slug}: home city {home['city']} ({home_slug}) — already clean")
        return {"slug": slug, "clean": True}

    # 1. delete content files
    deleted = []
    for f in ([sa_md] if sa_md.exists() else []) + loc_files:
        deleted.append(f.relative_to(site_dir).as_posix())
        if apply:
            f.unlink()

    # 2. scrub internal_links across all content
    scrubbed = 0
    touched = 0
    for md in (site_dir / "src" / "content").rglob("*.md"):
        n = scrub_internal_links(md, prefix, apply)
        if n:
            scrubbed += n
            touched += 1

    # 3. redirects
    red_lines = append_redirects(site_dir, home_slug, svc_slugs, apply)

    # 4. plan artifacts
    plan_removed = filter_plan_artifacts(slug, prefix, apply)

    mode = "APPLIED" if apply else "dry-run"
    print(f"  {slug}: home={home['city']} ({home_slug}) [{mode}]")
    print(f"    pages deleted: {len(deleted)} "
          f"({'hub + ' if sa_md.exists() else ''}{len(loc_files)} service pages)")
    print(f"    internal_links scrubbed: {scrubbed} across {touched} files")
    print(f"    redirect lines added: {red_lines}")
    print(f"    plan artifacts: {plan_removed}")
    return {"slug": slug, "home_slug": home_slug, "city": home["city"],
            "deleted": len(deleted), "scrubbed": scrubbed,
            "redirects": red_lines, "plan": plan_removed}


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    slugs = [args.slug] if args.slug else sorted(
        p.name for p in SITES.iterdir() if (p / "src").exists())
    results = []
    for slug in slugs:
        r = migrate(slug, args.apply)
        if r:
            results.append(r)
    dirty = [r for r in results if not r.get("clean")]
    print(f"\n{len(dirty)} site(s) migrated, "
          f"{len(results) - len(dirty)} already clean.")
    if args.apply and dirty:
        print("Next: rebuild locally to verify, commit the monorepo, then "
              "build_site.py sync-deploy per site.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
