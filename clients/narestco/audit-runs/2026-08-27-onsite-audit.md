# Onsite Audit - National Restoration Construction - 2026-08-27

**Live origin audited:** https://narestco.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-07-15
**Form factor:** desktop only (Lighthouse 13.4.0, cpuSlowdownMultiplier=1). Mobile scores would typically land 10-20 performance points lower.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 97.7 | -0.8 |
| Accessibility | 100 | 0 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

The site is held at amber by a single unresolved item: the homepage meta description is 194 characters, over the 160 character limit. This is the same item that held the site at amber in the 2026-07-15 audit. Everything else is green.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 97 | 100 | 100 | 100 | 1.29s | 0.007 |
| `/services/` | services-hub | green | 99 | 100 | 100 | 100 | 1.03s | 0.003 |
| `/services/water-damage-restoration/` | service-landing | green | 98 | 100 | 100 | 100 | 1.13s | 0.005 |
| `/services/fire-damage-restoration/` | service-landing | green | 98 | 100 | 100 | 100 | 1.15s | 0.005 |
| `/service-areas/seattle-wa/` | service-area | green | 100 | 100 | 100 | 100 | 0.57s | 0.004 |
| `/contact/` | contact | green | 94 | 100 | 100 | 100 | 1.63s | 0.006 |

Total blocking time was 0 ms on all six pages. Accessibility, best practices and SEO are perfect across the board. No broken internal links, no broken external links, no broken resources, no mixed content, exactly one H1 per page, self-referencing canonicals correct on all six, and valid schema on every page (LocalBusiness plus FAQPage and BreadcrumbList on the inner pages, Organization and WebSite on home, contact and the services hub, Service on both service landings).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `unused-javascript` | 6 | medium | Two separate `gtag/js` bundles load on every page: GA4 `G-5N8L5D4Z3C` (~154KB, 70KB unused) and Google Ads `AW-16824131335` (~147KB, 63KB unused). Load one `gtag.js` and register both IDs with a second `gtag('config', ...)` call. Removes roughly 147KB of duplicate JS per page. |
| `image-delivery-insight` | 6 | low | Serve display-sized variants. `logo.webp` wastes 81KB on home and contact by shipping a full-size asset into a small box; `hero-bg.webp` wastes 68KB on home. |
| `network-dependency-tree-insight` | 6 | low | Critical path chains through the render-blocking Astro CSS before the hero image request starts. Preload the hero and the route CSS. |
| `has_render_blocking_resources` | 6 | low | One render-blocking stylesheet and one render-blocking script per page. On contact this is `/_astro/_slug_.ChW6z_CF.css` (8.6KB, 52ms). Small, but it is the item gating LCP discovery. |
| `no_image_alt` | 6 | low | Flagged by DataForSEO in the rendered DOM only. Static HTML alt coverage was independently verified at 100 percent on all six pages. Treat as a detection artifact, not a defect. See caveats. |
| `cache-insight` | 5 | low | Third-party assets with short TTLs: the Supabase-hosted branding logo (1h) and `clarity.js` (24h). Both are off-origin, so this is not directly fixable. The one that is: `images.narestco.com/brand/hero.webp` at a 4h TTL - raise it in the R2 custom-domain cache rule. |
| `low_content_rate` | 3 | low | Text-to-HTML ratio under 10 percent on home (8.8 percent), services hub and contact. Driven by markup weight, not thin content: all six pages exceed their url-plan word targets. |

## Money page alerts

- **`/`** - verdict: amber. Performance 97, LCP 1.29s, all four categories at or above 97. The only thing holding it amber is the meta description at 194 characters. This is a one-line content fix, not a technical problem.

## Regressions vs prior audit

**Verdict transitions:** none. Every URL present in both runs held its prior verdict.

**Category regressions:** none. No Lighthouse category dropped 5 or more points on any URL. Site average performance moved -0.8, well inside the 3 point flag threshold.

**Core Web Vitals regressions:**
- `/contact/` LCP went from 1147ms to 1625ms, a 478ms regression (threshold is 200ms). The LCP element is `<img src="https://images.narestco.com/brand/hero.webp" loading="eager">` rendered into a 1350x276 box. Lighthouse reports 156KB of waste on that asset and the `lcp-discovery-insight` checklist fails `priorityHinted` - the image has no `fetchpriority="high"`. Performance still scored 94, so this is a slip to watch, not a failure.

**New issues this month:**
- `/contact/`: `low_content_rate` - text-to-HTML ratio fell under 10 percent. Contact is at 728 words against a 400 word url-plan target, so the content itself is fine; the ratio moved because of markup weight.

That is the only genuinely new issue. 31 further issue IDs appear as "new" in the state file and are all flagged `detection_artifact: true` - see caveats for why.

**Issues resolved since last audit:** (positive - keep doing this)
- `/services/`: `content_length_below_target` is no longer flagged. The hub is now at 801 words against its 800 word target.
- `/contact/`: `cumulative_layout_shift_borderline` is no longer flagged. CLS dropped from 0.028 to 0.006.

## Recommended next actions (priority order)

1. **(money page, one line)** Cut the homepage meta description from 194 to under 160 characters. Dropping only the trailing phone sentence is not enough, that still leaves 173. Replace the whole string with a tightened version, for example "24/7 water, fire, mold, and storm damage restoration in Federal Way, WA and nearby areas. Licensed, insured, IICRC-certified. Call (206) 883-0333." at 146 characters. This clears the single item holding the whole site at amber.
2. **(money page, LCP)** Add `fetchpriority="high"` to the contact hero `<img>` and serve a width-matched variant of `images.narestco.com/brand/hero.webp`. The asset is 221KB delivered into a 1350x276 box with 156KB of measured waste, and `lcp-discovery-insight` fails specifically on the missing priority hint. This is the direct cause of the 478ms LCP regression.
3. **(template, high impact)** Collapse the two `gtag/js` loads into one. GA4 `G-5N8L5D4Z3C` and Google Ads `AW-16824131335` each pull their own ~150KB bundle on all six pages. A single `gtag.js` with two `config` calls removes roughly 147KB of duplicate JavaScript site-wide.
4. **(template, low effort)** Rebuild `logo.webp` at its rendered display size. It wastes 81KB on home and 81KB on contact, and it is in the critical path on both.
5. **(content gap, not technical)** There is no service-area page for Federal Way, the client's own headquarters city. `/service-areas/federal-way-wa/` 301-redirects to the homepage and is absent from the sitemap. The city appears in every page title and in the LocalBusiness schema, but has no landing page of its own. Worth raising with whoever owns the url-plan.

## Notes / caveats

- **Service-area slot changed this month.** `/service-areas/federal-way-wa/`, audited in the three prior runs, now returns 301 to the homepage and does not appear in `sitemap-0.xml`. It was confirmed as a redirect: the instant-pages crawl of that URL returned the homepage title, description, canonical (`https://narestco.com/`) and word count byte for byte. Per the url-plan fallback rule it was replaced with `/service-areas/seattle-wa/`, the first area slug in `url-plan.json`. That URL scored a clean 100/100/100/100. The prior run's "green" for federal-way was almost certainly the homepage measured through the redirect, so its history is not meaningful.
- **The "new issues" list is dominated by detection changes, not site changes.** Two things widened detection this run. First, the prior audit deferred Lighthouse `full_data`, so it recorded zero `lighthouse_issues`; this run captured them, which makes every Lighthouse audit ID look new. Second, the dedicated `on_page_lighthouse` and `on_page_instant_pages` MCP wrappers are not exposed in this DataForSEO MCP server build, so the run called `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` directly with `enable_javascript`, `enable_browser_rendering` and `load_resources` on. That broader profile is what surfaced `no_image_alt` and `high_loading_time`. All 31 affected entries carry `detection_artifact: true` in the state file. Only one issue, `low_content_rate` on `/contact/`, is a real new finding.
- **`no_image_alt` is a false positive.** DataForSEO flags it on all six pages, but static HTML was independently checked and alt coverage is 100 percent everywhere (16/16 on home, 25/25 on the services hub, 3/3 on water, 3/3 on fire, 2/2 on Seattle, 3/3 on contact). It is recorded at low severity so it does not distort verdicts. Most likely source is a JS-injected tracking pixel in the rendered DOM.
- **`high_loading_time` on `/services/water-damage-restoration/` is not trusted.** The instant-pages crawl sampled 1299ms TTI and 4044ms dom_complete on that page, but the full Lighthouse run on the same URL minutes later returned performance 98 with LCP 1132ms and TBT 0. The same flag also fired on the federal-way redirect, which is the homepage. Both readings look like crawler-side variance rather than a page defect, so it is recorded at low severity. Worth re-checking next month.
- **Desktop only.** The DataForSEO Lighthouse endpoint was called with `for_mobile: false` to stay comparable with the three prior desktop runs. Mobile scores are not covered by this audit and would run materially lower.
- Run cost: 7 Lighthouse calls plus 7 instant-pages calls, approximately $0.05 total.
