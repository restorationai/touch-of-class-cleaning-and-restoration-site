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


# ---------------------------------------------------------------------------
# Logo harvest from the client's EXISTING website (Santino 2026-09-03,
# content-now/brand-later item: "don't we have a system to retrieve the logo
# by looking at their existing website?"). Candidates in priority order:
#   1. header/nav <img> whose src/alt/class/id mentions "logo"
#   2. og:image
#   3. apple-touch-icon, then any rel=icon big enough to be usable
# The winner is uploaded to branding/{cid}/brand/logo-0harvest-{epoch}.{ext}.
# The "logo-0harvest" prefix sorts BEFORE every hub upload (logo-{epoch} /
# logo_{epoch}), so a real client upload always wins pull_bucket_logo's
# lexical newest-wins pick — harvest is the fallback, never the override.
# ---------------------------------------------------------------------------

def harvest_logo_from_web(cid: str, website: str) -> str | None:
    """Fetch the client's existing site and pull their logo into the brand
    bucket. Returns the bucket filename written, or None. Never raises."""
    import io
    import time as _time
    from urllib.parse import urljoin

    if not website:
        return None
    url = website if website.startswith("http") else "https://" + website
    # Full browser UA: Scorpion/Wix WAFs 403 bot-looking agents (TDI test)
    ua = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/128.0.0.0 Safari/537.36",
          "Accept": "text/html,application/xhtml+xml"}
    try:
        resp = requests.get(url, headers=ua, timeout=25, allow_redirects=True)
        if resp.status_code >= 400 and url.startswith("https://"):
            resp = requests.get(url.replace("https://", "http://", 1),
                                headers=ua, timeout=25, allow_redirects=True)
        if resp.status_code >= 400:
            return None
        html = resp.text
    except Exception:
        return None

    cands: list[str] = []
    # 1. logo-looking <img>
    for m in re.finditer(r"<img[^>]+>", html[:120_000], re.I):
        tag = m.group(0)
        src = re.search(r"""src=["']([^"']+)["']""", tag, re.I)
        if not src:
            continue
        blob = tag.lower()
        if "logo" in blob and "sprite" not in blob:
            cands.append(src.group(1))
    # 2. og:image
    og = re.search(r"""property=["']og:image["'][^>]+content=["']([^"']+)["']""", html, re.I) \
        or re.search(r"""content=["']([^"']+)["'][^>]+property=["']og:image["']""", html, re.I)
    if og:
        cands.append(og.group(1))
    # 3. touch icon / icons
    for m in re.finditer(r"""<link[^>]+rel=["'][^"']*(?:apple-touch-icon|icon)[^"']*["'][^>]+href=["']([^"']+)["']""", html, re.I):
        cands.append(m.group(1))

    sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    for cand in cands:
        try:
            full = urljoin(url + "/", cand)
            r = requests.get(full, headers=ua, timeout=25)
            if not r.ok or len(r.content) < 1500:      # tiny favicon = useless
                continue
            ctype = (r.headers.get("content-type") or "").lower()
            ext = ("svg" if "svg" in ctype else "png" if "png" in ctype
                   else "webp" if "webp" in ctype else "jpg" if "jpe" in ctype or "jpg" in ctype
                   else full.lower().rsplit(".", 1)[-1][:4])
            if ext not in ("png", "webp", "jpg", "svg"):
                continue
            if ext != "svg":
                try:
                    from PIL import Image
                    im = Image.open(io.BytesIO(r.content))
                    if max(im.size) < 64:              # too small to be a logo
                        continue
                except Exception:
                    continue
            name = f"logo-0harvest-{int(_time.time() * 1000)}.{ext}"
            up = requests.post(
                f"{sb_url}/storage/v1/object/branding/{cid}/brand/{name}",
                headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
                         "Content-Type": ctype or "application/octet-stream"},
                data=r.content, timeout=60)
            if up.ok:
                print(f"  [logo-harvest] {cid}: {full} -> branding/{cid}/brand/{name}")
                return name
        except Exception:
            continue
    return None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="brand asset helpers")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("harvest", help="harvest a logo from the client's existing website")
    h.add_argument("--cid", required=True)
    h.add_argument("--website", required=True)
    a = ap.parse_args()
    if a.cmd == "harvest":
        out = harvest_logo_from_web(a.cid, a.website)
        print(out or "no harvestable logo found")
