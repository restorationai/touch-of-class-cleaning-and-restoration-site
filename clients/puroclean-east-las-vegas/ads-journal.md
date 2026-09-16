# Ads Journal — PuroClean of East Las Vegas (puroclean-east-las-vegas)

Running log of every change + decision on this client's Google Ads. Newest first.
Auto-appended by ads_manager.py change commands (budget / bid / pause / enable /
negatives) and by `note --add`. **Read this before touching the account; add an
entry after any change.**

<!-- entries below, newest first -->

## 2026-09-16 18:40Z · bids/negatives · —
OPTIMIZATION per Santino (09-16 review): 11 phrase negatives added at campaign level - competitor brands (911 bio clean, steri clean, cory chalmers, bio one, bioone, aftermath, remnant, valor biohazard, crime scene clean team; evidence: the 911-bio-clean click never called, ~25% of impressions were brand-seekers) + informational (who cleans up, protocol). Crime Scene group cap $30 -> $50 (ad group + all 10 keyword bids; core exact was at 14% IS / 86% lost to rank). Budget HELD at $60/day - avg spend $21/day, losses are rank-based not budget-based. Reassess in 7 days on ATTRIBUTED call data (LP DNI fixed 09-16 - today is day one of real call visibility). — _operator_

## 2026-09-16 18:29Z · note · —
AUDIT (Santino ask: no google_ads calls in reports): 14d = 162 impr, 6 clicks, $148.79, 0 conversions. IS healthy post-09-12 bid fix (64-88%). ROOT CAUSE of zero attributed calls: the /lp/ landing pages never carried the DNI swap (LpLayoutV1-3 lacked the BaseLayout block) — every ad click saw the canonical (702) 551-3040 and the google_ads line (725) 223-0877 never displayed; Twilio shows 0 calls ever to that line. FIX: DniSwap.astro extracted + wired into all 3 LP layouts, deployed to production. Same fix applied to narestco (the zero-call-conversion mechanism there too). Ad calls attribute from today. — _operator_

## 2026-09-08 15:29Z · launch · Biohazard Division
LAUNCH: 'PuroClean ELV - Biohazard Division' ENABLED per Santino 2026-09-08 morning. $40/day, manual CPC. Watch plan: search-term review at day 7, prune negatives, then budget toward $50 if terms are clean. — _operator_

## 2026-09-08 15:17Z · build · —
BUILD: campaign 'PuroClean ELV - Biohazard Division' (24234476311) created PAUSED. $40/day, manual CPC $30 cold-start cap, geo Las Vegas/Henderson/North Las Vegas NV (verified constants). 3 ad groups: Trauma Cleanup (7kw), Biohazard Cleanup (6kw), Crime Scene Cleanup (5kw, 'suicide cleanup services' dropped per HEALTH_IN_PERSONALIZED_ADS policy), exact+phrase only. 631 campaign negatives (616 fleet-curated from narestco+crew accounts + 51 vertical). 1 RSA per ad group -> matching /lp/ pages. Click-to-call conversion 'Lead - Phone Call' $100 (AW-18217052718) wired into brand.ts, site redeployed. Per Greg 09-05 call: launch on approval, watch search terms week 1. — _operator_


## 2026-09-12 00:5xZ · bids/budget/negatives · Biohazard Division
DAY-4 REVIEW finding: keyword bids were NEVER SET (all 0 -> inheriting the $0.01 ad-group default; the 09-08 "manual CPC $30 cap" never landed). Explains IS 24% with 76% lost to RANK, 31 impr / $4.62 total. FIX per Santino: keyword + ad-group CPC caps now $50 Biohazard + Trauma, $30 Crime Scene; budget $40 -> $60/day; 10 job-seeker negatives added (technician/jobs/hiring/salary/training/certification/how to become/careers/resume). Search terms were CLEAN (all real biohazard intent). Competitor brands (bio one, 911 bio clean, aftermath) left serving - decide at the 09-15 review on click-without-call evidence. Applied via Ads REST v25 (google-ads lib missing locally). — _claude session_
