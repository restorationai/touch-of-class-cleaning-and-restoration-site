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
| `puroclean-east-las-vegas` | client record `slug` | `narestco` |
| `PuroClean of East Las Vegas` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Puroclean` | plan-input `brand.short_name` | `NARESTCO` |
| `PuroClean of East Las Vegas` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `purocleaneastlasvegas.com` | client record `domain` | `narestco.com` |
| `https://purocleaneastlasvegas.com` | derived | `https://narestco.com` |
| `+17025513040` / `+117025513040` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `eastlasvegas@puroclean.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Las Vegas` / `NV` | derived from primary area | `Federal Way` / `WA` |
| `2777 N Lamb Blvd` / `89115` | brand.street_address / brand.postal_code | |
| `36.2153` / `-115.0867` | brand.lat / brand.lng | from GBP |
| `ChIJWRNeaVbDyIAR429H1EKyxas` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `[]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Las Vegas, NV.` | brand.tagline | short marketing line |
| `#c50a1d` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `https://images.purocleaneastlasvegas.com/brand/logo.png` / `PO` | derived; logo lives on the per-client R2 bucket | |
| `https://images.purocleaneastlasvegas.com` | `https://images.{domain}` | |
| `- [Fire Damage Restoration](https://purocleaneastlasvegas.com/services/fire-damage-restoration/)
- [Mold Remediation](https://purocleaneastlasvegas.com/services/mold-remediation/)
- [Water Damage Restoration](https://purocleaneastlasvegas.com/services/water-damage-restoration/)
- [Sewage Cleanup and Sanitization](https://purocleaneastlasvegas.com/services/sewage-cleanup/)
- [Biohazard Cleanup](https://purocleaneastlasvegas.com/services/biohazard-cleanup/)` / `- [Las Vegas, NV](https://purocleaneastlasvegas.com/service-areas/las-vegas-nv/)
- [Henderson, NV](https://purocleaneastlasvegas.com/service-areas/henderson-nv/)
- [North Las Vegas, NV](https://purocleaneastlasvegas.com/service-areas/north-las-vegas-nv/)
- [Paradise, NV](https://purocleaneastlasvegas.com/service-areas/paradise-nv/)
- [Spring Valley, NV](https://purocleaneastlasvegas.com/service-areas/spring-valley-nv/)
- [Sunrise Manor, NV](https://purocleaneastlasvegas.com/service-areas/sunrise-manor-nv/)
- [Whitney, NV](https://purocleaneastlasvegas.com/service-areas/whitney-nv/)
- [Boulder City, NV](https://purocleaneastlasvegas.com/service-areas/boulder-city-nv/)` / `Available on request` / `Greater Las Vegas region` | computed at scaffold from plan + brand | |

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
