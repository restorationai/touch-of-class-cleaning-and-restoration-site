# Onsite Audit - DISS Restoration - 2026-09-28

**Live origin audited:** https://dissrestoration.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26 (run against the staging Pages preview; this is the first apex audit)
**Form factor:** desktop only (DataForSEO wrapper does not expose mobile). Expect mobile performance 10-20 points lower.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 89.3 | -3.9 |
| Accessibility | 96.0 | 0 |
| Best Practices | 100.0 | 0 |
| SEO | 100.0 | +31 |

Pages by verdict: {green: 5, amber: 1, red: 0, error: 0}

SEO jumped from 69 to 100 because the apex no longer carries the Cloudflare Pages `x-robots-tag: noindex` header. That was a staging artifact, not a fix. SEO counts toward the verdict from this run on.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 80 | 100 | 100 | 100 | 1.9s | 0.215 |
| /services/ | services-hub | green | 91 | 95 | 100 | 100 | 2.0s | 0.002 |
| /services/water-damage-restoration/ | service-landing | green | 91 | 95 | 100 | 100 | 1.9s | 0.004 |
| /services/fire-damage-restoration/ | service-landing | green | 92 | 95 | 100 | 100 | 1.9s | 0.002 |
| /service-areas/warren-oh/ | service-area | green | 91 | 95 | 100 | 100 | 1.9s | 0.004 |
| /contact/ | contact | green | 91 | 96 | 100 | 100 | 2.0s | 0.024 |

TBT is 0 ms on every page. On-page checks came back clean everywhere: no broken internal or external links, no mixed content, 100% image alt coverage, one H1 per page, titles 53-57 chars, and self-referencing apex canonicals.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | Replace `/images/logo.png` (1,423,236 bytes, 1200x1078 PNG, shown at about 107x96) with a 256px-wide WebP/AVIF or SVG. Lighthouse puts the waste at 1.42 MB per page view, from the header and footer logos. |
| `unused-javascript` | 6 | medium | GA4 `gtag/js?id=G-QQDEBB808D` (159 KB, 44% unused) is new with the apex build. Load it after the `load` event or on first interaction, or move it to Cloudflare Zaraz so it runs off the main thread. |
| `render-blocking-insight` | 6 | medium | Inline the critical CSS from `/_astro/_slug_.*.css` (about 9 KB) with Astro `build.inlineStylesheets: "always"`. |
| `color-contrast` | 5 | medium | Breadcrumb link class `text-dark/50` renders #888c93 on white (3.37:1). Change it to `text-dark/70` or darker to reach 4.5:1. Home passes because it has no breadcrumb. |
| `lcp-discovery-insight` | 5 | medium | Add `fetchpriority="high"` to the `hero-bg.webp` `<img>` in the inner-page hero component. The homepage hero already has it. |

## Money page alerts

- **`/`** - verdict: amber. Performance 80, CLS 0.215, LCP 1.9s. Cause: the hero text container (`main > header.relative > div.container-wide`) reflows when the Google Fonts Inter woff2 swaps in (Lighthouse `cls-culprits-insight`: "Web font loaded"). The 1.42 MB logo.png and the new GA4 script make it worse. On-page, the meta description is 176 chars, so it will be cut off in search results, and the FAQ section ships no FAQPage JSON-LD.

## Regressions vs prior audit

Comparison is by URL path: staging preview (2026-08-26) vs apex+CDN (today). Some movement comes from the change of environment itself. The apex also loads GA4, Google Fonts, and Cloudflare Email Obfuscation, which staging did not.

**Metric regressions:**
- `/`: performance 88 to 80 (-8), LCP +291 ms, CLS 0.153 to 0.215 (+0.062).
- `/contact/`: performance 100 to 91 (-9), LCP 808 ms to 1,953 ms (+1,145 ms). The contact LCP is now in line with every other page. Its hero image lacks `fetchpriority="high"`, and the extra third-party bytes now compete for bandwidth.
- Site average performance dropped 3.9 points (threshold: 3).

**Verdict transitions:**
- `/services/water-damage-restoration/` went amber to green. The DataForSEO `high_loading_time` flag cleared (dom_complete dropped from 4,226 ms to 42 ms).
- `/services/fire-damage-restoration/` went amber to green. `high_loading_time` cleared (dom_complete dropped from 5,051 ms to 86 ms).

**New issues this month:**
- All 6 URLs: `unused-javascript`, which is GA4 gtag.js (about 69 KB unused).
- `/`: `meta_description_length_out_of_range` (176 chars). This was already true in August but was not flagged then, so it is newly detected rather than newly introduced.

**Issues resolved since last audit:** (positive - keep doing this)
- All 6 URLs: `is-crawlable` is no longer flagged. The apex is indexable.
- `/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`: `high_loading_time` is no longer flagged. The Cloudflare edge serves these pages much faster than the staging preview did.

**Still open from last audit:** logo.png size (`image-delivery-insight`), home hero web-font CLS, breadcrumb `color-contrast`, inner-page `lcp-discovery-insight`, home `faqpage_schema_missing`, and `/services/` word count (706 vs the 800 target).

## Recommended next actions (priority order)

1. **(money page, home)** Stop the hero font shift on `/`. Self-host Inter (for example `@fontsource-variable/inter`), preload the woff2 in the layout `<head>`, and add a metric-matched fallback (`size-adjust` / `ascent-override` on a local Arial `@font-face`). That should bring CLS from 0.215 to under 0.1. Also shorten the home meta description to 160 chars or fewer, for example: "DISS Restoration provides 24/7 water, fire, mold, and storm damage restoration in Youngstown, OH. IICRC-certified. Call (724) 981-1441." (136 chars).
2. **(money page, home)** Add a FAQPage JSON-LD block to the homepage, built from the questions already in its FAQ section. The hub, contact, landing, and area templates already emit FAQPage.
3. **(template, high impact)** Replace `/images/logo.png` with a properly sized WebP/AVIF (about 256x230, under 20 KB) or an SVG, and update the header and footer `<img>` tags. This saves about 1.42 MB on every page view and is the main driver of the uniform 1.9-2.0s simulated LCP.
4. **(template)** Defer GA4. Inject gtag.js after `window.load` or first interaction, or move it to Cloudflare Zaraz. This recovers about 69 KB of unused JS on all 6 pages and should win back most of the `/contact/` regression.
5. **(template)** Add `fetchpriority="high"` to the inner-page hero `<img src="/images/hero-bg.webp">`. Change the breadcrumb `text-dark/50` to a color with at least 4.5:1 contrast, which lifts accessibility from 95 to 100 on 5 pages.

## Notes / caveats

- First audit against the apex. Apex cutover completed 2026-09-19. There is no noindex header, so SEO counts in the verdict.
- Service-landing selection: fire-damage, mold-remediation, and water-damage all share url-plan priority 9.0. I kept water-damage and fire-damage (the August selection) so the regression comparison stays valid.
- Service-area selection: there is no `primary: true` area and no address city on the client record, so I used `/service-areas/warren-oh/` (first area slug, same as August).
- DataForSEO instant_pages returned `has_micromarkup: null` on all pages. I checked the served HTML directly and every page ships valid JSON-LD. The only gap is FAQPage on the homepage.
- `/service-areas/warren-oh/` trips the DataForSEO `frame` check because of the embedded map iframe. This is expected and is not reported as an issue.
- Cloudflare Email Obfuscation injects `/cdn-cgi/.../email-decode.min.js`, which shows up under `cache-insight` (285 bytes). It is negligible, but if no email addresses are obfuscated on the site, you can turn it off in the Cloudflare dashboard (Scrape Shield) and save a request.
- Run cost: about $0.03 (6 Lighthouse live calls plus 6 instant_pages calls).
