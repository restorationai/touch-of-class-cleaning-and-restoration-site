# Onsite Audit - Dry County Restoration - 2026-09-28

**Live origin audited:** https://staging.rankai-dry-county-restoration.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26 (red)
**Form factor:** desktop only (see caveats)

## Staging environment caveat (SEO score excluded from verdict)

The audited origin is a Cloudflare Pages preview and returns `x-robots-tag: noindex`. The Lighthouse `is-crawlable` audit fails on all 6 URLs and holds the SEO category at 69.

**SEO score: inconclusive. This is a staging noindex artifact, re-audit after apex cutover.** The verdict below uses Performance, Accessibility, and Best Practices only.

## Headline: last month's blocker is fixed

The `https://None` canonical defect from the 2026-08-26 audit is gone. `domain` is now set in the client record, and every audited page ships:

- `<link rel="canonical" href="https://drycountyrestoration.com/...">`
- a matching `og:url`
- JSON-LD `url` of `https://drycountyrestoration.com`

That removes all 12 high-severity findings and moves the site from red to amber. The one amber page is the homepage, and the only reason is a meta description that runs too long.

One cutover dependency to know: `https://drycountyrestoration.com/` currently returns 301 to `https://www.drycountyrestoration.com/` (the client's pre-cutover site). The new build canonicalises to the bare apex. So at cutover the new site must be served on the bare apex with `www` redirecting to it, not the other way round. Otherwise every canonical points at a redirect.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.2 | -0.8 |
| Accessibility | 95.3 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 69.0 (inconclusive) | 0.0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 96 | 96 | 100 | 69 | 1.22s | 0.002 | 0ms |
| `/services/` | services-hub | green | 99 | 95 | 100 | 69 | 1.04s | 0.003 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 98 | 95 | 100 | 69 | 1.05s | 0.030 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 69 | 1.01s | 0.030 | 0ms |
| `/service-areas/riverside-ca/` | service-area | green | 99 | 95 | 100 | 69 | 1.03s | 0.004 | 0ms |
| `/contact/` | contact | green | 98 | 96 | 100 | 69 | 1.05s | 0.027 | 0ms |

All Core Web Vitals pass comfortably on desktop. Every page has LCP of 1.22s or less, CLS no higher than 0.030, and TBT of zero.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | medium | `/images/logo.png` (245KB PNG, 598x600, displayed at 96x96) is still the biggest cost at 244KiB of the 245 to 328KiB avoidable per page. Export a 192x192 WebP and point `logoUrl` in `src/lib/brand.ts` at it. |
| `unused-javascript` | 6 | medium | New this month. `gtag/js?id=G-211581WVBQ` (156KiB, 69KiB unused) now loads on every page from `src/components/Analytics.astro`. It is already `async`. Delay injection until first user interaction or `requestIdleCallback` so it leaves the critical window. |
| `color-contrast` | 6 | medium | Unchanged. Brand primary `#007fb2` on white measures 4.48:1 against 4.5:1 on the footer phone, email, `/services/` and `/emergency/` links. Darken `DEFAULT` in `tailwind.config.mjs` to about `#00719e`. On interior pages, the `text-dark/50` breadcrumb link in `src/components/Breadcrumb.astro` measures 3.37:1 (`#888c93`) and needs about `text-dark/70`. |
| `render-blocking-insight` | 6 | low | Single 8.9KB stylesheet `_astro/_slug_.Dq2ycaMD.css`, about 50ms. No action. |
| `lcp-discovery-insight` | 5 | low | Interior pages render the hero as an inline `<img src="/images/hero-bg.webp" loading="eager">` without `fetchpriority="high"`. Add it in `src/pages/services/[slug].astro`, `src/pages/service-areas/[area].astro` and the contact and services index pages. The homepage `Hero.astro` already has it, which is why `/` passes. |
| `has_micromarkup_errors` | 5 | low | DataForSEO's schema.org validator flags every FAQPage `Question` for a missing `answerCount` (error) and `text` (warning). Google's FAQPage rich result does not require either field (they belong to QAPage), so this is a validator false positive. Optional: add `"answerCount": 1` to each Question in the FAQ schema builder to clear the flag. |

`is-crawlable` also fails on all 6 pages. It is the staging noindex artifact described above and needs no action.

## Money page alerts

- **`/`** (home) - verdict: amber. Meta description is 178 characters (target 70 to 160), so Google will truncate it in the SERP. Lighthouse is healthy: Perf 96, A11y 96, BP 100, LCP 1.22s.

The other four money pages (`/services/`, both service landings, `/contact/`) are green.

## Regressions vs prior audit

**Verdict transitions:** all 6 URLs went red to green, except `/`, which went red to amber. Every transition is an improvement.

**Score regressions (5+ points):** none. The largest drop is Performance on `/`, 99 to 96.

**Core Web Vitals regressions:**
- `/`: LCP rose from 0.93s to 1.22s (+286ms, above the 200ms threshold). It is still well inside the 2.5s "good" band. The timing matches the new GA4 `gtag.js` load competing with the hero image. Deferring gtag (action 3) should recover it.

**New issues this month:**
- All 6 pages: `unused-javascript`. GA4 `gtag.js` was added site-wide, with 66 to 69KiB unused per page.
- `/services/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`, `/service-areas/riverside-ca/`, `/contact/`: `has_micromarkup_errors`. Validator false positive on the FAQPage `answerCount` field, as described above. Last month's report called the JSON-LD error-free, so either the validator got stricter or last month's run did not catch it. The FAQ markup itself is unchanged.

**Issues resolved since last audit:** (positive, keep doing this)
- All 6 pages: `rankai_canonical_unresolvable_host` no longer flagged. Canonical and og:url now resolve to `https://drycountyrestoration.com/...`.
- All 6 pages: `rankai_schema_url_unresolvable_host` no longer flagged. JSON-LD `url` is correct.

## Recommended next actions (priority order)

1. **(money page)** Shorten the homepage meta description from 178 characters to 150 to 158. Only `/` is over, and it is the sole reason the site is amber rather than green. Edit the home entry `meta_description` in `plan/url-plan.json` (or its page source) and rebuild.
2. **(cutover dependency)** At apex cutover, serve the new site on the bare `drycountyrestoration.com` and 301 `www` to it. Today the apex redirects to `www`, which would make every canonical point at a redirect. Re-run this audit right after cutover to get a real SEO score.
3. **(template, new this month)** Defer GA4 in `src/components/Analytics.astro`: inject the `gtag/js` script on first scroll, click, or keydown, or in `requestIdleCallback`, instead of in the head. This removes 69KiB of unused JS from the critical path on every page and should bring home LCP back toward last month's 0.93s. Keep the `click_to_call` event binding intact.
4. **(template, every page)** Replace `/images/logo.png` with a 192x192 WebP, and fix its `width`/`height` attributes to match the 96x96 render size. This saves about 244KiB per page load site-wide. It was carried over from last month and is still the single biggest byte saving.
5. **(template, accessibility)** Darken brand primary `#007fb2` to `#00719e` in `tailwind.config.mjs`, and raise the breadcrumb `text-dark/50` to `text-dark/70` in `Breadcrumb.astro`. Together these clear `color-contrast` on all 6 pages. It was carried over from last month.

## Notes / caveats

- **Client status deviation.** The methodology expects `status == "active"`. This client is still `"onboarding"`. `build_status` is `pushed_main` and all 6 URLs returned HTTP 200, so the audit proceeded, as it did last month.
- **Tooling.** The `mcp__dataforseo__on_page_lighthouse` and `on_page_instant_pages` MCP tools are not present in this environment. This run called the DataForSEO REST endpoints directly (`/v3/on_page/lighthouse/live/json` with `for_mobile: false`, `/v3/on_page/instant_pages`) and saved the full responses to disk before extracting them. It also ran one single-page `/v3/on_page/task_post` + `/v3/on_page/microdata` pass each on `/services/water-damage-restoration/` and `/contact/` to identify the micromarkup errors. Total API cost was about $0.04.
- **Desktop only.** Scores are desktop (`formFactor=desktop`). Mobile Performance would typically run 10 to 20 points lower. The REST endpoint supports `for_mobile`. Desktop was kept so month-over-month numbers stay comparable.
- **URL selection.** There is no `audit-urls.txt`, so URLs were derived from `plan/url-plan.json`. Four service-landing URLs tie at priority 9.0 (water, fire, mold remediation, roofing). Water and fire damage were kept from the baseline so the comparison stays like-for-like. No service-area page is marked `primary`, and the HQ city (Corona) has no service-area page, so the slot uses the first area in plan order, `/service-areas/riverside-ca/`, as last month.
- **Phone numbers.** Visible `tel:` links use `(951) 629-3771` while JSON-LD `telephone` uses `(951) 667-9910`. This is intentional: `trackingPhone` in `src/lib/brand.ts` sends callers to the tracked line and keeps the canonical number for Google. It is not a defect.
- **Low-severity items not in the template table.** `/services/` has 768 words against its url-plan `target_word_count` of 800 (`rankai_word_count_below_target`, low). `/service-areas/riverside-ca/` embeds a Google Maps iframe (`frame`, low, carried over).
- **Custom issue IDs.** `rankai_*` IDs are Rank AI manual checks, namespaced so they are not mistaken for Lighthouse or DataForSEO IDs. All other IDs are real Lighthouse audit IDs or DataForSEO on-page check keys.
