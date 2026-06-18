# Handoff — Local Map Rankings (Geo-grid) Dashboard

**Audience:** Restoration-AI-APP developer.
**Status:** Validated end-to-end on the Rank AI side (NaRestCo, 10 keywords × 2 cities, 3,380 points, $3.54). This doc is the build contract — front-end to back-end.
**Companion doc:** `docs/handoff-client-dashboard.md` (GSC Coverage card + overall dashboard architecture). Same `marketing_*` + agency-credentials pattern.

---

## 0. TL;DR

A "Local Map Rankings" dashboard card: for each tracked keyword, a grid of colored pins on a map showing where the client ranks in Google Maps across their service area, per city. Green (top 3) → red (not found). Plus avg-rank, %-in-top-3, and **before/after % change over time**.

**It is NOT a Google API image.** It's a geo-grid technique: query Google Maps rank at a grid of coordinates (via **DataForSEO**, server-side, our account), store the per-point ranks, and render them on a map. We have proven the whole path; you build the tables + UI + two endpoint calls.

The single source of visual truth for the UI you'll build is the working report: `clients/{slug}/geogrid/report-*.html` (open one — that's the layout, colors, and stats to reproduce in-app).

---

## 1. Architecture & division of labor

```
 DataForSEO (our account)  ──►  Rank AI pipeline  ──►  Supabase marketing_geogrid_*  ──►  APP (you)
   per-coordinate Maps rank      scan + render PNG       scans + points + image_url        read + render
```

**The browser never calls DataForSEO.** All scanning uses our DataForSEO account, server-side, in the Rank AI pipeline. Results land in `marketing_*` tables; the app reads them.

| Piece | Owner |
|---|---|
| Create `marketing_geogrid_*` tables (migration + RLS) | **You** (you own the DB schema; DDL below) |
| Scan jobs (monthly + on-demand), DataForSEO calls, PNG render → R2 | **Rank AI pipeline** (we build; reference scripts exist) |
| `POST /geogrid/scan` endpoint on `rank-ai-api` (on-demand) | **Rank AI** exposes; **you** call |
| Dashboard UI (cards, maps, city tabs, before/after) | **You** |

Client join key everywhere: **`company_id`** (uuid) — same as `marketing_sites` / Ads tables.

---

## 2. Validated parameters & economics (measured, not estimated)

| Setting | Value | Why |
|---|---|---|
| Grid | **13 × 13** (169 points) | Matches the Merchynt-style density; clean gradient |
| Area | **6.5 × 6.5 miles** per city, centered on the city | Metro default (don't exceed for metro; 3.25 for tight urban, 9.75 rural) |
| Spacing | ~0.46 mi between points | Derived from 6.5mi / 13 |
| **Zoom** | **12** (critical) | zoom 14 = hyper-local "top-or-absent" CLIFF artifact; **zoom 12 = realistic 1→20→off gradient** |
| Max rank tracked | 20 (else "not found / 20+") | Local finder depth |
| Cost | **~$0.0011–0.002 per point** (measured $3.54 / 3,380 pts) | 13×13 ≈ **$0.18–0.34 per grid** |
| Per scan run | 10 keywords × 2 cities ≈ **$3.54** (measured) | Trivial |
| Per client / month | bi-weekly = ~2 runs ≈ **$7** | Scales fine across the book |

Color scale (use exactly):

| Rank | Color | Hex |
|---|---|---|
| 1–3 | green | `#16a34a` |
| 4–10 | yellow | `#eab308` |
| 11–20 | orange | `#f97316` |
| 20+ / not found | red | `#dc2626` |

---

## 3. Back end

### 3.1 Data source + business matching (we handle this)
- DataForSEO `POST /v3/serp/google/maps/live/advanced`, body `{"keyword","location_coordinate":"<lat>,<lng>,12z","language_code":"en","device":"desktop"}`.
- Identify the client's listing in the returned `items[]` by **`cid`**, then `place_id`, then business-name match → take `rank_absolute`. (We store the client's `cid`/`place_id`/`name` in the client record.)
- Sum the real per-call `cost` for spend tracking.
- Reference impl: `scripts/geogrid_scan.py` (single grid) and `scripts/geogrid_report.py` (multi-keyword/multi-city orchestration + render).

### 3.2 Tables (you create these — migration + RLS by `company_id`)

```sql
-- One row per (company, keyword, city, run)
create table marketing_geogrid_scans (
  id              uuid primary key default gen_random_uuid(),
  company_id      uuid not null,
  keyword         text not null,
  city_label      text not null,            -- e.g. "Tacoma, WA"
  center_lat      double precision not null,
  center_lng      double precision not null,
  grid_size       int  not null default 13,  -- N (=> N*N points)
  grid_spacing_mi numeric not null default 0.5,
  miles           numeric not null default 6.5,
  zoom            int  not null default 12,
  avg_rank        numeric,                   -- avg over found points (null if none)
  pct_in_top3     numeric,                   -- 0..100 of the WHOLE grid
  found_points    int  not null default 0,
  total_points    int  not null default 0,
  image_url       text,                      -- rendered PNG in R2 (fast display / PDF / email)
  cost_usd        numeric,                   -- DataForSEO spend for this scan
  scanned_at      timestamptz not null default now()
);
create index on marketing_geogrid_scans (company_id, keyword, city_label, scanned_at desc);

-- One row per grid point of a scan (the heat data; drives % change + re-render)
create table marketing_geogrid_points (
  id        uuid primary key default gen_random_uuid(),
  scan_id   uuid not null references marketing_geogrid_scans(id) on delete cascade,
  row       int not null,
  col       int not null,
  lat       double precision not null,
  lng       double precision not null,
  rank      int,                              -- 1..20, or null = "20+ / not found"
  found     boolean not null default false
);
create index on marketing_geogrid_points (scan_id);
```
RLS: scope `marketing_geogrid_scans` by `company_id`; points via their scan's `company_id`. Mirror your existing Ads-table policies.

**Never overwrite scans.** Each monthly/manual run inserts a NEW `scans` row (+ its points). History = the before/after feature.

### 3.3 Data contract (what the app reads)
Per keyword+city, the latest scan row gives the headline (`avg_rank`, `pct_in_top3`, `image_url`, `scanned_at`); its `points[]` give the pins. The exact JSON the pipeline produces (and the shape you'll get back from the scan endpoint) matches `clients/{slug}/geogrid/{kw}-{date}.json`:

```json
{
  "keyword": "water damage restoration",
  "city_label": "Federal Way, WA",
  "center": {"lat": 47.337, "lng": -122.314},
  "grid": 13, "miles": 6.5, "zoom": 12,
  "avg_rank": 6.3, "pct_in_top3": 36.0,
  "found_points": 64, "total_points": 169,
  "cost_usd": 0.34, "image_url": "https://images.{domain}/geogrid/...png",
  "points": [{"row":0,"col":0,"lat":47.36,"lng":-122.36,"rank":null,"found":false}, ...]
}
```

### 3.4 Scan jobs (we build, pipeline-side)
- **Bi-weekly auto (every 2 weeks):** loop each client's keyword list × city list → scan → insert `scans` + `points` → render PNG → R2 → set `image_url`. (Railway cron, like `ads_sync`.) Bi-weekly gives "Week 1 vs Week 3" granularity for the Compare view at ~2 runs/month.
- **On-demand:** the endpoint below.

### 3.5 On-demand scan endpoint (we expose on `rank-ai-api`; you call)
```
POST /geogrid/scan        (authed)
  body: { company_id, keyword, city_label }   // single keyword+city refresh
  → runs the grid with the agency DataForSEO account, inserts a new scan + points,
    renders + uploads the PNG, returns the new scan row (id, stats, image_url).
  → a scan takes ~30–90s; poll the row or subscribe to the table.
```
**Rate limit (cost guard): 1 manual scan per (company, keyword, city) per day.** One single-keyword refresh ≈ $0.18–0.34, so daily is safe; the limit just blocks accidental spamming. Monthly auto covers the full set.

### 3.6 Image rendering + R2
We render a static PNG per scan (grid pins on a map) and store at `images.{domain}/geogrid/{keyword-slug}/{scan_id}.png` (R2). The app can use `image_url` directly for fast display, PDFs, and email reports — no client-side map needed for the static view. (Interactive map optional; see 4.3.)

---

## 4. Front end (you build)

The dashboard has **two views** of the same data, both keyword-major and scrollable. Visual references (open them):
- **Overview** layout → `clients/{slug}/geogrid/report-*.html`
- **Compare** view → `clients/{slug}/geogrid/compare-prototype.html` (functional: working selectors + before/after)

Pins use the §2 color scale; maps are **static** (a locked, non-interactive screen — no zoom/pan).

### 4.1 View A — Overview (default): all cities, current, with change badges
The day-to-day "show me everything, flag what changed" view. Columns = **cities**.
```
[ Local Map Rankings — {Business}                          ]
[ KPIs:  Avg rank | % in top 3 | # keywords | # cities     ]
[ Legend: ● 1–3  ● 4–10  ● 11–20  ● 20+/not found          ]
-------------------------------------------------------------
 ▸ water damage restoration
   ┌── Federal Way ──────┐   ┌── Tacoma ───────────┐
   │ avg 3.0   ▲ +3.3     │   │ avg 9.0   ▲ +3.0     │
   │ 58% top3 (was 36%)   │   │ 8% top3 (was 0%)     │
   │ [ current grid ]     │   │ [ current grid ]     │
   └──────────────────────┘   └──────────────────────┘
 ▸ fire damage restoration  ...
```
- Responsive: 1 column on mobile, 2 columns (cities) ≥760px; 3+ cities wrap to a grid.
- Each city card: the **current** grid + a **change badge** vs the prior scan — Δavg-rank (lower = better) and Δ%-in-top3, colored green (improved) / red (worse) / gray (steady).
- **KPIs (header):** Avg rank (found) = points-weighted avg of found ranks across shown scans; % in top 3 = found-top3 / total points; plus keyword + city counts.
- Order keywords by importance, or worst-avg-rank first to surface problems.

### 4.3 Map rendering — two options
- **Default = static image** (`image_url` from R2). Simplest, fast, works in PDF/email. Reproduces the report exactly. **Recommended for the scrollable report view.**
- **Optional interactive** (nice-to-have): render pins from `points[]` on a map. The report uses **Leaflet + OpenStreetMap tiles** (no API key, no referrer issues) — copy that. Pin = colored `divIcon` circle with the rank number (or "20+"). Use this for a "click to expand" detail view.

Pin marker (from the reference):
```js
L.divIcon({ html:`<div class="pin" style="background:${color}">${label}</div>`,
            iconSize:[24,24], iconAnchor:[12,12] })
// color by rank per §2 scale; label = rank or "20+"
```

### 4.4 View B — Compare: one city, before/after by date (the ROI view)
The "before our work → after" story (Merchynt's "Before / 4 months later"). Here the **columns flip from cities to dates**, and you view **one city at a time**. Reference: `compare-prototype.html`.
```
 City: [ Federal Way ▼ ]    Compare: [ Week 1 ▼ ]  vs  [ Week 5 ▼ ]
-------------------------------------------------------------
 ▸ water damage restoration   ▲ improved 5.1 (avg 8.1→3.0, top3 12%→58%)
   ┌── Week 1 (Jun 2) ───┐   ┌── Week 5 (Jun 30) ──┐
   │ [ mostly red grid ] │   │ [ mostly green ]    │
   └─────────────────────┘   └─────────────────────┘
 ▸ fire damage restoration  ...
```
- **Selectors:** a **City** dropdown (one city at a time) + two **date** dropdowns ("Before" / "After"), populated from the actual scan dates (**bi-weekly** — see §3.4). Defaults: Before = ~30 days ago / earliest, After = latest. Presets welcome ("vs last scan", "vs first scan").
- **Layout:** keyword-major; per keyword the two columns are the two selected snapshots (Before | After), each a static grid + its date/stats.
- **Delta badge per keyword:** `before.avg − after.avg` (lower rank is better) → **▲ improved / ▼ down / ~ steady**, plus the top-3 change. If a keyword had no avg before (not found), show the top-3 delta instead.
- **One city at a time is intentional** — it lets the two columns be the two *dates* and stay readable. Switch cities via the dropdown. (Seeing every city at once is the Overview's job — §4.1.)
- Changing **any** selector re-renders all keyword rows + deltas (the prototype does exactly this).
- Data: every scan is timestamped and **never overwritten**, so any two dates can be compared from `marketing_geogrid_scans` history. Optional: a sparkline of avg-rank / %-top3 over time per keyword.

### 4.5 "Run scan" button
- Per city panel (or per keyword), a refresh button → `POST /geogrid/scan { company_id, keyword, city_label }`.
- Disable + show "next available" if the daily rate limit is hit (endpoint returns 429).
- Scan takes ~30–90s: show a spinner / optimistic "scanning…", then refresh the card from the new row (poll or realtime subscribe to `marketing_geogrid_scans`).

### 4.6 Data fetching
- Read from Supabase by `company_id` (RLS). For the dashboard, fetch the **latest** scan per (keyword, city) + its points (or just `image_url` for the static view).
- **Never** call DataForSEO or render scans from the browser.

---

## 5. Per-client config (we own; informational for you)
- **Keywords:** `clients/{slug}/geogrid-keywords.txt` (one per line) — the tracked terms (default: top ~10 money keywords across services). We can also surface these as an editable list later.
- **Cities:** `clients/{slug}/geogrid-cities.json` — `[{label,lat,lng}, ...]`. Default = the client's primary city (centered on the business) + key service-area cities. (NaRestCo example used Federal Way + Tacoma.)
- **Grid params:** 13×13, 6.5mi, zoom 12 defaults (per §2); overridable per client.

---

## 6. Build phasing
| Phase | What |
|---|---|
| 1 | Tables + **View A (Overview)**: latest scan per keyword×city, static-image cards (keyword-major, city columns), KPIs, legend |
| 2 | Overview **change badges** (Δ vs prior scan) + "Run scan" button → `/geogrid/scan` + rate-limit UX |
| 3 | **View B (Compare)**: city + before/after date selectors, Before\|After columns, delta badges (the prototype) |
| 4 | Optional: sparkline over time + interactive (Leaflet) "expand" detail |

---

## 7. Reference implementation (already built, Rank AI side)
- `scripts/geogrid_scan.py` — one grid: identity match, grid math, DataForSEO call, cost, JSON + standalone HTML.
- `scripts/geogrid_report.py` — multi-keyword × multi-city orchestration (threaded), aggregation, the combined report.
- `clients/narestco/geogrid/report-2026-06-18.html` — **the working Overview reference** (open it; that's View A to reproduce).
- `scripts/geogrid_compare_prototype.py` + `clients/narestco/geogrid/compare-prototype.html` — **the working Compare reference** (View B): functional city + before/after date selectors, delta badges, static maps (simulated data).
- These will be adapted into the bi-weekly cron + the `/geogrid/scan` endpoint that writes to the `marketing_geogrid_*` tables and R2.

---

## 8. Open decisions (need a call)
1. **Default keyword count + which cities** per client (default: ~10 money keywords; primary city + 1–2 service-area cities). More cities = linear cost (~$0.18–0.34/keyword/city).
2. **Static image vs interactive** as the primary view (recommend static for the report, interactive for detail).
3. **Manual-scan rate limit** confirm: 1 / (keyword, city) / day.
4. ~~Scan cadence~~ — **DECIDED: every 2 weeks (bi-weekly).** (Just pick which day to align with the other crons.)
5. ~~`company_id` join key~~ — **CONFIRMED** (unique account id).

---

## 9. What Rank AI delivers to unblock you
- The `marketing_geogrid_*` DDL above (you run the migration; ping us to hand you the exact migration file).
- The bi-weekly scan cron + `POST /geogrid/scan` endpoint writing to those tables + R2 (`image_url`).
- The per-client `keywords` + `cities` config, and the business `cid`/`place_id` for matching.
- The rendered PNGs in R2.

You build: the migration, the dashboard card (keyword-major / city-columns per the report), the before/after view, and the calls to `/geogrid/scan`.
