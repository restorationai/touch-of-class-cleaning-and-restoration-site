#!/usr/bin/env python3
"""graffiti_reversal.py: undo the backwards graffiti merge on Air Care + Coastal.

Santino 2026-09-30: service_merge.py folded /services/vandalism-graffiti-removal/
(graffiti removal: 1,300 + near me 210 = about 1,510 searches/mo nationally)
into /services/vandalism-cleanup/ (about 50/mo) on air-care-restoration and
coastal-restoration-services. That direction is backwards. Graffiti Removal is
the canonical page ("Graffiti Removal & Vandalism Cleanup in {City}"), the
vandalism URLs 301 to it. The other four sites that carry both
(homelyft, narestco, quality-contracting-inc, restoration-groups) already
merged the right way and are not touched.

Per site:
  1. RESTORE services/vandalism-graffiti-removal.md from the pre-merge tree
     (the client-requested dev-agent page, manual_override) and retitle it
     "Graffiti Removal & Vandalism Cleanup in {City}".
  2. MOVE every locations/{city}__vandalism-cleanup.md to
     {city}__vandalism-graffiti-removal.md (frontmatter reframed, body kept),
     delete services/vandalism-cleanup.md.
  3. _redirects: drop the graffiti -> vandalism merge rules, repoint any rule
     that ends on a vandalism-cleanup URL, add STATIC 301s for
     /services/vandalism-cleanup/ and each city child, then static-before-
     dynamic normalize (Cloudflare drops rules past the dynamic cap).
  4. Links rewritten site-wide, plan artifacts filtered, plan-input
     services / merged_services / homepage_services updated, the
     gbp-service-map merged record flipped and vandalism/graffiti GBP
     services pointed at the graffiti page.
The image stays the graffiti page's own live image (never replaced).

Usage:
  python3 scripts/graffiti_reversal.py                 # dry-run both sites
  python3 scripts/graffiti_reversal.py --apply
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import service_merge as sm  # noqa: E402
import site_structure as ss  # noqa: E402

SITES = ["air-care-restoration", "coastal-restoration-services"]
OLD, NEW = "vandalism-cleanup", "vandalism-graffiti-removal"
DISPLAY = "Graffiti Removal & Vandalism Cleanup"
MERGE_COMMIT = "badab3593"   # site structure policy commit (pre-merge tree = its parent)
STAMP = "graffiti reversal 2026-09-30"
SECONDARY = ["graffiti removal", "vandalism cleanup", "spray paint removal",
             "graffiti removal near me", "vandalism damage repair", "broken glass cleanup"]
VOLUMES = {"vandalism-graffiti-removal": {"head": 1300, "near_me": 210, "total": 1510},
           "vandalism-cleanup": {"head": 50, "near_me": 0, "total": 50},
           "terms": {"vandalism-graffiti-removal": "graffiti removal",
                     "vandalism-cleanup": "vandalism cleanup"}}
_NAME_RE = re.compile(r"(Vandalism\s*(&|and)\s*Graffiti Removal|Vandalism Clean ?[Uu]p)")


def _fm_split(text: str) -> tuple[list[str], str]:
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    return (m.group(1).splitlines(), text[m.end():]) if m else ([], text)


def reframe(text: str, city: str | None, is_service: bool) -> str:
    lines, rest = _fm_split(text)
    out = []
    for line in lines:
        k = line.split(":", 1)[0]
        if k in ("title", "h1"):
            line = _NAME_RE.sub(DISPLAY, line, count=1)
        elif k == "meta_description":
            line = re.sub(r"(24/7 )?(vandalism (and|&) graffiti removal|vandalism clean ?up)",
                          lambda mm: (mm.group(1) or "") + "graffiti removal and vandalism cleanup",
                          line, count=1, flags=re.I)
            line = re.sub(r'^meta_description: "g', 'meta_description: "G', line)
        elif k == "primary_keyword" and city:
            line = f'primary_keyword: "graffiti removal {city.lower()}"'
        elif k == "secondary_keywords":
            line = "secondary_keywords: " + json.dumps(SECONDARY)
        elif k == "breadcrumb":
            try:
                bc = json.loads(line.split(":", 1)[1])
                if bc:
                    bc[-1]["name"] = DISPLAY
                line = "breadcrumb: " + json.dumps(bc)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        elif k == "service_slug":
            line = f'service_slug: "{NEW}"'
        elif k == "service_display":
            line = f'service_display: "{DISPLAY}"'
        out.append(line)
    return "---\n" + "\n".join(out) + "\n---" + rest


def premerge_service(slug: str) -> str | None:
    r = subprocess.run(["git", "show", f"{MERGE_COMMIT}^:sites/{slug}/src/content/services/{NEW}.md"],
                       cwd=ss.ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def fix_redirects(slug: str, cities: list[str], apply: bool) -> dict:
    red = ss.SITES / slug / "public" / "_redirects"
    text = red.read_text() if red.exists() else ""
    keep, dropped, repointed = [], 0, 0
    for line in text.splitlines():
        if line.startswith("#") and f"/services/{NEW}/ folded into /services/{OLD}/" in line:
            dropped += 1
            continue
        parts = line.split()
        if len(parts) >= 3 and not line.startswith("#"):
            src, dst = parts[0], parts[1]
            if re.match(r"^/(services|service-areas/[a-z0-9-]+)/" + re.escape(NEW) + r"/?$", src) \
                    and f"/{OLD}/" in dst:
                dropped += 1
                continue
            if re.search(r"/" + re.escape(OLD) + r"/?$", dst):
                city = re.match(r"^/service-areas/([a-z0-9-]+)/", dst)
                parts[1] = (f"/service-areas/{city.group(1)}/{NEW}/"
                            if city and city.group(1) in cities else f"/services/{NEW}/")
                line = " ".join(parts)
                repointed += 1
        keep.append(line)
    existing = "\n".join(keep) + "\n"
    pairs = [(f"/services/{OLD}", f"/services/{NEW}/")]
    pairs += [(f"/service-areas/{c}/{OLD}", f"/service-areas/{c}/{NEW}/") for c in cities]
    add = []
    for a, b in pairs:
        for v in (a, a + "/"):
            if not re.search(r"^" + re.escape(v) + r" ", existing, re.M):
                add.append(f"{v} {b} 301")
    if apply:
        new = existing
        if add:
            new += (f"# {STAMP}: /services/{OLD}/ folded into /services/{NEW}/ "
                    "(graffiti is the higher-volume head; scripts/graffiti_reversal.py)\n"
                    + "\n".join(add) + "\n")
        red.write_text(new)
        ss.normalize_redirects(red)
    return {"dropped": dropped, "repointed": repointed, "added": len(add)}


def reverse(slug: str, apply: bool) -> dict:
    site = ss.SITES / slug
    content = site / "src" / "content"
    rep: dict = {"slug": slug}
    old_svc = content / "services" / f"{OLD}.md"
    new_svc = content / "services" / f"{NEW}.md"
    locs = sorted((content / "locations").glob(f"*__{OLD}.md"))
    cities = [f.stem.split("__", 1)[0] for f in locs]
    city, _ = ss.metro_of(slug)
    orig = premerge_service(slug)
    if orig is None:
        raise SystemExit(f"{slug}: no pre-merge {NEW}.md in {MERGE_COMMIT}^")
    svc_text = reframe(orig, city, True)
    # service page links its new city children (the moved pages)
    mm = re.search(r"^internal_links:\s*(\[.*\])\s*$", svc_text, re.M)
    if mm:
        links = json.loads(mm.group(1))
        links += [f"/service-areas/{c}/{NEW}/" for c in cities[:12]]
        links = list(dict.fromkeys(links))
        svc_text = svc_text[:mm.start()] + "internal_links: " + json.dumps(links) + svc_text[mm.end():]
    rep["service_restored"] = str(new_svc.relative_to(ss.ROOT))
    rep["city_pages_moved"] = len(locs)
    if apply:
        new_svc.write_text(svc_text)
        if old_svc.exists():
            old_svc.unlink()
        for f in locs:
            fm = ss._frontmatter(f.read_text())
            dst = f.with_name(f.name.replace(f"__{OLD}.md", f"__{NEW}.md"))
            dst.write_text(reframe(f.read_text(), fm.get("city"), False))
            f.unlink()
    touched = sm.rewrite_links(site, OLD, NEW, set(cities), apply)
    rep["files_relinked"] = len(touched)
    rep["redirects"] = fix_redirects(slug, cities, apply)
    rep["plan_rows_filtered"] = sm.filter_plan_artifacts(slug, OLD, apply)
    if apply:
        sm.dedupe_internal_links(site, True, only=set(touched))
        pi = ss.load_plan_input(slug)
        pi["services"] = [s for s in pi.get("services") or [] if s not in (OLD, NEW)]
        ms = dict(pi.get("merged_services") or {})
        ms.pop(NEW, None)
        ms[OLD] = NEW
        pi["merged_services"] = dict(sorted(ms.items()))
        if pi.get("homepage_services"):
            pi["homepage_services"] = list(dict.fromkeys(
                NEW if s == OLD else s for s in pi["homepage_services"]))
        ss.save_plan_input(slug, pi)
        m = ss.load_map(slug)
        m["merged"].pop(NEW, None)
        m["merged"][OLD] = {"into": NEW, "reason": "Santino 09-30: graffiti removal (~1,510/mo "
                            "nationally) is the canonical head, vandalism cleanup (~50/mo) folds "
                            "into it (reverses the 09-30 merge)", "volumes": VOLUMES,
                            "at": "2026-09-30"}
        for label, e in m["gbp_services"].items():
            n = ss.norm(label)
            if e.get("page") == OLD or re.search(r"\b(graffiti|vandalism)\b", n):
                e.update({"verdict": "mapped", "page": NEW, "source": "alias",
                          "reason": "graffiti / vandalism -> graffiti removal page (09-30 reversal)"})
        ss.save_map(slug, m)
        ss.write_homepage_services(slug)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", choices=SITES)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    for slug in ([a.slug] if a.slug else SITES):
        print(json.dumps(reverse(slug, a.apply)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
