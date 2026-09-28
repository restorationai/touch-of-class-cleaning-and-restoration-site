# Onsite Audit - Katofsky Construction LLC - 2026-09-28

**Live origin audited:** https://staging.rankai-katofsky-construction-llc.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit

> **Environment caveat: SEO score inconclusive.** This run audited the Cloudflare Pages staging preview, which serves `x-robots-tag: noindex` (confirmed with `curl -sI`). That makes Lighthouse's `is-crawlable` audit fail on every page and holds the SEO category at 69. This is a staging artifact, not a site defect. SEO is **excluded from all verdicts** in this report. Its real value is deferred until after apex cutover and a re-audit.
>
> **Form factor: desktop only.** DataForSEO runs Lighthouse with desktop settings (`cpuSlowdownMultiplier=1`, `throughputKbps=10240`). Mobile Performance usually scores 10-20 points lower.

First audit for this client - no comparison data.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 96.5 | n/a |
| Accessibility | 96.0 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 69.0 (inconclusive, staging noindex) | n/a |

Pages by verdict: {green: 0, amber: 6, red: 0, error: 0}

Every page scores 95 or higher on the three counted Lighthouse categories. All six pages are amber for on-page reasons: structured-data validation errors on five pages and an over-long meta description on the homepage. None are amber for performance.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 96 | 100 | 100 | 69* | 1.43s | 0.016 |
| /services/ | services-hub | amber | 96 | 95 | 100 | 69* | 1.39s | 0.003 |
| /services/fire-damage-restoration/ | service-landing | amber | 97 | 95 | 100 | 69* | 1.23s | 0.003 |
| /services/roofing/ | service-landing | amber | 99 | 95 | 100 | 69* | 0.96s | 0.004 |
| /service-areas/penn-hills-pa/ | service-area | amber | 96 | 95 | 100 | 69* | 1.37s | 0.003 |
| /contact/ | contact | amber | 95 | 96 | 100 | 69* | 1.51s | 0.024 |

\* Staging noindex artifact; not counted. TBT is 0 ms on all six pages. INP was not reported (lab run).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | medium | `/images/logo.png` is a 666 KiB, 1200x800 PNG. The header shows it at about 96px tall (`h-20 md:h-24`), so 679,722 bytes are wasted on every page. Export a trimmed logo around 300px wide as WebP or SVG, target under 20 KB, and set real `width`/`height` attributes. The current `width="64" height="64"` does not match the 3:2 aspect ratio. Est. LCP savings 450-550 ms per page. |
| `has_micromarkup_errors` | 5 | medium | DataForSEO flags structured-data errors on every page that has `BreadcrumbList` + `FAQPage`. The homepage has neither and is clean. In each BreadcrumbList, the last `ListItem` has no `item` URL (for example `("Contact", null)`). Add the page's own canonical URL as `item` on the final crumb in the breadcrumb schema component, then run `/contact/` and `/services/` through the Schema Markup Validator to confirm FAQPage passes. |
| `color-contrast` | 5 | medium | Breadcrumb links use `text-dark/50`, which renders #888c93 on #ffffff at 12px. That is 3.37:1 contrast, below the 4.5:1 minimum. Change the class to `text-dark/70` or darker in the breadcrumb component. This lifts Accessibility from 95 to 100 on five pages. |
| `lcp-discovery-insight` | 5 | low | The hero `<img>` (`main > section > div.absolute > img.w-full`) is eager-loaded but has no `fetchpriority="high"`. Add it in the interior-page hero component. The homepage hero already has it. |
| `render-blocking-insight` | 5 | low | The single Astro stylesheet `/_astro/_slug_.*.css` (about 8.8 KB) blocks first paint. Est. savings are only 50 ms. Optional: set `build.inlineStylesheets: "always"` in the Astro config. |
| `network-dependency-tree-insight` | 6 | low | Informational. Google Fonts (`fonts.googleapis.com` then `fonts.gstatic.com`) adds a chained request. Add `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>` in the layout head, or self-host the font. |

## Money page alerts

- **`/`** (home) - verdict: amber. The meta description is 185 characters (target 70-160), so Google will truncate it before the phone number. Perf 96, LCP 1.43s.
- **`/services/`** (services-hub) - verdict: amber. Structured-data errors (BreadcrumbList/FAQPage). Rendered word count is 695 against a url-plan target of 800. Perf 96, LCP 1.39s.
- **`/services/fire-damage-restoration/`** (service-landing) - verdict: amber. Structured-data errors. Perf 97, LCP 1.23s.
- **`/services/roofing/`** (service-landing) - verdict: amber. Structured-data errors. Perf 99, LCP 0.96s.
- **`/contact/`** (contact) - verdict: amber. Structured-data errors. This page has the site's weakest Performance (95), longest LCP (1.51s) and highest CLS (0.024), mostly caused by the same oversized logo and the `hero-bg.webp` (135 KB wasted).

## Regressions vs prior audit

Not applicable. This is the first audit for this client.

## Recommended next actions (priority order)

1. **(staging caveat)** Cut over the apex domain (`katofskyconstruction.com`) and re-audit. SEO findings are deferred, not resolved, until then. Today the apex resolves to 3.33.130.190 / 15.197.148.33 and fails the TLS handshake, while every canonical, `og:url` and JSON-LD `@id` already points at it.
2. **(money page, template)** Fix the BreadcrumbList schema: give the final crumb an `item` equal to the page canonical, then re-validate FAQPage. This clears `has_micromarkup_errors` on `/services/`, both service landings, `/contact/` and the Penn Hills area page.
3. **(money page)** Shorten the homepage meta description to 160 characters or fewer. For example: "Katofsky Construction LLC: 24/7 water, fire, mold and storm damage restoration in Pittsburgh. Licensed, insured, IICRC-certified. Call (412) 304-9284." (151 chars). Update both the page source and `plan/url-plan.json` for `/`.
4. **(template, high impact)** Replace the 666 KiB `/images/logo.png` with a properly sized WebP/SVG under 20 KB and correct its `width`/`height`. This is the largest image-waste item on all six pages. Est. 450-550 ms LCP savings each.
5. **(template)** Darken breadcrumb links from `text-dark/50` to `text-dark/70` and add `fetchpriority="high"` to the interior hero image.

## Notes / caveats

- **Client record status.** `clients/katofsky-construction-llc.json` has `status: "onboarding"`, not `"active"`, which strictly fails the documented pre-flight gate. The audit proceeded because `build_status` is `pushed_main` and the staging preview serves the current build. Other onboarding clients have been audited the same way.
- **URL selection.** There is no `audit-urls.txt`, so the URLs came from `plan/url-plan.json`. Four service landings are tied at priority 9.0 (fire damage, roofing, water damage, mold remediation). Plan order picked fire damage restoration and roofing. No url-plan service area has `primary: true`. The plan-input primary area (Pittsburgh) has no page because it is folded into the homepage (`/service-areas/pittsburgh-pa/` returns 404). The first area in plan order was used instead: Penn Hills.
- **Tooling.** The MCP `on_page_lighthouse` / `on_page_instant_pages` tools are not exposed in this build. The same DataForSEO endpoints were called over REST (`/v3/on_page/lighthouse/live/json` with `for_mobile=false`, and `/v3/on_page/instant_pages` with JS rendering and micromarkup validation). Full Lighthouse JSON (0.7-1.1 MB per URL) was written to disk and parsed there. Lighthouse 13.4.0. Cost: about $0.04 total.
- **is-crawlable** fails on all six pages (staging noindex). On five pages it fell outside the top-5 Lighthouse issue cap, so it only appears in the homepage issue list.
- **Other on-page checks passed on all six pages:** no broken internal or external links, no mixed content, 100% image alt coverage, exactly one H1 per page, titles 33-65 chars, and no duplicate titles or descriptions. DataForSEO on-page score was 97.44 on every page.
- **Penn Hills iframe.** `/service-areas/penn-hills-pa/` embeds a Google Maps iframe (DataForSEO `frame` check). Its third-party map tiles set short cache TTLs (`cache-insight`, 31 KiB), which the origin cannot fix. Consider a click-to-load static map image if mobile Performance turns out weak.
- **Word counts** come from DataForSEO's rendered plain text and include nav/footer. Only `/services/` (695 vs 800) is below its url-plan target.
