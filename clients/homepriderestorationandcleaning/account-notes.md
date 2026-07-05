# Home Pride Restoration and Cleaning — Account Notes

## Ranking targets

### Heber City, UT + Park City, UT — added 2026-06-23
Client wants to rank for **Heber City** and **Park City** (Wasatch / Summit counties — an
eastward expansion beyond the existing Utah County / south Salt Lake Valley cluster).

Goal: blog writing + AI-search (LLM/AI Overviews) indexing for searches in those two areas.

Action taken:
- Added both cities to `service_areas` in `plan-input.json` (slugs `heber-city-ut`,
  `park-city-ut`, `primary: false`).

Follow-up to fully activate (pending):
- Re-run `plan_site.py` to regenerate URL plan, content map, and location-page stubs
  (~36 new pages: 18 services × 2 cities).
- Run `rank-ai-build-site` to render + deploy the new location pages.
- Add both cities to keyword research seeds so System 1 → System 2 produce blog posts
  targeting these areas.
- Optionally add to `geogrid-cities.json` / `geogrid-keywords.txt` for local map-rank tracking.

## 2026-07-05 — Interim brand assets (REAL LOGO STILL NEEDED)
- Client has NO real logo on file. Shipped interim assets generated in-house:
  favicon set (HP monogram, navy #0d1b3e / orange #f97316, PIL-generated) and
  a wordmark logo.png at images.homepriderestorationandcleaning.com/brand/logo.png
  (fixes the previous 404 in brand.ts logoUrl / schema / footer).
- ACTION: get a real logo from the client (or commission one) and replace
  brand/logo.png in R2 + regenerate favicons to match.
- Homepage hero swapped to branded fleet scene: brand/hero-fleet.webp
  (alternates kept at brand/hero-fleet-alt1.webp / -alt2.webp; source PNG in
  clients/homepriderestorationandcleaning/Photos/brand-hero-fleet.png).
