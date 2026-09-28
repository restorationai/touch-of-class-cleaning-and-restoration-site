# Onsite Audit - Quality Contracting, Inc. - 2026-09-28

**Live origin audited:** https://staging.rankai-quality-contracting-inc.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-27 (staging, same 6 URLs)
**Form factor:** desktop (Lighthouse 13.4.0, cpuSlowdownMultiplier 1, throughputKbps 10240). Mobile scores would typically run 10-20 performance points lower.

## Environment caveat - read this before the scores

**The apex looks like it has already been cut over, but the client record does not say so.** `clients/quality-contracting-inc.json` still has no `apex_cutover.completed_at`, so under the audit rules this run went against the Cloudflare Pages staging preview. But `https://qualitycontracting.us/` is now serving the new Rank AI build: `server: cloudflare`, the same Astro asset set as staging, the new homepage title ("Restoration Services in Central Massachusetts..."), the IndexNow key file `/92370eb0990e4d9a832d8b93a4bd94ef.txt` returns 200 (it returned 404 on the old WordPress site in August), and there is no `x-robots-tag` header. Last month the apex was still the old WordPress site on Kinsta.

`GET https://staging.rankai-quality-contracting-inc.pages.dev/` returns `x-robots-tag: noindex`, which Cloudflare Pages adds automatically on `*.pages.dev`. The Lighthouse `is-crawlable` audit fails on all 6 URLs because of it and holds SEO at 69 on every page. **SEO is inconclusive on this staging run and was left out of every verdict.** Verdicts use performance, accessibility and best practices only.

As a check, one extra desktop Lighthouse run was made against the apex homepage (a diagnostic run, not counted in the audit set). It came back **performance 98, accessibility 100, best practices 100, SEO 100**, LCP 1.11s, CLS 0.036. That confirms `is-crawlable` is the only thing dragging the staging SEO score down, and that the live site is indexable.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.0 | -0.8 |
| Accessibility | 98.7 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 69.0 (inconclusive, staging) | 0.0 |

Pages by verdict: green: 1, amber: 5, red: 0, error: 0

Basically unchanged from August. Best practices is 100 on every page, TBT is 0ms everywhere, and LCP is between 0.82s and 0.93s. There are no broken links, no broken resources and no mixed content. The site is still amber for the same two reasons as last month: the homepage CLS failure and the DataForSEO FAQPage structured-data signal. **None of last month's five recommended actions has shipped yet.** Every issue from the August audit is still flagged, and one new template-level item appeared (the GA4 tag).

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 92 | 100 | 100 | 69 | 0.93s | 0.160 |
| `/services/` | services-hub | amber | 99 | 96 | 100 | 69 | 0.89s | 0.004 |
| `/services/water-damage-restoration/` | service-landing | amber | 99 | 100 | 100 | 69 | 0.82s | 0.038 |
| `/services/fire-damage-restoration/` | service-landing | amber | 100 | 100 | 100 | 69 | 0.82s | 0.038 |
| `/service-areas/worcester-ma/` | service-area | amber | 99 | 96 | 100 | 69 | 0.84s | 0.006 |
| `/contact/` | contact | amber | 99 | 100 | 100 | 69 | 0.86s | 0.004 |

TBT is 0ms on every page. INP is null everywhere because Lighthouse lab runs do not produce INP without user interaction. The SEO score of 69 on every row is the staging artifact explained above.

`/` gets green under the rubric (all three counted categories are at or above 90, and it has no on-page issues). But its CLS of 0.160 is a real Core Web Vitals failure, above Google's 0.1 "good" threshold, and it is slightly worse than August's 0.147. It is still the most important single fix on the site.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `unused-javascript` | 6 | low | **New this month.** The GA4 tag `googletagmanager.com/gtag/js?id=G-G8PLTS9XDN` (156KB) is now on every page, and about 69KB of it is unused. Lighthouse puts the LCP cost at 50-100ms. Keep GA4, but load it after first paint: move the gtag `<script>` to the end of `<body>` with `async`, or load it through Partytown (`@astrojs/partytown`). |
| `render-blocking-insight` | 6 | low | **Carried over, not fixed.** The layout head still emits the Google Fonts Inter stylesheet twice: once with the async `media="print" onload="this.media='all'"` pattern, then again as a plain blocking `<link rel="stylesheet">`. Delete the second, blocking one. `/_astro/_slug_.A-a6aXyj.css` (8.9KB, measured at 30-53ms) is not worth acting on by itself. |
| `network-dependency-tree-insight` | 6 | low | No action. Lighthouse reports no good preconnect candidates, and the layout already preconnects to `fonts.googleapis.com` and `fonts.gstatic.com`. |
| `is-crawlable` | 6 | low | No action. This is the staging noindex artifact. The apex diagnostic run scored SEO 100. |
| `has_micromarkup_errors` | 5 | medium | Carried over. DataForSEO flags every page that has an `FAQPage` node, and `/` (no FAQ) is clean again. August's hand-validation found no structural defect. Run `/contact/` through Google's Rich Results Test before changing anything. This one signal is what puts 5 of the 6 pages in amber. |
| `lcp-discovery-insight` | 5 | low | Carried over. The inner-page hero `<img>` still has no `fetchpriority="high"`. Copy the attribute over from the homepage hero. |
| `image-delivery-insight` | 4 | medium | Carried over. `/brand/hero.webp` (164KB) is still hardcoded into the inner-page hero with no `srcset` or `sizes`. Measured waste: 116KB on `/contact/`, 73KB on `/services/`, 47KB on `/service-areas/worcester-ma/`. Reuse the homepage's `hero-bg-480w/768w/1200w` srcset pattern. On `/services/` the service card thumbnails waste another 62KB, mostly `storm-damage-restoration-480w.webp` at 25KB. On `/` the `team-768w.webp` image wastes 33KB. |

## Money page alerts

- **`/services/`** (services-hub) - verdict: amber. Accessibility 96 because the `tel:` link in the dark prose block has 1.14:1 contrast against the surrounding text and no underline. **New this month:** that same link is also a call-tracking defect (see Regressions). The page has 135KB of avoidable image weight and carries the FAQPage schema signal.
- **`/services/water-damage-restoration/`** (service-landing) - verdict: amber. Scores 99/100/100. It is amber only because of the FAQPage schema signal. The hero is missing `fetchpriority="high"`.
- **`/services/fire-damage-restoration/`** (service-landing) - verdict: amber. Scores 100/100/100. It is amber only because of the FAQPage schema signal. The hero is missing `fetchpriority="high"`.
- **`/contact/`** (contact) - verdict: amber. Scores 99/100/100. It carries the FAQPage schema signal and has 116KB of avoidable weight in `/brand/hero.webp`, the largest single-image waste on the site.

## Regressions vs prior audit

**No threshold regressions.** No page lost 5 or more points in any category (the largest drop was `/` performance, 94 to 92). No LCP rose by 200ms or more (the largest rise was `/` at +140ms, to 0.93s). No CLS rose by 0.02 or more (the largest was `/` at +0.013). The site average for performance fell 0.8 points, well under the 3-point flag. Every page kept the same verdict as August.

The small LCP drift of +80 to +140ms on 5 pages lines up with the new GA4 tag and is worth watching. If it keeps rising next month, the tag is the first place to look.

**New issues this month:**
- All 6 pages: `unused-javascript`. GA4 `gtag.js` (G-G8PLTS9XDN) was added since August and ships about 69KB of unused JS per page.
- `/services/`: **phone number mismatch after call-tracking swap** (Rank AI check, not a Lighthouse or DataForSEO ID). The page has an inline number-swap script that replaces `(508) 756-8800` with the tracking number `(508) 355-3039`. The script only rewrites `tel:` hrefs that contain `+15087568800`. The prose link in the `.prose-body` block is `href="tel:5087568800"` (no `+1`), so its text gets swapped but its href does not. Lighthouse caught it after the swap: the link reads **(508) 355-3039** but dials **(508) 756-8800**. Calls from that link skip the tracking line, and visitors see one number while dialing another. The other 4 `tel:` links on the page use `+15087568800` and swap correctly.
- `/service-areas/worcester-ma/`: `forced-reflow-insight`. 90ms of forced reflow that Lighthouse could not attribute to a script, probably from the embedded map iframe (DataForSEO flags a `frame` on this page). Low priority.

**Issues resolved since last audit:** none. Every August issue is still present.

## Recommended next actions (priority order)

1. **(ops, unblocks SEO)** Record the apex cutover in `clients/quality-contracting-inc.json` (`apex_cutover.completed_at`). `https://qualitycontracting.us/` is already serving the new build and passes SEO 100 on the homepage. The next audit will then run against the apex and give a real SEO score for all 6 pages, instead of the staging figure, which is inconclusive.
2. **(money page, conversion + attribution)** On `/services/`, change the prose phone link from `href="tel:5087568800"` to `href="tel:+15087568800"`, to match the other 4 links on the page. Separately, make the swap script's href match format-agnostic: strip non-digits from the href and compare the last 10 digits, so any hand-written `tel:` link in content also swaps. While editing that block, add `underline` to its inline links. That clears the `link-in-text-block` 1.14:1 accessibility failure.
3. **(money page, high impact, carried over)** Fix the homepage CLS of 0.160. Lighthouse puts the whole shift on the hero container (`header.relative > div.container-wide`), and the cause is the Inter web font swapping in. Cheapest first: (a) delete the duplicate blocking `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter...&display=swap">` in the layout head, keeping the async `media="print"` copy; (b) add a metric-matched `@font-face` fallback (`size-adjust`, `ascent-override`, `descent-override` tuned to Inter), or switch to `&display=optional`; (c) self-host the Inter woff2 subset from `/public/fonts/` and preload it.
4. **(template, carried over)** In the shared inner-page hero component, replace `<img src="/brand/hero.webp" ... loading="eager">` with the homepage's responsive `srcset`/`sizes` and add `fetchpriority="high"`. That saves 116KB on `/contact/`, 73KB on `/services/` and 47KB on `/service-areas/worcester-ma/`, and clears `lcp-discovery-insight` on 5 pages. In the same pass, change the review-count `span.text-slate-400` (2.56:1 on white) to `text-slate-500` or darker. That clears `color-contrast` on every service-area page.
5. **(template, new)** Defer GA4. Move the `gtag/js?id=G-G8PLTS9XDN` loader to the end of `<body>` with `async`, or run it through Partytown. That clears `unused-javascript` on all 6 pages and should reverse this month's 80-140ms LCP drift.

## Notes / caveats

- Verdicts were computed with SEO left out, per the staging-noindex correction. If the `has_micromarkup_errors` signal turns out to be a false positive in the Rich Results Test, 4 of the 5 amber pages move to green. `/services/` would stay amber on the tel-link mismatch until item 2 ships.
- URL selection used Mode B (there is no `audit-urls.txt`). The 6 URLs are the same as the 2026-08-27 baseline so the months compare cleanly. `url-plan.json` has grown to 632 pages and now has four service-landing pages tied at priority 9.0: fire damage, mold remediation, roofing and water damage, in plan order. Water damage and fire damage were kept from that tie. No service-area entry has `primary: true`, and the business city (Auburn) is covered by the homepage, so the first area in the plan, `/service-areas/worcester-ma/`, was used again.
- The DataForSEO MCP server in this environment only exposes `api_request` and the docs tools, so the audit called `/v3/on_page/lighthouse/live/json` (`for_mobile: false`) and `/v3/on_page/instant_pages` directly over REST. The standard Lighthouse response included the audit `details`, so no separate `full_data` pass was needed.
- Run cost: $0.0359 (7 Lighthouse calls at $0.005 including the apex diagnostic, 6 instant_pages calls at $0.00015). Well under the $0.30-0.50 target.
- Checks that passed on all 6 URLs: HTTP 200, no broken internal or external links, no broken resources, no mixed content, exactly one H1 per page, titles 45-65 characters (the homepage title is now 45, down from last month, and still in range), meta descriptions 103-155 characters, and every page above its `url-plan.json` `target_word_count` (`/` 1723 vs 1200, `/services/` 961 vs 800, water damage 1772 vs 1100, fire damage 1684 vs 1100, Worcester 1296 vs 900, `/contact/` 711 vs 400).
- Canonicals on staging point to `https://qualitycontracting.us/...`, which is correct. DataForSEO's self-canonical check reports false on all 6 for that reason, and it is not counted as an issue.
- Security headers on staging are unchanged and look good: HSTS `max-age=31536000; includeSubDomains`, `content-security-policy: frame-ancestors`, `permissions-policy`, `referrer-policy: strict-origin-when-cross-origin`, `x-content-type-options: nosniff`. The apex returns the same CSP header, so the Pages header config carried over.
- Other Lighthouse findings on the apex homepage diagnostic run: `cache-insight` (inefficient cache lifetimes) showed up there and not on staging. Check the apex's `_headers` cache rules for `/images/*` and `/_astro/*` when the apex becomes the audited origin.
