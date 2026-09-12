# Rank AI — Build Queue

Canonical priority list. Updated 2026-09-11 (post attribution-suite +
call-intel + fleet-DNI night). Keep this file current when items ship or
reprioritize; the session todo mirrors it, this file is the durable truth.

## Ground rules that bind everything below

- **Hands-off clients**: Paul Davis Charleston and Go Green NC get NO work of
  any kind. Do not touch their GBP, site, ads, or records.
- **No em dashes in any client-visible text** (emails, SMS, site copy).
  Internal docs like this one are exempt.
- **Quiet hours**: no client sends outside their local daytime. Queue for
  their morning. GHL timestamps are UTC; convert before judging.
- **Registrar/NS work is human-only.** Browser agents get Google + Bing
  sessions only. setup@restorationai.io is the identity for all registrar
  and delegate accounts; contact@restorationai.io is the Google/Ads login.
- **Approval-gated sends**: Monica never claims/confirms what she can't
  verify (three incidents the week of 09-08). Anything novel she'd send
  goes out in approval mode first.
- **Single source of truth**: one canonical store per fact. Never ask a
  client for data we already hold. Never create a second copy of state.
- **GBP renames are never auto-pushed**: DBA first, then citations/signage,
  then ONE profile edit. NaRestCo never gets review campaigns.
- Monorepo `~/Desktop/mywebsitecode/rank-ai` (this repo). App repo clone at
  `~/Desktop/mywebsitecode/app-work` (never read the stale Desktop -main
  zip). App changes: serve the branch on localhost:5173, merge to main only
  after Santino confirms. `sync-deploy` needs a CLEAN tree and stamps
  clients/{slug}.json after each deploy: commit the stamp or the NEXT
  deploy silently refuses (error prints before the banner; easy to miss).

## Priority builds

1. **Monica calendar-awareness + booking — SHIPPED 2026-09-12.**
   New-booking flow live: classify 'booking' intent; books the client's
   proposed time when genuinely free past a 6h floor, else offers real
   Live Support free slots (one per day); confirms ONLY after the calendar
   POST returns an id. Fran-case claim guard in _CAPABILITY_CLAIMS (drafts
   can never confirm times; 'on the calendar for' + reschedule confirm
   stay legal). Selfcheck ALL GREEN. Original spec below for reference.
   WHY: three confirm-without-verify incidents the week of 09-08. Worst:
   Fran (QCI) asked "11am EST tomorrow good?" and Monica said yes without a
   calendar and never booked it (a human caught it; appointment was created
   manually). Monica must never state or confirm a meeting time she cannot
   prove.
   BUILD: (a) inject a next-48h booked-slots FACT into the compose context
   in scripts/client_concierge.py (GHL GET /calendars/events per calendar,
   ms epoch params — NOTE the endpoint returns the WHOLE DAY regardless of
   the window, filter client-side; see fathom_sync._appointment_anchor for
   the proven pattern); (b) a real booking action: POST
   /calendars/events/appointments with calendarId, contactId, startTime
   ISO+offset, assignedUserId xTuHtBz8G7Z4fyhAJ9kJ (Santino, required),
   appointmentStatus, ignoreFreeSlotValidation — proven working repeatedly;
   (c) a compose claim guard: no draft may confirm a specific time without
   a booking id behind it; (d) 6-hour minimum notice hard floor in code
   (the Live Support calendar BhEoJmoyowCaOpALMn61 allowBookingAfter was
   set to 6h on 09-11 — note this ALSO loosened the public booking link,
   which Santino may want reverted once the code floor exists).
   Calendars: Live Support BhEoJmoyowCaOpALMn61 (clients), Follow Up
   uZ7whcPD6NFDqcSu0hCf (prospects), kickoffs DcoatVel3rEw01lKoGlA +
   f6zNXUVXpPVdZtlknNNF, sales funnels 5GoVLLz9HDn8Ik3RjFMB /
   BOuvQbEVWGytVmoDxqrJ / Ya9jcpzKfBtfVJGHIyNS / nxDQ6IYn3QIIvrXS6Ib0 /
   szeyWKCEvVWkbFjMFtFT. GHL API: services.leadconnectorhq.com, Version
   2021-07-28 (contacts/convos) or 2021-04-15 (calendars), UA header
   "rank-ai-tollfree-autoreg/1.0" required. Related: fathom_sync.py already
   auto-books follow-ups FROM CALL RECORDINGS (client path + prospect path
   with GHL appointment-anchor); Monica's SMS/email lane is the gap.

2. **"Site preview ready" trigger — SHIPPED 2026-09-12.** sync-deploy
   now files a [PREVIEW PIPELINE] ops card the moment a client's FIRST
   build lands (redeploys stay quiet); reveal still rides the soak +
   hold/share-now overrides. Original spec below.
   WHY: DryCor's finished site sat on staging 10 days with no reveal.
   Root causes all fixed 09-11: the reveal gate only knew staging statuses
   (now accepts pushed_main when apex_live=false), and the app board called
   pushed_main "ready to launch" (now Preview Ready until the client has
   seen it). What remains is EVENT-DRIVEN notification: today the reveal
   card is seeded by the nightly setup_ledger pass, so a build finishing at
   9am waits until the next ledger run.
   BUILD: at the build_status transition (build_site.py sync-deploy writes
   it), file the ops card + queue Monica's preview message in APPROVAL mode
   (never auto-send). All the supporting machinery exists in
   scripts/setup_ledger.py (~line 2130-2240): 10-day perception window,
   "share now" note override, "hold/don't share" note hold, card seeding
   into marketing_action_plan (action_key site-preview-feedback-{slug},
   title "Take a look at your new website preview...", target = the pages
   URL). client_concierge.py PREVIEW_SOAK_DAYS=10 with the same share-now
   override; the [preview-share] promoter pushes the card above every other
   ask once released.

3. **All Pro homepage fixes (Angie, 09-11)**
   WHO: Angie Morabito (angie@prorestorationca.com) runs BOTH ProRestoration
   (prorestoration) and All Pro Plumbing (all-pro-plumbing, owner Jack
   Bispo). She emailed the getrest inbox 09-11 (left her work phone home).
   Ack was sent same day from contact@getrestorationai.com; promise was "a
   preview link as soon as the updates are up" — NO date promised.
   HER LIST for sites/all-pro-plumbing: (a) the van/fleet images "look like
   mini wind-up mail vans" — regenerate the AI hero fleet per
   clients/all-pro-plumbing/image-style-guide.md (real logo on livery,
   3 matched vehicles rule); (b) remove the red and blue lines; (c) palette
   red/white/blue ONLY, no black; (d) move the phone number + free-estimate
   CTA left so vehicles stay visible — NOTE: the hero two-column grid is
   now unconditional in the template AND was copied to some sites; check
   whether all-pro-plumbing/src/components/ui/Hero.astro already has it
   before doing layout work. Deploy staging, eyeball, THEN reply on her
   email thread with the link (from the getrest mailbox, reply-all).

4. **Fleet attribution follow-through**
   STATE: the source-attribution suite is live fleet-wide since 09-10/11.
   Per client: up to 9 tracking numbers (website/gbp/google_ads/yelp/
   chatgpt/gemini/bing; RT Olson also keeps facebook+instagram and has the
   only meta_ads number, (951) 261-8890). 196 numbers verified. Numbers
   live in companies.integration_settings.call_tracking; calls log to
   marketing_tracked_calls with .source; site DNI fetches
   restorationai.io/dni/{slug}.json (Cloudflare KV ns 404d46bf..., synced
   by scripts/dni_sync.py FROM integration_settings — never hand-edit);
   forms post /api/estimate -> marketing_form_submissions with source.
   NOTE 09-11: organic-social numbers (facebook/instagram) were RELEASED
   fleet-wide except RT Olson (58 numbers, ~$67/mo saved); meta_ads is an
   on-demand source, not in call_tracking.ALL_SOURCES.
   TO DO: watch the first source-tagged calls/leads accumulate a few days,
   then send channel-data proof emails: Miguel Padilla (miguel@
   icatchgroup.com, runs RT Olson ChatGPT campaign, cc tim@icatchgroup.com)
   and Bobby (bob@rtoplumbing.com). BDA (zheng@/jared@/belinda@bdadigital.us)
   already has the meta_ads number + UTM instructions (utm_source=facebook&
   utm_medium=paid) from 09-11; their Tuesday 9am call reviews it.

5. **Railway git checkout**
   WHY: the app's "Push site to production" button dispatches site_push_main
   to the Railway worker (rank-ai-api-production.up.railway.app), but /app
   has NO .git — the job cannot work as written. Also missing from the
   image: the agency GSC token and googleapiclient (GSC provisioning
   currently runs only on Santino's Mac via a scratch venv).
   BUILD: bake a monorepo clone + GITHUB_PERSONAL_ACCESS_TOKEN into the
   Railway service, make site_push_main do checkout->sync-deploy, add GSC
   token + googleapiclient. Payoff: full launches (incl. cutover stamps +
   GSC registration) with zero pipeline-machine involvement.

6. **Repiping default-on for plumbing plans**
   The plumbing vertical template already carries the repiping service;
   plan_site.py service selection should include it for every plumbing
   client by default (it is high-margin and every plumber does it).
   One-line-ish change in the plan defaults; verify against RT Olson's
   catalog (the client that surfaced it, 09-10).

7. **Tony/Coastal linktree page (+ his social icons ask)**
   WHO: Tony Mendez, Coastal Restoration Services (slug
   coastal-restoration-services, callcrs.com, Santa Maria CA). Monica
   history: the Tony Mendez case is why Monica never says "Santino will
   call you".
   PART A (queued): a small branded links page — Call / Website / Leave a
   Review — then flip the qr:coastal Cloudflare KV target to it.
   PART B (his 09-11 ask): Facebook/Instagram icons on his site footer.
   The template ALREADY renders social icons automatically from
   brand.sameAsUrls (Footer.astro matches facebook|instagram|linkedin|
   youtube|twitter). Coastal's sameAsUrls has maps/yelp/bbb/angi/bing but
   NO FB/IG because the profile harvest never found them. Get the exact
   URLs from Tony (or find/create profiles), add them to his citation
   records, and the automated sameAs sync carries them into brand.ts on
   the next pass; icons appear on next deploy. Do NOT hand-edit
   sameAsUrls only in brand.ts (dual-store violation).

8. **Missed-opportunity / callback alerts**
   call_intel.py (runs per tracked call via CI "Call Intel" workflow)
   already transcribes (Whisper dual-channel diarization) and labels
   outcomes including missed_opportunity and callback_needed into
   marketing_tracked_calls.analysis. Nothing surfaces them.
   BUILD: (a) near-real-time alert to the client (SMS via Monica in
   approval mode, or an ops card first — Santino to pick); (b) fold outcome
   counts into the monthly report (scripts/client_report.py).

9. **Xtreme Clean tracking decision — likely DEAD**
   Set to status Inactive on 09-11 (Santino: no longer clients, remove
   from the app). The old open question (no-NAP client tracking approach)
   is probably moot. Confirm with Santino, then delete this item and skip
   them in any remaining passes (they had domain xtreme-clean.invalid,
   nothing live).

10. **DISS launch (Wix domain transfer)**
    dissrestoration.com is Wix-registered; Wix domains can NEVER change
    nameservers — launch = transfer the domain to our Cloudflare registrar
    (5-7 days), so start early. The Wix transfer AUTH CODE is already
    captured in Addi's GHL thread (09-09). Site is built (pushed_main);
    DNI tracking fields fill at provision. Contact: Addi McCamon
    (addi@dissrestoration.com, +18145736346, GHL kw2RVGfQZtfEttwO0Crx).
    Open blockers on the same client: toll-free verification REJECTED
    (+18448757718, "Business Registration Number Missing or Invalid" —
    EIN 20-2720165 flagged; EIN-CONFIRM ops note open 09-11), and the
    review campaign is staged but never dispatched (stage-dwell note).
    Registrar transfer execution is human/Santino-side per the
    registrar-human-only law; prep everything else.

11. **Yelp-listing tracking numbers**
    Tim Prüsener (Icatch) confirmed the pattern: Yelp's rep can backend-
    code a tracking number onto the listing so the public NAP stays
    consistent. Request via the Yelp rep per client. Shortlist Yelp-heavy
    clients; RT Olson first (needs his Yelp Biz access handy). Numbers
    already exist (the per-client "yelp" tracking number in
    integration_settings.call_tracking).

12. **Inbound MMS handling — SHIPPED 2026-09-12.** Root cause was NOT
    missing media code (ingest_inbound_media already files photos/vcards
    with vision) — the webhook ignored every contact except each company's
    single tracked primary, so colleagues like Addi were silently dropped.
    Fixed: _company_for_contact email/phone/company-domain fallback. Addi's
    photo backfilled to DISS branding; her thank-you fires Sat 10:02am ET.
    Original spec below.
    INCIDENT: Addi (DISS) texted "Here's our team photo" with a photo on
    09-10 and the inbound pipeline produced NOTHING — no ack, no filing,
    no ops card, no escalation. Text-only inbound classifies fine; media
    messages fall through entirely.
    BUILD: in the inbound webhook path (api/main.py -> client_concierge
    inbound): detect message attachments, download from GHL, classify like
    email_intake does for email attachments (logo/photos/doc via
    CLASSIFY_DOC_SYSTEM), save to Supabase branding/{company_id}/, send a
    warm ack, and file an ops card when placement needs human judgment
    (team photos = exactly the asset site builds want).
    BACKFILL: pull Addi's photo from the thread, file it, and have Monica
    ack in her morning window.

13. **BrightLocal Citation Builder pipeline (+ opening-hours fix)**
    scripts/brightlocal.py already proves the full recipe live (our own
    location, campaign 996268, credits 500->490): POST /manage/v1/locations
    -> POST /manage/v1/citation-builder -> wait lookup complete -> PUT
    .../confirm {package cb10..cb100} -> GET for citations_submission_status.
    Auth: x-api-key = BRIGHTLOCAL_API_KEY (.env). State in
    clients/{slug}.json under "brightlocal". CLI: audit / setup / order /
    status. ~490 prepaid credits remain (1 credit = 1 citation).
    BUILD: (a) trigger setup+order automatically at client launch;
    (b) poll submission status into citation_listings rows so the app's
    Citations board (BuildStagesBoard) shows CB progress per directory;
    (c) BUG: the location payload sends NO OPENING HOURS — several
    citation sites require them, which is almost certainly the campaign
    error Santino saw in the portal. Include hours from the client's GBP
    regularHours in the locations POST. If the portal error text says
    something else, get the exact wording and re-diagnose.

14. **NaRestCo flood/storm/biohazard/crime-scene ranking sprint**
    FACTS (verified 09-11): all five service pages EXIST and are live on
    narestco (flood-damage-restoration, storm-damage-restoration,
    biohazard-cleanup, crime-scene-cleanup, trauma-scene-cleanup) plus 39
    flood/storm city cross-pages out of 286 location pages. Content is NOT
    the gap; off-page signals are.
    STEPS in order: (a) GBP: add those services to the profile and audit
    whether an additional category fits (scripts/gbp.py, write access is
    approved); (b) internal links to those services from the homepage +
    services hub (they are orphan-adjacent); (c) add the terms to geogrid
    tracking (clients/narestco/geogrid-keywords.txt) so movement is
    visible; (d) the Yelp overhaul — top manual item; emergency-intent AI
    answers pull Yelp+GBP entity feeds where narestco currently loses;
    (e) seed the terms into GBP review REPLIES (our replies to existing
    reviews — NOT review asks).
    LAWS: narestco NEVER gets review campaigns/asks. Their daily GBP posts
    come from a third-party Merchynt-like tool the client runs — do not
    double-post.

## Standing watches

- **DryCor preview send** — one-shot launchd job
  io.restorationai.drycor-preview-send fires Sat 9/12 9:32am PT (12:32pm
  ET, their morning), runs `client_concierge.py compose --company
  CO-1788205391336 --send`, logs to /tmp/drycor-preview-send.log, then
  deletes itself. Dry-run verified: SMS to Ashley Showalter with
  https://staging.rankai-drycor-restore.pages.dev. AFTER it fires: confirm
  in the log + GHL thread. Site state being previewed: 26 city pages, 234
  cross pages, charcoal canvas (#16181d, Santino's pick over the brand-kit
  petrol), red CTAs #e4002b, brand-kit orange as micro-accent, curated
  horizontal logo, no hero form (restoration = call-first).
- **RGP/Chesney (DryCor LSA handover)** — Carrie (carrie.price@drycor.com)
  asked us to take over LSA from Restoration Growth Partners; Robert told
  RGP "pause the leads" so DryCor's lead flow is STOPPED (time-sensitive).
  Facts: our MCC (201-884-4125) is already linked to LSA CID 816-134-6241
  BUT that account has ZERO leads all-time = a shell under the legal name
  "Showalter Construction & Restoration LLC"; RGP's real lead-carrying
  account is a different, unknown CID. Google is also warning the shell
  has no matching GBP — NEVER click "Create profile" (would duplicate
  their real GBP). Correction email sent 09-11: access must go to
  contact@restorationai.io (Chesney was about to send it to the TYPO
  domain contact@getresorationai.com from Carrie's original email). Watch
  the "DRYCOR Restore & RGP: Main Thread" (getrest inbox) for: the real
  CID, admin access grant, billing profile answer (if it bills RGP's card,
  move billing to DryCor before unpausing), verifications kept intact.
- **PuroClean day-7 search-term review (2026-09-15)** — campaign
  "PuroClean ELV - Biohazard Division" (id 24234476311, Ads CID
  1813437945). CRITICAL context: bids were broken from launch (all
  keywords unset -> $0.01 effective; found+fixed 09-12), so 9/15 is the
  FIRST window with real data. Current: Biohazard+Trauma $50 keyword caps,
  Crime Scene $30, budget $60/day, 10 job-seeker negatives added. Decide
  then: competitor-brand terms (bio one / 911 bio clean / aftermath
  cleaning) — negative them only on clicks-without-calls evidence. Journal:
  clients/puroclean-east-las-vegas/ads-journal.md (read before touching,
  append after). google-ads lib is NOT installed locally — use REST v25
  (narestco token + login-customer-id MCC works; see journal 09-12 entry).
- **Patti Collins follow-up (Thu 9/17 9:00am PT, CONFIRMED)** — AFC
  Cleaning and Restoration, Kansas City (GHL XRllC1w6ebN99NH563f2,
  pcollins@afcclean.com). Sales prospect from Levi's lane; recording
  fathom.video/calls/820426516. Deal shape quoted: $1,497 site build +
  $1,997/mo; they want to replace PPC+RealWorks with one provider, GBP/DBA
  multi-location strategy for KC metro, review program. Their internal
  steps before Thursday: RealWorks cancellation review (Tuesday), customer
  list export. Ours: proposal + GBP naming/DBA outline + mobile-first site
  examples + LSA competitive snapshot.
- **DIS toll-free verification** — +18448757718 rejected (business
  registration/EIN 20-2720165 flagged); EIN-CONFIRM ask is in Monica's
  flow; resubmit chain is automatic once the client confirms the correct
  EIN/legal name.
- **Kyle/Crew Sioux City GBP** — waiting on the Iowa state filing doc
  (Tonya digging); when it lands, create the second profile with Kyle as
  OWNER (not manager) and name it keyworded AT CREATION (see
  marketing_gbp_suggestions note for crew).
- **Amin / Dry Bros** — TWO open items from 09-10: Twilio TF verification
  rejected (+18336817307), and his G-Suite question WAS answered 09-10 3:38pm ("Yes, can you create that please?") — now WAITING on Amin to confirm info@drybros.com exists, then resubmit the TF (rejection code 3048) with the branded email. Site is pre-staging; DNI fills at first deploy.
- **Angie/All Pro** — preview link owed when queue item 3 lands (her
  thread lives in the getrest inbox).
- **Mac Mini runs** — the Mini is the browser-agent box (git-synced inbox:
  docs/MINI-OPERATOR.md -> mini-inbox.md -> mini-reports/). The LOCAL
  duplicate browser-agent sweep on Santino's Mac was disabled 09-12
  (~/Library/LaunchAgents/io.rankai.browser-agent-sweep.plist.disabled).
- **Frontline** — Monica's site-live announcement + EIN-CONFIRM ask ride
  her normal runs; the TF resubmit chain is automatic once the client
  replies. Site launched 09-10 on frontlinefireflood.com (26 cities).
- **Email intake (both mailboxes)** — as of 09-11 email_intake polls BOTH
  contact@restorationai.io AND contact@getrestorationai.com and Monica
  replies FROM whichever address the client wrote to; the 2-day stale
  backstop covers both. The local 5-min launchd poller is NOT loaded —
  replies ride the CI schedule (weekday concierge runs + daily ops sync),
  so weekend/inter-run email replies lag unless run manually.

## Recently shipped (context)

- 2026-09-11 day: HomeLyft launched app-native + GSC; TDI www live with
  entity rename to TDI USA, mitigation suppressed sitewide (SERVPRO
  conflict, central suppressedServices.ts), Manteca footer NAP; Frontline
  tier-2 territory build (9 -> 26 cities) + hub lists full 164-city
  5-county territory; bootstrap now seeds site cities FROM wizard
  service_areas (top 15-20 + expansion tiers recorded) instead of AI
  guessing; Kyle/Crew Sioux City GBP thread answered (DBA confirm +
  signage); QCI second-entity roadmap sent (QCI Restoration + triple-stack
  name option, qcirestoration.com)

- Source-attribution suite fleet-wide: 9 numbers/client (196 verified
  routes), DNI edge maps, form attribution, per-submission Website Leads,
  channel-filtered Calls tab
- Call intelligence: Whisper diarized transcripts (dual-channel split) +
  Haiku analysis on every recorded call, receptionist-style drawer, CSV
  exports, unified outcome column
- provision-all standard in onboarding; template-sourced DNI block
- Tollfree EIN rejections route to Monica (ask/confirm -> capture ->
  auto-resubmit with ladder reset)
- Monica: vision credential capture; apex-live probe self-healing;
  cutover panel provision-only job; Frontline launched end-to-end
