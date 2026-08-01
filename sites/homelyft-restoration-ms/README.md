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
| `homelyft-restoration-ms` | client record `slug` | `narestco` |
| `HomeLyft Restoration MS` | plan-input `brand.display_name` | `National Restoration Construction` |
| `HomeLyft Restoration MS` | plan-input `brand.short_name` | `NARESTCO` |
| `HomeLyft Restoration MS` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `` | client record `domain` | `narestco.com` |
| `https://None` | derived | `https://narestco.com` |
| `+12282845200` / `+112282845200` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `info@homelyft.net` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Gulfport` / `MS` | derived from primary area | `Federal Way` / `WA` |
| `1311 SPRING Street` / `39507` | brand.street_address / brand.postal_code | |
| `` / `` | brand.lat / brand.lng | from GBP |
| `` / `` | brand.place_id / brand.google_cid | from GBP |
| `["RO 2728"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `"IICRC CERTIFIED FIRM; IICRC WRT (WATER); IICRC ASD (STRUCTURAL DRYING); EPA LEAD-SAFE CERTIFIED; IICRC FSRT (FIRE & SMOKE); IICRC AMRT (MOLD); OSHA TRAINED; FORTIFIED-BUILDING-ROOFING-MS-WINDSTORM-CERTIFIED"` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Gulfport, MS.` | brand.tagline | short marketing line |
| `#dc2626` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `https://images.None/brand/logo.png` / `HR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.None` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://None/services/water-damage-restoration/)
- [Fire Damage Restoration](https://None/services/fire-damage-restoration/)
- [Mold Remediation](https://None/services/mold-remediation/)
- [Storm Damage Restoration](https://None/services/storm-damage-restoration/)
- [Sewage Cleanup and Sanitization](https://None/services/sewage-cleanup/)
- [Renovations, Remodels and General Contracting](https://None/services/general-contracting/)
- [Biohazard Cleanup](https://None/services/biohazard-cleanup/)
- [Asbestos Abatement](https://None/services/asbestos-abatement/)
- [Emergency Board-Up and Tarping](https://None/services/emergency-board-up-tarping/)
- [Contents Restoration and Storage](https://None/services/contents-restoration/)
- [Crawl Space Encapsulation](https://None/services/crawl-space-encapsulation/)
- [Carpet Cleaning](https://None/services/carpet-cleaning/)
- [Post-Construction and Specialty Cleaning](https://None/services/post-construction-cleaning/)` / `- [Bond, MS](https://None/service-areas/bond-ms/)
- [Eastabuchie, MS](https://None/service-areas/eastabuchie-ms/)
- [Glendale, MS](https://None/service-areas/glendale-ms/)
- [Hattiesburg, MS](https://None/service-areas/hattiesburg-ms/)
- [Petal, MS](https://None/service-areas/petal-ms/)
- [Rawls Springs, MS](https://None/service-areas/rawls-springs-ms/)
- [Leaf, MS](https://None/service-areas/leaf-ms/)
- [Leakesville, MS](https://None/service-areas/leakesville-ms/)
- [McLain, MS](https://None/service-areas/mclain-ms/)
- [State Line, MS](https://None/service-areas/state-line-ms/)
- [Biloxi, MS](https://None/service-areas/biloxi-ms/)
- [D'Iberville, MS](https://None/service-areas/d-iberville-ms/)
- [DeLisle, MS](https://None/service-areas/delisle-ms/)
- [Diamondhead, MS](https://None/service-areas/diamondhead-ms/)
- [Gulfport, MS](https://None/service-areas/gulfport-ms/)
- [Henderson Point, MS](https://None/service-areas/henderson-point-ms/)
- [Latimer, MS](https://None/service-areas/latimer-ms/)
- [Long Beach, MS](https://None/service-areas/long-beach-ms/)
- [Lyman, MS](https://None/service-areas/lyman-ms/)
- [Pass Christian, MS](https://None/service-areas/pass-christian-ms/)
- [Saucier, MS](https://None/service-areas/saucier-ms/)
- [St. Martin, MS](https://None/service-areas/st-martin-ms/)
- [Bay St. Louis, MS](https://None/service-areas/bay-st-louis-ms/)
- [Diamondhead, MS](https://None/service-areas/diamondhead-ms/)
- [Kiln, MS](https://None/service-areas/kiln-ms/)
- [Nicholson, MS](https://None/service-areas/nicholson-ms/)
- [Pearlington, MS](https://None/service-areas/pearlington-ms/)
- [Picayune, MS](https://None/service-areas/picayune-ms/)
- [Waveland, MS](https://None/service-areas/waveland-ms/)
- [Bond, MS](https://None/service-areas/bond-ms/)
- [Wiggins, MS](https://None/service-areas/wiggins-ms/)
- [Hide-A-Way Lake, MS](https://None/service-areas/hide-a-way-lake-ms/)
- [Lumberton, MS](https://None/service-areas/lumberton-ms/)
- [Nicholson, MS](https://None/service-areas/nicholson-ms/)
- [Picayune, MS](https://None/service-areas/picayune-ms/)
- [Poplarville, MS](https://None/service-areas/poplarville-ms/)
- [Big Point, MS](https://None/service-areas/big-point-ms/)
- [Biloxi, MS](https://None/service-areas/biloxi-ms/)
- [D'Iberville, MS](https://None/service-areas/d-iberville-ms/)
- [Escatawpa, MS](https://None/service-areas/escatawpa-ms/)
- [Gautier, MS](https://None/service-areas/gautier-ms/)
- [Gulf Hills, MS](https://None/service-areas/gulf-hills-ms/)
- [Gulf Park Estates, MS](https://None/service-areas/gulf-park-estates-ms/)
- [Helena, MS](https://None/service-areas/helena-ms/)
- [Hurley, MS](https://None/service-areas/hurley-ms/)
- [Latimer, MS](https://None/service-areas/latimer-ms/)
- [Moss Point, MS](https://None/service-areas/moss-point-ms/)
- [Ocean Springs, MS](https://None/service-areas/ocean-springs-ms/)
- [Pascagoula, MS](https://None/service-areas/pascagoula-ms/)
- [St. Martin, MS](https://None/service-areas/st-martin-ms/)
- [Vancleave, MS](https://None/service-areas/vancleave-ms/)
- [Wade, MS](https://None/service-areas/wade-ms/)
- [Agricola, MS](https://None/service-areas/agricola-ms/)
- [Benndale, MS](https://None/service-areas/benndale-ms/)
- [Lucedale, MS](https://None/service-areas/lucedale-ms/)
- [Eastabuchie, MS](https://None/service-areas/eastabuchie-ms/)
- [Ellisville, MS](https://None/service-areas/ellisville-ms/)
- [Laurel, MS](https://None/service-areas/laurel-ms/)
- [Moselle, MS](https://None/service-areas/moselle-ms/)
- [Ovett, MS](https://None/service-areas/ovett-ms/)
- [Sandersville, MS](https://None/service-areas/sandersville-ms/)
- [Sharon, MS](https://None/service-areas/sharon-ms/)
- [Soso, MS](https://None/service-areas/soso-ms/)` / `I, I, C, R, C,  , C, E, R, T, I, F, I, E, D,  , F, I, R, M, ;,  , I, I, C, R, C,  , W, R, T,  , (, W, A, T, E, R, ), ;,  , I, I, C, R, C,  , A, S, D,  , (, S, T, R, U, C, T, U, R, A, L,  , D, R, Y, I, N, G, ), ;,  , E, P, A,  , L, E, A, D, -, S, A, F, E,  , C, E, R, T, I, F, I, E, D, ;,  , I, I, C, R, C,  , F, S, R, T,  , (, F, I, R, E,  , &,  , S, M, O, K, E, ), ;,  , I, I, C, R, C,  , A, M, R, T,  , (, M, O, L, D, ), ;,  , O, S, H, A,  , T, R, A, I, N, E, D, ;,  , F, O, R, T, I, F, I, E, D, -, B, U, I, L, D, I, N, G, -, R, O, O, F, I, N, G, -, M, S, -, W, I, N, D, S, T, O, R, M, -, C, E, R, T, I, F, I, E, D` / `Greater Bond region` | computed at scaffold from plan + brand | |

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
