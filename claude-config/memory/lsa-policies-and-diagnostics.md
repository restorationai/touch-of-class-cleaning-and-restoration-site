---
name: lsa-policies-and-diagnostics
description: "Santino's LSA policies (no tracking numbers on LSA, message leads OFF, business-name search OFF) + the 0-second-call diagnostic from the DryCor 09-27 case + API limits"
metadata:
  node_type: memory
  type: project
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-27T20:15:27.254Z
---

**Policies (Santino 2026-09-27):**
- NO tracking numbers on LSA profiles: LSA calls are already tracked/recorded and we have API access. LSA must ring the client's real line.
- Message leads (texting) OFF on every client LSA; "direct search for company name" (navigational/brand search) OFF. He toggles both by hand today and wants app toggles.
- DryCor: no mold removal on LSA (they want water damage claims); water_damage_other restored 09-27.
- Do NOT unlink A&J Plumbing (6086199000, Craig Geatches, SearchKings-managed) from FFS yet, even though it is not FFS's own account.

**Diagnostic that found DryCor (09-27):** local_services_lead_conversation.phone_call_details.call_duration_millis. A streak of 0s calls = LSA forwarding to a dead/wrong number (DryCor: 7 straight from 09-10, after RGP offboarded). Cross-check Twilio: if no calls hit our numbers at those times, the LSA profile phone is wrong. change_event shows who paused/edited (RGP paused 09-11). Old agencies can keep MCC links: terminate via CustomerManagerLinkService status INACTIVE (worked from our MCC).

**API limits (v25):** leads, call durations + call_recording_url, provide_lead_feedback (GEO_MISMATCH/JOB_TYPE_MISMATCH/SPAM/DUPLICATE/SOLICITATION -> credits), append_lead_conversation (message leads only), service + location criteria all API. LSA profile phone, message-lead toggle, brand-search toggle are NOT readable/settable on legacy LOCAL_SERVICES campaigns (local_services_pmax_campaign_settings fields rejected) -> portal/browser only. Budget micros from API are unreliable for manual-CPA accounts.

**A&J vs fleet (09-27):** A&J = Plumber category, ~$670/day, 395 calls/30d, 90% answered, 16 services, 60 negative geos, 8-6 ad schedule, verified since 2020. Category + spend explain most of the gap; answer rate + tenure (reviews) next.

**Daily AI lead review LIVE 09-27:** scripts/lsa_lead_review.py + .github/workflows/lsa-lead-review.yml (06:17 PT, per-client matrix). Per-client note = companies.integration_settings.lead_profile (auto-seeded, editable; vertical-agnostic). SAFE mode: GOOD + SPAM/SOLICITATION/DUPLICATE sent automatically; JOB_TYPE/GEO/NOT_READY held until `approve --slug X --confirm-profile`. Ownership guard skips A&J (FFS). Missed calls (0s) never rated; 0s streak >=2 -> [FLAG] ops note.
**LSA -> Performance Max migration (Google, phased: Aug 2026 plumbing/HVAC/roofing, late 2026 service-area businesses, 2027 rest):** phone editable in Google Ads (no Google call), manual bids + industry target CPA deprecated, old LSA reports NOT carried over (back up leads first).
**DryCor 09-27 truth:** LSA calls reached DryCor through 09-09 (Jamie/Robert/Kari answered); broke 09-10. Mold re-enabled (Rob: "I'll take all calls"). The ~60 short calls to DryCor's GBP tracking number = "your business is not showing correctly on Google" robocalls.

Related: [[lsa-management-capabilities]], [[lsa-mcc-access-and-launch-blockers]], [[plumbing-forward-names]]
