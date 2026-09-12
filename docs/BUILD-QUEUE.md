# Rank AI — Build Queue

Canonical priority list. Updated 2026-09-11 (post attribution-suite +
call-intel + fleet-DNI night). Keep this file current when items ship or
reprioritize; the session todo mirrors it, this file is the durable truth.

## Priority builds

1. **Monica calendar-awareness + booking** — third confirm-without-verify
   incident this week (Fran 11am EST). Build: next-48h booked-slots FACT in
   compose, real GHL booking action (free-slots API, assigned to Santino,
   6-hour minimum notice hard floor), and a claim guard: no draft may
   confirm a specific meeting time without a booking id behind it.
   Plumbing proven (appointment API works; calendar allowBookingAfter set
   to 6 hours on Live Support 2026-09-11 — NOTE: was 3 days; public
   booking link loosened too, revisit if unwanted).
2. **"Site preview ready" trigger** — no automated announce exists when a
   build reaches pushed_staging (DryCor sat on staging 10 days, nothing
   queued; previews have always been sent by hand). Build: on the
   pushed_staging transition, file an ops card + queue Monica's preview
   message in APPROVAL mode (never auto-send). DryCor itself: hold all
   sends until expansion + red accent are done (Santino 09-11).
3. **All Pro homepage fixes (Angie 09-11, ack sent)** — new van/fleet
   photos (current AI hero vans look like wind-up toys), remove the red
   and blue lines, palette red/white/blue only (no black), move the phone
   number + free-estimate CTA left so vehicles stay visible. Send Angie a
   preview link when up (she was told "as soon as the updates are up",
   no date promised).
4. **Fleet attribution follow-through** — watch first live source-tagged
   calls/leads; follow-up email to Miguel/Icatch with RT Olson channel
   data after a few days; Bobby gets the same proof.
5. **Railway git checkout** — the app's "Push site to production"
   (site_push_main) needs a real git clone on the Railway service (no .git
   in /app today). Also fixes cutover stamp commits + enables full
   launches with zero pipeline-machine involvement. Include agency GSC
   token + googleapiclient in the Railway image while in there.
6. **Repiping default-on** in plumbing plan selection (template already
   carries the service; plan step should include it for every plumber).
7. **Tony/Coastal linktree page** — small branded links page (Call /
   Website / Leave a Review), then flip qr:coastal KV target to it.
8. **Missed-opportunity alerts** — call-intel now labels
   missed_opportunity / callback_needed; surface to clients (SMS or ops
   card) + fold outcome data into monthly reports.
9. **Xtreme Clean tracking decision** — no-NAP client; decide tracking
   approach.
10. **DISS launch** — Wix EPP code from Santino → transfer to Cloudflare;
   site carries DNI already (empty tracking fields filled at provision).
11. **Yelp-listing tracking numbers** — request via Yelp rep (Tim/Icatch
    confirmed the backend-coded pattern keeps NAP safe); shortlist
    Yelp-heavy clients; RT Olson first when Yelp Biz access is handy.
12. **Inbound MMS handling (Addi/DISS 09-10)** — a photo SMS ("Here's our
    team photo") produced NOTHING: no ack, no filing, no ops card. Build:
    inbound media -> save to branding/{cid}/ (photos/logo classify like
    email attachments), warm ack, card when placement judgment needed.
13. **BrightLocal CB into the Citations stage** — brightlocal.py already
    proves the full recipe (location -> campaign -> confirm cb10..cb100 ->
    status). Wire it into the pipeline: auto setup+order at launch, poll
    citations_submission_status into citation_listings so the app's
    Citations board shows CB progress. ALSO: location payload sends no
    OPENING HOURS today — likely the portal's campaign error; include
    hours from GBP regularHours in POST /manage/v1/locations.
14. **NaRestCo flood/storm/biohazard ranking sprint** — pages already
    exist (all 5 incl. trauma/crime-scene, 39 flood/storm cross pages);
    the gap is off-page: GBP services+categories for those lines, internal
    links from home/hub, geogrid tracking for the terms, Yelp overhaul
    (emergency-mode AI answers pull Yelp+GBP feeds), review-reply keyword
    seeding. NO review campaigns (standing law).

## Standing watches

- DryCor preview send — scheduled one-shot Sat 9/12 9:32am PT (12:32pm ET)
  via launchd io.restorationai.drycor-preview-send; log /tmp/drycor-preview-send.log
- RGP/Chesney — LSA admin access grant to contact@restorationai.io
  (correction sent 09-11 after they nearly sent it to the typo'd domain);
  real lead-carrying LSA CID still unknown (linked 816-134-6241 is a shell)
- PuroClean day-7 search-term review (2026-09-15) — first review with REAL
  bids (unset-bid bug fixed 09-12: was $0.01 effective since launch); also
  decide competitor-brand negatives (bio one / 911 bio clean / aftermath)
- Patti Collins (AFC Cleaning, KC) sales follow-up — CONFIRMED Thu 9/17
  9:00am PT on the Follow Up calendar; proposal prep from the 9/11 call
- DIS toll-free verification approval
- Kyle/Crew — Iowa filing doc for the Sioux City GBP (Tonya digging)
- Amin/Dry Bros — Twilio TF rejected +18336817307; his G-Suite
  info@drybros.com question still unanswered
- Angie/All Pro — homepage fixes promised (queue #3); preview link owed
- Mac Mini runs (git-synced inbox)
- Frontline: Monica's site-live announcement + EIN-CONFIRM ask;
  resubmit chain automatic once the client replies

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
