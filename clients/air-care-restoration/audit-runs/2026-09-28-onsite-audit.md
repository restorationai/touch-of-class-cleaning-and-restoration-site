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

This month is a net improvement. Three money pages moved from amber to green, the homepage now scores 100 on Accessibility, and the sitewide contrast failures dropped from 35 elements to 13. The only amber page is the homepage. Its layout shift got worse (CLS 0.157 to 0.205) and its Performance score fell to 89, and both come from the same web-font swap that was flagged last month. There is also one new sitewide finding: a Google Analytics 4 tag (`G-FW5QLBCH24`) was added after the August audit, and Lighthouse now reports 69 KiB of unused JavaScript on every page.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 89 | 100 | 100 | 100 | 1.00s | 0.205 | 0ms |
| `/services/` | services-hub | green | 99 | 95 | 100 | 100 | 1.04s | 0.028 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 98 | 95 | 100 | 100 | 0.90s | 0.024 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | green | 98 | 95 | 100 | 100 | 0.90s | 0.024 | 0ms |
| `/service-areas/sweetwater-tx/` | service-area | green | 99 | 95 | 100 | 100 | 0.88s | 0.009 | 0ms |
| `/contact/` | contact | green | 98 | 96 | 100 | 100 | 0.97s | 0.067 | 0ms |

INP was null on all six URLs because the lab run does not simulate an interaction.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | **Carried over from August, not fixed.** `/images/logo.png` is still a 173 KiB PNG, 878x500 intrinsic, rendered at 169x96. It is the largest single item on every page. See action 2. |
| `color-contrast` | 5 | high | **Partly fixed.** Down from 35 failing elements to 13. Three token choices remain; see action 3. The homepage now passes. |
| `unused-javascript` | 6 | medium | **New this month.** `https://www.googletagmanager.com/gtag/js?id=G-FW5QLBCH24` is 156 KiB transferred and 69 KiB of it goes unused on first load. It costs 37 to 57ms of main-thread time per page. See action 4. |
| `lcp-discovery-insight` | 5 | medium | **Carried over.** The inner-page hero `<img>` still lacks `fetchpriority="high"` and `srcset`. The homepage hero has both. See action 5. |
| `render-blocking-insight` | 6 | medium | `/_astro/_slug_.DWEqrGuE.css` (about 9 KB). It cost 56ms on `/services/` and nothing measurable elsewhere. Leave it until the items above are done. |
| `forced-reflow-insight` | 2 | medium | New on both service landings, 44ms and 50ms, with the source reported as `[unattributed]`. Most likely GA4 initialization reading layout. Re-check after action 4 before spending time on it. |
| `cache-insight` | 6 | low | The only short-TTL asset is Cloudflare's injected `email-decode.min.js`, with 0 KiB of estimated savings. Not ours to fix. |
| `network-dependency-tree-insight` | 6 | low | This fires on the shape of the dependency chain, not on its latency. No action. |
| `has_render_blocking_resources` | 6 | low | This is DataForSEO's view of the same Astro CSS bundle as above. No action. |
| `no_image_title` | 6 | low | A `title` attribute on images is not an SEO or a11y requirement, and alt coverage is 100%. No action. |
| `low_content_rate` | 3 | low | Text-to-HTML ratio on `/`, `/services/` and `/contact/` is low because of inline JSON-LD and Tailwind markup. Every page is above its word-count target. No action. |

Note on verdicts: under the rubric, only category scores, on-page issue severities and Core Web Vitals thresholds move a page's verdict. Pages that carry a high-severity Lighthouse template issue such as `color-contrast` can therefore still be green.

## Money page alerts

- **`/` (home)** verdict: amber. Performance is 89, down from 93. **CLS is 0.205**, up from 0.157, and it fails the Core Web Vitals "good" threshold of 0.10 by a wider margin than in August. Lighthouse attributes 0.2035 of the 0.205 to one element: `main.flex-1 > header.relative > div.container-wide`, the hero copy block. That block reflows when the Poppins and Anton woff2 files load (cause reported: "Web font loaded"). The meta description is still 177 characters. LCP is 1.00s, which is fine in absolute terms.

## Regressions vs prior audit

**Verdict transitions (worse):** none.

**Verdict transitions (better):**
- `/services/` amber to green
- `/services/water-damage-restoration/` amber to green
- `/services/fire-damage-restoration/` amber to green

All three moved because DataForSEO's `high_loading_time` flag cleared. Crawler `dom_complete` fell from 3.3 to 3.4s to between 0.26s and 1.47s.

**Metric regressions (flag thresholds: score -5, LCP +200ms, CLS +0.02, TBT +100ms):**
- `/` CLS 0.157 to 0.205 (+0.048). The web-font swap is the real regression here. See action 1.
- `/contact/` CLS 0.029 to 0.067 (+0.038). The biggest shift (0.065) is `section#estimate`. Lighthouse lists "Media element lacking an explicit size" first, pointing at the footer logo `<img src="/images/logo.png" width="48" height="48">`, followed by five "Web font loaded" causes. The page is still under 0.10.
- `/` LCP 650ms to 999ms (+349ms).
- `/services/water-damage-restoration/` LCP 643ms to 898ms (+255ms).

The two LCP flags are relative. Every page still paints LCP under 1.05s, far inside the 2.5s threshold. Some of the increase probably comes from the new GA4 script competing for bandwidth, and the rest is within normal single-run lab noise. No per-URL category score dropped by 5 or more; the largest drop was the homepage Performance score at -4. No site-level average dropped by 3 or more.

**New issues this month:**
- All 6 URLs: `unused-javascript` (the new GA4 gtag.js, 69 KiB unused)
- `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`: `forced-reflow-insight` (44ms and 50ms, unattributed)
- `/services/`, `/contact/`: `low_content_rate` (DataForSEO text-ratio flag, no action)

**Issues resolved since last audit:** (positive, keep doing this)
- `/`: `color-contrast` no longer flagged. The homepage Accessibility score is now 100.
- `/`, `/services/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`: `high_loading_time` no longer flagged.
- Sitewide contrast failures fell from 35 to 13. The accent-orange-as-text failures (`.eyebrow`, `.text-accent`, 17 elements in August) and the `text-dark/60` failures are gone.

## Recommended next actions (priority order)

1. **(money page, Core Web Vitals)** Stop the homepage hero from reflowing when fonts load. Self-host Poppins (400 to 900) and Anton as same-origin woff2 files under `/fonts/`. Preload the two weights used in the hero (`<link rel="preload" as="font" type="font/woff2" crossorigin>` for Anton and Poppins 400). Then declare metric-matched fallbacks: an `@font-face` for "Poppins Fallback" on `local("Arial")` and one for "Anton Fallback" on `local("Arial Narrow")`, each with `size-adjust`, `ascent-override` and `descent-override` tuned so the fallback matches the web font's box. List them in the `font-family` stacks right after the web fonts. This targets the 0.2035 shift on `header.relative > div.container-wide` and should bring homepage CLS under 0.10 and Performance back above 90. It also removes most of the "Web font loaded" shifts on `/contact/`.

2. **(template, high impact)** Replace the header and footer logo. This was action 1 in August and is still open. `/images/logo.png` is 173 KiB and 878x500 (aspect ratio 1.756:1). Export `logo-192w.webp` and `logo-384w.webp` and use `srcset="/images/logo-192w.webp 192w, /images/logo-384w.webp 384w"`. The tags also declare the wrong box: the header has `width="64" height="64"` and the footer has `width="48" height="48"`. Change these to `width="169" height="96"` and `width="141" height="80"` so the browser reserves a box with the correct aspect ratio. The footer tag is the "Media element lacking an explicit size" cause behind the `/contact/` CLS increase. Expected savings are about 173 KiB per page on all 366 planned pages.

3. **(template, accessibility)** Fix the 13 remaining contrast failures. Three token choices cause all of them:
   - Breadcrumb links using `text-dark/50` render as `#8b8b8c` on white, which is 3.40:1 at 12px. Change them to `text-dark/70` (`#5d5d5f`, 6.57:1). This covers 1 element per page on `/services/` and `/contact/`, and 2 per page on the service landings and service-area template.
   - `.btn-accent` uses white text on `#ff6901`, which is 2.89:1 at 14px bold. Either switch the label to navy `#02255d` (5.10:1) or darken the background to `#c75201` (4.53:1). This is the "Call" CTA (`<a href="tel:+13253398723" class="btn-accent">`) on the service landings and the service-area template.
   - One `text-slate-400` (`#94a3b8`, 2.56:1) remains on the service-area template. Change it to `text-slate-500` (`#64748b`, 4.76:1).

4. **(template, new this month)** Defer the GA4 tag. `gtag/js?id=G-FW5QLBCH24` now loads `async` in the `<head>` on every page. First confirm that this property was added on purpose and belongs to the client. Then move the `<script async src=...gtag/js...>` injection into a `window.addEventListener('load', ...)` callback, or inside a `requestIdleCallback`, and keep the `dataLayer`/`gtag('config', ...)` stub inline so no events are lost. This takes the 156 KiB script off the critical path on all pages, clears `unused-javascript` from the first-load view, and will probably clear the unattributed `forced-reflow-insight` on the service landings.

5. **(template plus per-page)** Bring the inner-page hero `<img>` up to homepage parity (carried over from August). The shared hero on `/services/`, the service landings, the service-area template and `/contact/` is still only `<img src="..." class="w-full h-full object-cover" loading="eager">`. Add `fetchpriority="high"`, `decoding="async"`, and the same `srcset` (480w, 768w, 1200w, 1376w) with `sizes="100vw"` that the homepage uses. While you are in the head template, also trim the homepage meta description from 177 characters to 160 or fewer. Removing "Licensed, insured, " brings it to 158.

## What is already correct (do not regress these)

- **Schema:** JSON-LD is present on every page. `LocalBusiness` with `AggregateRating`, `PostalAddress`, `GeoCoordinates` and `OpeningHoursSpecification` appears sitewide; `Service` is on both service landings; `BreadcrumbList` and `FAQPage` are on all five non-home pages.
- **Titles and canonicals:** titles run 54 to 61 characters. Canonicals are absolute and self-referencing, and every page has exactly one `h1`. There are no duplicate titles or descriptions.
- **Links and resources:** no broken internal links, broken external links or broken resources, and no `http://` references (no mixed content).
- **Image alt text:** 100% coverage on all six pages.
- **Content depth:** every page beats its `url-plan.json` target. Home has 1652 words against 1200, `/services/` 851 against 800, water damage 1833 against 1100, fire damage 1928 against 1100, Sweetwater 1314 against 900, and contact 648 against 400.
- **Security headers:** `strict-transport-security: max-age=31536000; includeSubDomains`, `x-content-type-options: nosniff`, `content-security-policy: frame-ancestors ...` and `referrer-policy: strict-origin-when-cross-origin` are all present. Best Practices is 100 on all six URLs.

## Notes / caveats

- **Desktop only.** Lighthouse 13.4.0 ran with `formFactor: desktop`, `cpuSlowdownMultiplier: 1` and `throughputKbps: 10240`. Mobile scores typically land 10 to 20 Performance points lower. The CLS and logo-weight findings will hit harder on mobile, where the logo renders at `max-w-[55vw]`. Do not report these numbers as mobile-first scoring. Desktop was kept so this month compares like for like with August.
- **Correction to the August report.** August's action 3 said the Google Fonts stylesheet was loaded twice and told you to delete the blocking copy. That was wrong. The second `<link rel="stylesheet">` sits inside a `<noscript>` block, which is the correct fallback for the `media="print" onload` async pattern. Leave it in place. The font-related CLS fix is action 1 above.
- **Client record status is still stale.** `clients/air-care-restoration.json` still reads `status: "onboarding"`. The apex cutover completed on 2026-08-21 and the site is live, so the audit went ahead for the second month running. Flip the status to `active`.
- **URL selection:** auto-derived from `plan/url-plan.json`, since there is no `audit-urls.txt`. Three service landings tie at priority 9.0: water damage, fire damage and mold remediation. Water and fire were kept so the comparison with August is like for like. No `service-area` page has `primary: true` and there is no Abilene area page, so the fallback picked the first area in the plan, `/service-areas/sweetwater-tx/`.
- **Verdict rubric extension:** a Core Web Vitals miss (CLS > 0.1, LCP > 2.5s or TBT > 200ms) holds a page at amber at minimum. This month it only affected `/`, which was already amber on Performance 89 and its meta description.
- **No URLs errored.** All 6 Lighthouse calls and all 6 instant-pages calls returned status 20000.
- **Run cost:** $0.041 (6 Lighthouse live calls at $0.005, 6 instant-pages calls at $0.0018). This is well inside the $0.30 to $0.50 target.
