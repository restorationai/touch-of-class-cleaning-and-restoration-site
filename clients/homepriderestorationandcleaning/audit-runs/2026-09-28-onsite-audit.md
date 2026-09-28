# Onsite Audit - Home Pride Restoration and Cleaning LLC - 2026-09-28

**Live origin audited:** https://homepriderestorationandcleaning.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-08-27
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98 | -1 |
| Accessibility | 95 | -5 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

The site is still green. Every category is at 92 or higher on every page, and there are no high or medium severity on-page issues. **But accessibility fell from 100 to 95 across the site. That drop is 5 points, above the 3-point regression threshold.** One template change caused it: the footer license-number link now renders in pale peach (#fac7b2) on white, at a contrast ratio of 1.51:1. WCAG AA requires 4.5:1. Every audited page fails `color-contrast` because of it. This is a single CSS fix.

Every page returned HTTP 200. Every page has HTTPS, a correct self-referencing canonical, exactly one H1, valid JSON-LD, no broken links, no broken resources, and no mixed content. Word counts beat the archetype target on all six pages.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 98 | 92 | 100 | 100 | 1.06s | 0.004 |
| `/services/` | services-hub | green | 96 | 95 | 100 | 100 | 1.25s | 0.004 |
| `/services/water-damage-restoration/` | service-landing | green | 98 | 95 | 100 | 100 | 0.98s | 0.006 |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 100 | 0.96s | 0.007 |
| `/service-areas/lehi-ut/` | service-area | green | 97 | 95 | 100 | 100 | 1.22s | 0.005 |
| `/contact/` | contact | green | 97 | 96 | 100 | 100 | 1.27s | 0.004 |

Total Blocking Time was 0ms on five pages and 17ms on `/contact/`. INP was not measured (lab run, no field data).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 6 | medium | The footer license link (`Footer.astro:110`) has no color class, so it inherits the global `a { @apply text-primary-200 }` rule from `src/styles/global.css:31`. That rule was written for dark sections and gives #fac7b2 on the white footer. Add `text-inherit` (or `text-navy-900/70` to match the surrounding footer text) to the link's class list. |
| `unused-javascript` | 6 | low | `googletagmanager.com/gtag/js` ships about 69KB of unused code on every page. Third-party bundle with limited control; consider loading gtag after first interaction or via Partytown. |
| `image-delivery-insight` | 5 (fails on all 6) | low | `/images/logo.png` is now 1220x426 PNG (185KB) rendered at 64px tall. Lighthouse counts 183KB as waste on every page. This replaced last month's 74KB logo in the 2026-09-25 brand restore. |
| `lcp-discovery-insight` | 5 | low | Inner-page hero `<img>` in `src/pages/[fixed].astro:53` has `loading="eager"` but no `fetchpriority="high"`. The homepage `Hero.astro` already sets it and passes this audit. |
| `forced-reflow-insight` | 3 | low | A script reads layout geometry after a style write. Zero measured TBT impact; leave it. |
| `cache-insight` | 2 in top 5 (fails on all 6) | low | `images.homepriderestorationandcleaning.com/brand/hero.webp` (168KB) still has a 4 hour cache lifetime. This was flagged last month and is not fixed. It is the top savings item on `/service-areas/lehi-ut/` (200ms). |
| `network-dependency-tree-insight` | 2 | low | Critical chain depth from third-party tags. Mostly resolves with the `fetchpriority` fix above. |

`cache-insight`, `image-delivery-insight` and `render-blocking-insight` fail on all six pages in the full audit set. They drop out of some per-page top-5 lists only because other audits have larger savings.

## Money page alerts

None. Home, services hub, both service landings and contact are all green.

## Regressions vs prior audit

**Score deltas:** Site accessibility average -5 (100 to 95), flagged. Performance -1, within noise. Best Practices and SEO held at 100.

**Per-page accessibility regressions (5 points or more):**
- `/` 100 to 92 (-8). It fails both `color-contrast` (footer license link) and `link-in-text-block`. The in-paragraph service links in the dark "services" section (`/services/basement-flooding-cleanup/`, `/services/mold-remediation/`) are #fac7b2 on #cfd1d4 body text. That is a 1.01:1 contrast between link and surrounding text, with no underline.
- `/services/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`, `/service-areas/lehi-ut/` 100 to 95 (-5). Footer license link.
- `/service-areas/lehi-ut/` also fails on the Google reviews count under the map (`GoogleMap.astro:55`, `text-slate-400` #94a3b8 on white, 2.56:1).
- `/contact/` 100 to 96 (-4, under threshold, same footer cause).

**Core Web Vitals:** One regression. `/contact/` LCP went from 1016ms to 1266ms (+250ms, threshold 200ms). The LCP element is the R2 hero `brand/hero.webp` with no `fetchpriority="high"`, no `srcset` (Lighthouse estimates 182KB of delivery waste), and a 4 hour cache TTL. 244ms of LCP is element render delay. `/service-areas/lehi-ut/` rose 194ms, just under threshold, from the same hero image. CLS and TBT did not regress anywhere.

**Verdict transitions:** None. All six pages were green and remain green.

**New issues this month:**
- All 6 pages: `color-contrast` (footer license link, see above)
- `/`: `link-in-text-block`
- `/services/water-damage-restoration/`: `lcp-discovery-insight`
- `/services/fire-damage-restoration/`: `unused-javascript`, `forced-reflow-insight`
- `/contact/`: `forced-reflow-insight`

**Issues resolved since last audit:**
- `/`: `forced-reflow-insight` no longer fails; `cache-insight` savings on the homepage fell to 10KB (Clarity script only)
- `/services/`: `forced-reflow-insight`

Only the two accessibility items are real changes in page behaviour. The other entries are low-severity insights with near-zero savings moving in and out of the top-5 list. `cache-insight`, `render-blocking-insight` and `image-delivery-insight` still fail on the pages where they appear "resolved".

## Recommended next actions (priority order)

1. **(template, money pages, accessibility)** Fix the footer license link color. In `sites/homepriderestorationandcleaning/src/components/Footer.astro` line 112, change the class to `underline decoration-dotted underline-offset-2 hover:opacity-80 text-inherit`. The link then takes the footer's `text-navy-900/70` color instead of the global #fac7b2. This one change fixes `color-contrast` on all 6 audited pages and should bring accessibility back to 100 on 5 of them. The same `certifications.astro:52` and `reviews.astro:41` link pattern should be checked for the same issue.
2. **(money page, homepage)** Give the in-paragraph links in the homepage's dark services section a visible underline. Adding `underline` to `section.bg-dark p a` (or changing global.css line 31 from `hover:underline` to always-on `underline` inside `.bg-dark p`) clears `link-in-text-block`, which is the other 3 points of the homepage's 8-point drop.
3. **(money page, contact LCP)** In `src/pages/[fixed].astro` line 53 (the hero used by `/contact/` and other fixed pages), add `fetchpriority="high"` and a `srcset`/`sizes` pair like the one in `components/ui/Hero.astro:36`. That fixes the 250ms contact LCP regression, clears `lcp-discovery-insight` on 5 pages, and cuts about 180KB from the 1350x276 rendered hero.
4. **(template, carried over from August)** Set `cache-control: public, max-age=31536000, immutable` on the R2 image domain `images.homepriderestorationandcleaning.com`, using a Cloudflare Cache Rule or object metadata on the bucket. `brand/hero.webp` (168KB) still has a 4 hour TTL. That costs 200ms on Lehi and 150ms on the services hub.
5. **(template)** Re-export `/images/logo.png` at 2x display size (about 184x64, or 368x128 for retina) as WebP. It is currently a 1220x426, 185KB PNG loaded eagerly in the header of every page, and it is the largest single byte waste on the site. Keep the orange/navy artwork restored on 2026-09-25; only the dimensions and format change. Also fix the header `<img>` `width="36" height="36"` attributes to match the real aspect ratio.

Lower priority, not in the top 5: homepage meta description is still 201 characters (target 70-160). The suggested 135-character trim from August still applies.

## Notes / caveats

- Lighthouse ran DESKTOP only via DataForSEO (formFactor=desktop, Lighthouse 13.4.0). Mobile scores would typically run 10 to 20 performance points lower. These scores are not mobile-first. Recorded as `audit_form_factor: desktop`.
- No `on_page_lighthouse` or `on_page_instant_pages` MCP tools are exposed in this environment. Both steps used the DataForSEO REST API directly (`on_page/lighthouse/live/json`, `on_page/instant_pages` with JavaScript rendering). Full audit data was retrieved for every URL.
- Three service landings tie at the top url-plan priority (9.0): water damage, fire damage and mold remediation. Water and fire were kept for month-over-month comparability.
- The service-area slot is `/service-areas/lehi-ut/`, the first service-area entry in url-plan.json. No entry has `primary: true`, and Saratoga Springs has no service-area page. This is the same URL as August, so the comparison is valid.
- DataForSEO `has_micromarkup` does not detect JSON-LD. Rendered HTML was checked directly: valid JSON-LD on all 6 pages. LocalBusiness appears on every page, Service on both landings, and BreadcrumbList and FAQPage on every non-home page. Schema is not flagged.
- DataForSEO `frame=true` on Lehi is the embedded Google Map iframe. `low_content_rate=true` on home, services hub and contact is a text-to-HTML ratio flag. Word counts are home 1777 vs 1200, hub 810 vs 800, and contact 743 vs 400. Neither flag is counted as an issue.
- Context for the accessibility drop: commit 099a6941d on 2026-09-25 re-pinned the orange palette (`primary-200` = #fac7b2) and restored the full logo. The footer license link was not caught because the global link color assumes a dark background.
- Run cost: 12 DataForSEO calls (6 Lighthouse at $0.005, 6 instant_pages at $0.0018), about $0.04 total.
