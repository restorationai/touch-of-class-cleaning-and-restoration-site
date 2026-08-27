# Onsite Audit, Davis Construction Contractors, 2026-08-26

**Live origin audited:** https://davisconstructioncontractors.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-07-15
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 99 | 0 |
| Accessibility | 100 | +1 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Exact performance mean is 98.5, rounded to 99 for the table. Prior mean was 98.67.

Pages by verdict: green 6, amber 0, red 0, error 0.

No page dropped below 95 in any category. There are no high-severity on-page issues, no broken internal or external links, no 4xx or 5xx responses, no mixed content, no duplicate titles or meta descriptions, and every page has a self-referencing canonical plus valid JSON-LD.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | Words |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 100 | 100 | 100 | 0.95s | 0.023 | 1213 |
| `/services/` | services-hub | green | 95 | 100 | 100 | 100 | 1.56s | 0.003 | 767 |
| `/services/home-remodeling/` | service-landing | green | 100 | 100 | 100 | 100 | 0.77s | 0.004 | 1658 |
| `/services/roofing/` | service-landing | green | 99 | 100 | 100 | 100 | 1.00s | 0.018 | 1549 |
| `/service-areas/huntsville-al/` | service-area | green | 99 | 100 | 100 | 100 | 0.93s | 0.004 | 1337 |
| `/contact/` | contact | green | 99 | 100 | 100 | 100 | 1.01s | 0.006 | 688 |

Total blocking time is 0ms on all six pages. INP was not reported by Lighthouse in lab mode and is recorded as null rather than estimated.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `lcp-discovery-insight` | 5 | medium | Add `fetchpriority="high"` and a `srcset` to the hero `<img>` in the non-home templates. The homepage hero already has both and passes this audit; the other five templates have neither. |
| `cache-insight` | 6 | medium | Raise `Cache-Control` from `max-age=14400` (4 hours) to `max-age=31536000, immutable` on the R2 image domain and on content-hashed `/_astro/` assets. Worth 475 KiB on `hero.webp` alone. |
| `image-delivery-insight` | 6 | medium | Resize the oversized source images listed below. 430 KiB of the waste is `hero.webp`, 138 KiB is the footer `logo.webp`. |
| `unused-javascript` | 6 | low | 401 KiB total, effectively all of it the Google Tag Manager `gtag/js` bundle (68 KiB unused per page, 45 percent of the file). Third-party, limited control. Leave unless GTM containers can be trimmed. |
| `render-blocking-insight` | 6 | low | `/_astro/_slug_.BahPBSU8.css` is 8.4 KiB and costs about 57ms. Small enough to inline as critical CSS if you want the last point. |
| `largest-contentful-paint` | 6 | low | Downstream of the three items above, not a separate fix. |
| `network-dependency-tree-insight` | 6 | low | Diagnostic only, no measurable savings reported on these pages. |
| `forced-reflow-insight` | 3 | low | Diagnostic only, 0ms reported savings. |

### The one fix that matters most

The homepage hero is marked up like this and scores a clean pass:

```
<img src="/images/hero-bg.webp"
     srcset="/images/hero-bg-480w.webp 480w, /images/hero-bg-768w.webp 768w, ..."
     fetchpriority="high" loading="eager">
```

The hero on `/services/`, `/services/home-remodeling/`, `/services/roofing/`, `/service-areas/huntsville-al/` and `/contact/` looks like this instead:

```
<img src="https://images.davisconstructioncontractors.com/brand/hero.webp"
     class="w-full h-full object-cover" loading="eager">
```

No `fetchpriority`, no `srcset`, and on three of those templates it points at the unresized 238 KiB R2 original. The homepage hero component got the optimization treatment during a previous pass and the shared hero partial used by the other templates did not. One change to that partial lifts five of the six audited pages.

## Money page alerts

None. All four money page archetypes (home, services-hub, service-landing, contact) came back green.

## Regressions vs prior audit

**Verdict transitions:** none. All six pages were green last month and are green this month.

**Score regressions:** none. No Lighthouse category dropped by 5 or more points on any page.

**Core Web Vitals regressions:**

- `/services/`: LCP rose from 1095ms to 1563ms, a 468ms increase, crossing the 200ms regression threshold. Performance also eased from 98 to 95, which is inside normal run-to-run noise on its own, but the LCP move is not. The LCP element is the R2-hosted `hero.webp`, eagerly loaded and discoverable in the initial document but missing `fetchpriority="high"`. The 4-hour cache TTL on that image means Cloudflare frequently serves it from a cold cache. A `cf-cache-status: MISS` was observed on `hero.webp` during this run. The cache TTL fix and the `fetchpriority` fix both target this directly. This is the only measured regression in the run.

**New issues this month:**

- `/`: `low_content_rate`, low text-to-HTML ratio. The page has 1213 words, so this is markup weight rather than thin content. Low priority.
- `/services/`: `interactive`, Time to Interactive scored 0.99. Effectively noise at that score.
- `/services/roofing/`: `render-blocking-insight`, the 8.4 KiB Astro stylesheet, about 50ms.
- `/contact/`: `forced-reflow-insight`, 0ms reported savings, diagnostic only.

**Issues resolved since last audit** (positive, keep doing this):

- `/contact/`: `color-contrast` is no longer flagged. Accessibility went from 96 to 100, which is the entire site-level accessibility gain this month.
- `/`: `content_below_target_word_count` is resolved. The homepage is now 1213 words against a 1200 target.

## Recommended next actions (priority order)

1. **(template, high impact)** Add `fetchpriority="high"` to the hero `<img>` in the shared non-home hero partial, and give it the same `srcset` treatment the homepage hero already has. This is the single change that addresses `lcp-discovery-insight` across 5 of 6 pages and is the most direct fix for the `/services/` LCP regression.

2. **(template, high impact)** Change `Cache-Control` from `max-age=14400` to `max-age=31536000, immutable` for `images.davisconstructioncontractors.com` (Cloudflare cache rule on the R2 custom domain) and for `/_astro/` content-hashed assets. Those filenames already carry content hashes, so a 4-hour TTL buys nothing and costs a cold-cache origin fetch on the LCP image. Estimated 475 KiB of repeat-visit transfer on `hero.webp` and 60 KiB on the Clarity script.

3. **(template, medium)** Resize `brand/hero.webp`. It is 238 KiB and renders at 1350x392 or smaller depending on template. Also resize `/images/logo.webp`, which is 25 KiB rendering at 160x80 in the footer on all six pages. Combined reported savings are about 570 KiB.

4. **(per-page, low)** `/services/` is 767 words against its 800-word archetype target. It is the only page in the audited set under target and the shortfall is 33 words, so this is a trim-level fix rather than a rewrite.

5. **(hygiene)** Consider whether `/service-areas/madison-al/` should exist as a real page. It currently 301s to the homepage, which is a defensible consolidation given the homepage already targets "restoration services madison" and carries the Madison H1. Nothing is broken and nothing links to it. Flagging only so the redirect is a deliberate choice on record rather than an accident.

## Notes / caveats

- **Desktop only.** The DataForSEO Lighthouse wrapper runs `formFactor=desktop` with `cpuSlowdownMultiplier=1` and `throughputKbps=10240`, and does not expose a form-factor parameter. Mobile performance for this site would likely land 10 to 20 points lower and mobile-specific issues are not surfaced here. The green verdict is a desktop verdict.

- **Service-area slot changed this run.** The url-plan marks Madison as the primary service area, but `/service-areas/madison-al/` returns 301 to the homepage. It is absent from `sitemap-0.xml` and is not linked from `/service-areas/`, so the redirect is intentional consolidation, not a defect. The prior audit followed that redirect and therefore scored the homepage twice, once under the `home` slot and once under `service-area`. This run moved the slot to `/service-areas/huntsville-al/` so the archetype gets genuine coverage. As a result there is no month-over-month comparison for the service-area slot, and last month's reported `service-area` figures should be read as a duplicate of the homepage.

- **Schema detection false negative.** DataForSEO `instant_pages` reports `has_micromarkup=false` on all six pages. This was re-verified against the served HTML this run: every page carries 3 to 5 valid JSON-LD blocks (LocalBusiness, Organization, WebSite, Service, FAQPage, BreadcrumbList) with zero parse errors. `has_micromarkup` does not count JSON-LD. Missing schema was not flagged and should not be flagged on future runs on this basis alone.

- **MCP tool surface changed.** The dataforseo MCP server no longer exposes `on_page_lighthouse` or `on_page_instant_pages` as named tools; its surface collapsed to a generic `api_request`. Since Lighthouse payloads run 0.7 to 1.0 MB each, this run called the same two endpoints over REST using the `DATAFORSEO_*` environment credentials and piped responses to disk. Same account, same data source, same cost.

- **Issue diffing.** `lighthouse_issues` stores the top 5 failing audits per URL. To stop that cap from manufacturing false results, `new_issues` is computed from the current top 5 against the prior stored set, while `resolved_issues` is computed against the current full failing set. An issue only counts as resolved if it genuinely no longer fails.

- **Render-blocking deduplication.** `instant_pages` sets `has_render_blocking_resources=true` on all six pages. That is the same finding as the Lighthouse `render-blocking-insight` audit, so it was not recorded a second time as an on-page issue.

- All 12 API calls returned successfully. No URL errored, timed out, or needed a re-run.
