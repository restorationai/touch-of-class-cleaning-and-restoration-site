# Onsite Audit - Dry County Restoration - 2026-09-28

**Live origin audited:** https://staging.rankai-dry-county-restoration.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26 (red)
**Form factor:** desktop only (see caveats)

## Staging environment caveat (SEO score excluded from verdict)

The audited origin is a Cloudflare Pages preview and returns `x-robots-tag: noindex`. That makes the Lighthouse `is-crawlable` audit fail on all 6 URLs and deflates the SEO category to a uniform 69.

**The SEO score of 69 is inconclusive. It is a staging noindex artifact, re-audit after apex cutover.** Per methodology the verdict below is computed from Performance, Accessibility, and Best Practices only.

## Headline: the `https://None` blocker is fixed

Last month every page was red because `client.domain` was null and every canonical, `og:url`, JSON-LD `url`, and the `robots.txt` sitemap line rendered as `https://None`. The domain is now set. All 6 pages now serve `https://drycountyrestoration.com/...` in canonical, `og:url`, and JSON-LD, and `robots.txt` points to `https://drycountyrestoration.com/sitemap-index.xml`. The production Pages build (`rankai-dry-county-restoration.pages.dev`) serves the same corrected canonical.

Result: 5 of 6 pages moved red to green. The homepage moved red to amber, held back only by an over-length meta description.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.7 | -0.3 |
| Accessibility | 95.3 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 69.0 (inconclusive) | 0.0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 98 | 96 | 100 | 69 | 1.11s | 0.003 | 0ms |
| `/services/` | services-hub | green | 98 | 95 | 100 | 69 | 1.10s | 0.003 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 69 | 1.01s | 0.030 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 69 | 1.00s | 0.030 | 0ms |
| `/service-areas/riverside-ca/` | service-area | green | 99 | 95 | 100 | 69 | 1.01s | 0.003 | 0ms |
| `/contact/` | contact | green | 99 | 96 | 100 | 69 | 1.03s | 0.027 | 0ms |

All Core Web Vitals pass comfortably on desktop: LCP 1.0 to 1.1s, CLS well under 0.1, TBT zero everywhere.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | medium | `/images/logo.png` is still a 245KB PNG (598x600) rendered at 64x64 in the header. Export a 128x128 WebP (2x for retina), point `brand.logoUrl` in `src/lib/brand.ts:52` at it. Saves about 239KiB on every page. |
| `color-contrast` | 6 | medium | Brand primary `#007fb2` on white is 4.48:1 (needs 4.5:1). Change `primary.DEFAULT` in `tailwind.config.mjs:30` to `#00719e` (5.45:1). Also see breadcrumb and `btn-accent` fixes below. |
| `unused-javascript` | 6 | low | New this month: GA4 `gtag/js?id=G-211581WVBQ` (156KB, 69KiB unused). Already loaded `async`, costs 50 to 100ms. No action recommended; it is required for tracking. |
| `render-blocking-insight` | 6 | low | Single 9KB stylesheet `_astro/_slug_.Dq2ycaMD.css`, about 55ms. No action needed. |
| `network-dependency-tree-insight` | 6 | low | Chain is document then Astro CSS. Already short. No action needed. |
| `lcp-discovery-insight` | 5 | low | Hero `<img>` lacks `fetchpriority="high"` on every template except home. See action 5. |
| `is-crawlable` | 6 | low | No action. Staging noindex artifact, excluded from verdict. |

## Money page alerts

- **`/`** (home) - verdict: amber. Meta description is 178 characters (target 70 to 160), so Google will truncate it mid-sentence in the SERP. Lighthouse scores are all 96 to 100 and LCP is 1.11s, so this is the only issue on the page.

All other money pages (`/services/`, both service landings, `/contact/`) are green.

## Regressions vs prior audit

No metric regressions. No URL dropped 5 or more points in any category, no LCP increase of 200ms or more (largest was home at +182ms, 930ms to 1112ms), no CLS or TBT regressions, and no site average fell by 3 or more points.

**Verdict transitions (all improvements):**
- `/` went red to amber. Canonical defect fixed; meta description length still open.
- `/services/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`, `/service-areas/riverside-ca/`, `/contact/` went red to green. Canonical defect fixed.

**New issues this month:**
- All 6 pages: `unused-javascript`. GA4 gtag was added since last audit; 69KiB of the 156KB script goes unused. Expected cost of analytics, low severity.
- `/services/`: `rankai_word_count_below_target`. 768 words against a `target_word_count` of 800. Low severity.
- `render-blocking-insight` shows as new on 5 pages but it was already failing last month outside the stored top-5 list. This is list churn, not a change on the site.

**Issues resolved since last audit:** (positive, keep doing this)
- All 6 pages: `rankai_canonical_unresolvable_host` no longer flagged. Canonical and `og:url` now resolve to `https://drycountyrestoration.com/`.
- All 6 pages: `rankai_schema_url_unresolvable_host` no longer flagged. JSON-LD `url` now resolves correctly.

## What is still healthy

- Zero broken internal links, external links, or resources across all 6 pages.
- Image alt text coverage 100 percent on all pages.
- One H1 per page, no duplicate titles or meta descriptions. All titles 55 to 62 characters.
- JSON-LD present and parse-clean on every page (Organization, WebSite, LocalBusiness, Service, FAQPage, BreadcrumbList).
- HTTPS everywhere, no mixed content.

## Recommended next actions (priority order)

1. **(blocker for SEO numbers, cutover)** Cut over the apex domain and re-audit. Today `drycountyrestoration.com` 301s to `www.drycountyrestoration.com`, which still serves the legacy WP Engine / Elementor site with a `www` canonical. The Rank AI build canonicalises to the bare apex, so at cutover point the apex at Pages and 301 `www` to the apex (not the reverse). Otherwise every canonical points at a URL that redirects. SEO findings stay deferred until this re-audit.
2. **(money page)** Trim the homepage meta description in `sites/dry-county-restoration/src/content/pages/home.md:5` from 178 to under 160 characters. Suggested: "24/7 water, fire, mold, and storm damage restoration in Corona and nearby areas. Licensed, insured, IICRC-certified. Call (951) 667-9910." (138 chars). Mirror it in `plan/url-plan.json` so the plan does not regenerate the long version.
3. **(template, every page)** Replace `/images/logo.png` (245KB PNG, 598x600, rendered at 64x64) with a 128x128 WebP and update `logoUrl` in `src/lib/brand.ts:52`. This is the largest single byte saving on the site, about 239KiB per page load. Carried over from last month.
4. **(template, accessibility)** Fix three contrast failures in `tailwind.config.mjs`: brand primary `#007fb2` to `#00719e` (4.48:1 to 5.45:1, footer phone/email/nav links on every page); `btn-accent` background `#fe0000` (line 61) to `#e00000` (4.02:1 to 5.04:1, header call button on service pages); breadcrumb `text-dark/50` (`#888c93`, 3.37:1) to `text-dark/70` or darker (at least 4.5:1). Carried over from last month.
5. **(template, LCP)** Add `fetchpriority="high"` to the page-hero `<img>` in `src/pages/services/[slug].astro:60` and the matching hero markup in `src/pages/service-areas/[area].astro` and the services hub and contact heroes. Home already has it via `Hero.astro`. One attribute, fixes `lcp-discovery-insight` on 5 pages.

## Notes / caveats

- **Desktop only.** Lighthouse ran with `for_mobile=false` (formFactor=desktop, no CPU throttling) for comparability with 2026-08-26. Mobile performance would likely land 10 to 20 points lower. The amber verdict is a desktop verdict.
- **Client status deviation.** The client record is `status: "onboarding"`, not `"active"`. `build_status` is `pushed_main` and all 6 URLs returned 200, so the audit proceeded, as it did last month.
- **URL selection.** No `audit-urls.txt`, so URLs were derived from `plan/url-plan.json`, the same set as last month for like-for-like comparison. Four service landings tie at priority 9.0 (water, fire, mold, roofing); the first two by plan order were kept.
- **Phone number in Lighthouse vs HTML.** Lighthouse's rendered DOM shows `tel:+19516293771` while the raw HTML serves `tel:+19516679910`. This is the intended call-tracking swap (`trackingPhone` in `brand.ts`); schema and NAP keep the canonical number. Not a defect.
- **Schema image URLs are relative.** JSON-LD `logo` and `image` are emitted as `/images/logo.png` rather than absolute URLs. Google generally resolves these, but absolute URLs are safer for validators. Low priority; fold into the logo swap in action 3 by making `logoUrl` absolute when used in schema.
- **Custom issue IDs.** `rankai_meta_description_length` and `rankai_word_count_below_target` are Rank AI manual checks, namespaced so they are not mistaken for Lighthouse or DataForSEO IDs. `frame` on the Riverside page is DataForSEO's check firing on the intended Google Maps embed (low, informational).
- **Tool surface.** The MCP server only exposes a generic `api_request`, so `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` were called over REST with the `DATAFORSEO_*` credentials and parsed from disk. 12 calls, about $0.03. No URL errored.
- **Issue diffing.** `new_issues` compares stored top-5 and on-page lists. `resolved_issues` requires the issue to be absent from the current full failing set, so nothing is marked resolved just because it fell out of the top 5.
