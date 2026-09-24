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
| `dry-bros-water-fire-restoration` | client record `slug` | `narestco` |
| `Dry Bros Water & Fire Restoration` | plan-input `brand.display_name` | `National Restoration Construction` |
| `Dry Bros Water & Fire Restoration` | plan-input `brand.short_name` | `NARESTCO` |
| `Dry Bros Water & Fire Restoration` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `drybros.com` | client record `domain` | `narestco.com` |
| `https://drybros.com` | derived | `https://narestco.com` |
| `(877) 379-2767` / `+18773792767` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `amin.mashouf@gmail.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `` | brand.founded_year | `2004` |
| `Chicago` / `IL` | derived from primary area | `Federal Way` / `WA` |
| `3918 W 63rd ST` / `60629` | brand.street_address / brand.postal_code | |
| `41.8755616` / `-87.6244212` | brand.lat / brand.lng | from GBP |
| `` / `` | brand.place_id / brand.google_cid | from GBP |
| `[]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `` / `` | brand.license_authority / brand.license_type | |
| `[]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `[]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Chicago, IL.` | brand.tagline | short marketing line |
| `#0172EC` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Archivo` | brand.fonts | `Inter` / `Inter` |
| `/images/logo.png` / `DB` | derived; logo lives on the per-client R2 bucket | |
| `https://images.drybros.com` | `https://images.{domain}` | |
| `- [Water Damage Restoration](https://drybros.com/services/water-damage-restoration/)
- [Fire Damage Restoration](https://drybros.com/services/fire-damage-restoration/)
- [Mold Remediation](https://drybros.com/services/mold-remediation/)
- [Emergency Water Cleanup](https://drybros.com/services/water-cleanup/)
- [Flood Damage Restoration](https://drybros.com/services/flood-damage-restoration/)
- [Burst Pipe Cleanup and Repair](https://drybros.com/services/burst-pipe-repair/)
- [Basement Flooding Cleanup](https://drybros.com/services/basement-flooding-cleanup/)
- [Sewage Cleanup and Sanitization](https://drybros.com/services/sewage-cleanup/)
- [Smoke Damage Restoration](https://drybros.com/services/smoke-damage-restoration/)
- [Odor Removal and Deodorization](https://drybros.com/services/odor-removal/)
- [Storm Damage Restoration](https://drybros.com/services/storm-damage-restoration/)
- [Emergency Board-Up and Tarping](https://drybros.com/services/emergency-board-up-tarping/)
- [Contents Restoration and Storage](https://drybros.com/services/contents-restoration/)` / `- [Chicago, IL](https://drybros.com/service-areas/chicago-il/)
- [Naperville, IL](https://drybros.com/service-areas/naperville-il/)
- [Cicero, IL](https://drybros.com/service-areas/cicero-il/)
- [Evanston, IL](https://drybros.com/service-areas/evanston-il/)
- [Oak Park, IL](https://drybros.com/service-areas/oak-park-il/)
- [Skokie, IL](https://drybros.com/service-areas/skokie-il/)
- [Berwyn, IL](https://drybros.com/service-areas/berwyn-il/)
- [Des Plaines, IL](https://drybros.com/service-areas/des-plaines-il/)
- [Stickney, IL](https://drybros.com/service-areas/stickney-il/)
- [Bedford Park, IL](https://drybros.com/service-areas/bedford-park-il/)
- [Lincolnwood, IL](https://drybros.com/service-areas/lincolnwood-il/)
- [River Forest, IL](https://drybros.com/service-areas/river-forest-il/)
- [Forest Park, IL](https://drybros.com/service-areas/forest-park-il/)
- [Lyons, IL](https://drybros.com/service-areas/lyons-il/)
- [Riverside, IL](https://drybros.com/service-areas/riverside-il/)
- [Elmwood Park, IL](https://drybros.com/service-areas/elmwood-park-il/)
- [North Riverside, IL](https://drybros.com/service-areas/north-riverside-il/)
- [Melrose Park, IL](https://drybros.com/service-areas/melrose-park-il/)
- [Burbank, IL](https://drybros.com/service-areas/burbank-il/)
- [Evergreen Park, IL](https://drybros.com/service-areas/evergreen-park-il/)
- [Brookfield, IL](https://drybros.com/service-areas/brookfield-il/)
- [Maywood, IL](https://drybros.com/service-areas/maywood-il/)` / `Available on request` / `Greater Chicago region` | computed at scaffold from plan + brand | |

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
