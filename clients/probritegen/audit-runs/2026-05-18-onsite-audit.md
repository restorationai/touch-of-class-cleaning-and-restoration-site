# Onsite Audit — ProBrite Gen — 2026-05-18 (first baseline)

**Live origin audited:** `https://probritegen.com` (apex)
**Site verdict:** red (URGENT)
**URLs audited:** 6
**Prior audit:** none — this is the first baseline.

## Site rollup

| Metric | Score |
| --- | ---: |
| Performance | 72.2 |
| Accessibility | 75 |
| Best Practices | 77 |
| SEO | 83 |

Pages by verdict: 0 green, 2 amber, 4 red

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 70 | 75 | 77 | 83 | 5.2s | 0.137 |
| `/water-damage/` | service-landing | red | 65 | 75 | 77 | 83 | 6.8s | 0.207 |
| `/mold-remediation/` | service-landing | red | 65 | 75 | 77 | 83 | 6.7s | 0.207 |
| `/sewage-backup/` | service-landing | red | 70 | 75 | 77 | 83 | 4.2s | 0.172 |
| `/hot-water/` | service-landing | amber | 77 | 75 | 77 | 83 | 2.4s | 0.208 |
| `/contact/` | contact | amber | 86 | 75 | 77 | 83 | 2.4s | 0.075 |

## Template-level issues (fix once, lift many pages)

| Issue ID | Affected URLs | Severity | Description |
| --- | ---: | --- | --- |
| `a11y_below_threshold` | 6 | medium | Accessibility 75 |
| `bp_below_threshold` | 6 | medium | Best Practices 77 (likely 3rd-party script console errors) |
| `cls_needs_improvement` | 5 | medium | CLS is 0.137 (Needs Improvement: > 0.1) |
| `lcp_poor` | 4 | high | LCP is 5202ms (Poor: > 4000ms) |
| `large_total_byte_weight` | 4 | medium | Page weight is 20.5MB |
| `perf_below_threshold` | 2 | high | Performance 65 (target ≥ 70 amber, ≥ 90 green) |

## Money page alerts (all 6 audited URLs are money pages)

- **`/`** (home) — verdict red. performance score 70, LCP 5202ms, CLS 0.137
- **`/water-damage/`** (service-landing) — verdict red. performance score 65, LCP 6753ms, CLS 0.207
- **`/mold-remediation/`** (service-landing) — verdict red. performance score 65, LCP 6738ms, CLS 0.207
- **`/sewage-backup/`** (service-landing) — verdict red. performance score 70, LCP 4243ms, CLS 0.172
- **`/hot-water/`** (service-landing) — verdict amber. accessibility score 75, LCP 2400ms, CLS 0.208
- **`/contact/`** (contact) — verdict amber. accessibility score 75, LCP 2371ms, CLS 0.075

## What's actually wrong

ProBrite Gen's site is functionally working but has serious technical debt:

1. **Massive page weight on critical pages.** Homepage is **21.5 MB** and service pages are **10-12 MB** each. Compared to a healthy restoration site (~2-5 MB), this is 4-10x oversized. Likely cause: hero images and gallery images are loaded eagerly at full resolution.

2. **LCP failure on money pages.** Water damage, mold remediation, and sewage backup all have LCP of 4-7 seconds. Core Web Vitals "Poor" threshold is 4 seconds. Google uses this as a ranking signal — these pages will lose to faster competitors regardless of content quality.

3. **CLS failure across the board.** All 5 service pages have CLS in the 0.13-0.21 range. CWV "Poor" is > 0.25, "Good" is < 0.1. Layout is shifting after the page renders — likely fonts loading without `font-display: optional` or images without explicit width/height attributes.

4. **Accessibility = 75 site-wide.** Common causes on hand-built React sites: missing form labels, low color contrast, missing alt text, non-semantic interactive elements.

5. **Best Practices = 77 site-wide.** Almost certainly the same 3rd-party script console errors we see on narestco (Stripe, Supabase, Tailwind CDN, the restorationai chat widget). 1 specific failing audit ID would confirm — requires a `full_data: true` Lighthouse re-call.

## Recommended next actions (priority order)

1. **(critical, all service pages) Add `loading="lazy"` to gallery + below-fold images.** Service pages average 10MB because every image loads eagerly. Lazy-loading below-fold images alone will cut LCP by ~3 seconds.

2. **(critical, all pages) Set explicit `width`/`height` on `<img>` tags.** Lighthouse CLS scores of 0.17-0.21 are caused by images popping into the layout after initial render. Explicit dimensions reserve space.

3. **(critical, homepage) Inspect the 21.5 MB payload.** Open browser DevTools → Network → filter Images → sort by size. The top 3-5 files are almost certainly uncompressed PNGs that should be WebP at 80% quality. Same playbook we used for narestco (~70% size reduction).

4. **(template) Identify the Best Practices = 77 cause.** Run `full_data: true` Lighthouse on `/` and grep for failing audit IDs. Likely `errors-in-console` or `inspector-issues`.

5. **(template) Audit the React form components for missing aria-labels.** The Header, Contact form, and Footer likely have a few interactive elements without accessible names.

## Notes / caveats

- **Audit form factor: desktop.** DataForSEO Lighthouse MCP runs desktop-only. Mobile scores would be 10-20 perf points lower — meaning the mobile LCP on water-damage and mold-remediation is probably 9-10 seconds, not 6-7.
- **instant_pages calls failed this run** with a transient API error. Re-run them later for on-page check details (title length, schema, render-blocking resources).
- **Significant gap vs narestco.** Narestco's Astro-based Rank AI site averages Performance 97 and CLS 0.005. ProBrite Gen averages Performance 72 and CLS 0.17. The technical debt here is meaningful but fixable.

## Next scheduled audit

30 days out: 2026-06-17.
