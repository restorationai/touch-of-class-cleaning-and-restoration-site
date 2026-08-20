# Working State — leave-and-resume doc

Updated: 2026-08-20 (UTC). Keep this current when a work thread pauses.
Deeper context: docs/seo-videos-gap-analysis-2026-08.md (SEO queue),
docs/bobby-olson-call-plan-2026-08-18.md (Bobby items + statuses),
docs/rt-olson-hvac-split-memo-2026-08.md (split recommendation).

## Latest (2026-08-20 late): Monica 2d + 2e SHIPPED; Kenny campaign verified

- **2d reply-in-channel LIVE**: owed_reply_channel() upgrades compose/send_now
  to email when the owed reply arrived by email (proactive nudges stay SMS);
  email threading crumbs (subject + provider msg id) ride awaiting_reply;
  send_message sends GHL emailReplyMode=reply with plain-email fallback and
  Re: subjects. 14 selfcheck cases. Deployed both Railway services.
- **2e upload acks LIVE**: pg_cron `upload-event-sweep` (*/10, job 7) posts
  new branding-bucket objects -> Railway POST /upload-event ->
  client_concierge.upload_event(): ONE deterministic thank-you per client
  per burst; acked-paths ledger dedupes; hours-gated bursts persist and
  retry; 48h drop w/ log; system artifacts (review-qr) never ack; work_log
  'uploads-received' rows; upload_stranded_check daily (7-day re-flag
  dedupe) — FIRST RUN FOUND 9 STRANDED LOGOS (Puroclean ELV 31d, Go Green
  27d, Crew 26d, ServiceMaster 23d, RX 23d, Coastal 21d, Home Pride 12d,
  RT Olson 11d, Dry County 7d) — cards land on first live sweep; several
  may just need the action row marked done (logo may already be applied).
  heartbeat THRESHOLDS covers the new job. E2E: canary test photo uploaded
  15:50Z awaiting the 16:00Z sweep -> ack to Santino's phone.
- **Kenny/Paul Davis review campaign VERIFIED healthy** (his "no movement"
  reply): 1526 enrolled 08-11, 248 SMS out, 137 reached (pace 2/20min),
  40 clicked (29% CTR), 1 opt-out; link chain live-tested to his Google
  review box; sender = HydroZ fallback pin; Monica replied fine, nothing
  owed. His corporate-access connect link was the broken short-link class
  (fixed today); no Google connection yet = can't show review counts.

## Previous (2026-08-20): Fran's ten changes SHIPPED to preview + Monica video rule

- **QCI / Fran feedback round (lane 1) DONE, commit 195e3e42, staging deploy
  verified live** at staging.rankai-quality-contracting-inc.pages.dev:
  header logo removed (name in type); ALL free-estimate copy -> Request Service;
  all dollar figures stripped from 12 content files (lint-gated model pass);
  about meta + FAQ = incorporated April 2001; emergency page = his six services
  (capsule + card grid, "structural surety" is Fran's own term); his MA-CT-RI map
  on /service-areas/; van hero regenerated via nanobanana (2 passes, v2 kept:
  INSURANCE RESTORATION + WATER/FIRE/MOLD/FLOOD gold icon row, middle-van
  lettering cleaned, wall ghosting gone; v3 rejected for grain) in all 4 webp
  derivatives; PAY HERE found on qualitycontracting.us and ported VERBATIM
  (Authorize.net Simple Checkout LinkId 84c642bd...) into header + mobile nav +
  footer, 3 forms verified on the live preview.
- **Domain fixed along the way**: QCI record had domain=None (the
  domain-after-scaffold class). Real domain = qualitycontracting.us (his email
  domain; old site + Pay Here live there; Hostmonster NS flip target). Recorded
  in clients/quality-contracting-inc.json; brand.ts canonicalUrl, astro.config
  site, llms.txt, ai.txt healed of https://None; imagesBase="" + local
  public/brand/hero.webp replaces the broken images.None og:image fallback
  (was 404ing on 32 pages). NOTE: build_site sync-deploy has a rehydration
  guard since 08-11 (_rehydrate_domain) — the "unbuilt" note in memory is stale.
- **Fran reply draft READY**: clients/quality-contracting-inc/fran-reply-draft.md
  (per-item rundown, Auburn architecture answer, domains-question answer, asks
  if he wants CONSTRUCTION instead of FLOOD as 4th van word since his logo
  differs from his attachments; NO verification topic). Santino sends.
- **Monica video-verification rule (lane 2a) SHIPPED earlier this window**:
  prompt rewrite + video_verification_call_offer guard inside
  capability_violation + selfcheck ALL GREEN, committed, both Railway services
  redeployed.
- **Fran reply is IN GMAIL DRAFTS** on his thread (to fcarlo@, cc TOstrokolowicz@,
  draft id r5445986604550719178) — Santino reviews + clicks send. Nothing sends
  automatically.
- **Monica 2b sender map SHIPPED (08-20 second window)**: is_internal_sender()
  in client_concierge.py — any GHL row with a userId is OUR side regardless of
  direction (GHL's two-way Gmail sync logs Santino's external-mailbox sends as
  inbound WITH his userId; fleet sample 371 inbound rows -> 7 userId rows, all
  ours). fetch_inbound_since skips them (webhook + poll), fetch_history flips
  them to our side, transcript renders 'us-human' with updated prompt legends.
  Verified against Bobby's live thread: "These are perfect..." now us-human,
  0 processable inbound. Selfcheck +9 cases ALL GREEN; pushed (6d1185d8) and
  both Railway services redeployed.
- **JEFF SIBLEY / MCC INCIDENT (08-20) — root-caused + FIXED, Santino owes the
  personal call**: every /connect/{slug} SHORT link since they shipped 07-28 was
  100% broken: the worker mints a fresh signed jti per click but never inserts
  it into connect_links, while connect-link-exchange requires a matching row
  (its one-time check) -> clients cleared Google sign-in + consent, then hit
  "AUTHENTICATION FAILED / Link not found". Jeff hit it 3+ times (08-09, 08-16,
  08-20 screenshots), Monica kept re-sending the same link, he's furious
  ("Same shit for 2 months.. don't charge my account again"). FIX: connect-
  link-start now upserts the row after HMAC verification (ignoreDuplicates;
  fail-closed if the write fails) — deployed via supabase CLI + committed
  (app-work fdbbf5f), verified end-to-end (click -> row stored -> 302 Google).
  Jeff's EXISTING link works on his next tap. HOLD note 8c3306ca on MCC keeps
  Monica out of the thread until Santino personally reaches him (billing
  make-good = Santino's call). Fleet: last successful standalone connect was
  07-25 (pre-short-link); HomeLyft has an unused 08-03 pre-minted link (may
  have tapped a short one instead); other open connect asks will now succeed.
- **Next per BUILD-QUEUE.md**: Monica email evolution stages c-f (second-mailbox
  OAuth needs Santino sign-in, reply-in-channel, upload acks, Bobby+Fran pilot);
  then citations program; then social discovery sweep.

## Latest (2026-08-19 second pass): big-two + small batch + paired items SHIPPED

- **Area-page FAQs**: content already existed fleet-wide (1 unrendered page fixed);
  the real gap was schema wiring — FAQPage now emitted on area pages + areas hubs
  across 27 template trees, deployed fleet-wide (52 syncs), live-verified (edge-cache
  purge needed on live zones; narestco needed a second pass — patcher anchor bug).
- **Wrong-page-ranks monthly check**: scripts/wrong_page_ranks.py on GSC 28d data;
  WRONG_PAGE / BUILD_GAP / AREA_DEMAND classes (home-city + research-intent aware —
  first-run classifier flaws fixed by hand-review); 12 clients scanned, 91 findings,
  reports in clients/{slug}/seo/, deduped ops cards, wired into monthly-reports.yml.
  Home Pride: 52 area-demand queries = ring-expansion map (Marion/Kamas/Hoytsville UT).
- **Small batch**: hub QR screen asks reviews to mention service+city (SMS drip
  untouched per Santino); GBP services-topic posts deep-link the spotlighted service
  page (live-apex + 200-probe gated); 3rd weekly slot = gbp-posts-midweek.yml (Wed;
  posts + review responder only; verified via dry-run dispatch); GSC social = UI-only
  feature -> docs/gsc-social-connections.md click worksheet (18 clients mapped).
- **Job Stories before/after fields**: live on the hub (verified on Dry County's hub).
- **Plumbing prompts**: templates/plumbing/prompts/render/ (system + services-hub +
  service-landing) + vertical-aware scaffold overlay (tested on rt-olson).
- **Scheduler heartbeat**: public.cron_heartbeat() RPC + scripts/cron_heartbeat.py in
  client-ops-sync; FIRST RUN CAUGHT billing_monthly_reset failing daily since Jun 10
  (71 fails, renamed column) — investigated: Stripe webhook owns resets since the June
  migration, job was a dead duplicate -> UNSCHEDULED, note resolved.
- **Intake auto-satisfy**: rendered branded site closes brand-kit intake items (Kyle
  class); 5 stale items closed fleet-wide.
- **Self-hosted QR**: 21 per-client PNGs in branding bucket; hub serves them
  (qrserver = onerror fallback only); auto-generation on upload_links_sync.
- **Citations cleanup**: conservative rule (listing-match false AND no phone match);
  1 wrong-business entry flagged (flood-fixers houzz), HomeLyft's two kept (phone match).
- **Bing/Olson**: sweep run early; rt-olson queued for HomeGuide creation; results in
  the sweep log + browser_agent_actions.

## Previous (2026-08-19): safety trilogy SHIPPED, Yelp ON ICE

- **Pipeline safety trilogy done + reviewed**: (1) scripts/repo_git_guard.py — every
  automation git sync (cutover_execute, content_writer, ads_provision,
  case_study_intake) skips active sessions, aborts stranded rebases, never raises;
  (2) scaffold product guard — copy_starter merges code but preserves rendered
  content .md, public/images, image-meta.json, prompts/ (plus a rendered:true guard
  in write_content_md); (3) stage_checker MID-BUILD STALL alarm — 2d+ in building
  with a started-but-unfinished build alarms as Santino-owned (dwell-anchored, loop-proof).
  Review pass fixed: timeout leak in the guard, queued-behind-cap false alarms, and a
  test-inflicted empty image registry (restored, staging redeployed + verified).
- **Yelp playbook ON ICE (Santino + my recommendation agreed)**: needs a live
  code-relay loop + scheduled verification windows; runs LOCAL (Yelp bot defenses
  make cloud browsers impractical). When un-iced: phase 0 = Monica collects existing
  Yelp logins via secure share (skips the claim dance entirely for already-claimed
  pages); phase 1 = unattended audit + email-verifiable claims; phase 2 = phone-code
  windows. Fran incident fixed on the way: Monica's human-defer now keys on GHL
  userId everywhere (she was deferring to her own unrecorded webhook reply).
- Uploads gallery MERGED to app production.

## Where we were before the Bobby Olson sidetrack

Working the SEO gap-analysis queue, one item per Santino "go":
1. ~~Home-city cannibalization fix~~ **DONE 08-18**: plan_site skips the primary area
   for all new builds; 23 sites migrated with 301s, deployed main+staging fleet-wide,
   live-verified on 5 domains, work_log lines written.
2. **Yelp claiming playbook** (browser agent, supervised runs) ← NEXT on "go"
3. Area-page FAQs (FAQPage schema on area hubs)
4. Wrong-page-ranks monthly check (DataForSEO + GSC)
5. Small batch: review-card wording, GBP post deep links, 3rd weekly post slot, GSC social connections
6. Santino yes/no: BrightLocal spend for long-tail citations
New queue items from that session: YouTube buildout (question-videos + shorts + owner-avatar
pilot with Kyle), social-channel connections (phase 1 = handle fields + we click GSC; phase 2 =
Meta OAuth), citations program (agent + BrightLocal + tracking), visual sitemap generator
(post-#1, reveal-deck artifact).

## Bobby Olson (RT Olson + Dry County) — current state

- **RT Olson site**: 124 pages LIVE on staging preview, hero lead form, real van hero
  (wrapped Sprinter), real crew team photo, zero placeholders. Promised: done Friday,
  live before next Tue (follow-up call booked Tue). Production push NOT yet done.
- **Go-live blocker**: GoDaddy NS flip to amos + anastasia.ns.cloudflare.com (zone
  provisioned, email-safe, we hold no GoDaddy access — ask is with Bobby via Monica).
- **Monica directive filed** (note 89b734d8): emails Bobby preview + findings + NS ask
  during his business hours.
- **Review request test**: sent 9:00:01 AM his time, he clicked it. Step 2 drips Thu
  unless parked. Hub worker fixed: submissions now arm immediately (were parked forever).
- **Geo-grid**: 8 plumbing keywords x 5 cities configured, baseline scan stored 08-18.
- **Citations**: NEVER created for either company — queued for browser-agent runs; also
  investigate why nightly sweep skips post-08-09 clients.
- **Uploads gallery**: app shows team/ + docs/ + job-photos now — branch
  `feat/uploaded-gallery` on localhost:5173, AWAITING SANTINO CONFIRM before main push.
- **HVAC split memo**: drafted (one site + one GBP; ads-only domain fine). Bobby's
  agency audit went to getrestorationai.com inbox — Santino to forward to contact@.
- Waiting on Bobby: customer list, review selfies (him+Tim by truck, both companies),
  job stories from Jenny, real Dry County van photos (supersede invented fleet), the
  audit doc, GoDaddy NS change.
- 2 content-review lint flags open: santa-ana-ca lead-paint line, slab-leak blog
  insurance wording.

## Incidents this session (fixes shipped, lessons queued)

- rt-olson gitlink loop (8 nights of re-scaffold): fixed + guards in both workflows +
  scaffold try/finally.
- site-build scaffold-skip bug (brief plants logo first): check keys on package.json now.
- Plumbing template gaps: services-hub archetype added; site prompts patched in-place —
  QUEUED: port proper render prompts into templates/plumbing/.
- Scaffold clobbers rendered content (known NaRestCo gotcha, hit again): QUEUED guard.
- Local automation ran git pull mid-session → orphaned commits, 48 files shipped with
  merge markers, core images lost: all recovered; QUEUED: repo lock so crons don't do
  git ops while a session works.
- photo_harvest apply now re-applies when manifest says done but file missing (was the
  invisible-hero bug).

## Standing watchers / crons to be aware of

- Monica: 60-min human quiet window on every send; call requests = pass-along only.
- Ops pings → Santino's 808 (reverted from travel 805-539).
- Dry County dev-agent revamp SHIPPED (3-van hero live); optional van-lettering regen
  once Bob's real van photos arrive.
- Iowa DBA registry watcher (Kyle/Crew Sioux City) nightly; Apple Maps 3 listings in
  review (runs 2-3 pending); Air Care reveal + WordPress NS flip pending Sarha.
