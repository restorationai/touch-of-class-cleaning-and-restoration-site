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
| `tdi-builders` | client record `slug` | `narestco` |
| `TDI Builders, Inc.` | plan-input `brand.display_name` | `National Restoration Construction` |
| `TDI Builders, Inc.` | plan-input `brand.short_name` | `NARESTCO` |
| `TDI Builders, Inc.` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `tdiusa.com` | client record `domain` | `narestco.com` |
| `https://tdiusa.com` | derived | `https://narestco.com` |
| `(877) 688-0866` / `+18776880866` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `1985` | brand.founded_year | `2004` |
| `Sacramento` / `CA` | derived from primary area | `Federal Way` / `WA` |
| `701 Del Paso Rd` / `95834` | brand.street_address / brand.postal_code | |
| `38.6446` / `-121.5058` | brand.lat / brand.lng | from GBP |
| `` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["LICENSED & INSURED", "COMMERCIAL, INDUSTRIAL & RESIDENTIAL", "40+ YEARS OF CONSTRUCTION & REBUILDING EXPERIENCE"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `Construction and remodeling services in Sacramento, CA.` | brand.tagline | short marketing line |
| `#0080C4` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Jost` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `TB` | derived; logo lives on the per-client R2 bucket | |
| `https://images.tdiusa.com` | `https://images.{domain}` | |
| `- [Commercial Construction and Tenant Improvements](https://tdiusa.com/services/commercial-construction/)
- [Renovations, Remodels and General Contracting](https://tdiusa.com/services/general-contracting/)
- [New Home Construction](https://tdiusa.com/services/new-construction/)
- [Fire and Smoke Damage Rebuilding](https://tdiusa.com/services/fire-smoke-rebuilding/)
- [Water Damage Restoration](https://tdiusa.com/services/water-damage-restoration/)
- [Storm Damage Restoration](https://tdiusa.com/services/storm-damage-restoration/)
- [Mold Remediation](https://tdiusa.com/services/mold-remediation/)
- [Home Remodeling](https://tdiusa.com/services/home-remodeling/)
- [Kitchen Remodeling](https://tdiusa.com/services/kitchen-remodeling/)
- [Bathroom Remodeling](https://tdiusa.com/services/bathroom-remodeling/)
- [Garage Construction](https://tdiusa.com/services/garage-construction/)
- [Room Additions and Home Additions](https://tdiusa.com/services/room-addition/)` / `- [Sacramento, CA](https://tdiusa.com/service-areas/sacramento-ca/)
- [Roseville, CA](https://tdiusa.com/service-areas/roseville-ca/)
- [Elk Grove, CA](https://tdiusa.com/service-areas/elk-grove-ca/)
- [Folsom, CA](https://tdiusa.com/service-areas/folsom-ca/)
- [Modesto, CA](https://tdiusa.com/service-areas/modesto-ca/)
- [Rocklin, CA](https://tdiusa.com/service-areas/rocklin-ca/)
- [Citrus Heights, CA](https://tdiusa.com/service-areas/citrus-heights-ca/)
- [Rancho Cordova, CA](https://tdiusa.com/service-areas/rancho-cordova-ca/)
- [Fair Oaks, CA](https://tdiusa.com/service-areas/fair-oaks-ca/)
- [Carmichael, CA](https://tdiusa.com/service-areas/carmichael-ca/)
- [West Sacramento, CA](https://tdiusa.com/service-areas/west-sacramento-ca/)
- [Lincoln, CA](https://tdiusa.com/service-areas/lincoln-ca/)
- [Granite Bay, CA](https://tdiusa.com/service-areas/granite-bay-ca/)
- [El Dorado Hills, CA](https://tdiusa.com/service-areas/el-dorado-hills-ca/)
- [Loomis, CA](https://tdiusa.com/service-areas/loomis-ca/)` / `LICENSED & INSURED, COMMERCIAL, INDUSTRIAL & RESIDENTIAL, 40+ YEARS OF CONSTRUCTION & REBUILDING EXPERIENCE` / `Greater Sacramento region` | computed at scaffold from plan + brand | |

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
