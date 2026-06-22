# Ads Journal — National Restoration Construction (narestco)

Running log of every change + decision on this client's Google Ads. Newest first.
Auto-appended by ads_manager.py change commands (budget / bid / pause / enable /
negatives) and by `note --add`. **Read this before touching the account; add an
entry after any change.**

<!-- entries below, newest first -->

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

