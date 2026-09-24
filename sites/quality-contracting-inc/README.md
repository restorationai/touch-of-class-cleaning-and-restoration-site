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
| `quality-contracting-inc` | client record `slug` | `narestco` |
| `Quality Contracting, Inc.` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Quality Contracting, Inc.` | plan-input `brand.short_name` | `NARESTCO` |
| `Quality Contracting, Inc.` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `qualitycontracting.us` | client record `domain` | `narestco.com` |
| `https://qualitycontracting.us` | derived | `https://narestco.com` |
| `(508) 756-8800` / `+15087568800` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `info@qualitycontracting.us` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Auburn` / `MA` | derived from primary area | `Federal Way` / `WA` |
| `211 Southbridge Street` / `01501` | brand.street_address / brand.postal_code | |
| `42.1945465` / `-71.8358095` | brand.lat / brand.lng | from GBP |
| `ChIJ9wuzUNMF5IkR23w7vv0t_Hc` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `[]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `["https://www.facebook.com/qualcon534/", "https://www.linkedin.com/company/quality-contracting-inc-"]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Auburn, MA.` | brand.tagline | short marketing line |
| `#dc0a0e` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `QC` | derived; logo lives on the per-client R2 bucket | |
| `https://images.qualitycontracting.us` | `https://images.{domain}` | |
| `- [Air Duct Cleaning](https://qualitycontracting.us/services/air-duct-cleaning/)
- [Asbestos Abatement](https://qualitycontracting.us/services/asbestos-abatement/)
- [Biohazard Cleanup](https://qualitycontracting.us/services/biohazard-cleanup/)
- [Carpet Cleaning](https://qualitycontracting.us/services/carpet-cleaning/)
- [Contents Restoration and Storage](https://qualitycontracting.us/services/contents-restoration/)
- [Contents Restoration & Storage](https://qualitycontracting.us/services/contents-restoration-storage/)
- [Crawl Space Encapsulation](https://qualitycontracting.us/services/crawl-space-encapsulation/)
- [Emergency Board-Up and Tarping](https://qualitycontracting.us/services/emergency-board-up-tarping/)
- [Emergency Plumbing](https://qualitycontracting.us/services/emergency-plumbing/)
- [Fire Damage Restoration](https://qualitycontracting.us/services/fire-damage-restoration/)
- [Renovations, Remodels and General Contracting](https://qualitycontracting.us/services/general-contracting/)
- [Mold Remediation](https://qualitycontracting.us/services/mold-remediation/)
- [Odor Removal and Deodorization](https://qualitycontracting.us/services/odor-removal/)
- [Post-Construction and Specialty Cleaning](https://qualitycontracting.us/services/post-construction-cleaning/)
- [Roofing Installation and Replacement](https://qualitycontracting.us/services/roofing/)
- [Sewage Cleanup and Sanitization](https://qualitycontracting.us/services/sewage-cleanup/)
- [Storm Damage Restoration](https://qualitycontracting.us/services/storm-damage-restoration/)
- [Vandalism Cleanup](https://qualitycontracting.us/services/vandalism-cleanup/)
- [Water Damage Restoration](https://qualitycontracting.us/services/water-damage-restoration/)
- [Water Leak Detection](https://qualitycontracting.us/services/water-leak-detection/)` / `- [Auburn, MA](https://qualitycontracting.us/service-areas/auburn-ma/)
- [Worcester, MA](https://qualitycontracting.us/service-areas/worcester-ma/)
- [Shrewsbury, MA](https://qualitycontracting.us/service-areas/shrewsbury-ma/)
- [Westborough, MA](https://qualitycontracting.us/service-areas/westborough-ma/)
- [Southborough, MA](https://qualitycontracting.us/service-areas/southborough-ma/)
- [Hopkinton, MA](https://qualitycontracting.us/service-areas/hopkinton-ma/)
- [Framingham, MA](https://qualitycontracting.us/service-areas/framingham-ma/)
- [Natick, MA](https://qualitycontracting.us/service-areas/natick-ma/)
- [Wellesley, MA](https://qualitycontracting.us/service-areas/wellesley-ma/)
- [Needham, MA](https://qualitycontracting.us/service-areas/needham-ma/)
- [Newton, MA](https://qualitycontracting.us/service-areas/newton-ma/)
- [Weston, MA](https://qualitycontracting.us/service-areas/weston-ma/)
- [Oxford, MA](https://qualitycontracting.us/service-areas/oxford-ma/)
- [Whitinsville, MA](https://qualitycontracting.us/service-areas/whitinsville-ma/)
- [East Douglas, MA](https://qualitycontracting.us/service-areas/east-douglas-ma/)
- [Northborough, MA](https://qualitycontracting.us/service-areas/northborough-ma/)
- [Southbridge Town, MA](https://qualitycontracting.us/service-areas/southbridge-town-ma/)
- [Sturbridge, MA](https://qualitycontracting.us/service-areas/sturbridge-ma/)
- [Fiskdale, MA](https://qualitycontracting.us/service-areas/fiskdale-ma/)
- [Milford, MA](https://qualitycontracting.us/service-areas/milford-ma/)
- [Marlborough, MA](https://qualitycontracting.us/service-areas/marlborough-ma/)
- [Hudson, MA](https://qualitycontracting.us/service-areas/hudson-ma/)
- [Bellingham, MA](https://qualitycontracting.us/service-areas/bellingham-ma/)
- [Ware, MA](https://qualitycontracting.us/service-areas/ware-ma/)
- [Leominster, MA](https://qualitycontracting.us/service-areas/leominster-ma/)
- [Franklin Town, MA](https://qualitycontracting.us/service-areas/franklin-town-ma/)
- [Palmer Town, MA](https://qualitycontracting.us/service-areas/palmer-town-ma/)
- [Maynard, MA](https://qualitycontracting.us/service-areas/maynard-ma/)` / `Available on request` / `Southern New England, with crews responding across a 50 mile radius of Auburn` | computed at scaffold from plan + brand | |

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
