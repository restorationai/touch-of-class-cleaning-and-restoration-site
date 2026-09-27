---
name: gbp-optimizer-system
description: "AI GBP optimizer + page-build automation — grounded suggestions, app panel, and the scheduled gbp-maintenance pipeline"
metadata: 
  node_type: memory
  type: project
  originSessionId: effad5a0-121f-4b23-8ed3-55145af07a14
  modified: 2026-08-29T16:34:57.919Z
---

Shipped to production 2026-06-26. An AI layer that audits each client's Google Business Profile and reconciles it with their website, grounded in what the client actually offers.

**Ground truth:** `companies.services` / `companies.negative_services` (set by clients in the app's "Services & Area" tab). Never suggest a `negative_services` item; categories always human-gated.

**Ruleset (editable):** `GBP/rank-ai-gbp-best-practices.md` — loaded as the system prompt. Key rules: categories 3-10 + human-gated; MERGE only true duplicates (keep distinct long-tail services); structured `job_type_id:` items are canonical KEEP (merge free-form into them).

**Engine:** `scripts/gbp.py`
- `optimize --slug|--all` → AI classifies every category/service/gap into KEEP/ADD/REMOVE/MERGE/NEEDS-REVIEW (+reason, confidence) → `marketing_gbp_suggestions` table. Deterministic guardrail overrides model on negatives; `auto_safe` = grounded high-confidence non-category service change.
- `create-pages --all [--build]` → drains `marketing_page_requests` queue → adds service to plan-input, `ensure_catalog_entry()` self-heals `templates/restoration/services.json`, then (with --build) plan_site generate → build_site add-pages (only NEW files, never destructive scaffold) → render (best-effort) → commit → sync-deploy main.

**App (live):** `MarketingSuggestions.tsx` in Marketing > Locations — "Vetted / Needs review / Create website pages"; edge fns `gbp-add-service` (add+remove[]) and `gbp-create-page`. See [[rank-ai-kpi-dashboard]] for the broader app.

**Scheduled:** `.github/workflows/gbp-maintenance.yml` — Mon 10am PT (cron `0 17 * * 1`): optimize --all + create-pages --all --build. Also manual via workflow_dispatch.

**Gotchas learned:** build_site `scaffold` OVERWRITES every page with a placeholder (use `add-pages` for incremental); `plan_site` DIES on slugs not in the catalog (hence self-heal); sync-deploy needs a clean tree + committed pages (subtree split over committed history); optimize must be per-client resilient (one bad Anthropic response shouldn't abort --all).

**2026-08-29 AUTO-APPLY EXECUTOR (4820be67)**: `gbp.py auto-apply --slug|--all` executes open auto_safe SERVICE suggestions unattended — Santino 08-26 flip: service adds/removals/descriptions/attributes full-auto; name/categories/address/pages stay one-click. ADDs via add_services(); REMOVEs ONLY when whole-phrase-matched to declared negative_services (other REMOVEs left open — wrong removal costs rankings); MERGE removes dup phrasing only when canonical live. Cap 12/client/run. Documentation contract: every change → marketing_gbp_changes row (GbpChangeLog.tsx Reports feed + monthly summary) AND suggestion stamped 'applied — AUTO-APPLIED {date} (optimizer, auto-safe)' so the app board = review ledger. Wired into gbp-maintenance.yml after optimize step; first fleet run 08-29: 49 adds across 12 clients, 7 negative-backed removals, 2 correctly held for click. Also: create-pages now re-picks orphaned 'building' rows (killed-run self-heal); workflow timeout 60→300 min (city×service drains).

**2026-07-24 reviews + post images (gbp.py / gbp_post.py):**
- Reviews in `marketing_gbp_reviews` were FROZEN (DFS `reviews` cmd was never scheduled). Now `sync_reviews_v4()` rides `sync --all` (Mon+Thu): pulls ALL reviews from GBP v4, WHOLESALE-REPLACES the company's rows (DFS md5 ids can't merge with v4 reviewIds), patches profile rating/review_count/last_review_at. DFS path is fallback for unconnected clients only.
- `import_gbp_media()` (also rides sync + `media-import` CLI): client's GBP photo library → `branding/{cid}/job-photos/posted/gbp-{key}.jpg` (skips PROFILE/COVER/LOGO + our own supabase-sourced uploads). MUST land in posted/, never root — gbp_photos.py drains root UP to GBP (would dupe their own photos).
- ⚠️ Supabase Storage move/rename PRESERVES created_at — any LRU keyed on created_at silently degenerates to "same file forever" (why NaRestCo posted one photo for a month). gbp_post `next_job_photo` now sorts posted/ by the `r{epoch}_` filename prefix instead.
- App Locations→Profile = GBP management HUB (2026-07-25): inline edit description (gbp-update-profile fn), add/remove categories vs taxonomy, add/remove free-form services, write/EDIT review replies in-app (gbp-reply-review fn, v4-synced rows only). Primary category deliberately NOT editable (re-verification risk).
- Optimizer now: (a) proposes NEW categories — taxonomy-validated, gcid in `canonical`, never auto_safe, applyable from MarketingSuggestions (caught ProRestoration missing "Water damage restoration service" entirely); (b) audit payload includes _geogrid_summary (per-keyword avg rank/top-3 + trend) — reasons cite grid position; (c) AI description suggestions (auto-push only when empty).
- ⚠️ Geo-grid summaries MUST group by (keyword, city_label): clients get same-day scans around multiple centers (NaRestCo: Federal Way + Tacoma) — keyword-only grouping fabricated a "7.55→14.63 decline" that was just two cities. prev_* only from an earlier scan DAY of the same city. App dashboards default to the client's HOME city (parsed from marketing_gbp_profiles.address).
- ⚠️ GBP categories taxonomy filter accepts ONE token only: multi-word `displayName=X Y` 400s, quoted is silently IGNORED (returns unfiltered list). Search the longest word, exact/rank-match locally. Fixed in gbp.py + gbp-update-profile.
- Campaign card: click↔review "likely" matching (first name + ≤10d window, amber "review?" chip, always framed likely).
