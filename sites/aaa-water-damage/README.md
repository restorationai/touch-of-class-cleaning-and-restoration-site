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
| `aaa-water-damage` | client record `slug` | `narestco` |
| `AAA Water Damage Restoration & Carpet Care` | plan-input `brand.display_name` | `National Restoration Construction` |
| `AAA Water Damage` | plan-input `brand.short_name` | `NARESTCO` |
| `AAA Flood Service LLC` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `aaawaterdamagehawaii.com` | client record `domain` | `narestco.com` |
| `https://aaawaterdamagehawaii.com` | derived | `https://narestco.com` |
| `(808) 349-3407` / `+18083493407` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Honolulu` / `HI` | derived from primary area | `Federal Way` / `WA` |
| `` / `96825` | brand.street_address / brand.postal_code | |
| `` / `` | brand.lat / brand.lng | from GBP |
| `ChIJD0yxLYptAHwRja-0yOuatzE` / `3582502366071795597` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `[]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `["https://www.google.com/maps?cid=3582502366071795597", "https://www.facebook.com/26flood"]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 water damage restoration & carpet care across Oahu.` | brand.tagline | short marketing line |
| `#0284c7` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `` / `AW` | derived; logo lives on the per-client R2 bucket | |
| `https://images.aaawaterdamagehawaii.com` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://aaawaterdamagehawaii.com/services/water-damage-restoration/)
- [Flood Damage Restoration](https://aaawaterdamagehawaii.com/services/flood-damage-restoration/)
- [Burst Pipe Cleanup and Repair](https://aaawaterdamagehawaii.com/services/burst-pipe-repair/)
- [Sewage Cleanup and Sanitization](https://aaawaterdamagehawaii.com/services/sewage-cleanup/)
- [Mold Remediation](https://aaawaterdamagehawaii.com/services/mold-remediation/)
- [Mold Inspection and Testing](https://aaawaterdamagehawaii.com/services/mold-inspection-testing/)
- [Carpet Cleaning](https://aaawaterdamagehawaii.com/services/carpet-cleaning/)
- [Upholstery Cleaning](https://aaawaterdamagehawaii.com/services/upholstery-cleaning/)
- [Flood & Drying Equipment Rental](https://aaawaterdamagehawaii.com/services/flood-equipment-rental/)
- [Commercial Restoration](https://aaawaterdamagehawaii.com/services/commercial-restoration/)` / `- [Honolulu, HI](https://aaawaterdamagehawaii.com/service-areas/honolulu-hi/)
- [Hawaii Kai, HI](https://aaawaterdamagehawaii.com/service-areas/hawaii-kai-hi/)
- [Kahala, HI](https://aaawaterdamagehawaii.com/service-areas/kahala-hi/)
- [Aina Haina, HI](https://aaawaterdamagehawaii.com/service-areas/aina-haina-hi/)
- [Kaimuki, HI](https://aaawaterdamagehawaii.com/service-areas/kaimuki-hi/)
- [Diamond Head, HI](https://aaawaterdamagehawaii.com/service-areas/diamond-head-hi/)
- [Kailua, HI](https://aaawaterdamagehawaii.com/service-areas/kailua-hi/)
- [Kaneohe, HI](https://aaawaterdamagehawaii.com/service-areas/kaneohe-hi/)
- [Pearl City, HI](https://aaawaterdamagehawaii.com/service-areas/pearl-city-hi/)
- [Aiea, HI](https://aaawaterdamagehawaii.com/service-areas/aiea-hi/)
- [Ewa Beach, HI](https://aaawaterdamagehawaii.com/service-areas/ewa-beach-hi/)
- [Kapolei, HI](https://aaawaterdamagehawaii.com/service-areas/kapolei-hi/)
- [Mililani, HI](https://aaawaterdamagehawaii.com/service-areas/mililani-hi/)` / `Available on request` / `Greater Honolulu region` | computed at scaffold from plan + brand | |

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
