# Onsite Audit - Katofsky Construction LLC - 2026-09-28

**Live origin audited:** https://staging.rankai-katofsky-construction-llc.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit
**Form factor:** desktop (DataForSEO Lighthouse wrapper runs desktop only; mobile performance would typically run 10-20 points lower)

> **STAGING CAVEAT: SEO score is inconclusive.** This audit ran against the Cloudflare Pages preview, which injects `x-robots-tag: noindex` (verified via `curl -sI`). That fails the Lighthouse `is-crawlable` audit on every page and pins SEO at 69. SEO is excluded from all verdicts below; verdicts use Performance, Accessibility and Best Practices only. Re-audit after the apex cutover to get a real SEO score.

First audit for this client - no comparison data.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 97 | n/a |
| Accessibility | 96 | n/a |
| Best Practices | 100 | n/a |
| SEO | 69 (inconclusive, staging noindex) | n/a |

Pages by verdict: {green: 5, amber: 1, red: 0, error: 0}

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 97 | 100 | 100 | 69* | 1.3s | 0.02 |
| /services/ | services-hub | green | 97 | 95 | 100 | 69* | 1.3s | 0.00 |
| /services/fire-damage-restoration/ | service-landing | green | 96 | 95 | 100 | 69* | 1.3s | 0.00 |
| /services/roofing/ | service-landing | green | 97 | 95 | 100 | 69* | 1.3s | 0.00 |
| /service-areas/penn-hills-pa/ | service-area | green | 97 | 95 | 100 | 69* | 1.3s | 0.00 |
| /contact/ | contact | green | 97 | 96 | 100 | 69* | 1.3s | 0.02 |

\* SEO excluded from verdict (staging noindex artifact). TBT was 0 ms on every page except /services/roofing/ (54 ms). INP not reported by lab Lighthouse.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | Replace /images/logo.png with a WebP or SVG sized for display (~200px tall max, target under 15 KB); add srcset/sizes to hero-bg.webp |
| `render-blocking-insight` | 6 | low | Inline the ~8.8 KB /_astro/*.css critical CSS in the layout head (Astro build.inlineStylesheets: 'always') |
| `is-crawlable` | 6 | low | None on staging. Resolves at apex cutover; re-audit then |
| `color-contrast` | 5 | medium | Change breadcrumb link class text-dark/50 to text-dark/70 (or #5f6368, 6.0:1) in the breadcrumb component |
| `lcp-discovery-insight` | 5 | medium | Add fetchpriority="high" to the hero <img> in the inner-page hero component |

## Money page alerts

- **`/`** - verdict: amber. Lighthouse is fully green (Perf 97, A11y 100, BP 100, LCP 1.3s). The amber comes from the on-page check: the meta description is 185 characters, over the 160-character limit, so Google will truncate it mid-sentence before the phone number.

## Per-page on-page findings

- `/`: `rankai_meta_description_too_long` (medium). 185 characters.
- `/services/`: `rankai_word_count_below_target` (low). 695 words vs url-plan target 800.
- `/service-areas/penn-hills-pa/`: `frame` (low). Google Maps embed iframe; expected, no action needed. Also `cache-insight` (low) for the Google Maps static image and JS (~31 KiB), which is third-party and not fixable on our side.
- All 6 pages: titles 33-65 characters, single H1, self-canonical to the apex URL, no broken links or resources, no mixed content, 100% image alt coverage, valid JSON-LD (LocalBusiness on every page, Service on service landings, FAQPage and BreadcrumbList on inner pages).

## Recommended next actions (priority order)

1. **(staging, blocks SEO scoring)** Cut over the apex domain and re-audit. katofskyconstruction.com currently resolves to 15.197.148.33 / 3.33.130.190 (not Cloudflare) and gave no HTTPS response during this run. Point DNS at the Cloudflare Pages project, record `apex_cutover.completed_at`, then re-run this audit so the SEO category is scored for real.
2. **(money page)** Shorten the homepage meta description from 185 to at most 160 characters. Edit `meta_description` for `/` in `clients/katofsky-construction-llc/plan/url-plan.json` and rebuild. Suggested: "24/7 water, fire, mold and storm damage restoration in Pittsburgh. Licensed, insured, IICRC-certified. Call (412) 304-9284." (123 characters).
3. **(template, high impact, all 6 pages)** Replace `/images/logo.png`. It is a 682 KB, 1200x800 PNG rendered at about 96px tall in the header, and again in the footer, on every page. Lighthouse estimates 666 KiB wasted per page. Export it as SVG, or as a WebP around 200px tall (under 15 KB), and update the header and footer `<img>` src. Lighthouse estimates 500-600 ms LCP savings per page from image delivery overall.
4. **(template, 5 pages incl. /contact/ and both service landings)** Add `fetchpriority="high"` to the hero `<img>` in the inner-page hero component (`main > section.relative > div.absolute > img.w-full`). The homepage hero already has it; the inner pages do not. While in there, add `srcset`/`sizes` to `/images/hero-bg.webp` (135 KiB wasted on /contact/, 92 KiB on /services/).
5. **(template, accessibility, 5 pages)** Darken the breadcrumb links. `a.text-dark/50` renders #888c93 on white at 3.37:1 (needs 4.5:1). Change to `text-dark/70` or a fixed #5f6368 in the breadcrumb component. This takes Accessibility from 95 to 100 on every inner page.

## Notes / caveats

- live_origin_source=staging: client record has apex_cutover=null, so the Cloudflare Pages preview was audited. katofskyconstruction.com currently resolves to 15.197.148.33 / 3.33.130.190 (not Cloudflare) and returned no HTTPS response to curl during this run.
- Cloudflare Pages preview returns x-robots-tag: noindex (verified via curl -sI). The Lighthouse is-crawlable audit fails on all 6 URLs and deflates the SEO category to 69. SEO is EXCLUDED from all verdicts this run and is inconclusive - staging noindex artifact, re-audit after apex cutover.
- Lighthouse ran DESKTOP only via DataForSEO (formFactor=desktop, cpuSlowdownMultiplier=1, throughputKbps=10240). Mobile scores would typically run 10-20 performance points lower. Do not read these as mobile-first scores.
- Client record status is "onboarding", not "active". build_status is pushed_main and the staging preview returns 200 on all 6 URLs, so the audit proceeded (same precedent as other onboarding clients).
- Canonical tags on staging correctly point at the apex https://katofskyconstruction.com/... URLs. Expected pre-cutover, not counted as a canonical issue.
- DataForSEO has_micromarkup=false on all pages because it checks microdata only; JSON-LD is present on every page (LocalBusiness everywhere; Service on service landings; FAQPage and BreadcrumbList on inner pages). Not counted as missing schema.
- URL selection: auto-derived from `plan/url-plan.json` (no `audit-urls.txt`). Four service landings tie at priority 9.0; the first two in plan order (fire-damage-restoration, roofing) were used. No service area is marked `primary` and the client record has no business address city, so the first service area (penn-hills-pa) was used.
- Lower-severity items not in the top list: `render-blocking-insight` (8.8 KB /_astro stylesheet, 0 ms estimated savings) and `network-dependency-tree-insight` (Google Fonts critical chain) on all pages. Worth self-hosting the font when the template is next touched.
- DataForSEO cost this run: about $0.04 (6 Lighthouse at $0.005 + 6 instant_pages at $0.0018, plus one headline Lighthouse probe).
