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
| `prorestoration` | client record `slug` | `narestco` |
| `ProRestoration Services` | plan-input `brand.display_name` | `National Restoration Construction` |
| `ProRestoration` | plan-input `brand.short_name` | `NARESTCO` |
| `ProRestoration Services Inc.` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `prorestorationca.com` | client record `domain` | `narestco.com` |
| `https://prorestorationca.com` | derived | `https://narestco.com` |
| `(661) 393-9306` / `+16613939306` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Bakersfield` / `CA` | derived from primary area | `Federal Way` / `WA` |
| `3556 Bowman Ct Suite B` / `93308` | brand.street_address / brand.postal_code | |
| `` / `` | brand.lat / brand.lng | from GBP |
| `ChIJH_3NClVC6oAR3mxvd5xofrQ` / `13005947795120549086` | brand.place_id / brand.google_cid | from GBP |
| `["960566"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `Contractors State License Board (CSLB), State of California` / `` | brand.license_authority / brand.license_type | |
| `["IICRC Certified", "EPA Lead-Safe Certified Firm", "BBB Accredited"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `["https://www.google.com/maps?cid=13005947795120549086"]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Bakersfield, CA.` | brand.tagline | short marketing line |
| `#dc2626` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `https://images.prorestorationca.com/brand/logo.png` / `PS` | derived; logo lives on the per-client R2 bucket | |
| `https://images.prorestorationca.com` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://prorestorationca.com/services/water-damage-restoration/)
- [Flood Damage Restoration](https://prorestorationca.com/services/flood-damage-restoration/)
- [Burst Pipe Cleanup and Repair](https://prorestorationca.com/services/burst-pipe-repair/)
- [Appliance Leak Cleanup](https://prorestorationca.com/services/appliance-leak-cleanup/)
- [Sewage Cleanup and Sanitization](https://prorestorationca.com/services/sewage-cleanup/)
- [Fire Damage Restoration](https://prorestorationca.com/services/fire-damage-restoration/)
- [Smoke Damage Restoration](https://prorestorationca.com/services/smoke-damage-restoration/)
- [Soot Removal](https://prorestorationca.com/services/soot-removal/)
- [Odor Removal and Deodorization](https://prorestorationca.com/services/odor-removal/)
- [Mold Remediation](https://prorestorationca.com/services/mold-remediation/)
- [Mold Inspection and Testing](https://prorestorationca.com/services/mold-inspection-testing/)
- [Storm Damage Restoration](https://prorestorationca.com/services/storm-damage-restoration/)
- [Carpet Cleaning](https://prorestorationca.com/services/carpet-cleaning/)
- [Reconstruction Services](https://prorestorationca.com/services/reconstruction/)
- [Home Remodeling](https://prorestorationca.com/services/home-remodeling/)
- [Renovations, Remodels and General Contracting](https://prorestorationca.com/services/general-contracting/)` / `- [Bakersfield, CA](https://prorestorationca.com/service-areas/bakersfield-ca/)
- [Oildale, CA](https://prorestorationca.com/service-areas/oildale-ca/)
- [Rosedale, CA](https://prorestorationca.com/service-areas/rosedale-ca/)
- [Delano, CA](https://prorestorationca.com/service-areas/delano-ca/)
- [Shafter, CA](https://prorestorationca.com/service-areas/shafter-ca/)
- [Wasco, CA](https://prorestorationca.com/service-areas/wasco-ca/)
- [Taft, CA](https://prorestorationca.com/service-areas/taft-ca/)
- [Tehachapi, CA](https://prorestorationca.com/service-areas/tehachapi-ca/)
- [Arvin, CA](https://prorestorationca.com/service-areas/arvin-ca/)
- [Lamont, CA](https://prorestorationca.com/service-areas/lamont-ca/)
- [Lake Isabella, CA](https://prorestorationca.com/service-areas/lake-isabella-ca/)` / `IICRC Certified, EPA Lead-Safe Certified Firm, BBB Accredited` / `Greater Bakersfield region` | computed at scaffold from plan + brand | |

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
