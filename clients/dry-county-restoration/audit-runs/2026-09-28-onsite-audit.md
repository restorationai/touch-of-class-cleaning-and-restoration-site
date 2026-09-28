# Onsite Audit - Dry County Restoration - 2026-09-28

**Live origin audited:** https://staging.rankai-dry-county-restoration.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26 (red)
**Form factor:** desktop only (see caveats)

## Staging environment caveat (SEO score excluded from verdict)

The audited origin is a Cloudflare Pages preview and returns `x-robots-tag: noindex`. That makes the Lighthouse `is-crawlable` audit fail on all 6 URLs and holds the SEO category at 69.

**The SEO score of 69 is inconclusive - it is a staging noindex artifact, re-audit after apex cutover.** The verdict below is computed from Performance, Accessibility, and Best Practices only. SEO findings are deferred, not resolved.

## Headline: last month's blocker is fixed

The `https://None` canonical defect that made every page red in August is gone. `client.domain` is now `drycountyrestoration.com`, and all 6 audited pages now ship:

- `<link rel="canonical">` and `og:url` on `https://drycountyrestoration.com/...` (correct path on every page)
- JSON-LD `url` fields on `https://drycountyrestoration.com`
- `robots.txt` with `Sitemap: https://drycountyrestoration.com/sitemap-index.xml`

The site moves from red to amber. The only thing keeping it off green is a too-long meta description on the homepage.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.3 | -0.7 |
| Accessibility | 95.3 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 69.0 (inconclusive) | 0.0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 98 | 96 | 100 | 69 | 1.08s | 0.003 | 61ms |
| `/services/` | services-hub | green | 99 | 95 | 100 | 69 | 0.99s | 0.003 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 98 | 95 | 100 | 69 | 1.12s | 0.030 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | green | 98 | 95 | 100 | 69 | 0.98s | 0.030 | 17ms |
| `/service-areas/riverside-ca/` | service-area | green | 98 | 95 | 100 | 69 | 1.12s | 0.003 | 0ms |
| `/contact/` | contact | green | 99 | 96 | 100 | 69 | 0.88s | 0.027 | 0ms |

All desktop Core Web Vitals pass easily: LCP under 1.2s, CLS under 0.031, TBT under 100ms on every page.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 6 | medium | Brand primary `#007fb2` on white measures 4.48:1 (needs 4.5:1) on footer phone, email, `/services/` and `/emergency/` links. Darken the token to about `#00719e`. Breadcrumb `text-dark/50` (`#888c93`, 3.37:1) and `btn-accent` (white on `#fe0000`, 4.02:1) also fail on inner pages. |
| `image-delivery-insight` | 6 | medium | Still unfixed from August. `/images/logo.png` is a PNG served at 64-96px in the header and footer. Export a 192x192 WebP and correct the `width`/`height` attributes (header says 36x36, footer says 48x48, rendered larger). Hero images also flagged. 245 to 328 KiB avoidable per page. |
| `unused-javascript` | 6 | low | New this month. GA4 tag `gtag/js?id=G-211581WVBQ` loads 159 KiB with about 69 KiB unused. Est. 50 to 100ms. Load it with `async` after first interaction or via Partytown if performance ever slips. |
| `lcp-discovery-insight` | 5 | low | Hero LCP image on inner pages lacks `fetchpriority="high"`. The homepage already has it; copy the attribute into the shared inner-page hero component. |
| `forced-reflow-insight` | 4 | low | New this month, up to 197ms unattributed reflow on `/`. Most likely the GA4 script or a layout-reading script. No action unless TBT rises. |
| `render-blocking-insight` | 3 | low | Single 9 KiB stylesheet (`_astro/_slug_.Dq2ycaMD.css`), about 50 to 63ms. Fires on all 6 pages; shown here only where it made the per-page top-5. Not worth acting on. |

`is-crawlable` (6 URLs) and `network-dependency-tree-insight` (6 URLs) also fired but fell outside the per-page top-5 cap. The first is the staging artifact; the second is a short document-to-CSS chain and needs no action.

## Money page alerts

- **`/`** (home) - verdict: amber. Meta description is 178 characters (target 70-160), so Google will truncate it. Lighthouse is healthy: Perf 98, A11y 96, BP 100, LCP 1.08s.

No other money page is amber or red.

## Regressions vs prior audit

**Verdict transitions:** all improvements, no regressions.
- `/` went red to amber (canonical fixed; meta description length is still open).
- `/services/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`, `/service-areas/riverside-ca/`, `/contact/` went red to green.

**Score regressions:** none. No page dropped 5 or more points in any category, and no site average dropped 3 or more points.

**Core Web Vitals regressions:**
- `/services/water-damage-restoration/`: LCP 857ms to 1121ms (+264ms, over the 200ms threshold). It is still well under the 2.5s "good" line. Single-run Lighthouse varies, and the GA4 tag added since August is a plausible cause. Watch next month; act only if it continues to rise.

**New issues this month:**
- All 6 pages: `unused-javascript` (GA4 `gtag/js`, about 69 KiB unused). The tag was added to the client config around 2026-09-23.
- `/`, `/services/fire-damage-restoration/`, `/service-areas/riverside-ca/`, `/contact/`: `forced-reflow-insight`.
- `/services/`: `rankai_word_count_below_target` (768 words vs 800 target). Not actually new: August measured 770 words but the audit did not flag it.

**Issues resolved since last audit:** (positive - keep doing this)
- All 6 pages: `rankai_canonical_unresolvable_host` is no longer present. Canonicals and og:url resolve to `https://drycountyrestoration.com`.
- All 6 pages: `rankai_schema_url_unresolvable_host` is no longer present. JSON-LD `url` resolves correctly.

## What is still healthy

- Zero broken internal links, external links, or resources on all 6 pages.
- Image alt text coverage 100 percent (every `<img>` on the 6 pages has an `alt` attribute).
- Exactly one H1 per page, no duplicate titles or meta tags, all titles 55 to 62 characters.
- JSON-LD present on every page: `LocalBusiness`, `Organization`, `WebSite`, `Service`, `FAQPage`, `BreadcrumbList`, `AggregateRating`.
- HTTPS, HSTS, `x-content-type-options`, and `referrer-policy` all present. Best Practices 100 on every page.

## Recommended next actions (priority order)

1. **(blocker for real SEO data)** Cut over the apex domain `drycountyrestoration.com` and re-audit. The domain is set and canonicals now point there, but `apex_cutover.completed_at` is empty, so SEO is still unmeasurable behind the staging noindex header.
2. **(money page)** Shorten the homepage meta description from 178 to 150-155 characters. This is the only thing between the site and an all-green verdict. Edit the `meta_description` for `/` in `plan/url-plan.json` (or the page template override) and rebuild.
3. **(template, every page)** Replace `/images/logo.png` with a 192x192 WebP and set correct `width`/`height` (header currently says 36x36, footer 48x48). Carried over from August. Saves about 240 KiB on every page load.
4. **(template, accessibility)** Darken brand primary `#007fb2` to about `#00719e` (4.48:1 today, 4.5:1 required). While in the theme file, darken the breadcrumb `text-dark/50` color to at least `#767676` and the `btn-accent` red `#fe0000` to about `#e00000` so white text passes. Carried over from August.
5. **(template, performance)** Add `fetchpriority="high"` to the hero `<img>` in the shared inner-page hero component (already present on the homepage). One-line change on 5 of 6 audited pages.

## Notes / caveats

- **Client status deviation.** The pre-flight expects `status == "active"`. This client is still `"onboarding"`. `build_status` is `pushed_main` and all 6 URLs return HTTP 200, so the audit proceeded, as it did in August.
- **Tooling.** The `mcp__dataforseo__on_page_lighthouse` and `on_page_instant_pages` MCP tools are not exposed here. This run called `/v3/on_page/lighthouse/live/json` (`for_mobile: false`) and `/v3/on_page/instant_pages` directly, saved the full responses to disk, and extracted them with python. Desktop was kept for month-over-month comparability. Mobile scores would typically run 10 to 20 performance points lower. DataForSEO cost for the run was about $0.04.
- **URL selection.** No `audit-urls.txt` exists, so URLs came from `plan/url-plan.json`. Four service landings tie at priority 9.0 (fire, mold, roofing, water). Water and fire were kept to match August for comparability. Corona is the HQ city but has no service-area page (the homepage covers it), so the service-area slot stays on `/service-areas/riverside-ca/`.
- **Custom issue IDs.** `rankai_meta_description_length` and `rankai_word_count_below_target` are Rank AI manual checks, deliberately namespaced. `frame` is the DataForSEO on-page check ID (the Riverside page embeds a map iframe, low severity, no action). All other IDs are real Lighthouse audit IDs.
- **Minor schema note.** The `Organization`/`ImageObject` `logo` URL is relative (`/images/logo.png`). Google recommends an absolute URL for logos. Low priority; fix it in the same pass as the logo WebP swap.
- **Word counts on service landings dropped** (water 1782 to 1617, fire 1959 to 1792) but remain well above the 1100 target. Content changes are out of scope for this audit (System 4).
