# Ads Journal — National Restoration Construction (narestco)

Running log of every change + decision on this client's Google Ads. Newest first.
Auto-appended by ads_manager.py change commands (budget / bid / pause / enable /
negatives) and by `note --add`. **Read this before touching the account; add an
entry after any change.**

<!-- entries below, newest first -->

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

