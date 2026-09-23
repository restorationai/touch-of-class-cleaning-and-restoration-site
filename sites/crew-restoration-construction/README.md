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
| `crew3r.com` | client record `domain` | `narestco.com` |
| `https://crew3r.com` | derived | `https://narestco.com` |
| `(605) 965-2727` / `+16059652727` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `estimates@crewthatcares.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2015` | brand.founded_year | `2004` |
| `Sioux Falls` / `SD` | derived from primary area | `Federal Way` / `WA` |
| `3503 South Norton Avenue` / `57110` | brand.street_address / brand.postal_code | |
| `43.5476008` / `-96.7293629` | brand.lat / brand.lng | from GBP |
| `ChIJ62IxEgm2jocRJj94-dsO6Nw` / `` | brand.place_id / brand.google_cid | from GBP |
| `["3814"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Sioux Falls, SD.` | brand.tagline | short marketing line |
| `#b31217` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `CR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.crew3r.com` | `https://images.{domain}` | |
| `- [Asbestos Abatement](https://crew3r.com/services/asbestos-abatement/)
- [Biohazard Cleanup](https://crew3r.com/services/biohazard-cleanup/)
- [Contents Restoration and Storage](https://crew3r.com/services/contents-restoration/)
- [Contents Restoration & Storage](https://crew3r.com/services/contents-restoration-storage/)
- [Emergency Board-Up and Tarping](https://crew3r.com/services/emergency-board-up-tarping/)
- [Fire Damage Restoration](https://crew3r.com/services/fire-damage-restoration/)
- [Renovations, Remodels and General Contracting](https://crew3r.com/services/general-contracting/)
- [Mold Remediation](https://crew3r.com/services/mold-remediation/)
- [Post-Construction and Specialty Cleaning](https://crew3r.com/services/post-construction-cleaning/)
- [Roofing Installation and Replacement](https://crew3r.com/services/roofing/)
- [Sewage Cleanup and Sanitization](https://crew3r.com/services/sewage-cleanup/)
- [Siding and Gutters](https://crew3r.com/services/siding-gutters/)
- [Storm Damage Restoration](https://crew3r.com/services/storm-damage-restoration/)
- [Water Damage Restoration](https://crew3r.com/services/water-damage-restoration/)` / `- [Sioux Falls, SD](https://crew3r.com/service-areas/sioux-falls-sd/)
- [Brookings, SD](https://crew3r.com/service-areas/brookings-sd/)
- [Yankton, SD](https://crew3r.com/service-areas/yankton-sd/)
- [Worthington, MN](https://crew3r.com/service-areas/worthington-mn/)
- [Brandon, SD](https://crew3r.com/service-areas/brandon-sd/)
- [Le Mars, IA](https://crew3r.com/service-areas/le-mars-ia/)
- [Sioux Center, IA](https://crew3r.com/service-areas/sioux-center-ia/)
- [Harrisburg, SD](https://crew3r.com/service-areas/harrisburg-sd/)
- [Madison, SD](https://crew3r.com/service-areas/madison-sd/)
- [Tea, SD](https://crew3r.com/service-areas/tea-sd/)
- [Orange City, IA](https://crew3r.com/service-areas/orange-city-ia/)
- [Luverne, MN](https://crew3r.com/service-areas/luverne-mn/)
- [Pipestone, MN](https://crew3r.com/service-areas/pipestone-mn/)
- [Rock Valley, IA](https://crew3r.com/service-areas/rock-valley-ia/)
- [Dell Rapids, SD](https://crew3r.com/service-areas/dell-rapids-sd/)
- [Hartford, SD](https://crew3r.com/service-areas/hartford-sd/)
- [Canton, SD](https://crew3r.com/service-areas/canton-sd/)
- [North Sioux City, SD](https://crew3r.com/service-areas/north-sioux-city-sd/)
- [Sibley, IA](https://crew3r.com/service-areas/sibley-ia/)
- [Rock Rapids, IA](https://crew3r.com/service-areas/rock-rapids-ia/)
- [Lennox, SD](https://crew3r.com/service-areas/lennox-sd/)
- [Flandreau, SD](https://crew3r.com/service-areas/flandreau-sd/)
- [Parker, SD](https://crew3r.com/service-areas/parker-sd/)
- [Salem, SD](https://crew3r.com/service-areas/salem-sd/)
- [Slayton, MN](https://crew3r.com/service-areas/slayton-mn/)
- [Crooks, SD](https://crew3r.com/service-areas/crooks-sd/)
- [Baltic, SD](https://crew3r.com/service-areas/baltic-sd/)
- [Garretson, SD](https://crew3r.com/service-areas/garretson-sd/)
- [Worthing, SD](https://crew3r.com/service-areas/worthing-sd/)
- [Volga, SD](https://crew3r.com/service-areas/volga-sd/)
- [Beresford, SD](https://crew3r.com/service-areas/beresford-sd/)
- [Dakota Dunes, SD](https://crew3r.com/service-areas/dakota-dunes-sd/)
- [Elk Point, SD](https://crew3r.com/service-areas/elk-point-sd/)
- [Adrian, MN](https://crew3r.com/service-areas/adrian-mn/)
- [Edgerton, MN](https://crew3r.com/service-areas/edgerton-mn/)
- [Fulda, MN](https://crew3r.com/service-areas/fulda-mn/)
- [George, IA](https://crew3r.com/service-areas/george-ia/)
- [Hawarden, IA](https://crew3r.com/service-areas/hawarden-ia/)
- [Hull, IA](https://crew3r.com/service-areas/hull-ia/)
- [Alton, IA](https://crew3r.com/service-areas/alton-ia/)
- [Akron, IA](https://crew3r.com/service-areas/akron-ia/)
- [Remsen, IA](https://crew3r.com/service-areas/remsen-ia/)
- [Hinton, IA](https://crew3r.com/service-areas/hinton-ia/)
- [Merrill, IA](https://crew3r.com/service-areas/merrill-ia/)
- [Kingsley, IA](https://crew3r.com/service-areas/kingsley-ia/)` / `IICRC` / `Greater Sioux Falls region` | computed at scaffold from plan + brand | |

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
