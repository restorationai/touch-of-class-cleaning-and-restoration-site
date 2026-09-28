# Onsite Audit - California Restoration West - 2026-09-28

**Live origin audited:** https://staging.rankai-california-restoration-west.pages.dev (staging)
**Site verdict:** amber (was red on 2026-08-26)
**URLs audited:** 6
**Prior audit:** 2026-08-26
**Form factor:** desktop only (Lighthouse 13.4.0, `for_mobile=false`)

---

## Read this first

**1. SEO is inconclusive: staging noindex artifact, re-audit after apex cutover.**
`curl -sI` on the staging origin still returns `x-robots-tag: noindex`, which Cloudflare Pages injects on every `*.pages.dev` preview. That fails the Lighthouse `is-crawlable` audit and holds SEO at 69 on all six URLs. SEO is recorded in the state file but **excluded from every verdict below**. Do not open a ticket to "fix SEO."

**2. The launch blocker from August is fixed.**
Last month every page was red because `/images/hero-bg.webp`, `/images/team.webp` and `/images/services.webp` returned 404. All three now return 200, `broken_resources` and `errors-in-console` are gone on all six pages, and best practices went from 96 to 100 sitewide. Nothing on the site is red any more. What is left is amber-level cleanup: the logo file, a breadcrumb contrast token, a missing `fetchpriority` hint, a schema validator warning, and the homepage title, meta description and FAQ schema.

---

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 97.8 | +3.1 |
| Accessibility | 96.0 | 0.0 |
| Best Practices | 100.0 | +4.0 |
| SEO | 69.0 (inconclusive) | 0.0 |

Pages by verdict: green 0, amber 6, red 0, error 0

Verdict basis: performance, accessibility, best practices. SEO excluded per caveat 1. Every counted Lighthouse score is 95 or higher, so all six pages would be green on scores alone. They are amber only because of medium-severity on-page issues.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 98 | 100 | 100 | 69* | 1.13s | 0.003 |
| `/services/` | services-hub | amber | 98 | 95 | 100 | 69* | 1.15s | 0.002 |
| `/services/water-damage-restoration/` | service-landing | amber | 98 | 95 | 100 | 69* | 1.05s | 0.024 |
| `/services/mold-remediation/` | service-landing | amber | 98 | 95 | 100 | 69* | 1.10s | 0.003 |
| `/service-areas/oxnard-ca/` | service-area | amber | 98 | 95 | 100 | 69* | 1.12s | 0.003 |
| `/contact/` | contact | amber | 97 | 96 | 100 | 69* | 1.19s | 0.002 |

\* SEO held down by the staging noindex header. Not counted toward any verdict.

TBT is 0ms on every page. INP is null on every page because Lighthouse lab runs do not produce INP without user interaction. That is expected, not missing data.

## Template-level issues (fix once, lift many pages)

| Issue | Source | Affected URLs | Severity | Recommended fix |
| --- | --- | ---: | --- | --- |
| `image-delivery-insight` | lighthouse | 6 | high | Replace `/images/logo.png` (306 KB, 1000x971 PNG shown at 66x64). See action 2. |
| `unused-javascript` | lighthouse | 6 | medium | GA4 `gtag/js?id=G-5DKZE0DK8C`, 159 KB, about 44% unused. See action 5. |
| `render-blocking-insight` | lighthouse | 6 | low | `/_astro/_slug_.6yV_ElKU.css`, about 9 KB. Only Oxnard shows a measurable cost (53ms). Leave it. |
| `color-contrast` | lighthouse | 5 | medium | Breadcrumb `a.text-dark/50` is 3.37:1. See action 3. |
| `lcp-discovery-insight` | lighthouse | 5 | medium | Hero `<img>` lacks `fetchpriority="high"` on every non-home template. See action 4. |
| `has_micromarkup_errors` | dataforseo_onpage | 5 | medium | Flags only on pages that have BreadcrumbList. See action 4. |

## Money page alerts

All five money pages are amber. None are red. Their Lighthouse scores are all 97 to 98 performance and 95 to 100 accessibility, so this is on-page and schema cleanup, not a conversion emergency.

- **`/`** (home) - amber. Title is `California Restoration West`, 27 chars (below 30). Meta description is 185 chars (above 160, will truncate). The page renders a "Frequently Asked Questions" section with 5 items but ships no `FAQPage` JSON-LD. Only `Organization`, `WebSite` and `LocalBusiness` are present. The August build had `FAQPage` and `BreadcrumbList` on home, so FAQ schema was dropped in a rebuild.
- **`/services/`** (services-hub) - amber. `has_micromarkup_errors`. Also 753 words against an 800 target (low).
- **`/services/water-damage-restoration/`** (service-landing) - amber. `has_micromarkup_errors`, plus hero not priority-hinted and breadcrumb contrast.
- **`/services/mold-remediation/`** (service-landing) - amber. Same as water damage.
- **`/contact/`** (contact) - amber. `has_micromarkup_errors`. The hero `hero-bg.webp` is shown in a 1350x207 strip but ships at 179 KB. Lighthouse estimates 131 KB of it is wasted on this page.

## Regressions vs prior audit

**Verdict transitions (all improvements):**
- All six URLs went red to amber: `/`, `/services/`, `/services/water-damage-restoration/`, `/services/mold-remediation/`, `/service-areas/oxnard-ca/`, `/contact/`. No page got worse.

**Score changes per URL:** performance +6 on `/`, water damage and Oxnard, +5 on contact, and -2 on `/services/` and mold remediation (100 to 98). Best practices +4 everywhere. Accessibility is unchanged. No category dropped by 5 points or more on any URL, and no site average dropped by 3 or more.

**Flagged metric regressions (2), both expected:**
- `/services/`: LCP went from 0.50s to 1.15s (+647ms).
- `/services/mold-remediation/`: LCP went from 0.81s to 1.10s (+289ms).
These are not real slowdowns. In August the hero image 404ed, so the LCP element was a text block that painted instantly. Now the real hero image loads and becomes the LCP element. Both values are well under the 2.5s "good" threshold. On the other four pages LCP improved by 672 to 823ms because the logo payload dropped from 1.73 MB to 306 KB.

**New issues this month:**
- All 6 pages: `unused-javascript`. The GA4 tag `G-5DKZE0DK8C` was added since August. It is the only third-party script on the site.
- 5 non-home pages: `lcp-discovery-insight`. The hero image now exists and is the LCP element, but only the homepage template sets `fetchpriority="high"` on it.
- 5 non-home pages: `has_micromarkup_errors` (DataForSEO structured-data validator).
- `/`: `rankai_faqpage_schema_missing`. The FAQ section renders but its JSON-LD is gone.
- `/service-areas/oxnard-ca/`: `render-blocking-insight`, 53ms. It probably existed last month below the top-issue cutoff.

**Issues resolved since last audit (keep doing this):**
- All 6 pages: `broken_resources` and `errors-in-console`. The missing hero, team and services images are published.
- `/`, water damage, Oxnard, contact: `largest-contentful-paint` no longer fails. LCP is 1.05 to 1.19s everywhere.
- `/` and `/service-areas/oxnard-ca/`: `high_loading_time` cleared.
- `/service-areas/oxnard-ca/`: `cache-insight` (Google Maps TTLs) no longer flagged.
- `/`: `rankai_word_count_below_target` cleared. Now 1,359 words against a 1,200 target.
- The logo went from 1,811,735 bytes to 306,109 bytes. It is still flagged (action 2), but the waste is down 83%.

## Recommended next actions (priority order)

1. **(money page, homepage)** **Fix the home `<title>`, meta description and FAQ schema in one pass.** The title renders as the bare brand name, `California Restoration West` (27 chars). `url-plan.json` has the planned title `California Restoration West  | Restoration Services in Ventura, CA`, which is 66 chars because the trailing space on `display_name` puts a double space before the pipe. The home template is still falling back to `display_name` instead of reading the plan value, so wire it to the plan. Trimming the `display_name` space brings the planned title to exactly 65 chars. Cut the 185-char meta description to 160 or fewer at the plan level. Then put the `FAQPage` JSON-LD back on home, built from the same 5 questions the page already renders in its `<details>` items. Every other template already emits `FAQPage`, so the home layout is simply not calling the schema component.

2. **(template, high)** **Replace `/images/logo.png` with a correctly sized WebP.** The current file is a 306,109-byte 1000x971 PNG, displayed at about 66x64 in the header (`img.h-14`) and again in the footer (`img.h-16`) on all six pages. Lighthouse estimates 305 KB wasted per page. Export a 132x128 WebP (2x DPR, probably under 10 KB), and fix the `width="36" height="36"` attributes, which match neither the intrinsic nor the rendered size. While you are there, change `loading="eager"` on the footer copy to `loading="lazy"`. Also point `LocalBusiness.image`, `LocalBusiness.logo` and `Organization.logo.url` in the JSON-LD at an absolute URL. They are currently the relative path `/images/logo.png`.

3. **(template, accessibility)** **Darken the breadcrumb link token.** Breadcrumb anchors use `text-dark/50`, which computes to `#888c93` on `#ffffff` at 12px. That is 3.37:1 against the WCAG AA minimum of 4.5:1. This is the only accessibility failure on 5 of 6 pages, and it was already flagged in August. Change it to `text-dark/70` or darker and re-check. On `/service-areas/oxnard-ca/`, also change `span.text-slate-400` ("7 Google reviews" in the reviews card, 2.56:1) to `text-slate-600`.

4. **(template, money pages)** **Add `fetchpriority="high"` to the hero `<img>` on the section-hero template, and complete the BreadcrumbList.** The homepage hero already has `fetchpriority="high"`. The hero component used by `/services/`, service landings, service areas and contact renders `<img ... loading="eager">` without it, so copy the attribute across. In the same layout, the final `ListItem` in `BreadcrumbList` has no `item` URL. For example, on `/services/` the list is `{"position": 2, "name": "Services"}`. DataForSEO's validator flags `has_micromarkup_errors` on exactly the 5 pages that carry BreadcrumbList and not on home, which has none. Add `"item": "<canonical URL of the current page>"` to the last element to clear the warning. Google tolerates the omission, but this is a one-line fix.

5. **(environment)** **Cut over the apex domain and re-audit.** SEO findings are deferred, not resolved. The August blocker (404 images) is fixed, so the remaining items above are not launch blockers. Actions 1 and 2 are worth doing first because the homepage title and FAQ schema are what Google and AI answers read on day one. When you re-audit on the apex, also check how GA4 is loaded. The `unused-javascript` flag (69 KB of the 159 KB gtag bundle unused) costs 50 to 200ms of estimated LCP on desktop. Load gtag after `window.load` or through Partytown, rather than removing analytics.

## Notes / caveats

- **Client status.** `clients/california-restoration-west.json` still has `status: "onboarding"`, not `"active"`. The methodology gates on active. `build_status` is `pushed_main` and all six URLs returned HTTP 200, so the run went ahead. Flagging this rather than silently skipping.
- **Micromarkup error detail is inferred.** DataForSEO `instant_pages` returns the `has_micromarkup_errors` flag but not the error text. The cause named in action 4 (breadcrumb final item without `item`) is inferred from which pages are flagged. The relative logo URLs appear on home too, which is not flagged, so they are not the trigger. If the flag survives action 4, run the page through the Schema.org validator.
- **Schema otherwise verified.** Service landings ship `Service`, `LocalBusiness`, `FAQPage` and `BreadcrumbList`. The hub, area and contact pages ship `Organization`, `WebSite`, `LocalBusiness`, `FAQPage` and `BreadcrumbList`. JSON-LD is split across separate `<script>` blocks now instead of one graph. That is fine.
- **Canonicals are correct.** All six point at `https://californiarestorationwest.com/...`. From staging that is technically an offsite canonical, but it is the intended production target and is not counted as a defect.
- **URL selection.** There is no `audit-urls.txt`, so the six URLs were auto-derived from `plan/url-plan.json`. The set is identical to August's, so every URL has a delta. Water damage and mold remediation tie for the highest service-landing priority (9.0). There is no `primary: true` service area, and the home city (Ventura) has no dedicated area page, so the run fell back to the first area, `/service-areas/oxnard-ca/`.
- **Comparison method.** The August run stored only the top failing audits per URL. A "new" issue this month may have existed below last month's cutoff (most likely Oxnard `render-blocking-insight`). Resolved issues were checked against this run's full failing-audit list, so none of them are false positives.
- **Data hygiene, still open from August.** `display_name` is `"California Restoration West "` with a trailing space. It still produces a double space in the logo alt text (`California Restoration West  logo`), `LocalBusiness.name`, and the contact hero alt text. `streetAddress` in the schema is `363 mackay ave ` (lowercase, trailing space). Trim both at the client-record level.
- **Desktop only.** Mobile performance would typically run 10 to 20 points lower. The logo and GA4 costs matter more on mobile than these desktop numbers suggest.
- **Cost.** 6 Lighthouse live calls ($0.005 each) plus 6 instant-pages calls ($0.0018 each), $0.04 total. No failed or retried calls.
