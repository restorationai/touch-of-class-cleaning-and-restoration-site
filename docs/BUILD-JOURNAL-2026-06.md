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
- **NEXT**: build `scripts/ai_search_scan.py` collector (money queries = service × top cities; scope to control cost), then app "AI Search" view, then strategist integration (AI visibility = high-weight signal).

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
