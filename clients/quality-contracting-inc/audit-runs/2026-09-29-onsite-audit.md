# Onsite Audit - Quality Contracting, Inc. - 2026-09-29

**Live origin audited:** https://staging.rankai-quality-contracting-inc.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-27 (staging, amber)
**Form factor:** desktop (Lighthouse 13.4.0, cpuSlowdownMultiplier 1, throughputKbps 10240). Mobile scores would typically run 10-20 performance points lower.

## Environment caveat - read this before the scores

**The apex domain appears to be cut over, but the client record does not say so.** `clients/quality-contracting-inc.json` still has no `apex_cutover.completed_at`, so this audit followed the rule and hit the staging Pages preview. But `https://qualitycontracting.us/` no longer serves the old WordPress/Kinsta site. It now returns the Rank AI Astro build through Cloudflare, with the same homepage title as staging ("Restoration Services in Central Massachusetts"), the IndexNow key file `/92370eb0990e4d9a832d8b93a4bd94ef.txt` returns 200 (it returned 404 on 2026-08-27), there is no `x-robots-tag` header, and the record's `deploy_url` is already `https://qualitycontracting.us`.

**Staging and the apex are not running the same build.** The CSS bundle hash differs (`_slug_.B3bBBMuK.css` on apex vs `_slug_.A-a6aXyj.css` on staging), the apex serves inner-page images from `images.qualitycontracting.us`, the apex homepage hero markup has a different layout (`lg:grid`), and apex CTA buttons use the `bg-cta` token where staging still uses `bg-primary-600`. Staging looks like it lags production. The scores below describe the staging preview. They may not describe what visitors and Google see.

`GET https://staging.rankai-quality-contracting-inc.pages.dev/` returns `x-robots-tag: noindex`, which Cloudflare Pages injects automatically on `*.pages.dev`. The Lighthouse `is-crawlable` audit fails on all 6 URLs and holds SEO at 69 on every page. **SEO is inconclusive this run and was excluded from every verdict.** Verdicts use performance, accessibility and best practices only.

A single diagnostic pass on the apex homepage (not counted in the verdict) scored **99 / 100 / 100 / SEO 100**, LCP 0.89s, CLS 0.036. The real SEO number on production looks clean. See Notes for the full diagnostic.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.2 | -0.6 |
| Accessibility | 98.7 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 69.0 (inconclusive) | 0.0 |

Pages by verdict: green: 1, amber: 5, red: 0, error: 0

This is essentially the same result as last month. Best practices is 100 on every page, TBT is 0ms everywhere except 28ms on `/contact/`, LCP sits between 0.79s and 0.91s, and there are zero broken links, zero broken resources and zero mixed content. The same two things keep the site at amber: the homepage web-font layout shift and the DataForSEO FAQPage structured-data signal. **None of the fixes recommended on 2026-08-27 have reached the staging build.**

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 93 | 100 | 100 | 69 | 0.79s | 0.160 | 0ms |
| `/services/` | services-hub | amber | 99 | 96 | 100 | 69 | 0.91s | 0.004 | 0ms |
| `/services/water-damage-restoration/` | service-landing | amber | 100 | 100 | 100 | 69 | 0.81s | 0.038 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | amber | 99 | 100 | 100 | 69 | 0.84s | 0.038 | 0ms |
| `/service-areas/worcester-ma/` | service-area | amber | 99 | 96 | 100 | 69 | 0.87s | 0.006 | 0ms |
| `/contact/` | contact | amber | 99 | 100 | 100 | 69 | 0.87s | 0.014 | 28ms |

INP is null on every page because Lighthouse lab runs do not produce INP without user interaction.

`/` counts as green under the rubric because its three counted categories are all at or above 90 and it has no on-page issues. It still has the single biggest real defect in the set: a CLS of 0.160, above Google's 0.1 "good" threshold, up from 0.147 last month.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `unused-javascript` | 6 | low | New this month. The GA4 tag `googletagmanager.com/gtag/js?id=G-G8PLTS9XDN` (159KB) loads on every page and about 69KB of it goes unused on first load. Lighthouse estimates 50-100ms of LCP on 5 of 6 pages. It is already `async`. Delay the gtag loader until after `window.load` or the first user interaction, or move it off the main thread with `@astrojs/partytown` (`type="text/partytown"`). Check that GA4 still records page_view after the change. |
| `render-blocking-insight` | 6 | low | Still unfixed from last month. The layout head emits the Google Fonts Inter stylesheet twice: once as async (`media="print" onload="this.media='all'"`) and then again as a plain blocking `<link rel="stylesheet">`. Delete the second, blocking copy. The same duplicate is live on the apex. |
| `network-dependency-tree-insight` | 6 | low | Lighthouse reports no good preconnect candidates, and the layout already preconnects to `fonts.googleapis.com` and `fonts.gstatic.com`. No action. |
| `is-crawlable` | 6 | low | No action. This is the staging `x-robots-tag: noindex` artifact. The apex homepage passes. |
| `has_micromarkup_errors` | 5 | medium | Same signal as last month, on every page that carries an `FAQPage` node (`/` has no FAQ and comes back clean). The markup was hand-validated as structurally correct on 2026-08-27. Nobody has run it through Google's Rich Results Test yet. Do that before changing anything, and do not remove the FAQ markup based on a DataForSEO signal alone. |
| `lcp-discovery-insight` | 5 | low | The shared inner-page hero `<img>` is eager but has no `fetchpriority="high"`. Copy that attribute from the homepage hero. Lighthouse puts the saving at 0ms, so treat it as hygiene. |
| `image-delivery-insight` | 4 | medium | The shared inner-page hero hardcodes `<img src="/brand/hero.webp" loading="eager">` (164KB) with no `srcset`/`sizes`. Measured waste: 116KB on `/contact/`, 73KB on `/services/`, 47KB on `/service-areas/worcester-ma/`. Copy the homepage's `hero-bg-480w/768w/1200w` srcset pattern. `/services/` also wastes about 61KB on card thumbnails (`storm-damage-restoration-480w.webp` 25KB, the largest). |

## Money page alerts

- **`/services/`** (services-hub) - verdict: amber. Accessibility 96: the `<a href="tel:5087568800">` inside the dark prose block renders `#fbb1b2` against `#cfd1d4` body text (1.14:1, needs 3:1) and has no underline. It also carries 134KB of avoidable image weight and the FAQPage schema signal. LCP rose 113ms to 0.91s, the slowest in the set but well inside "good".
- **`/services/water-damage-restoration/`** (service-landing) - verdict: amber. 100/100/100. Amber only because of the FAQPage schema signal. The hero is missing `fetchpriority="high"`.
- **`/services/fire-damage-restoration/`** (service-landing) - verdict: amber. 99/100/100. Amber because of the FAQPage schema signal. There is a new `forced-reflow-insight` (76ms of unattributed reflow), and the hero is missing `fetchpriority="high"`.
- **`/contact/`** (contact) - verdict: amber. 99/100/100. It has the largest single-image waste on the site (116KB on the shared hero) plus the FAQPage schema signal. This is the only page with non-zero TBT (28ms).

## Regressions vs prior audit

Compared against the 2026-08-27 staging audit (same 6 URLs, same origin, same form factor).

**No regressions crossed a threshold.** No category dropped 5 or more points on any page (worst: -1 performance on 4 pages). No LCP rose 200ms or more (largest: +116ms on `/contact/`). No CLS rose 0.02 or more (largest: +0.0125 on `/`). No TBT rose 100ms or more. The site-level performance average moved by -0.6. All of this is within normal lab-run variance.

**Verdict transitions:** none. Every page kept last month's verdict.

**New issues this month:**
- All 6 pages: `unused-javascript`. The GA4 gtag.js loader ships about 69KB of unused script. Lighthouse did not flag it on 2026-08-27.
- `/services/fire-damage-restoration/`: `forced-reflow-insight`, 76ms of unattributed forced reflow. It showed up on this page only, and also on the apex homepage diagnostic, so it may come and go between runs. Re-check next month before chasing it.

**Issues resolved since last audit:** none. Every issue ID from 2026-08-27 is still present on the same page. That includes the homepage CLS, the duplicate Google Fonts stylesheet, both contrast failures and the unsized inner-page hero.

## Recommended next actions (priority order)

1. **(blocking, ops)** Confirm the apex cutover and record it. `https://qualitycontracting.us/` is already serving the new build. Set `apex_cutover.completed_at` in `clients/quality-contracting-inc.json` and re-run this audit against the apex so the next report measures production and returns a real SEO score. Also find out why staging lags production (different CSS hash, image host and hero layout). Either redeploy staging from the same commit or retire it as the audit target.
2. **(money page, high impact)** Fix the homepage CLS of 0.160. It is the same root cause as last month: `header.relative > div.container-wide` (hero H1 plus intro) reflows when `fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7W0Q5nw.woff2` swaps in. Cheapest first: (a) delete the duplicate blocking Google Fonts `<link>` in the layout head; (b) add an Inter-matched fallback `@font-face` with `size-adjust`, `ascent-override` and `descent-override`, or switch to `&display=optional`; (c) self-host and preload the Inter woff2 subset. The apex homepage measured CLS 0.036 with the same font culprit, so production may already have a partial fix. Port it to staging and finish it on both.
3. **(template)** Replace the hardcoded `<img src="/brand/hero.webp" loading="eager">` in the shared inner-page hero with the homepage's responsive `srcset`/`sizes` plus `fetchpriority="high"`. This saves 116KB on `/contact/`, 73KB on `/services/` and 47KB on `/service-areas/worcester-ma/`, and clears `lcp-discovery-insight` on 5 pages. On the apex, also convert the header `/images/logo.png` (205KB PNG, declared `width="36" height="36"`, rendered at `h-14`) to a correctly sized WebP. Lighthouse measures 204KB of waste on that one file, and it loads on every production page.
4. **(money page, accessibility)** Fix the two contrast failures, which are unchanged since last month. On `/services/`, add `underline` to the inline `tel:` link in the dark prose block, or move its colour well away from the `#cfd1d4` body text. On `/service-areas/worcester-ma/`, change `span.text-slate-400` (`#94a3b8` on white, 2.56:1) to `text-slate-500` or darker. Both are template classes, so the fixes reach every service and service-area page.
5. **(template)** Defer the GA4 gtag loader (new `unused-javascript` on all 6 pages, about 69KB unused, up to 100ms LCP). Load it after `window.load`/first interaction or through Partytown, then confirm page_view still fires in GA4 real-time.

## Notes / caveats

- Verdicts exclude SEO under the staging-noindex correction. The site is amber because 5 of 6 pages carry the medium-severity `has_micromarkup_errors` signal. If Rich Results Test shows it to be a false positive, the site would move to green on this rubric, with the homepage CLS still open.
- **Apex diagnostic (not in `audited_urls`, not in the verdict):** `https://qualitycontracting.us/` scored performance 99, accessibility 100, best practices 100, SEO 100, LCP 895ms, CLS 0.036, TBT 0ms. Failing Lighthouse audits: `image-delivery-insight` (237KB total, of which 204KB is `logo.png`), `forced-reflow-insight`, `unused-javascript` (GA4), `cache-insight`, `render-blocking-insight`, `network-dependency-tree-insight`. On instant_pages it has no broken links or resources, its self-referencing canonical passes, and it is flagged `low_content_rate` and `no_image_title`. Neither flag needs action.
- URL selection used Mode B from `plan/url-plan.json`, the same set as 2026-08-27. No `audit-urls.txt` exists. The top two `service-landing` pages at priority 9.0 were taken in plan order (water damage, fire damage). No service area has `primary: true`, and the business city (Auburn) has no area page, so the first area slug was used: `/service-areas/worcester-ma/`.
- The DataForSEO MCP in this environment exposes only `api_request` and the `docs_*` tools, so the audit called `/v3/on_page/lighthouse/live/json` (`for_mobile: false`) and `/v3/on_page/instant_pages` over REST. The live Lighthouse endpoint returns the full audit tree, so failing-audit detail was captured without separate `full_data` calls.
- Run cost: $0.03605 (7 Lighthouse at $0.005, 7 instant_pages at $0.00015, including the apex diagnostic pair). This is well under the $0.30-0.50 target.
- On-page checks that passed on all 6 URLs: all return 200; no broken internal or external links; no broken resources; no mixed content; exactly one H1 per page; no duplicate titles or descriptions; titles 45-65 characters; meta descriptions 103-155 characters; no missing image alt text; every page is over its `target_word_count` (`/` 1723 vs 1200, `/services/` 961 vs 800, water damage 1772 vs 1100, fire damage 1684 vs 1100, Worcester 1296 vs 900, `/contact/` 711 vs 400). The `frame` flag on Worcester is the embedded map iframe and is not an issue.
- Security headers on staging are unchanged and good: HSTS `max-age=31536000; includeSubDomains`, CSP `frame-ancestors`, `permissions-policy` locking geolocation, microphone and camera, `referrer-policy: strict-origin-when-cross-origin`, and `x-content-type-options: nosniff`. Because the apex is now live, confirm that the same headers are served there.
