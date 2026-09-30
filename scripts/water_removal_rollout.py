#!/usr/bin/env python3
"""water_removal_rollout.py — water-cleanup becomes the Emergency Water Removal page.

Santino 2026-09-30: "get the water out now" is one search cluster (US
national: emergency water removal 4,400 + near me 12,100, water extraction
3,600, water removal 2,400, water cleanup 1,600 + near me 18,100, emergency
water cleanup 480), separate from water damage restoration (135,000). Every
site with a water-cleanup page (or the earlier emergency-water-removal page)
gets ONE dedicated page at /services/emergency-water-removal/ titled
"Emergency Water Removal & Cleanup in {City}".

Per site:
  1. UNDO the emergency-water-removal -> water-damage-restoration merge from
     service_merge.py (its redirect rules, merged_services + map entries).
  2. MOVE services/water-cleanup.md and every locations/{city}__water-cleanup.md
     to the emergency-water-removal slug. Frontmatter reframed (title, h1,
     meta, keywords, breadcrumb, service_slug/display). Rendered bodies are
     carried over and reframed by one Claude pass per page (--rewrite):
     extraction, removal, cleanup, 24/7 response; every link, number and
     claim preserved; validated before it is written. Placeholder pages stay
     placeholders for the render sweep.
  3. STATIC 301s: /services/water-cleanup/ and each city child -> the matching
     emergency-water-removal URL; old emergency-water-removal city URLs that
     have no new page -> /services/emergency-water-removal/.
  4. Links rewritten site-wide, plan-input services/merged_services/
     homepage_services updated, gbp-service-map entries for water cleanup /
     removal / extraction point at the new page.
  5. IMAGE: the page keeps a real, distinct image without replacing any live
     file. Where /images/services/emergency-water-removal.webp already exists
     (it was that page's own live image) it is used; otherwise the
     water-cleanup image set is copied to the new name (same page, moved).
     water-damage-restoration is never touched.

Usage:
  python3 scripts/water_removal_rollout.py --all            # dry-run
  python3 scripts/water_removal_rollout.py --all --apply --rewrite
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dotenv import load_dotenv  # noqa: E402

import service_merge as sm  # noqa: E402
import site_structure as ss  # noqa: E402

load_dotenv(ss.ROOT / ".env")

OLD, NEW = "water-cleanup", "emergency-water-removal"
DISPLAY = "Emergency Water Removal & Cleanup"
STAMP = "emergency water removal rollout 2026-09-30"
MERGE_COMMIT = "badab3593"   # the duplicate-merge commit (pre-merge tree = its parent)
SECONDARY = ["water removal", "water extraction", "emergency water cleanup", "water cleanup",
             "standing water removal", "flood water removal"]
_TITLE_RE = re.compile(r"(24/7 )?(Emergency )?Water Clean ?[Uu]p", re.I)


def _reframe_title(s: str) -> str:
    return _TITLE_RE.sub(DISPLAY, s, count=1)


def _reframe_meta(s: str) -> str:
    return re.sub(r"(24/7 )?(emergency )?water clean ?up", lambda m: (m.group(1) or "")
                  + "emergency water removal and cleanup", s, count=1, flags=re.I)


def reframe_frontmatter(text: str, city: str | None) -> str:
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if not m:
        return text
    lines = []
    for line in m.group(1).splitlines():
        k = line.split(":", 1)[0]
        if k in ("title", "h1"):
            line = _reframe_title(line)
        elif k == "meta_description":
            line = _reframe_meta(line)
        elif k == "primary_keyword" and city:
            line = f'primary_keyword: "emergency water removal {city.lower()}"'
        elif k == "secondary_keywords":
            line = "secondary_keywords: " + json.dumps(SECONDARY)
        elif k == "breadcrumb":
            try:
                bc = json.loads(line.split(":", 1)[1])
                if bc:
                    bc[-1]["name"] = DISPLAY
                line = "breadcrumb: " + json.dumps(bc)
            except (json.JSONDecodeError, KeyError, TypeError):
                line = _reframe_title(line)
        elif k == "service_slug":
            line = f'service_slug: "{NEW}"'
        elif k == "service_display":
            line = f'service_display: "{DISPLAY}"'
        elif k == "hero" and OLD in line:
            pass  # an explicit hero keeps pointing at the same image
        lines.append(line)
    return "---\n" + "\n".join(lines) + "\n---" + text[m.end():]


REWRITE_SYSTEM = """You edit one page of a local restoration company's website.
The page used to be "Emergency Water Cleanup". It is now "Emergency Water
Removal & Cleanup": the get-the-water-out-now service (24/7 response,
water extraction, standing water removal, pumping, cleanup), distinct from
full water damage restoration (drying, repairs), which has its own page.

Revise the markdown BODY and the FAQ so the framing is emergency water
removal and cleanup. Rules:
- Keep the same structure, headings count, length (within 15%), and facts.
- Keep EVERY link URL, phone number, license number, city name, statistic
  and certification exactly as given. Do not add any new claim, number,
  certification, guarantee, price or response time.
- Where the old copy says "water cleanup" as the service name, say
  "emergency water removal" or "water removal and cleanup" naturally; do not
  stuff keywords.
- Never use em dashes or en dashes; use commas, periods, or parentheses.
Return JSON only: {"body": "<markdown>", "faq": [{"question": "...", "answer": "..."}]}"""


def _dashless(s: str) -> str:
    return s.replace("—", ", ").replace("–", "-")


def rewrite_body(text: str) -> str | None:
    """Claude reframe of a rendered page (body + faq). None = keep as is."""
    import gbp
    m = re.match(r"---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m or ss.PLACEHOLDER_MARK in text:
        return None
    fm, body = m.group(1), m.group(2)
    fq = re.search(r"^faq:\s*(\[.*\])\s*$", fm, re.M)
    faq = json.loads(fq.group(1)) if fq else []
    try:
        out = gbp._anthropic_json(REWRITE_SYSTEM, json.dumps({"body": body, "faq": faq}),
                                  model="claude-sonnet-5")
    except Exception as e:  # noqa: BLE001
        print(f"      rewrite failed ({str(e)[:80]}), content carried unchanged")
        return None
    nb, nf = _dashless(str(out.get("body") or "")), out.get("faq")
    links = lambda s: sorted(set(re.findall(r"\]\(([^)]+)\)", s)))  # noqa: E731
    nums = lambda s: sorted(set(re.findall(r"\(?\d{3}\)?[ .-]\d{3}-\d{4}|\b\d{3,}\b", s)))  # noqa: E731
    ok = (nb and 0.7 <= len(nb) / max(len(body), 1) <= 1.35
          and links(nb) == links(body) and nums(nb) == nums(body)
          and isinstance(nf, list) and len(nf) == len(faq)
          and all(isinstance(x, dict) and x.get("question") and x.get("answer") for x in nf))
    if not ok:
        print("      rewrite rejected by validation, content carried unchanged")
        return None
    nf = [{"question": _dashless(x["question"]), "answer": _dashless(x["answer"])} for x in nf]
    if fq:
        fm = fm[:fq.start()] + "faq: " + json.dumps(nf) + fm[fq.end():]
    return "---\n" + fm + "\n---\n" + nb.lstrip("\n")


def undo_ewr_merge(slug: str, apply: bool) -> int:
    red = ss.SITES / slug / "public" / "_redirects"
    if not red.exists():
        return 0
    lines = red.read_text().splitlines()
    keep, dropped = [], 0
    for line in lines:
        parts = line.split(" ") if line and not line.startswith("#") else []
        ours = (len(parts) == 3 and re.match(r"^/(services|service-areas/[a-z0-9-]+)/"
                                            + re.escape(NEW) + r"/?$", parts[0])
                and "/water-damage-restoration/" in parts[1])
        if (line.startswith("#") and f"/services/{NEW}/ folded into" in line) or ours:
            dropped += 1
            continue
        keep.append(line)
    if apply and dropped:
        red.write_text("\n".join(keep) + "\n")
    return dropped


def premerge_ewr_cities(slug: str) -> list[str]:
    ls = subprocess.run(["git", "ls-tree", "--name-only", f"{MERGE_COMMIT}^",
                         f"sites/{slug}/src/content/locations/"],
                        cwd=ss.ROOT, capture_output=True, text=True).stdout.split()
    return [Path(p).stem.split("__", 1)[0] for p in ls if p.endswith(f"__{NEW}.md")]


def ensure_image(slug: str, apply: bool) -> str:
    site = ss.SITES / slug
    img = site / "public" / "images" / "services"
    meta_p = site / "src" / "data" / "image-meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    if (img / f"{NEW}.webp").exists():
        return "kept existing emergency-water-removal image"
    if not (img / f"{OLD}.webp").exists():
        return "no service image (template fallback)"
    if apply:
        for f in img.glob(f"{OLD}*.webp"):
            shutil.copy2(f, img / f.name.replace(OLD, NEW, 1))
        key_old, key_new = f"/images/services/{OLD}.webp", f"/images/services/{NEW}.webp"
        if key_old in meta and key_new not in meta:
            meta[key_new] = meta[key_old]
            meta_p.write_text(json.dumps(meta, indent=2) + "\n")
    return "water-cleanup image reused (copied to the new name)"


def rollout(slug: str, apply: bool, rewrite: bool) -> dict | None:
    site = ss.SITES / slug
    content = site / "src" / "content"
    svc = content / "services" / f"{OLD}.md"
    pi = ss.load_plan_input(slug)
    merged = pi.get("merged_services") or {}
    if not svc.exists() and NEW not in merged:
        return None
    rep = {"slug": slug}
    rep["undo_redirect_lines"] = undo_ewr_merge(slug, apply)
    locs = sorted((content / "locations").glob(f"*__{OLD}.md"))
    moves = ([(svc, content / "services" / f"{NEW}.md", None)] if svc.exists() else [])
    for f in locs:
        city_slug = f.stem.split("__", 1)[0]
        fm = ss._frontmatter(f.read_text())
        moves.append((f, content / "locations" / f"{city_slug}__{NEW}.md", fm.get("city")))
    svc_city = ss.metro_of(slug)[0]
    rep["pages_moved"] = len(moves)
    rep["image"] = ensure_image(slug, apply)

    def _one(mv):
        src, dst, city = mv
        text = src.read_text()
        text = reframe_frontmatter(text, city or svc_city)
        rendered = ss.PLACEHOLDER_MARK not in text
        if not rendered:
            text = re.sub(r"(Placeholder content for )(.*)", lambda mm: mm.group(1)
                          + _reframe_title(mm.group(2)), text)
        if rewrite and rendered:
            new = rewrite_body(text)
            if new:
                text = new
        return src, dst, text, rendered

    rewritten = 0
    if apply:
        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(_one, moves))
        for src, dst, text, rendered in results:
            dst.write_text(text)
            if dst != src:
                src.unlink()
            rewritten += rendered
    rep["rendered_pages"] = rewritten
    new_cities = {f.stem.split("__", 1)[0] for f in (content / "locations").glob(f"*__{NEW}.md")} \
        if apply else {f.stem.split("__", 1)[0] for f in locs}
    # links, redirects
    touched = sm.rewrite_links(site, OLD, NEW, new_cities, apply)
    rep["files_relinked"] = len(touched)
    red = site / "public" / "_redirects"
    existing = red.read_text() if red.exists() else ""
    pairs = [(f"/services/{OLD}", f"/services/{NEW}/")]
    pairs += [(f"/service-areas/{f.stem.split('__', 1)[0]}/{OLD}",
               f"/service-areas/{f.stem.split('__', 1)[0]}/{NEW}/") for f in locs]
    for c in premerge_ewr_cities(slug):
        if c not in new_cities:
            pairs.append((f"/service-areas/{c}/{NEW}", f"/services/{NEW}/"))
    add = []
    for a, b in pairs:
        for v in (a, a + "/"):
            line = f"{v} {b} 301"
            if line not in existing:
                add.append(line)
    rep["redirect_lines"] = len(add)
    if apply and add:
        red.write_text(existing + ("" if existing.endswith("\n") or not existing else "\n")
                       + f"# {STAMP}: /services/{OLD}/ moved to /services/{NEW}/ "
                         "(scripts/water_removal_rollout.py)\n" + "\n".join(add) + "\n")
        ss.normalize_redirects(red)
    if apply:
        sm.dedupe_internal_links(site, True, only=set(touched))
        # plan-input
        pi = ss.load_plan_input(slug)
        svcs = [NEW if s == OLD else s for s in pi.get("services") or []]
        pi["services"] = list(dict.fromkeys(svcs))
        ms = dict(pi.get("merged_services") or {})
        ms.pop(NEW, None)
        ms[OLD] = NEW
        pi["merged_services"] = dict(sorted(ms.items()))
        if pi.get("homepage_services"):
            pi["homepage_services"] = list(dict.fromkeys(
                NEW if s == OLD else s for s in pi["homepage_services"]))
        ss.save_plan_input(slug, pi)
        # map
        m = ss.load_map(slug)
        m["merged"].pop(NEW, None)
        m["merged"][OLD] = {"into": NEW, "reason": "Santino 09-30: water cleanup renamed into "
                            "the Emergency Water Removal & Cleanup page (one 'get the water out' cluster)",
                            "volumes": {"emergency water removal": 16500, "water extraction": 3600,
                                        "water removal": 2400, "water cleanup": 19700,
                                        "emergency water cleanup": 480},
                            "at": "2026-09-30"}
        m["kept_pairs"] = [k for k in m["kept_pairs"] if OLD not in (k["a"], k["b"])]
        cluster_re = re.compile(r"^(24 7 )?(emergency )?(standing |flood )?water "
                                r"(removal|extraction|clean ?up)( services?| company)?$")
        for label, e in m["gbp_services"].items():
            if e.get("page") == OLD or cluster_re.match(ss.norm(label)):
                e.update({"verdict": "mapped", "page": NEW, "source": "alias",
                          "reason": "water removal/cleanup cluster -> emergency water removal page"})
        ss.save_map(slug, m)
        ss.write_homepage_services(slug)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rewrite", action="store_true", help="Claude-reframe rendered bodies")
    a = ap.parse_args()
    slugs = [a.slug] if a.slug else ss.live_slugs()
    for slug in slugs:
        r = rollout(slug, a.apply, a.rewrite)
        if r:
            print(json.dumps(r), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
