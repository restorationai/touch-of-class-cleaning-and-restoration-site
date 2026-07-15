# Onsite Audit - National Restoration Construction - 2026-07-15

**Live origin audited:** https://narestco.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-06-22 (apex)
**Form factor:** desktop (DataForSEO Lighthouse MCP is desktop-only; mobile would run 10-20 perf points lower)

This is a big month. The build push earlier today (2026-07-15) resolved almost every issue from the prior audit: home payload dropped from 5.44 MiB to 1.01 MiB, accessibility went 77 to 100 site-wide, best practices 77 to 100, page titles were shortened from 75 to about 50 characters, and SEO went 92 to 100. Five of six pages are now green. The only thing holding the site at amber is a single over-length meta description on the homepage.

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 98.5 | +2.17 |
| Accessibility | 100 | +16.83 |
| Best Practices | 100 | +23.0 |
| SEO | 100 | +8.0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 98 | 100 | 100 | 100 | 1.2s | 0.006 |
| /services/ | services-hub | green | 98 | 100 | 100 | 100 | 1.2s | 0.003 |
| /services/water-damage-restoration/ | service-landing | green | 99 | 100 | 100 | 100 | 1.0s | 0.004 |
| /services/fire-damage-restoration/ | service-landing | green | 98 | 100 | 100 | 100 | 1.1s | 0.004 |
| /service-areas/federal-way-wa/ | service-area | green | 100 | 100 | 100 | 100 | 0.6s | 0.004 |
| /contact/ | contact | green | 98 | 100 | 100 | 100 | 1.1s | 0.028 |

Total blocking time and INP were not returned in the headline Lighthouse response and are recorded as null in the state file. All schema.org markup verified present on money pages (LocalBusiness, Organization, Service, FAQPage, BreadcrumbList, AggregateRating). No mixed content, no broken links, canonicals self-reference correctly, single H1 per page.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `has_render_blocking_resources` | 6 | low | One render-blocking script plus one stylesheet in the shared layout. Performance is unaffected (all pages 98-100, LCP under 1.2s), so this is cosmetic. Add `defer` to the layout script to clear the last Lighthouse opportunity; leave the critical CSS stylesheet as-is. |
| `low_content_rate` | 2 | low | DataForSEO flags a low text-to-HTML ratio on `/` and `/services/`. Word counts are adequate; the ratio is low because of component-heavy markup. No action required beyond the services-hub word-count note below. |

## Money page alerts

- **`/`** (home) - verdict: amber. All Lighthouse categories score 98-100. The single blocker is the meta description at 194 characters (limit 160). Google truncates around 155-160 characters, so the tail is wasted. This is the only issue keeping the whole site from an all-green verdict.

## Regressions vs prior audit

No regressions. Every metric on every carried-over URL improved or held steady within threshold. Recorded changes are all positive:

**Verdict transitions (all upward):**
- `/services/` went amber to green.
- `/services/water-damage-restoration/` went amber to green.
- `/service-areas/federal-way-wa/` went amber to green.
- `/contact/` went amber to green.
- `/` stayed amber (meta description still over length).

**Issues resolved since last audit (positive - keep doing this):**
- Page titles trimmed to 46-50 characters on all pages (was 71-75, `title_length_over_65` cleared everywhere).
- Total payload now under the 1.6 MB recommendation on all pages. Home dropped from 5.44 MiB to 1.01 MiB; the rest sit at 0.55-1.32 MiB (`total-byte-weight` cleared everywhere).
- `/`: LCP improved from 2076ms to 1199ms (`largest_contentful_paint_borderline` cleared).
- `/services/water-damage-restoration/`: og:image is now an absolute URL (`og_image_relative_url` cleared).
- Site-wide accessibility 77 to 100 and best practices 77 to 100.

**New issues this month (low severity):**
- `/` and `/services/`: `low_content_rate` newly surfaced (low text-to-HTML ratio). Word counts are fine; likely present before but not captured. No action required.
- `/services/`: body copy is 790 words against the 800-word services-hub target (10 short).

## Recommended next actions (priority order)

1. **(money page, home)** Trim the homepage meta description from 194 to 160 characters or fewer. It is the only issue holding the site at amber. The current text ("National Restoration Construction provides 24/7 water, fire, mold, and storm damage restoration across Federal Way and surrounding areas. Licensed, insured, IICRC-certified. Call (206) 883-0333.") runs long. Shorten "across Federal Way and surrounding areas" to "in Federal Way" and cut one certification adjective to land under 160 while keeping the phone number.
2. **(template, low)** Add `defer` to the single render-blocking script in the shared layout. Present on all six pages. Impact on scores is negligible today (perf 98-100), so this is housekeeping, not urgent. Leave the render-blocking stylesheet (critical CSS) alone.
3. **(per-page, low)** Add one or two sentences to a section intro on `/services/` to clear the 800-word target (currently 790) and quiet the low-content-rate flag.
4. **(per-page, low)** `/contact/` CLS is 0.028. Still inside Google's "Good" band (under 0.1) but above our internal 0.025 target. Reserve explicit height for the hero image and the estimate form so late-loading elements stop nudging layout.

## Notes / caveats

- **Environment:** apex production (`https://narestco.com`), served through Cloudflare. No staging noindex correction needed; SEO counts toward the verdict normally and scores 100 on every page.
- **Form factor:** desktop only. The DataForSEO Lighthouse MCP wrapper does not expose a mobile form factor. Mobile scores would typically run 10-20 performance points lower. This is not a mobile-first score.
- **Lighthouse detail deferred:** full_data (opportunities/diagnostics arrays) was not pulled this run because all four categories scored 98-100 on every URL, leaving no material failing audits to drill. total-byte-weight was read from the headline diagnostics. Pull full_data on demand if a category regresses next month.
- **URL set change:** `url-plan.json` was regenerated today and three service-landings now tie at priority 9.0 (fire, mold, water). We audited water-damage-restoration (tied-top, and preserves month-over-month continuity) and fire-damage-restoration (tied-top, alphabetically first of the remaining). flood-damage-restoration, audited last month, is no longer a top-priority landing and was dropped, so it has no comparison this run.
- **Severity recalibration:** the render-blocking finding was `medium` last month and is `low` this month. Same underlying condition (1 script + 1 stylesheet in the layout); the downgrade reflects that performance is now near-perfect, so the render-block no longer carries real cost. The prior id `render_blocking_resources` is normalized to the real DataForSEO check id `has_render_blocking_resources`.
- **Prior stray artifact:** an earlier run today aborted (DataForSEO MCP had not finished connecting) and left an "ABORTED" placeholder at this path. This report supersedes it.
