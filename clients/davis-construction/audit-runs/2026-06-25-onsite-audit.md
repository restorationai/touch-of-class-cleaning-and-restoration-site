# Onsite Audit - Davis Construction Contractors - 2026-06-25

**Live origin audited:** https://davisconstructioncontractors.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-05-25 (ran on staging Pages preview, before apex cutover)
**Audit form factor:** desktop only (see caveats)

> Note on tooling: the DataForSEO MCP wrapper did not expose tools this run. The audit was executed against the same DataForSEO OnPage Lighthouse live (v13.4.0) and Instant Pages REST endpoints using the environment credentials. Same data source as the MCP wrapper.

> Note on comparison: the prior audit ran on the staging `*.pages.dev` preview with SEO excluded (noindex artifact). This run is the live apex with SEO counted. Regression is matched by URL path across the staging-to-apex cutover, so the large SEO gain and some best-practices movement reflect the environment change, not page edits. Details called out below.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 95 | -4 |
| Accessibility | 89 | -1 |
| Best Practices | 80 | -12 |
| SEO | 100 | +31 |

Pages by verdict: green: 0, amber: 6, red: 0, error: 0

The SEO +31 (69 to 100) is the staging noindex artifact resolving now that the site is on apex; it is not a real content change. The Best Practices -12 (92 to 80) is a genuine template regression, covered below.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 77 | 90 | 77 | 100 | 4.6s | 0.017 |
| /services/ | services-hub | amber | 98 | 89 | 96 | 100 | 0.9s | 0.001 |
| /services/home-remodeling/ | service-landing | amber | 98 | 89 | 77 | 100 | 0.9s | 0.002 |
| /services/roofing/ | service-landing | amber | 100 | 89 | 77 | 100 | 0.5s | 0.002 |
| /service-areas/madison-al/ | service-area | amber | 99 | 89 | 77 | 100 | 0.8s | 0.002 |
| /contact/ | contact | amber | 99 | 89 | 77 | 100 | 0.8s | 0.026 |

All Core Web Vitals are lab values from a desktop Lighthouse run. TBT was 0ms and INP was not measured (lab) on every page.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `button-name` | 6 | high | Add `aria-label` to the icon-only buttons in the shared header/footer (menu, social, call/CTA icons). Keeps Accessibility under 90 sitewide. |
| `color-contrast` | 6 | high | Adjust the low-contrast text/background token pairs in the layout to meet 4.5:1. Primary cause of the 89 Accessibility ceiling. |
| `inspector-issues` | 6 | high | Driven by the third-party embeds below (Stripe and the app.restorationai.io widget) logging cookie/console issues in DevTools. |
| `third-party-cookies` | 5 | high | Stripe (`m.stripe.com`) and the `app.restorationai.io` widget set third-party cookies on nearly every page. Defer/sandbox them (see recommendations). |
| `network-dependency-tree-insight` | 4 | high | Lighthouse 13.4.0 insight audit (critical request chain). Tied to render-blocking CSS/JS in the layout; mostly informational at current Performance scores. |
| `title_too_long` | 4 | medium | Trim `<title>` to 65 chars or fewer on `/`, `/services/roofing/` (80), `/service-areas/madison-al/`, `/contact/` (all 68 except roofing). |

## Money page alerts

- **`/`** (home) - verdict: amber. Performance 77, LCP 4.6s; Best Practices 77. The homepage is the only page with a slow LCP (every other page is under 0.9s), so this looks like a cold-cache CDN/R2 miss on the hero image during the run. Re-audit to confirm before treating it as a standing regression; if it persists, preload the hero image.
- **`/services/`** (services-hub) - verdict: amber. Accessibility 89 (button-name, color-contrast). Best Practices is healthy here at 96. Word count 749 is just under the 800 target.
- **`/services/home-remodeling/`** (service-landing) - verdict: amber. Best Practices 77 (third-party cookies + inspector issues), Accessibility 89.
- **`/services/roofing/`** (service-landing) - verdict: amber. Best Practices 77; `server-response-time` flagged the root document at 640ms (savings ~543ms). Title is 80 chars.
- **`/contact/`** (contact) - verdict: amber. Best Practices 77 (third-party cookies + inspector issues), Accessibility 89. CLS 0.026 is the highest on the site but still well within the 0.1 good threshold.

## Regressions vs prior audit

**Verdict transitions:** none. Every page was amber last month and is amber this month.

**Score movements:**
- Best Practices -12 (92 to 80): real template regression. `third-party-cookies` now appears on 5 of 6 pages (was 2 on staging) and `inspector-issues` on all 6 (was 2). The Stripe and app.restorationai.io widget embeds are now loading across nearly the whole site.
- Performance -4 (99 to 95): driven almost entirely by the homepage LCP outlier (4.6s). The other five pages are 98-100. Likely a cold-cache artifact, not a code regression.
- SEO +31 (69 to 100): the staging noindex artifact resolving on apex. Not a real change.
- Accessibility -1 (90 to 89): roughly flat. The homepage actually improved (84 to 90) while services-hub and contact dipped a few points.

**New issues this month:**
- Genuine: `third-party-cookies` and `inspector-issues` spread to `/`, `/services/home-remodeling/`, `/services/roofing/`, `/service-areas/madison-al/`, `/contact/`. `color-contrast` spread to `/services/` and `/contact/` (now all 6 pages). `server-response-time` on `/services/roofing/` (640ms root document). `content_below_target_word_count` on `/services/` (749 vs 800).
- Tooling vocabulary, not new defects: `network-dependency-tree-insight` and `render-blocking-insight` are Lighthouse 13.4.0 "insight" audits that did not exist under the prior run's Lighthouse version. They surface render-blocking/critical-chain that was already present; treat as informational at the current Performance scores. The homepage `largest-contentful-paint` flag ties to the LCP outlier above.

**Issues resolved since last audit:** (positive - keep doing this)
- `/`: `errors-in-console` is no longer flagged (was high-severity last month).
- `/services/`: `third-party-cookies` is no longer flagged on the services hub.

## Recommended next actions (priority order)

1. **(money page, home)** Re-audit `/` to rule out a cold-cache CDN/R2 miss on the hero image - LCP came back 4.6s while every other page is under 0.9s, and Performance fell from 100 to 77 on this page alone. If the slow LCP persists on a warm re-run, preload the hero with `<link rel="preload" as="image" fetchpriority="high">` in the home layout.
2. **(template, best practices regression)** Defer and sandbox the third-party embeds that dropped Best Practices from 92 to 80. Stripe (`m.stripe.com`) and the `app.restorationai.io` widget set third-party cookies and log inspector/console issues on 5-6 pages. Load the widget on user interaction (or behind a consent gate) and only load Stripe on pages that actually take payment.
3. **(template, accessibility high)** Fix `color-contrast` across all 6 pages - adjust the text/background color tokens in the shared layout to meet the 4.5:1 ratio. This is the main blocker keeping Accessibility at 89.
4. **(template, accessibility high)** Add accessible names (`aria-label`) to the icon-only buttons in the shared header/footer (`button-name`) - affects all 6 pages and pairs with item 3 to push Accessibility over 90.
5. **(per-page)** Trim over-length `<title>` tags to 65 chars or fewer on `/services/roofing/` (80 chars), `/`, `/service-areas/madison-al/`, and `/contact/` (68 chars each); and add roughly 50 words to `/services/` (749 vs the 800-word target).

## Notes / caveats

- **Desktop-only scoring.** DataForSEO Lighthouse runs desktop only (cpuSlowdownMultiplier=1, throughputKbps=10240). Mobile Performance typically runs 10-20 points lower; mobile-specific issues are not surfaced here. Recorded as `audit_form_factor: desktop`.
- **MCP wrapper unavailable.** The `mcp__dataforseo` MCP server exposed no tools this run. The audit used the identical DataForSEO OnPage Lighthouse live and Instant Pages REST endpoints with the environment credentials, so the data source matches what the MCP would return.
- **Schema is present despite `has_micromarkup=false`.** Instant Pages reported `has_micromarkup=false` on all pages, but JSON-LD was verified directly in the HTML of all 6 pages (LocalBusiness, Organization, WebSite, Service, FAQPage, BreadcrumbList). DataForSEO's microdata check does not count JSON-LD, so missing-schema was deliberately not flagged. No schema validation errors were reported.
- **Comparison spans the staging-to-apex cutover.** The prior audit (2026-05-25) ran on the staging preview with SEO excluded. SEO is now counted on apex. The SEO jump and part of the Best Practices movement reflect that environment change; the genuine regression is the third-party embed spread, not the cutover.
- **Homepage LCP needs a confirming re-run** before it is treated as a standing performance regression.
