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
| `homelyft.net` | client record `domain` | `narestco.com` |
| `https://homelyft.net` | derived | `https://narestco.com` |
| `+12282845200` / `+112282845200` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `info@homelyft.net` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2022` | brand.founded_year | `2004` |
| `Gulfport` / `MS` | derived from primary area | `Federal Way` / `WA` |
| `1311 SPRING Street` / `39507` | brand.street_address / brand.postal_code | |
| `30.3886736` / `-89.0586991` | brand.lat / brand.lng | from GBP |
| `ChIJ5dJT_FQWnIgRzm4i4D1BgR4` / `2198109827142676174` | brand.place_id / brand.google_cid | from GBP |
| `["RO 2728"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "IICRC ASD (STRUCTURAL DRYING)", "EPA LEAD-SAFE CERTIFIED", "IICRC FSRT (FIRE & SMOKE)", "IICRC AMRT (MOLD)", "OSHA TRAINED", "FORTIFIED-BUILDING-ROOFING-MS-WINDSTORM-CERTIFIED"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Gulfport, MS.` | brand.tagline | short marketing line |
| `#e33e2e` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `HR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.homelyft.net` | `https://images.{domain}` | |
| `- [Asbestos Abatement](https://homelyft.net/services/asbestos-abatement/)
- [Biohazard Cleanup](https://homelyft.net/services/biohazard-cleanup/)
- [Carpet Cleaning](https://homelyft.net/services/carpet-cleaning/)
- [Contents Restoration and Storage](https://homelyft.net/services/contents-restoration/)
- [Contents Restoration & Storage](https://homelyft.net/services/contents-restoration-storage/)
- [Crawl Space Encapsulation](https://homelyft.net/services/crawl-space-encapsulation/)
- [Emergency Board-Up and Tarping](https://homelyft.net/services/emergency-board-up-tarping/)
- [Fire Damage Restoration](https://homelyft.net/services/fire-damage-restoration/)
- [Renovations, Remodels and General Contracting](https://homelyft.net/services/general-contracting/)
- [Mold Remediation](https://homelyft.net/services/mold-remediation/)
- [Odor Removal and Deodorization](https://homelyft.net/services/odor-removal/)
- [Post-Construction and Specialty Cleaning](https://homelyft.net/services/post-construction-cleaning/)
- [Roofing Installation and Replacement](https://homelyft.net/services/roofing/)
- [Sewage Cleanup and Sanitization](https://homelyft.net/services/sewage-cleanup/)
- [Storm Damage Restoration](https://homelyft.net/services/storm-damage-restoration/)
- [Vandalism Cleanup](https://homelyft.net/services/vandalism-cleanup/)
- [Water Damage Restoration](https://homelyft.net/services/water-damage-restoration/)
- [Water Leak Detection](https://homelyft.net/services/water-leak-detection/)` / `- [Eastabuchie, MS](https://homelyft.net/service-areas/eastabuchie-ms/)
- [Hattiesburg, MS](https://homelyft.net/service-areas/hattiesburg-ms/)
- [Petal, MS](https://homelyft.net/service-areas/petal-ms/)
- [Rawls Springs, MS](https://homelyft.net/service-areas/rawls-springs-ms/)
- [Leakesville, MS](https://homelyft.net/service-areas/leakesville-ms/)
- [McLain, MS](https://homelyft.net/service-areas/mclain-ms/)
- [State Line, MS](https://homelyft.net/service-areas/state-line-ms/)
- [Biloxi, MS](https://homelyft.net/service-areas/biloxi-ms/)
- [D'Iberville, MS](https://homelyft.net/service-areas/d-iberville-ms/)
- [DeLisle, MS](https://homelyft.net/service-areas/delisle-ms/)
- [Diamondhead, MS](https://homelyft.net/service-areas/diamondhead-ms/)
- [Gulfport, MS](https://homelyft.net/service-areas/gulfport-ms/)
- [Henderson Point, MS](https://homelyft.net/service-areas/henderson-point-ms/)
- [Latimer, MS](https://homelyft.net/service-areas/latimer-ms/)
- [Long Beach, MS](https://homelyft.net/service-areas/long-beach-ms/)
- [Lyman, MS](https://homelyft.net/service-areas/lyman-ms/)
- [Pass Christian, MS](https://homelyft.net/service-areas/pass-christian-ms/)
- [Saucier, MS](https://homelyft.net/service-areas/saucier-ms/)
- [St. Martin, MS](https://homelyft.net/service-areas/st-martin-ms/)
- [Bay St. Louis, MS](https://homelyft.net/service-areas/bay-st-louis-ms/)
- [Kiln, MS](https://homelyft.net/service-areas/kiln-ms/)
- [Pearlington, MS](https://homelyft.net/service-areas/pearlington-ms/)
- [Picayune, MS](https://homelyft.net/service-areas/picayune-ms/)
- [Waveland, MS](https://homelyft.net/service-areas/waveland-ms/)
- [Wiggins, MS](https://homelyft.net/service-areas/wiggins-ms/)
- [Hide-A-Way Lake, MS](https://homelyft.net/service-areas/hide-a-way-lake-ms/)
- [Lumberton, MS](https://homelyft.net/service-areas/lumberton-ms/)
- [Poplarville, MS](https://homelyft.net/service-areas/poplarville-ms/)
- [Big Point, MS](https://homelyft.net/service-areas/big-point-ms/)
- [Escatawpa, MS](https://homelyft.net/service-areas/escatawpa-ms/)
- [Gautier, MS](https://homelyft.net/service-areas/gautier-ms/)
- [Gulf Hills, MS](https://homelyft.net/service-areas/gulf-hills-ms/)
- [Gulf Park Estates, MS](https://homelyft.net/service-areas/gulf-park-estates-ms/)
- [Helena, MS](https://homelyft.net/service-areas/helena-ms/)
- [Hurley, MS](https://homelyft.net/service-areas/hurley-ms/)
- [Moss Point, MS](https://homelyft.net/service-areas/moss-point-ms/)
- [Ocean Springs, MS](https://homelyft.net/service-areas/ocean-springs-ms/)
- [Pascagoula, MS](https://homelyft.net/service-areas/pascagoula-ms/)
- [Vancleave, MS](https://homelyft.net/service-areas/vancleave-ms/)
- [Wade, MS](https://homelyft.net/service-areas/wade-ms/)
- [Agricola, MS](https://homelyft.net/service-areas/agricola-ms/)
- [Benndale, MS](https://homelyft.net/service-areas/benndale-ms/)
- [Lucedale, MS](https://homelyft.net/service-areas/lucedale-ms/)
- [Ellisville, MS](https://homelyft.net/service-areas/ellisville-ms/)
- [Laurel, MS](https://homelyft.net/service-areas/laurel-ms/)
- [Moselle, MS](https://homelyft.net/service-areas/moselle-ms/)
- [Ovett, MS](https://homelyft.net/service-areas/ovett-ms/)
- [Sandersville, MS](https://homelyft.net/service-areas/sandersville-ms/)` / `IICRC CERTIFIED FIRM, IICRC WRT (WATER), IICRC ASD (STRUCTURAL DRYING), EPA LEAD-SAFE CERTIFIED, IICRC FSRT (FIRE & SMOKE), IICRC AMRT (MOLD), OSHA TRAINED, FORTIFIED-BUILDING-ROOFING-MS-WINDSTORM-CERTIFIED` / `Greater Eastabuchie region` | computed at scaffold from plan + brand | |

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
