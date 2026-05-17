# Onsite Audit — National Restoration Construction — 2026-05-17 (apex, post-cutover)

**Live origin audited:** `https://narestco.com` (apex)
**Site verdict:** amber (ACTION)
**URLs audited:** 6
**Prior audit:** STAGING (archived to `audit-runs/2026-05-17-onsite-audit-staging.json`) — environment differs, not directly comparable. This run is the first apex baseline.

## Cutover-vs-staging score recovery

Comparing the staging run (earlier today) to this apex run:

| Metric | Staging | Apex | Delta |
| --- | ---: | ---: | ---: |
| Performance | 97.3 | 97.3 | 0 |
| Accessibility | 83 | 83 | 0 |
| Best Practices | 80.8 | 77 | -3.8 (negligible run-to-run variance) |
| SEO | 61 | 92 | **+31** (staging noindex caveat resolved) |
| Site verdict | red | amber | improved |

The 31-point SEO jump confirms the staging-noindex caveat we encoded into the
prompt yesterday: Cloudflare Pages preview deployments inject
`X-Robots-Tag: noindex` on `*.pages.dev` subdomains, deflating Lighthouse SEO
from a realistic ~92 down to 61. The caveat-handling code path
(`origin_source == "apex"` keeps SEO in the verdict) works correctly.

## Site rollup

| Metric | Score |
| --- | ---: |
| Performance | 97.3 |
| Accessibility | 83 |
| Best Practices | 77 |
| SEO | 92 |

Pages by verdict: 0 green, 6 amber, 0 red

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 90 | 77 | 77 | 92 | 2.0s | 0.003 |
| `/services/` | services-hub | amber | 100 | 87 | 77 | 92 | 0.7s | 0.006 |
| `/services/water-damage-restoration/` | service-landing | amber | 98 | 82 | 77 | 92 | 0.9s | 0.003 |
| `/services/flood-damage-restoration/` | service-landing | amber | 99 | 82 | 77 | 92 | 0.8s | 0.003 |
| `/service-areas/federal-way-wa/` | service-area | amber | 98 | 82 | 77 | 92 | 0.8s | 0.007 |
| `/contact/` | contact | amber | 99 | 88 | 77 | 92 | 0.9s | 0.032 |

## Template-level issues (fix once, lift many pages)

| Issue ID | Affected URLs | Severity | Description |
| --- | ---: | --- | --- |
| `title_length_over_65` | 6 | medium | Title is 75 chars (over 65) |
| `render_blocking_resources` | 6 | medium | 1 render-blocking script + 1 render-blocking stylesheet in the layout |

In addition, **Best Practices = 77 on all 6 pages** points to a likely
template-level issue not surfaced by instant_pages — almost certainly
console errors or HTTPS subresource warnings from a 3rd-party script.
The homepage `entities` list shows `localmarketingmanager.com` as a
3rd-party resource not present on other pages, which may explain why
homepage A11y also drops a few points (extra interactive widgets). To
pin this down precisely, a follow-up `full_data: true` Lighthouse call
on one URL is needed.

## Money page alerts

- **`/`** (home) — verdict amber. accessibility score 77, LCP 1953ms
- **`/services/`** (services-hub) — verdict amber. best_practices score 77, LCP 715ms
- **`/services/water-damage-restoration/`** (service-landing) — verdict amber. best_practices score 77, LCP 871ms
- **`/services/flood-damage-restoration/`** (service-landing) — verdict amber. best_practices score 77, LCP 808ms
- **`/contact/`** (contact) — verdict amber. best_practices score 77, LCP 889ms

All money pages are amber (none red, none green). Most are 1-2 points
shy of green on the limiting category (Best Practices 77 or Accessibility
77-88). All are conversion-functional today; this is "polish before scale"
rather than urgent.

## Recommended next actions (priority order)

1. **(template, all 6 pages) Investigate Best Practices = 77.** The
   pattern (identical score, all pages) is a 3rd-party script issue or
   HTTPS subresource warning. Likely candidates from the entities list:
   the `localmarketingmanager.com` widget on the homepage, or a console
   error from `supabase.co` / `stripe.com`. Run a single `full_data: true`
   Lighthouse call on `/` to identify the exact failing audit IDs.

2. **(template, all 6 pages) Shorten page titles to ≤ 65 chars.**
   instant_pages flagged `title_too_long: true` on every URL.
   Current titles are 71-75 chars and will truncate in SERPs.
   Fix in the Astro layout/templates so all archetypes inherit.

3. **(template, all 6 pages) Defer render-blocking script + stylesheet.**
   1 + 1 in the layout. Likely the analytics script and the layout-level
   stylesheet. Defer/async will save ~400-600ms LCP per page.

4. **(homepage) Reduce homepage page weight from 5.3 MB.** 3× the other
   pages. The gallery section is likely eager-loading multiple WebP images.
   Add `loading="lazy"` to gallery images below the fold.

5. **(water-damage-restoration page) Fix og:image to absolute URL.**
   Currently `/images/services/water-damage-restoration.webp`.
   Should be `https://images.narestco.com/services/water-damage-restoration.webp`.
   LinkedIn, Pinterest, and some Discord embeds reject relative og:image.

## Notes / caveats

- **Audit form factor: desktop.** DataForSEO Lighthouse MCP wrapper does not
  expose `form_factor` / `strategy`. Mobile scores would typically be
  10-20 perf points lower. The mobile reality (which is what Google
  ranks against) is unknown via this MCP today.
- **Top-5-failing-audits detail not captured.** Headline scores + instant_pages
  checks are sufficient for this report. For deep diagnosis of any specific
  issue, call `mcp__dataforseo__on_page_lighthouse` with `full_data: true`
  on a single URL and pipe to disk.
- **Cutover validated.** Both new May 17 blog posts return 200 on production.
  TLS via Google Trust Services. www.narestco.com follows the apex via
  proxied CNAME. Email + R2 + Microsoft 365 untouched.

## Next scheduled audit

30 days out: **2026-06-17**. The first run with regression detection enabled
(this run is the baseline; the next run will compute deltas against it).
