# Onsite Audit - National Restoration Construction - 2026-09-28

**Live origin audited:** https://narestco.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-27
**Form factor:** desktop only (Lighthouse 13.4.0, cpuSlowdownMultiplier=1). Mobile scores would typically land 10-20 performance points lower.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 97.2 | -0.5 |
| Accessibility | 94.7 | -5.3 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

The site is still amber for the same reason as the last two audits: the homepage meta description is 194 characters (limit 160). The new problem this month is accessibility. It dropped from 100 on every page to 92-96 on every page, because of a contrast failure in the shared footer. Every page is still above 90, so no verdict changed, but this is a real site change. Lighthouse is on the same version (13.4.0), so a scoring-rule change does not explain it.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 98 | 92 | 100 | 100 | 1.12s | 0.005 |
| `/services/` | services-hub | green | 96 | 95 | 100 | 100 | 1.39s | 0.004 |
| `/services/water-damage-restoration/` | service-landing | green | 95 | 95 | 100 | 100 | 1.33s | 0.010 |
| `/services/fire-damage-restoration/` | service-landing | green | 97 | 95 | 100 | 100 | 1.16s | 0.006 |
| `/service-areas/seattle-wa/` | service-area | green | 98 | 95 | 100 | 100 | 1.05s | 0.005 |
| `/contact/` | contact | green | 99 | 96 | 100 | 100 | 0.93s | 0.033 |

Total blocking time was 69 ms or less on every page. Best practices and SEO are 100 everywhere. No broken internal links, no broken external links, no broken resources and no mixed content. Every page has exactly one H1, a correct self-referencing canonical, a title between 46 and 50 characters, and all pages except the homepage have meta descriptions between 121 and 141 characters.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 6 | medium | The footer license link (`<a href="https://secure.lni.wa.gov/verify/">`) renders at `#f0c1bd` on the white footer, a 1.6:1 contrast ratio (4.5:1 needed). The link has no color class, so it inherits the global `a { @apply text-primary-200 }` rule in `sites/narestco/src/styles/global.css`, which was designed for dark sections. Add `text-navy-900/70` (the color of the surrounding footer text) to the anchor in `sites/narestco/src/components/Footer.astro` line 114. Fixing this one line should bring accessibility back to 100 on 4 pages (services hub, water, fire, contact). The homepage and Seattle page each have one more failure, listed below. |
| `unused-javascript` | 6 | medium | Only one `gtag/js` bundle loads now (GA4 `G-5N8L5D4Z3C`, 159KB, 69KB unused). The duplicate Google Ads bundle flagged last month is gone. What is left is the base cost of GA4. The only further fix is to load gtag after first interaction or through Partytown. Low priority. |
| `image-delivery-insight` | 6 | low | `images.narestco.com/brand/hero.webp` is served full-size into short hero boxes: 163KB waste on contact, 129KB on the services hub, 104KB on Seattle. On the homepage it is `/images/hero-bg.webp` (68KB waste). Serve width-matched `srcset` variants (the `hero-480w.webp` variant already exists on R2). |
| `has_render_blocking_resources` | 6 | low | One render-blocking Astro stylesheet per page. It is small, but it sits in front of hero image discovery. Inline critical CSS for the header and hero. |
| `lcp-discovery-insight` | 5 | low | Every hero `<img loading="eager">` is missing `fetchpriority="high"` (the `priorityHinted` check fails on all 5 inner pages). Add it to the hero `<img>` markup. |
| `cache-insight` | 4 | low | `images.narestco.com/brand/hero.webp`, `hero-480w.webp` and `logo.png` are served with a 4h TTL. Raise it to 30 days or more in the R2 custom-domain cache rule. `clarity.js` (24h) is third-party and cannot be fixed on our side. |
| `low_content_rate` | 3 | low | Text-to-HTML ratio is under 10 percent on the homepage, services hub and contact page. This comes from markup weight, not thin copy. Informational only. |
| `largest-contentful-paint` | 2 | low | LCP metric score below 0.9 on the services hub (1.39s) and water landing (1.33s). Both are still well under 2.5s. Fixed by the `fetchpriority` and width-matched hero changes above. |

## Money page alerts

- **`/`** - verdict: amber. Performance 98, accessibility 92, LCP 1.12s. It is held amber by the meta description at 194 characters. This is the third audit in a row with this finding (2026-07-15, 2026-08-27, 2026-09-28). Accessibility is 92 instead of 95 because the homepage has a second failure, `link-in-text-block`: the service-area city links in a paragraph inside the dark `section.bg-dark` block (for example `<a href="/service-areas/tacoma-wa/">`) are `#f0c1bd` against `#cfd1d4` body text (1.05:1) and have no underline.

## Regressions vs prior audit

**Verdict transitions:** none. Every URL kept its prior verdict.

**Category regressions (5-point drop or more):**
- Accessibility dropped on 5 URLs: `/` 100 to 92, `/services/` 100 to 95, `/services/water-damage-restoration/` 100 to 95, `/services/fire-damage-restoration/` 100 to 95, `/service-areas/seattle-wa/` 100 to 95. `/contact/` dropped 100 to 96, just under the flag threshold. The site average fell 5.3 points, over the 3-point site flag. The common cause is the footer license link contrast described above. The footer license link to the WA L&I verify page was added to this site around 2026-09-23 and has been live since then.

**Core Web Vitals regressions:**
- `/service-areas/seattle-wa/` LCP went from 574ms to 1053ms (+479ms). The LCP element is `images.narestco.com/brand/hero.webp`, with no priority hint and 104KB of measured waste. At 1.05s it is still fast. Last month's 574ms looks like an unusually good sample, but the hero fix will help either way.
- `/services/` LCP went from 1026ms to 1393ms (+367ms). Same hero asset: 129KB of waste, no `fetchpriority`, and resource load time of 386ms after a 303ms TTFB.
- `/contact/` CLS went from 0.0057 to 0.0333 (+0.028). The shift is in `section#estimate` and is caused by the late-loading Inter web font plus the footer logo. The footer logo `<img>` declares `width="48" height="48"`, but it renders at 372x80, so the browser reserves the wrong space for it. Still far under Google's 0.1 "good" line.

**Improvements worth noting:**
- `/contact/` LCP improved from 1625ms to 930ms (-695ms). Last month's LCP regression is resolved. Contact performance went from 94 to 99.
- The duplicate Google Ads `gtag/js` bundle (`AW-16824131335`) no longer loads. Only GA4 remains.

**New issues this month:**
- All 6 pages: `color-contrast` - footer license link at 1.6:1 contrast.
- `/service-areas/seattle-wa/`: `color-contrast` also fires on a `span.text-slate-400` inside a white card (`#94a3b8` on white, 2.56:1). Change `text-slate-400` to `text-slate-600` on that element.
- `/`: `link-in-text-block` - city links in the dark section rely on color alone.
- `/services/`: `content_length_below_target` - body copy is 785 words against the 800-word services-hub target (15 under). This was resolved last month at 801 words and has come back.
- `/services/` and `/services/water-damage-restoration/`: `largest-contentful-paint` metric below 0.9 (see CWV above).

The state file also lists 4 more "new" IDs (`lcp-discovery-insight` on water, fire and Seattle, and `cache-insight` on fire), each marked `detection_artifact: true`. These were already failing last month but fell outside that run's top-5 cut. They are not site changes.

**Issues resolved since last audit:** (positive - keep doing this)
- All 6 pages: `no_image_alt` is no longer flagged by DataForSEO. That finding was already confirmed as a false positive.
- `/services/water-damage-restoration/`: `high_loading_time` is no longer flagged.
- `/`: `forced-reflow-insight` is no longer flagged.

## Recommended next actions (priority order)

1. **(money page, one line)** Replace the homepage meta description (194 characters) with a version under 160. For example: "24/7 water, fire, mold, and storm damage restoration in Federal Way, WA and nearby areas. Licensed, insured, IICRC-certified. Call (206) 883-0333." (146 characters). This is the only thing keeping the whole site amber, and it is now three audits old.
2. **(template, high impact)** Add `text-navy-900/70` to the license `<a>` in `sites/narestco/src/components/Footer.astro` (line 114), so it stops inheriting the pale `text-primary-200` global link color on the white footer. This one change should clear `color-contrast` on all 6 pages and bring 4 of them back to 100 accessibility.
3. **(money page)** On the homepage, underline the service-area city links in the `section.bg-dark` paragraph (add `underline` to those anchors) to clear `link-in-text-block`. On the Seattle page, change the card's `text-slate-400` span to `text-slate-600`.
4. **(template, LCP)** Add `fetchpriority="high"` to the hero `<img>` in the hero markup, and serve `images.narestco.com/brand/hero.webp` through a `srcset` that includes the existing `hero-480w.webp` plus a roughly 1400w variant. This fixes `lcp-discovery-insight` on 5 pages and brings back the LCP lost on `/services/` and `/service-areas/seattle-wa/`.
5. **(per-page, contact CLS)** Change the footer logo `<img>` in `Footer.astro` line 17 from `width="48" height="48"` to the real aspect ratio (about `width="372" height="80"`, matching the h-16/h-20 render), and add `font-display: swap` with a size-adjusted fallback for Inter. This clears the `/contact/` CLS increase. While editing the hub, add about 30 words to `/services/` so it is back over its 800-word target.

## Notes / caveats

- **Desktop only.** The DataForSEO Lighthouse endpoint was called with `for_mobile: false`, the same as the four prior desktop runs, so scores are comparable. Mobile is not covered by this audit.
- **Endpoint profile unchanged.** The dedicated `on_page_lighthouse` and `on_page_instant_pages` MCP wrappers are not exposed in this DataForSEO MCP server build. As on 2026-08-27, this run called `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` directly, with `enable_javascript`, `enable_browser_rendering` and `load_resources` on. Detection is comparable month over month.
- **URL set unchanged.** Water and fire damage restoration are still tied for top service-landing priority (9.0) in `url-plan.json`, together with mold remediation and roofing. They were kept for continuity. `/service-areas/federal-way-wa/` still 301-redirects to the homepage, and no area has `primary: true`, so `/service-areas/seattle-wa/` (the first area slug) is still the service-area slot. There is still no Federal Way landing page for the client's headquarters city.
- **Checks not recorded.** DataForSEO also flagged `no_image_title` (images without a `title` attribute) on all 6 pages and `frame` (the Google Maps embed) on the Seattle page. Neither is in the audit rubric and neither affects SEO or accessibility, so they are not recorded as issues.
- **No site changes made.** This audit only records findings. The fixes above need to be made in `sites/narestco/` and deployed separately.
- Run cost: 6 Lighthouse calls plus 6 instant-pages calls, about $0.06 total.
