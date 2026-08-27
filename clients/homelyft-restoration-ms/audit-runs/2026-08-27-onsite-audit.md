# Onsite Audit, HomeLyft Restoration MS, 2026-08-27

**Live origin audited:** https://staging.rankai-homelyft-restoration-ms.pages.dev (staging)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** first audit for this client, no comparison data
**Form factor:** desktop only (see caveats)

## Read this first: two separate things, do not conflate them

**1. The staging SEO score is a false alarm.** All 6 audited URLs return `x-robots-tag: noindex`. That is the Cloudflare Pages preview default, not a site defect. Lighthouse SEO is deflated to **69** on every page, and `is-crawlable` is the **only** failing SEO audit on all 6 pages. Nothing else in the SEO category fails anywhere. SEO is therefore **excluded from every verdict in this run** and recorded as `inconclusive, staging noindex artifact, re-audit after apex cutover`. Do not open a ticket to "fix SEO" off this report.

**2. The red verdict is real and it is not the noindex header.** Every page on this site ships a canonical tag pointing at a host that does not exist:

```
<link rel="canonical" href="https://None/">
<meta property="og:url" content="https://None/">
```

The literal string `None` is a Python `None` that got interpolated into the site base URL at build time, because `clients/homelyft-restoration-ms.json` has `"domain": null`. This is a build-config defect, it is present on all 6 pages, and it will **not** fix itself at apex cutover. Verdicts below are computed from Performance, Accessibility, and Best Practices only, plus on-page severity.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.5 | n/a |
| Accessibility | 95.3 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 69.0 (excluded) | n/a |

Pages by verdict: green: 0, amber: 0, red: 6, error: 0

Every page is red for exactly one reason: the broken canonical. Strip that single template issue out and this site is green across the board. The Lighthouse numbers are among the best in the portfolio.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 98 | 100 | 100 | 69* | 0.9s | 0.002 |
| `/services/` | services-hub | red | 99 | 91 | 100 | 69* | 0.8s | 0.002 |
| `/services/water-damage-restoration/` | service-landing | red | 100 | 95 | 100 | 69* | 0.8s | 0.024 |
| `/services/fire-damage-restoration/` | service-landing | red | 100 | 95 | 100 | 69* | 0.8s | 0.030 |
| `/service-areas/eastabuchie-ms/` | service-area | red | 100 | 95 | 100 | 69* | 0.8s | 0.003 |
| `/contact/` | contact | red | 100 | 96 | 100 | 69* | 0.6s | 0.007 |

\* SEO excluded from verdict, staging noindex artifact.

Total Blocking Time is 0ms on five of six pages (102ms on `/`, still inside the 200ms "good" threshold). INP was not reported, it requires field data and is unavailable in a lab run. All Core Web Vitals are comfortably inside Google's "good" thresholds: LCP under 1.0s everywhere, CLS under 0.04 everywhere.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `rankai:canonical_host_unresolvable` | 6 | high | Set `"domain": "homelyft.net"` in `clients/homelyft-restoration-ms.json`, rebuild, redeploy. See detail below. |
| `image-delivery-insight` | 6 | high | `/images/hero-bg.webp` is a single 193KB file served at full size on every inner page with no `srcset`. `/images/logo.png` is a 500x500 PNG served to a 64x64 and an 80x80 slot. |
| `color-contrast` | 5 | medium | Breadcrumb links use `.text-dark/50`, which resolves to `#888c93` on white at 3.37:1 at 12px. WCAG AA needs 4.5:1. Change the breadcrumb utility to `text-dark/70` or darker. |
| `link-in-text-block` | 1 | medium | On `/services/`, the inline `tel:+12282845200` link inside `p` is `#951818` against `#374151` body text, only 1.18:1 apart, and carries no underline. Add `underline` to inline prose links. |
| `network-dependency-tree-insight` | 6 | low | Longest critical chain is 119-222ms (`page.CyD_eNI3.js` behind the HTML). No preconnected origins. Acceptable at this size. |
| `render-blocking-insight` | 6 | low | `_astro/_slug_.*.css` (8.8KB) blocks render. Costs 54-57ms on `/contact/` and `/service-areas/`, 0ms elsewhere. Acceptable at this size. |
| `lcp-discovery-insight` | 5 | low | LCP element `/images/hero-bg.webp` is eager-loaded and discoverable but lacks `fetchpriority="high"` on the inner-page hero. The homepage hero already has it. |
| `high_loading_time` | 3 | low | DataForSEO's own loading-time threshold on `/`, `/services/water-damage-restoration/`, `/contact/`. Contradicted by Lighthouse LCP under 1s on all three. Treat as noise unless it persists at apex. |

`is-crawlable` also appears on all 6 pages and is deliberately excluded from this table. It is the staging noindex artifact described above, not a template defect.

### Detail: the `https://None/` canonical

Verified by direct fetch, not by a vendor check. DataForSEO's `canonical` check returns "has canonical: true" because a canonical tag is syntactically present, and Lighthouse's `canonical` audit passes for the same reason. Neither tool resolves the host. `getent hosts None` returns NXDOMAIN and `curl https://None/` fails with exit 6, host unresolvable.

Blast radius, counted from the served HTML: 6 to 10 occurrences of `https://None` per page.

- `<link rel="canonical">` on every page, including `/404/`
- `<meta property="og:url">` on every page
- JSON-LD `@id` and `url` on the `Organization`, `WebSite`, and `LocalBusiness` nodes, plus `publisher.@id`
- `/sitemap-index.xml` points to `https://none/sitemap-0.xml` (lowercase variant, same root cause, from the Astro `site` config)

The intended domain is already known to the build: `/robots.txt` correctly emits `Sitemap: https://homelyft.net/sitemap-index.xml`, and the client contact is `terry@homelyft.net`. Only the `domain` field in the client record is null.

If this ships to apex as-is, every page on the site self-canonicalizes to a nonexistent host and the sitemap points off-domain. That is an indexation-level risk for the whole property, which is why it outranks everything else in this report.

## Money page alerts

All five money pages are red, all for the same single cause. None of them has a performance, accessibility, or best-practices problem.

- **`/`** (home) red. Canonical resolves to `https://None/`. Otherwise Perf 98, A11y 100, BP 100, LCP 0.9s. Also carries a 174-character meta description, target is 70-160.
- **`/services/`** (services-hub) red. Canonical. Otherwise Perf 99, A11y 91. Lowest accessibility score on the site, driven by the breadcrumb contrast plus the unstyled inline `tel:` link. Word count 767 against a url-plan target of 800.
- **`/services/water-damage-restoration/`** (service-landing) red. Canonical only. Perf 100, A11y 95.
- **`/services/fire-damage-restoration/`** (service-landing) red. Canonical only. Perf 100, A11y 95.
- **`/contact/`** (contact) red. Canonical only. Perf 100, A11y 96, LCP 0.6s, the fastest page on the site. Its hero still ships the full 193KB `hero-bg.webp` for a 1350x207 slot, 145KB of which is waste.

## Regressions vs prior audit

First audit for this client, no comparison data. This run becomes the baseline for next month.

## Recommended next actions (priority order)

1. **(template, blocking)** Set `"domain": "homelyft.net"` in `clients/homelyft-restoration-ms.json`, then rebuild and redeploy `restorationai/homelyft-restoration-ms-site`. This clears the canonical, `og:url`, JSON-LD `@id`/`url`, and sitemap-index `loc` in one change, across all 912 built pages. Confirm afterward that `curl -s https://.../ | grep canonical` returns the real domain and that `/sitemap-index.xml` no longer contains `https://none`. Do this before apex cutover, not after.
2. **(template, high impact)** Add `srcset`/`sizes` to the inner-page hero `img`, which currently hardcodes `src="/images/hero-bg.webp"` with no responsive set. The homepage hero already does this correctly, so copy that pattern into the section-hero component. Saves 102KB on `/services/`, 145KB on `/contact/`, 97KB on service-area pages.
3. **(template, high impact)** Re-export `/images/logo.png`. It is a 500x500 PNG rendered into a 64x64 header slot and an 80x80 footer slot, wasting roughly 22KB on every page in the site. Ship a 160x160 WebP, or an SVG. While there, fix the `width`/`height` attributes: the footer logo declares `width="48" height="48"` but renders at 80x80.
4. **(template, accessibility)** Change the breadcrumb link utility from `text-dark/50` to `text-dark/70`. Current computed color `#888c93` on white is 3.37:1 against a 4.5:1 requirement, and it is the sole accessibility failure on four of the six pages. Separately, add `underline` to inline prose links so the `tel:` link on `/services/` stops relying on color alone.
5. **(money page, per-page)** Trim the homepage meta description from 174 to under 160 characters so it stops truncating in the SERP, and add `fetchpriority="high"` to the inner-page hero image to close `lcp-discovery-insight` on the five pages that report it.

## Notes / caveats

- **Staging, not apex.** Client record has `domain: null` and no `apex_cutover`, so the audit ran against the Cloudflare Pages preview. Scores on Pages-preview versus apex plus CDN can differ. Re-audit after cutover.
- **SEO is deferred, not resolved.** See the block at the top. Expected apex SEO score once the noindex header is gone and the canonical is fixed is 100.
- **Desktop only.** Lighthouse 13.4.0 ran `formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`. Mobile scores would typically run 10-20 performance points lower. Do not report these numbers as mobile-first.
- **Tooling deviation.** The dedicated `on_page_lighthouse` and `on_page_instant_pages` MCP tools are not present in this MCP build. Both datasets were collected from the same DataForSEO endpoints (`/v3/on_page/lighthouse/live/json`, `/v3/on_page/instant_pages`) over authenticated HTTP, with responses written to disk and parsed out of band. Desktop was kept deliberately rather than switching to `for_mobile: true`, so this run stays comparable with the other audits in this repo. Switching the portfolio to mobile is a methodology decision, not one to make silently mid-run.
- **Pre-flight deviation.** Client `status` is `onboarding`, not `active`. `build_status` is `pushed_main` and all 6 URLs serve HTTP 200, so the audit proceeded. This matches how non-active clients have been audited in this repo already.
- **Issue-ID honesty.** Two findings are prefixed `rankai:` because no real vendor check ID covers them: `rankai:canonical_host_unresolvable` and `rankai:meta_description_too_long`. Both were verified directly rather than read off a vendor flag. The prefix exists so nobody mistakes them for Lighthouse or DataForSEO check IDs.
- **Service-area selection.** `url-plan.json` has no `primary: true` service area, and there is no `/service-areas/gulfport-ms/` page despite Gulfport being the business city (that path 301-redirects). Per the selection rule the audit fell back to the first area slug, `/service-areas/eastabuchie-ms/`. Whether the home city warrants its own service-area page is a content-plan question for System 4, not a technical finding.
- **Clean bills of health.** No broken internal or external links, no broken resources, no mixed content, no duplicate titles or descriptions, exactly one `h1` per page, all titles within 30-65 characters, full image alt coverage, and valid JSON-LD present on every page (`Organization`, `WebSite`, `LocalBusiness`). DataForSEO's `has_micromarkup` reads false because it does not detect JSON-LD, only microdata and RDFa. The schema is there, verified by hand.
- **Run cost.** 0.0606 USD total (Lighthouse 0.030, instant_pages 0.0306) across 6 URLs, inside the 0.30 to 0.50 target.
