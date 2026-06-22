# Onsite Audit - National Restoration Construction - 2026-06-22

**Live origin audited:** https://narestco.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-05-17 (apex baseline)
**Form factor:** desktop only (DataForSEO Lighthouse MCP does not expose mobile; mobile perf would typically run 10-20 points lower)

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 96.3 | -1.0 |
| Accessibility | 83.2 | +0.2 |
| Best Practices | 77.0 | 0 |
| SEO | 92.0 | 0 |

Pages by verdict: green 0, amber 6, red 0, error 0

The site is stable month over month. No verdict transitions, no new red pages, and no site-level score drop large enough to flag (threshold is -3 per category). The whole site sits at amber for the same two structural reasons it did last month: Best Practices is pinned at 77 on every page, and the page titles run long. One real regression appeared on the services hub (see below).

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 89 | 77 | 77 | 92 | 2.1s | 0.003 |
| /services/ | services-hub | amber | 95 | 87 | 77 | 92 | 1.4s | 0.006 |
| /services/water-damage-restoration/ | service-landing | amber | 98 | 82 | 77 | 92 | 0.9s | 0.004 |
| /services/flood-damage-restoration/ | service-landing | amber | 99 | 82 | 77 | 92 | 0.8s | 0.004 |
| /service-areas/federal-way-wa/ | service-area | amber | 99 | 83 | 77 | 92 | 0.8s | 0.004 |
| /contact/ | contact | amber | 98 | 88 | 77 | 92 | 1.1s | 0.028 |

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `total-byte-weight` | 6 | high | All pages exceed the 1.6 MB recommended payload. Home is the outlier at 5.44 MiB (15 images); the rest are 2.1-2.5 MiB. Serve right-sized responsive images (`srcset`/`sizes`), confirm WebP/AVIF, and stop eager-inlining the full hero at full resolution. |
| `title_length_over_65` | 6 | medium | Every audited `<title>` is 71-75 chars. Trim the ` \| National Restoration Construction` brand suffix on interior pages (or shorten it) so titles land at 55-60 chars and are not truncated in SERPs. |
| `render_blocking_resources` | 6 | medium | One render-blocking script and one render-blocking stylesheet load in the shared layout on every page. Defer/async the script and inline critical CSS, deferring the rest. |

Best Practices is uniformly 77 on all 6 pages. Because the value is identical site-wide, the cause is layout-level (not page content) and almost certainly the third-party scripts detected on every page (Google Tag Manager, Google/Doubleclick Ads, Stripe). Pinning the exact failing audit requires a `full_data=true` Lighthouse drill on one URL, which is deferred this run to protect cost/context. See recommended action 3.

## Money page alerts

All five conversion-critical pages came back amber. Common cause across all of them is the site-wide Best Practices 77 plus long titles; per-page specifics below.

- **`/`** (home) - amber. Accessibility 77 (lowest on the site), Best Practices 77, Performance 89, LCP 2.1s. Heaviest page at 5.44 MiB. The low accessibility score and the page weight are both worth a closer look here.
- **`/services/`** (services hub) - amber, and the one real regression this month. Performance dropped 100 to 95 and LCP nearly doubled from 0.7s to 1.4s. See regression section.
- **`/services/water-damage-restoration/`** - amber. Best Practices 77, Accessibility 82. Also carries a relative `og:image` URL.
- **`/services/flood-damage-restoration/`** - amber. Best Practices 77, Accessibility 82.
- **`/contact/`** - amber. Best Practices 77, LCP 1.1s (up from 0.9s), CLS 0.028 (improved from 0.032 but still just over the 0.025 "solidly good" line).

## Regressions vs prior audit

Comparison baseline is the 2026-05-17 apex audit, using the identical 6-URL set.

**Score / metric regressions:**
- `/services/` (services hub): Performance 100 to 95 (-5, at the flag threshold) and LCP 715ms to 1391ms (+676ms). LCP nearly doubled. Likely cause: a newly added or newly heavier above-the-fold resource on the hub (image or third-party embed) since last month. Worth diffing the services-hub template against the 2026-05-17 deploy.
- `/contact/` (contact): LCP 889ms to 1103ms (+214ms). Still well within "Good" (under 2.5s) but trending up.

**Verdict transitions:** none. All six URLs were amber last month and remain amber.

**New issues this month:**
- `total-byte-weight` now recorded on all 6 URLs. This is a measurement-coverage change, not a confirmed new defect: the 2026-05-17 run did not extract this Lighthouse diagnostic, so there is no prior value to compare. From this run forward it is a tracked baseline. The home page at 5.44 MiB is the actionable part regardless of history.

**Issues resolved since last audit:** none structurally. On the positive side, `/contact/` CLS improved from 0.032 to 0.028.

## Recommended next actions (priority order)

1. **(money page, regression)** Investigate the `/services/` hub LCP regression (0.7s to 1.4s, Performance 100 to 95). Diff the services-hub template/hero against the 2026-05-17 build to find what was added above the fold, and lazy-load or right-size it.
2. **(template, high impact)** Cut home page weight. At 5.44 MiB it is more than 3x the other pages. Add `srcset`/`sizes` to the 15 homepage images, confirm WebP/AVIF delivery, and stop inlining the hero at full resolution. This is the single biggest performance lever and directly lifts the lowest-performing money page.
3. **(template)** Pin and fix the site-wide Best Practices 77. Run one on-demand `full_data=true` Lighthouse on `/contact/` to identify the failing best-practices audit (most likely third-party cookies / console errors from GTM + Doubleclick Ads), then fix it once in the shared layout to lift all pages.
4. **(template)** Shorten every `<title>` to 55-60 chars (currently 71-75). Trim or shorten the brand suffix on interior pages so titles are not truncated in search results.
5. **(per-page)** Two quick wins: trim the home page meta description from 194 to under 160 chars, and change the `/services/water-damage-restoration/` `og:image` from the relative path to an absolute `https://images.narestco.com/...` URL so social platforms render it.

## Notes / caveats

- **Desktop-only scoring.** Lighthouse ran desktop (`cpuSlowdownMultiplier=1`, `formFactor=desktop`) because the DataForSEO MCP wrapper does not expose a mobile form factor. Mobile performance would typically be 10-20 points lower. This is not mobile-first scoring; switch when the MCP exposes it.
- **Lighthouse failing-audit detail deferred.** The per-URL `opportunities`/`diagnostics` arrays require a `full_data=true` call (5-15MB per URL) that would blow up agent context, so it was skipped to protect the ~$0.30-0.50 cost target. `total-byte-weight` was available in the headline diagnostics and is captured. Findings are otherwise drawn from headline scores + instant_pages checks. Action 3 calls for a single targeted full_data drill.
- **Apex audit.** SEO counts toward the verdict (no staging noindex artifact). SEO is a flat 92 across all pages.
- **TBT/INP unavailable.** Total Blocking Time and INP are not returned in the Lighthouse headline response and are recorded as null, consistent with the prior baseline.
