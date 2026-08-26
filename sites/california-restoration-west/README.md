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
| `california-restoration-west` | client record `slug` | `narestco` |
| `California Restoration West ` | plan-input `brand.display_name` | `National Restoration Construction` |
| `California Restoration West ` | plan-input `brand.short_name` | `NARESTCO` |
| `California Restoration West ` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `californiarestorationwest.com` | client record `domain` | `narestco.com` |
| `https://californiarestorationwest.com` | derived | `https://narestco.com` |
| `(805) 290-7292` / `+18052907292` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `Californiarestorationwest@gmail.com.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2025` | brand.founded_year | `2004` |
| `Ventura` / `CA` | derived from primary area | `Federal Way` / `WA` |
| `363 mackay ave ` / `93004` | brand.street_address / brand.postal_code | |
| `34.4458248` / `-119.0779359` | brand.lat / brand.lng | from GBP |
| `` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC WRT (WATER)", "IICRC AMRT (MOLD)", "IICRC ASD (STRUCTURAL DRYING)", "IICRC CERTIFIED FIRM", "OSHA TRAINED"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Ventura, CA.` | brand.tagline | short marketing line |
| `#dc2626` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `CR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.californiarestorationwest.com` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://californiarestorationwest.com/services/water-damage-restoration/)
- [Mold Remediation](https://californiarestorationwest.com/services/mold-remediation/)
- [Storm Damage Restoration](https://californiarestorationwest.com/services/storm-damage-restoration/)
- [Contents Restoration and Storage](https://californiarestorationwest.com/services/contents-restoration/)
- [Crawl Space Encapsulation](https://californiarestorationwest.com/services/crawl-space-encapsulation/)
- [Water Cleanup](https://californiarestorationwest.com/services/water-cleanup/)` / `- [Ventura, CA](https://californiarestorationwest.com/service-areas/ventura-ca/)
- [Oxnard, CA](https://californiarestorationwest.com/service-areas/oxnard-ca/)
- [Thousand Oaks, CA](https://californiarestorationwest.com/service-areas/thousand-oaks-ca/)
- [Simi Valley, CA](https://californiarestorationwest.com/service-areas/simi-valley-ca/)
- [Camarillo, CA](https://californiarestorationwest.com/service-areas/camarillo-ca/)
- [Santa Paula, CA](https://californiarestorationwest.com/service-areas/santa-paula-ca/)
- [Port Hueneme, CA](https://californiarestorationwest.com/service-areas/port-hueneme-ca/)
- [Ojai, CA](https://californiarestorationwest.com/service-areas/ojai-ca/)
- [Fillmore, CA](https://californiarestorationwest.com/service-areas/fillmore-ca/)` / `IICRC WRT (WATER), IICRC AMRT (MOLD), IICRC ASD (STRUCTURAL DRYING), IICRC CERTIFIED FIRM, OSHA TRAINED` / `Greater Ventura region` | computed at scaffold from plan + brand | |

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
