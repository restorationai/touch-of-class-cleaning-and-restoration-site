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
