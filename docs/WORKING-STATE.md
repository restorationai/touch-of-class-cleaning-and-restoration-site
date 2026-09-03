# Working State — leave-and-resume doc

Updated: 2026-09-03 ~1:30 AM (PT). Keep this current when a work thread pauses.

## 2026-09-03 — QUEUE SAVED (resume here in the morning)

### Morning schedule (Thu Sep 3, all PT)
- ~7:00 daily ops lane: 4 unblocked auto site-builds fire (Frontline, DRYCOR,
  Arch, Xtreme — payment gate healed via Stripe backfill; Xtreme will stall on
  no-NAP, that's expected)
- 9:00 **Bobby** (RT Olson): review staging (blue-hood fleet hero, founders
  About, toilet-scene edit, ac-repair blue hood, "best plumber in Corona";
  424-URL 34-city expansion already LIVE on production). On his OK: promote
  staging visuals to main + run the remaining minimal-edit batch (9 images:
  gray pants + flag patches, 2 tan→blue shirts on leak-detection +
  indoor-air-quality, swap industrial pump on emergency-plumbing). His
  filtration flyer + DBA/GMB-name decision still owed by him.
- 9:07 Monica sends **Jimmy (Cal-West)** the site PREVIEW ask (hold note
  resolved; reveal = preview for approval, cutover only after his OK +
  Santino's typed domain).
- 10:00 **Shana** (Pro Restoration): everything live on
  rankai-prorestoration.pages.dev — hero with real ProMaster fleet from the
  canonical mockup (clients/prorestoration/van-wrap-mockup.jpg), Jack-at-sign
  About, all 13 red-shirt service images now navy, services banner navy.
  Known nits: tiny roundel text on far hero vans imperfect; flood-damage
  van text was flawed in the ORIGINAL (regen from mockup if she flags).
  Meta launch still blocked on Jack's payment method + budget.
- 11:00 **Josiah** (HomeLyft): prep BEFORE call — JobTread integration plan
  (direct API vs GHL bridge), LSA brand-search filter + flag miscategorized
  calls, tell him A2P/SMS registration is FIXED (UseCaseCategories enum) so
  he can resubmit. His side: card update link, domain access via Emily/
  Dwayne, customer list + team selfie, phone forwarding.
- **Greg** (PuroClean): Santino launched review campaign himself overnight
  (verify); still ours: smoke-damage GBP service (quick API add), trauma PPC
  plan for approval, press release, 40 citations (= BrightLocal first order).
  Billing paused (resumes Oct 4). Sep 5 11am check-in booked.

### Build queue (order agreed with Santino)
1. **Stripe reconciliation sweep** — nightly Stripe-paid-invoices vs
   billing_invoices diff + backfill (webhook race fix + 10-row backfill
   already LIVE; sweep is the self-heal layer). Include ProRest "daily
   rating freshness" sub-item: rating/count refresh daily via DFS fallback
   (their GBP API returns 0 reviews — count stuck at 105 vs real 107),
   deploy only on change.
2. **Ops Attention revamp + client side panel** — collapse/minimize notes
   (402-item Today tab unusable), GHL-style condensed per-client slide-in
   with tabs Notes / To-dos (checkbox worklist both humans and agents write
   to, via marketing_ops_notes worklist flag) / Activity. WAITING on
   Santino's GoHighLevel reference screenshots for design pass.
3. **Perception-window pieces** — 7-day site-reveal grace as system default
   (note mechanism = override; dated-hold auto-expiry already SHIPPED) +
   hide in-app preview link until day 7 + image ROLE metadata guard (the
   review-campaign face can never be wired into a site slot again — the
   RT Olson About regression).
4. **Content-now / brand-later builds** — build sites immediately at signup;
   logo auto-harvest from client's old site (fallback franchisor → Monica
   ask); colors via brand_colors_sync on logo arrival; logo soak stops
   delaying content.
5. **Dev-agent scale-up** — agent dispatches render-heavy cards to the build
   pipeline; nightly render sweep for changed plans; 2-bucket parallel
   matrix with per-client claiming (staging→production promotion stays
   human by design). Brief now carries image rules 2a-2e (AI-standard,
   smallest-change, composite-text, real-photo references + real geography,
   canonical vehicle mockup + deterministic recolor first).
6. **Post-meeting recap messages** — "what we're doing / what we need from
   you" after every call off fathom_sync extraction + stale-item nudges.
7. **BrightLocal citations** — Phase 1 location sync (free) → supervised
   first order on draft campaign 996268 → Greg's 40 → fleet. Key live,
   500 credits. Still owed: Harry email (Listings API path + credit draw).
8. **LAST: Monica campaign-activation checklist** — full auto-launch intake
   (list parsed, selfie or explicit skip, name-spelling confirm, review-link
   verification, sender + pace), reply-to-checklist matching (the Jared
   gap); DISS = pilot (list uploaded, account active), Frontline = second.

### Standing decisions parked with Santino
- Fleet multi-radius pricing: full standard ~$700/mo vs home-radii ~$500/mo
  vs tiered (24 clients still single-radius)
- CRW cutover (after Jimmy approves preview; type the domain)
- Delete Railway geogrid-cron service (obsolete, replaced by GH Actions)
- GHL screenshots for Ops Attention redesign
- Payment link confirmed staying $997/mo (the $1,297 link also exists)

### Standing watch/trace
- GSC spam property (baginda168/garuda55), Gmail OAuth consent paste,
  Kenny stats send, Scott growth-plan OK, Randy/EIN replies, DISS PA-city
  ring proposal awaiting confirm, Davis Construction has NO findable GBP
  (Greg D. conversation), Xtreme Clean has no NAP.

## 2026-09-02 — geogrid self-running end to end + BrightLocal API live

- **Geogrid is now fully native/server-side, all VERIFIED with live runs**:
  signup (stripe-webhook) and BOTH Google-connect edge fns dispatch
  client-ops-sync.yml; app "Refresh scan" button (geogrid-refresh edge fn,
  6h cooldown) + geogrid-scan.yml; bi-weekly fleet cron MOVED Railway →
  GitHub Actions (1st+15th 09:00 UTC — Railway image was stale: Aug 15 run
  saw 5 clients, Sept 1 crashed mid-narestco). Same-day dedupe in
  geogrid_cron makes reruns/overlap $0. **Santino: delete Railway
  geogrid-cron service (one click, obsolete).** Fleet run = 532 scans
  ≈ $180/run ≈ $360/mo — flagged to Santino, trim on request.
- **DryCor incident closed** (see memory zero-scan-guard.md): 5 actives had
  zero scans ever; DryCor/Paul Davis/MCC healed + scanned (MCC listing is
  named "Masters Carpet Cleaning..." — ranks ~0 for restoration terms,
  client conversation); davis-construction has NO findable GBP, xtreme-clean
  has no NAP — both fire daily *** NO MAP DATA *** digest lines (tripwire
  verified live in run 33606056124) until resolved.
- **"Suspended" status now inactive in ALL 9 roster gates** (geogrid, gbp,
  citations, concierge-mute, press, scheduler, analyzer, service-trim,
  report) — Burley + Coastal were still being scanned/messaged.
- **BrightLocal key LIVE** (memory brightlocal-api.md): x-api-key,
  /manage/v1; locations CRUD + citation-builder + credits(500) verified.
  Plan delivered in-session: brightlocal_sync.py location upsert → CB
  campaigns (skip live/browser-agent/client-owned dirs) → nightly status
  poll into citation_listings source='brightlocal' → existing Listings view
  + sameAs sync + NAP audit inherit. First order = supervised, on draft
  campaign 996268 (Restoration AI itself). NO auto-ordering; email Harry
  for Listings-API path + Quick-credit auto-draw (awaiting Santino's go).

## 2026-08-30 (Sun night) — reports v2.3 + Burley suspension

- **Burley SUSPENDED for non-payment** (CO-1785945543613, Russ Burley,
  Restoration 1 franchisee): trial ended Aug 12, $997 invoice open, 9 failed
  Link charges, Stripe dunning exhausted + subscription auto-canceled.
  companies.status=Suspended (drops him from ops-sync/Monica/reports gates).
  **DECISION 2026-09-30: delete the account if still unpaid** (ops note filed,
  needs Santino's explicit go; hosted pay link is in the note if Russ returns).
- **Reports: "Where you rank" section SHIPPED** (client_report.py
  rankings_section): GSC page-1 terms + pages-shown (28d vs prior), geo-grid
  map table (latest per keyword+city, 60d recency, trend arrows) + embedded
  R2 heat-map PNG, AI visibility % from marketing_ai_search_history + real
  cited-query examples. TRG shows 44 page-1 terms / 714 pages / 53% AI.
  All 27 reports regenerated (same URLs).
- **Sweep FULLY UNBLOCKED**: Santino re-granted Full Disk Access to /bin/zsh
  (launchd-spawned zsh read the Desktop .env in a live test) AND the wake
  schedule is set (osascript admin prompt): `pmset -g sched` shows
  "wakepoweron at 9:28PM every day". First autonomous 21:30 run since
  Aug 23 is tonight.
- **Paul Davis logo**: official franchisor logo fetched from pauldavis.com,
  in branding bucket CO-1783462003421/brand/logo-pauldavis-official.png
  (citations gate reads bucket; no site dir exists for them yet).
- Houzz all-pro-plumbing still owed Monday AM (3rd same-day signup bounces):
  `python3 -m browser_agent.playbooks.houzz_state_machine all-pro-plumbing`

## 2026-08-29 (Sat) — citations day + auto-apply flip

- **GBP auto-apply SHIPPED + fleet-run** (4820be67): gbp.py auto-apply executes
  auto_safe service suggestions (adds + negative-backed removals only; name/
  categories/address/pages stay one-click). First run: 49 adds / 12 clients,
  7 removals, all in marketing_gbp_changes + stamped on the app board. In the
  Monday workflow after optimize. Descriptions+attributes were already weekly.
- **Kenilworth VERIFIED from Jul 28 transcript**: Michael declined (Elite
  association, "don't want it to hurt what we have"); wants Island Park +
  Staten Island connected (link with Adi since Jul 28, still unaccepted).
  TRG FB/IG are Elite-branded = Monday talking point. TRG Monday pack:
  https://claude.ai/code/artifact/1804fc88-2871-4db0-b388-ece7f9fb490d
  (GSC 28d: 81,347 impr / 82 clicks, 3.3x/2.5x).
- **Citations**: sweep was DEAD ~1wk (Chrome held the profile at 21:30;
  cleared). Two manual sweeps: HomeGuide created cal-west + TDI
  (review_needed). TRG logo pulled from GBP → homeguide unblocked (tonight).
  BING login EXPIRED → Santino: `python3 -m browser_agent login`. PuroLV/
  HomeLyft/Pro Bing need owner to add contact@restorationai.io as GBP manager.
- **Apple**: API access requested in-portal 08-16, waiting on Apple email.
  Listing runs need Santino live (SMS code to phone ..49). 3 In Review.
- **BrightLocal**: committed to Simply Listings + $1,200/500 bundle (acct
  606053, verified); Harry must activate — pricing page is Contact Us.
- **City×service drains**: PuroLV (48pg) + TRG (318pg) building locally
  (nohup, log in session scratchpad); remaining ~600pg drain Mon 10am PT via
  gbp-maintenance (timeout now 300m; create-pages re-picks 'building' rows).
Deeper context: docs/seo-videos-gap-analysis-2026-08.md (SEO queue),
docs/bobby-olson-call-plan-2026-08-18.md (Bobby items + statuses),
docs/rt-olson-hvac-split-memo-2026-08.md (split recommendation).

## 2026-08-24 additions

- **Call-tracking DNI fleet LIVE**: 8 activated clients' sites display their
  agent/tracking number (source+schema keep real NAP; narestco verified on
  the live domain). Tool: scripts/site_call_tracking.py. GBP side already
  standard (gbp.py set-phone). OPEN: citations must build on the REAL line;
  provisioning for non-activated clients.
- **Cloud deploys PROVEN**: .github/workflows/deploy-sites.yml
  (workflow_dispatch, slugs+branch) sync-deploys from GitHub's cloud — no
  laptop needed once commits are pushed. Auth gotcha solved:
  persist-credentials false + GH_PAT url rewrite (bot credential 403s
  per-client repos). Validated green on narestco run 32721048464.
- **Review test-message feature** live on the Reviews panel (phone + step +
  name -> real sender, real link, MMS image when configured). Image style
  pack: no-Hey default, "!" always, Oswald/Caveat/Marker fonts, boxless
  whiteboard mode, borders, font max 300. RT Olson live campaign is
  TEXT-ONLY (whiteboard demo config saved but disarmed pending approval).
- TDI staging: construction rebuild w/ fixed hero truck, awaiting Rob/Santino
  approval before production.

## 2026-08-23 BIG SHIP DAY — current state

- **TDI Builders signed** (Rob Carpenter, Sacramento+Manteca, buildwithtdi.com
  → tdiusa.com). 211-page plan generated, rendered (~$8), staging deploy in
  flight. Kickoff meeting 08-24: walk clients/tdi-builders/docs/
  rank-ai-beyond-sop.md + tdi-build-plan.md. CSLB license MISSING (cutover
  blocked); leads go to THEIR HubSpot 48033708 + CallRail, not GHL.
- **Sarha round 2 DONE + verified live** (asbestos links stripped from 26
  files + redirects, mold wording protocol-based, verification before
  containment removal, more orange, old blog title gone). Replied IN HER
  EMAIL THREAD + Monica SMS. LSA answer in email was soft — real ask is her
  GL insurance cert; follow-up drafted, awaiting Santino go.
- **Review suite LIVE**: superadmin Campaign Sender Control on Reviews page
  (pool w/ live load, one-active-campaign-per-number), staged uploads
  (CSV/XLSX), Activate Review Campaign button. RT Olson: 6,667 staged
  (16.6k raw deduped), pinned to 3 Lions TF +18779194344, pace 4/20, gate
  ON. ACTIVATION = Santino presses the button (or says go).
- **Gate page**: light redesign (logo default, big faces) + now SERVED ON
  THE CLIENT'S OWN DOMAIN by the review-link-redirect worker (RPC carries
  branding; track_review_click captures sentiment/feedback). SPA fallback
  intact.
- **Media Library**: app sidebar "Files" tab per company (branding bucket,
  signed uploads, superadmin delete). media-library edge fn.
- **Suspend system LIVE**: pause click = Suspended + dunning
  (d0/d3/d7 human notices from Monica, d10 call card, d14 work-pause,
  d30 AUTO site takedown — pre-authorized by Santino 08-23). Coastal
  SUSPENDED (no payment method); d0 goes out Monday business hours.
  Mold Solutionz REMOVED (Inactive, citations purged, preview deleted).
- Bing: Google session restored in agent profile (Santino signed in 08-23);
  a parallel agent may be running Bing Places completion for 10 clients
  (Mold Solutionz removed from that list).

## PAUSED 2026-08-22 (Santino's machine going offline) — resume here

- Sarha's ONE combined message (corrections + visual refresh, both LIVE +
  verified on aircarerestoration.com): local watcher KILLED, cloud
  directive filed — Monica's 16:07 UTC slot delivers it machine-off-safe.
- RT Olson: 17,300-row customer export staged (harvested/ + his docs);
  Bobby wants the REVIEW GATE ON ("bad review blocker"). ENROLLMENT AWAITS
  SANTINO'S EXPLICIT GO (10x our biggest campaign; sender + gate check
  first). Reply to Bobby goes BY EMAIL in-thread when actioned.
- HomeLyft: pipeline nudged 5x then escalated 08-09 "needs a human touch
  (call them?)" — card 13 days old; decisions pending: escalation re-ping
  after a week + may Monica re-engage after 10d ladder silence?
- Kenny pace -> 3/20min LIVE. Sister-company double-ack FIXED + deployed.
- Bing + Apple: Santino signed into BOTH in the agent profile (window may
  still be open on his machine); tonight's 21:30 sweep validates Bing —
  only runs if his Mac is awake, else next night.
- Analyzer LIVE (script + Sunday cron + app Reports > Analysis tab, RX +
  Crew published). GSC panel: date ranges shipped.
- Watching: Bobby/Fran email replies (2f); citations nightly (rotation
  picks fresh 3); GBP junk-photo cleanup for RX still open; wrong-page
  fixes open; content-job hang root-cause open.

## Latest (2026-08-22): Sarha's corrections LIVE; RX diagnosed; priority feature

- **AIR CARE CORRECTIONS DEPLOYED + VERIFIED LIVE** (346 pages, lint 0):
  25 asbestos pages deleted, mold roles corrected fleet-of-pages-wide
  (remediation vs independent assessment consultant), licenses split
  (RCO1798 company / MRC2262 Sarha), insurance wording per her exact text,
  ~10 copy fixes, review count 15, CARE slogan. Design round = open
  [AIRCARE-DESIGN] dev card (staging review, NOT straight to prod). Monica
  directive filed for the morning slot (quiet hours held the instant send).
  claims_lint: listicle competitor review-counts downgraded to review sev.
- **RX decline DIAGNOSED**: impressions flat, ACTIONS collapsed in the
  08-06->08-21 maintenance outage window (posts + review replies dark);
  14 junk customer photos flagged; citations 2-of-15; wrong-page x5 open;
  organic ramping (0->32 clicks first GSC month). RX prioritized in
  tonight's rotation (verified first pick).
- **Citations priority feature LIVE**: citation_listings.priority +
  rotation ranks it first (consumed on pick) + popup buttons (company
  header + per-row) via build-stages prioritize_citations action.
- Concierge slots now run email_inbox_sync first (Sarha-promise gap).

## Latest (2026-08-21): pilots live — 2f sent, citations pipeline v1, Air Care LAUNCHED

- **2f emails SENT**: Fran (his Gmail draft, on-thread) + Bobby (from the
  getrestorationai.com mailbox he wrote to, in-thread, delegate-access
  version). Their replies are the live pilot of intake + reply-in-channel.
- **Citations pipeline v1 SHIPPED (no rotation yet, per Santino)**:
  public.citation_listings (RLS per-effective-company) seeded with 33 rows
  (fleet from browser-agent history + Reign pilot); build-stages fn v10
  projects citation_rows (deployed); BuildStagesBoard on branch
  feat/citations-popup (localhost:5173, NOT merged): tracker counts on
  citations cards, wrong_data forces gaps + red chip, click opens the
  detail popup (corrections, listing links, socials ladder).
- **Reign pilot**: yelp + mapquest rows status=wrong_data with correction
  payload (6691 TX-276 STE C); google/website live-correct; homeguide live;
  bing pending. Jerrott texted the update (address fixed, no re-verify).
- **AIR CARE LAUNCHED**: aircarerestoration.com cut over end to end
  (email-safe, NS flip by Santino, apex+www attached, verified from outside:
  llms.txt identity + zip 79602 on the live page), cut_over_at stamped,
  baseline captured (40 backlinks / citations 3 found, 10 missing).
  Sarha got the apology + verified-live text AFTER outside verification.
  gsc_register subprocess needs the 3.9 python (module error under CLI) —
  re-run pending.
- Next builds queued: launched-claim guard, social discovery pass,
  citations rotation (awaiting go).

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
  heartbeat THRESHOLDS covers the new job. E2E VERIFIED 17:00Z: sweep
  succeeded, ack SMS delivered on the canary thread ('Got the photo,
  thank you!...'), acked-path ledger + pending cleared, stranded cards
  filed live. Railway 'deployment delays' incident stalled rollout
  ~15:32-16:52Z (containers healthy, traffic flip stuck) — cleared.
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
