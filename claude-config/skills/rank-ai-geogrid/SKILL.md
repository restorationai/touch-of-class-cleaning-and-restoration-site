---
name: rank-ai-geogrid
description: Onboard a Rank AI client into local map-rank (geo-grid) tracking — the colored grid that shows where the client ranks in Google Maps across their service area, per keyword. Derives the keyword list + geocoded city list from the client's plan-input.json, looks up the business listing identity (place_id / google_cid) needed to match them in Maps results, resolves the app company_id, writes the two config files, runs a baseline scan that stores to Supabase (marketing_geogrid_*) + renders PNGs to R2, and verifies the dashboard populates. The bi-weekly cron then auto-includes the client. Use when the user says "set up geo-grid for {client}", "add geo-grid tracking", "local map rankings", "geogrid", or "rank-ai-geogrid".
---

# Rank AI — Geo-grid (Local Map Rankings) Setup

Onboards one client into local map-rank tracking. The scanning/storage/render/cron
machinery already exists (`scripts/geogrid_*.py`, `railway.geogrid-cron.toml`,
`POST /geogrid/scan`); this skill is the **client-onboarding front-end** to it.

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — change here at session start and
source the env: `set -a; . .env; set +a`.

## What it produces

```
clients/{slug}/geogrid-keywords.txt   one keyword per line (head map-pack terms)
clients/{slug}/geogrid-cities.json    [{label, lat, lng}, ...] grid centers
clients/{slug}.json -> company_id     the app companies.id ("CO-...") join key
plan-input.json brand.place_id/cid    business identity (Maps listing match)
```

Plus the baseline rows in Supabase (`marketing_geogrid_scans` + `_points`) and the
static PNGs in R2 (`images.{domain}/geogrid/...`) that the app reads via `image_url`.

## Methodology (don't change without reason)

- **13×13 grid, 6.5×6.5 mi** per city. **Zoom 12** — gives a realistic rank gradient;
  zoom 14+ produces an unrealistic top-or-absent cliff. Color scale: 1–3 green, 4–10
  yellow, 11–20 orange, 20+/absent red.
- **Cost ≈ $0.34 per (keyword × city) scan** (169 points × ~$0.002). So a run = keywords
  × cities × $0.34. **Bi-weekly** (1st & 15th) → 2 runs/month. Keep cities curated.
- Match the client in each cell by **cid → place_id → name** (why identity lookup matters).

## Pre-flight

1. Client must be **planned** (has `clients/{slug}/plan-input.json` with `services`,
   `service_areas`, and `brand.lat`/`brand.lng`). If not, run `rank-ai-plan-site` first.
2. You need the client's **app company_id** (`CO-...`, the `companies.id` from the React
   app). Ask the user if it isn't already on the client record.

## Step 1 — company_id

```bash
python3 scripts/geogrid_setup.py company-id --slug {slug}            # show resolved
python3 scripts/geogrid_setup.py company-id --slug {slug} --set CO-… # store it
```
Without a resolvable company_id the **cron silently skips the client** — so this is
required, not optional. It's stored on `clients/{slug}.json` (single source of truth).

## Step 2 — Business listing identity

```bash
python3 scripts/geogrid_setup.py identity --slug {slug} --write
```
Searches Maps for the business name at the brand location, matches the listing, and
writes `brand.place_id` + `brand.google_cid` into `plan-input.json`. If `--write` finds
nothing, the name doesn't match the listing — confirm the GBP name in `plan-input.json`.
(Skip if those fields are already present.)

## Step 3 — Derive + preview (no writes)

```bash
python3 scripts/geogrid_setup.py plan --slug {slug} [--max-keywords 10]
```
Prints the derived **keywords** (head terms from the client's services, ranked by tier
then priority) and the **geocoded cities** (all service areas), with a **cost table**.

**Show the user the keywords and cities. Get approval / edits before applying.** Two
decisions:
- **Keywords** — the derivation is a starting point. Trim/add to match what people
  actually search in this market (the user knows their leads).
- **Cities** — this is the cost lever. All service areas is usually overkill; default to
  the **primary market + 1–3 strategic ones** (e.g., a city where they want to grow).
  Show the per-run cost for the chosen count.

## Step 4 — Apply (write the config files)

```bash
python3 scripts/geogrid_setup.py apply --slug {slug} \
    --cities "Federal Way, WA;Tacoma, WA" [--max-keywords 10]
```
Writes `geogrid-keywords.txt` + `geogrid-cities.json`. (Hand-edit the keyword file after
if the user wanted specific additions like "near me" variants.)

## Step 5 — Baseline scan + verify

```bash
python3 -u scripts/geogrid_cron.py --slug {slug}      # scans every kw × city, stores, renders, uploads
```
Run in the **background** (~30–45s per keyword×city; a 10×2 run ≈ 10–12 min). Then verify:
- Supabase: `marketing_geogrid_scans` rows for the company_id (one per kw×city), each with
  a non-null `image_url`; `marketing_geogrid_points` has 169 rows per scan.
- R2: one of the `image_url`s returns HTTP 200 `image/png`.
- Report the DataForSEO spend (the cron prints it).

The **Overview** dashboard populates immediately. The **Compare** (before/after) view needs
a second dated snapshot — it fills in on the next bi-weekly run.

## Step 6 — Hand off to the cron

No action needed: the bi-weekly cron (`railway.geogrid-cron.toml`, `0 8 1,15 * *`)
auto-includes **any** client that has both config files + a resolvable company_id. Confirm
to the user that ongoing scans are automatic; on-demand refreshes go through
`POST /geogrid/scan { company_id, keyword, city_label }` (1/keyword/city/day).

## Guardrails

- **Cost**: always show the per-run estimate (keywords × cities × $0.34 × 2 runs/month)
  before the baseline scan. Don't scan all service areas by default.
- **Supabase**: only `marketing_geogrid_*` (and the company_id join). Never touch other tables.
- **Don't overwrite** an existing `geogrid-keywords.txt`/`geogrid-cities.json` without showing
  the diff and getting an OK.
- **Idempotent**: re-running `plan` is free (no writes). `apply` overwrites the two config files.

## Known tech-debt (fix opportunistically)

`company_id` is still hardcoded in `COMPANY_MAP` inside `geogrid_store.py`,
`supabase_sync.py`, and `api/runner.py`. `geogrid_setup.resolve_company_id()` already reads
it from the client record first (falling back to the map). The cleanup is to point those
three maps at `resolve_company_id()` so adding a client is config-only — do it when you next
touch those files.
