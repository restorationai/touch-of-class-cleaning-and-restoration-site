# Rank AI — Build Journal (2026-07)

### 2026-07-01 — AI-search system, GBP automation groundwork, template fixes

Big session. Highlights, grouped.

**AI-search visibility system (the UVP).**
- **Demand engine** `scripts/ai_keyword_planner.py` (pipeline `b68a08b`): DataForSEO `ai_keyword_data` → ranks a client's services by *real AI search volume*; writes top untracked ones to `marketing_action_plan` (`action_type='ai_keyword'`). Surfaced the headline: NaRestCo's tracked term (water damage, ~1.1k/mo) is near the bottom; **mold removal ~16k, leak detection ~8k, mold remediation ~3.4k are untracked**. App "AI keyword opportunities" card with Prioritize + dismiss + volume sort (app `f259bc1`, `115c276`).
- **Phase 2 loop:** Prioritize now (1) inserts a tracked query into `marketing_ai_search_custom_queries` (next scan measures it) and (2) pins the row; `strategist.sync_content_queue` now matches `ai_keyword` and `content_writer next-post` auto-syncs pinned items, so a prioritized term gets written on the next content run (pipeline `48b7afb`, `1a17cff`; app `f2dffce`).
- **Claude** added to default AI-search engines (4-engine coverage, `1a17cff`).
- **Google AI Overviews tracker** `scripts/google_aio_scan.py` (`e63b12d`): SERP `load_async_ai_overview` on national informational queries → `engine='google_ai'` rows in `marketing_ai_search_scans` (renders in the AI Search tab, cyan chip). NaRestCo cited in 0/9 — the sources are restoration-company blogs (bukrestoration, palmbld, Paul Davis) + Angi/HomeGuide/Reddit = content/citation targets. NOTE: national/informational only (local commercial = map pack, already covered by geo-grid).
- **AI Search UI** grouped by question + color-coded engines (Gemini blue, ChatGPT green, Perplexity purple, Claude orange, Google AI cyan) (app `37e3d89`).

**Geo-grid fix (NaRestCo "collapse" was a mirage).** Root cause: **DataForSEO ran out of prepaid balance (402)** mid-run on 07-01 → all-red/avg-0 grids that looked identical to a ranking drop. Pipeline guard added (`d37b777`): retries $0/errored points, raises if >40% still errored so the cron skips the write (no poison rows). App UI now distinguishes "couldn't measure" (grey) from "not ranking" (red) and killed the null→0.0 "improved" bug (app `9d0aada`). Balance topped up ($200); NaRestCo backfilled (actually improving where measured); 12 dead rows deleted.

**Get-Listed ("authority targets").** `scripts/authority_targets.py` (`99897b9`, `0d27d16`): directories AI cites + national backlink link-gap → `marketing_action_plan` (`action_type='get_listed'`); core-directory seed for new clients; `--all`; monthly **Railway cron `authority-cron`** created (config `railway.authority-cron.toml`, runs authority_targets + ai_keyword_planner `--all --write`, 1st of month) + onboard baseline.

**Client-site template.**
- **Real-GBP map + NAP/Call card** on service-area pages (`5d38703`): free `output=embed` of the client's real GBP (renders with no API key — old Embed-API path showed nothing without a key) + styled "Serving {City} from our {HQ} office" card with Call Now / Get Directions. Conversion/reliability, not a ranking lever; `areaServed` JSON-LD was already correct.
- **TrustStrip fix** (`d8f00e1`): was hardcoded "12+ Years" on every site (contradicted "since {foundedYear}" copy). Now derives "Since {foundedYear}" per client — factual consistency = E-E-A-T + AI trust. Related class of bug: "Family Business" etc. are still hardcoded — audit later. Consistency is captured per-client via onboarding (Trust & Credentials step — planned).

**GBP automation groundwork.**
- **GBP API write access APPROVED** (unlocks posts[shipped]/photos/Q&A). See [[gbp-api-access-reapplication]].
- **Photo intake** [[gbp-photo-intake]]: public no-login upload links `restorationai.io/gbpphotos/{slug}` (Cloudflare Worker `gbpphotos-proxy` → `job-photos` edge function). EXIF/GPS stripped on-device; lands in `branding/{cid}/job-photos/`. Verified on a real NaRestCo upload. Consumers (GBP weekly uploader, website gallery) not yet built.
- **Q&A** — starting: `mybusinessqanda` seeding of universal questions on the listing; city/response-time questions go on per-city page FAQ.

**Onboarding wizard:** real photo uploads in Brand & Photos (app `7d415d8`); customer-list CSV step parked (bucket mime). Planned: Trust & Credentials multi-select (badges, years-in-business) → drives site build + kills hardcoded-claim inconsistencies.

### 2026-07-05 — Review Reactivation Engine backend (app branch `marketing-ui-refresh`, commit `7f5ba57`)

The in-app review engine now actually sends. Everything below is LIVE in prod (Supabase project `nyscciinkhlutvqkgyvq`); UI/lib fixes ship when the branch merges.

- **4-step SMS drip** (chosen over the 8-step skeleton for simplicity): Day 0, +2d, +3d, +2d, operator-approved donate-a-meal copy, per-company overrides via new `review_message_templates` (company_id, step, channel, body). `step_number` = next step to send; after step 4 → `completed`; a click (`clicked`/`reviewed`/`feedback_given`) stops follow-ups.
- **Dispatcher** `dispatch-review-requests` rewritten + deployed (verify_jwt=false), cron `*/10 * * * *` (pg_cron job 3; the old broken every-minute job with the never-configured auth header is gone). Gates: due (`next_send_at <= now()`, NULL = parked), not opted out, company-local 08:00–17:59 (`companies.timezone`), pace cap `companies.review_pace_per_20min` (default 2 per rolling 20 min). Lease-based claiming (`next_send_at += 15min` conditional update) — no more stuck `processing` rows, crash self-heals. Personalized MMS via the deployed `generate-review-image` fn when `dynamic_images` category `review` has a base image; else plain SMS.
- **Senders:** approved `company_phone_setup` subaccount + `agent_phone_1`; else fallback = master Twilio creds authenticating against the DryMedic subaccount's `+17542470132` (edge secrets `TWILIO_MASTER_*`, `REVIEW_FALLBACK_FROM`, `REVIEW_FALLBACK_ACCOUNT_SID`). Master's own only number (+18666184974) is a TF with REJECTED verification — can't send SMS. Hardcoded DryMedic creds removed from source.
- **RLS fixed:** dropped public SELECT + public UPDATE on `review_requests` (anyone could rewrite any row). Redirector now uses SECURITY DEFINER RPCs `get_review_request_public(slug)` + `track_review_click(slug,status,sentiment,feedback)` (clicked/reviewed/feedback_given only). Verified anon direct select/update return nothing.
- **STOP handling:** new `twilio-inbound-review-optout` fn (deployed) → `review_opt_out_by_phone` RPC (last-10-digit match) sets `contacts.opted_out` + `review_requests.opted_out/status='unsubscribed'/next_send_at=NULL`. Wired as SmsUrl on +17542470132 (was the n8n `sms-status` webhook). Per-company numbers need the same SmsUrl set as they come online.
- **UI fixes (branch):** Quick Add + bulk direct inserted phantom columns (`campaign_id`, contacts `company_id`/`status`) → fixed to `client_id` upsert on the real unique constraint, full request payload (tracking_slug/campaign_type/step_number/next_send_at); stats card counts real click statuses only; CSV contact insert fixed.
- **generate-review-image** source recreated in-repo from live probing (1200×675 PNG, cover-fit photo, rotated pill, always-200) — NOT redeployed over the working v15.
- **Stranded data:** the 6 `processing` rows parked (`pending`, `next_send_at` NULL).
- **E2E test:** enrolled +18053293449 under NaRestCo → SMS SID `SMa82f740f6ffdca0f545d70bf8f4bf96b` **delivered** from +18446420298; row advanced 1→2 (+2d); pace + hours gates proven live (due=2, sent=0: `pace_capped=1`, `outside_hours=1`); STOP simulation opted out all matching rows; test row left `completed`, all test state cleaned.
