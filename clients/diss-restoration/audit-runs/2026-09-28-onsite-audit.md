# Onsite Audit - DISS Restoration - 2026-09-28

**Live origin audited:** https://dissrestoration.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26 (staging Pages preview, https://staging.rankai-diss-restoration.pages.dev)
**Form factor:** desktop only (DataForSEO Lighthouse wrapper; mobile would typically score 10-20 performance points lower)

> **Environment change since last audit:** this is the first audit on the production apex (cutover completed 2026-09-19). Last month was audited on the staging preview. Deltas below are matched by URL path across two different origins, so small performance and LCP swings partly reflect environment, not code. The SEO jump from 69 to 100 is the expected removal of the staging `x-robots-tag: noindex` artifact, not a site fix. SEO counts toward every verdict this run.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 90.7 | -2.5 |
| Accessibility | 96.0 | 0 |
| Best Practices | 100 | 0 |
| SEO | 100 | +31 (staging artifact removed) |

Pages by verdict: {green: 5, amber: 1, red: 0, error: 0}

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 79 | 100 | 100 | 100 | 2.0s | 0.215 |
| /services/ | services-hub | green | 90 | 95 | 100 | 100 | 2.0s | 0.002 |
| /services/water-damage-restoration/ | service-landing | green | 91 | 95 | 100 | 100 | 1.9s | 0.004 |
| /services/fire-damage-restoration/ | service-landing | green | 98 | 95 | 100 | 100 | 0.9s | 0.002 |
| /service-areas/warren-oh/ | service-area | green | 90 | 95 | 100 | 100 | 2.0s | 0.003 |
| /contact/ | contact | green | 96 | 96 | 100 | 100 | 1.2s | 0.024 |

TBT is 0 ms on every page. INP not reported by lab Lighthouse.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is 1,423,236 bytes and is rendered at `h-20` (80px tall) in the header of every page. Export a WebP/AVIF at 2x display size (roughly 160-200px tall, target under 20 KB), add explicit width/height. About 1.4 MB saved per page view. Secondary: `/images/services.webp` (262 KB, 247 KB wasted) on `/services/`, `/images/team.webp` (250 KB, 152 KB wasted) on `/`. |
| `unused-javascript` | 6 | medium | GA4 `gtag.js` (G-QQDEBB808D) ships about 69 KiB unused of 156 KiB. Keep GA4 but load it after first interaction or on `requestIdleCallback`, or move it to Cloudflare Zaraz so it runs off the main thread. |
| `color-contrast` | 5 | medium | Breadcrumb links (`nav ol li a.text-dark/50`) render `#888c93` on white at 12px, ratio 3.37:1. Change to `text-dark/70` or darker (needs 4.5:1). On `/service-areas/warren-oh/` also fix `span.text-slate-400` (`#94a3b8`, 2.56:1) to `text-slate-600`. |
| `lcp-discovery-insight` | 5 | medium | The hero `<img>` is the LCP element on inner pages but has no `fetchpriority="high"` (only the homepage hero has it). Add `fetchpriority="high"` to the hero image in the inner-page hero component, and a `<link rel="preload" as="image">` for it. |
| `largest-contentful-paint` | 3 | medium | LCP is 1.9-2.0s on `/services/`, `/services/water-damage-restoration/`, `/service-areas/warren-oh/`. Resolved by the two fixes above (logo weight competing for bandwidth, hero discovery). |

Also present on all 6 pages but below the top-5 cap on most: `render-blocking-insight`. The Inter Google Fonts stylesheet is linked **twice** in `<head>`: once async (`media="print" onload`) and once as a plain render-blocking `<link rel="stylesheet">`. Delete the plain duplicate.

## Money page alerts

- **`/` (home)** - verdict: amber. Performance 79 (down from 88), CLS 0.215 (threshold 0.1), LCP 2.0s. Cause of the CLS: the hero text container (`main > header.relative > div.container-wide`) reflows when the Inter web font from fonts.gstatic.com swaps in (`display=swap`). Also: meta description is 176 chars (truncates in SERPs), and the homepage FAQ section still ships no `FAQPage` JSON-LD.

## Regressions vs prior audit

Note: prior run was staging, this run is apex. Treat small deltas with caution.

**Metric regressions (per-URL thresholds):**
- `/`: performance 88 to 79 (-9); CLS 0.153 to 0.215 (+0.062); LCP 1646ms to 2021ms (+375ms). The CLS issue was already present last month and has worsened; the font-swap shift is the culprit.
- `/service-areas/warren-oh/`: LCP 1766ms to 2020ms (+254ms). Performance 93 to 90.
- `/contact/`: LCP 808ms to 1239ms (+431ms). Performance 100 to 96. Still green.

Site-level average performance fell 2.5 points (below the 3-point flag threshold).

**Verdict transitions (improvements):**
- `/services/water-damage-restoration/` went amber to green. The DataForSEO `high_loading_time` flag cleared (dom_complete now 394ms, was over 3.4s on staging).
- `/services/fire-damage-restoration/` went amber to green. `high_loading_time` cleared (dom_complete 1610ms); performance 93 to 98, LCP 1.7s to 0.9s.

No green to amber, amber to red, or error transitions.

**New issues this month:**
- All 6 pages: `unused-javascript` (GA4 gtag.js, about 69 KiB unused). The same script is on the staging build today, so this was likely present last month but below the top-5 cap.
- `/`: `meta_description_length_out_of_range` (176 chars). The length was also 176 last month but was not recorded; newly recorded, not newly introduced.
- `/contact/`: `largest-contentful-paint` (1.2s, score 0.88).
- `/services/fire-damage-restoration/`: `network-dependency-tree-insight` (low severity, informational request-chain finding).

**Issues resolved since last audit:** (positive - keep doing this)
- All 6 pages: `is-crawlable` no longer fails. The apex serves no noindex header, and SEO is 100 everywhere.
- `/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`: `high_loading_time` no longer flagged.
- `/services/fire-damage-restoration/`: `largest-contentful-paint` now passes (0.9s).

**Carried over, not yet fixed:** `image-delivery-insight` (1.4 MB logo.png) on all 6, `color-contrast` breadcrumbs on 5, `lcp-discovery-insight` on 5, homepage CLS, homepage `faqpage_schema_missing`, `/services/` `word_count_below_plan_target` (706 vs 800).

## Recommended next actions (priority order)

1. **(money page, home)** Stop the homepage hero layout shift (CLS 0.215). Self-host Inter as woff2 via `@fontsource/inter` (or Astro's font tooling), preload the 400 and 700 weights, and define a metric-matched fallback (`@font-face { font-family: "Inter Fallback"; src: local("Arial"); size-adjust: ...; ascent-override: ...; }`, values generated with a tool such as fontaine or capsize, not hand-guessed) so the swap no longer reflows `header.relative > div.container-wide`. While in `<head>`, delete the duplicate render-blocking Google Fonts `<link>`.
2. **(money page, home)** Trim the homepage meta description from 176 to 150-160 chars, and add `FAQPage` JSON-LD for the existing homepage FAQ section (the same generator already emits it on `/services/` and `/contact/`).
3. **(template, high impact)** Replace `/images/logo.png` (1.42 MB) with a properly sized WebP/AVIF (under 20 KB) with explicit `width`/`height`. This one asset is the main `image-delivery-insight` cost on all 6 pages, and on mobile it is the single biggest performance risk on the site.
4. **(template)** Add `fetchpriority="high"` plus an image preload to the inner-page hero `<img>` (`section.relative > div.absolute > img.w-full`), and defer GA4 gtag.js until idle or first interaction (or move it to Zaraz). Targets the 1.9-2.0s LCP on `/services/`, water damage, and Warren.
5. **(template, accessibility)** Darken the breadcrumb link color from `text-dark/50` (#888c93, 3.37:1) to at least `text-dark/70`, and `text-slate-400` to `text-slate-600` on service-area cards. That takes accessibility from 95 to 100 on 5 pages.

## Notes / caveats

- First apex audit. Canonicals now self-reference correctly on all 6 pages (`https://dissrestoration.com/...`). No broken links, broken resources, mixed content, or missing alt text found. Titles are 53-57 chars; meta descriptions are 120-140 chars except the homepage.
- DataForSEO returned `has_micromarkup` null on every URL. Checked against the served HTML: every page ships valid JSON-LD. Treated as a vendor false negative, not reported as missing schema.
- DataForSEO also flagged `no_image_title` (all 6), `low_content_rate` (`/`, `/services/`) and `frame` (`/service-areas/warren-oh/`). Not actioned: these are cosmetic or an intentional embed.
- `lighthouse_issues` in the state file is capped at 5 per URL. The full list of failing audit IDs is stored in `lighthouse_failing_audit_ids_all`, so an issue that drops below the cap is not miscounted as resolved next month.
- Service-landing slots: water damage, fire damage, and mold remediation are tied at priority 9.0 in the url-plan. Water and fire were kept to stay comparable with last month.
- Run cost: $0.0408 (6 Lighthouse + 6 instant_pages calls).
