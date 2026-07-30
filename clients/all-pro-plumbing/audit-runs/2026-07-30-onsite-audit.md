# Onsite Audit - All Pro Plumbing Heating and Air - 2026-07-30

**Live origin audited:** https://allproplumbingheatingandair.com (apex)  
**Form factor:** desktop (see caveats)  
**Site verdict:** amber  
**URLs audited:** 6  
**Prior audit:** first audit for this client - no comparison data

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 99.3 | n/a |
| Accessibility | 93.5 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 100.0 | n/a |

Pages by verdict: green: 4, amber: 2, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 99 | 93 | 100 | 100 | 0.87s | 0.017 | 0ms |
| `/services/` | services-hub | amber | 99 | 91 | 100 | 100 | 0.87s | 0.026 | 0ms |
| `/services/emergency-plumbing/` | service-landing | green | 99 | 95 | 100 | 100 | 0.80s | 0.054 | 0ms |
| `/services/drain-cleaning/` | service-landing | green | 99 | 95 | 100 | 100 | 0.85s | 0.005 | 0ms |
| `/service-areas/bakersfield-ca/` | service-area | green | 100 | 95 | 100 | 100 | 0.81s | 0.026 | 0ms |
| `/contact/` | contact | green | 100 | 92 | 100 | 100 | 0.65s | 0.016 | 0ms |

INP is null on every page: Lighthouse lab runs do not produce an INP value without real user interaction.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Peak per-page saving | Recommended fix |
| --- | ---: | --- | --- | --- |
| `image-delivery-insight` | 6 | high | 316KB / 100ms | `/images/logo.webp` is a 640x623 / 107KB file rendered into a 131x128 slot in `header.bg-white > a.flex > img.h-28`. Export it at 262x256 and re-compress. Saves about 103KB on every page of the site. |
| `render-blocking-insight` | 6 | high | 55ms | `/_astro/_slug_.CyZTOTvo.css` (8.6KB) blocks first paint on all 6 pages. Inline the above-the-fold rules in the Astro layout head and load the remainder with `media="print" onload="this.media='all'"`. |
| `color-contrast` | 5 | high | n/a | Breadcrumb links use `a.text-dark/50` (50% opacity on dark) and fail WCAG AA. Raise to `text-dark/70` or darker. `a.btn-accent` / `span.btn-accent` also fail on 3 pages: darken the accent token or switch its label to white. |
| `lcp-discovery-insight` | 5 | high | n/a | The hero image `main.flex-1 > section.relative > div.absolute > img.w-full` is the LCP element but is discovered late. Add `fetchpriority="high"` and `loading="eager"` to the hero `<img>` in the shared page layout, and drop any `loading="lazy"` on it. |
| `link-in-text-block` | 3 | high | n/a | In-prose links are distinguished by color alone (`div.prose-body > p > a`). Add `text-decoration: underline` to links inside `.prose-body` and homepage body copy. |
| `meta_description_length_off` | 2 | medium | n/a | Trim the meta description to 160 characters or fewer so Google does not truncate it in the SERP. |
| `network-dependency-tree-insight` | 6 | low | n/a | Informational. The critical chain is only 2 levels deep and completes in about 247ms. No action needed at current LCP. |
| `cache-insight` | 6 | low | 11KB | The flagged asset is Cloudflare's own injected `email-decode.min.js` (957 bytes), plus Google Maps tiles on the Bakersfield page. Both are third-party controlled. No action available. |
| `has_render_blocking_resources` | 6 | low | n/a | DataForSEO's restatement of the render-blocking CSS above. Same fix. |
| `no_image_title` | 6 | low | n/a | Informational only. Images have no `title` attribute, which is not an SEO or accessibility requirement. Alt coverage is 100% on all 6 pages. Do not action. |

## Money page alerts

- **`/`** (home) - verdict: amber. Meta description is 170 chars (target 70-160). Lighthouse scores are otherwise clean (perf 99, BP 100, SEO 100); the meta description length is the only thing holding this page below green.
- **`/services/`** (services-hub) - verdict: amber. Meta description is 173 chars (target 70-160). Lighthouse scores are otherwise clean (perf 99, BP 100, SEO 100); the meta description length is the only thing holding this page below green.

## Regressions vs prior audit

First audit for this client - no comparison data. This run establishes the baseline that next month's audit will diff against.

## Recommended next actions (priority order)

1. **(money page)** Trim the meta description on `/` from 170 to 160 characters or fewer, and on `/services/` from 173 to 160 or fewer. These two overruns are the only reason the site is amber rather than green. Both are money pages and both descriptions will currently truncate in the SERP.
2. **(template, highest impact)** Replace `/images/logo.webp`. It is exported at 640x623 and 107KB but displays at 131x128 in the header, wasting about 103KB on all 6 audited pages and every other page on the site. Re-export at 262x256 for 2x displays.
3. **(template, accessibility)** Fix the WCAG AA contrast failures. Breadcrumb `a.text-dark/50` fails on 5 of 6 pages; `.btn-accent` fails on 3. This is the single largest drag on the accessibility average (93.5).
4. **(template, Core Web Vitals)** Add `fetchpriority="high"` to the hero `<img>` in the shared layout. The hero is the LCP element on 5 of 6 pages and is currently discovered late by the preload scanner.
5. **(template, performance)** Inline the above-the-fold portion of `_astro/_slug_.CyZTOTvo.css` and defer the rest. It render-blocks all 6 pages, costing 50-55ms of measured FCP delay on the pages where Lighthouse attributed a saving.

## Notes / caveats

- Lighthouse ran DESKTOP only (cpuSlowdownMultiplier=1, throughputKbps=10240, formFactor=desktop). Mobile scores would typically run 10-20 performance points lower. Not mobile-first scoring.
- Apex audited (cutover completed 2026-07-23). No x-robots-tag: noindex on any audited URL, so the staging SEO-exclusion correction does not apply and SEO counts toward the verdict.
- Lighthouse 13.4.0 reports the newer *-insight audit IDs (image-delivery-insight, render-blocking-insight, lcp-discovery-insight, cache-insight, network-dependency-tree-insight) in place of the older opportunity IDs.
- DataForSEO check has_micromarkup returns false on all 6 URLs; this is a false negative for JSON-LD. Schema was verified directly from the served HTML and parses as valid JSON-LD on all 6 pages.
- No broken internal or external links, no mixed content, no duplicate titles, and exactly one canonical and one H1 on every audited page.
- Image alt coverage is 100% on all 6 pages (10 images on the homepage, 25 on the services hub, 3 elsewhere).
- Valid JSON-LD is present on all 6 pages: LocalBusiness sitewide, plus Service and FAQPage on the two service landings, BreadcrumbList on 5 of 6, and Organization / WebSite on the homepage, services hub, and contact page.
- `/services/emergency-plumbing/` tripped DataForSEO's `high_loading_time` flag (2023ms TTFB on a single cold fetch), but Lighthouse measured an 87ms server response and a 796ms LCP on the same URL moments later. Treated as a cold-cache probe artifact, not a site issue. Worth re-checking next month.
- Best Practices and SEO are a clean 100 on all 6 URLs.
