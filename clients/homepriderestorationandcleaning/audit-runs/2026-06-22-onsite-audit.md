# Onsite Audit - Home Pride Restoration and Cleaning LLC - 2026-06-22

**Live origin audited:** https://homepriderestorationandcleaning.com (apex)  
**Audit form factor:** desktop (DataForSEO Lighthouse wrapper is desktop-only; mobile would typically score 10-20 perf points lower)  
**Site verdict:** amber  
**URLs audited:** 6  
**Prior audit:** first audit for this client - no comparison data

## Environment caveats

> The configured staging Pages preview returned HTTP 404. The apex production domain (homepriderestorationandcleaning.com) is live, serving HTTP 200 with no `x-robots-tag: noindex`, so the apex was audited and SEO counts normally toward the verdict. The client record does not yet carry `apex_cutover.completed_at`, but the apex is in production.

> Two DataForSEO instant-page signals were verified against Lighthouse and excluded as artifacts: `broken_resources=true` (Lighthouse loaded every page with 0 failed requests) and `has_micromarkup=false` (rendered HTML contains valid JSON-LD: LocalBusiness, Organization, WebSite, FAQPage, BreadcrumbList). Neither is a real site issue.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98 | n/a |
| Accessibility | 95 | n/a |
| Best Practices | 100 | n/a |
| SEO | 100 | n/a |

Pages by verdict: green: 0, amber: 6, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 96 | 95 | 100 | 100 | 1.1s | 0.002 |
| /services/ | services-hub | amber | 100 | 95 | 100 | 100 | 0.5s | 0.002 |
| /services/water-damage-restoration/ | service-landing | amber | 99 | 95 | 100 | 100 | 0.8s | 0.002 |
| /services/fire-damage-restoration/ | service-landing | amber | 98 | 95 | 100 | 100 | 0.8s | 0.004 |
| /service-areas/saratoga-springs-ut/ | service-area | amber | 99 | 95 | 100 | 100 | 0.8s | 0.002 |
| /contact/ | contact | amber | 98 | 95 | 100 | 100 | 0.8s | 0.06 |

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `render-blocking-insight` | 6 | medium | Defer or async the non-critical CSS/JS loaded in the layout `<head>`. ~550-600ms FCP savings per page. |
| `color-contrast` | 6 | medium | Raise foreground/background contrast on the low-contrast text/button elements to meet WCAG AA (4.5:1 for body text). |
| `title_too_long` | 6 | medium | Shorten the `<title>` template in the shared layout. Current titles run 78-82 chars; the city/state suffix repeats the brand and overflows Google's ~60-65 char display limit. Target 50-60 chars. |
| `llms-txt` | 6 | low | Optional: add an `/llms.txt` file describing the site for LLM crawlers (emerging best practice, low priority). |

## Money page alerts

- **`/`** (home) - verdict: amber. Main issue: Title length 82 chars (over 65).
- **`/services/`** (services-hub) - verdict: amber. Main issue: Title length 78 chars (over 65).
- **`/services/water-damage-restoration/`** (service-landing) - verdict: amber. Main issue: Title length 82 chars (over 65).
- **`/services/fire-damage-restoration/`** (service-landing) - verdict: amber. Main issue: Title length 81 chars (over 65).
- **`/contact/`** (contact) - verdict: amber. Main issue: Title length 82 chars (over 65).

_All money-page alerts this run are driven by the sitewide title-length template issue (no performance or broken-element problems on money pages; scores are 96-100)._

## Regressions vs prior audit

First audit for this client - no comparison data.

## Recommended next actions (priority order)

1. **(template, money pages, medium)** Shorten the `<title>` tag template in the shared layout. All 6 audited pages (including home, contact, and both service landings) have titles of 78-82 chars, over Google's ~60-65 char display limit. Drop the redundant brand/city suffix so titles land at 50-60 chars. One layout fix lifts every page.
2. **(template, medium)** Defer/async the render-blocking CSS and JS in the layout `<head>`. Lighthouse `render-blocking-insight` shows ~550-600ms FCP savings on every page. LCP is already strong (0.5-1.1s), so this is a polish item, not an emergency.
3. **(template, accessibility, medium)** Fix the `color-contrast` failures flagged on all 6 pages. Identify the low-contrast text/buttons and raise contrast to WCAG AA 4.5:1. This is the single item holding accessibility at 95 instead of 100.
4. **(money page, home, low)** Home page: trim the meta description from 201 to under 160 chars, and compress the hero/inline imagery. Home ships ~3.8MB across 12 images and `image-delivery-insight` estimates ~200ms LCP savings from better image delivery (responsive sizes / next-gen formats).
5. **(housekeeping, low)** Cut over the apex domain formally (set `apex_cutover.completed_at` in the client record) so future audits no longer have to detect-and-override the dead staging preview, and optionally add `/llms.txt`.

## Notes / caveats

- Audited the apex production site because the configured staging Pages preview (`staging.rankai-homepriderestorationandcleaning.pages.dev`) returned 404. Apex serves 200 with no noindex header, so SEO was scored normally.
- Desktop-only scoring (DataForSEO Lighthouse wrapper does not expose mobile). Mobile performance would likely be 10-20 points lower.
- `broken_resources` (instant-pages) and `has_micromarkup=false` were both verified as tooling artifacts, not real issues (see Environment caveats).
- Overall this is a healthy, fast site. The amber verdict is driven entirely by the sitewide title-length template pattern (a medium on-page issue), not by any performance, security, or broken-element problem.
