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
| `touch-of-class-cleaning-and-restoration` | client record `slug` | `narestco` |
| `Touch of Class Cleaning and Restoration ` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Touch of Class Cleaning and Restoration ` | plan-input `brand.short_name` | `NARESTCO` |
| `Touch of Class Cleaning and Restoration ` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `touch-of-class-cleaning-and-restoration.invalid` | client record `domain` | `narestco.com` |
| `https://touch-of-class-cleaning-and-restoration.invalid` | derived | `https://narestco.com` |
| `(979) 418-6099` / `+19794186099` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `touchofclasscc@yahoo.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2025` | brand.founded_year | `2004` |
| `Richardson` / `TX` | derived from primary area | `Federal Way` / `WA` |
| `1250 Brazosport Blvd #23` / `77531` | brand.street_address / brand.postal_code | |
| `` / `` | brand.lat / brand.lng | from GBP |
| `` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `[]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Richardson, TX.` | brand.tagline | short marketing line |
| `#171717` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `https://images.touch-of-class-cleaning-and-restoration.invalid/brand/logo.png` / `TO` | derived; logo lives on the per-client R2 bucket | |
| `https://images.touch-of-class-cleaning-and-restoration.invalid` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://touch-of-class-cleaning-and-restoration.invalid/services/water-damage-restoration/)` / `- [Richardson, TX](https://touch-of-class-cleaning-and-restoration.invalid/service-areas/richardson-tx/)
- [Dallas, TX](https://touch-of-class-cleaning-and-restoration.invalid/service-areas/dallas-tx/)
- [Plano, TX](https://touch-of-class-cleaning-and-restoration.invalid/service-areas/plano-tx/)
- [Garland, TX](https://touch-of-class-cleaning-and-restoration.invalid/service-areas/garland-tx/)
- [McKinney, TX](https://touch-of-class-cleaning-and-restoration.invalid/service-areas/mckinney-tx/)
- [Carrollton, TX](https://touch-of-class-cleaning-and-restoration.invalid/service-areas/carrollton-tx/)
- [Allen, TX](https://touch-of-class-cleaning-and-restoration.invalid/service-areas/allen-tx/)
- [Rowlett, TX](https://touch-of-class-cleaning-and-restoration.invalid/service-areas/rowlett-tx/)
- [Wylie, TX](https://touch-of-class-cleaning-and-restoration.invalid/service-areas/wylie-tx/)` / `Available on request` / `Greater Richardson region` | computed at scaffold from plan + brand | |

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
