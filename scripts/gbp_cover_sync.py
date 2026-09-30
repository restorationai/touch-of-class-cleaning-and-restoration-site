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
  preview  Survey + build the proposed cover (see build_cover) and write
           current / proposed / crop-map images + a per-client JSON under --out;
           `sheet` assembles covers.json + index.html. Never writes anywhere.
  apply    Build + upload the cover for ONE client (--slug). Dry run unless
           --apply AND env GBP_COVER_SYNC_WRITE=1. The final JPG is hosted in
           Supabase storage (branding/{cid}/site-assets/gbp-cover/...) and
           created via sourceUrl (the path that works for COVER everywhere
           tested); the v4 bytes flow is the fallback. The COVER is read back
           afterwards (newest COVER must be ours). Logged to
           marketing_gbp_changes (actor 'cover-sync', the Reports tab) and
           ops_kv 'gbp-cover-sync/{cid}' (anchor = site hero sha1, applied_at,
           media name, source, QA) so the same hero never goes up twice; a NEW
           hero sha1 re-applies (with the same crop + QA).
  run      the same as apply (the nightly unit).
  variant  Register (--file) or generate (--generate, Gemini edit of the
           hero with the client's REAL logo; --mode clean strips all lettering)
           a COVER-ONLY variant for a hero whose AI lettering is garbled. It is
           QA'd, stored in Supabase storage and bound to today's hero sha1 in
           the ledger; build_cover prefers it while the hero is unchanged.
  sheet    Assemble covers.json + index.html from the per-client JSONs in --out.

COVER BUILD (build_cover, 2026-09-30 after Santino's review: "crop it to make
sure the vans are fitting within the image"):
  sources  in order: a registered cover-only variant for today's hero; the
           site hero (unless its AI lettering is garbled / invented); the
           client's best REAL branded photo (photo_harvest hero score >= 80).
  crop     fit_crop: a vision pass (detect_subjects, Claude) returns boxes for
           every vehicle, logo / lettering block, person and sign. The 16:9
           window must contain their UNION plus a margin, sits on the
           subjects' centre, and is only as tight as keeps the main subject in
           the central 70% (a preference, never at the cost of a cut). When no
           16:9 window of the source holds the union, the canvas is PADDED
           with a blurred, darkened fill of the photo instead of cutting.
           Exact 16:9: 1920x1080 when the window is >= 1920 px wide, else
           1280x720. Energy smart_crop is only the fallback when vision is down
           (and such a cover cannot pass QA, so it is never written).
  QA       qa_cover: a vision check of the FINAL image (with the real logo as
           a reference): nothing cut by the frame, no garbled / invented text,
           no phone number or URL that is not the client's, the right brand.
           Anything that fails QA is HELD, never written.

POLICY (Santino 2026-09-30: "The only one I think we should skip would be Crew
Restoration"):
  set      no cover, our own older cover, OR any owner / app-picked cover
           (replaced) -- except KEEP_OWNER_COVER (Crew: their real team photo)
  update   our cover-sync cover whose anchor differs from today's site hero
  keep     Crew; or the owner changed the cover AFTER our apply (kept until the
           site hero changes)
  planner  unverified or no-access profile: the cover is built, QA'd and
           stored as ledger 'prepared' (goes up at verification / access)
  held     no source passed QA (reason recorded)

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
  python3 scripts/gbp_cover_sync.py variant --slug diss-restoration --generate --apply
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
import time
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
CENTER_BAND = 0.70           # Google crops the cover further on mobile/desktop (a preference only)
VISION_MODEL = os.environ.get("GBP_COVER_VISION_MODEL") or os.environ.get("PHOTO_TRIAGE_MODEL", "claude-sonnet-5")
# box localisation + the final QA need the stronger reader (09-30 test: sonnet's
# logo boxes drifted by a logo-width on Reign; opus boxes were tight)
DETECT_MODEL = os.environ.get("GBP_COVER_DETECT_MODEL", "claude-opus-5-5")
QA_MODEL = os.environ.get("GBP_COVER_QA_MODEL", "claude-opus-5-5")
GEMINI_MODEL = os.environ.get("GBP_COVER_GEMINI_MODEL", "gemini-3-pro-image-preview")   # Nano Banana Pro
KEEP_OWNER_COVER = {"crew-restoration-construction"}   # Santino 09-30: their real team/fleet photo stays
ALT_MIN_SCORE = 80           # photo_harvest hero score for a REAL photo to stand in for the hero
KEEP_KINDS = ("vehicle", "logo", "text", "person", "sign")
MARGIN = 0.035               # around the subject union, per axis, of the source size
DETECT_V, QA_V, BUILD_V = 1, 4, 3
CACHE_KEEP = 8


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


# --------------------------------------------------------------------------- #
# SUBJECT-FIT CROP (2026-09-30): the window must hold every branded subject
# --------------------------------------------------------------------------- #
def _out_tier(window_w: float) -> tuple[int, int]:
    return next(((ow, oh) for ow, oh in OUT_TIERS if window_w >= ow), OUT_TIERS[-1])


def _union(boxes: list[list[float]]) -> list[float]:
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _place(size: float, src: float, lo: float, hi: float, centre: float) -> float:
    """Window start on one axis: contain [lo, hi], stay inside the source when
    the window is smaller than it (else cover the whole source: padding), and
    sit as close to `centre` as those allow."""
    if size >= src:
        a_min, a_max = src - size, 0.0
    else:
        a_min, a_max = max(0.0, hi - size), min(src - size, lo)
        if a_min > a_max:                       # cannot happen when size >= the union; be safe
            a_min = a_max = min(max(0.0, (lo + hi - size) / 2), src - size)
    return min(max(centre - size / 2, a_min), a_max)


def fit_crop(W: int, H: int, subjects: list[dict]) -> dict | None:
    """Exact-16:9 window that CONTAINS every key subject (union of the vehicle /
    logo / lettering / person / sign boxes + MARGIN), centred on the subjects
    (65% union centre, 35% main-subject centre). Size: the largest of the
    union need, the main subject inside the central 70% (preference), and a
    zoom floor (85% of the full window, never below the output tier), capped
    at the full 16:9 window. When the union needs more than the source's full
    16:9 window, the window grows past the source and the canvas is PADDED.
    None when there are no subjects (caller falls back to smart_crop)."""
    keep = [s for s in subjects if s.get("kind") in KEEP_KINDS and s.get("box")]
    if not keep:
        return None
    target = 16 / 9
    fw = min(W, H * target)
    fh = fw / target
    if fw < MIN_W or fh < MIN_H:
        return {"ok": False, "reason": f"too small for a cover: best 16:9 window {int(fw)}x{int(fh)} < {MIN_W}x{MIN_H}"}
    raw = _union([s["box"] for s in keep])
    ux0, uy0 = max(0.0, raw[0] - MARGIN * W), max(0.0, raw[1] - MARGIN * H)
    ux1, uy1 = min(float(W), raw[2] + MARGIN * W), min(float(H), raw[3] + MARGIN * H)
    uw, uh = ux1 - ux0, uy1 - uy0
    need_w = max(uw, uh * target)
    raw_need = max(raw[2] - raw[0], (raw[3] - raw[1]) * target)
    if need_w > fw and raw_need <= fw:          # the margin is best effort: drop it rather than pad
        need_w = fw
        ux0, uy0, ux1, uy1 = raw
    vehicles = [s for s in keep if s["kind"] == "vehicle"]
    main = next((s for s in keep if s.get("main")), None) or max(
        vehicles or keep, key=lambda s: (s["box"][2] - s["box"][0]) * (s["box"][3] - s["box"][1]))
    mb = main["box"]
    pref_w = max((mb[2] - mb[0]) / CENTER_BAND, (mb[3] - mb[1]) / CENTER_BAND * target)
    tier_w = _out_tier(fw)[0]
    floor_w = max(0.85 * fw, tier_w if fw >= tier_w else fw)
    pad = need_w > fw + 1
    ww = need_w if pad else min(fw, max(need_w, pref_w, floor_w))
    wh = ww / target
    cx = 0.65 * (ux0 + ux1) / 2 + 0.35 * (mb[0] + mb[2]) / 2
    cy = 0.65 * (uy0 + uy1) / 2 + 0.35 * (mb[1] + mb[3]) / 2
    x0 = _place(ww, W, ux0, ux1, cx)
    y0 = _place(wh, H, uy0, uy1, cy)
    box = (int(round(x0)), int(round(y0)), int(round(x0 + ww)), int(round(y0 + wh)))
    used_w = min(ww, W)                          # real source pixels across the output
    out_w, out_h = _out_tier(used_w)
    lo, hi = (1 - CENTER_BAND) / 2, 1 - (1 - CENTER_BAND) / 2
    in70 = (lo <= (mb[0] - x0) / ww and (mb[2] - x0) / ww <= hi and lo <= (mb[1] - y0) / wh and (mb[3] - y0) / wh <= hi)
    contained = box[0] <= raw[0] + 1 and box[1] <= raw[1] + 1 and box[2] >= raw[2] - 1 and box[3] >= raw[3] - 1
    return {
        "ok": True, "method": "subjects", "box": box, "out": [out_w, out_h], "source": [W, H],
        "window": [box[2] - box[0], box[3] - box[1]], "pad": pad,
        "pad_px": [max(0, -box[0]) + max(0, box[2] - W), max(0, -box[1]) + max(0, box[3] - H)] if pad else [0, 0],
        "upscaled": used_w < out_w, "union": [int(v) for v in raw], "main": main.get("label"),
        "main_box": [int(v) for v in mb], "main_in_center70": in70, "subjects_contained": contained,
        "subjects": [{"label": s.get("label"), "kind": s["kind"], "box": [int(v) for v in s["box"]]} for s in keep],
    }


def render_cover(im: Image.Image, crop: dict) -> bytes:
    """Crop (or, for a padded window, compose the photo over a blurred,
    darkened fill of itself) and resize to the exact output tier."""
    ow, oh = crop["out"]
    rgb = im.convert("RGB")
    W, H = rgb.size
    x0, y0, x1, y1 = crop["box"]
    if x0 >= 0 and y0 >= 0 and x1 <= W and y1 <= H:
        out = rgb.crop((x0, y0, x1, y1)).resize((ow, oh), Image.LANCZOS)
    else:
        s = ow / (x1 - x0)
        fill_scale = max(ow / W, oh / H)
        bg = rgb.resize((max(1, round(W * fill_scale)), max(1, round(H * fill_scale))), Image.LANCZOS)
        bx, by = (bg.width - ow) // 2, (bg.height - oh) // 2
        bg = bg.crop((bx, by, bx + ow, by + oh)).filter(ImageFilter.GaussianBlur(max(8, ow // 45)))
        bg = Image.blend(bg, Image.new("RGB", bg.size, (0, 0, 0)), 0.28)
        fg = rgb.resize((max(1, round(W * s)), max(1, round(H * s))), Image.LANCZOS)
        feather = max(6, ow // 160)
        fl, ft = (feather if x0 < 0 else -feather * 3), (feather if y0 < 0 else -feather * 3)
        fr, fb = (feather if x1 > W else -feather * 3), (feather if y1 > H else -feather * 3)
        mask = Image.new("L", fg.size, 0)
        ImageDraw.Draw(mask).rectangle((fl, ft, fg.width - 1 - fr, fg.height - 1 - fb), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(feather / 2))
        bg.paste(fg, (round(-x0 * s), round(-y0 * s)), mask)
        out = bg
    assert out.size == (ow, oh) and abs(ow / oh - 16 / 9) < 1e-6
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=90, optimize=True, progressive=True)
    return buf.getvalue()


def crop_map(im: Image.Image, crop: dict, width: int = 720) -> Image.Image:
    """The source (on a grey canvas when the window pads past it) with the
    chosen 16:9 window (white), its central 70% (yellow, a preference only),
    each detected subject (green vehicles, magenta lettering/logos, orange
    people/signs) and their union (cyan)."""
    rgb = im.convert("RGB")
    W, H = rgb.size
    x0, y0, x1, y1 = crop["box"]
    cx0, cy0, cx1, cy1 = min(0, x0), min(0, y0), max(W, x1), max(H, y1)
    s = width / (cx1 - cx0)
    canvas = Image.new("RGB", (width, max(1, round((cy1 - cy0) * s))), (90, 90, 96))
    canvas.paste(rgb.resize((round(W * s), round(H * s)), Image.LANCZOS), (round(-cx0 * s), round(-cy0 * s)))
    shade = Image.new("RGB", canvas.size, (0, 0, 0))
    mask = Image.new("L", canvas.size, 110)

    def P(v: list | tuple) -> list[int]:
        return [round((v[0] - cx0) * s), round((v[1] - cy0) * s), round((v[2] - cx0) * s), round((v[3] - cy0) * s)]
    wb = P(crop["box"])
    ImageDraw.Draw(mask).rectangle(wb, fill=0)
    view = Image.composite(shade, canvas, mask)
    d = ImageDraw.Draw(view)
    ww, wh = wb[2] - wb[0], wb[3] - wb[1]
    bx0, by0, bx1, by1 = wb[0] + ww * 0.15, wb[1] + wh * 0.15, wb[0] + ww * 0.85, wb[1] + wh * 0.85
    for i in range(int(bx0), int(bx1), 12):
        d.line((i, by0, min(i + 6, bx1), by0), fill=(255, 214, 0), width=1)
        d.line((i, by1, min(i + 6, bx1), by1), fill=(255, 214, 0), width=1)
    for i in range(int(by0), int(by1), 12):
        d.line((bx0, i, bx0, min(i + 6, by1)), fill=(255, 214, 0), width=1)
        d.line((bx1, i, bx1, min(i + 6, by1)), fill=(255, 214, 0), width=1)
    colors = {"vehicle": (60, 220, 90), "logo": (255, 60, 220), "text": (255, 60, 220)}
    for sub in crop.get("subjects") or []:
        d.rectangle(P(sub["box"]), outline=colors.get(sub["kind"], (255, 150, 40)), width=2)
    if crop.get("union"):
        d.rectangle(P(crop["union"]), outline=(0, 200, 255), width=1)
    elif crop.get("subject_box"):
        d.rectangle(P(crop["subject_box"]), outline=(0, 200, 255), width=1)
    d.rectangle((wb[0], wb[1], wb[2] - 1, wb[3] - 1), outline=(255, 255, 255), width=3)
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


def _jpeg_part(img: bytes | Image.Image, max_side: int = 1400) -> dict:
    im = img if isinstance(img, Image.Image) else Image.open(io.BytesIO(img))
    im = im.convert("RGB")
    if max(im.size) > max_side:
        im = im.copy()
        im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.b64encode(buf.getvalue()).decode()}}


def _vision_json(img: bytes | Image.Image, prompt: str, max_tokens: int = 600, model: str | None = None,
                 extra: list | None = None, max_side: int = 1400) -> dict:
    """One Claude vision call -> the JSON object in its reply. `extra` images
    (e.g. the client's real logo) follow the main one."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("no ANTHROPIC_API_KEY")
    content = [_jpeg_part(img, max_side)] + [_jpeg_part(x, 800) for x in (extra or []) if x]
    last: Exception | None = None
    for attempt in range(3):                     # a 429/5xx or a reply without JSON gets two retries
        try:
            r = requests.post("https://api.anthropic.com/v1/messages", timeout=150, headers={
                "x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": model or VISION_MODEL, "max_tokens": max_tokens, "messages": [{"role": "user",
                      "content": [*content, {"type": "text", "text": prompt}]}]})
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}")
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json().get("content", []))
            return json.loads(text[text.find("{"):text.rfind("}") + 1])
        except (RuntimeError, ValueError, requests.ConnectionError, requests.Timeout) as e:
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"vision failed after retries: {last}")


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


def real_alternatives(slug: str, n: int = 3) -> list[dict]:
    """The best REAL landscape photos photo_harvest scored for the hero slot."""
    p = ROOT / "clients" / slug / "photo-manifest.json"
    try:
        assets = (json.loads(p.read_text()) if p.exists() else {}).get("assets") or {}
    except json.JSONDecodeError:
        return []
    out = []
    for a in assets.values():
        sc = ((a.get("slots") or {}).get("hero") or 0)
        w, h = a.get("width") or 0, a.get("height") or 0
        if sc >= 60 and w > h and w >= 960 and not a.get("flags") and a.get("url"):
            out.append({"url": a.get("url"), "subject": a.get("subject"), "hero_score": sc, "size": f"{w}x{h}",
                        "sha1": a.get("sha1")})
    out.sort(key=lambda x: -x["hero_score"])
    return out[:n]


def real_alternative(slug: str) -> dict | None:
    alts = real_alternatives(slug, 1)
    return alts[0] if alts else None


REVIEW_VERSION = 4


def vision_review(hero: dict, cached: dict | None, facts: dict, logo: bytes | None = None) -> dict:
    """Heroes the manifest calls AI: one vision pass per hero sha1 (cached in
    the ledger) for readable text/branding, judged against the client's real
    name / phone / domain and (v3, 09-30) the real logo as a reference, plus a
    second opinion on whether it is a real photograph (narestco's hero
    predates photo_harvest, so the manifest calls a real crew photo AI).
    Verdicts:
      ai-clean     no readable text
      ai-brand-ok  only the real name (or a clean shortening), the logo's own
                   wording, the real phone (vanity letters that map to it are
                   fine) or domain, generic service words, correctly spelled
                   claims -- all spelled right
      ai-branding  garbled / misspelled lettering, pseudo-logos, a phone / URL
                   that is not the client's, another business's name
    Fail-open to 'unreviewed' (the hero is then not used as a cover)."""
    if not hero.get("ai_generated"):
        return {"sha1": hero["sha1"], "status": "real-photo", "v": REVIEW_VERSION}
    if cached and cached.get("sha1") == hero["sha1"] and cached.get("v") == REVIEW_VERSION \
            and cached.get("status") not in (None, "unreviewed"):
        return cached
    phones = ", ".join(facts.get("phones") or []) or "unknown"
    prompt = (
        "The FIRST image is about to become the Google Business Profile cover photo for a real company."
        + (" The SECOND image is the company's real logo; its wording (name, tagline) is real." if logo else "")
        + f"\nReal business name: {facts.get('name')!r}. Real phone(s): {phones}. "
        f"Real website: {facts.get('domain') or 'unknown'!r}.\n"
        "1) List EVERY readable string in the FIRST image (vehicle wraps, uniforms, signs, logos, phone numbers, URLs).\n"
        "2) verdict: 'clean' if there is no readable text; 'brand-ok' if every string is the real business name or a "
        "clean shortening of it, the logo's own wording, the real phone (a vanity number whose letters map to it on a "
        "phone keypad is the real phone), the real website, generic service words, or correctly spelled slogans / "
        "claims; otherwise 'fake' (misspelled or garbled lettering anywhere, pseudo-letters, an illegible pseudo-logo, "
        "a phone number or URL that is not the real one, another business's name). Tiny unreadable blur far away "
        "is not a problem; readable wrong letters are.\n"
        "3) origin: 'real' if this is clearly a genuine photograph of real people/vehicles/places, 'ai' if it looks "
        "AI-generated or rendered, 'unsure' otherwise.\n"
        'Reply ONLY with JSON: {"texts": [...], "verdict": "clean|brand-ok|fake", "problems": [short strings], '
        '"claims": [correctly spelled slogans/claims], "origin": "real|ai|unsure", "note": "one sentence"}')
    try:
        j = _vision_json(Path(hero["path"]).read_bytes(), prompt, max_tokens=900, model=QA_MODEL,
                         extra=[logo] if logo else None)
    except Exception as e:  # noqa: BLE001
        return {"sha1": hero["sha1"], "status": "unreviewed", "note": f"vision failed: {str(e)[:80]}",
                "v": REVIEW_VERSION}
    verdict = str(j.get("verdict") or "").lower()
    status = {"clean": "ai-clean", "brand-ok": "ai-brand-ok"}.get(verdict, "ai-branding")
    return {"sha1": hero["sha1"], "status": status, "texts": [str(t) for t in (j.get("texts") or [])][:10],
            "problems": [str(t) for t in (j.get("problems") or [])][:6],
            "claims": [str(t) for t in (j.get("claims") or [])][:4], "origin": j.get("origin"),
            "note": str(j.get("note") or "")[:220], "model": QA_MODEL, "at": sm.iso(), "v": REVIEW_VERSION}


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
    rep["facts"] = client_facts(slug, pi, brand, domain)
    if hero.get("ok"):
        rep["hero_review"] = vision_review(hero, ledger.get("hero_review"), rep["facts"], client_logo(slug))
    rep["anchor"] = hero["sha1"] if hero.get("ok") else "no-hero"
    rep["real_alternatives"] = real_alternatives(slug)
    rep["real_alternative"] = (rep["real_alternatives"] or [None])[0]

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
    rep["facts"]["gbp_title"] = (loc or {}).get("title")
    rep.update(decide(rep, ledger))
    return rep


def client_facts(slug: str, pi: dict, brand: str, domain: str) -> dict:
    """What the QA judges text against: the real name, every real phone we
    publish (plan-input + the site's brand.ts: phone / tracking numbers) and
    the domain."""
    phones = [(pi.get("brand") or {}).get("phone")]
    bt = ROOT / "sites" / slug / "src" / "lib" / "brand.ts"
    if bt.exists():
        phones += re.findall(r'\b(?:phone|trackingPhone|adsTrackingPhone|gbpTrackingPhone)\s*:\s*"([^"]+)"',
                             bt.read_text(errors="replace"))
    seen, uniq = set(), []
    for p in phones:
        d = re.sub(r"\D", "", p or "")[-10:]
        if len(d) == 10 and d not in seen:
            seen.add(d)
            uniq.append(f"({d[:3]}) {d[3:6]}-{d[6:]}")
    return {"name": brand, "phones": uniq, "domain": domain}


def decide(rep: dict, ledger: dict) -> dict:
    """What the PROFILE needs (build_cover then decides whether a cover that
    passes QA exists). Policy 2026-09-30 (Santino): replace every cover except
    Crew's; an owner who changes the cover after our apply is respected until
    the site hero changes."""
    hero, cur, g = rep.get("hero") or {}, rep.get("current_cover") or {}, rep.get("gbp") or {}
    slug, anchor = rep.get("slug"), rep.get("anchor")
    if slug in KEEP_OWNER_COVER:
        return {"action": "keep", "reason": "Santino 09-30: keep the owner's own cover (their real team/fleet photo)"}
    variant = ledger.get("variant") or {}
    if not hero.get("ok") and not rep.get("real_alternative") and variant.get("anchor") != anchor:
        return {"action": "skip", "reason": f"{hero.get('reason', 'no hero')} and no real branded photo to use"}
    if not g.get("location"):
        return {"action": "planner", "reason": f"goes up at access: no GBP location we can reach ({g.get('detail')})"}
    if not g.get("verified"):
        return {"action": "planner", "reason": "goes up at verification (unverified profile)"}
    if cur.get("who") == "unknown":
        return {"action": "skip", "reason": f"cover unreadable: {cur.get('detail')}"}
    last = (ledger.get("applied") or [{}])[-1]
    if cur.get("who") == "cover-sync" and (cur.get("hero_sha1") or last.get("hero_sha1")) == anchor:
        return {"action": "in-sync", "reason": "cover already is today's hero cover"}
    who = cur.get("who")
    ct, at = _ts(cur.get("create_time")), _ts(last.get("applied_at"))
    if who in ("owner", "app-picked") and last.get("hero_sha1") == anchor and ct and at and ct > at:
        return {"action": "keep", "reason": f"the owner changed the cover after our {last.get('applied_at', '')[:10]} "
                                            "apply; kept until the site hero changes"}
    if who == "none":
        return {"action": "set", "reason": "no cover yet"}
    if who == "cover-sync":
        return {"action": "update", "reason": "site hero changed since our last cover"}
    if who == "ours-site-asset":
        return {"action": "set", "reason": "replace our earlier site-asset cover with the fitted cover"}
    if who in ("owner", "app-picked"):
        kind = "graphic" if cur.get("photo_like") is False else "photo"
        return {"action": "set", "reason": f"replace the {who} cover ({kind}); policy 09-30: only Crew keeps its own"}
    return {"action": "skip", "reason": f"unhandled cover state {who}"}


# --------------------------------------------------------------------------- #
# subject detection + QA (Claude vision), cached per image sha1 in the ledger
# --------------------------------------------------------------------------- #
def _sha(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()[:16]


def _cache_get(ledger: dict, key: str, sha: str, v: int) -> dict | None:
    hit = (ledger.get(key) or {}).get(sha)
    return hit if hit and hit.get("v") == v else None


def _cache_put(ledger: dict, key: str, sha: str, val: dict) -> None:
    c = dict(ledger.get(key) or {})
    c.pop(sha, None)
    c[sha] = val
    ledger[key] = dict(list(c.items())[-CACHE_KEEP:])


def detect_subjects(data: bytes, ledger: dict) -> dict:
    """Bounding boxes (source pixels) of every vehicle, logo / lettering block,
    person and sign: what a cover must show in full."""
    sha = _sha(data)
    hit = _cache_get(ledger, "detect_cache", sha, DETECT_V)
    if hit:
        return hit
    im = Image.open(io.BytesIO(data)).convert("RGB")
    W, H = im.size
    s = 1000 / max(W, H)
    view = im.resize((max(1, round(W * s)), max(1, round(H * s))), Image.LANCZOS)
    prompt = (
        f"This image is {view.width}x{view.height} pixels. It will be cropped into a Google Business Profile "
        "cover photo, and the crop must show every KEY SUBJECT in full. List each one with a TIGHT bounding box "
        "in pixel coordinates of this image (x0,y0 = top-left, x1,y1 = bottom-right):\n"
        "- every vehicle (van, truck, trailer), boxed to its full visible extent including bumpers and wheels\n"
        "- every logo and every block of lettering (vehicle wraps, signs, uniforms, equipment), phone numbers included\n"
        "- every person\n- every sign\n"
        "Skip background houses, trees, sky, road and generic equipment unless it carries branding. "
        "Mark main=true on the single most important branded subject (usually the nearest branded vehicle).\n"
        'Reply ONLY with JSON: {"subjects": [{"label": "...", "kind": "vehicle|logo|text|person|sign", '
        '"box": [x0, y0, x1, y1], "main": false}]}')
    j = _vision_json(view, prompt, max_tokens=1800, model=DETECT_MODEL, max_side=1000)
    subs = []
    for sub in j.get("subjects") or []:
        b = sub.get("box") or []
        if len(b) != 4:
            continue
        x0, y0, x1, y1 = [float(v) / s for v in b]
        x0, x1 = sorted((max(0.0, min(W, x0)), max(0.0, min(W, x1))))
        y0, y1 = sorted((max(0.0, min(H, y0)), max(0.0, min(H, y1))))
        if x1 - x0 < 4 or y1 - y0 < 4:
            continue
        kind = str(sub.get("kind") or "").lower()
        subs.append({"label": str(sub.get("label") or kind)[:80], "kind": kind if kind in KEEP_KINDS else "other",
                     "box": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)], "main": bool(sub.get("main"))})
    val = {"v": DETECT_V, "sha1": sha, "size": [W, H], "subjects": subs, "model": DETECT_MODEL, "at": sm.iso()}
    _cache_put(ledger, "detect_cache", sha, val)
    return val


def client_logo(slug: str) -> bytes | None:
    d = ROOT / "sites" / slug / "public" / "images"
    for name in ("logo.png", "logo-light-bg.png", "logo.webp", "logo-dark-bg.png"):
        p = d / name
        if p.exists():
            try:
                im = Image.open(p).convert("RGBA")
                bg = Image.new("RGBA", im.size, (255, 255, 255, 255) if "dark" not in name else (20, 20, 20, 255))
                bg.alpha_composite(im)
                buf = io.BytesIO()
                bg.convert("RGB").save(buf, "PNG")
                return buf.getvalue()
            except Exception:  # noqa: BLE001
                continue
    return None


def qa_cover(jpg: bytes, facts: dict, logo: bytes | None, ledger: dict, origin: str = "ai") -> dict:
    """Vision QA of the FINAL cover. pass = nothing cut by the frame, no
    garbled / invented text, no phone or URL that is not the client's, the
    right brand, no broken image. `origin` 'real' (a genuine photo of the
    client's own vehicles) relaxes only the license-number rule: lettering
    painted on a real truck is real, but a phone number that is not ours still
    fails (09-30: never a wrong number on a cover). Cached per output sha1."""
    sha = _sha(jpg)
    hit = _cache_get(ledger, "qa_cache", sha, QA_V)
    if hit:
        return hit
    phones = ", ".join(facts.get("phones") or []) or "unknown"
    kind = ("a genuine photograph of the company's own vehicles/work (lettering painted on their real vehicles is "
            "real; judge spelling only where you can read it clearly)" if origin == "real"
            else "an AI-generated scene (lettering in it may be invented or garbled)")
    prompt = (
        f"The FIRST image is about to become the Google Business Profile COVER photo of a real company. It is {kind}. "
        + ("The SECOND image is that company's real logo; any wording in it (name, tagline) is real. " if logo else "")
        + f"\nCompany: {facts.get('name')!r} (Google listing name: {facts.get('gbp_title') or facts.get('name')!r}). "
        f"Real phone number(s): {phones}. Real website: {facts.get('domain') or 'unknown'!r}.\n"
        "Check the FIRST image strictly:\n"
        "1. CUT: is any service vehicle (van, truck, trailer; branded or not), any logo or block of lettering, or a "
        "person's head/face sliced by the image FRAME (left/right/top/bottom edge)? Lettering or a logo running past "
        "the edge = cut. A service vehicle whose body is sliced through by the frame = cut. NOT cut: a vehicle partly "
        "hidden BEHIND another vehicle in the scene; ordinary passenger cars parked in the background; a person "
        "framed from the waist or thighs up. Only a "
        "sliver of bumper/tail past the edge with every letter and logo fully visible = minor_cut, not cut.\n"
        "2. TEXT: list every readable string. text_problems = misspelled or garbled lettering, pseudo-letters, "
        + ("invented or garbled license numbers, " if origin != "real" else "")
        + "a phone number that is not one of the real numbers (a vanity number whose letters map to a real number "
        "on a phone keypad is fine), a website that is not the real one (a national franchise brand's own site is "
        "fine), another company's name. The real name, a clean shortening of it, the logo's own wording and generic "
        "service words (Water, Fire, Mold, Storm, Restoration, Plumbing, 24/7, Emergency Service) are fine. "
        "Correctly spelled slogans or claims (e.g. 'Veteran Owned', 'Licensed & Insured') go in unverified_claims, "
        "NOT text_problems. Background signs that are not the company's: only a problem if readable and garbled. "
        "Tiny unreadable blur at a distance is not a problem; readable wrong letters are.\n"
        "3. BRAND: if branding is visible, is it this company's (matches the name / the logo)? Do not judge the "
        "wrap design, colours or number of vehicles.\n"
        "4. QUALITY: a broken result (heavy artifacts, warped vehicles, visible seams or borders, a screenshot, a "
        "text-only graphic, collage)?\n"
        'Reply ONLY with JSON: {"cut": [], "minor_cut": [], "texts": [], "text_problems": [], "unverified_claims": [], '
        '"wrong_phone": false, "brand_ok": true, "quality_problems": [], "note": "one sentence"} '
        "(brand_ok null when no branding is visible).")
    try:
        j = _vision_json(jpg, prompt, max_tokens=1200, model=QA_MODEL, extra=[logo] if logo else None)
    except Exception as e:  # noqa: BLE001
        return {"v": QA_V, "sha1": sha, "pass": False, "problems": [f"QA unavailable: {str(e)[:100]}"],
                "at": sm.iso(), "uncached": True}
    L = lambda k: [str(x) for x in (j.get(k) or []) if str(x).strip()]  # noqa: E731
    problems = [f"cut: {x}" for x in L("cut")] + [f"text: {x}" for x in L("text_problems")] \
        + [f"quality: {x}" for x in L("quality_problems")]
    if j.get("wrong_phone") is True:
        problems.append("a phone number on the image is not the client's")
    if j.get("brand_ok") is False:
        problems.append("branding does not match the client")
    val = {"v": QA_V, "sha1": sha, "pass": not problems, "problems": problems[:8], "texts": L("texts")[:12],
           "minor_cut": L("minor_cut")[:4], "unverified_claims": L("unverified_claims")[:4],
           "note": str(j.get("note") or "")[:240], "origin": origin, "model": QA_MODEL, "at": sm.iso()}
    _cache_put(ledger, "qa_cache", sha, val)
    return val


# --------------------------------------------------------------------------- #
# build: pick the source, fit, render, QA
# --------------------------------------------------------------------------- #
def _fetch(url: str) -> bytes:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def cover_sources(rep: dict, ledger: dict) -> tuple[list[dict], list[str]]:
    """Ordered candidates + why others were left out."""
    hero, review = rep.get("hero") or {}, rep.get("hero_review") or {}
    out, notes = [], []
    variant = ledger.get("variant") or {}
    if variant.get("anchor") == rep.get("anchor") and variant.get("url"):
        out.append({"kind": "variant", "label": f"cover-only variant ({variant.get('mode')})", "url": variant["url"],
                    "origin": variant.get("origin") or "ai"})
    if hero.get("ok"):
        if hero.get("ai_generated") and review.get("status") == "ai-branding":
            notes.append("site hero: AI lettering is garbled/invented ("
                         + "; ".join(review.get("problems") or review.get("texts") or [])[:160] + ")")
        elif hero.get("ai_generated") and review.get("status") == "unreviewed":
            notes.append(f"site hero: branding review unavailable ({review.get('note')})")
        else:
            out.append({"kind": "hero", "label": "site hero (" + ("AI" if hero.get("ai_generated") else "real photo")
                        + ")", "path": hero.get("path"), "origin": "ai" if hero.get("ai_generated") else "real"})
    for alt in rep.get("real_alternatives") or []:
        if (alt.get("hero_score") or 0) >= ALT_MIN_SCORE:
            out.append({"kind": "real-photo", "origin": "real", "url": alt["url"],
                        "label": f"real photo: {alt.get('subject')} (score {alt.get('hero_score')})"})
        else:
            notes.append(f"real photo scored {alt.get('hero_score')} < {ALT_MIN_SCORE} ({alt.get('subject')})")
    return out, notes


def build_cover(rep: dict, ledger: dict, slug: str) -> dict:
    """First source whose fitted cover passes QA. Returns {ok, jpg, crop,
    source, qa, attempts} or {ok: False, reason, attempts}."""
    srcs, notes = cover_sources(rep, ledger)
    facts, logo = rep.get("facts") or {}, client_logo(slug)
    attempts = [{"source": n, "result": "not used"} for n in notes]
    for src in srcs:
        try:
            data = Path(src["path"]).read_bytes() if src.get("path") else _fetch(src["url"])
            im = Image.open(io.BytesIO(data))
            im.load()
        except Exception as e:  # noqa: BLE001
            attempts.append({"source": src["label"], "result": f"unreadable: {str(e)[:80]}"})
            continue
        try:
            det = detect_subjects(data, ledger)
            crop = fit_crop(im.width, im.height, det["subjects"])
            method = "energy (no key subjects detected)"
        except Exception as e:  # noqa: BLE001
            crop, method = None, "vision-down"
            attempts.append({"source": src["label"], "result": f"subject detection unavailable: {str(e)[:80]}"})
        if crop is None:
            crop = {**smart_crop(im), "method": method}
        if not crop.get("ok"):
            attempts.append({"source": src["label"], "result": crop.get("reason")})
            continue
        jpg = render_cover(im, crop)
        if crop.get("method") == "vision-down":
            qa = {"pass": False, "problems": ["subject detection down: an unverified energy crop is never written"]}
        else:
            qa = qa_cover(jpg, facts, logo, ledger, src.get("origin") or "ai")
        attempts.append({"source": src["label"], "result": "pass" if qa.get("pass") else "; ".join(qa.get("problems") or [])})
        cand = {"ok": bool(qa.get("pass")), "jpg": jpg, "crop": crop, "source": src, "qa": qa,
                "source_img": im, "source_sha1": _sha(data), "out_sha1": _sha(jpg)}
        if qa.get("pass"):
            return {**cand, "attempts": attempts}
        rep.setdefault("_failed", []).append(cand)
    failed = rep.pop("_failed", [])
    why = "; ".join(f"{a['source']}: {a['result']}" for a in attempts) or "no usable source"
    return {"ok": False, "reason": why, "attempts": attempts, **({k: failed[0][k] for k in (
        "jpg", "crop", "source", "qa", "source_img", "source_sha1", "out_sha1")} if failed else {})}


# --------------------------------------------------------------------------- #
# process one client (preview = dry; apply/run = write when enabled)
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


def readback_cover(tok: str, acct: str, loc_name: str, name: str) -> dict:
    covers = [m for m in list_media(tok, acct, loc_name)
              if (m.get("locationAssociation") or {}).get("category") == "COVER"]
    covers.sort(key=lambda m: m.get("createTime", ""), reverse=True)
    top = covers[0] if covers else {}
    return {"ok": bool(top) and top.get("name") == name, "newest_cover": top.get("name"),
            "google_url": top.get("googleUrl"), "create_time": top.get("createTime"), "at": sm.iso()}


def process_one(slug: str, out: Path, write: bool) -> dict:
    """survey -> decide -> build (source, subject-fit crop, QA) -> write
    (when enabled) -> per-client JSON + images under `out`."""
    rep = survey_one(slug, want_current_bytes=True)
    cid = rep.get("company_id")
    img_dir, full_dir = out / "img", out / "full"
    img_dir.mkdir(parents=True, exist_ok=True)
    full_dir.mkdir(exist_ok=True)
    (out / "clients").mkdir(exist_ok=True)
    cur_bytes = rep.pop("_current_bytes", None)
    if cur_bytes:
        im = Image.open(io.BytesIO(cur_bytes)).convert("RGB")
        im.thumbnail((960, 960))
        im.save(img_dir / f"{slug}-current.jpg", "JPEG", quality=84)
        rep["current_img"] = f"img/{slug}-current.jpg"
    ledger = (sm.kv_get(LEDGER.format(cid=cid)) or {}) if cid else {}
    action = rep.get("action")
    built = None
    if cid and action in ("set", "update", "planner"):
        built = build_cover(rep, ledger, slug)
        if built.get("jpg"):
            crop, jpg = built["crop"], built["jpg"]
            full = f"full/{slug}-cover-{crop['out'][0]}x{crop['out'][1]}.jpg"
            (out / full).write_bytes(jpg)
            view = Image.open(io.BytesIO(jpg))
            view.thumbnail((960, 540))
            view.save(img_dir / f"{slug}-proposed.jpg", "JPEG", quality=86)
            crop_map(built["source_img"], crop).save(img_dir / f"{slug}-cropmap.jpg", "JPEG", quality=82)
            rep.update({"proposed_img": f"img/{slug}-proposed.jpg", "cropmap_img": f"img/{slug}-cropmap.jpg",
                        "proposed_full": full, "proposed_bytes": len(jpg)})
        rep["build"] = {k: built.get(k) for k in ("ok", "reason", "attempts", "qa", "source_sha1", "out_sha1")}
        rep["build"]["source"] = (built.get("source") or {}).get("label")
        rep["build"]["source_kind"] = (built.get("source") or {}).get("kind")
        rep["crop"] = {k: v for k, v in (built.get("crop") or {}).items() if k != "subjects"} | (
            {"n_subjects": len((built.get("crop") or {}).get("subjects") or [])})
    # ---- outcome ----
    if action == "keep":
        status, why = "kept", rep["reason"]
    elif action == "in-sync":
        status, why = "in-sync", rep["reason"]
    elif action == "skip":
        status, why = "skip", rep["reason"]
    elif action == "planner":
        status = "goes-at-verification" if "verification" in rep["reason"] else "goes-at-access"
        why = rep["reason"] + ("; prepared cover QA-passed" if built and built.get("ok")
                               else f"; no cover passes QA yet ({(built or {}).get('reason')})")
    elif not (built and built.get("ok")):
        status, why = "held", f"{rep['reason']}; HELD: {(built or {}).get('reason')}"
    else:
        status, why = ("applied" if write else "would-apply"), rep["reason"]
    rep["status"], rep["status_reason"] = status, why
    if write and cid and built and built.get("ok") and status in ("applied", "goes-at-verification", "goes-at-access"):
        try:
            _write(slug, cid, rep, built, ledger)
        except Exception as e:  # noqa: BLE001
            rep["status"], rep["status_reason"] = "failed", f"{rep['reason']}; write FAILED: {str(e)[:300]}"
    elif cid:
        led = sm.kv_get(LEDGER.format(cid=cid)) or {}
        for k in ("detect_cache", "qa_cache"):
            if ledger.get(k):
                led[k] = ledger[k]
        sm.kv_put(LEDGER.format(cid=cid), led)
    rep.get("hero", {}).pop("path", None)
    (out / "clients" / f"{slug}.json").write_text(json.dumps(rep, indent=1, default=str))
    _persist_survey(rep)
    return rep


def _write(slug: str, cid: str, rep: dict, built: dict, ledger: dict) -> None:
    """Upload the QA-passed cover to our storage; set it as the GBP COVER
    (verified profiles) or keep it as the prepared cover (unverified / no
    access); read the COVER back; ledger + change log."""
    crop, jpg, anchor = built["crop"], built["jpg"], rep["anchor"]
    prev = (sm.kv_get(LEDGER.format(cid=cid)) or {}).get("prepared") or {}
    if rep["status"] != "applied" and prev.get("out_sha1") == built["out_sha1"]:
        rep["prepared_url"] = prev.get("source_url")          # already stored; nothing new to write
        return
    path = (f"{cid}/site-assets/gbp-cover/cover-{anchor[:16]}-{built['out_sha1'][:10]}"
            f"-{crop['out'][0]}x{crop['out'][1]}.jpg")
    public = sm.storage_upload(path, jpg, "image/jpeg")
    rec = {"hero_sha1": anchor, "hero_key": (rep.get("hero") or {}).get("key"),
           "ai_generated": (rep.get("hero") or {}).get("ai_generated"), "source": built["source"]["label"],
           "source_kind": built["source"]["kind"], "source_sha1": built["source_sha1"], "out_sha1": built["out_sha1"],
           "source_url": public, "crop_box": crop["box"], "out": crop["out"], "pad": crop.get("pad"),
           "qa": {k: built["qa"].get(k) for k in ("pass", "texts", "minor_cut", "note", "model")}, "build_v": BUILD_V}
    led = sm.kv_get(LEDGER.format(cid=cid)) or {}
    for k in ("detect_cache", "qa_cache", "variant"):
        if ledger.get(k):
            led[k] = ledger[k]
    if rep["status"] != "applied":
        led["prepared"] = {**rec, "prepared_at": sm.iso(), "waiting_for": rep["status"]}
        sm.kv_put(LEDGER.format(cid=cid), led)
        rep["prepared_url"] = public
        return
    cur = rep.get("current_cover") or {}
    tok, acct, loc, _ = resolve_location(slug, cid)
    name, via = create_cover(tok, acct, loc["name"], public, jpg)
    rb = readback_cover(tok, acct, loc["name"], name)
    rec.update({"applied_at": sm.iso(), "media_name": name, "via": via, "replaced": cur.get("media_name"),
                "replaced_who": cur.get("who"), "readback": rb})
    led.setdefault("applied", []).append(rec)
    led.pop("prepared", None)
    sm.kv_put(LEDGER.format(cid=cid), led)
    src_note = {"hero": "the website hero", "real-photo": "a real photo of the team's branded work",
                "variant": "the website hero (cover edition)"}.get(built["source"]["kind"], "the website hero")
    gbp.log_change(cid, "profile_cover_photo",
                   f"Cover photo updated: {src_note}, fitted to 16:9 so every vehicle and logo shows in full",
                   actor=ACTOR, meta={"media_name": name, "photo_url": public, "hero_sha1": anchor, "via": via,
                                      "source": built["source"]["kind"], "replaced": cur.get("media_name"),
                                      "replaced_who": cur.get("who"), "readback_ok": rb.get("ok")})
    rep["applied"] = {"media_name": name, "via": via, "url": public, "readback": rb}
    if not rb.get("ok"):
        rep["status_reason"] += f"; READBACK: newest COVER is {rb.get('newest_cover')}, not {name}"


def summary_line(rep: dict, mode: str) -> str:
    b, c = rep.get("build") or {}, rep.get("crop") or {}
    crop = (f"; {b.get('source')} crop {c.get('window')}->{c.get('out')}{' PADDED' if c.get('pad') else ''}"
            f" main-in-70%={c.get('main_in_center70')}" if c.get("out") else "")
    extra = ""
    if rep.get("applied"):
        a = rep["applied"]
        extra = f"\n    COVER -> {a['media_name']} via {a['via']}; readback ok={a['readback'].get('ok')}"
    if rep.get("prepared_url"):
        extra = f"\n    prepared cover stored: {rep['prepared_url']}"
    return f"  [{rep['slug']}] {mode}: {rep.get('status', '').upper()}: {rep.get('status_reason')}{crop}{extra}"


# --------------------------------------------------------------------------- #
# cover-only variant (Gemini edit of the hero with the REAL logo)
# --------------------------------------------------------------------------- #
VARIANT_PROMPTS = {
    "logo": ("Edit the FIRST image, a photo of a restoration company's service vehicles. Keep the scene, camera "
             "angle, composition, lighting, vehicles, colours and background the same. Replace ALL lettering, logos "
             "and graphics on every vehicle with the company logo from the SECOND image, reproduced EXACTLY (same "
             "spelling, letters, colours and shapes), large and clean on the side of each vehicle, fully visible. "
             "The ONLY text allowed anywhere in the image is that logo exactly as shown. Remove every other text: no "
             "phone numbers, no websites, no slogans, no service lists, no license or certification claims, no "
             "readable signs in the background. Never invent, add or alter a single letter. Photorealistic."),
    # 09-30: the 'logo' edit garbles every logo with a small tagline (CRW, DISS, Dry County, FIX...);
    # the company NAME alone, large, is the one lettering the model reproduces reliably
    "name": ("Edit this photo of a restoration company's service vehicles. Keep the scene, camera angle, lighting "
             "and background the same. On every vehicle, replace ALL existing lettering, logos and graphics with ONLY "
             "the company name \"{name}\" in large, bold, clean, correctly spelled capital letters on the side "
             "panel, with strong contrast against the paint. No other text anywhere in the image: no tagline, no "
             "phone number, no website, no small print, no emblem, no rear-door lettering; license plates blank. "
             "Remove any vehicle that is only partly inside the frame (replace it with the background) so every "
             "remaining vehicle is complete. Photorealistic."),
    "clean": ("Edit this photo of service vehicles. Keep the scene, camera angle, composition, lighting and "
              "background the same. Remove ALL lettering, logos, numbers and graphics from every vehicle, sign and "
              "piece of clothing, leaving clean solid vehicle paint in the same colours. No text anywhere in the "
              "image. Photorealistic."),
    "nophone": ("Edit this photo. Remove ONLY the phone numbers (every telephone number painted on vehicles, signs or "
                "equipment), filling each spot seamlessly with the surrounding surface (vehicle paint, wrap "
                "background). Change nothing else: keep every logo, every other word, the vehicles, people, "
                "lighting, framing and background exactly as they are. Photorealistic."),
    "bgtext": ("Edit this photo. Remove ALL lettering from background buildings, storefront signs and street signs "
               "(anything that is NOT on the service vehicles), leaving plain surfaces. Keep the service vehicles, "
               "their logos and lettering, the people, lighting, framing and everything else exactly as they are. "
               "Photorealistic."),
    "reframe": ("Recompose this exact scene as a slightly wider shot so that EVERY vehicle is completely inside the "
                "frame, with clear space on both sides; nothing touches the image edges. Keep the vehicles, their "
                "exact wraps, logos and lettering, the setting, time of day and lighting identical. Never change, "
                "add or re-letter any text. Photorealistic."),
}


def cover_name(brand: str) -> str:
    """The name as it would ride on a van: legal suffixes off, upper case."""
    n = re.sub(r"[,\s]+(LLC|L\.L\.C\.|Inc\.?|INC\.?|Corp\.?|Co\.)\s*$", "", (brand or "").strip(), flags=re.I)
    return re.sub(r"\s+", " ", n).strip().upper()


def gemini_edit(src: bytes, logo: bytes | None, mode: str, aspect: str = "16:9", name: str = "") -> bytes:
    key = os.environ.get("GOOGLE_AI_API_KEY")
    if not key:
        raise RuntimeError("no GOOGLE_AI_API_KEY")
    parts: list = [{"text": VARIANT_PROMPTS[mode].replace("{name}", name)}]
    for b in ([src] + ([logo] if mode == "logo" and logo else [])):
        parts.append({"inline_data": {"mime_type": "image/jpeg" if b[:3] == b"\xff\xd8\xff" else "image/png",
                                      "data": base64.b64encode(b).decode()}})
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}",
                      timeout=300, json={"contents": [{"parts": parts}], "generationConfig": {
                          "responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}}})
    r.raise_for_status()
    for cand in r.json().get("candidates", []):
        for part in (cand.get("content") or {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise RuntimeError("Gemini returned no image")


def _aspect_for(w: int, h: int) -> str:
    opts = {"16:9": 16 / 9, "3:2": 1.5, "4:3": 4 / 3, "1:1": 1.0, "3:4": 0.75, "2:3": 2 / 3, "9:16": 9 / 16}
    return min(opts, key=lambda k: abs(opts[k] - w / h))


def variant_one(slug: str, file: str | None, generate: bool, mode: str, tries: int, write: bool,
                out: Path, source: str = "hero", name: str | None = None) -> str:
    """Make (or take) a cover-only variant, QA it as a finished cover, and
    (write) store + bind it to today's hero sha1 in the ledger. --source real
    edits the best real photo (mode nophone: strip a phone number that is not
    the client's from a real truck photo)."""
    cid = gbp.company_id_for(slug)
    if not cid:
        return f"  [{slug}] no company_id"
    rep = survey_one(slug)
    rep.pop("_current_bytes", None)
    ledger = sm.kv_get(LEDGER.format(cid=cid)) or {}
    logo = client_logo(slug)
    hero = rep.get("hero") or {}
    vdir = out / "variants"
    vdir.mkdir(parents=True, exist_ok=True)
    # a real photo with only a phone number / background signs removed is still a real photo
    real_src = source == "real" or not hero.get("ai_generated")
    origin = "real" if real_src and (file or mode in ("nophone", "bgtext")) else "ai"
    cands: list[tuple[str, bytes]] = []
    if file:
        cands.append((file, Path(file).read_bytes()))
    elif generate:
        if source == "real":
            alts = rep.get("real_alternatives") or []
            if not alts:
                return f"  [{slug}] no real photo to edit"
            src = _fetch(alts[0]["url"])
        else:
            if not hero.get("ok"):
                return f"  [{slug}] no site hero to edit"
            src = Path(hero["path"]).read_bytes()
        if mode == "logo" and not logo:
            return f"  [{slug}] no logo on disk for a logo variant (use --mode clean)"
        sim = Image.open(io.BytesIO(src))
        aspect = _aspect_for(*sim.size)
        for i in range(tries):
            try:
                cands.append((f"gemini-{mode}-{i + 1}", gemini_edit(src, logo, mode, aspect, name or cover_name(rep["facts"].get("name")))))
            except Exception as e:  # noqa: BLE001
                print(f"    gemini try {i + 1}: {str(e)[:120]}")
    lines = []
    for label, data in cands:
        im = Image.open(io.BytesIO(data))
        im.load()
        det = detect_subjects(data, ledger)
        crop = fit_crop(im.width, im.height, det["subjects"]) or {**smart_crop(im), "method": "energy"}
        if not crop.get("ok"):
            lines.append(f"    {label}: {crop.get('reason')}")
            continue
        jpg = render_cover(im, crop)
        qa = qa_cover(jpg, rep["facts"], logo, ledger, origin)
        sha = _sha(data)
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=92)
        (vdir / f"{slug}-{sha}.jpg").write_bytes(buf.getvalue())
        (vdir / f"{slug}-{sha}-cover.jpg").write_bytes(jpg)
        lines.append(f"    {label} {sha}: QA {'PASS' if qa.get('pass') else 'FAIL'} {qa.get('problems') or qa.get('texts')}"
                     f" -> {vdir / f'{slug}-{sha}-cover.jpg'}")
        if qa.get("pass"):
            if write:
                url = sm.storage_upload(f"{cid}/site-assets/gbp-cover/variant-{rep['anchor'][:16]}-{sha}.jpg",
                                        buf.getvalue(), "image/jpeg")
                ledger["variant"] = {"anchor": rep["anchor"], "url": url, "sha1": sha, "origin": origin,
                                     "mode": mode if generate else "file", "from": source, "label": label,
                                     "qa": {k: qa.get(k) for k in ("texts", "note")}, "at": sm.iso()}
                lines.append(f"    bound to hero {rep['anchor']}: {url}")
            break
    led = sm.kv_get(LEDGER.format(cid=cid)) or {}
    for k in ("detect_cache", "qa_cache", "variant"):
        if ledger.get(k):
            led[k] = ledger[k]
    sm.kv_put(LEDGER.format(cid=cid), led)
    return f"  [{slug}] variant ({'WRITE' if write else 'DRY'}):\n" + "\n".join(lines or ["    no candidates"])


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
        led["survey"] = {k: rep.get(k) for k in ("at", "action", "reason", "status", "status_reason", "gbp",
                                                 "current_cover", "crop", "build")}
        led["survey"]["hero"] = {k: v for k, v in (rep.get("hero") or {}).items() if k != "path"}
        sm.kv_put(LEDGER.format(cid=cid), led)
    except Exception as e:  # noqa: BLE001
        print(f"    ! ledger write failed: {str(e)[:100]}")


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
.head h2{font-size:17px;margin:0}.muted{color:var(--muted);font-size:13px}.reason{font-size:13.5px;margin:0 0 10px}
.chip{display:inline-block;background:var(--chip);border-radius:999px;padding:2px 10px;font-size:12.5px;font-weight:600}
.s-applied,.s-would-apply{color:var(--ok)}.s-held,.s-failed{color:var(--bad)}
.s-goes-at-verification,.s-goes-at-access{color:var(--info)}.s-kept,.s-in-sync,.s-skip{color:var(--muted)}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media (max-width:720px){.pair{grid-template-columns:1fr}}
figure{margin:0}figcaption{font-size:12.5px;color:var(--muted);margin-top:4px}
.frame{position:relative;aspect-ratio:16/9;background:var(--chip);border-radius:8px;overflow:hidden}
.frame img{width:100%;height:100%;object-fit:cover;display:block}
.frame.cur img{object-fit:contain}
.empty{display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);font-size:13px;
padding:12px;text-align:center}
details{margin-top:10px}summary{cursor:pointer;color:var(--muted);font-size:13px}
details img{max-width:100%;border-radius:6px;margin-top:8px}details ul{margin:6px 0 0;padding-left:18px;font-size:13px}
"""
STATUS_ORDER = ["applied", "would-apply", "failed", "held", "goes-at-verification", "goes-at-access",
                "kept", "in-sync", "skip"]
STATUS_LABEL = {"applied": "APPLIED", "would-apply": "WOULD APPLY", "failed": "FAILED", "held": "HELD",
                "goes-at-verification": "GOES UP AT VERIFICATION", "goes-at-access": "GOES UP AT ACCESS",
                "kept": "KEPT", "in-sync": "IN SYNC", "skip": "SKIPPED"}


def build_sheet(out: Path) -> Path:
    reps = [json.loads(p.read_text()) for p in sorted((out / "clients").glob("*.json"))]
    rank = {s: i for i, s in enumerate(STATUS_ORDER)}
    reps.sort(key=lambda r: (rank.get(r.get("status"), 99), r.get("brand") or r.get("slug")))
    summary = []
    for r in reps:
        hero, cur, crop, b = r.get("hero") or {}, r.get("current_cover") or {}, r.get("crop") or {}, r.get("build") or {}
        summary.append({
            "slug": r["slug"], "brand": r.get("brand"), "company_id": r.get("company_id"),
            "status": r.get("status"), "reason": r.get("status_reason"), "action": r.get("action"),
            "gbp_verified": (r.get("gbp") or {}).get("verified"), "gbp_location": (r.get("gbp") or {}).get("location"),
            "current_cover": {k: cur.get(k) for k in ("who", "detail", "create_time", "size", "photo_like", "media_name")},
            "hero": {k: hero.get(k) for k in ("key", "sha1", "width", "height", "ai_generated", "provenance")},
            "source": b.get("source"), "source_kind": b.get("source_kind"),
            "qa": b.get("qa"), "attempts": b.get("attempts"),
            "crop": {k: crop.get(k) for k in ("method", "box", "out", "window", "pad", "pad_px", "upscaled",
                                              "main", "main_in_center70", "subjects_contained", "n_subjects",
                                              "reason")} if crop else None,
            "applied": r.get("applied"), "prepared_url": r.get("prepared_url"),
            "images": {k: r.get(k) for k in ("current_img", "proposed_img", "cropmap_img", "proposed_full")},
        })
    (out / "covers.json").write_text(json.dumps({"generated_at": sm.iso(), "clients": summary}, indent=1))
    counts: dict[str, int] = {}
    for s in summary:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    e = html.escape
    cards = []
    for s in summary:
        cur, crop, im, qa = s["current_cover"], s["crop"] or {}, s["images"], s.get("qa") or {}
        st = str(s["status"])
        cur_fig = (f'<div class="frame cur"><img loading="lazy" src="{e(im["current_img"])}" alt="current cover"></div>'
                   if im.get("current_img") else '<div class="frame"><div class="empty">no cover on the profile</div></div>')
        new_label = "New cover" if st == "applied" else "Proposed cover"
        prop_fig = (f'<div class="frame"><img loading="lazy" src="{e(im["proposed_img"])}" alt="{new_label}"></div>'
                    if im.get("proposed_img") else
                    '<div class="frame"><div class="empty">'
                    + ("owner cover kept" if st == "kept" else "no proposal") + '</div></div>')
        cap = ""
        if crop.get("out"):
            cap = (f"{e(str(s.get('source') or ''))} &rarr; {crop['out'][0]}x{crop['out'][1]}"
                   + (" &middot; padded (subjects did not fit a 16:9 window)" if crop.get("pad") else "")
                   + (f" &middot; {crop.get('n_subjects')} subjects kept whole" if crop.get("n_subjects") else ""))
        qa_line = ""
        if qa:
            qa_line = (f'<p class="muted">QA {"passed" if qa.get("pass") else "FAILED"}'
                       + (f': {e("; ".join(qa.get("problems") or []))}' if qa.get("problems") else "")
                       + (f' &middot; text read: {e(", ".join(qa.get("texts") or []))}' if qa.get("texts") else "")
                       + "</p>")
        tries = s.get("attempts") or []
        tries_html = (f'<details><summary>Sources tried ({len(tries)})</summary><ul>'
                      + "".join(f"<li>{e(str(a.get('source')))}: {e(str(a.get('result')))}</li>" for a in tries)
                      + "</ul></details>") if tries else ""
        map_html = (f'<details><summary>Crop map (white = 16:9 window, green = vehicles, magenta = lettering/logos, '
                    f'cyan = union of subjects, faint yellow = central 70%)</summary>'
                    f'<img loading="lazy" src="{e(im["cropmap_img"])}" alt="crop map"></details>'
                    if im.get("cropmap_img") else "")
        cards.append(f"""<section class="card"><div class="head"><h2>{e(s.get('brand') or s['slug'])}</h2>
<span class="chip s-{e(st)}">{e(STATUS_LABEL.get(st, st.upper()))}</span></div>
<p class="reason">{e(str(s.get('reason') or ''))}</p>
<div class="pair"><figure>{cur_fig}<figcaption>{'Replaced' if st == 'applied' else 'Current'}: {e(str(cur.get('who')))}
&middot; {e(str(cur.get('create_time') or '')[:10])} {e(str(cur.get('size') or ''))}</figcaption></figure>
<figure>{prop_fig}<figcaption>{new_label}: {cap}</figcaption></figure></div>
{qa_line}{tries_html}{map_html}</section>""")
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>GBP Cover Rollout</title>
<style>{SHEET_CSS}</style></head><body><main>
<h1>GBP covers: current vs new</h1>
<p class="sub">Each cover is cropped around every detected vehicle, logo and lettering block (never cutting one;
padded when a 16:9 window can't hold them) and passes a vision QA (nothing cut, no garbled or wrong text, no
wrong phone number, right brand) before it goes up. Crew keeps its own cover. Run {e(sm.iso())}.</p>
<div class="summary">{''.join(f'<span class="chip s-{e(k)}">{e(STATUS_LABEL.get(k, k))}: {counts[k]}</span>'
                               for k in STATUS_ORDER if k in counts)}</div>
{''.join(cards)}
</main></body></html>"""
    (out / "index.html").write_text(doc)
    return out / "index.html"


# --------------------------------------------------------------------------- #
def roster() -> list[str]:
    return [s for s in sm.list_due() if s not in DEAD]


def main() -> int:
    ap = argparse.ArgumentParser(description="GBP cover from the site hero (per client)")
    ap.add_argument("cmd", choices=["survey", "preview", "apply", "run", "variant", "sheet", "list-due"])
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true", help="local convenience loop (CI runs one process per client)")
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "gbp-covers"))
    ap.add_argument("--apply", action="store_true", help="allow the write (still needs env GBP_COVER_SYNC_WRITE=1)")
    ap.add_argument("--file", help="variant: register this local image as the cover-only variant")
    ap.add_argument("--generate", action="store_true", help="variant: Gemini-edit the hero with the real logo")
    ap.add_argument("--mode", choices=list(VARIANT_PROMPTS), default="logo")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--source", choices=["hero", "real"], default="hero",
                    help="variant: edit the site hero (default) or the best real photo")
    ap.add_argument("--name", help="variant --mode name: the lettering (default: the brand name, suffixes off)")
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
    if args.cmd in ("apply", "run", "variant") and args.all:
        ap.error("apply/run/variant is per client: --slug only (LAW 09-19)")
    write = write_enabled(args.apply)
    for slug in slugs:
        if slug in DEAD:
            print(f"  [{slug}] skip: dead client")
            continue
        try:
            if args.cmd == "survey":
                r = survey_one(slug)
                r.pop("_current_bytes", None)
                _persist_survey(r)
                cur, hero, rev = r.get("current_cover") or {}, r.get("hero") or {}, r.get("hero_review") or {}
                print(f"  [{slug}] cover={cur.get('who')} {cur.get('create_time', '')} | hero "
                      f"{'AI' if hero.get('ai_generated') else 'real'} {hero.get('width')}x{hero.get('height')} "
                      f"review={rev.get('status')} {rev.get('texts') or ''} | {r.get('action')}: {r.get('reason')}")
            elif args.cmd == "variant":
                print(variant_one(slug, args.file, args.generate, args.mode, args.tries, write, out, args.source, args.name))
            else:
                w = write if args.cmd in ("apply", "run") else False
                mode = "WRITE" if w else ("DRY (GBP_COVER_SYNC_WRITE not set)" if args.apply else "DRY")
                print(summary_line(process_one(slug, out if args.cmd != "run" else
                                               Path(tempfile.mkdtemp(prefix="cover-sync-")), w), mode))
        except Exception as e:  # noqa: BLE001 -- fail-open per client
            print(f"  [{slug}] ERROR (non-fatal): {type(e).__name__}: {str(e)[:200]}")
    if args.cmd == "preview" and args.all:
        print(build_sheet(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
