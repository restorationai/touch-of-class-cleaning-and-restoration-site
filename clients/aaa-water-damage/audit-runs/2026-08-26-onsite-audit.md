# Onsite Audit - AAA Water Damage Restoration & Carpet Care - 2026-08-26

**Live origin audited:** https://staging.rankai-aaa-water-damage.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client - no comparison data
**Lighthouse form factor:** desktop (`formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`)

## Environment caveat - SEO score is inconclusive this run

The apex domain `aaawaterdamagehawaii.com` does not resolve (no DNS A record) and the client record has `apex_cutover: null`, so this audit ran against the Cloudflare Pages preview.

`curl -sI` on the preview confirms the response header `x-robots-tag: noindex`. Cloudflare injects this on all `*.pages.dev` preview deployments. As a result the Lighthouse `is-crawlable` audit fails on all 6 URLs and drags the SEO category down to **69 on every page**.

**This is not a site defect.** SEO has been excluded from every verdict in this report. Verdicts are computed from Performance, Accessibility, and Best Practices only. The SEO score is recorded in the state file as measured, with status `inconclusive - staging noindex artifact, re-audit after apex cutover`.

Two related pre-cutover conditions, both expected and both intentionally **not** counted as issues:

- Canonical tags, schema `url`, and `og:url` on every page correctly point at `https://aaawaterdamagehawaii.com/...`, a domain that is not yet resolving.
- All 6 pages are absent from the sitemap check (`from_sitemap: false`) because `instant_pages` does not crawl a sitemap.

Because scores on a Pages preview and on apex behind the production CDN can differ, treat the numbers below as directionally correct rather than final.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.8 | n/a |
| Accessibility | 95.2 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 69.0 (inconclusive) | n/a |

Pages by verdict: green: 1, amber: 5, red: 0, error: 0

Every page returned HTTP 200. No broken internal links, no broken external links, no broken resources, no mixed content, no duplicate titles or descriptions, exactly one H1 per page, and full image alt coverage across all 6 URLs. DataForSEO `onpage_score` was 97.44 on all six. The amber rollup is driven by two template defects, not by page health.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 100 | 100 | 100 | 69* | 0.82s | 0.002 | 0ms |
| `/services/` | services-hub | amber | 100 | 95 | 100 | 69* | 0.82s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | amber | 100 | 95 | 100 | 69* | 0.45s | 0.031 | 0ms |
| `/services/mold-remediation/` | service-landing | amber | 100 | 95 | 100 | 69* | 0.80s | 0.003 | 0ms |
| `/service-areas/hawaii-kai-hi/` | service-area | amber | 100 | 95 | 100 | 69* | 0.82s | 0.004 | 0ms |
| `/contact/` | contact | amber | 99 | 91 | 100 | 69* | 0.83s | 0.004 | 0ms |

\* SEO excluded from verdict - staging noindex artifact. INP was null on all pages (not measured in a desktop lab run without a user flow).

Core Web Vitals are excellent across the board on desktop: every page passes LCP, CLS, and TBT thresholds with wide margin.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 5 | high | Breadcrumb links use `text-dark/50`, rendering `#878b95` on `#ffffff` at 12px - a 3.41:1 ratio against the 4.5:1 WCAG AA minimum. Darken the breadcrumb link token to roughly `text-dark/70` or darker in the shared breadcrumb component. Absent on `/` only because the homepage has no breadcrumb. |
| `unsized-images` | 6 | medium | `/images/logo.webp` has no explicit `width`/`height` in the header component. Add them so the browser can reserve space before decode. |
| `image-delivery-insight` | 6 | medium | Two distinct causes. (1) `/images/logo.webp` is a 360x360, 12.5KB file displayed at 64x64 (80x80 on `/contact/`) - 12KB wasted on every page. Ship a 128x128 variant or add `srcset`. (2) `/images/hero-bg.webp` is 175KB and under-compressed; it wastes 84KB on `/services/`, 59KB on the service-area page, and 118KB on `/contact/`. |
| `lcp-discovery-insight` | 5 | medium | The inner-page hero is a bare `<img src="/images/hero-bg.webp" loading="eager">` with no `srcset`, no `sizes`, and no `fetchpriority="high"`. The homepage hero already does this correctly. See the root-cause note below. |
| `has_micromarkup_errors` | 5 | medium | DataForSEO's structured-data validator reports errors on every page that carries `FAQPage` and `BreadcrumbList`. See the schema note below. |
| `render-blocking-insight` | 6 | low | `_astro/_slug_.<hash>.css` (8.8KB) blocks render for 55-68ms. Small enough to leave alone; inline critical CSS only if you are chasing the last few points. |
| `network-dependency-tree-insight` | 6 | low | Informational chain-depth warning on the same Astro CSS bundle. No action needed at current LCP. |
| `largest-contentful-paint` | 5 | low | Scores 0.97-0.98 at ~0.8s. Effectively noise; resolves with the hero fix below. |

### Root cause behind `lcp-discovery-insight` and most of `image-delivery-insight`

The homepage hero is built correctly:

```html
<img src="/images/hero-bg.webp"
     srcset="/images/hero-bg-480w.webp 480w, /images/hero-bg-768w.webp 768w, ..."
     sizes="100vw" loading="eager" fetchpriority="high" decoding="async">
```

The inner-page hero used by the services hub, both service landings, the service-area page, and `/contact/` is not:

```html
<img src="/images/hero-bg.webp" class="w-full h-full object-cover" loading="eager">
```

No `srcset`, no `sizes`, no `fetchpriority`. Those five pages each download the full 175KB desktop hero to fill a band only 247-392px tall, and Lighthouse flags the missing priority hint. The responsive variants (`hero-bg-480w.webp`, `hero-bg-768w.webp`) already exist and are already deployed - the inner-page template simply is not referencing them. Porting the homepage hero markup into the inner-page hero component fixes two template issues across five pages in one change.

### Note on `has_micromarkup_errors`

`has_micromarkup` is true and every JSON-LD block parses as valid JSON on all six pages. The error flag appears on exactly the five pages that emit `FAQPage` and `BreadcrumbList`; the homepage, which emits only `Organization`, `WebSite`, and `LocalBusiness`, is clean. Two structural defects were verified directly by parsing the served HTML:

- The terminal `BreadcrumbList` `ListItem` omits the `item` property (for example `{"@type":"ListItem","position":2,"name":"Contact"}`). Google tolerates this; stricter validators flag it as a missing required property.
- `LocalBusiness` emits `image` and `logo` as relative paths (`/images/logo.webp`). Schema.org expects absolute URLs. `LocalBusiness.address` also has no `streetAddress` - the client record's `nap.street` is an empty string.

Exact validator messages require the task-based `/v3/on_page/microdata` endpoint, which was not called this run (deferred on cost and runtime). Fixing the three defects above is worth doing regardless, then re-check the flag next month.

## Money page alerts

- **`/services/`** - amber. Performance 100, Accessibility 95, LCP 0.82s. Caused by the breadcrumb `color-contrast` failure and `has_micromarkup_errors`, plus the un-optimized inner-page hero wasting 84KB. Content is 755 words against an 800-word target.
- **`/services/water-damage-restoration/`** - amber. Performance 100, Accessibility 95, LCP 0.45s (fastest page audited). Same breadcrumb contrast and schema-validation causes. Its hero `water-damage-restoration.webp` is 173KB and under-compressed, wasting 56KB.
- **`/services/mold-remediation/`** - amber. Performance 100, Accessibility 95, LCP 0.80s. Same two template causes.
- **`/contact/`** - amber, and the highest-priority page on this list. Accessibility 91 is the lowest score in the set, driven by a real defect: the page renders `<a href="mailto:" class="font-bold text-white no-underline break-all">` - an **empty `mailto:` with no link text**. Lighthouse flags it as `link-name` (high) and `agent-accessibility-tree` (Agentic Browsing 67, the only sub-100 Agentic Browsing score in the set). Root cause is `"contact": null` in `clients/aaa-water-damage.json`, so the template has no email to render. On the primary conversion page this is a dead, unlabeled link that screen readers announce as an empty destination.

`/` is green and needs no intervention beyond the template fixes above.

## Regressions vs prior audit

First audit for this client - no comparison data. `clients/aaa-water-damage/onsite-audit.json` did not exist before this run, so regression detection was skipped. Next month's run will diff against the state file written today.

## Recommended next actions (priority order)

1. **(money page, high)** Fix the empty `mailto:` link on `/contact/`. Populate `contact.email` in `clients/aaa-water-damage.json` (currently `null`) and have the contact template skip the email block entirely when no address is set, rather than emitting `href="mailto:"`. This clears `link-name`, lifts `/contact/` accessibility from 91, and restores Agentic Browsing from 67 to 100.
2. **(template, high)** Darken the breadcrumb link color. `text-dark/50` resolves to `#878b95` on white at 12px, a 3.41:1 ratio that fails WCAG AA. Move to `text-dark/70` or darker in the shared breadcrumb component and re-check with the contrast checker. Fixes `color-contrast` on 5 of 6 audited pages and every other page using breadcrumbs.
3. **(template, high impact)** Port the homepage hero markup to the inner-page hero component - add `srcset` referencing the existing `hero-bg-480w.webp` / `hero-bg-768w.webp` variants, `sizes="100vw"`, `fetchpriority="high"`, and `decoding="async"`. Clears `lcp-discovery-insight` on 5 pages and saves 59-118KB per page. Separately, re-encode `hero-bg.webp` (175KB) and `services/water-damage-restoration.webp` (173KB) at a higher compression factor.
4. **(template, medium)** Add explicit `width="128" height="128"` to the header logo `<img>` and ship a 128x128 `logo.webp` variant. The current 360x360 file displays at 64x64 (80x80 on `/contact/`), wasting 12KB on every page site-wide and triggering `unsized-images` on all 6.
5. **(template, medium)** Repair the three schema defects: add `item` to the terminal `BreadcrumbList` `ListItem`, make `LocalBusiness.image` and `LocalBusiness.logo` absolute URLs, and populate `nap.street` so `LocalBusiness.address.streetAddress` is emitted. Then re-run to confirm `has_micromarkup_errors` clears.

## Notes / caveats

- **Amber does not mean "low urgency" on `/contact/`.** The verdict rubric flips a page to red only when a counted Lighthouse category drops below 70 or a high-severity on-page (DataForSEO) issue is present. `/contact/` scores Accessibility 91 and has no high-severity on-page issue, so it lands amber, yet it carries a genuine high-severity Lighthouse accessibility failure (`link-name`). Action 1 below is the single most important item in this report despite the amber label.
- **Re-audit required after apex cutover.** SEO findings are deferred, not resolved. Once `aaawaterdamagehawaii.com` resolves and `apex_cutover.completed_at` is set, re-run this audit against apex to get a real SEO score and CDN-accurate performance numbers.
- **Client record hygiene.** `clients/aaa-water-damage.json` has `status: "pending"` while `build_status: "pushed_main"` and `last_pushed_main_at: 2026-08-26`. The methodology's pre-flight expects `status: "active"`. The audit proceeded because the site is live and auditable, but the status field should be reconciled. `contact` and `zone` are also `null`, and `contact` being null is the direct cause of finding 1.
- **Desktop only.** The Lighthouse run was desktop. Mobile performance typically lands 10-20 points lower, and the un-optimized inner-page hero will hurt considerably more on a throttled mobile connection than the desktop scores suggest. No mobile-first claim is made from this data. The DataForSEO API does expose a `for_mobile` parameter; desktop was used this run to match the documented baseline and keep month-over-month comparisons valid.
- **URL selection.** No `audit-urls.txt` exists, so the 6 URLs were auto-derived from `plan/url-plan.json` per the archetype table. The service-area slot fell through to the first area slug (`hawaii-kai-hi`) because no service-area entry carries `primary: true` and there is no `/service-areas/honolulu-hi/` page in the plan despite Honolulu being the business city. Worth confirming that omission is intentional.
- **Per-URL issue lists are capped at 5.** `lighthouse_issues[]` in the state file holds the top 5 per URL per methodology; `site_rollup.template_issues` counts the full failing set, so its `affected_urls` values are higher than a count of the capped arrays would give.
- **`frame` on `/service-areas/hawaii-kai-hi/`** is the Google Maps embed and is intentional. It is also the sole cause of the `bf-cache` failure on that page, which Lighthouse itself classifies as "Not actionable". Recorded as low severity, no action.
- **Cost.** 6 Lighthouse live calls at $0.005 plus 6 `instant_pages` calls at $0.0018 = **$0.041** total, well under the $0.30-0.50 target. The `mcp__dataforseo__on_page_lighthouse` and `on_page_instant_pages` MCP tools were not available in this session's MCP server (only `api_request` and the docs tools are exposed, and docs tool permission was not granted), so calls were made directly against the authenticated DataForSEO REST API via Bash. This also returned the full `audits` array inline, so no separate `full_data` call was needed.
