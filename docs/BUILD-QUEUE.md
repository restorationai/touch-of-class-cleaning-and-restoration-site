# Build Queue — living document

Started 2026-09-20 from the FIX Restoration stage audit. This file is the
running queue Santino references; Claude keeps it current as items ship or
get added. Rule of the road: **nothing below runs without Santino's go**,
items run in letter order unless he says otherwise, and DONE items keep
their entry (with date) so the queue doubles as a change log.

MCC auto-accept correction (2026-09-20): auto-accept DID exist — the
browser-agent daytime sweep ran accept_pending_links() daily until its
launchd job was disabled Aug 31 (Mini migration made sweeps supervised).
GBP-side invite+accept never broke (nightly since 08-04). The accept now
rides nightly ops-sync CI — machine-independent restoration.

Related standing queue: `docs/per-client-conversion-queue.md` (bulk-to-
per-client conversions — separate track, untouched by this file).

---

## 0. Scott / FIX Restoration — GBP connect nudge — **WATCHING**

Decision: wait for his organic cycle (Mon Sep 21, ~2 PM MT) rather than
send early. A monitor is armed that reports the actual message text the
moment Monica sends, and alerts if nothing goes out by 7 PM PT.
NOTE: with the soak fix (A2), FIX is past soak and the priority law sends
the SITE REVEAL first, GBP connect the next cycle — Santino may reorder.

## A. Website truth (the FIX class) — **DONE 2026-09-20**

- **A1** Reveal `sent_at` stamped at the actual send (concierge chokepoint);
  board silence-release anchors there. Backfill from real thread evidence:
  4 stamped, 7 truthfully "reveal not yet sent".
  - **A1 refinement (2026-09-20, Santino)**: silence promotes only after
    TWO touches — reveal → 2 quiet days → ONE follow-up (cooldown
    carve-out; the link-carrying follow-up stamps `followup_sent_at`) →
    2 MORE quiet days → Ready to Launch. Chips: "preview sent" /
    "follow-up due" / "follow-up sent" / "silence release (2 touches
    ignored)".
- **A2** Preview soak + ledger perception window anchored to immutable
  `scaffolded_at` (deploy-reset bug dead), paired with a finishing gate.
- **A3** FIX site prepped for his reveal: 4 generated before/after pairs
  (water/fire/mold/sewage, after = edit of before), TrustStrip + Reviews
  components refreshed (4 badges verified live), deployed + live-verified.
- **A4** Before/after pair generation runs automatically at every scaffold
  (service-matched, max 4; a populated work.ts is NEVER overwritten).
- **Bonus** `apex_live` false-positive killed: serves-us check now requires
  hashed-asset identity with our own deploy (FIX's old agency also ships
  Astro; the generic marker had stamped his old site as ours).

## B. Reviews — **DONE 2026-09-20**

- **B1** Auto-staging SHIPPED: hourly `review_list_stage.py` on the
  ops-worker turns every hub-uploaded list pin into STAGED rows via the
  proven `review_enroll.py --staged` loader (dispatcher-invisible; the
  existing Activate Review Campaign button goes live). First run cleared
  the backlog: HomeLyft 17 contacts (waiting since Aug 24!), DryCor 280.
  Unparseable files (PDF) get a one-time ops note; a list with NO phone
  column (FIX's names+emails export) seeds a Monica ask for a re-export
  with phones — staging is automatic when the new file lands.
- **B2** Readiness asks SHIPPED: list on file + no approved sender +
  missing EIN → a specific Monica ask is seeded (DryCor + FIX got theirs
  on the first sweep). The reviews card's red chip now says WHY:
  "sender blocked: no number, needs EIN" instead of a bare
  "not submitted". Staged mode no longer refuses on a missing sender
  (stage now, activate later — activation still runs the real preflight).


- **B3 (added 2026-09-20, NOT started)**: full sender auto-provisioning
  chain at signup — create the Twilio subaccount, buy the review-campaign
  number (LOCAL per the 09-18 decision, auto-forwarded to the business
  line), write company_phone_setup, then auto-submit compliance the moment
  the 3 conditions hold (info provided incl EIN + onboarding wizard done +
  Stripe customer on record). The BACK half (customer profile -> trust ->
  brand -> campaign, hourly advance; TF verification wizard + resubmit)
  already exists — B3 is the front leg + the 3-condition trigger.
  GATED: flips on only after the CRW pilot proves end-to-end (CRW is at
  a2p_trust, in Twilio review). Also: activation of staged lists stays a
  human click.

## C. LSA leads-health — **DONE 2026-09-20**

Detector pulls LSA lead counts (calls + messages, 14d) next to the
impressions it already pulls; Running cards with 0 leads/14d wear a red
"0 leads / 14d — check on it" chip + a watchdog line; optional
needs-attention filter on the Running column.

## D. LSA connection gating — **DONE 2026-09-20**

Running (including impressions-based auto-serving) requires the detected
LSA account to be selected/attributed in the app. Detected-but-unselected
renders as Pending with "detected — needs connection" + one-click
"Attach this account". Matcher fixes ride along: our own claimed LSA
customer id counts as a match; "(other client)" label becomes
"(unmatched name)" when it's merely a name miss.

## E. ACS LSA revival — **DROPPED 09-21 per Santino** (not needed)

Resolved itself: Alfredo self-toggles the account (change_event shows
elcabimero1971@gmail.com paused 9/19, re-enabled 9/20) and it is
producing (21 leads/14d, ~$329/7d). The leads radar (C) watches it
permanently; no revival work needed.

Real account = Google Guaranteed 723-080-5223 (Santino connected it;
calls as recent as yesterday). It was PAUSED within the last ~24h — same
window as the ex-agency drama; step 1 is who paused it + re-enable with
Alfredo's blessing, then the optimization pass (verification fully
PASSED: budget + settings are the whole job). Dead twin 481-522-7444
(no calls since May) gets noted and ignored.

---

## Parked decisions (Santino's desk)

- Yelp in or out of BrightLocal citation orders (google.com already
  excluded; Yelp discussion happened, no verdict).
- FIX Monday message order: site reveal first (priority law) vs GBP
  connect link first.

## Reviews go-live sprint (2026-09-20 evening)

- HomeLyft: two texts to Josiah SENT (campaign-ready confirm + team-photo
  question w/ upload link). ACTIVATION fires on his reply (photo lands ->
  attach to dynamic_images -> activate; "start without" -> activate now).
  337 contacts staged, sender approved. Gate currently OFF for them.
- DryCor: fully provisioned BOTH lanes 2026-09-20 — subaccount
  ACeffee350…, LOCAL +1 (813) 798-3837 (A2P lane, voice through the
  call-tracking review router, opt-out SMS handler), TOLL-FREE
  +1 (855) 983-1710 (agent_phone_1, autoreg lane). Submissions auto-fire
  when Ashley's EIN lands (Monica ask out): TF via nightly
  tollfree_autoreg watch, A2P via hourly advance. 280 contacts staged.
- Review gate leak FIXED: "Go back" removed from the feedback form
  (negative raters could return to the rating and reach Google).

## Standing watches (no action needed)

- DISS toll-free verification (pending review under IRS legal name).
- CRW A2P pilot at `a2p_trust` (Twilio reviewing the trust bundle;
  hourly advance handles brand → campaign; generalizing signup
  auto-provisioning unblocks AFTER this completes — it is the reason
  FIX has no sender yet).
- Fran/QCI rename reply; Alfredo DBA filing photo.
