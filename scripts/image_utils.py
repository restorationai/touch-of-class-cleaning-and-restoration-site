#!/usr/bin/env python3
"""
Rank AI — image conversion + upload helpers.

Why this exists: Nano Banana / Gemini returns PNG. PNG is 3-4× larger than
visually-equivalent WebP, which is meaningful for CWV when a page loads a hero
plus 2-4 inline images. We always convert PNG → WebP at upload time and store
the .webp in R2. Source PNGs may be archived locally for re-conversion at
different quality, but the deployed image is always WebP.

Quality policy:
  hero / og   → quality 90 (visual quality matters; image is the first impression)
  inline      → quality 82 (smaller payload, still good)
  thumb / icon→ quality 78

Usage:
  As a script:
    python3 scripts/image_utils.py convert path/to/foo.png            # → foo.webp at q=90
    python3 scripts/image_utils.py convert-dir public/images/services --quality 90
    python3 scripts/image_utils.py upload --slug narestco --src path/file.png \\
        --r2-key brand/hero.webp --quality 90

  As a library (from blog_routine.py or build_site.py):
    from image_utils import png_to_webp_bytes, upload_to_r2_bucket
    webp = png_to_webp_bytes(png_bytes, quality=90)
    url = upload_to_r2_bucket(webp, bucket="rankai-narestco", key="blog/2026/05/foo/hero.webp")
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.stderr.write("ERROR: Pillow not installed. Run: pip install Pillow\n")
    sys.exit(1)


QUALITY_DEFAULTS = {
    "hero": 90,
    "og": 90,
    "inline": 82,
    "thumb": 78,
}


def png_to_webp_bytes(png_bytes: bytes, quality: int = 90, method: int = 6) -> bytes:
    """Convert PNG bytes to WebP bytes. method=6 is slowest/best-quality encode."""
    im = Image.open(io.BytesIO(png_bytes))
    # Preserve alpha if present
    if im.mode == "P":
        im = im.convert("RGBA" if "transparency" in im.info else "RGB")
    out = io.BytesIO()
    im.save(out, format="WEBP", quality=quality, method=method)
    return out.getvalue()


def convert_file(src: Path, dst: Path | None = None, quality: int = 90) -> Path:
    """Convert a PNG file to WebP. Returns the destination path. If dst is None,
    derives it from src by swapping .png → .webp."""
    if dst is None:
        dst = src.with_suffix(".webp")
    png_bytes = src.read_bytes()
    webp_bytes = png_to_webp_bytes(png_bytes, quality=quality)
    dst.write_bytes(webp_bytes)
    return dst


def report_size_change(src: Path, dst: Path) -> None:
    s = src.stat().st_size
    d = dst.stat().st_size
    pct = (d / s) * 100 if s else 0
    print(f"  {src.name:42}  {s/1024:>7.1f}KB → {d/1024:>7.1f}KB  ({pct:>4.1f}% of original)")


def upload_to_r2(
    bucket: str,
    key: str,
    file_path: Path,
    content_type: str = "image/webp",
) -> bool:
    """Upload a local file to an R2 bucket via wrangler. Returns True on success.
    Requires CLOUDFLARE_API_TOKEN env (set to a token with R2:Edit scope)."""
    env = os.environ.copy()
    if "CLOUDFLARE_R2_API_TOKEN" in env and "CLOUDFLARE_API_TOKEN" not in env:
        env["CLOUDFLARE_API_TOKEN"] = env["CLOUDFLARE_R2_API_TOKEN"]
    result = subprocess.run(
        [
            "npx", "--yes", "wrangler@latest", "r2", "object", "put",
            f"{bucket}/{key}",
            f"--file={file_path}",
            f"--content-type={content_type}",
            "--remote",
        ],
        env=env, capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(f"R2 upload failed for {key}:\n{result.stderr}\n")
        return False
    return True


def upload_bytes_to_r2(
    bucket: str,
    key: str,
    data: bytes,
    content_type: str = "image/webp",
) -> bool:
    """Upload bytes to R2 via a temp file. Returns True on success."""
    with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        return upload_to_r2(bucket, key, tmp_path, content_type)
    finally:
        tmp_path.unlink(missing_ok=True)


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def cmd_convert(args) -> int:
    src = Path(args.src)
    if not src.exists():
        sys.stderr.write(f"Not found: {src}\n")
        return 1
    if src.suffix.lower() != ".png":
        sys.stderr.write(f"Expected .png, got {src.suffix}\n")
        return 1
    dst = Path(args.dst) if args.dst else src.with_suffix(".webp")
    convert_file(src, dst, quality=args.quality)
    print(f"Converted: {src} → {dst}")
    report_size_change(src, dst)
    if args.delete_source:
        src.unlink()
        print(f"  (deleted source {src.name})")
    return 0


def cmd_convert_dir(args) -> int:
    src_dir = Path(args.dir)
    if not src_dir.is_dir():
        sys.stderr.write(f"Not a directory: {src_dir}\n")
        return 1
    pngs = sorted(src_dir.glob("*.png"))
    if not pngs:
        print(f"No PNGs in {src_dir}")
        return 0
    print(f"Converting {len(pngs)} PNG(s) at quality={args.quality}:")
    total_before = 0
    total_after = 0
    for src in pngs:
        dst = src.with_suffix(".webp")
        convert_file(src, dst, quality=args.quality)
        total_before += src.stat().st_size
        total_after += dst.stat().st_size
        report_size_change(src, dst)
        if args.delete_source:
            src.unlink()
    print(f"\nTotal: {total_before/1024:.1f}KB → {total_after/1024:.1f}KB  "
          f"({(total_after/total_before)*100:.1f}% of original)  "
          f"Saved: {(total_before - total_after)/1024:.1f}KB")
    return 0


def cmd_upload(args) -> int:
    src = Path(args.src)
    if not src.exists():
        sys.stderr.write(f"Not found: {src}\n")
        return 1
    # Convert if PNG, otherwise upload as-is (assume already WebP)
    if src.suffix.lower() == ".png":
        tmp = src.with_suffix(".webp")
        convert_file(src, tmp, quality=args.quality)
        upload_path = tmp
        if not args.r2_key.endswith(".webp"):
            sys.stderr.write(f"Warning: r2-key {args.r2_key!r} does not end in .webp\n")
    else:
        upload_path = src

    bucket = f"rankai-{args.slug}"
    ok = upload_to_r2(bucket, args.r2_key, upload_path, content_type="image/webp")
    if ok:
        domain = f"images.{args.slug}.com" if not args.domain else args.domain
        # Build the public URL — caller should already know the imagesBase
        print(f"Uploaded {upload_path.name} → r2://{bucket}/{args.r2_key}")
        if args.public_base:
            print(f"Public URL: {args.public_base}/{args.r2_key}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="image_utils", description="PNG→WebP + R2 upload helpers for Rank AI.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("convert", help="Convert a single PNG file to WebP")
    pc.add_argument("src")
    pc.add_argument("--dst", help="Output path (default: src with .webp extension)")
    pc.add_argument("--quality", type=int, default=90)
    pc.add_argument("--delete-source", action="store_true", help="Delete the .png after conversion")
    pc.set_defaults(func=cmd_convert)

    pcd = sub.add_parser("convert-dir", help="Convert all PNGs in a directory to WebP")
    pcd.add_argument("dir")
    pcd.add_argument("--quality", type=int, default=90)
    pcd.add_argument("--delete-source", action="store_true")
    pcd.set_defaults(func=cmd_convert_dir)

    pu = sub.add_parser("upload", help="Convert (if PNG) and upload to R2")
    pu.add_argument("--slug", required=True, help="Client slug (used to derive bucket name rankai-{slug})")
    pu.add_argument("--src", required=True)
    pu.add_argument("--r2-key", required=True, help="Object key in the bucket (e.g. brand/hero.webp)")
    pu.add_argument("--quality", type=int, default=90)
    pu.add_argument("--domain", help="Override domain (default: derive from slug)")
    pu.add_argument("--public-base", help="If given, print the public URL after upload")
    pu.set_defaults(func=cmd_upload)

    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    sys.exit(args.func(args))
