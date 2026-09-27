---
name: client-bootstrap-system
description: Sales-to-ops bootstrap — scripts/bootstrap_client.py one-command + client_ops_sync auto-backstop; built 2026-07-21
metadata:
  type: project
---

The "Gregory gap": companies created mid-demo had NO slug/upload-link/intake/marketing_sites → app looked empty, links said "no Rank AI slug". Fixed 2026-07-21:
- `scripts/bootstrap_client.py --company-id CO-... [--slug s] [--domain d]` = full handoff: company_map + clients/{slug}(.json) + plan-input (place_id from google integration) + marketing_sites row + KV upload link + standard intake items + gbp.py sync.
- `client_ops_sync.ensure_bootstrapped()` backstop (runs with nightly ops sync): auto-creates marketing_sites+KV for Active companies with wizard artifacts (integration_settings.goals|lp_consent), reusing pipeline slug via slug_map(); excludes name ~ test|trachawk|xyz; emails alert to finish repo half. marketing_sites.domain NOT NULL → placeholder "{slug}.invalid" until real domain.
- Bootstrapped: puroclean-east-las-vegas (Greg), transformation-remodeling (Derek), paul-davis-charleston (Kenny — Leakproof but keeps bootstrap for review engine). servicemaster-restore + drytech UNWOUND (receptionist plans); backstop now gated plan=eq.Rank AI. hub_url in integration_settings for all 12 mapped clients; top-nav button = Client Hub. Header strip REMOVED (Queue/Published -> Content tab). Domains: WE absorb phantom-domain cost (~$13, Santino agreed 07-21); premium domains ask first. Docs-intake upgrade for hub QUEUED (accept PDFs/COI for LSA, category folders, auto-complete intake items, 'already received' list).
- Baseline audit reports inserted into marketing_reports ("Baseline — July 2026") for Greg + Derek; weekly progress job still to build. Wizard bug fixes MERGED to app main 2026-07-21 (Santino approved): real Google client-id fallback, /brand + /job-photos folders, widget_logo_url persist, theme -> integration_settings.theme, top-nav UploadLinkButton.

## Progress reports (P6b, LIVE 2026-07-21)
- scripts/progress_report.py: weekly per-client baseline-vs-now (reuses lead_audit run_rankings/run_ai_search on the SAME keywords/questions; reviews via marketing_gbp_profiles else gbp_by_id; content count from marketing_content). Petrol-branded HTML -> R2 lead-audits/{aid}/progress-YYYYMMDD.html -> marketing_reports row "Progress — <date>". Gates: skip if last progress <6d OR baseline <6d (no all-zero day-2 reports). Scheduler: ops_scheduler DAILY_JOBS "progress" 15:00 UTC.
- baseline_audit_id lives in companies.integration_settings (set for Greg 00a41a898a1c + Derek 2b1c77214c4d). First real reports ~Jul 27-28.
- Stripe->GHL confirmed: stripe-webhook fires GHL success/failed webhook triggers + tags contact trial/paid; 'client secured' presumably added by the success-trigger workflow — Santino adding kickoff-prep webhook there. Domains: absorb cost ourselves (<=$50 auto, premium ask first).

## Domains + geo-grid (2026-07-21/22)
- Domain purocleaneastlasvegas.com bought NATIVELY on GoDaddy (in-app purchase blocked by wallet INVALID_BILLING_ADDRESS even after billing fix — buy path UNVALIDATED; search/pricing path works). Santino set CF nameservers (amos/anastasia) himself; marketing_sites/zone records correct. Next domain: retry in-app; if wallet error persists, swap purchase backend to Porkbun/Name.com behind the same card UI. GoDaddy legacy API key is DEAD (2024 lockdown) — PAT Bearer on api.godaddy.com/v1 is the working auth. INVALID_BILLING_ADDRESS = GoDaddy wallet payment-profile fields, fixed account-side then retry.
- Geo-grid cadence: geogrid-cron Railway cron '0 8 1,15 * *' = 1st + 15th monthly (BIWEEKLY, not nightly). bootstrap_client now seeds geogrid-keywords.txt + geogrid-cities.json + runs first scan immediately. Greg scanned 07-21: mold removal N.LV avg 8.4, top3 28%.
- kickoff-prep now ALSO fires from signup-alert (account creation) — covers closes with no booking AND no subscription (Greg had 'client not yet secured').
- NEXT HEADLINE: Greg's site plan+build (domain live; brand guide + team photo pending via intake), then P3 wizard redesign, P4 docs intake on hub.

## ghl-sync-contact identity guard (2026-07-22)
- BUG: fuzzy GHL ?query= search let an office/day-to-day wizard entry match the OWNER's contact (shared phone) and rewrite name/email/phone (RestorationXpress: Isaac's record renamed to Jaziel). Both app entries also got BOUND to the owner's ghl_contact_id -> would re-clobber on every sync.
- FIX (deployed): office entries NEVER rewrite existing GHL records (tag-only 'rank-ai-office-contact'; create separate contact when no email-verified match); fuzzy matches require email agreement (owner may also match by E.164 phone); stored ghl_contact_id checked first. RULE from Santino: app contacts (integration_settings.contacts, preferred flag) = source of truth for WHO to contact; GHL is only the channel.
- RestorationXpress (CO-1784745317157, slug restorationxpress) bootstrapped 07-22: owner Isaac Nahum isaac@restorationxpress.com +19542003027 (GHL QCqxrFadwsbVURspLBcB), day-to-day Jaziel (preferred, jaziel@, 786-439-7604). No Google connect yet -> GBP/geo-grid pending; kickoff-prep fired via signup-alert path (first live test), transcript poll in flight at time of writing.

## Fully automated (2026-07-22)
- .github/workflows/bootstrap-new-clients.yml: every 2h, `client_ops_sync.py --bootstrap-only` runs the FULL bootstrap_client.py (repo half included — CI has GH_PAT commit rights, unlike the Railway worker) for any Active plan='Rank AI' company missing marketing_sites. Validation run green. New-signup timeline: account created -> kickoff-prep on transcript landing -> full setup <=2h -> maps minutes later -> progress report day 7. Manual bootstrap_client.py remains for instant/custom-slug cases.

## In-app site builds (2026-07-22, Isaac = pilot, NOTHING manual for him)
- App Site tab (superadmin): SiteBuildCard = brief (theme, brand colors w/ "use my current website's colors" extractor, city add/remove chips) + attach-existing-domain input + Build Site button. API: /site-brief/extract-colors (palette from client's live site CSS), /domains/attach (existing domain + CF zone pre-create), /site-build (validates brief+domain, dispatches GH workflow, build_status=queued).
- .github/workflows/site-build.yml: brief->plan-input (scripts/site_brief_build.py, Claude-enriched area profiles few-shot from restoration-groups) -> plan_site generate -> build_site scaffold(first only)/add-pages/render -> sync-deploy --branch staging -> build_status=preview_ready + email w/ staging URL. Production push + NS cutover stay HUMAN-GATED (no Go Live button yet — production via manual sync-deploy main for now).
- Isaac test path: 5173 -> RestorationXpress -> Site tab -> extract colors (his green) -> confirm cities (Davie + Broward/Miami-Dade picks) -> attach restorationxpress.com OR buy phantom -> Save Brief -> Build Site. FIRST RUN WILL SURFACE PIPELINE GAPS (scaffold/CI env) — expected, fix forward. App card committed locally, NOT pushed to prod (Santino tests on 5173 first).
