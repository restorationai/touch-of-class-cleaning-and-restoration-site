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
| `heritage-restoration-llc` | client record `slug` | `narestco` |
| `Heritage Restoration LLC` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Heritage Restoration LLC` | plan-input `brand.short_name` | `NARESTCO` |
| `Heritage Restoration LLC` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `heritagermn.com` | client record `domain` | `narestco.com` |
| `https://heritagermn.com` | derived | `https://narestco.com` |
| `(320) 733-8868` / `+13207338868` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `support@heritagermn.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2023` | brand.founded_year | `2004` |
| `Little Falls` / `MN` | derived from primary area | `Federal Way` / `WA` |
| `10984 Harvest Road` / `56345` | brand.street_address / brand.postal_code | |
| `45.9763545` / `-94.3625024` | brand.lat / brand.lng | from GBP |
| `ChIJlRLa-3KCHy8RUE-lOQD16VU` / `` | brand.place_id / brand.google_cid | from GBP |
| `["BC807677"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC WRT (WATER)", "IICRC FSRT (FIRE & SMOKE)", "IICRC ASD (STRUCTURAL DRYING)", "EPA LEAD-SAFE CERTIFIED", "IICRC AMRT (MOLD)"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Little Falls, MN.` | brand.tagline | short marketing line |
| `#171717` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `HR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.heritagermn.com` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://heritagermn.com/services/water-damage-restoration/)
- [Storm Damage Restoration](https://heritagermn.com/services/storm-damage-restoration/)
- [Renovations, Remodels and General Contracting](https://heritagermn.com/services/general-contracting/)
- [Water Cleanup](https://heritagermn.com/services/water-cleanup/)` / `- [Little Falls, MN](https://heritagermn.com/service-areas/little-falls-mn/)
- [St. Cloud, MN](https://heritagermn.com/service-areas/st-cloud-mn/)
- [Sartell, MN](https://heritagermn.com/service-areas/sartell-mn/)
- [Sauk Rapids, MN](https://heritagermn.com/service-areas/sauk-rapids-mn/)
- [Brainerd, MN](https://heritagermn.com/service-areas/brainerd-mn/)
- [Baxter, MN](https://heritagermn.com/service-areas/baxter-mn/)
- [Foley, MN](https://heritagermn.com/service-areas/foley-mn/)
- [Royalton, MN](https://heritagermn.com/service-areas/royalton-mn/)
- [Pierz, MN](https://heritagermn.com/service-areas/pierz-mn/)` / `IICRC WRT (WATER), IICRC FSRT (FIRE & SMOKE), IICRC ASD (STRUCTURAL DRYING), EPA LEAD-SAFE CERTIFIED, IICRC AMRT (MOLD)` / `Greater Little Falls region` | computed at scaffold from plan + brand | |

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
