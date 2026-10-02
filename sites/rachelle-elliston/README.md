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
| `rachelle-elliston` | client record `slug` | `narestco` |
| `Desert Valley Contracting Inc ` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Desert Valley Contracting Inc ` | plan-input `brand.short_name` | `NARESTCO` |
| `Desert Valley Contracting Inc ` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `desertvalleyrestoration.com` | client record `domain` | `narestco.com` |
| `https://desertvalleyrestoration.com` | derived | `https://narestco.com` |
| `(702) 633-5033` / `+17026335033` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `relliston@desertvalleyco.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2000` | brand.founded_year | `2004` |
| `North Las Vegas` / `NV` | derived from primary area | `Federal Way` / `WA` |
| `3808 N Octagon Rd` / `89030` | brand.street_address / brand.postal_code | |
| `36.2005191` / `-115.1214745` | brand.lat / brand.lng | from GBP |
| `ChIJHe5ukQHCyIARitorWulYy8U` / `` | brand.place_id / brand.google_cid | from GBP |
| `["0072652-B & B6"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC CERTIFIED FIRM", "IICRC AMRT (MOLD)", "OSHA TRAINED", "IICRC FSRT (FIRE & SMOKE)", "IICRC WRT (WATER)", "IICRC ASD (STRUCTURAL DRYING)", "EPA LEAD-SAFE CERTIFIED"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in North Las Vegas, NV.` | brand.tagline | short marketing line |
| `#171717` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `DV` | derived; logo lives on the per-client R2 bucket | |
| `https://images.desertvalleyrestoration.com` | `https://images.{domain}` | |
| `- [Biohazard Cleanup](https://desertvalleyrestoration.com/services/biohazard-cleanup/)
- [Contents Restoration & Storage](https://desertvalleyrestoration.com/services/contents-restoration-storage/)
- [Fire Damage Restoration](https://desertvalleyrestoration.com/services/fire-damage-restoration/)
- [Renovations, Remodels and General Contracting](https://desertvalleyrestoration.com/services/general-contracting/)
- [Mold Remediation](https://desertvalleyrestoration.com/services/mold-remediation/)
- [Odor Removal and Deodorization](https://desertvalleyrestoration.com/services/odor-removal/)
- [Sewage Cleanup and Sanitization](https://desertvalleyrestoration.com/services/sewage-cleanup/)
- [Storm Damage Restoration](https://desertvalleyrestoration.com/services/storm-damage-restoration/)
- [Emergency Water Cleanup](https://desertvalleyrestoration.com/services/water-cleanup/)
- [Water Damage Restoration](https://desertvalleyrestoration.com/services/water-damage-restoration/)` / `- [North Las Vegas, NV](https://desertvalleyrestoration.com/service-areas/north-las-vegas-nv/)
- [Las Vegas, NV](https://desertvalleyrestoration.com/service-areas/las-vegas-nv/)
- [Henderson, NV](https://desertvalleyrestoration.com/service-areas/henderson-nv/)
- [Paradise, NV](https://desertvalleyrestoration.com/service-areas/paradise-nv/)
- [Spring Valley, NV](https://desertvalleyrestoration.com/service-areas/spring-valley-nv/)
- [Sunrise Manor, NV](https://desertvalleyrestoration.com/service-areas/sunrise-manor-nv/)
- [Enterprise, NV](https://desertvalleyrestoration.com/service-areas/enterprise-nv/)
- [Summerlin, NV](https://desertvalleyrestoration.com/service-areas/summerlin-nv/)
- [Boulder City, NV](https://desertvalleyrestoration.com/service-areas/boulder-city-nv/)
- [Winchester, NV](https://desertvalleyrestoration.com/service-areas/winchester-nv/)
- [Whitney, NV](https://desertvalleyrestoration.com/service-areas/whitney-nv/)
- [Summerlin South, NV](https://desertvalleyrestoration.com/service-areas/summerlin-south-nv/)
- [Blue Diamond, NV](https://desertvalleyrestoration.com/service-areas/blue-diamond-nv/)
- [Mount Charleston, NV](https://desertvalleyrestoration.com/service-areas/mount-charleston-nv/)
- [Sandy Valley, NV](https://desertvalleyrestoration.com/service-areas/sandy-valley-nv/)
- [Nelson, NV](https://desertvalleyrestoration.com/service-areas/nelson-nv/)
- [Indian Springs, NV](https://desertvalleyrestoration.com/service-areas/indian-springs-nv/)
- [Moapa Town, NV](https://desertvalleyrestoration.com/service-areas/moapa-town-nv/)
- [Moapa Valley, NV](https://desertvalleyrestoration.com/service-areas/moapa-valley-nv/)
- [Searchlight, NV](https://desertvalleyrestoration.com/service-areas/searchlight-nv/)` / `IICRC CERTIFIED FIRM, IICRC AMRT (MOLD), OSHA TRAINED, IICRC FSRT (FIRE & SMOKE), IICRC WRT (WATER), IICRC ASD (STRUCTURAL DRYING), EPA LEAD-SAFE CERTIFIED` / `Greater North Las Vegas region` | computed at scaffold from plan + brand | |

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
