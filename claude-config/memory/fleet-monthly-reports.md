---
name: fleet-monthly-reports
description: "Per-client monthly results pages — client_report.py, Railway /report front door, monthly workflow; Supabase public storage refuses to render HTML"
metadata: 
  node_type: memory
  type: project
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-08-30T14:18:00.313Z
---

LIVE 2026-08-30 (Santino: "systematically for every client, not my machine"). `scripts/client_report.py --all|--slug X [--period YYYY-MM]` renders one styled results page per active Rank AI client: GSC 28d-vs-prior (agency token via gsc_setup paths; sc-domain:{clients/{slug}.json domain}), review-campaign progress (same processed formula as app card), work delivered (marketing_work_log, col is **ts** not created_at, category neq reporting; + marketing_gbp_changes counts), live citation_listings. Sections render only when data exists; "nothing reportable" clients skipped. First fleet run: 27 published.

**Serving gotcha**: Supabase PUBLIC storage serves stored HTML as text/plain + nosniff no matter what mimetype the object carries (XSS policy) — reports upload to `client-reports` bucket but serve through the Railway API front door `GET /report/{company_id}/{fname}` (api/main.py; auth = unguessable token in filename, crew-hub model). Registry: `marketing_client_reports` (unique company_id+period; regenerate = same URL, "refreshed", no duplicate ledger line). One work_log line per NEW report ("Your {Month} results report is ready: {url}") so the app Reports feed + Monica carry the link.

Schedule: .github/workflows/client-reports.yml — 1st of month 16:00 UTC + workflow_dispatch (slug/period inputs); GSC creds via secrets GSC_AGENCY_TOKEN_JSON / GSC_OAUTH_CLIENT_JSON. PostgREST trap fixed twice here: '+00:00' in a URL query = space → 400 → use strftime Z. Queued idea (Santino): Monica biweekly SMS pointer to the report page per client. [[gbp-optimizer-system]] [[client-concierge]]
