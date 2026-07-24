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

    SHOTS = {
        "hero-bg.webp": (
            f"Wide cinematic photograph for a restoration company website hero background. "
            f"A clean modern service van (solid {color} and white livery, NO readable text or "
            f"logos on the van) parked in front of a well-kept home. {geo} "
            f"Golden-hour professional photography, shallow depth, photorealistic, no people's "
            f"faces prominent, no text anywhere in the image. 16:9 composition with the left "
            f"third visually calm for overlaid headline text."),
        "team.webp": (
            f"Photorealistic photo of a small professional restoration crew (3-4 people, mixed, "
            f"in matching clean uniforms with NO readable logos) standing confidently by their "
            f"service van. {geo} Natural light, friendly and trustworthy, no text in image."),
        "services.webp": (
            f"Photorealistic photo of professional water damage restoration equipment in action "
            f"inside a home: air movers and a dehumidifier on a drying job, technician in the "
            f"background working. Clean, well-lit, no readable text or logos. {geo}"),
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
        png = gemini_generate_image(full_prompt)
        img = Image.open(io.BytesIO(png)).convert("RGB")
        img.save(out, "WEBP", quality=84)
        made += 1
        print(f"    saved {out.relative_to(ROOT)} ({out.stat().st_size // 1024}KB)")
    print(f"{slug}: {made} image(s) generated for {city}, {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
