---
name: ga4-clarity-provisioning
description: GA4 is provisioned via a service account (no OAuth grant needed); Clarity is manual. Per-client measurement IDs + how to deploy analytics tags.
metadata: 
  node_type: memory
  type: reference
  originSessionId: effad5a0-121f-4b23-8ed3-55145af07a14
---

**GA4 = service account, NOT OAuth.** Earlier notes said "we have no service account" — wrong. `claude@restoration-ai-analytics.iam.gserviceaccount.com` has **Editor** on the "Restoration AI" GA4 account (`accounts/397914758`). Editor is enough to **create properties** — no admin upgrade, no OAuth consent flow needed.

- Key: `.secrets/ga4-sa.json` (gitignored, copied from ~/Downloads/restoration-ai-analytics-*.json).
- `.env`: `GOOGLE_ANALYTICS_SA_KEY=<path>` + `GOOGLE_ANALYTICS_ACCOUNT_ID=397914758`.
- `scripts/create_ga4.py` uses the SA via `access_token()` → `create_ga4.py --slug X` creates property + web stream + writes the measurement ID into `sites/X/src/lib/brand.ts` + plan-input.
- Deploy the tag live: `build_site.py sync-deploy --slug X --branch main` (sites/{slug} is a monorepo SUBDIR, so a plain git push pushes the monorepo, not the client site — must subtree-deploy). The gtag is wired in `templates/astro-starter/src/components/Analytics.astro` (no-op until id set).

**Live per-client GA4 measurement IDs (created 2026-06-27):** narestco `G-5N8L5D4Z3C` · davis-construction `G-BRL1Q2KTGV` · homepriderestorationandcleaning `G-6X1L63FBE5`. (Agency funnel properties already existed: restorationai.io, Opt Digital Funnel, Quiz Funnel.)

**Microsoft Clarity = manual.** No project-creation API. Create each project at clarity.microsoft.com, then `analytics_set.py --slug X --clarity <id> --push` writes `clarityProjectId` into brand.ts (same Analytics.astro tag). narestco Clarity project = `xdoigoc8of` (live).

**GA4 numeric property IDs (for Data API runReport queries — distinct from the G- measurement IDs):** narestco = `543376986`. Stored in `clients/{slug}.json` → `analytics.ga4_property_id`. Query with `.secrets/ga4-sa.json` (the config.env `GA_SA_PATH` is STALE — points at deleted Restoration-AI-website-2026-main/.ga4-sa.json; use `.secrets/ga4-sa.json`). The SA must be granted Viewer on each client property or runReport 403s.

**Clarity Data Export token is PER-PROJECT** (scoped to the single project it's generated in — Clarity → Settings → Data Export). narestco's token saved as `NARESTCO_CLARITY_TOKEN` in `.env`. Each other client needs its own token. API: `GET https://www.clarity.ms/export-data/api/v1/project-live-insights?numOfDays=1..3[&dimension1=URL|Source|Device]` with `Authorization: Bearer <token>`. Returns DeadClickCount/RageClickCount/ScrollDepth/EngagementTime/Traffic. Gotcha: strip any trailing `.` (sentence punctuation) — a JWT must have exactly 2 dots or you get HTTP 403.

Same SA key can read GA4 data (Data API) for a future GA4 card in the app's Analytics tab. See [[gbp-optimizer-system]] for the broader marketing-app context.
