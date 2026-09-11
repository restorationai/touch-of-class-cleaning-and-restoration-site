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
2. **All Pro homepage fixes (Angie 09-11, ack sent)** — new van/fleet
   photos (current AI hero vans look like wind-up toys), remove the red
   and blue lines, palette red/white/blue only (no black), move the phone
   number + free-estimate CTA left so vehicles stay visible. Send Angie a
   preview link when up (she was told "as soon as the updates are up",
   no date promised).
3. **Fleet attribution follow-through** — watch first live source-tagged
   calls/leads; follow-up email to Miguel/Icatch with RT Olson channel
   data after a few days; Bobby gets the same proof.
3. **Railway git checkout** — the app's "Push site to production"
   (site_push_main) needs a real git clone on the Railway service (no .git
   in /app today). Also fixes cutover stamp commits + enables full
   launches with zero pipeline-machine involvement. Include agency GSC
   token + googleapiclient in the Railway image while in there.
4. **Repiping default-on** in plumbing plan selection (template already
   carries the service; plan step should include it for every plumber).
6. **Tony/Coastal linktree page** — small branded links page (Call /
   Website / Leave a Review), then flip qr:coastal KV target to it.
7. **Missed-opportunity alerts** — call-intel now labels
   missed_opportunity / callback_needed; surface to clients (SMS or ops
   card) + fold outcome data into monthly reports.
8. **Xtreme Clean tracking decision** — no-NAP client; decide tracking
   approach.
9. **DISS launch** — Wix EPP code from Santino → transfer to Cloudflare;
   site carries DNI already (empty tracking fields filled at provision).
10. **Yelp-listing tracking numbers** — request via Yelp rep (Tim/Icatch
    confirmed the backend-coded pattern keeps NAP safe); shortlist
    Yelp-heavy clients; RT Olson first when Yelp Biz access is handy.

## Standing watches

- PuroClean day-7 search-term review (2026-09-15)
- DIS toll-free verification approval
- Frontline: Monica's site-live announcement + EIN-CONFIRM ask land on her
  9:07am PT run; resubmit chain is automatic once the client replies
- Mac Mini runs (git-synced inbox)
- Dry Bros + ACS (aldredo-moreno) get DNI at first deploy automatically
  (code committed, sites pre-staging)

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
