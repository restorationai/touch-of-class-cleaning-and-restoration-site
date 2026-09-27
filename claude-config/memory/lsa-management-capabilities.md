---
name: lsa-management-capabilities
description: "LSA is FULLY manageable via Google Ads API (verified 2026-07-09) — budget, per-lead bids ABOVE the $1k portal cap, service areas; requires one-time EU political-ads declaration first"
metadata: 
  node_type: memory
  type: project
  originSessionId: b7646e8b-4a3a-42b9-809a-4dc1c55c9f5c
---

Google LSA management via Google Ads API — all verified live on narestco (acct 3832550597, campaign 22143629917) 2026-07-09:
- **Budget**: CampaignBudgetService mutate works (LSA budget = daily micros; portal shows weekly = daily×7).
- **Per-lead bids**: `campaign.local_services_campaign_settings.category_bids[]` (category_id like `xcat:service_area_business_water_damage`, manual_cpa_bid_micros). **Bids ABOVE the portal's $1,000 slider cap validate via API** ($1,500/$2,500 passed validate_only). narestco sits at exactly $1,000 (cap) — headroom usable.
- **Service areas ARE API-editable** (CampaignCriterionService location criteria) — earlier "portal-only" belief was wrong. GATE: campaign must first have `contains_eu_political_advertising = DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING` (one-time harmless mutate; Google rejects criteria/bid edits without it: "only allowed after you confirm... EU political ads"). Use GeoTargetConstantService suggest for city→ID (do NOT guess IDs — Olympia WA is 1027691, not 1027045).
- **LSA account discovery**: LSA provisions its own "Unnamed Account" customer separate from PPC; found via listAccessibleCustomers on the client's token. Cached in user_integrations.connection_metadata.lsa_customer_id.
- **Access**: we send CustomerClientLink invites FROM MCC 2018844125 via API (client gets Google email → Accept). Acceptance verified via GAQL customer_client_link.status = ACTIVE — never trust a checkbox.
- App: LsaPanel.tsx + edge fns lsa-status/lsa-manage/lsa-request-access (MCC creds in Supabase secrets GOOGLE_ADS_MCC_*). Writes superadmin-gated. Daily ads-sync workflow added (ads-sync.yml).

Client facts (2026-07-09): narestco LSA ENABLED $512.14/day, water bid $1,000. **Home Pride LSA acct 2957729882: budget $0.01/day (why 0 leads ever), categories Carpet Cleaning $23 / Junk Removal $40 / Water Damage $95, invite PENDING Kurt's acceptance.** Related: [[ads-skills-suite]], [[narestco-paid-and-geogrid-state]].

## flag_lead validated LIVE (2026-07-19)
- REST body confirmed good; the 403 USER_PERMISSION_DENIED was a login-header bug: NaRestCo (app company CO-1771290587387, Ads 3832550597, agency-connected token) is reached THROUGH MCC 2018844125, but flag_lead only tried direct+self. Fixed+deployed: tries stored login_customer_id → agency MCC → direct → self.
- First live flag: NaRestCo lead 326618953 (Jul 16, +12067787366) JOB_TYPE_MISMATCH → 200, creditIssuanceDecision=FAIL_OVER_THRESHOLD (feedback recorded, no instant credit).
- ⚠️ CO-1780333664867 = HOME PRIDE (PPC 2347693633 + LSA 2957729882), NOT NaRestCo — don't confuse when querying user_integrations.
**08-05 SELF-APPROVAL PROVEN (b1ca9f93)**: our OAuth user is a client-side ADMIN on every connected Ads account (customer_user_access=ADMIN, adwords scope) — so WE can flip customer_manager_link PENDING→ACTIVE ourselves. Tested live: Crew 3041785923 + Home Pride LSA 2957729882 approved, then FF/HomeLyft/Reign/TRG cleared. **Zero PENDING manager links fleet-wide; never ask a client to accept an Ads/LSA invite again.** GBP is different: self-invite works only when our OAuth grant is OWNER; MANAGER grants get a hard 404 (HomeLyft, ProRestoration=Shana Cardoza, PuroClean=Big Island Marketing) — that is the ONLY legitimate access ask, and it ONLY blocks Bing/Apple import (we ARE on those listings and post weekly — never say we can't reach them). access_ask_guard() fronts all compose paths. Nightly: browser_agent/sweep.py access_sweep() runs on Santino's Mac (Railway has no Ads creds), heartbeat + silence_watch registered. ⚠️ ALL PRO PLUMBING has NO Google grant yet Monica twice told Angie access "came through fine" — inverse bug, connect link needs re-minting + OAuth callback check.

**LSA setup SOP (Santino 2026-08-10, docs-first):** do not default to a screen-share call. Collect license + insurance COI via hub, then WE create/set up the account from the agency side (MCC + the client's connected Google access); the client's only personal steps are the background check (emailed to them) and the credit card. Call is the fallback, not the lead. First application: All Pro Plumbing.
