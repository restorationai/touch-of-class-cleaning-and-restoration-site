# Onsite Audit - RestorationXpress - 2026-09-28

**Live origin audited:** https://restorationxpress.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-28
**Form factor:** desktop only (Lighthouse 13.4.0)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.3 | -1.2 |
| Accessibility | 94.7 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | 0.0 |

Pages by verdict: green: 1, amber: 5, red: 0, error: 0

Headline: no verdict changes this month, and none of last month's five recommendations have shipped yet. Every issue from the 2026-08-28 audit is still live: the BreadcrumbList schema error that keeps five pages amber, the brand-green contrast failure, the oversized `logo.png`, the missing `fetchpriority` on inner-page heroes, and the un-underlined `mailto:` link on `/contact/`. The only new item is GA4 (`gtag.js`), which has been added to every page since the last audit. It adds about 68KB of unused JavaScript per page and is the most likely cause of the small LCP increase.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT | Words |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 97 | 96 | 100 | 100 | 1.13s | 0.004 | 0ms | 1561 |
| `/services/` | services-hub | amber | 98 | 95 | 100 | 100 | 1.03s | 0.002 | 0ms | 783 |
| `/services/water-damage-restoration/` | service-landing | amber | 99 | 95 | 100 | 100 | 0.95s | 0.003 | 0ms | 1853 |
| `/services/fire-damage-restoration/` | service-landing | amber | 99 | 95 | 100 | 100 | 1.04s | 0.005 | 0ms | 1593 |
| `/service-areas/fort-lauderdale-fl/` | service-area | amber | 98 | 95 | 100 | 100 | 1.04s | 0.003 | 0ms | 1427 |
| `/contact/` | contact | amber | 99 | 92 | 100 | 100 | 1.04s | 0.005 | 0ms | 731 |

Lighthouse returned no INP because this is a lab run with no field data, so INP is stored as null.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `has_micromarkup_errors` | 5 | medium | The last `ListItem` in the `BreadcrumbList` JSON-LD has only `position` and `name`, with no `item`. Confirmed live on `/contact/`: `{"position": 2, "name": "Contact"}`. Add a self-referencing `item` URL to the last crumb in the breadcrumb component. This is the only thing keeping 5 pages amber. |
| `color-contrast` | 6 | high | Brand primary `#719430` measures 3.51:1 in both directions against white (white text on green, and green text on white), below the WCAG AA minimum of 4.5:1. It shows up on the top notice bar, the header "Call Now" CTA, the tel buttons, and the "service areas" eyebrow link. The breadcrumb home link `#888c93` on white is 3.37:1. Darken `primary-600` to about `#5A7726`, and replace `text-dark/50` in the breadcrumb with `text-dark/70`. |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is a 1000x429 PNG (158,570 bytes) displayed at 149x64 in the header and 186x80 in the footer, on every page. Export a 372x160 WebP and use it in both places. On `/contact/` and `/services/`, Lighthouse says `hero-bg.webp` (218KB) could be about 170KB smaller with higher compression. Re-encode it at quality 70 and add the existing `srcset` variants, which only the home hero uses today. Estimated savings are 181-326KB per page. |
| `unused-javascript` | 6 | medium | New this month. `googletagmanager.com/gtag/js?id=G-YMWBHG8Y4F` loads with `async` in `<head>`: about 159KB total, 68KB of it unused on first paint. Delay GA4 until after `load` (or first user interaction), or move it to Partytown. Lighthouse estimates 50-100ms of LCP savings per page. |
| `lcp-discovery-insight` | 5 | medium | The inner-page hero `<img src="/images/hero-bg.webp" loading="eager">` has no `fetchpriority="high"`. The home hero already sets it. Add the same attribute to the hero component used by the hub, landing, area, and contact layouts. |
| `forced-reflow-insight` | 3 | low | Flagged on home, water-damage, and Fort Lauderdale. Only home reports a measured cost (36ms, unattributed); the other two list no source or time. No action until mobile auditing shows it matters. |
| `render-blocking-insight` / `has_render_blocking_resources` | 6 | low | `_astro/_slug_.Ds6AEepO.css` (8.7KB) blocks render for 0-60ms. Optional. Inline critical CSS only if you are chasing the last performance point. |
| `cache-insight` | 6 | low | The only flagged file is Cloudflare's injected `email-decode.min.js` (about 950 bytes). This comes from Cloudflare Email Obfuscation, not our build. No action. |
| `network-dependency-tree-insight` | 6 | low | The critical chain is short and healthy. No action. |
| `no_image_title` | 6 | low | Images have no `title` attribute, but alt coverage is 100%. Informational only. |

## Money page alerts

- **`/contact/`** (contact): verdict amber. Accessibility is 92, the lowest on the site. The `mailto:` link in body copy still fails `link-in-text-block` because it is set apart by colour only, with no underline. BreadcrumbList schema error. 326KB of avoidable image bytes. LCP went from 0.69s to 1.04s.
- **`/services/`** (services-hub): verdict amber. BreadcrumbList schema error. Hero is missing `fetchpriority="high"`. 319KB of avoidable image bytes.
- **`/services/water-damage-restoration/`** (service-landing): verdict amber. BreadcrumbList schema error. Hero is missing `fetchpriority="high"`. 185KB of avoidable image bytes.
- **`/services/fire-damage-restoration/`** (service-landing): verdict amber. BreadcrumbList schema error. Hero is missing `fetchpriority="high"`. LCP went from 0.65s to 1.04s.

## Regressions vs prior audit

**Verdict transitions:** none. All six pages kept last month's verdict (1 green, 5 amber).

**Site-level score deltas:** no category fell by 3 or more points. Performance averaged 98.3, down from 99.5.

**Per-URL metric regressions (LCP up 200ms or more):**
- `/`: LCP 924ms to 1132ms (+208ms). Performance 99 to 97.
- `/services/fire-damage-restoration/`: LCP 646ms to 1036ms (+390ms).
- `/contact/`: LCP 693ms to 1037ms (+344ms).

Every page is still well under the 2.5s "good" threshold on desktop. TTFB stayed at 38-152ms, so the server is not the cause. The only new resource on these pages is GA4 `gtag.js`. Some of the change is probably normal variance between single lab runs, so re-check after GA4 is delayed.

**New issues this month:**
- All 6 URLs: `unused-javascript`. The GA4 `gtag.js` bundle is about 68KB unused.
- `/`, `/services/water-damage-restoration/`, `/service-areas/fort-lauderdale-fl/`: `forced-reflow-insight` (36ms unattributed on home; no measured cost on the other two).

**Issues resolved since last audit:**
- `/services/fire-damage-restoration/`: `high_loading_time` no longer appears. Last month's 5.1s reading was transient, and this crawl loaded the page in 253ms.

## Recommended next actions (priority order)

1. **(money page, schema)** Add the missing `item` URL to the last `ListItem` in the `BreadcrumbList` JSON-LD emitted by the breadcrumb component. This one change moves `/services/`, both service landings, `/contact/`, and the service-area page from amber to green. It was also the top schema item last month and has not shipped.
2. **(money page, accessibility)** On `/contact/`, underline in-prose links (`text-decoration: underline` on `a` inside the body copy container). This clears `link-in-text-block` for the `mailto:` link and raises contact accessibility from 92.
3. **(template, performance)** Delay GA4: remove the `async` `gtag.js` tag from `<head>` and inject it after `window.load` or on first interaction, or run it through Partytown. This removes about 68KB of unused JS from the critical path on all pages and should undo most of this month's LCP increase.
4. **(template, images)** Replace `/images/logo.png` (1000x429, 158KB) with a 372x160 WebP in both header and footer. Re-encode `/images/hero-bg.webp` at quality 70 and give the inner-page hero the same `srcset`/`sizes` plus `fetchpriority="high"` the home hero already has. Saves 181-326KB per page and clears `lcp-discovery-insight` on 5 pages.
5. **(template, accessibility)** Darken `primary-600` from `#719430` to about `#5A7726` for any white-on-green or green-on-white text, and raise the breadcrumb home link from `text-dark/50` to `text-dark/70`. This clears `color-contrast` on all 6 pages.

## Notes / caveats

- **Desktop only.** Lighthouse ran with `formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`. Mobile scores usually run 10-20 performance points lower and were not measured. The direct DataForSEO API supports `for_mobile`, so a mobile pass is possible if the methodology is updated.
- **How data was collected.** The named MCP wrappers (`on_page_lighthouse`, `on_page_instant_pages`) were not available in this CI session. Both endpoints were called directly through the DataForSEO REST API (`on_page/lighthouse/live/json` with `for_mobile=false`, and `on_page/instant_pages` with JavaScript and micromarkup validation on). Raw responses were saved to disk and parsed there. The state file keeps every failing audit per URL, not only the top 5, so that month-over-month issue diffs stay like-for-like with the 2026-08-28 baseline.
- **Client record status.** `clients/restorationxpress.json` still says `status: "onboarding"`. The audit ran because `build_status` is `pushed_main` and the apex cutover finished 2026-08-04. This was flagged last month too. The ops owner should set status to `active`.
- **Last month's recommendations are still open.** None of the five actions from 2026-08-28 appear in the live build. The only change seen is the CSS bundle hash (`CuEjtIRd` to `Ds6AEepO`) plus the GA4 addition. If a site fix is planned, it should include items 1, 2, 4, and 5 above.
- **Services hub word count.** `/services/` has 783 words against an 800-word target in `url-plan.json` (17 short). This is low severity and is not a real DataForSEO check ID, so it is recorded here and not as an issue.
- **Clean checks.** No broken links, broken resources, mixed content, duplicate titles, or missing H1s. Canonicals are present and self-referencing on all 6 URLs. Titles are 48-63 characters and meta descriptions 104-139, all within range. The Google Maps iframe (`frame` on `/service-areas/fort-lauderdale-fl/`) is lazy-loaded and has a title, so it is informational.
