# Onsite Audit - National Restoration Construction - 2026-09-28

**Live origin audited:** https://narestco.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-27
**Form factor:** desktop only (Lighthouse 13.4.0, cpuSlowdownMultiplier=1). Mobile scores would typically come in 10-20 performance points lower.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.5 | +0.8 |
| Accessibility | 94.7 | -5.3 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

The site is amber for the third audit running. The only cause is still the homepage meta description at 194 characters (limit 160). The new finding this month is an accessibility drop on every audited page, from 100 to between 92 and 96. The same footer link causes it on all 6 pages. Performance improved slightly, and best practices and SEO are still perfect.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 97 | 92 | 100 | 100 | 1.30s | 0.005 |
| `/services/` | services-hub | green | 98 | 95 | 100 | 100 | 1.13s | 0.004 |
| `/services/water-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 100 | 1.00s | 0.006 |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 100 | 0.93s | 0.006 |
| `/service-areas/seattle-wa/` | service-area | green | 99 | 95 | 100 | 100 | 1.04s | 0.005 |
| `/contact/` | contact | green | 99 | 96 | 100 | 100 | 0.98s | 0.033 |

Total blocking time was 0 ms on all six pages. The on-page checks came back clean:
- no broken internal links, broken external links or broken resources
- no mixed content
- exactly one H1 per page
- self-referencing canonicals on all six
- titles between 46 and 50 characters
- JSON-LD present in the static HTML on every page

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 6 | medium | The footer license link (`#NATIORC792M6`, pointing to `secure.lni.wa.gov/verify/`) renders in `#f0c1bd` on a white footer, which is a 1.6:1 contrast ratio (4.5:1 is required). Change that link to the footer body text color or the dark brand red. This one change restores accessibility to 100 on 4 of the 6 pages. |
| `unused-javascript` | 6 | medium | Only one `gtag/js` bundle now loads (GA4 `G-5N8L5D4Z3C`, ~69KB unused). The duplicate Google Ads bundle flagged last month is gone. What's left is standard GA4 overhead; defer it until after first interaction if you want the last 50-200ms. |
| `has_render_blocking_resources` | 6 | low | The layout loads the Google Fonts Inter stylesheet twice: once non-blocking (`media="print" onload`) and once as a plain blocking `<link rel="stylesheet">`. Delete the plain one. `/_astro/_slug_.CZgGo4Mo.css` is the only remaining blocking request. |
| `image-delivery-insight` | 5 | low | `images.narestco.com/brand/hero.webp` wastes 161-165KB per page because it is shipped at full size into a 276px-tall box. Serve a width-matched variant through `srcset`. On home, `hero-bg.webp` wastes 68KB. |
| `lcp-discovery-insight` | 5 | low | The LCP image (`brand/hero.webp`, `loading="eager"`) has no `fetchpriority="high"` on inner-page templates. The homepage hero already has it. Add the same attribute to the shared inner-page hero component. |
| `network-dependency-tree-insight` | 3 | low | The hero request waits behind the render-blocking CSS. Clearing the duplicate font stylesheet and adding `fetchpriority` addresses this too. |
| `low_content_rate` | 3 | low | Text-to-HTML ratio is 6.8 percent on home, 5.1 percent on the services hub and 8.2 percent on contact. This comes from markup weight, not thin content, so no action is needed. |
| `cache-insight` | 3 | low | `brand/hero.webp` and `brand/logo.png` on `images.narestco.com` are served with a 4h TTL. Raise the R2 custom-domain cache rule to 30 days. `clarity.js` (24h) is third-party and cannot be fixed on our side. |

## Money page alerts

- **`/`** - verdict: amber. Performance 97, LCP 1.30s. It is held amber by the meta description at 194 characters, which has been unresolved since 2026-07-15. Accessibility is also down to 92: on top of the footer link, the Tacoma service-area link inside the dark "areas" paragraph (`section.bg-dark p > a`) is `#f0c1bd` on `#cfd1d4` body text. That is a 1.05:1 ratio with no underline, which fails `link-in-text-block`.

## Regressions vs prior audit

**Verdict transitions:** none. All 6 URLs held last month's verdict.

**Category regressions (drop of 5 or more points):**
- Accessibility fell on 5 of 6 pages: `/` 100 to 92, and `/services/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/` and `/service-areas/seattle-wa/` each 100 to 95. `/contact/` fell 100 to 96, just under the flag threshold. The site average fell 5.3 points, which is past the 3-point site flag. The shared cause is the footer license link added since the last audit. `/service-areas/seattle-wa/` has a second contrast failure: the "64 Google reviews" count uses `text-slate-400` (`#94a3b8`, 2.56:1).

**Core Web Vitals regressions:**
- `/service-areas/seattle-wa/` LCP went from 574ms to 1037ms (+463ms, threshold 200ms). The page now uses the full-size `brand/hero.webp` as its LCP element, eager-loaded with no `fetchpriority`. It is still well under 2.5s, and performance scored 99.
- `/contact/` CLS went from 0.006 to 0.033 (+0.028, threshold 0.02). Lighthouse traces the shift to the `#estimate` section, caused by the unsized footer logo. `brand/logo.png` is declared `width="48" height="48"`, but the file is 242x52 and renders 372x80, so the browser reserves the wrong box. The Inter web font swap also contributes. CLS is still far inside the 0.1 "good" limit.

**New issues this month:**
- All 6 pages: `color-contrast`, the footer license link as described above. This is a real site change.
- `/`: `link-in-text-block`, the Tacoma link in the dark service-areas paragraph. This is a real site change.
- `/` (`render-blocking-insight`) and the two service landings plus Seattle (`lcp-discovery-insight`): these IDs were not in last month's top-5 capture, but they may have been failing then too. They are not traced to a site change.

**Issues resolved since last audit:** (positive - keep doing this)
- `/contact/` LCP improved from 1625ms to 984ms, which reverses last month's regression.
- Site-wide: the duplicate Google Ads `gtag/js` bundle (`AW-16824131335`, ~147KB) no longer loads.
- `/` and `/services/fire-damage-restoration/`: `forced-reflow-insight` passes.
- `/services/water-damage-restoration/`: `high_loading_time` is no longer flagged.
- `no_image_alt` is no longer flagged on any page. This is probably due to the different detection profile (see caveats), so it is not counted as a real fix.

## Recommended next actions (priority order)

1. **(money page, carried over twice)** Cut the homepage meta description from 194 to 160 characters or fewer. Suggested text (135 chars): "24/7 water, fire, mold and storm damage restoration in Federal Way and nearby. Licensed, insured, IICRC-certified. Call (206) 883-0333." This is the only thing keeping the site from green.
2. **(template, high impact)** In the footer component, change the license link `#NATIORC792M6` from `#f0c1bd` to the footer body text color (or a 4.5:1-compliant brand red). This lifts accessibility on all 6 pages and on every other page that shares the footer.
3. **(money page)** On `/`, give the Tacoma link in the dark service-areas paragraph an underline and a color with at least 3:1 contrast against `#cfd1d4`. This clears `link-in-text-block`.
4. **(template)** Fix the footer logo `<img>`: set `width="242" height="52"` to match the real file, or `width="372" height="80"` to match the rendered size, so the aspect ratio is reserved. In the same layout pass, delete the duplicate blocking Inter `<link rel="stylesheet">` and add `fetchpriority="high"` to the inner-page `brand/hero.webp` hero. Together these fix the `/contact/` CLS regression and the Seattle LCP regression.
5. **(per-page)** On `/service-areas/seattle-wa/`, change the "64 Google reviews" count from `text-slate-400` to `text-slate-600` or darker.

## Notes / caveats

- The dedicated DataForSEO MCP wrappers are not exposed in this build, so the endpoints were called directly: `/v3/on_page/lighthouse/live/json` with full data extracted on disk, and `/v3/on_page/instant_pages` with JavaScript and resource loading on. The total API cost was about $0.08 including the retries.
- A parity re-run of `instant_pages` with `enable_browser_rendering` (the profile used on 2026-08-27) returned zero items for all 6 URLs. Two retries of the original profile also came back empty. The on-page findings come from the first successful pass. Because the profile differed, the disappearance of `no_image_alt` is not credited as a fix.
- DataForSEO reported `has_micromarkup=false` on every page, but the static HTML carries 3 JSON-LD blocks (LocalBusiness, Organization, FAQPage, BreadcrumbList and more, verified on `/contact/`). This is treated as a detection gap.
- `no_image_title` (images without a `title` attribute) and `frame` (the Google Maps embed on Seattle) were flagged. Neither is a ranking issue, so neither is recorded as an issue.
- The services hub measured 785 words against its 800-word url-plan target. That is 2 percent short on a JS-rendered count, so it is treated as borderline and not recorded as an issue.
