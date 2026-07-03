#!/usr/bin/env python3
"""
Rank AI — Hero image backfill.

Finds published blog posts in sites/{slug}/src/content/blog/*.md whose
frontmatter lacks a `hero:` line (or has an empty one), generates a hero image
via Gemini (Nano Banana) following the client's image-style-guide.md rules,
converts to WebP, uploads to R2 under blog/{YYYY/MM}/{post-slug}/hero.webp
(YYYY/MM from the post's published_at), and inserts `hero:` + `og:` lines into
the frontmatter.

Rerunnable: posts that already have a hero are never touched. Per-post
failures are reported and skipped — the run never aborts.

Does NOT commit and does NOT build/deploy anything.

Usage:
  python3 scripts/backfill_heroes.py                      # all default clients
  python3 scripts/backfill_heroes.py narestco             # one client
  python3 scripts/backfill_heroes.py --dry-run            # print prompts only
  python3 scripts/backfill_heroes.py --flash              # use Flash image model
  python3 scripts/backfill_heroes.py --sleep 6            # seconds between gens

Env (rank-ai/.env, auto-loaded): GOOGLE_AI_API_KEY, CLOUDFLARE_R2_API_TOKEN.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
REPO_ROOT = SCRIPT_DIR.parent

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass  # fall back to ambient environment

import content_writer as cw  # noqa: E402 — gemini_generate_image + model ids
import image_utils           # noqa: E402 — WebP conversion + R2 upload

SITES_DIR = REPO_ROOT / "sites"

DEFAULT_SLUGS = ["narestco", "homepriderestorationandcleaning"]

# ----------------------------------------------------------------------------
# Per-client style constants (from clients/{slug}/image-style-guide.md)
# ----------------------------------------------------------------------------

CLIENT_STYLE = {
    "narestco": {
        "domain": "narestco.com",
        "uniform": (
            "restoration technician in a dark brick-red (#a83227) NARESTCO-branded "
            "work polo with an IICRC certification patch, neutral charcoal work "
            "pants, sturdy work boots"
        ),
        "region": (
            "Pacific Northwest residential setting near Federal Way, Washington — "
            "1970s-80s rambler housing stock, cedar siding and evergreen "
            "silhouettes glimpsed through windows, low gray Puget Sound cloud "
            "cover and drizzle outside"
        ),
    },
    "homepriderestorationandcleaning": {
        "domain": "homepriderestorationandcleaning.com",
        "uniform": (
            "restoration technician in a navy (#0d1b3e) Home Pride-branded work "
            "polo with a small orange accent stripe and an IICRC certification "
            "patch, neutral khaki work pants, sturdy work boots"
        ),
        "region": (
            "Utah Valley residential setting near Saratoga Springs, Utah — "
            "2000s stucco-and-brick suburban two-story housing stock, dry "
            "high-desert light, Wasatch mountain silhouette glimpsed through a "
            "window"
        ),
    },
}

STYLE_SUFFIX = (
    "Professional editorial photography, mirrorless full-frame look, neutral "
    "white balance, cool diffused interior light with warm accents from a "
    "portable work light where noted, true-to-life muted colors, layered depth "
    "with foreground equipment interest, the left third of the frame "
    "compositionally calmer for headline overlay, faces obscured (photographed "
    "from behind or at a side angle, never looking at camera), competent "
    "mid-task posture — not posed, no smiling at camera, no text, no "
    "watermarks, no logos, 16:9 editorial hero composition."
)

# ----------------------------------------------------------------------------
# Curated scene per post — varied deliberately; no two identical.
# Keyed by (client_slug, post_slug). Service posts: worker mid-task with the
# service's equipment/PPE. Informational / insurance posts: calm documentation
# scene per the content-writer prompt rules.
# ----------------------------------------------------------------------------

SCENES = {
    # ---------------- narestco (Federal Way, WA) ----------------
    ("narestco", "black-mold-vs-regular-mold"): (
        "Medium 50mm shot of a {uniform}, seen from a side angle, crouched in a "
        "bathroom corner shining a flashlight on a patch of dark mold staining "
        "along the drywall above the baseboard, holding a surface swab test kit "
        "in a gloved hand, clipboard with sample labels resting on the closed "
        "toilet lid. Calm inspection mood, minimal PPE (nitrile gloves, N95 "
        "hanging ready at the neck). {region}."
    ),
    ("narestco", "burst-pipe-emergency-checklist"): (
        "A {uniform}, photographed from behind, reaching under a kitchen sink "
        "to close the water supply shut-off valve with a gloved hand, water "
        "sheen pooling on the vinyl floor around his knees, a portable "
        "extraction unit and hose staged in the doorway behind him. Urgent but "
        "controlled emergency-response feel, headlamp glow under the cabinet. "
        "{region}."
    ),
    ("narestco", "choosing-a-restoration-company"): (
        "Calm documentation scene: a restoration project manager ({uniform}), "
        "back to camera, standing in a tidy living room reviewing a printed "
        "written estimate on a clipboard, two equipment cases and a moisture "
        "meter neatly staged at his feet, drying equipment visible but powered "
        "down. Methodical, trustworthy, in-command mood — no active damage "
        "drama. {region}."
    ),
    ("narestco", "how-long-does-water-damage-restoration-take"): (
        "Wide 28mm shot of a water-damage drying job in progress: a {uniform}, "
        "side angle, pressing a pin-type moisture meter against drywall with a "
        "visible wet-to-dry demarcation line, three air movers arranged across "
        "the living-room floor and an LGR dehumidifier running mid-frame, hoses "
        "as leading lines. {region}."
    ),
    ("narestco", "mold-after-water-damage"): (
        "A {uniform}, kneeling with his back three-quarters to camera at a "
        "living-room baseboard, holding a moisture meter against a water-stained "
        "wall where the first speckles of early mold growth are appearing at the "
        "stain's edge, a roll of poly containment sheeting and blue tape staged "
        "beside him ready to isolate the area. Close 60mm detail-leaning "
        "composition. {region}."
    ),
    ("narestco", "smoke-odor-removal-techniques"): (
        "A {uniform}, photographed from behind, setting up a hydroxyl generator "
        "in a hallway with faint yellow-brown smoke staining on the upper walls "
        "and ceiling, a HEPA air scrubber with flex ducting running in the "
        "background, subtle haze in the work-light beam. Specialty-equipment "
        "focus, slightly underexposed serious mood. {region}."
    ),
    ("narestco", "signs-of-hidden-mold"): (
        "Inspection scene: a {uniform}, side angle with cap brim shadowing the "
        "face, operating an air-sampling pump with a spore-trap cassette on a "
        "small tripod beside a partially opened wall cavity where dark staining "
        "is just visible on the stud bay, flashlight beam raking across the "
        "opening. Clipboard-and-camera investigative vibe, minimal PPE. "
        "{region}."
    ),
    ("narestco", "what-to-do-first-24-hours-water-damage"): (
        "A {uniform}, back to camera, guiding a carpet extraction wand across a "
        "soaked beige carpet with visible standing-water sheen, extraction hose "
        "curving through the frame toward the front door, rain-streaked window "
        "and gray drizzle outside reinforcing the emergency-response urgency. "
        "{region}."
    ),
    ("narestco", "sewage-backup-health-risks"): (
        "A {uniform} wearing a full white Tyvek suit over the brand polo (collar "
        "color just visible), half-face respirator and rubber boots, "
        "photographed from behind at the top of basement stairs staging a "
        "submersible pump and discharge hose, caution demarcation tape across "
        "the doorway. Restrained and clinical — no visible waste, the "
        "professionalism is the subject. {region}."
    ),
    ("narestco", "storm-damage-insurance-claim-checklist"): (
        "Calm insurance-documentation scene: a restoration project manager "
        "({uniform}) with a hi-vis vest over the polo, side angle, standing at "
        "the base of an extension ladder photographing a blue-tarped roof "
        "section with a phone, clipboard with a claim checklist tucked under one "
        "arm, wind-scattered branches on the wet lawn, overcast sky and "
        "evergreens behind the house. {region}."
    ),

    # -------- homepriderestorationandcleaning (Saratoga Springs, UT) --------
    ("homepriderestorationandcleaning", "black-mold-vs-regular-mold"): (
        "Close 60mm detail-leaning shot: the gloved hands and side profile of a "
        "{uniform} holding a bright LED inspection light up to a tile-and-drywall "
        "junction above a bathtub where two different mold patches are visible — "
        "one greenish-dark, one lighter gray — a labeled swab sample vial held in "
        "the other hand. Shallow f/2.8 focus on the staining. {region}."
    ),
    ("homepriderestorationandcleaning", "burst-pipe-emergency-checklist"): (
        "A {uniform}, photographed from behind in a basement utility room, "
        "gripping a pipe wrench on the main shut-off valve beside a burst copper "
        "pipe with a visible split seam, headlamp beam on the pipe, water "
        "trailing down the concrete wall, portable extractor staged at the foot "
        "of the stairs. Controlled-urgency emergency feel. {region}."
    ),
    ("homepriderestorationandcleaning", "choosing-a-restoration-company"): (
        "Calm walk-through scene: a restoration estimator ({uniform}), back "
        "three-quarters to camera, walking a home's entry hallway holding a "
        "tablet with an inspection form, two branded equipment cases parked "
        "neatly inside the front door, morning light across hardwood. "
        "Trust-and-competence mood, no visible damage drama. {region}."
    ),
    ("homepriderestorationandcleaning", "does-homeowners-insurance-cover-water-damage"): (
        "Calm insurance-paperwork scene: a restoration project manager "
        "({uniform}), side angle at a kitchen table, annotating a printed "
        "insurance claim form beside a moisture-mapping floor plan and a "
        "moisture meter used as a paperweight, a dried water-stain demarcation "
        "visible on the wall behind, mountain view out the window. Quiet "
        "documentation moment, warm table-lamp accent. {region}."
    ),
    ("homepriderestorationandcleaning", "fire-damage-restoration-process"): (
        "A {uniform} in a white Tyvek suit and half-face HEPA respirator, "
        "photographed from behind, dry-sponging matte black soot off charred "
        "drywall in a fire-damaged living room, a HEPA air scrubber with flex "
        "duct running in the mid-ground, contents boxed and labeled along the "
        "wall. Slightly underexposed, serious and methodical. {region}."
    ),
    ("homepriderestorationandcleaning", "how-to-test-for-mold"): (
        "Inspection scene: a {uniform}, side angle, adjusting an air-sampling "
        "pump with spore-trap cassette mounted on a tripod in the middle of a "
        "bedroom, an open mold test kit and clipboard laid out on a drop cloth "
        "in the foreground, closet door open with faint staining visible on the "
        "back wall. Clipboard-and-camera investigative vibe. {region}."
    ),
    ("homepriderestorationandcleaning", "how-long-does-water-damage-restoration-take"): (
        "Wide 24mm environmental shot of a family room mid-dry-out: a grid of "
        "five air movers aimed at the walls, an LGR dehumidifier with drain hose "
        "center-frame, and a {uniform}, back to camera, crouched to read and log "
        "the dehumidifier's display onto a drying log clipboard. Equipment as "
        "the story, day-3-of-drying feel. {region}."
    ),
    ("homepriderestorationandcleaning", "signs-of-hidden-mold"): (
        "A {uniform}, kneeling side-on, using a pry bar to gently pull a section "
        "of baseboard away from a hallway wall, revealing a dark band of hidden "
        "mold growth behind it, flashlight clenched under his arm lighting the "
        "reveal, a moisture meter on the floor in the foreground. Discovery "
        "moment, shallow focus on the revealed staining. {region}."
    ),
    ("homepriderestorationandcleaning", "mold-after-water-damage"): (
        "A {uniform}, back three-quarters to camera, marking moisture-reading "
        "boundaries on a water-stained wall with strips of green painter's tape, "
        "early pin-dot mold spotting emerging inside the taped zone, a doorway "
        "behind him already sealed with poly containment sheeting and a zipper. "
        "Methodical containment-in-progress mood. {region}."
    ),
    ("homepriderestorationandcleaning", "sewage-backup-health-risks"): (
        "A {uniform} in full PPE — white Tyvek suit, half-face respirator, "
        "double nitrile gloves, rubber boots — photographed from behind while "
        "positioning a negative-air machine at the base of basement stairs, "
        "poly sheeting containment behind, biohazard-caution demarcation tape in "
        "the foreground. Clinical and restrained, no visible waste anywhere. "
        "{region}."
    ),
    ("homepriderestorationandcleaning", "storm-damage-insurance-claim-checklist"): (
        "Calm documentation scene: a {uniform} with a hi-vis vest, side angle in "
        "a driveway, photographing hail-dented siding and wind-lifted shingles "
        "on a two-story stucco home with a phone while holding a clipboard "
        "checklist, scattered shingle fragments on the lawn, dramatic clearing "
        "storm clouds over the mountains behind. {region}."
    ),
    ("homepriderestorationandcleaning", "what-to-do-first-24-hours-water-damage"): (
        "A {uniform}, back to camera, lifting the corner of a sofa onto foam "
        "blocks in a water-soaked family room while a second technician "
        "(background, out of focus) runs an extraction wand across the wet "
        "carpet, area rug rolled and propped by the door, first-hours triage "
        "energy. {region}."
    ),
    ("homepriderestorationandcleaning", "smoke-odor-removal-techniques"): (
        "A {uniform}, photographed from behind through a light haze, operating a "
        "thermal fogger in a living room with subtle yellowed smoke film on the "
        "walls and ceiling, an ozone generator staged on a drop cloth in the "
        "foreground with its cord coiled, work light cutting through the fog. "
        "Specialty-equipment showcase, moody and technical. {region}."
    ),
}

# Generic fallback for any future post not curated above.
SERVICE_FALLBACK = {
    "water-damage-restoration": "operating an air mover and checking a moisture meter against wet drywall, extraction hoses in frame",
    "mold-remediation": "in Tyvek suit and respirator working inside poly containment with a HEPA vacuum",
    "mold-inspection-testing": "running an air-sampling pump near a suspect wall, clipboard in hand",
    "fire-damage-restoration": "in Tyvek and HEPA respirator cleaning soot from charred drywall, air scrubber running",
    "smoke-damage-restoration": "setting up a hydroxyl generator in a smoke-stained interior",
    "sewage-cleanup": "in full PPE staging extraction equipment at a basement doorway, no visible waste",
    "storm-damage-restoration": "tarping a damaged roof section, ladder and overcast sky visible",
    "appliance-leak-cleanup": "examining a failed appliance supply line with extraction equipment staged",
}


def build_prompt(client_slug: str, post_slug: str, title: str, intent: str,
                 services: list[str]) -> str:
    style = CLIENT_STYLE[client_slug]
    scene = SCENES.get((client_slug, post_slug))
    if scene is None:
        # Fallback: compose from service table + intent rule.
        svc = next((s for s in services if s in SERVICE_FALLBACK), None)
        action = SERVICE_FALLBACK.get(svc, "documenting a restoration jobsite with a clipboard and moisture meter")
        if "insurance" in intent or intent in ("informational", "commercial_decision"):
            scene = ("Calm documentation scene: a {uniform}, back to camera, "
                     f"{action}. Methodical, professional mood. {{region}}.")
        else:
            scene = f"A {{uniform}}, photographed from behind, {action}. {{region}}."
    body = scene.format(uniform=style["uniform"], region=style["region"])
    return f"{body} {STYLE_SUFFIX}"


# ----------------------------------------------------------------------------
# Frontmatter handling
# ----------------------------------------------------------------------------

FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text: str) -> str | None:
    m = FM_RE.match(text)
    return m.group(1) if m else None


def fm_field(fm: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.*)$", fm, re.MULTILINE)
    return m.group(1).strip().strip('"') if m else ""


def has_hero(fm: str) -> bool:
    return bool(re.search(r'^hero:\s*"?\S', fm, re.MULTILINE)
                and fm_field(fm, "hero") not in ("", '""', "null"))


def insert_hero(path: Path, hero_url: str) -> None:
    """Insert (or replace empty) hero: + og: lines in the post's frontmatter,
    after the priority: line to match the canonical field order."""
    text = path.read_text()
    m = FM_RE.match(text)
    if not m:
        raise RuntimeError("no frontmatter block found")
    fm = m.group(1)
    lines = [ln for ln in fm.split("\n")
             if not re.match(r'^(hero|og):\s*("")?\s*$', ln)]  # drop empty hero/og
    hero_lines = [f'hero: "{hero_url}"', f'og: "{hero_url}"']

    anchor = next((i for i, ln in enumerate(lines) if ln.startswith("priority:")), None)
    if anchor is None:
        anchor = next((i for i, ln in enumerate(lines) if ln.startswith("search_intent:")), None)
    if anchor is None:
        anchor = len(lines) - 1
    new_fm = "\n".join(lines[: anchor + 1] + hero_lines + lines[anchor + 1:])
    path.write_text(f"---\n{new_fm}\n---\n" + text[m.end():])


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def backfill_post(client_slug: str, path: Path, *, use_pro: bool, dry_run: bool) -> tuple[str, str]:
    """Returns (status, detail). status is 'ok' | 'skip' | 'fail' | 'dry'."""
    text = path.read_text()
    fm = parse_frontmatter(text)
    if fm is None:
        return "fail", "no frontmatter block"
    if has_hero(fm):
        return "skip", "already has hero"

    post_slug = path.stem
    title = fm_field(fm, "title")
    intent = fm_field(fm, "search_intent") or "informational"
    services_raw = fm_field(fm, "services")
    try:
        import json as _json
        services = _json.loads(services_raw) if services_raw else []
    except Exception:
        services = []

    prompt = build_prompt(client_slug, post_slug, title, intent, services)

    published = fm_field(fm, "published_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yyyy_mm = published[:7].replace("-", "/")
    r2_key = f"blog/{yyyy_mm}/{post_slug}/hero.webp"
    domain = CLIENT_STYLE[client_slug]["domain"]
    bucket = f"rankai-{client_slug}"
    public_url = f"https://images.{domain}/{r2_key}"

    if dry_run:
        print(f"  [dry-run] {post_slug} -> {public_url}\n    prompt: {prompt[:220]}...")
        return "dry", public_url

    model = cw.GEMINI_PRO_MODEL if use_pro else cw.GEMINI_FLASH_MODEL
    print(f"  {post_slug}: generating with {model}...")
    try:
        png = cw.gemini_generate_image(prompt, model=model, aspect_ratio="16:9")
    except Exception as e:
        if use_pro:
            print(f"    pro model failed ({str(e)[:120]}), retrying with flash...")
            try:
                png = cw.gemini_generate_image(prompt, model=cw.GEMINI_FLASH_MODEL,
                                               aspect_ratio="16:9")
            except Exception as e2:
                return "fail", f"image gen failed: {str(e2)[:200]}"
        else:
            return "fail", f"image gen failed: {str(e)[:200]}"

    webp = image_utils.png_to_webp_bytes(png, quality=90)
    print(f"    WebP {len(webp)/1024:.0f} KB -> r2://{bucket}/{r2_key}")
    if not image_utils.upload_bytes_to_r2(bucket, r2_key, webp, content_type="image/webp"):
        return "fail", f"R2 upload failed for {r2_key}"

    insert_hero(path, public_url)
    return "ok", public_url


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill missing blog hero images.")
    ap.add_argument("slugs", nargs="*", default=None,
                    help=f"client slugs (default: {' '.join(DEFAULT_SLUGS)})")
    ap.add_argument("--dry-run", action="store_true", help="print prompts/URLs, no generation")
    ap.add_argument("--flash", action="store_true", help="use the Flash image model")
    ap.add_argument("--sleep", type=float, default=4.0, help="seconds between generations")
    args = ap.parse_args()

    slugs = args.slugs or DEFAULT_SLUGS
    results: list[tuple[str, str, str, str]] = []  # (slug, post, status, detail)

    for slug in slugs:
        if slug not in CLIENT_STYLE:
            print(f"WARNING: no style constants for '{slug}' — add to CLIENT_STYLE. Skipping.")
            continue
        blog_dir = SITES_DIR / slug / "src" / "content" / "blog"
        if not blog_dir.exists():
            print(f"WARNING: {blog_dir} missing. Skipping {slug}.")
            continue
        print(f"\n== {slug} ==")
        for md in sorted(blog_dir.glob("*.md")):
            try:
                status, detail = backfill_post(slug, md, use_pro=not args.flash,
                                               dry_run=args.dry_run)
            except Exception as e:
                status, detail = "fail", f"unexpected: {str(e)[:200]}"
            if status != "skip":
                results.append((slug, md.stem, status, detail))
            if status == "ok":
                print(f"    OK {detail}")
                time.sleep(args.sleep)
            elif status == "fail":
                print(f"    FAIL {md.stem}: {detail}")

    print("\n===== Summary =====")
    for slug, post, status, detail in results:
        print(f"{status.upper():5}  {slug:34}  {post:50}  {detail}")
    fails = sum(1 for r in results if r[2] == "fail")
    print(f"\n{sum(1 for r in results if r[2] == 'ok')} written, {fails} failed, "
          f"{sum(1 for r in results if r[2] == 'dry')} dry-run.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
