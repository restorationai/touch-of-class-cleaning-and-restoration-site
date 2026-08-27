# Onsite Audit - Quality Contracting, Inc. - 2026-08-27

**Live origin audited:** https://staging.rankai-quality-contracting-inc.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client - no comparison data
**Form factor:** desktop (Lighthouse 13.4.0, cpuSlowdownMultiplier 1, throughputKbps 10240). Mobile scores would typically run 10-20 performance points lower.

## Environment caveat - read this before the scores

This audit ran against the Cloudflare Pages staging preview, not the apex domain. `clients/quality-contracting-inc.json` has no `apex_cutover.completed_at`, and `https://qualitycontracting.us/` still serves the client's old WordPress site on Kinsta (page title "Home - Quality Contracting, Inc.", and the IndexNow key file `/92370eb0990e4d9a832d8b93a4bd94ef.txt` returns 404 there but is present in the new build).

`GET https://staging.rankai-quality-contracting-inc.pages.dev/` returns `x-robots-tag: noindex`, which Cloudflare Pages injects automatically on `*.pages.dev` preview subdomains. The Lighthouse `is-crawlable` audit therefore fails on all 6 URLs and drags the SEO category down to 69 on every page. That is an artifact of the preview host, not a defect in the site.

**SEO is inconclusive this run and was excluded from every verdict.** All verdicts below were computed from performance, accessibility and best practices only. `is-crawlable` is the only SEO audit failing on any page. Re-audit after apex cutover to get a real SEO number.

Related: canonical tags on all 6 pages point at `https://qualitycontracting.us/...` rather than the staging URL, so the DataForSEO `canonical` self-reference check reports false on all 6. That is the correct behaviour for a staging preview and is not counted as an issue.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.8 | n/a |
| Accessibility | 98.7 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 69.0 (inconclusive) | n/a |

Pages by verdict: green: 1, amber: 5, red: 0, error: 0

This is a strong technical baseline. Best practices is a clean 100 across the board, TBT is 0ms on every page, LCP sits between 0.75s and 0.83s everywhere, there are zero broken links, zero broken resources, zero mixed content, and alt text coverage is 100 percent on all 42 images across the 6 pages. Two things hold it at amber: a genuine layout-shift failure on the homepage, and a DataForSEO structured-data validation error on every page that carries an FAQ block.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 94 | 100 | 100 | 69 | 0.79s | 0.147 | 0ms |
| `/services/` | services-hub | amber | 100 | 96 | 100 | 69 | 0.80s | 0.004 | 0ms |
| `/services/water-damage-restoration/` | service-landing | amber | 100 | 100 | 100 | 69 | 0.78s | 0.033 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | amber | 99 | 100 | 100 | 69 | 0.82s | 0.033 | 0ms |
| `/service-areas/worcester-ma/` | service-area | amber | 100 | 96 | 100 | 69 | 0.76s | 0.005 | 0ms |
| `/contact/` | contact | amber | 100 | 100 | 100 | 69 | 0.75s | 0.012 | 0ms |

SEO 69 on every row is the staging noindex artifact described above and did not affect any verdict.

INP is null on every page: Lighthouse lab runs do not emit an INP value without user interaction.

Note that `/` scores green on the rubric while carrying the single most impactful defect in this audit. Its three category scores are all at or above 90, and it has no on-page issues, so the rubric puts it in green. Its CLS of 0.147 is above Google's 0.1 "good" threshold and is a real Core Web Vitals failure. Fix it first regardless of the colour.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `is-crawlable` | 6 | low | No action. Cloudflare Pages injects `x-robots-tag: noindex` on the preview subdomain. Disappears at apex cutover. |
| `render-blocking-insight` | 6 | low | Two things block first paint. `/_astro/_slug_.CzmCq3fu.css` (8.8KB) costs a measured 55-57ms and is not worth acting on alone. More importantly, the shared layout emits the Google Fonts stylesheet **twice**: once with the async `media="print" onload="this.media='all'"` pattern, and immediately after as a plain blocking `<link rel="stylesheet">`. The second copy defeats the first and blocks render on a third-party origin. Delete the blocking duplicate. |
| `network-dependency-tree-insight` | 6 | low | No origins are preconnected in Lighthouse's view, but Lighthouse also reports "no additional origins are good candidates". The layout already emits preconnects to `fonts.googleapis.com` and `fonts.gstatic.com`. Marginal at current LCP figures. No action. |
| `has_micromarkup_errors` | 5 | medium | DataForSEO reports structured-data validation errors on every audited page except `/`. Isolated to the `FAQPage` node: `/blog/`, which ships `WebSite` plus `BreadcrumbList` and no FAQ, comes back clean, and `/` ships `Organization` plus `WebSite` plus `LocalBusiness` and no FAQ and also comes back clean. Every page that fails carries an `FAQPage`. Hand-validation of all 21 Question nodes across the 5 pages found no structural defect: every Question has `name` and `acceptedAnswer`, every Answer has non-empty plain-text `text`, and no HTML is embedded in answer text. Verify once in Google's Rich Results Test before changing anything, and do not strip the FAQ markup on a DataForSEO signal alone. It is very likely reflecting Google's 2023 restriction of FAQ rich results to government and health sites, which is an eligibility change rather than a markup error, and the markup still feeds AI answer engines. |
| `lcp-discovery-insight` | 5 | low | The inner-page hero `<img>` is eager-loaded and discoverable in the initial document, but has no `fetchpriority="high"`. Only the `priorityHinted` check fails; Lighthouse scores the LCP saving at 0ms. The homepage hero already does this correctly, so port that one attribute onto the shared inner-page hero component. |
| `image-delivery-insight` | 4 | medium | `/brand/hero.webp` is a single 178KB file hardcoded into every inner-page hero with no `srcset` and no `sizes`. Measured waste: 130KB on `/contact/`, 87KB on `/services/`, 62KB on `/service-areas/worcester-ma/`. The homepage hero already ships a responsive `srcset` (`hero-bg-480w/768w/1200w`); port that pattern onto the shared inner-page hero. Separately on `/services/`, the service card thumbnails add another 64KB of waste (worst offenders: `storm-damage-restoration-480w.webp` 24KB, `emergency-board-up-tarping-480w.webp` 13KB), and on `/` the `team-768w.webp` image wastes 33KB. |

## Money page alerts

- **`/services/`** (services-hub) - verdict: amber. Accessibility 96. A `tel:` link inside a prose block on a dark background renders at `#fbb1b2` against surrounding text at `#cfd1d4`, which is 1.14:1 where WCAG needs 3:1 for colour-only link differentiation, and the link has no underline or other non-colour styling. Also the heaviest page in the set at 151KB of avoidable image weight.
- **`/services/water-damage-restoration/`** (service-landing) - verdict: amber. Perfect 100/100/100. Amber solely on the FAQPage schema validation signal. Hero missing `fetchpriority="high"`.
- **`/services/fire-damage-restoration/`** (service-landing) - verdict: amber. 99/100/100. Amber solely on the FAQPage schema validation signal. Hero missing `fetchpriority="high"`.
- **`/contact/`** (contact) - verdict: amber. Perfect 100/100/100 and the fastest LCP in the set at 0.75s. Amber on the FAQPage schema validation signal, plus 130KB of avoidable hero weight, the largest single-image waste measured anywhere on the site.

`/` is not listed here because it came back green, but see the CLS finding in the recommended actions below.

## Regressions vs prior audit

First audit for this client. No comparison data. This run establishes the baseline that the 2026-09 audit will diff against.

## Recommended next actions (priority order)

1. **(money page, high impact)** Fix the homepage CLS of 0.147. Lighthouse pins the entire shift on one element, `body.min-h-screen > main.flex-1 > header.relative > div.container-wide` (the hero H1 plus intro paragraph), with the cause recorded as "Web font loaded" and the culprit resource named as `fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7W0Q5nw.woff2`. Inter is loaded from Google Fonts with `&display=swap`, so the hero copy paints in the fallback face and then reflows when Inter arrives. Three fixes, cheapest first: (a) delete the duplicate blocking Google Fonts `<link>` described in the template table, which is the second of two identical `css2?family=Inter...` stylesheet tags in the layout head; (b) add a `@font-face` fallback with `size-adjust`, `ascent-override` and `descent-override` tuned to Inter so the fallback occupies the same box, or switch the query string to `&display=optional`; (c) best long-term, self-host the Inter woff2 subset out of `/public/fonts/` and preload it, which also removes the third-party render-block. This is the only page in the set above the 0.1 CLS threshold, and it is the homepage. Expect it to be worse on mobile, which this desktop-only run cannot measure.
2. **(template, high impact)** Remove the duplicate Google Fonts stylesheet from the shared layout head. The layout currently emits `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" media="print" onload="this.media='all'">` and then the same URL again as a plain blocking `<link rel="stylesheet">`. Keep one. Present on all 6 audited pages and therefore on all 46 built pages. This is also step (a) of item 1.
3. **(template)** Port the homepage hero's responsive `srcset`/`sizes` and `fetchpriority="high"` onto the shared inner-page hero component, which currently hardcodes `<img src="/brand/hero.webp" ... loading="eager">` with no width descriptors and no priority hint. Saves 130KB on `/contact/`, 87KB on `/services/` and 62KB on `/service-areas/worcester-ma/`, and clears `lcp-discovery-insight` on 5 pages.
4. **(money page, accessibility)** Fix the two contrast failures. On `/services/`, the `tel:` link inside the dark prose block measures 1.14:1 against its surrounding text and relies on colour alone: add `underline` to inline links in that block, or lift the link colour well clear of the `#cfd1d4` body text. On `/service-areas/worcester-ma/`, `span.text-slate-400` (`#94a3b8` on `#ffffff` at 14px) measures 2.56:1 against the 4.5:1 requirement: change that class to `text-slate-500` or darker. Both are template classes, so the fix reaches every service page and every one of the 11 service-area pages.
5. **(verification, then decide)** Run `/contact/` and `/services/water-damage-restoration/` through Google's Rich Results Test to confirm or dismiss the `has_micromarkup_errors` signal. This one signal is what puts 5 of 6 pages into amber, and hand-validation found no defect in the markup. Confirming it costs nothing and either removes the amber or gives a concrete field to fix.

## Notes / caveats

- Verdict rubric applied with SEO excluded, per the staging-noindex correction. Counted categories were performance, accessibility and best practices. Under that rubric the site is amber because 5 of 6 pages carry a medium-severity on-page issue (`has_micromarkup_errors`). If that signal is confirmed to be a false positive, the site moves to green with `/` still needing the CLS fix.
- `clients/quality-contracting-inc.json` carries `status: "onboarding"` rather than `"active"`. The audit proceeded because `build_status` is `pushed_main` and all 6 staging URLs serve 200. This matches prior practice on `prorestoration` (status `pending`) and `mcc-restoration`.
- URL selection used Mode B. No `audit-urls.txt` exists for this client, so the 6 URLs were derived from `plan/url-plan.json`: home, `/services/`, the top two `service-landing` pages by `priority` (both at 9.0, taken in plan order: water damage then fire damage), one `service-area`, and `/contact/`. No `service-area` entry has `primary: true`, and the business city (Auburn, MA) has no service-area page of its own because it is the homepage's target city, so the rule fell through to the first area slug in plan order, `/service-areas/worcester-ma/`.
- The DataForSEO MCP server in this environment exposes only `api_request` and the `docs_*` tools, with no `on_page_lighthouse` or `on_page_instant_pages` wrapper, so the audit called `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` directly over REST using the `DATAFORSEO_USERNAME` and `DATAFORSEO_PASSWORD` environment credentials. `for_mobile: false` was sent explicitly to match the documented System 3 desktop baseline. The REST path does accept `for_mobile: true`, so a mobile baseline can be added whenever the team wants one. Following the prorestoration run, no `categories` field was sent.
- One diagnostic `instant_pages` call was made against `/blog/`, outside the 6-URL audit set, purely to isolate the `has_micromarkup_errors` signal to the `FAQPage` node. It is not counted in `audited_urls` and cost $0.00045.
- Total run cost: $0.03315 (6 Lighthouse at $0.005, 7 instant_pages at $0.00045). Well under the $0.30-0.50 target.
- Checks that passed cleanly across all 6 URLs and are worth recording as the baseline: no broken internal or external links, no broken resources, no 4xx or 5xx, no mixed content (zero `http://` references in any page), no duplicate titles, no duplicate descriptions, no duplicate or missing H1, 100 percent image alt coverage (42 of 42 images), all titles between 57 and 65 characters, all meta descriptions between 103 and 140 characters, and every page clearing its `url-plan.json` `target_word_count` with room to spare (`/` 1678 against 1200, `/services/` 935 against 800, water damage 1743 against 1100, fire damage 1655 against 1100, Worcester 1270 against 900, `/contact/` 681 against 400).
- Security headers on the staging origin are in good shape: `strict-transport-security: max-age=31536000; includeSubDomains`, `content-security-policy: frame-ancestors`, `permissions-policy` locking geolocation, microphone and camera, `referrer-policy: strict-origin-when-cross-origin`, and `x-content-type-options: nosniff`. Confirm these carry over to the apex Pages deployment at cutover.
- `robots.txt` and `/sitemap-index.xml` both serve 200 and the sitemap reference already points at the apex (`https://qualitycontracting.us/sitemap-index.xml`). `/sitemap.xml` returns 404, which is expected given the index-style sitemap. All three planned `legal` pages (`/privacy/`, `/terms/`, `/accessibility/`) serve 200.
- Minor, not scored by any tool and not worth its own action item: the dark-background logo is emitted as `<img src="/images/logo-dark-bg.png" class="h-16 md:h-20 w-auto" width="48" height="48">` on the service-landing template. The declared 48x48 does not match either the rendered height or the file's aspect ratio. Lighthouse's `unsized-images` passes because the attributes are present, but the wrong intrinsic ratio can reserve the wrong box during load. Worth correcting whenever that template is next touched.
- `/services/water-damage-restoration/` and `/services/fire-damage-restoration/` do not appear in `image-delivery-insight` because they use service-specific hero images (`/images/services/water-damage-restoration.webp`) rather than the shared 178KB `/brand/hero.webp`. Those two pages are the model the other templates should follow on image sizing.
