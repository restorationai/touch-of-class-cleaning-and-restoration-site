# Onsite Audit - Air Care Restoration - 2026-09-28

**Live origin audited:** https://aircarerestoration.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 98 | 0 |
| Accessibility | 96 | +1 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0 (last month: green 2, amber 4)

This month is better overall. Three pages moved from amber to green, the homepage CLS problem is fixed (0.157 down to 0.003), the homepage now scores 100 on accessibility, and the `high_loading_time` crawler flag is gone from all four pages that had it. The only thing keeping the site amber is the homepage meta description, which is still 177 characters. Every page returns 200 and scores 95 or higher in all four categories.

Two things are new and worth attention. A Google Analytics 4 tag (`gtag.js?id=G-FW5QLBCH24`, 159 KB) has been added since last month and now shows up as `unused-javascript` on all six pages. LCP also went up on four pages, though every LCP is still under 1.4s (the "good" threshold is 2.5s).

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 96 | 100 | 100 | 100 | 1.34s | 0.003 | 52ms |
| `/services/` | services-hub | green | 98 | 95 | 100 | 100 | 1.07s | 0.029 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 97 | 95 | 100 | 100 | 1.10s | 0.025 | 86ms |
| `/services/fire-damage-restoration/` | service-landing | green | 98 | 95 | 100 | 100 | 1.06s | 0.025 | 6ms |
| `/service-areas/sweetwater-tx/` | service-area | green | 98 | 95 | 100 | 100 | 0.96s | 0.009 | 18ms |
| `/contact/` | contact | green | 98 | 96 | 100 | 100 | 1.06s | 0.066 | 53ms |

INP returned null on all six URLs because the lab run does not simulate any interaction.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | Not fixed from last month. `/images/logo.png` is still a 180 KB PNG, 878x500 intrinsic, shown at 169x96 in the header (and at 140x80 in the footer). It wastes 177 KB on every page. Export `logo-192w.webp` and `logo-384w.webp`, add `srcset`/`sizes`, and fix the `width`/`height` attributes on both the header and footer `<img>` tags. |
| `unused-javascript` | 6 | medium | New this month. `https://www.googletagmanager.com/gtag/js?id=G-FW5QLBCH24` is 159 KB, and about 69 KB of it (44 percent) goes unused. It also costs 56 to 88ms of main-thread time per page. Load it after the page is interactive (see action 3). |
| `color-contrast` | 5 | high | Much better: down from 35 failing elements last month to 13. The accent-orange eyebrow text is fixed. Three patterns are left: breadcrumb links using `text-dark/50` (all 5 inner pages), white text on `.btn-accent` (the hero "Call" button on both service landings and the service-area page, plus the service-area CTA), and one `span.text-slate-400` on the service-area template. |
| `lcp-discovery-insight` | 5 | medium | Not fixed from last month. The shared inner-page hero `<img>` is still `<img src="..." class="w-full h-full object-cover" loading="eager">`, with no `fetchpriority="high"`, no `srcset` and no `decoding="async"`. The homepage hero already has all three. |
| `forced-reflow-insight` | 3 | medium | New this month. Unattributed forced reflow takes 40ms on `/services/`, 68ms on the fire landing and 210ms on `/contact/`. It appeared in the same month as the GA4 tag, which is the only new script on the page. Check again after deferring gtag. |
| `render-blocking-insight` / `has_render_blocking_resources` | 6 | low | `/_astro/_slug_.DWEqrGuE.css` is 9 KB and costs 30 to 61ms. The render-blocking duplicate Google Fonts stylesheet from last month is also still in the `<head>` (see action 4). |
| `low_content_rate` | 3 | low | This is a text-to-HTML ratio flag on `/`, `/services/` and `/contact/`. Every page is above its word-count target, so no content action is needed. |
| `cache-insight` | 6 | low | The only short-TTL resource is Cloudflare's injected `email-decode.min.js` (949 bytes). This is not ours to fix. |
| `network-dependency-tree-insight` | 6 | low | This is flagged on the shape of the dependency tree, not on latency. No action. |
| `no_image_title` | 6 | low | Images have no `title` attribute. This is not an SEO or accessibility requirement, and alt coverage is 100 percent. No action. |

## Money page alerts

- **`/` (home)** verdict: amber. Performance 96, accessibility 100, CLS 0.003 (fixed). The only reason it is amber is the meta description, which is still 177 characters and will be truncated in search results. LCP went from 0.65s to 1.34s. It is still well within "good", but it is the biggest LCP increase this month. The LCP breakdown is TTFB 198ms, resource load 173ms and render delay 223ms.

## Regressions vs prior audit

**Verdict transitions:** none in the bad direction. Three improvements:
- `/services/` went amber to green (`high_loading_time` cleared).
- `/services/water-damage-restoration/` went amber to green (`high_loading_time` cleared).
- `/services/fire-damage-restoration/` went amber to green (`high_loading_time` cleared).

**Category scores:** no URL dropped 5 or more points in any category. The largest drop was water damage performance, from 100 to 97.

**Core Web Vitals regressions (above threshold):**
- `/`: LCP +692ms (650ms to 1342ms).
- `/services/water-damage-restoration/`: LCP +460ms (643ms to 1103ms).
- `/services/fire-damage-restoration/`: LCP +226ms (834ms to 1060ms).
- `/contact/`: LCP +277ms (784ms to 1061ms), and CLS +0.037 (0.029 to 0.066). Lighthouse attributes 0.065 of that shift to `section#estimate`, the estimate form section. It names two causes. The first is an unsized image: the lazy-loaded footer logo `<img src="/images/logo.png" class="h-16 md:h-20 w-auto mb-6" width="48" height="48" loading="lazy">`, whose declared 1:1 box does not match the real 1.756:1 image. The second is the Poppins and Anton web font swap. This is still under the 0.10 threshold, but it is heading the wrong way on the conversion page.

LCP went up on every page, and GA4 arrived in the same month, so gtag competing with the hero image for bandwidth and main thread is the most likely cause. Some of it is also normal run-to-run lab variance on sub-1.5s numbers. See caveats.

**New issues this month:**
- All 6 pages: `unused-javascript`. The GA4 gtag.js has about 69 KB unused.
- `/services/`, `/services/fire-damage-restoration/`, `/contact/`: `forced-reflow-insight`, taking 40ms, 68ms and 210ms.
- `/`: `largest-contentful-paint`. Lighthouse gives the metric a score of 0.85 at 1.3s. That is below its "passing" line but still inside Google's "good" threshold.
- `/services/`, `/contact/`: `low_content_rate`. This is a text-to-HTML ratio flag and not a content problem.

**Issues resolved since last audit:** (positive, keep doing this)
- `/`: `cumulative-layout-shift`, `layout-shifts` and `cls-culprits-insight` are all cleared. The homepage hero copy block no longer reflows, and CLS dropped from 0.157 to 0.003.
- `/`: `color-contrast` is cleared, and accessibility is now 100.
- `/`, `/services/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`: `high_loading_time` is cleared. Crawler `dom_complete` is now 278 to 1560ms on these pages, down from 3.3 to 3.7s.
- Sitewide: accent-orange text contrast (`.eyebrow`, `.text-accent`) is fixed, which took the contrast failures from 35 to 13.

## Recommended next actions (priority order)

1. **(money page)** Trim the homepage meta description to 160 characters or fewer. This is the only thing keeping the site amber. The current text is: "Air Care Restoration provides 24/7 water, fire, mold, and storm damage restoration across Abilene and surrounding areas. Licensed, insured, IICRC-certified. Call (325) 339-8723." Removing "Licensed, insured, " brings it to 158 characters. This is carried over from last month.

2. **(template, high impact)** Replace the logo, which is still unfixed from last month. `/images/logo.png` is 180 KB and wastes 177 KB on all six pages. Export WebP at `192w` and `384w`. Use `srcset="/images/logo-192w.webp 192w, /images/logo-384w.webp 384w"` with `sizes="(min-width: 768px) 192px, 160px"` on the header tag. Change `width="64" height="64"` on the header tag and `width="48" height="48"` on the footer tag to the real aspect ratio (for example `width="169" height="96"` and `width="140" height="80"`). Fixing the footer attributes also removes the "unsized image element" cause behind the `/contact/` CLS increase.

3. **(template, new this month)** Defer the GA4 tag. Right now `<script async src="https://www.googletagmanager.com/gtag/js?id=G-FW5QLBCH24">` sits in the `<head>` and starts downloading 159 KB in parallel with the hero image. Inject it after `window.load` (or inside `requestIdleCallback`), keeping the inline `gtag('config', ...)` stub so page_view is still recorded. A Partytown worker is another option. This should recover the 69 KB `unused-javascript` flag and most of the 56 to 88ms of main-thread time. It is also the most likely fix for this month's LCP increases and the new `forced-reflow-insight` on three pages. Re-audit next month to confirm.

4. **(template, LCP and fonts)** Bring the inner-page hero `<img>` up to homepage parity. Add `fetchpriority="high"`, `decoding="async"` and a responsive `srcset`/`sizes` to the shared hero on `/services/`, service landings, service areas and `/contact/`. This clears `lcp-discovery-insight` on 5 of 6 pages. In the same layout edit, delete the duplicate blocking `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Poppins:wght@400;500;600;700;800;900&display=swap">`, which is still present next to the async `media="print" onload` copy. Also recompress `/images/hero-bg.webp` (99 KB, with 50 KB recoverable per Lighthouse on `/contact/`). Both are carried over from last month.

5. **(template, accessibility)** Finish the contrast fixes, 13 elements in all. Change breadcrumb links from `text-dark/50` (`#8192ae`, 3.15:1) to `text-dark/70` (`#4e668e`, 5.81:1). Give `.btn-accent` a navy `#02255d` label on the orange background (5.10:1), or darken the background to `#c75201` and keep white text (4.53:1). Change the one `span.text-slate-400` on the service-area template to `text-slate-600`.

## What is already correct (do not regress these)

- **Schema:** all 24 JSON-LD blocks across the six pages parse cleanly. The home page has `Organization`, `WebSite` and `LocalBusiness`. `/services/` and `/contact/` have those three plus `FAQPage` and `BreadcrumbList`. Both service landings have `Service`, `LocalBusiness`, `FAQPage` and `BreadcrumbList`. Sweetwater has `LocalBusiness`, `FAQPage` and `BreadcrumbList`. DataForSEO's `has_micromarkup` check reads `false` on every page because it looks for inline microdata, not JSON-LD. This was confirmed by fetching and parsing the live HTML, and it is not a defect.
- **Titles and canonicals:** all titles are 54 to 61 characters. Every canonical is self-referencing and absolute. Every page has exactly one `h1`, and there are no duplicate titles or meta tags.
- **Links and resources:** there are zero broken links, zero broken resources, and zero HTTPS-to-HTTP links (no mixed content).
- **Image alt text:** `no_image_alt` does not fire on any page, so coverage is 100 percent.
- **Content depth:** every page is above its `url-plan.json` target. Home is at 1652 words against 1200, the services hub 851 against 800, water damage 1833 against 1100, fire damage 1928 against 1100, Sweetwater 1324 against 900, and contact 648 against 400.
- **Security headers:** HSTS (`max-age=31536000; includeSubDomains`), `x-content-type-options: nosniff`, CSP `frame-ancestors`, `permissions-policy` and `referrer-policy` are all present, and Best Practices is 100 on all six pages.

## Notes / caveats

- **Desktop only.** Lighthouse 13.4.0 ran with `formFactor: desktop`, `cpuSlowdownMultiplier: 1`, `throughputKbps: 10240`. Mobile scores usually come in 10 to 20 performance points lower, and the logo and GA4 costs will be larger on mobile. Do not read these numbers as mobile-first scoring. Desktop was kept so the results compare like-for-like with the August baseline.
- **LCP variance.** Each URL got one lab run. The LCP increases are consistent across pages and line up with the new GA4 tag, so they are worth acting on. But deltas of 200 to 700ms on LCPs under 1.5s are partly normal lab noise. Every LCP is still well inside Google's 2.5s "good" threshold.
- **`meta_description_too_long` is a Rank AI rule, not a native DataForSEO check.** It comes from `meta.description_length` measured against the 70 to 160 character target. The same ID was used last month so month-to-month tracking stays continuous.
- **Client record status is stale.** `clients/air-care-restoration.json` still reads `status: "onboarding"`, even though the apex cutover completed 2026-08-21 and the site is live on `pushed_main`. The audit ran on that basis. The field should be changed to `active`.
- **URL selection:** the URLs were auto-derived from `plan/url-plan.json`, since there is no `audit-urls.txt`. These are the same six URLs as August, for comparability. No service-area page has `primary: true`, and there is no Abilene area page, so the first area in the plan (`/service-areas/sweetwater-tx/`) was used. The plan has three service landings tied at priority 9.0. Water damage and fire damage were kept to match the baseline.
- **No URLs errored.** All 6 Lighthouse calls and all 6 instant-pages calls returned status 20000.
- **Run cost:** about $0.041 (6 Lighthouse live calls at $0.005 each and 6 instant-pages calls at $0.0018 each).
