---
name: call-tracking-dni
description: "Sitewide call-tracking LIVE 2026-08-24: DNI swap (humans see/dial tracking number, source+JSON-LD keep real NAP) in starter template + scripts/site_call_tracking.py; fleet = 8 activated clients incl narestco pilot (verified live); tracking number = agent_phone_1 (AI dispatcher, calls recorded in app); GBP already standard via gbp.py set-phone (tracking primary, real in additionalPhones); OPEN: citations must build on REAL line, provisioning for non-activated clients, per-source DNI"
metadata: 
  node_type: memory
  type: project
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-08-24T11:06:01.565Z
---

**Santino 2026-08-24: every client website displays a tracking number, without breaking NAP.** The answer is Dynamic Number Insertion, shipped same day:

- **Template**: astro-starter brand.ts has `trackingPhone`/`trackingPhoneRaw` (empty = off) + a BaseLayout inline script that, when set, swaps every visible phone text + tel: href AFTER DOM parse. It skips SCRIPT/STYLE nodes, so JSON-LD schema and the HTML source keep the canonical NAP number. Crawlers/citation checkers see real NAP; humans dial the tracked line.
- **Rollout tool**: `scripts/site_call_tracking.py --slug X | --all-activated [--dry-run] [--number +1...]` — patches a site's brand.ts + BaseLayout idempotently, npm-build gate with git-revert on failure. Deploy stays separate (sync-deploy main).
- **Tracking number source**: company_phone_setup.agent_phone_1 (the AI-dispatcher line) — already answered by Retell + logged/recorded into marketing_tracked_calls, so site calls appear in the app call log with zero new Twilio spend.
- **Fleet 2026-08-24**: narestco PILOT verified on the live domain (rendered shows only (844) 642-0298, all tel: swapped, schema keeps (206) 883-0333) + homepride, go-green, prorestoration, flood-fixers (no-op: real==tracking), davis-construction, crew, restorationxpress.
- **GBP side was ALREADY standard**: gbp.py `set-phone` writes tracking as primaryPhone and moves the real number to additionalPhones (Google's own sanctioned pattern; additional number is used for NAP matching).

**Why:** call attribution from the website without citation inconsistency; Santino explicitly wants this default for every build.

**How to apply:** new builds inherit the template (fields empty until provisioning). For a new activated client: run site_call_tracking.py + sync-deploy. OPEN ITEMS: (1) citations builder must use the REAL line, not GBP-primary, now that GBP primaries are tracking numbers; (2) auto-provision numbers for clients WITHOUT an agent line (ads-call-tracking skill pattern); (3) future: per-source DNI (different number per traffic source) needs a JS matrix, current swap is single-number.

**2026-09-11 update:** organic-social tracking numbers (facebook/instagram) RELEASED fleet-wide (58 numbers, 29 clients, ~$67/mo saved) — never placed anywhere, only spam probe calls. EXCEPTION: RT Olson keeps facebook+instagram (BDA works Meta there) AND got the first on-demand `meta_ads` source: (951) 261-8890, given to BDA/Zheng for Meta campaigns. `meta_ads` is NOT in ALL_SOURCES (provision explicitly per client running paid Meta). DNI detectSource now returns meta_ads for utm facebook/meta + medium paid/cpc/ppc (template + rt-olson). dni_sync PUBLIC_SOURCES includes meta_ads.
