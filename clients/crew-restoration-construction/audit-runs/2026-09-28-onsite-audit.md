# Onsite Audit - Crew Restoration & Construction - 2026-09-28

**Live origin audited:** https://crew3r.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-08-26 (amber)
**Form factor:** desktop only (see Notes)

> **Read the green correctly.** All six pages are green this month, up from one
> in August. The site did not change to earn that. DataForSEO stopped flagging
> `has_micromarkup_errors`, which was the only thing keeping five pages amber, but
> the BreadcrumbList markup that flag pointed at is the same as last month. None
> of August's five recommendations have shipped. The one real change is a new
> Google Analytics 4 tag (`G-GCKPEW6C00`) on every page. It adds about 159 KB of
> JavaScript, roughly 69 KB of it unused on first load, and it lines up with LCP
> rising on all six pages. `/contact/` rose the most, 492ms to 1159ms. Scores are
> still 95-100 everywhere, so this is a healthy site with a small backlog that has
> grown slightly.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.5 | -1.3 |
| Accessibility | 96.0 | -0.3 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | 0.0 |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

No site-level category dropped by 3 or more points.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 100 | 100 | 100 | 0.92s | 0.003 | 0ms |
| `/services/` | services-hub | green | 98 | 95 | 100 | 100 | 0.97s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 100 | 0.85s | 0.003 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 100 | 0.89s | 0.003 | 0ms |
| `/service-areas/brookings-sd/` | service-area | green | 99 | 95 | 100 | 100 | 0.88s | 0.003 | 0ms |
| `/contact/` | contact | green | 97 | 96 | 100 | 100 | 1.16s | 0.005 | 0ms |

On desktop, Core Web Vitals are still well inside the "good" range: LCP under
1.2s on every page, CLS effectively zero, and TBT zero. Lighthouse did not report
INP (it needs field data), so INP is recorded as null.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `unused-javascript` | 6 | high | **New this month.** `https://www.googletagmanager.com/gtag/js?id=G-GCKPEW6C00` (159 KB, 66-70 KB unused per page) is loaded with `<script async>` in the `<head>` of the shared layout. Move it off the critical path: either run it in a worker via `@astrojs/partytown` (`<script type="text/partytown">`), or inject the gtag script on the first `scroll`/`pointerdown`/`keydown` or after `requestIdleCallback`. Keep the `dataLayer`/`gtag('config')` stub inline so no events are lost. |
| `image-delivery-insight` | 6 | high | Not fixed since August. `/images/logo.png` is a 640x640 PNG (78.9 KB, 77.3 KB wasted) shown at 64x64 in the header on every page. Export a 128x128 WebP and point the header `<img>` at it. Page-specific extras: `/contact/` and `/services/` serve the full 1376w `hero-bg.webp` (97.9 KB) with no `srcset`. `/services/water-damage-restoration/` serves `water-damage-restoration.webp` at 186 KB (61.7 KB wasted). |
| `render-blocking-insight` | 6 | high | The only blocking request is `/_astro/_slug_.DEXtdMVo.css` (about 9.1 KB). Lighthouse estimates 50ms FCP savings on fire-damage and brookings-sd and 0ms elsewhere. Inline the above-the-fold rules with Astro `build.inlineStylesheets: 'always'` (the sheet is small enough) and drop the external link. Low absolute payoff. |
| `network-dependency-tree-insight` | 6 | high | The critical chain is the document plus that same 9 KB stylesheet. Inlining the CSS (row above) removes the chain. Lighthouse reports no extra preconnect candidates. |
| `cache-insight` | 6 | medium | The only flagged asset is Cloudflare's `/cdn-cgi/scripts/.../email-decode.min.js`, with a 2-day TTL we can't change. Either turn off Email Address Obfuscation in Cloudflare Scrape Shield or ignore this. |
| `color-contrast` | 5 | high | Not fixed since August. Breadcrumb links use `text-dark/50`, which renders `#888c93` on white at 3.38:1. Change to `text-slate-500` (`#64748b`, 4.76:1) or darker. The `.btn-accent` CTA is white on `#e9292f` at 4.35:1; darken the background to `#dc2626` (4.83:1). On the service-area template, `text-slate-400` (`#94a3b8`, 2.56:1) should become `text-slate-500`. |
| `lcp-discovery-insight` | 5 | high | Not fixed since August. Every non-home template renders the hero as `<img src="/images/hero-bg.webp" ... loading="eager">` with no `fetchpriority="high"` and no `srcset`. The homepage already emits `srcset="/images/hero-bg-480w.webp 480w, ...768w, ...1200w, /images/hero-bg.webp 1376w" sizes="100vw" fetchpriority="high" decoding="async"` and passes. Copy that markup into the other hero components. |
| `forced-reflow-insight` | 3 | high | **New this month** on `/`, `/services/` and `/services/fire-damage-restoration/`: 33-79ms of forced reflow, and Lighthouse could not attribute it to a script. It first appears alongside the GA4 tag. Re-check after the gtag change before digging further. |
| `low_content_rate` | 3 | low | Flagged on `/`, `/services/` and `/contact/`. All three pages beat their word targets (1366/1200, 804/800, 619/400), so the low ratio comes from markup weight, not thin content. No action needed. |

## Money page alerts

None. All four money pages (`/`, `/services/`, both service landings, `/contact/`)
are green. `/contact/` has the largest LCP regression in the set, though, so it
leads the action list below.

## Regressions vs prior audit

**Score regressions (5+ point drop):** none. Per-page category deltas range from
-3 to 0. The largest is `/contact/` performance, 100 to 97.

**Core Web Vitals regressions (LCP +200ms or more):**
- `/contact/`: LCP 492ms to 1159ms (+667ms), FCP 290ms to 776ms. Two things
  now sit on this page's critical path: the new 159 KB gtag.js, and the hero
  `hero-bg.webp`, which is 97.9 KB with no `srcset` or `fetchpriority` (40 KB
  wasted). This is the strongest signal in the run.
- `/`: LCP 577ms to 924ms (+347ms). The homepage hero was already optimized, so
  most of the increase comes from gtag.js plus normal run-to-run variance.
- `/service-areas/brookings-sd/`: LCP 560ms to 878ms (+318ms). The cause looks the
  same as on `/`.

The other three pages rose 47-117ms, which is inside normal variance. No CLS or
TBT regressions.

**Verdict transitions:** five pages went amber to green (`/services/`, both
service landings, `/service-areas/brookings-sd/`, `/contact/`). All five are
improvements, but see the callout at the top: the vendor flag cleared without a
site change.

**New issues this month:**
- All six pages: `unused-javascript`. The GA4 gtag.js was added since August,
  with 66-70 KB unused per page.
- `/`, `/services/`, `/services/fire-damage-restoration/`: `forced-reflow-insight`
  (33-79ms, unattributed).
- `/services/fire-damage-restoration/`, `/service-areas/brookings-sd/`:
  `render-blocking-insight` now fails outright (50ms FCP estimate). On the other
  four pages it still fails at partial score. August stored only the top 5 issues
  per page, so this may have gotten worse rather than appeared for the first time.
- `/contact/`: `low_content_rate` (low, informational).

**Issues resolved since last audit:** `has_micromarkup_errors` no longer fires
on `/services/`, `/services/water-damage-restoration/`,
`/services/fire-damage-restoration/`, `/service-areas/brookings-sd/` or
`/contact/`. The markup itself is unchanged, as explained above. One real fix
did ship: the `LocalBusiness` JSON-LD `foundingDate` is no longer an empty string
(it is now `"2015"`).

## Recommended next actions (priority order)

1. **(money page, regression)** Fix the `/contact/` hero. Change
   `<img src="/images/hero-bg.webp" alt="Contact Crew Restoration &amp; Construction" class="w-full h-full object-cover" loading="eager">`
   to the homepage pattern: add
   `srcset="/images/hero-bg-480w.webp 480w, /images/hero-bg-768w.webp 768w, /images/hero-bg-1200w.webp 1200w, /images/hero-bg.webp 1376w" sizes="100vw" fetchpriority="high" decoding="async"`.
   Make the change in the shared inner-page hero component, not only on
   `/contact/`. That also clears `lcp-discovery-insight` on `/services/`, both
   service landings and the service-area template (280 built pages). This is the
   August recommendation 2, still open.
2. **(template, new, high impact)** Take GA4 off the critical path. The layout
   currently has
   `<script async src="https://www.googletagmanager.com/gtag/js?id=G-GCKPEW6C00">`
   in `<head>`. Add `@astrojs/partytown`, set `forward: ["dataLayer.push", "gtag"]`,
   and change the tag to `type="text/partytown"`. If you'd rather not add a
   dependency, inject the script from a small inline loader on the first user
   interaction or on `requestIdleCallback`. Expect about 69 KB less main-thread JS
   per page, and it should reverse most of this month's LCP drift.
3. **(template, high impact)** Replace the header logo. `/images/logo.png` is
   640x640 and 78.9 KB but displays at 64x64. Export
   `/images/logo-128.webp` (it should be about 3-5 KB) and update the header
   partial, and also update the `LocalBusiness` `logo`/`image` fields (see item 5).
   This is the largest byte saving on every page and has been open since August.
4. **(template, accessibility)** Fix the three contrast failures in the layout:
   breadcrumb `text-dark/50` to `text-slate-500` (#64748b, 4.76:1), `.btn-accent`
   background `#e9292f` to `#dc2626` (4.83:1, which also covers the
   `tel:+16059652727` CTA), and `text-slate-400` to `text-slate-500` on the
   service-area template. Together these move accessibility from 95-96 to 100 on
   five pages.
5. **(template, schema hygiene)** In the `LocalBusiness` block on all pages,
   change `image` and `logo` from the relative `/images/logo.png` to the absolute
   `https://crew3r.com/images/logo.png` (or the new WebP). In the breadcrumb
   component, add `"item": "<page canonical URL>"` to the final `ListItem`. It
   still reads, for example,
   `{"@type":"ListItem","position":3,"name":"Water Damage Restoration"}`.
   DataForSEO no longer flags either one, but both remain open from August and
   are one-line fixes.

## Notes / caveats

- **Origin.** Audited the apex production domain, the same origin as the August
  baseline, so deltas compare like with like. The client record still has no
  `apex_cutover.completed_at`, but `cut_over_at` is 2026-08-08. The apex returned
  HTTP 200 on all six URLs and sends no `x-robots-tag: noindex`. The staging
  SEO-exclusion correction does not apply, and all four categories counted.
- **Form factor.** Lighthouse ran desktop only (`formFactor=desktop`,
  `cpuSlowdownMultiplier=1`, `throughputKbps=10240`, `rttMs=40`). The DataForSEO
  wrapper has no mobile option. On mobile the 159 KB gtag.js and the unprioritized
  heroes would cost noticeably more than they do here. Do not quote these numbers
  as mobile scores.
- **Why the vendor flag cleared.** In August, `has_micromarkup_errors: true`
  fired on five pages. This month it is `false` everywhere, and DataForSEO also
  reports `has_micromarkup: false` on every page, even though each page ships 3-5
  valid JSON-LD blocks (Organization, WebSite, LocalBusiness, Service, FAQPage,
  BreadcrumbList). The vendor's detection changed; the site did not. The green
  verdicts follow the rubric correctly, but the breadcrumb fix is still
  outstanding (item 5).
- **LCP variance.** Single-run desktop Lighthouse typically varies by 100-300ms
  at these LCP levels. `/contact/` (+667ms, with FCP also up 486ms) is a clear
  signal. The `/` and `/service-areas/brookings-sd/` rises crossed the 200ms
  threshold and are recorded as regressions, but confirm them in October before
  acting on them alone.
- **New-issue detection.** The August state stored only the top 5 Lighthouse
  issues per page. An issue counts as new here only when it is high severity
  (it would have outranked the stored mediums) or when the page's August list was
  complete (the homepage). This run also stores `all_failing_lighthouse_audit_ids`
  per page so October can diff the full set.
- **Phone number changed.** The CTA `tel:` link is now `+16059652727`, and the
  `LocalBusiness` `telephone` matches. In August it was `+18444917560`. That is
  out of scope for this audit, but confirm the GBP and citations use the same
  number.
- **Client record status.** `status` is still `"onboarding"` even though the site
  has been live since 2026-08-08. This was flagged in August too, and it should
  be `active`.
- **Tooling and cost.** This DataForSEO MCP build does not expose the
  `on_page_lighthouse` and `on_page_instant_pages` tools, so the audit used
  authenticated REST calls to `/v3/on_page/lighthouse/live/json` and
  `/v3/on_page/instant_pages`. The Lighthouse live response already includes the
  full audit set, so no separate `full_data` call was needed. Total spend was
  about $0.03.
- **Not reported.** DataForSEO's `frame` check fires on
  `/service-areas/brookings-sd/` again because of one map `<iframe>`; that's a
  false positive. `no_image_title`, `has_render_blocking_resources` and
  `high_loading_time` fall outside this skill's check list, and Lighthouse
  already covers the last two.
- **Clean bill on the basics.** All six URLs return HTTP 200, have correct
  self-referencing canonicals, exactly one H1, titles of 41-46 chars and meta
  descriptions of 110-151 chars. There are no duplicate titles or descriptions,
  no broken links or resources, and no mixed content. Image alt coverage is full
  (Lighthouse `image-alt` passed on every page), and every page is above its
  `target_word_count`.
- **URL selection.** Same six URLs as August, taken from `plan/url-plan.json`
  (there is no `audit-urls.txt`). No service-area page has `primary: true` and
  the plan has no Sioux Falls area page, so the first plan-order area,
  `/service-areas/brookings-sd/`, was used. For the two service landings, four
  pages tie at priority 9.0. Water and fire damage were kept for continuity with
  the August baseline.
