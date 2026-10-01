# Onsite Audit, All Pro Plumbing Heating and Air, 2026-10-01

**Live origin audited:** https://allproplumbingheatingandair.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-31
**Lighthouse:** v13.4.0, DESKTOP form factor

## Read this first

**Last month's biggest problem is fixed.** The wrong-business `sameAs` links are gone. The LocalBusiness and Organization blocks now emit `sameAs: []` on all 6 pages, so the site no longer tells Google it is the same company as the Oceanside CA and Ontario CA businesses. That was the highest business-impact item in the August report.

**The site is still amber for the same reason as August.** No page has a performance or ranking problem. Every Lighthouse category is 91 or higher on every page, and Core Web Vitals sit well inside "good". All 6 pages stay amber because two LocalBusiness schema defects are still live sitewide (empty strings and relative image URLs), and 5 pages still carry the DataForSEO FAQPage micromarkup flag. Fix the schema block once and most of the amber goes away.

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 98.7 | +0.2 |
| Accessibility | 93.5 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | 0.0 |

Pages by verdict: green 0, amber 6, red 0, error 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 98 | 93 | 100 | 100 | 1.03s | 0.017 | 0ms |
| `/services/` | services-hub | amber | 98 | 91 | 100 | 100 | 1.07s | 0.022 | 0ms |
| `/services/emergency-plumbing/` | service-landing | amber | 99 | 95 | 100 | 100 | 1.03s | 0.018 | 0ms |
| `/services/drain-cleaning/` | service-landing | amber | 99 | 95 | 100 | 100 | 0.96s | 0.005 | 0ms |
| `/service-areas/oildale-ca/` | service-area | amber | 99 | 95 | 100 | 100 | 0.83s | 0.005 | 0ms |
| `/contact/` | contact | amber | 99 | 92 | 100 | 100 | 0.88s | 0.006 | 0ms |

TBT dropped to 0ms on every page (emergency-plumbing was 98ms and Oildale 65ms in August). LCP improved on 5 of 6 pages. Only the homepage got slower; see Regressions.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `schema_localbusiness_empty_required_fields` | 6 | medium | Stop emitting `""` for `streetAddress`, `postalCode`, `geo.latitude`, `geo.longitude`, `foundingDate`. Populate or omit |
| `schema_localbusiness_relative_image_url` | 6 | medium | LocalBusiness `image`/`logo` and Organization `logo.url` are `/images/logo.webp`. Make them absolute |
| `image-delivery-insight` | 6 | low | `logo.webp` is 107,502 bytes with 103,120 wasted on every page. Interior heroes ship the full 203KB `hero-bg.webp` with no `srcset` |
| `has_render_blocking_resources` | 6 | low | `_astro/_slug_.CZs0raQ6.css` (about 9KB) blocks render, 50-60ms |
| `no_image_title` | 6 | low | Cosmetic only. Alt coverage is fine. Safe to ignore |
| `color-contrast` | 5 | medium | Breadcrumb `a.text-dark/50` is #878b95 on #ffffff (3.41:1). `btn-accent` is #ffffff on #ef4444 (3.76:1). Both need 4.5:1 |
| `has_micromarkup_errors` | 5 | medium | DataForSEO flags every page carrying the FAQPage block. Confirm in Google's Rich Results Test first, see caveats |
| `unused-javascript` | 5 | low | GA4 `gtag/js`, about 70KB unused. Third-party, low priority |
| `link-in-text-block` | 3 | medium | Body links are 1.6:1 against surrounding text with no underline (`div.prose-body > p > a`, home `section.bg-white p > a`) |
| `lcp-discovery-insight` | 3 | low | Interior hero `<img>` lacks `fetchpriority="high"` (home already has it) |
| `low_content_rate` | 3 | low | Text-to-HTML ratio on `/`, `/services/`, `/contact/` |
| `render-blocking-insight` | 3 | low | Same Astro CSS file as `has_render_blocking_resources` |
| `meta_description_length_off` | 2 | medium | `/` is 170 chars, `/services/` is 173. Target 70-160 |
| `forced-reflow-insight` | 2 | low | A script reads layout after a DOM write on emergency-plumbing and Oildale. Minor |
| `network-dependency-tree-insight` | 2 | low | Informational, follows from the render-blocking CSS |

## Money page alerts

All 5 money pages are amber. As in August, the cause is the shared schema block plus accessibility contrast, not page speed.

- **`/`** (home), amber. Perf 98, a11y 93, LCP 1.03s, up 406ms from August. Meta description is 170 chars (trim to 160 or under). Word count 1173 against a 1200 target. Schema empty and relative values.
- **`/services/`** (services-hub), amber. Perf 98, a11y 91 (lowest on the site, breadcrumb contrast plus prose link contrast). Meta description 173 chars. `hero-bg.webp` wastes 111,678 bytes here.
- **`/services/emergency-plumbing/`** (service-landing), amber. Perf 99, LCP 1.03s. New `color-contrast` failure on the red "Call now" button (`a.btn-accent`, white on #ef4444, 3.76:1). FAQPage micromarkup flag.
- **`/services/drain-cleaning/`** (service-landing), amber. Perf 99, LCP 0.96s. Same `btn-accent` contrast failure and FAQPage flag.
- **`/contact/`** (contact), amber. Perf 99, a11y 92, LCP 0.88s (improved 116ms). `hero-bg.webp` wastes 138,775 bytes here, the most of any page. Title 53 chars, description 140 chars, canonical correct, zero broken links.

## Regressions vs prior audit

**Verdict transitions:** none. All 6 pages were amber in August and remain amber.

**Category regressions (5+ point drop):** none. The largest category move is homepage performance 100 to 98.

**Core Web Vitals regressions:**
- `/` LCP 627ms to 1033ms (+406ms). Still well under the 2.5s "good" line. Lighthouse now measures `hero-bg.webp` at 203,246 bytes, up from 167,726 bytes in August, so the hero image file was re-exported larger. The homepage `<img>` now has `srcset` and `fetchpriority="high"` (good), but desktop still picks the full 1376w file. Re-compress it.

**New issues this month (on-page, reliable):**
- `/contact/`: `low_content_rate` (text-to-HTML ratio). Low severity.

**New issues this month (Lighthouse, lower confidence):**
- `/services/`, `/services/emergency-plumbing/`, `/contact/`: `render-blocking-insight` (same Astro CSS file already flagged by DataForSEO on all 6 pages)
- `/services/emergency-plumbing/`, `/service-areas/oildale-ca/`: `forced-reflow-insight`
- `/services/drain-cleaning/`: `network-dependency-tree-insight`
- `/`: `cache-insight` (scored 0.5 with 0KB estimated savings, effectively noise)

These compare against August's top-5 capture only, so an audit that already failed below rank 5 in August can appear here without a real change. The one confirmed new Lighthouse finding is the `btn-accent` contrast failure inside `color-contrast` on emergency-plumbing, drain-cleaning and Oildale (August named only the breadcrumb).

**Issues resolved since last audit:** (positive, keep doing this)
- All 6 pages: `schema_sameas_entity_mismatch` is gone. `sameAs` is now an empty array.
- `/`, `/services/`: `high_loading_time` no longer flagged by DataForSEO.
- `/services/drain-cleaning/`: `forced-reflow-insight` no longer fails.
- `/`: hero now carries `fetchpriority="high"` and a `srcset`, and `lcp-discovery-insight` passes on the homepage.
- All pages: TBT is 0ms everywhere.

## Recommended next actions (priority order)

1. **(template, money pages, schema correctness)** Fix the shared LocalBusiness block. It still emits `streetAddress: ""`, `postalCode: ""`, `geo.latitude: ""`, `geo.longitude: ""` and `foundingDate: ""` on all 6 pages. Empty strings are invalid (`geo` expects numbers). Either populate `streetAddress` and `postalCode` from the GBP address in `nap-audit.json` (3556 Bowman Ct suite C, Bakersfield, CA 93308) if the client is not a hidden-address SAB, or drop the `streetAddress`, `postalCode`, `geo` and `foundingDate` keys entirely. In the same block, change LocalBusiness `image` and `logo` and the Organization `logo.url` from `/images/logo.webp` to `https://allproplumbingheatingandair.com/images/logo.webp`. This one edit clears the two schema template issues on every page of the site.

2. **(template, money pages, performance)** Shrink the two oversized images. `/images/logo.webp` is still 107,502 bytes rendered about 56px tall, with 103,120 bytes wasted on every page (unchanged since August). Export it at about 112px tall for 2x retina, target under 10KB. `hero-bg.webp` grew to 203,246 bytes: re-compress it (quality 70-75 should land near 100KB), and give the interior hero `<img>` on `/services/`, `/contact/` and `/service-areas/*` the same `srcset`, `sizes="100vw"` and `fetchpriority="high"` the homepage hero already has. That removes 111-139KB per interior page and reverses the homepage LCP regression.

3. **(template, accessibility, money pages)** Fix three contrast failures in the layout CSS. (a) Breadcrumb links: change `text-dark/50` to `text-dark/70` or darker (currently #878b95 on white, 3.41:1). (b) The red `btn-accent` call button: darken the background from #ef4444 to about #dc2626 (Tailwind red-600, 4.8:1 with white text) or #b91c1c. (c) Add `text-decoration: underline` to `.prose-body a` and the home `section.bg-white p a` so links do not rely on color alone (`link-in-text-block`, 1.6:1). This lifts accessibility on all 6 pages and moves `/services/` off its site-low 91.

4. **(money pages, on-page)** Trim the meta descriptions on `/` (170 chars) and `/services/` (173 chars) to 155-160 characters. Both are in the page frontmatter, so it is a two-line content edit.

5. **(verify before building)** Run `/services/emergency-plumbing/` through Google's Rich Results Test to confirm whether the `has_micromarkup_errors` flag on the FAQPage block is real. August's manual inspection found the FAQPage JSON-LD structurally valid. If Google reports it clean, mark this as a known DataForSEO validator false positive and stop tracking it.

## Notes and caveats

- **Apex audited, so SEO counts.** This run hit the production apex. SEO scored 100 on all 6 pages and counted toward every verdict. No `x-robots-tag` header is set. HSTS (`max-age=31536000; includeSubDomains`) and `x-content-type-options: nosniff` are present, and no `http://` resources are referenced.
- **Desktop only.** Lighthouse ran with `for_mobile=false` to stay comparable with July and August. Mobile scores typically run 10 to 20 performance points lower and were not measured.
- **Tooling.** This MCP build exposes only the generic `dataforseo api_request` tool, so calls went directly to `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` with responses parsed on disk. Full Lighthouse detail was captured. All 12 calls succeeded first try. API cost about $0.04.
- **Schema issue IDs.** `schema_localbusiness_*` are Rank AI findings from parsing the served JSON-LD directly, kept from August for continuity. They are not native DataForSEO check IDs. Every other on-page ID is a native DataForSEO check.
- **Same URL set as August.** Service-area slot stays `/service-areas/oildale-ca/` (url-plan's first area slug, no `primary: true` entry). Service landings are the first two of four priority-9.0 ties in url-plan order.
- **Clean basics.** Across all 6 pages: zero broken links, zero broken resources, no duplicate titles or descriptions, exactly one H1 each, correct self-referencing canonicals, titles 48-64 chars. Word counts beat plan targets everywhere except `/` (1173 against 1200).
- **Load time spread.** DataForSEO page load times ranged from 336ms (`/services/`) to 1,659ms (`/services/drain-cleaning/`). None crossed DataForSEO's `high_loading_time` threshold, but if drain-cleaning stays slow next month, look at it.
