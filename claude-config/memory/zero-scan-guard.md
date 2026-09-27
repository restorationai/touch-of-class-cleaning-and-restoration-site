---
name: zero-scan-guard
description: DryCor incident 09-02 — 5 actives had zero map scans; guards now live (digest tripwire + heal fallbacks); Davis Construction has NO findable GBP
metadata: 
  node_type: memory
  type: project
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-02T07:25:11.778Z
---

2026-09-02 DryCor incident: 5 Active Rank AI clients had ZERO geogrid scans ever (DryCor, Xtreme Clean, Paul Davis Charleston since Jul 7, MCC since Jul 6, Davis Construction since May 14). Root causes: bootstrap gated cities-seeding on kw-file existence (half-seeded = stranded forever), geocode fail on DB city typo (Thonotosasa vs Thonotosassa), setup_ledger heal hard-required service_areas AND identity, failures only surfaced as quiet amber cards.

Guards now live (commit "zero-scan guards"):
- client_ops_sync daily digest: "*** NO MAP DATA ***" line for any Active Rank AI client with empty/missing geogrid config + zero scans (skips names starting "test"). Fires until scans exist.
- bootstrap_client: keywords and cities seeded independently; geocode falls back to street address.
- setup_ledger heal: home-city 3-radius fallback ring when service_areas unplanned (identity only requirement).

Healed 09-02 with verified place_ids + canon top-5 restoration kw + home ring: drycor-restore (ChIJ--4aNxtJuIURz7eqWifJBM4, Thonotosassa FL), paul-davis-charleston (ChIJkYy3631v_ogRjyTdLSlEueU), mcc-restoration (GBP is named "Masters Carpet Cleaning and Restoration Services", ChIJpyENmC6EToYRjYMSNwK1MGo — name mismatch likely hurts restoration-kw rankings, potential client conversation).

Still blocked, need human/Monica input: [[new-client-sites-jul-2026]]
- davis-construction (Greg): NO findable GBP listing anywhere in Huntsville metro (searched name, domain, broad) — biggest issue for him, geo-grid pointless until a listing exists.
- xtreme-clean: no city/address/place_id anywhere in our systems.

place_id discovery pattern: DataForSEO serp/google/maps/live/advanced, keyword=name(+city), verify by street address before trusting.
