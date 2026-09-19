# GBP Keyword-Name Candidates — canonical record

Last updated: 2026-09-10. Live state mirrors `marketing_gbp_suggestions`
(item_type `name`, plus gating `category` rows); the app renders open rows
ranked by confidence on each client's Locations tab (Profile Rename card).
This file is the durable record of the candidates AND the reasoning, so a
name discussion never has to be reconstructed from chat history again.

## Method (settled 2026-09-09/10)

- **HARD 90-CHARACTER CAP (LAW 2026-09-19)**: every candidate name must be
  90 characters or fewer, counted exactly. BrightLocal's platform rejects
  longer business names outright and many directories truncate near the
  same range — and the name must print IDENTICALLY on every surface (GBP,
  citations, site, llms.txt). Kenny's 94-char chosen name 400'd his whole
  citation order; FF Solutions confirmed a 91-char name and needed a
  pre-filing correction SMS. "&" is the DEFAULT joiner (standard REVERSED
  2026-09-19, was "and"): it saves characters that buy keyword lanes under
  the cap; Dry Bros' "&" DBA filed and verified fine. If a state portal
  rejects "&" at filing, file with "and" and keep "&" as display canon —
  the concierge matcher treats the two as equivalent. The researcher
  (gbp_rename_research.py) enforces cap + joiner at generation; anything
  hand-written gets counted before it is pitched.

- **Proof case**: OneStop Plumbers, Corona — CSLB #951907 registered under
  the keyworded name; they outrank on brand+keyword blend. The playbook
  works when the paper trail matches the name.
- **Sequence, always**: DBA filing first, then citations + signage + site
  mentions, then ONE GBP name change. Never auto-pushed; the card's Choose
  button records the decision, a human makes the change.
- **Calibration**: 2 service terms safe, 3 = max. Entities (service nouns)
  beat adjectives (24/7, emergency) for ranking, but modifiers capture
  panic-moment click intent. The CATEGORY GATE matters more than name
  words: never carry a name term whose category is missing from the
  profile.
- **Grey-zone stance** (Santino 2026-09-10): we lean aggressive — the full
  "24/7 Emergency {service} & {service}" pattern is the house style where
  the client can back it with a DBA, e.g. both restoration flagships below.

## RT Olson Plumbing, Heating and Air Conditioning (CO-1786206263495)

Market data: CA emergency plumber pool 8-10k/mo; water heater repair
9,900/mo CA; leak detection = highest-margin line, feeds Dry County.
OneStop is the direct keyworded-name competitor in Corona.

1. **0.92 — "… - 24/7 Emergency Plumber & Leak Detection"** — the house
   grey pattern on the OneStop flank (Santino 09-10). Brand already
   carries Plumbing, so plumber signal doubles; Riverside County DBA first.
2. **0.90 — "… - Emergency Plumber & Leak Detection"** — same flank
   without the 24/7 modifier.
3. **0.80 — "… - 24 Hour Plumber & Water Heater Repair"** — sidesteps
   OneStop entirely; water heater volume workhorse.
4. **0.70 — "… - Emergency Plumber, Leak Detection & Water Heater Repair"**
   — three terms, max grey; only with the full DBA/citation runway.

Dual-entity: RT Olson (plumbing) + Dry County Restoration (damage) split
the SERP; never merge the positioning.

## Pro Restoration Services (CO-1779551010975) — Jack Bispo, Bakersfield

Dual-entity with All Pro (plumbing). Pro Restoration is the RESTORATION
flag that also hunts emergency-plumbing panic searches.

1. **0.85 — "… - 24/7 Emergency Water Damage & Mold Remediation"** — house
   grey pattern, both entities category-backed.
2. **0.80 — "… - 24/7 Emergency Plumbing & Water Damage Restoration"** —
   the plumbing-capture play (CA emergency plumber pool 8-10k/mo).
   **GATE: add Plumber as secondary category first** (suggestion seeded,
   0.81 open). Aggressive end: plumbing is outside current categories
   until that lands. LSA plumber vertical would also need a license doc.
3. **0.75 — "… - Water Damage Restoration & Mold Remediation"** — clean
   fallback, category-mirrored, no modifiers.
4. **0.72 — "… - 24/7 Emergency Plumbing, Water Damage Restoration, &
   Mold Remediation"** — the CEILING option (Santino 09-10): both
   strategies in one name. Costs: per-term weight dilutes vs 2-term
   names, ~97 chars rides the GBP field limit, 3-term report class, DBA
   must match verbatim. The all-in play if Jack commits fully.

Category pushes open for the same strategy: Plumber (0.81), plus
Construction company / Roofing contractor / Remodeler rows the optimizer
seeded.

## All Pro Plumbing Heating and Air (CO-1783380243102) — Jack Bispo

1. **0.90 — "All Pro Plumbing - 24/7 Emergency Plumber & Leak Detection"**
   — the house grey pattern for Bakersfield (Santino 09-10); Kern County
   DBA first.
2. **0.85 — "All Pro Plumbing - Bakersfield Plumbers & Leak Detection"** —
   city term + two services; the geo alternative.
3. **0.75 — "All Pro Plumbing - Water Heater Repair & Drain Cleaning"** —
   volume workhorse fallback, no modifiers, category-clean.

## NaRestCo (CO-1771290587387)

1. **0.85 — "NaRestCo - Water Damage Restoration & Mold Remediation"** —
   WA data: mold remediation 1,900/mo > water damage restoration 1,600/mo
   statewide, so mold earns the second slot. Tacoma second entity parked
   until the office is real.

## California Restoration West (CO-1787707972245) — Chris

Market: service areas (Altadena, Malibu, Topanga, Pasadena, Calabasas) sit
in the 2025 fire corridors; coastal-canyon mold demand (Malibu/Topanga) is
year-round. Primary category: Water damage restoration service.

1. **0.92 — "… - 24/7 Emergency Water Damage & Mold Remediation"** — first
   choice per Santino 09-10; the house grey pattern. Mold covers the
   coastal demand fire terms miss.
2. **0.90 — "… - Water & Fire Damage Restoration"** — the fire-corridor
   positioning; two entities, category-clean.
3. **0.80 — "… - Water Damage Restoration"** — conservative single-term.
4. **0.70 — "… - Fire & Smoke Damage Cleanup"** — full fire pivot; needs a
   Fire damage restoration secondary category first, only if fire rebuild
   becomes the growth priority.

## Search data these ranks stand on (validated 09-09/10)

- DataForSEO search_volume verified IDENTICAL to native Google Keyword
  Planner, so DFS pulls are Planner truth. Always state-level.
- CA: emergency plumber 8-10k/mo pool; water heater repair 9,900/mo;
  leak detection highest-margin. WA: mold 1,900 > water 1,600 (orderings
  flip by state). 2025 fire corridors keep fire terms elevated in CRW's
  service areas. Fleet GSC cross-checks agreed; Crew's gambling-spam
  impressions excluded from all analyses.

## Dry Bros Water & Fire Restoration (CO-1788898034500) — Chicago, NEW company, no GBP yet

The FOUNDING-NAME case: no profile exists, so the "rename" is what the
profile gets CREATED as. Register the chosen string from day one and the
grey pattern is fully defensible, NAP consistent from birth.

1. **0.92 — "Dry Bros - 24/7 Emergency Plumbing, Water Damage Restoration,
   & Mold Remediation"** — ceiling shape as founding identity (Santino
   09-10). Gates: confirm plumbing + mold are real service lines; Plumber
   secondary category if plumbing stays; IL registration/DBA verbatim.
2. **0.85 — "Dry Bros - 24/7 Emergency Water Damage & Mold Remediation"**
   — house pattern without the plumbing bet. Chicago metro pulls queued.
3. **0.75 — "Dry Bros Water & Fire Restoration"** — the already-registered
   name, itself keyworded (water + fire); zero filing, leaves emergency +
   mold on the table.

## Standing rules

- Never push a name to GBP from automation. Card choice → DBA → citations
  → manual GBP edit.
- A name term without its backing category is a suspension flag: fix the
  category row first (the Plumber gate on Pro Restoration is the template).
- Multi-location clients keep ONE name strategy across locations.
- **No-GBP / founding clients are the STRONGEST case**: the keyworded name
  becomes the registered identity from day one (grey becomes white). The
  Profile Rename card renders pre-GBP as of 09-10, so candidates must be
  seeded for new clients BEFORE profile creation, not after.

## Fleet-wide seeding pass — 2026-09-11

Santino: "make sure all clients are seeing the profile rename." Every active
Rank AI client now has item_type=name rows (the app card renders only those —
Dry County had 150+ category/service rows and zero name rows, which is why
its card was invisible). 24 clients seeded with 3 ranked candidates each from
fresh state-level DFS volumes (DFS=Planner verified): UT, MI, FL, TX, NJ, CA,
AL, HI, NV, WA, SD, PA, MS, MA pulled 09-11/09-12.

State orderings (searches/mo): CA mold 9,900 > water 8,100, fire 4,400 (fire
corridors). TX mold 5,400 > water 3,600. FL mold 5,400 > water 2,400.
PA mold 2,900 > water 1,000. MI mold 2,400 > water 880. NJ mold 2,400 >
water 1,300. WA mold 1,900 > water 1,600. MA mold 1,600 > water 590
(basement waterproofing 1,000). UT mold 590 > water 480. NV mold 480 >
water 320. AL mold 880 > water 390. MS mold 320 = removal 320 > water 210.
SD water 140 > mold 110. HI carpet cleaning 1,000 >> water 110.
Mold beats water in ELEVEN of fourteen states — the house two-term default
(Water Damage + Mold Remediation) is volume-backed almost everywhere.

Notable calls: FireDEX leads WATER (water-first shop despite the fire name);
Arch = testing-only terms (never remediation they don't sell); AAA HI leads
Carpet Cleaning (searchers type "cleaning", brand says "care"); Dry County is
in OneStop's Corona (the proof case) — claims the water/mold lane; Crew's
bigger win is naming the Sioux City IA profile AT CREATION; QCI rows mirror
the roadmap already sent to Fran (plumbing triple gated on the Master
Plumber license); DryCor DBA rides the rebrand filing. Documented holds
(KEEP rows so the card is never blank): PuroClean (franchisor controls
naming), TDI (mid rebrand + suppressed services). Untouched by design:
Paul Davis Charleston + Go Green (hands-off), canary, day-old signups.

### Dry Bros (dry-bros-water-fire-restoration) — IL volumes finalized 09-12

Founding-name decision (DBA + GBP created with the chosen string; profile
already exists UNVERIFIED under "Dry Bros Water & Fire Restoration" — rename
it BEFORE verification, verify once). IL: mold remediation 2,900/mo #1,
emergency plumber 2,400 (+water heater repair 3,600), water damage 1,600.
- **#1 (plumbing confirmed + licensed):** Dry Bros - 24/7 Emergency
  Plumbing, Water Damage Restoration, & Mold Remediation
- **#1 (default, plumbing unconfirmed):** Dry Bros - 24/7 Emergency Water
  Damage & Mold Remediation
Citations (BrightLocal CB tester) run only AFTER the DBA string is final —
they carry the exact name + Amin's real line (TF still rejected).

## Plumbing option, house-wide — 2026-09-12

Santino's call: the plumbing capture play is now a FIRST-CLASS OPTION for
every water-damage-category client (24 seeded at 0.91: "{Brand} - 24/7
Emergency Plumbing, Water Damage & Mold Remediation"). Rationale: biggest
emergency-intent pool most restoration names leave on the table, and
plumbing calls monetize even unserved (referral relationships, lead
resale). HARD GATE in every card reason: a Master/state plumbing license
(own or licensed partner) before choosing — unlicensed plumbing
advertising is fineable in most states and is the report a competitor
always wins. Skipped: hands-off (Paul Davis, Go Green), PuroClean
(franchise naming), TDI (hold), Arch (testing vertical), RT Olson (is a
plumber). QCI + Dry Bros already carried plumbing options.
The app's rename card now also flags any candidate naming a service
outside companies.services (the Dry Bros mold catch) — the flag says
confirm-or-add, never auto-hides.

## Coverage-check addition 2026-09-12 (the Crew roofing miss)

crew-restoration-construction: seeded "Crew Restoration & Construction -
Roofing, Water & Fire Damage Restoration" at 0.89. Roofing contractor was
already a live GBP category + Roofing Services selected + Kyle's stated
retail-roofing goal, and no candidate named it. Root cause: the original
seeding keyed on restoration search terms without cross-checking
companies.services or GBP categories. Fixed mechanically: rename-pitch now
runs _rename_coverage_gaps (blocking tier roofing/plumbing/mold/water/fire)
and refuses an incomplete slate; the skill doc carries the same law.

## Flood Solutions (CO-1789143868981) — seeded 2026-09-15 (live during Craig meeting)

MI state pools (DataForSEO 09-15): mold remediation 2,400/mo; emergency
plumber/plumbing 1,600/mo each; water damage restoration 880/mo; basement
flooding 390/mo; fire 210; sewage 70; flood cleanup 40 (their brand word
barely searches — service terms must do the work).

1. 0.91 Flood Solutions - 24/7 Emergency Plumbing & Water Damage Restoration
   (aggressive-first; plumbing license gate)
2. 0.90 Flood Solutions - 24/7 Emergency Water Damage Restoration & Mold
   Remediation (mold NOT in services — coverage question first)
3. 0.80 Flood Solutions - Water Damage Restoration & Sewage Cleanup
   (conservative, fully covered)

### CORRECTION 2026-09-15 (live, same meeting): Flood Solutions is actually
**Flood and Fire Solutions** — NO mold ever (they don't do it), fire is
wanted. Old 3 dismissed; re-seeded fire-focused (company row name+services
corrected too). New: 0.91 plumbing-aggressive / 0.90 "24/7 Emergency Water &
Fire Damage Restoration" / 0.80 conservative water+sewage.

### AUTOSEED live 2026-09-15: scripts/rename_autoseed.py rides call-intel
(every 30 min). GBP connect -> state-volume research -> house candidate set
(coverage-gated, plumbing-aggressive-first) + first Location Scout pass.
Autoseeded rows carry source='autoseed'; this doc records manual/corrected
research only.
