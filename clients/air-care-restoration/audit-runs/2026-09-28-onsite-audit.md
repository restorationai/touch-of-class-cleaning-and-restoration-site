# Onsite Audit - Air Care Restoration - 2026-09-28

**Live origin audited:** https://aircarerestoration.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 97 | -1 |
| Accessibility | 96 | +1 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0 (August: green 2, amber 4)

Overall the site improved. Three money pages moved from amber to green because DataForSEO's `high_loading_time` flag cleared everywhere. WCAG contrast failures dropped from 35 elements to 13, and the homepage now scores 100 on accessibility. The one amber page is the homepage, and it got worse: performance fell from 93 to 88, and CLS rose from 0.157 to 0.204. A new Google Analytics 4 tag (`G-FW5QLBCH24`) now loads on every page and shows up as `unused-javascript`. None of the five actions from August have shipped yet except part of the contrast fix.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 88 | 100 | 100 | 100 | 1.02s | 0.204 | 0ms |
| `/services/` | services-hub | green | 99 | 95 | 100 | 100 | 1.04s | 0.030 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 98 | 95 | 100 | 100 | 0.99s | 0.025 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | green | 98 | 95 | 100 | 100 | 0.95s | 0.024 | 0ms |
| `/service-areas/sweetwater-tx/` | service-area | green | 99 | 95 | 100 | 100 | 1.00s | 0.006 | 0ms |
| `/contact/` | contact | green | 98 | 96 | 100 | 100 | 0.95s | 0.066 | 0ms |

INP returned null on all six URLs because the lab run simulates no interaction.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | Still the header logo: `/images/logo.png` is 176 KB at 878x500 intrinsic and renders at 169x96. It wastes 173 KB per page. Same fix as August (action 2 below). |
| `color-contrast` | 5 | high | Down to 13 elements from 35. What remains: breadcrumb links `a.text-dark/50` (#8b8b8c on white, 3.4:1), `.btn-accent` (white on #ff6901, 2.88:1) and one `span.text-slate-400` (2.56:1) on the service-area template. |
| `unused-javascript` | 6 | medium | **New this month.** `https://www.googletagmanager.com/gtag/js?id=G-FW5QLBCH24` is 156 KB, and 66 to 70 KB of it goes unused on first load. Lighthouse estimates 50 to 100ms of LCP savings. |
| `lcp-discovery-insight` | 5 | medium | Not fixed since August. The inner-page hero `<img>` still has no `fetchpriority="high"`. |
| `render-blocking-insight` | 6 | low | The Google Fonts stylesheet is still loaded twice, once async and once blocking. On `/services/` and `/service-areas/sweetwater-tx/` Lighthouse now puts a price on it: 50ms of FCP. |
| `forced-reflow-insight` | 2 | low | New on `/services/` and `/service-areas/sweetwater-tx/`. A script reads layout after a DOM write. It likely comes from the new gtag bootstrap or the mobile-nav script. Low priority. |
| `cache-insight` | 6 | low | Only Cloudflare's injected `email-decode.min.js` has a short cache lifetime. We don't control it, so no action. |
| `network-dependency-tree-insight` | 6 | low | This audit flags the shape of the request chain, not slow requests. No action. |
| `has_render_blocking_resources` | 6 | low | This is DataForSEO's version of the duplicate font stylesheet. Action 3 fixes it. |
| `no_image_title` | 6 | low | Images have no `title` attribute. That is not an SEO or accessibility requirement, and every image already has alt text. No action. |
| `low_content_rate` | 3 | low | DataForSEO's text-to-HTML ratio check. Word counts are above target on every page, so no action. |

## Money page alerts

- **`/` (home)** verdict: amber. Performance 88, LCP 1.02s, **CLS 0.204**. Google rates CLS above 0.10 as "needs improvement", and this is now closer to the 0.25 "poor" line. Lighthouse puts 0.2035 of the shift on one element: `main.flex-1 > header.relative > div.container-wide`, the hero copy block ("24/7 Restoration Services in Abilene"). It reflows when seven Poppins and Anton woff2 files arrive from `fonts.gstatic.com`. The CLS audit alone costs about 10 performance points. The meta description is still 177 characters, which is the medium on-page issue that also keeps this page amber.

## Regressions vs prior audit

**Verdict transitions (worsening):** none.

**Verdict improvements:**
- `/services/` amber to green (`high_loading_time` cleared: crawler dom_complete 3.40s down to 1.53s)
- `/services/water-damage-restoration/` amber to green (`high_loading_time` cleared: 3.43s down to 2.05s)
- `/services/fire-damage-restoration/` amber to green (`high_loading_time` cleared)

**Per-URL metric regressions:**
- `/`: performance 93 to 88 (-5). CLS 0.157 to 0.204 (+0.047). LCP 650ms to 1024ms (+374ms).
- `/services/water-damage-restoration/`: LCP 643ms to 990ms (+347ms). Performance still 98.
- `/contact/`: CLS 0.029 to 0.066 (+0.037). The main cause is the footer logo `<img src="/images/logo.png" class="h-16 md:h-20 w-auto" width="48" height="48" loading="lazy">`. Lighthouse flags it as an "unsized image element": it declares 48x48, but it renders at 140x80. When it loads, it shifts `section#estimate`, which holds the estimate form.

LCP went up by 110 to 170ms on the other four pages too, just under the 200ms flag threshold. The new gtag script plausibly explains this sitewide rise because it competes with the hero image for bandwidth. Lab variance is also possible.

**New issues this month:**
- All 6 URLs: `unused-javascript` (the gtag.js for GA4 property G-FW5QLBCH24)
- `/services/` and `/service-areas/sweetwater-tx/`: `forced-reflow-insight`
- `/services/` and `/contact/`: `low_content_rate` (informational)

**Issues resolved since last audit:** (positive, keep doing this)
- `/`: `color-contrast` is no longer flagged. The accent-orange eyebrow text and the `text-dark/50` / `text-dark/60` body and footer copy were fixed. Sitewide, failing contrast elements fell from 35 to 13.
- `/`, `/services/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`: `high_loading_time` is no longer flagged.

## Recommended next actions (priority order)

1. **(money page, Core Web Vitals)** Fix the homepage CLS of 0.204. It is the only thing keeping the site amber, and it got worse this month. Self-host Poppins (400, 600, 700, 800, 900) and Anton as same-origin woff2 files under `/fonts/`. Add `<link rel="preload" as="font" type="font/woff2" crossorigin>` for the two weights used in the hero h1 and body copy. Then declare metric-matched fallbacks (`@font-face { font-family: "Poppins Fallback"; src: local("Arial"); size-adjust: 112%; ascent-override: 93%; descent-override: 31%; }`, then tune them) so the hero `div.container-wide` stays the same size when the fonts swap. Expected result: CLS under 0.05 and homepage performance back to 95 or higher.

2. **(template, high impact)** Replace the header and footer logo. This carries over from August. `/images/logo.png` is 176 KB, is 878x500 intrinsic, and ships twice per page (header `loading="eager"` and footer `loading="lazy"`). Export `logo-192w.webp` and `logo-384w.webp` and use `srcset`/`sizes`. **Also correct the dimension attributes to the real 1.756:1 ratio.** The header tag says `width="64" height="64"` and the footer tag says `width="48" height="48"`. Change the footer to `width="140" height="80"` and the header to `width="169" height="96"`. That fixes the `/contact/` CLS regression and the header `nav` shift, and it saves about 173 KB per page.

3. **(template, render path)** Delete the blocking duplicate Google Fonts stylesheet from the shared layout `<head>`. Keep only the `media="print" onload="this.media='all'"` copy, or drop both if action 1 self-hosts the fonts. This clears `render-blocking-insight` (50ms FCP on two pages) and `has_render_blocking_resources` on all six.

4. **(template, new this month)** Load GA4 after the page renders. Keep the `gtag` stub and `dataLayer` inline. Inject `https://www.googletagmanager.com/gtag/js?id=G-FW5QLBCH24` from a `requestIdleCallback` or `window.addEventListener('load', ...)` handler instead of a head `<script async>`. Alternatively, move it to a Cloudflare Zaraz or Partytown worker. That recovers the 66 to 70 KB of unused JS and 50 to 100ms of LCP on every page. Conversion events for calls and form submits still fire, because the stub queues them.

5. **(template, contrast and LCP)** Close out the remaining August items in one pass:
   - Breadcrumb `a.text-dark/50` (#8b8b8c): move to `text-dark/70`.
   - `.btn-accent`: switch the label to navy `#02255d` on the existing orange (5.10:1), or darken the background to `#c75201` and keep white text (4.53:1).
   - Service-area `span.text-slate-400`: move to `text-slate-600`.
   - Add `fetchpriority="high"` and `decoding="async"` to the shared inner-page hero `<img>`. This clears `lcp-discovery-insight` on 5 of 6 pages.
   - Trim the homepage meta description from 177 to 160 characters or fewer. Dropping "Licensed, insured, " gives 158. That clears the last medium on-page issue on `/`.

## What is already correct (do not regress these)

- **Schema:** every page has valid, parseable JSON-LD (24 blocks, zero parse errors). `LocalBusiness` with `AggregateRating`, `PostalAddress`, `GeoCoordinates` and `OpeningHoursSpecification` appears sitewide. `Service` is on both service landings. `BreadcrumbList` and `FAQPage` are on all five non-home pages.
- **Titles and canonicals:** titles are 54 to 61 characters. Canonicals are absolute and point to the page itself. Every page has exactly one `h1`. There are no duplicate titles or descriptions.
- **Links and resources:** there are zero broken internal or external links, zero broken resources, and zero `http://` references (no mixed content). All six URLs return 200.
- **Image alt text:** 100 percent of `<img>` elements across the six pages have non-empty alt text.
- **Content depth:** every page is above its `url-plan.json` target. Home has 1652 words against 1200, services hub 851 against 800, water damage 1833 against 1100, fire damage 1928 against 1100, Sweetwater 1314 against 900, and contact 648 against 400.
- **Security headers:** HSTS (`max-age=31536000; includeSubDomains`), `x-content-type-options: nosniff`, CSP `frame-ancestors`, `permissions-policy` and `referrer-policy` are all present. Best Practices is 100 on all six pages.

## Notes / caveats

- **Desktop only.** Lighthouse 13.4.0 ran with `formFactor: desktop`, `cpuSlowdownMultiplier: 1`, `throughputKbps: 10240`. That matches August so the numbers compare like for like. Mobile scores typically come in 10 to 20 performance points lower, and the font-swap CLS and logo weight will hit harder on mobile.
- **Client record status is still `onboarding`.** The apex cutover completed 2026-08-21 and the site is live, so the audit went ahead on the same basis as August. The status field should be flipped to `active`.
- **URL selection:** derived automatically from `plan/url-plan.json`, since there is no `audit-urls.txt`. It is the same six URLs as August.
- **No URLs errored.** All 12 API calls returned status 20000.
- **LCP drift:** every page's LCP rose by 110 to 374ms, but TBT stayed at 0 and TTFB stayed at 18 to 50ms. The server is not the cause. The only structural change since August is the new gtag script. If the next audit still shows the rise after action 4, look at the hero image next.
- **Run cost:** about $0.041 (6 Lighthouse live calls at $0.005, plus 6 instant-pages calls at $0.0018).
