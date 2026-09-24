# Onsite Audit - Frontline Fire & Flood - 2026-09-24

**Live origin audited:** https://frontlinefireflood.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit (no comparison data)
**Form factor:** desktop only (the DataForSEO Lighthouse wrapper does not run mobile; expect mobile performance 10-20 points lower)

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 98.7 | n/a |
| Accessibility | 96.0 | n/a |
| Best Practices | 96.0 | n/a |
| SEO | 100.0 | n/a |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

The site is in good technical shape. The only reason it is amber is one medium on-page issue on the homepage (meta description too long). No broken links, no mixed content, canonicals all self-referencing, valid JSON-LD on every page, 100% image alt coverage, one H1 per page.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 98 | 100 | 96 | 100 | 1.1s | 0.035 |
| /services/ | services-hub | green | 98 | 95 | 96 | 100 | 0.9s | 0.003 |
| /services/fire-damage-restoration/ | service-landing | green | 99 | 95 | 96 | 100 | 1.0s | 0.004 |
| /services/mold-remediation/ | service-landing | green | 99 | 95 | 96 | 100 | 0.9s | 0.008 |
| /service-areas/tacoma-wa/ | service-area | green | 99 | 95 | 96 | 100 | 1.0s | 0.007 |
| /contact/ | contact | green | 99 | 96 | 96 | 100 | 0.9s | 0.032 |

TBT was 0 ms on every page. INP was not reported (lab run).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | medium | `/images/logo.png` is 266 KB (1422x260 PNG) but shows at about 386x80 in the header and footer. Export a 800px-wide WebP (or SVG) logo and swap it in the layout. Saves about 258 KB per page. Inner-page `hero-bg.webp` (154 KB) also needs a `srcset` with 768w/1280w variants. |
| `image-aspect-ratio` | 6 | low | Footer logo (`footer img.h-16`) renders at 4.83:1 while the file is 5.47:1, so it is squashed. Add `width="1422" height="260"` plus `object-contain`, or drop the fixed width so `w-auto` keeps the real ratio. |
| `color-contrast` | 5 | medium | Breadcrumb "HOME" link uses `text-dark/50` (contrast 3.4:1, needs 4.5:1). Change the breadcrumb component to `text-dark/70` or darker. Every page with breadcrumbs is affected. |
| `lcp-discovery-insight` | 5 | low | The inner-page hero image (`section.relative > div.absolute > img`) is the LCP element but has no `fetchpriority="high"`. The homepage hero already has it; copy that attribute into the shared page-hero component. |
| `render-blocking-insight` / `has_render_blocking_resources` | 6 | low | A single 9 KB Astro CSS bundle (`_slug_.*.css`) blocks render for about 50 ms. Optional: inline critical CSS with Astro `build.inlineStylesheets: "auto"`. Low priority at these scores. |
| `no_image_title` | 6 | low | Cosmetic DataForSEO check (no `title` attribute on images). Alt text is already 100%. No action needed. |

## Money page alerts

- **`/`** (home): verdict amber. The meta description is 180 characters, so Google will cut it off before the phone number and "IICRC-certified". Performance and Core Web Vitals are fine (Perf 98, LCP 1.1s).

## Regressions vs prior audit

First audit for this client, so there is nothing to compare against. This run is the baseline for next month.

## Recommended next actions (priority order)

1. **(money page)** Shorten the homepage meta description from 180 to 160 characters or fewer and keep the phone number in it. For example: "24/7 water, fire, mold & storm damage restoration in Lakewood, WA. Licensed, insured, IICRC-certified. Call (253) 200-0503." (123 chars). Update the source in `plan/url-plan.json` so a rebuild does not bring the long version back.
2. **(template, high impact)** Replace the 266 KB `/images/logo.png` in the header and footer with a resized WebP or SVG (about 800px wide, under 20 KB). This removes about 258 KB from every page on the site.
3. **(template, accessibility)** Change the breadcrumb link color from `text-dark/50` to `text-dark/70` or darker to pass WCAG AA 4.5:1. This fixes the only accessibility failure on 5 of the 6 audited pages.
4. **(template)** Add `fetchpriority="high"` to the inner-page hero `<img>` and give `hero-bg.webp` responsive `srcset` sizes (the contact page wastes 105 KB on it).
5. **(template)** Fix the footer logo aspect ratio by adding intrinsic `width`/`height` and `object-contain` so it is no longer squashed.

## Notes / caveats

- Audited the apex production domain (cut over 2026-09-11). No staging noindex correction was needed, and SEO counts toward the verdict. The `x-robots-tag` header is absent on the apex.
- URLs came from Mode B (auto-derived from `plan/url-plan.json`). Service landings are the two highest-priority entries (both 9.0, tied with `/services/water-damage-restoration/`, picked by plan order). No `/service-areas/lakewood-wa/` page exists (Lakewood is the home city and is covered by the homepage), so the first service area, Tacoma, was used.
- Lighthouse was run desktop-only, so mobile scores will be lower. Re-check mobile manually in PageSpeed Insights if a mobile KPI is needed.
- The `cache-insight` flag comes from Cloudflare's injected `email-decode.min.js` (2-day TTL, 0 KiB real savings). It is not actionable in the site code. Turning off Cloudflare Email Obfuscation would remove it.
- Word counts all meet plan targets (home 1595/1200, hub 817/800, landings about 1900/1100, Tacoma 1369/900, contact 704/400).
- The Tacoma page flags `frame` (embedded map iframe). This is expected.
