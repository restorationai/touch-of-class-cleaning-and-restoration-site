# Onsite Audit, Davis Construction Contractors, 2026-09-28

**Live origin audited:** https://davisconstructioncontractors.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-08-26
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 99 | 0 |
| Accessibility | 100 | 0 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Exact performance mean is 98.5, the same as last month, rounded to 99 for the table.

Pages by verdict: green 6, amber 0, red 0, error 0.

Every page scored 98 or higher in every category. There are no high- or medium-severity on-page issues, no broken internal or external links, no broken resources, no mixed content, and no title, meta description or H1 problems. Every page has a self-referencing canonical, valid JSON-LD, and 100 percent image alt coverage.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | Words |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 98 | 100 | 100 | 100 | 1.05s | 0.005 | 1174 |
| `/services/` | services-hub | green | 98 | 100 | 100 | 100 | 1.06s | 0.004 | 757 |
| `/services/home-remodeling/` | service-landing | green | 99 | 100 | 100 | 100 | 0.92s | 0.006 | 1647 |
| `/services/roofing/` | service-landing | green | 98 | 100 | 100 | 100 | 1.06s | 0.021 | 1538 |
| `/service-areas/huntsville-al/` | service-area | green | 99 | 100 | 100 | 100 | 1.01s | 0.006 | 1347 |
| `/contact/` | contact | green | 99 | 100 | 100 | 100 | 0.96s | 0.004 | 688 |

Total blocking time is 0ms on all six pages. Lighthouse lab mode did not report INP, so it is recorded as null rather than estimated.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `lcp-discovery-insight` | 5 | medium | Add `fetchpriority="high"` to the hero `<img>` in the shared non-home hero partial. The homepage hero already has it and passes. |
| `cache-insight` | 6 | medium | Raise `Cache-Control` on `images.davisconstructioncontractors.com` from `max-age=14400` to `max-age=31536000, immutable`. That is 162 KiB per page on `brand/hero.webp`. |
| `image-delivery-insight` | 6 | medium | Serve the R2 hero through its existing `srcset` variants, and resize `/images/logo.webp`, `/images/team.webp` and `/images/services/roofing.webp`. |
| `unused-javascript` | 6 | low | 66 to 69 KiB unused per page, all of it the Google Tag Manager `gtag/js` bundle. Third-party code with limited control, so leave it. |
| `render-blocking-insight` | 6 | low | `/_astro/_slug_.BgI2evEd.css` (about 9 KiB, about 50ms). You could inline it as critical CSS, but the gain is marginal. |
| `network-dependency-tree-insight` | 6 | low | Diagnostic only. It reports no measurable savings. |
| `low_content_rate` | 3 | low | Text-to-HTML ratio on `/`, `/services/`, `/contact/`. The cause is markup weight, not thin copy. No action needed on its own. |
| `content_below_target_word_count` | 2 | low | `/` at 1174 of 1200 words and `/services/` at 757 of 800. |
| `forced-reflow-insight` | 2 | low | Diagnostic only. It reports 0ms savings. |

### Last month's top fix has not shipped yet

The shared hero partial on `/services/`, `/service-areas/huntsville-al/` and `/contact/` still renders:

```
<img src="https://images.davisconstructioncontractors.com/brand/hero.webp"
     class="w-full h-full object-cover" loading="eager">
```

It has no `fetchpriority` and no `srcset`, so every viewport downloads the 232 KiB original (1376w). The resized variants **already exist on R2** and return 200: `hero-480w.webp` (30 KiB), `hero-768w.webp` (72 KiB) and `hero-1200w.webp` (164 KiB). The service cards further down `/services/` already use them with a correct `srcset`. The hero partial just needs the same `srcset`/`sizes`, plus `fetchpriority="high"`. On `/contact/` Lighthouse puts the waste at 173 KiB, on `/services/` at 146 KiB, and on `/service-areas/huntsville-al/` at 121 KiB.

The service-landing template (`/services/roofing/`) has the same pattern with a local image: `<img src="/images/services/roofing.webp" ... loading="eager">` is 245 KiB, and Lighthouse flags 123 KiB of it as waste.

## Money page alerts

None. All four money-page archetypes (home, services-hub, service-landing, contact) came back green.

## Regressions vs prior audit

**Verdict transitions:** none. All six pages stayed green.

**Score regressions:** none. No category dropped 5 or more points on any page. The largest drop was 1 point, on `/`, `/services/home-remodeling/` and `/services/roofing/`, which is normal run-to-run noise.

**Core Web Vitals regressions:** none. The home LCP rose 109ms (945ms to 1054ms), below the 200ms threshold. The roofing CLS rose 0.003, below the 0.02 threshold.

**Improvement:** last month's only regression has cleared. `/services/` LCP fell from 1563ms to 1056ms (-507ms), and performance recovered from 95 to 98. The hero markup and cache TTL are unchanged (see above), so this looks like a warm edge cache on this run, not a fix. It could recur until the cache TTL and `fetchpriority` changes ship.

**New issues this month:**

- `/`: `content_below_target_word_count`. The homepage fell from 1213 to 1174 words, 26 below its 1200 target. Copy was trimmed at some point in the last month.
- `/services/` and `/contact/`: `low_content_rate`, from markup weight. Word counts are unchanged from last month.
- `/service-areas/huntsville-al/`: `forced-reflow-insight`, which reports 0ms savings.
- `lcp-discovery-insight` on `/services/`, `/services/home-remodeling/`, `/services/roofing/`, `/contact/`, and `unused-javascript` / `network-dependency-tree-insight` on several pages. These are **not** genuinely new. All of them failed on the same pages last month but fell outside the stored top-5 list. They show up now because `largest-contentful-paint` stopped failing and freed a slot.

**Issues resolved since last audit** (keep doing this):

- `largest-contentful-paint` now passes on 6 of 6 pages. Last month it failed on 5 of them. Every page's LCP is now under 1.1s desktop.
- `/services/`: `interactive` (Time to Interactive) and `forced-reflow-insight` no longer fail.
- `/contact/`: `forced-reflow-insight` no longer fails.

## Recommended next actions (priority order)

1. **(template, high impact)** In the shared non-home hero partial, add `fetchpriority="high"` plus `srcset="https://images.davisconstructioncontractors.com/brand/hero-480w.webp 480w, .../hero-768w.webp 768w, .../hero-1200w.webp 1200w, .../hero.webp 1376w"` and `sizes="100vw"` to the hero `<img>`. The variants are already uploaded. This clears `lcp-discovery-insight` on 5 of 6 pages and cuts 121 to 173 KiB per money page. It was also last month's number one item.

2. **(template, high impact)** Add a Cloudflare cache rule on `images.davisconstructioncontractors.com` that sets `Cache-Control: public, max-age=31536000, immutable` (currently `max-age=14400`, and `cf-cache-status: MISS` on `hero.webp` again this run). Apply the same rule to the content-hashed `/_astro/*` paths, which are currently `max-age=14400, must-revalidate`. This removes the cold-cache origin fetch behind last month's `/services/` LCP spike.

3. **(template, medium)** Give the service-landing hero the same treatment. Generate 480/768/1200w variants of `/images/services/*.webp` (for example, `roofing.webp` is 245 KiB) and add `srcset` and `fetchpriority="high"`. Also resize `/images/logo.webp` (25 KiB, 23 KiB wasted on every page), which renders at logo size (56 to 64px tall) in the header and footer. And resize `/images/team.webp` on the homepage (263 KiB, 188 KiB wasted).

4. **(per-page, low)** Restore about 30 words to the homepage (1174 of 1200 target) and add about 45 words to `/services/` (757 of 800). A short intro paragraph on each is enough. These are trims, not rewrites.

5. **(hygiene)** Backfill `apex_cutover.completed_at` in `clients/davis-construction.json`. The apex has served the Rank AI build since at least the 2026-08-26 audit, but the record still says it has not cut over. Anything keyed off that field, including this audit's origin selection, will otherwise fall back to staging.

## Notes / caveats

- **Desktop only.** The DataForSEO Lighthouse wrapper runs `formFactor=desktop` with `cpuSlowdownMultiplier=1` and `throughputKbps=10240`. Mobile performance would likely land 10 to 20 points lower, and mobile-specific issues are not surfaced here. The green verdict is a desktop verdict.
- **Apex audited without a cutover record.** `apex_cutover.completed_at` is not set, but the apex returns 200 with the Rank AI Astro build and no `x-robots-tag: noindex`. It was audited to stay like-for-like with the 2026-08-26 run, and SEO counts toward the verdict.
- **Service-area slot.** `/service-areas/madison-al/` still 301s to the homepage, so the service-area slot stays on `/service-areas/huntsville-al/`, as last month.
- **Schema detection.** `instant_pages` does not count JSON-LD in `has_micromarkup`. JSON-LD was re-verified in the served HTML: 3 to 5 blocks per page (Organization, WebSite, LocalBusiness, Service, FAQPage, BreadcrumbList), with zero parse errors.
- **Checks not flagged.** `has_render_blocking_resources` duplicates `render-blocking-insight`. `no_image_title` refers to title attributes, which are not an SEO requirement, and alt coverage is 100 percent. `frame` on Huntsville is the intended Google Maps embed.
- **Tool surface.** The MCP server only exposes a generic `api_request`, so the two endpoints were called over REST with the `DATAFORSEO_*` credentials and the responses were parsed from disk. Cost was about $0.03 for 12 calls. All 12 returned successfully, and no URL errored or needed a re-run.
- **Issue diffing.** `new_issues` compares stored top-5 lists. `resolved_issues` checks against the current full failing set, so an issue only counts as resolved if it genuinely passes. See "New issues" above for which entries are top-5 churn.
