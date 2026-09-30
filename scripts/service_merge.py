#!/usr/bin/env python3
"""service_merge.py — fold duplicate service pages into their canonical twin.

WHY (Santino 2026-09-30): "We don't really need duplicate pages that cover
the same service, unless those services have a high volume of search terms
each." Dry1 Out shipped /services/emergency-board-up/ AND
/services/emergency-board-ups/; ProRestoration carried air-duct-cleaning AND
air-duct-hvac-cleaning. The cluster table and the keep/merge bar live in
scripts/site_structure.py (rule 4). This script applies it:

  decide   per site, every same-service cluster with 2+ live pages:
           variant members (plural / 24-7 / emergency / combined name) merge;
           a non-variant twin stays only when its head term + "near me"
           reaches DUP_KEEP_NATIONAL_MIN searches/mo nationally (DataForSEO).
  merge    for each merged page (src -> dst):
             1. delete services/{src}.md + locations/{city}__{src}.md
             2. rewrite every /services/{src}/ and /service-areas/{c}/{src}/
                link under sites/{slug}/src (and public text files) to the
                canonical URL; dedupe internal_links, drop self-links
             3. append 301s to public/_redirects (the site's existing
                redirect mechanism): service -> /services/{dst}/, each city
                child -> /service-areas/{c}/{dst}/ (or /services/{dst}/)
             4. plan-input: drop src from services / homepage_services, add
                merged_services {src: dst} (plan_site.py honors it, so the
                core floor never rebuilds it); filter plan artifacts
             5. record merged + kept pairs (with volumes) in
                clients/{slug}/gbp-service-map.json
  The sitemap is generated from the content collections at build time, so it
  drops merged URLs on the next deploy. Deploy is NOT done here: commit, then
  build_site.py sync-deploy per site.

Usage:
  python3 scripts/service_merge.py --slug dry1-out-restoration-and-construction
  python3 scripts/service_merge.py --all [--apply]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dotenv import load_dotenv  # noqa: E402

import site_structure as ss  # noqa: E402

load_dotenv(ss.ROOT / ".env")

STAMP = "duplicate service merge 2026-09-30"
TEXT_EXT = {".md", ".mdx", ".astro", ".ts", ".tsx", ".js", ".mjs", ".json"}


def decide(slug: str) -> list[dict]:
    """[{cluster, canonical, member, variant, action: merge|keep, demand}]"""
    m = ss.load_map(slug)
    kept = {tuple(sorted((k["a"], k["b"]))) for k in m.get("kept_pairs", [])}
    out = []
    for c in ss.duplicate_clusters(slug):
        canon = c["canonical"]
        canon_head = next(h for s, h, _ in c["members"] if s == canon)
        for s, head, variant in c["secondaries"]:
            if tuple(sorted((canon, s))) in kept:
                continue
            demand = ss.national_demand(head)
            canon_demand = ss.national_demand(canon_head)
            if variant:
                action, why = "merge", "phrasing variant of the same service"
            elif demand["total"] >= ss.DUP_KEEP_NATIONAL_MIN and head != canon_head:
                action, why = "keep", (f"distinct query with {demand['total']:,}/mo "
                                       f"nationally (head + near me)")
            else:
                action, why = "merge", (f"{demand['total']:,}/mo nationally (head + near me) "
                                        f"< {ss.DUP_KEEP_NATIONAL_MIN:,} bar")
            out.append({"cluster": c["name"], "canonical": canon, "member": s,
                        "variant": variant, "action": action, "reason": why,
                        "volumes": {s: demand, canon: canon_demand,
                                    "terms": {s: head, canon: canon_head}}})
    return out


def _boundary(src: str) -> str:
    return re.escape(src) + r"(?![a-z0-9-])"


def rewrite_text(text: str, src: str, dst: str, dst_cities: set[str]) -> str:
    """Page URLs only: /services/{src} and /service-areas/{c}/{src}. Never
    asset paths like /images/services/{src}.webp (image files stay put)."""
    svc_re = re.compile(r"(?<!/images)(?<!/img)/services/" + _boundary(src) + r"(?!\.)")
    loc_re = re.compile(r"/service-areas/([a-z0-9-]+)/" + _boundary(src) + r"(?!\.)/?")

    def _loc(mm: re.Match) -> str:
        city = mm.group(1)
        if city in dst_cities:
            return f"/service-areas/{city}/{dst}/"
        return f"/services/{dst}/"

    new = loc_re.sub(_loc, text)
    new = svc_re.sub(f"/services/{dst}", new)
    return new.replace(f"/services/{dst}//", f"/services/{dst}/")


def rewrite_links(site: Path, src: str, dst: str, dst_cities: set[str], apply: bool) -> set:
    touched: set = set()
    files = [p for p in (site / "src").rglob("*") if p.is_file() and p.suffix in TEXT_EXT]
    files += [p for p in (site / "public").glob("*.txt")]
    for p in files:
        try:
            text = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if src not in text:
            continue
        new = rewrite_text(text, src, dst, dst_cities)
        if new != text:
            touched.add(p)
            if apply:
                p.write_text(new)
    return touched


def dedupe_text(text: str, rel: str) -> str:
    """Dedupe one content file's internal_links and drop its self-link (a
    merge can turn two distinct links into the same URL). rel is the path
    under src/content, e.g. services/x.md or locations/city__svc.md."""
    mm = re.search(r"^internal_links:\s*(\[.*\])\s*$", text, re.M)
    if not mm:
        return text
    try:
        links = json.loads(mm.group(1))
    except json.JSONDecodeError:
        return text
    stem = Path(rel).stem
    own = None
    if rel.startswith("services/"):
        own = f"/services/{stem}/"
    elif rel.startswith("locations/") and "__" in stem:
        city, svc = stem.split("__", 1)
        own = f"/service-areas/{city}/{svc}/"
    seen, out = set(), []
    for link in links:
        if link == own or link in seen:
            continue
        seen.add(link)
        out.append(link)
    if out == links:
        return text
    return text[:mm.start()] + "internal_links: " + json.dumps(out) + text[mm.end():]


def dedupe_internal_links(site: Path, apply: bool, only: set[Path] | None = None) -> int:
    fixed = 0
    content = site / "src" / "content"
    for md in content.rglob("*.md"):
        if only is not None and md not in only:
            continue
        text = md.read_text(errors="replace")
        new = dedupe_text(text, md.relative_to(content).as_posix())
        if new != text:
            fixed += 1
            if apply:
                md.write_text(new)
    return fixed


def append_redirects(site: Path, src: str, dst: str, cities: list[str],
                     dst_cities: set[str], apply: bool) -> int:
    """Static rule for the service page; city children use ONE placeholder
    rule (Cloudflare Pages: 2,000 static / 100 dynamic), with static
    overrides first for any city that has no canonical child page."""
    red = site / "public" / "_redirects"
    existing = red.read_text() if red.exists() else ""
    pairs = [(f"/services/{src}", f"/services/{dst}/")]
    for c in cities:
        if c not in dst_cities:
            pairs.append((f"/service-areas/{c}/{src}", f"/services/{dst}/"))
    if cities:
        pairs.append((f"/service-areas/:city/{src}", f"/service-areas/:city/{dst}/"))
    lines = []
    for a, b in pairs:
        for variant in (a, a + "/"):
            line = f"{variant} {b} 301"
            if line not in existing:
                lines.append(line)
    if lines and apply:
        block = (("" if existing.endswith("\n") or not existing else "\n")
                 + f"# {STAMP}: /services/{src}/ folded into /services/{dst}/ "
                   "(scripts/service_merge.py)\n" + "\n".join(lines) + "\n")
        red.parent.mkdir(parents=True, exist_ok=True)
        red.write_text(existing + block)
    return len(lines)


def filter_plan_artifacts(slug: str, src: str, apply: bool) -> int:
    plan = ss.CLIENTS / slug / "plan"
    pat = re.compile(r"/(services|service-areas/[a-z0-9-]+)/" + _boundary(src))

    def bad(url: str) -> bool:
        return bool(pat.search(url or ""))

    removed = 0
    up = plan / "url-plan.json"
    if up.exists():
        d = json.loads(up.read_text())
        pages = d.get("pages") or []
        kept = [p for p in pages if not bad(p.get("url_path", ""))
                and p.get("service_slug") != src]
        removed += len(pages) - len(kept)
        if apply and len(kept) != len(pages):
            d["pages"] = kept
            up.write_text(json.dumps(d, indent=2))
    il = plan / "internal-links.json"
    if il.exists():
        d = json.loads(il.read_text())
        new = {}
        for k, v in d.items():
            if bad(k):
                removed += 1
                continue
            new[k] = [t for t in v if not bad(t)] if isinstance(v, list) else v
        if apply and new != d:
            il.write_text(json.dumps(new, indent=2))
    sp = plan / "schema-stubs.json"
    if sp.exists():
        d = json.loads(sp.read_text())
        kept = {k: v for k, v in d.items() if not bad(k)}
        removed += len(d) - len(kept)
        if apply and len(kept) != len(d):
            sp.write_text(json.dumps(kept, indent=2))
    cm = plan / "content-map.csv"
    if cm.exists():
        rows = cm.read_text().splitlines(keepends=True)
        kept_rows = [r for r in rows if not bad(r)]
        removed += len(rows) - len(kept_rows)
        if apply and len(kept_rows) != len(rows):
            cm.write_text("".join(kept_rows))
    for pip in (plan / "plan-input.json",):
        if pip.exists() and apply:
            d = json.loads(pip.read_text())
            if src in (d.get("services") or []):
                d["services"] = [s for s in d["services"] if s != src]
                pip.write_text(json.dumps(d, indent=2) + "\n")
    return removed


def merge(slug: str, src: str, dst: str, evidence: dict, apply: bool) -> dict:
    site = ss.SITES / slug
    loc_dir = site / "src" / "content" / "locations"
    src_locs = sorted(loc_dir.glob(f"*__{src}.md")) if loc_dir.exists() else []
    cities = [f.stem.split("__", 1)[0] for f in src_locs]
    dst_cities = {f.stem.split("__", 1)[0] for f in loc_dir.glob(f"*__{dst}.md")} \
        if loc_dir.exists() else set()
    svc_md = site / "src" / "content" / "services" / f"{src}.md"
    deleted = ([svc_md] if svc_md.exists() else []) + src_locs
    if apply:
        for f in deleted:
            f.unlink()
    touched = rewrite_links(site, src, dst, dst_cities, apply)
    reds = append_redirects(site, src, dst, cities, dst_cities, apply)
    plan_rm = filter_plan_artifacts(slug, src, apply)
    if apply:
        pi = ss.load_plan_input(slug)
        pi["services"] = [s for s in pi.get("services") or [] if s != src]
        if pi.get("homepage_services"):
            hp = [dst if s == src else s for s in pi["homepage_services"]]
            pi["homepage_services"] = list(dict.fromkeys(hp))
        ms = pi.get("merged_services") or {}
        ms[src] = dst
        pi["merged_services"] = dict(sorted(ms.items()))
        ss.save_plan_input(slug, pi)
        m = ss.load_map(slug)
        m["merged"][src] = {"into": dst, "reason": evidence.get("reason"),
                            "volumes": evidence.get("volumes"),
                            "at": datetime.now(timezone.utc).date().isoformat()}
        for v in m["gbp_services"].values():
            if v.get("page") == src:
                v["page"] = dst
        ss.save_map(slug, m)
    return {"src": src, "dst": dst, "pages_deleted": len(deleted),
            "files_relinked": len(touched), "_touched": touched, "redirect_lines": reds, "plan_rows": plan_rm}


def record_kept(slug: str, d: dict) -> None:
    m = ss.load_map(slug)
    pair = tuple(sorted((d["canonical"], d["member"])))
    if any(tuple(sorted((k["a"], k["b"]))) == pair for k in m["kept_pairs"]):
        return
    m["kept_pairs"].append({"a": d["canonical"], "b": d["member"],
                            "reason": d["reason"], "volumes": d["volumes"]})
    ss.save_map(slug, m)


def run(slug: str, apply: bool) -> list[dict]:
    decisions = decide(slug)
    results = []
    for d in decisions:
        if d["action"] == "keep":
            print(f"  KEEP  {d['member']:40} + {d['canonical']:28} {d['reason']}")
            if apply:
                record_kept(slug, d)
            results.append({**d})
            continue
        r = merge(slug, d["member"], d["canonical"], d, apply)
        print(f"  MERGE {d['member']:40} -> {d['canonical']:28} "
              f"({r['pages_deleted']} pages, {r['redirect_lines']} redirects, "
              f"{r['files_relinked']} files relinked) {d['reason']}")
        results.append({**d, **r})
    if apply and results:
        ded = dedupe_internal_links(ss.SITES / slug, apply, only=set().union(*[r.get("_touched", set()) for r in results]))
        if ded:
            print(f"  internal_links deduped in {ded} files")
        ss.write_homepage_services(slug)
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--json-out", help="write the decisions to this file")
    a = ap.parse_args()
    slugs = [a.slug] if a.slug else ss.live_slugs()
    ss.prefetch_national(ss.cluster_heads())
    if not ss._NATIONAL:
        print("DataForSEO national volumes unavailable: refusing to decide merges blind")
        return 1
    report = {}
    for slug in slugs:
        if not ss.duplicate_clusters(slug):
            continue
        print(f"\n== {slug} [{'APPLY' if a.apply else 'dry-run'}]")
        report[slug] = run(slug, a.apply)
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
