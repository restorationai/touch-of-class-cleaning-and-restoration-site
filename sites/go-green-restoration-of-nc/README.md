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
| `go-green-restoration-of-nc` | client record `slug` | `narestco` |
| `Go Green Restoration of NC` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Go Green Restoration` | plan-input `brand.short_name` | `NARESTCO` |
| `Go Green Restoration of NC` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `gogreenrestorationofnc.com` | client record `domain` | `narestco.com` |
| `https://gogreenrestorationofnc.com` | derived | `https://narestco.com` |
| `(919) 906-5473` / `+19199065473` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `gogreenrestorationofnc@gmail.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Middlesex` / `NC` | derived from primary area | `Federal Way` / `WA` |
| `10805 w. NC Hwy 97` / `27557` | brand.street_address / brand.postal_code | |
| `35.7888369` / `-78.2039124` | brand.lat / brand.lng | from GBP |
| `ChIJhWCvh9tJrIkRkCEs58UBIRw` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `[]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Middlesex, NC.` | brand.tagline | short marketing line |
| `#15803d` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `GG` | derived; logo lives on the per-client R2 bucket | |
| `https://images.gogreenrestorationofnc.com` | `https://images.{domain}` | |
| `- [Air Duct Cleaning](https://gogreenrestorationofnc.com/services/air-duct-cleaning/)
- [Biohazard Cleanup](https://gogreenrestorationofnc.com/services/biohazard-cleanup/)
- [Carpet Cleaning](https://gogreenrestorationofnc.com/services/carpet-cleaning/)
- [Crawl Space Encapsulation](https://gogreenrestorationofnc.com/services/crawl-space-encapsulation/)
- [Fire Damage Restoration](https://gogreenrestorationofnc.com/services/fire-damage-restoration/)
- [Insulation Removal & Installation](https://gogreenrestorationofnc.com/services/insulation-removal-installation/)
- [Mold Remediation](https://gogreenrestorationofnc.com/services/mold-remediation/)
- [Odor Removal and Deodorization](https://gogreenrestorationofnc.com/services/odor-removal/)
- [Water Damage Restoration](https://gogreenrestorationofnc.com/services/water-damage-restoration/)` / `- [Middlesex, NC](https://gogreenrestorationofnc.com/service-areas/middlesex-nc/)
- [Raleigh, NC](https://gogreenrestorationofnc.com/service-areas/raleigh-nc/)
- [Durham, NC](https://gogreenrestorationofnc.com/service-areas/durham-nc/)
- [Rocky Mount, NC](https://gogreenrestorationofnc.com/service-areas/rocky-mount-nc/)
- [Wilson, NC](https://gogreenrestorationofnc.com/service-areas/wilson-nc/)
- [Smithfield, NC](https://gogreenrestorationofnc.com/service-areas/smithfield-nc/)
- [Wake Forest, NC](https://gogreenrestorationofnc.com/service-areas/wake-forest-nc/)
- [Zebulon, NC](https://gogreenrestorationofnc.com/service-areas/zebulon-nc/)
- [Wendell, NC](https://gogreenrestorationofnc.com/service-areas/wendell-nc/)
- [Archer Lodge, NC](https://gogreenrestorationofnc.com/service-areas/archer-lodge-nc/)
- [Lake Royale, NC](https://gogreenrestorationofnc.com/service-areas/lake-royale-nc/)
- [Spring Hope, NC](https://gogreenrestorationofnc.com/service-areas/spring-hope-nc/)
- [Kenly, NC](https://gogreenrestorationofnc.com/service-areas/kenly-nc/)
- [Clayton, NC](https://gogreenrestorationofnc.com/service-areas/clayton-nc/)
- [Knightdale, NC](https://gogreenrestorationofnc.com/service-areas/knightdale-nc/)
- [Wilson's Mills, NC](https://gogreenrestorationofnc.com/service-areas/wilson-s-mills-nc/)
- [Rolesville, NC](https://gogreenrestorationofnc.com/service-areas/rolesville-nc/)
- [Selma, NC](https://gogreenrestorationofnc.com/service-areas/selma-nc/)
- [Nashville, NC](https://gogreenrestorationofnc.com/service-areas/nashville-nc/)
- [Elm City, NC](https://gogreenrestorationofnc.com/service-areas/elm-city-nc/)
- [Pine Level, NC](https://gogreenrestorationofnc.com/service-areas/pine-level-nc/)
- [Louisburg, NC](https://gogreenrestorationofnc.com/service-areas/louisburg-nc/)
- [Youngsville, NC](https://gogreenrestorationofnc.com/service-areas/youngsville-nc/)` / `Available on request` / `Greater Middlesex region` | computed at scaffold from plan + brand | |

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
