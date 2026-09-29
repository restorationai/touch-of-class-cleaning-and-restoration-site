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
| `dry1-out-restoration-and-construction` | client record `slug` | `narestco` |
| `Dry1 Out Restoration and Construction` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Dry1` | plan-input `brand.short_name` | `NARESTCO` |
| `Dry1 Out Restoration and Construction` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `dry1out.com` | client record `domain` | `narestco.com` |
| `https://dry1out.com` | derived | `https://narestco.com` |
| `(760) 576-1987` / `+17605761987` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `Jason@dry1out.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2026` | brand.founded_year | `2004` |
| `Vista` / `CA` | derived from primary area | `Federal Way` / `WA` |
| `1235 activity dr ` / `82081` | brand.street_address / brand.postal_code | |
| `` / `` | brand.lat / brand.lng | from GBP |
| `ChIJh3y1Q-iumqsRn1E-rGgHmcU` / `` | brand.place_id / brand.google_cid | from GBP |
| `["#993442"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC Certified Firm", "IICRC WRT (Water)", "IICRC ASD (Structural Drying)", "IICRC AMRT (Mold)", "IICRC FSRT (Fire & Smoke)"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Vista, CA.` | brand.tagline | short marketing line |
| `#171717` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `DO` | derived; logo lives on the per-client R2 bucket | |
| `https://images.dry1out.com` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://dry1out.com/services/water-damage-restoration/)
- [Emergency Water Cleanup](https://dry1out.com/services/water-cleanup/)
- [Fire Damage Restoration](https://dry1out.com/services/fire-damage-restoration/)
- [Mold Remediation](https://dry1out.com/services/mold-remediation/)
- [Mold Inspection and Testing](https://dry1out.com/services/mold-inspection-testing/)
- [Renovations, Remodels and General Contracting](https://dry1out.com/services/general-contracting/)
- [Crime Scene Cleanup](https://dry1out.com/services/crime-scene-cleanup/)
- [Storm Damage Restoration](https://dry1out.com/services/storm-damage-restoration/)
- [Biohazard Cleanup](https://dry1out.com/services/biohazard-cleanup/)
- [Sewage Cleanup and Sanitization](https://dry1out.com/services/sewage-cleanup/)` / `- [Vista, CA](https://dry1out.com/service-areas/vista-ca/)
- [San Diego, CA](https://dry1out.com/service-areas/san-diego-ca/)
- [San Jose, CA](https://dry1out.com/service-areas/san-jose-ca/)
- [San Francisco, CA](https://dry1out.com/service-areas/san-francisco-ca/)
- [Oakland, CA](https://dry1out.com/service-areas/oakland-ca/)
- [Chula Vista, CA](https://dry1out.com/service-areas/chula-vista-ca/)
- [Fremont, CA](https://dry1out.com/service-areas/fremont-ca/)
- [Oceanside, CA](https://dry1out.com/service-areas/oceanside-ca/)
- [Escondido, CA](https://dry1out.com/service-areas/escondido-ca/)
- [Carlsbad, CA](https://dry1out.com/service-areas/carlsbad-ca/)
- [San Marcos, CA](https://dry1out.com/service-areas/san-marcos-ca/)
- [Temecula, CA](https://dry1out.com/service-areas/temecula-ca/)
- [Hayward, CA](https://dry1out.com/service-areas/hayward-ca/)
- [Sunnyvale, CA](https://dry1out.com/service-areas/sunnyvale-ca/)
- [Santa Clara, CA](https://dry1out.com/service-areas/santa-clara-ca/)
- [El Cajon, CA](https://dry1out.com/service-areas/el-cajon-ca/)
- [Concord, CA](https://dry1out.com/service-areas/concord-ca/)
- [Berkeley, CA](https://dry1out.com/service-areas/berkeley-ca/)
- [Encinitas, CA](https://dry1out.com/service-areas/encinitas-ca/)
- [Santa Cruz, CA](https://dry1out.com/service-areas/santa-cruz-ca/)` / `IICRC Certified Firm, IICRC WRT (Water), IICRC ASD (Structural Drying), IICRC AMRT (Mold), IICRC FSRT (Fire & Smoke)` / `Greater Vista region` | computed at scaffold from plan + brand | |

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
