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
| `homepriderestorationandcleaning` | client record `slug` | `narestco` |
| `Home Pride Restoration and Cleaning` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Home Pride Restoration and Cleaning` | plan-input `brand.short_name` | `NARESTCO` |
| `Home Pride Restoration and Cleaning` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `homepriderestorationandcleaning.com` | client record `domain` | `narestco.com` |
| `https://homepriderestorationandcleaning.com` | derived | `https://narestco.com` |
| `(801) 995-2437` / `+18019952437` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `homepriderestorationut@gmail.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `1997` | brand.founded_year | `2004` |
| `Saratoga Springs` / `UT` | derived from primary area | `Federal Way` / `WA` |
| `78 W Wildflower Dr` / `84045` | brand.street_address / brand.postal_code | |
| `40.31172` / `-111.89406` | brand.lat / brand.lng | from GBP |
| `ChIJGzr1iePDLCsR1fkC5O33F10` / `6708102771096353237` | brand.place_id / brand.google_cid | from GBP |
| `["RC-25-0737"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC Certified"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Saratoga Springs, UT.` | brand.tagline | short marketing line |
| `#171717` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `HP` | derived; logo lives on the per-client R2 bucket | |
| `https://images.homepriderestorationandcleaning.com` | `https://images.{domain}` | |
| `- [Appliance Leak Cleanup](https://homepriderestorationandcleaning.com/services/appliance-leak-cleanup/)
- [Basement Flooding Cleanup](https://homepriderestorationandcleaning.com/services/basement-flooding-cleanup/)
- [Biohazard Cleanup](https://homepriderestorationandcleaning.com/services/biohazard-cleanup/)
- [Burst Pipe Cleanup and Repair](https://homepriderestorationandcleaning.com/services/burst-pipe-repair/)
- [Carpet Cleaning](https://homepriderestorationandcleaning.com/services/carpet-cleaning/)
- [Crawl Space Encapsulation](https://homepriderestorationandcleaning.com/services/crawl-space-encapsulation/)
- [Emergency Board-Up and Tarping](https://homepriderestorationandcleaning.com/services/emergency-board-up-tarping/)
- [Fabric Protection](https://homepriderestorationandcleaning.com/services/fabric-protection/)
- [Fire Damage Restoration](https://homepriderestorationandcleaning.com/services/fire-damage-restoration/)
- [Frozen Pipe Restoration](https://homepriderestorationandcleaning.com/services/frozen-pipe-restoration/)
- [Hoarding Cleanup](https://homepriderestorationandcleaning.com/services/hoarding-cleanup/)
- [Junk & Debris Removal](https://homepriderestorationandcleaning.com/services/junk-debris-removal/)
- [Mold Inspection and Testing](https://homepriderestorationandcleaning.com/services/mold-inspection-testing/)
- [Mold Remediation](https://homepriderestorationandcleaning.com/services/mold-remediation/)
- [Odor Removal and Deodorization](https://homepriderestorationandcleaning.com/services/odor-removal/)
- [Post-Construction and Specialty Cleaning](https://homepriderestorationandcleaning.com/services/post-construction-cleaning/)
- [Roof Leak Cleanup and Repair](https://homepriderestorationandcleaning.com/services/roof-leak-repair/)
- [Sewage Cleanup and Sanitization](https://homepriderestorationandcleaning.com/services/sewage-cleanup/)
- [Smoke Damage Restoration](https://homepriderestorationandcleaning.com/services/smoke-damage-restoration/)
- [Storm Damage Restoration](https://homepriderestorationandcleaning.com/services/storm-damage-restoration/)
- [Tile & Grout Cleaning](https://homepriderestorationandcleaning.com/services/tile-grout-cleaning/)
- [Upholstery Cleaning](https://homepriderestorationandcleaning.com/services/upholstery-cleaning/)
- [Water Damage Restoration](https://homepriderestorationandcleaning.com/services/water-damage-restoration/)
- [Water Leak Detection](https://homepriderestorationandcleaning.com/services/water-leak-detection/)` / `- [Saratoga Springs, UT](https://homepriderestorationandcleaning.com/service-areas/saratoga-springs-ut/)
- [Lehi, UT](https://homepriderestorationandcleaning.com/service-areas/lehi-ut/)
- [Eagle Mountain, UT](https://homepriderestorationandcleaning.com/service-areas/eagle-mountain-ut/)
- [American Fork, UT](https://homepriderestorationandcleaning.com/service-areas/american-fork-ut/)
- [Pleasant Grove, UT](https://homepriderestorationandcleaning.com/service-areas/pleasant-grove-ut/)
- [Orem, UT](https://homepriderestorationandcleaning.com/service-areas/orem-ut/)
- [Provo, UT](https://homepriderestorationandcleaning.com/service-areas/provo-ut/)
- [Herriman, UT](https://homepriderestorationandcleaning.com/service-areas/herriman-ut/)
- [South Jordan, UT](https://homepriderestorationandcleaning.com/service-areas/south-jordan-ut/)
- [Riverton, UT](https://homepriderestorationandcleaning.com/service-areas/riverton-ut/)
- [Heber City, UT](https://homepriderestorationandcleaning.com/service-areas/heber-city-ut/)
- [Park City, UT](https://homepriderestorationandcleaning.com/service-areas/park-city-ut/)
- [Vineyard, UT](https://homepriderestorationandcleaning.com/service-areas/vineyard-ut/)
- [Highland, UT](https://homepriderestorationandcleaning.com/service-areas/highland-ut/)
- [Lindon, UT](https://homepriderestorationandcleaning.com/service-areas/lindon-ut/)
- [Fairfield, UT](https://homepriderestorationandcleaning.com/service-areas/fairfield-ut/)
- [Cedar Hills, UT](https://homepriderestorationandcleaning.com/service-areas/cedar-hills-ut/)
- [Cedar Fort, UT](https://homepriderestorationandcleaning.com/service-areas/cedar-fort-ut/)
- [Bluffdale, UT](https://homepriderestorationandcleaning.com/service-areas/bluffdale-ut/)
- [Alpine, UT](https://homepriderestorationandcleaning.com/service-areas/alpine-ut/)
- [Draper, UT](https://homepriderestorationandcleaning.com/service-areas/draper-ut/)
- [Lake Shore, UT](https://homepriderestorationandcleaning.com/service-areas/lake-shore-ut/)
- [Benjamin, UT](https://homepriderestorationandcleaning.com/service-areas/benjamin-ut/)` / `IICRC Certified` / `Greater Saratoga Springs region` | computed at scaffold from plan + brand | |

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
