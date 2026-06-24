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
