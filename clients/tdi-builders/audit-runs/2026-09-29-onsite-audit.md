# Onsite Audit - TDI Builders, Inc. - 2026-09-29

**Live origin audited:** https://staging.rankai-tdi-builders.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-28
**Form factor:** desktop (Lighthouse 13.4.0, for_mobile=false). Mobile scores would typically run 10-20 performance points lower. These are NOT mobile-first scores.

## Environment caveat - SEO is inconclusive on staging

The staging preview still returns `x-robots-tag: noindex` (re-checked today). The Lighthouse `is-crawlable` audit fails on all 6 URLs and holds SEO at 69 everywhere. That is a preview-host artifact, not a site defect.

**SEO has been excluded from every verdict in this report.** It is recorded in the state file as-is. SEO status is `inconclusive - staging noindex artifact, re-audit after apex cutover`. Verdicts use Performance, Accessibility, and Best Practices only.

## Important: the apex is already live, but the cutover is not recorded

Last month `tdiusa.com` 302-redirected to the old Scorpion site. Today both `https://tdiusa.com/` and `https://www.tdiusa.com/` return HTTP 200 and serve this build. The `_astro` asset hashes match staging and there is no noindex header. The client record has no `apex_cutover.completed_at`, so this run still audited staging, as the methodology requires.

To confirm SEO is clean off the preview host, one extra desktop Lighthouse run was done on `https://www.tdiusa.com/`. It scored **Performance 99, Accessibility 92, Best Practices 100, SEO 100**. It is recorded under `supplementary_apex_check` in the state file and is not counted in any verdict. If the cutover is real, record it on the client record so next month's audit runs on the apex.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.8 | -1.2 |
| Accessibility | 91.0 | +1.0 |
| Best Practices | 100.0 | +1.3 |
| SEO (excluded) | 69.0 | 0.0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

Month over month the site improved: Best Practices is now 100 on every page, and the services hub moved from amber to green. Performance is still excellent (98-99 on every page, TBT 0ms, CLS 0.033 or lower). LCP rose by 64-183ms on every page, to 840-963ms. That is below the 200ms regression threshold on every URL and is most likely caused by the newly added GA4 tag (see below).

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 99 | 92 | 100 | 69* | 0.96s | 0.033 | 0ms |
| `/services/` | services-hub | green | 99 | 90 | 100 | 69* | 0.91s | 0.028 | 0ms |
| `/services/home-remodeling/` | service-landing | green | 99 | 91 | 100 | 69* | 0.84s | 0.003 | 0ms |
| `/services/new-construction/` | service-landing | green | 99 | 91 | 100 | 69* | 0.93s | 0.025 | 0ms |
| `/service-areas/roseville-ca/` | service-area | green | 98 | 91 | 100 | 69* | 0.95s | 0.002 | 0ms |
| `/contact/` | contact | green | 99 | 91 | 100 | 69* | 0.94s | 0.013 | 0ms |

\* SEO excluded from verdict because of the staging noindex artifact. INP is null on all pages because Lighthouse navigation mode does not produce it.

JSON-LD was checked against the served HTML and parses on every page: Organization, WebSite, and LocalBusiness on `/`; Service, FAQPage, and BreadcrumbList on the landings; LocalBusiness, FAQPage, and BreadcrumbList on the area page. DataForSEO `has_micromarkup: false` is a false negative again. There is no mixed content, no broken links, a single H1 on every page, and every title is within 44-53 chars.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `link-name` | 6 | high | Footer still renders `<a href="mailto:">` with no address and no text (twice on `/contact/`, including the white-on-blue contact card). `clients/tdi-builders.json` now has `rob@tdiusa.com`, but `plan-input.json` still has `brand.email: ""`. |
| `color-contrast` | 6 | high | Four patterns (details below). All 6 pages have the footer `text-primary` links (`#0080C4` on white, 4.29:1 at 10.5pt). |
| `unused-javascript` | 6 | low (new) | GA4 `gtag/js?id=G-HCNBG7B9HN` was added since last month. It is 159KB, of which about 69KB is unused. Est. 20-150ms LCP. |
| `image-delivery-insight` | 6 | low | `hero-bg.webp` (219KB) is served without `srcset` on the inner pages (up to 164KB of savings on `/contact/`). `logo.png` (14KB) is displayed at 48px. |
| `render-blocking-insight` | 6 | low | `_astro/_slug_.C-PcsskP.css` (9KB). Est. 30-50ms. Not worth acting on at Performance 98-99. |
| `lcp-discovery-insight` | 5 | low | LCP hero image is not preloaded or `fetchpriority=high` on inner pages. |
| `network-dependency-tree-insight` | 6 | low | Diagnostic only, no score impact. |
| `agent-accessibility-tree` | 6 | low | Lighthouse 13 `agentic-browsing` category, outside this methodology. Recorded, not counted. |
| `is-crawlable` | 6 | environment | Staging noindex. SEO scores 100 on the live apex. |

Color-contrast nodes found this run:

| Element | Ratio | Colors | Pages |
| --- | ---: | --- | --- |
| Footer `a.text-primary` (tel, services, emergency links) | 4.29:1 | `#0080C4` on `#FFFFFF`, 10.5pt | all 6 |
| Breadcrumb `a.text-dark/50` | 3.31:1 | `#8D8D8D` on `#FFFFFF`, 9pt | 5 (not `/`) |
| `.btn-accent` small buttons | 4.29:1 | `#FFFFFF` on `#0080C4`, 10.5pt | 2 landings + area |
| `span.text-slate-400` | 2.56:1 | `#94A3B8` on `#FFFFFF`, 10.5pt | `/service-areas/roseville-ca/` |

## Money page alerts

- **`/`** (home) - verdict: amber. All three counted Lighthouse categories are 92 or higher. The only thing keeping it amber is the meta description, which is now 211 characters (down from 231, still over 160). It also carries the empty footer `mailto:` and 3 footer contrast nodes.

`/contact/` is green but still has the empty `mailto:` twice, including in the main contact card. That is a dead link on the page where conversion matters most.

## Regressions vs prior audit

No URL crossed any regression threshold. No category dropped by 5 or more points on any page. No LCP rise reached 200ms, no CLS rise reached 0.02, and no TBT rise reached 100ms. No site average dropped by 3 or more points.

**Verdict transitions:**
- `/services/` went amber to green. Best Practices rose from 96 to 100 because the `/images/services.webp` 404 is gone.

**New issues this month:**
- All 6 pages: `unused-javascript`. GA4 `gtag.js` was added to the layout, with about 69KB unused. This is the likely cause of the small LCP increase across the site.
- `/`: `forced-reflow-insight`. Diagnostic, no measurable score impact.
- `/services/`: `image-delivery-insight`, with 192KB of potential image savings across 7 images.
- `/service-areas/roseville-ca/`: `frame`. This is the Google Maps embed and is intentional. No action.

**Issues resolved since last audit:** (positive, keep doing this)
- `/` and `/services/`: `broken_resource` and `errors-in-console` are cleared. The pages no longer reference the missing `/images/services.webp`.
- `/`: `low_content_rate` is no longer flagged (1457 words vs a 1200 target). This month's word counts are measured differently from last month's, so part of this change is methodological.
- `/`: Accessibility went from 86 to 92.

## Recommended next actions (priority order)

1. **(unblocks SEO scoring)** Confirm whether the `tdiusa.com` cutover is complete. It is serving this build today, and SEO scores 100 there. If it is complete, set `apex_cutover.completed_at` on `clients/tdi-builders.json` so the next audit runs on the apex and SEO counts toward the verdict. Also fix the host inconsistency: `tdiusa.com` returns 200 instead of 301-redirecting to `www.tdiusa.com` (the canonical host), robots.txt declares `Sitemap: https://tdiusa.com/sitemap-index.xml` on the non-www host, and the client record `domain` is the non-www host. Choose one host, add the 301 redirect, and make the sitemap URL match the canonical.

2. **(money page + template, high)** Fix the empty `mailto:` link. Set `brand.email` in `clients/tdi-builders/plan-input.json` to `rob@tdiusa.com` (already on the client record) and rebuild. Separately, make the footer and contact-card templates skip the anchor when `brand.email` is empty, so this cannot recur on other clients. This clears `link-name` on all 6 pages and removes the dead link from `/contact/`.

3. **(money page, medium)** Cut the homepage meta description from 211 to 160 characters or fewer, keeping the phone and call to action inside the first 155. This is the only thing keeping `/` amber.

4. **(template, high)** Fix contrast with three token changes. Use a darker small-text brand blue (about `#0067A0`, roughly 5.3:1) for footer links and `.btn-accent` at 14px, and keep `#0080C4` for large headings and large buttons. Change the breadcrumb from `text-dark/50` to `text-dark/70` or darker. Change `text-slate-400` on the area page to `text-slate-600`. The brand blue comes from the client's branding guidelines, so confirm the darker variant with Santino before shipping.

5. **(template, low)** Load GA4 after the page is interactive. Either use Partytown or inject `gtag.js` on `requestIdleCallback` or first interaction, instead of in `<head>`. This removes the new `unused-javascript` flag and should bring LCP back toward last month's ~0.77s. In the same pass, add `srcset`/`sizes` and `fetchpriority="high"` to `hero-bg.webp` on inner pages, which clears `image-delivery-insight` and `lcp-discovery-insight`.

## Notes / caveats

- URLs came from `plan/url-plan.json` (Mode B; there is no `audit-urls.txt`), giving the same 6 as last month. The landings are the top 2 by priority: `/services/home-remodeling/` (9.0) and `/services/new-construction/` (8.1, the first of three tied at 8.1). No service area has `primary: true` and there is no Sacramento area page, so the fallback `/service-areas/roseville-ca/` was used. Set a `primary: true` flag so this selection stays fixed from month to month.
- Canonicals changed from `https://tdiusa.com/...` last month to `https://www.tdiusa.com/...` this month. They are consistent across all 6 pages and are not counted as an offsite-canonical defect on staging.
- The `mcp__dataforseo__on_page_lighthouse` and `on_page_instant_pages` tools are not in this MCP build. The raw endpoints `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` were called directly, and full Lighthouse JSON was parsed on disk. Total API cost was about $0.04, including the one supplementary apex check.
- Client `status` is still `onboarding`, not `active`. The audit proceeded on `build_status: pushed_main`, the same as last month.
- Verdicts use category scores plus on-page issue severity. The high-severity `color-contrast` and `link-name` Lighthouse failures are already reflected in the Accessibility score, so they are not counted a second time. This matches the 2026-08-28 baseline.
- `/services/` is 705 words against the plan's 800 target (low severity, and it did not affect the verdict).
- All 6 URLs returned HTTP 200 and audited cleanly. No errors or re-runs.
