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
# (created pre-onboarding, 2026-07-26; managed r2.dev domain enabled).
FALLBACK_BUCKET = "rankai-geogrid"
FALLBACK_PUBLIC_URL = "https://pub-1fc4fbd06484414192f087f3e6a5eca9.r2.dev"


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
    r2 = rec.get("r2", {})
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
# Persist: insert scan -> render+upload PNG -> patch image_url -> insert points
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
    """Write one scan + its points. Returns the inserted scan row (incl. id, image_url)."""
    grid_spacing_mi = round(miles / (grid_size - 1), 4) if grid_size > 1 else miles
    scan_row = {
        "company_id":      company_id,
        "keyword":         keyword,
        "city_label":      city_label,
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
        "scanned_at":      scanned_at or _now_iso(),
    }
    inserted = sb.table("marketing_geogrid_scans").insert(scan_row).execute()
    scan = inserted.data[0]
    scan_id = scan["id"]

    # Render PNG + upload to R2, keyed by scan_id, then patch image_url.
    # Fallback (Kyle/Crew3r 2026-07-26): the per-client bucket only exists
    # after full site onboarding, so day-one scans lost every image ("bucket
    # does not exist"). When the client bucket rejects the put, the shared
    # public bucket takes it — map images must exist from the first scan.
    image_url = None
    if render:
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            render_png(points, tmp_path)
            key = f"geogrid/{_kw_slug(keyword)}/{scan_id}.png"
            data = tmp_path.read_bytes()
            if r2_put(bucket, key, data, "image/png"):
                image_url = f"{public_url}/{key}"
            elif r2_put(FALLBACK_BUCKET, key, data, "image/png"):
                image_url = f"{FALLBACK_PUBLIC_URL}/{key}"
            if image_url:
                sb.table("marketing_geogrid_scans").update({"image_url": image_url}).eq("id", scan_id).execute()
                scan["image_url"] = image_url
            tmp_path.unlink(missing_ok=True)
        except Exception as e:
            sys.stderr.write(f"  render/upload failed (scan {scan_id} still stored): {str(e)[:200]}\n")

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
    for i in range(0, len(point_rows), 200):
        sb.table("marketing_geogrid_points").insert(point_rows[i:i + 200]).execute()

    return scan


# ---------------------------------------------------------------------------
# Scan one keyword × one city (DataForSEO) and persist — the unit of work for
# both the bi-weekly cron and the POST /geogrid/scan endpoint.
# ---------------------------------------------------------------------------

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
    """Run a live geo-grid scan for one keyword+city, store it, return the scan row.

    `city` = {"label": "...", "lat": .., "lng": ..}. Business identity (cid/place_id/
    name, used to match the listing) comes from the client's plan-input.json.
    """
    meta = resolve_client(slug)
    u, p = gs.load_dfs_creds()
    auth = base64.b64encode(f"{u}:{p}".encode()).decode()
    biz = gs.load_center(slug)

    pts = gs.build_grid(city["lat"], city["lng"], grid, miles)
    results = [None] * len(pts)

    def _run(indices):
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(gs.rank_at_point, auth, keyword, pts[k], biz, zoom, max_rank): k
                    for k in indices}
            for fut in cf.as_completed(futs):
                results[futs[fut]] = fut.result()

    _run(range(len(pts)))

    # A point whose DataForSEO call ERRORED bills $0 and returns found=False. A point
    # that simply didn't contain the listing still bills >$0. So $0-cost, not-found
    # points = failed calls (rate-limit / timeout / auth), NOT a genuine "not ranking
    # here". Retry those once — a transient blip shouldn't poison the scan.
    def _errored(r):
        return (not r["found"]) and (r.get("cost") or 0.0) == 0.0

    err_idx = [k for k, r in enumerate(results) if _errored(r)]
    if err_idx:
        time.sleep(2)
        _run(err_idx)

    # If a large share of points STILL errored, the scan is unreliable. Raise instead
    # of persisting — an all-error scan writes as an all-red / avg-0 grid that looks
    # identical to a real ranking collapse and misleads the dashboard. The cron catches
    # this per keyword, logs a FAIL, and leaves the last good scan in place.
    errored_final = sum(1 for r in results if _errored(r))
    if errored_final > 0.4 * len(pts):
        raise RuntimeError(
            f"unreliable scan: {errored_final}/{len(pts)} points errored ($0 cost) for "
            f"'{keyword}' @ {city['label']} — likely DataForSEO rate-limit/credit/auth; not writing"
        )

    found = [r for r in results if r["found"]]
    cost = sum(r["cost"] for r in results)
    avg = (sum(r["rank"] for r in found) / len(found)) if found else None
    top3 = (100.0 * sum(1 for r in found if r["rank"] <= 3) / len(pts)) if pts else 0.0

    return persist_scan(
        sb,
        slug=slug,
        company_id=meta["company_id"],
        keyword=keyword,
        city_label=city["label"],
        center_lat=city["lat"],
        center_lng=city["lng"],
        grid_size=grid,
        miles=miles,
        zoom=zoom,
        points=results,
        avg_rank=avg,
        pct_in_top3=top3,
        found_points=len(found),
        total_points=len(pts),
        cost_usd=cost,
        public_url=meta["public_url"],
        bucket=meta["bucket"],
        render=render,
    )


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
