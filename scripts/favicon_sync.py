#!/usr/bin/env python3
"""favicon_sync.py — every site's favicon is the client's LOGO, automatically
(Santino 2026-08-31, Air Care's tab showing a generic "AC" square: "I want to
make sure this is going to happen automatically moving forward").

The scaffold ships a placeholder favicon.svg (rounded square + initials in a
<text> element). This pass replaces that placeholder with the client's real
logo wherever one exists, and regenerates the PNG sizes BaseLayout links:

  favicon.svg            SVG wrapper embedding the logo PNG (crisp at any size)
  favicon-32x32.png      browser tab
  favicon-16x16.png      legacy tab
  apple-touch-icon.png   180x180, iOS home screen

Rules:
  - only sites whose favicon.svg still contains a <text> element (the
    placeholder signature) are touched — a custom favicon is never clobbered
  - the logo is square-padded onto a white canvas (favicons are tiny; white
    keeps dark-tab contrast for logos with transparency)
  - idempotent: run daily from client-ops-sync; picks up newly landed logos

Usage:
  python3 scripts/favicon_sync.py            # apply to all sites
  python3 scripts/favicon_sync.py --slug X   # one site
  python3 scripts/favicon_sync.py --dry-run  # report only
"""
from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "sites"


def build_square(logo_path: Path, size: int) -> Image.Image:
    im = Image.open(logo_path).convert("RGBA")
    canvas = Image.new("RGBA", (max(im.size),) * 2, (255, 255, 255, 255))
    canvas.paste(im, ((canvas.width - im.width) // 2,
                      (canvas.height - im.height) // 2), im)
    return canvas.resize((size, size), Image.LANCZOS)


def sync_site(site: Path, dry: bool) -> str:
    pub = site / "public"
    fav = pub / "favicon.svg"
    if not fav.exists():
        return "no favicon.svg (not a scaffolded site?)"
    if "<text" not in fav.read_text(errors="ignore"):
        return "custom favicon — untouched"
    logo = next((p for n in ("logo.png", "logo.webp")
                 if (p := pub / "images" / n).exists()), None)
    if not logo:
        return "placeholder favicon but NO logo on file yet"
    if dry:
        return f"would build favicon set from {logo.name}"
    png512 = build_square(logo, 512)
    buf = io.BytesIO()
    png512.convert("RGB").save(buf, "PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    fav.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        f'<image width="512" height="512" href="data:image/png;base64,{b64}"/></svg>')
    for name, px in (("favicon-32x32.png", 32), ("favicon-16x16.png", 16),
                     ("apple-touch-icon.png", 180)):
        build_square(logo, px).convert("RGB").save(pub / name, "PNG", optimize=True)
    return f"favicon set built from {logo.name}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    changed = []
    for site in sorted(SITES.iterdir()):
        if not site.is_dir():
            continue
        if args.slug and site.name != args.slug:
            continue
        msg = sync_site(site, args.dry_run)
        print(f"  {site.name:44} {msg}")
        if msg.startswith(("favicon set built", "would build")):
            changed.append(site.name)
    print(f"\n{len(changed)} site(s) {'would be ' if args.dry_run else ''}updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
