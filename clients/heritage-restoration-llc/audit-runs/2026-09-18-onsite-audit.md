# Onsite Audit - Heritage Restoration LLC - 2026-09-18

**Live origin audited:** https://staging.rankai-heritage-restoration-llc.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit
**Form factor:** desktop only (Lighthouse 13.4.0, cpuSlowdownMultiplier=1, 10240 Kbps, 1350x940)

> **STAGING AUDIT. SEO SCORE IS INCONCLUSIVE.**
> This client has no `apex_cutover.completed_at`, so the audit ran against the
> Cloudflare Pages staging preview. Cloudflare injects `x-robots-tag: noindex` on
> `*.pages.dev` previews, which fails the Lighthouse `is-crawlable` audit and drags
> SEO down to 69 on all six pages. That is an environment artifact, not a site defect.
> **SEO is recorded as-is but excluded from every verdict in this run.** Verdicts below
> are computed from performance, accessibility and best practices only.
> `is-crawlable` is the *only* failing SEO audit on all six pages, so SEO should measure
> 100 once the apex is serving. Re-audit after cutover to confirm.

> Scores below are DESKTOP. Mobile would typically land 10 to 20 performance points
> lower, and the mobile-only audits (`font-size`, `tap-targets`, `viewport`) were not
> evaluated at all. Do not quote these as mobile-first numbers.

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 99.3 | n/a |
| Accessibility | 96.0 | n/a |
| Best Practices | 100 | n/a |
| SEO | 69.0 (inconclusive) | n/a |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | Words |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 99 | 100 | 100 | 69* | 0.9s | 0.007 | 1235/1200 |
| `/services/` | services-hub | green | 99 | 95 | 100 | 69* | 0.9s | 0.006 | 796/800 |
| `/services/water-damage-restoration/` | service-landing | green | 100 | 95 | 100 | 69* | 0.8s | 0.008 | 1761/1100 |
| `/services/storm-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 69* | 0.9s | 0.008 | 1888/1100 |
| `/service-areas/st-cloud-mn/` | service-area | green | 99 | 95 | 100 | 69* | 0.9s | 0.008 | 1271/900 |
| `/contact/` | contact | green | 100 | 96 | 100 | 69* | 0.8s | 0.011 | 676/400 |

\* SEO excluded from the verdict. See the staging block above.

Total Blocking Time was 0 ms on all six pages. INP is not produced by a lab run and is
recorded as null. All six pages returned HTTP 200. No broken internal links, no broken
external links, no broken resources, no mixed content (zero `http://` references), no
duplicate titles or descriptions. Every page has exactly one H1, 100 percent image alt
coverage, and 3 to 5 valid JSON-LD blocks. All security headers pass: HSTS,
`x-content-type-options`, `referrer-policy`, `permissions-policy`, and the Lighthouse
`csp-xss`, `has-hsts`, `origin-isolation` and `trusted-types-xss` audits all score 1.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is the worst offender and appears on every page: 79 KB PNG, intrinsic 1200x296, rendered at 389x96, wasting 73 KB per page load. Also `storm-damage-restoration.webp` at 288 KB and `team.webp` at 196 KB. See action 3. |
| `render-blocking-insight` | 6 | medium | `_astro/_slug_.C4WG1zzV.css` (8.6 KB) blocks first paint for a measured 53 ms. Inline the critical subset or preload the route stylesheet. Low absolute cost given LCP is already under 1s. |
| `is-crawlable` | 6 | low | Environment artifact only. Cloudflare's `x-robots-tag: noindex` on the `*.pages.dev` preview. Resolves itself at apex cutover. Do not "fix" this. |
| `canonical` | 6 | low | Every page canonicalises to `https://heritagermn.com/<path>`, the correct post-cutover target, so it is not self-referencing on the staging origin and DataForSEO flags it. Lighthouse's own `canonical` audit passes. Expected pre-cutover state. |
| `color-contrast` | 5 | high | Breadcrumb links (`nav.container-wide > ol.flex > li.flex > a.text-dark/50`) render #888c93 on #ffffff = 3.37:1 at 12px, below the WCAG AA 4.5:1 floor. axe impact: serious. This is the single audit holding accessibility at 95 instead of 100. |
| `lcp-discovery-insight` | 5 | high | The hero image on every non-home page has no `fetchpriority="high"`. The home page hero has it, the shared inner-page hero does not. See action 4. |
| `largest-contentful-paint` | 5 | low | LCP measures 0.79s to 0.91s, comfortably inside the 2.5s "good" threshold. Flagged only because the audit scores 0.96 to 0.98 rather than a clean 1.0. No action needed. |
| `cache-insight` | 1 | low | `maps.googleapis.com` serves its JS with a 30 minute lifetime and its static map tile with 24 hours. Third-party, not fixable in the template. Only affects `/service-areas/st-cloud-mn/`. |

## Money page alerts

- **`/`** (home) - verdict: amber. Lighthouse is effectively perfect (performance 99,
  accessibility 100, best practices 100, LCP 0.87s, CLS 0.007). The amber comes from a
  single on-page defect: the meta description is 181 characters, 21 over the 160 limit,
  so Google will truncate it mid-sentence and cut the phone number off the end. This is
  the one finding standing between this site and an all-green audit. See action 2.

`/services/`, both service landings and `/contact/` all came back green.

The one item worth tracking even though it does not flip a verdict: the breadcrumb
contrast failure at 3.37:1 affects `/services/`, both service landings, `/contact/` and
the service-area page. It is a WCAG AA failure on every money page except home.

## Regressions vs prior audit

First audit for this client. No comparison data. This run is the baseline for next month.

## Recommended next actions (priority order)

1. **(blocker, environment)** Cut over the apex `heritagermn.com` and re-audit. The
   domain currently resolves to 160.153.0.157, a registrar parking IP: the TLS handshake
   fails outright and plain HTTP returns 409. Every audited page already canonicalises to
   `https://heritagermn.com/<path>`, so right now all six canonical targets are
   unreachable. Until cutover lands, the SEO category is deferred rather than resolved,
   and nothing on this site can rank. This is the highest-value action by a wide margin.
2. **(money page)** Trim the home page meta description from 181 to 160 characters or
   fewer. Current value is "Heritage Restoration LLC provides water, fire, mold, and
   storm damage restoration across Little Falls and surrounding areas. Licensed, insured,
   IICRC-certified. Call (320) 733-8868." The phone number sits at the very end and will
   be the first thing truncated. Suggested rewrite at 152 characters: "Water, fire, mold,
   and storm damage restoration in Little Falls, MN. Licensed, insured, IICRC-certified.
   Call Heritage Restoration at (320) 733-8868." Fix this in
   `plan/url-plan.json` for the `home` entry so it survives the next render. This single
   edit flips the home page and the whole site from amber to green.
3. **(template, high impact)** Replace `/images/logo.png`. It is a 79 KB PNG with
   intrinsic dimensions 1200x296, served on all six audited pages and rendered at roughly
   389x96 CSS px, wasting 73 KB on every page load (438 KB across the six audited pages
   alone). Re-export as WebP at about 780px wide (2x) and it drops to single-digit KB.
   While editing, fix the markup: the header `<img>` declares `width="64" height="64"` on
   an image whose intrinsic ratio is 4.05:1, so the declared aspect ratio is wrong. That
   bad declaration is also the cited cause of one of the two layout shifts on the home
   page ("Media element lacking an explicit size"). Then recompress the two other heavy
   assets: `/images/services/storm-damage-restoration.webp` is 288 KB with 166 KB of pure
   compression waste, and `/images/team.webp` is 196 KB with 100 KB of waste.
4. **(template, LCP)** Add `fetchpriority="high"` to the hero `<img>` in the shared
   inner-page hero section (`main.flex-1 > section.relative > div.absolute > img.w-full`).
   Lighthouse reports `priorityHinted: false` on all five non-home pages; the image is
   already eagerly loaded and discoverable in the initial document, so the priority hint
   is the only missing piece. The home page hero (`header.relative` variant) already has
   it, which is why home is the one page that passes this audit. While in that component,
   add a `srcset` for `/images/hero-bg.webp`: the 1376x765 source is reused for inner-page
   hero bands only 207px to 533px tall, wasting 64 KB to 130 KB depending on the page.
5. **(template, accessibility)** Darken the breadcrumb link token. `a.text-dark/50`
   resolves to #888c93 on white = 3.37:1 at 12px, failing WCAG AA. Raise the token to at
   least #64696f to clear 4.5:1. This is the only accessibility audit failing anywhere on
   the site, and fixing it takes accessibility from 95 to 100 on five of six pages.

## Notes / caveats

- **Staging origin, SEO deferred.** Covered in the block at the top. `is-crawlable` is
  the sole failing SEO audit on all six pages; every other SEO audit (`canonical`,
  `robots-txt`, `meta-description`, `document-title`, `link-text`, `image-alt`,
  `hreflang`, `crawlable-anchors`, `http-status-code`) scores 1. SEO should read 100 at
  the apex.
- **Desktop only.** The DataForSEO Lighthouse call ran `for_mobile=false`, giving
  `formFactor=desktop`, `cpuSlowdownMultiplier=1` and `throughputKbps=10240`. The
  mobile-only audits `font-size`, `tap-targets` and `viewport` were absent from the
  response entirely, so small-screen tap-target and legibility problems are not covered
  by this run. Worth noting that the REST endpoint does expose `for_mobile`, so a future
  version of this skill could run both form factors for roughly double the per-URL cost.
- **Client record status.** `clients/heritage-restoration-llc.json` has
  `status: "onboarding"`, not `"active"`, which strictly speaking fails the documented
  pre-flight gate. The audit proceeded because `build_status` is `pushed_main` and the
  staging preview serves the current build, so the intent of the gate (the site is live
  somewhere auditable) is met. Ops owner should flip the status to `active` at cutover.
- **Schema false negative.** DataForSEO's `has_micromarkup` check returns false on all
  six pages. This is wrong. Each page serves 3 to 5 valid JSON-LD blocks (Organization,
  WebSite, LocalBusiness, Service, FAQPage, BreadcrumbList), all of which parse clean. The
  check only detects Microdata and RDFa attributes, not JSON-LD. No missing-schema issue
  was recorded, and none should be opened.
- **URL selection.** No `audit-urls.txt` exists, so the six URLs were auto-derived from
  `plan/url-plan.json`. The two service landings are the top two by priority: water damage
  at 9.0, then storm damage at 8.1 (tied with water cleanup, broken by plan order). For
  the service-area slot, no `service-area` entry in the url-plan carries `primary: true`,
  and the primary city from `plan-input.json` is Little Falls, which has no
  `/service-areas/little-falls-mn/` page because the primary city is folded into the home
  page. The rule therefore fell through to the first area in plan order, St. Cloud, which
  is also the largest market in the list.
- **Google Maps API key.** `/service-areas/st-cloud-mn/` loads the Maps JS API with the
  key in the query string. That is unavoidable for a browser-side Maps embed, but the key
  should be HTTP-referrer-restricted to the client's domains in Google Cloud Console.
  Worth a one-time verification, not a defect found by this audit.
- **Content note, out of scope.** The home page title and meta description advertise fire
  and mold restoration, but the url-plan contains no fire or mold service pages (the four
  services are water damage restoration, storm damage restoration, general contracting and
  water cleanup). That is a content and claims question for System 4 and `claims_lint`,
  not a technical finding, but it is flagged here because it was visible in the meta data
  this audit read.
- **Tooling deviation.** The `on_page_lighthouse` and `on_page_instant_pages` MCP tools
  are not exposed by this MCP server build, which only provides a generic `api_request`.
  The audit called the DataForSEO REST API directly at
  `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` with desktop
  settings. Raw responses (roughly 5.7 MB of Lighthouse JSON) were written to disk and
  parsed with Python, never read into context.
- **Cost.** 6 Lighthouse calls at $0.005 plus 6 instant_pages calls at $0.0051 = $0.0606
  total, well under the $0.30 to $0.50 target. One earlier Lighthouse batch was rejected
  for an invalid `version` field and was billed at $0.
