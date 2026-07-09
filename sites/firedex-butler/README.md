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
| `firedex-butler` | client record `slug` | `narestco` |
| `FireDEX Butler` | plan-input `brand.display_name` | `National Restoration Construction` |
| `FireDEX` | plan-input `brand.short_name` | `NARESTCO` |
| `FireDEX Butler, Inc.` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `firedex.net` | client record `domain` | `narestco.com` |
| `https://firedex.net` | derived | `https://narestco.com` |
| `(724) 452-7400` / `+17244527400` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `mail@firedex.net` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `1981` | brand.founded_year | `2004` |
| `Cranberry Township` / `PA` | derived from primary area | `Federal Way` / `WA` |
| `9133 Marshall Rd` / `16066` | brand.street_address / brand.postal_code | |
| `` / `` | brand.lat / brand.lng | from GBP |
| `ChIJ4zqdqGF9NIgR0zyEf6VVd80` / `14805396469301132499` | brand.place_id / brand.google_cid | from GBP |
| `["PA001913"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `Pennsylvania Attorney General — Home Improvement Contractor Registration` / `` | brand.license_authority / brand.license_type | |
| `[]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `["https://www.google.com/maps?cid=14805396469301132499"]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `Water • Fire • Storm Restoration — 24/7 emergency response across Cranberry Township, Butler County and the Pittsburgh North suburbs since 1981.` | brand.tagline | short marketing line |
| `#c8102e` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `` / `FB` | derived; logo lives on the per-client R2 bucket | |
| `https://images.firedex.net` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://firedex.net/services/water-damage-restoration/)
- [Flood Damage Restoration](https://firedex.net/services/flood-damage-restoration/)
- [Basement Flooding Cleanup](https://firedex.net/services/basement-flooding-cleanup/)
- [Sewage Cleanup and Sanitization](https://firedex.net/services/sewage-cleanup/)
- [Burst Pipe Cleanup and Repair](https://firedex.net/services/burst-pipe-repair/)
- [Frozen Pipe Restoration](https://firedex.net/services/frozen-pipe-restoration/)
- [Storm Damage Restoration](https://firedex.net/services/storm-damage-restoration/)
- [Fire Damage Restoration](https://firedex.net/services/fire-damage-restoration/)
- [Smoke Damage Restoration](https://firedex.net/services/smoke-damage-restoration/)
- [Soot Removal](https://firedex.net/services/soot-removal/)
- [Odor Removal and Deodorization](https://firedex.net/services/odor-removal/)
- [Mold Remediation](https://firedex.net/services/mold-remediation/)
- [Mold Inspection and Testing](https://firedex.net/services/mold-inspection-testing/)
- [Biohazard and Trauma Cleanup](https://firedex.net/services/biohazard-cleanup/)
- [Commercial Restoration](https://firedex.net/services/commercial-restoration/)
- [Reconstruction Services](https://firedex.net/services/reconstruction/)
- [Renovations, Remodels and General Contracting](https://firedex.net/services/general-contracting/)` / `- [Cranberry Township, PA](https://firedex.net/service-areas/cranberry-township-pa/)
- [Wexford, PA](https://firedex.net/service-areas/wexford-pa/)
- [Mars, PA](https://firedex.net/service-areas/mars-pa/)
- [Zelienople, PA](https://firedex.net/service-areas/zelienople-pa/)
- [Evans City, PA](https://firedex.net/service-areas/evans-city-pa/)
- [Seven Fields, PA](https://firedex.net/service-areas/seven-fields-pa/)
- [Butler, PA](https://firedex.net/service-areas/butler-pa/)
- [Gibsonia, PA](https://firedex.net/service-areas/gibsonia-pa/)
- [Beaver Falls, PA](https://firedex.net/service-areas/beaver-falls-pa/)` / `Available on request` / `Greater Cranberry Township region` | computed at scaffold from plan + brand | |

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
