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

Consults clients/{slug}/image-style-guide.md when present. Images are
ILLUSTRATIVE brand imagery (same policy as blog heroes) — real job photos
stay real (jobPhotos renders only crew-hub uploads).

Usage: python3 scripts/gen_site_images.py --slug restorationxpress [--force]
Env:   GOOGLE_AI_API_KEY
"""
from __future__ import annotations

import argparse
import io
import json
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    slug = args.slug

    pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
    brand = pi.get("brand", {})
    primary = next((a for a in pi.get("service_areas", []) if a.get("primary")),
                   (pi.get("service_areas") or [{}])[0])
    city, state = primary.get("city", ""), primary.get("state", "")
    name = brand.get("display_name", slug)
    color = brand.get("primary_color", "#dc2626")
    guide_p = ROOT / "clients" / slug / "image-style-guide.md"
    guide = guide_p.read_text()[:1500] if guide_p.exists() else ""
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
    if logo_png:
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

    SHOTS = {
        "hero-bg.webp": (
            f"Wide cinematic photograph for a restoration company website hero background: "
            f"{van} parked in a staggered row in front of a well-kept property. {geo} "
            f"Golden-hour professional photography, shallow depth, photorealistic, no people's "
            f"faces prominent. {logo_rule} 16:9 composition with the left "
            f"third visually calm for overlaid headline text."),
        "team.webp": (
            f"Photorealistic photo of a small professional restoration crew (3-4 people, mixed, "
            f"in matching clean uniforms) standing confidently in front of {van}. {geo} "
            f"Natural light, friendly and trustworthy. {logo_rule}"),
        "services.webp": (
            f"Photorealistic photo of a technician unloading professional drying equipment "
            f"(air movers, dehumidifier) from {van} at a job site. Clean, well-lit. "
            f"{logo_rule} {geo}"),
    }

    from PIL import Image
    made = 0
    for fname, prompt in SHOTS.items():
        out = img_dir / fname
        if out.exists() and not args.force:
            print(f"  {fname}: exists — skipped")
            continue
        full_prompt = prompt + ("\n\nStyle guide notes:\n" + guide if guide else "")
        print(f"  generating {fname}...")
        png = gemini_generate_image(full_prompt, reference_png=logo_png)
        img = Image.open(io.BytesIO(png)).convert("RGB")
        img.save(out, "WEBP", quality=84)
        made += 1
        print(f"    saved {out.relative_to(ROOT)} ({out.stat().st_size // 1024}KB)")
    print(f"{slug}: {made} image(s) generated for {city}, {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
