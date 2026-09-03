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
| `drycor-restore` | client record `slug` | `narestco` |
| `DRYCOR RESTORE` | plan-input `brand.display_name` | `National Restoration Construction` |
| `DRYCOR RESTORE` | plan-input `brand.short_name` | `NARESTCO` |
| `DRYCOR RESTORE` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `drycor.com` | client record `domain` | `narestco.com` |
| `https://drycor.com` | derived | `https://narestco.com` |
| `(813) 829-1091` / `+18138291091` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `team@drycor.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2005` | brand.founded_year | `2004` |
| `Thonotosasa` / `FL` | derived from primary area | `Federal Way` / `WA` |
| `10798 Florence Ave` / `33592` | brand.street_address / brand.postal_code | |
| `28.0655281` / `-82.294789` | brand.lat / brand.lng | from GBP |
| `ChIJ--4aNxtJuIURz7eqWifJBM4` / `14845211442582042575` | brand.place_id / brand.google_cid | from GBP |
| `["CBC1253966"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "EPA LEAD-SAFE CERTIFIED", "OSHA TRAINED", "NAERMC-(MOLD)"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Thonotosasa, FL.` | brand.tagline | short marketing line |
| `#dc2626` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `DR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.drycor.com` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://drycor.com/services/water-damage-restoration/)
- [Fire Damage Restoration](https://drycor.com/services/fire-damage-restoration/)
- [Mold Remediation](https://drycor.com/services/mold-remediation/)
- [Contents Restoration & Storage](https://drycor.com/services/contents-restoration-storage/)
- [Renovations, Remodels and General Contracting](https://drycor.com/services/general-contracting/)
- [Storm Damage Restoration](https://drycor.com/services/storm-damage-restoration/)
- [Water Cleanup](https://drycor.com/services/water-cleanup/)
- [Sewage Cleanup and Sanitization](https://drycor.com/services/sewage-cleanup/)
- [Emergency Board-Up and Tarping](https://drycor.com/services/emergency-board-up-tarping/)` / `- [Thonotosasa, FL](https://drycor.com/service-areas/thonotosasa-fl/)
- [Tampa, FL](https://drycor.com/service-areas/tampa-fl/)
- [Brandon, FL](https://drycor.com/service-areas/brandon-fl/)
- [Plant City, FL](https://drycor.com/service-areas/plant-city-fl/)
- [Temple Terrace, FL](https://drycor.com/service-areas/temple-terrace-fl/)
- [Lakeland, FL](https://drycor.com/service-areas/lakeland-fl/)
- [Seffner, FL](https://drycor.com/service-areas/seffner-fl/)
- [Zephyrhills, FL](https://drycor.com/service-areas/zephyrhills-fl/)
- [Dover, FL](https://drycor.com/service-areas/dover-fl/)` / `IICRC CERTIFIED FIRM, IICRC WRT (WATER), EPA LEAD-SAFE CERTIFIED, OSHA TRAINED, NAERMC-(MOLD)` / `Greater Thonotosasa region` | computed at scaffold from plan + brand | |

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
