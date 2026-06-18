#!/usr/bin/env python3
"""
Rank AI — Geo-grid static PNG renderer (server-side, no browser).

Renders a scan's colored, numbered grid pins over a street-map background to a
PNG. This is what the app shows via `image_url` (R2). Pure PIL + requests —
stitches map tiles (Web Mercator) and draws the pins.

    from geogrid_render import render_png
    render_png(points, out_path)          # points: [{"lat","lng","rank"}...]

Tile source is configurable via GEOGRID_TILE_URL (default OSM). For production
scale, point it at a keyed provider (MapTiler/Mapbox/self-host) — OSM's tile
policy discourages heavy automated use.
"""
from __future__ import annotations

import io
import math
import os
import sys
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from geogrid_scan import color_for  # noqa: E402

TILE_URL = os.environ.get("GEOGRID_TILE_URL", "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
TILE = 256
UA = {"User-Agent": "RankAI-geogrid/1.0 (+contact@restorationai.io)"}


def _world(lon: float, lat: float, z: int) -> tuple[float, float]:
    n = TILE * (2 ** z)
    x = (lon + 180.0) / 360.0 * n
    siny = min(max(math.sin(math.radians(lat)), -0.9999), 0.9999)
    y = (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)) * n
    return x, y


def _fit_zoom(min_lon, min_lat, max_lon, max_lat, w, h, pad=0.86, maxz=16) -> int:
    for z in range(maxz, 0, -1):
        x0, y0 = _world(min_lon, max_lat, z)
        x1, y1 = _world(max_lon, min_lat, z)
        if (x1 - x0) <= w * pad and (y1 - y0) <= h * pad:
            return z
    return 1


def _font(size: int) -> ImageFont.FreeTypeFont:
    cands = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for c in cands:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _fetch_tile(z: int, x: int, y: int) -> Image.Image:
    url = TILE_URL.format(z=z, x=x, y=y)
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGBA")


def render_png(points: list[dict], out_path: str | Path, size: tuple[int, int] = (760, 760)) -> Path:
    """Render grid points (each {lat,lng,rank}) to a PNG with a map background."""
    out_path = Path(out_path)
    w, h = size
    lats = [p["lat"] for p in points]
    lons = [p["lng"] for p in points]
    min_lat, max_lat, min_lon, max_lon = min(lats), max(lats), min(lons), max(lons)
    z = _fit_zoom(min_lon, min_lat, max_lon, max_lat, w, h)

    clon, clat = (min_lon + max_lon) / 2, (min_lat + max_lat) / 2
    cx, cy = _world(clon, clat, z)
    left, top = cx - w / 2, cy - h / 2

    canvas = Image.new("RGBA", (w, h), (226, 232, 240, 255))
    tx0, tx1 = int(math.floor(left / TILE)), int(math.floor((left + w) / TILE))
    ty0, ty1 = int(math.floor(top / TILE)), int(math.floor((top + h) / TILE))
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            try:
                tile = _fetch_tile(z, tx, ty)
                canvas.paste(tile, (int(tx * TILE - left), int(ty * TILE - top)), tile)
            except Exception as e:
                sys.stderr.write(f"  tile {z}/{tx}/{ty} failed: {str(e)[:80]}\n")

    # subtle dark veil so the colored pins pop
    veil = Image.new("RGBA", (w, h), (15, 23, 42, 38))
    canvas = Image.alpha_composite(canvas, veil)

    draw = ImageDraw.Draw(canvas)
    r = max(12, int(w * 0.85 / (len(set((p["row"]) for p in points)) or 13) / 2.6)) if all("row" in p for p in points) else 14
    fnum, fsm = _font(int(r * 0.95)), _font(int(r * 0.7))
    for p in points:
        px, py = _world(p["lng"], p["lat"], z)
        ix, iy = px - left, py - top
        col = color_for(p["rank"])
        rgb = tuple(int(col[i:i+2], 16) for i in (1, 3, 5))
        draw.ellipse([ix - r, iy - r, ix + r, iy + r], fill=rgb + (255,), outline=(255, 255, 255, 235), width=2)
        label = "20+" if p["rank"] is None else str(p["rank"])
        f = fsm if len(label) > 2 else fnum
        bb = draw.textbbox((0, 0), label, font=f)
        draw.text((ix - (bb[2]-bb[0]) / 2, iy - (bb[3]-bb[1]) / 2 - bb[1]), label, font=f, fill=(255, 255, 255, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG", optimize=True)
    return out_path


if __name__ == "__main__":
    import json
    src = sys.argv[1] if len(sys.argv) > 1 else "clients/narestco/geogrid/water-damage-restoration-2026-06-17.json"
    d = json.load(open(src))
    out = render_png(d["points"], "/tmp/geogrid-render-test.png")
    print(f"rendered {out}  ({out.stat().st_size} bytes)")
