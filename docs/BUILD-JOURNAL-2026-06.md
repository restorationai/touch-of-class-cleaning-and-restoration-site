# Rank AI — Build Journal (June 2026)

Internal build/handoff doc. Captures what we built, why, where it lives, and what's
queued — so a fresh conversation (or teammate) can pick up cold. Date range:
**~2026-06-15 → 2026-06-25** (this build sprint). Newest context at top of each section.

---

## 0) System map (so you know where things live)

- **Pipeline monorepo** (this repo): `~/Desktop/mywebsitecode/rank-ai/` → GitHub `restorationai/Rank-AI-Pipeline`. Scripts (`scripts/*.py`), templates, per-client state (`clients/{slug}/*`), Astro sites (`sites/{slug}/`), FastAPI backend (`api/`), Railway cron configs (`railway.*.toml`), GitHub Actions (`.github/workflows/`).
- **Client React app** ("the app"): GitHub `restorationai/Restoration-AI-APP` (Vite+React+TS, Netlify, deploys on push to `main`). **ALWAYS pull from GitHub, not the desktop `-main` folder.** Local dev clone used for testing: `~/Desktop/mywebsitecode/Restoration-AI-APP-main` (it IS a real git clone; we checkout branches there + `npm run dev` on **localhost:5173**).
- **Supabase** (the app's DB + edge functions): project **`nyscciinkhlutvqkgyvq`** ("Restoration AI App"). Access via `SUPABASE_ACCESS_TOKEN` (sbp_… in chat — rotate when convenient) for CLI/Management-API; runtime via `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (in `rank-ai/.env`). App data lives in `marketing_*` tables; RLS pattern = `company_id = get_effective_company_id()`.
- **Per-client sites**: `restorationai/{slug}-site` repos → Cloudflare Pages → apex domain. Images on R2 `images.{domain}`.
- **Crons**: Railway runs ads/geogrid/refresh/supabase-sync + the FastAPI app. **GitHub Actions `weekly-maintenance.yml` (Mon+Thu 16:00 UTC)** runs `master_scheduler.py run-due --all --headless` (Systems 1–4) **then `strategist.py --all`**.

## 1) Working conventions (IMPORTANT)

- **App testing loop** (per Santino): after ANY app change → push a feature branch → checkout in the desktop clone → restart `npm run dev` on **5173** → tell Santino what to click. **Only merge to `main` after he confirms on localhost.** Don't ask each time — just serve it. (Memory: `auto-localhost-testing`.)
- Backend/edge-function changes deploy straight to Supabase (no localhost equivalent).
- After a feature merges, switch the desktop clone back to `main`.
- Commit/push only relevant files; `kpi-dashboard/` untracked folder is unrelated — leave it.

## 2) Identity / access facts

- **OAuth client** (Google): `936081984190-6p9t4du982u4lh7purv34t8gcbnshig9.apps.googleusercontent.com` (GCP project number **936081984190** — same project as the GBP API application). Authorized redirect URIs include `https://app.restorationai.io/connect/google/callback` and `http://localhost:5173/connect/google/callback`.
- **Supabase function secrets set this sprint**: `CONNECT_LINK_SIGNING_SECRET`, `CONNECT_APP_ORIGIN=https://app.restorationai.io` (GOOGLE_CLIENT_ID/SECRET, SUPABASE_URL/SERVICE_ROLE_KEY already existed).
- **GitHub Actions secrets added** (Rank-AI-Pipeline): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (for the scheduled strategist).
- **company_id map** is now centralized: `clients/company_map.json` (narestco=CO-1771290587387, davis-construction=CO-1778778644861, homepriderestorationandcleaning=CO-1780333664867). probritegen = churned (excluded). Test company in app: XYZ Restoration = CO-1766552577794.

## 3) What we built this sprint (by feature)

### Home Pride — Heber City + Park City expansion (DONE, live)
Added 2 service areas → re-plan (229→267 URLs) → rendered 38 new pages → pushed to prod (apex live). First blog post published (ice-dam-removal-park-city). Geo-grid baselined for the 2 new cities (all `found=0/169` — expected for new markets; $6.48). **App marketing-tab fix**: recorded the apex cut-over (`cut_over_at`/`apex_cutover`, build_status→cut_over) so `supabase_sync` computes `apex_live=true` and the site shows in the app. Reapplying for **GBP API** with Home Pride's listing (its GBP Website already = the Rank AI domain; the prior app was rejected for listing/website mismatch — used restorationai.io). See memory `gbp-api-access-reapplication`.

### Scheduler hardening (DONE, in prod via GitHub Actions)
`scripts/master_scheduler.py`: System 1 cadence 30→**14 days**, added a **queue-low trigger** (System 1 becomes due when queued < 4, evaluated each Mon/Thu run — refills before System 2 in the same pass), and an **empty-queue email alert** (SendGrid, via the same path as `notify_failure.py`) when a client is still < 2 queued after a run. Refilled davis + narestco content queues (System 1, seed = mold remediation).

### narestco ads cleanup (DONE, live account) + systemic fixes
- **Geo bug**: 6 of 10 targeted cities were the WRONG STATE (Auburn AL, Kent CT, Bellevue IA, Kirkland IL, Everett MA, Redmond OR). Fixed live (→ WA) on all 3 SKAGs. **Root cause fixed systemically** in `ads_manager.geo_lookup()` — now state-disambiguated (matches `canonical_name`), skips if no city+state match (never wrong-state). Both call sites pass state.
- **87 negatives** (29 unique × 3 SKAGs) for junk/competitor/out-of-area terms. Added national franchises (coit/voda/delta/ars) to `Ads/universal-negative-keywords.md` D.1 + cert/product terms to B.6.
- **Call tracking unified**: created a Google call asset (id 378508981599) = the **Twilio tracking number 253-338-5162** on all 3 SKAGs (conversion reporting preserved → conversionActions/7371348636). Now ad-button calls route Google forwarding → Twilio (recorded) → real line, AND keep Google campaign/keyword attribution. ⚠️ **OPEN LEGAL**: WA two-party consent — Twilio recording has NO disclaimer yet (`recording_disclaimer:false`); add a notice to `narestco.com/twilio/voice` before relying on recordings (operator deferred).
- **LSA** is suppressed by **verification**, not bids: `INSURANCE: FAILED` + `BACKGROUND_CHECK: CANCELLED`. Fix is manual in localservices.google.com (re-submit insurance, complete background check) + LSA reviews/responsiveness. Do NOT raise LSA budget.
- The 6/23 "1 conversion" was a **real call** (Calls from ads / Google forwarding → main line), no recording because Google doesn't record + it bypassed Twilio (now fixed).
- **Location assets**: narestco's correct GBP is already account-linked (asset set "Google Maps" 9118232479). Map-pack absence = Ad Rank, not missing location. **Systemic**: added `ads_manager.ensure_location_assets()` (place_id-matched, fail-safe skip) wired into scaffold so future clients get map-pack eligibility with the correct GBP.
- **ads_review.py vet bug fixed**: `max_tokens=2000` truncated the JSON → all terms kept unvetted (silently degraded nightly auto-negatives for ALL clients). Now token budget scales + salvage parser.

### Standalone OAuth connect-links (DONE, live in prod)
Clients connect Google Ads/GBP/Search Console/YouTube via an emailed/texted link, **no app login**. Model approved: **one-time HMAC-signed links**, reuse the existing `/connect/google/callback` redirect URI (zero GCP change).
- App: `supabase/functions/connect-link-start` (public; verifies HMAC, redirects to Google), `connect-link-exchange` (public; verifies HMAC + one-time `connect_links` row, stores refresh token in `user_integrations`), `connect-link-generate` (authenticated; "Copy Connection Link" button mints links server-side so the secret never hits the browser). `connect_links` table (one-time, RLS service-role-only). `GoogleOAuthCallback.tsx` branches on a `clk_` token (skips session). `/connect/` made public in `App.tsx`. **"Copy Connection Link"** button on the Connect tab (admin/superadmin/owner).
- Pipeline: `scripts/generate_connect_link.py` (CLI minter; `--origin` allowlist incl. localhost for testing).
- Token = `b64url(payload).b64url(HMAC_SHA256(secret, b64url(payload)))`, payload `{cid, p, jti, exp, o}`. Signed `origin` allowlisted to prod + localhost.
- **Verified end-to-end** on localhost for both Google + YouTube (tokens stored under CO-1766552577794, `connected_via=standalone_link`).
- ⚠️ Clients see Google's "unverified app" warning until the **OAuth consent screen is verified** (Advanced→Continue; refresh tokens persist). Verification is a queued task (needs Google Cloud Console MCP).

### Strategist — System 0 (DONE v1, scheduled) + Action Plan UI
- `scripts/strategist.py`: per client, gathers signals (geo-grid weak cells, content-queue depth + uncovered priority-1 keywords, onsite-audit verdict), ranks actions by impact/effort, writes to **`marketing_action_plan`** (Supabase). `--all` runs every active client. Stable `action_key` so re-runs don't resurrect dismissed actions or lose pins. **Scheduled** in weekly-maintenance after S1–S4.
- App: **"Action Plan"** tab (first in Marketing nav) `components/MarketingActionPlan.tsx` — ranked plan, impact/system badges. **Dismiss + Prioritize** controls (admin/superadmin/owner): Dismiss = remove (won't resurrect); Prioritize = pin to top. Pinned-first ordering. `marketing_action_plan` cols incl `pinned`, `action_key`.
- **Model = hands-off**: actions run autonomously; humans only Dismiss/Prioritize (scales to 30+ clients; clients rarely log in). Safe actions (blog/keyword/video/GBP-post) auto; money/listing changes flagged-only.

### Content scheduled date + sorting (DONE, live)
`marketing_content_items.scheduled_for` populated by `supabase_sync` from the Mon/Thu cadence (FIFO by queued_at). Content tab shows "Scheduled · <date>" and sorts queued posts soonest-first.

### AI-search rank tracking (IN PROGRESS — spike done)
- **Spike validated**: DataForSEO `ai_optimization_chat_gpt_scraper` (force_web_search) returns ranked businesses + cited sources + brand entities. Proof: **narestco = #1** ChatGPT for "water damage Federal Way"; **Home Pride absent** for "Park City" (matches geo-grid). Gives client-cited?/rank/competitors/sources.
- **Table created**: `marketing_ai_search_scans` (engine, query, cited, client_rank, competitors jsonb, cited_sources jsonb, answer_excerpt, scanned_at; RLS select by company).
- **Collector BUILT + tested**: `scripts/ai_search_scan.py` — REST `POST /v3/ai_optimization/chat_gpt/llm_responses/live`, model `gpt-4o`, `web_search=true`. **Cost ≈ $0.075/query** (confirmed; pay-as-you-go, no monthly minimum — vs the LLM Mentions API which is $0.10/req + $100/mo min, so we use the scraper). Money queries = service × top cities; `--limit` for cost control; `--all` for every client. Defensive parser (recursively collects answer text + source domains); `cited` = client domain in sources OR brand name in answer; stores cited_sources (flags directory domains as GEO targets). Verified narestco: CITED for Federal Way, NOT for Seattle. `client_rank`/`competitors` are null in v1 (refine parsing later).
- **NEXT**: (a) app "AI Search" view reading `marketing_ai_search_scans`; (b) strategist integration — make AI-absence for a money query a high-priority action; (c) schedule it (bi-weekly, like geo-grid) once the view exists.
- **How the strategist will target an AI gap** (e.g. Home Pride absent for "Park City"): the AI answer cites companies with dedicated city service-area pages + many reviews + directory listings (BBB/Expertise/Yelp). So the gap → high-priority actions: citable city-specific content (Home Pride now HAS Park City pages post-rebuild) + FAQ/schema + reviews push + get listed on the directories the answer cites. Same plays lift Maps pack AND AI answers; re-scan measures progress.

## 4) Build queue (next, prioritized)
1. **AI-search collector** → app "AI Search" view → strategist integration. (Spike done, table ready.)
2. **Alerts in the Action Plan** — strategist detects account problems (LSA verification, disconnected integrations, red audit, no review velocity) → red "Needs Attention" section atop the plan. (Consider `kind`/`severity` on marketing_action_plan.)
3. **GA4 + Clarity per client** — auto-create property/project at onboarding, inject tags into site + ad LPs, backfill 3 live clients. (We have GA + Clarity MCP access.)
4. **Keyword Bank page** — make actionable: show priority/coverage/intent, separate opportunities vs covered, "Queue for post"/"Dismiss", label local vs national volume.
5. **Auto-execution wiring** — Prioritize/Dismiss should bump/remove the actual content queue (close the loop between the plan and System 2).
6. **OAuth consent-screen verification** (kill "unverified app" warning) — needs Google Cloud Console MCP.
7. **App streamlining** (from architecture review): Supabase as client-config source of truth (cadences); unified "Operations/Jobs" dashboard + retry; per-client audit trail.

## 5) Key decisions + reasoning
- **Hands-off > approve**: at 30+ clients a per-item approval bottleneck breaks; clients rarely log in. So autonomous-by-default + Dismiss/Prioritize override; money/listing actions flagged-only for safety.
- **DataForSEO for AI-search** (not Profound/Peec/Otterly): it's a data API we already pay for, scriptable into the autonomous pipeline + rendered in OUR app; per-brand SaaS is costlier at scale + lives outside the app. Revisit a purpose-built tool later only for premium sentiment/share-of-voice reporting.
- **Strategist is read-only v1** (writes the plan; doesn't execute) — see plan to wire execution later.
- **AI search is the sales wedge** (owners get fired up; easy close) — invest here.

## 6) Per-client quick state
- **narestco** (CO-1771290587387): Seattle metro water/fire/mold + reconstruction. Ads in cold-start (geo fixed, negatives applied, call tracking → Twilio). LSA blocked on verification. #1 on ChatGPT for Federal Way. Content queue refilled (mold seed).
- **homepriderestorationandcleaning** (CO-1780333664867): Saratoga Springs UT + 11 areas incl new Heber/Park City. Site live, first post published, geo-grid baselined, app tab fixed. GBP API reapplication candidate. Park City = AI + Maps gap.
- **davis-construction** (CO-1778778644861): Madison AL hybrid construction+restoration. Content queue refilled (mold). No geo-grid set up. No claimed GBP found via lookup.

---

## 7) Updates log (keep this doc LIVE — update as we build)

**Convention:** update this journal as we go — new features, decisions, specs, learnings. Newest first.

### 2026-06-26 (pm-24) — www duplicate fixed on ALL 3 clients + Analytics width
- Completed the www→apex 301 on **narestco + davis** (Home Pride was already done). Root cause confirmed: all 3 had www as a Pages custom domain, but narestco/davis www CNAME pointed to the APEX (loopback) which blocks the zone redirect rule; Home Pride's pointed to pages.dev (works).
- **How (answering Santino's "you should have full DNS / try wrangler"):** provisioning never edited DNS — it adds Pages custom domains and Pages auto-creates DNS (via CLOUDFLARE_PAGES_API_TOKEN, which is Pages/account-scoped, NO zone access). CLOUDFLARE_API_TOKEN has zone read + Rulesets edit + DNS **create/delete** but NOT PATCH/PUT edit (returns method_not_allowed). Delete+re-add of the Pages custom domain did NOT repoint (Pages re-adopts the existing apex record). **Working fix:** DELETE the www→apex DNS record + CREATE www→pages.dev (proxied) — the redirect rule then fires. wrangler doesn't manage DNS records. All 3 verified 301; apexes stay 200.
- Note: narestco's www Pages custom domain was delete+re-added (now re-verifying) — cosmetic since the 301 fires before Pages; davis was DNS-swap only (cleaner). Both action-plan items → done.
- **Analytics:** widened container max-w-5xl → max-w-[1400px] (removed right-side gap).
- **NEXT:** roll premium style to other tabs + merge feat/gsc-analytics.

### 2026-06-26 (pm-23) — Premium Analytics restyle + www-duplicate fix (found via GSC)
- **Found a real SEO bug from the GSC data:** Home Pride's 32,923 impressions were 75% the `www.` homepage ranking ~pos 29 across thousands of long-tail queries (CTR 0.04%). Confirmed www served HTTP 200 with NO redirect on ALL 3 client domains (systemic duplicate-host issue splitting ranking authority). GSC = web search only (country dim, ~99% USA), NOT the local pack — that's geo-grid.
- **Fix:** added Cloudflare zone Redirect Rule (http_request_dynamic_redirect) www→apex 301, query+path preserved. **Home Pride verified** (www 301→apex, apex stays 200, no loop). narestco/davis rules created but a www **Pages custom domain** intercepts before the zone rule (the CLOUDFLARE_API_TOKEN lacks Pages perms to remove it) — flagged as pinned Action Plan items; Home Pride flagged as a `done` item.
- **Premium UI restyle (Analytics pilot, Santino: dislikes glassmorphism):** flat white surfaces, hairline borders, tabular-nums, indigo accent, no shadows/blur. Added a **"What your search data says"** insight header (derived client-side: impressions-vs-position story, striking count, low-CTR note) so the tab leads with *what to do*, not raw tables.
- **Striking distance now explicit + actionable:** copy states the top few are auto-added to the Action Plan; per-row **Prioritize** button pins/creates a `gsc_striking` plan row (RLS "manage own" allows it) and shows "In plan". Answers Santino's "is this automatic / button?" question.
- Branch `feat/gsc-analytics`, localhost:5175. **NEXT:** Santino reviews the premium look → if good, roll the style to other tabs + merge. Follow-up: finish narestco/davis www (needs Pages-domain access).

### 2026-06-26 (pm-22) — Reports tab finished (real monthly reports, no more mock)
- Santino chose "finish it." The Reports tab showed REAL review-engine stats but FAKE monthly summaries (marketing_reports empty → hardcoded May/Apr/Mar mock) behind a dead `alert()` "View" button.
- **`client_report.py publish --slug|--all [--period]`**: renders the monthly report, writes the HTML file (parity with preview), computes real metrics (posts_published=len(posts), videos_created=blog md w/ youtube_id in period, avg_lighthouse_score=mean of audit site_rollup avg_scores), and UPSERTS to `marketing_reports` (added `report_html`/`report_url` cols + unique (company_id,report_month); status CHECK only allows draft|completed → use 'completed'). Ran --all: Home Pride 14 posts/lh98, narestco 5/lh87, Davis 5/lh91, full HTML stored.
- **App:** "View" now opens the stored report_html in a new tab; **mock fallback removed** → honest empty state when no reports. (`feat/gsc-analytics`, localhost:5175.)
- **Scheduled:** monthly-reports.yml step switched `preview` → `publish` (+ SUPABASE env), so the 1st-of-month run populates the app automatically.
- **Tab split is now coherent:** Analytics = live perf (GSC/GA4/Clarity); Reports = packaged monthly deliverable + review-engine results.
- **NEXT:** merge `feat/gsc-analytics` (now carries GSC Analytics tab + Reports finish); add GSC_AGENCY_TOKEN secret.

### 2026-06-26 (pm-21) — Google Search Console analytics: app "Analytics" tab + strategist striking-distance + sync
- **New app surface:** "Analytics" tab in Marketing (shared home for organic search + GA4 + Clarity). `MarketingAnalytics.tsx`: GSC month-over-month tiles (clicks/impressions/CTR/avg position, position inverted so lower=better), a **striking-distance** opportunity table, and top queries / top pages. GA4 + Clarity show as "tags live, data view next" placeholders (their site tags already ship per journal pm-2; GA4 data pull still pending the analytics.edit OAuth grant). Branch `feat/gsc-analytics`, localhost:5175.
- **Bug fixed:** `gsc_client.py` hardcoded `webmasters.readonly` but the agency token was granted `webmasters`+`siteverification` → refresh failed `invalid_scope` (latent; broke once the token expired, would have killed URL-inspection too). Now uses the token's granted scopes.
- **Data layer:** `scripts/gsc_sync.py` pulls Search Analytics → `marketing_gsc_daily` (pre-existing, total_*/avg_* cols, 90d), `marketing_gsc_queries` (top 200, 28d, +`striking` flag: pos 8-20 & impr≥10), `marketing_gsc_pages`. Per-client resilient. Synced all 3: narestco 200q/11 striking, Home Pride 200q (33K impr), Davis 173q.
- **Strategist:** `gather_gsc()` → top striking queries become high-impact/low-effort "Push '{query}' onto page one" actions (assigned s2, capped 3). narestco surfaced e.g. *federal way water damage restoration* @ pos 13.7. Ran --all live.
- **Scheduled:** `gsc_sync --all` step added to weekly-maintenance BEFORE the strategist (so striking data is fresh). Gated on a new **`GSC_AGENCY_TOKEN`** GH secret (the .gsc-agency-token.json is gitignored / not in CI) — writes it to disk then syncs; skips gracefully if unset. **ACTION: add GSC_AGENCY_TOKEN secret** (paste contents of .gsc-agency-token.json).
- **NEXT:** Santino review localhost → merge `feat/gsc-analytics`; add the GSC_AGENCY_TOKEN secret; (later) GA4 data card once analytics.edit grant is done, Clarity metrics card.

### 2026-06-26 (pm-20) — GBP insights wired into the strategist's Action Plan (System 0)
- `strategist.py` now has `gather_gbp(company_id)` reading `marketing_gbp_suggestions` (optimizer output) + `marketing_gbp_profiles` (review recency). Threaded into `gather_alerts` + `build_actions`.
- **Surfaces:** (1) ALERT — services the client declared they do NOT offer that are live on the GBP (negatives → trust/suspension risk, high); (2) "Add N confirmed services" (medium/low); (3) "Create N website pages for confirmed services" (medium/medium); (4) "Clean up N duplicate/off-brand services" (low/low); (5) "Get fresh Google reviews" if last_review_at ≥45 days. All aggregated (counts, not per-service) and one-click in Marketing → Locations.
- All assigned_system='gbp'; stable action_keys (gbp_add_services/gbp_create_pages/gbp_cleanup/gbp_reviews + gbp_negatives alert) so re-runs honor dismissed/pinned.
- **Ran --all live:** Home Pride (1 negative, 10 add, 10 pages, 15 cleanup), narestco (9 negatives, 4 add, 8 pages, 27 cleanup), Davis (0 — no synced GBP, handled gracefully). Rows confirmed in marketing_action_plan; the app's "What we're working on" card now shows GBP work. No workflow change needed — strategist already runs in weekly-maintenance (Mon+Thu).
- **GBP optimizer system now complete:** optimize → suggestions → app panel (one-click apply) → page-build pipeline → strategist Action Plan. End of this build arc.

### 2026-06-26 (pm-19) — Page-build automation PROVEN end-to-end; schedule enabled
- Manual gbp-maintenance runs surfaced + fixed THREE real build-chain bugs (each a distinct footgun):
  1. **render fatality:** 13/14 pages rendered but 1 straggler made the chain abort before deploy. Fix: render is best-effort (retry once); the DEPLOY is the success gate.
  2. **optimize --all not resilient:** one client's empty/non-JSON Anthropic response crashed the whole loop (skipping everyone, incl. the build step). Fix: per-client try/except + `_anthropic_json` retry on empty/non-JSON/overload (429/5xx/529); run stays exit-0.
  3. **dirty-tree deploy:** sync-deploy does `git subtree split` over COMMITTED history, so rendered pages must be committed first (and `--allow-dirty` would push WITHOUT them). Fix: `build_client_pages` commits clients/sites/templates before sync-deploy; workflow always `git push HEAD:main`.
- **RESULT (verified):** Home Pride `homepriderestorationandcleaning-site` now has services/crawl-space-encapsulation.md (11.8KB, rendered:true) + 12 location pages; DB request status=built. Cloudflare auto-builds.
- **Schedule enabled:** gbp-maintenance.yml cron `0 17 * * 1` (Mon 10am PT, after the content run). optimize --all refreshes suggestions; create-pages --all --build drains the page queue + deploys.
- **NEXT:** merge `feat/gbp-add-button` (the app side: optimizer panel + Add/remove/merge + Create-page) to ship; then strategist Action-Plan wiring.

### 2026-06-26 (pm-18) — Page-build automation wired (safe incremental chain) + GBP maintenance workflow
- **Goal:** queued pages (e.g. Crawl Space Encapsulation) actually build/deploy, and `optimize` runs on a schedule.
- **Footgun caught:** `build_site scaffold` overwrites EVERY page with a placeholder (would wipe rendered content); and `plan_site` DIES on any plan-input slug not in `templates/restoration/services.json` (the GBP-confirmed services — Crawl Space, Biohazard, Board-Up, Red Stain… — aren't in the 44-service catalog). So a naive build would crash or nuke the site.
- **Safe incremental chain built:**
  - `build_site.py add-pages --slug` — writes content md ONLY for planned URLs missing a file (never overwrites rendered pages; unlike scaffold).
  - `gbp.py create-pages --build` — runs: `plan_site generate` → `add-pages` → `render` (skips already-rendered) → `sync-deploy --branch main`; marks requests built/error.
  - `gbp.py ensure_catalog_entry()` — self-heals the catalog: appends a VALID entry (intent local_specialty, tier adjacent; biohazard/trauma/hoarding/sewage → content_guardrails sensitive) for confirmed services the template lacks, so plan_site accepts them. Verified: 8 Home Pride services produce valid entries.
- **Workflow `gbp-maintenance.yml`** (workflow_dispatch now; schedule commented until tested): step 1 `optimize --all` (safe, DB-only), step 2 `create-pages --all --build` (gated by input). All required GH secrets confirmed present (GOOGLE_OAUTH_CLIENT_ID/SECRET, CLOUDFLARE_*, GH_PAT, ANTHROPIC, SUPABASE, DATAFORSEO).
- **Why a separate manual workflow (not the weekly cron):** the build chain touches live client sites — test Crawl Space end-to-end via manual run BEFORE enabling the schedule.
- **NEXT:** trigger gbp-maintenance manually → confirm Crawl Space builds + deploys to Home Pride → enable the schedule; then merge feat/gbp-add-button.

### 2026-06-26 (pm-17) — Structured items canonical; build-cadence finding
- **Tuning (Santino-approved):** ruleset now treats Google `job_type_id:` *structured* service types as canonical — KEEP them when the client offers the work; MERGE free-form duplicates INTO the structured item (never flag the structured one as the dup). Re-ran Home Pride: structured mold/water/sewage/carpet types now KEEP; MERGE 33→15; even merges duplicate structured carpet types into the canonical one. Matches "keep the Google-recognized type, drop the text dupes" + removes the "can't remove in dashboard" friction.
- **Build cadence (answer to Santino):** recurring builds = `weekly-maintenance.yml`, **Mon + Thu 9am PT** (master_scheduler S1-S4 → ai_search_scan → strategist → commit/deploy). **GAP:** nothing consumes the `marketing_page_requests` queue yet — `gbp.py create-pages` is built but NOT wired into any workflow, so queued pages (e.g. Crawl Space Encapsulation) won't auto-build. NEXT: wire `create-pages` + the re-plan/scaffold/render/deploy chain into the maintenance run (or a dedicated step).
- **NEXT:** wire create-pages into the cron; schedule `gbp.py optimize` per client (refresh suggestions); then merge `feat/gbp-add-button`.

### 2026-06-26 (pm-16) — Merge grouping + website pages folded into the optimizer (blue card retired)
- **Optimizer now emits website pages:** `optimize` prompt produces a 3rd item kind — for each confirmed_service with NO matching website page (after synonym/dup collapse), emit item_type='page', verdict ADD. Home Pride → 9 page suggestions (Biohazard, Board-Up, Crawl Space Encapsulation, Hoarding, Drywall, Trim, Red Stain, Flooring, Post-Construction). Pages are NOT auto_safe (13x cross-product fan-out + categories stay human-gated).
- **App panel rebuilt (`MarketingSuggestions.tsx`):**
  - MERGE rows now GROUPED by canonical target — "Merge N → Water Damage Restoration · Merge all" with variant chips, instead of 30+ individual rows.
  - New "Create website pages" section (the page items) → "Create all" / per-item, wired to `gbp-create-page` queue. Replaces the old blue card.
  - "Apply all vetted" spans vetted singles + vetted merge groups; one batched gbp-add-service call (services + remove).
- **Retired the blue card** + removed all dead reconcile state/handlers from `MarketingLocations.tsx`. The AI panel is now the single surface for both directions (GBP listing + website pages).
- Home Pride latest: KEEP 32, MERGE 33, ADD 19 (10 service + 9 page), REMOVE 4, NEEDS-REVIEW 4; 30 auto-safe (services only).
- **NEXT:** Santino review on localhost → merge `feat/gbp-add-button`; then wire `optimize` into the sync cadence (run per client) + strategist Action Plan.

### 2026-06-26 (pm-15) — Optimizer tuning + UI cleanup (Santino review)
- Renamed ruleset → `GBP/rank-ai-gbp-best-practices.md` (matches rank-ai-* skill naming).
- **Over-merge fix:** the first pass collapsed distinct long-tail services (Toilet Overflow / Sump Pump / Washing Machine Leak Cleanup) into "Water Damage Restoration" — wrong; on a GBP, services are keyword-bearing. Tightened the MERGE rule: same *work* different words → MERGE; different *situation* sharing a parent → KEEP. Re-ran Home Pride: KEEP 23→48, MERGE 56→30, ADD 16→9 (much healthier).
- **UI:** removed the redundant amber "Add to your Business Profile" card (the dumb string-diff; the AI panel's grounded ADD replaces it). Kept the blue "Create page" card until website-page suggestions are folded into the optimizer.
- Open Qs answered for Santino: website-page intelligence not yet in the optimizer (pending, next layer); cards were leftover (amber removed).
- **NEXT:** group MERGE rows by canonical target in the UI; fold website "page" verdicts into the optimizer (retire the blue card); then merge + wire optimize into the sync cadence.

### 2026-06-26 (pm-14) — AI GBP optimizer: grounded judgment layer (no more dumb string-diff)
- **Why:** the reconcile was a pure string diff with no judgment — it suggested near-duplicate pages and off-brand services (Fabric Protection, Roof Leak "Repair"). Santino: it must not suggest/auto-do wrong things, and should advise like an expert (e.g. "you have 45 categories, keep 8").
- **Ground truth discovered in-app:** `companies.services` (confirmed do) + `companies.negative_services` (confirmed do-NOT) — set by clients in the AI-dispatcher "Services & Area" tab. This is the trust anchor; we stop guessing.
- **`GBP/gbp-best-practices.md`** (editable ruleset, mirrors `Ads/universal-negative-keywords.md`): categories high-stakes → 3-10, always human-gated; services → dedupe near-synonyms, must map to a confirmed service; anything in negative_services = forbidden (REMOVE, never ADD); unconfirmed = NEEDS-REVIEW. Defines the output contract + auto_safe policy.
- **`scripts/gbp.py optimize --slug|--all`**: reads live GBP + declared/negative + site pages → Anthropic (`claude-sonnet-4-6`, 16k tokens) classifies EVERY category/service/gap into KEEP/ADD/REMOVE/MERGE/NEEDS-REVIEW + reason + confidence. **Deterministic guardrail overrides the model** on negatives + computes `auto_safe` (verdict∈ADD/MERGE/REMOVE, not a category, conf≥0.85, grounded in declared lists). Stores to **`marketing_gbp_suggestions`** (read-own + manager-update RLS).
- **Proven on Home Pride:** 68-item bloated listing → KEEP 23, MERGE 56, REMOVE 5, ADD 16, NEEDS-REVIEW 7 (38 auto-safe). Caught Fabric Protection (artifact), Plumbing Leak Cleanup (negative), Roof Leak "Repair" (roofing=negative), 5 mold-removal dupes → one Mold Remediation; surfaced 16 confirmed services missing from GBP.
- **App:** new `MarketingSuggestions.tsx` in Locations → "Vetted — safe to apply" vs "Needs your review", verdict badges + reasons + per-item Apply + "Apply all vetted" + Dismiss. **`gbp-add-service` extended** to take a `remove[]` list (REMOVE + MERGE delete the label; structured job_type_id items reported as needing manual removal). Marks suggestions `applied`.
- **Asymmetry/safety:** categories never auto; only grounded high-confidence service changes are vetted; everything else needs a click. Nothing auto-executes yet — this is the layer that makes future autonomy safe.
- Branch `feat/gbp-add-button`, localhost:5174. **NEXT:** Santino reviews the panel → merge; then wire `optimize` into the sync/strategist cadence + a one-time dedupe pass.

### 2026-06-26 (pm-13) — "Add now" bugfix + website "Create page" half built (both reconciliation directions now have buttons)
- **Bug:** the GBP "Add" button errored `No connected Google Business Profile for this company` for Home Pride. Root cause: only 2 of 4 clients have their own `user_integrations` google row; Home Pride has none. `scripts/gbp.py` works because it **falls back to any agency google token** (the agency account manages all 4 locations) — the edge function lacked that fallback. **Fix:** `gbp-add-service` now mirrors gbp.py — `getAccessToken()` tries the client's row then any agency 'google' integration; `resolveLocation()` uses the synced `location_name` else finds the location by `place_id` across managed accounts. Deployed. (Home Pride has both location_name + place_id, so it resolves.)
- **Website half ("Create page"):** the blue card was display-only. Built the enqueue path end-to-end:
  - **Table `marketing_page_requests`** (queued|building|built|error; read-own RLS) — migration `20260626140000`.
  - **Edge fn `gbp-create-page`** (auth + manager-gated): inserts queued rows, dedupes vs existing.
  - **UI:** blue card chips + "Create all" now invoke it → toast "Queued — live after the next site build."
  - **Pipeline consumer `gbp.py create-pages --slug|--all`**: drains queued rows → maps each GBP service to a catalog slug (`service_to_slug`) → adds to `clients/<slug>/plan-input.json` services (deduped) → marks the request `building`. The normal **re-plan + rebuild** then scaffolds/renders/deploys the page (subtree push → Cloudflare). Why enqueue (not synchronous): a page needs generation + git push + a CF build — can't be done in the edge function.
- **Asymmetry by design:** GBP add = instant (API PATCH). Website page = queued build. Both are one click in the app.
- Both functions on branch `feat/gbp-add-button`, served on **localhost:5174**. **NEXT:** Santino re-tests Add (now fixed) + Create page on Home Pride → merge; then auto-trigger the rebuild on enqueue (optional), strategist `gather_gbp()`, schedule syncs.

### 2026-06-26 (pm-12) — One-click "Add now" productized + Locations view merged (PR #17)
- **Locations view merged to prod** (app PR #17).
- **`gbp-add-service` edge function** (app, authenticated + manager-gated in-fn: superadmin or admin/owner of the company): refreshes the client's google token from user_integrations, GETs the location (categories+serviceItems), appends free-form services under the primary category, PATCHes. Mirrors `scripts/gbp.py add_services`. Deployed; rejects no-auth with 401.
- **UI:** Locations "Add to your Business Profile" chips are now clickable + an "Add all" button → `supabase.functions.invoke('gbp-add-service')` → optimistic chip removal + toast. **Services only** (categories left untouched — ranking-sensitive; a confirm-gated category add is a later step). Branch `feat/gbp-add-button`, served on **localhost:5174** for review.
- narestco is already finished out (no gaps); **Home Pride has 4 gaps** (Appliance Leak Cleanup, Fabric Protection, Odor Removal, Roof Leak) to demo the button live.
- **NEXT:** confirm on localhost → merge `feat/gbp-add-button`; then the **"Create page"** direction (right card → async site-build job); `gather_gbp()` into strategist; schedule `gbp.py sync`/`reviews` crons.

### 2026-06-26 (pm-11) — GBP "Add now" write op (gbp.py add-services) + narestco finished out
- **GBP writes work.** `gbp.py add-services --slug X --service "..."` adds free-form services to a client's live GBP via the Business Information API PATCH (`updateMask=serviceItems`): reads current serviceItems, appends `{freeFormServiceItem:{category:<primaryCategory.name>, label:{displayName}}}`, patches the full list, reads back to confirm. Idempotent (skips present). Free-form services attach to `categories/gcid:water_damage_restoration_service` (narestco's primary).
- **Tested on one** (Storm Damage Restoration → narestco, 45→46, read-back confirmed), then **finished out narestco**: added all 9 remaining `reconcile_site_without_gbp` services (Basement Flooding, Biohazard/Trauma, Burst Pipe, Frozen Pipe, Odor Removal, Reconstruction, Renovations/Remodels/GC, Roof Leak, Sewage). Listing now 55 services; the "Add to your Business Profile" gap is CLOSED (reconcile re-run confirms). Re-synced so the Locations view reflects it.
- **NEXT (productize "Add now"):** Supabase edge function `gbp-add-service` (mirrors this: refresh token from user_integrations, GET location categories+serviceItems, append, PATCH) → "Add" buttons on the Locations reconciliation chips for one-click. Categories behind a confirm (ranking-sensitive); services one-click (safe). Then the other direction: "Create page" → enqueue a site-build job.

### 2026-06-26 (pm-9) — GBP "Locations" data layer (layer 1) — Supabase tables + `gbp.py sync` (insights MoM)
- Building a client-facing **Locations / GBP view** (blueprint = a competitor "Rank AI" screenshot showing narestco's profile + reviews + GMB insights + rank grids + audits). We already have every data source; ours adds the GBP↔website reconciliation + AI-search visibility they lack.
- **Confirmed GBP Insights work now** (Performance API, already enabled): narestco last 30d — 9 calls, 17 website clicks, 63 directions, 153 map impressions.
- **Data layer (layer 1) DONE.** Reconciled with a pre-existing empty `marketing_gbp_daily` (from the 6/13 migration) instead of duplicating — extended it (added `impressions_desktop_search`/`impressions_mobile_maps`/`conversations` + a unique `(company_id,date)` + RLS), dropped a redundant `marketing_gbp_insights` I'd created. New tables: `marketing_gbp_profiles` (snapshot + reconcile gaps), `marketing_gbp_reviews` (for later). RLS = `(company_id = get_effective_company_id())` mirroring other marketing_* tables. App-repo migration: `20260626120000_gbp_data_layer.sql`.
- **`scripts/gbp.py sync`** (`--slug`/`--all`): upserts profile (Business Info + reconcile) → `marketing_gbp_profiles`; **daily** insights (Performance API, 90 days, 8 metrics) → `marketing_gbp_daily` (one row/company/day, so the app computes ANY period delta). Backfilled narestco + Home Pride (91 days each); Davis skipped (no claimed GBP). MoM verified — narestco calls 6→8, web 29→14, dir 69→41, impr 415→271 (May→Jun-partial).
- **Open:** `review_aggregate` (rating/count via DataForSEO) returns null — endpoint/cid-match needs a fix (non-blocking). Individual reviews → DataForSEO Reviews task (read) now / native v4 once allowlisted. **v4.9 allowlist request submitted** (support form, case **8-3674000040966**) for reviews + local posts; live v4 returns 403 "not used/disabled" (Gemini's "it inherits implicitly" was empirically false).
- **NEXT:** (a) fix review aggregate + populate `marketing_gbp_reviews` (DataForSEO); (b) build the app **"Locations"** view (dedicated section) reading these tables — MoM insight cards, reviews, reconcile gaps; (c) wire `gather_gbp()` into `strategist.py`; (d) schedule `gbp.py sync` (daily/weekly cron).

### 2026-06-26 (pm-8) — GBP API enabled + `scripts/gbp.py` module + GBP↔website reconciliation (BUILT, read-only v1)
- **GBP API approved + enabled.** Project 936081984190 (`feisty-grid-487507-h8`) approved for GBP API. Via a service-account ("Claude", `serviceUsageAdmin`) enabled **3 of 4**: `mybusinessbusinessinformation` (categories/services/hours/description — the map-pack levers), `mybusinessaccountmanagement`, `businessprofileperformance`. ⚠️ **`mybusiness` v4.9 (reviews + local posts) is allowlist-gated** ("not available to this consumer") — no propagation fix; reply to approval **case 8-3674000040966** to request it (the Cloud AI's suggested case `0-0974000041482` was hallucinated — use ours).
- **No reconnection needed for existing clients.** narestco's app `google` integration already has `business.manage`; refreshed its token and read its GBP live. The **agency account (Santino Velci) manages all 4 client locations** (narestco, Home Pride, Davis, ProBrite) — one business.manage token reaches them all; match the right one by `brand.place_id`.
- **`scripts/gbp.py`** (System: GBP, read-only v1): `read` + `reconcile` (`--slug`/`--all`). Pulls the client's (or fallback agency) refresh_token from `user_integrations` via the project REST API (uses `requests` — the Management API `urllib` path hits a Cloudflare WAF 1010), refreshes, finds the location by place_id, reads categories/services/hours/description, and **reconciles GBP categories+services against the website's service pages** (`plan-input.json` services). Flags both directions: GBP item with **no dedicated site page** (build one) + site service **not on the GBP** (add to listing). This is the local-SEO consistency lever (Santino: a GBP service with no crawlable page underranks).
- **First run:** narestco (45 services on GBP), Home Pride (67), Davis **skipped** (no claimed GBP / no `place_id`). Real gaps surfaced — most actionable = **site services missing from the GBP** (narestco: Storm Damage, Roof Leak, Sewage, Reconstruction, Frozen Pipe — all have pages, not listed on GBP). v1 matching is **noisy** (raw `job_type_id:*` entries + granular sub-services don't map to top-level pages) — refine to category/top-service level next.
- **NEXT:** (a) refine the matcher (drop `job_type_id`, match at category + service-landing level); (b) wire `gather_gbp()` into `strategist.py` → Action Plan items (site-service-not-on-GBP = safe `gbp_update`; GBP-category-without-page = `blog_post`/service page → content queue); (c) add WRITE ops (update categories/services/description); (d) reviews/posts once v4.9 is allowlisted.

### 2026-06-26 (pm-7) — Sales page v2 (rank.ai-modeled, white theme) + booking
- **Booking:** embedded GHL calendar (`link.restorationai.io/widget/booking/5GoVLLz9HDn8Ik3RjFMB` + `form_embed.js`) in a `#book` section; all primary CTAs scroll to it; hero "see where you rank" form also routes to `#book`.
- **v2 (commit b00e177):** rewrote `sales/rank-ai/src/pages/index.astro` to a **white/light theme** modeled on **rank.ai's** layout (per Santino's "make it like theirs"). Sections: nav, hero ("Rank higher. With AI. For AI." + rank-check input + dashboard mockup), 4 quick solution cards, 3-ways grid, **before/after** (AI / Map Pack / Google), **AI-analytics** mock (per-engine recommendation bars + "recommends instead"), **geo-grid heatmap + reviews** mock, why-us, single **$997 flat** pricing, FAQ, CTA+booking, multi-column footer. global.css → light; build green. Own copy/brand (not rank.ai's text/assets). Review on localhost:4321.
- **Domain decided: `rank.restorationai.io`** — Santino will update Cloudflare DNS. astro.config `site` set to it. NEXT: deploy to Cloudflare Pages + map the domain once Santino approves the design; then personalized proposal generator (page + PDF + live audit) for the hot lead.

### 2026-06-26 (pm-6) — NEW DIRECTION: Sales assets
Pivot to sales collateral. Context: 3 demos — 2 want "more info on what Rank AI is / how it helps," 1 wants a proposal.
- **Decision (web vs PDF):** lead with **web page** (it's a proof of capability for an SEO/AI product, trackable via GA4/Clarity, updatable, personalizable); offer **PDF export** for proposals. Two distinct assets: a reusable **overview page** (info requests) and **personalized proposal pages** (+PDF) with a **live audit of the prospect's own business** (run our AI-search + geo-grid + keyword tools on them — the unfair advantage).
- **Key finding:** `restorationai.io` is already live = the **AI Receptionist / dispatch** product (separate Astro site on Cloudflare, different repo). Rank AI (SEO/AI-search) is a **separate product line**. So position as **"Rank AI — by Restoration AI"**; recommended URL **`rankai.restorationai.io`** (subdomain, doesn't touch existing site).
- **User chose:** build the **reusable overview page first**; personalize with **full live audits per prospect** next (they'll supply name/site/city/services; ~$1–3 DataForSEO/prospect).
- **BUILT (this turn):** `sales/rank-ai/` — standalone Astro landing page (own indigo/blue theme, Tailwind compiled, Inter), single `src/pages/index.astro`. Sections: hero (AI-search shift), the shift/problem (with a mock AI scoreboard), services (AI search / map pack / content / reviews / GBP / local SEO), 4-step how-it-works, live-scoreboard proof, why-us, pricing ($997/mo flat, month-to-month), FAQ, CTAs (mailto contact@restorationai.io — **need real booking link**). Build green; **review on localhost:4321** (NOT deployed yet). Committed (pipeline 9f0b432).
- **NEXT:** (1) Santino reviews/edits copy + confirms brand/URL; (2) swap mailto → real booking link (Calendly?); (3) deploy to Cloudflare Pages + map `rankai.restorationai.io`; (4) build personalized proposal generator (page + PDF + live audit) for the hot lead.

### 2026-06-26 (pm-5) — AI Search trend over time (BUILT + MERGED to prod, PR #16)
"Track improvement over time." Data already existed (every scan is timestamped) but wasn't surfaced; raw rows are noisy (test runs) + capped by row limits — so built a **rollup**:
- New table `marketing_ai_search_history` (company_id, scanned_at, total, cited, top_picks, visibility_pct, by_engine jsonb; unique(company_id,scanned_at); RLS select by `get_effective_company_id()`).
- `ai_search_scan.py` writes **one snapshot per run** (`_sb_history`, guarded `HISTORY_MIN_ROWS=5` to skip ad-hoc/validation runs). Pipeline commit b641e61.
- App AI Search tab: **Visibility trend** card — dependency-free inline-SVG sparkline + delta vs last scan (▲/▼ pts) + top-pick change + date range; "builds after next scan" empty state. PR #16 merged to main; **prod build green**. localhost now runs `main` directly (all features merged).
- Backfilled history from the two real existing snapshots/client (skipped the 1- and 4-row test runs). Current trend: davis 7%→10%, Home Pride 17%→18% (0→2 top picks), narestco 17%→17%.
- Future scans (weekly Mon + manual) append snapshots automatically → trend grows on its own.

### 2026-06-26 (pm-4) — Merged to production + scan refresh
- **All 3 app PRs merged to `main`** (production, Netlify auto-deploy): **#13** AI Search (multi-engine, top-10+locations, Prioritize→action, position/rank, custom queries), **#14** Action Plan alerts + deprioritize, **#15** actionable Keyword Bank. Merge order #13→#14→#15; #15 had an AIMarketing.tsx import conflict (both added imports) — resolved on-branch (kept all three imports), pushed, merged. **Production build verified green** (`npm run build` exit 0, all 3 components present).
- **Full AI-search refresh** complete ($3.70, ~93 queries incl. Home Pride's Park City custom). `client_rank` now populated from full answers. Fresh rank breakdown:
  - **narestco**: 6 cited (0 top-pick, 4 listed #N, 2 mentioned)
  - **davis-construction**: 3 cited (0 top-pick, 1 listed, 2 mentioned)
  - **homepriderestorationandcleaning**: 6 cited (**2 top-pick**, 4 listed) — incl. Park City custom (not cited there)
  - Reality check: nobody is winning the AI-search game broadly yet (lots of "listed/mentioned," few #1) — which is exactly the gap the strategist's AI-visibility actions + content wiring target.
- Reminder: this is the **first production push** of the strategist/AI-search/keyword-bank suite. Pipeline (strategist items 3+4, scanner) already on `main` of the pipeline repo.

### 2026-06-26 (pm-3) — AI Search 2b: guard-railed custom queries (BUILT)
Decision: **service × city dropdowns** (fully on-rails — no vanity/irrelevant queries, cost-capped). Cap **5 per company**.
- New table `marketing_ai_search_custom_queries` (company_id, rank_ai_slug, service, location, query; unique(company_id,query); RLS select+all by `get_effective_company_id()`).
- Scanner `fetch_custom_queries()` merges active custom queries into each scan (dedup vs auto). `--limit 0` scans custom-only (used for cheap testing).
- App (`MarketingAISearch.tsx`, managers only): "Track your own queries" card — service dropdown (from distinct `marketing_keywords.seed`) × city dropdown (from scanned `location`s) → builds "best {service} company in {city}"; shows each tracked query's latest rank badge or "Pending next scan"; remove button; cap-5 enforced.
- Verified end-to-end: inserted a **Park City** custom query → scanner picked it up (`--limit 0`) → stored with location, Home Pride not cited there (matches earlier finding). Left that Park City query in place (real city they want tracked).

**AI Search roadmap (1, 2a, 2b, position tracking) COMPLETE.** PR #13 (`feat/ai-search-view`) now carries: multi-engine, top-10+locations, Prioritize→action, position/rank, custom queries. Strategist items 3 + 4 complete (pipeline, on main).

### 2026-06-26 (pm-2) — Item 4 (strategist rebalance) + position tracking (BUILT)
**Item 4 — lead-gen rebalance** (pipeline 7841841): `gather_content` tags uncovered keywords **local-transactional** (city + buy-intent = real call driver) vs **informational**; `build_actions` makes local-tx gaps **HIGH** impact (local pages), generic informational **LOW** (supporting/AI-citation), and adds a **HIGH** "research local-transactional keywords" action when `local_tx_total < n_areas`. Verified: Home Pride now leads with local-keyword research + AI-visibility + GBP; ice-dam/insurance blogs demoted off the top. Plans refreshed for all 3.

**Position tracking** (pipeline 1aa02d0; app PR #13 663da1d): scanner `detect_rank()` parses the AI answer (numbered/bulleted lists, then "the best … is X" headline) → stores `client_rank` (1 = top pick, N = listed Nth, null = cited but position unclear). App shows **★ Top pick / Listed #N / Mentioned / Not mentioned** + a "Top Pick" stat. Honest metric now: "cited" ≠ "#1". Validated live (narestco Federal Way = **#2** on ChatGPT). Excerpt bumped 400→600. NOTE: existing rows mostly show "Mentioned" (rank not recoverable from old truncated excerpts); the Monday scheduled scan repopulates ranks from full answers (or trigger `ai_search_scan.py --all` to refresh now, ~$3.6).

### 2026-06-26 (pm) — Item 3: content-queue wiring (pin = pull forward) (BUILT)
The one safe auto-exec. Pipeline commit 9749e8a (no app changes).
- `strategist.sync_content_queue(slug, company_id)`: reads **pinned** `blog_post`/`ai_visibility` actions from `marketing_action_plan` → ensures a **prioritized** content-queue item exists (find-or-create by primary_keyword, case-insensitive; rich fields from keyword-bank when available; `city_anchor` parsed from "…in {City}, {ST}" for AI-visibility queries; `intent` commercial/informational; anti-self-ranking `notes` for AI-visibility). Never touches written/live items; idempotent.
- `content_writer.pop_next_queued()`: **prioritized items jump the line**, then oldest-first.
- **Verified end-to-end:** app Prioritize → pinned action → strategist creates prioritized queue item (city_anchor=lehi-ut) → S2 pop selects it first. Test data cleaned up.
- GBP/video stay **advisory** (not auto-executed) per the "don't overcomplicate" call.
- Q&A this session: confirmed "cited" currently = *mentioned at all* (not #1) — recommended adding `client_rank` position tracking later. Advised AGAINST self-ranking "best companies in {city}" listicles (low trust, AI discounts them); DO third-party directory inclusion + reviews + criteria FAQs. Recommended criteria-based self-positioning FAQ (not "we're the best") — queued as content-gen follow-up.

Remaining roadmap: **item 4 (strategist rebalance: local-transactional + AI-visibility > generic informational blogs)**; AI Search **2b (guard-railed custom queries)**; position/rank tracking; criteria-FAQ content.

### 2026-06-26 — AI Search v2: multi-engine + redesign (BUILT)
Working the agreed roadmap (1 multi-LLM, 2 redesign, then 3 content-wiring, 4 strategist rebalance). Items 1+2 done.

**Bug fixed first (keyword dupes):** `marketing_keywords` unique index `(company_id,keyword,city)` let `city=NULL` (national) rows duplicate every sync (Postgres treats NULL as distinct). Rebuilt index `NULLS NOT DISTINCT` (PG17), deleted **1,265** dupe rows, sync now idempotent. Also fixed the dev clone blank screen: `/tmp/rankai/Restoration-AI-APP` had no dev env → wrote `.env.local` from the **correct** project (`nyscciinkhlutvqkgyvq`; the repo's `.env.staging` points at a *different* project `cahi…`).

**1. Multi-engine scanner** (`ai_search_scan.py`): `ENGINES` map → ChatGPT (`chat_gpt`/gpt-4o), Gemini (`gemini`/gemini-2.5-flash), Perplexity (`perplexity`/sonar), Claude available but off by default (low ROI for local-service). `--engines` flag, default chatgpt,gemini,perplexity. All four DataForSEO endpoints verified live (`/ai_optimization/{provider}/llm_responses/live`). Engine priority rationale: ChatGPT (biggest) → Gemini/Google AI (in Google Search where local searches happen — highest ROI) → Perplexity → skip Claude. **dry-run is now offline** (was making real API calls).
**2a. Top-10 + locations:** `money_queries` now returns up to 10 `{query,city,state,location}` across top 4 services × 4 cities (service-major so early rows span cities); added `location` column to `marketing_ai_search_scans`. App `MarketingAISearch.tsx`: **engine filter + location filter**, location chip per row, and **per-row Prioritize** on uncited rows → find-or-create a **pinned `ai_visibility`** action using the **same `action_key` = sha1("ai_visibility|"+query)[:16]** as the strategist (so no dup on next run); shows "In plan" once pinned. Weekly workflow → `--limit 8 --engines chatgpt,gemini,perplexity` (~$5/wk at 3 clients).
**2b. Guard-railed custom queries:** still TODO (phase 2).

Pipeline commit 5386aa7; app PR #13 updated (branch `feat/ai-search-view`, commit 3309858). Cost note: ~$0.075/query × engines.

### 2026-06-25 (pm-3) — Actionable Keyword Bank (BUILT — PR #15, app)
Replaced the static keyword table (`components/MarketingKeywordBank.tsx`, swapped into Content → Keyword Bank sub-tab).
- Summary chips (total / covered / uncovered-P1 / local-national); filters: search, scope (local/national via `city`), coverage (covered vs gap via `covered_by`), priority, sort (priority/volume/difficulty), show-dismissed.
- Manager actions: **Queue** (`status='queued'`) and **Dismiss** (`status='dismissed'`), plus Restore/Unqueue.
- DB: added `covered_by`, `cpc`, `status` (default 'active') to `marketing_keywords` (+ index on company_id,status). `supabase_sync.py` now syncs covered_by/cpc and **omits status** so operator choices persist across syncs.
- **Loop closed (pipeline commit 3e2ab10):** strategist `gather_content()` reads `marketing_keywords.status` → drops dismissed, floats queued uncovered-P1 to the front. Verified live (dismiss → strategist drops the kw).

**All four plan items shipped this session. PRs: #13 (AI Search), #14 (Action Plan alerts, stacked on #13), #15 (Keyword Bank).** Merge order: #13 → #14 → #15. Combined preview branch `test/all-features` is what's on localhost:5173 now (all four merged for testing; conflict in AIMarketing.tsx imports resolved by keeping both).

### 2026-06-25 (pm-2) — GA4 + Clarity per client (PLUMBING BUILT; provisioning pending)
**Decision: OAuth Connect, not service account.** We have NO service account; our whole Google stack is OAuth refresh-token based. GA4 properties get created under OUR agency GA account (we own/retain data; client gets viewer access) → one-time agency OAuth grant, then automate. Clarity has **no project-creation API** — always manual.

Built (pipeline commit 7c4e29d):
- `templates/astro-starter/src/components/Analytics.astro` — GA4 gtag + Clarity, **no-op when id empty**. Wired into BaseLayout + LpLayoutV1/2/3 (site **and** ad LPs) across template + all 3 live sites. narestco site build verified (299 pages, exit 0).
- `brand.ts` gains `ga4MeasurementId` / `clarityProjectId`; `build_site.py` hydrates `BRAND_GA4_MEASUREMENT_ID` / `BRAND_CLARITY_PROJECT_ID` from `plan-input.json` brand block (so future scaffolds keep them).
- `scripts/analytics_set.py` — update-or-insert ids into a site's brand.ts + mirror to plan-input; optional `--push` commits/deploys the site's own repo.
- `scripts/create_ga4.py` — Analytics Admin API (OAuth) creates property + web stream per client, saves measurement id via analytics_set. `--auth-url` prints the consent URL; `--all --push`.

**Note on deploy:** monorepo `sites/` commit ≠ deploy. Each site is its own `{slug}-site` repo (Cloudflare Pages). `analytics_set.py --push` / `create_ga4.py --push` push the site repo to deploy. No rush — tags are no-op until ids set.

**STILL NEEDED from Santino (provisioning):**
1. **GA4:** add `analytics.edit` scope to our OAuth consent screen (needs Google Cloud Console), then one-time grant via the URL from `create_ga4.py --auth-url`; set `GOOGLE_ANALYTICS_REFRESH_TOKEN` + `GOOGLE_ANALYTICS_ACCOUNT_ID` in `.env`. Then I run `create_ga4.py --all --push`.
2. **Clarity:** manually create 3 projects at clarity.microsoft.com, send me the project ids → I run `analytics_set.py --slug <s> --clarity <id> --push`.

### 2026-06-25 (pm) — AI-search view + Action Plan alerts (BUILT)
Working through the 4-item plan in order. Local dev clone now in use: **`/tmp/rankai/Restoration-AI-APP`** (fresh GitHub clone; `npm run dev` → localhost:5173). Feature branch `feat/action-plan-alerts` is stacked on `feat/ai-search-view`, so localhost shows both.

1. **AI Search view (DONE — PR #13, app).** New `components/MarketingAISearch.tsx` + "AI Search" tab in `AIMarketing.tsx`. Reads `marketing_ai_search_scans`. Shows AI Visibility % (cited/total), per-query Recommended vs Not-mentioned cards (answer excerpt + cited domains, competitors highlighted / directories greyed), and "Who AI recommends most". **Strategist now weights AI visibility** (`scripts/strategist.py` `gather_ai_search()` → uncited money queries become high-impact `action_type='ai_visibility'` items naming the competitors AI cites instead). **Weekly AI scan** added to `weekly-maintenance.yml` (Monday + manual only, `ai_search_scan.py --all --limit 4`, runs before strategist). Pipeline commit b151548. All 3 clients scanned: narestco 2/4 cited, Davis 1/4, Home Pride 1/4.
2. **Action Plan alerts (DONE — PR #14, app).** Red **"Needs Attention"** section above routine actions. Strategist `gather_alerts()` writes `action_type='alert'` rows from (a) operator-set `clients/{slug}.json['ops_alerts']` and (b) auto-derived flags (red audit, empty queue, zero AI visibility). Alerts sort first. **narestco LSA-not-serving** added as its first ops_alert. UI: `MarketingActionPlan.tsx` splits alerts vs actions; managers get a "Resolve" button. Pipeline commit f1b18b0.

**ops_alerts convention:** add to `clients/{slug}.json` as `"ops_alerts": [{key,title,detail,severity,system,status}]`; `status:"open"` shows it, anything else hides it. Strategist picks them up next run.

**Merge order:** merge PR #13 first, then #14 (stacked).

### 2026-06-25 — strategy decisions (from Santino Q&A)
- **Credibility surfacing on client sites (the "Voda 10,000 reviews" lesson).** AI answers cite pages that prominently feature trust/credibility signals. Voda's "Over 10,000 5-Star Reviews" is a *headline claim* (aggregate across their national franchise), NOT a display of 10k reviews — plus a testimonials widget + trust badges (Google Guaranteed, IICRC). Takeaway: prominently surface each client's **REAL** credibility — actual review count + star rating (ideally pulled from GBP), awards ("voted #1 …"), certs (IICRC), years in business — in page titles/headers + Review/AggregateRating schema + a testimonials widget. Never fabricate numbers; grow them via the reviews push. → **Build queue.**
- **How AI uses reviews:** it repeats BOTH real platform signals it can read (Google/Yelp/BBB — it cited BBB + linked Yelp in the Federal Way result) AND self-reported on-page claims (it didn't verify Voda's 10k). So the play = drive real reviews on GMB/Yelp/BBB **and** surface them prominently on-site.
- **Onboarding wizard (planned, like the AI-receptionist wizard):** should (a) connect accounts via the standalone connect-links flow, (b) collect business info (NAP/services/areas/hours/license/certs), and (c) **collect accomplishments/awards/noteworthy achievements** ("voted #1 restoration company on the east coast", # jobs, notable projects). Reasoning: achievements are E-E-A-T + **AI-citation fuel** + content/sales differentiators. Store as brand credentials → content writer + strategist + GBP + site credibility section use them. → **Build queue.**
- **DataForSEO product strategy** (we charge $997/mo/client, so agency tooling that adds value is justified at scale):
  - **LLM Mentions API**: $0.10/req + $0.001/row + **$100/mo minimum = AGENCY-level (per DataForSEO account), NOT per client.** Adds AI *share-of-voice* / competitive mention analytics beyond the per-query scraper. Plan: keep the **scraper** (built, ~$0.075/q, no commitment) for core "are we cited"; **add LLM Mentions when we build the AI-search competitive/share-of-voice view** (powers the sales story; $100/mo amortizes to <$20/client at 5+ clients).
  - **Reviews API (Business Data)**: pull clients'/competitors' real Google/Yelp reviews + ratings → feeds the credibility-surfacing play + strategist review signal + competitive analysis. Strong candidate.
  - **Backlinks API**: authority signals (relevant to AI/SEO authority). Later.
  - At scale, move from pay-as-you-go to a committed DataForSEO plan for lower per-call rates.

### Build queue additions (from this session)
- Onboarding wizard (connect accounts + business info + **achievements/credentials intake**).
- Credibility surfacing on client sites (real review count/rating + awards + certs in titles/headers + schema + testimonials widget); drive reviews.
- Evaluate/add **LLM Mentions API** (when building AI share-of-voice view) + **Reviews API** (review intelligence).
