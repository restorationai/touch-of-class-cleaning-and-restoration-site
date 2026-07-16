# Competitor playbook analysis — Noah Igler / Sustain Media (2026-07-16)

Source: youtube.com/watch?v=iobcYyt6yYs ("$571k in 9 months" Portland plumbing
case study). Transcript reviewed in full. Mapping of his tactics vs ours, with
adopt/skip verdicts. See chat 2026-07-16 for discussion with Santino.

| His tactic | Us today | Verdict |
|---|---|---|
| GBP category tuning (primary+secondary) | ✅ gbp_face_audit checks; human-gated changes | Keep ours |
| GBP description: keywords+proof+areas+CTA, auto-set | ✅ SHIPPED — fix_description autofix + monthly cron | Done |
| GBP service-area towns on the listing (2-hr drive rule) | ❌ we don't read/set `serviceArea` field | **ADOPT (easy — API field)** |
| Consistent real job photos | ✅ crew upload links + rotation | Ours stronger |
| Services as GBP **Products** | ❌ | **ADOPT manually** (no public API — dashboard only; pilot NaRestCo/TRG) |
| Review engine (QR + 12/24/72h automation + CSR + incentives) | ✅ automation; ❌ client-side playbook (QR cards, tech scripts, bonuses) | **ADOPT as client playbook PDF** |
| Multiple GBPs via real offices in new metros | Managed reactively (TRG has 5) | **ADOPT as strategy + app feature** |
| Conversion-first site, service×location pages, cross-linking | ✅ our whole template | Done |
| Location pages: local specifics + FAQs + form up top | ✅ | Done |
| **Driving directions from metro points to the pin** + transit data | ❌ | ADOPT lightly — "Getting here" block on listing-anchored location pages only (skip SAB/hidden-address; anecdotal value, low cost) |
| NAP-exact citations incl. Chamber/local | ✅ nap-audit + citations.json | Keep |
| **Supplier/association backlinks** (Trane-installer pattern) | ❌ | **ADOPT — highest-value gap.** Restoration equivalents: IICRC firm locator, equipment suppliers (Dri-Eaz/Phoenix), Xactimate/TPA networks, chambers |
| Reddit posting as clients for AI search | ❌ | SKIP astroturf (ban risk, brand risk); authentic participation only |
| Press releases via wire for AI search + listicles-as-PR | ❌ | **PILOT** — LLMs ingest newswires; ~$100-400/release; 1-2 clients first |
| LSA: >90% answer rate monitoring | ❌ (we manage LSA, not answer-rate) | ADOPT metric — we already have Twilio call data to compute it |
| High-ticket-only Ads | ✅ SKAG water damage | Done |
| Revenue/ROAS reporting | Partial | Roadmap (needs job-value data from client CRM) |

## Multi-GBP app support (phased)
1. **Storage/UI:** allow selecting MULTIPLE locations per company
   (connection_metadata.selected_locations[] or marketing_gbp_locations table);
   picker becomes multi-select; per-location card in Marketing → Locations.
2. **Systems fan-out:** gbp_face_audit / posts / photos / description loop per
   location (face-audit table needs a location_id column, one score card per
   listing); geo-grid gets one grid per pin.
3. **Site linkage:** each listing's websiteUri → its /locations/{slug} page.
TRG (5 listings) is the pilot client.
