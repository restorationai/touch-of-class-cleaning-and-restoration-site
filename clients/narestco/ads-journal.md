# Ads Journal — National Restoration Construction (narestco)

Running log of every change + decision on this client's Google Ads. Newest first.
Auto-appended by ads_manager.py change commands (budget / bid / pause / enable /
negatives) and by `note --add`. **Read this before touching the account; add an
entry after any change.**

<!-- entries below, newest first -->

## 2026-07-04 19:37Z · pause · customers/3832550597/campaigns/23943830377
Paused customers/3832550597/campaigns/23943830377. — _auto_

## 2026-07-04 19:37Z · pause · customers/3832550597/campaigns/23939263802
Paused customers/3832550597/campaigns/23939263802. — _auto_

## 2026-07-04 19:37Z · pause · customers/3832550597/campaigns/23934073908
Paused customers/3832550597/campaigns/23934073908. — _auto_

## 2026-07-03 17:05Z · tracking · sites/narestco LP layouts (deployed)
ROOT CAUSE FOUND + FIXED for the 6/29 broken click-to-call: Astro define:vars wraps each inline script in its own IIFE, so `function gtag()` in the loader never became window.gtag and the tel-click handler's `typeof gtag !== 'undefined'` guard was ALWAYS false — the conversion event never executed, on any tap, since launch. Google Ads side was verified CORRECT (Lead·Phone Call id 7647450951 ENABLED, primary, label matches brand.ts exactly). FIX: expose window.gtag in the loader + handler checks window.gtag + transport_type beacon (survives tel: navigation). Applied to LpLayoutV1/2/3 in ALL sites + astro-starter + ads-landing-page skill champions; narestco rebuilt (301 pages) + sync-deployed to prod. VERIFY over next 48h: Ads UI 'Lead · Phone Call' should flip to Recording conversions; cross-check daily vs Twilio 253-338-5162 (~1:1, ONE_PER_CLICK). Do NOT backfill 6/24-6/28 Twilio calls (no GCLID captured). — _claude_

## 2026-07-03 17:05Z · budget · all 3 SKAGs
RESTORED budgets cut on the false 0-conv signal: Water $62.50→$125, Fire $37.50→$75, Mold $37.50→$75 (pre-second-cut levels). Next step per plan: raise to $250/$150/$150 once gtag conversions visibly record (~3-5 days). Real economics per Twilio: ~2 calls/day ≈ $120/call vs $750 lead value. Budget-lost IS was 16-33% at the cut levels. — _claude_

## 2026-07-03 17:05Z · negatives · all 3 SKAGs
Added 15 campaign-level negatives ×3 campaigns (45 total) from the 7/03 deep dive: cerca (broad, Spanish variants), "handyman", "accuserve" (insurance TPA), "free mold testing", "free mold inspection", "renters", "king county housing repair", "oregon", "raincity restoration" + "five star restoration" (competitor brands, re-verified), "iicrc", [fire] + [black mold] (EXACT bare-word only — black mold removal stays live), "decon 30", "moisture absorber" (DIY). Geo confirmed PRESENCE-only on all 3 (out-of-state terms came via broad match, not geo settings). — _claude_

## 2026-07-03 17:05Z · watch · —
LP copy rewritten first-person (was lead-broker 'connects homeowners with independent contractors' boilerplate contradicting the licensed-GC brand; plausible bounce driver): now 'licensed and insured general contractor (WA License NATIORC792M6) since 2004', IICRC crew framing, real GBP proof 4.9★/53 reviews wired into brand.ts. STILL OPEN: majority of live keywords are BROAD (Water 76/29/9 broad/phrase/exact; Mold 93; Fire 84 broad) — tighten to phrase/exact per SKAG SOP as the next account action. Graduate to Max Conversions at 15-30 recorded conversions (~2-3 wks post-fix). — _claude_

## 2026-06-29 16:22Z · watch · —
MAJOR — CONVERSION TRACKING IS BROKEN, campaign IS producing leads (2026-06-29): Twilio subaccount logs show 10 CONNECTED calls to the tracking number 253-338-5162 over 6/24-6/28 (durations 11-159s, several WA area codes), all forwarded to 206-883-0333. Because ONLY the noindex ad LPs use 253-338-5162 (main site uses real NAP 206-883-0333), every one of these is an ads-LP lead. Yet Google Ads recorded 0 'Calls from ads'/phone-lead conversions over the same span (last call-conv was 6/23) — only GBP Local-actions (directions/other) registered. => The LP tel-taps connect but the gtag click-to-call conversion (AW-16824131335) is NOT firing/counting, so the campaign looks dead (0 conv) when it's actually generating ~2 calls/day. REVERSES the prior 'LP fine, traffic junk, no qualified traffic' verdict. ACTION: do NOT keep cutting budget on a 0-conv illusion; fix the click-to-call conversion (verify gtag fires on tap + action enabled/primary) or import Twilio calls as offline conversions. Trigger: Santino watched a Clarity recording (user 2ip9al) of a Bellevue-WA-water LP visitor tapping Call Now. LP + button verified WORKING (tel:+12533385162 live, HTTP 200); the (□□□) in the recording is Clarity text-masking, not a broken number. — _operator_

## 2026-06-29 05:54Z · note · —
Negative search-term pruning (2026-06-29, approved): added 7 phrase/broad negatives x3 SKAGs (21 total). cerca de mi (Spanish near-me, $88 leak), northwest restoration + homeguard environmental (competitor brands), drying out a basement + best way to remove black mold from shower (DIY), is mold damage covered by home insurance (informational), seattle home inspection cost (wrong service+shopper). ~$170/mo waste. NOTE: top 'wasted' terms were actually BUYER queries (restoration contractors near me etc) NOT negated — their 0-conv is the LP-engagement problem (GA4: paid sessions bounce 1-6s, 0% eng; Clarity: 15s active, 34% scroll), not bad keywords. Promoting DIY/informational ones to universal B.6. — _operator_

## 2026-06-29 05:54Z · add-negatives · customers/3832550597/campaigns/23943830377
Added campaign negatives: cerca de mi,northwest restoration,drying out a basement,is mold damage covered by home insurance,homeguard environmental,seattle home inspection cost,best way to remove black mold from shower — _auto_

## 2026-06-29 05:54Z · add-negatives · customers/3832550597/campaigns/23934073908
Added campaign negatives: cerca de mi,northwest restoration,drying out a basement,is mold damage covered by home insurance,homeguard environmental,seattle home inspection cost,best way to remove black mold from shower — _auto_

## 2026-06-29 05:54Z · add-negatives · customers/3832550597/campaigns/23939263802
Added campaign negatives: cerca de mi,northwest restoration,drying out a basement,is mold damage covered by home insurance,homeguard environmental,seattle home inspection cost,best way to remove black mold from shower — _auto_

## 2026-06-29 05:49Z · budget · —
Budget HALVED AGAIN (2026-06-29, Santino directive): Water $125->$62.50, Fire $75->$37.50, Mold $75->$37.50. Daily ceiling $275 -> $137.50. Rationale: GA4 (prop 543376986) + Clarity (proj xdoigoc8of) now wired — paid-search sessions land & bounce in ~1-6s, 0% engagement, 0 key events; Clarity avg active time 15s, scroll 34%, 13% dead-click. Pulling spend while we fix LP engagement + apply new negatives. NOTE: set-budget --campaign needs a RESOURCE NAME (customers/<cid>/campaigns/<id>), not a display name — name breaks GAQL. — _operator_

## 2026-06-29 05:49Z · set-budget · customers/3832550597/campaigns/23934073908
Set daily budget to $37.50. — _auto_

## 2026-06-29 05:49Z · set-budget · customers/3832550597/campaigns/23939263802
Set daily budget to $37.50. — _auto_

## 2026-06-29 05:49Z · set-budget · customers/3832550597/campaigns/23943830377
Set daily budget to $62.50. — _auto_

## 2026-06-27 20:08Z · apply-negatives · —
Applied 23 NEW negatives across 3 SKAGs (Santino directive): 20 BROAD (multi-word junk: competitors palouse/raincity/pacific/eco/groundworks, DIY/research, handyman/inspection/out-of-area) + 3 EXACT (['fire', 'narestco', 'handyman']). 'fire' added as EXACT [fire] — NOT broad — so it only blocks the lone-word search and does NOT block 'fire damage restoration'. Single-word negatives applied as exact to avoid over-blocking desired service queries. — _operator_

## 2026-06-27 19:41Z · note · —
Budget CUT IN HALF (2026-06-27, Santino directive): Water $250->$125, Fire $150->$75, Mold $150->$75. Daily ceiling $550 -> $275. Rationale: ~$2.5k/5d for 1 conversion (all on day 1), live SKAGs ~0 conv on broad-match junk; pulling spend back while we tighten match types + apply the 27 new negatives + let GA4/Clarity (now live) show post-click behavior. Bid strategy untouched (still Max Clicks). — _operator_

## 2026-06-27 19:40Z · set-budget · 23934073908
Set daily budget to $75.00. — _auto_

## 2026-06-27 19:40Z · set-budget · 23939263802
Set daily budget to $75.00. — _auto_

## 2026-06-27 19:40Z · set-budget · 23943830377
Set daily budget to $125.00. — _auto_

## 2026-06-24 19:45Z · location · —
Map-pack location assets (2026-06-24): on inspection, narestco's CORRECT GBP location (place_id ChIJ8URpSkf_UaURDg_hVb9wMrQ, asset 365472398992) is ALREADY linked account-wide via the ENABLED LOCATION_SYNC asset set 9118232479 ('Google Maps'). So the ads are already eligible for the local/Maps pack; not showing there is an AD RANK issue (still 55-58% IS lost to rank), not a missing-location issue. NOTE: a stray location asset 365472398989 (place_id ChIJP1UllmyLYogRrvhg5FrxH7U = a DIFFERENT business) exists but only in the REMOVED set 9117961649 — not serving; worth cleaning up. Systematized: ads_manager.scaffold now calls ensure_location_assets() which links the client's OWN GBP by place_id from plan-input (fail-safe: skips if no place_id match, never links a wrong/stray location). Verified against narestco live (correct place_id -> 'already linked'; wrong place_id -> skipped). — _operator_

## 2026-06-24 19:22Z · tracking · —
Call tracking unified to Twilio (2026-06-24): the 3 live SKAGs had NO call asset (the lone manual asset 206-883-0333 was on the PAUSED narestco-Search-2; the 6/23 'Calls from ads' conv on the Mold SKAG came via account-level calls-from-website/auto). Created a new call asset (id 378508981599) = Twilio tracking number 253-338-5162, call_conversion_reporting=RESOURCE_LEVEL -> conversionActions/7371348636 (same 'Calls from ads' $750 action preserved), linked to all 3 SKAGs. Now ad call-button calls route Google forwarding -> Twilio (253-338-5162) -> 206-883-0333, so every ad call is logged + recorded by Twilio AND still counts as a conversion. LP taps already used the Twilio number. OPEN LEGAL ITEM (deferred by operator): WA is two-party consent and the Twilio voice webhook has recording:true with NO disclaimer (recording_disclaimer:false) — add the 'this call may be recorded' notice to narestco.com/twilio/voice before relying on recordings. — _operator_

## 2026-06-24 19:01Z · review · —
REVIEW + FIXES (2026-06-24, via Claude/Santino): (1) GEO BUG FIXED — 6 of 10 targeted cities were in the WRONG STATE on all 3 SKAGs (Auburn AL, Kent CT, Bellevue IA, Kirkland IL, Everett MA, Redmond OR instead of WA). Swapped to the WA versions via API. Root cause: geo_lookup() matched city name with NO state filter and took rows[0]; FIXED in ads_manager.py (state-disambiguated + skips when no city+state match) so future builds cannot mis-target. Only narestco had live ads, so no other client needed repair. (2) NEGATIVES — applied 29 phrase negatives x3 SKAGs (87 total): competitor brands (delta/ars/voda/coit/northstar/attic projects), DIY/product (mold killer, mold abatement products, mold treatment for wood, iicrc, asbestos), janitorial (cleaning services / cleaning near me), roofing (roofers, roofing contractors), out-of-area (oregon backstop). Added coit/voda/delta restoration/ars restoration to universal D.1 and iicrc/mold abatement products/mold treatment for wood to B.6. (3) CONVERSION VERIFIED — the 1 conv (6/23, $750) is a REAL connected call: 'Calls from ads' via the GOOGLE forwarding number (metrics.phone_calls=1), NOT the Twilio LP number — so no recording exists (Google call-from-ads is not recorded; it bypassed Twilio). (4) VET BUG FIXED — ads_review.py vetter truncated at max_tokens=2000 so the JSON failed and ALL terms were kept unvetted; raised token budget + added salvage parser; dry-run now negates 26 correctly. 7d perf: $1644 spend / 190 clicks / 1 conv. Still 55-58% IS lost to RANK on 2 SKAGs — HOLDING bids per the 14-day rule (last change 6/22); NOT graduating to Max Conversions yet. — _operator_

## 2026-06-22 22:00Z · action · —
Added competitor negatives: 18 national restoration brands (servpro, servicemaster, belfor, puroclean, restoration 1, first onsite, ati restoration, etc.) now in the UNIVERSAL list (D.1, auto-applied) + local 'total restore' per-client. All 3 SKAGs now ~251-256 negatives. NOTE: a future Competitor Conquest campaign must have 'conquest' in its name — apply-negatives skips those so it can bid on competitor brands. Also FIXED a bug: apply-negatives was crashing on the LSA campaign (LSA rejects keyword negatives) which aborted the whole run — now targets SEARCH campaigns only + is resilient per-campaign. — _santino_

## 2026-06-22 21:59Z · apply-negatives · —
Applied the universal negative-keyword list. — _santino_

## 2026-06-22 21:58Z · add-negatives · customers/3832550597/campaigns/23934073908
Added campaign negatives: total restore — _santino_

## 2026-06-22 21:58Z · add-negatives · customers/3832550597/campaigns/23939263802
Added campaign negatives: total restore — _santino_

## 2026-06-22 21:58Z · add-negatives · customers/3832550597/campaigns/23943830377
Added campaign negatives: total restore — _santino_

## 2026-06-22 21:32Z · action · —
GET-CLICKS push (2026-06-22): (1) Removed the halted 'A/C LP' Water experiment — its trial campaign couldn't be paused (CANNOT_MODIFY_FOR_TRIAL); base Water is now the sole Water campaign. (2) All 3 SKAGs → Maximize Clicks (Mold was wrongly on Max Conversions with 0 data → underbidding), max-CPC cap $45→$80. (3) Budgets: Water $150→$250, Fire $100→$150, Mold $75→$150 (~$550/day ceiling). (4) BUG FIXED: apply-negatives only pulled Section A + B.1 — never B.6 — so restoration DIY/product/symptom negatives were NEVER applied to any client. Now includes B.6; pushed 224-229 negatives/SKAG. Added public adjuster, fire department, rmr 86, mold detection kit to B.6. MONITOR spend 48-72h; do not graduate to Max Conversions until 15-30 conv. — _santino_

## 2026-06-22 21:30Z · set-budget · customers/3832550597/campaigns/23934073908
Set daily budget to $150.00. — _santino_

## 2026-06-22 21:30Z · set-budget · customers/3832550597/campaigns/23939263802
Set daily budget to $150.00. — _santino_

## 2026-06-22 21:30Z · set-budget · customers/3832550597/campaigns/23943830377
Set daily budget to $250.00. — _santino_

## 2026-06-22 21:30Z · set-bid-strategy · customers/3832550597/campaigns/23943830377
Set bid strategy → maximize-clicks (max-CPC $80.00/click). — _santino_

## 2026-06-22 21:30Z · set-bid-strategy · customers/3832550597/campaigns/23939263802
Set bid strategy → maximize-clicks (max-CPC $80.00/click). — _santino_

## 2026-06-22 21:30Z · set-bid-strategy · customers/3832550597/campaigns/23934073908
Set bid strategy → maximize-clicks (max-CPC $80.00/click). — _santino_

## 2026-06-22 21:11Z · review · —
INVESTIGATION (no calls): verdict = TRAFFIC problem, not conversion/LP. SKAGs lose 55-89% impression share to RANK (Water 87-89%, ~52 clicks total/30d) and the clicks we get are broad-match JUNK (search terms: mold test kit, hydrogen peroxide for mold, mold exposure symptoms, public adjuster, everett fire department, general contractors, competitor names). Keywords are mostly BROAD (should be phrase/exact) incl malformed 'mold removal removal'. LP is FINE (loads, right H1, tracking # + AW-16824131335 gtag conversion present) — but no GA4/Clarity. Conversion tracking OK ('Calls from ads' $750 primary; LP 'Lead·Phone Call' $750 primary, 0 recorded = expected w/ no qualified traffic). STRAY: 'Water and Flood [A/C LP]' experiment still ENABLED (should be off). TODO: pause A/C LP, tighten match→phrase/exact, apply negatives, then add GA4+Clarity to judge LP once traffic flows. — _santino_

## 2026-06-22 20:58Z · review · —
30d/7d read (2026-06-22): 6 calls in 30d (5 from legacy narestco-Search-2 before it was paused + 1 LSA), 0 calls last 7d on $726 spend. WATCH: the 3 SKAGs spent ~$515/30d with 0 conversions and the enabled set shows 286 BROAD-match keywords + CPC $9.31 — verify match types are phrase/exact per SKAG SOP, and confirm the $750 value + biddable goals are attached (report shows ~$1/conv). Still cold-starting since ~6/18, so give it runway but tighten broad match. — _santino_

## 2026-06-22 20:58Z · watch · —
GRADUATE the SKAGs Maximize Clicks -> Maximize Conversions once ~15-30 conversions accumulate (~early July 2026): set-bid-strategy --strategy maximize-conversions. LSA is starved (3 leads/90d, none since ~May 28) — needs manual work in localservices.google.com (reviews, responsiveness, 24/7 hours), not a config issue. — _santino_

## 2026-06-22 20:58Z · bid · National Restoration Construction (all 3 SKAGs)
Raised max-CPC cap $30 -> $45. At $30 we were losing ~85% impression share to RANK. Don't change bid strategy more than once per 14 days. — _santino_

## 2026-06-22 20:58Z · note · —
Migrated to clean SKAGs: the 3 'National Restoration Construction - {Water/Fire/Mold}' campaigns are now our live structure, cold-started on Maximize Clicks. Budgets $150/$100/$75 per day. Legacy broad campaigns (Search-1, narestco-Search-2) turned OFF; the Water A/C-LP experiment off; LSA kept on. — _santino_

## 2026-06-22 20:58Z · tracking · —
Conversion tracking fixed: phone-lead value set to $750. Both PHONE_CALL_LEAD goals (WEBSITE + CALL_FROM_ADS) made primary/biddable; GBP local actions kept secondary. GBP/LSA conversions are API read-only (left at $1, secondary so they don't skew bidding). — _santino_


## 2026-07-04 19:25Z · pause · all campaigns
Client requested PPC pause (all 3 SKAG campaigns → PAUSED). Context: he reports
steady work coming from Gig Harbor, Tacoma, Bremerton, Port Orchard, University
Place — organic/GBP/AI channels. NOTE: click-to-call conversion tracking was
fixed 07-03 and budgets restored same day; tracking stays wired, so a future
restart begins with working attribution from day one. Restart checklist: enable
3 campaigns, verify conversion action still ENABLED/primary, re-check negatives
backlog. — _claude (per Santino)_
