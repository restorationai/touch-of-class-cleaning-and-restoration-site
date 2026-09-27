---
name: rank-ai-gbp-rename
description: Generate ranked GBP rename candidates (first/second/third choice) for a Rank AI client — data-backed keyword names, DBA-first sequencing, seeded into the app's Profile Rename card
---

# Rank AI — GBP Profile Rename Advisor

Profile renames are a standard Rank AI service. This skill produces THREE
ranked name candidates for a client, grounded in real search data, and seeds
them into the app (Marketing → Google Profile → Profile Rename card).

Proof case: OneStop Plumbers - Plumbing and Leak Detection (Corona CA, CSLB
#951907 registered under the FULL keyworded string) ranks #1 for "plumber
corona ca" after 12+ years. The keyworded name survives because it IS the
real-world registered identity. That is the whole game.

## Step 1 — Gather the data (never guess)

1. **Keyword Planner volumes** via DataForSEO (identical numbers to native,
   verified 2026-09-10): `/v3/keywords_data/google_ads/search_volume/live`
   with `location_name: "{State},United States"`. ALWAYS state-level, never
   national — orderings flip by region (WA: mold > water; plumbing-heavy
   metros differ). Max ~10 keywords per call (AI-mode truncation).
2. **Fleet GSC** (`marketing_gsc_queries`, paginate 1000/req, filter the
   Crew gambling-spam terms garuda/baginda/slot): what real users typed.
3. **Geogrid competitors**: what names already win the client's map packs —
   if three rivals stuffed the same term, differentiate (RT Olson vs
   OneStop: claim "Emergency" since OneStop owns daytime positioning).
4. The client's confirmed services + negative_services (never name a
   service they refuse) and their REVIEW COUNT (a keyworded name on a
   zero-review profile ranks nowhere — All Pro rule: review campaign first).

## Step 2 — Compose candidates by the rules

### HARD 90-CHARACTER CAP (LAW 2026-09-19) <!-- ninety-char-cap -->

Every candidate must be **90 characters or fewer**, counted exactly.
BrightLocal's platform hard-rejects longer business names (Kenny's 94-char
chosen name 400'd his citation order) and many directories truncate near
the same range. The name must print IDENTICALLY on every surface: GBP,
citations, site footer/schema, llms.txt. When a name runs long, shorten or
use "&" (the house default) and shorten or drop a lane if still over. gbp_rename_research.py enforces this at
generation; count any hand-written candidate before pitching it.

- **Format**: `{Real brand} - {Term A} & {Term B}` (first choice),
  `... - {A}, {B} & {C}` (third-choice aggressive ceiling). NEVER 4+ terms:
  the fourth keyword is the worst investment in local SEO — sliver of gain,
  compounding suspension/report/review risk.
- **Term selection — PRIORITY LADDER, never raw volume (v2 2026-09-25)**:
  restoration names order lanes 24/7 Emergency Plumbing -> Water Damage
  Restoration -> Fire Damage Restoration, then everything else. Mold-class
  terms TRAIL even when their state volume is higher (PuroClean NV: mold
  480/mo > water 320/mo, water still leads — identity beats volume; a
  restoration company is not a mold company). Volume only orders the
  trailing tier and breaks ties inside it. Plumbing is UNCONDITIONAL in
  restoration slates (Santino 09-25: no license caveat on the suggestion;
  the pitch conversation carries the license question). Plumbing-vertical
  clients unchanged: Emergency Plumber + Leak Detection.
- **Free modifiers**: "24/7" costs nothing, matches the 24-hour query
  family, zero risk — include when the client truly runs 24/7.
- **Front-loading is display-only**: ranking reads the whole name; humans
  see ~30-40 chars in Maps. Brand first, keywords after. Field limit ~100.
- **Category gate**: name words only pull hard when a matching CATEGORY
  backs them. Never put "plumber" in a restoration-category name when a
  sibling entity holds the Plumber category (same-owner duplicate risk);
  DO add category+name together when no sibling exists and the client
  accepts mismatch-call costs.
- **Multi-location**: Google REQUIRES the same name across locations of one
  entity (support.google.com/business/answer/3038177 — "The Home Depot at
  Springfield" is the banned example). City suffixes are only legitimate
  when each location is a separately owned entity whose real-world name
  varies (franchise pattern). Max shelf-space = separate entities, not
  suffixes (2 entities = 2 map slots + 2 LSA accounts).
- **Entity real estate beats adjectives**: budget aggression toward sibling
  entities in ADJACENT categories (restoration + plumbing, the Jack Bispo /
  Bob Olson structure), never toward a fourth keyword.

### Rename Intelligence v2 (Santino 2026-09-25) <!-- rename-intelligence-v2 -->

Two reference cases: PuroClean East LV + Arch Environmental (full slates
in docs/gbp-rename-candidates.md). Three rules on top of everything above:

1. **Brand compression BEFORE keyword budget.** Strip non-identity filler
   from the stem: legal suffixes (LLC/Inc/Corp), "Group", leading "The",
   connective "of" ("PuroClean of East Las Vegas" -> "PuroClean East Las
   Vegas"). Customers only care about the result: "Arch Environmental -
   ..." beats "Arch Environmental Group - ...". Keep the recognizable
   brand; list every trim in the reason. When a candidate still blows the
   cap, GEO NARROWING is legitimate ("East Las Vegas" -> "Las Vegas")
   when the wider metro is the target market.
2. **Exact-phrase engineering.** Descriptors are COMPLETE search phrases,
   not compacted lists — repeat the noun when the budget allows:
   "Mold Testing, Asbestos Testing, Lead & Air Quality Testing" beats
   "Mold, Asbestos, Lead and Air Quality Testing" (every repeated noun is
   another verbatim query match). Compression order when over budget:
   compress brand first, then merge shared tails ("Water & Fire Damage
   Restoration"), drop a trailing lane LAST.
3. **Coverage-first top option.** Compose the slate so every major sold
   lane (companies.services OR live GBP categories) is named across the
   candidates — the pitch coverage gate then passes by construction
   (PuroClean's fire refusal was this rule missing).

`scripts/rename_autoseed.py` implements all of v2 mechanically for
restoration clients; manual slates (Arch-style verticals) follow the same
rules by hand.

## Step 3 — Seed the app + sequence

Insert candidates into `marketing_gbp_suggestions`:
`{company_id, item: <name string>, item_type: "name", source: "confirmed",
verdict: "ADD", reason: <why + prereqs>, confidence: 0.9/0.8/0.7 (rank
order), auto_safe: false, status: "open"}`. The Profile Rename card renders
them ranked with Choose/Dismiss.

The rename is NEVER pushed to Google by automation. Sequence (in the card,
enforce verbally with the client):
1. File the DBA / trade name for the EXACT chosen string (CA = county FBN
   ~$50, e.g. Kern/Riverside; WA = one statewide trade-name registration
   covering all locations).
2. Roll the string through website header, signage, citations.
3. Change GBP once. Never iterate — name edits can trigger video
   re-verification, and the DBA + citations are the defense.

## House stance (Santino 2026-09-10)

- **Lead aggressive.** The house first-choice pattern is
  `{Brand} - 24/7 Emergency {Term A} & {Term B}` wherever the client can
  back it with a DBA. Conservative category-mirror versions rank BELOW it
  as fallbacks, not above.
- **The triple-stack ceiling** (`24/7 Emergency {A}, {B}, & {C}`) is a
  legitimate card option when a client stacks two strategies (e.g. Pro
  Restoration: plumbing capture + restoration core). Present it honestly:
  per-term weight dilutes vs a 2-term name, ~97+ chars rides the field
  limit, report risk is the 3-term class, and the DBA must match verbatim.
- **Canonical per-client record**: rank-ai/docs/gbp-rename-candidates.md —
  update it whenever candidates are seeded or changed. The DB
  (marketing_gbp_suggestions, item_type name) is what the app renders;
  the doc carries the reasoning.

## Validated search data (2026-09-09/10 pulls)

- DataForSEO search_volume == native Google Keyword Planner EXACTLY
  (verified side by side 09-10) — trust DFS numbers as Planner numbers.
- CA: emergency plumber pool 8-10k/mo; water heater repair 9,900/mo;
  leak detection = highest-margin plumbing line.
- WA: mold remediation 1,900/mo > water damage restoration 1,600/mo —
  orderings flip by state, ALWAYS pull state-level.
- Fire corridors (Altadena/Malibu/Topanga/Pasadena, 2025 fires): fire
  damage terms stay elevated locally — a fire term can earn a name slot
  there and nowhere else.
- Fleet GSC cross-checks confirmed the orderings; exclude Crew's
  gambling-spam residue (garuda|baginda|slot|judi|toto|gacor).

## Founding clients (no GBP yet)

The strongest case of all: with no profile, the candidate is what the
profile gets CREATED as. Register the string from day one (state filing +
DBA verbatim) and the keyworded name IS the legal identity — no rename
sequence, no edit-triggered re-verification, NAP consistent from birth.
Seed candidates BEFORE profile creation; the app's Profile Rename card
renders for no-GBP clients too (2026-09-10). Gate stays: never a term for
a service they do not actually offer.

## Landmines

- Keyword-stuffed names are competitor-reportable in one click; 2 terms
  survives ~always, 3 = occasional suggested-edit, 4+ = suspension class.
- LSA verticals demand the license doc (plumber LSA needs a plumbing
  license) — the name can't shortcut that gate.
- Mismatch calls become 1-star reviews, and reviews are a Maps ranking
  factor — spam names eat their own ranking.
- No em dashes in any client-facing name/copy (house law).

## Registered-name policy (Santino 2026-09-12)

A name is NEVER a candidate merely because it is already registered or is
the current name. The client files a DBA for the winning string either
way, so every candidate must earn its slot on keyword/search-term data.
"Zero extra filing" is not a merit. If the current/registered name happens
to be strong, improve it (e.g. carry the full searched phrase — "Water &
Fire DAMAGE Restoration", people search the DAMAGE n-grams) or find a
better angle (state-specific pools like basement flooding in IL). Also:
name terms must be backed by the client's SELECTED SERVICES
(companies.services) — the app flags mismatches; resolve the flag (confirm
or add the service) before choosing.

## Coverage cross-check (MANDATORY before a slate is final — Crew roofing miss, 2026-09-12)

Crew Restoration had "Roofing contractor" as a live GBP category, "Roofing
Services" in companies.services, AND a stated retail-roofing goal — yet the
seeded slate named zero roofing. Never seed from restoration search terms
alone. Before a slate is final, pull BOTH stores and cross-check:

1. `companies.services` (the app's selected services — single source)
2. `marketing_gbp_profiles.primary_category` + `additional_categories`

Every TOP-VOLUME lane present in either store (roofing, plumbing, mold,
water damage, fire) must be represented in at least one candidate or
explicitly ruled out in the reason of another. Minor lanes (sewage, storm,
biohazard, asbestos, carpet) are advisory. `client_concierge.py
rename-pitch` enforces this mechanically (_rename_coverage_gaps): a
blocking-tier gap REFUSES to open the Monica conversation until the slate
is fixed (--force overrides). Client goals count too: a service the owner
SAYS they want to grow (Kyle: retail roofing) is a blocking-tier lane even
if volume data says otherwise.


## "&", not "and" (house standard REVERSED, Santino 2026-09-19) <!-- ampersand-default -->

Default every candidate to "&", not the word "and". The 90-character hard
cap changed the math: "&" saves 2 characters per joint, and those
characters buy a whole keyword lane on long names (FF Solutions' confirmed
name only fit at 89 BECAUSE of the "&"). Precedent: Dry Bros' DBA with "&"
filed and verified fine in Illinois; GBP and BrightLocal both accept it.
The old concern (state DBA portals normalizing special characters) is
handled at filing time: if a client's state portal rejects "&", file with
"and" and keep "&" as the display canon — the concierge matcher treats
&/and as equivalent so verification tolerates either. Strings already
communicated to a client stay as communicated, whichever form they carry.


## Volumes in every reason (Santino 2026-09-14) <!-- volumes-in-reasons -->

Every candidate's `reason` MUST carry the client's OWN state's monthly
search volumes for the terms in that name (pull live via DataForSEO when
seeding; states vary with climate and housing stock: storm terms run
hotter in storm belts, basement terms where basements exist). Monica's
rename conversations quote these numbers verbatim when clients ask why
or counter-propose (the DISS flood case: PA mold 2,900/mo, water
1,000/mo, flood family ~150/mo, basement flooding 260/mo) — so a reason
without numbers leaves her unarmed. Numbers in reasons only; she never
invents them.
## Conversation laws (v2 2026-09-26, Greg/PuroClean incident) <!-- convo-v2 -->

- **Hedge is not consent.** "Probably/maybe/leaning/I think", or ANY open
  question in the same message, never locks a name. Monica answers first
  (volumes included, never invented), then asks ONE clean lock-in question
  quoting the name verbatim. A clean short yes afterwards locks it.
- **Questions come before pipeline advancement**, always.
- **Objection playbooks** (delivered once, then the client's choice
  stands): PLUMBING-LICENSE HESITATION -> no license is needed for name
  words; the risk is a competitor report and it is VERY UNLIKELY; Google
  path worst case = name reverted, state-board path worst case = citation,
  drop the word, small fine; house stance = ask forgiveness; and the
  plumber-intent story: emergency-plumber searchers are often restoration
  jobs, owning the phrase gets you the call first and flips referral
  leverage toward you. (Full client-facing text: PLUMBING_NAME_PLAYBOOK in
  client_concierge.py.)
- **No em dashes ever** in anything client-facing (mechanically stripped
  at the send chokepoint; write without them anyway).
