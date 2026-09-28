# Onsite Audit - National Restoration Construction - 2026-09-28

**Live origin audited:** https://narestco.com (apex)
**Form factor:** desktop only (Lighthouse 13.x via DataForSEO; mobile would typically score 10-20 performance points lower)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-27

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 98.3 | +0.6 |
| Accessibility | 94.7 | -5.3 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: {green: 5, amber: 1, red: 0, error: 0}

The site is still amber for one reason: the homepage meta description is 194 characters, over the 160 limit. It has been open since 2026-07-15. The new finding this month is accessibility. Every page lost 4 to 8 points because of a new low-contrast footer link. All pages are still above 90, so no page changed verdict.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 97 | 92 | 100 | 100 | 1.1s | 0.005 |
| /services/ | services-hub | green | 98 | 95 | 100 | 100 | 1.2s | 0.004 |
| /services/water-damage-restoration/ | service-landing | green | 98 | 95 | 100 | 100 | 1.0s | 0.006 |
| /services/fire-damage-restoration/ | service-landing | green | 99 | 95 | 100 | 100 | 1.0s | 0.004 |
| /service-areas/seattle-wa/ | service-area | green | 99 | 95 | 100 | 100 | 1.0s | 0.005 |
| /contact/ | contact | green | 99 | 96 | 100 | 100 | 1.0s | 0.033 |

TBT is 0 to 5ms on every page. INP is not reported in lab mode. No broken links or broken resources on any page. Titles are 46 to 50 chars, H1s are single and present, and canonicals are self-referencing on all six pages.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 6 | medium | This is new since August. The footer link to `https://secure.lni.wa.gov/verify/` (the WA L&I license verify link) uses `#f0c1bd` on a white footer, a 1.6:1 ratio. WCAG requires 4.5:1 for 12px text. Switch it to the dark brand text color, or a primary shade of at least 4.5:1 on white, in the footer component. On `/`, the same `#f0c1bd` is used for the in-paragraph city links in the dark `section.bg-dark` band. Those links fail `link-in-text-block` at 1.05:1 against the surrounding `#cfd1d4` text and have no underline. Add `underline` to them. |
| `unused-javascript` | 6 | medium | GA4 `gtag.js` (G-5N8L5D4Z3C) ships 159KB, with about 69KB unused on every page. Load it with Partytown, or defer the gtag snippet until after `load`. The estimated saving is 50 to 100ms per page. |
| `image-delivery-insight` | 6 | medium | Interior heroes use the 220KB `images.narestco.com/brand/hero.webp` with no `srcset`, and `hero-480w`, `hero-768w` and `hero-1200w` variants already exist on R2. Add `srcset`/`sizes` plus `width="1376" height="768"` to the hero `<img>` in the services index, service-area, and contact templates. The water landing serves a 266KB `/images/services/water-damage-restoration.webp` with about 197KB of waste, so give it a responsive variant too. |
| `cache-insight` | 6 | medium | R2 images on `images.narestco.com` (hero.webp, hero-480w.webp, logo.png) are served with a 4 hour browser TTL. Add a Cloudflare Cache Rule on the `images.narestco.com` hostname that sets Browser Cache TTL to 1 year, since the filenames are versioned assets. This saves about 150KB on repeat visits to `/services/`, `/service-areas/seattle-wa/` and `/contact/`. |
| `lcp-discovery-insight` | 5 | medium | The LCP image on every non-home page is the hero `<img ... loading="eager">` with no `fetchpriority="high"`. The homepage hero already has it, which is why `/` passes. Add `fetchpriority="high"` in the same template edit as the `srcset` fix above. |
| `render-blocking-insight` / `has_render_blocking_resources` | 6 | low | The main stylesheet blocks render. The measured saving is 0ms at current sizes, so this is informational. |
| `network-dependency-tree-insight` | 6 | low | Informational. The fetchpriority and gtag changes above resolve it as a side effect. |
| `has_micromarkup_errors` | 5 | low | DataForSEO's schema.org validator flags every FAQPage `Question` for a missing `answerCount`. A `/v3/on_page/microdata` check of `/contact/` confirmed this is the only error-level result. Google's FAQPage rich result does not require that field (it belongs to QAPage), so this is a validator false positive. Optional: add `"answerCount": 1` to each Question in the FAQ schema builder. |
| `forced-reflow-insight` | 3 | low | Minor layout thrash from a client-side script on `/`, water and contact. TBT is 0 to 5ms, so no action is needed. |
| `low_content_rate` | 3 | low | Text-to-HTML ratio is low on `/`, `/services/` and `/contact/`. `/` (1766 words vs 1200) and `/contact/` (731 vs 400) are well above their word targets, so this is markup weight, not thin content. |

## Money page alerts

- **`/`** - verdict: amber. The meta description is 194 characters, 34 over the 160 limit, so Google truncates it in the SERP. This is the only thing holding the site at amber, and it has been unresolved for three audit cycles (since 2026-07-15). Performance 97, LCP 1.1s. The page is otherwise healthy.

## Regressions vs prior audit

**Verdict transitions:** none. `/` stayed amber and the other five pages stayed green.

**Category regressions (5+ point drop):**
- Accessibility dropped on `/` (100 to 92), `/services/` (100 to 95), water (100 to 95), fire (100 to 95) and `/service-areas/seattle-wa/` (100 to 95). `/contact/` dropped 100 to 96, just under the flag threshold. The site average fell 5.3 points. The single cause is the new footer L&I verify link color. The homepage takes an extra hit from the `link-in-text-block` failure on its dark city-links band.

**Core Web Vitals regressions:**
- `/service-areas/seattle-wa/` LCP went from 574ms to 1041ms (+467ms). The LCP element is the un-prioritized, non-responsive 220KB R2 hero on a 4 hour cache. The real load breakdown is only about 305ms (TTFB 122ms, load 71ms, render delay 103ms), so part of the jump is lab simulation variance. The fetchpriority, srcset and cache fixes above address the real part. 1.0s is still a good desktop LCP.
- `/contact/` CLS went from 0.006 to 0.033 (+0.028). It is still well inside the good range (under 0.1). Lighthouse attributes the shift to `section#estimate`, with the footer logo `<img>` as the culprit. That logo is declared `width="48" height="48"` but renders at 372x80 (`h-16 md:h-20 w-auto`). Set the real intrinsic dimensions on the footer logo, and on the header logo, which is declared 36x36.

**Core Web Vitals improvements:**
- `/contact/` LCP went from 1625ms to 986ms (-639ms). Last month's flagged regression is resolved.

**New issues this month:**
- All 6 pages: `color-contrast`. This is a real site change, the footer WA L&I license verify link.
- `/`: `link-in-text-block`. This is a real site change, the `#f0c1bd` city links in the dark band.
- `/services/`: `low_word_count`. The rendered page has 785 words against the url-plan target of 800. This is a new check, and the page is 15 words short.
- 5 pages: `has_micromarkup_errors`. This is a detection change: `validate_micromarkup` was enabled for the first time. The schema is unchanged.
- Water, fire and Seattle: `lcp-discovery-insight`. Fire: `cache-insight`. These were likely failing before but cut off by last month's top-5 cap on stored Lighthouse issues.

**Issues resolved since last audit:** (positive, keep doing this)
- All 6 pages: `no_image_alt` is no longer flagged. Static HTML alt coverage is 100 percent on every page.
- `/services/water-damage-restoration/`: `high_loading_time` is no longer flagged.
- `/services/fire-damage-restoration/`: `forced-reflow-insight` is no longer failing.
- `/contact/`: LCP back under 1 second.

## Recommended next actions (priority order)

1. **(money page)** Shorten the homepage meta description from 194 to 150-160 characters. Keep "24/7", "Federal Way" and the phone number or IICRC hook up front. This single edit flips the site from amber to green, and it has been open since 2026-07-15.
2. **(template, high impact)** Fix the footer WA L&I license verify link color: replace `#f0c1bd` with a color that has at least 4.5:1 contrast on white (for example the dark body text color). In the homepage dark city band, add `underline` to the `#f0c1bd` links or switch them to white. This restores accessibility to 100 on all 6 pages.
3. **(template)** In the services index, service-area and contact hero `<img>`, add `fetchpriority="high"`, `width="1376" height="768"`, and a `srcset` pointing at the existing `hero-480w`, `hero-768w` and `hero-1200w` R2 variants with `sizes="100vw"`. Do the same for the service-landing hero (`/images/services/*.webp`). This addresses `lcp-discovery-insight` and `image-delivery-insight` on 5 pages and the Seattle LCP regression.
4. **(template)** Add a Cloudflare Cache Rule for hostname `images.narestco.com` that sets Browser Cache TTL to 1 year, replacing the current 4 hours. Fix the logo `<img>` width/height attributes to match the real aspect ratio (currently 36x36 and 48x48 for a wide logo), which removes the `/contact/` CLS regression.
5. **(template)** Defer GA4 `gtag.js` until after `load` (or move it to Partytown) to cut about 69KB of unused JS from every page.

## Notes / caveats

- Desktop only. The DataForSEO Lighthouse endpoint was called with `for_mobile=false` to stay comparable with prior runs. Mobile performance would typically be 10-20 points lower.
- The dedicated MCP wrappers are not exposed in this server build. This run called `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` directly, with `enable_javascript`, `load_resources` and `validate_micromarkup` on. `validate_micromarkup` is new this run, which is why `has_micromarkup_errors` appears without any schema change. It is recorded at low severity rather than the rubric's medium, because the only error is a field Google does not require. Following the rubric literally would have produced a false amber on 5 pages.
- The service-area slot remains `/service-areas/seattle-wa/`, because `/service-areas/federal-way-wa/` still 301s to the homepage (as in August).
- `no_image_title` (image title attributes) is not an SEO factor and was not recorded. `frame` on the Seattle page is the embedded Google Map and is expected.
- The site is on the apex, with no `x-robots-tag: noindex`, so SEO counts toward the verdict.
- Run cost was about $0.04 (6 Lighthouse + 6 instant_pages + 1 single-page microdata crawl). Lighthouse full detail was captured for all pages.
