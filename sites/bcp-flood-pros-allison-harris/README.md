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
| `bcp-flood-pros-allison-harris` | client record `slug` | `narestco` |
| `FIX Restoration` | plan-input `brand.display_name` | `National Restoration Construction` |
| `FIX Restoration` | plan-input `brand.short_name` | `NARESTCO` |
| `FIX Restoration` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `bcp-flood-pros-allison-harris.invalid` | client record `domain` | `narestco.com` |
| `https://bcp-flood-pros-allison-harris.invalid` | derived | `https://narestco.com` |
| `(801) 930-9750` / `+18019309750` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `scott.noland@gofloodpros.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2012` | brand.founded_year | `2004` |
| `American Fork` / `UT` | derived from primary area | `Federal Way` / `WA` |
| `250 W Main St` / `84003` | brand.street_address / brand.postal_code | |
| `40.3768064` / `-111.7959146` | brand.lat / brand.lng | from GBP |
| `` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `[]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in American Fork, UT.` | brand.tagline | short marketing line |
| `#171717` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `https://images.bcp-flood-pros-allison-harris.invalid/brand/logo.png` / `FR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.bcp-flood-pros-allison-harris.invalid` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://bcp-flood-pros-allison-harris.invalid/services/water-damage-restoration/)
- [Storm Damage Restoration](https://bcp-flood-pros-allison-harris.invalid/services/storm-damage-restoration/)
- [Fire Damage Restoration](https://bcp-flood-pros-allison-harris.invalid/services/fire-damage-restoration/)
- [Renovations, Remodels and General Contracting](https://bcp-flood-pros-allison-harris.invalid/services/general-contracting/)
- [Sewage Cleanup and Sanitization](https://bcp-flood-pros-allison-harris.invalid/services/sewage-cleanup/)
- [Emergency Board-Up and Tarping](https://bcp-flood-pros-allison-harris.invalid/services/emergency-board-up-tarping/)
- [Water Cleanup](https://bcp-flood-pros-allison-harris.invalid/services/water-cleanup/)
- [Mold Remediation](https://bcp-flood-pros-allison-harris.invalid/services/mold-remediation/)
- [Biohazard Cleanup](https://bcp-flood-pros-allison-harris.invalid/services/biohazard-cleanup/)
- [Contents Restoration & Storage](https://bcp-flood-pros-allison-harris.invalid/services/contents-restoration-storage/)
- [Flood & Drying Equipment Rental](https://bcp-flood-pros-allison-harris.invalid/services/flood-equipment-rental/)` / `- [American Fork, UT](https://bcp-flood-pros-allison-harris.invalid/service-areas/american-fork-ut/)
- [Provo, UT](https://bcp-flood-pros-allison-harris.invalid/service-areas/provo-ut/)
- [Orem, UT](https://bcp-flood-pros-allison-harris.invalid/service-areas/orem-ut/)
- [Lehi, UT](https://bcp-flood-pros-allison-harris.invalid/service-areas/lehi-ut/)
- [Pleasant Grove, UT](https://bcp-flood-pros-allison-harris.invalid/service-areas/pleasant-grove-ut/)
- [Spanish Fork, UT](https://bcp-flood-pros-allison-harris.invalid/service-areas/spanish-fork-ut/)
- [Springville, UT](https://bcp-flood-pros-allison-harris.invalid/service-areas/springville-ut/)
- [Saratoga Springs, UT](https://bcp-flood-pros-allison-harris.invalid/service-areas/saratoga-springs-ut/)
- [Highland, UT](https://bcp-flood-pros-allison-harris.invalid/service-areas/highland-ut/)` / `Available on request` / `Greater American Fork region` | computed at scaffold from plan + brand | |

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
