#!/usr/bin/env python3
"""
Rank AI — Geo-grid local rank scanner (System: local map rankings).

For one client + one keyword, samples the client's Google Maps rank across an
N x N grid of coordinates over their service area (default 6.5 x 6.5 miles),
using DataForSEO's Google Maps SERP at each point. Writes a JSON result and a
self-contained HTML report (Leaflet + OpenStreetMap, no API key needed) you can
open in a browser — the Merchynt/Local-Falcon style colored grid.

This is the PIPELINE prototype. Once validated, the same data feeds the app:
marketing_geogrid_scans + marketing_geogrid_points (see docs/handoff-client-dashboard.md).

Center + business identity come from clients/{slug}/plan-input.json -> brand
(lat, lng, place_id, google_cid, display_name).

DataForSEO creds are read from the dataforseo MCP env in ~/.claude.json
(DATAFORSEO_USERNAME / DATAFORSEO_PASSWORD) — same account the MCP uses.

Usage:
  python3 scripts/geogrid_scan.py --slug narestco --keyword "water damage restoration" \
      [--grid 13] [--miles 6.5] [--zoom 14] [--max-rank 20] [--workers 6]

Cost: grid^2 DataForSEO Google Maps requests. The script sums the ACTUAL cost
returned by the API and prints it (no guessing).
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import datetime as dt
import json
import math
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DFS_URL = "https://api.dataforseo.com/v3/serp/google/maps/live/advanced"
MILES_PER_DEG_LAT = 69.0


def load_dfs_creds() -> tuple[str, str]:
    # Production (Railway/CI): env vars. Local: fall back to the dataforseo MCP
    # creds embedded in ~/.claude.json (same account the MCP uses).
    import os
    env_u = os.environ.get("DATAFORSEO_USERNAME")
    env_p = os.environ.get("DATAFORSEO_PASSWORD")
    if env_u and env_p:
        return env_u, env_p
    home_cfg = Path.home() / ".claude.json"
    if not home_cfg.exists():
        sys.exit("ERROR: DATAFORSEO_USERNAME/PASSWORD not set and ~/.claude.json not found.")
    cfg = json.loads(home_cfg.read_text())
    found = {}
    def walk(o):
        if isinstance(o, dict):
            if "DATAFORSEO_USERNAME" in o and "DATAFORSEO_PASSWORD" in o:
                found["u"], found["p"] = o["DATAFORSEO_USERNAME"], o["DATAFORSEO_PASSWORD"]
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(cfg)
    if "u" not in found:
        sys.exit("ERROR: DATAFORSEO_USERNAME/PASSWORD not found in ~/.claude.json MCP env.")
    return found["u"], found["p"]


def load_center(slug: str) -> dict:
    p = ROOT / "clients" / slug / "plan-input.json"
    if not p.exists():
        sys.exit(f"ERROR: {p} not found.")
    b = json.loads(p.read_text()).get("brand", {})
    for k in ("lat", "lng", "display_name"):
        if not b.get(k):
            sys.exit(f"ERROR: brand.{k} missing in plan-input.json — can't center the grid.")
    return {
        "name": b["display_name"],
        "lat": float(b["lat"]),
        "lng": float(b["lng"]),
        "place_id": b.get("place_id"),
        "cid": str(b.get("google_cid")) if b.get("google_cid") else None,
    }


def build_grid(lat: float, lng: float, n: int, miles: float) -> list[dict]:
    half = miles / 2.0
    pts = []
    for i in range(n):          # row 0 = north
        for j in range(n):      # col 0 = west
            fi = (i / (n - 1)) * 2 - 1 if n > 1 else 0
            fj = (j / (n - 1)) * 2 - 1 if n > 1 else 0
            dlat = (fi * half) / MILES_PER_DEG_LAT
            dlng = (fj * half) / (MILES_PER_DEG_LAT * math.cos(math.radians(lat)))
            pts.append({"row": i, "col": j, "lat": round(lat - dlat, 6), "lng": round(lng + dlng, 6)})
    return pts


def rank_at_point(auth: str, keyword: str, pt: dict, biz: dict, zoom: int, max_rank: int) -> dict:
    body = json.dumps([{
        "keyword": keyword,
        "location_coordinate": f"{pt['lat']},{pt['lng']},{zoom}z",
        "language_code": "en",
        "device": "desktop",
    }]).encode()
    req = urllib.request.Request(DFS_URL, data=body, method="POST",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    rank, cost = None, 0.0
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
        task = (resp.get("tasks") or [{}])[0]
        cost = float(task.get("cost") or 0.0)
        items = ((task.get("result") or [{}])[0] or {}).get("items") or []
        for it in items:
            if not isinstance(it, dict):
                continue
            cid = str(it.get("cid")) if it.get("cid") is not None else None
            title = (it.get("title") or "").lower()
            match = (
                (biz["cid"] and cid == biz["cid"]) or
                (biz["place_id"] and it.get("place_id") == biz["place_id"]) or
                (biz["name"].lower() in title)
            )
            if match:
                rank = it.get("rank_absolute") or it.get("rank_group")
                break
    except Exception as e:
        sys.stderr.write(f"  WARN point ({pt['row']},{pt['col']}): {str(e)[:120]}\n")
    if rank is not None and rank > max_rank:
        rank = None
    return {**pt, "rank": rank, "found": rank is not None, "cost": cost}


def color_for(rank):
    if rank is None:        return "#dc2626"   # 20+ / not found — red
    if rank <= 3:           return "#16a34a"   # green
    if rank <= 10:          return "#eab308"   # yellow
    return "#f97316"                            # 11-20 — orange


def render_html(out: Path, biz: dict, keyword: str, pts: list[dict], miles: int,
                grid: int, avg_rank, pct_top3, scanned: str) -> None:
    markers = []
    for p in pts:
        label = "20+" if p["rank"] is None else str(p["rank"])
        markers.append({"lat": p["lat"], "lng": p["lng"], "label": label, "color": color_for(p["rank"])})
    data_js = json.dumps(markers)
    avg_s = "—" if avg_rank is None else f"{avg_rank:.1f}"
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Geo-grid — {biz['name']} — {keyword}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0f172a;color:#e2e8f0}}
 .hdr{{padding:16px 20px;border-bottom:1px solid #1e293b}}
 .hdr h1{{margin:0 0 4px;font-size:18px}} .hdr .kw{{color:#38bdf8;font-weight:700}}
 .stats{{display:flex;gap:24px;margin-top:10px}}
 .stat .n{{font-size:26px;font-weight:800}} .stat .l{{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em}}
 #map{{height:78vh}}
 .pin{{display:flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:50%;
   color:#fff;font-weight:800;font-size:12px;border:2px solid rgba(255,255,255,.85);box-shadow:0 1px 4px rgba(0,0,0,.5)}}
 .legend{{padding:10px 20px;font-size:12px;color:#94a3b8;display:flex;gap:16px;align-items:center;flex-wrap:wrap}}
 .legend span b{{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:5px;vertical-align:-1px}}
</style></head><body>
<div class="hdr">
 <h1>{biz['name']} — <span class="kw">{keyword}</span></h1>
 <div class="stats">
  <div class="stat"><div class="n">{avg_s}</div><div class="l">Avg rank</div></div>
  <div class="stat"><div class="n">{pct_top3:.0f}%</div><div class="l">In top 3</div></div>
  <div class="stat"><div class="n">{grid}×{grid}</div><div class="l">Grid / {miles}×{miles} mi</div></div>
  <div class="stat"><div class="n" style="font-size:14px">{scanned}</div><div class="l">Scanned</div></div>
 </div>
</div>
<div id="map"></div>
<div class="legend">
 <span><b style="background:#16a34a"></b>1–3</span>
 <span><b style="background:#eab308"></b>4–10</span>
 <span><b style="background:#f97316"></b>11–20</span>
 <span><b style="background:#dc2626"></b>20+ / not found</span>
 <span style="margin-left:auto">Map data © OpenStreetMap</span>
</div>
<script>
 const pts={data_js};
 const map=L.map('map').setView([{biz['lat']},{biz['lng']}],12);
 L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
   {{maxZoom:19,attribution:'© OpenStreetMap'}}).addTo(map);
 pts.forEach(p=>{{
   const icon=L.divIcon({{className:'',html:`<div class="pin" style="background:${{p.color}}">${{p.label}}</div>`,iconSize:[30,30],iconAnchor:[15,15]}});
   L.marker([p.lat,p.lng],{{icon}}).addTo(map);
 }});
 L.circleMarker([{biz['lat']},{biz['lng']}],{{radius:7,color:'#fff',weight:2,fillColor:'#2563eb',fillOpacity:1}})
   .addTo(map).bindTooltip('{biz["name"]}');
</script></body></html>"""
    out.write_text(html)


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank AI geo-grid local rank scanner")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--grid", type=int, default=13)
    ap.add_argument("--miles", type=float, default=6.5)
    ap.add_argument("--zoom", type=int, default=12,
                    help="Maps zoom per point. 12 gives a realistic rank gradient (Merchynt-like); "
                         "higher (14+) is hyper-local and produces an unrealistic top-or-absent cliff.")
    ap.add_argument("--max-rank", type=int, default=20)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    u, p = load_dfs_creds()
    auth = base64.b64encode(f"{u}:{p}".encode()).decode()
    biz = load_center(args.slug)
    pts = build_grid(biz["lat"], biz["lng"], args.grid, args.miles)
    print(f"==> Geo-grid: {biz['name']} | '{args.keyword}' | {args.grid}x{args.grid} over {args.miles}x{args.miles} mi")
    print(f"    Center: {biz['lat']},{biz['lng']}  ({len(pts)} points)  matching cid={biz['cid']}")

    results = [None] * len(pts)
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(rank_at_point, auth, args.keyword, pt, biz, args.zoom, args.max_rank): k
                for k, pt in enumerate(pts)}
        done = 0
        for fut in cf.as_completed(futs):
            results[futs[fut]] = fut.result()
            done += 1
            if done % 20 == 0 or done == len(pts):
                print(f"    scanned {done}/{len(pts)}")

    found = [r for r in results if r["found"]]
    total_cost = sum(r["cost"] for r in results)
    avg_rank = (sum(r["rank"] for r in found) / len(found)) if found else None
    pct_top3 = (100.0 * sum(1 for r in found if r["rank"] <= 3) / len(pts)) if pts else 0.0
    scanned = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")

    kw_slug = re.sub(r"[^a-z0-9]+", "-", args.keyword.lower()).strip("-")
    date_s = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    outdir = ROOT / "clients" / args.slug / "geogrid"
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = outdir / f"{kw_slug}-{date_s}.json"
    html_path = outdir / f"{kw_slug}-{date_s}.html"

    json_path.write_text(json.dumps({
        "slug": args.slug, "business": biz, "keyword": args.keyword,
        "grid": args.grid, "miles": args.miles, "zoom": args.zoom,
        "scanned_at": scanned, "avg_rank": avg_rank, "pct_in_top3": round(pct_top3, 1),
        "found_points": len(found), "total_points": len(pts),
        "cost_usd": round(total_cost, 4), "points": results,
    }, indent=2))
    render_html(html_path, biz, args.keyword, results, int(args.miles), args.grid, avg_rank, pct_top3, scanned)

    print(f"\n    Avg rank (found): {avg_rank:.1f}" if avg_rank else "\n    Avg rank: n/a (not found anywhere)")
    print(f"    In top 3:         {pct_top3:.0f}% of grid")
    print(f"    Found in:         {len(found)}/{len(pts)} points")
    print(f"    DataForSEO cost:  ${total_cost:.4f}  (=> ${total_cost/len(pts):.5f}/point)")
    print(f"\n    JSON:   {json_path}")
    print(f"    REPORT: {html_path}")
    print(f"    open '{html_path}'   # view the grid in your browser")
    return 0


if __name__ == "__main__":
    sys.exit(main())
