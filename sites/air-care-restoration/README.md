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
| `air-care-restoration` | client record `slug` | `narestco` |
| `Air Care Restoration` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Air Care Restoration` | plan-input `brand.short_name` | `NARESTCO` |
| `Air Care Restoration` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `aircarerestoration.com` | client record `domain` | `narestco.com` |
| `https://aircarerestoration.com` | derived | `https://narestco.com` |
| `(325) 339-8723` / `+13253398723` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `info@aircarerestoration.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2026` | brand.founded_year | `2004` |
| `Abilene` / `TX` | derived from primary area | `Federal Way` / `WA` |
| `2241 S 41ST ST SUITE A` / `79602` | brand.street_address / brand.postal_code | |
| `32.44645` / `-99.7475905` | brand.lat / brand.lng | from GBP |
| `ChIJAbX4Kjsyg2IRF9RgElzgJXk` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC CERTIFIED FIRM", "OSHA TRAINED", "IICRC WRT (WATER)", "IICRC FSRT (FIRE & SMOKE)", "EPA LEAD-SAFE CERTIFIED", "MRC2262-RCO1798-TCST-HST-OCT"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Abilene, TX.` | brand.tagline | short marketing line |
| `#02255d` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Poppins` / `Anton` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `AC` | derived; logo lives on the per-client R2 bucket | |
| `https://images.aircarerestoration.com` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://aircarerestoration.com/services/water-damage-restoration/)
- [Water Cleanup](https://aircarerestoration.com/services/water-cleanup/)
- [Storm Damage Restoration](https://aircarerestoration.com/services/storm-damage-restoration/)
- [Air Duct Cleaning](https://aircarerestoration.com/services/air-duct-cleaning/)
- [Fire Damage Restoration](https://aircarerestoration.com/services/fire-damage-restoration/)
- [Renovations, Remodels and General Contracting](https://aircarerestoration.com/services/general-contracting/)
- [Sewage Cleanup and Sanitization](https://aircarerestoration.com/services/sewage-cleanup/)
- [Biohazard Cleanup](https://aircarerestoration.com/services/biohazard-cleanup/)
- [Contents Restoration and Storage](https://aircarerestoration.com/services/contents-restoration/)
- [Post-Construction and Specialty Cleaning](https://aircarerestoration.com/services/post-construction-cleaning/)
- [Emergency Board-Up and Tarping](https://aircarerestoration.com/services/emergency-board-up-tarping/)
- [Asbestos Abatement](https://aircarerestoration.com/services/asbestos-abatement/)
- [Mold Remediation](https://aircarerestoration.com/services/mold-remediation/)` / `- [Abilene, TX](https://aircarerestoration.com/service-areas/abilene-tx/)
- [Sweetwater, TX](https://aircarerestoration.com/service-areas/sweetwater-tx/)
- [Clyde, TX](https://aircarerestoration.com/service-areas/clyde-tx/)
- [Merkel, TX](https://aircarerestoration.com/service-areas/merkel-tx/)
- [Anson, TX](https://aircarerestoration.com/service-areas/anson-tx/)
- [Tuscola, TX](https://aircarerestoration.com/service-areas/tuscola-tx/)
- [Tye, TX](https://aircarerestoration.com/service-areas/tye-tx/)
- [Buffalo Gap, TX](https://aircarerestoration.com/service-areas/buffalo-gap-tx/)
- [Brownwood, TX](https://aircarerestoration.com/service-areas/brownwood-tx/)
- [Early, TX](https://aircarerestoration.com/service-areas/early-tx/)
- [Roby, TX](https://aircarerestoration.com/service-areas/roby-tx/)
- [Rotan, TX](https://aircarerestoration.com/service-areas/rotan-tx/)
- [Robert Lee, TX](https://aircarerestoration.com/service-areas/robert-lee-tx/)
- [Bronte, TX](https://aircarerestoration.com/service-areas/bronte-tx/)
- [Eden, TX](https://aircarerestoration.com/service-areas/eden-tx/)
- [Paint Rock, TX](https://aircarerestoration.com/service-areas/paint-rock-tx/)` / `IICRC CERTIFIED FIRM, OSHA TRAINED, IICRC WRT (WATER), IICRC FSRT (FIRE & SMOKE), EPA LEAD-SAFE CERTIFIED, MRC2262-RCO1798-TCST-HST-OCT` / `Greater Abilene region` | computed at scaffold from plan + brand | |

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
