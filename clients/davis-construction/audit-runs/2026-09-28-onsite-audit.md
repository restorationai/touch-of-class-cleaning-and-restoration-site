# Onsite Audit - Davis Construction Contractors - 2026-09-28

**Live origin audited:** https://davisconstructioncontractors.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-08-26
**Form factor:** desktop only (DataForSEO Lighthouse wrapper does not expose mobile; expect mobile performance 10-20 points lower)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 97 | -2 |
| Accessibility | 100 | 0 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: {green: 6, amber: 0, red: 0, error: 0}

All six pages stay green, and no single category score dropped by 5 or more points. The one real movement: LCP got slower on the three pages whose hero image is served from `images.davisconstructioncontractors.com` (/services/, /service-areas/huntsville-al/, /contact/). Two of them crossed the 200ms regression threshold. The cause is the same on all three and is covered under recommended actions.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | green | 98 | 100 | 100 | 100 | 1.0s | 0.01 |
| /services/ | services-hub | green | 93 | 100 | 100 | 100 | 1.7s | 0.00 |
| /services/home-remodeling/ | service-landing | green | 99 | 100 | 100 | 100 | 0.9s | 0.01 |
| /services/roofing/ | service-landing | green | 99 | 100 | 100 | 100 | 1.0s | 0.02 |
| /service-areas/huntsville-al/ | service-area | green | 96 | 100 | 100 | 100 | 1.4s | 0.01 |
| /contact/ | contact | green | 96 | 100 | 100 | 100 | 1.3s | 0.01 |

TBT is 0ms on every page. INP was not returned by the lab run (null).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `cache-insight` | 6 | medium | `images.davisconstructioncontractors.com/brand/hero.webp` (238 KB) is served with `cache-control: max-age=14400` (4 hours), which alone accounts for 162 KB of the flagged savings. Set `public, max-age=31536000, immutable` on the R2 custom domain (Cloudflare Cache Rule or R2 object metadata). Same-origin `/images/*` is also on `max-age=14400, must-revalidate`; raise it to 30 days or more in `public/_headers`. The remaining flagged items are third-party (clarity.ms, 1 day; Cloudflare email-decode) and cannot be changed. |
| `image-delivery-insight` | 6 | medium | The sitewide page-hero `<img>` on /services/, /service-areas/*, /contact/ loads the full 1376w `brand/hero.webp` with no `srcset`/`sizes`, even though 480w/768w/1200w variants already exist on R2 (the homepage uses them). Add the same `srcset` to the page-hero component. Also: `/images/logo.webp` is 25 KB but renders at 36x36 declared size, so export a 2x (about 128px wide) version (saves about 23 KB on every page). Home `/images/team.webp` is 269 KB with 192 KB savings, so add `srcset` variants. `/images/services/roofing.webp` wastes 126 KB on /services/roofing/. |
| `lcp-discovery-insight` | 5 | medium | Every page except the homepage has an LCP image with `loading="eager"` but no `fetchpriority="high"`. Add `fetchpriority="high"` to the hero `<img>` in the page-hero and service-landing hero components (the homepage already does this and passes). |
| `unused-javascript` | 6 | low | 69 KB of the 159 KB `googletagmanager.com/gtag/js?id=G-BRL1Q2KTGV` payload goes unused. Load gtag with a deferred or on-interaction strategy (for example Partytown, or inject after `load`) instead of in the head. Worth up to 150ms LCP on /contact/. |
| `render-blocking-insight` | 6 | low | Single 9 KB stylesheet `/_astro/_slug_.*.css`. Only 50ms of savings on the two service landings. Low priority; inline it via Astro `build.inlineStylesheets: "always"` if convenient. |
| `network-dependency-tree-insight` | 6 | low | Informational. Resolves as a side effect of the fetchpriority and gtag changes above. |
| `has_micromarkup_errors` | 5 | low | DataForSEO's validator flags every FAQPage `Question` as missing `answerCount`. It is not a Google rich-result requirement, but the fix is one line: add `"answerCount": 1` to each Question in the FAQ schema component. |
| `low_content_rate` | 3 | low | Text-to-HTML ratio is below the DataForSEO threshold on /, /services/, /contact/. Informational; no action beyond the word-count items below. |
| `content_below_target_word_count` | 2 | low | / is 1174 words (target 1200); /services/ is 757 words (target 800). |

## Money page alerts

None. All money pages (home, services hub, both service landings, contact) are green.

## Regressions vs prior audit

**Verdict transitions:** none. All 6 URLs green in both runs.

**Score regressions (5+ point drop):** none. Largest drops: /service-areas/huntsville-al/ performance 99 to 96, /contact/ 99 to 96, /services/ 95 to 93.

**Core Web Vitals regressions:**
- `/service-areas/huntsville-al/`: LCP 929ms to 1398ms (+469ms). Lighthouse breakdown puts 623ms in resource load duration for `brand/hero.webp` (238 KB, no srcset, no fetchpriority, 4-hour cache, `cf-cache-status: MISS` at audit time).
- `/contact/`: LCP 1009ms to 1301ms (+292ms). Same hero image; 345ms resource load duration.
- `/services/` did not cross the threshold (+145ms) but is the slowest page at 1.7s. It has the same image, with 1098ms resource load duration.

**New issues this month:**
- `/`: `content_below_target_word_count` (1174 words vs 1200 target; was at or above 1200 in August)
- `/services/`, `/contact/`: `low_content_rate`
- `/services/`, `/services/home-remodeling/`, `/services/roofing/`, `/service-areas/huntsville-al/`, `/contact/`: `has_micromarkup_errors`. This check was not recorded in prior runs, so it may have been present before and only now surfaced. The schema itself is unchanged in shape and parses cleanly.

**Issues resolved since last audit:** (positive, keep doing this)
- `/`, `/services/`, `/contact/`: `forced-reflow-insight` no longer flagged (score 1.0 on all three)
- `/`: CLS improved from 0.023 to 0.005

## Recommended next actions (priority order)

1. **(money pages + template, high impact)** Fix the page-hero image in the shared hero component used by /services/, /service-areas/*, /contact/: add the existing `hero-480w/768w/1200w.webp` variants as `srcset` with `sizes="100vw"`, and add `fetchpriority="high"`. This addresses the two LCP regressions and the slowest page (/services/ at 1.7s). Lighthouse estimates 100-150ms LCP savings per page from image delivery alone.
2. **(template)** Set long-lived cache headers on `images.davisconstructioncontractors.com` (currently `max-age=14400`). Use a Cloudflare Cache Rule on that hostname: Edge TTL 1 year, Browser TTL 1 year. Also raise `/images/*` in `public/_headers` from `max-age=14400, must-revalidate` to `public, max-age=2592000`. Up to 150ms LCP savings on repeat visits for /services/ and /service-areas/huntsville-al/.
3. **(template)** Add `fetchpriority="high"` to the LCP image on the service-landing template (/services/home-remodeling/, /services/roofing/). Also swap `/images/services/roofing.webp` (251 KB) for a srcset with the existing `-480w` variant pattern.
4. **(template)** Defer the GA4 gtag script (`G-BRL1Q2KTGV`) until after `load`, or move it to Partytown. 69 KB of unused JS on every page; up to 150ms LCP on /contact/.
5. **(per-page, low)** Add `"answerCount": 1` to each FAQ `Question` node in the schema component. Add 30-50 words to the /services/ hub intro to clear the 800-word target (currently 757).

## Notes / caveats

- **Origin choice:** the client record has no `apex_cutover.completed_at` field, but `cut_over_at` is 2026-05-28 and `deploy_url` is the apex, so the apex was audited, the same as in the prior three runs. The apex serves no `x-robots-tag: noindex`, so SEO counts toward the verdict.
- **Desktop only:** the DataForSEO Lighthouse run uses formFactor=desktop, no CPU throttling, 10 Mbps. These are not mobile-first scores.
- **Transport:** the dataforseo MCP server only exposes a generic `api_request`. Lighthouse and instant_pages were called over REST at `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` with the same account, and responses were piped to disk.
- **Service-area slot:** `/service-areas/madison-al/` still 301s to the homepage (a deliberate consolidation of the home city), so `/service-areas/huntsville-al/`, the first service-area in url-plan, was audited. This is the same substitution as August.
- **Schema:** instant_pages reports `has_micromarkup=false` because it does not count JSON-LD. The served HTML carries 3-5 valid JSON-LD blocks per page with zero parse errors, so missing-schema was not flagged. `has_micromarkup_errors` was run down with a one-page `/v3/on_page/microdata` validation of /services/roofing/. The only error-level result is a missing `answerCount` on FAQ Questions. That is not a Google FAQPage requirement, so it was recorded at low severity rather than the rubric's medium to avoid a false amber. The same validation surfaced two schema-hygiene items worth a look in a future build pass. First, LocalBusiness `sameAs` points to the site's own `/about/` page rather than external profiles (GBP, Facebook, BBB). Second, `image`/`logo` use relative URLs (`/images/logo.webp`); absolute URLs are safer.
- **Dedup:** `has_render_blocking_resources` from instant_pages duplicates the Lighthouse `render-blocking-insight` finding and was not double-counted. `no_image_title` (title attribute on images) is not an SEO factor and was not recorded. `frame` on /service-areas/huntsville-al/ is the embedded map iframe and is expected.
- **Comparison method:** failing thresholds match the prior run (insights below 0.9, weighted performance metrics below 1). Audits that last month's template list showed failing on 5-6 of 6 URLs were treated as present on every prior URL, so they were not reported as new just because they fell outside last month's top 5. Lab LCP varies by roughly 100-200ms run to run. The two LCP regressions share a clear, verified cause (hero image delivery and cache headers), so they are treated as real.
- **Cost:** 6 Lighthouse ($0.030) + 6 instant_pages ($0.011) + 1 microdata crawl ($0.00015), about $0.04 total. No `full_data` calls were needed.
