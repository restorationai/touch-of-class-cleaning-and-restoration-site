#!/usr/bin/env python3
"""
PROTOTYPE — Geo-grid "Compare" view (before/after by date range).

SIMULATED DATA ONLY (no DataForSEO calls). Builds a functional reference of the
compare view: a city selector + two date selectors (bi-weekly snapshots), and
per-keyword Before|After columns with delta badges. Maps are static (locked).

This is purely to lock the UX before the developer builds it. The real version
reads the same shape from marketing_geogrid_scans/_points (timestamped history).

Run: python3 scripts/geogrid_compare_prototype.py
"""
from __future__ import annotations
import json, math, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import geogrid_scan as gs  # build_grid + color_for

random.seed(11)

CITIES = {
    "Federal Way, WA": {"lat": 47.337, "lng": -122.314, "base": 0.0},   # home market (strong)
    "Tacoma, WA":      {"lat": 47.2529, "lng": -122.4443, "base": 2.2},  # weaker / further
}
KEYWORDS = [
    "water damage restoration", "fire damage restoration", "mold remediation",
    "storm damage restoration", "water damage restoration near me",
]
WEEKS = [("Week 1", "Jun 2"), ("Week 3", "Jun 16"), ("Week 5", "Jun 30")]  # bi-weekly
FALLOFF = {0: 6.2, 1: 4.3, 2: 2.6}  # rank gradient steepness per snapshot (improves over time)
HALF = 6.5 / 2


def dist_mi(p):
    dy = (p["row"] - 6) / 6 * HALF
    dx = (p["col"] - 6) / 6 * HALF
    return math.hypot(dx, dy)


def build_snapshots():
    snap = {}
    for city, cfg in CITIES.items():
        pts = gs.build_grid(cfg["lat"], cfg["lng"], 13, 6.5)
        snap[city] = {}
        for ki, kw in enumerate(KEYWORDS):
            snap[city][kw] = {}
            kw_pen = ki * 0.5          # some keywords weaker than others
            for wi, (wlabel, wdate) in enumerate(WEEKS):
                k = FALLOFF[wi] + cfg["base"] + kw_pen
                grid, found = [], []
                for p in pts:
                    base = 1 + dist_mi(p) * k + random.uniform(-1.6, 1.6) - wi * 0.6
                    r = max(1, round(base))
                    rank = None if r > 20 else r
                    if rank is not None:
                        found.append(rank)
                    grid.append({"lat": round(p["lat"], 6), "lng": round(p["lng"], 6),
                                 "label": "20+" if rank is None else str(rank),
                                 "color": gs.color_for(rank)})
                avg = round(sum(found) / len(found), 1) if found else None
                top3 = round(100 * sum(1 for r in found if r <= 3) / len(grid))
                snap[city][kw][wlabel] = {"date": wdate, "avg": avg, "top3": top3,
                                          "found": len(found), "total": len(grid), "points": grid}
    return snap


def render(snap) -> Path:
    centers = {c: [cfg["lat"], cfg["lng"]] for c, cfg in CITIES.items()}
    week_opts = "".join(f'<option value="{w}">{w} ({d})</option>' for w, d in WEEKS)
    city_opts = "".join(f'<option value="{c}">{c}</option>' for c in CITIES)
    sections = "".join(f"""
      <section class="kw">
        <div class="kwhd"><h3>{kw}</h3><span class="delta" id="d-{i}"></span></div>
        <div class="cols">
          <div class="col"><div class="lbl badge-before" id="bl-{i}"></div><div id="map-{i}-b" class="map"></div></div>
          <div class="col"><div class="lbl badge-after" id="al-{i}"></div><div id="map-{i}-a" class="map"></div></div>
        </div>
      </section>""" for i, kw in enumerate(KEYWORDS))

    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Compare view (prototype) — Local Map Rankings</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 :root{{color-scheme:dark}} *{{box-sizing:border-box}}
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0b1220;color:#e2e8f0}}
 .top{{position:sticky;top:0;z-index:500;background:#0b1220ee;backdrop-filter:blur(8px);border-bottom:1px solid #1e293b;padding:16px 24px}}
 .top h1{{margin:0;font-size:19px}} .top .sub{{color:#fbbf24;font-size:12px;margin-top:2px}}
 .controls{{display:flex;gap:18px;flex-wrap:wrap;align-items:flex-end;margin-top:12px}}
 .ctrl label{{display:block;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}}
 select{{background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:8px 12px;font-size:14px;font-weight:600}}
 .vs{{color:#64748b;font-weight:800;padding-bottom:8px}}
 .wrap{{max-width:1100px;margin:0 auto;padding:6px 24px 60px}}
 section.kw{{margin-top:26px}}
 .kwhd{{display:flex;align-items:center;gap:14px;margin-bottom:10px}}
 .kwhd h3{{font-size:17px;margin:0;text-transform:capitalize;border-left:3px solid #f97316;padding-left:10px}}
 .delta{{font-size:13px;font-weight:700}}
 .up{{color:#22c55e}} .down{{color:#ef4444}} .flat{{color:#94a3b8}}
 .cols{{display:grid;grid-template-columns:1fr;gap:14px}}
 @media(min-width:760px){{.cols{{grid-template-columns:1fr 1fr}}}}
 .col{{background:#0f172a;border:1px solid #1e293b;border-radius:12px;overflow:hidden}}
 .lbl{{padding:9px 13px;font-size:12.5px;font-weight:600}}
 .badge-before{{border-bottom:2px solid #64748b}} .badge-after{{border-bottom:2px solid #22c55e}}
 .map{{height:300px}}
 .pin{{display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;color:#fff;font-weight:800;font-size:11px;border:2px solid rgba(255,255,255,.85);box-shadow:0 1px 3px rgba(0,0,0,.5)}}
 .legend{{display:flex;gap:14px;font-size:12px;color:#94a3b8;margin-top:10px;flex-wrap:wrap}}
 .legend b{{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px;vertical-align:-1px}}
</style></head><body>
<div class="top">
  <h1>Local Map Rankings — Compare</h1>
  <div class="sub">PROTOTYPE · simulated bi-weekly data · maps are static (locked)</div>
  <div class="controls">
    <div class="ctrl"><label>City</label><select id="city">{city_opts}</select></div>
    <div class="ctrl"><label>Before</label><select id="before">{week_opts}</select></div>
    <div class="vs">vs</div>
    <div class="ctrl"><label>After</label><select id="after">{week_opts}</select></div>
  </div>
  <div class="legend">
    <span><b style="background:#16a34a"></b>1–3</span><span><b style="background:#eab308"></b>4–10</span>
    <span><b style="background:#f97316"></b>11–20</span><span><b style="background:#dc2626"></b>20+ / not found</span>
  </div>
</div>
<div class="wrap">{sections}</div>
<script>
 const SNAP={json.dumps(snap)};
 const CENTERS={json.dumps(centers)};
 const KW={json.dumps(KEYWORDS)};
 const citySel=document.getElementById('city'), beforeSel=document.getElementById('before'), afterSel=document.getElementById('after');
 beforeSel.value="Week 1"; afterSel.value="Week 5";
 const LOCK={{zoomControl:false,attributionControl:false,dragging:false,scrollWheelZoom:false,doubleClickZoom:false,touchZoom:false,boxZoom:false,keyboard:false}};
 const maps={{}};
 function ensure(id,center){{
   if(maps[id]) return maps[id];
   const m=L.map(id,LOCK).setView(center,11);
   L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19}}).addTo(m);
   const layer=L.layerGroup().addTo(m); maps[id]={{m,layer}}; return maps[id];
 }}
 function pins(layer,points){{
   layer.clearLayers();
   points.forEach(p=>{{
     const icon=L.divIcon({{className:'',html:`<div class="pin" style="background:${{p.color}}">${{p.label}}</div>`,iconSize:[24,24],iconAnchor:[12,12]}});
     L.marker([p.lat,p.lng],{{icon}}).addTo(layer);
   }});
 }}
 function fmt(s){{return `${{s.date}} · avg ${{s.avg??'—'}} · ${{s.top3}}% top3`;}}
 function render(){{
   const city=citySel.value, bw=beforeSel.value, aw=afterSel.value, center=CENTERS[city];
   KW.forEach((kw,i)=>{{
     const b=SNAP[city][kw][bw], a=SNAP[city][kw][aw];
     const mb=ensure(`map-${{i}}-b`,center), ma=ensure(`map-${{i}}-a`,center);
     mb.m.setView(center,11); ma.m.setView(center,11);
     pins(mb.layer,b.points); pins(ma.layer,a.points);
     document.getElementById(`bl-${{i}}`).textContent=fmt(b);
     document.getElementById(`al-${{i}}`).textContent=fmt(a);
     const d=document.getElementById(`d-${{i}}`);
     if(a.avg!=null && b.avg!=null){{
       const diff=+(b.avg-a.avg).toFixed(1);  // lower rank is better
       if(diff>0.2){{d.className='delta up';d.textContent=`▲ improved ${{diff}} (avg ${{b.avg}}→${{a.avg}}, top3 ${{b.top3}}%→${{a.top3}}%)`;}}
       else if(diff<-0.2){{d.className='delta down';d.textContent=`▼ down ${{Math.abs(diff)}} (avg ${{b.avg}}→${{a.avg}})`;}}
       else{{d.className='delta flat';d.textContent=`~ steady (avg ${{a.avg}}, top3 ${{a.top3}}%)`;}}
     }} else {{ d.className='delta flat'; d.textContent=`top3 ${{b.top3}}% → ${{a.top3}}%`; }}
   }});
 }}
 citySel.onchange=beforeSel.onchange=afterSel.onchange=render;
 render();
</script></body></html>"""
    out = ROOT / "clients" / "narestco" / "geogrid" / "compare-prototype.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    return out


if __name__ == "__main__":
    out = render(build_snapshots())
    print(f"PROTOTYPE: {out}")
    print(f"open '{out}'")
