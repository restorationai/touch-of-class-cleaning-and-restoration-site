# Onsite Audit - DISS Restoration - 2026-09-28

**Live origin audited:** https://dissrestoration.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26 (amber, staging Pages preview)
**Form factor:** desktop only (see caveats)

## Headline

This is the first audit on the live apex. The 2026-09-19 cutover went through: all 6 URLs return 200 from Cloudflare with no `x-robots-tag`, HSTS is on, and canonicals self-reference the apex. SEO now counts toward the verdict and scores 100 on every page (it was 69 on staging only because of the Pages noindex header).

Two service landings improved from amber to green. The site stays amber because of the homepage. It scores 80 on performance, has a 0.215 CLS hero shift that got worse since last month, a 176-character meta description, and still has no FAQPage schema.

The biggest cost on the site is unchanged from last month. `/images/logo.png` is a 1,423,236-byte 1200x1078 PNG displayed at 64 to 96px tall, and it loads on every page.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 89.3 | -3.9 |
| Accessibility | 96.0 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | +31.0 (staging artifact removed) |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 80 | 100 | 100 | 100 | 1.98s | 0.215 | 0ms |
| `/services/` | services-hub | green | 91 | 95 | 100 | 100 | 1.99s | 0.003 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 91 | 95 | 100 | 100 | 1.95s | 0.002 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | green | 92 | 95 | 100 | 100 | 1.87s | 0.004 | 0ms |
| `/service-areas/warren-oh/` | service-area | green | 92 | 95 | 100 | 100 | 1.91s | 0.003 | 0ms |
| `/contact/` | contact | green | 90 | 96 | 100 | 100 | 2.00s | 0.002 | 0ms |

On desktop, LCP passes the 2.5s "good" threshold on every page, but only by a little (1.87 to 2.00s). The homepage is the only page that fails CLS (0.215 against a 0.1 threshold). On-page basics are clean on all 6 URLs: one H1 each, titles of 53 to 57 characters, self-referencing canonicals, no broken links, and no mixed content.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | Lighthouse estimates 1,388 to 1,738 KiB of avoidable image bytes per page, about 1,421 KiB of it from `/images/logo.png`. The header renders it at `width="64" height="64"` (`h-20 md:h-24`) and the footer at 48px. Export a WebP about 200px tall (target under 20 KB) and point both header and footer `<img>` at it. Also flagged: `/images/services.webp` on `/services/` (262 KB, 247 KB wasted) and `/images/team.webp` on `/` (250 KB, 152 KB wasted). Resize both to their displayed dimensions. |
| `unused-javascript` | 6 | medium | New since cutover. `gtag/js?id=G-QQDEBB808D` (about 156 KiB, about 69 KiB unused) now loads on every page. Inject it on first user interaction or in `requestIdleCallback` so it stays out of the critical window. |
| `lcp-discovery-insight` | 5 | medium | Unchanged from last month. The inner-page hero `<img src="/images/hero-bg.webp" ... loading="eager">` (and `/images/services/water-damage-restoration.webp` on that landing) has no `fetchpriority="high"`. The homepage hero has it, which is why `/` passes. Add the attribute in the shared inner-page hero component. |
| `color-contrast` | 5 | medium | Unchanged. Breadcrumb links use `text-dark/50`, which renders as `#888c93` on `#ffffff` at 3.37:1 (4.5:1 required). Change them to `text-dark/70` or darker in the breadcrumb component. `/service-areas/warren-oh/` also has a `text-slate-400` span (`#94a3b8`) at 2.56:1. Use `text-slate-600` there. |
| `largest-contentful-paint` | 5 | medium | LCP is 1.9 to 2.0s on desktop and scores 0.63 to 0.67. It is a symptom, not a separate fix. The logo and `fetchpriority` changes above address it. |
| `has_micromarkup_errors` | 5 | low | DataForSEO's schema.org validator flags the FAQPage `Question` objects for missing `answerCount` and `text`. Those are QAPage fields that Google's FAQPage rich result does not require, so this is a validator false positive. Optional: add `"answerCount": 1` to each Question in the FAQ schema builder to clear the flag. |

## Money page alerts

- **`/`** (home). Verdict: amber. Performance 80 and CLS 0.215. The shifting element is the hero text container `div.container-wide relative z-10 pt-10 pb-14 ...` (shift score 0.215). Inter loads asynchronously (`media="print" onload="this.media='all'"`, six weights 400 to 900 with `display=swap`), so the hero headline reflows when the web font replaces the fallback. The 1.36 MB logo also loads here. On the on-page side, the meta description is 176 characters (limit 160), and the visible "Frequently Asked Questions" section ships no FAQPage JSON-LD.

## Regressions vs prior audit

Deltas below compare apex (this run) against the staging Pages preview (2026-08-26), matched by path. Part of each performance and LCP change comes from the different edge path and single-run Lighthouse variance. The new gtag script is a real code change that contributes on every page.

**Per-page regressions (thresholds: category -5, LCP +200ms, CLS +0.02, TBT +100ms):**
- `/`: performance 88 to 80 (-8). LCP 1,646 to 1,980ms (+334ms). CLS 0.153 to 0.215 (+0.062). The hero font-swap shift was already the top issue last month and it grew.
- `/contact/`: performance 100 to 90 (-10). LCP 808 to 1,998ms (+1,190ms). The LCP element is now the hero `<img src="/images/hero-bg.webp" loading="eager">` with no `fetchpriority`. Lighthouse estimates 95 KB of that 144 KB image is wasted at the rendered size. FCP is 835ms here, against 280 to 350ms on most other pages.

**Site-level:** average performance fell by 3.9 points (93.2 to 89.3), past the 3-point flag. No page moved to a worse verdict.

**Verdict improvements:**
- `/services/water-damage-restoration/` went from amber to green. The `high_loading_time` crawl flag cleared: dom_complete dropped from 4,226ms to 311ms.
- `/services/fire-damage-restoration/` went from amber to green, for the same reason (dom_complete fell from 5,051ms to 1,909ms).

**New issues this month:**
- All 6 pages: `unused-javascript` (gtag G-QQDEBB808D, about 69 KiB unused).
- `/`: `meta_description_length` (176 characters).
- `/contact/`: `largest-contentful-paint` now fails (2.0s, previously 0.8s).
- `/services/`, both landings, `/service-areas/warren-oh/`, `/contact/`: `has_micromarkup_errors`. This is new only because DataForSEO detected no micromarkup at all on staging last month. See the template table.

**Issues resolved since last audit:** (positive, keep doing this)
- All 6 pages: `is-crawlable` passes now that the site is served from the apex without the staging noindex header.
- `/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`: `high_loading_time` has cleared (dom_complete is now 224ms, 311ms and 1,909ms respectively).

## Recommended next actions (priority order)

1. **(money page + template, high impact)** Replace `/images/logo.png` (1,423,236 bytes, 1200x1078) with an approximately 200px-tall WebP in both the header and footer `<img>` tags. This removes about 1.4 MB from every page load. Lighthouse estimates about 1,100ms of LCP savings per page. It is also the single biggest mobile risk. This item was #1 last month and has not been done.
2. **(money page, `/`)** Stop the hero font-swap shift (CLS 0.215). Self-host Inter as woff2 and add `<link rel="preload" as="font" type="font/woff2" crossorigin>` for the hero weight(s). Load only the weights actually used instead of all six (400 to 900). Add a metric-matched fallback `@font-face` (`size-adjust` / `ascent-override` on Arial) so the swap does not move the hero container.
3. **(money page, `/`)** Add FAQPage JSON-LD for the homepage "Frequently Asked Questions" section, using the same builder the inner pages use. Shorten the meta description from 176 to 160 characters or fewer. Suggested 148-character version: "DISS Restoration provides 24/7 water, fire, mold, and storm damage restoration in Youngstown and nearby areas. IICRC-certified. Call (724) 981-1441."
4. **(template, money pages)** Add `fetchpriority="high"` to the hero `<img>` in the shared inner-page hero (affects `/services/`, both landings, `/service-areas/warren-oh/`, `/contact/`). This is the main lever for the `/contact/` LCP regression. In the same change, defer the gtag `G-QQDEBB808D` injection until first interaction or idle.
5. **(template, accessibility)** Change breadcrumb link color from `text-dark/50` (3.37:1) to `text-dark/70` or darker. Change the `text-slate-400` span on the service-area template (2.56:1) to `text-slate-600`. This lifts accessibility from 95 to 100 on 5 pages.

## Notes / caveats

- **Origin change.** Last month's baseline was `https://staging.rankai-diss-restoration.pages.dev`. This run used the apex because `apex_cutover.completed_at` is 2026-09-19. Read the score deltas with that in mind. The +31 SEO delta is entirely the staging noindex going away.
- **Desktop only.** The DataForSEO Lighthouse wrapper ran with `for_mobile=false`. Mobile performance would typically be 10 to 20 points lower, and the 1.36 MB logo would dominate on a throttled mobile connection.
- **URL selection.** URLs were auto-derived from `plan/url-plan.json` because no `audit-urls.txt` exists. The service-landing slots came from a three-way tie at priority 9.0 (water-damage-restoration, fire-damage-restoration, mold-remediation). I kept the same two as last month for comparability. No service-area has `primary: true`, and the business city (Farrell, PA) has no area page, so `warren-oh` was used per the fallback rule.
- **Issue cap.** Only the top 5 failing Lighthouse audits are stored per URL. These minor failures also appear but sit outside the cap: `render-blocking-insight` (single 9 KB CSS file, about 50ms), `cache-insight` (Cloudflare `email-decode.min.js`, 0 KiB savings), `network-dependency-tree-insight`, and `forced-reflow-insight` (fire page only).
- **Word count.** `/services/` has 706 words against a url-plan target of 800 (low severity). Every other page meets its target.
- **Security headers.** HSTS (`max-age=31536000; includeSubDomains`), `x-content-type-options: nosniff`, and a `frame-ancestors` CSP are present on all 6 URLs.
- **Run cost:** $0.041 in DataForSEO calls (6 Lighthouse plus 6 instant_pages).
