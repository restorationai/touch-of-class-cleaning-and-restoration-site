# Onsite Audit - RestorationXpress - 2026-09-29

**Live origin audited:** https://restorationxpress.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-28
**Form factor:** desktop only (Lighthouse 13.4.0)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.3 | -1.2 |
| Accessibility | 94.7 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | 0.0 |

Pages by verdict: green: 1, amber: 5, red: 0, error: 0

Headline: the site is still in very good technical shape, and nothing moved to red. However, **none of the five fixes recommended last month have shipped**. The same BreadcrumbList schema error keeps five of six pages amber, and the brand-colour contrast, oversized logo, and missing `fetchpriority` findings are all unchanged. The one new thing is Google Analytics 4 (`gtag.js`, property `G-YMWBHG8Y4F`), which now loads on every page. It accounts for the new `unused-javascript` finding and most likely for the new `forced-reflow-insight` finding. It is also the most likely reason LCP rose 200-360ms on three pages. LCP is still around 1 second everywhere, well inside the 2.5s "good" threshold.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT | Words |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 98 | 96 | 100 | 100 | 1.06s | 0.004 | 0ms | 1561 |
| `/services/` | services-hub | amber | 98 | 95 | 100 | 100 | 1.14s | 0.002 | 0ms | 783 |
| `/services/water-damage-restoration/` | service-landing | amber | 99 | 95 | 100 | 100 | 0.94s | 0.003 | 0ms | 1853 |
| `/services/fire-damage-restoration/` | service-landing | amber | 98 | 95 | 100 | 100 | 1.00s | 0.005 | 0ms | 1593 |
| `/service-areas/fort-lauderdale-fl/` | service-area | amber | 99 | 95 | 100 | 100 | 0.89s | 0.003 | 0ms | 1427 |
| `/contact/` | contact | amber | 98 | 92 | 100 | 100 | 1.06s | 0.005 | 18ms | 728 |

INP was not returned (lab run, no field data) and is recorded as null.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 6 | high | Unchanged from last month. White on brand primary `#719430` (and `#719430` on white) is 3.51:1, below the 4.5:1 AA floor. It fails on the top notice bar, the header "CALL US NOW" button, the "24/7 EMERGENCY LINE" label, the CTA-band "Call" button, and the footer phone and email links. Darken `primary-600` to about `#5A7726`. Also new in the node list this month: the breadcrumb "HOME" link (`text-dark/50`, `#888c93` on white, 3.37:1). Change it to `text-dark/70` or darker. |
| `image-delivery-insight` | 6 | high | Unchanged. `/images/logo.png` is a 158,570-byte 1000x429 PNG displayed at about 149x64 in the header and 186x80 in the footer, so 156KB is wasted on every page. Export a 372x160 WebP (2x of the footer size) and use it in both places. On `/services/` and `/contact/` the hero `hero-bg.webp` (218KB) also has no `srcset`, so another 127-170KB is wasted. Reuse the home hero's `srcset`/`sizes` markup. |
| `unused-javascript` | 6 | medium | **New.** `googletagmanager.com/gtag/js?id=G-YMWBHG8Y4F` is 159KB, and 69KB of it goes unused on each page. Keep GA4 but load it after the page becomes interactive: inject the gtag `<script>` from a `requestIdleCallback` (or a `load` listener) instead of in `<head>`. Alternatively, run it off the main thread with Partytown (`@astrojs/partytown`). |
| `has_micromarkup_errors` | 5 | medium | Unchanged. It is the sole cause of the amber verdict on 5 of 6 pages. The last `ListItem` in the `BreadcrumbList` JSON-LD (for example `{"position":2,"name":"Contact"}`) has no `item`. Add the current page's canonical URL as `item` in the breadcrumb component. |
| `lcp-discovery-insight` | 5 | medium | Unchanged. The hero `<img>` on the hub, landing, area, and contact layouts has `loading="eager"` but no `fetchpriority="high"`. The home layout already has it, so copy that attribute over. |
| `forced-reflow-insight` | 5 | low | **New.** 45-65ms of unattributed forced reflow. It appeared at the same time as GA4, and deferring gtag (see `unused-javascript`) should clear it. Re-check next month before investigating further. |
| `render-blocking-insight` / `has_render_blocking_resources` | 6 | low | `_astro/_slug_.Ds6AEepO.css` (8.8KB) blocks render for 0-54ms. Optional. |
| `cache-insight` | 6 | low | This is Cloudflare's injected `email-decode.min.js`, not our build. No action. |
| `network-dependency-tree-insight` | 6 | low | Critical chain is short and healthy. No action. |
| `no_image_title` | 6 | low | Alt-text coverage is 100 percent, and `title` is not required. Informational only. |
| `low_content_rate` | 2 | low | Low text-to-HTML ratio on `/` and `/contact/`. This is a DataForSEO informational check, and both pages meet their word-count targets. No action. |

## Money page alerts

- **`/services/`** (services-hub) - verdict amber. BreadcrumbList schema error, accessibility 95, 312KB of avoidable image bytes, hero missing `fetchpriority="high"`. LCP rose from 0.92s to 1.14s.
- **`/services/water-damage-restoration/`** (service-landing) - verdict amber. BreadcrumbList schema error, accessibility 95, 181KB of avoidable image bytes (the logo alone is 156KB).
- **`/services/fire-damage-restoration/`** (service-landing) - verdict amber. BreadcrumbList schema error, accessibility 95, 176KB of avoidable image bytes. LCP rose from 0.65s to 1.00s.
- **`/contact/`** (contact) - verdict amber. BreadcrumbList schema error. Accessibility is 92, the lowest on the site, because the body-copy `mailto:issac@restorationxpress.com` link is still distinguished by colour alone (`#b91c1c` vs `#374151`, 1.59:1, no underline). 318KB of avoidable image bytes. LCP rose from 0.69s to 1.06s.

## Regressions vs prior audit

**Verdict transitions:** none. Every page kept the verdict it had on 2026-08-28 (home green, the other five amber).

**Score regressions (5+ point drop):** none. Performance slipped 1-2 points on four pages and the site average fell 1.2 points, which is below the 3-point site-level flag threshold.

**Core Web Vitals regressions (LCP +200ms or more):**
- `/contact/`: LCP 693ms to 1055ms (+362ms)
- `/services/fire-damage-restoration/`: LCP 646ms to 1000ms (+354ms)
- `/services/`: LCP 924ms to 1141ms (+217ms)

All three pages are still well under the 2.5s "good" threshold. The likely cause is the 159KB GA4 script competing with the hero image for bandwidth. The hero image itself is unchanged. CLS and TBT did not regress anywhere.

**New issues this month:**
- All 6 pages: `unused-javascript`. 66-69KB of unused code in the newly added GA4 `gtag.js`.
- `/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`, `/service-areas/fort-lauderdale-fl/`, `/contact/`: `forced-reflow-insight`, 45-65ms of unattributed reflow.
- `/contact/`: `low_content_rate` (informational; word count 728 vs a target of 400).

**Issues resolved since last audit:**
- `/services/fire-damage-restoration/`: `high_loading_time` is no longer flagged. Last month's one-off 5.1s crawl fetch did not recur (load time 89ms this run).

**Carried over unfixed from last month:** all five recommended actions. The same issue IDs (`has_micromarkup_errors`, `color-contrast`, `image-delivery-insight`, `link-in-text-block`, `lcp-discovery-insight`) are still present on the same pages.

## Recommended next actions (priority order)

1. **(money page, accessibility)** On `/contact/`, add `text-decoration: underline` to links inside `.prose-body`. This clears `link-in-text-block` on the mailto link and lifts the lowest-scoring money page. It is a one-line CSS change and was the top item last month too.
2. **(template, schema)** In the breadcrumb component, add `"item": <canonical URL>` to the final `ListItem` of the `BreadcrumbList` JSON-LD. This is the only medium on-page issue on the site, and fixing it moves `/services/`, both service landings, the service-area page, and `/contact/` from amber to green.
3. **(template, new this month)** Defer GA4. Move the `gtag/js?id=G-YMWBHG8Y4F` loader out of `<head>` and inject it on `requestIdleCallback`/`window.load`, or route it through `@astrojs/partytown`. That removes 69KB of unused main-thread JS per page and should undo this month's LCP drift on `/contact/`, `/services/`, and the fire-damage page.
4. **(template, high impact bytes)** Replace `/images/logo.png` (158KB PNG) with a roughly 372x160 WebP in both the header and footer, which saves about 156KB per page load. In the same change, give the `/services/` and `/contact/` hero `<img>` the home hero's `srcset`/`sizes` and add `fetchpriority="high"` to every non-home hero.
5. **(template, accessibility)** Darken brand primary `#719430` to about `#5A7726` wherever it is used as text on white or behind white text: the notice bar, the "CALL US NOW" button, the CTA band, and the footer phone and email. Also change the breadcrumb "HOME" link from `text-dark/50` to `text-dark/70`.

## Notes / caveats

- **Desktop only.** Lighthouse ran with `formFactor=desktop`, `cpuSlowdownMultiplier=1`, and `throughputKbps=10240`. Mobile scores typically run 10-20 performance points lower and were not measured. A 159KB analytics script matters far more on throttled mobile, which is another reason to prioritise item 3.
- **Client record status.** `clients/restorationxpress.json` still reads `status: "onboarding"`, the same as last month. The audit proceeded because `build_status` is `pushed_main` and the apex cutover completed on 2026-08-04. The ops owner should flip status to `active`.
- **Services hub word count.** `/services/` has 783 words against a url-plan target of 800. That is only 17 words short, unchanged from last month, and DataForSEO has no native check for it. It is recorded in the state file caveats, not as an issue.
- **No broken links, broken resources, mixed content, or redirect problems** on any of the 6 URLs. Canonicals are present and self-referencing on every page, and titles (48-63 chars) and meta descriptions (104-139 chars) are all within range. Security headers are unchanged and healthy: HSTS, `X-Content-Type-Options`, Referrer-Policy, Permissions-Policy, and CSP `frame-ancestors`.
- **Asset hash changed** from `_slug_.CuEjtIRd.css` to `_slug_.Ds6AEepO.css`, so the site has been rebuilt since last month. The rebuilds did not include any of the recommended fixes.
- Run cost: about $0.03 (6 Lighthouse + 6 instant_pages calls via the DataForSEO API with `for_mobile: false`).
