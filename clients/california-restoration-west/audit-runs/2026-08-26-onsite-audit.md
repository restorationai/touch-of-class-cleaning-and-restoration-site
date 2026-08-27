# Onsite Audit - California Restoration West - 2026-08-26

**Live origin audited:** https://staging.rankai-california-restoration-west.pages.dev (staging)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** first audit for this client, no comparison data
**Form factor:** desktop only (Lighthouse 13.4.0, `for_mobile=false`)

---

## Read this first: two caveats that change how you read the numbers

**1. The SEO score of 69 is a staging artifact, not a site problem.**
Cloudflare Pages injects `x-robots-tag: noindex` on every `*.pages.dev` preview deployment. That fails the Lighthouse `is-crawlable` audit and drags the SEO category to 69 on all six URLs. Production apex will not have this header. SEO is recorded in the state file as measured but is **excluded from every verdict in this report**. SEO status is inconclusive until apex cutover. Do not open a ticket to "fix SEO."

**2. The red verdict is real and it is not about scores.**
Every Lighthouse category that counts is healthy: performance 92 to 100, accessibility 95 to 100, best practices 96 across the board. On scores alone all six pages would be green. They are red because all six pages request image files that return 404, including the hero image that is the intended LCP element on every template. Details in the next section.

---

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 94.7 | n/a |
| Accessibility | 96.0 | n/a |
| Best Practices | 96.0 | n/a |
| SEO | 69.0 (inconclusive) | n/a |

Pages by verdict: green 0, amber 0, red 6, error 0

Verdict basis: performance, accessibility, best practices. SEO excluded per caveat 1.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 92 | 100 | 96 | 69* | 1.82s | 0.003 | 0ms |
| `/services/` | services-hub | red | 100 | 95 | 96 | 69* | 0.50s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | red | 92 | 95 | 96 | 69* | 1.88s | 0.030 | 0ms |
| `/services/mold-remediation/` | service-landing | red | 100 | 95 | 96 | 69* | 0.81s | 0.003 | 0ms |
| `/service-areas/oxnard-ca/` | service-area | red | 92 | 95 | 96 | 69* | 1.84s | 0.003 | 0ms |
| `/contact/` | contact | red | 92 | 96 | 96 | 69* | 1.86s | 0.041 | 0ms |

\* SEO score suppressed by the staging noindex header. Not counted toward any verdict.

INP is null on every page. Lighthouse lab runs do not produce INP without user interaction; this is expected, not a gap in the data.

## Template-level issues (fix once, lift many pages)

| Issue | Source | Affected URLs | Severity | Recommended fix |
| --- | --- | ---: | --- | --- |
| `broken_resources` | dataforseo_onpage | 6 | high | Publish the missing image assets. See action 1. |
| `errors-in-console` | lighthouse | 6 | high | Same root cause: three 404 image fetches log console errors. |
| `image-delivery-insight` | lighthouse | 6 | high | Replace the 1.73 MB `logo.png`. See action 2. |
| `color-contrast` | lighthouse | 5 | high | Darken the breadcrumb link color. See action 3. |
| `largest-contentful-paint` | lighthouse | 4 | medium | Resolves once the hero image exists and the logo shrinks. |
| `high_loading_time` | dataforseo_onpage | 2 | medium | `/` and `/service-areas/oxnard-ca/`. Driven by the logo payload and, on Oxnard, the Google Maps embed. |
| `network-dependency-tree-insight` | lighthouse | 6 | low | Longest chain is 123 to 146ms. No preconnect for `fonts.gstatic.com`. Low value on desktop. |
| `render-blocking-insight` | lighthouse | 6 | low | `/_astro/_slug_.XNCHlTiA.css`, 8.8 KB, roughly 50ms. |
| `rankai_word_count_below_target` | rankai_spec | 2 | low | `/` at 1175 vs 1200 target, `/services/` at 779 vs 800. Both within 3 percent. |

## Money page alerts

All five audited money pages are red. Every one of them for the same reason: the hero image 404s.

- **`/`** (home) - red. Requests `/images/hero-bg.webp`, `/images/team.webp` and `/images/services.webp`, all 404. Also carries a 27-char title and a 185-char meta description.
- **`/services/`** (services-hub) - red. Requests `/images/hero-bg.webp` and `/images/services.webp`, both 404.
- **`/services/water-damage-restoration/`** (service-landing) - red. `/images/hero-bg.webp` 404.
- **`/services/mold-remediation/`** (service-landing) - red. `/images/hero-bg.webp` 404.
- **`/contact/`** (contact) - red. `/images/hero-bg.webp` 404. Highest CLS of the set at 0.041, still well inside the 0.1 good threshold.

`/service-areas/oxnard-ca/` is also red for the same 404 but is not a money-page archetype.

## Regressions vs prior audit

First audit for this client. No comparison data. This run becomes the baseline for the September audit.

## Recommended next actions (priority order)

1. **(template, launch-blocking)** **Publish the missing image assets.** `/images/hero-bg.webp`, `/images/team.webp` and `/images/services.webp` all return 404 (the server hands back the 12 KB HTML 404 page instead). `hero-bg.webp` is referenced three ways on every page: as the hero `<img src="/images/hero-bg.webp" loading="eager" fetchpriority="high">`, as `og:image`, and as `twitter:image`. So the hero is blank sitewide and every social or AI-answer card for this domain renders with no image.
   Root cause is upstream, not in the site repo: `clients/california-restoration-west/photo-manifest.json` has 98 triaged assets but `"slots": {}`. The slot assignment step never ran, so the image build had nothing to emit. Re-run photo slotting for this client, regenerate the derivatives, redeploy, then re-audit. Do not cut over the apex domain until this is done.

2. **(template, high impact)** **Replace `/images/logo.png`.** It is a 1,811,735 byte PNG with intrinsic dimensions 900x1200, rendered at 72x96 CSS pixels in the header of all six pages. Lighthouse estimates 1,768 KiB of waste per page load. Export a WebP at 144x192 (2x DPR) and correct the HTML attributes, which currently read `width="64" height="64"` and match neither the intrinsic nor the rendered aspect ratio. Desktop scores hide most of this because the run uses a 10 Mbps pipe; on a real mobile connection a 1.73 MB header logo is the single most expensive thing on the page.

3. **(template, accessibility)** **Darken the breadcrumb link color.** The breadcrumb anchors use `text-dark/50`, which computes to `#888c93` on `#ffffff` at 12px. That is a contrast ratio of 3.37:1 against the WCAG AA requirement of 4.5:1. Affects all five pages that render breadcrumbs (every page except home). Move to `text-dark/70` or whichever token clears 4.5:1 and re-check. This is the only accessibility failure on the site.

4. **(money page)** **Fix the home page title and meta description.** The live `<title>` is `California Restoration West`, 27 characters, below the 30 to 65 window and carrying no city or service term. `url-plan.json` already specifies the correct 66-character title (`California Restoration West | Restoration Services in Ventura, CA`), so the home template is falling back to the bare brand name instead of consuming the planned value. The meta description is 185 characters and will truncate in the SERP; the planned value is the same 185 characters, so trim it at the plan level to 160 or fewer. Every other audited page has a correct title (57 to 65 chars) and description (120 to 137 chars).

5. **(environment)** **Cut over the apex domain and re-audit.** SEO findings are deferred, not resolved. Until `californiarestorationwest.com` serves the site, the `is-crawlable` failure makes the SEO category unreadable and the canonical tags (which already point at the apex) cannot be validated against the origin serving them. `cutover_prep` is already done: 10 URLs harvested, 7 redirects mapped. Sequence this after actions 1 and 2, then re-run this audit against the apex.

## Notes / caveats

- **Client status.** `clients/california-restoration-west.json` has `status: "onboarding"`, not `"active"`. The methodology gates on active. `build_status` is `pushed_main` and all six URLs returned HTTP 200, so the site was auditable and the run proceeded rather than aborting. Flagging rather than silently skipping.
- **Schema is present. DataForSEO says otherwise and is wrong.** The on-page API returned `has_micromarkup: false` on all six URLs. Verified directly against the served HTML: every page ships one `application/ld+json` block containing `LocalBusiness`, `Organization`, `WebSite`, `BreadcrumbList` and `FAQPage`, with `Service` added on service landings and `AdministrativeArea` on the water-damage page. This is a vendor false negative and is **not** reported as a missing-schema defect. Worth remembering for other clients, since the rubric would otherwise fire a false high-severity money-page alert on every Rank AI site.
- **Canonicals are correct.** All six point at `https://californiarestorationwest.com/...`. From staging that is technically an offsite canonical, but it is the intended production target, so it is not counted as a defect.
- **Google Maps caching on `/service-areas/oxnard-ca/` is not actionable.** `cache-insight` flags 18 KiB of savings on two `maps.googleapis.com` resources (a 38.9 KB static map tile at a 24h TTL and the Maps JS at 30 min). Those cache headers are set by Google, not by us. Ignore.
- **URL selection.** No `audit-urls.txt` exists, so the six URLs were auto-derived from `plan/url-plan.json`. `url-plan.json` has no `service-area` entry with `primary: true`, and the primary city from `plan-input.json` (Ventura) has no dedicated area page because the home page targets it. Fell back to the first area slug, `/service-areas/oxnard-ca/`.
- **Data hygiene.** `display_name` is `"California Restoration West "` with a trailing space. It propagates into rendered titles, image alt text and schema (`California Restoration West  logo` renders with a double space). Cosmetic, but it is in the JSON-LD that Google reads. Worth trimming at the client-record level. Separately, `contact` on the client record is `Californiarestorationwest@gmail.com.com` with a doubled TLD.
- **Mobile is now technically reachable.** The DataForSEO MCP surface has collapsed to a generic `api_request` tool, so the raw `/v3/on_page/lighthouse/live/json` endpoint and its `for_mobile` parameter are directly available. This run stayed on desktop to remain comparable with the rest of the fleet and with the thresholds in this methodology. Switching the fleet to mobile is a deliberate decision to make once, not per client.
- **Cost.** 6 Lighthouse live calls plus 6 instant-pages calls. Two earlier Lighthouse batches were rejected for invalid parameters (`categories: "best-practices"` and `version: "latest"`) and were billed at zero.
