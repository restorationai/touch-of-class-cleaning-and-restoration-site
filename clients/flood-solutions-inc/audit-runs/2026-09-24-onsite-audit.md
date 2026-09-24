# Onsite Audit - Flood Solutions inc - 2026-09-24

**Live origin audited:** https://staging.rankai-flood-solutions-inc.pages.dev (staging)
**Site verdict:** amber (up from red)
**URLs audited:** 6
**Prior audit:** 2026-09-21 (red)
**Form factor:** desktop only (Lighthouse 13.4.0, cpuSlowdownMultiplier 1, throughputKbps 10240). Mobile scores would typically run 10-20 performance points lower. These are NOT mobile-first numbers.

## Read this first: SEO score is inconclusive, not bad

The staging Pages preview still returns `x-robots-tag: noindex` (checked with `curl -sI` on 2026-09-24).
Cloudflare adds this header to every `*.pages.dev` preview. It fails the Lighthouse `is-crawlable` audit and
holds the SEO category at 69 on all 6 URLs. Following Step 4, the SEO score is recorded as-is but
left out of every verdict. Don't try to "fix SEO" based on this report. SEO status is inconclusive: cut over the
apex domain, then re-audit.

## What changed since 9/21

All three blocking defects from the last audit are fixed on the live preview:

- Canonical, `og:url` and `sitemap-index.xml` now point to `https://floodsolutionsinc.com/`. The `.invalid` placeholder host is gone.
- The logo is now the local `/images/logo.png` (returns 200), so the header logo and JSON-LD `logo` resolve.
- `/images/hero-bg.webp`, `/images/services.webp` and `/images/team.webp` all return 200. The console errors are gone and Best Practices is now 100 on every page.

The site is amber because of structured-data warnings and one colour-contrast problem across the site templates. Performance scores are not the cause.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.7 | +0.4 |
| Accessibility | 95.3 | -0.7 |
| Best Practices | 100.0 | +4.0 |
| SEO | 69.0 (inconclusive) | 0.0 |

Pages by verdict: green: 0, amber: 6, red: 0, error: 0

Verdict basis: performance, accessibility, best practices. SEO excluded (staging noindex artifact).

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 99 | 96 | 100 | 69* | 0.9s | 0.017 | 0ms |
| `/services/` | services-hub | amber | 100 | 95 | 100 | 69* | 0.8s | 0.017 | 0ms |
| `/services/water-damage-restoration/` | service-landing | amber | 100 | 95 | 100 | 69* | 0.8s | 0.029 | 0ms |
| `/services/water-cleanup/` | service-landing | amber | 100 | 95 | 100 | 69* | 0.8s | 0.014 | 0ms |
| `/service-areas/sterling-heights-mi/` | service-area | amber | 99 | 95 | 100 | 69* | 0.8s | 0.014 | 0ms |
| `/contact/` | contact | amber | 100 | 96 | 100 | 69* | 0.7s | 0.036 | 0ms |

\* SEO inconclusive, staging noindex artifact.

Core Web Vitals pass Google's "good" thresholds on every page (LCP under 2.5s, CLS under 0.1, TBT 0ms).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 6 | medium | Footer phone/email links, breadcrumb links, and `btn-accent` label (see actions 3 and 4) |
| `rankai:geo_coordinates_empty` | 6 | medium | Populate `lat` / `lng` in `src/lib/brand.ts:47-48` (see action 1) |
| `has_micromarkup_errors` | 5 | medium | Structured-data validation errors on every page except the homepage (see action 2) |
| `image-delivery-insight` | 6 | low | Serve the 92KB, 511x193 `logo.png` as a resized WebP (displayed at 254x96). Up to 225KB savings on `/contact/` |
| `lcp-discovery-insight` | 5 | low | Add `fetchpriority="high"` to the hero `<img>` on interior page templates (the homepage already has it) |
| `render-blocking-insight` | 6 | low | No action: one 8.8KB CSS file, about 50-60ms |
| `network-dependency-tree-insight` | 6 | low | No action: no preconnect candidates, no LCP saving |

## Money page alerts

All five money pages are amber, and all for the same template-level reasons. None of them has a page-specific problem. Their Lighthouse scores are 95 to 100.

- **`/`** (home): amber. Empty `geo` in LocalBusiness JSON-LD, and footer links fail contrast (4.16:1).
- **`/services/`** (services-hub): amber. `has_micromarkup_errors`, empty `geo`, breadcrumb and footer contrast.
- **`/services/water-damage-restoration/`** (service-landing, priority 9.0): amber. Same as `/services/`, plus the hero "Call" button (`btn-accent`) is at 2.3:1 contrast.
- **`/services/water-cleanup/`** (service-landing): amber. Same as water-damage-restoration.
- **`/contact/`** (contact): amber. `has_micromarkup_errors`, empty `geo`, breadcrumb and footer contrast. CLS went up to 0.036 (still "good").

## Regressions vs prior audit

**Verdict transitions:** all 6 URLs went red to amber. These are improvements, not regressions.

**Metric regressions (triggered the threshold, low real-world impact):**
- LCP increased by 284-336ms on `/services/` (527 to 811ms), `/services/water-damage-restoration/` (502 to 812ms) and `/service-areas/sterling-heights-mi/` (496 to 832ms). The likely cause is expected: on 9/21 the hero images returned 404, so the LCP element was text. Now the real hero image loads and becomes the LCP element. All three pages are still below 0.9s. Action 5 (`fetchpriority`) recovers part of the increase.
- CLS on `/contact/` went from 0.004 to 0.036. This is still under the 0.1 "good" limit. Check that the hero image and form embed have fixed dimensions reserved.

**New issues this month:**
- `/`: `color-contrast`. New footer links (`text-primary`, `#e63a41` on white, 4.16:1). The homepage was at 100 accessibility on 9/21.
- All 6 pages: `rankai:geo_coordinates_empty`. The 9/21 audit missed this, but the defect was already there.
- 5 pages (all except `/`): `has_micromarkup_errors`. The 9/21 run did not record its validation settings, so this may be new detection rather than a site change.
- All 6 pages: `image-delivery-insight`. The images now actually load, so Lighthouse can grade them. 5 interior pages: `lcp-discovery-insight`, for the same reason.

**Issues resolved since last audit** (keep doing this):
- All 6 pages: `rankai:canonical_host_unresolvable`, `rankai:og_url_host_unresolvable`, `rankai:brand_logo_unresolvable`, `rankai:broken_image_assets`, `errors-in-console`
- Site-level: `rankai:sitemap_host_unresolvable`
- `/`: `rankai:word_count_below_target` (now 1533 words against a 1200 target)
- `/service-areas/sterling-heights-mi/`: `cache-insight`

## Recommended next actions (priority order)

1. **(template, money pages, schema)** Fill in `lat` and `lng` in `sites/flood-solutions-inc/src/lib/brand.ts:47-48`
   using the Ira, MI office (10153 Marine City Highway, 48023). The GBP place ID
   `ChIJF_GiDO_gJIgR1VZPHRihQr4` is already in the same file, so take the coordinates from that listing.
   `src/lib/schema.ts:69-73` currently outputs `"latitude": "", "longitude": ""` on every page. Google treats empty
   GeoCoordinates as invalid LocalBusiness markup. If the coordinates can't be sourced, drop the
   `geo` block instead of shipping empty strings.

2. **(template, money pages, schema)** Fix what triggers `has_micromarkup_errors` on the 5 interior
   pages. The homepage does not trigger it. What those 5 pages share and the homepage lacks is `BreadcrumbList` and
   `FAQPage` JSON-LD. Check these two first:
   (a) the last breadcrumb `ListItem` has no `item` URL (`src/lib/schema.ts:220`), and on service pages its
   `name` is the raw slug (`water-cleanup`) instead of the display name;
   (b) the `Service` node on service pages also has `name` and `serviceType` set to the slug
   (`"water-cleanup"`), which means `service_display` in that content entry holds a slug.
   Run one service page through Google's Rich Results Test to confirm which node is failing, then fix
   it in `schema.ts` and not per page.

3. **(template, accessibility)** Darken the footer phone and email links in `src/components/Footer.astro:26-27,66`
   from `text-primary` (`#e63a41`, 4.16:1) to `text-primary-700` (`#9a1419`). The tailwind config
   reserves the 600/700 range for brand text on white. This footer change was new this week and cost
   the homepage 4 accessibility points. In the same pass, change the breadcrumb links in
   `src/components/Breadcrumb.astro:8,14` from `text-dark/50` (3.39:1) to `text-dark/70` or darker.

4. **(template, accessibility, money pages)** Fix the `btn-accent` label colour in
   `src/styles/global.css:57-58`. It uses `text-white` on `#2fb9dd` (2.3:1), but the tailwind config says
   `btn-accent` must use `text-accent-fg` (`#0f172a`). Replace `text-white` with `text-accent-fg`. This is
   the hero "Call" button on every service and service-area page, so it is a conversion element.

5. **(template, low)** Add `fetchpriority="high"` to the hero `<img>` in the interior page templates
   (services hub, service, service-area, contact). The homepage hero already has it. Also replace
   the 92KB 511x193 `public/images/logo.png` with a WebP sized for its 254x96 display (about 2x for retina).
   These are small gains that bring back some of the LCP increase listed above.

## Notes / caveats

- **Apex not cut over.** The client record has no `apex_cutover.completed_at`, so the staging preview was
  audited. SEO results stay inconclusive until an apex audit is run.
- **Client status.** `clients/flood-solutions-inc.json` has `status: "onboarding"`, not `"active"`.
  The audit went ahead because `build_status: "pushed_main"` means the build is live. The status was left unchanged.
- **Tooling substitution.** The `on_page_lighthouse` and `on_page_instant_pages` MCP wrappers were not
  available, so the DataForSEO REST endpoints were called directly with `for_mobile: false`. This matches the
  9/21 baseline. 12 calls, about $0.043.
- **Service-area page.** The url-plan has no `primary: true` service area and no Macomb page, so
  `/service-areas/sterling-heights-mi/` was used again to keep the comparison consistent. The missing Macomb page is still
  an open question, since Macomb is the primary marketing city.
- **Brand name mismatch in copy.** The FAQ answer text on `/services/water-cleanup/` says "Flood Solutions Inc", but the
  schema and headings use "Flood & Fire Solutions". This is content, not technical health. It is flagged here for System 4 and NAP review.
- **Clean elsewhere.** No broken internal or external links, no mixed content, exactly one H1 per page, titles
  44-59 chars, meta descriptions 95-156 chars, canonicals self-referencing to the apex. `/services/` is 721 words
  against an 800 target (low priority, content work). The `frame` check on the service-area page is the embedded map and was
  not counted as an issue.
- `is-crawlable` is left out of the per-URL issue lists because it only fails due to the staging noindex header.
