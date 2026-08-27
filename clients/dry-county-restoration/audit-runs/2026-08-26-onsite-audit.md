# Onsite Audit - Dry County Restoration - 2026-08-26

**Live origin audited:** https://staging.rankai-dry-county-restoration.pages.dev (staging)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** first audit for this client - no comparison data
**Form factor:** desktop only (see caveats)

## Blocking issue: every page canonicalises to `https://None`

This is the headline finding and it is a hard blocker for apex cutover.

`clients/dry-county-restoration.json` has `"domain": null`. The site build interpolates that null straight into the templates as the Python string `None`, so every audited page ships:

- `<link rel="canonical" href="https://None/...">`
- `<meta property="og:url" content="https://None/...">`
- JSON-LD `LocalBusiness` / `Organization` / `WebSite` `"url": "https://None"`
- `robots.txt` with `Sitemap: https://None/sitemap-index.xml`

`https://None` is not a resolvable host. If this reaches an indexable production domain, every page self-canonicalises to a dead host and the sitemap directive is unfetchable, which is an indexation-loss scenario rather than a ranking-loss one.

This is **not** a staging-only artifact. The production Pages build (`https://rankai-dry-county-restoration.pages.dev/`, last pushed to main 2026-08-26) serves the identical `https://None/` canonical. It is already live on the production branch.

## Staging environment caveat (SEO score excluded from verdict)

The audited origin is a Cloudflare Pages preview and returns `x-robots-tag: noindex`. That makes the Lighthouse `is-crawlable` audit fail on all 6 URLs and deflates the SEO category to a uniform 69.

**The SEO score of 69 is inconclusive - it is a staging noindex artifact, not a site defect.** Per methodology the verdict below is computed from Performance, Accessibility, and Best Practices only. The production Pages URL does not carry the noindex header, so re-audit after apex cutover for a real SEO number.

The `https://None` canonical issue above is a genuine defect and is unrelated to this caveat.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.0 | n/a |
| Accessibility | 95.3 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 69.0 (inconclusive) | n/a |

Pages by verdict: green: 0, amber: 0, red: 6, error: 0

The red verdict is driven entirely by the canonical defect. On the counted Lighthouse categories the site is genuinely strong: Performance 99 and Best Practices 100 on every single page, with no page falling below 95 on Accessibility.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 99 | 96 | 100 | 69 | 0.93s | 0.003 | 0ms |
| `/services/` | services-hub | red | 99 | 95 | 100 | 69 | 1.02s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | red | 99 | 95 | 100 | 69 | 0.86s | 0.030 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | red | 99 | 95 | 100 | 69 | 0.91s | 0.030 | 0ms |
| `/service-areas/riverside-ca/` | service-area | red | 99 | 95 | 100 | 69 | 0.97s | 0.003 | 0ms |
| `/contact/` | contact | red | 99 | 96 | 100 | 69 | 0.91s | 0.025 | 0ms |

All Core Web Vitals pass comfortably on desktop: LCP under 1.1s everywhere, CLS well under the 0.1 threshold, TBT zero on every page.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `rankai_canonical_unresolvable_host` | 6 | high | Set `domain` in the client record, then rebuild. Add a build-time guard that fails the render if the canonical host is empty, `None`, or `null`. |
| `rankai_schema_url_unresolvable_host` | 6 | high | Same root cause. The JSON-LD `url` fields resolve from the same variable. |
| `image-delivery-insight` | 6 | medium | `/images/logo.png` is a 245KB PNG at 598x600 served into a 96x96 slot. Convert to WebP and ship at 192x192. Saves 238KiB on every page. |
| `color-contrast` | 6 | medium | Brand primary `#007fb2` on white measures 4.48:1 against a 4.5:1 requirement. Darken the token to about `#00719e`. |
| `is-crawlable` | 6 | low | No action. Staging noindex artifact, excluded from verdict. |
| `network-dependency-tree-insight` | 6 | low | Critical chain is document then `_astro/*.css`. Already short. No action needed. |
| `lcp-discovery-insight` | 5 | low | Hero image lacks `fetchpriority="high"`. One-line layout change. |

`render-blocking-insight` also fired on all 6 pages but fell outside the top-5 per-page cap. It is a single 8.8KB stylesheet (`_astro/_slug_.DkBxcLjF.css`) costing about 50ms. Not worth acting on.

## Money page alerts

All 5 money pages are red, all for the same single root cause. None of them have an independent performance or accessibility problem.

- **`/`** (home) - red. Canonical, og:url, and schema url all point to `https://None`. Perf 99, LCP 0.93s.
- **`/services/`** (services-hub) - red. Same canonical defect. Perf 99. Also the heaviest image page at 372KiB of avoidable image bytes across 13 images.
- **`/services/water-damage-restoration/`** (service-landing) - red. Same canonical defect. Perf 99, 1782 words.
- **`/services/fire-damage-restoration/`** (service-landing) - red. Same canonical defect. Perf 99, 1959 words.
- **`/contact/`** (contact) - red. Same canonical defect. Perf 99, LCP 0.91s. Highest avoidable image weight of any page at 377KiB.

## Regressions vs prior audit

First audit for this client. No comparison data. This run establishes the baseline for next month.

## What is already healthy

Worth recording so next month's regression check has context:

- Zero broken internal links, zero broken external links, zero broken resources across all 6 pages.
- Image alt text coverage 100 percent on all 6 pages (35 images total, none missing alt).
- No duplicate title tags, no duplicate meta tags, no missing H1, exactly one H1 per page.
- All 6 titles within the 30-65 character target (55 to 62).
- JSON-LD present and error-free: `LocalBusiness`, `Organization`, `WebSite`, `Service`, `FAQPage`, `BreadcrumbList`, `AggregateRating`.
- All pages meet or exceed their `target_word_count`. Service landings target 1100 and hit 1782 and 1959.
- HTTPS everywhere, no mixed content, HSTS and `x-content-type-options` present.

## Recommended next actions (priority order)

1. **(blocker, all 6 pages, money pages included)** Set `"domain"` in `clients/dry-county-restoration.json` (currently `null`) and rebuild. This one change fixes canonical, og:url, JSON-LD `url`, and the `robots.txt` sitemap directive across all 136 planned URLs. Do this before apex cutover, and note the bad canonical is already live on the production Pages branch.
2. **(build safety, prevents recurrence)** Add a render-time assertion that fails the build when the canonical host is empty, `None`, or `null`. This defect shipped to main undetected, so it will recur on the next client with a null domain.
3. **(template, every page)** Replace `/images/logo.png`. It is 245KB, natively 598x600, displayed at 96x96, and PNG. Export a 192x192 WebP and correct the `width`/`height` attributes, which currently say `64x64` while CSS renders it at 96x96. Saves about 238KiB per page load site-wide.
4. **(template, accessibility)** Darken brand primary `#007fb2` to roughly `#00719e`. It fails WCAG AA by 0.02 (4.48:1 measured, 4.5:1 required) on footer phone, email, and nav links. Affects 4 to 9 elements per page. Also check `btn-accent` and `text-dark/50`, which fail on the service and area pages.
5. **(per-page)** Trim the homepage meta description from 178 characters to under 160 so it is not truncated in the SERP. Every other page is within range.

## Notes / caveats

- **Client status deviation.** The methodology pre-flight expects `status == "active"`. This client is `"onboarding"`. Because `build_status` is `pushed_main` and all 6 URLs returned HTTP 200, the audit proceeded rather than hard-failing. Flagging so it can be reconciled.
- **Tooling deviation.** The `mcp__dataforseo__on_page_lighthouse` and `mcp__dataforseo__on_page_instant_pages` MCP tools are not available in this environment. Only the generic `api_request` tool exists, and its AI-optimized response omits TBT and the failing-audit arrays. This run called the DataForSEO REST endpoints (`/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages`) directly via curl, writing full responses to disk and extracting with python. Results are equivalent and include the full audit detail.
- **Mobile is now reachable.** The raw REST endpoint does expose `for_mobile`, unlike the MCP wrapper the methodology was written against. This run stayed on desktop for consistency and future month-over-month comparability. Worth a methodology decision: mobile would be the more representative form factor for restoration traffic, and scores would run 10 to 20 performance points lower.
- **URL selection.** No `audit-urls.txt` exists, so URLs were auto-derived from `plan/url-plan.json`. Corona is marked the primary service area in `plan-input.json` but has no `service-area` page in the url-plan (the HQ city is covered by the homepage), so the service-area slot fell through to the first area by plan order, `/service-areas/riverside-ca/`. The two service landings are the joint-highest priority 9.0 entries.
- **Custom issue IDs.** `rankai_canonical_unresolvable_host` and `rankai_schema_url_unresolvable_host` are Rank AI manual checks, deliberately namespaced so they are not mistaken for Lighthouse or DataForSEO check IDs. DataForSEO's native `canonical` check returned false because it only verifies that a canonical tag is present, not that its host resolves. All other issue IDs in this report are real Lighthouse audit IDs.
- **Re-audit trigger.** Re-run this audit immediately after the domain is set and apex cutover completes. Both the canonical defect and the inconclusive SEO score resolve in that same pass.
