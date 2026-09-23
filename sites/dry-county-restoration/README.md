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
| `dry-county-restoration` | client record `slug` | `narestco` |
| `Dry County Restoration` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Dry County Restoration` | plan-input `brand.short_name` | `NARESTCO` |
| `Dry County Restoration` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `drycountyrestoration.com` | client record `domain` | `narestco.com` |
| `https://drycountyrestoration.com` | derived | `https://narestco.com` |
| `(951) 667-9910` / `+19516679910` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `info@drycountyrestoration.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2020` | brand.founded_year | `2004` |
| `Corona` / `CA` | derived from primary area | `Federal Way` / `WA` |
| `9064 Pulsar Ct. Suit I ` / `92883` | brand.street_address / brand.postal_code | |
| `33.8752945` / `-117.566444` | brand.lat / brand.lng | from GBP |
| `ChIJBQyutfy53IARKDqQsaEwmyQ` / `` | brand.place_id / brand.google_cid | from GBP |
| `["1083555"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `["IICRC CERTIFIED FIRM", "IICRC WRT (WATER)", "IICRC ASD (STRUCTURAL DRYING)", "IICRC AMRT (MOLD)", "OSHA TRAINED"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Corona, CA.` | brand.tagline | short marketing line |
| `#007fb2` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `DC` | derived; logo lives on the per-client R2 bucket | |
| `https://images.drycountyrestoration.com` | `https://images.{domain}` | |
| `- [Air Duct Cleaning](https://drycountyrestoration.com/services/air-duct-cleaning/)
- [Carpet Cleaning](https://drycountyrestoration.com/services/carpet-cleaning/)
- [Contents Restoration and Storage](https://drycountyrestoration.com/services/contents-restoration/)
- [Contents Restoration & Storage](https://drycountyrestoration.com/services/contents-restoration-storage/)
- [Emergency Board-Up and Tarping](https://drycountyrestoration.com/services/emergency-board-up-tarping/)
- [Emergency Plumbing](https://drycountyrestoration.com/services/emergency-plumbing/)
- [Fire Damage Restoration](https://drycountyrestoration.com/services/fire-damage-restoration/)
- [Renovations, Remodels and General Contracting](https://drycountyrestoration.com/services/general-contracting/)
- [Mold Remediation](https://drycountyrestoration.com/services/mold-remediation/)
- [Odor Removal and Deodorization](https://drycountyrestoration.com/services/odor-removal/)
- [Post-Construction and Specialty Cleaning](https://drycountyrestoration.com/services/post-construction-cleaning/)
- [Roofing Installation and Replacement](https://drycountyrestoration.com/services/roofing/)
- [Sewage Cleanup and Sanitization](https://drycountyrestoration.com/services/sewage-cleanup/)
- [Storm Damage Restoration](https://drycountyrestoration.com/services/storm-damage-restoration/)
- [Water Damage Restoration](https://drycountyrestoration.com/services/water-damage-restoration/)
- [Water Leak Detection](https://drycountyrestoration.com/services/water-leak-detection/)` / `- [Corona, CA](https://drycountyrestoration.com/service-areas/corona-ca/)
- [Riverside, CA](https://drycountyrestoration.com/service-areas/riverside-ca/)
- [Anaheim, CA](https://drycountyrestoration.com/service-areas/anaheim-ca/)
- [Santa Ana, CA](https://drycountyrestoration.com/service-areas/santa-ana-ca/)
- [Ontario, CA](https://drycountyrestoration.com/service-areas/ontario-ca/)
- [Fullerton, CA](https://drycountyrestoration.com/service-areas/fullerton-ca/)
- [Norco, CA](https://drycountyrestoration.com/service-areas/norco-ca/)
- [Chino, CA](https://drycountyrestoration.com/service-areas/chino-ca/)
- [Chino Hills, CA](https://drycountyrestoration.com/service-areas/chino-hills-ca/)
- [Eastvale, CA](https://drycountyrestoration.com/service-areas/eastvale-ca/)
- [Silverado, CA](https://drycountyrestoration.com/service-areas/silverado-ca/)
- [Jurupa Valley, CA](https://drycountyrestoration.com/service-areas/jurupa-valley-ca/)
- [Temescal Valley, CA](https://drycountyrestoration.com/service-areas/temescal-valley-ca/)
- [Yorba Linda, CA](https://drycountyrestoration.com/service-areas/yorba-linda-ca/)
- [Lake Mathews, CA](https://drycountyrestoration.com/service-areas/lake-mathews-ca/)
- [Woodcrest, CA](https://drycountyrestoration.com/service-areas/woodcrest-ca/)
- [Trabuco Canyon, CA](https://drycountyrestoration.com/service-areas/trabuco-canyon-ca/)
- [North Tustin, CA](https://drycountyrestoration.com/service-areas/north-tustin-ca/)
- [Montclair, CA](https://drycountyrestoration.com/service-areas/montclair-ca/)
- [Villa Park, CA](https://drycountyrestoration.com/service-areas/villa-park-ca/)
- [Fontana, CA](https://drycountyrestoration.com/service-areas/fontana-ca/)
- [Pomona, CA](https://drycountyrestoration.com/service-areas/pomona-ca/)` / `IICRC CERTIFIED FIRM, IICRC WRT (WATER), IICRC ASD (STRUCTURAL DRYING), IICRC AMRT (MOLD), OSHA TRAINED` / `Greater Corona region` | computed at scaffold from plan + brand | |

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
