# Onsite Audit, Davis Construction Contractors, 2026-09-28

**Live origin audited:** https://davisconstructioncontractors.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 97 | -1.7 |
| Accessibility | 100 | 0 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Exact performance mean is 96.83, down from 98.5. That is under the 3-point site-level regression threshold.

Pages by verdict: green 1, amber 5, red 0, error 0.

Every Lighthouse category on every page is 93 or higher. The amber verdicts come from one on-page finding, not from scores. DataForSEO now flags `has_micromarkup_errors` (structured data validation errors) on the 5 pages that carry a BreadcrumbList. The rubric rates schema validation warnings as medium, and any medium on-page issue makes a page amber. The fix is a one-line template change (action 1 below). There are no broken internal or external links, no 4xx or 5xx responses, no mixed content, and no duplicate titles or meta descriptions. Every page has a self-referencing canonical, one H1, and 100 percent image alt coverage.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | Words |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 100 | 100 | 100 | 1.00s | 0.005 | 1174 |
| `/services/` | services-hub | amber | 93 | 100 | 100 | 100 | 1.71s | 0.004 | 757 |
| `/services/home-remodeling/` | service-landing | amber | 97 | 100 | 100 | 100 | 1.31s | 0.004 | 1647 |
| `/services/roofing/` | service-landing | amber | 95 | 100 | 100 | 100 | 1.39s | 0.021 | 1538 |
| `/service-areas/huntsville-al/` | service-area | amber | 99 | 100 | 100 | 100 | 0.98s | 0.005 | 1347 |
| `/contact/` | contact | amber | 98 | 100 | 100 | 100 | 1.10s | 0.007 | 688 |

Total blocking time is 0 to 4ms on all six pages. Lighthouse does not report INP in lab mode, so it is recorded as null.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `has_micromarkup_errors` | 5 | medium | Add an `item` URL to the last `ListItem` in the BreadcrumbList JSON-LD. See action 1. |
| `lcp-discovery-insight` | 5 | medium | Add `fetchpriority="high"` to the hero `<img>` in the shared non-home hero partial. Still open from last month. See action 2. |
| `cache-insight` | 5 | medium | `images.davisconstructioncontractors.com` and `/images/*` still serve `max-age=14400` (4 hours). On `/services/`, `/service-areas/huntsville-al/` and `/contact/`, 162 KiB of the 238 KiB `brand/hero.webp` is wasted on repeat visits. It also fails on `/`, but falls outside the stored top 5 there. |
| `image-delivery-insight` | 5 | medium | `brand/hero.webp` (238 KiB) is oversized for its render box, as is `services/roofing.webp` (245 KiB, 146 KiB of reported savings). The 25 KiB `logo.webp` renders at 160x80 on every page. |
| `unused-javascript` | 5 | low | 69 KiB of the 159 KiB Google Tag Manager `gtag/js` bundle goes unused on every page. On the two service landings Lighthouse now charges it 160 to 190ms of LCP savings. |
| `forced-reflow-insight` | 4 | low | Diagnostic only, 0ms reported savings. |
| `largest-contentful-paint` | 3 | low | Downstream of the hero, cache and GTM items above. Not a separate fix. |
| `low_content_rate` | 3 | low | Low text-to-HTML ratio on `/`, `/services/`, `/contact/`. This is markup weight, not thin content. |
| `network-dependency-tree-insight` | 3 | low | Diagnostic only, no measurable savings. |
| `content_below_target_word_count` | 2 | low | `/` is 1174 words against a 1200 target. `/services/` is 757 against 800. |

Affected-URL counts for Lighthouse audits count only each page's stored top 5, so `cache-insight`, `image-delivery-insight` and `unused-javascript` actually fail on all 6 pages.

### The breadcrumb finding

Every page that has a BreadcrumbList ends it with a crumb that has no URL:

```
{"@type": "ListItem", "position": 2, "name": "Contact"}
```

The earlier crumbs all have `"item": "https://davisconstructioncontractors.com/..."`. Google accepts a last crumb with no `item`, but DataForSEO's validator does not. The flag is set on exactly the 5 pages that have a BreadcrumbList and not on `/`, which has none. Every other JSON-LD block (LocalBusiness, Organization, WebSite, Service, FAQPage) parses cleanly and has its expected properties. Setting `item` on the last crumb to the page's canonical URL is valid for Google too, so the change carries no risk.

## Money page alerts

- **`/services/`** (services-hub), verdict amber. Performance 93, LCP 1.71s, `has_micromarkup_errors`. Most of the LCP is image load time: 864ms of resource load for the 238 KiB R2 `brand/hero.webp`, which has no `fetchpriority` or `srcset` and a 4-hour cache TTL. This is the slowest page in the set for the second month running.
- **`/services/home-remodeling/`** (service-landing), verdict amber. Performance 97, LCP 1.31s, `has_micromarkup_errors`.
- **`/services/roofing/`** (service-landing), verdict amber. Performance 95, LCP 1.39s, `has_micromarkup_errors`. The hero image `services/roofing.webp` is 245 KiB, with 146 KiB of image-delivery savings.
- **`/contact/`** (contact), verdict amber. Performance 98, LCP 1.10s, `has_micromarkup_errors`. It has the largest combined savings in the set: 150ms each from `cache-insight` and `image-delivery-insight`, plus 140ms from `unused-javascript`.

All four would be green again once action 1 is shipped. Scores alone keep every one of them above 90.

## Regressions vs prior audit

The audit set matches last month's six URLs exactly, so every page is directly comparable.

**Verdict transitions:**

- `/services/` went green to amber. The only cause is the new `has_micromarkup_errors` flag. Performance moved 95 to 93.
- `/services/home-remodeling/` went green to amber. Same cause. Performance moved 100 to 97.
- `/services/roofing/` went green to amber. Same cause. Performance moved 99 to 95.
- `/service-areas/huntsville-al/` went green to amber. Same cause. Performance was unchanged at 99.
- `/contact/` went green to amber. Same cause. Performance moved 99 to 98.

The breadcrumb blocks have the same types as last month, and last month's run did not record this check. So the transition may come from a DataForSEO validator change rather than a site change. The same flag appears on the same template shape for several other Rank AI clients this cycle. Either way, the markup fix is correct and cheap.

**Score regressions:** none. No Lighthouse category dropped 5 or more points on any page.

**Core Web Vitals regressions:**

- `/services/home-remodeling/`: LCP rose from 770ms to 1312ms, up 542ms.
- `/services/roofing/`: LCP rose from 1001ms to 1394ms, up 393ms.

Both are Lighthouse's simulated LCP. The observed trace on these pages is much faster: on `/services/home-remodeling/`, TTFB 164ms, load delay 7ms, load duration 149ms and render delay 220ms add up to about 540ms. Most of the simulated increase comes from the GTM `gtag/js` bundle, which Lighthouse now puts on the LCP critical path on these two pages (160ms and 190ms of `unused-javascript` LCP savings, against 10 to 50ms elsewhere). The hero image on both has no `fetchpriority`, so the browser gives it no priority over that script. Actions 2 and 4 address this directly. No CLS or TBT regressions.

**New issues this month:**

- `/services/`, `/services/home-remodeling/`, `/services/roofing/`, `/service-areas/huntsville-al/`, `/contact/`: `has_micromarkup_errors`, the terminal BreadcrumbList crumb described above.
- `/`: `content_below_target_word_count`. The homepage is 1174 words, down from 1213 last month and now 26 under its 1200 target. Last month this issue was marked resolved, so something trimmed homepage copy since 2026-08-26.
- `/services/` and `/contact/`: `low_content_rate`, low text-to-HTML ratio. Word counts are unchanged, so this is markup weight. Low priority.
- `/services/roofing/` and `/service-areas/huntsville-al/`: `forced-reflow-insight`, 0ms reported savings, diagnostic only.

**Issues resolved since last audit** (positive, keep doing this):

- `/` and `/service-areas/huntsville-al/`: `largest-contentful-paint` now passes (0.98 to 1.00s).
- `/services/`: `interactive` (Time to Interactive) and `forced-reflow-insight` no longer fail.

**Still open from last month:** the three template recommendations from the 2026-08-26 audit have not shipped. The non-home hero partial still has no `fetchpriority="high"` and no `srcset`. The image domains still serve `max-age=14400`. `brand/hero.webp` is still the 238 KiB original.

## Recommended next actions (priority order)

1. **(money pages, template, 5 URLs)** In the BreadcrumbList JSON-LD generator, set `"item"` on the final `ListItem` to the current page's canonical URL. For example, on `/contact/` use `{"@type": "ListItem", "position": 2, "name": "Contact", "item": "https://davisconstructioncontractors.com/contact/"}`. This clears `has_micromarkup_errors` on `/services/`, both service landings, `/contact/` and `/service-areas/huntsville-al/`. With no other medium issues on those pages, all 5 return to green and the site verdict returns to green.

2. **(money pages, template, 5 URLs)** In the shared non-home hero partial, add `fetchpriority="high"` to the hero `<img>`. Also give it the same `srcset`/`sizes` treatment the homepage hero already has (`hero-bg-480w/768w/1200w.webp`, `sizes="100vw"`). Include `services/*.webp` and `brand/hero.webp`, and generate 480w/768w/1200w variants for `services/roofing.webp` (245 KiB) and `services/home-remodeling.webp` (93 KiB). This clears `lcp-discovery-insight` on 5 pages and is the most direct fix for the `/services/` LCP (1.71s) and both landing-page LCP regressions.

3. **(template, 6 URLs)** Add a Cloudflare cache rule that raises `Cache-Control` on `images.davisconstructioncontractors.com/*` and `davisconstructioncontractors.com/images/*` from `max-age=14400` to `max-age=2592000` (30 days). These filenames are not content-hashed, so use 30 days rather than `immutable`, and rename files when you replace them. This is worth 150ms on `/services/` and `/contact/`, plus 162 KiB of repeat-visit transfer on `brand/hero.webp`.

4. **(template, 6 URLs)** Load Google Tag Manager `gtag/js` (`G-BRL1Q2KTGV`) after first paint. Inject the script from a `requestIdleCallback` or `load` event handler instead of a `<head>` async tag, or move it to Partytown. 69 KiB of its 159 KiB goes unused on every page, and on the two service landings Lighthouse charges it 160 to 190ms of LCP.

5. **(per-page, low)** Add about 45 words to `/services/` (757 against an 800 target). Restore about 30 words on `/` (1174 against 1200, down from 1213 last month). Check the homepage's recent content changes to find what was trimmed.

## Notes / caveats

- **Desktop only.** The DataForSEO Lighthouse endpoint runs `formFactor=desktop` with `cpuSlowdownMultiplier=1` and `throughputKbps=10240`, and the MCP wrapper exposes no form-factor setting. Mobile performance would likely land 10 to 20 points lower, and mobile-specific issues are not surfaced. Treat these verdicts as desktop verdicts.
- **Live origin choice.** The client record has no `apex_cutover.completed_at` key but does have `cut_over_at: 2026-05-28T18:48:09Z` and an apex `deploy_url`. The apex was audited, as in the four prior runs. The apex sends no `x-robots-tag: noindex`, so SEO counts toward the verdict.
- **Service-area slot.** `/service-areas/madison-al/` still returns 301 to the homepage (re-checked this run), so the slot stays on `/service-areas/huntsville-al/`, as in the 2026-08-26 run.
- **Schema detection false negative.** `instant_pages` reports `has_micromarkup=false` on all six pages, but each page's served HTML has 3 to 5 JSON-LD blocks that parse cleanly. That check ignores JSON-LD, so missing schema was not flagged.
- **MCP tool surface.** The dataforseo MCP server exposes only a generic `api_request` tool. Lighthouse payloads run 0.75 to 1.05 MB, so this run called `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` over REST with the `DATAFORSEO_*` credentials and saved the responses to disk. Total API cost was about $0.04 for 12 calls.
- **Issue diffing.** `lighthouse_issues` stores the top 5 failing audits per URL. New issues compare the current top 5 against last month's stored set. An issue counts as resolved only if it is missing from the current full failing set. Issues that last month reported as template-wide on 5 or more of 6 URLs are not reported as new just because they rotated into a page's top 5.
- **Not recorded as issues:** `no_image_title` (alt text coverage is 100 percent, and a title attribute has no SEO or accessibility value when alt text is present). `frame` on `/service-areas/huntsville-al/` is the embedded Google Map. `has_render_blocking_resources` is the same finding as Lighthouse `render-blocking-insight` (the 9 KiB `/_astro/_slug_.BgI2evEd.css`, 40 to 50ms).
- All 12 API calls returned status 20000. No URL errored, timed out, or needed a re-run.
