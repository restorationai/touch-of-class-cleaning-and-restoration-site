# Onsite Audit - Home Pride Restoration and Cleaning LLC - 2026-09-29

**Live origin audited:** https://homepriderestorationandcleaning.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-08-27
**Form factor:** desktop only (DataForSEO Lighthouse wrapper; mobile would typically score 10-20 performance points lower)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98 | -1 |
| Accessibility | 95 | -5 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: {green: 6, amber: 0, red: 0, error: 0}

Every page is still green, but accessibility fell from 100 to 92-96 on all 6 pages. The cause is one new template-level contrast failure, covered below.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | green | 99 | 92 | 100 | 100 | 1.0s | 0.004 |
| /services/ | services-hub | green | 97 | 95 | 100 | 100 | 1.2s | 0.004 |
| /services/water-damage-restoration/ | service-landing | green | 98 | 95 | 100 | 100 | 1.1s | 0.005 |
| /services/fire-damage-restoration/ | service-landing | green | 98 | 95 | 100 | 100 | 1.1s | 0.007 |
| /service-areas/lehi-ut/ | service-area | green | 96 | 95 | 100 | 100 | 1.4s | 0.005 |
| /contact/ | contact | green | 97 | 96 | 100 | 100 | 1.2s | 0.006 |

TBT is 0-5ms on every page. INP was not reported (lab run).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 6 | medium | The footer license link (`#RC-25-0737`, links to secure.utah.gov) renders #fac7b2 on white, a 1.51:1 contrast ratio. It inherits the global `a { text-primary-200 }` rule, which is meant for dark sections. Add a dark text class in `sites/homepriderestorationandcleaning/src/components/Footer.astro:112` (e.g. `text-navy-900/70`, matching the surrounding footer text) |
| `image-delivery-insight` | 6 | low | Estimated savings of 179-381 KiB per page. Serve hero and gallery images as AVIF/WebP at the rendered size, and add `srcset`/`sizes` so desktop does not download oversized sources |
| `unused-javascript` | 5 | low | About 66-69 KiB of unused JS on every page. Most of it is the same shared bundle, so code-split or lazy-load it (for example, load the map and review widgets only on pages that use them) |
| `forced-reflow-insight` | 5 | low | A layout read after a DOM write in shared JS. Batch the reads before the writes in the header/scroll handler |
| `cache-insight` | 3 | low | 175-190 KiB of short-TTL assets on /services/, Lehi and /contact/. Set a long `Cache-Control` max-age on the R2/CDN image paths |
| `lcp-discovery-insight` | 2 | low | Add `fetchpriority="high"` and remove `loading="lazy"` on the hero image of /services/ and the water-damage landing |

## Money page alerts

None. Every money page (home, services hub, both service landings, contact) is green.

## Regressions vs prior audit

**Verdict transitions:** none (6 of 6 green in both runs).

**Score regressions (5+ point drop):**
- `/`: accessibility 100 -> 92 (-8). The footer contrast failure, plus `link-in-text-block`: the in-content links to `/services/basement-flooding-cleanup/` and `/services/mold-remediation/` in the dark body-content section are #fac7b2 against near-identical surrounding text (1.01:1), and they only underline on hover.
- `/services/`, `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`, `/service-areas/lehi-ut/`: accessibility 100 -> 95 (-5), all from the footer license link. On Lehi there is a second instance: the "Google reviews" count in `GoogleMap.astro:55` uses `text-slate-400` on white (2.56:1).
- `/contact/`: accessibility 100 -> 96 (-4, under the threshold, same cause).

The timing matches the 2026-09-25 brand-restore commit (099a6941d), which re-pinned the orange palette. The primary-200 tint used for links is now a light peach that fails on white backgrounds.

**Core Web Vitals regressions:**
- `/services/fire-damage-restoration/`: LCP 793ms -> 1072ms (+279ms)
- `/service-areas/lehi-ut/`: LCP 1028ms -> 1368ms (+340ms)

Both are still well under the 2.5s "good" threshold, and each comes from a single desktop run. Treat them as watch items and confirm on next month's run.

**New issues this month:**
- All 6 pages: `color-contrast` (footer license link; on Lehi, also the review-count span)
- `/`: `link-in-text-block` (dark-section content links)
- Other new entries in the state file (`forced-reflow-insight`, `lcp-discovery-insight`, `unused-javascript`, `network-dependency-tree-insight`) are performance insights that moved into the top 5 per page. They are not new code problems.

**Issues resolved since last audit:** (positive - keep doing this)
- `/services/`: `forced-reflow-insight` no longer flagged
- `no_image_alt` is no longer reported on any page by DataForSEO, and Lighthouse `image-alt` passes everywhere

## Recommended next actions (priority order)

1. **(template, all 6 pages)** In `sites/homepriderestorationandcleaning/src/components/Footer.astro:112`, add `text-navy-900/70` (or `text-primary-700`) to the license-lookup `<a>` so it no longer inherits `text-primary-200`. This should restore accessibility to 100 on 5 of 6 pages.
2. **(money page, home)** In `sites/homepriderestorationandcleaning/src/pages/index.astro:90`, add `prose-a:underline` to the dark body-content container. Also check that the `prose-a:text-primary-500` override actually wins over the global `a` rule, because links currently render #fac7b2 at 1.01:1 against the body text. This clears `link-in-text-block` on the homepage.
3. **(per-page, service areas)** In `sites/homepriderestorationandcleaning/src/components/GoogleMap.astro:55`, change `text-slate-400` to `text-slate-600` on the "Google reviews" count span. This component is shared by every service-area page.
4. **(template, performance)** Convert the hero and gallery images to AVIF/WebP with `srcset` at their rendered widths. This saves up to 381 KiB per page and is the largest remaining performance opportunity on all 6 pages.
5. **(per-page, home)** Trim the homepage meta description from 201 characters to 150-160 (carried over from August, still open).

## Notes / caveats

- Audited the apex production site (cut over 2026-06-18). SEO counts toward the verdict, and there is no staging noindex artifact.
- Both Lighthouse and instant-pages ran through the DataForSEO REST endpoints (Lighthouse 13.4.0), because no dedicated MCP tools are exposed here. Total API cost was about $0.04.
- Three service landings tie at priority 9.0 in url-plan.json (fire, mold, water). Water and fire were kept so the comparison with August stays like-for-like. The service-area slot stays on `/service-areas/lehi-ut/`, because no area is marked primary and Saratoga Springs has no service-area page.
- JSON-LD schema is present on all 6 pages (LocalBusiness, Organization, WebSite, BreadcrumbList, FAQPage, Service). DataForSEO's micromarkup check does not detect JSON-LD, so schema is not flagged.
- No broken links, no mixed content, canonicals self-reference correctly, each page has exactly one H1, and titles are 32-44 characters. HSTS, `x-content-type-options` and `frame-ancestors` CSP headers are present.
- Word counts meet every archetype target (home 1777, services 810, water 1856, fire 1652, Lehi 1356, contact 743).
- From this run on, the state file stores `all_failing_audit_ids` per URL, so next month's new/resolved comparison is not distorted by the top-5 cap.
