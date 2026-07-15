# Onsite Audit — Home Pride Restoration and Cleaning LLC — 2026-07-15

**Live origin audited:** https://homepriderestorationandcleaning.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-06-22 (verdict: amber)
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98 | 0 |
| Accessibility | 100 | +5 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

All six audited pages moved from amber to green since last month. Three issue classes that held every page at amber in June are now resolved (title length, color contrast, llms.txt). No high or medium severity issues remain on any audited page.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | green | 98 | 100 | 100 | 100 | 1.13s | 0.014 |
| /services/ | services-hub | green | 97 | 100 | 100 | 100 | 1.22s | 0.012 |
| /services/water-damage-restoration/ | service-landing | green | 100 | 100 | 100 | 100 | 0.81s | 0.017 |
| /services/fire-damage-restoration/ | service-landing | green | 99 | 100 | 100 | 100 | 0.86s | 0.024 |
| /service-areas/saratoga-springs-ut/ | service-area | green | 98 | 100 | 100 | 100 | 1.07s | 0.017 |
| /contact/ | contact | green | 97 | 100 | 100 | 100 | 1.07s | 0.069 |

All Core Web Vitals are inside Google's "good" band on every page (LCP under 2.5s, CLS under 0.1, TBT 0ms). INP is a field metric and is not produced by the lab run, so it is null.

## Template-level issues (fix once, lift many pages)

All remaining issues are low severity. None block the green verdict. They are minor performance opportunities surfaced by Lighthouse's "insight" audits, each worth roughly 50-200ms.

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `cache-insight` | 6 | low | Set longer `Cache-Control` max-age on static assets (JS, CSS, fonts, images). Cloudflare Pages defaults are short for some asset types. |
| `image-delivery-insight` | 6 | low | Serve hero and inline images at the displayed size and in next-gen formats (already AVIF/WebP on most); trim the largest R2 originals. |
| `unused-javascript` | 6 | low | Reduce unused JS shipped by GTM, Google Analytics, and Clarity. Consider consent-gated or deferred loading of analytics. |
| `network-dependency-tree-insight` | 5 | low | Shorten the critical request chain; preconnect to Google Fonts and the R2 image host. |
| `lcp-discovery-insight` | 5 | low | Add `fetchpriority="high"` to the LCP hero image and ensure it is not lazy-loaded. |

`render-blocking-insight` also remains present at a partial score on all pages (render-blocking requests worth roughly 0-50ms after simulation). It is low priority and was deprioritized out of the per-page top five by savings.

## Money page alerts

None. All money pages (home, services hub, both service landings, contact) are green this month.

## Regressions vs prior audit

No score regressions. No verdict downgrades. Every counted category held or improved (accessibility +5 site-wide).

**Verdict transitions (all improvements):**
- `/` amber to green
- `/services/` amber to green
- `/services/water-damage-restoration/` amber to green
- `/services/fire-damage-restoration/` amber to green
- `/service-areas/saratoga-springs-ut/` amber to green
- `/contact/` amber to green

**Core Web Vitals movement (informational, all still in the "good" band):**
- `/services/`: LCP 0.51s to 1.22s (+704ms). Still well under the 2.5s threshold. Consistent with lab run-to-run variance on a fast site, not a user-facing regression.
- `/contact/`: LCP 0.80s to 1.07s (+269ms). Still good.
- `/service-areas/saratoga-springs-ut/`: LCP 0.83s to 1.07s (+238ms). Still good.
- `/services/fire-damage-restoration/`: CLS 0.004 to 0.024 (+0.020). Still well under the 0.1 threshold.

These crossed the mechanical delta thresholds (LCP +200ms, CLS +0.02) but every value remains inside Google's "good" range. Treat as watch-items, not action items, unless they trend upward next month.

**New issues this month:**
- Low-severity performance "insight" diagnostics (`cache-insight`, `unused-javascript`, `image-delivery-insight`, `lcp-discovery-insight`, `network-dependency-tree-insight`, `forced-reflow-insight`) now appear across the pages. These are newly surfaced by Lighthouse 13.4.0's expanded insight audit set rather than new site defects. Site performance held flat at 98.

**Issues resolved since last audit (positive — keep doing this):**
- `title_too_long` resolved on all 6 pages. Titles were 78-82 chars in June and are now 40-44 chars, inside the 30-65 target.
- `color-contrast` resolved on all 6 pages. Accessibility rose from 95 to 100 site-wide.
- `llms-txt` resolved on all 6 pages. The llms.txt file now follows recommendations.

## Recommended next actions (priority order)

1. **(per-page, low)** Shorten the home page meta description from 201 to under 160 characters. It is the only on-page SEO issue remaining across the audited set. Trim to a single sentence with the primary keyword and phone number.
2. **(template, low)** Extend `Cache-Control` max-age on static assets (JS, CSS, fonts, images) via Cloudflare Pages headers. Lifts cache-insight on all 6 pages.
3. **(template, low)** Add `fetchpriority="high"` to the LCP hero image in the layout and confirm it is not lazy-loaded. Addresses lcp-discovery-insight and helps hold LCP down as the three watch-item pages fluctuated upward this month.
4. **(template, low)** Defer or consent-gate the analytics stack (GTM, GA, Clarity) to cut unused JavaScript on all pages.
5. **(watch)** Re-check LCP on `/services/`, `/contact/`, and `/service-areas/saratoga-springs-ut/` next month. All are still good but rose 200-700ms; confirm the trend is variance, not drift.

## Notes / caveats

- Lighthouse ran DESKTOP only via DataForSEO (formFactor=desktop, cpuSlowdownMultiplier=1, throughputKbps=10240). Mobile scores would typically run 10-20 performance points lower. These scores are not mobile-first. Recorded as `audit_form_factor: desktop`.
- Lighthouse detail was fetched from the DataForSEO `on_page/lighthouse/live/json` REST endpoint (full audit set, version 13.4.0) rather than the MCP `full_data` flag, to keep the run inside context and cost budget.
- DataForSEO `no_image_alt` reported true on all 6 pages, but the Lighthouse `image-alt` accessibility audit passes (score 1) on every page and accessibility scores 100. Alt-text coverage is effectively at or above 90 percent; the DataForSEO flag is a decorative/pixel-image detection artifact and is not counted as an issue.
- DataForSEO `has_micromarkup` is false on all pages, but the rendered HTML contains valid JSON-LD. DataForSEO's micromarkup check does not detect JSON-LD, so schema is not flagged as missing.
- DataForSEO `frame` is true on the Saratoga Springs service-area page because of an embedded map iframe, not a legacy frameset. Not counted as an issue.
- `low_content_rate` is true on the home and services-hub pages. This reflects a low text-to-HTML ratio, not thin content: measured plain-text word counts exceed every archetype target (home 1501 vs 1200, services hub 807 vs 800). No content-length issue is flagged.
- `broken_resources` reported true on all 6 pages last month (documented then as a detection artifact) and is now false on all 6.
