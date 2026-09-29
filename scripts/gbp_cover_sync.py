#!/usr/bin/env python3
"""gbp_cover_sync.py -- GBP COVER from the site hero, per client
(Santino 2026-09-29: "RestorationXpress ... we added their hero image to their
cover photo and I think it looks great. Make sure we're doing the same thing for
every client and that we crop and fit the image to best represent it as their
cover photo.")

Subcommands (one client per process in CI, LAW 09-19; --all is a local
convenience loop):

  survey   For each active client with a site hero: resolve the GBP (verified?),
           read the CURRENT cover (v4 media, category COVER, newest), classify
           who put it there (our site asset / our cover-sync / picked in the app /
           owner), and record the site hero candidate (AI or real photo, sha1,
           size). AI heroes get a one-time vision check for readable text or
           branding (cached per hero sha1): an AI van that reads "Dry Bros" is
           invented branding, even when the name is right.
  preview  Survey + build the proposed cover: SMART crop to exact 16:9 (see
           smart_crop), 1920x1080 when the source window is >= 1920 wide, else
           1280x720; anything whose best 16:9 window is under 480x270 is
           rejected. Writes current / proposed / crop-map images + a per-client
           JSON under --out; `sheet` assembles covers.json + index.html.
  apply    Upload the proposed cover for ONE client (--slug). Dry run unless
           --apply AND env GBP_COVER_SYNC_WRITE=1. The final JPG is hosted in
           Supabase storage (branding/{cid}/site-assets/gbp-cover/...) and
           created via sourceUrl (the path that works for COVER everywhere
           tested); the v4 bytes flow is the fallback. Logged to
           marketing_gbp_changes (actor 'cover-sync') and ops_kv
           'gbp-cover-sync/{cid}' (hero sha1, applied_at, media name) so the
           same hero never goes up twice; a NEW hero sha1 re-applies.
  run      survey + preview + apply for one client (the nightly unit).
  sheet    Assemble covers.json + index.html from the per-client JSONs in --out.

POLICY (default; Santino to confirm):
  set      no cover, OR the cover is one we uploaded (site asset / an older
           cover-sync hero), OR the owner's cover is a graphic, not a photo
  update   our cover-sync cover whose hero sha1 differs from today's site hero
  skip     'owner-cover: needs Santino' -- the client/owner uploaded a real
           photo themselves (override: --replace-owner-cover); also covers a
           human picked in the app (actor 'app' in marketing_gbp_changes)
  skip     'ai-branding: needs Santino' -- AI hero with invented/readable
           branding or text (override: --allow-ai-branding)
  planner  unverified profile: 'planner: goes up at verification' (Google
           will not take a COVER through the API before verification)

Note on how the panel actually looks: Google chooses the panel's lead image
itself. RestorationXpress's COVER slot is still the owner's 2021 team photo;
the hero Santino saw is the EXTERIOR upload from the site-photo lane
(gbp_site_media.py) that Google promoted. Setting COVER explicitly is the
strongest signal we have, and the only one we control.

Usage:
  python3 scripts/gbp_cover_sync.py survey --all
  python3 scripts/gbp_cover_sync.py preview --all --out /tmp/covers && \
    python3 scripts/gbp_cover_sync.py sheet --out /tmp/covers
  python3 scripts/gbp_cover_sync.py apply --slug restorationxpress            # dry run
  python3 scripts/gbp_cover_sync.py run --slug X --apply                       # nightly (dry unless env)
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
import math
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gbp_site_media as sm  # noqa: E402  (loads rank-ai/.env; kv/storage/locate/probe helpers)
import gbp  # noqa: E402
import gbp_face_audit as fa  # noqa: E402  (media_account_for, upload_photo_bytes)

import requests  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageStat  # noqa: E402

DEAD = {"mcc-restoration", "mold-solutionz-24-7-llc"}   # never include (09-09, 09-19)
LEDGER = "gbp-cover-sync/{cid}"
ACTOR = "cover-sync"
OUT_TIERS = ((1920, 1080), (1280, 720))
MIN_W, MIN_H = 480, 270
CENTER_BAND = 0.70           # Google crops the cover further on mobile/desktop
VISION_MODEL = os.environ.get("GBP_COVER_VISION_MODEL") or os.environ.get("PHOTO_TRIAGE_MODEL", "claude-sonnet-5")


def write_enabled(apply: bool) -> bool:
    return apply and str(os.environ.get("GBP_COVER_SYNC_WRITE", "")).lower() in ("1", "true", "yes")


# --------------------------------------------------------------------------- #
# SMART CROP (PIL only; no numpy/OpenCV in CI)
# --------------------------------------------------------------------------- #
def _norm(vals: list[float]) -> list[float]:
    s = sorted(vals)
    hi = s[int(len(s) * 0.99)] or 1.0
    return [min(v / hi, 1.0) for v in vals]


def _pixels(im: Image.Image) -> list:
    """Pillow 12 deprecates getdata(); get_flattened_data() is its replacement."""
    fn = getattr(im, "get_flattened_data", None)
    return list(fn() if fn else im.getdata())


def energy_map(im: Image.Image, gw: int = 160) -> tuple[list[list[float]], int, int]:
    """Per-cell subject energy on a small grid: edge energy (structure: vans,
    people, rooflines) + frequency-tuned saliency (color distance from the
    image mean, Achanta 2009: bright vans against lawn) + saturation (brand
    color). Sky and plain lawn score low on all three."""
    gh = max(1, round(gw * im.height / im.width))
    small = im.convert("RGB").resize((gw, gh), Image.LANCZOS)
    blur = small.filter(ImageFilter.GaussianBlur(1.2))
    edges = _pixels(blur.convert("L").filter(ImageFilter.FIND_EDGES))
    px = _pixels(blur)
    mr, mg, mb = ImageStat.Stat(blur).mean
    sal = [math.sqrt((r - mr) ** 2 + (g - mg) ** 2 + (b - mb) ** 2) for r, g, b in px]
    sat = _pixels(blur.convert("HSV").getchannel("S"))
    # the outermost ring of FIND_EDGES is border noise
    for y in range(gh):
        for x in (0, gw - 1):
            edges[y * gw + x] = 0
    for x in range(gw):
        edges[x] = edges[(gh - 1) * gw + x] = 0
    e, s, c = _norm([float(v) for v in edges]), _norm(sal), _norm([float(v) for v in sat])
    flat = [0.45 * e[i] + 0.35 * s[i] + 0.20 * c[i] for i in range(gw * gh)]
    grid = [flat[y * gw:(y + 1) * gw] for y in range(gh)]
    return grid, gw, gh


def _integral(grid: list[list[float]]) -> list[list[float]]:
    h, w = len(grid), len(grid[0])
    ii = [[0.0] * (w + 1) for _ in range(h + 1)]
    for y in range(h):
        run = 0.0
        row, prev, cur = grid[y], ii[y], ii[y + 1]
        for x in range(w):
            run += row[x]
            cur[x + 1] = prev[x + 1] + run
    return ii


def _rect(ii, x0: float, y0: float, x1: float, y1: float) -> float:
    x0, y0 = max(0, int(round(x0))), max(0, int(round(y0)))
    x1, y1 = min(len(ii[0]) - 1, int(round(x1))), min(len(ii) - 1, int(round(y1)))
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return ii[y1][x1] - ii[y0][x1] - ii[y1][x0] + ii[y0][x0]


def subject_box(grid, gw: int, gh: int) -> tuple[float, float, float, float]:
    """Main-subject box: the energy-weighted 12th..88th percentile span on
    each axis of a centre-weighted energy map (a wide Gaussian prior keeps a
    busy palm-frond border from owning the box)."""
    col = [0.0] * gw
    row = [0.0] * gh
    for y in range(gh):
        wy = math.exp(-((y / gh - 0.47) ** 2) / (2 * 0.32 ** 2))
        for x in range(gw):
            wx = math.exp(-((x / gw - 0.5) ** 2) / (2 * 0.36 ** 2))
            v = grid[y][x] ** 1.6 * wx * wy       # ^1.6: strong cells dominate the texture floor
            col[x] += v
            row[y] += v

    def span(p: list[float], lo=0.12, hi=0.88) -> tuple[float, float]:
        tot = sum(p) or 1.0
        acc, a, b = 0.0, 0, len(p)
        for i, v in enumerate(p):
            acc += v
            if acc / tot < lo:
                a = i + 1
            if acc / tot <= hi:
                b = i + 1
        return float(a), float(max(b, a + 1))
    x0, x1 = span(col)
    y0, y1 = span(row)
    return x0, y0, x1, y1


def smart_crop(im: Image.Image) -> dict:
    """Choose the exact-16:9 window that best keeps the subject.

    Candidates: every 16:9 window from full size down to 80% zoom (zoom only
    when the source still fills the chosen output tier without upscaling),
    slid across both axes on the energy grid. Score =
        in-window energy + in-central-70% energy  (Google's further crop)
      - 3 x subject-box area cut off by the window   (never cut the subject)
      - boundary energy (edges that slice through structure)
      - a slight distance penalty from the centre / upper-centre prior.
    Returns the crop box in source pixels plus diagnostics."""
    W, H = im.size
    target = 16 / 9
    fw = min(W, H * target)                          # full-size 16:9 window
    fh = fw / target
    if fw < MIN_W or fh < MIN_H:
        return {"ok": False, "reason": f"too small for a cover: best 16:9 window {int(fw)}x{int(fh)} < {MIN_W}x{MIN_H}"}
    out_w, out_h = next(((ow, oh) for ow, oh in OUT_TIERS if fw >= ow), OUT_TIERS[-1])
    min_scale = max(0.80, out_w / fw) if fw >= out_w else 1.0
    grid, gw, gh = energy_map(im)
    ii = _integral(grid)
    total = ii[gh][gw] or 1.0
    k = gw / W                                       # source px -> grid cells
    sx0, sy0, sx1, sy1 = subject_box(grid, gw, gh)
    s_area = max((sx1 - sx0) * (sy1 - sy0), 1.0)
    tall = (H * target) < W - 1e-6                   # window slides horizontally when False
    prior_y = 0.44 if not tall and H > fh + 1 else 0.5   # upper-centre bias when sliding vertically
    best = None
    scales = [1.0]
    s = 1.0
    while s - 0.025 >= min_scale - 1e-9:
        s -= 0.025
        scales.append(round(s, 3))
    for sc in scales:
        ww, wh = fw * sc * k, fh * sc * k
        nx = max(1, int((gw - ww) // 1) + 1)
        ny = max(1, int((gh - wh) // 1) + 1)
        stepx = max(1, (nx - 1) // 60 or 1)
        stepy = max(1, (ny - 1) // 60 or 1)
        for oy in range(0, ny, stepy):
            for ox in range(0, nx, stepx):
                x0, y0 = min(ox, gw - ww), min(oy, gh - wh)
                x1, y1 = x0 + ww, y0 + wh
                inside = _rect(ii, x0, y0, x1, y1)
                cx0, cy0 = x0 + ww * (1 - CENTER_BAND) / 2, y0 + wh * (1 - CENTER_BAND) / 2
                core = _rect(ii, cx0, cy0, cx0 + ww * CENTER_BAND, cy0 + wh * CENTER_BAND)
                ix = max(0.0, min(x1, sx1) - max(x0, sx0))
                iy = max(0.0, min(y1, sy1) - max(y0, sy0))
                cut = 1.0 - (ix * iy) / s_area
                band = max(1.0, ww * 0.02)
                edge = (_rect(ii, x0, y0, x0 + band, y1) + _rect(ii, x1 - band, y0, x1, y1)) / (2 * band * wh) \
                    if ww < gw - 1 else 0.0
                edge_v = (_rect(ii, x0, y0, x1, y0 + band) + _rect(ii, x0, y1 - band, x1, y1)) / (2 * band * ww) \
                    if wh < gh - 1 else 0.0
                mean = total / (gw * gh)
                cxn, cyn = (x0 + ww / 2) / gw, (y0 + wh / 2) / gh
                dist = abs(cxn - 0.5) + abs(cyn - prior_y)
                score = (inside + core) / total - 3.0 * cut - 0.04 * (edge + edge_v) / mean - 0.15 * dist
                if best is None or score > best[0]:
                    best = (score, sc, x0 / k, y0 / k, ww / k, wh / k, inside / total, core / max(inside, 1e-9), cut)
    _, sc, bx, by, bw, bh, kept, core_share, cut = best
    bx, by = max(0.0, min(bx, W - bw)), max(0.0, min(by, H - bh))
    box = (int(round(bx)), int(round(by)), int(round(bx + bw)), int(round(by + bh)))
    # subject centroid inside the chosen window, 0..1 (for the central-70% check)
    scx = ((sx0 + sx1) / 2 / k - box[0]) / (box[2] - box[0])
    scy = ((sy0 + sy1) / 2 / k - box[1]) / (box[3] - box[1])
    lo, hi = (1 - CENTER_BAND) / 2, 1 - (1 - CENTER_BAND) / 2
    return {
        "ok": True, "box": box, "scale": sc, "out": [out_w, out_h],
        "source": [W, H], "window": [box[2] - box[0], box[3] - box[1]],
        "upscaled": (box[2] - box[0]) < out_w,
        "energy_kept": round(kept, 3), "center70_share": round(core_share, 3),
        "subject_cut": round(cut, 3),
        "subject_box": [int(sx0 / k), int(sy0 / k), int(sx1 / k), int(sy1 / k)],
        "subject_centroid": [round(scx, 3), round(scy, 3)],
        "subject_in_center70": lo <= scx <= hi and lo <= scy <= hi,
    }


def render_cover(im: Image.Image, crop: dict) -> bytes:
    ow, oh = crop["out"]
    out = im.convert("RGB").crop(crop["box"]).resize((ow, oh), Image.LANCZOS)
    assert out.size == (ow, oh) and abs(ow / oh - 16 / 9) < 1e-6
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=90, optimize=True, progressive=True)
    return buf.getvalue()


def crop_map(im: Image.Image, crop: dict, width: int = 720) -> Image.Image:
    """The source with the chosen window (solid), its central 70% (dashed-ish)
    and the detected subject box (thin) drawn on it."""
    rgb = im.convert("RGB")
    s = width / rgb.width
    view = rgb.resize((width, max(1, int(rgb.height * s))), Image.LANCZOS)
    shade = Image.new("RGB", view.size, (0, 0, 0))
    mask = Image.new("L", view.size, 110)
    x0, y0, x1, y1 = [int(v * s) for v in crop["box"]]
    ImageDraw.Draw(mask).rectangle((x0, y0, x1, y1), fill=0)
    view = Image.composite(shade, view, mask)
    d = ImageDraw.Draw(view)
    d.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(255, 255, 255), width=3)
    ww, wh = x1 - x0, y1 - y0
    cx0, cy0 = x0 + ww * 0.15, y0 + wh * 0.15
    cx1, cy1 = x0 + ww * 0.85, y0 + wh * 0.85
    for i in range(int(cx0), int(cx1), 12):
        d.line((i, cy0, min(i + 6, cx1), cy0), fill=(255, 214, 0), width=2)
        d.line((i, cy1, min(i + 6, cx1), cy1), fill=(255, 214, 0), width=2)
    for i in range(int(cy0), int(cy1), 12):
        d.line((cx0, i, cx0, min(i + 6, cy1)), fill=(255, 214, 0), width=2)
        d.line((cx1, i, cx1, min(i + 6, cy1)), fill=(255, 214, 0), width=2)
    sb = [int(v * s) for v in crop["subject_box"]]
    d.rectangle(sb, outline=(0, 200, 255), width=1)
    return view


# --------------------------------------------------------------------------- #
# GBP state
# --------------------------------------------------------------------------- #
def resolve_location(slug: str, cid: str) -> tuple[str | None, str | None, dict | None, str]:
    """(token, v4 account, location{name,title,metadata}, detail). The site
    lane's locate() (place_id / planner google_location) first; else the
    connection's selected_location_id (Dry Bros has no place_id yet)."""
    try:
        tok, acct, loc, detail = sm.locate(slug, cid)
    except Exception as e:  # noqa: BLE001
        tok, acct, loc, detail = None, None, None, f"locate failed: {str(e)[:80]}"
    if loc:
        return tok, acct, loc, detail
    rows = gbp._sb(f"user_integrations?provider=eq.google&client_id=eq.{cid}&select=connection_metadata")
    sel = next(((r.get("connection_metadata") or {}).get("selected_location_id") for r in rows
                if (r.get("connection_metadata") or {}).get("selected_location_id")), None)
    if not sel:
        return tok, None, None, detail
    tok = tok or gbp.get_access_token(cid)
    if not tok:
        return None, None, None, "no business.manage token"
    try:
        loc = gbp._g(f"{gbp.INFO_API}/{sel}?readMask=name,title,metadata", tok)
    except Exception as e:  # noqa: BLE001
        return tok, None, None, f"selected {sel} unreadable: {str(e)[:80]}"
    acct = fa.media_account_for(tok, sel.split("/")[-1])
    return tok, acct, loc, "found via selected_location_id"


def list_media(tok: str, acct: str, loc_name: str) -> list[dict]:
    lid = loc_name.split("/")[-1]
    items, page = [], ""
    for _ in range(20):
        r = requests.get(f"{sm.GBP_V4}/{acct}/locations/{lid}/media?pageSize=100"
                         + (f"&pageToken={page}" if page else ""),
                         headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        r.raise_for_status()
        j = r.json()
        items += j.get("mediaItems", [])
        page = j.get("nextPageToken") or ""
        if not page:
            break
    return items


def _our_url_markers(slug: str, domain: str) -> list[str]:
    marks = [f"{sm.SB_URL}/storage/v1/object/public/{sm.BUCKET}/"] if sm.SB_URL else []
    if domain:
        marks += [f"//{domain}/", f"//www.{domain}/", f"//images.{domain}/"]
    try:
        rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
        for u in ((rec.get("r2") or {}).get("public_url"), rec.get("deploy_url")):
            if u:
                marks.append(u.rstrip("/") + "/")
    except Exception:  # noqa: BLE001
        pass
    return marks


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def looks_like_photo(data: bytes) -> tuple[bool, str]:
    """Cheap photo-vs-graphic test: logos, text banners and flat graphics put
    most of their pixels in a handful of colours."""
    try:
        im = Image.open(io.BytesIO(data)).convert("RGB").resize((96, 54))
        q = im.quantize(colors=64)
        counts = sorted((c for c, _ in q.getcolors(64) or []), reverse=True)
        top8 = sum(counts[:8]) / (96 * 54)
        return top8 < 0.72, f"top-8 colour share {top8:.2f}"
    except Exception as e:  # noqa: BLE001
        return True, f"unreadable ({str(e)[:40]})"


def _vision_json(img: bytes, prompt: str, max_tokens: int = 600) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("no ANTHROPIC_API_KEY")
    im = Image.open(io.BytesIO(img)).convert("RGB")
    im.thumbnail((1400, 1400))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=90, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
        json={"model": VISION_MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.b64encode(buf.getvalue()).decode()}},
            {"type": "text", "text": prompt}]}]})
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json().get("content", []))
    return json.loads(text[text.find("{"):text.rfind("}") + 1])


def cover_kind(data: bytes, media_name: str | None, cached: dict | None) -> dict:
    """Is the current cover a real PHOTO, or a graphic (logo, flyer, banner
    with text overlay, illustration)? The pixel test alone missed logos on
    photo backgrounds and flyers (2026-09-29 fleet survey: it caught 1 of 10),
    so a vision pass decides, cached per media name; the pixel test is the
    fallback when vision is unavailable."""
    if cached and cached.get("media_name") == media_name and cached.get("cover_kind_by") == "vision":
        return {k: cached.get(k) for k in ("photo_like", "photo_test", "cover_kind_by")}
    try:
        j = _vision_json(data, "This is the current cover image of a Google Business Profile. Classify it. "
                         "'photo' = a genuine photograph (people, vehicles, a building, a job site, equipment), "
                         "even if a wrap or sign shows text. 'graphic' = a logo, flyer, ad banner, text overlay "
                         "on a photo, collage, illustration or 3D render. Reply ONLY with JSON: "
                         '{"kind": "photo|graphic", "note": "short reason"}', max_tokens=200)
        kind = str(j.get("kind") or "").lower()
        if kind in ("photo", "graphic"):
            return {"photo_like": kind == "photo", "photo_test": str(j.get("note") or kind)[:160],
                    "cover_kind_by": "vision"}
    except Exception as e:  # noqa: BLE001
        print(f"    (cover vision unavailable: {str(e)[:60]}; pixel test)")
    ok, why = looks_like_photo(data)
    return {"photo_like": ok, "photo_test": why, "cover_kind_by": "pixels"}


def classify_cover(slug: str, cid: str, domain: str, cover: dict | None, ledger: dict) -> dict:
    if not cover:
        return {"who": "none", "detail": "no COVER set"}
    src = cover.get("sourceUrl") or ""
    name = cover.get("name") or ""
    created = _ts(cover.get("createTime"))
    applied = ledger.get("applied") or []
    if any(a.get("media_name") == name or (src and a.get("source_url") == src) for a in applied):
        a = next(a for a in applied if a.get("media_name") == name or (src and a.get("source_url") == src))
        return {"who": "cover-sync", "detail": f"our cover-sync hero {a.get('hero_sha1')}",
                "hero_sha1": a.get("hero_sha1")}
    if "/site-assets/gbp-cover/" in src:
        m = re.search(r"cover-([0-9a-f]{8,16})", src)
        return {"who": "cover-sync", "detail": "our cover-sync upload (ledger lost)",
                "hero_sha1": m.group(1) if m else None}
    if "googleusercontent" in src and "=w1280-h720-c" in src:
        return {"who": "app-picked", "detail": "picked from the GBP photos in the app (human choice)"}
    if src and any(mk in src for mk in _our_url_markers(slug, domain)):
        return {"who": "ours-site-asset", "detail": f"our upload ({src[:90]})"}
    # a bytes-flow cover from the app's --set-cover leaves no sourceUrl: match
    # the change log by time (+-20 min of createTime)
    try:
        rows = gbp._sb(f"marketing_gbp_changes?company_id=eq.{cid}&change_type=eq.profile_cover_photo"
                       "&select=actor,changed_at,meta")
    except Exception:  # noqa: BLE001
        rows = []
    for r in rows:
        t = _ts(r.get("changed_at"))
        if (r.get("meta") or {}).get("media_name") == name or (created and t and abs((t - created).total_seconds()) < 1200):
            who = "cover-sync" if r.get("actor") == ACTOR else "app-picked"
            return {"who": who, "detail": f"change log: set by {r.get('actor')} {r.get('changed_at', '')[:10]}"}
    return {"who": "owner", "detail": "not in any of our ledgers: the client/owner (or a prior vendor) set it"}


# --------------------------------------------------------------------------- #
# hero candidate
# --------------------------------------------------------------------------- #
def hero_candidate(slug: str, cid: str) -> dict:
    man = None
    try:
        man = sm.kv_get(f"site-assets/{cid}")
    except Exception:  # noqa: BLE001
        pass
    img_dir = ROOT / "sites" / slug / "public" / "images"
    entry = next((i for i in (man or {}).get("images", []) if i.get("role") == "hero"), None)
    path = img_dir / entry["key"] if entry else None
    if not path or not path.exists():
        path = next((f for f in sm.collect_images(slug) if f.stem == "hero-bg"), None)
    if not path or not path.exists():
        return {"ok": False, "reason": "no hero-bg in the site build"}
    raw = path.read_bytes()
    reals = sm.real_slots(slug)
    rel = path.relative_to(img_dir).as_posix()
    real = reals.get(f"/images/{rel}")
    ai = bool(entry["ai_generated"]) if entry else (not real)
    if real:
        ai = False
    w, h = Image.open(io.BytesIO(raw)).size
    return {"ok": True, "path": str(path), "key": rel, "sha1": hashlib.sha1(raw).hexdigest()[:16],
            "width": w, "height": h, "ai_generated": ai,
            "provenance": (entry or {}).get("provenance") or (
                f"real photo ({real.get('source')})" if real else "AI-generated site image"),
            "site_url": (entry or {}).get("site_url") or "", "live": bool((entry or {}).get("live")),
            "manifest": bool(man)}


def real_alternative(slug: str) -> dict | None:
    """Best REAL landscape photo photo_harvest scored for the hero slot."""
    p = ROOT / "clients" / slug / "photo-manifest.json"
    try:
        assets = (json.loads(p.read_text()) if p.exists() else {}).get("assets") or {}
    except json.JSONDecodeError:
        return None
    best = None
    for a in assets.values():
        sc = ((a.get("slots") or {}).get("hero") or 0)
        w, h = a.get("width") or 0, a.get("height") or 0
        if sc >= 60 and w > h and w >= 960 and not a.get("flags") and (best is None or sc > best["hero_score"]):
            best = {"url": a.get("url"), "subject": a.get("subject"), "hero_score": sc, "size": f"{w}x{h}"}
    return best


REVIEW_VERSION = 2


def vision_review(hero: dict, cached: dict | None, facts: dict) -> dict:
    """Heroes the manifest calls AI: one vision pass per hero sha1 (cached in
    the ledger) for readable text/branding, judged against the client's real
    name / phone / domain, plus a second opinion on whether it is a real
    photograph (narestco's hero predates photo_harvest, so the manifest calls
    a real crew photo AI). Verdicts:
      ai-clean     no readable text
      ai-brand-ok  only the real name (or a clean shortening), the real phone
                   or domain, or generic service words, all spelled right
                   (RestorationXpress: the look Santino liked)
      ai-branding  anything else: garbled lettering, an invented phone / URL /
                   slogan / license-or-certification claim, another name
    Fail-open to 'unreviewed' (blocks the automatic write, never the report)."""
    if not hero.get("ai_generated"):
        return {"sha1": hero["sha1"], "status": "real-photo", "v": REVIEW_VERSION}
    if cached and cached.get("sha1") == hero["sha1"] and cached.get("v") == REVIEW_VERSION \
            and cached.get("status") not in (None, "unreviewed"):
        return cached
    prompt = (
        "This image is about to become the Google Business Profile cover photo for a real company.\n"
        f"Real business name: {facts.get('name')!r}. Real phone: {facts.get('phone') or 'unknown'!r}. "
        f"Real website: {facts.get('domain') or 'unknown'!r}.\n"
        "1) List EVERY readable string (vehicle wraps, uniforms, signs, logos, phone numbers, URLs).\n"
        "2) verdict: 'clean' if there is no readable text; 'brand-ok' if every string is the real business "
        "name or an obvious clean shortening of it, the real phone, the real website, or plain generic "
        "service words (e.g. 'Water Damage Restoration', '24/7'), all spelled correctly; otherwise 'fake' "
        "(misspelled/garbled lettering, a phone number or URL that is not the real one, invented slogans, "
        "license/certification/insurance claims, another business's name, an illegible pseudo-logo).\n"
        "3) origin: 'real' if this is clearly a genuine photograph of real people/vehicles/places, 'ai' if it "
        "looks AI-generated or rendered, 'unsure' otherwise.\n"
        'Reply ONLY with JSON: {"texts": [...], "verdict": "clean|brand-ok|fake", "problems": [short strings], '
        '"origin": "real|ai|unsure", "note": "one sentence"}')
    try:
        j = _vision_json(Path(hero["path"]).read_bytes(), prompt, max_tokens=800)
    except Exception as e:  # noqa: BLE001
        return {"sha1": hero["sha1"], "status": "unreviewed", "note": f"vision failed: {str(e)[:80]}",
                "v": REVIEW_VERSION}
    verdict = str(j.get("verdict") or "").lower()
    status = {"clean": "ai-clean", "brand-ok": "ai-brand-ok"}.get(verdict, "ai-branding")
    return {"sha1": hero["sha1"], "status": status, "texts": [str(t) for t in (j.get("texts") or [])][:10],
            "problems": [str(t) for t in (j.get("problems") or [])][:6], "origin": j.get("origin"),
            "note": str(j.get("note") or "")[:220], "model": VISION_MODEL, "at": sm.iso(), "v": REVIEW_VERSION}


# --------------------------------------------------------------------------- #
# survey (one client)
# --------------------------------------------------------------------------- #
def survey_one(slug: str, want_current_bytes: bool = False) -> dict:
    cid = gbp.company_id_for(slug)
    rep: dict = {"slug": slug, "company_id": cid, "at": sm.iso()}
    if not cid:
        return {**rep, "action": "skip", "reason": "no company_id"}
    ledger = sm.kv_get(LEDGER.format(cid=cid)) or {}
    rep["ledger_applied"] = (ledger.get("applied") or [])[-1:] or None
    pi_path = ROOT / "clients" / slug / "plan-input.json"
    pi = json.loads(pi_path.read_text()) if pi_path.exists() else {}
    brand = (pi.get("brand") or {}).get("display_name") or slug
    rep["brand"] = brand
    site = sm.site_row(cid)
    domain = (site.get("domain") or "").strip().lower().replace("https://", "").strip("/")
    rep["domain"] = domain

    hero = hero_candidate(slug, cid)
    rep["hero"] = {k: v for k, v in hero.items() if k != "path"} | ({"path": hero.get("path")} if hero.get("path") else {})
    if hero.get("ok"):
        rep["hero_review"] = vision_review(hero, ledger.get("hero_review"), {
            "name": brand, "phone": (pi.get("brand") or {}).get("phone"), "domain": domain})
    rep["real_alternative"] = real_alternative(slug)

    tok, acct, loc, detail = resolve_location(slug, cid)
    md = (loc or {}).get("metadata") or {}
    rep["gbp"] = {"location": (loc or {}).get("name"), "title": (loc or {}).get("title"),
                  "verified": bool(md.get("hasVoiceOfMerchant")), "detail": detail, "account": acct}
    cover = None
    if loc and acct:
        try:
            covers = [m for m in list_media(tok, acct, loc["name"])
                      if (m.get("locationAssociation") or {}).get("category") == "COVER"]
            covers.sort(key=lambda m: m.get("createTime", ""), reverse=True)
            cover = covers[0] if covers else None
            rep["cover_count"] = len(covers)
        except Exception as e:  # noqa: BLE001
            rep["cover_error"] = str(e)[:160]
    elif loc and not acct:
        rep["cover_error"] = "no v4 media account can see this location"
    who = classify_cover(slug, cid, domain, cover, ledger) if not rep.get("cover_error") else {"who": "unknown", "detail": rep["cover_error"]}
    cur: dict = {**who}
    if cover:
        dim = cover.get("dimensions") or {}
        cur.update({"media_name": cover.get("name"), "create_time": cover.get("createTime"),
                    "google_url": cover.get("googleUrl"), "source_url": cover.get("sourceUrl"),
                    "size": f"{dim.get('widthPixels')}x{dim.get('heightPixels')}" if dim else None})
        base = (cover.get("googleUrl") or cover.get("thumbnailUrl") or "").split("=")[0]
        if base:
            try:
                r = requests.get(base + "=w1280", timeout=30)
                r.raise_for_status()
                cur.update(cover_kind(r.content, cover.get("name"), ledger.get("cover_review")))
                rep["cover_review"] = {"media_name": cover.get("name"), **{k: cur.get(k) for k in (
                    "photo_like", "photo_test", "cover_kind_by")}}
                if want_current_bytes:
                    rep["_current_bytes"] = r.content
            except Exception as e:  # noqa: BLE001
                cur["fetch_error"] = str(e)[:100]
    rep["current_cover"] = cur
    rep.update(decide(rep, ledger))
    return rep


def decide(rep: dict, ledger: dict, replace_owner: bool = False, allow_ai_branding: bool = False) -> dict:
    hero, cur, g = rep.get("hero") or {}, rep.get("current_cover") or {}, rep.get("gbp") or {}
    review = rep.get("hero_review") or {}
    if not hero.get("ok"):
        return {"action": "skip", "reason": hero.get("reason", "no hero")}
    if not g.get("location"):
        return {"action": "skip", "reason": f"no GBP location resolved ({g.get('detail')})"}
    if not g.get("verified"):
        return {"action": "planner", "reason": "planner: goes up at verification (unverified profile)"}
    if cur.get("who") == "unknown":
        return {"action": "skip", "reason": f"cover unreadable: {cur.get('detail')}"}
    last = (ledger.get("applied") or [{}])[-1]
    if cur.get("who") == "cover-sync" and (cur.get("hero_sha1") or last.get("hero_sha1")) == hero["sha1"]:
        return {"action": "in-sync", "reason": "cover already is today's hero"}
    if hero.get("ai_generated") and review.get("status") == "ai-branding" and not allow_ai_branding:
        why = "; ".join(review.get("problems") or review.get("texts") or [])
        if review.get("origin") == "real":
            return {"action": "skip", "reason": "provenance: manifest says AI but it looks like a REAL photo with "
                                                f"branding ({why}); confirm in photo-manifest, needs Santino"}
        return {"action": "skip", "reason": f"ai-branding: needs Santino ({why})"}
    if hero.get("ai_generated") and review.get("status") == "unreviewed" and not allow_ai_branding:
        return {"action": "skip", "reason": f"ai-hero unreviewed ({review.get('note')}); rerun when vision is back"}
    who = cur.get("who")
    if who == "none":
        return {"action": "set", "reason": "no cover yet"}
    if who == "cover-sync":
        return {"action": "update", "reason": "site hero changed since our last cover"}
    if who == "ours-site-asset":
        return {"action": "set", "reason": "replace our earlier site-asset cover with the fitted hero"}
    if who == "owner" and cur.get("photo_like") is False:
        return {"action": "set", "reason": f"owner cover is a graphic, not a photo ({cur.get('photo_test')})"}
    if who == "app-picked" and cur.get("photo_like") is False and not replace_owner:
        return {"action": "skip", "reason": f"app-picked cover is a graphic ({cur.get('photo_test')}); "
                                            "a human chose it: needs Santino"}
    if who in ("owner", "app-picked"):
        if replace_owner:
            return {"action": "set", "reason": f"--replace-owner-cover over the {who} cover"}
        return {"action": "skip", "reason": "owner-cover: needs Santino" if who == "owner"
                else "app-picked cover (a human chose it): needs Santino"}
    return {"action": "skip", "reason": f"unhandled cover state {who}"}


# --------------------------------------------------------------------------- #
# preview
# --------------------------------------------------------------------------- #
def preview_one(slug: str, out: Path) -> dict:
    rep = survey_one(slug, want_current_bytes=True)
    img_dir = out / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    (out / "full").mkdir(exist_ok=True)
    cur_bytes = rep.pop("_current_bytes", None)
    if cur_bytes:
        im = Image.open(io.BytesIO(cur_bytes)).convert("RGB")
        im.thumbnail((960, 960))
        im.save(img_dir / f"{slug}-current.jpg", "JPEG", quality=84)
        rep["current_img"] = f"img/{slug}-current.jpg"
    hero = rep.get("hero") or {}
    if hero.get("ok"):
        src = Image.open(hero["path"])
        crop = smart_crop(src)
        rep["crop"] = crop
        if crop["ok"]:
            jpg = render_cover(src, crop)
            (out / "full" / f"{slug}-cover-{crop['out'][0]}x{crop['out'][1]}.jpg").write_bytes(jpg)
            view = Image.open(io.BytesIO(jpg))
            view.thumbnail((960, 540))
            view.save(img_dir / f"{slug}-proposed.jpg", "JPEG", quality=84)
            crop_map(src, crop).save(img_dir / f"{slug}-cropmap.jpg", "JPEG", quality=82)
            rep["proposed_img"] = f"img/{slug}-proposed.jpg"
            rep["cropmap_img"] = f"img/{slug}-cropmap.jpg"
            rep["proposed_full"] = f"full/{slug}-cover-{crop['out'][0]}x{crop['out'][1]}.jpg"
            rep["proposed_bytes"] = len(jpg)
        elif rep.get("action") in ("set", "update"):
            rep["action"], rep["reason"] = "skip", crop["reason"]
    rep.get("hero", {}).pop("path", None)
    (out / "clients").mkdir(exist_ok=True)
    (out / "clients" / f"{slug}.json").write_text(json.dumps(rep, indent=1, default=str))
    _persist_survey(rep)
    return rep


def _persist_survey(rep: dict) -> None:
    """Keep the survey + vision review on the per-client ledger (our store)."""
    cid = rep.get("company_id")
    if not cid:
        return
    try:
        led = sm.kv_get(LEDGER.format(cid=cid)) or {}
        if rep.get("hero_review"):
            led["hero_review"] = rep["hero_review"]
        if rep.get("cover_review"):
            led["cover_review"] = rep["cover_review"]
        led["survey"] = {k: rep.get(k) for k in ("at", "action", "reason", "gbp", "current_cover", "crop")}
        led["survey"]["hero"] = {k: v for k, v in (rep.get("hero") or {}).items() if k != "path"}
        sm.kv_put(LEDGER.format(cid=cid), led)
    except Exception as e:  # noqa: BLE001
        print(f"    ! ledger write failed: {str(e)[:100]}")


# --------------------------------------------------------------------------- #
# apply (one client)
# --------------------------------------------------------------------------- #
def create_cover(tok: str, acct: str, loc_name: str, public_url: str, jpg: bytes) -> tuple[str, str]:
    lid = loc_name.split("/")[-1]
    r = requests.post(f"{sm.GBP_V4}/{acct}/locations/{lid}/media", timeout=60,
                      headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                      json={"mediaFormat": "PHOTO", "locationAssociation": {"category": "COVER"},
                            "sourceUrl": public_url})
    if r.status_code in (200, 201):
        return r.json().get("name", ""), "sourceUrl"
    first = f"sourceUrl HTTP {r.status_code}: {r.text[:200]}"
    try:
        return fa.upload_photo_bytes(tok, acct, lid, jpg, category="COVER"), "bytes"
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"{first}; bytes fallback: {str(e)[:200]}")


def apply_one(slug: str, apply: bool, replace_owner: bool, allow_ai_branding: bool,
              out: Path | None = None) -> str:
    out = out or Path(tempfile.mkdtemp(prefix="cover-sync-"))
    rep = preview_one(slug, out)
    cid = rep.get("company_id")
    if not cid:
        return f"  [{slug}] skip: no company_id"
    ledger = sm.kv_get(LEDGER.format(cid=cid)) or {}
    if rep.get("hero", {}).get("ok") and (rep.get("crop") or {}).get("ok"):
        rep.update(decide(rep, ledger, replace_owner, allow_ai_branding))
    write = write_enabled(apply)
    mode = "WRITE" if write else ("DRY (GBP_COVER_SYNC_WRITE not set)" if apply else "DRY")
    hero, cur, crop = rep.get("hero") or {}, rep.get("current_cover") or {}, rep.get("crop") or {}
    tag = "AI" if hero.get("ai_generated") else "real"
    line = (f"  [{slug}] {mode}: cover={cur.get('who')} ({cur.get('create_time', '-')}); hero {tag} "
            f"{hero.get('width')}x{hero.get('height')} sha {hero.get('sha1')}"
            + (f"; crop {crop['window'][0]}x{crop['window'][1]}->{crop['out'][0]}x{crop['out'][1]} "
               f"subject-in-center70={crop['subject_in_center70']}" if crop.get("ok") else "")
            + f"\n    -> {rep['action'].upper()}: {rep['reason']}")
    if rep["action"] not in ("set", "update"):
        return line
    if not write:
        return line + f"\n    would upload {rep.get('proposed_full')} as COVER on {rep['gbp']['location']}"
    # ---- WRITE path (only with --apply AND GBP_COVER_SYNC_WRITE=1) ----
    jpg = (out / rep["proposed_full"]).read_bytes()
    path = f"{cid}/site-assets/gbp-cover/cover-{hero['sha1']}-{crop['out'][0]}x{crop['out'][1]}.jpg"
    try:
        public = sm.storage_upload(path, jpg, "image/jpeg")
        tok, acct, loc, _ = resolve_location(slug, cid)
        name, via = create_cover(tok, acct, loc["name"], public, jpg)
    except Exception as e:  # noqa: BLE001
        return line + f"\n    FAILED: {str(e)[:300]}"
    rec = {"hero_sha1": hero["sha1"], "hero_key": hero.get("key"), "ai_generated": hero.get("ai_generated"),
           "applied_at": sm.iso(), "media_name": name, "source_url": public, "via": via,
           "crop_box": crop["box"], "out": crop["out"], "replaced": cur.get("media_name"),
           "replaced_who": cur.get("who")}
    ledger = sm.kv_get(LEDGER.format(cid=cid)) or {}
    ledger.setdefault("applied", []).append(rec)
    sm.kv_put(LEDGER.format(cid=cid), ledger)
    gbp.log_change(cid, "profile_cover_photo",
                   "Cover photo updated to match the website hero" if rep["action"] == "update"
                   else "Website hero set as the Google listing cover photo",
                   actor=ACTOR, meta={"media_name": name, "photo_url": public, "hero_sha1": hero["sha1"],
                                      "via": via, "replaced": cur.get("media_name")})
    return line + f"\n    COVER set -> {name} (via {via})"


# --------------------------------------------------------------------------- #
# contact sheet
# --------------------------------------------------------------------------- #
SHEET_CSS = """
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1f;--muted:#6b6b70;--line:#e3e1dc;--ok:#1f7a45;--warn:#a15c00;
--bad:#b3261e;--info:#2f5fb3;--chip:#efeee9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--card:#1d1d20;--ink:#ececef;
--muted:#9a9aa2;--line:#2e2e33;--ok:#58c287;--warn:#e0a34a;--bad:#ef7b72;--info:#86a8ea;--chip:#26262a}}
:root[data-theme="dark"]{--bg:#141416;--card:#1d1d20;--ink:#ececef;--muted:#9a9aa2;--line:#2e2e33;--ok:#58c287;
--warn:#e0a34a;--bad:#ef7b72;--info:#86a8ea;--chip:#26262a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:24px;margin:0 0 4px}
.sub{color:var(--muted);margin:0 0 20px}.summary{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:0 0 16px}
.head{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 12px;margin-bottom:12px}
.head h2{font-size:17px;margin:0}.muted{color:var(--muted);font-size:13px}
.chip{display:inline-block;background:var(--chip);border-radius:999px;padding:2px 10px;font-size:12.5px}
.a-set,.a-update{color:var(--ok)}.a-skip{color:var(--warn)}.a-planner{color:var(--info)}.a-in-sync{color:var(--muted)}
.flag{color:var(--bad);font-weight:600}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media (max-width:720px){.pair{grid-template-columns:1fr}}
figure{margin:0}figcaption{font-size:12.5px;color:var(--muted);margin-top:4px}
.frame{position:relative;aspect-ratio:16/9;background:var(--chip);border-radius:8px;overflow:hidden}
.frame img{width:100%;height:100%;object-fit:cover;display:block}
.frame.cur img{object-fit:contain}
.frame .c70{position:absolute;inset:15%;border:1.5px dashed rgba(255,214,0,.9);pointer-events:none}
.empty{display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);font-size:13px}
details{margin-top:10px}summary{cursor:pointer;color:var(--muted);font-size:13px}
details img{max-width:100%;border-radius:6px;margin-top:8px}
"""


def build_sheet(out: Path) -> Path:
    reps = [json.loads(p.read_text()) for p in sorted((out / "clients").glob("*.json"))]
    order = {"set": 0, "update": 1, "skip": 2, "planner": 3, "in-sync": 4}
    reps.sort(key=lambda r: (order.get(r.get("action"), 9), r.get("slug")))
    summary = []
    for r in reps:
        hero, cur, crop, rev = r.get("hero") or {}, r.get("current_cover") or {}, r.get("crop") or {}, r.get("hero_review") or {}
        summary.append({
            "slug": r["slug"], "brand": r.get("brand"), "company_id": r.get("company_id"),
            "action": r.get("action"), "reason": r.get("reason"),
            "gbp_verified": (r.get("gbp") or {}).get("verified"), "gbp_location": (r.get("gbp") or {}).get("location"),
            "current_cover": {k: cur.get(k) for k in ("who", "detail", "create_time", "size", "photo_like", "media_name")},
            "hero": {k: hero.get(k) for k in ("key", "sha1", "width", "height", "ai_generated", "provenance", "site_url")},
            "hero_review": rev or None,
            "crop": {k: crop.get(k) for k in ("box", "out", "window", "upscaled", "subject_in_center70",
                                              "subject_centroid", "center70_share", "energy_kept", "reason")} if crop else None,
            "real_alternative": r.get("real_alternative"),
            "images": {k: r.get(k) for k in ("current_img", "proposed_img", "cropmap_img", "proposed_full")},
        })
    (out / "covers.json").write_text(json.dumps({"generated_at": sm.iso(), "clients": summary}, indent=1))
    counts: dict[str, int] = {}
    for s in summary:
        counts[s["action"]] = counts.get(s["action"], 0) + 1
    e = html.escape
    cards = []
    for s in summary:
        cur, hero, crop, rev, im = s["current_cover"], s["hero"], s["crop"] or {}, s["hero_review"] or {}, s["images"]
        flags = []
        if rev.get("status") == "ai-branding":
            flags.append(("Looks like a REAL photo (manifest says AI); branding: " if rev.get("origin") == "real"
                          else "AI hero shows invented branding/lettering: ")
                         + "; ".join(rev.get("problems") or rev.get("texts") or []))
        elif rev.get("status") == "ai-brand-ok":
            flags.append("AI hero renders the brand (spelled right): " + ", ".join(rev.get("texts") or []))
        if crop and crop.get("subject_in_center70") is False:
            flags.append("subject centroid outside the central 70%")
        if crop and crop.get("upscaled"):
            flags.append("upscaled source")
        cur_fig = (f'<div class="frame cur"><img loading="lazy" src="{e(im["current_img"])}" alt="current cover"></div>'
                   if im.get("current_img") else '<div class="frame"><div class="empty">no cover</div></div>')
        prop_fig = (f'<div class="frame"><img loading="lazy" src="{e(im["proposed_img"])}" alt="proposed cover">'
                    '<div class="c70" title="central 70%: what Google keeps on tighter crops"></div></div>'
                    if im.get("proposed_img") else f'<div class="frame"><div class="empty">{e(str(crop.get("reason") or "no proposal"))}</div></div>')
        ai = "AI" if hero.get("ai_generated") else "real photo"
        alt = s.get("real_alternative")
        cards.append(f"""<section class="card"><div class="head"><h2>{e(s.get('brand') or s['slug'])}</h2>
<span class="chip a-{e(str(s['action']))}">{e(str(s['action']).upper())}</span>
<span class="muted">{e(str(s.get('reason')))}</span></div>
<div class="pair"><figure>{cur_fig}<figcaption>Current: {e(str(cur.get('who')))} &middot; {e(str(cur.get('create_time') or '')[:10])} {e(str(cur.get('size') or ''))}</figcaption></figure>
<figure>{prop_fig}<figcaption>Proposed: site hero ({ai}) {e(str(hero.get('width')))}x{e(str(hero.get('height')))}
{('&rarr; ' + e(str(crop['out'][0])) + 'x' + e(str(crop['out'][1]))) if crop.get('out') else ''}</figcaption></figure></div>
{''.join(f'<p class="flag">{e(f)}</p>' for f in flags)}
{f'<p class="muted">Real alternative: {e(str(alt.get("subject")))} ({e(alt["size"])}, hero score {alt["hero_score"]})</p>' if alt else ''}
{f'<details><summary>Crop map (white = chosen 16:9 window, yellow = central 70%, blue = detected subject)</summary><img loading="lazy" src="{e(im["cropmap_img"])}" alt="crop map"></details>' if im.get('cropmap_img') else ''}
</section>""")
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>GBP Cover Proposals</title>
<style>{SHEET_CSS}</style></head><body><main>
<h1>GBP cover from site hero</h1>
<p class="sub">Current Google cover vs the proposed smart-cropped site hero (exact 16:9). The dashed box is the central 70%
that survives Google's tighter crops. Survey {e(sm.iso())}. Nothing has been written to any Google profile.</p>
<div class="summary">{''.join(f'<span class="chip a-{e(k)}">{e(k)}: {v}</span>' for k, v in sorted(counts.items()))}</div>
{''.join(cards)}
</main></body></html>"""
    (out / "index.html").write_text(doc)
    return out / "index.html"


# --------------------------------------------------------------------------- #
def roster() -> list[str]:
    return [s for s in sm.list_due() if s not in DEAD]


def main() -> int:
    ap = argparse.ArgumentParser(description="GBP cover from the site hero (per client)")
    ap.add_argument("cmd", choices=["survey", "preview", "apply", "run", "sheet", "list-due"])
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true", help="local convenience loop (CI runs one process per client)")
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "gbp-covers"))
    ap.add_argument("--apply", action="store_true", help="allow the write (still needs env GBP_COVER_SYNC_WRITE=1)")
    ap.add_argument("--replace-owner-cover", action="store_true",
                    help="replace an owner-uploaded (or app-picked) real-photo cover too")
    ap.add_argument("--allow-ai-branding", action="store_true",
                    help="allow an AI hero the vision check flagged for invented branding/lettering")
    args = ap.parse_args()
    out = Path(args.out)
    if args.cmd == "list-due":
        print(json.dumps(roster()))
        return 0
    if args.cmd == "sheet":
        print(build_sheet(out))
        return 0
    slugs = roster() if args.all else [args.slug] if args.slug else []
    if not slugs:
        ap.error("--slug (or --all for survey/preview)")
    if args.cmd in ("apply", "run") and args.all:
        ap.error("apply/run is per client: --slug only (LAW 09-19)")
    for slug in slugs:
        if slug in DEAD:
            print(f"  [{slug}] skip: dead client")
            continue
        try:
            if args.cmd == "survey":
                r = survey_one(slug)
                _persist_survey(r)
                cur, hero, rev = r.get("current_cover") or {}, r.get("hero") or {}, r.get("hero_review") or {}
                print(f"  [{slug}] cover={cur.get('who')} {cur.get('create_time', '')} | hero "
                      f"{'AI' if hero.get('ai_generated') else 'real'} {hero.get('width')}x{hero.get('height')} "
                      f"review={rev.get('status')} {rev.get('texts') or ''} | {r.get('action')}: {r.get('reason')}")
            elif args.cmd == "preview":
                r = preview_one(slug, out)
                print(f"  [{slug}] {r.get('action')}: {r.get('reason')}")
            else:
                print(apply_one(slug, args.apply, args.replace_owner_cover, args.allow_ai_branding,
                                out if args.cmd == "apply" else None))
        except Exception as e:  # noqa: BLE001 -- fail-open per client
            print(f"  [{slug}] ERROR (non-fatal): {type(e).__name__}: {str(e)[:200]}")
    if args.cmd == "preview" and args.all:
        print(build_sheet(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
