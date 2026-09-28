# Onsite Audit - Crew Restoration & Construction - 2026-09-28

**Live origin audited:** https://crew3r.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26
**Form factor:** desktop only (see Notes)

> **Read the amber correctly.** Nothing broke this month, and nothing got fixed
> either. Scores hold at 95-100 in every category on every page, no page errored,
> and no page changed verdict. The same five pages are amber for the same single
> reason as August: the BreadcrumbList JSON-LD still leaves out `item` on the last
> crumb. None of the five August recommendations have shipped. The one new item
> is a Google Analytics tag (`gtag.js`, 159 KB) that now loads on every page. It
> accounts for the new `unused-javascript` flag and matches the timing of the
> simulated LCP increases below. Every LCP value is still under 1.2s.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.5 | -1.3 |
| Accessibility | 96.0 | -0.3 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | 0.0 |

Pages by verdict: green: 1, amber: 5, red: 0, error: 0

No site-level average dropped by 3 or more points.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 100 | 100 | 100 | 0.92s | 0.003 | 0ms |
| `/services/` | services-hub | amber | 99 | 95 | 100 | 100 | 0.97s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | amber | 98 | 95 | 100 | 100 | 1.18s | 0.002 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | amber | 99 | 95 | 100 | 100 | 0.88s | 0.003 | 0ms |
| `/service-areas/brookings-sd/` | service-area | amber | 98 | 95 | 100 | 100 | 1.12s | 0.003 | 0ms |
| `/contact/` | contact | amber | 98 | 96 | 100 | 100 | 1.15s | 0.005 | 0ms |

INP was not reported by Lighthouse, so it is recorded as null.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | Still the header logo: `/images/logo.png` is a 640x640 PNG (78.9 KB) now shown at 96x96. Export a 192x192 WebP and point the header and footer `<img>` at it. That removes about 77 KB from every page. |
| `unused-javascript` | 6 | high | **New.** `https://www.googletagmanager.com/gtag/js?id=G-GCKPEW6C00` (159 KB, about 69 KB unused) now loads on every page. It is already `async`, so TBT is still 0ms. To take it off the critical path, load it after `window.load` or move GA4 to Cloudflare Zaraz. |
| `network-dependency-tree-insight` | 6 | high | Critical chain is document to `/_astro/_slug_.DEXtdMVo.css` (about 9.1 KB). Same as August. The payoff is small because the chain is already short. |
| `render-blocking-insight` | 6 | high | Same stylesheet, `/_astro/_slug_.DEXtdMVo.css`. Lighthouse estimates 40-55ms FCP savings on fire, brookings and contact. Inline the critical CSS (Astro `build.inlineStylesheets: "always"` works at this file size). |
| `cache-insight` | 6 | medium | Still only Cloudflare's `/cdn-cgi/scripts/.../email-decode.min.js`. We cannot edit this file. Turn off Email Address Obfuscation in Cloudflare or ignore it. |
| `color-contrast` | 5 | high | Not fixed. Breadcrumb links `text-dark/50` (#888c93 on white, 3.37:1), `.btn-accent` (white on #e9292f, 4.35:1) on the `tel:+16059652727` CTA, and `text-slate-400` (2.56:1) on the service-area card. Change breadcrumbs to `text-dark/70`, darken `.btn-accent` to about #c81e24, and change `text-slate-400` to `text-slate-600`. |
| `lcp-discovery-insight` | 5 | high | Not fixed. Every non-home hero `<img>` still has no `fetchpriority="high"`. The homepage is still the only page that passes. |
| `has_micromarkup_errors` | 5 | medium | Not fixed. The last `BreadcrumbList` `ListItem` is still `{"@type":"ListItem","position":3,"name":"Water Damage Restoration"}`, with no `item`. |
| `low_content_rate` | 3 | low | Flagged on `/`, `/services/` and `/contact/`. All three are above their word-count targets (1366/1200, 804/800, 619/400). The HTML is heavy relative to the text; the pages are not thin. No action needed. |

## Money page alerts

- **`/services/`** - verdict: amber. BreadcrumbList schema error, accessibility 95 (one breadcrumb link fails contrast), LCP 0.97s.
- **`/services/water-damage-restoration/`** - verdict: amber. BreadcrumbList schema error, accessibility 95 (three contrast nodes: two breadcrumb links plus the `.btn-accent` phone CTA). LCP 1.18s is the slowest of the six. The hero `/images/services/water-damage-restoration.webp` is 186 KB with about 62 KB compressible, and it has no `fetchpriority`.
- **`/services/fire-damage-restoration/`** - verdict: amber. Same schema error and the same three contrast nodes as the water page.
- **`/contact/`** - verdict: amber. BreadcrumbList schema error, accessibility 96. LCP went from 0.49s to 1.15s. Its hero `/images/hero-bg.webp` (98 KB, about 40 KB compressible) is loaded without `fetchpriority` or `srcset`. The conversion path itself is clean: HTTP 200, correct canonical, no broken links.

`/` is green. `/service-areas/brookings-sd/` is amber but is not a money archetype.

## Regressions vs prior audit

**Verdict transitions:** none. Every page has the same verdict as on 2026-08-26.

**Per-URL score regressions (5+ point drop):** none. The largest drop is 2 points (accessibility 96 to 95 on the two service landings; performance 100 to 98 on three pages).

**Core Web Vitals regressions (LCP +200ms or more):**
- `/`: LCP 0.58s to 0.92s (+344ms)
- `/services/water-damage-restoration/`: LCP 0.81s to 1.18s (+376ms)
- `/service-areas/brookings-sd/`: LCP 0.56s to 1.12s (+563ms)
- `/contact/`: LCP 0.49s to 1.15s (+662ms)

These are Lighthouse simulated values. They went up the same month the 159 KB gtag.js request was added. All four are still well under the 2.5s "good" threshold. The regressions are real but have not yet affected any user. CLS and TBT did not regress anywhere.

**New issues this month:**
- All six pages: `unused-javascript`, caused by the new GA4 `gtag.js`.
- `/service-areas/brookings-sd/`: `render-blocking-insight`. This may not be truly new. The August baseline kept only the top 5 audits per page, and this one sat just outside that cutoff on the other non-home pages.
- `/contact/`: `low_content_rate` (low, no action needed; the page has 619 words against a 400 target).

**Issues resolved since last audit:** none of the tracked Lighthouse or DataForSEO issues cleared. One untracked item from last month's recommendations did land: `foundingDate` in the `LocalBusiness` JSON-LD is now `"2015"` instead of an empty string, and it matches the "Since 2015" copy on the homepage.

## Recommended next actions (priority order)

1. **(money page + template, high impact)** In the shared breadcrumb component,
   set `item` on the final `ListItem` to the page's own canonical URL (for
   example `"item":"https://crew3r.com/services/water-damage-restoration/"`).
   This is still the only thing keeping all four money pages and the
   service-area page amber. It is the same fix as August, and it takes one line.
2. **(money page + template, high impact)** Copy the homepage hero markup
   (`srcset` + `sizes="100vw"` + `fetchpriority="high"`) into the services-hub,
   service-landing, service-area and contact templates. While there, re-export
   `/images/services/water-damage-restoration.webp` (186 KB) at a higher
   compression setting, since that page has the slowest LCP of the six.
3. **(template, new this month)** Defer GA4. Either inject the
   `googletagmanager.com/gtag/js?id=G-GCKPEW6C00` script from a
   `window.addEventListener('load', ...)` handler or move GA4 to Cloudflare Zaraz.
   This clears `unused-javascript` on all six pages and should undo most of the
   simulated LCP increase.
4. **(template, accessibility)** Fix the three contrast styles: breadcrumb
   `text-dark/50` to `text-dark/70`, `.btn-accent` background from #e9292f to
   about #c81e24 (4.5:1 or better with white text), and `text-slate-400` to
   `text-slate-600` on the service-area template. This brings accessibility to
   100 on five pages.
5. **(template, bytes)** Replace `/images/logo.png` (640x640, 78.9 KB) with a
   192x192 WebP in the header and footer partials, and make `image` and `logo` in
   the `LocalBusiness` JSON-LD absolute (`https://crew3r.com/images/...`); they
   are still relative.

## Notes / caveats

- **Origin.** Audited the apex production domain again, the same as the
  baseline. The client record still has `apex_cutover: null`, but crew3r.com has
  been live since the 2026-08-08 cutover. It returned HTTP 200 on all six URLs and
  sends no `x-robots-tag: noindex`, so the staging SEO-exclusion correction does
  not apply and all four categories counted.
- **Form factor.** Lighthouse ran desktop only. The DataForSEO wrapper does not
  expose mobile. Mobile performance would typically land 10-20 points lower, and
  the new gtag.js payload and the unprioritized heroes would hurt more there. Do
  not quote these as mobile scores.
- **Client record status.** Still `status: "onboarding"`, even though
  `build_status` is `pushed_main` and the site has been live for seven weeks.
  This was also flagged in August. It should be corrected to `active`.
- **Unchanged backlog.** None of the five August recommendations have shipped
  to the live site except the `foundingDate` value. If these fixes are queued
  in the client deploy repo, they have not been deployed yet. Please check
  before the October audit.
- **Phone number changed.** The `tel:` CTA is now `+16059652727` (it was
  `+18444917560` in August). This is consistent with a call-tracking or local
  number swap. It is noted here only so the contrast selector references line
  up.
- **Truncation in the baseline.** The August state file kept only the top 5
  failing Lighthouse audits per page. This run also records every failing audit
  ID in `lighthouse_failing_audit_ids`, so from next month on, new/resolved
  detection will not have this blind spot. Template counts this month use the
  full list.
- **Carried-over false positives.** DataForSEO's `frame` check on
  `/service-areas/brookings-sd/` (a map `<iframe>`) and the
  `has_render_blocking_resources` / `no_image_title` checks are not recorded as
  issues, for the same reasons as August.
- **Clean on the basics.** Across all six URLs: HTTP 200, self-referencing
  canonicals, one H1 each, titles 41-46 chars, meta descriptions 110-151 chars,
  no duplicate titles or descriptions, no broken links or resources, no mixed
  content, and every page above its `target_word_count`.
- **Tooling and cost.** Used REST calls to `/v3/on_page/lighthouse/live/json`
  (full_data, piped to disk) and `/v3/on_page/instant_pages`. The named MCP tools
  are not exposed in this build. Spend was about $0.04.
