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
| `diss-restoration` | client record `slug` | `narestco` |
| `DISS Restoration` | plan-input `brand.display_name` | `National Restoration Construction` |
| `DISS Restoration` | plan-input `brand.short_name` | `NARESTCO` |
| `DISS Restoration` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `dissrestoration.com` | client record `domain` | `narestco.com` |
| `https://dissrestoration.com` | derived | `https://narestco.com` |
| `(724) 981-1441` / `+17249811441` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `info@dissrestoration.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2021` | brand.founded_year | `2004` |
| `Youngstown` / `OH` | derived from primary area | `Federal Way` / `WA` |
| `712 Spearman Avenue` / `16121` | brand.street_address / brand.postal_code | |
| `41.1035786` / `-80.6520161` | brand.lat / brand.lng | from GBP |
| `ChIJHWRJjvrBM4gRsKk68P7eLjc` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "IICRC FSRT (FIRE & SMOKE)", "IICRC AMRT (MOLD)", "EPA LEAD-SAFE CERTIFIED", "OSHA TRAINED", "IICRC ASD (STRUCTURAL DRYING)"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Youngstown, OH.` | brand.tagline | short marketing line |
| `#123f85` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `DR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.dissrestoration.com` | `https://images.{domain}` | |
| `- [Air Duct Cleaning](https://dissrestoration.com/services/air-duct-cleaning/)
- [Asbestos Abatement](https://dissrestoration.com/services/asbestos-abatement/)
- [Biohazard Cleanup](https://dissrestoration.com/services/biohazard-cleanup/)
- [Carpet Cleaning](https://dissrestoration.com/services/carpet-cleaning/)
- [Contents Restoration and Storage](https://dissrestoration.com/services/contents-restoration/)
- [Contents Restoration & Storage](https://dissrestoration.com/services/contents-restoration-storage/)
- [Emergency Board-Up and Tarping](https://dissrestoration.com/services/emergency-board-up-tarping/)
- [Fire Damage Restoration](https://dissrestoration.com/services/fire-damage-restoration/)
- [Renovations, Remodels and General Contracting](https://dissrestoration.com/services/general-contracting/)
- [Mold Remediation](https://dissrestoration.com/services/mold-remediation/)
- [Odor Removal and Deodorization](https://dissrestoration.com/services/odor-removal/)
- [Post-Construction and Specialty Cleaning](https://dissrestoration.com/services/post-construction-cleaning/)
- [Sewage Cleanup and Sanitization](https://dissrestoration.com/services/sewage-cleanup/)
- [Storm Damage Restoration](https://dissrestoration.com/services/storm-damage-restoration/)
- [Emergency Water Cleanup](https://dissrestoration.com/services/water-cleanup/)
- [Water Damage Restoration](https://dissrestoration.com/services/water-damage-restoration/)` / `- [Youngstown, OH](https://dissrestoration.com/service-areas/youngstown-oh/)
- [Warren, OH](https://dissrestoration.com/service-areas/warren-oh/)
- [Boardman, OH](https://dissrestoration.com/service-areas/boardman-oh/)
- [Austintown, OH](https://dissrestoration.com/service-areas/austintown-oh/)
- [Niles, OH](https://dissrestoration.com/service-areas/niles-oh/)
- [Girard, OH](https://dissrestoration.com/service-areas/girard-oh/)
- [Struthers, OH](https://dissrestoration.com/service-areas/struthers-oh/)
- [Canfield, OH](https://dissrestoration.com/service-areas/canfield-oh/)
- [Hubbard, OH](https://dissrestoration.com/service-areas/hubbard-oh/)
- [Campbell, OH](https://dissrestoration.com/service-areas/campbell-oh/)
- [Mineral Ridge, OH](https://dissrestoration.com/service-areas/mineral-ridge-oh/)
- [Farrell, PA](https://dissrestoration.com/service-areas/farrell-pa/)
- [Sharon, PA](https://dissrestoration.com/service-areas/sharon-pa/)
- [Hermitage, PA](https://dissrestoration.com/service-areas/hermitage-pa/)
- [Sharpsville, PA](https://dissrestoration.com/service-areas/sharpsville-pa/)
- [Wheatland, PA](https://dissrestoration.com/service-areas/wheatland-pa/)
- [West Middlesex, PA](https://dissrestoration.com/service-areas/west-middlesex-pa/)
- [Greenville, PA](https://dissrestoration.com/service-areas/greenville-pa/)
- [Grove City, PA](https://dissrestoration.com/service-areas/grove-city-pa/)
- [Mercer, PA](https://dissrestoration.com/service-areas/mercer-pa/)
- [New Castle, PA](https://dissrestoration.com/service-areas/new-castle-pa/)` / `IICRC CERTIFIED FIRM, IICRC WRT (WATER), IICRC FSRT (FIRE & SMOKE), IICRC AMRT (MOLD), EPA LEAD-SAFE CERTIFIED, OSHA TRAINED, IICRC ASD (STRUCTURAL DRYING)` / `Greater Youngstown region` | computed at scaffold from plan + brand | |

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
