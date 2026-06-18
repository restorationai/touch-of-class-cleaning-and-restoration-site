#!/usr/bin/env python3
"""
Rank AI — Geo-grid multi-keyword / multi-city REPORT builder.

Scans a client's Google Maps rank across an N x N grid for EACH keyword in
clients/{slug}/geogrid-keywords.txt, centered on EACH city in
clients/{slug}/geogrid-cities.json, then renders ONE scrollable HTML report
(keyword-major, a city column per keyword — the Merchynt layout) so you can see
exactly what the in-app dashboard will show.

Reuses the scanning core from geogrid_scan.py. DataForSEO Google Maps SERP per
point; sums the ACTUAL API cost.

Usage:
  python3 scripts/geogrid_report.py --slug narestco [--grid 13] [--miles 6.5] [--zoom 12] [--workers 16]
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import geogrid_scan as gs  # noqa: E402


def load_keywords(slug: str) -> list[str]:
    f = ROOT / "clients" / slug / "geogrid-keywords.txt"
    if not f.exists():
        sys.exit(f"ERROR: {f} not found (one keyword per line).")
    return [ln.strip() for ln in f.read_text().splitlines() if ln.strip()]


def load_cities(slug: str, biz: dict) -> list[dict]:
    f = ROOT / "clients" / slug / "geogrid-cities.json"
    if f.exists():
        return json.loads(f.read_text())
    return [{"label": "Primary", "lat": biz["lat"], "lng": biz["lng"]}]


def render(out: Path, biz: dict, keywords: list[str], cities: list[dict],
           data: dict, grid: int, miles: float, zoom: int, total_cost: float, scanned: str) -> None:
    # data[(kw, city_label)] = {points, avg_rank, pct_top3, found, total, center}
    # overall stats
    all_found = [d["avg_rank"] for d in data.values() if d["avg_rank"] is not None]
    overall_avg = (sum(d["avg_rank"] * d["found"] for d in data.values() if d["avg_rank"]) /
                   max(1, sum(d["found"] for d in data.values()))) if data else None
    overall_top3 = (sum(d["found_top3"] for d in data.values()) /
                    max(1, sum(d["total"] for d in data.values())) * 100) if data else 0

    maps_js = {}
    cards_html = []
    for kw in keywords:
        cols = []
        for city in cities:
            d = data.get((kw, city["label"]))
            if not d:
                continue
            mid = f"m_{abs(hash((kw, city['label']))) % (10**9)}"
            maps_js[mid] = {
                "center": [city["lat"], city["lng"]],
                "points": [{"lat": p["lat"], "lng": p["lng"],
                            "label": ("20+" if p["rank"] is None else str(p["rank"])),
                            "color": gs.color_for(p["rank"])} for p in d["points"]],
            }
            avg = "—" if d["avg_rank"] is None else f"{d['avg_rank']:.1f}"
            cols.append(f"""
          <div class="city">
            <div class="city-hd"><span class="city-name">{city['label']}</span>
              <span class="city-stats"><b>{avg}</b> avg &nbsp;·&nbsp; <b>{d['pct_top3']:.0f}%</b> top&nbsp;3</span></div>
            <div id="{mid}" class="map"></div>
          </div>""")
        cards_html.append(f"""
      <section class="kw">
        <h3>{kw}</h3>
        <div class="cols">{''.join(cols)}</div>
      </section>""")

    overall_avg_s = "—" if not all_found else f"{overall_avg:.1f}"
    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Local Map Rankings — {biz['name']}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 :root{{color-scheme:dark}}
 *{{box-sizing:border-box}}
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0b1220;color:#e2e8f0}}
 .top{{position:sticky;top:0;z-index:500;background:#0b1220ee;backdrop-filter:blur(8px);border-bottom:1px solid #1e293b;padding:18px 24px}}
 .top h1{{margin:0;font-size:20px}} .top .sub{{color:#94a3b8;font-size:13px;margin-top:2px}}
 .kpis{{display:flex;gap:28px;margin-top:14px;flex-wrap:wrap}}
 .kpi .n{{font-size:28px;font-weight:800;line-height:1}} .kpi .l{{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.07em;margin-top:4px}}
 .legend{{display:flex;gap:14px;align-items:center;font-size:12px;color:#94a3b8;margin-top:12px;flex-wrap:wrap}}
 .legend b{{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px;vertical-align:-1px}}
 .wrap{{max-width:1180px;margin:0 auto;padding:8px 24px 60px}}
 section.kw{{margin-top:30px}}
 section.kw h3{{font-size:17px;margin:0 0 12px;text-transform:capitalize;border-left:3px solid #f97316;padding-left:10px}}
 .cols{{display:grid;grid-template-columns:1fr;gap:16px}}
 @media(min-width:760px){{.cols{{grid-template-columns:1fr 1fr}}}}
 .city{{background:#0f172a;border:1px solid #1e293b;border-radius:12px;overflow:hidden}}
 .city-hd{{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;font-size:13px}}
 .city-name{{font-weight:700}} .city-stats{{color:#94a3b8}} .city-stats b{{color:#e2e8f0}}
 .map{{height:300px}}
 .pin{{display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;color:#fff;font-weight:800;font-size:11px;border:2px solid rgba(255,255,255,.85);box-shadow:0 1px 3px rgba(0,0,0,.5)}}
</style></head><body>
<div class="top">
  <h1>Local Map Rankings — {biz['name']}</h1>
  <div class="sub">{grid}×{grid} grid · {miles}×{miles} mi per city · {len(keywords)} keywords × {len(cities)} cities · scanned {scanned}</div>
  <div class="kpis">
    <div class="kpi"><div class="n">{overall_avg_s}</div><div class="l">Avg rank (found)</div></div>
    <div class="kpi"><div class="n">{overall_top3:.0f}%</div><div class="l">Grid in top 3</div></div>
    <div class="kpi"><div class="n">{len(keywords)}</div><div class="l">Keywords</div></div>
    <div class="kpi"><div class="n">{len(cities)}</div><div class="l">Cities</div></div>
  </div>
  <div class="legend">
    <span><b style="background:#16a34a"></b>1–3</span><span><b style="background:#eab308"></b>4–10</span>
    <span><b style="background:#f97316"></b>11–20</span><span><b style="background:#dc2626"></b>20+ / not found</span>
    <span style="margin-left:auto">DataForSEO · Map © OpenStreetMap</span>
  </div>
</div>
<div class="wrap">{''.join(cards_html)}</div>
<script>
 const MAPS={json.dumps(maps_js)};
 for(const id in MAPS){{
   const cfg=MAPS[id];
   // Locked / non-interactive: a static screen (no zoom, pan, or scroll).
   const map=L.map(id,{{zoomControl:false,attributionControl:false,dragging:false,scrollWheelZoom:false,doubleClickZoom:false,touchZoom:false,boxZoom:false,keyboard:false}}).setView(cfg.center,11);
   L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19}}).addTo(map);
   cfg.points.forEach(p=>{{
     const icon=L.divIcon({{className:'',html:`<div class="pin" style="background:${{p.color}}">${{p.label}}</div>`,iconSize:[24,24],iconAnchor:[12,12]}});
     L.marker([p.lat,p.lng],{{icon}}).addTo(map);
   }});
 }}
</script></body></html>"""
    out.write_text(html)


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank AI geo-grid multi-keyword/multi-city report")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--grid", type=int, default=13)
    ap.add_argument("--miles", type=float, default=6.5)
    ap.add_argument("--zoom", type=int, default=12)
    ap.add_argument("--max-rank", type=int, default=20)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    u, p = gs.load_dfs_creds()
    auth = base64.b64encode(f"{u}:{p}".encode()).decode()
    biz = gs.load_center(args.slug)
    keywords = load_keywords(args.slug)
    cities = load_cities(args.slug, biz)
    print(f"==> Geo-grid report: {biz['name']} | {len(keywords)} keywords × {len(cities)} cities "
          f"| {args.grid}x{args.grid} @ zoom {args.zoom}")

    # Build every (kw, city, point) task
    grids: dict = {}
    tasks: list = []
    for city in cities:
        pts_base = gs.build_grid(city["lat"], city["lng"], args.grid, args.miles)
        for kw in keywords:
            pts = [dict(pp) for pp in pts_base]
            grids[(kw, city["label"])] = pts
            for idx, pt in enumerate(pts):
                tasks.append((kw, city["label"], idx, pt))
    print(f"    {len(tasks)} total grid points to scan...")

    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(gs.rank_at_point, auth, kw, pt, biz, args.zoom, args.max_rank): (kw, cl, idx)
                for (kw, cl, idx, pt) in tasks}
        for fut in cf.as_completed(futs):
            kw, cl, idx = futs[fut]
            grids[(kw, cl)][idx].update(fut.result())
            done += 1
            if done % 200 == 0 or done == len(tasks):
                print(f"    scanned {done}/{len(tasks)}")

    # Aggregate
    data: dict = {}
    total_cost = 0.0
    for (kw, cl), pts in grids.items():
        found = [p for p in pts if p.get("found")]
        total_cost += sum(p.get("cost", 0) for p in pts)
        avg = (sum(p["rank"] for p in found) / len(found)) if found else None
        top3 = sum(1 for p in found if p["rank"] <= 3)
        data[(kw, cl)] = {"points": pts, "avg_rank": avg,
                          "pct_top3": (100.0 * top3 / len(pts)) if pts else 0,
                          "found": len(found), "found_top3": top3, "total": len(pts)}

    scanned = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    outdir = ROOT / "clients" / args.slug / "geogrid"
    outdir.mkdir(parents=True, exist_ok=True)
    date_s = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    report = outdir / f"report-{date_s}.html"
    render(report, biz, keywords, cities, data, args.grid, args.miles, args.zoom, total_cost, scanned)

    print(f"\n    DataForSEO cost: ${total_cost:.2f}")
    print(f"    REPORT: {report}")
    print(f"    open '{report}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
