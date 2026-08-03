#!/usr/bin/env python3
"""
Rank AI — responsive image variants generator (the "responsive images pass").

Generates 480/768/1200w WebP variants for the homepage-critical images of each
active site so the templates can serve srcset/sizes and cut mobile transfer
(narestco mobile homepage was ~3.4MB of images before this).

What it does per site:
  LOCAL images (sites/{slug}/public/images/...):
      hero-bg.*, team.*, services/*.webp, gallery/img*.webp, before-after/*
      → writes {stem}-480w.webp / -768w.webp / -1200w.webp next to the original
        (PIL, WebP q=80, LANCZOS, never upscales — widths >= original skipped).
        Idempotent: a variant is skipped when it exists and is newer than the
        source.
  R2 images (brand/hero.webp, brand/hero-fleet.webp, plus any R2 URL found in
  src/content/services/*.md `hero:` frontmatter):
      → HEAD the public URL; if present, download, generate the same variants,
        upload alongside as {dir}/{stem}-{w}w.webp via wrangler (reuses
        scripts/image_utils.upload_to_r2 and the R2-scoped token). Variants
        already live on R2 (HEAD 200) are skipped unless --force.
  MANIFEST:
      → writes sites/{slug}/src/data/image-meta.json mapping the exact src
        string the components use (local path or full public URL) to
        {width, height, variants:[...]}. src/lib/images.ts#srcsetFor consumes
        this; images absent from the manifest render exactly as before.

Usage:
  python3 scripts/resize_images.py --slug narestco
  python3 scripts/resize_images.py --all              # the 4 active slugs
  python3 scripts/resize_images.py --all --dry-run
  python3 scripts/resize_images.py --slug narestco --force   # re-upload R2 variants
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from PIL import Image
except ImportError:
    sys.stderr.write("ERROR: Pillow not installed. Run: pip install Pillow\n")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass  # env may already be exported; wrangler will complain if not

from image_utils import upload_to_r2  # noqa: E402  (needs sys.path insert above)

VARIANT_WIDTHS = [480, 768, 1200]
WEBP_QUALITY = 80

SITES = {
    "narestco": {
        "bucket": "rankai-narestco",
        "images_base": "https://images.narestco.com",
    },
    "flood-fixers": {
        "bucket": "rankai-flood-fixers",
        "images_base": "https://images.flood-fixers.com",
    },
    "homepriderestorationandcleaning": {
        "bucket": "rankai-homepriderestorationandcleaning",
        "images_base": "https://images.homepriderestorationandcleaning.com",
    },
    "davis-construction": {
        "bucket": "rankai-davis-construction",
        "images_base": "https://images.davisconstructioncontractors.com",
    },
    # Preview-stage clients (Pages *-preview projects). Their images.{domain}
    # R2 hosts don't resolve yet — the R2 pass HEAD-fails and skips gracefully;
    # local variants + manifest still generate.
    "restoration-groups": {
        "bucket": "rankai-restoration-groups",
        "images_base": "https://images.restorationgroups.com",
    },
    "mcc-restoration": {
        "bucket": "rankai-mcc-restoration",
        "images_base": "https://images.mccrestoration.com",
    },
    "aaa-water-damage": {
        "bucket": "rankai-aaa-water-damage",
        "images_base": "https://images.aaawaterdamagehawaii.com",
    },
    "restorationxpress": {
        "bucket": "rankai-restorationxpress",
        "images_base": "https://images.restorationxpress.com",
    },
    "mold-solutionz-24-7-llc": {
        "bucket": "rankai-mold-solutionz-24-7-llc",
        "images_base": "https://images.moldsolutionz247.com",
    },
    "crew-restoration-construction": {
        "bucket": "rankai-crew-restoration-construction",
        "images_base": "https://images.crew3r.com",
    },
    # Auto-built previews (2026-07-29) — no domain yet; the R2 pass skips
    # gracefully, local variants + manifest still generate.
    "go-green-restoration-of-nc": {
        "bucket": "rankai-go-green-restoration-of-nc",
        "images_base": "https://images.gogreenrestorationofnc.pending",
    },
    "quality-contracting-inc": {
        "bucket": "rankai-quality-contracting-inc",
        "images_base": "https://images.qualitycontracting.pending",
    },
    "coastal-restoration-services": {
        "bucket": "rankai-coastal-restoration-services",
        "images_base": "https://images.coastalrestoration.pending",
    },
    "homelyft-restoration-ms": {
        "bucket": "rankai-homelyft-restoration-ms",
        "images_base": "https://images.homelyft.pending",
    },
}

# R2 keys every site may have; 404s are skipped gracefully.
R2_BRAND_KEYS = ["brand/hero.webp", "brand/hero-fleet.webp"]

IMG_SUFFIX_RE = re.compile(r"\.(webp|png|jpe?g)$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Variant generation
# ---------------------------------------------------------------------------

def open_rgb(data_or_path) -> Image.Image:
    im = Image.open(data_or_path)
    if im.mode == "P":
        im = im.convert("RGBA" if "transparency" in im.info else "RGB")
    elif im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    return im


def variant_bytes(im: Image.Image, width: int) -> bytes:
    h = max(1, round(im.height * width / im.width))
    resized = im.resize((width, h), Image.LANCZOS)
    out = io.BytesIO()
    resized.save(out, format="WEBP", quality=WEBP_QUALITY, method=6)
    return out.getvalue()


def variant_path(src: Path, width: int) -> Path:
    return src.with_name(f"{src.stem}-{width}w.webp")


# Cloudflare fronts the R2 public domains and 403s urllib's default UA.
UA = "Mozilla/5.0 (rank-ai resize_images)"


def head_url(url: str) -> int | None:
    """Return Content-Length for a 200 response, None on 404/error."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status == 200:
                cl = resp.headers.get("Content-Length")
                return int(cl) if cl else 0
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    return None


def download(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None


# ---------------------------------------------------------------------------
# Target discovery
# ---------------------------------------------------------------------------

def local_targets(site_dir: Path) -> list[Path]:
    """Homepage-critical local images for a site, in a stable order."""
    images = site_dir / "public" / "images"
    targets: list[Path] = []
    patterns = [
        "hero-bg.webp",
        "team.webp", "team.png",
        "crew.webp",
        "services.webp",
        "services/*.webp",
        "gallery/img*.webp",
        "work/*.webp",
        "before-after/*.png", "before-after/*.webp",
    ]
    for pat in patterns:
        for p in sorted(images.glob(pat)):
            # never treat an already-generated variant as a source
            if re.search(r"-(?:480|768|1200)w\.webp$", p.name):
                continue
            targets.append(p)
    return targets


def r2_targets(site_dir: Path, images_base: str) -> list[str]:
    """R2 object keys referenced by this site (brand heroes + service-card
    heroes whose frontmatter points at the site's imagesBase)."""
    keys = list(R2_BRAND_KEYS)
    services_dir = site_dir / "src" / "content" / "services"
    if services_dir.is_dir():
        for md in sorted(services_dir.glob("*.md")):
            for line in md.read_text(encoding="utf-8").splitlines():
                m = re.match(r"""^hero:\s*['"]?([^'"\s]+)['"]?\s*$""", line)
                if not m:
                    continue
                val = m.group(1)
                if val.startswith(images_base + "/"):
                    key = val[len(images_base) + 1:]
                    if key not in keys:
                        keys.append(key)
                # root-relative values are either local (handled by
                # local_targets) or, if missing locally, skipped — we never
                # emit srcset for an unverified variant.
    return keys


# ---------------------------------------------------------------------------
# Per-site processing
# ---------------------------------------------------------------------------

def process_site(slug: str, dry_run: bool, force: bool) -> dict:
    cfg = SITES[slug]
    site_dir = REPO_ROOT / "sites" / slug
    if not site_dir.is_dir():
        print(f"!! sites/{slug} not found — skipping")
        return {}

    print(f"\n===== {slug} =====")
    meta: dict[str, dict] = {}
    stats = {"generated": [], "uploaded": [], "skipped": [], "kb_480_total": 0.0}

    # ---- local images -----------------------------------------------------
    public_dir = site_dir / "public"
    for src in local_targets(site_dir):
        rel_url = "/" + src.relative_to(public_dir).as_posix()   # e.g. /images/team.webp
        im = open_rgb(src)
        widths = [w for w in VARIANT_WIDTHS if w < im.width]
        meta[rel_url] = {"width": im.width, "height": im.height, "variants": widths}
        if not widths:
            stats["skipped"].append(f"{rel_url} ({im.width}px wide — no smaller variants)")
        for w in widths:
            dst = variant_path(src, w)
            if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime and not force:
                if w == 480:
                    stats["kb_480_total"] += dst.stat().st_size / 1024
                continue
            if dry_run:
                print(f"  [dry-run] would generate {dst.relative_to(REPO_ROOT)}")
                continue
            data = variant_bytes(im, w)
            dst.write_bytes(data)
            kb = len(data) / 1024
            if w == 480:
                stats["kb_480_total"] += kb
            stats["generated"].append(f"{dst.relative_to(REPO_ROOT)} ({kb:.0f}KB)")
            print(f"  local  {rel_url} -> {dst.name}  {kb:.0f}KB")

    # ---- R2 images ---------------------------------------------------------
    for key in r2_targets(site_dir, cfg["images_base"]):
        url = f"{cfg['images_base']}/{key}"
        size = head_url(url)
        if size is None:
            stats["skipped"].append(f"{url} (404 on R2)")
            print(f"  r2     {key}: 404 — skipped")
            continue
        raw = download(url)
        if raw is None:
            stats["skipped"].append(f"{url} (download failed)")
            continue
        im = open_rgb(io.BytesIO(raw))
        widths = [w for w in VARIANT_WIDTHS if w < im.width]
        meta[url] = {"width": im.width, "height": im.height, "variants": widths}
        if not widths:
            stats["skipped"].append(f"{url} ({im.width}px wide — no smaller variants)")
        for w in widths:
            vkey = IMG_SUFFIX_RE.sub("", key) + f"-{w}w.webp"
            vurl = f"{cfg['images_base']}/{vkey}"
            existing = head_url(vurl)
            if existing is not None and not force:
                if w == 480:
                    stats["kb_480_total"] += existing / 1024
                print(f"  r2     {vkey}: already on R2 ({existing/1024:.0f}KB) — skipped")
                continue
            if dry_run:
                print(f"  [dry-run] would upload {cfg['bucket']}/{vkey}")
                continue
            data = variant_bytes(im, w)
            with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
                tmp.write(data)
                tmp_path = Path(tmp.name)
            try:
                ok = upload_to_r2(cfg["bucket"], vkey, tmp_path, content_type="image/webp")
            finally:
                tmp_path.unlink(missing_ok=True)
            kb = len(data) / 1024
            if ok:
                if w == 480:
                    stats["kb_480_total"] += kb
                stats["uploaded"].append(f"{cfg['bucket']}/{vkey} ({kb:.0f}KB)")
                print(f"  r2     uploaded {cfg['bucket']}/{vkey}  {kb:.0f}KB")
            else:
                stats["skipped"].append(f"{vkey} (upload failed)")

    # ---- manifest ----------------------------------------------------------
    meta_path = site_dir / "src" / "data" / "image-meta.json"
    if dry_run:
        print(f"  [dry-run] would write {meta_path.relative_to(REPO_ROOT)} ({len(meta)} entries)")
    else:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(dict(sorted(meta.items())), indent=2) + "\n", encoding="utf-8")
        print(f"  wrote  {meta_path.relative_to(REPO_ROOT)}  ({len(meta)} entries)")

    print(f"  -- {slug}: {len(stats['generated'])} local variants generated, "
          f"{len(stats['uploaded'])} R2 uploads, {len(stats['skipped'])} skipped, "
          f"480w set totals {stats['kb_480_total']:.0f}KB")
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate 480/768/1200w WebP variants + image-meta.json per site.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug", choices=sorted(SITES))
    g.add_argument("--all", action="store_true", help="process all active slugs")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="regenerate local variants and re-upload existing R2 variants")
    args = ap.parse_args()

    slugs = sorted(SITES) if args.all else [args.slug]
    for slug in slugs:
        process_site(slug, dry_run=args.dry_run, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
