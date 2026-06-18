# Handoff — Client Visibility Dashboard (GSC Coverage + Geo-grid Rankings)

**Audience:** Restoration-AI-APP developer.
**Author:** Rank AI pipeline side.
**Status:** spec — ready to build. Phase 1 (GSC) has data plumbing already; Phase 2 (geo-grid) is new.

---

## 1. Goal

Give every client (and us) clear, in-app visibility into the SEO + local metrics that prove the service is working:

1. **GSC Coverage** — how many of a client's pages are actually indexed by Google, which aren't, and why.
2. **Geo-grid Local Rankings** — the green/yellow/red map-pin grid showing where the client ranks in Google Maps across their service area, per keyword.

These join the **Ads dashboard** (already live in the app) and a future **GBP Insights** card to form one unified client dashboard.

---

## 2. Architecture — who owns what (read this first)

The single most important rule: **the browser never calls Google or DataForSEO directly.** All third-party data is fetched **server-side using Rank AI's agency credentials**, written into Supabase `marketing_*` tables, and the **app only reads those tables**. This is the same pattern the Ads dashboard already uses.

```
  ┌─────────────────────────────────────────────┐
  │ Rank AI pipeline (our infra, agency creds)   │
  │  • GSC agency token  • DataForSEO  • Ads MCC │
  │  Scheduled jobs (Railway crons) + on-demand  │
  │  endpoints on the rank-ai-api FastAPI service│
  └───────────────┬─────────────────────────────┘
                  │ writes (service-role)
                  ▼
        ┌───────────────────────┐
        │ Supabase marketing_*  │   ← shared contract (this doc)
        └───────────┬───────────┘
                    │ reads (RLS by company_id)
                    ▼
        ┌───────────────────────┐
        │ Restoration-AI-APP    │   ← you build the UI here
        │  dashboard cards       │
        └───────────────────────┘
```

**Division of labor**

| Piece | Owner |
|---|---|
| Create the `marketing_*` tables (migration + RLS) | **You** (you own the DB schema). DDL below. |
| Populate the tables (scheduled fetch jobs, agency creds) | **Rank AI pipeline** (we build, like `ads_sync` / `supabase_sync`) |
| On-demand actions ("re-check index", "run scan") | **Rank AI pipeline** exposes small authed endpoints on `rank-ai-api`; **you** call them |
| Dashboard UI (cards, tables, the map) | **You** |

So your build is: **tables + UI + a couple of fetch calls to our endpoints.** You do not touch Google/DataForSEO auth.

Client linkage is `company_id` (uuid), same key the existing `marketing_sites` / Ads tables use. The slug↔company_id mapping already lives in `marketing_sites`.

---

## 3. Feature A — GSC Index Coverage

### 3.1 What the client sees
- A **"Search Console"** card: a donut/번호 like **"187 / 192 pages indexed"** + sitemap status ("submitted, 192 URLs").
- A **drill-down table**: URL · status · last crawled · Google-selected canonical · "re-check" button. Filterable to **"Not indexed."**
- Per-row action **"Re-check status now"** (allowed). **No "force re-index" button** — see §5.

### 3.2 Data source (pipeline-side)
- **GSC URL Inspection API** (`urlInspection.index.inspect`) — per-URL verdict, coverage state, last crawl time, Google canonical, robots/indexing state.
- **GSC Sitemaps API** (`sitemaps.get`) — submitted/indexed counts at the sitemap level (cheap rollup).
- Auth: the **agency token** (`contact@restorationai.io`), which already owns every client property we provisioned (Step 1 + the build-site cut-over now auto-provisions GSC). **Clients connect nothing.**

> Important verification win: because GSC data flows through the **agency token (pipeline)**, the **app does not need the `webmasters.readonly` scope** on its own OAuth consent. Recommend **removing `webmasters.readonly`** from the app's requested scopes — it's currently requested but unused, which is a "request minimum scopes" risk on the pending OAuth verification.

### 3.3 Tables (DDL — you create these)

```sql
-- Per-URL index status (one row per client URL)
create table marketing_gsc_pages (
  id              uuid primary key default gen_random_uuid(),
  company_id      uuid not null,
  url             text not null,
  index_status    text not null,         -- 'INDEXED' | 'NOT_INDEXED' | 'CRAWLED_NOT_INDEXED'
                                          --  | 'DISCOVERED_NOT_INDEXED' | 'EXCLUDED' | 'ERROR'
  coverage_state  text,                   -- GSC's human verdict, e.g. "Submitted and indexed"
  google_canonical text,                  -- Google-selected canonical (mismatch = a flag)
  last_crawl_time timestamptz,
  last_checked_at timestamptz not null default now(),
  raw             jsonb,                  -- full inspection response (debug)
  unique (company_id, url)
);
create index on marketing_gsc_pages (company_id, index_status);

-- Cached per-site rollup so the card doesn't COUNT on every load
create table marketing_gsc_coverage (
  company_id            uuid primary key,
  total_urls            int  not null default 0,
  indexed_count         int  not null default 0,
  not_indexed_count     int  not null default 0,
  sitemap_submitted     boolean default false,
  sitemap_url           text,
  sitemap_last_submitted timestamptz,
  last_run_at           timestamptz
);
```
RLS: scope both by `company_id` to the authenticated user's company, same policy shape as the Ads tables.

### 3.4 Population (we build)
- New pipeline cron `gsc_sync.py` (mirrors `ads_sync`): loop provisioned clients → run URL Inspection per URL → upsert `marketing_gsc_pages` + recompute `marketing_gsc_coverage`. **Weekly** cadence (index status changes slowly).
- **Rate limits to respect:** URL Inspection = **2,000 inspections/day** and **600/min per property**. A few-hundred-page site weekly is well within budget; we batch + back off.

### 3.5 On-demand "Re-check status" (we expose, you call)
- We add `POST /gsc/inspect` to `rank-ai-api` (authed): body `{ company_id, url }` → runs a live URL Inspection with the agency token, upserts the row, returns fresh status. You wire the button to it and refresh the row.

---

## 4. Feature B — Geo-grid Local Rankings

### 4.1 What the client sees
- A **"Local Map Rankings"** card: a map of their service area with a grid of colored pins, each showing the rank number for the selected keyword.
- **Color scale:** green = 1–3, yellow = 4–10, orange = 11–20, red = 20+ / not found.
- Controls: **keyword selector** (which keyword's grid), **date selector**, optional **before/after** compare of two scans. Headline stats: **avg rank** + **% of grid in top 3**.

### 4.2 It is NOT a Google API image — here's how it really works
There is no Google endpoint that returns this picture. It's a **geo-grid technique**:
1. Generate an *N×N* grid of lat/lng points around the business (e.g. 13×13, ~0.5–1 mi spacing).
2. For **each point**, query the **Google Maps local results at that coordinate** for the keyword, and find the client's rank.
3. Plot each point on a map, colored by rank.

- **Data source: DataForSEO** (our account, pipeline-side) — `serp/google/maps/live/advanced` with a `location_coordinate` (lat,lng,zoom) per grid point; find the business by name/place_id → its rank in the pack. (This is exactly what Local Falcon / BrightLocal do under the hood.)
- **GBP Performance API is NOT used here** and does **not** block this — GBP gives aggregate counts (calls/views/directions), not geo-grid ranks. (GBP insights is a separate future card, currently blocked on the quota-0 access form.)

### 4.3 Tables (DDL — you create these)

```sql
-- One row per grid scan (a client + keyword + timestamp)
create table marketing_geogrid_scans (
  id                uuid primary key default gen_random_uuid(),
  company_id        uuid not null,
  keyword           text not null,
  center_lat        double precision not null,
  center_lng        double precision not null,
  grid_size         int  not null,          -- e.g. 13 (=> 13x13 = 169 points)
  grid_spacing_mi   numeric not null,       -- spacing between points
  avg_rank          numeric,                -- average across found points
  pct_in_top3       numeric,                -- 0..100
  cost_usd          numeric,                -- DataForSEO spend for this scan (track it)
  scanned_at        timestamptz not null default now()
);
create index on marketing_geogrid_scans (company_id, keyword, scanned_at desc);

-- One row per grid point of a scan
create table marketing_geogrid_points (
  id        uuid primary key default gen_random_uuid(),
  scan_id   uuid not null references marketing_geogrid_scans(id) on delete cascade,
  row       int not null,
  col       int not null,
  lat       double precision not null,
  lng       double precision not null,
  rank      int,                            -- 1..20, or null = not in top 20 ("20+")
  found     boolean not null default false
);
create index on marketing_geogrid_points (scan_id);
```
RLS: scope by `company_id` (points via their scan's company_id).

### 4.4 Population (we build)
- Pipeline script `geogrid_scan.py(company_id, keyword)`: build the grid → DataForSEO Maps SERP per point → write one `marketing_geogrid_scans` + N² `marketing_geogrid_points`. 
- Cadence: **monthly auto** for each client's top 1–3 money keywords, **plus on-demand** via the app button.
- **Cost control (important):** each scan = `grid_size²` Maps SERP queries. A 13×13 grid = 169 queries ≈ **$0.30–2.00 per scan** depending on DataForSEO mode. We record `cost_usd` per scan and **rate-limit manual scans** (e.g., 1/keyword/day) so a client can't run up the bill.

### 4.5 On-demand "Run scan" (we expose, you call)
- `POST /geogrid/scan` on `rank-ai-api` (authed): `{ company_id, keyword }` → runs the grid, writes the rows, returns the new `scan_id`. You poll/subscribe and render when ready (a scan takes ~30–90s).

### 4.6 Rendering the map (your side)
- Read `marketing_geogrid_points` for the selected `scan_id`; render colored circle markers on a **Google Maps JavaScript API** map (you already use a Maps key for the site template — reuse the agency key, restricted to the app domain). Each marker = a circle colored by `rank` with the number label.
- Recommend **interactive** (Maps JS API) over a static image — it's nicer and lets you do hover/compare. A static-image export (Google Static Maps) can come later if you want shareable PNGs in reports.

---

## 5. Hard constraints / honesty caveats (do not skip)

1. **No compliant "force re-index" button for normal pages.** Google's Indexing API is officially only for `JobPosting` / `BroadcastEvent` pages; the real "Request Indexing" lives only in the GSC UI with **no public API**. So:
   - ✅ Ship **"Re-check status"** (URL Inspection) — legit.
   - ❌ Do **not** ship a button that claims to force Google to crawl/index a normal page.
   - Optional middle ground: **"Resubmit sitemap"** (we expose an endpoint) with honest copy ("asks Google to re-scan the sitemap; indexing is still Google's decision"). Don't over-promise.
2. **GSC data is agency-token-based.** Clients connect nothing; it works for every site we provision. ⇒ remove the unused `webmasters.readonly` scope from the app's OAuth request (verification hygiene).
3. **GBP insights is blocked** on the quota-0 access-request form — geo-grid does not depend on it, so geo-grid is not blocked.
4. **DataForSEO costs real money per geo-grid scan** — surface `cost_usd`, cap manual scans.
5. **Never call third-party APIs from the browser** — creds, rate limits, and cost all live server-side.

---

## 6. Suggested build order

| Phase | What | Why first |
|---|---|---|
| **1** | GSC Coverage (tables + card + re-check) | Highest trust value, lowest cost, data plumbing already exists agency-side |
| **2** | Geo-grid (tables + map + run-scan) | High visual impact; has DataForSEO cost to gate |
| **3** | GBP Insights card | Waits on the GBP quota-0 access form |

---

## 7. Open decisions (need your / Santino's call)

1. **Geo-grid map:** interactive (Maps JS API) — recommended — vs static image export?
2. **Which keywords** to auto-scan per client (default: top 1–3 money keywords from `keyword-research.json`)?
3. **Geo-grid grid size + spacing** default (recommend 13×13 @ ~0.75 mi for a metro service area)?
4. **Manual-scan gating** — per-keyword/day cap to control DataForSEO spend (recommend 1/day)?
5. Confirm `company_id` is the right join key on your side for these new tables (it matches `marketing_sites`).

---

## 8. What Rank AI delivers to unblock you

- The `marketing_*` table DDL above (you run the migration; ping us if you want us to draft the exact migration file).
- The population jobs: `gsc_sync.py` (weekly) + `geogrid_scan.py` (monthly + on-demand) writing to these tables.
- Two authed endpoints on `rank-ai-api`: `POST /gsc/inspect` and `POST /geogrid/scan` (+ optional `POST /gsc/resubmit-sitemap`).
- Confirmation of the `company_id` ↔ site mapping.

You build: the migration, the two dashboard cards, and the calls to those two endpoints.
