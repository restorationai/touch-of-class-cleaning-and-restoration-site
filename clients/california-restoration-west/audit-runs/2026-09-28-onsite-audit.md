# Onsite Audit - California Restoration West - 2026-09-28

**Live origin audited:** https://staging.rankai-california-restoration-west.pages.dev (staging)
**Site verdict:** amber (was red on 2026-08-26)
**URLs audited:** 6
**Prior audit:** 2026-08-26
**Form factor:** desktop only (Lighthouse 13.4.0, `for_mobile=false`)

---

## Read this first

**1. The SEO score of 69 is a staging artifact, not a site problem.**
`curl -sI` on the staging origin still returns `x-robots-tag: noindex`, which Cloudflare Pages injects on every `*.pages.dev` preview. That fails the Lighthouse `is-crawlable` audit on all six URLs. SEO is recorded as measured but is **excluded from every verdict in this report**. SEO status: inconclusive, re-audit after apex cutover. Do not open a ticket to "fix SEO."

**2. Last month's launch blocker is fixed.**
`/images/hero-bg.webp`, `/images/team.webp` and `/images/services.webp` now return 200. `broken_resources` and `errors-in-console` are gone from all six pages, and Best Practices moved from 96 to 100 everywhere. Four of six pages are now green. The two amber pages are amber because of on-page metadata and a vendor load-time flag, not Lighthouse scores.

---

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 98.3 | +3.6 |
| Accessibility | 96.0 | 0.0 |
| Best Practices | 100.0 | +4.0 |
| SEO | 69.0 (inconclusive) | 0.0 |

Pages by verdict: green 4, amber 2, red 0, error 0

Verdict basis: performance, accessibility, best practices. SEO excluded per caveat 1.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 98 | 100 | 100 | 69* | 1.12s | 0.003 | 0ms |
| `/services/` | services-hub | green | 98 | 95 | 100 | 69* | 1.17s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 98 | 95 | 100 | 69* | 1.07s | 0.024 | 0ms |
| `/services/mold-remediation/` | service-landing | green | 99 | 95 | 100 | 69* | 0.84s | 0.003 | 0ms |
| `/service-areas/oxnard-ca/` | service-area | green | 99 | 95 | 100 | 69* | 0.97s | 0.003 | 0ms |
| `/contact/` | contact | amber | 98 | 96 | 100 | 69* | 0.87s | 0.041 | 0ms |

\* SEO score suppressed by the staging noindex header. Not counted toward any verdict.

INP is null on every page. Lighthouse lab runs do not produce INP without user interaction. This is expected.

## Template-level issues (fix once, lift many pages)

| Issue | Source | Affected URLs | Severity | Recommended fix |
| --- | --- | ---: | --- | --- |
| `color-contrast` | lighthouse | 5 | high | Breadcrumb links still `text-dark/50` (#888c93 on #ffffff, 3.37:1, needs 4.5:1). See action 3. |
| `image-delivery-insight` | lighthouse | 6 | medium | `logo.png` is still a 306 KB 1000x971 PNG shown at about 66x64. See action 2. |
| `unused-javascript` | lighthouse | 6 | low | 69 KiB unused out of 156 KiB in `googletagmanager.com/gtag/js?id=G-5DKZE0DK8C`. Third-party code. See notes. |
| `render-blocking-insight` | lighthouse | 6 | low | `/_astro/_slug_.6yV_ElKU.css`, about 9 KB, 50ms at most. Low value on desktop. |
| `network-dependency-tree-insight` | lighthouse | 6 | low | Chain runs through Google Fonts CSS to `fonts.gstatic.com`. Add `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>`. |
| `lcp-discovery-insight` | lighthouse | 5 | low | Inner-page hero `<img src="/images/hero-bg.webp">` has no `fetchpriority="high"`. See action 4. |

## Money page alerts

- **`/`** (home) - amber. Scores are 98/100/100. Amber because of two metadata issues carried over from last month: the `<title>` is `California Restoration West`, 27 chars, below the 30 to 65 window, and the meta description is 185 chars, above 160.
- **`/contact/`** (contact) - amber. Scores are 98/96/100 and LCP is 0.87s. Amber because DataForSEO flagged `high_loading_time` on two separate calls (page durations 5,467ms and 4,112ms). Lighthouse does not see this: the last network request finishes at about 412ms. Treat it as a vendor-side timing signal worth one manual check, not a confirmed slow page.

## Regressions vs prior audit

**Verdict transitions (all improvements):**
- `/services/`, `/services/water-damage-restoration/`, `/services/mold-remediation/`, `/service-areas/oxnard-ca/`: red to green. The 404 image assets now resolve.
- `/` and `/contact/`: red to amber. The 404s are fixed, but the metadata issues (home) and vendor load-time flag (contact) remain.

**Metric regression flagged by the rules (explained, not a real slowdown):**
- `/services/` LCP went from 0.50s to 1.17s (+666ms). Last month the hero image returned 404, so LCP was measured on text. Now the real 1350x392 hero image is the LCP element. The page is still well under the 2.5s "good" threshold. Action 4 recovers some of this.

No category score dropped on any URL. Site averages rose or held in every category.

**New issues this month:**
- All 6 pages: `unused-javascript`. This comes from the GA4 `gtag.js` tag. The fix and the trade-off are in the notes.
- `/services/`, `/services/water-damage-restoration/`, `/services/mold-remediation/`, `/service-areas/oxnard-ca/`, `/contact/`: `lcp-discovery-insight`. This showed up now because the hero image loads and has become the LCP element.
- `/services/water-damage-restoration/`, `/service-areas/oxnard-ca/`, `/contact/`: `network-dependency-tree-insight` (Google Fonts request chain).
- `/service-areas/oxnard-ca/`: `render-blocking-insight` (same 9 KB Astro stylesheet as the other pages).
- `/contact/`: `high_loading_time` (DataForSEO, see money page alerts).

**Issues resolved since last audit (positive, keep doing this):**
- All 6 pages: `broken_resources` and `errors-in-console` no longer appear. The hero, team and services images are published.
- `/`, `/services/water-damage-restoration/`, `/service-areas/oxnard-ca/`, `/contact/`: `largest-contentful-paint` no longer fails.
- `/`, `/service-areas/oxnard-ca/`: `high_loading_time` did not reproduce.
- `/`: `rankai_word_count_below_target` is resolved. The home page has 1,359 words against a 1,200 target.
- The logo went from 1.81 MB to 306 KB. `image-delivery-insight` severity dropped from high to medium.

## Recommended next actions (priority order)

1. **(money page)** **Fix the home page title and meta description.** The home template still renders the bare brand name as `<title>`. The planned title in `plan/url-plan.json` is `California Restoration West  | Restoration Services in Ventura, CA`, which includes a double space from the trailing space in `display_name`. Trim `display_name` in `clients/california-restoration-west.json` to `California Restoration West`. Then fix the home template so it uses the url-plan `title` instead of falling back to the brand. Cut the planned home `meta_description` (185 chars) to 160 or fewer, for example by dropping "Licensed, insured, IICRC-certified." The trailing space also shows up as `West  ` 3 to 9 times per page in alt text and JSON-LD.

2. **(template, all 6 pages)** **Finish shrinking `/images/logo.png` and the favicon.** The logo is a 306,109-byte PNG with intrinsic size 1000x971. It renders at about 66x64 in the header (with `width="36" height="36"` attributes) and about 82x80 in the footer. Export a WebP at 164x160 (2x the footer size). It should come in under 15 KB and remove about 300 KB per page view. Set the `width`/`height` attributes to the real aspect ratio. Also, `/favicon.svg` is 97,926 bytes because it is an SVG wrapper around a base64 512x512 PNG. Replace it with a real vector SVG or a 32x32 PNG/ICO. Together these save about 400 KB on every page. On mobile this matters far more than the desktop scores suggest.

3. **(template, accessibility)** **Darken the breadcrumb link color.** This is unchanged since last month. The breadcrumb anchors use `text-dark/50`, which computes to `#888c93` on `#ffffff` at 12px, a 3.37:1 ratio against the 4.5:1 WCAG AA minimum. It is the only accessibility failure on the site and holds five pages at 95 to 96. Switch to `text-dark/70` or darker, and check with any contrast tool before redeploying.

4. **(template, performance)** **Prioritize and right-size the inner-page hero.** On `/services/`, `/contact/`, and the service and area templates, the hero is `<img src="/images/hero-bg.webp" loading="eager">` with no `fetchpriority="high"`. Add it (the home template already has it). The same 179 KB, full-size file also serves a 1350x207 strip on `/contact/`, and Lighthouse estimates 128 KiB of waste there. Add a `srcset` with 768w/1350w derivatives at a higher compression factor.

5. **(environment)** **Cut over the apex domain and re-audit.** SEO findings are deferred, not resolved. Last month's blocker (the missing images) is cleared, so cutover can go ahead once actions 1 and 2 ship. The canonicals already point at `https://californiarestorationwest.com/`. They can't be validated until the apex serves the site. Re-run this audit against the apex right after cutover.

## Notes / caveats

- **Client status.** `clients/california-restoration-west.json` still has `status: "onboarding"`, not `"active"`. `build_status` is `pushed_main` and all six URLs returned HTTP 200, so the run went ahead. Flagged rather than skipped, same as last month.
- **`high_loading_time` reproducibility rule.** The first instant_pages pass flagged `/services/`, `/services/water-damage-restoration/`, `/service-areas/oxnard-ca/` and `/contact/`. A second pass on those four reproduced the flag only on `/contact/`. Lighthouse LCP is between 0.84s and 1.17s on every page. This run counts the vendor flag only when it reproduces. That means the "resolved" items for `/` and `/service-areas/oxnard-ca/` partly reflect the stricter rule, not only site changes.
- **Schema is present.** DataForSEO returned no micromarkup signal. Checked directly against the served HTML: every page ships parseable JSON-LD with `LocalBusiness`. Inner pages add `BreadcrumbList` and `FAQPage`. Service landings add `Service` and `AdministrativeArea`. No missing-schema defect. Alt text coverage is 100% on all six pages, and there is no mixed content.
- **Canonicals are correct.** All six point at `https://californiarestorationwest.com/...`. From staging that is technically an offsite canonical, but it is the intended production target.
- **`unused-javascript` is GA4.** All 69 KiB comes from `gtag.js`, which is third-party code that we can't tree-shake. Removing it would lose analytics. The low-cost option is to load it after first interaction or on `requestIdleCallback`, at the cost of missing very short sessions. Leave as-is unless mobile performance becomes a problem after cutover.
- **Google Maps caching on `/service-areas/oxnard-ca/`** (`cache-insight`, about 19 KiB) comes from Google-set cache headers. Not actionable.
- **`/services/` word count** is 753 against an 800 target, 6% under. Low severity. Adding one short paragraph to the hub intro clears it.
- **URL selection.** There is no `audit-urls.txt`. The URL set was auto-derived from `plan/url-plan.json` and is identical to the 2026-08-26 baseline. No service area has `primary: true`, and the client record has no `business.address.city`, so the first area slug (`/service-areas/oxnard-ca/`) was kept for comparability.
- **Cost.** 6 Lighthouse live calls and 10 instant_pages calls (including the 4 reproducibility re-checks) cost $0.081. One extra headline Lighthouse probe added about $0.005. Well under the $0.30 target.
