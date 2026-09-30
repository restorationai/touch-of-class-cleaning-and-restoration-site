---
name: 09-23-sweep-restore-done-09-29
description: "How the b68f92332 scaffold sweep damage was undone fleet-wide, plus the gaps it exposed"
metadata:
  node_type: memory
  type: project
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-30T00:18:55.332Z
---

09-23 ops-sync (b68f92332) re-scaffolded ~20 live sites over their customizations. Restored 09-29 (commits 3c5a010dd Crew, per-site "restore what the 09-23 ops-sync sweep wiped" commits, ed541044d fleet nav/DNI).

**Method:** per file, 3-way merge of the pre-sweep file upgraded within its own template lineage (starter vs light overlay, best-matching historical template render as base), then merged with everything committed since; conflicts hand-resolved. brand.ts/geo-videos handled separately (brand.ts only lost synced review data; geo-videos = union).

**Why:** the sweep's light overlay (templates/astro-starter-light) was a stale fork: no DniSwap (tracking numbers stopped displaying on every light site), no Case Studies nav, old FreeEstimateForm; plan-input without brand.theme flipped hand-light sites (firedex, restoration-groups, prorestoration) to dark.

**How to apply:**
- Client-written About copy now lives in plan-input brand.home_about_blurb (durable), not index.astro.
- Fleet nav label is "Case Studies" (was "Our Work"); empty state on /case-studies/ is a card with a call button.
- Big losses found: narestco 61 ad LPs (lp-manifest reset to []) + Google Ads tag AW-16824131335; QCI PAY HERE button; Dry County's 2-hour claim reverted to a false 60-minute; Davis "24/7" copy on a M-F contractor.
- gbp-maintenance CI deployed pages that never reached main; recovered for ~12 sites (see commit log 09-29). Older lost runs (RT Olson 09-07 170 pages, tdi 60, go-green 48) NOT recovered: Santino's call.
- Regression-watch baselines re-seeded for every deployed site after the nav relabel.
