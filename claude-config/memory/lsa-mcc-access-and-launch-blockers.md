---
name: lsa-mcc-access-and-launch-blockers
description: 2026-08-07 audit — Flood Fixers LSA verified but not delivering (portal-layer suspect); 5 clients never got an MCC invite; auto-invite on OAuth NOT built; Go Green + Quality Contracting are self-blocked launches
metadata: 
  node_type: memory
  type: project
  originSessionId: 6a7501ec-9e6b-4102-8623-fdfc8fa505ff
  modified: 2026-08-08T02:18:27.519Z
---

**FLOOD FIXERS LSA (customer 5252629170), audited live 2026-08-07.**
Not an access problem and not a verification problem:

- MCC manager link ACTIVE, invite accepted (we can already log in)
- BACKGROUND_CHECK / INSURANCE / LICENSE artifacts ALL **PASSED**
- Campaign 23782723359 LOCAL_SERVICES, status ENABLED, serving_status SERVING
- **Only ONE service enabled: `water_damage_cleanup_repair`**
- Last 30 days: **5 impressions, 0 clicks, $0.00 spend, ZERO leads ever**
  (2 impr Jul 28, 1 Jul 29, 1 Aug 6)

Prime suspect is the layer the API cannot see: LOCAL_SERVICE_ID campaign
criteria are only an INCLUDE-LIST. Real eligibility comes from job-type
enrollment in the LSA PORTAL (business-profile level, no API) — the same
distinction found on 2026-08-01. A profile with no job types enrolled reads
ENABLED and still shows ~4 times a month. Needs a human or the browser agent
in the portal. API renders the budget as $1,154.29/day, which is not
trustworthy for LSA; eyeball it in the portal at the same time.

**MCC LINK AUDIT (manager 2018844125), 13 linked accounts.**
NO INVITE EVER SENT (5): all-pro-plumbing, coastal-restoration-services,
go-green-restoration-of-nc, mcc-restoration, quality-contracting-inc.
ACTIVE (10): crew, flood-fixers, home-pride (TWO accounts linked, check),
homelyft, life-savers, narestco, prorestoration, puroclean, reign,
restorationxpress. Three show a CANCELED predecessor, which is normal (each
resend cancels the prior pending link). Run `scripts/lsa_link_audit.py`.

**AUTO-GRANTING OURSELVES MANAGER ACCESS ON OAUTH IS NOT BUILT** (Santino
wants it for both Ads/LSA and GBP). Today the invite is created ONLY by a
human clicking the app's `lsa-request-access` edge function. Nothing fires on
connect, which is why 5 clients have none. Build-queue item.

**Google Ads API auth gotcha:** GOOGLE_ADS_REFRESH_TOKEN is NOT in the local
.env and only narestco has `clients/{slug}/.ads-token.json`. Use
`lsa_detect.build_mcc_client()`, which falls back to ANY client token file
(every such grant is an MCC-admin user). `ads_manager.py report` fails on
flood-fixers because the customer id lives in Supabase
integration_settings.lsa.customer_id, not in the client JSON.

**LAUNCH BLOCKERS — the two that are OURS, not the client's (2026-08-07):**
- go-green-restoration-of-nc: gogreenrestorationofnc.com is ALREADY on our
  Cloudflare nameservers but the zone has NO A RECORD, so the domain resolves
  to nothing. Site is preview_ready. Nothing needed from the client.
- quality-contracting-inc: domain_access_status=creds_provided (we hold Fran's
  credentials), NS still at HostMonster. Nothing needed from Fran.

**`marketing_sites.apex_live` IS UNRELIABLE — do not trust it.** PuroClean
reads False while purocleaneastlasvegas.com is genuinely live; life-savers
reads ns_live while its NS are at NS1 and the site is not even built. Verify
launches with an HTTP probe, never the flag.

Related: [[site-lead-capture-broken]], [[lsa-management-capabilities]],
[[flood-fixers-onboarding]], [[browser-agent-suite]]
