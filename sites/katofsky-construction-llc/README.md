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
| `katofsky-construction-llc` | client record `slug` | `narestco` |
| `Katofsky Construction LLC` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Katofsky Construction LLC` | plan-input `brand.short_name` | `NARESTCO` |
| `Katofsky Construction LLC` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `katofskyconstruction.com` | client record `domain` | `narestco.com` |
| `https://katofskyconstruction.com` | derived | `https://narestco.com` |
| `(412) 304-9284` / `+14123049284` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `michael@katofskyconstruction.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Pittsburgh` / `PA` | derived from primary area | `Federal Way` / `WA` |
| `150 Leroy st ` / `15239` | brand.street_address / brand.postal_code | |
| `40.4406968` / `-80.0025666` | brand.lat / brand.lng | from GBP |
| `` / `` | brand.place_id / brand.google_cid | from GBP |
| `["090877"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "IICRC AMRT (MOLD)"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Pittsburgh, PA.` | brand.tagline | short marketing line |
| `#171717` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `KC` | derived; logo lives on the per-client R2 bucket | |
| `https://images.katofskyconstruction.com` | `https://images.{domain}` | |
| `- [Fire Damage Restoration](https://katofskyconstruction.com/services/fire-damage-restoration/)
- [Renovations, Remodels and General Contracting](https://katofskyconstruction.com/services/general-contracting/)
- [Roofing Installation and Replacement](https://katofskyconstruction.com/services/roofing/)
- [Sewage Cleanup and Sanitization](https://katofskyconstruction.com/services/sewage-cleanup/)
- [Biohazard Cleanup](https://katofskyconstruction.com/services/biohazard-cleanup/)
- [Asbestos Abatement](https://katofskyconstruction.com/services/asbestos-abatement/)
- [Lead Paint Abatement](https://katofskyconstruction.com/services/lead-paint-abatement/)
- [Emergency Board-Up and Tarping](https://katofskyconstruction.com/services/emergency-board-up-tarping/)
- [Contents Restoration & Storage](https://katofskyconstruction.com/services/contents-restoration-storage/)
- [Air Duct Cleaning](https://katofskyconstruction.com/services/air-duct-cleaning/)
- [Carpet Cleaning](https://katofskyconstruction.com/services/carpet-cleaning/)
- [Upholstery Cleaning](https://katofskyconstruction.com/services/upholstery-cleaning/)` / `- [Pittsburgh, PA](https://katofskyconstruction.com/service-areas/pittsburgh-pa/)
- [Penn Hills, PA](https://katofskyconstruction.com/service-areas/penn-hills-pa/)
- [McCandless, PA](https://katofskyconstruction.com/service-areas/mccandless-pa/)
- [Bethel Park, PA](https://katofskyconstruction.com/service-areas/bethel-park-pa/)
- [Mount Lebanon, PA](https://katofskyconstruction.com/service-areas/mount-lebanon-pa/)
- [Ross Township, PA](https://katofskyconstruction.com/service-areas/ross-township-pa/)
- [Monroeville, PA](https://katofskyconstruction.com/service-areas/monroeville-pa/)
- [Shaler Township, PA](https://katofskyconstruction.com/service-areas/shaler-township-pa/)
- [Plum, PA](https://katofskyconstruction.com/service-areas/plum-pa/)
- [West Mifflin, PA](https://katofskyconstruction.com/service-areas/west-mifflin-pa/)
- [McKeesport, PA](https://katofskyconstruction.com/service-areas/mckeesport-pa/)
- [Baldwin, PA](https://katofskyconstruction.com/service-areas/baldwin-pa/)
- [Greensburg, PA](https://katofskyconstruction.com/service-areas/greensburg-pa/)
- [Hempfield Township, PA](https://katofskyconstruction.com/service-areas/hempfield-township-pa/)
- [North Huntingdon, PA](https://katofskyconstruction.com/service-areas/north-huntingdon-pa/)
- [New Kensington, PA](https://katofskyconstruction.com/service-areas/new-kensington-pa/)
- [Murrysville, PA](https://katofskyconstruction.com/service-areas/murrysville-pa/)
- [Latrobe, PA](https://katofskyconstruction.com/service-areas/latrobe-pa/)
- [Lower Burrell, PA](https://katofskyconstruction.com/service-areas/lower-burrell-pa/)
- [Jeannette, PA](https://katofskyconstruction.com/service-areas/jeannette-pa/)
- [Green Tree, PA](https://katofskyconstruction.com/service-areas/green-tree-pa/)
- [Carnegie, PA](https://katofskyconstruction.com/service-areas/carnegie-pa/)` / `IICRC CERTIFIED FIRM, IICRC WRT (WATER), IICRC AMRT (MOLD)` / `Greater Pittsburgh region` | computed at scaffold from plan + brand | |

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
