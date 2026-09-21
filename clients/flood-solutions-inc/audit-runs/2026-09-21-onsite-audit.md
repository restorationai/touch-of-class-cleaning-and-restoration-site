# Onsite Audit - Flood Solutions inc - 2026-09-21

**Live origin audited:** https://staging.rankai-flood-solutions-inc.pages.dev (staging)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** first audit for this client, no comparison data
**Form factor:** desktop only (Lighthouse 13.4.0, cpuSlowdownMultiplier 1, throughputKbps 10240). Mobile scores would typically run 10-20 performance points lower. These are NOT mobile-first numbers.

## Read this first: two environment caveats

**1. SEO score is inconclusive, not bad.** The staging Pages preview returns `x-robots-tag: noindex`
(Cloudflare injects this on every `*.pages.dev` preview). That fails the Lighthouse `is-crawlable`
audit and pins the SEO category at 69 on all 6 URLs. Per methodology Step 4 the SEO category is
recorded as-is but EXCLUDED from all verdicts. Do not "fix SEO" off this report. SEO status:
inconclusive, re-audit after apex cutover.

**2. The red verdict is NOT about scores.** Lighthouse performance (98-100), accessibility (95-100)
and best practices (96) are all strong. The site is red because every audited page ships a canonical
tag, an `og:url`, a sitemap and a JSON-LD logo pointing at **non-resolving placeholder hostnames**.
That is an indexing-blocking defect, and it must be fixed before apex cutover, not after.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.3 | n/a |
| Accessibility | 96.0 | n/a |
| Best Practices | 96.0 | n/a |
| SEO | 69.0 (inconclusive) | n/a |

Pages by verdict: green: 0, amber: 0, red: 6, error: 0

Verdict basis: performance, accessibility, best practices. SEO excluded (staging noindex artifact).

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 99 | 100 | 96 | 69* | 0.9s | 0.014 | 0ms |
| `/services/` | services-hub | red | 100 | 95 | 96 | 69* | 0.5s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | red | 100 | 95 | 96 | 69* | 0.5s | 0.024 | 0ms |
| `/services/water-cleanup/` | service-landing | red | 98 | 95 | 96 | 69* | 0.9s | 0.003 | 0ms |
| `/service-areas/sterling-heights-mi/` | service-area | red | 100 | 95 | 96 | 69* | 0.5s | 0.003 | 0ms |
| `/contact/` | contact | red | 99 | 96 | 96 | 69* | 0.9s | 0.004 | 56ms |

\* SEO inconclusive, staging noindex artifact.

Core Web Vitals are comfortably inside Google's "good" thresholds on every page (LCP under 2.5s,
CLS under 0.1, TBT effectively zero). There is no performance work worth doing here right now.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `rankai:canonical_host_unresolvable` | 6 | high | Rebuild and redeploy the Pages project so `brand.canonicalUrl` (already correct in source) reaches the deployed HTML |
| `rankai:brand_logo_unresolvable` | 6 | high | Provision the `images.floodsolutionsinc.com` DNS record plus R2 bucket, or switch `logoUrl` to a local `/images/logo.png` asset |
| `rankai:sitemap_host_unresolvable` | 6 (site-level) | high | Same redeploy; then resubmit the sitemap once apex is live |
| `errors-in-console` | 6 | high | Resolve the dead logo host and the 404 image assets below, which are the only console errors |
| `rankai:broken_image_assets` | 6 | medium | Ensure `public/images/*.webp` are copied into the deploy artifact (they exist in the monorepo but 404 on the preview) |
| `rankai:og_url_host_unresolvable` | 6 | medium | Same redeploy as the canonical fix |
| `color-contrast` | 5 | medium | Darken the breadcrumb link colour in the breadcrumb component (see item 4 below) |
| `render-blocking-insight` | 6 | low | Not worth acting on: 8.8KB of CSS, about 50-62ms |
| `network-dependency-tree-insight` | 6 | low | No action: Lighthouse reports no preconnect candidates and 0ms LCP saving |
| `rankai:word_count_below_target` | 2 | low | Homepage 1148 vs 1200 target, services hub 707 vs 800 target |

## Money page alerts

All five audited money pages are red for the same root cause, not for page-specific reasons.

- **`/`** (home) - red. Canonical, og:url and JSON-LD logo/image all on non-resolving hosts. Hero background and team image 404.
- **`/services/`** (services-hub) - red. Same host defects. Hero and services card images 404.
- **`/services/water-damage-restoration/`** (service-landing) - red. Same host defects. This is the client's highest-priority page in the url-plan (priority 9.0).
- **`/services/water-cleanup/`** (service-landing) - red. Same host defects.
- **`/contact/`** (contact) - red. Same host defects. Performance is fine (99, LCP 0.9s, TBT 56ms from the form JS).

## Regressions vs prior audit

First audit for this client. No comparison data. This file becomes next month's baseline.

## Recommended next actions (priority order)

1. **(template, blocks indexing, do first)** Rebuild and redeploy the `rankai-flood-solutions-inc`
   Pages project from current `main`. The monorepo source at
   `sites/flood-solutions-inc/src/lib/brand.ts:10-11` already holds the healed values
   (`domain: floodsolutionsinc.com`, `canonicalUrl: https://floodsolutionsinc.com`) from commit
   `a33216866`, but the live preview still serves `https://flood-solutions-inc.invalid/` in the
   canonical tag, `og:url`, and `sitemap-index.xml`. The deployed artifact is behind the source.
   `build.last_pushed_main_at` is 2026-09-21T16:57Z and this audit ran 17:03-17:08Z, so confirm the
   Pages build actually completed and did not fail, rather than assuming it is still in flight.

2. **(template, high, does NOT fix itself on redeploy)** Fix the brand logo host. Redeploying swaps
   `images.flood-solutions-inc.invalid` for `images.floodsolutionsinc.com`, but that hostname has
   **no DNS record either** (verified: no A/AAAA, connection fails), so the logo stays broken and
   the `logo` and `image` fields in the LocalBusiness and Organization JSON-LD keep pointing at a
   dead URL, which costs rich-result eligibility. Either provision the `images.floodsolutionsinc.com`
   record and R2 bucket, or follow the `sites/reign-restoration/src/lib/brand.ts:34` precedent and
   point `logoUrl` at a local `/images/logo.png`. No local logo asset exists in
   `sites/flood-solutions-inc/public/` today, so that route needs the file added first.

3. **(template, medium)** Get the three hero and section images into the deploy artifact.
   `/images/hero-bg.webp` 404s on all 6 pages, `/images/services.webp` on 2, `/images/team.webp` on
   the homepage. All three exist in `sites/flood-solutions-inc/public/images/` (97KB, 215KB, 168KB),
   so this is a deploy-sync gap, not missing artwork. Until fixed, every hero renders with no
   background image.

4. **(template, accessibility, medium)** Darken the breadcrumb link colour. The breadcrumb anchors
   (`nav.container-wide > ol.flex > li.flex > a.text-dark/50`) render `#888c93` on `#ffffff` at 12px,
   a contrast ratio of 3.37:1 against the 4.5:1 WCAG AA requirement. This is the only accessibility
   failure on the site and it appears on all 5 pages that have breadcrumbs (the homepage has none).
   Changing `text-dark/50` to roughly `text-dark/70` or darker clears it and lifts accessibility from
   95 to 100 site-wide.

5. **(per-page, low)** Bring the two thin pages up to their url-plan targets: homepage 1148 words
   against a 1200 target, `/services/` 707 against 800. Both are close enough that this is polish,
   not a priority, and it is content work rather than technical work.

## Notes / caveats

- **Apex is not ours yet.** `floodsolutionsinc.com` still serves the client's legacy WordPress site
  (`x-powered-by: WP Engine`, 301 to `www`). The client record has no `apex_cutover.completed_at`, so
  the audit correctly targeted the staging preview. Auditing the apex today would have measured the
  old site, not the Rank AI build.
- **Client status.** `clients/flood-solutions-inc.json` has `status: "onboarding"`, not `"active"`,
  which the methodology pre-flight expects. The audit proceeded because `build_status: "pushed_main"`
  means the build is live and auditable. The status field was left untouched.
- **Tooling substitution.** The dedicated `on_page_lighthouse` and `on_page_instant_pages` MCP
  wrappers were not available in this environment. The DataForSEO REST endpoints
  (`/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages`) were called directly with
  `for_mobile: false` to preserve desktop comparability with future runs. Run cost was about $0.041
  for 12 calls, well inside the $0.30-0.50 target.
- **Issue ID namespacing.** Findings that came from direct inspection of the served HTML rather than
  from a vendor audit carry a `rankai:` prefix so they can never be mistaken for real Lighthouse or
  DataForSEO check IDs. Every issue in the state file records its `source`.
- **`is-crawlable` omitted from per-URL issue lists.** It fails on all 6 URLs, but only because of
  the staging noindex header, so listing it per page would send the operator chasing a non-issue. It
  is documented once under `environment_caveats` in the state file.
- **Clean bill of health elsewhere.** No broken internal or external links, no duplicate titles or
  descriptions, no mixed content, exactly one H1 per page, 100 percent image alt coverage, favicon
  present, and all titles (44-56 chars) and meta descriptions (95-153 chars) inside target ranges.
  Security headers on the preview are solid: HSTS, `nosniff`, `Referrer-Policy`,
  `Permissions-Policy`, and a `frame-ancestors` CSP.
- **Service-area page selection.** `url-plan.json` has no service-area entry flagged `primary: true`,
  and the primary area from `plan-input.json` (`macomb-mi`) has no page in the plan at all. Per the
  documented fallback, the first service-area page in the plan was used
  (`/service-areas/sterling-heights-mi/`); all 8 share priority 4.8. Worth checking separately
  whether the missing Macomb page is intentional, since Macomb is the primary marketing city.
- **Re-audit trigger.** Once items 1 through 3 are deployed, re-run this audit. If it runs before
  apex cutover the SEO category will still read about 69 and stay inconclusive.
