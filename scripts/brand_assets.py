#!/usr/bin/env python3
"""Branding-bucket asset helpers, shared between the setup ledger and the
site scaffold.

Extracted from setup_ledger.py 2026-08-14 (Air Care build): the ledger's
nightly pass knew how to pull a client's uploaded logo out of the branding
bucket, but build_site's scaffold did not — so every build whose client had
already uploaded a logo got it hand-fixed after the fact. One implementation,
two callers: setup_ledger's citations-readiness pass and build_site scaffold.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = ROOT / "sites"


def bucket_logo_files(cid: str) -> list[str]:
    """Logo-looking filenames in branding/{cid}/brand/. Read-only and safe on a
    dry run, which is the point: knowing whether we HOLD a logo must not depend
    on whether we are also allowed to write one into the repo."""
    sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (sb_url and sb_key):
        return []
    r = requests.post(f"{sb_url}/storage/v1/object/list/branding",
                      headers={"apikey": sb_key,
                               "Authorization": f"Bearer {sb_key}",
                               "Content-Type": "application/json"},
                      json={"prefix": f"{cid}/brand/", "limit": 100}, timeout=30)
    if not r.ok:
        return []
    return [f["name"] for f in r.json() if f.get("id")
            and re.match(r"(?i)logo.*\.(png|webp|jpe?g|svg|ai|eps)$", f.get("name") or "")]


def pull_bucket_logo(cid: str, slug: str) -> str | None:
    """Branding-bucket logo -> sites/{slug}/public/images/. Logos sometimes
    already exist in the bucket (Go Green's 07-29 upload sat there while the
    queue skipped them for 'no logo') — CHECK there before asking the client.
    Only files that LOOK like logo files count (the hub's Send Us Files page
    names them logo-{epoch}.{ext}); job photos/docs never match. Oversized
    originals get downscaled via Pillow (fail-open to raw bytes for png/webp;
    a JPEG we cannot convert is skipped — the pipelines read logo.png/webp).
    Returns the written filename or None."""
    sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    hdrs = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
            "Content-Type": "application/json"}
    r = requests.post(f"{sb_url}/storage/v1/object/list/branding", headers=hdrs,
                      json={"prefix": f"{cid}/brand/", "limit": 100}, timeout=30)
    if not r.ok:
        return None
    cands = [f["name"] for f in r.json() if f.get("id")
             and re.match(r"(?i)logo.*\.(png|webp|jpe?g)$", f.get("name") or "")]
    if not cands:
        return None
    name = sorted(cands)[-1]  # hub prefixes epoch ms -> lexically newest wins
    rf = requests.get(f"{sb_url}/storage/v1/object/branding/{cid}/brand/{name}",
                      headers=hdrs, timeout=60)
    if not rf.ok or not rf.content:
        return None
    data = rf.content
    ext = name.lower().rsplit(".", 1)[-1].replace("jpeg", "jpg")
    out_dir = SITES_DIR / slug / "public" / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        if max(im.size) > 1200:
            im.thumbnail((1200, 1200))
        buf = io.BytesIO()
        if ext == "webp":
            im.save(buf, "WEBP", quality=90)
            out = out_dir / "logo.webp"
        else:
            if im.mode not in ("RGB", "RGBA", "P", "L", "LA"):
                im = im.convert("RGBA")
            im.save(buf, "PNG", optimize=True)
            out = out_dir / "logo.png"
        data = buf.getvalue()
    except Exception:
        if ext == "jpg":
            return None  # can't hand a JPEG to pipelines expecting logo.png/webp
        out = out_dir / f"logo.{ext}"
    out.write_bytes(data)
    return out.name
