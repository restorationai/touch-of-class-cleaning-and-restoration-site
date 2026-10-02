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
| `restopros-of-central-maryland` | client record `slug` | `narestco` |
| `RestoPros of Central Maryland` | plan-input `brand.display_name` | `National Restoration Construction` |
| `RestoPros of Central Maryland` | plan-input `brand.short_name` | `NARESTCO` |
| `RestoPros of Central Maryland` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `restopros-of-central-maryland.invalid` | client record `domain` | `narestco.com` |
| `https://restopros-of-central-maryland.invalid` | derived | `https://narestco.com` |
| `(240) 261-1639` / `+12402611639` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `drestum@restopros.co` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Baldwin` / `MD` | derived from primary area | `Federal Way` / `WA` |
| `2710 Hunting Ridge Ct` / `21013` | brand.street_address / brand.postal_code | |
| `39.4945894` / `-76.4701866` | brand.lat / brand.lng | from GBP |
| `ChIJ64mT9f9M2oMRGaajJtP-T4A` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC WRT (WATER)"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Baldwin, MD.` | brand.tagline | short marketing line |
| `#171717` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `RO` | derived; logo lives on the per-client R2 bucket | |
| `https://images.restopros-of-central-maryland.invalid` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://restopros-of-central-maryland.invalid/services/water-damage-restoration/)
- [Fire Damage Restoration](https://restopros-of-central-maryland.invalid/services/fire-damage-restoration/)
- [Mold Remediation](https://restopros-of-central-maryland.invalid/services/mold-remediation/)
- [Sewage Cleanup and Sanitization](https://restopros-of-central-maryland.invalid/services/sewage-cleanup/)
- [Contents Restoration & Storage](https://restopros-of-central-maryland.invalid/services/contents-restoration-storage/)
- [Emergency Water Cleanup](https://restopros-of-central-maryland.invalid/services/water-cleanup/)
- [Storm Damage Restoration](https://restopros-of-central-maryland.invalid/services/storm-damage-restoration/)` / `- [Baldwin, MD](https://restopros-of-central-maryland.invalid/service-areas/baldwin-md/)
- [Columbia, MD](https://restopros-of-central-maryland.invalid/service-areas/columbia-md/)
- [Silver Spring, MD](https://restopros-of-central-maryland.invalid/service-areas/silver-spring-md/)
- [Rockville, MD](https://restopros-of-central-maryland.invalid/service-areas/rockville-md/)
- [Bethesda, MD](https://restopros-of-central-maryland.invalid/service-areas/bethesda-md/)
- [Gaithersburg, MD](https://restopros-of-central-maryland.invalid/service-areas/gaithersburg-md/)
- [Germantown, MD](https://restopros-of-central-maryland.invalid/service-areas/germantown-md/)
- [Ellicott City, MD](https://restopros-of-central-maryland.invalid/service-areas/ellicott-city-md/)
- [Glen Burnie, MD](https://restopros-of-central-maryland.invalid/service-areas/glen-burnie-md/)
- [Dundalk, MD](https://restopros-of-central-maryland.invalid/service-areas/dundalk-md/)
- [Bowie, MD](https://restopros-of-central-maryland.invalid/service-areas/bowie-md/)
- [Towson, MD](https://restopros-of-central-maryland.invalid/service-areas/towson-md/)
- [Annapolis, MD](https://restopros-of-central-maryland.invalid/service-areas/annapolis-md/)
- [Catonsville, MD](https://restopros-of-central-maryland.invalid/service-areas/catonsville-md/)
- [Wheaton, MD](https://restopros-of-central-maryland.invalid/service-areas/wheaton-md/)
- [Aspen Hill, MD](https://restopros-of-central-maryland.invalid/service-areas/aspen-hill-md/)
- [Essex, MD](https://restopros-of-central-maryland.invalid/service-areas/essex-md/)
- [Potomac, MD](https://restopros-of-central-maryland.invalid/service-areas/potomac-md/)
- [Severn, MD](https://restopros-of-central-maryland.invalid/service-areas/severn-md/)
- [Owings Mills, MD](https://restopros-of-central-maryland.invalid/service-areas/owings-mills-md/)` / `IICRC WRT (WATER)` / `Greater Baldwin region` | computed at scaffold from plan + brand | |

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
