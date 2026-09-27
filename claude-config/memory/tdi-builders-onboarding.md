---
name: tdi-builders-onboarding
description: "TDI Builders, Inc. signed 2026-08-23 (Rob Carpenter): CONSTRUCTION company (corporate/commercial vibe; restoration = their Insurance Services silo), Sacramento+Manteca CA; migrate buildwithtdi.com (16pg Scorpion) -> tdiusa.com; client supplied a 47-page Website Architecture SOP (~550pg, 30 cities x 7 services) + brand guidelines; open decisions: platform (SOP says WordPress, we build Astro), HubSpot 48033708 + CallRail wiring, CSLB license number missing"
metadata: 
  node_type: memory
  type: project
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-08-24T01:00:20.509Z
---

New client signed 2026-08-23. **TDI Builders, Inc.** — operator-led restoration/construction, positioning against franchise brands. Contact: Rob Carpenter (owner, doc author). Offices: 701 Del Paso Rd Sacramento CA 95834 + 1086 Bessemer Ave Manteca CA 95337. Phone (877) 688-0866. Greater Sacramento + San Joaquin Valley.

**Domains**: current site buildwithtdi.com (16 pages, Scorpion platform). Build target is **tdiusa.com** (today just a 302 to buildwithtdi.com). Migration plan: 301 map + GSC Change of Address, keep buildwithtdi.com registered forever.

**Brand** (from "TDI Branding Guidelines & Logo.ai", a PDF-compatible .ai): TDI Blue #0080C4, grey #A4B0BA, white, dark text #1A1A1A, bg grey #F4F6F8. Futura PT (licensed — needs web license or Inter fallback per their own spec). Logo = white TDI on blue square, ALWAYS with the (R) mark, min 32px, no effects. Angular chevron patterns at 10-40% opacity, blue/grey/white only. Voice: operator, short sentences, no "world-class/industry-leading" boilerplate.

**Client-supplied SOP** (47-page "Website Architecture SOP" v1.0 May 2026, internal-confidential): ~550 pages, 10 silos, 27 templates, 30 cities x 7 services geo matrix (Tier 1 w/ neighborhoods: Sacramento, Roseville, Elk Grove, Folsom, Modesto), insurance-claims advocacy silo (their moat), 14 industry verticals, 6 phases over 12-18 months (Phase 1 = 22 revenue-priority pages), 60% uniqueness rule on geo-service pages, no stock photography, speed-to-lead SLAs, ops-must-back-marketing rule. HubSpot Account ID 48033708; CallRail planned (separate SOP). Docs archived at rank-ai/clients/tdi-builders/docs/.

**Assessment 2026-08-23**: SOP is ~90% aligned with our pipeline (silo architecture, city x service money pages, uniqueness rule, FAQ/LocalBusiness schema, truthful ratings, real-photo moat, claims-backed copy). Deltas needing Rob's buy-in: (1) platform — SOP recommends WordPress/WP Engine, we build static Astro on Cloudflare Pages which beats every performance target in their Section 7; (2) lead routing must land in THEIR HubSpot + CallRail, not our GHL default; (3) their 22-page phased launch vs our full unique render (we can phase bigger because differentiation is automated); (4) Futura PT web license or fallback. **CSLB license number is not on their site and not in the SOP — must collect before build.**

**BUILD (final) 2026-08-24**: REBUILT on the CONSTRUCTION template after Santino's call (their menu: Commercial/Specialty/Residential Construction + an 'Insurance Services' restoration silo). 12 services x 14 cities = 211 pages, ~$8: commercial-construction, general-contracting, new-construction, fire-smoke-rebuilding (NEW catalog entry added to templates/construction/services.json), water/storm/mold, home/kitchen/bathroom remodeling, garage-construction, room-addition. Maiden voyage of the construction template. Homepage: 'Trusted General Contractor in Sacramento', trust strip leads 'Commercial, Industrial & Residential'. All 12 service images + hero/team fleet imagery in place. Sacramento=primary (homepage IS the Sacramento page; /service-areas/sacramento-ca/* 301s). STAGING LIVE https://staging.rankai-tdi-builders.pages.dev/. GOTCHA learned: build_site scaffold AUTO-PUSHES the bare skeleton to staging+production branches (briefly wiped the live preview mid-rebuild). Polish list: About body leans restoration-voiced in spots. Production push + cutover await staging approval + CSLB + DNS.

Related: [[rank-ai-sales-playbook]].
