# Onsite Audit, FireDEX Butler, 2026-08-27

**Live origin audited:** https://staging.rankai-firedex-butler.pages.dev (staging)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** first audit for this client, no comparison data
**Form factor:** desktop only (see caveats)

## Read this first: staging SEO exclusion

All 6 audited URLs return `x-robots-tag: noindex`. This is the Cloudflare Pages preview default, not a site defect. The Lighthouse SEO category is deflated to **69** on every page, and `is-crawlable` is the **only** failing SEO audit on all 6 pages. Nothing else in the SEO category fails anywhere.

SEO is therefore **excluded from every verdict in this run** and is recorded as `inconclusive, staging noindex artifact, re-audit after apex cutover`. Expected apex SEO score is 100. Do not open a ticket to "fix SEO" off this report.

Verdicts below are computed from Performance, Accessibility, and Best Practices only.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.0 | n/a |
| Accessibility | 90.7 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 69.0 (excluded) | n/a |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 98 | 91 | 100 | 69* | 1.1s | 0.042 |
| `/services/` | services-hub | green | 97 | 90 | 100 | 69* | 1.2s | 0.004 |
| `/services/water-damage-restoration/` | service-landing | green | 98 | 90 | 100 | 69* | 1.1s | 0.010 |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 90 | 100 | 69* | 1.0s | 0.005 |
| `/service-areas/wexford-pa/` | service-area | green | 98 | 91 | 100 | 69* | 1.1s | 0.005 |
| `/contact/` | contact | green | 98 | 92 | 100 | 69* | 1.1s | 0.006 |

\* SEO excluded from verdict, staging noindex artifact.

Total Blocking Time is 0ms on all 6 pages. INP was not reported (requires field data, not available in a lab run). All Core Web Vitals are inside Google's "good" thresholds: LCP well under 2.5s, CLS well under 0.1.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is a 535KB PNG rendered at 154x64px. Export to WebP or SVG at 2x display size. Est. saving 534KB per page. |
| `color-contrast` | 6 | medium | `.text-dark/60` is `#102a4399`, which resolves to `#707f8e` on white at 4.1:1. WCAG AA needs 4.5:1. Change the utility to `text-dark/70`. |
| `target-size` | 6 | medium | Footer `tel:` and `mailto:` links in `address.not-italic` are 17px tall. Minimum is 24x24px. |
| `unsized-images` | 6 | medium | Same `logo.png` has no explicit `width`/`height`. This is the sole driver of the 0.042 CLS on `/`. |
| `network-dependency-tree-insight` | 6 | low | Critical path depth driven by the Google Fonts preconnect chain. |
| `render-blocking-insight` | 6 | low | `_astro/_slug_.*.css` (8.7KB) blocks render for 55ms. Acceptable at this size. |
| `lcp-discovery-insight` | 5 | low | LCP element `/images/hero-bg.webp` is eager-loaded and discoverable but lacks `fetchpriority="high"`. |

Every single finding in this audit is template-level, appearing identically on all 6 pages. There are no page-specific defects other than one meta description length.

## Money page alerts

None. All four money page archetypes (`home`, `services-hub`, `service-landing` x2, `contact`) came back green.

## Regressions vs prior audit

First audit for this client. No comparison data. This run establishes the baseline for next month.

## What was checked and passed

- Broken internal links: all 73 unique internal links across the 6 pages return 200. Zero broken links.
- Image alt coverage: 100 percent. Zero images missing alt text on any audited page.
- Schema.org: valid JSON-LD on all 6 pages. `Organization`, `WebSite`, `LocalBusiness` sitewide, plus `Service` on the service landings and `FAQPage` + `BreadcrumbList` where appropriate.
- Titles: 52 to 63 characters, all inside the 30 to 65 target.
- H1: exactly one per page on all 6.
- Word counts: every page exceeds its `url-plan.json` target (contact 691 vs 400, services-hub 819 vs 800, home 1527 vs 1200, service landings ~1725 vs 1100, service area 1425 vs 900).
- Mixed content: none. No http resources on https pages.
- Duplicate title or meta tags: none.
- Best Practices: 100 on all 6 pages. HSTS, CSP `frame-ancestors`, `X-Content-Type-Options`, `Referrer-Policy` and `Permissions-Policy` all present.

## Recommended next actions (priority order)

1. **(template, high impact)** Replace `/images/logo.png`. It is a 535KB PNG displayed at 154x64px in the site header, eager-loaded on every page, and accounts for 61 to 76 percent of total page weight on the service landings. Export as WebP (or SVG, since it is a logo) at roughly 480x200px and add explicit `width` and `height` attributes. This one change closes `image-delivery-insight` and `unsized-images` on all 6 pages and removes the 0.042 CLS on the homepage. Est. saving 534KB per page load.
2. **(template, accessibility)** Change the `.text-dark/60` body utility to `.text-dark/70`. Measured contrast is 4.1:1 against white (`#707f8e` on `#ffffff`), below the WCAG AA 4.5:1 floor. `text-dark/70` measures 5.58:1. Note `text-dark/65` is already compiled into the stylesheet at 4.67:1 if a smaller visual change is preferred. This is the single largest lever on the accessibility score, affecting 1 to 5 nodes per page.
3. **(template, accessibility)** Give the footer contact links a tap target of at least 24x24px. `a[href^="tel:"]` and `a[href^="mailto:"]` inside `address.not-italic` currently render 17px tall with 21.6px of safe clickable space. Adding `inline-block py-1.5` resolves both the size and the spacing failure. Affects all 6 pages.
4. **(blocked, then re-audit)** Cut over the apex domain and re-run this audit. SEO findings are deferred, not resolved. Until `firedex.net` points at the Pages build, SEO cannot be scored and canonicals continue to resolve to the legacy 2020 WordPress site. Per `onboarding_notes.dns_warning`, this needs Robert's approval first.
5. **(per-page)** Trim the homepage meta description from 165 to 160 characters or fewer, so it does not truncate in the SERP.

## Notes / caveats

- **Desktop-only scoring.** The DataForSEO Lighthouse run is desktop (`formFactor: desktop`, `cpuSlowdownMultiplier: 1`, `throughputKbps: 10240`). Do not read these as mobile scores. Mobile would typically run 10 to 20 Performance points lower, and the 535KB logo would be weighted far more heavily than the green Performance scores here suggest. The high-severity `image-delivery-insight` finding is real and worth fixing despite the green verdict, precisely because desktop throttling masks it. The raw REST endpoint does accept `for_mobile: true`, so a mobile pass is now technically available; it was not used here because the verdict thresholds in this methodology are calibrated to desktop and this run establishes the regression baseline.
- **Two live staging origins exist.** `staging.rankai-firedex-butler.pages.dev` (audited, per methodology) and `firedex-butler-preview.pages.dev` (recorded in `build.preview_url`) both return 200 and serve **different builds** (102KB vs 69KB homepage, different CSS hashes, and a reviews block present only on the audited origin). Worth reconciling so it is unambiguous which deployment is canonical for QA.
- **Client record says `status: "pending"`, not `"active"`.** The methodology expects `active`. Audited anyway because `build_status` is `pushed_main`, `last_pushed_main_at` is today, and the preview is live. Flagging so the record can be corrected or the run treated as provisional.
- **The site publishes the Google rating, which the client record forbids.** `/` renders "3.6 rating, 12 Google reviews" and ships a matching `AggregateRating` (`ratingValue: 3.6`, `reviewCount: 12`) inside the `LocalBusiness` JSON-LD. `clients/firedex-butler.json` `gbp.note` states: "NEVER quote rating in site copy; review reactivation planned before any rating surfaces". This is a content and compliance issue rather than a technical one, so it is out of this audit's scope, but it is live right now and should be routed to whoever owns that rule. The `3.8` / `11` in the client record is simply stale against the current GBP; the page copy and the schema agree with each other, so there is no structured-data mismatch.
- **Canonicals are cross-domain by design.** All 6 pages canonicalize to `https://firedex.net/...` for cutover readiness. DataForSEO's `canonical` check reads false because the tags are not self-referencing on the staging host. This is correct pre-cutover behaviour and is not a defect, but it does mean canonicals currently point at legacy WordPress URLs.
- **Asset caching is not configured.** Every asset, including content-hashed `_astro/*` bundles, is served with `cache-control: public, max-age=0, must-revalidate`. Lighthouse 13.4.0 did not run a `uses-long-cache-ttl` audit, so this is an observation from response headers rather than a Lighthouse finding. A `_headers` rule giving `/_astro/*` a long immutable TTL is worth adding in the deploy repo before cutover, since those filenames are already content-hashed.
- **The `frame` check on `/service-areas/wexford-pa/`** is a Google Maps embed. It is already `loading="lazy"` with `referrerpolicy="no-referrer-when-downgrade"`. Benign, recorded as low severity for completeness only.
- **Broken-link coverage.** `on_page_instant_pages` does not compute outlink status, so the 73-link check above was done with direct HTTP requests at no API cost. It covers links found on the 6 audited pages only, not the full 182-page site.
- Raw Lighthouse JSON retained at `/tmp/rank-ai-audit/raw/` for this run (roughly 1MB per URL, not committed).
