# Onsite Audit - Life Savers Restoration LLC - 2026-09-29

**Live origin audited:** https://lifesaversrestorationvegas.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-27 (red, run on the staging Pages preview)
**Form factor:** desktop (the DataForSEO Lighthouse wrapper does not expose mobile; mobile performance would typically run 10-20 points lower)

> **First audit on the apex.** The client record has `cut_over_at` = 2026-09-04 and `deploy_url` = https://lifesaversrestorationvegas.com, and the apex serves the Rank AI build with no noindex header. SEO now counts toward the verdict and scores 100 on every page. Last month ran on staging, so this run matches URLs to last month by path. The +31 SEO delta comes from the origin change (staging noindex removed), not from a code fix.

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 96 | -2 |
| Accessibility | 95 | +0 |
| Best Practices | 100 | +0 |
| SEO | 100 | +31 |

Pages by verdict: green: 0, amber: 6, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 98 | 96 | 100 | 100 | 1.0s | 0.023 |
| /services/ | services-hub | amber | 96 | 95 | 100 | 100 | 1.4s | 0.003 |
| /services/water-damage-restoration/ | service-landing | amber | 96 | 95 | 100 | 100 | 1.3s | 0.004 |
| /services/mold-remediation/ | service-landing | amber | 96 | 91 | 100 | 100 | 1.4s | 0.003 |
| /service-areas/las-vegas-nv/ | service-area | amber | 94 | 95 | 100 | 100 | 1.4s | 0.004 |
| /contact/ | contact | amber | 95 | 96 | 100 | 100 | 1.4s | 0.056 |

All six pages are amber for the same reason: a medium on-page issue (schema validation on 5 pages, meta description length on the homepage). Every Lighthouse category is 91 or higher, and SEO is 100 across the board.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 6 | high | `text-primary` (#a07828) on white is 4.03:1, below the 4.5:1 AA minimum. Darken the `primary` text token to #8a6620 (5.25:1), and fix the `text-dark/50` breadcrumb links |
| `unused-javascript` | 6 | medium | The GA4 script `gtag/js?id=G-EGE48LYQVZ` loads 69 KiB of unused code. Load it via Partytown, or defer it until after `load` or first interaction |
| `image-delivery-insight` | 5 | high | `/images/logo.png` is 432 KB but displays at about 200px wide. Export a 400px WebP (under 20 KB). Also serve `hero-bg.webp` (184 KB) at display size via srcset. Saves 420-555 KiB per page, and 473 KiB on the homepage (flagged there at a lower score) |
| `lcp-discovery-insight` | 5 | medium | Add `fetchpriority=high` to the hero `<img>` (`hero-bg.webp`) in the page-header section |
| `has_micromarkup_errors` | 5 | medium | In the BreadcrumbList, give the final ListItem an `item` URL (it currently has only `name`). Make `logo`/`image` absolute URLs (`https://lifesaversrestorationvegas.com/images/logo.png`), not `/images/logo.png` |
| `network-dependency-tree-insight` | 4 | medium | Informational: critical chain is HTML -> `_astro` CSS -> fonts. Preload the primary webfont file |
| `forced-reflow-insight` | 2 | medium | Unattributed reflow of about 30ms. Low priority |

## Money page alerts

- **`/`** (home) - verdict: amber. Meta description length 186 chars, outside the 70-160 target.
- **`/services/`** (services-hub) - verdict: amber. Schema.org markup fails DataForSEO validation (likely cause: BreadcrumbList final ListItem has no `item`; logo/image values are relative paths).
- **`/services/water-damage-restoration/`** (service-landing) - verdict: amber. Schema.org markup fails DataForSEO validation (likely cause: BreadcrumbList final ListItem has no `item`; logo/image values are relative paths).
- **`/services/mold-remediation/`** (service-landing) - verdict: amber. Schema.org markup fails DataForSEO validation (likely cause: BreadcrumbList final ListItem has no `item`; logo/image values are relative paths).
- **`/contact/`** (contact) - verdict: amber. Schema.org markup fails DataForSEO validation (likely cause: BreadcrumbList final ListItem has no `item`; logo/image values are relative paths).

All five alerts come from on-page metadata and schema issues, not speed. On every money page, Lighthouse performance is 95-98 and LCP is 1.0-1.4s.

## Regressions vs prior audit

**Verdict transitions:** all 6 pages moved red -> amber (improved). Last month's red came from the `https://none/` canonical bug, which is now fixed.

**Core Web Vitals regressions (LCP up 200ms or more):**
- `/services/`: LCP 1129ms -> 1383ms (+254ms)
- `/services/water-damage-restoration/`: LCP 951ms -> 1324ms (+373ms)
- `/services/mold-remediation/`: LCP 976ms -> 1364ms (+388ms)
- `/service-areas/las-vegas-nv/`: LCP 1055ms -> 1397ms (+342ms)
- `/contact/`: LCP 1061ms -> 1410ms (+349ms)

All pages remain well under the 2.5s good threshold. Two things drive the +250-390ms shift. First, the newly flagged GA4 `gtag.js` script. Second, the switch from the pages.dev preview to the apex custom domain, so part of the shift is environmental. The homepage improved (1059ms -> 975ms). No Lighthouse category dropped 5 or more points on any page. Average performance moved 98 -> 96, and the service-area page is lowest at 94 (TBT 124ms).

**New issues this month:**
- All 6 pages: `unused-javascript`. GA4 `gtag/js?id=G-EGE48LYQVZ` loads 69 KiB of unused JavaScript. It was not flagged last month, so the tag was likely added since.
- `/services/mold-remediation/`: `link-in-text-block`. The inline link to `/blog/how-to-test-for-mold/` is distinguished by color only. Accessibility dropped 95 -> 91.
- `/`, `/services/water-damage-restoration/`: `forced-reflow-insight` (about 30ms, unattributed). `/`: `cache-insight` (0 KiB estimated savings, informational).

Note: last month stored only the top 5 Lighthouse failures per page, so an item listed as new may have been failing below that cap before.

**Issues resolved since last audit:** (positive, keep doing this)
- All 6 pages: `canonical` no longer points to `https://none/...`. Canonicals now resolve to `https://lifesaversrestorationvegas.com/...`.
- All 6 pages: `is-crawlable` passes. The site is indexable on the apex, and SEO is 100.
- `/`: `unsized-images` no longer flagged.

**Still open from last month:** `color-contrast` (6 pages), `image-delivery-insight` (6), `lcp-discovery-insight` (5), `has_micromarkup_errors` (5), `description_length` on `/`, `plain_text_word_count` on `/services/`.

## Recommended next actions (priority order)

1. **(money page, template)** Fix the BreadcrumbList schema in the layout component: add `"item": "https://lifesaversrestorationvegas.com{path}"` to the final ListItem, and make every `logo`/`image` value an absolute URL. This clears `has_micromarkup_errors` on 5 pages and is the main thing keeping them amber. Re-validate one page in the Rich Results Test before shipping.
2. **(money page)** Shorten the homepage meta description from 186 to 150-160 characters. It is the only issue keeping `/` amber.
3. **(template, high)** Darken the `primary` color token used for text links from #a07828 to #8a6620 (5.25:1 on white), and underline inline body-copy links. This clears `color-contrast` on all 6 pages and `link-in-text-block` on the mold page.
4. **(template, high)** Replace `/images/logo.png` (432 KB) with a 400px-wide WebP, and convert the five award/IICRC/USFCR badge PNGs to sized WebP with explicit `width`/`height`. That saves 420-555 KiB per page, and the explicit dimensions keep `unsized-images` from coming back.
5. **(template, speed)** Load GA4 (`G-EGE48LYQVZ`) via Partytown, or inject it after first interaction. Also add `fetchpriority=high` to the hero image. Together these target this month's LCP drift and the `unused-javascript` / `lcp-discovery-insight` flags on 5-6 pages.

## Notes / caveats

- Origin choice: the record lacks an `apex_cutover.completed_at` object but has `cut_over_at` and an apex `deploy_url`. Audited the apex, following the go-green-restoration-of-nc convention. Consider stamping `apex_cutover.completed_at` so every tool agrees. A staging pass was also run first (SEO 69 from the noindex artifact, other scores within 1-3 points of the apex). Only the apex results are recorded in the state file.
- Prior audit was on staging, and URLs are compared by path. Some of the performance and LCP deltas come from the environment change.
- Desktop-only Lighthouse (DataForSEO wrapper). Treat performance as optimistic for mobile.
- `/services/` word count is 725 against an 800-word url-plan target (low severity, carried over from last month).
- `/service-areas/las-vegas-nv/` contains an iframe (embedded map). This is informational and low severity.
- Service-landing slots used water-damage-restoration and mold-remediation, the same as last month. Fire-damage-restoration ties them at priority 9.0, and keeping the same pages keeps the comparison valid. The service-area slot used las-vegas-nv (first area, no `primary` flag in the url-plan).
- NAP observation, outside audit scope: page links use `tel:+17029308647`, while the schema `telephone` is `+17028451325`. Flag this for the NAP owner to reconcile.
- All 24 DataForSEO calls succeeded (12 staging, 12 apex). Total cost was about $0.08.
