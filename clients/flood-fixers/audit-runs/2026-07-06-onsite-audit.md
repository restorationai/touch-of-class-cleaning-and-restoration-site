# Onsite Audit — Flood Fixers — 2026-07-06

**Live origin audited:** https://flood-fixers.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client — no comparison data
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98 | n/a |
| Accessibility | 90 | n/a |
| Best Practices | 100 | n/a |
| SEO | 100 | n/a |

Accessibility mean is 89.7 (rounded to 90); it is pulled down by the homepage (86). All other pages score 90-91.

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 96 | 86 | 100 | 100 | 1.45s | 0.011 |
| /services/ | services-hub | green | 95 | 90 | 100 | 100 | 1.48s | 0.002 |
| /services/water-damage-restoration/ | service-landing | green | 100 | 90 | 100 | 100 | 0.80s | 0.003 |
| /services/flood-damage-restoration/ | service-landing | green | 100 | 90 | 100 | 100 | 0.81s | 0.003 |
| /service-areas/san-diego-ca/ | service-area | green | 99 | 91 | 100 | 100 | 0.86s | 0.003 |
| /contact/ | contact | green | 99 | 91 | 100 | 100 | 0.87s | 0.023 |

TBT and INP are not shown: the reduced Lighthouse response does not return total-blocking-time or interaction-to-next-paint. They are recorded as null in the state file rather than guessed.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `has_render_blocking_resources` | 6 | low | Each page ships 1 render-blocking script and 1 render-blocking stylesheet from the shared layout. Performance is already 95-100 desktop, so this is low priority, but inlining the critical CSS for above-the-fold and deferring the single layout script would harden mobile scores when mobile auditing lands. |
| `relative_og_image` | 2 | low | The two service-landing pages set `og:image` to a relative path (e.g. `/services/water-damage-restoration.webp`). Social and messaging scrapers require an absolute URL. Change the service-landing template to emit an absolute `https://images.flood-fixers.com/...` (or full-origin) og:image, matching the home/contact/service-area pages which already do. |

## Money page alerts

- **`/`** (home) — verdict: amber. Accessibility 86, the only sub-90 category anywhere in this audit. Performance (96), Best Practices (100), SEO (100), LCP 1.45s and CLS 0.011 are all healthy. The homepage is the highest-traffic entry point, so the accessibility gap is worth closing. Specific failing audits were not pulled this run (full_data deferred — see caveats); enumerate them via an on-demand full_data Lighthouse run or a browser Lighthouse pass on the homepage before fixing.

## Regressions vs prior audit

First audit for this client. No prior `onsite-audit.json` existed, so regression detection was skipped. This run becomes the baseline for next month.

## Recommended next actions (priority order)

1. **(money page, home)** Diagnose and fix the homepage accessibility gap (86 vs 90+ elsewhere). Because full_data was deferred, run a browser Lighthouse accessibility pass (or an on-demand `full_data: true` call) on `https://flood-fixers.com/` to get the exact failing audit IDs, then remediate. Homepage-specific elements (hero, top nav with 33 links, multi-section layout) are the likely source; common culprits at this score band are color-contrast and link/button accessible names, but confirm before changing.
2. **(template)** Switch the service-landing `og:image` to an absolute URL. Currently `/services/water-damage-restoration/` and `/services/flood-damage-restoration/` emit relative og:image paths, which break link previews on social and messaging platforms. One template edit fixes both (and every other service-landing page site-wide).
3. **(per-page, home)** Trim the homepage meta description from 171 to under 160 characters so Google does not truncate it in the SERP. Current: "Flood Fixers provides 24/7 water, fire, mold, and storm damage restoration across San Diego and surrounding areas. Licensed, insured, IICRC-certified. Call (855) 204-1124."
4. **(per-page, services hub)** `/services/` has 750 words against an 800-word archetype target. Add roughly 50-100 words (a short paragraph on response time or coverage) to clear the threshold. Low priority; the page is otherwise green.
5. **(template, low)** Address render-blocking resources in the shared layout (inline critical CSS, defer the single layout script). Desktop performance is already excellent, so treat this as mobile-readiness hardening rather than an urgent fix.

## Notes / caveats

- **Desktop-only scoring.** Lighthouse ran through the DataForSEO MCP wrapper, which does not expose a form_factor/strategy parameter and runs desktop only (`formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`). Mobile performance would typically land 10-20 points lower. These scores are not mobile-first. Re-evaluate if a future MCP version exposes mobile.
- **Lighthouse detail deferred.** `full_data` was not pulled. In this harness the MCP `full_data` response returns into the agent context rather than to a shell pipe, so it cannot be redirected to disk as the methodology's Bash workflow assumes; a 5-15MB payload per URL would blow the context window and the ~$0.30-0.50 per-run cost target. Per-URL `lighthouse_issues` are therefore empty in the state file. Headline category scores and Core Web Vitals (from the reduced response) are accurate. Call `full_data` on-demand when specific audit IDs are needed — start with the homepage accessibility category.
- **Apex, not staging.** The client record has no literal `apex_cutover.completed_at` field, but `cut_over_at` is set to 2026-07-04T20:30:00Z (in the past), `build_status` is `pushed_main`, and GSC is verified on `sc-domain:flood-fixers.com`. The apex responds HTTP 200 with no `x-robots-tag: noindex`. The apex was audited and SEO counts toward the verdict; the staging noindex correction does not apply.
- **Schema not asserted.** The reduced `on_page_instant_pages` response does not return structured-data checks, so schema.org presence/validity was neither confirmed nor flagged this run. The url-plan schedules schema stubs (service, local-business, faq, breadcrumb-list) for these archetypes; verify separately if needed.
- **Clean bill elsewhere.** All 6 URLs returned HTTP 200 over HTTPS with self-referencing canonicals, exactly one H1, titles within 30-65 chars, no broken links, and no mixed content flagged. The San Diego service-area page carries a `frame` flag from its Google Maps embed, which is expected and low severity.
