# Onsite Audit - ProRestoration Services - 2026-09-28

**Live origin audited:** https://prorestorationca.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-27 (amber)
**Form factor:** desktop (Lighthouse 13.4.0, cpuSlowdownMultiplier 1, throughputKbps 10240). Mobile scores would typically run 10-20 performance points lower.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.3 | -1.4 |
| Accessibility | 91.3 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | 0.0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

Three pages moved from amber to green. They did not get faster: DataForSEO's crawler simply stopped flagging `high_loading_time` on them. The homepage is the only amber page, because its meta description is still too long. The two accessibility failures from August are still there on every page (one of them was partly fixed). A new header logo image and a new Google Analytics tag have added weight since last month, and LCP went up on every page as a result.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 98 | 96 | 100 | 100 | 1.06s | 0.059 | 0ms |
| `/services/` | services-hub | green | 98 | 90 | 100 | 100 | 1.02s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 99 | 90 | 100 | 100 | 0.96s | 0.005 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 90 | 100 | 100 | 0.93s | 0.003 | 0ms |
| `/service-areas/oildale-ca/` | service-area | green | 99 | 91 | 100 | 100 | 1.00s | 0.003 | 0ms |
| `/contact/` | contact | green | 97 | 91 | 100 | 100 | 1.18s | 0.063 | 0ms |

INP is null on every page because Lighthouse lab runs do not produce INP without user interaction. Every LCP and CLS value is still inside Google's "good" thresholds (2.5s and 0.1).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `link-name` | 6 | high | Not fixed since August. The footer `address` block still renders `<a href="mailto:" class="text-primary ...">` with no address and no text, and `/contact/` has a second empty anchor in the contact card (`div.space-y-5 > div.flex > div > a.font-bold`). `clients/prorestoration.json` still has `contact: null`, and "email address" is still listed in `awaiting_intake`. Wrap both anchors in a truthiness check on the email field. |
| `image-delivery-insight` | 6 | medium | **New root cause.** The header logo is now `/images/logo.png` (1688x646, 106,636 bytes) but displays at 251x96, which wastes 104KB on every page. The footer loads the same file too. Export a 502x192 (2x) WebP or restore the SVG. On `/services/` and `/contact/`, the inner hero `/images/hero-bg.webp` has grown to 248KB (it was 165KB) and still has no `srcset`. Lighthouse flags 157KB of waste on `/services/`, 200KB on `/contact/` and part of the 230KB flagged on `/service-areas/oildale-ca/`. |
| `unused-javascript` | 6 | low | **New.** `googletagmanager.com/gtag/js?id=G-LQE0DXHG08` (159KB) was added to the layout since the last audit, and 67-70KB of it goes unused on each page. It already loads `async`. To take it off the critical path, load it after `window.load` or through Partytown. |
| `color-contrast` | 5 | high | Partly fixed. The `.btn-accent` failure is gone. Breadcrumb links (`a.text-dark/50`, `#888c93` on white = 3.37:1) still fail on every breadcrumbed page. Change them to `text-dark/70`. New on `/service-areas/oildale-ca/`: the review count `span.text-slate-400` ("115 Google reviews") is 2.56:1, so change it to `text-slate-600`. |
| `lcp-discovery-insight` | 5 | low | The homepage hero now has `fetchpriority="high"` and passes. The shared inner-page hero (`main > section.relative > div.absolute > img.w-full`) still renders `loading="eager"` without `fetchpriority="high"`. Copy the homepage hero attributes over. |
| `cache-insight` | 6 | low | The only resource flagged is Cloudflare's `email-decode.min.js` (about 950 bytes). It goes away once the empty mailto anchors are removed. |
| `render-blocking-insight` / `has_render_blocking_resources` | 6 | low | `/_astro/_slug_.B_qI-cHQ.css` (9KB) blocks render for 51-54ms. Low priority at current scores. |
| `network-dependency-tree-insight` | 6 | low | No preconnect to `fonts.gstatic.com` or `www.googletagmanager.com`. Add `<link rel="preconnect">` for both in the layout head. |
| `forced-reflow-insight` | 2 | low | New on `/` (37ms, unattributed) and `/services/fire-damage-restoration/`. Probably comes from the gtag bootstrap. Check again after deferring gtag. |
| `no_image_title` | 6 | low | Cosmetic. No action. |
| `low_content_rate` | 2 | low | `/` and `/services/` are markup-heavy hubs. No action. |

## Money page alerts

- **`/`** (home) - verdict: amber. The meta description is still 184 characters, which is over the 160 target, so it gets truncated in the SERP. It ends "...Licensed, insured, IICRC-certified. Call (661) 393-9306." Accessibility is 96 because of the empty footer mailto link. LCP went from 0.77s to 1.06s, and CLS is 0.059 because the Inter web font swap shifts the hero container.

## Regressions vs prior audit

No Lighthouse category fell by 5 or more points on any URL. The site average for performance fell 1.4 points, which is under the 3-point threshold.

**Core Web Vitals regressions (threshold: LCP +200ms, CLS +0.02):**
- `/`: LCP went from 765ms to 1055ms (+290ms).
- `/contact/`: LCP went from 771ms to 1181ms (+410ms). The LCP element is the 248KB `hero-bg.webp`, which has no `srcset`.
- `/contact/`: CLS went from 0.021 to 0.063 (+0.042). The shift hits `section#estimate`. Lighthouse lists two causes: the Inter web font and the footer logo `img.h-16`. That logo has `width="48" height="48"` (square), but the file is 1688x646 and styled `w-auto`, so the browser reserves the wrong box until the image loads.
- LCP also went up on the other four pages, but by less than the threshold (+112 to +195ms). The consistent rise across all pages points to the new logo PNG and the gtag script, not to changes on individual pages.

**Verdict transitions:**
- `/services/`, `/service-areas/oildale-ca/`, `/contact/` improved from amber to green. The only reason is that DataForSEO's crawler stopped flagging `high_loading_time`. HTML still ships `cache-control: public, max-age=0, must-revalidate` with `cf-cache-status: DYNAMIC`, so the underlying cause is not fixed. The crawler still saw cold loads of 1447ms on `/services/water-damage-restoration/` and 2031ms on `/services/fire-damage-restoration/`, with 276-283ms connection times.
- No verdict got worse.

**New issues this month:**
- All 6 pages: `unused-javascript` (new gtag script, about 69KB unused).
- `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`: `image-delivery-insight` (the oversized `logo.png`).
- `/`, `/services/fire-damage-restoration/`: `forced-reflow-insight`.

**Issues resolved since last audit:** (positive, keep doing this)
- All 6 pages: `unsized-images` is gone, because the header logo now has explicit `width`/`height`. The values are the wrong aspect ratio, though (see action 3).
- `/services/`, `/service-areas/oildale-ca/`, `/contact/`: `high_loading_time` is no longer flagged.
- Homepage hero now has `fetchpriority="high"`.
- `.btn-accent` contrast failure is gone.

## Plan conformance (carried forward, re-verified)

`/service-areas/oildale-ca/` still emits `LocalBusiness`, `FAQPage` and `BreadcrumbList` JSON-LD, but no `Service` node. `plan/url-plan.json` calls for `schema_stubs: [local-business, service, breadcrumb-list]`. This is template-wide.

## Recommended next actions (priority order)

1. **(money page)** Shorten the homepage meta description from 184 to under 160 characters, for example by dropping "Licensed, insured, IICRC-certified." and keeping the phone number. This is the only thing keeping the site at amber. Fixing it makes all 6 pages green.
2. **(template, high)** Remove the empty `mailto:` anchors from the footer and from the `/contact/` contact card by adding a guard on the email field. Then get the email address from the client (still open in `awaiting_intake`). This fixes `link-name` on all 6 pages and clears `cache-insight` and `agent-accessibility-tree` along with it.
3. **(template, medium)** Replace `/images/logo.png` (1688x646, 104KB wasted per page) with a 502x192 WebP or the original SVG. Fix the aspect ratio in the attributes: header `width="251" height="96"` and footer `width="209" height="80"` instead of the current squares. This recovers most of the LCP regression and removes the footer layout shift on `/contact/`.
4. **(template, high)** Change the breadcrumb links from `text-dark/50` to `text-dark/70` (currently 3.37:1, needs 4.5:1) and the service-area review-count `span.text-slate-400` to `text-slate-600`. Affects 5 of 6 audited pages and every breadcrumbed page on the site.
5. **(template)** Give the inner-page hero component the same `srcset`/`sizes`/`fetchpriority="high"` as the homepage hero, and re-compress `hero-bg.webp`, which grew from 165KB to 248KB. Saves 157-200KB on `/services/` and `/contact/` and clears `lcp-discovery-insight` on 5 pages.

## Notes / caveats

- **Origin choice.** `apex_cutover.completed_at` is null in the client record. Under the methodology that means auditing the staging Pages preview. I audited the apex anyway: `https://prorestorationca.com` serves the Rank AI Astro build (200, `/_astro/` assets, no `x-robots-tag`), and the 2026-08-27 baseline was taken there, so the regression comparison stays like-for-like. The staging preview does send `x-robots-tag: noindex`, so auditing it would have deflated SEO for no benefit. SEO counts toward the verdict normally. Someone should record the cutover in the client record.
- `clients/prorestoration.json` still has `status: "pending"`. I ran the audit anyway because `build_status` is `pushed_main` and the apex is live, the same call as in August.
- **URL selection.** There is no `audit-urls.txt`, so I used Mode B. Five service landings tie at priority 9.0 (water, fire, mold, roofing, home remodeling). I kept water and fire to match the baseline. No service area has `primary: true` and the client record has no `business.address`, so I kept `oildale-ca`.
- Lighthouse 13.4 also reports an `agentic-browsing` category (66-67 on every page). I recorded it under `supplemental_scores` and left it out of verdicts and issue lists. Its only failing audit, `agent-accessibility-tree`, comes from the same empty mailto anchors as `link-name`.
- Zero broken links, zero broken resources, zero duplicate titles or descriptions. One H1 per page. Canonicals point to the page itself and are correct. Titles are 61-65 characters. Word counts meet `target_word_count` everywhere except `/services/` (795 vs 800, not worth acting on).
- `has_micromarkup: false` still fires on every page but is a false positive. The pages ship valid JSON-LD, and that check only detects microdata/RDFa.
- The DataForSEO endpoints were called directly over REST because the MCP server only exposes `api_request` and `docs_*`. I sent `for_mobile: false`. Estimated spend: 0.041 USD (6 Lighthouse at 0.005, 6 instant_pages at 0.0018).
