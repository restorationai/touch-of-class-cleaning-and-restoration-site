# Onsite Audit, FireDEX Butler, 2026-09-28

**Live origin audited:** https://staging.rankai-firedex-butler.pages.dev (staging)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-08-27 (green)
**Form factor:** desktop only (see caveats)

## Read this first: staging SEO exclusion

All 6 audited URLs still return `x-robots-tag: noindex`. That header is the Cloudflare Pages preview default, not a site defect. The Lighthouse SEO score is held down to **69** on every page, and `is-crawlable` is the **only** failing SEO audit on all 6 pages.

SEO is therefore **left out of every verdict in this run** and is recorded as `inconclusive, staging noindex artifact, re-audit after apex cutover`. `apex_cutover` is still null, and `firedex.net` still 301s to `www.firedex.net` on the legacy Apache/WordPress host. Do not open a ticket to "fix SEO" based on this report.

Verdicts below use Performance, Accessibility, and Best Practices only.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 97.8 | -0.2 |
| Accessibility | 90.7 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 69.0 (excluded) | 0.0 |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 97 | 91 | 100 | 69* | 1.2s | 0.042 |
| `/services/` | services-hub | green | 98 | 90 | 100 | 69* | 1.2s | 0.006 |
| `/services/water-damage-restoration/` | service-landing | green | 98 | 90 | 100 | 69* | 1.1s | 0.006 |
| `/services/fire-damage-restoration/` | service-landing | green | 98 | 90 | 100 | 69* | 1.1s | 0.008 |
| `/service-areas/wexford-pa/` | service-area | green | 98 | 91 | 100 | 69* | 1.1s | 0.005 |
| `/contact/` | contact | green | 98 | 92 | 100 | 69* | 1.2s | 0.004 |

\* SEO left out of the verdict because of the staging noindex artifact.

Total Blocking Time is 0ms on all 6 pages. INP was not reported because it needs field data, which a lab run cannot provide. All lab Core Web Vitals fall inside Google's "good" thresholds.

**Watch item:** Accessibility is exactly **90** on `/services/` and both service landings. That is the green/amber line. A one-point drop on any of these pages flips it, and the site, to amber. Actions 2 and 3 below remove that risk.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is still a 535,618-byte PNG shown at 154x64px. Export to SVG or WebP at 2x display size. Estimated savings are 521 to 682 KiB per page. |
| `unsized-images` | 6 | medium | The same `logo.png` has no `width`/`height`. It is the only cause of the 0.042 CLS on `/`. |
| `color-contrast` | 6 | medium | There are three offenders (details under action 2): `text-dark/60` (4.1:1) in the homepage card captions, `text-dark/50` (3.06:1) in the breadcrumb on every non-home page, and `.btn-accent` white on `#e5304c` (4.32:1) on the service landings. |
| `target-size` | 6 | medium | Footer `tel:` and `mailto:` links in `address.not-italic` are smaller than 24x24px. |
| `lcp-discovery-insight` | 5 | low | The LCP hero image is discoverable but has no `fetchpriority="high"` on the 5 non-home pages. The homepage already passes. |
| `has_micromarkup_errors` | 5 | low | DataForSEO validator false positive (see caveats). No fix required. |

`network-dependency-tree-insight` and `render-blocking-insight` (one 8.7KB `_astro/_slug_.*.css` file, 50ms) also fail on every page at low severity. They fall outside each page's top-5 issues, so they are not tracked as template issues. At this size they are acceptable.

## Money page alerts

None. All five money pages (`/`, `/services/`, two service landings, `/contact/`) came back green.

## Regressions vs prior audit

**No regressions.** No URL dropped 5 or more points in any category, and no site average fell 3 or more points. No LCP rose by 200ms, no CLS rose by 0.02, and no TBT rose by 100ms. The largest movement was `/` at Performance 98 to 97 and LCP +81ms, which is normal run-to-run noise.

**Verdict transitions:** none. All 6 URLs were green in both runs.

**New issues this month:**
- `/services/`, both service landings, `/service-areas/wexford-pa/`, `/contact/`: `has_micromarkup_errors`. This is the first time it has been flagged. It traces to DataForSEO demanding `answerCount` on FAQPage `Question` items. That property belongs to QAPage and is not required for FAQPage. `/` has no FAQPage block and is not flagged. This is a validator quirk, not a site change.

**Issues resolved since last audit:** none. Main was pushed at 2026-09-28T02:50Z, but `logo.png` is byte-identical (535,618 bytes), and none of the 5 recommendations from the 2026-08-27 report have shipped.

## What was checked and passed

- Internal links: all 79 unique internal links across the 6 pages return 200.
- Image alt coverage: 100 percent on all 6 pages.
- JSON-LD parses cleanly on all 6 pages (`Organization`, `WebSite`, `LocalBusiness`, plus `Service`, `FAQPage`, and `BreadcrumbList` where appropriate).
- Titles are 52 to 63 characters. Each page has exactly one H1. There is no mixed content and no duplicate title or meta tags.
- Word counts beat the `url-plan.json` targets on every page: home 1527/1200, hub 819/800, landings about 1725/1100, Wexford 1425/900, contact 691/400.
- Best Practices scores 100 on all 6 pages.

## Recommended next actions (priority order)

1. **(template, high impact, carried over)** Replace `/images/logo.png`. It is a 535KB PNG shown at 154x64px in the header on every page. Export it as SVG (or as WebP at about 308x128) and add `width="154" height="64"` to the `<img>` in the header component. That one change closes `image-delivery-insight` and `unsized-images` on all 6 pages and removes the 0.042 CLS on `/`.
2. **(template, accessibility, carried over and expanded)** Fix three contrast failures:
   - In the homepage card captions (`p.text-sm.text-dark/60`), change `text-dark/60` to `text-dark/70`. Contrast goes from 4.1:1 to 5.58:1.
   - In the breadcrumb (`nav ol li a.text-dark/50`, every non-home page), change `text-dark/50` to `text-dark/70`. It is 3.06:1 today.
   - On the service landings, darken the `.btn-accent` background from `#e5304c` to a shade that reaches 4.5:1 against white, or make the label 18.66px bold so the 3:1 large-text rule applies.

   This is what keeps the three pages sitting at exactly 90 off amber.
3. **(template, accessibility, carried over)** Add `inline-block py-1.5` to the footer `a[href^="tel:"]` and `a[href^="mailto:"]` inside `address.not-italic` so each tap target is at least 24px tall. This fixes `target-size` on all 6 pages.
4. **(template, schema)** The sitewide `LocalBusiness` JSON-LD ships `"geo":{"@type":"GeoCoordinates","latitude":"","longitude":""}`, which is empty strings. Either fill in the coordinates for 9133 Marshall Rd, Cranberry Township, PA 16066, or remove the `geo` object from the template. Empty coordinates are invalid structured data.
5. **(blocked, then re-audit)** Cut over the apex domain and re-run this audit. SEO cannot be scored until `firedex.net` serves the Pages build. Per `onboarding_notes`, cutover needs Robert's approval.

## Notes / caveats

- **Desktop-only scoring.** Lighthouse 13.4.0 ran through DataForSEO on desktop (`formFactor: desktop`, `cpuSlowdownMultiplier: 1`, `throughputKbps: 10240`). These are not mobile scores. Mobile would likely score 10 to 20 Performance points lower, and the 535KB logo would weigh much more heavily there.
- **Google rating is now on more pages, against the client-record rule.** `clients/firedex-butler.json` `gbp.note` says "NEVER quote rating in site copy". On 2026-08-27 the rating appeared visibly only on `/`. It now also appears in the body copy of both service landings ("rate us 3.6 out of 5 stars across 12 Google reviews") and next to the reviews snippet on `/service-areas/wexford-pa/`. `AggregateRating` (`3.6` / `12`) ships in the `LocalBusiness` JSON-LD on all 6 audited pages. This is a content/compliance issue outside this audit's technical scope, but it is live and growing, so route it to whoever owns the rule.
- **`has_micromarkup_errors` is a false positive.** A one-page DataForSEO microdata crawl of `/contact/` returned 4 errors, all `FAQPage.mainEntity.answerCount missing`. It also returned 4 warnings (`text` missing on Question, which Google does not require) and 4 info items: the empty `geo` latitude/longitude (action 4), `WebSite.potentialAction`, and the final breadcrumb `ListItem` with no `item`, which Google explicitly allows. It is recorded as low severity and does not affect any verdict.
- **Canonicals are cross-domain by design.** All pages canonicalize to `https://firedex.net/...` so they are ready for cutover. DataForSEO's `canonical` check reads false on the staging host. That is expected before cutover.
- **Client record `status` is `pending`, not `active`.** The audit ran anyway, as it did for the baseline, because `build_status` is `pushed_main` and the preview is live.
- **URL selection.** Three service landings tie at priority 9.0 in `url-plan.json` (fire, mold, water). Water and fire were kept to match the 2026-08-27 baseline so the month-over-month comparison is valid. No service area is marked `primary`, and there is no Cranberry Township (NAP city) page, so the first area slug, `wexford-pa`, was used.
- **Asset caching is still not configured.** Assets, including the content-hashed `_astro/*` bundles and `logo.png`, are served with `cache-control: public, max-age=0, must-revalidate`. A `_headers` rule giving `/_astro/*` `max-age=31536000, immutable` is worth adding before cutover.
- **The `frame` check on `/service-areas/wexford-pa/`** is the lazy-loaded Google Maps embed. It is harmless and recorded as low severity.
- Run cost: about $0.041 (6 Lighthouse at $0.005, 6 instant_pages at $0.0018, 1 one-page microdata crawl at $0.00015). Raw JSON is kept at `/tmp/rank-ai-audit/fdx/` and was not committed.
