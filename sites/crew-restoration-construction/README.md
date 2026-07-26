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
| `crew-restoration-construction` | client record `slug` | `narestco` |
| `Crew Restoration & Construction` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Crew` | plan-input `brand.short_name` | `NARESTCO` |
| `Crew Restoration & Construction` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `` | client record `domain` | `narestco.com` |
| `https://None` | derived | `https://narestco.com` |
| `(605) 965-2727` / `+16059652727` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `estimates@crewthatcares.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Sioux Falls` / `SD` | derived from primary area | `Federal Way` / `WA` |
| `3503 South Norton Avenue` / `57110` | brand.street_address / brand.postal_code | |
| `43.5476008` / `-96.7293629` | brand.lat / brand.lng | from GBP |
| `ChIJ62IxEgm2jocRJj94-dsO6Nw` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `[]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Sioux Falls, SD.` | brand.tagline | short marketing line |
| `#b31217` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `https://images.None/brand/logo.png` / `CR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.None` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://None/services/water-damage-restoration/)
- [Fire Damage Restoration](https://None/services/fire-damage-restoration/)
- [Mold Remediation](https://None/services/mold-remediation/)
- [Storm Damage Restoration](https://None/services/storm-damage-restoration/)
- [Renovations, Remodels and General Contracting](https://None/services/general-contracting/)
- [Roofing Installation and Replacement](https://None/services/roofing/)
- [Sewage Cleanup and Sanitization](https://None/services/sewage-cleanup/)
- [Biohazard Cleanup](https://None/services/biohazard-cleanup/)
- [Asbestos Abatement](https://None/services/asbestos-abatement/)` / `- [Sioux Falls, SD](https://None/service-areas/sioux-falls-sd/)
- [Brookings, SD](https://None/service-areas/brookings-sd/)
- [Yankton, SD](https://None/service-areas/yankton-sd/)
- [Worthington, MN](https://None/service-areas/worthington-mn/)
- [Brandon, SD](https://None/service-areas/brandon-sd/)
- [Le Mars, IA](https://None/service-areas/le-mars-ia/)
- [Sioux Center, IA](https://None/service-areas/sioux-center-ia/)
- [Harrisburg, SD](https://None/service-areas/harrisburg-sd/)
- [Madison, SD](https://None/service-areas/madison-sd/)
- [Tea, SD](https://None/service-areas/tea-sd/)
- [Orange City, IA](https://None/service-areas/orange-city-ia/)
- [Luverne, MN](https://None/service-areas/luverne-mn/)
- [Pipestone, MN](https://None/service-areas/pipestone-mn/)
- [Rock Valley, IA](https://None/service-areas/rock-valley-ia/)
- [Dell Rapids, SD](https://None/service-areas/dell-rapids-sd/)
- [Hartford, SD](https://None/service-areas/hartford-sd/)
- [Canton, SD](https://None/service-areas/canton-sd/)
- [North Sioux City, SD](https://None/service-areas/north-sioux-city-sd/)
- [Sibley, IA](https://None/service-areas/sibley-ia/)
- [Rock Rapids, IA](https://None/service-areas/rock-rapids-ia/)
- [Lennox, SD](https://None/service-areas/lennox-sd/)
- [Flandreau, SD](https://None/service-areas/flandreau-sd/)
- [Parker, SD](https://None/service-areas/parker-sd/)
- [Salem, SD](https://None/service-areas/salem-sd/)
- [Slayton, MN](https://None/service-areas/slayton-mn/)` / `Available on request` / `Greater Sioux Falls region` | computed at scaffold from plan + brand | |

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
