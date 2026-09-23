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
| `coastal-restoration-services` | client record `slug` | `narestco` |
| `Coastal Restoration Services Inc` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Coastal Restoration Services Inc` | plan-input `brand.short_name` | `NARESTCO` |
| `Coastal Restoration Services Inc` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `callcrs.com` | client record `domain` | `narestco.com` |
| `https://callcrs.com` | derived | `https://narestco.com` |
| `(805) 345-7440` / `+18053457440` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `tony@callcrs.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Santa Maria` / `CA` | derived from primary area | `Federal Way` / `WA` |
| `217 E Fesler St` / `93454` | brand.street_address / brand.postal_code | |
| `34.9531295` / `-120.435857` | brand.lat / brand.lng | from GBP |
| `ChIJgb6Gdhxh4wYRjbzm6ELYT38` / `` | brand.place_id / brand.google_cid | from GBP |
| `["11245226"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `"IICRC Certified Firm; WRT (Water Damage Restoration Technician); ASD (Applied Structural Drying)"` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Santa Maria, CA.` | brand.tagline | short marketing line |
| `#e6ac1a` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.webp` / `CR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.callcrs.com` | `https://images.{domain}` | |
| `- [Biohazard Cleanup](https://callcrs.com/services/biohazard-cleanup/)
- [Contents Restoration and Storage](https://callcrs.com/services/contents-restoration/)
- [Contents Restoration & Storage](https://callcrs.com/services/contents-restoration-storage/)
- [Crawl Space Encapsulation](https://callcrs.com/services/crawl-space-encapsulation/)
- [Emergency Board-Up and Tarping](https://callcrs.com/services/emergency-board-up-tarping/)
- [Fire Damage Restoration](https://callcrs.com/services/fire-damage-restoration/)
- [Mold Remediation](https://callcrs.com/services/mold-remediation/)
- [Odor Removal and Deodorization](https://callcrs.com/services/odor-removal/)
- [Post-Construction and Specialty Cleaning](https://callcrs.com/services/post-construction-cleaning/)
- [Sewage Cleanup and Sanitization](https://callcrs.com/services/sewage-cleanup/)
- [Storm Damage Restoration](https://callcrs.com/services/storm-damage-restoration/)
- [Vandalism Cleanup](https://callcrs.com/services/vandalism-cleanup/)
- [Water Damage Restoration](https://callcrs.com/services/water-damage-restoration/)` / `- [Vandenberg Village, CA](https://callcrs.com/service-areas/vandenberg-village-ca/)
- [Santa Maria, CA](https://callcrs.com/service-areas/santa-maria-ca/)
- [Orcutt, CA](https://callcrs.com/service-areas/orcutt-ca/)
- [Los Alamos, CA](https://callcrs.com/service-areas/los-alamos-ca/)
- [Lompoc, CA](https://callcrs.com/service-areas/lompoc-ca/)
- [Los Olivos, CA](https://callcrs.com/service-areas/los-olivos-ca/)
- [Mission Hills, CA](https://callcrs.com/service-areas/mission-hills-ca/)
- [Santa Ynez, CA](https://callcrs.com/service-areas/santa-ynez-ca/)
- [Solvang, CA](https://callcrs.com/service-areas/solvang-ca/)
- [Vandenberg AFB, CA](https://callcrs.com/service-areas/vandenberg-afb-ca/)
- [Guadalupe, CA](https://callcrs.com/service-areas/guadalupe-ca/)
- [Buellton, CA](https://callcrs.com/service-areas/buellton-ca/)
- [Ballard, CA](https://callcrs.com/service-areas/ballard-ca/)
- [Arroyo Grande, CA](https://callcrs.com/service-areas/arroyo-grande-ca/)
- [Avila Beach, CA](https://callcrs.com/service-areas/avila-beach-ca/)
- [Cambria, CA](https://callcrs.com/service-areas/cambria-ca/)
- [El Paso de Robles, CA](https://callcrs.com/service-areas/el-paso-de-robles-ca/)
- [Grover Beach, CA](https://callcrs.com/service-areas/grover-beach-ca/)
- [Los Berros, CA](https://callcrs.com/service-areas/los-berros-ca/)
- [Nipomo, CA](https://callcrs.com/service-areas/nipomo-ca/)
- [Oceano, CA](https://callcrs.com/service-areas/oceano-ca/)
- [San Luis Obispo, CA](https://callcrs.com/service-areas/san-luis-obispo-ca/)
- [Templeton, CA](https://callcrs.com/service-areas/templeton-ca/)
- [Santa Margarita, CA](https://callcrs.com/service-areas/santa-margarita-ca/)
- [Pismo Beach, CA](https://callcrs.com/service-areas/pismo-beach-ca/)
- [Morro Bay, CA](https://callcrs.com/service-areas/morro-bay-ca/)
- [Los Osos, CA](https://callcrs.com/service-areas/los-osos-ca/)
- [Edna, CA](https://callcrs.com/service-areas/edna-ca/)
- [Callender, CA](https://callcrs.com/service-areas/callender-ca/)
- [Blacklake, CA](https://callcrs.com/service-areas/blacklake-ca/)
- [Atascadero, CA](https://callcrs.com/service-areas/atascadero-ca/)` / `I, I, C, R, C,  , C, e, r, t, i, f, i, e, d,  , F, i, r, m, ;,  , W, R, T,  , (, W, a, t, e, r,  , D, a, m, a, g, e,  , R, e, s, t, o, r, a, t, i, o, n,  , T, e, c, h, n, i, c, i, a, n, ), ;,  , A, S, D,  , (, A, p, p, l, i, e, d,  , S, t, r, u, c, t, u, r, a, l,  , D, r, y, i, n, g, )` / `Greater Vandenberg Village region` | computed at scaffold from plan + brand | |

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
