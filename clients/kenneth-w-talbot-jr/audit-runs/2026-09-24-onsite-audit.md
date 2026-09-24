# Onsite Audit - Veterans Remediation & Restoration - 2026-09-24

**Live origin audited:** https://staging.rankai-kenneth-w-talbot-jr.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client - no comparison data
**Form factor:** desktop (Lighthouse 13.4.0, cpuSlowdownMultiplier=1, throughputKbps=10240). Mobile scores would typically run 10-20 performance points lower. These are NOT mobile-first scores.

## Environment caveat - SEO is inconclusive this run

This audit ran against the Cloudflare Pages staging preview. `curl -sI` confirms it returns `x-robots-tag: noindex`, so the Lighthouse `is-crawlable` audit fails on all 6 URLs and pins the SEO category at 69 everywhere. That comes from the preview host. It is not a site defect.

**SEO is excluded from every verdict in this report.** The score is still recorded in the state file. SEO status: `inconclusive - staging noindex artifact, re-audit after apex cutover`. Verdicts use Performance, Accessibility, and Best Practices only.

Related notes:

- Canonicals point at the future apex (`https://veteransremediation.com/...`), not at the staging host. That is correct before cutover, so it is not counted as an offsite-canonical defect. The `veteransremediation.com` Cloudflare zone is still `pending` (nameservers not switched yet).
- DataForSEO `instant_pages` returned `has_micromarkup: null`. JSON-LD is actually present and parses on every page: LocalBusiness on all 6, plus Organization/WebSite on the hub pages and Service, FAQPage, and BreadcrumbList on the inner pages. This was checked against the served HTML. There is no schema defect.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 92.3 | n/a |
| Accessibility | 96.0 | n/a |
| Best Practices | 100.0 | n/a |
| SEO (excluded) | 69.0 | n/a |

Pages by verdict: green: 2, amber: 4, red: 0, error: 0

This is a clean build with one dominant problem. Best Practices is 100 on every page, TBT is 0ms everywhere, CLS stays under 0.031, and there are no broken links, broken resources, or mixed content. Four of the six pages score Performance 89, and one cause explains all four: the header logo is a 1024x1024 PNG weighing 1.9 MB (1,917,829 bytes), shown at about 56-64px tall on every page. It makes up about 70% of each page's total weight (2.4-2.8 MB).

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 89 | 100 | 100 | 69* | 2.26s | 0.003 | 0ms |
| `/services/` | services-hub | green | 99 | 95 | 100 | 69* | 0.83s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | amber | 89 | 95 | 100 | 69* | 2.19s | 0.024 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 69* | 0.85s | 0.030 | 0ms |
| `/service-areas/destin-fl/` | service-area | amber | 89 | 95 | 100 | 69* | 2.25s | 0.003 | 0ms |
| `/contact/` | contact | amber | 89 | 96 | 100 | 69* | 2.23s | 0.020 | 0ms |

\* SEO excluded from verdict because of the staging noindex artifact. INP is null on all pages because Lighthouse navigation mode does not produce it.

The 89 vs 99 split comes from the same template and the same logo. On the four slow pages, the 1.9 MB logo download competed with the hero image for bandwidth and pushed LCP to about 2.2s. On `/services/` and `/services/fire-damage-restoration/`, the hero won the race. First Contentful Paint is 0.3-0.4s on all the slow pages, so the HTML and CSS arrive fast. Only the LCP image is late.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is 1,917,829 bytes at 1024x1024 and is shown at 56-64px tall. Lighthouse estimates 1.30-1.45s of LCP savings on the four slow pages. Replace it with a resized WebP (about 480px wide, under 30 KB). |
| `largest-contentful-paint` | 4 | high | LCP is 2.19-2.26s on `/`, the water-damage landing page, `/service-areas/destin-fl/`, and `/contact/`. This is a symptom of the logo issue above, and fixing that should clear it. |
| `color-contrast` | 5 | medium | Breadcrumb links in `src/components/Breadcrumb.astro` use `text-dark/50`, which renders as `#888c93` on white. That is 3.37:1 at 12px, below the 4.5:1 AA minimum. Change it to `text-dark/70` or darker. This is the only accessibility failure on the site. |
| `lcp-discovery-insight` | 5 | low | Inner-page hero `<img>` tags have `loading="eager"` but no `fetchpriority="high"`. The home hero already has it. Add it to the inner-page hero components. |
| `render-blocking-insight` | 6 | low | `_astro/_slug_.iR0GJrkX.css` (about 9 KB) blocks for 50-60ms. Not worth acting on at this size. |
| `network-dependency-tree-insight` | 6 | low | Diagnostic only, no score impact. |
| `is-crawlable` | 6 | environment | Staging noindex artifact. No action needed; it resolves at apex cutover. |

The home page also has its own `total-byte-weight` flag (2,796 KiB). The logo accounts for 1,873 KiB of that, and `team.webp` has about 163 KiB of recoverable waste.

## Money page alerts

- **`/`** (home) - verdict: amber. Performance 89, LCP 2.26s, caused by the 1.9 MB logo. The meta description is also 175 characters, 15 over the 160-character SERP truncation point.
- **`/services/water-damage-restoration/`** (service-landing, highest-priority page in the plan) - verdict: amber. Performance 89, LCP 2.19s, same logo cause. The breadcrumb contrast issue is on this page too.
- **`/contact/`** (contact) - verdict: amber. Performance 89, LCP 2.23s, same logo cause.

`/services/` and `/services/fire-damage-restoration/` came back green. They carry the same 1.9 MB logo, though, so their scores are luck of the load order. They are not structurally faster.

## Regressions vs prior audit

This is the first audit for this client, so there is no comparison data. This run sets the baseline at `clients/kenneth-w-talbot-jr/onsite-audit.json`.

## Recommended next actions (priority order)

1. **(blocked externally, unblocks SEO scoring)** Complete the apex cutover to `veteransremediation.com`, then re-audit. The Cloudflare zone is still `pending`, so the registrar nameservers need to move to `amos.ns.cloudflare.com` / `anastasia.ns.cloudflare.com`. Until then the SEO category cannot be measured. Treat SEO findings as deferred, not resolved.

2. **(money pages + template, high)** Replace `sites/kenneth-w-talbot-jr/public/images/logo.png` (1024x1024, 1.9 MB) with a resized, compressed version. For example, export a 480px-wide WebP (or a PNG run through pngquant/oxipng) under 30 KB, and point `logoUrl` in `src/lib/brand.ts` to it. While editing `src/components/Header.astro`, correct the `width="36" height="36"` attributes to the logo's real aspect ratio. The same file loads in the footer and in the JSON-LD `logo`, so one swap fixes every page. Expected result: Performance goes from 89 to the high 90s on `/`, `/contact/`, the water-damage landing page, and the Destin area page, and page weight drops from about 2.5 MB to about 0.6 MB.

3. **(money page, medium)** Trim the homepage meta description from 175 to 160 characters or fewer. The current text ends "...Licensed, insured. Call (337) 344-1248.", so the phone-number call to action gets cut off in search results. Update it in the url-plan / page source for `/`. Every other audited page is within range (112-138).

4. **(template, medium)** In `sites/kenneth-w-talbot-jr/src/components/Breadcrumb.astro`, change the breadcrumb link class from `text-dark/50` to `text-dark/70` (or a darker gray that measures 4.5:1 or better). That clears the only `color-contrast` failure and should lift Accessibility from 95-96 to 100 on the 5 inner pages. The component is shared by the starter template, so check whether the fix belongs upstream too.

5. **(template, low)** Add `fetchpriority="high"` to the hero `<img>` on inner-page templates (service landing, service area, services hub, contact). The home hero already has it. This lets the browser prioritize the LCP image over the logo and other images.

## Notes / caveats

- The client record has `status: "onboarding"`, not `"active"`. The audit went ahead because `build_status` is `pushed_main` (last pushed 2026-09-24T16:56Z), and the pipeline's System 3 gate keys on `build_status`. Other onboarding clients (tdi-builders, crew-restoration-construction) were audited under the same precedent. The written methodology and the scheduler still disagree on this gate; one of them should be updated.
- The `mcp__dataforseo__on_page_lighthouse` and `mcp__dataforseo__on_page_instant_pages` tools are not in this MCP build. The endpoints were called directly (`/v3/on_page/lighthouse/live/json` with `for_mobile: false`, and `/v3/on_page/instant_pages`), with raw responses written to disk and parsed there. The live Lighthouse response already includes full audit detail, so no separate `full_data` call was needed. Total API cost was about $0.031.
- `audit-urls.txt` does not exist, so URLs were auto-derived from `plan/url-plan.json` (Mode B). Three service landings are tied at priority 9.0, so the first two in plan order were used (water damage, fire damage). No service-area page has `primary: true`, and the home city (Freeport) has no service-area page among the 22, so the first area slug was used: `/service-areas/destin-fl/`. Consider adding a Freeport area page or a `primary: true` flag so this pick stays the same month to month.
- On-page checks computed from the returned `meta` object, not from DataForSEO check flags, are marked `"source": "computed"` in the state file: `meta_description_too_long` on `/`, and `low_content_rate` on `/services/` (699 words vs the 800 target, low severity). The `frame` flag on `/service-areas/destin-fl/` is the intentional Google Maps embed. It is informational only.
- Image alt coverage is 100% on all 6 pages. There is no mixed content, and there are no broken internal or external links.
- All 6 URLs returned HTTP 200 and audited cleanly. There were no errors or timeouts, and no re-run is needed.
