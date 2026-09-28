# Onsite Audit - Flood Fixers - 2026-09-28

**Live origin audited:** https://flood-fixers.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-08-27 (green)
**Form factor:** desktop only (see Notes)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98 | -1 |
| Accessibility | 95 | +4 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

The August contrast fixes shipped. Breadcrumb links and the accent CTA now pass on four pages, so accessibility is up 5 points on each of them. Performance slipped 1 point. The GA4 tag added on 2026-08-31 is the only new cost in the payload.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 98 | 96 | 100 | 100 | 0.96s | 0.039 |
| `/services/` | services-hub | green | 98 | 95 | 100 | 100 | 1.09s | 0.004 |
| `/services/water-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 100 | 0.93s | 0.006 |
| `/services/flood-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 100 | 0.91s | 0.006 |
| `/service-areas/chula-vista-ca/` | service-area | green | 98 | 91 | 100 | 100 | 1.01s | 0.050 |
| `/contact/` | contact | green | 98 | 96 | 100 | 100 | 1.17s | 0.036 |

TBT was 0ms on all six pages. INP is null on all six because lab Lighthouse does not report it.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `link-name` | 6 | medium | The footer `<address>` renders an empty email anchor on every page, and `/contact/` has a second one in the contact aside. `brand.ts` has `email: ""`, so Cloudflare email obfuscation outputs `<a href="/cdn-cgi/l/email-protection#..."></a>` with no text. Third month open. |
| `unused-javascript` | 6 | low | New this month. `googletagmanager.com/gtag/js?id=G-BPB9R60M10` is 156 KiB, and 69 KiB of it is unused on load. It is loaded `async` in the head by `Analytics.astro`. |
| `cache-insight` | 6 | low | `images.flood-fixers.com/brand/hero.webp` (262 KiB) returns `max-age=14400, must-revalidate` and `cf-cache-status: DYNAMIC`, so it is re-fetched about every 4 hours. This hits 3 pages hard (hub, chula-vista, contact). The other 3 only flag Cloudflare's `email-decode.min.js`. |
| `image-delivery-insight` | 6 | low | `/images/logo.webp` (21 KiB) is displayed at 36-48px on every page, so about 21 KiB is recoverable per page. `brand/hero.webp` has up to 213 KiB recoverable on `/contact/` and 171 KiB on `/services/`. |
| `render-blocking-insight` / `has_render_blocking_resources` | 6 | low | One stylesheet (`/_astro/_slug_.CURUGAg3.css`, 9 KiB) plus one script. Measured cost is 56ms FCP. Low priority at current scores. |
| `network-dependency-tree-insight` | 6 | low | Chains through Google Fonts (`fonts.googleapis.com` to `fonts.gstatic.com`). Same root cause as the home CLS regression below. |
| `lcp-discovery-insight` | 5 | low | Every template except home renders the hero `<img ... loading="eager">` with no `fetchpriority="high"`, so the `priorityHinted` check fails on all five. Home passes. |
| `low_content_rate` | 2 | low | Text-to-HTML ratio: 7.1% on `/` and 9.1% on `/contact/`. Informational. Word counts are fine (1554 and 733). |
| `forced-reflow-insight` | 2 | low | New on `/services/` (32ms) and `/service-areas/chula-vista-ca/` (54ms). Lighthouse gives no source attribution. |

## Money page alerts

None. All four money-page archetypes (home, services hub, both service landings, contact) came back green.

One money-page finding is still worth acting on even though it did not trip a verdict. **`/contact/`** still renders two empty email anchors, one in the contact aside and one in the footer. A visitor who taps the email affordance on the contact page gets nothing.

## Regressions vs prior audit

**Verdict transitions:** none.

**Category drops of 5+ points:** none. Five of six pages lost 1 performance point, and `/` held at 98.

**Core Web Vitals past threshold (both still inside Google's "good" band):**
- `/` CLS went from 0.018 to 0.039 (+0.021). Lighthouse attributes the whole shift to the Inter web font (`fonts.gstatic.com/.../UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7W0Q5nw.woff2`) swapping in and reflowing the hero `div.container-wide`.
- `/contact/` LCP went from 846ms to 1172ms (+326ms). The LCP element is the non-prioritized `images.flood-fixers.com/brand/hero.webp`. Its lab breakdown subparts sum to about 300ms, so part of this is throttling simulation variance. The other pages drifted +67 to +187ms, which is under the threshold.

**New issues this month:**
- All 6 pages: `unused-javascript`. This is the GA4 gtag.js added 2026-08-31, after the prior audit.
- `/services/` and `/service-areas/chula-vista-ca/`: `forced-reflow-insight` (32ms and 54ms).
- `/contact/`: `low_content_rate`. Text-to-HTML ratio is 9.1%.

**Issues resolved since last audit:** (positive, keep doing this)
- `/services/`, `/services/water-damage-restoration/`, `/services/flood-damage-restoration/`, `/contact/`: `color-contrast` no longer fails. The breadcrumb token and the `btn-accent` CTA fixes landed, and each page gained 5 accessibility points.

## Recommended next actions (priority order)

1. **(money page + template)** Remove the empty email anchors. `sites/flood-fixers/src/lib/brand.ts` has `email: ""`, and the footer `<address>` block and the `/contact/` aside render the anchor anyway. Wrap both in a `{brand.email && (...)}` guard so they disappear when no email is set, or get a confirmed business email from the client and set it. Do not reuse `luxurycustomfloors@gmail.com` from `clients/flood-fixers.json` `contact` without confirming it: the name does not match this business. This is the only `link-name` failure on all 6 pages and has been open since July.
2. **(template, LCP; also covers the `/contact/` LCP regression)** Add `fetchpriority="high"` to the hero `<img>` in the services hub, service landing, service area and contact templates. Also give `brand/hero.webp` the `srcset`/`sizes` treatment home already uses (`hero-bg-480w/768w`). `/contact/` serves the 262 KiB original into a 1350x207 box, and Lighthouse estimates 213 KiB is recoverable there.
3. **(template, CLS; fixes the home CLS regression)** Stop the Inter font swap from shifting the hero. Self-host Inter under `/fonts/` with a `<link rel="preload" as="font" type="font/woff2" crossorigin>` in the layout head. Add a fallback `@font-face` using `size-adjust`/`ascent-override` so Arial matches Inter metrics, or switch to `font-display: optional`. This also removes the `fonts.googleapis.com` to `fonts.gstatic.com` chain flagged by `network-dependency-tree-insight`.
4. **(template, infra)** Add a Cloudflare Cache Rule for `images.flood-fixers.com/*` with Edge TTL and Browser TTL of 1 year (`public, max-age=31536000, immutable`). `brand/hero.webp` currently returns `max-age=14400, must-revalidate` with `cf-cache-status: DYNAMIC`, which costs about 178 KiB per repeat view on 3 of 6 pages. Also re-export `/images/logo.webp` at 96x96 (2x the largest 48px render). The file is 21 KiB today and should be under 3 KiB.
5. **(per-page, accessibility)** On `/service-areas/chula-vista-ca/`, change `span.text-slate-400` (#94a3b8 on white, 2.56:1 at 14px) to `text-slate-600` (#475569, 7.6:1). It is the last `color-contrast` failure in the audited set and would lift the page from 91 to about 96 accessibility, in line with the other templates.

## Notes / caveats

- **Live origin choice.** `clients/flood-fixers.json` has no `apex_cutover.completed_at` key, but it records the cutover as `cut_over_at: 2026-07-04T20:30:00Z`. The apex is live: HTTP 200 on all 6 URLs, no `x-robots-tag: noindex`, and `build_status: pushed_main`. So the apex was audited, SEO counts toward the verdict, and deltas are comparable with the three prior apex audits.
- **Desktop only.** Lighthouse 13.4.0 ran with `formFactor=desktop` (verified in `configSettings`). Mobile would typically score 10-20 performance points lower. These are not mobile-first scores.
- **MCP transport.** The DataForSEO MCP wrapper in this CI run exposes only the generic `api_request` tool, so this run called the same REST endpoints directly (`on_page/lighthouse/live/json`, `on_page/instant_pages`). Total API cost: $0.041.
- **GA4 unused-javascript trade-off.** The gtag bytes are the cost of conversion tracking (`click_to_call` and `generate_lead` events in `Analytics.astro`). Do not remove the tag. If the payload needs to shrink later, the only safe options are deferring the gtag load until after `load`, or moving it to a server-side or Partytown worker. The current 0-1 point cost does not justify either yet.
- **Schema false negative.** instant_pages returned `has_micromarkup=false` on all 6 URLs. Direct HTML inspection found parseable JSON-LD everywhere: Organization, WebSite and LocalBusiness on home; FAQPage and BreadcrumbList added on the hub and contact; Service, LocalBusiness, FAQPage and BreadcrumbList on the landings; LocalBusiness, FAQPage and BreadcrumbList on the service area. This was not treated as missing schema.
- **Link crawling not performed.** instant_pages audits one URL and does not follow outlinks. It reported `broken_links=false` and `broken_resources=false` on all 6 pages, and every audited URL returned 200.
- **Alt text at 100%, no mixed content.** Every `<img>` on the 6 pages has a non-empty `alt`, and none of the pages load `http://` resources. DataForSEO's `no_image_title` fired everywhere but is outside the rubric and was not recorded.
- **Carried-over low items.** The home meta description is still 171 characters (`meta_description_too_long`, target 70-160). The `/services/` word count is 751, against a url-plan target of 800 (`content_below_target_word_count`). The Chula Vista page embeds a map iframe (`frame`). All are low severity and unchanged from last month.
- **Lab variance.** LCP rose 67-326ms on 5 of 6 pages, but the scores moved at most 1 point and every LCP is under 1.2s. If `/contact/` is still above 1.1s next month after the priority-hint fix, investigate it directly.
