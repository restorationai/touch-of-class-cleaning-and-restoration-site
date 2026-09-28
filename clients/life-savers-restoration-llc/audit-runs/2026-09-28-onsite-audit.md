# Onsite Audit - Life Savers Restoration LLC - 2026-09-28

**Live origin audited:** https://lifesaversrestorationvegas.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-27 (staging Pages preview, all 6 pages red)
**Lighthouse form factor:** desktop

## Environment caveats (read first)

**This is the first apex audit.** The site went live on `lifesaversrestorationvegas.com` on 2026-09-04 (`cut_over_at` in the client record). The record has no `apex_cutover.completed_at`, but `cut_over_at` and `deploy_url` both point at the apex, and the apex returns 200 with no `x-robots-tag`. So this run audits production, and **SEO counts toward the verdict again**. The August audit ran on the staging preview with the noindex artifact, so the SEO jump from 69 to 100 is mostly that artifact going away.

**Deltas mix a code change with an origin change.** Prior numbers came from `staging.rankai-life-savers-restoration-llc.pages.dev`. Today's numbers come from the apex behind the Cloudflare zone. A same-day staging pass gave LCP around 1.3-1.4s too, so the roughly 300ms LCP increase shows up on both origins. It is not caused by the apex. All pages are still well under the 2.5s "good" LCP threshold.

**TBT is noisy.** `/contact/` ran 4 times today and scored performance 82, 95, 95, 77 (TBT 311, 0, 0, 467 ms). This report records the first scheduled run (82). The blocking comes from real scripts (see the money page alert), so treat it as intermittent, not as a measurement fluke.

**Desktop scoring.** Lighthouse ran with `formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`. Mobile scores would typically land 10-20 performance points lower.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 93 | -5 |
| Accessibility | 95 | 0 |
| Best Practices | 100 | 0 |
| SEO | 100 | +31 (noindex artifact removed) |

Pages by verdict: green: 4, amber: 2, red: 0, error: 0

Last month's site-wide red came from the `https://None/` canonical and schema bug. That bug is **fixed**: every audited page now has a self-referencing canonical on the apex, and all JSON-LD `@id` values resolve to `https://lifesaversrestorationvegas.com/`. Both amber verdicts today come from single, specific issues.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 97 | 96 | 100 | 100 | 1.3s | 0.024 | 24ms |
| /services/ | services-hub | green | 96 | 95 | 100 | 100 | 1.4s | 0.003 | 31ms |
| /services/water-damage-restoration/ | service-landing | green | 97 | 95 | 100 | 100 | 1.3s | 0.004 | 0ms |
| /services/mold-remediation/ | service-landing | green | 92 | 91 | 100 | 100 | 1.3s | 0.004 | 180ms |
| /service-areas/las-vegas-nv/ | service-area | green | 96 | 95 | 100 | 100 | 1.4s | 0.005 | 0ms |
| /contact/ | contact | amber | 82 | 96 | 100 | 100 | 1.4s | 0.056 | 311ms |

No broken links, broken resources, mixed content, missing H1s, or missing alt text on any audited page.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is 423 KiB and loads on every page, and nearly all of it is wasted. Export the logo as a WebP/AVIF (or SVG) at its display size, aiming for under 20 KiB. `hero-bg.webp` (180 KiB) also wastes 66-132 KiB on the hub, area, and contact templates: serve it with a responsive `srcset`. Estimated LCP savings: 200-350ms per page. |
| `color-contrast` | 6 | high | Header/footer `tel:` and `mailto:` links use `text-primary` on a light background, and breadcrumb links use `text-dark/50`. Both fail WCAG AA. Switch text links to `text-primary-700` and breadcrumbs to `text-dark/70` in the layout and breadcrumb components. |
| `unused-javascript` | 6 | medium | About 69 KiB of unused JS on every page, mostly the GA4 `gtag/js` bundle. Load gtag after the `load` event (or on first interaction) instead of in `<head>`. |
| `lcp-discovery-insight` | 4 | medium | The LCP hero image on `/services/`, service landings, service areas, and `/contact/` has no `fetchpriority="high"`. Home already has it. Add `fetchpriority="high"` and `loading="eager"` to the hero `<img>` in the shared page-hero component. |
| `network-dependency-tree-insight` | 4 | medium | Critical chain: HTML, then `/_astro/_slug_.*.css`, `/_astro/page.*.js`, and Cloudflare `email-decode.min.js`. Inline the above-the-fold CSS (Astro `build.inlineStylesheets: "auto"`) and turn off Cloudflare Email Address Obfuscation so `email-decode.min.js` drops out of the chain. |
| `total-blocking-time` | 2 | high | See the `/contact/` money page alert. `/services/mold-remediation/` shows the same pattern at 180ms. |
| `low_content_rate` | 2 | low | Home and `/services/` have a low text-to-HTML ratio because of inline Tailwind markup. No action needed beyond the word-count note below. |

## Money page alerts

- **`/contact/`**: verdict amber. Performance 82, TBT 311ms (4 runs ranged 0-467ms), CLS 0.056. Long tasks come from GA4 `gtag/js` (up to 257ms), the page's inline scripts (the `[data-estimate-form]` handler, up to 206ms), and unattributable work. Cloudflare's `email-decode.min.js` loads **twice** on this page. The 0.056 CLS comes from the `<section id="estimate">` block shifting as it renders.
- **`/`**: verdict amber. Performance 97 and LCP 1.3s are fine. The only problem is a 186-character meta description, which Google will truncate (limit 160).

## Regressions vs prior audit

**Verdict transitions (all improvements):**
- `/`: red to amber (canonical fixed; the long meta description remains)
- `/services/`, `/services/water-damage-restoration/`, `/services/mold-remediation/`, `/service-areas/las-vegas-nv/`: red to green
- `/contact/`: red to amber (canonical fixed; now amber on TBT)

**Metric regressions flagged:**
- `/contact/`: performance 98 to 82 (-16), TBT 0 to 311ms. Intermittent main-thread blocking, covered in the money page alert above.
- `/services/mold-remediation/`: performance 98 to 92 (-6), accessibility 95 to 91 (-4). The accessibility drop comes from the new `link-in-text-block` failure: the in-body link to `/blog/how-to-test-for-mold/` is distinguished only by color.
- LCP rose 300-370ms on `/services/`, both service landings, `/service-areas/las-vegas-nv/`, and `/contact/` (for example 951ms to 1317ms on water damage). Same-day staging shows the same values, so this is not caused by the apex. Everything is still under 1.5s. The logo and hero fixes above should recover it.
- Site average performance: 98 to 93 (-5). Most of this is the single `/contact/` run.

**New issues this month:**
- `/services/mold-remediation/`: `link-in-text-block`, and `total-blocking-time` at 180ms
- `/contact/`: `total-blocking-time` at 311ms
- `/`: `cache-insight` (low; the Cloudflare cache TTL on static assets is short)
- `unused-javascript` appears on all 6 pages. It also fails on today's staging pass and fell below last month's top-5 cutoff, so treat it as pre-existing, not introduced.

**Issues resolved since last audit:** (positive, keep doing this)
- `canonical` (`https://None/...`) is fixed on all 6 pages
- `has_micromarkup_errors` is fixed on all 5 pages that had it; JSON-LD now resolves to the apex host
- `is-crawlable` passes on all 6 pages now that production has no noindex
- `/`: `unsized-images` is fixed; the Best of Las Vegas badges now have explicit width/height

## Recommended next actions (priority order)

1. **(money page)** On `/contact/`: move the GA4 `gtag/js` include and its inline config to load after `window.load` (or on first scroll/click), and remove the duplicate `cdn-cgi/.../email-decode.min.js` by leaving only one obfuscated `mailto:` on the page, or by turning off Cloudflare Email Address Obfuscation for the zone and rendering the address directly. Give `<section id="estimate">` a fixed `min-height` so it stops shifting. Re-run Lighthouse 3 times and expect TBT under 100ms on every run.
2. **(money page)** Cut the homepage meta description from 186 to 150-160 characters. Keep "Henderson" (it matches the H1 and title) and the (702) 845-1325 number, and trim the credential list, for example: "24/7 water, fire, mold and storm damage restoration in Henderson, NV. IICRC-certified, insurance billing. Call (702) 845-1325."
3. **(template, high impact)** Re-export `/images/logo.png` (423 KiB) as SVG or a size-matched WebP under 20 KiB, and add a responsive `srcset` to `hero-bg.webp`. This lifts all 6 pages, with 422-555 KiB less payload and 200-350ms estimated LCP savings each.
4. **(template)** Fix `color-contrast` in the layout: `text-primary` to `text-primary-700` on header/footer `tel:`/`mailto:` links, and `text-dark/50` to `text-dark/70` on breadcrumbs. Also underline in-body links (fixes `link-in-text-block` on `/services/mold-remediation/`).
5. **(template)** Add `fetchpriority="high"` to the hero image in the shared page-hero component used by `/services/`, service landings, service areas, and `/contact/`.

## Notes / caveats

- Service-landing tie-break: `fire-damage-restoration`, `mold-remediation`, and `water-damage-restoration` all have priority 9.0 in `url-plan.json`. This run kept water damage and mold (last month's pair) so the deltas are comparable.
- The staging Pages preview is still an older build: its `tel:` links use `+17029308647`, while the apex uses `+17028451325` everywhere. Staging is no longer production. Do not use it for NAP checks or screenshots.
- `/services/` has 725 words against an 800-word hub target (low severity, content-length only).
- `/service-areas/las-vegas-nv/` embeds a Google Maps iframe (`frame` check, low). It is not currently causing blocking time on the apex.
- The client record should get `apex_cutover.completed_at` set to match `cut_over_at` so future runs choose the apex without an override.
- Cost: about $0.11 (6 Lighthouse + 6 instant pages on the apex, 6 + 6 on staging for the origin comparison, 3 extra `/contact/` reruns).
