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
    "general-contracting": "a carpenter in a tool belt hanging drywall in a partly rebuilt room, lumber and materials staged",
    "reconstruction": "a technician with a nail gun framing a partially rebuilt interior wall, fresh lumber and drywall stacked nearby",
    "asbestos-abatement": "a technician in full hooded Tyvek with a P100 respirator working inside a negative-pressure containment, flexible ducting visible",
    "air-duct-cleaning": "a technician feeding a rotary brush line into an open ceiling duct register, HEPA vacuum unit on the floor below",
    "carpet-cleaning": "a technician pulling a truck-mount carpet extraction wand across carpet, clean stripes visible behind the wand",
    # 2026-09-29 (Santino, ProRestoration + fleet): the ops-sync parity step
    # added these service pages with no image, and the generic "performing
    # {display} work" fallback prompt is how a wrong-subject card happens.
    # Every slug the fleet actually ships gets a concrete, distinct scene.
    "commercial-restoration": "a technician running a ride-behind extraction unit across the wet carpet tile of an empty commercial office floor, rows of desks and air movers staged along glass partitions",
    "industrial-restoration": "two technicians in hard hats and hi-vis vests staging large desiccant dehumidifiers and lay-flat ducting inside a high-bay warehouse with steel racking and a wet concrete floor",
    "large-loss-response": "a crew staging dozens of air movers and several large dehumidifiers along the long corridor of a multi-unit commercial building, a technician with a clipboard directing the setup",
    "roofing": "two roofers on a pitched residential roof nailing fresh architectural asphalt shingles in neat courses, a bundle of new shingles and a nail gun beside them, clear daylight",
    "emergency-plumbing": "a plumber kneeling under a kitchen sink tightening a compression fitting with a wrench, headlamp on, towels and a bucket catching drips, tool bag open beside them",
    "emergency-water-removal": "a technician running a portable truck-mount extraction wand across soaked living-room carpet at night, work lights on, water visibly drawing up into the wand",
    "water-leak-detection": "a technician wearing an acoustic leak-detection headset, kneeling and pressing a ground microphone to a tile floor while holding a pin moisture meter against the baseboard; plain walls, no thermal camera, no glow or colored light anywhere",
    "water-heater-flood-cleanup": "a technician wet-vacuuming standing water around a failed tank water heater in a garage utility corner, towels down and an air mover staged nearby",
    "ceiling-water-damage-repair": "a technician on a step ladder cutting out a sagging water-stained section of ceiling drywall, a plastic drop sheet catching debris below",
    "contents-restoration-storage": "a technician in the everyday company uniform (no hazmat suit) carefully wrapping household items into padded packing boxes on a folding table, labeled moving boxes stacked on shelving in a clean storage warehouse behind",
    "contents-restoration-pack-out": "technicians carrying padded, wrapped furniture and packed boxes out of a home toward a box truck on a sunny driveway",
    "vandalism-graffiti-removal": "a technician in the everyday company uniform (no hazmat suit) pressure-washing abstract colored spray-paint smears (no readable letters or symbols) off a concrete block wall, runoff on the pavement, cleaned section visibly bright",
    "vandalism-cleanup": "a technician in work gloves sweeping broken window glass into a dustpan inside a vandalized storefront, a sheet of plywood leaned against the broken window frame",
    "structural-drying-dehumidification": "an LGR dehumidifier and a ring of axial air movers running in a room with baseboards removed and small drill holes along the bottom of the drywall, a technician checking a hygrometer",
    "mold-inspection-assessment": "a technician holding an air-sampling pump cassette near a suspect wall corner, moisture meter and flashlight in hand",
    "dryer-vent-cleaning": "a technician feeding a rotary brush through a disconnected dryer vent duct behind a pulled-out clothes dryer in a laundry room, lint collected in a bag",
    "junk-debris-removal": "two workers carrying water-damaged boxes and a broken chair out of a garage toward a trailer, the garage half cleared",
    "tile-grout-cleaning": "a technician running a rotary tile-cleaning tool across a kitchen tile floor, a clearly brighter clean section beside the dingy grout",
    "windows": "a carpenter setting a new vinyl replacement window into a prepared wall opening, level held against the frame, shims and caulk gun nearby",
    "windows-doors": "a carpenter hanging a new exterior entry door in its frame, checking the reveal with a level, window trim supplies staged nearby",
    "fire-smoke-rebuilding": "a carpenter framing new wall studs in a fire-gutted room, fresh lumber bright against a few remaining soot-darkened joists, drywall stacked nearby",
    "textile-restoration": "a technician lifting freshly cleaned curtains and garments from a rack in a clean contents-cleaning facility, ozone chamber and wrapped textiles behind",
    "temporary-fencing": "workers setting sections of galvanized temporary chain-link construction fencing on weighted stands around a damaged property",
    "drywall-repair": "a technician taping and skimming joint compound over a new drywall patch on a living-room wall, a mud pan and taping knife in hand",
    "flooring-carpet-installation": "an installer on his knees laying new luxury vinyl plank flooring in a bright empty room, boxes of planks and a rubber mallet beside him",
    "trim-baseboard-installation": "a carpenter nailing new white baseboard trim along a freshly painted wall with a finish nailer, a miter saw on the floor nearby",
    "red-stain-removal": "a technician applying a heat-transfer stain treatment to a red drink stain on light beige carpet, spray bottle and towels beside him",
    "attic-insulation": "a technician in a respirator blowing loose-fill insulation across attic joists with a hose, a depth ruler standing in the fresh insulation",
    "hvac-installation": "an HVAC technician setting a new condenser unit on a pad beside a house, refrigerant gauges connected, the old unit on a dolly behind",
    "repiping": "a plumber fitting new PEX supply lines through opened drywall in a hallway wall, manifold and crimp tool in hand",
    # 2026-09-29 (live-only gbp-maintenance pages persisted fleet-wide): the
    # GBP job-type slugs those pages carry. Near-synonyms get deliberately
    # DIFFERENT scenes so two cards on one site never look alike.
    "24-7-emergency-water-damage-restoration": "a technician at night carrying an air mover through a front door into a flooded hallway, work light glowing, {van} parked at the curb with its doors open",
    "24-7-emergency-water-cleanup": "a technician at night squeegeeing standing water toward a floor drain in a laundry room, a headlamp on and a portable extractor running",
    "basement-water-cleanup": "a technician running a portable extractor wand across a wet basement carpet beside a sump pit, a dehumidifier staged by the stairs",
    "basement-sewage-cleanup": _SENSITIVE_SCENE,
    "category-3-water-cleanup": _SENSITIVE_SCENE,
    "blood-cleanup": _SENSITIVE_SCENE,
    "carpet-water-extraction": "a technician driving a weighted stand-on extraction tool across soaked wall-to-wall carpet, water visibly pulled up into the hose",
    "carpet-upholstery-cleaning": "a technician cleaning a fabric sofa cushion with a handheld upholstery extraction tool, a clean stripe visible on the fabric",
    "upholstery-cleaning": "a technician kneeling beside a fabric sofa in a bright living room, running a small handheld upholstery extraction tool across a seat cushion, a visibly cleaner stripe on the fabric, portable extractor unit on the floor",
    "air-duct-hvac-cleaning": "a technician inspecting the inside of an opened HVAC air handler cabinet with a flashlight, a HEPA negative-air machine hose attached to the trunk line",
    "air-duct-cleaning-service": "a technician feeding a rotary brush line into an open ceiling duct register, HEPA vacuum unit on the floor below",
    "emergency-board-up": "a technician screwing a plywood sheet over a broken sliding glass door at dusk, a drill in hand and glass swept into a pile",
    "emergency-board-ups": "a technician on a ladder securing plywood over a broken upstairs window at dusk, {van} parked below",
    "vandalism-damage-cleanup-and-repair": "a technician in work gloves sweeping broken window glass into a dustpan inside a vandalized storefront, a sheet of plywood leaned against the broken window frame",
    "vehicle-impact-damage-repair": "a technician installing temporary steel shoring posts and plywood over a large hole in a house's exterior wall, debris swept into a pile, no vehicle in frame",
    "hurricane-damage-restoration": "a technician tarping a wind-torn roof after a hurricane, palm fronds and debris across a soaked lawn, {van} parked at the curb",
    "content-recovery": "a technician carefully wrapping household items into padded packing boxes on a folding table, labeled moving boxes stacked on shelving in a clean storage warehouse behind",
    "environmental-consultants": "an environmental technician setting up an air-sampling pump on a tripod in a clean room, clipboard and sample cassettes on a case beside him",
    "ice-dams": "a technician on a ladder using a low-pressure steamer to clear a thick ice dam and icicles from a snowy roof edge",
    "general-contractor": "a carpenter checking a newly framed interior wall with a long level, lumber and drywall staged in a bright partly rebuilt room",
    "remodeler": "a carpenter installing new shaker kitchen cabinet doors in a remodeled kitchen, protective paper on the countertops",
    "job-type-id-construction": "a crew framing the wood walls of a home addition on a clear day, a nail gun and lumber stacks on the new subfloor",
    "job-type-id-basement-remodeling": "a carpenter hanging drywall on newly framed basement walls, recessed lights installed in the ceiling, finished-basement in progress",
    "basement-remodeling": "a finished basement nearly complete: a carpenter installing baseboard trim beside new carpet and freshly painted walls",
    "job-type-id-bathroom-remodeling": "a tile setter laying large-format tile on a new walk-in shower wall, spacers and a mortar bucket nearby",
    "bathroom-remodeler": "a contractor installing a new floating vanity and sink in a freshly tiled bathroom",
    "kitchen-bathroom-remodeling": "a contractor installing a new quartz countertop section onto base cabinets in a kitchen remodel",
    "post-construction-specialty-cleaning": "a technician HEPA-vacuuming fine dust in a freshly renovated room with new drywall and floor-protection paper down",
    "all-plumbing-services": "a plumber organizing fittings and a pipe wrench from an open tool bag beside a residential water main shutoff in a garage",
    "camera-inspections-of-drain-and-sewer-line": "a plumber feeding a push-rod sewer camera into an outdoor cleanout pipe in a front yard, the inspection monitor on its reel showing the pipe interior",
    "sewer-camera-inspection": "a plumber indoors kneeling at an open floor drain in a utility room, watching a small inspection monitor as the camera cable feeds in",
    "common-plumbing-emergencies": "a plumber replacing the fill valve inside an open toilet tank, towels on the bathroom floor",
    "drain-sewer-repairs": "a plumber in a trench in a residential yard joining a new section of white PVC sewer pipe, shovels and gravel beside the trench",
    "gas-line-inspections": "a technician holding an electronic combustible-gas leak detector to a yellow gas line fitting behind a water heater",
    "instant-hot-water-system": "a plumber mounting a wall-hung tankless water heater in a garage, venting and copper lines being connected",
    "reverse-osmosis": "a plumber installing an under-sink reverse osmosis filtration unit with filter canisters and a small storage tank",
    "slab-leak-and-pipe-repair": "a plumber opening a small section of a concrete slab floor to reach a leaking copper pipe, with a leak-detection headset around his neck",
    "plasma-guard-pro": "an HVAC technician installing a compact whole-home air purification module into the supply plenum of an indoor air handler, sheet-metal screws and a drill in hand, no product branding readable",
    "financing": "a project manager at a kitchen table walking a homeowner couple through a printed repair estimate on a tablet and clipboard, calm and friendly, faces not the focus",
    "insurance-claim-assistance": "a project manager photographing water damage for an insurance claim with a tablet while a homeowner looks on, moisture meter clipped to his belt",
    # 2026-09-29 (Crew service-image pass): construction-tier services.
    "deck-construction": "a carpenter fastening new deck boards onto fresh pressure-treated joists of a backyard deck attached to a two-story home, cordless drill and stacked lumber nearby",
    "excavations": "a compact excavator digging a trench along a house foundation in a residential yard while a technician in a hi-vis vest guides it, a mound of dark soil beside the trench; no vehicles other than the excavator, and no lettering, numbers or color codes anywhere in the frame",
    "foundation-installation": "workers tying rebar inside plywood concrete forms for a new poured foundation wall on a residential lot, a concrete pump boom hose lowered into the form",
}


def _fm_field(md_text: str, key: str) -> str | None:
    m = re.search(rf"""^{key}:\s*['"]?([^'"\n]+?)['"]?\s*$""", md_text, re.M)
    return m.group(1).strip() if m else None


def generate_service_images(*, slug: str, geo: str, guide: str,
                            refs: list, van: str,
                            logo_rule: str, img_dir: Path,
                            crew: str = "", mood: str = "",
                            equip: str = "", redo: set | None = None,
                            real: dict | None = None,
                            scene_overrides: dict | None = None,
                            request: str = "", requested_by: str = "",
                            only: set | None = None) -> int:
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
        if only and svc_slug not in only:
            continue    # --only: touch just the named service cards

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
            scene = (scene_overrides or {}).get(svc_slug) or SERVICE_SCENES.get(
                svc_slug,
                f"a uniformed restoration technician performing {display} work "
                f"with professional equipment at a job site").format(van=van)
            prompt = (
                f"Photorealistic photograph for a restoration company website service "
                f"card — {scene}. Professional full-frame mirrorless look, "
                f"{mood or 'natural competent lighting'}, mid-task not posed, "
                f"shot from behind or three-quarter back so faces are turned away "
                f"or in natural profile. Any face in frame is a normal, sharp, "
                f"natural face: NEVER blurred, pixelated, smudged, masked or "
                f"blacked out (2026-09-29 QC: 'no faces visible' made the model "
                f"blur and black out faces). {crew}{equip}"
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
            if svc_slug in redo:
                # A redo REPLACES a live image: record the client's request and
                # archive the old version, or the deploy's image guard reverts it.
                import image_guard
                image_guard.approve(slug, f"services/{svc_slug}.webp", request,
                                    requested_by, None, "main")

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


# ---------------------------------------------------------------------------
# BEFORE/AFTER PAIRS (A4, Santino 2026-09-20: "make sure the template would
# include all of this for new websites"). The homepage slider ships wired but
# self-hidden until src/data/work.ts holds pairs; the fleet policy (work.ts
# header, 2026-09-18) says EVERY client gets service-matched showcase pairs
# at build time — this closes the automation gap. Before is generated fresh;
# after is an EDIT of the before (passed as a reference image) so the scene
# geometry matches under the drag slider. SERVICE-MATCHED: only pairs for
# services in plan-input; catalog order is the priority order; max 4 pairs.
# A populated work.ts is NEVER overwritten (ACS carries a REAL job photo).
# ---------------------------------------------------------------------------
PAIR_CATALOG: list[tuple[str, set, str, str, str, str, str]] = [
    ("water", {"water-damage-restoration", "water-mitigation"},
     "Water Damage Restoration",
     "Interior of a family living room with two inches of standing water "
     "across the floor, waterline staining on the lower walls, furniture "
     "legs submerged. Shot on a phone by a technician, natural window "
     "light, no people, no text.",
     "the SAME living room fully restored after water damage restoration: "
     "standing water extracted, the water-damaged flooring TORN OUT and "
     "REPLACED with brand-new PREMIUM extra-wide-plank flooring in a "
     "noticeably lighter different wood tone, the new planks laid in the "
     "PERPENDICULAR direction to the old floor so the replacement is "
     "unmistakable (an obvious upgrade, never a downgrade like carpet), "
     "new baseboards, lower walls repaired and freshly painted, the "
     "furniture professionally cleaned or replaced (no stains), no "
     "leftover materials, rugs or debris anywhere, dry and bright",
     "Flooded living room with standing water before restoration",
     "Same living room with new premium plank flooring and repaired "
     "walls after restoration"),
    ("fire", {"fire-damage-restoration", "smoke-damage-restoration",
              "fire-and-smoke-restoration"},
     "Fire & Smoke Restoration",
     "Interior of a living room after a serious house fire: walls and "
     "ceiling heavily charred black, exposed burned ceiling joists, soot "
     "coating every surface, scorched furniture and burned debris across "
     "the floor, daylight through a smoke-stained window. Shot on a "
     "phone, no people, no flames, no text.",
     "the SAME living room fully rebuilt and restored after fire damage "
     "restoration: new drywall walls and a fully CLOSED finished drywall "
     "ceiling (no exposed beams, joists or framing), freshly painted, new "
     "flooring, the burned furniture HAULED AWAY and replaced with "
     "different brand-new furnishings, the same window spotless, room "
     "bright",
     "Living room with severe fire damage and charred walls before "
     "restoration",
     "Same living room fully rebuilt and restored after fire damage"),
    ("sewage", {"sewage-cleanup", "sewage-backup-cleanup"},
     "Sewage Cleanup",
     "A finished basement after a MAJOR sewage backup: several inches of "
     "dark contaminated water flooding the entire floor wall to wall, "
     "debris floating, filth staining up the lower walls. Shot on a "
     "phone, no people, no text.",
     "the SAME basement after professional cleanup: all sewage extracted, "
     "floor and walls disinfected and dried, clean and bright",
     "Basement flooded wall to wall by a sewage backup before cleanup",
     "Same basement extracted, disinfected and dry after cleanup"),
    ("storm", {"storm-damage-restoration", "storm-damage-repair"},
     "Storm Damage Restoration",
     "A bedroom after severe storm damage: a section of the ceiling "
     "collapsed exposing broken rafters and torn insulation, wet debris "
     "and fallen drywall on the bed and floor, rain staining streaking "
     "down the wall. Shot on a phone, no people, no text.",
     "the SAME bedroom fully repaired after storm damage restoration: "
     "ceiling rebuilt with new drywall and seamless finish, freshly "
     "painted, debris cleared, the bed remade with brand-new bedding in "
     "a different color, room clean and dry",
     "Bedroom with collapsed ceiling and storm debris before repair",
     "Same bedroom with rebuilt ceiling after storm damage restoration"),
    ("mold", {"mold-remediation", "mold-removal", "mold-inspection"},
     "Mold Remediation",
     "Corner of a bathroom wall and ceiling overtaken by a large spreading "
     "colony of black and dark-green mold climbing from the baseboard to "
     "the ceiling, paint bubbling and peeling, heavy staining. Shot on a "
     "phone, close enough to see texture, no people, no text.",
     "the SAME bathroom corner fully remediated: mold completely gone, "
     "surfaces repaired and repainted a clean bright white, dry",
     "Bathroom wall with spreading mold before remediation",
     "Same bathroom wall clean and repainted after mold remediation"),
    ("reconstruction", {"general-contracting", "reconstruction",
                        "home-remodeling"},
     "Reconstruction & Rebuild",
     "Interior room gutted to bare wood studs and subfloor mid-project: "
     "exposed framing, hanging wires capped, dusty subfloor. Shot on a "
     "phone, no people, no text.",
     "the SAME room fully rebuilt and finished: new drywall painted, new "
     "flooring, trim and outlets installed, bright and move-in ready",
     "Room gutted to the studs before reconstruction",
     "Same room fully rebuilt and finished after reconstruction"),
    ("flood", {"water-cleanup", "flood-cleanup", "basement-flood-cleanup",
               "emergency-water-removal", "flood-damage-restoration"},
     "Emergency Water Cleanup",
     "A finished basement flooded with several inches of murky floodwater "
     "wall to wall: a couch and boxes sitting in the water, waterline on "
     "the drywall. Shot on a phone, no people, no text.",
     "the SAME basement after emergency water extraction and structural "
     "drying: floor completely dry and clean, waterline repaired and "
     "repainted, contents dried out or removed",
     "Basement flooded wall to wall before emergency water cleanup",
     "Same basement extracted, dried and repaired after cleanup"),
    ("roofing", {"roofing", "roofing-services", "roof-leak-repair"},
     "Roof Replacement",
     "Close view of a residential asphalt-shingle roof with severe storm "
     "damage: torn and missing shingles, exposed dark underlayment "
     "patches, lifted edges. Shot on a phone from a ladder, no people, "
     "no text.",
     "the SAME roof fully replaced with brand-new architectural "
     "shingles, crisp clean lines, new flashing",
     "Roof with torn and missing shingles before replacement",
     "Same roof fully replaced with new architectural shingles"),
    ("carpet", {"carpet-cleaning"},
     "Carpet Cleaning",
     "Wall-to-wall beige carpet in a lived-in family room, heavily soiled "
     "with dark traffic lanes and scattered stains, matted pile. Shot on "
     "a phone, no people, no text.",
     "the SAME carpet professionally deep-cleaned: uniform bright color, "
     "fresh vacuum lines, stains gone",
     "Heavily soiled carpet with traffic lanes before cleaning",
     "Same carpet restored to like-new condition after cleaning"),
    ("duct", {"air-duct-cleaning", "duct-cleaning"},
     "Air Duct Cleaning",
     "Looking straight into an open residential HVAC duct: the interior "
     "caked with grey dust, lint and debris. Shot on a phone with flash, "
     "no people, no text.",
     "the SAME duct interior professionally cleaned: bare shining metal, "
     "spotless",
     "HVAC duct interior caked with dust before cleaning",
     "Same duct interior spotless after professional cleaning"),
    ("tile", {"tile-grout-cleaning", "tile-and-grout-cleaning"},
     "Tile & Grout Cleaning",
     "A tiled kitchen floor with grout lines blackened by years of grime, "
     "tiles dull and dingy. Shot on a phone, no people, no text.",
     "the SAME tiled floor after professional cleaning: grout lines "
     "uniformly bright, tiles glossy clean",
     "Tile floor with blackened grout before cleaning",
     "Same tile floor with bright grout after professional cleaning"),
    ("junk", {"junk-debris-removal", "junk-removal", "debris-removal"},
     "Junk & Debris Removal",
     "A two-car garage packed with accumulated junk: broken furniture, "
     "boxes, bags and clutter piled high. Shot on a phone, no people, "
     "no text.",
     "the SAME garage completely cleared out and swept clean, empty "
     "floor visible wall to wall",
     "Garage packed with junk and debris before removal",
     "Same garage cleared and swept clean after junk removal"),
]

_WORK_EMPTY_MARKER = "export const workPairs: BeforeAfterPair[] = [];"


def generate_pairs(*, slug: str, geo: str, guide: str) -> None:
    site = ROOT / "sites" / slug
    work_p = site / "src" / "data" / "work.ts"
    if not work_p.exists():
        print("  pairs: no work.ts (pre-slider scaffold) — skipping")
        return
    if _WORK_EMPTY_MARKER not in work_p.read_text():
        print("  pairs: work.ts already populated — never overwritten")
        return
    services = set(json.loads(
        (ROOT / "clients" / slug / "plan-input.json").read_text()
    ).get("services") or [])
    matches = [c for c in PAIR_CATALOG if c[1] & services]
    picks = matches[:6]
    # EVEN COUNT LAW (Santino 2026-09-22, extend-first same day): the grid
    # never renders an odd number of pairs. Prefer ADDING the next
    # service-matched kind (the catalog carries reconstruction/GC so one
    # nearly always exists); trim only when no further match exists.
    if len(picks) >= 3 and len(picks) % 2:
        if len(matches) > len(picks):
            picks = matches[:len(picks) + 1]
        else:
            picks = picks[:-1]
    if not picks:
        print("  pairs: no catalog match for this client's services")
        return
    out_dir = site / "public" / "images" / "before-after"
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for kind, _svc, label, before_prompt, after_edit, alt_b, alt_a in picks:
        b_p, a_p = out_dir / f"{kind}-before.png", out_dir / f"{kind}-after.png"
        try:
            if b_p.exists():
                before_png = b_p.read_bytes()
                print(f"  pairs: {kind}-before exists — kept")
            else:
                before_png = gemini_generate_image(
                    f"{before_prompt} Photorealistic. {geo} {guide[:600]}",
                    aspect_ratio="16:9")
                b_p.write_bytes(before_png)
                print(f"  pairs: {kind}-before generated")
            if not a_p.exists():
                after_png = gemini_generate_image(
                    "Using the attached photo of this exact room, produce "
                    f"{after_edit}. IDENTICAL camera angle and "
                    "architecture — the same room after professional "
                    "restoration, COMPLETELY FINISHED: no exposed framing "
                    "or beams, no leftover materials, tools or debris, "
                    "all furniture and textiles clean or brand new. "
                    "Photorealistic, no text.",
                    aspect_ratio="16:9", reference_png=before_png)
                a_p.write_bytes(after_png)
                print(f"  pairs: {kind}-after generated (edit of before)")
        except Exception as e:  # noqa: BLE001 — a failed pair never blocks the rest
            print(f"  pairs: {kind} FAILED ({str(e)[:90]}) — skipped")
            continue
        entries.append((kind, label, alt_b, alt_a))
    if not entries:
        print("  pairs: nothing generated — work.ts untouched")
        return
    # PAGE-WEIGHT (Santino 2026-09-22, FIX sliders lagging): the raw PNGs
    # run 700-900KB each — ~7MB of slider imagery. Serve compressed 1400w
    # webp (~80-120KB); the PNGs stay as archival masters.
    from PIL import Image
    for kind, _l, _ab, _aa in entries:
        for side in ("before", "after"):
            png = out_dir / f"{kind}-{side}.png"
            webp = out_dir / f"{kind}-{side}.webp"
            if png.exists() and not webp.exists():
                img = Image.open(png).convert("RGB")
                if img.width > 1400:
                    img = img.resize(
                        (1400, round(img.height * 1400 / img.width)))
                img.save(webp, "WEBP", quality=78)
    rows = ",\n".join(
        f'''  {{
    label: "{label}",
    beforeSrc: "/images/before-after/{kind}-before.webp",
    beforeAlt: "{alt_b}",
    afterSrc: "/images/before-after/{kind}-after.webp",
    afterAlt: "{alt_a}",
  }}''' for kind, label, alt_b, alt_a in entries)
    txt = work_p.read_text().replace(
        _WORK_EMPTY_MARKER,
        "export const workPairs: BeforeAfterPair[] = [\n" + rows + "\n];")
    work_p.write_text(txt)
    print(f"  pairs: work.ts populated with {len(entries)} pair(s)")


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
    ap.add_argument("--request", default="",
                    help="REQUIRED with --redo/--force: the client's explicit "
                         "request for these specific images (quoted). Live images "
                         "are never replaced without one (image_guard.py).")
    ap.add_argument("--requested-by", default="",
                    help="REQUIRED with --redo/--force: who asked and when")
    ap.add_argument("--only", default="",
                    help="with --services: comma-separated service_slugs to generate "
                         "(e.g. a new page's card) without touching any other card")
    ap.add_argument("--no-harvest", action="store_true",
                    help="skip the real-photo harvest that otherwise runs "
                         "before the first generation for a client")
    ap.add_argument("--pairs", action="store_true",
                    help="generate service-matched before/after slider pairs "
                         "and populate an EMPTY src/data/work.ts (a populated "
                         "work.ts is never overwritten)")
    args = ap.parse_args()
    slug = args.slug
    # STANDING RULE (Santino 2026-09-29, after 26 days of blue-skinned
    # ProRestoration technicians): automation never replaces an approved
    # image on its own. --redo/--force exist for ONE purpose, a client asking
    # for a specific image to change, and must say so.
    if (args.redo or args.force) and (len(args.request.strip()) < 12
                                      or not args.requested_by.strip()):
        print("REFUSED: --redo/--force replace live images. Pass --request "
              "\"<the client's words about THIS image>\" and --requested-by "
              "\"<who, when>\". Without an explicit client request, leave "
              "approved images alone.")
        return 2

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
    # SCENE-OVERRIDE[service_slug] (2026-09-30, Frontline): Jared — "The
    # emergency plumbing should have a picture of a water pipe spraying out
    # water". The SERVICE_SCENES table is fleet-wide, so a client's own idea
    # of what a service card shows had nowhere to live; a --redo just drew
    # the table's scene again. One line per service, --services mode only.
    scene_overrides = {
        m_sc.group(1): m_sc.group(2).strip().rstrip(".")
        for m_sc in re.finditer(r"SCENE-OVERRIDE\[([\w-]+)\]:\s*(.+)", guide_full)}

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

    if args.pairs:
        generate_pairs(slug=slug, geo=geo, guide=guide)
        return 0

    if args.services:
        return generate_service_images(
            slug=slug, geo=geo, guide=guide, refs=refs, van=van,
            logo_rule=logo_rule, img_dir=img_dir, crew=crew, mood=mood,
            equip=equip, real=real, scene_overrides=scene_overrides,
            redo={s.strip() for s in args.redo.split(",") if s.strip()},
            request=args.request, requested_by=args.requested_by,
            only={s.strip() for s in args.only.split(",") if s.strip()} or None)

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
        existed = out.exists()
        img.save(out, "WEBP", quality=84)
        made += 1
        print(f"    saved {out.relative_to(ROOT)} ({out.stat().st_size // 1024}KB)")
        if existed:  # --force replaced a live image: record + archive (image_guard)
            import image_guard
            image_guard.approve(slug, fname, args.request, args.requested_by,
                                None, "main")
        # The hero doubles as the continuity anchor for the shots after it.
        if fname == "hero-bg.webp":
            buf = io.BytesIO()
            img.save(buf, "PNG")
            refs.append(buf.getvalue())
    print(f"{slug}: {made} image(s) generated for {city}, {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
