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
| `restoration-groups` | client record `slug` | `narestco` |
| `The Restoration Group` | plan-input `brand.display_name` | `National Restoration Construction` |
| `The Restoration Group` | plan-input `brand.short_name` | `NARESTCO` |
| `The Restoration Group` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `therestorationgroup.com` | client record `domain` | `narestco.com` |
| `https://therestorationgroup.com` | derived | `https://narestco.com` |
| `(855) 650-7422` / `+18556507422` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2021` | brand.founded_year | `2004` |
| `Kenilworth` / `NJ` | derived from primary area | `Federal Way` / `WA` |
| `500 S 31st St` / `07033` | brand.street_address / brand.postal_code | |
| `40.6749` / `-74.2957` | brand.lat / brand.lng | from GBP |
| `ChIJfZMnExzVxiIRkevldLILJW8` / `8008820373441604497` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `NJ Division of Consumer Affairs` / `NJ Licensed Home Improvement Contractor` | brand.license_authority / brand.license_type | |
| `["IICRC Certified Firm #210213"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `["https://www.google.com/maps?cid=8008820373441604497"]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 water, fire & mold damage restoration across New Jersey.` | brand.tagline | short marketing line |
| `#c8102e` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `` / `TR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.therestorationgroup.com` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://therestorationgroup.com/services/water-damage-restoration/)
- [Flood Damage Restoration](https://therestorationgroup.com/services/flood-damage-restoration/)
- [Burst Pipe Cleanup and Repair](https://therestorationgroup.com/services/burst-pipe-repair/)
- [Basement Flooding Cleanup](https://therestorationgroup.com/services/basement-flooding-cleanup/)
- [Appliance Leak Cleanup](https://therestorationgroup.com/services/appliance-leak-cleanup/)
- [Sewage Cleanup and Sanitization](https://therestorationgroup.com/services/sewage-cleanup/)
- [Fire Damage Restoration](https://therestorationgroup.com/services/fire-damage-restoration/)
- [Smoke Damage Restoration](https://therestorationgroup.com/services/smoke-damage-restoration/)
- [Odor Removal and Deodorization](https://therestorationgroup.com/services/odor-removal/)
- [Mold Remediation](https://therestorationgroup.com/services/mold-remediation/)
- [Mold Inspection and Testing](https://therestorationgroup.com/services/mold-inspection-testing/)
- [Storm Damage Restoration](https://therestorationgroup.com/services/storm-damage-restoration/)
- [Emergency Board-Up and Tarping](https://therestorationgroup.com/services/emergency-board-up-tarping/)
- [Commercial Restoration](https://therestorationgroup.com/services/commercial-restoration/)
- [Reconstruction Services](https://therestorationgroup.com/services/reconstruction/)
- [Renovations, Remodels and General Contracting](https://therestorationgroup.com/services/general-contracting/)` / `- [Kenilworth, NJ](https://therestorationgroup.com/service-areas/kenilworth-nj/)
- [Union, NJ](https://therestorationgroup.com/service-areas/union-nj/)
- [Elizabeth, NJ](https://therestorationgroup.com/service-areas/elizabeth-nj/)
- [Westfield, NJ](https://therestorationgroup.com/service-areas/westfield-nj/)
- [Cranford, NJ](https://therestorationgroup.com/service-areas/cranford-nj/)
- [Springfield, NJ](https://therestorationgroup.com/service-areas/springfield-nj/)
- [Summit, NJ](https://therestorationgroup.com/service-areas/summit-nj/)
- [Newark, NJ](https://therestorationgroup.com/service-areas/newark-nj/)
- [Jersey City, NJ](https://therestorationgroup.com/service-areas/jersey-city-nj/)
- [Brooklyn, NY](https://therestorationgroup.com/service-areas/brooklyn-ny/)
- [Manhattan, NY](https://therestorationgroup.com/service-areas/manhattan-ny/)` / `IICRC Certified Firm #210213` / `Union County NJ home base (Kenilworth) with statewide New Jersey focus plus the Brooklyn and Manhattan NY metro` | computed at scaffold from plan + brand | |

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
