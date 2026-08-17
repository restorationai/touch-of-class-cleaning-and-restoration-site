#!/usr/bin/env python3
"""gen_site_images.py — generate the core site image set for a client.

The in-app site-build pipeline shipped sites with NO images (hero-bg 404s on
PuroClean + RestorationXpress, found 2026-07-24) because image generation had
always been manual agent work. This script closes the gap, geo-aware per
Santino: the imagery quietly matches the client's actual region — Las Vegas
reads desert-dry (stucco, rock yards, hard light), South Florida reads
tropical (palms, humidity haze, pastel stucco), the Pacific Northwest reads
evergreen and overcast.

Generates (skipping any that already exist — never overwrites):
  public/images/hero-bg.webp   wide exterior scene, brand-adjacent, no text
  public/images/team.webp      crew + branded van (generic people, no real-
                               person claims; sites label it as the team the
                               same way every brand-image site does)
  public/images/services.webp  equipment/action shot (shared service card)

--services mode (the "site imagery finisher", 2026-07-31): one photorealistic
image per service page under src/content/services/*.md, named by the page's
service_slug so src/lib/images.ts#serviceImage resolves it —
  public/images/services/{service_slug}.webp  (+ -480w/-768w/-1200w variants)
and registers each in src/data/image-meta.json (serviceImage only resolves
REGISTERED images; an unregistered file still renders the shared fallback).
Existing service images are NEVER overwritten, even with --force — but their
missing variants/manifest entries are backfilled, so this is also the repair
command for half-finished sites.

Consults clients/{slug}/image-style-guide.md when present. Images are
ILLUSTRATIVE brand imagery (same policy as blog heroes) — real job photos
stay real (jobPhotos renders only crew-hub uploads).

Usage: python3 scripts/gen_site_images.py --slug restorationxpress [--force]
       python3 scripts/gen_site_images.py --slug restorationxpress --services
Env:   GOOGLE_AI_API_KEY
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

from content_writer import gemini_generate_image  # noqa: E402


# ---------------------------------------------------------------------------
# REAL PHOTOS FIRST (Santino 2026-08-05)
# ---------------------------------------------------------------------------
# The standing rule this file now obeys: a client's own photograph outranks
# anything we can generate, so generation only ever fills a genuine gap. Every
# client with a claimed GBP already has a photo library on it, and most have a
# pre-existing or franchise website full of the same — scripts/photo_harvest.py
# collects, classifies and installs those. Whatever it has installed is recorded
# in clients/{slug}/photo-manifest.json under "slots", and this module treats
# such a slot as immovable: not skipped-because-exists (which --force overrides)
# but skipped-because-real.
#
# The saga this ends: every invented phone number, garbled wordmark, distorted
# technician and unzipped Tyvek suit came out of asking a generator to reproduce
# something that already existed as a JPEG.
def real_slots(slug: str) -> dict:
    """{"hero"|"team"|"services"|"service:{svc}": {...provenance}} for slots a
    real photograph already fills. Empty dict when nothing has been harvested —
    in which case this file behaves exactly as it did before."""
    p = ROOT / "clients" / slug / "photo-manifest.json"
    if not p.exists():
        return {}
    try:
        return {k: v for k, v in (json.loads(p.read_text()).get("slots") or {}).items()
                if isinstance(v, dict) and v.get("asset")}
    except json.JSONDecodeError:
        return {}


def harvest_first(slug: str) -> None:
    """Two things, in order, before a single pixel is generated for this client:

      1. if nothing has ever been harvested, harvest and triage now — so
         onboarding a client can never generate a van we could have downloaded;
      2. install real photos into any slot that is still EMPTY.

    Step 2 runs every time, not just the first time, because harvest and build
    are separate events: bootstrap_client banks the photos on day one and the
    site build happens days later. It fills gaps only — a slot that already
    holds a generated image is left alone and merely reported, since swapping
    imagery on a live site is a decision, not a side effect of a build.

    Non-fatal throughout: a client with no GBP connection and no old website
    banks nothing and falls through to generation, exactly as before."""
    try:
        import photo_harvest as ph
    except Exception as e:
        print(f"  photo_harvest unavailable ({str(e)[:80]}) — generating")
        return
    cid = None
    try:
        import gbp as _gbp
        cid = _gbp.company_id_for(slug)
    except Exception:
        pass
    if not (ROOT / "clients" / slug / "photo-manifest.json").exists():
        print("  real-photo-first: nothing harvested yet — pulling the client's "
              "own GBP/website photos before generating anything")
        if not cid:
            print("    no company_id — nothing to harvest, generating")
            return
        try:
            print("    " + ph.gbp.import_gbp_media(slug, cap=40))
        except Exception as e:
            print(f"    GBP import skipped: {str(e)[:100]}")
        try:
            ph.register_gbp_assets(slug, cid)
            got, note = ph.harvest_website(slug, cid, cap=30)
            print(f"    web: {got} image(s) from {note}")
        except Exception as e:
            print(f"    web harvest skipped: {str(e)[:100]}")
        try:
            print("    " + ph.triage(slug))
        except Exception as e:
            print(f"    triage skipped: {str(e)[:100]}")
    try:
        print("  " + ph.apply_real_photos(slug, only_missing=True))
    except Exception as e:
        print(f"  real-photo install skipped: {str(e)[:100]}")


def geo_cues(city: str, state: str) -> str:
    """Region-appropriate environmental cues so imagery feels local."""
    st = (state or "").upper()
    table = {
        "NV": "Mojave desert setting: dry hard sunlight, stucco homes, gravel and rock yards, distant tan mountains, cloudless sky",
        "AZ": "Sonoran desert setting: saguaro-adjacent landscaping, stucco homes, intense sun",
        "FL": "South Florida tropical setting: palm trees, humid bright haze, pastel stucco homes, lush green lawns",
        "WA": "Pacific Northwest setting: tall evergreens, overcast soft light, damp streets",
        "OR": "Pacific Northwest setting: evergreens, overcast soft light",
        "UT": "Mountain West setting: dry air, Wasatch foothills in the distance, wide suburban streets",
        "CA": "Southern California setting: dry golden light, stucco homes, palms",
        "NJ": "Northeastern US setting: mature deciduous trees, colonial and split-level homes",
        "NY": "Northeastern US setting: mature trees, dense suburban streets",
        "NC": "Southeastern US setting: tall pines, humid green light",
        "VA": "Mid-Atlantic setting: mixed hardwoods, brick and siding homes",
        "TX": "Texas setting: wide flat streets, big sky, brick ranch homes",
        "PA": "Northeastern US setting: rolling hills, mixed housing stock",
        "AL": "Deep South setting: pines and hardwoods, humid light",
    }
    base = table.get(st, "typical American suburban setting")
    return f"{base}. The scene should feel like {city}, {state} without any text or signage naming it."


# ---------------------------------------------------------------------------
# --services mode: one image per service page (per-service card imagery)
# ---------------------------------------------------------------------------

# Scene per service_slug, mirroring the per-service worker-context table in
# the client image-style-guides: same uniform everywhere, PPE/equipment shift
# per service so every image is unmistakably THAT job. `{van}` (branded fleet
# van, real logo when on disk) appears only where the scene is exterior.
# Sensitive services follow the style-guide guardrail: full PPE in a CLEAN,
# prepped, neutral space — never the scene itself, nothing graphic.
_SENSITIVE_SCENE = (
    "a technician sealed inside a FULL hooded Tyvek coverall — zipper closed "
    "to the throat, hood pulled up over the head, full-face respirator, double "
    "gloves, wrists and ankles taped — staging sealed cleanup supplies in a "
    "clean, prepped, neutral interior space, calm, discreet and professional, "
    "absolutely nothing graphic")
SERVICE_SCENES = {
    "water-damage-restoration": "a technician kneeling to hold a moisture meter against water-stained drywall while axial air movers and an LGR dehumidifier run across the wet floor behind them",
    "water-cleanup": "a technician guiding a portable extraction wand across a sheet of shallow standing water on a hard floor, clean dry stripes showing behind the wand, air movers staged along the wall",
    "flood-damage-restoration": "a technician guiding a weighted extraction wand across a flooded floor, standing water still visible, extraction hose trailing out the doorway",
    "basement-flooding-cleanup": "a technician in rubber boots working a sump pump in a partly flooded basement, exposed framing showing a waterline",
    "burst-pipe-repair": "a technician shutting off a water supply valve at a burst copper pipe while drying equipment sits staged behind them",
    "appliance-leak-cleanup": "a technician examining a failed washing-machine supply line, towels down and a portable extraction unit staged nearby",
    "frozen-pipe-restoration": "a technician wrapping insulation on an exposed copper pipe in a cold utility space, drying equipment staged on the floor",
    "sewage-cleanup": "a technician sealed inside a FULL hooded Tyvek coverall (zipper closed to the throat, hood up, full-face respirator, gloves, wrists and ankles taped) running an extraction wand across a bathroom floor, containment plastic taped at the doorway — clean professional framing, nothing graphic",
    "storm-damage-restoration": "a technician on a ladder securing a heavy tarp over a wind-damaged roof section, scattered branches below, {van} parked at the curb",
    "roof-leak-repair": "a technician on a roof inspecting lifted shingles around a leak point, {van} parked on the street below",
    "fire-damage-restoration": "a technician in a Tyvek suit and respirator running a HEPA air scrubber in a room with charred drywall and soot-darkened surfaces",
    "smoke-damage-restoration": "a technician dry-sponging smoke residue off a wall, clean streaks showing against the gray film, air scrubber running behind",
    "soot-removal": "a technician wiping matte black soot from a wall with a chemical sponge, drop cloths protecting the floor",
    "odor-removal": "a technician setting up a hydroxyl generator in a living room with subtle smoke staining on the walls",
    "mold-remediation": "a technician sealed inside a FULL hooded Tyvek coverall (zipper closed to the throat, hood up, respirator) HEPA-vacuuming a mold-stained wall inside a poly-sheeting containment zone, air scrubber running",
    "mold-inspection-testing": "a technician holding an air-sampling pump cassette near a suspect wall corner, moisture meter and flashlight in hand",
    "biohazard-cleanup": _SENSITIVE_SCENE,
    "trauma-scene-cleanup": _SENSITIVE_SCENE,
    "crime-scene-cleanup": _SENSITIVE_SCENE,
    "unattended-death-cleanup": _SENSITIVE_SCENE,
    "hoarding-cleanup": "technicians in gloves carrying packed unlabeled boxes through a partly organized room, cleanup supplies staged — respectful mid-progress framing, no extreme clutter",
    "contents-restoration": "a technician carefully wrapping household items into padded packing boxes on a folding table, shelving of packed contents behind",
    "crawl-space-encapsulation": "a technician with a headlamp installing a bright white vapor-barrier liner across a crawl space floor and foundation walls",
    "emergency-board-up-tarping": "a technician at dusk drilling plywood over a broken window, ladder against the wall, {van} parked with headlights on",
    "post-construction-cleaning": "a technician HEPA-vacuuming fine dust in a freshly renovated room with new drywall and floor-protection paper down",
    "vandalism-cleanup": "a technician pressure-cleaning abstract paint smears (no readable letters or symbols) off a masonry storefront wall, glass-repair supplies staged",
    "general-contracting": "a carpenter in a tool belt hanging drywall in a partly rebuilt room, lumber and materials staged",
    "reconstruction": "a technician with a nail gun framing a partially rebuilt interior wall, fresh lumber and drywall stacked nearby",
    "asbestos-abatement": "a technician in full hooded Tyvek with a P100 respirator working inside a negative-pressure containment, flexible ducting visible",
    "air-duct-cleaning": "a technician feeding a rotary brush line into an open ceiling duct register, HEPA vacuum unit on the floor below",
    "carpet-cleaning": "a technician pulling a truck-mount carpet extraction wand across carpet, clean stripes visible behind the wand",
}


def _fm_field(md_text: str, key: str) -> str | None:
    m = re.search(rf"""^{key}:\s*['"]?([^'"\n]+?)['"]?\s*$""", md_text, re.M)
    return m.group(1).strip() if m else None


def generate_service_images(*, slug: str, geo: str, guide: str,
                            refs: list, van: str,
                            logo_rule: str, img_dir: Path,
                            crew: str = "", mood: str = "",
                            equip: str = "", redo: set | None = None,
                            real: dict | None = None) -> int:
    """One image per src/content/services/*.md page, named {service_slug}.webp
    so serviceImage() resolves it. Existing base images are never overwritten
    (missing variants + manifest entries are still backfilled) — EXCEPT the
    service slugs named in `redo`, the client-correction path (2026-08-05,
    PuroClean): when a client rejects a shipped image the only way to fix it
    was to delete files by hand, so the rule now has one explicit, named
    opt-out instead of an implicit one."""
    redo = redo or set()
    real = real or {}
    from PIL import Image
    from resize_images import VARIANT_WIDTHS, open_rgb, variant_bytes, variant_path

    svc_content = ROOT / "sites" / slug / "src" / "content" / "services"
    if not svc_content.is_dir():
        print(f"{slug}: no src/content/services/ — nothing to do")
        return 0
    out_dir = img_dir / "services"
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = ROOT / "sites" / slug / "src" / "data" / "image-meta.json"
    try:
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    except json.JSONDecodeError:
        meta = {}

    made, failed, variants_made = 0, [], 0
    for md in sorted(svc_content.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        svc_slug = _fm_field(text, "service_slug") or md.stem
        display = _fm_field(text, "service_display") or md.stem.replace("-", " ").title()
        out = out_dir / f"{svc_slug}.webp"

        rp = real.get(f"service:{svc_slug}")
        if rp:
            # A real photograph of THIS service holds the card. --redo does not
            # reach it: the way to replace a real photo is to pick a different
            # real photo (photo_harvest apply --force), never to generate over it.
            print(f"  services/{out.name}: REAL PHOTO ({rp.get('source')}, "
                  f"{rp.get('category')}) — generation skipped")
            continue

        if out.exists() and svc_slug not in redo:
            print(f"  services/{out.name}: exists — kept (never overwritten)")
        else:
            if out.exists():
                print(f"  services/{out.name}: REDO requested — regenerating")
                for w in VARIANT_WIDTHS:
                    variant_path(out, w).unlink(missing_ok=True)
            scene = SERVICE_SCENES.get(
                svc_slug,
                f"a uniformed restoration technician performing {display} work "
                f"with professional equipment at a job site").format(van=van)
            prompt = (
                f"Photorealistic photograph for a restoration company website service "
                f"card — {scene}. Professional full-frame mirrorless look, "
                f"{mood or 'natural competent lighting'}, mid-task not posed, no "
                f"faces clearly visible (back or side angle). {crew}{equip}"
                f"{logo_rule} {geo}")
            full_prompt = prompt + ("\n\nStyle guide notes:\n" + guide if guide else "")
            print(f"  generating services/{out.name} ({display})...")
            try:
                png = gemini_generate_image(full_prompt, reference_png=refs)
            except Exception as e:  # quota/API failures: keep going, flag at end
                print(f"    FAILED: {e}")
                failed.append(svc_slug)
                continue
            img = Image.open(io.BytesIO(png)).convert("RGB")
            img.save(out, "WEBP", quality=84)
            made += 1
            print(f"    saved {out.relative_to(ROOT)} ({out.stat().st_size // 1024}KB)")

        # variants + manifest entry — same shape resize_images.py writes, so
        # srcsetFor/serviceImage pick the image up without a separate pass.
        im = open_rgb(out)
        widths = [w for w in VARIANT_WIDTHS if w < im.width]
        for w in widths:
            dst = variant_path(out, w)
            if not dst.exists():
                dst.write_bytes(variant_bytes(im, w))
                variants_made += 1
        meta[f"/images/services/{svc_slug}.webp"] = {
            "width": im.width, "height": im.height, "variants": widths}

    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(dict(sorted(meta.items())), indent=2) + "\n",
                         encoding="utf-8")
    print(f"  wrote  {meta_path.relative_to(ROOT)}  ({len(meta)} entries)")
    print(f"{slug}: {made} service image(s) generated, {variants_made} variants, "
          f"{len(failed)} failed" + (f" ({', '.join(failed)})" if failed else ""))
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--services", action="store_true",
                    help="generate one image per src/content/services/ page "
                         "(existing images are never overwritten, --force included)")
    ap.add_argument("--redo", default="",
                    help="comma-separated service_slugs to regenerate even "
                         "though they exist — the client-correction path "
                         "(e.g. --redo mold-remediation,sewage-cleanup)")
    ap.add_argument("--no-harvest", action="store_true",
                    help="skip the real-photo harvest that otherwise runs "
                         "before the first generation for a client")
    args = ap.parse_args()
    slug = args.slug

    if not args.no_harvest:
        harvest_first(slug)
    real = real_slots(slug)
    if real:
        print(f"  real photos hold: {', '.join(sorted(real))}")

    pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
    brand = pi.get("brand", {})
    primary = next((a for a in pi.get("service_areas", []) if a.get("primary")),
                   (pi.get("service_areas") or [{}])[0])
    city, state = primary.get("city", ""), primary.get("state", "")
    name = brand.get("display_name", slug)
    color = brand.get("primary_color", "#dc2626")
    guide_p = ROOT / "clients" / slug / "image-style-guide.md"
    guide_full = guide_p.read_text() if guide_p.exists() else ""
    # The prompt carries the CLIENT-DIRECTION block — everything above the
    # first horizontal rule, which is where the shared canonical boilerplate
    # starts. Was a flat guide[:1500], which silently truncated mid-sentence:
    # Reign's livery table (the whole point of the 2026-08-05 revision) fell
    # off the end at char 1500 and never reached the generator.
    # The cap is now 8000 and LOUD (2026-08-05, PuroClean): the head is by
    # construction nothing but client direction, and quietly dropping the tail
    # of it is the exact failure this block was written to end. PuroClean's
    # block (Greg's three rules + the PuroClean BIG livery/PPE spec) is ~5.2k
    # and would have lost its overrides under the old 5000 ceiling.
    _head = guide_full.split("\n---\n", 1)[0]
    _CAP = 8000
    if len(_head) > _CAP:
        print(f"  WARNING: CLIENT DIRECTION block is {len(_head)} chars — "
              f"truncated to {_CAP} for the prompt. Tighten it.")
    guide = _head[:_CAP] if len(_head) > 1500 else guide_full[:1500]
    geo = geo_cues(city, state)

    img_dir = ROOT / "sites" / slug / "public" / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # STANDING RULE (Santino 2026-07-29): heroes show a MULTI-VAN fleet, and
    # the branded vans appear in the About/team and Services shots too. When
    # the client's real logo is on disk it rides along as a reference image so
    # the wraps carry the REAL mark; without a logo the fleet stays unmarked.
    logo_png = None
    for cand in ("logo-dark-bg.png", "logo.png"):
        p = img_dir / cand
        if p.exists():
            logo_png = p.read_bytes()
            break

    # LIVERY-REFERENCE (2026-08-05, Reign): a real photograph of the client's
    # own wrapped vehicle, declared in the style guide as
    #   LIVERY-REFERENCE: harvested/<file>
    # relative to clients/{slug}/. A logo on white tells the model what the
    # MARK is but nothing about how it sits on a vehicle, so every generation
    # re-invented the wrap and the decals drifted image to image — exactly what
    # Jerrott Gray flagged ("the company vehicle decals need to match from
    # photo to photo"). The real photo pins crest, wordmark, placement and
    # proportion to something that actually exists. It leads the reference list
    # because the last-listed image tends to dominate less.
    # MULTIPLE LIVERY-REFERENCE lines are allowed (2026-08-05, PuroClean): one
    # asset rarely carries the whole wrap. Greg Arianoff sent the four-colour
    # service bar that runs along the bottom of his vans, which pins the bar
    # exactly but says nothing about where it sits on a vehicle; the approved
    # whole-van artwork from his franchise brand guide supplies the placement.
    # Both are needed, so every line is collected in file order.
    livery_pngs: list[bytes] = []
    # Path-ish token only: prose that merely NAMES the directive (a changelog
    # entry reading "declared via `LIVERY-REFERENCE:` and passed to ...") used
    # to match with \S+ and warn about a missing file called "`".
    for m_lv in re.finditer(r"LIVERY-REFERENCE:\s*([\w./-]+)", guide_full):
        lp = ROOT / "clients" / slug / m_lv.group(1).strip()
        if lp.exists():
            livery_pngs.append(lp.read_bytes())
            print(f"  livery reference: {lp.relative_to(ROOT)}")
        else:
            print(f"  WARNING: LIVERY-REFERENCE {lp} not found — skipping")

    # PPE-REFERENCE (2026-08-05, PuroClean): same mechanism as LIVERY-REFERENCE
    # but for what the crew WEARS. Greg Arianoff rejected the first service set
    # because the Tyvek suits came back worn like open jackets — unzipped, hood
    # down, one pulled down and tied around the waist over the polo ("wearing
    # the suit around waist is frowned upon"). Words alone did not carry
    # "sealed"; his franchise's required-attire page, which draws the sealed
    # suit, does. Declared in the style guide as
    #   PPE-REFERENCE: harvested/<file>
    # relative to clients/{slug}/, and rides into every generation.
    ppe_pngs: list[bytes] = []
    for m_ppe in re.finditer(r"PPE-REFERENCE:\s*([\w./-]+)", guide_full):
        pp = ROOT / "clients" / slug / m_ppe.group(1).strip()
        if pp.exists():
            ppe_pngs.append(pp.read_bytes())
            print(f"  PPE reference: {pp.relative_to(ROOT)}")
        else:
            print(f"  WARNING: PPE-REFERENCE {pp} not found — skipping")

    refs = [r for r in (*livery_pngs, *ppe_pngs, logo_png) if r]
    if livery_pngs:
        van = (f"a fleet of two-three matching service vans wrapped in EXACTLY "
               f"the livery shown in the reference image(s) of the company's "
               f"real vehicle — same crest, same wordmark, same colours, same "
               f"proportions, same position on the body panel — reproduced "
               f"identically on every vehicle in the frame. EVERY VEHICLE FACES "
               f"THE SAME DIRECTION and is photographed from the same side, so "
               f"the wrap reads identically across all of them: the crest sits "
               f"at the same end of every van relative to its own nose. Vans "
               f"facing opposite ways put the crest at the nose of one and the "
               f"tail of another, which reads as a mirrored, unprofessional wrap")
        logo_rule = ("Copy the vehicle graphics from the reference image(s) of "
                     "the real vehicle exactly; invent no new decal, no new "
                     "stripe, no new badge and no additional lettering.")
    elif logo_png:
        van = (f"a fleet of two-three matching service vans, each side panel "
               f"carrying the company logo from the reference image reproduced "
               f"faithfully at vehicle-wrap scale, with a {color} accent stripe")
        logo_rule = ("The ONLY text allowed anywhere is the logo mark itself, "
                     "exactly as in the reference image — no phone numbers, no "
                     "URLs, no other lettering.")
    else:
        van = (f"a fleet of two-three matching clean service vans (solid "
               f"{color} and white livery, NO readable text or logos)")
        logo_rule = "No text anywhere in the image."

    # Per-client prompt overrides (Santino 2026-08-01, Coastal feedback: vans
    # drifted to yellow-accented, crew must match the client's real team).
    # Style-guide lines "VAN-OVERRIDE: ..." replace the generic fleet wording
    # entirely; "CREW-OVERRIDE: ..." rides into every prompt as a sentence.
    # "MOOD-OVERRIDE: ..." replaces the hardcoded lighting clause in every shot
    # (Reign feedback 2026-08-04: the guide said dark and moody but the hero
    # prompt's baked-in "Golden-hour" won, and the client got a bright sunny
    # hero back — the style guide could not reach the lighting at all).
    m = re.search(r"VAN-OVERRIDE:\s*(.+)", guide_full)
    if m:
        van = m.group(1).strip()
    m = re.search(r"CREW-OVERRIDE:\s*(.+)", guide_full)
    crew = (m.group(1).strip().rstrip(".") + ". ") if m else ""
    m = re.search(r"MOOD-OVERRIDE:\s*(.+)", guide_full)
    mood = m.group(1).strip().rstrip(".") if m else ""
    # EQUIPMENT-OVERRIDE (2026-08-05, PuroClean): Greg Arianoff — "Please
    # ensure our equipment is red/black on pictures." Every SERVICE_SCENES
    # entry names the gear ("axial air movers", "LGR dehumidifier", "HEPA
    # vacuum") with no colour, so the model reached for stock blue and yellow
    # rental units in eight of eight images. Uniform is CREW-OVERRIDE's job;
    # what the crew is HOLDING needed its own line.
    m = re.search(r"EQUIPMENT-OVERRIDE:\s*(.+)", guide_full)
    equip = (m.group(1).strip().rstrip(".") + ". ") if m else ""

    # NO-VEHICLES (2026-08-05 round 3, Reign): the escape hatch for a client
    # whose wrap the generator cannot be trusted with. Jerrott Gray flagged
    # mirrored crests on his hero vans after TWO rounds of livery references
    # ("Logos on company vehicles need to match"), so for him the only correct
    # number of generated vehicles is zero. Words alone do not do it — asked
    # for a vehicle-free pack-out scene, with the livery photo still in the
    # reference list, the model parked a van in the driveway anyway. The
    # REFERENCES are the instruction the model actually obeys, so this drops
    # them: no livery photo, no logo, and the fleet wording replaced by its
    # negation. Real photographs of the client's fleet are untouched by this;
    # they are exactly what it protects.
    m = re.search(r"NO-VEHICLES:\s*(.+)", guide_full)
    if m:
        no_vehicle_rule = m.group(1).strip().rstrip(".") + "."
        van = "no company vehicle in frame"
        logo_rule = ("NO VEHICLES AND NO LOGOS: " + no_vehicle_rule
                     + " No company wordmark, crest, decal or readable text "
                       "anywhere in the image.")
        livery_pngs, logo_png = [], None
        refs = [r for r in (*livery_pngs, *ppe_pngs, logo_png) if r]
        print("  NO-VEHICLES directive: livery/logo references dropped")

    # FLEET CONTINUITY (2026-08-05, Reign): once a fleet shot is approved it
    # becomes a reference for every later vehicle image, so the wrap carries
    # forward instead of being re-imagined per call. Text alone cannot hold a
    # decal identical across independent generations; a picture of the van we
    # already shipped can.
    # Only in --services mode: in the main pass the hero may itself be about to
    # be regenerated, and conditioning a replacement on the image it replaces
    # would carry the rejected livery straight back in.
    # When the hero is a REAL photograph it is the strongest continuity anchor
    # there is: the wrap in it is the wrap, not an interpretation of one.
    hero_path = img_dir / "hero-bg.webp"
    if args.services and hero_path.exists():
        import io as _io
        from PIL import Image as _Image
        buf = _io.BytesIO()
        _Image.open(hero_path).convert("RGB").save(buf, "PNG")
        refs.append(buf.getvalue())
        print("  fleet-continuity reference: public/images/hero-bg.webp")

    if args.services:
        return generate_service_images(
            slug=slug, geo=geo, guide=guide, refs=refs, van=van,
            logo_rule=logo_rule, img_dir=img_dir, crew=crew, mood=mood,
            equip=equip, real=real,
            redo={s.strip() for s in args.redo.split(",") if s.strip()})

    SHOTS = {
        "hero-bg.webp": (
            f"Wide cinematic photograph for a restoration company website hero background: "
            f"{van} parked in a staggered row in front of a well-kept property. {geo} "
            f"{mood or 'Golden-hour professional photography'}, shallow depth, photorealistic, "
            f"no people's faces prominent. {logo_rule} 16:9 composition with the left "
            f"third visually calm for overlaid headline text."),
        # CREW-OVERRIDE reaches these two as well (2026-08-05): it was only
        # ever applied in --services mode, so Reign's team shot came back as a
        # smiling posed group portrait — the single thing the override forbids.
        "team.webp": (
            f"Photorealistic photo of a small professional restoration crew (3-4 people, mixed, "
            f"in matching clean uniforms) standing confidently in front of {van}. {geo} "
            f"{crew}{equip}{mood or 'Natural light, friendly and trustworthy'}. {logo_rule}"),
        "services.webp": (
            f"Photorealistic photo of a technician unloading professional drying equipment "
            f"(air movers, dehumidifier) from {van} at a job site. "
            f"{crew}{equip}{mood or 'Clean, well-lit'}. {logo_rule} {geo}"),
    }

    from PIL import Image
    made = 0
    slot_of = {"hero-bg.webp": "hero", "team.webp": "team",
               "services.webp": "services"}
    for fname, prompt in SHOTS.items():
        out = img_dir / fname
        rp = real.get(slot_of[fname])
        if rp:
            # Deliberately checked BEFORE --force: --force means "regenerate the
            # generated ones", never "overwrite the client's own photograph".
            print(f"  {fname}: REAL PHOTO ({rp.get('source')}, "
                  f"{rp.get('category')}: {rp.get('subject','')}) — generation skipped")
            if fname == "hero-bg.webp" and out.exists():
                buf = io.BytesIO()
                Image.open(out).convert("RGB").save(buf, "PNG")
                refs.append(buf.getvalue())
            continue
        if out.exists() and not args.force:
            print(f"  {fname}: exists — skipped")
            continue
        full_prompt = prompt + ("\n\nStyle guide notes:\n" + guide if guide else "")
        print(f"  generating {fname}...")
        png = gemini_generate_image(full_prompt, reference_png=refs)
        img = Image.open(io.BytesIO(png)).convert("RGB")
        img.save(out, "WEBP", quality=84)
        made += 1
        print(f"    saved {out.relative_to(ROOT)} ({out.stat().st_size // 1024}KB)")
        # The hero doubles as the continuity anchor for the shots after it.
        if fname == "hero-bg.webp":
            buf = io.BytesIO()
            img.save(buf, "PNG")
            refs.append(buf.getvalue())
    print(f"{slug}: {made} image(s) generated for {city}, {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
