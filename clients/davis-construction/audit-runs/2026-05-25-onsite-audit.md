# Onsite Audit - Davis Construction Contractors - 2026-05-25

**Live origin audited:** https://staging.rankai-davis-construction.pages.dev (staging Cloudflare Pages preview)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client
**Audit form factor:** desktop (DataForSEO Lighthouse MCP wrapper does not expose mobile)

> **Staging environment caveats**
> 
> - **SEO score is inconclusive.** Pages are served from staging.rankai-davis-construction.pages.dev which injects `x-robots-tag: noindex`. The Lighthouse `is-crawlable` audit fails on every page, deflating SEO to 69. SEO is excluded from per-page verdict computation. Re-audit after apex cutover. The recommended next action is to cut over the apex domain, not to fix SEO.
> - **Canonical points offsite by design.** Every page declares canonical `https://davisconstructioncontractors.com/...` while served from the Pages preview. This is the intentional pre-cutover behavior and will become self-referencing once apex is live.
> - **Desktop only.** The Lighthouse run is desktop. Mobile scores typically run 10-20 perf points lower; mobile-specific issues are not surfaced.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99 | n/a |
| Accessibility | 90 | n/a |
| Best Practices | 92 | n/a |
| SEO | 69 (inconclusive, staging noindex) | n/a |

Pages by verdict: green: 0, amber: 6, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 100 | 84 | 96 | 69 | 0.6s | 0.016 |
| `/services/` | services-hub | amber | 99 | 93 | 77 | 69 | 0.8s | 0.020 |
| `/services/home-remodeling/` | service-landing | amber | 98 | 89 | 100 | 69 | 0.8s | 0.004 |
| `/services/roofing/` | service-landing | amber | 98 | 89 | 100 | 69 | 0.8s | 0.003 |
| `/service-areas/madison-al/` | service-area | amber | 98 | 89 | 100 | 69 | 0.9s | 0.004 |
| `/contact/` | contact | amber | 99 | 94 | 77 | 69 | 0.8s | 0.028 |

Note: SEO 69 across all pages is the staging noindex artifact (see caveat above).

## Template-level issues (fix once, lift many pages)

| Issue ID | Title | Category | Affected URLs | Severity | Recommended fix |
| --- | --- | --- | ---: | --- | --- |
| `button-name` | Buttons do not have an accessible name | accessibility | 6 | high | Add accessible names to all buttons (aria-label, visible text, or aria-labelledby). Likely culprits are icon-only buttons in the header navigation, mobile menu toggle, and chat widget close button. |
| `color-contrast` | Background and foreground colors do not have a sufficient contrast ratio. | accessibility | 4 | high | Audit foreground/background contrast ratios. Likely culprit is light text on light-image hero overlays and muted secondary text on the brand background. |
| `inspector-issues` | Issues were logged in the `Issues` panel in Chrome Devtools | best_practices | 2 | high | Open Chrome DevTools Issues panel on the affected pages; common causes are deprecated APIs, third-party cookie warnings, and CORS messages from the chat widget or Stripe. |
| `third-party-cookies` | Uses third-party cookies | best_practices | 2 | high | Migrate any embedded Stripe or chat widget to use partitioned cookies (CHIPS) or first-party fallbacks; consider lazy-loading the chat widget until user interaction so it does not fire on every page load. |

## Money page alerts

- **`/`** (home) - verdict: amber. accessibility 84.
- **`/services/`** (services-hub) - verdict: amber. best practices 77.
- **`/services/home-remodeling/`** (service-landing) - verdict: amber. accessibility 89.
- **`/services/roofing/`** (service-landing) - verdict: amber. accessibility 89.
- **`/contact/`** (contact) - verdict: amber. best practices 77.

None of the money pages are red; all are amber and driven by the template-level accessibility (button-name, color-contrast) and best-practices (third-party-cookies, inspector-issues) issues called out above.

## Regressions vs prior audit

First audit for this client - no comparison data available. The next monthly run will compare against this baseline.

## Recommended next actions (priority order)

1. **(deploy)** Cut over the apex domain `davisconstructioncontractors.com` to Cloudflare Pages and re-run this audit. Until that happens the SEO category cannot be evaluated honestly - the staging noindex header makes every page fail `is-crawlable`. This is the single highest-leverage action this month.
2. **(template, accessibility, 6/6 pages)** Add accessible names to every button in the shared layout. `button-name` fails on all 6 audited pages. Start with the header mobile-menu toggle, any icon-only buttons in the chat widget, and any close buttons - add an `aria-label` or visually-hidden span. Expected lift: a11y +5 to +10 points across every page.
3. **(template, accessibility, 4/6 pages)** Fix `color-contrast` failures on the home, two service-landing pages, and the service-area page. The two pages that pass (`/services/` and `/contact/`) are the simplest layouts, so the failure is almost certainly in the hero-overlay or feature-card styling used by the other archetypes. Check the brand foreground on muted backgrounds against WCAG AA 4.5:1.
4. **(template, best-practices, money pages)** Address `inspector-issues` and `third-party-cookies` on `/services/` and `/contact/`. These two pages drop best-practices to 77 because of third-party cookie warnings from the embedded chat widget / Stripe. Lazy-load the chat widget on user intent rather than firing it on every page load, and confirm any Stripe embed uses partitioned cookies (CHIPS).
5. **(per-page, low)** Tighten the home page meta description (currently 187 chars, ideal 70-160) and the home/roofing/madison-al/contact titles (currently 68-80 chars, ideal 30-65). These are warnings, not failures, but trimming improves SERP snippet display.

## Notes / caveats

- Core Web Vitals are excellent across the board (LCP 0.8-0.9s, CLS under 0.03). Performance is not a concern for this site.
- `lighthouse_detail: captured`. Full Lighthouse responses (approx 1.1-1.3MB each) were fetched via direct DataForSEO API and parsed locally to extract failing audit IDs. They are not persisted in the monorepo; re-fetch on demand if needed.
- The TBT field in the state file is sourced from `max-potential-fid` because the desktop simulated trace does not produce a `total-blocking-time` numeric in this Lighthouse build.
- Total page weight is around 1.9-2.0MB per page, dominated by hero/brand imagery. Not flagged today because LCP is still under 1s, but worth watching when mobile auditing comes online.
