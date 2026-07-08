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
| `all-pro-plumbing` | client record `slug` | `narestco` |
| `All Pro Plumbing Heating and Air` | plan-input `brand.display_name` | `National Restoration Construction` |
| `All Pro` | plan-input `brand.short_name` | `NARESTCO` |
| `All Pro Plumbing Heating and Air` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `allproplumbingheatingandair.com` | client record `domain` | `narestco.com` |
| `https://allproplumbingheatingandair.com` | derived | `https://narestco.com` |
| `(661) 863-9242` / `+16618639242` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `info@allproplumbingheatingandair.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Bakersfield` / `CA` | derived from primary area | `Federal Way` / `WA` |
| `` / `` | brand.street_address / brand.postal_code | |
| `` / `` | brand.lat / brand.lng | from GBP |
| `` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `[]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 plumbing, heating and air service in Bakersfield, CA.` | brand.tagline | short marketing line |
| `#dc2626` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `https://images.allproplumbingheatingandair.com/brand/logo.png` / `AP` | derived; logo lives on the per-client R2 bucket | |
| `https://images.allproplumbingheatingandair.com` | `https://images.{domain}` | |
| `- [Emergency Plumbing](https://allproplumbingheatingandair.com/services/emergency-plumbing/)
- [Burst and Leaking Pipe Repair](https://allproplumbingheatingandair.com/services/burst-pipe-repair/)
- [Drain Cleaning](https://allproplumbingheatingandair.com/services/drain-cleaning/)
- [Sewer Line Repair and Replacement](https://allproplumbingheatingandair.com/services/sewer-line-repair/)
- [Water Heater Repair](https://allproplumbingheatingandair.com/services/water-heater-repair/)
- [Water Heater Installation and Replacement](https://allproplumbingheatingandair.com/services/water-heater-installation/)
- [Leak Detection](https://allproplumbingheatingandair.com/services/leak-detection/)
- [Slab Leak Repair](https://allproplumbingheatingandair.com/services/slab-leak-repair/)
- [Whole-House Repiping](https://allproplumbingheatingandair.com/services/repiping/)
- [Gas Line Installation and Leak Repair](https://allproplumbingheatingandair.com/services/gas-line-services/)
- [Sump Pump Installation and Repair](https://allproplumbingheatingandair.com/services/sump-pumps/)
- [Water Softeners and Filtration Systems](https://allproplumbingheatingandair.com/services/water-softeners-filtration/)
- [Toilet, Faucet and Fixture Services](https://allproplumbingheatingandair.com/services/toilet-faucet-repair/)
- [Garbage Disposal Repair and Installation](https://allproplumbingheatingandair.com/services/garbage-disposal/)
- [Furnace Repair](https://allproplumbingheatingandair.com/services/furnace-repair/)
- [Furnace Installation and Replacement](https://allproplumbingheatingandair.com/services/furnace-installation/)
- [Heat Pump Installation and Repair](https://allproplumbingheatingandair.com/services/heat-pump-services/)
- [Air Conditioning Repair](https://allproplumbingheatingandair.com/services/ac-repair/)
- [AC Installation and Replacement](https://allproplumbingheatingandair.com/services/ac-installation/)
- [Ductless Mini-Split Systems](https://allproplumbingheatingandair.com/services/ductless-mini-splits/)
- [Ductwork Repair and Installation](https://allproplumbingheatingandair.com/services/ductwork/)
- [Indoor Air Quality Services](https://allproplumbingheatingandair.com/services/indoor-air-quality/)` / `- [Bakersfield, CA](https://allproplumbingheatingandair.com/service-areas/bakersfield-ca/)
- [Oildale, CA](https://allproplumbingheatingandair.com/service-areas/oildale-ca/)
- [Rosedale, CA](https://allproplumbingheatingandair.com/service-areas/rosedale-ca/)
- [Shafter, CA](https://allproplumbingheatingandair.com/service-areas/shafter-ca/)
- [Delano, CA](https://allproplumbingheatingandair.com/service-areas/delano-ca/)
- [Taft, CA](https://allproplumbingheatingandair.com/service-areas/taft-ca/)
- [Tehachapi, CA](https://allproplumbingheatingandair.com/service-areas/tehachapi-ca/)` / `Available on request` / `Greater Bakersfield region` | computed at scaffold from plan + brand | |

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
