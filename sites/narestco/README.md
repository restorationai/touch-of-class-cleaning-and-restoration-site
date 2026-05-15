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
| `narestco` | client record `slug` | `narestco` |
| `National Restoration Construction` | plan-input `brand.display_name` | `National Restoration Construction` |
| `NARESTCO` | plan-input `brand.short_name` | `NARESTCO` |
| `National Restoration Construction LLC` | plan-input `brand.legal_name` | `National Restoration Construction LLC` |
| `narestco.com` | client record `domain` | `narestco.com` |
| `https://narestco.com` | derived | `https://narestco.com` |
| `(206) 883-0333` / `+12068830333` | brand.phone | `(206) 883-0333` / `+12068830333` |
| `info@narestco.com` | brand.email | `info@narestco.com` |
| `24/7` | brand.hours | `24/7` |
| `2004` | brand.founded_year | `2004` |
| `Federal Way` / `WA` | derived from primary area | `Federal Way` / `WA` |
| `1530 S Dash Point Rd` / `98003` | brand.street_address / brand.postal_code | |
| `47.337` / `-122.314` | brand.lat / brand.lng | from GBP |
| `ChIJ8URpSkf_UaURDg_hVb9wMrQ` / `12984564642744438542` | brand.place_id / brand.google_cid | from GBP |
| `["NATIORC792M6"]` | brand.license_numbers (JSON-encoded array) | `["NATIORC792M6"]` |
| `WA State Department of Labor & Industries` / `General Contractor Certificate of Registration` | brand.license_authority / brand.license_type | |
| `["IICRC Certified", "BBB Accredited", "Lead-Safe Certified Firm", "EPA Certified", "ANSI Certified"]` | brand.certifications (JSON-encoded array) | `["IICRC", "BBB Accredited"]` |
| `["https://www.google.com/maps?cid=12984564642744438542", "https://www.facebook.com/narestco", "https://www.instagram.com/narestco", "https://www.tiktok.com/@narestco", "https://twitter.com/narestco"]` | brand.same_as_urls (JSON-encoded array) | |
| `` / `` | from GBP | `5.0` / `31` |
| `24/7 restoration services in Federal Way, WA.` | brand.tagline | short marketing line |
| `#1e3a8a` etc. | brand.colors (set per client or default to restoration palette) | `#0b3a7a` |
| `Inter` / `Inter` | brand.fonts | `Inter` / `Inter` |
| `https://images.narestco.com/brand/logo.png` / `NR` | derived; logo lives on the per-client R2 bucket | |
| `https://images.narestco.com` | `https://images.{domain}` | |
| `- Water Damage Restoration: https://narestco.com/services/water-damage-restoration/
- Flood Damage Restoration: https://narestco.com/services/flood-damage-restoration/
- Burst Pipe Cleanup and Repair: https://narestco.com/services/burst-pipe-repair/
- Basement Flooding Cleanup: https://narestco.com/services/basement-flooding-cleanup/
- Appliance Leak Cleanup: https://narestco.com/services/appliance-leak-cleanup/
- Frozen Pipe Restoration: https://narestco.com/services/frozen-pipe-restoration/
- Roof Leak Cleanup and Repair: https://narestco.com/services/roof-leak-repair/
- Sewage Cleanup and Sanitization: https://narestco.com/services/sewage-cleanup/
- Fire Damage Restoration: https://narestco.com/services/fire-damage-restoration/
- Smoke Damage Restoration: https://narestco.com/services/smoke-damage-restoration/
- Soot Removal: https://narestco.com/services/soot-removal/
- Odor Removal and Deodorization: https://narestco.com/services/odor-removal/
- Mold Remediation: https://narestco.com/services/mold-remediation/
- Mold Inspection and Testing: https://narestco.com/services/mold-inspection-testing/
- Storm Damage Restoration: https://narestco.com/services/storm-damage-restoration/
- Biohazard and Trauma Cleanup: https://narestco.com/services/biohazard-cleanup/
- Reconstruction Services: https://narestco.com/services/reconstruction/
- Renovations, Remodels and General Contracting: https://narestco.com/services/general-contracting/` / `- Federal Way, WA: https://narestco.com/service-areas/federal-way-wa/
- Seattle, WA: https://narestco.com/service-areas/seattle-wa/
- Bellevue, WA: https://narestco.com/service-areas/bellevue-wa/
- Tacoma, WA: https://narestco.com/service-areas/tacoma-wa/
- Everett, WA: https://narestco.com/service-areas/everett-wa/
- Kent, WA: https://narestco.com/service-areas/kent-wa/
- Renton, WA: https://narestco.com/service-areas/renton-wa/
- Auburn, WA: https://narestco.com/service-areas/auburn-wa/
- Kirkland, WA: https://narestco.com/service-areas/kirkland-wa/
- Redmond, WA: https://narestco.com/service-areas/redmond-wa/` / `IICRC Certified, BBB Accredited, Lead-Safe Certified Firm, EPA Certified, ANSI Certified` / `Greater Federal Way region` | computed at scaffold from plan + brand | |

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
