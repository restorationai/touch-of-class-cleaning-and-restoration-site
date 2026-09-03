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
| `arch-enviornmental-group-llc` | client record `slug` | `narestco` |
| `Arch Enviornmental Group LLC` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Arch Enviornmental Group LLC` | plan-input `brand.short_name` | `NARESTCO` |
| `Arch Enviornmental Group LLC` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `archenviroservice.com` | client record `domain` | `narestco.com` |
| `https://archenviroservice.com` | derived | `https://narestco.com` |
| `(559) 296-2088` / `+15592962088` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `info@archenviroservice.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2026` | brand.founded_year | `2004` |
| `Kingsburg` / `CA` | derived from primary area | `Federal Way` / `WA` |
| `2453 16th Ave` / `93631` | brand.street_address / brand.postal_code | |
| `36.5138398` / `-119.5538929` | brand.lat / brand.lng | from GBP |
| `ChIJw9aO0Idq82sRNFXGkfL6roA` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["CERTIFIED ASBESTOS CONSULTANT - LEAD INSPECTOR ASSESSOR - NIOSH 582 MICROSCOPIST"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Kingsburg, CA.` | brand.tagline | short marketing line |
| `#dc2626` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `AE` | derived; logo lives on the per-client R2 bucket | |
| `https://images.archenviroservice.com` | `https://images.{domain}` | |
| `- [Mold Inspection and Testing](https://archenviroservice.com/services/mold-inspection-testing/)` / `- [Kingsburg, CA](https://archenviroservice.com/service-areas/kingsburg-ca/)
- [Fresno, CA](https://archenviroservice.com/service-areas/fresno-ca/)
- [Visalia, CA](https://archenviroservice.com/service-areas/visalia-ca/)
- [Clovis, CA](https://archenviroservice.com/service-areas/clovis-ca/)
- [Selma, CA](https://archenviroservice.com/service-areas/selma-ca/)
- [Reedley, CA](https://archenviroservice.com/service-areas/reedley-ca/)
- [Dinuba, CA](https://archenviroservice.com/service-areas/dinuba-ca/)
- [Sanger, CA](https://archenviroservice.com/service-areas/sanger-ca/)
- [Fowler, CA](https://archenviroservice.com/service-areas/fowler-ca/)` / `CERTIFIED ASBESTOS CONSULTANT - LEAD INSPECTOR ASSESSOR - NIOSH 582 MICROSCOPIST` / `Greater Kingsburg region` | computed at scaffold from plan + brand | |

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
