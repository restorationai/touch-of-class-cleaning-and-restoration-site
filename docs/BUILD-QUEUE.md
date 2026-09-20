# Build Queue — living document

Started 2026-09-20 from the FIX Restoration stage audit. This file is the
running queue Santino references; Claude keeps it current as items ship or
get added. Rule of the road: **nothing below runs without Santino's go**,
items run in letter order unless he says otherwise, and DONE items keep
their entry (with date) so the queue doubles as a change log.

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

## B. Reviews — **HELD for go**

- **B1** Auto-staging: received customer list (hub upload or texted file)
  → parsed (CSV/XLSX/contact export) → STAGED review-request rows →
  card shows "N contacts staged · awaiting activation" → Santino/CSM
  click activates. Includes backfilling Scott's already-received list.
- **B2** Review-readiness asks: list exists but sender prerequisites
  missing (no number / no EIN / compliance not started) → the review
  agent seeds the specific Monica ask automatically and the card shows
  WHY it's blocked. (FIX's EIN is the live example.)

## C. LSA leads-health — **HELD for go** (approved in principle)

Detector pulls LSA lead counts (calls + messages, 14d) next to the
impressions it already pulls; Running cards with 0 leads/14d wear a red
"0 leads / 14d — check on it" chip + a watchdog line; optional
needs-attention filter on the Running column.

## D. LSA connection gating — **HELD for go** (understanding confirmed)

Running (including impressions-based auto-serving) requires the detected
LSA account to be selected/attributed in the app. Detected-but-unselected
renders as Pending with "detected — needs connection" + one-click
"Attach this account". Matcher fixes ride along: our own claimed LSA
customer id counts as a match; "(other client)" label becomes
"(unmatched name)" when it's merely a name miss.

## E. ACS LSA revival — **HELD for go** (account identified)

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

## Standing watches (no action needed)

- DISS toll-free verification (pending review under IRS legal name).
- CRW A2P pilot at `a2p_trust` (Twilio reviewing the trust bundle;
  hourly advance handles brand → campaign; generalizing signup
  auto-provisioning unblocks AFTER this completes — it is the reason
  FIX has no sender yet).
- Fran/QCI rename reply; Alfredo DBA filing photo.
