# Run blockers: arch-enviornmental-group-llc, seed "mold testing", 2026-08-31

Research completed and banked. **Content queue held at 0 items.** Reasons below,
in the order the keyword-researcher methodology checks them.

## 1. Client record fails the activation gate (blocking for queue)

`clients/arch-enviornmental-group-llc.json`:

- `status: "onboarding"` (methodology requires `"active"`)
- `plan_status` absent (methodology requires `"planned"`)
- `domain: null`
- `build_status` absent

## 2. plan-input.json has no services truth table (blocking for queue)

`clients/arch-enviornmental-group-llc/plan-input.json` contains only a `brand`
block (display_name, lat, lng, place_id). It has no `services[]` and no
`service_areas[]`.

Consequences:

- The hard rule "never queue a topic for a service that is NOT in plan-input
  services" cannot be satisfied by any keyword, because the service list is
  empty. Queueing anything would be queueing against an unwritten truth table.
- Step 4 priority-1 criterion "for local queries, city must be in this client's
  `service_areas[]`" cannot be satisfied. All 10 city-modified keywords were
  therefore capped at priority 2 or 3 even where volume and KD qualified
  (notably `mold testing fresno`, volume 70, KD 0, CPC 13.51).
- `service_tags` and `internal_link_targets` for queue items cannot be resolved.

## 3. Coverage check (Step 5) could not run (blocking for queue)

`clients/arch-enviornmental-group-llc/plan/url-plan.json` does not exist, and
the site is not live (`domain: null`), so the sitemap fallback is unavailable.
Every banked keyword has `covered_by: null` by default, not by verification.
All priority-1 assignments in this run are provisional pending the coverage pass.

## 4. Wizard goals unavailable (non-blocking, degraded input)

`companies.integration_settings.goals` for company_id `CO-1788198240333` could
not be read: no `SUPABASE_URL` or service-role key is present in this CI
environment. Substitute signal used for the client-stated priorities:

- `clients/arch-enviornmental-group-llc/geogrid-cities.json` gives one city:
  Kingsburg, CA (36.5138398, -119.5538929), Fresno County.
- `clients/arch-enviornmental-group-llc/geogrid-keywords.txt` gives two
  owner-configured tracking terms: `mold testing`, `lead testing`.

These two terms are the only owner-stated service signal available, so
`mold testing` was chosen as this run's seed over the file-order default
(`water damage restoration`). `lead testing` is the recommended next seed.

Flagged mismatch: `mold testing` and `lead testing` are owner-configured, but
neither can be confirmed against plan-input `services[]` because that list does
not exist. `lead paint removal` and `asbestos abatement` exist in the shared
restoration seed list and fit the "Arch Environmental Group" positioning, but
they remain unconfirmed as sellable services for this client.

## 5. Ads-side keyword data absent (non-blocking)

`clients/arch-enviornmental-group-llc/keyword-research.json` does not exist, so
the PPC money-keyword override (Step 4) did not run. No keyword carries
`ppc_validated: true` in this run.

## 6. DataForSEO failures logged during the run (non-blocking)

- `POST /v3/ai_optimization/chat_gpt/llm_scraper/live/advanced` for
  `"mold testing cost and when to hire a professional mold inspector in Fresno
  County California"`: status 50401, Internal Error - Timeout.
- `POST /v3/ai_optimization/chat_gpt/llm_scraper/live/advanced` for
  `"how much does professional mold testing cost"`: status 50401, Internal Error
  - Timeout.
- The first scraper call (`"mold testing"`) succeeded and supplied the AI
  decomposition used for the question-format quota.
- Tool-name note: the methodology names `mcp__dfs-mcp__*` tools. Those are not
  present in this environment. Equivalent endpoints were called through
  `mcp__dataforseo__api_request`: `dataforseo_labs/google/keyword_ideas/live`,
  `dataforseo_labs/google/related_keywords/live`,
  `dataforseo_labs/google/bulk_keyword_difficulty/live`,
  `keywords_data/google_ads/search_volume/live`, and
  `ai_optimization/chat_gpt/llm_scraper/live/advanced`.

## What unblocks the queue

1. Populate `plan-input.json` with `services[]` (slugs from
   `templates/restoration/services.json`) and `service_areas[]` (Kingsburg CA as
   primary, plus the Fresno County cities actually served).
2. Generate `plan/url-plan.json` so the intent-aware coverage check can run.
3. Flip `clients/arch-enviornmental-group-llc.json` to `status: "active"` with
   `plan_status: "planned"` and a real `domain`.

Then re-run the keyword researcher with `--force` on seed `mold testing`; the 12
priority-1 keywords already banked will be re-scored against the real truth
table and coverage map, and the top 10 will queue.
