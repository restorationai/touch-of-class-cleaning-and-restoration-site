# Onsite Audit: Go Green Restoration of NC, 2026-08-27

**Live origin audited:** https://gogreenrestorationofnc.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** first audit for this client, no comparison data

**Form factor:** DESKTOP only. The Lighthouse run used `formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`. Mobile scores typically run 10 to 20 performance points lower and are not represented anywhere in this report. Do not quote these numbers as mobile scores.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.3 | n/a |
| Accessibility | 96.0 | n/a |
| Best Practices | 96.0 | n/a |
| SEO | 100.0 | n/a |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

The apex is live and correctly indexable (no `x-robots-tag: noindex`), so SEO counts toward the verdict in full. Every audited page returned HTTP 200 with a correct self-referencing canonical, exactly one H1, a title within 30 to 65 characters, a meta description within 70 to 160 characters, 100 percent image alt coverage, zero broken links, and zero broken resources.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 100 | 96 | 100 | 0.94s | 0.005 |
| `/services/` | services-hub | green | 99 | 95 | 96 | 100 | 0.90s | 0.005 |
| `/services/water-damage-restoration/` | service-landing | green | 100 | 95 | 96 | 100 | 0.76s | 0.005 |
| `/services/fire-damage-restoration/` | service-landing | green | 100 | 95 | 96 | 100 | 0.77s | 0.005 |
| `/service-areas/raleigh-nc/` | service-area | green | 99 | 95 | 96 | 100 | 0.90s | 0.006 |
| `/contact/` | contact | green | 99 | 96 | 96 | 100 | 0.87s | 0.026 |

Total blocking time was 0 ms on all six pages. INP was not reported by this Lighthouse run and is recorded as null rather than guessed.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | medium | `logo.png` ships as a 105 KB PNG on every page. Convert to WebP and serve at real display size. Separately, the `/contact/` hero has no `srcset` and ships the full 269 KB source into a 1350x207 slot, wasting 221 KB. |
| `image-aspect-ratio` | 6 | medium | The footer logo declares `width="48" height="48"` but renders at 386x80. Correct the intrinsic attributes in the footer component to the true aspect ratio. |
| `color-contrast` | 5 | medium | Breadcrumb link `a.text-dark/50` renders `#888c93` on `#ffffff` = 3.37:1 at 12px. WCAG AA needs 4.5:1. Darken to roughly `text-dark/70` or higher. |
| `lcp-discovery-insight` | 5 | low | The inner-page hero `<img>` is `loading="eager"` but has no `fetchpriority="high"` and no `srcset`. The homepage hero already has both; mirror that markup in the inner-page hero component. |
| `render-blocking-insight` | 6 | low | One 8.7 KB Astro stylesheet (`_slug_.UsQ6mpDA.css`) blocks render for roughly 50 ms. Marginal at this page weight. |
| `network-dependency-tree-insight` | 6 | low | Critical-path depth diagnostic. Lighthouse measures 0 ms of actual savings here. No action needed. |
| `cache-insight` | 6 | low | Cloudflare's own `email-decode.min.js`, 288 bytes of waste. Injected by the platform, not fixable in our template. |
| `has_render_blocking_resources` | 6 | low | DataForSEO's counterpart to `render-blocking-insight` above. Same single stylesheet, same roughly 50 ms. |

## Money page alerts

None. All four money-page archetypes (`home`, `services-hub`, `service-landing`, `contact`) came back green.

## Regressions vs prior audit

First audit for this client. No comparison data. This run establishes the baseline that next month's audit will diff against.

## Recommended next actions (priority order)

1. **(template, highest impact)** Convert `/images/logo.png` to WebP and fix its declared dimensions. The file is a 105 KB PNG loaded on all six pages, and the footer instance declares `width="48" height="48"` while rendering at 386x80. This one change closes both `image-delivery-insight` and `image-aspect-ratio` across the whole site and is the only finding worth roughly 100 KB per pageview.
2. **(money page)** Add `srcset`/`sizes` to the `/contact/` hero image. It currently ships the full 269 KB `hero-bg.webp` into a 1350x207 band, wasting 221 KB on the most conversion-critical page. The homepage hero already has the correct responsive markup to copy.
3. **(template, accessibility)** Darken the breadcrumb link color. `#888c93` on white is 3.37:1 at 12px, below the 4.5:1 WCAG AA threshold, and it is the single reason accessibility sits at 95 instead of 100 on five of six pages.
4. **(template, performance)** Add `fetchpriority="high"` and `srcset` to the inner-page hero `<img>` component so service, service-area, and contact heroes match the homepage pattern. Measured savings today are near zero because the site is already fast, but this protects LCP as pages get heavier.
5. **(low, housekeeping)** Serve `/sitemap.xml` as an alias or 301 to `/sitemap-index.xml`. The canonical path is correct and `robots.txt` points at it properly, but `/sitemap.xml` currently returns a 404 HTML page, and many third-party crawlers and audit tools probe that conventional path first.

## Notes / caveats

- **Desktop-only scoring.** Repeated because it matters: these are desktop Lighthouse numbers. A mobile run would land meaningfully lower on performance. Treat the 99.3 average as a desktop ceiling, not a mobile reality.
- **Five DataForSEO checks were false positives and were excluded from the verdict.** Each was verified directly against the live HTML before being dismissed, and each is recorded per URL in the state file under `excluded_false_positives`:
  - `has_micromarkup` claimed no structured data. JSON-LD is in fact present on all six pages, 3 to 5 blocks each (Organization, WebSite, LocalBusiness, Service, FAQPage, BreadcrumbList).
  - `has_meta_title` claimed no meta title. Every page has a valid `<title>`. This check looks for the non-standard `<meta name="title">` tag, which Google ignores.
  - `from_sitemap` claimed the pages were absent from the sitemap. All six are present in `/sitemap-0.xml`, correctly referenced from `robots.txt` via `/sitemap-index.xml`. The check appears to probe only the conventional `/sitemap.xml` path.
  - `frame` flagged the Raleigh page. It is a single Google Maps embed with `loading="lazy"` and a `title` attribute, which is correct usage.
  - `no_image_title` flags images lacking a `title` attribute, which is not a ranking signal. Measured `alt` coverage is 100 percent on all six pages.

  Had these been taken at face value, all six pages would have been scored red on a site that is in genuinely good technical health. This is worth remembering for future runs.
- **Severity was calibrated to measured impact, not to raw Lighthouse score.** Lighthouse 13's new `*-insight` audits report a score of 0 even when they quantify 0 ms of savings. Rather than label seven such audits "high" on pages scoring 99 to 100, severity here reflects the savings Lighthouse actually measured. Nothing on this site currently rises to high severity.
- **Client record status is `onboarding`, not `active`.** The methodology's pre-flight calls for `active`. The audit proceeded because `build_status` is `pushed_main` and the apex serves HTTP 200. Someone should confirm whether the status field is simply stale.
- **Apex selection was inferred.** The client record has no `apex_cutover.completed_at` field. The apex was chosen based on `cut_over_at` (2026-08-09, noted "522 cleared + verified live"), a live 200 response, and the absence of a `noindex` header. The staging Pages preview does carry `x-robots-tag: noindex`, so auditing it would have deflated SEO; the staging correction was therefore not needed this run.
- **No Middlesex service-area page exists.** Middlesex is the business's home base and is marked `primary: true` in `plan-input.json`, but `url-plan.json` contains no `/service-areas/middlesex-nc/` page. The service-area slot fell back to `/service-areas/raleigh-nc/` (first area in plan order). This is a content-plan gap rather than a technical defect, so it is out of scope for System 3, but it is worth routing to whoever owns the URL plan.
- **Homepage schema is missing `AggregateRating`.** The plan lists `aggregate-rating` among the homepage schema stubs; the live page serves Organization, WebSite, and LocalBusiness only. Minor, and it should not be added until there are real reviews to back it.
- **Security headers are in good shape.** The apex returns HSTS with `includeSubDomains`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, and a CSP `frame-ancestors` directive. No mixed content was found on any page.
- **Run cost:** 0.0408 USD (6 Lighthouse live calls at 0.005, 6 instant_pages calls at 0.0018). Well inside the 0.30 to 0.50 target.
- **Tooling note.** This MCP build does not expose `on_page_lighthouse` or `on_page_instant_pages` wrapper tools. The audit called the DataForSEO REST endpoints directly (`/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages`). Full payloads were written to disk and parsed out of band rather than read into context. Because the raw API does expose a `for_mobile` flag, mobile auditing is now technically available; it was deliberately not used here so this baseline stays comparable with the documented desktop standard. Switching to mobile is an explicit decision for the operator, and it should be made before the next run rather than after, since it would otherwise register as a large false regression.
