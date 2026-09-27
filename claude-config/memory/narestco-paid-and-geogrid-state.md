---
name: narestco-paid-and-geogrid-state
description: "NaRestCo (CO-1771290587387) paid-ads + geo-grid state as of 2026-06-18, with time-sensitive follow-ups"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4d36230a-30f9-4230-8ffa-d814dc9fef8b
---

NaRestCo = company_id `CO-1771290587387`, Google Ads customer `3832550597`. State as of 2026-06-18:

**Google Ads (Search):** Only the 3 SKAG campaigns run — Water/Fire/Mold ("National Restoration Construction - {service}"), **cold-started on Maximize Clicks; max-CPC cap raised $30 → $45 on 2026-06-19** (after the fix worked — they went from ~0 to 141 impr/4 clicks on 6/18 — but were still losing ~85% impression share to RANK at $30). Budgets $150/$100/$75/day (only ~$46/day spending so far, lots of headroom). Legacy broad campaigns (Search-1, narestco-Search-2) + the Water "A/C LP" experiment are off; LSA kept on.

**Conversion tracking (fixed this session):** phone-lead value set to **$750**; the two `PHONE_CALL_LEAD` goals (WEBSITE + CALL_FROM_ADS) made **primary/biddable**; GBP "Local actions" are secondary. GBP-hosted + LSA conversions are API-read-only (left at $1, but secondary so they don't affect bidding).

**Time-sensitive follow-ups:**
- **Graduate the SKAGs** Maximize Clicks → Maximize Conversions once **~15–30 conversions accumulate (~early July 2026)**: `ads_manager.py set-bid-strategy --slug narestco --campaign <res> --strategy maximize-conversions`. Don't change strategy more than once / 14 days.
- **LSA is starved of leads** (3 in 90 days, none since ~May 28) — NOT a config/conversion issue (it's ELIGIBLE/serving). Needs manual work in the LSA dashboard (localservices.google.com): LSA-specific reviews, responsiveness, 24/7 hours. Owner action, limited API.
- **Geo-grid:** bi-weekly cron (`geogrid-cron`, Railway, `0 8 1,15 * *`) first REAL run is **July 1** — the Compare view's deltas are noise until then (the June 4 snapshot was backdated from a same-day run to seed Compare).

**2026-06-22 read:** 6 calls in last 30d (5 from legacy `narestco-Search-2` before it was paused + 1 LSA), **0 calls in last 7d on $726 spend**. The 3 live SKAGs spent ~$515/30d with 0 conversions, show 286 BROAD-match keywords, and CPC jumped to $9.31 — WATCH: verify match types are phrase/exact per SKAG SOP, and confirm the $750 value + biddable goals actually attached (report still shows ~$1/conv). Still cold-starting since ~6/18 — give runway but tighten broad match. Now logged in the client's ads journal.

**2026-06-24 review + fixes:** found a GEO BUG — 6 of 10 targeted cities were in the WRONG STATE on all 3 SKAGs (Auburn AL, Kent CT, Bellevue IA, Kirkland IL, Everett MA, Redmond OR instead of WA), the source of "oregon restoration" + much wasted spend. Root cause: `ads_manager.geo_lookup()` matched city name with no state and took `rows[0]`. FIXED live (swapped to WA) AND in code (geo_lookup now state-disambiguated, skips on no match) so future builds can't mis-target. Applied 29 junk negatives x3 SKAGs (competitor brands, DIY/product, janitorial, roofing); added national franchises (coit/voda/delta/ars) to universal D.1 + cert/product terms to B.6. The 1 conversion (6/23, $750) is a REAL call via Google's call-asset forwarding number (`metrics.phone_calls=1`), NOT the Twilio LP number — so there is NO recording (Google call-from-ads isn't recorded; it bypassed Twilio). Also fixed the `ads_review.py` vet step (max_tokens=2000 truncated the JSON → all terms kept unvetted → nightly auto-negatives were silently degraded for ALL clients). 7d perf: $1644/190 clicks/1 conv; still 55-58% IS lost to RANK on 2 SKAGs — bids HELD (14-day rule, last change 6/22).

See [[ads-skills-suite]], [[ads-journal-system]], and [[no-call-whisper]]. The ads cold-start lifecycle + impression-share diagnostic is documented in `Ads/bidding-strategy-playbook.md`.
