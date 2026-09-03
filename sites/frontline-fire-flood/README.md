# Rank AI — Restoration Astro Starter

**Version:** see `VERSION`
**Owner:** restorationai
**Purpose:** Canonical Astro starter for Rank AI restoration-industry client sites.

## What this is

The deterministic Astro template that Skill 3 (`rank-ai-build-site`) clones per client, theming via tokens and populating via content collections. Every Rank AI client site is a copy of this directory plus per-client content and brand config.

## What this is not

- Not a stand-alone Astro project — `{{TOKEN}}` placeholders are substituted at scaffold time and will break direct `npm install && npm run build` until Skill 3 runs.
- Not per-client customizable in the starter — per-client variation lives in three places only:
  1. Brand tokens (colors, logo, fonts, NAP) — replaced at scaffold
  2. Content collection markdown — produced by `render`
  3. Domain binding — set by `cut-over`

If you find yourself wanting to fork the starter per client, instead update this starter and version-bump. All existing client sites stay pinned to their build's starter version.

## Token reference

These `{{TOKEN}}` strings are substituted by `build_site.py scaffold` from `plan-input.json` and the client record. Adding a new token requires updating both this starter and the scaffold step.

| Token | Source | Example |
| --- | --- | --- |
| `frontline-fire-flood` | client record `slug` | `narestco` |
| `Frontline Fire & Flood` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Frontline Fire & Flood` | plan-input `brand.short_name` | `NARESTCO` |
| `Frontline Fire & Flood` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `frontlinefireflood.com` | client record `domain` | `narestco.com` |
| `https://frontlinefireflood.com` | derived | `https://narestco.com` |
| `+12532000503` / `+112532000503` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `service@frontlinefireflood.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2014` | brand.founded_year | `2004` |
| `Lakewood` / `WA` | derived from primary area | `Federal Way` / `WA` |
| `9520 Front St` / `98499` | brand.street_address / brand.postal_code | |
| `47.1717649` / `-122.518458` | brand.lat / brand.lng | from GBP |
| `ChIJK-c9495UkFQRpJu9uz3VE20` / `` | brand.place_id / brand.google_cid | from GBP |
| `["CCFRONTFF761CB"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC CERTIFIED FIRM", "IICRC AMRT (MOLD)", "IICRC WRT (WATER)", "IICRC FSRT (FIRE & SMOKE)", "IICRC ASD (STRUCTURAL DRYING)", "EPA LEAD-SAFE CERTIFIED", "OSHA TRAINED"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Lakewood, WA.` | brand.tagline | short marketing line |
| `#dc2626` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `FF` | derived; logo lives on the per-client R2 bucket | |
| `https://images.frontlinefireflood.com` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://frontlinefireflood.com/services/water-damage-restoration/)
- [Fire Damage Restoration](https://frontlinefireflood.com/services/fire-damage-restoration/)
- [Mold Remediation](https://frontlinefireflood.com/services/mold-remediation/)
- [Storm Damage Restoration](https://frontlinefireflood.com/services/storm-damage-restoration/)
- [Sewage Cleanup and Sanitization](https://frontlinefireflood.com/services/sewage-cleanup/)
- [Asbestos Abatement](https://frontlinefireflood.com/services/asbestos-abatement/)
- [Emergency Board-Up and Tarping](https://frontlinefireflood.com/services/emergency-board-up-tarping/)
- [Contents Restoration & Storage](https://frontlinefireflood.com/services/contents-restoration-storage/)
- [Water Cleanup](https://frontlinefireflood.com/services/water-cleanup/)` / `- [Lakewood, WA](https://frontlinefireflood.com/service-areas/lakewood-wa/)
- [Tacoma, WA](https://frontlinefireflood.com/service-areas/tacoma-wa/)
- [Puyallup, WA](https://frontlinefireflood.com/service-areas/puyallup-wa/)
- [University Place, WA](https://frontlinefireflood.com/service-areas/university-place-wa/)
- [Lacey, WA](https://frontlinefireflood.com/service-areas/lacey-wa/)
- [Olympia, WA](https://frontlinefireflood.com/service-areas/olympia-wa/)
- [Spanaway, WA](https://frontlinefireflood.com/service-areas/spanaway-wa/)
- [Parkland, WA](https://frontlinefireflood.com/service-areas/parkland-wa/)
- [DuPont, WA](https://frontlinefireflood.com/service-areas/dupont-wa/)` / `IICRC CERTIFIED FIRM, IICRC AMRT (MOLD), IICRC WRT (WATER), IICRC FSRT (FIRE & SMOKE), IICRC ASD (STRUCTURAL DRYING), EPA LEAD-SAFE CERTIFIED, OSHA TRAINED` / `Greater Lakewood region` | computed at scaffold from plan + brand | |

## File layout

See `rank-ai/docs/build-site-skill-spec.md` § Outputs for the canonical tree.

## Content collections

`src/content/config.ts` defines the schemas every page entry must match. The collections map to the Astro routes:

| Collection  | Route file                                             | Frontmatter must include                   |
| ----------- | ------------------------------------------------------ | ------------------------------------------ |
| `pages`     | `src/pages/index.astro`, `src/pages/[fixed].astro`     | archetype, title, h1, meta_description, primary_keyword |
| `services`  | `src/pages/services/[slug].astro`                      | + service_slug, service_display            |
| `serviceAreas` | `src/pages/service-areas/[area].astro`             | + area_slug, city, state                   |
| `locations` | `src/pages/service-areas/[area]/[service].astro`       | + area_slug, service_slug, city, state, service_display |
| `blog`      | `src/pages/blog/[slug].astro`                          | + slug, published_at, services             |
| `legal`     | `src/pages/[legal].astro`                              | + ref (privacy/terms/accessibility)        |

## Adding a route

If a new archetype is added to the planning template, also add:
1. Content collection definition in `src/content/config.ts`
2. Route file under `src/pages/` matching the URL pattern
3. Schema-stub references in the route
4. Update this README's collection table

## Versioning

Bump `VERSION` whenever:
- A `{{TOKEN}}` is added or removed (breaking — scaffold must be updated)
- A content-collection field is added/removed/renamed (breaking — Skill 3's frontmatter writer must be updated)
- A new route or archetype is added (additive)
- A component/layout signature changes in a way Skill 3 consumes (potentially breaking)

Tweaks to copy or styling within an existing component are not breaking and don't require a bump.
