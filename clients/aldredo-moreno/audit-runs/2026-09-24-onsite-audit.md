# Onsite Audit - ACS Enterprise (aldredo-moreno) - 2026-09-24

**Live origin audited:** https://staging.rankai-aldredo-moreno.pages.dev (staging)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** first audit
**Form factor:** desktop only (Lighthouse 13.4.0, cpuSlowdownMultiplier=1, 10240 Kbps)

> **Staging caveat: SEO score is inconclusive.** Cloudflare Pages injects
> `x-robots-tag: noindex` on `*.pages.dev` previews (confirmed with `curl -sI`), which fails
> the Lighthouse `is-crawlable` audit and pins SEO at 69 on every page. SEO was recorded but
> excluded from the verdicts. Re-audit after apex cutover to `theacs-enterprises.com`.
>
> **The red verdict is NOT caused by the staging artifact.** It comes from a real build
> defect: every page ships with `https://aldredo-moreno.invalid` as its canonical host (see
> template issue 1). That would carry straight through to production if the site were cut
> over as-is.

First audit for this client - no comparison data.

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 99 | n/a |
| Accessibility | 96 | n/a |
| Best Practices | 100 | n/a |
| SEO | 69 (inconclusive, staging) | n/a |

Pages by verdict: green: 0, amber: 1, red: 5, error: 0

Lighthouse itself is close to perfect. Performance is 99 and Best Practices is 100 on all
six pages, LCP is under 1.0s everywhere, TBT is 0 and CLS is at most 0.024. Every red comes
from the on-page canonical defect.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | red | 99 | 100 | 100 | 69* | 0.82s | 0.002 |
| /services/ | services-hub | red | 99 | 95 | 100 | 69* | 0.94s | 0.002 |
| /services/water-damage-restoration/ | service-landing | red | 99 | 95 | 100 | 69* | 0.87s | 0.024 |
| /services/sewage-cleanup/ | service-landing | red | 99 | 95 | 100 | 69* | 0.94s | 0.024 |
| /service-areas/odessa-tx/ | service-area | amber | 99 | 95 | 100 | 69* | 0.98s | 0.003 |
| /contact/ | contact | red | 99 | 96 | 100 | 69* | 0.88s | 0.005 |

\* SEO excluded from the verdict (staging noindex artifact).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `canonical` | 6 | high | Every page's `<link rel="canonical">`, `og:url`, `og:image`, `twitter:image`, JSON-LD `url`/`@id`/BreadcrumbList `item`, `sitemap-index.xml` `<loc>` and the robots.txt `Sitemap:` line use `https://aldredo-moreno.invalid`. There are 8 to 12 references per page and zero references to `theacs-enterprises.com`. The client record got the real domain on 2026-09-18 (commit f8a364e1e), but the site's brand.ts / astro.config `site` tokens were never updated to match. Set the site URL to `https://theacs-enterprises.com` in the deploy repo, rebuild, redeploy, then confirm with `curl -s https://staging.rankai-aldredo-moreno.pages.dev/ \| grep -c aldredo-moreno.invalid` returning 0. |
| `image-delivery-insight` | 6 | medium | `/images/logo.png` is a 228 KB, 700x571 PNG displayed at roughly 96px tall. Lighthouse estimates 222 KB of waste per page. Re-export it as WebP/AVIF at 2x display size (about 200px tall, under 15 KB) and ship a `srcset`. The `/services/` hub also loads `services.webp` (173 KB of waste), and `hero-bg.webp` is oversized on `/contact/` (89 KB) and `/services/` (46 KB). |
| `color-contrast` | 5 | medium | The breadcrumb links use `text-dark/50` (12px on white), which fails the 4.5:1 ratio. Change them to `text-dark/70` or darker in the breadcrumb component. On `/service-areas/odessa-tx/`, a `text-slate-400` span also fails; use `text-slate-600`. |
| `has_micromarkup_errors` | 5 | medium | DataForSEO flags structured-data errors on every page except home. The only schema type those five pages share (and home lacks) is `BreadcrumbList`, whose last `ListItem` has no `item` URL, and whose other items point at the `.invalid` host. Fix the canonical host first, then run the pages through the Schema Markup Validator and give the final crumb an `item` if the error persists. |
| `lcp-discovery-insight` | 5 | low | The LCP hero `<img>` has `loading="eager"` but no `fetchpriority="high"` (`priorityHinted: false`). Add `fetchpriority="high"` to the hero image in the page-hero component. |
| `render-blocking-insight` | 6 | low | The single 9 KB `/_astro/_slug_.*.css` blocks render for up to about 58ms. Low priority. Astro's `build.inlineStylesheets: "auto"` would inline it. |
| `is-crawlable` | 6 | low | Staging artifact only (Pages `x-robots-tag: noindex`). No action. It clears at apex cutover. |

## Money page alerts

- **`/`** (home) - verdict: red. Canonical is `https://aldredo-moreno.invalid/`. Lighthouse perf 99, LCP 0.82s. The page is otherwise clean: A11y 100, no schema errors, 1,478 words.
- **`/services/`** (services-hub) - verdict: red. Wrong canonical, schema errors, a breadcrumb contrast failure, and 757 words against an 800 target. It has the heaviest image waste (logo plus the 173 KB `services.webp`).
- **`/services/water-damage-restoration/`** (service-landing, top priority 9.0) - verdict: red. Wrong canonical and schema errors. Perf 99, LCP 0.87s.
- **`/services/sewage-cleanup/`** (service-landing) - verdict: red. Wrong canonical and schema errors. Perf 99, LCP 0.94s.
- **`/contact/`** (contact) - verdict: red. Wrong canonical and schema errors. `hero-bg.webp` has 89 KB of waste on this page.

## Regressions vs prior audit

Not applicable. This is the first audit.

## Recommended next actions (priority order)

1. **(template, money pages, blocks cutover)** Replace the `aldredo-moreno.invalid` placeholder with `https://theacs-enterprises.com` in the deploy repo `restorationai/aldredo-moreno-site` (brand.ts canonical URL token and the astro.config `site`), then rebuild and redeploy. Verify that the canonical, og:url, JSON-LD and robots.txt `Sitemap:` all read the real domain. Do not cut over until this is done. Otherwise Google gets a canonical pointing at a host that cannot resolve on all 72 pages.
2. **(template)** Re-export `/images/logo.png` (228 KB, 700x571) as a small WebP/AVIF of about 200px height. That saves about 222 KB on every page view across the site.
3. **(template)** Darken the breadcrumb link color from `text-dark/50` to `text-dark/70` or darker. That clears `color-contrast` on 5 of 6 pages and lifts Accessibility from 95 to 100.
4. **(template)** After item 1 ships, re-validate the structured data. Add an `item` URL to the final BreadcrumbList crumb if DataForSEO still flags `has_micromarkup_errors`, and add `fetchpriority="high"` to the hero image.
5. **(cutover)** Cut over the apex domain and re-audit, so the deferred SEO category can be scored for real.

## Notes / caveats

- **Staging origin, SEO deferred.** No `apex_cutover.completed_at` on the client record, so the audit ran against the Pages preview. `is-crawlable` is the only failing SEO audit.
- **Desktop only.** The DataForSEO Lighthouse call ran `for_mobile=false`. Mobile performance typically runs 10 to 20 points lower, and mobile-only audits (tap targets, font size) are not covered.
- **Client record status.** `clients/aldredo-moreno.json` has `status: "onboarding"`, not `"active"`, which strictly fails the documented pre-flight gate. The audit proceeded because `build_status` is `pushed_main` and the staging preview serves the current build. This matches how other onboarding clients have been audited.
- **URL selection.** No `audit-urls.txt` exists, so the URLs were derived from `plan/url-plan.json`. The service landings are water damage restoration (priority 9.0), then sewage cleanup (8.1, tied with storm damage and water cleanup, tie broken by plan order). No service area has `primary: true`, and the business city (Midland) has no area page because it is folded into home, so the first area in plan order was used: Odessa.
- **NAP data worth checking (out of scope, flag for claims/NAP lint).** The LocalBusiness JSON-LD has `postalCode: "70705"`, which is a Louisiana ZIP. Midland, TX ZIPs are in the 797xx range. `streetAddress` is `"2318 Horizon Rd Midland"`, with the city duplicated into the street line. The business name also carries a trailing space (`display_name: "ACS Enterprise "`), which renders as a double space in the home title (`ACS Enterprise  | ...`), in the logo alt text and in the schema `name`.
- **Google Maps API key.** `/service-areas/odessa-tx/` loads the Maps JS API with the key in the query string. That is normal for a browser embed, but confirm the key is HTTP-referrer-restricted.
- **Deploy repo not inspected.** The CI token could not read `restorationai/aldredo-moreno-site`, so action item 1 identifies the fix location from the build pipeline (`scripts/build_site.py` token resolution plus the 2026-09-18 rehydration guard), not from reading the repo files. The rehydration guard updated the client record but evidently not the rendered site tokens.
- **Tooling deviation.** This MCP build does not expose the `on_page_lighthouse` / `on_page_instant_pages` tools. DataForSEO REST was called directly and the raw JSON parsed from disk.
- **Cost.** 6 Lighthouse calls at $0.005 plus 6 instant_pages calls at $0.0018 = $0.041.
