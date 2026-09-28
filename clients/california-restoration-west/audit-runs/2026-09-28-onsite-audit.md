# Onsite Audit - California Restoration West - 2026-09-28

**Live origin audited:** https://californiarestorationwest.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26 (staging Pages preview)
**Form factor:** desktop only (Lighthouse 13.4.0, `for_mobile=false`)

---

## Read this first

**Last month was red on all six pages. This month there is no red page. All six are amber.** The missing images that 404'd are now published, the 1.73 MB PNG logo is now a 58 KB WebP, and the site serves on the apex with no noindex header. Every Lighthouse category is 95 or higher on every page. Nothing on the site is broken.

The pages are amber, not green, because of two small template fixes and one home-page metadata fix. They are listed in the recommended actions below. None of them block launch.

**Why this run audited the apex.** The client record has no `apex_cutover.completed_at`, so the methodology default would be the staging preview. But the record does carry `cut_over_at: 2026-09-22`, the apex serves the current `main` build, and the staging alias still serves the 2026-08-27 build (different CSS bundle hash). Auditing staging would have measured month-old code. SEO counts toward the verdict this run because the apex sends no `x-robots-tag`.

---

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 99.0 | +4.3 |
| Accessibility | 96.0 | 0.0 |
| Best Practices | 100.0 | +4.0 |
| SEO | 100.0 | +31.0 (staging noindex removed, not a site change) |

Pages by verdict: green 0, amber 6, red 0, error 0

Verdict basis: all four categories plus on-page issues.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 99 | 100 | 100 | 100 | 0.90s | 0.003 | 0ms |
| `/services/` | services-hub | amber | 98 | 95 | 100 | 100 | 0.91s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | amber | 100 | 95 | 100 | 100 | 0.74s | 0.024 | 0ms |
| `/services/mold-remediation/` | service-landing | amber | 99 | 95 | 100 | 100 | 0.84s | 0.003 | 0ms |
| `/service-areas/oxnard-ca/` | service-area | amber | 99 | 95 | 100 | 100 | 0.91s | 0.003 | 0ms |
| `/contact/` | contact | amber | 99 | 96 | 100 | 100 | 0.91s | 0.041 | 0ms |

INP is null on every page. Lighthouse lab runs do not produce INP without user interaction. This is expected.

What makes each page amber:
- `/` : title is 27 characters and the meta description is 185 characters.
- The other five pages: DataForSEO reports structured-data validation errors (`has_micromarkup_errors`).

## Template-level issues (fix once, lift many pages)

| Issue | Source | Affected URLs | Severity | Recommended fix |
| --- | --- | ---: | --- | --- |
| `color-contrast` | lighthouse | 5 | high | Breadcrumb links use `text-dark/50`, 3.37:1 on white. See action 2. |
| `has_micromarkup_errors` | dataforseo_onpage | 5 | medium | Add `item` URL to the final BreadcrumbList crumb. See action 1. |
| `image-delivery-insight` | lighthouse | 6 | medium | Logo and hero are oversized for their slots. See action 4. |
| `unused-javascript` | lighthouse | 6 | medium | GA4 `gtag.js` (156 KB, about 69 KB unused). Third-party. See notes. |
| `lcp-discovery-insight` | lighthouse | 5 | medium | Hero `<img>` on inner templates lacks `fetchpriority="high"`. See action 3. |
| `render-blocking-insight` | lighthouse | 6 | low | `/_astro/_slug_.DZqYX603.css`, 9 KB. About 50ms on `/contact/`, negligible elsewhere. |
| `network-dependency-tree-insight` | lighthouse | 6 | low | Long critical chain via Google Fonts. Low value on desktop. |
| `cache-insight` | lighthouse | 6 | low | Only Cloudflare's own `email-decode.min.js` (under 1 KB). Not actionable. |
| `forced-reflow-insight` | lighthouse | 2 | low | 32 to 38ms unattributed reflow on `/services/mold-remediation/` and `/contact/`. Monitor only. |

## Money page alerts

All five audited money pages are amber. None are red. None have a score below 95.

- **`/`** (home) - amber. Lighthouse 99/100/100/100. Title is `California Restoration West`: 27 characters, no city or service keyword. Meta description is 185 characters and will be cut off in search results.
- **`/services/`** (services-hub) - amber. Structured-data validation errors, breadcrumb contrast 3.37:1, hero image missing `fetchpriority="high"`. Word count 753 against an 800 target (low).
- **`/services/water-damage-restoration/`** (service-landing) - amber. Structured-data validation errors, breadcrumb contrast 3.37:1.
- **`/services/mold-remediation/`** (service-landing) - amber. Same two issues.
- **`/contact/`** (contact) - amber. Same two issues. `hero-bg.webp` (179 KB, 1350px wide) is shown in a 207px-tall strip, so about 131 KB of it is wasted.

## Regressions vs prior audit

The prior run audited the staging preview. This run audited the apex. URLs were matched by path.

**Score regressions (5 points or more):** none. Every category held or improved on every page.

**Core Web Vitals flags:**
- `/services/` LCP rose from 0.50s to 0.91s (+416ms). This is not a real slowdown. Last month the hero image 404'd, so the LCP element was text. Now the real hero image loads and counts as the LCP. At 0.91s it is well within the 2.5s "good" threshold. Action 3 will bring it down.

**Verdict transitions (all improvements):**
- All six pages went from red to amber: `/`, `/services/`, `/services/water-damage-restoration/`, `/services/mold-remediation/`, `/service-areas/oxnard-ca/`, `/contact/`.

**New issues this month:**
- 5 pages: `has_micromarkup_errors`. Last month DataForSEO did not detect the JSON-LD at all. Now it detects it and finds validation errors.
- 5 inner pages: `lcp-discovery-insight`. This appears now that the hero images actually load.
- `/services/mold-remediation/`, `/contact/`: `forced-reflow-insight`, 32 to 38ms. Minor.
- All pages: `unused-javascript` and `cache-insight`. GA4 `gtag.js` was also on last month's build. These were probably failing then but fell outside last month's top-6 capture per page. They are probably not new.

**Issues resolved since last audit (positive, keep doing this):**
- All 6 pages: `broken_resources` and `errors-in-console` are gone. `/images/hero-bg.webp`, `team.webp` and `services.webp` now return 200.
- All 6 pages: `is-crawlable` is gone. The apex serves no noindex header.
- `/`, `/services/water-damage-restoration/`, `/service-areas/oxnard-ca/`, `/contact/`: `largest-contentful-paint` is no longer flagged. LCP is under 1s everywhere.
- `/`, `/service-areas/oxnard-ca/`: `high_loading_time` is gone.
- `/`: `rankai_word_count_below_target` is gone (1401 words vs 1200 target).
- Logo went from a 1.73 MB PNG to a 58 KB WebP. `image-delivery-insight` savings dropped from about 1,768 KiB to 57 to 185 KiB per page.

## Recommended next actions (priority order)

1. **(template, money pages)** **Give the final breadcrumb its URL in JSON-LD.** On every page except home, the last `ListItem` in `BreadcrumbList` has only `position` and `name`, for example `{"position": 2, "name": "Services"}`. Add `"item": "<canonical URL of the current page>"` to it in the breadcrumb schema component. This is the only structural difference between home (no validation errors) and the other five pages (all have errors), so it is the most likely cause. Google accepts a last crumb without `item`, but the validators that DataForSEO uses do not. After deploying, re-check `/services/` with Google's Rich Results Test and the Schema.org validator to confirm the errors clear. If they do not, pull the exact error through a DataForSEO `on_page` crawl task with microdata enabled. This single change moves 4 of the 5 amber money pages toward green.

2. **(template, accessibility)** **Darken the breadcrumb link color.** Still open from last month. Breadcrumb anchors use `text-dark/50`, which renders as `#888c93` on white at 12px. That is 3.37:1 contrast; WCAG AA needs 4.5:1. It affects every page except home. Change it to `text-dark/70` or darker and confirm the ratio is at least 4.5:1. On `/service-areas/oxnard-ca/`, also change the `text-slate-400` span "· 8 Google reviews" in the reviews card, which is 2.56:1, to `text-slate-600`. These are the only accessibility failures on the site. Fixing them takes the five 95/96 pages to 100.

3. **(money page)** **Fix the home page `<title>` and meta description.** Still open from last month. The live title is the bare brand name (27 characters). `url-plan.json` already plans `California Restoration West | Restoration Services in Ventura, CA`, so the home template is still falling back to `display_name` instead of using the planned title. The planned title has a double space before the pipe, from the trailing space in `display_name`. Once that is removed it is 65 characters, within the limit. Trim the planned meta description from 185 characters to 160 or fewer, for example by dropping "Licensed, insured, IICRC-certified." or shortening the service list. Every other audited page already has a title of 35 to 65 characters and a description of 120 to 137 characters.

4. **(template, performance)** **Add `fetchpriority="high"` to the inner-page hero `<img>`.** Home already has it and gets the fastest LCP render. The shared hero on the other templates (`main > section.relative > div.absolute > img`) has `loading="eager"` but no priority hint. Lighthouse identifies it as the LCP element on all five inner pages. This is a one-attribute change in the hero component.

5. **(template, performance)** **Resize the logo and add a `srcset` to the hero.** `/images/logo.webp` is 1200x1200 (58 KB) but displays at 80 to 96px tall. Export it at 192x192 and set the `width`/`height` attributes to match (they currently read 64x64). `/images/hero-bg.webp` is one 179 KB file used for every screen size. Add 768w and 1280w versions with `srcset` and `sizes="100vw"`. On `/contact/`, the hero strip is only 207px tall, so most of the file is wasted. Desktop scores are already 98 to 100. The real benefit is on mobile, which this audit does not measure.

## Notes / caveats

- **Origin choice.** See "Read this first". The client record should get `apex_cutover.completed_at` (or the cutover tooling should write it) so that next month's audit picks the apex by rule, not by judgment. Also, the `staging` branch alias has not been redeployed since 2026-08-27, so any staging-based QA for this client is looking at stale code.
- **Client status.** `clients/california-restoration-west.json` has `status: "onboarding"`, not `"active"`. The methodology requires active. `build_status` is `pushed_main`, the domain is cut over, and all six URLs returned HTTP 200, so the run went ahead. Flagged, not skipped. The status probably should now be `active`.
- **Structured-data diagnosis is inferred.** DataForSEO's instant-pages endpoint returns the `has_micromarkup_errors` flag but not the error text. The breadcrumb cause is based on the home-vs-inner-page difference. Confirm it with the validator after the fix.
- **`unused-javascript` is GA4.** `https://www.googletagmanager.com/gtag/js?id=G-5DKZE0DK8C` is 156 KB, and about 69 KB of it is unused on first load. It is third-party and needed for analytics. The only lever is loading it with a Partytown worker or after user interaction. Not worth doing while performance is 98 to 100.
- **Google Maps iframe on `/service-areas/oxnard-ca/`.** DataForSEO flags `frame`. This is expected (map embed) and not a defect.
- **Service-area selection.** `url-plan.json` has no `primary: true` area. The primary city (Ventura) maps to `/service-areas/san-buenaventura-ventura-ca/`. `/service-areas/oxnard-ca/` was kept so this month can be compared with the 2026-08-26 baseline. Consider adding `primary: true` to the Ventura area page, or creating `audit-urls.txt`, to settle this permanently.
- **Data hygiene, still open.** `display_name` is `"California Restoration West "` with a trailing space. It still produces double spaces in the logo alt text (`California Restoration West  logo`), the contact hero alt text, and the planned titles.
- **Form factor.** Desktop only, the same as the rest of the fleet. Mobile performance would typically be 10 to 20 points lower. The logo and hero sizes in action 5 matter more on mobile.
- **Cost.** 7 Lighthouse live calls (one exploratory call plus 6 full-data calls at $0.005) and 6 instant-pages calls at $0.0018. About $0.046 total.
