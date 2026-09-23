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
| `reign-restoration` | client record `slug` | `narestco` |
| `Reign Restoration` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Reign Restoration` | plan-input `brand.short_name` | `NARESTCO` |
| `Reign Restoration` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `reign-restoration.com` | client record `domain` | `narestco.com` |
| `https://reign-restoration.com` | derived | `https://narestco.com` |
| `(214) 304-0621` / `+12143040621` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `jerrott@reign-restoration.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Royse City` / `TX` | derived from primary area | `Federal Way` / `WA` |
| `6691 TX- 276 STE C` / `75189` | brand.street_address / brand.postal_code | |
| `32.9761045` / `-96.331334` | brand.lat / brand.lng | from GBP |
| `ChIJXzVQsb7lS4YR7G33273qh8c` / `` | brand.place_id / brand.google_cid | from GBP |
| `["MRC2276"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC WRT (WATER)", "IICRC CERTIFIED FIRM", "IICRC AMRT (MOLD)", "IICRC FSRT (FIRE & SMOKE)"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Royse City, TX.` | brand.tagline | short marketing line |
| `#f2b623` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `RR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.reign-restoration.com` | `https://images.{domain}` | |
| `- [Contents Restoration and Storage](https://reign-restoration.com/services/contents-restoration/)
- [Contents Restoration & Storage](https://reign-restoration.com/services/contents-restoration-storage/)
- [Fire Damage Restoration](https://reign-restoration.com/services/fire-damage-restoration/)
- [Renovations, Remodels and General Contracting](https://reign-restoration.com/services/general-contracting/)
- [Mold Remediation](https://reign-restoration.com/services/mold-remediation/)
- [Odor Removal and Deodorization](https://reign-restoration.com/services/odor-removal/)
- [Roofing Installation and Replacement](https://reign-restoration.com/services/roofing/)
- [Storm Damage Restoration](https://reign-restoration.com/services/storm-damage-restoration/)
- [Water Damage Restoration](https://reign-restoration.com/services/water-damage-restoration/)` / `- [Royse City, TX](https://reign-restoration.com/service-areas/royse-city-tx/)
- [Rockwall, TX](https://reign-restoration.com/service-areas/rockwall-tx/)
- [Fate, TX](https://reign-restoration.com/service-areas/fate-tx/)
- [Rowlett, TX](https://reign-restoration.com/service-areas/rowlett-tx/)
- [Wylie, TX](https://reign-restoration.com/service-areas/wylie-tx/)
- [Garland, TX](https://reign-restoration.com/service-areas/garland-tx/)
- [Mesquite, TX](https://reign-restoration.com/service-areas/mesquite-tx/)
- [Dallas, TX](https://reign-restoration.com/service-areas/dallas-tx/)
- [Richardson, TX](https://reign-restoration.com/service-areas/richardson-tx/)
- [Plano, TX](https://reign-restoration.com/service-areas/plano-tx/)
- [Allen, TX](https://reign-restoration.com/service-areas/allen-tx/)
- [McKinney, TX](https://reign-restoration.com/service-areas/mckinney-tx/)
- [Frisco, TX](https://reign-restoration.com/service-areas/frisco-tx/)
- [Highland Park, TX](https://reign-restoration.com/service-areas/highland-park-tx/)
- [University Park, TX](https://reign-restoration.com/service-areas/university-park-tx/)
- [Greenville, TX](https://reign-restoration.com/service-areas/greenville-tx/)
- [Terrell, TX](https://reign-restoration.com/service-areas/terrell-tx/)
- [Nevada, TX](https://reign-restoration.com/service-areas/nevada-tx/)
- [Union Valley, TX](https://reign-restoration.com/service-areas/union-valley-tx/)
- [Josephine, TX](https://reign-restoration.com/service-areas/josephine-tx/)
- [Lavon, TX](https://reign-restoration.com/service-areas/lavon-tx/)
- [McLendon-Chisholm, TX](https://reign-restoration.com/service-areas/mclendon-chisholm-tx/)
- [Caddo Mills, TX](https://reign-restoration.com/service-areas/caddo-mills-tx/)
- [Poetry, TX](https://reign-restoration.com/service-areas/poetry-tx/)
- [Heath, TX](https://reign-restoration.com/service-areas/heath-tx/)
- [Farmersville, TX](https://reign-restoration.com/service-areas/farmersville-tx/)
- [Sachse, TX](https://reign-restoration.com/service-areas/sachse-tx/)
- [Lucas, TX](https://reign-restoration.com/service-areas/lucas-tx/)
- [Murphy, TX](https://reign-restoration.com/service-areas/murphy-tx/)` / `IICRC WRT (WATER), IICRC CERTIFIED FIRM, IICRC AMRT (MOLD), IICRC FSRT (FIRE & SMOKE)` / `Greater Royse City region` | computed at scaffold from plan + brand | |

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
