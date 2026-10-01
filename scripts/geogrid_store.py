#!/usr/bin/env python3
"""
Rank AI — Geo-grid production store (Supabase + R2).

Takes a finished scan (one keyword × one city, an N×N grid of ranked points),
renders a static PNG, uploads it to the client's R2 bucket, and writes the
canonical rows the APP reads:

    marketing_geogrid_scans   (one row per company × keyword × city × run)
    marketing_geogrid_points  (one row per grid point: grid_row/grid_col/rank)

Schema is owned by the app developer (migration 20260618160200_add_geogrid_tables.sql):
  - company_id is TEXT (FK companies.id)
  - points use grid_row / grid_col (NOT row/col)
  - authenticated = SELECT only; we write with the SERVICE ROLE key (bypasses RLS)
  - scans are NEVER overwritten — every run inserts a new row (that history IS the
    before/after Compare feature).

R2 upload uses the Cloudflare REST API (bearer token) directly — NOT `npx wrangler` —
so it runs in a python-only Railway container with no node toolchain.

Library:
    from geogrid_store import scan_and_store, persist_scan, resolve_client
    row = scan_and_store(sb, slug="narestco", keyword="water damage restoration",
                         city={"label": "Tacoma, WA", "lat": 47.2529, "lng": -122.4443})

CLI (one keyword+city, the same path /geogrid/scan uses):
    python3 scripts/geogrid_store.py --slug narestco \
        --keyword "water damage restoration" --city "Tacoma, WA:47.2529,-122.4443"
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
load_dotenv(ROOT / ".env")

import geogrid_scan as gs          # noqa: E402  (build_grid, rank_at_point, load_center, load_dfs_creds)
from geogrid_render import render_png  # noqa: E402

# company_id (TEXT, = companies.id) per slug.
# Single source of truth: clients/company_map.json (fail-soft on missing file).
try:
    COMPANY_MAP = json.loads((ROOT / "clients" / "company_map.json").read_text())
except Exception:
    COMPANY_MAP = {}

CF_API = "https://api.cloudflare.com/client/v4"
# Shared public bucket for clients whose per-client bucket doesn't exist yet
# (created pre-onboarding, 2026-07-26). 2026-08-21: served via the custom
# domain geogrid.restorationai.io — the managed r2.dev URL stays enabled as
# the bucket's fallback, but r2.dev is rate-limited, not-for-production,
# and Santino's LAN DNS poisons it (resolved to a bogus non-Cloudflare IP,
# so every map image looked broken from his network).
FALLBACK_BUCKET = "rankai-geogrid"
FALLBACK_PUBLIC_URL = "https://geogrid.restorationai.io"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _kw_slug(keyword: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-")


def sb_client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


# ---------------------------------------------------------------------------
# Client metadata (company_id + R2 target) from the client record
# ---------------------------------------------------------------------------

def resolve_client(slug: str) -> dict:
    """Return {company_id, domain, bucket, public_url} for a slug, or raise."""
    company_id = COMPANY_MAP.get(slug)
    if not company_id:
        raise ValueError(f"No company_id mapping for slug '{slug}'. Add it to COMPANY_MAP.")
    rec_path = ROOT / "clients" / f"{slug}.json"
    if not rec_path.exists():
        raise FileNotFoundError(f"{rec_path} not found")
    rec = json.loads(rec_path.read_text())
    # `or {}`, NOT get("r2", {}) — the default only fires when the key is
    # ABSENT, and pre-onboarding records carry an explicit "r2": null. That
    # returned None and blew up on .get() BEFORE a single point was scanned,
    # so the whole client failed with "'NoneType' object has no attribute
    # 'get'" and $0 spent — indistinguishable, from the dashboard, from a
    # client nobody had configured yet (FireDEX / The Restoration Group / AAA,
    # 2026-08-04). The R2 fallback bucket below already handles a missing
    # bucket fine; there was never a reason to require the block.
    r2 = rec.get("r2") or {}
    domain = rec.get("domain")
    return {
        "company_id":  company_id,
        "domain":      domain,
        "bucket":      r2.get("bucket") or f"rankai-{slug}",
        "public_url":  (r2.get("public_url") or f"https://images.{domain}").rstrip("/"),
    }


# ---------------------------------------------------------------------------
# R2 upload via Cloudflare REST API (bearer token, no node/wrangler needed)
# ---------------------------------------------------------------------------

_HOST_OK: dict[str, bool] = {}


def _host_resolves(url: str) -> bool:
    """Does this URL's host actually resolve? Cached per process.

    Fail-OPEN on anything other than a clean NXDOMAIN-style failure would be
    wrong here (we'd keep writing dead URLs), but a resolver hiccup shouldn't
    demote a healthy client's images to the shared bucket forever either —
    hence the per-run cache rather than a persisted verdict."""
    import socket
    from urllib.parse import urlparse
    host = urlparse(url).netloc.split(":")[0]
    if not host:
        return False
    if host not in _HOST_OK:
        try:
            socket.gethostbyname(host)
            _HOST_OK[host] = True
        except OSError:
            _HOST_OK[host] = False
    return _HOST_OK[host]


def r2_put(bucket: str, key: str, data: bytes, content_type: str = "image/png") -> bool:
    """PUT an object into an R2 bucket via the Cloudflare REST API.

    Uses CLOUDFLARE_R2_API_TOKEN (R2:Edit). Falls back to CLOUDFLARE_API_TOKEN.
    Returns True on success. Best-effort: a failed upload should not lose the scan.
    """
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    token = os.environ.get("CLOUDFLARE_R2_API_TOKEN") or os.environ.get("CLOUDFLARE_API_TOKEN")
    if not account or not token:
        sys.stderr.write("  R2: missing CLOUDFLARE_ACCOUNT_ID / token — skipping upload\n")
        return False
    url = f"{CF_API}/accounts/{account}/r2/buckets/{bucket}/objects/{key}"
    try:
        r = requests.put(
            url, data=data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
            timeout=60,
        )
        if r.status_code not in (200, 201):
            sys.stderr.write(f"  R2 put {key} failed: {r.status_code} {r.text[:200]}\n")
            return False
        return True
    except Exception as e:
        sys.stderr.write(f"  R2 put {key} error: {str(e)[:200]}\n")
        return False


# ---------------------------------------------------------------------------
# Image: render + upload, verified by a real GET-able URL
# ---------------------------------------------------------------------------

def _url_serves(url: str) -> bool:
    try:
        r = requests.head(url, timeout=20, allow_redirects=True)
        return r.status_code == 200 and "image" in r.headers.get("content-type", "")
    except Exception:  # noqa: BLE001
        return False


def upload_image(points: list[dict], key: str, bucket: str, public_url: str) -> str | None:
    """Render the grid PNG and return a URL that ACTUALLY SERVES it.

    A 200 PUT is not a working image: images.{domain} can resolve yet not be
    bound to the bucket, or not resolve at all before the site cuts over
    (ProRestoration 08-04). The per-client URL is used only after a HEAD
    proves it serves; otherwise the shared bucket on our own domain takes it.
    Returns None only when every upload failed (the app then draws the grid
    from the stored points)."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        render_png(points, tmp_path)
        data = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
    if _host_resolves(public_url) and r2_put(bucket, key, data, "image/png"):
        url = f"{public_url}/{key}"
        if _url_serves(url):
            return url
        sys.stderr.write(f"  image: {url} does not serve after upload; using shared bucket\n")
    if r2_put(FALLBACK_BUCKET, key, data, "image/png"):
        url = f"{FALLBACK_PUBLIC_URL}/{key}"
        if _url_serves(url):
            return url
        sys.stderr.write(f"  image: shared-bucket URL {url} does not serve\n")
    return None


# ---------------------------------------------------------------------------
# Persist: render+upload PNG -> insert scan (with image_url) -> insert points
# ---------------------------------------------------------------------------

def persist_scan(
    sb,
    *,
    slug: str,
    company_id: str,
    keyword: str,
    city_label: str,
    center_lat: float,
    center_lng: float,
    grid_size: int,
    miles: float,
    zoom: int,
    points: list[dict],
    avg_rank: float | None,
    pct_in_top3: float,
    found_points: int,
    total_points: int,
    cost_usd: float,
    public_url: str,
    bucket: str,
    scanned_at: str | None = None,
    render: bool = True,
) -> dict:
    """Write one scan + its points. Returns the inserted scan row (incl. id, image_url).

    ORDER MATTERS (10-01): the row used to be inserted first and patched with
    image_url afterwards, then points inserted last. A run killed in between
    (the 330-min fleet timeout did exactly that) left rows with no image and
    no points, i.e. a permanently blank map in the app. Now the scan id is
    minted here, the image is uploaded BEFORE the row exists, and a row whose
    points fail to insert is deleted again."""
    import uuid
    scan_id = str(uuid.uuid4())
    grid_spacing_mi = round(miles / (grid_size - 1), 4) if grid_size > 1 else miles
    image_url = None
    if render:
        try:
            image_url = upload_image(points, f"geogrid/{_kw_slug(keyword)}/{scan_id}.png",
                                     bucket, public_url)
        except Exception as e:  # noqa: BLE001 — the points still render in-app
            sys.stderr.write(f"  render/upload failed (scan {scan_id} still stored): {str(e)[:200]}\n")
    scan_row = {
        "id":              scan_id,
        "company_id":      company_id,
        "keyword":         " ".join(keyword.split()),
        # labels are compared trimmed everywhere; store them that way
        # ('Santa Maria ' and 'Santa Maria' were two cities in the app)
        "city_label":      " ".join(str(city_label).split()),
        "center_lat":      center_lat,
        "center_lng":      center_lng,
        "grid_size":       grid_size,
        "grid_spacing_mi": grid_spacing_mi,
        "miles":           miles,
        "zoom":            zoom,
        "avg_rank":        round(avg_rank, 2) if avg_rank is not None else None,
        "pct_in_top3":     round(pct_in_top3, 1),
        "found_points":    found_points,
        "total_points":    total_points,
        "cost_usd":        round(cost_usd, 4),
        "image_url":       image_url,
        "scanned_at":      scanned_at or _now_iso(),
    }
    scan = sb.table("marketing_geogrid_scans").insert(scan_row).execute().data[0]

    # Points — grid_row / grid_col per the app's migration.
    point_rows = [{
        "scan_id":  scan_id,
        "grid_row": p["row"],
        "grid_col": p["col"],
        "lat":      p["lat"],
        "lng":      p["lng"],
        "rank":     p.get("rank"),
        "found":    bool(p.get("found")),
    } for p in points]
    try:
        for i in range(0, len(point_rows), 200):
            sb.table("marketing_geogrid_points").insert(point_rows[i:i + 200]).execute()
    except Exception:
        # a scan without its points is a blank map forever; take it back out
        try:
            sb.table("marketing_geogrid_scans").delete().eq("id", scan_id).execute()
        except Exception:  # noqa: BLE001
            pass
        raise
    return scan


# ---------------------------------------------------------------------------
# Scan -> verify -> persist. scan_many_and_store is the unit of work for the
# per-client cron job (all of a client's grids in flight at once);
# scan_and_store is the single-grid path POST /geogrid/scan uses.
# ---------------------------------------------------------------------------

def _biz_inside(biz: dict, city: dict, miles: float) -> bool:
    """Is the business's own location inside this grid? Only then is
    'not found at a single point' implausible; a satellite city 20 miles
    away can truthfully read 0/169."""
    import math
    half = miles / 2.0
    dlat = abs(biz["lat"] - city["lat"]) * gs.MILES_PER_DEG_LAT
    dlng = abs(biz["lng"] - city["lng"]) * gs.MILES_PER_DEG_LAT * math.cos(math.radians(city["lat"]))
    return dlat <= half and dlng <= half


def _review_count(sb, company_id: str) -> int:
    try:
        rows = sb.table("marketing_gbp_profiles").select("review_count") \
            .eq("company_id", company_id).limit(1).execute().data or []
        return int((rows[0] if rows else {}).get("review_count") or 0)
    except Exception:  # noqa: BLE001
        return 0


def _finalize(sb, slug, meta, biz, auth, keyword, city, miles, pts, results,
              grid, zoom, max_rank, workers, render, review_count) -> dict:
    # A point whose DataForSEO call ERRORED (or whose task never completed)
    # bills $0 and returns found=False — a failed call, NOT "not ranking here".
    # Retry those once live.
    def _errored(r):
        return (not r["found"]) and (r.get("cost") or 0.0) == 0.0

    err_idx = [k for k, r in enumerate(results) if _errored(r)]
    if err_idx:
        time.sleep(2)
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(gs.rank_at_point, auth, keyword, pts[k], biz, zoom, max_rank): k
                    for k in err_idx}
            for fut in cf.as_completed(futs):
                results[futs[fut]] = fut.result()

    # Still mostly errored = unreliable. Raise instead of persisting an
    # all-red grid that looks identical to a real ranking collapse.
    errored_final = sum(1 for r in results if _errored(r))
    if errored_final > 0.4 * len(pts):
        raise RuntimeError(
            f"unreliable scan: {errored_final}/{len(pts)} points errored ($0 cost) for "
            f"'{keyword}' @ {city['label']} — likely DataForSEO rate-limit/credit/auth; not writing")

    found = [r for r in results if r["found"]]
    # IMPLAUSIBLE-ZERO GUARD (BIONIC 2026-10-01): a listing with real reviews
    # that is "not found" at EVERY point of a grid that contains the business
    # itself is a matching/centering bug, not a ranking. 10-01 refinement:
    # only when the business sits inside the grid; satellite cities can be
    # genuinely empty and must still be written.
    if not found and len(pts) >= 25 and review_count >= 10 and _biz_inside(biz, city, miles):
        raise RuntimeError(
            f"implausible scan: 0/{len(pts)} found for '{keyword}' @ {city['label']} "
            f"but the listing has {review_count} reviews and sits inside the grid; check "
            "place_id/name match and the grid center; not writing")
    cost = sum(r["cost"] for r in results)
    avg = (sum(r["rank"] for r in found) / len(found)) if found else None
    top3 = (100.0 * sum(1 for r in found if r["rank"] <= 3) / len(pts)) if pts else 0.0
    return persist_scan(
        sb, slug=slug, company_id=meta["company_id"], keyword=keyword,
        city_label=city["label"], center_lat=city["lat"], center_lng=city["lng"],
        grid_size=grid, miles=miles, zoom=zoom, points=results, avg_rank=avg,
        pct_in_top3=top3, found_points=len(found), total_points=len(pts),
        cost_usd=cost, public_url=meta["public_url"], bucket=meta["bucket"],
        render=render)


def scan_many_and_store(
    sb,
    slug: str,
    combos: list[dict],
    grid: int = 13,
    zoom: int = 12,
    max_rank: int = 20,
    workers: int = 16,
    render: bool = True,
    on_result=None,
) -> list[dict]:
    """Scan many (keyword, city, miles) grids for ONE client concurrently and
    persist each that passes verification.

    combos: [{"keyword": str, "city": {"label","lat","lng"}, "miles": float}]
    Returns [{"combo", "row" | None, "error" | None}] in combo order;
    on_result(outcome) fires as each one is stored/refused."""
    meta = resolve_client(slug)
    u, p = gs.load_dfs_creds()
    auth = base64.b64encode(f"{u}:{p}".encode()).decode()
    biz = gs.load_center(slug)
    rc = _review_count(sb, meta["company_id"])
    jobs = [{"id": i, "keyword": c["keyword"],
             "pts": gs.build_grid(c["city"]["lat"], c["city"]["lng"], grid, float(c["miles"]))}
            for i, c in enumerate(combos)]

    if os.environ.get("GEOGRID_LIVE"):
        raw = {j["id"]: [None] * len(j["pts"]) for j in jobs}
        for j in jobs:
            with cf.ThreadPoolExecutor(max_workers=workers) as ex:
                futs = {ex.submit(gs.rank_at_point, auth, j["keyword"], pt, biz, zoom, max_rank): k
                        for k, pt in enumerate(j["pts"])}
                for fut in cf.as_completed(futs):
                    raw[j["id"]][futs[fut]] = fut.result()
    else:
        try:
            raw = gs.scan_many_tasked(auth, jobs, biz, zoom, max_rank,
                                      log=lambda m: print(m, flush=True))
        except Exception as e:  # noqa: BLE001 — every point retries live below
            sys.stderr.write(f"  task-mode failed ({str(e)[:120]}); every point "
                             "will be retried live\n")
            raw = {j["id"]: [{**pt, "rank": None, "found": False, "cost": 0.0}
                             for pt in j["pts"]] for j in jobs}

    out = []
    for j, c in zip(jobs, combos):
        res = {"combo": c, "row": None, "error": None}
        try:
            res["row"] = _finalize(sb, slug, meta, biz, auth, c["keyword"], c["city"],
                                   float(c["miles"]), j["pts"], raw[j["id"]], grid, zoom,
                                   max_rank, workers, render, rc)
        except Exception as e:  # noqa: BLE001 — one bad grid never sinks the rest
            res["error"] = str(e)
        out.append(res)
        if on_result:
            on_result(res)
    return out


def scan_and_store(
    sb,
    slug: str,
    keyword: str,
    city: dict,
    grid: int = 13,
    miles: float = 6.5,
    zoom: int = 12,
    max_rank: int = 20,
    workers: int = 16,
    render: bool = True,
) -> dict:
    """Run one geo-grid scan for one keyword+city, store it, return the scan
    row (raises when the scan is refused). `city` = {"label","lat","lng"}."""
    r = scan_many_and_store(sb, slug, [{"keyword": keyword, "city": city, "miles": miles}],
                            grid=grid, zoom=zoom, max_rank=max_rank, workers=workers,
                            render=render)[0]
    if r["error"]:
        raise RuntimeError(r["error"])
    return r["row"]

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_city(s: str) -> dict:
    # "Tacoma, WA:47.2529,-122.4443"
    label, coords = s.rsplit(":", 1)
    lat, lng = coords.split(",")
    return {"label": label.strip(), "lat": float(lat), "lng": float(lng)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan one keyword+city and store to Supabase + R2")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--city", required=True, help='"Label:lat,lng" e.g. "Tacoma, WA:47.2529,-122.4443"')
    ap.add_argument("--grid", type=int, default=13)
    ap.add_argument("--miles", type=float, default=6.5)
    ap.add_argument("--zoom", type=int, default=12)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--no-render", action="store_true", help="Skip PNG render + R2 upload")
    args = ap.parse_args()

    sb = sb_client()
    city = _parse_city(args.city)
    print(f"==> scan+store: {args.slug} | '{args.keyword}' @ {city['label']} | {args.grid}x{args.grid} z{args.zoom}")
    row = scan_and_store(sb, args.slug, args.keyword, city,
                         grid=args.grid, miles=args.miles, zoom=args.zoom,
                         workers=args.workers, render=not args.no_render)
    print(f"    scan_id:    {row['id']}")
    print(f"    avg_rank:   {row.get('avg_rank')}  |  top3: {row.get('pct_in_top3')}%  "
          f"|  found {row.get('found_points')}/{row.get('total_points')}")
    print(f"    cost_usd:   ${row.get('cost_usd')}")
    print(f"    image_url:  {row.get('image_url')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
