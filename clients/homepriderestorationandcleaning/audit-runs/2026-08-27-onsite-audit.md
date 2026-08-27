# Onsite Audit - Home Pride Restoration and Cleaning LLC - 2026-08-27

**Live origin audited:** https://homepriderestorationandcleaning.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-07-15
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99 | +1 |
| Accessibility | 100 | 0 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

No page scored below 98 in any category. No high or medium severity on-page issues on any page. Every page returned HTTP 200 with a correct self-referencing canonical, HTTPS, exactly one H1, valid JSON-LD, no broken links, and no broken resources. Word counts exceed the archetype target on all six pages.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 98 | 100 | 100 | 100 | 1.13s | 0.004 |
| `/services/` | services-hub | green | 98 | 100 | 100 | 100 | 1.17s | 0.003 |
| `/services/water-damage-restoration/` | service-landing | green | 99 | 100 | 100 | 100 | 0.91s | 0.005 |
| `/services/fire-damage-restoration/` | service-landing | green | 100 | 100 | 100 | 100 | 0.79s | 0.007 |
| `/service-areas/lehi-ut/` | service-area | green | 99 | 100 | 100 | 100 | 1.03s | 0.004 |
| `/contact/` | contact | green | 99 | 100 | 100 | 100 | 1.02s | 0.006 |

Total Blocking Time was 0ms on five pages and 16.5ms on the Lehi service-area page. INP was not measured (no field data in a lab run).

## Template-level issues (fix once, lift many pages)

All are low severity. The site is already green, so these are headroom items rather than defects.

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `cache-insight` | 6 | low | R2 image origin sends no `cache-control`, so Cloudflare defaults to a 4 hour lifetime. Set `public, max-age=31536000, immutable` on `images.homepriderestorationandcleaning.com`. |
| `image-delivery-insight` | 6 | low | `brand/logo-icon.png` is a 488x488 PNG (73.9KB) rendered at 64x64. Re-export at 128x128 WebP. Hero WebP files carry roughly 71KB of compression headroom each. |
| `unused-javascript` | 5 | low | `googletagmanager.com/gtag/js` ships 153KB, of which about 68KB is unused. Third-party bundle, limited control. |
| `lcp-discovery-insight` | 4 | low | LCP hero image is discoverable but not preloaded on some templates. Add `<link rel="preload" as="image">` for the hero with matching `imagesrcset`. |
| `render-blocking-insight` | 3 | low | `/_astro/_slug_.WRTrWfit.css` (8.6KB) blocks first render. Small enough that inlining critical rules is optional. |
| `forced-reflow-insight` | 3 | low | A script reads layout geometry after a style write. Low impact at TBT 0ms. |
| `network-dependency-tree-insight` | 3 | low | Critical request chain depth from third-party tags. Resolves largely with the preload above. |

## Money page alerts

None. All four money page archetypes (home, services-hub, both service-landings, contact) came back green.

## Regressions vs prior audit

**Score deltas:** Performance improved by 1 point site-wide. Accessibility, Best Practices, and SEO held at 100.

**Verdict transitions:** None. All pages were green last month and remain green.

**Core Web Vitals:** No regressions against threshold. CLS improved substantially on every comparable page, most notably `/contact/` from 0.069 to 0.006 and `/services/fire-damage-restoration/` from 0.024 to 0.007. LCP moved within noise on all pages (largest single move: `/services/water-damage-restoration/` 811ms to 906ms, which is below the 200ms regression threshold).

**New issues this month:**
- `/services/`: `forced-reflow-insight`
- `/services/water-damage-restoration/`: `render-blocking-insight`, `forced-reflow-insight`
- `/services/fire-damage-restoration/`: `render-blocking-insight`

**Issues resolved since last audit:**
- `/services/`: `render-blocking-insight` no longer in the top failing set
- `/services/water-damage-restoration/`: `lcp-discovery-insight`, `network-dependency-tree-insight`
- `/services/fire-damage-restoration/`: `unused-javascript`

Treat both lists with caution. Every page has 7 or 8 failing audits and only the top 5 by estimated savings are recorded, so low-severity insights with near-zero savings swap in and out of the list between runs. None of these represent a real change in page behaviour: no category score moved by more than 1 point and no Core Web Vital crossed a threshold.

## Recommended next actions (priority order)

1. **(template, highest impact)** Replace `brand/logo-icon.png` with a 128x128 WebP. It is currently a 488x488 PNG weighing 73.9KB, rendered at 64x64 in the header of every page. Lighthouse attributes 73.2KB of the 73.9KB as waste, and it loads `eager` on all six audited pages. This is the single largest byte win on the site and it is one file.
2. **(template)** Set a long cache lifetime on the R2 image domain. `images.homepriderestorationandcleaning.com` returns no `cache-control` header, so Cloudflare falls back to a 4 hour TTL and every hero re-validates about 168KB per page. Add a Cloudflare Cache Rule (or set object metadata on the `rankai-homepriderestorationandcleaning` bucket) with `public, max-age=31536000, immutable`. Brand assets are versioned by path, so immutable is safe.
3. **(template)** Fix the cache header on Astro build assets. `/_astro/_slug_.WRTrWfit.css` is served `public, max-age=14400, must-revalidate`, but the filename is already content-hashed. Change the `/_astro/*` rule in `_headers` to `public, max-age=31536000, immutable`.
4. **(template)** Re-compress the brand hero WebP files. `brand/hero.webp` and `brand/hero-fleet.webp` are each about 246KB with roughly 71KB of compression headroom at unchanged dimensions. Re-encode at quality 78 to 82.
5. **(per-page)** Trim the homepage meta description from 201 to under 160 characters so it does not truncate in the SERP. Current text ends with the phone number, which is the part Google will cut. Suggested trim: "24/7 water, fire, mold, and storm damage restoration in Saratoga Springs, UT. Licensed, insured, IICRC-certified. Call (801) 995-2437."

## Notes / caveats

- Lighthouse ran DESKTOP only via DataForSEO (formFactor=desktop, cpuSlowdownMultiplier=1, throughputKbps=10240, rttMs=40). Mobile scores would typically run 10 to 20 performance points lower. These scores are not mobile-first. Recorded as `audit_form_factor: desktop`.
- No `on_page_lighthouse` or `on_page_instant_pages` MCP tools are exposed in this environment. Both steps used the DataForSEO REST API directly (`on_page/lighthouse/live/json` and `on_page/instant_pages`), Lighthouse version 13.4.0.
- **The service-area slot changed this month.** The July audit used `/service-areas/saratoga-springs-ut/`, which returns a 301 to `/`. It is a legacy pre-cutover URL present in `cutover/url-inventory.json` but absent from `plan/url-plan.json`. Lighthouse followed the redirect and silently scored the homepage, so the July service-area row was a duplicate homepage measurement rather than a service-area measurement. This run uses `/service-areas/lehi-ut/`, the first `service-area` entry in the url-plan. No plan entry carries `primary: true`, and the client city Saratoga Springs has no service-area page (it is covered by the homepage). The service-area slot therefore has no valid prior comparison, and the prior site-level average was slightly distorted by the duplicated homepage row.
- DataForSEO `no_image_alt` reported true on all 6 pages, but the Lighthouse `image-alt` accessibility audit passes (score 1) on every page and accessibility scores 100. Alt-text coverage is at or above 90 percent. Treated as a decorative/pixel-image detection artifact and not counted as an issue.
- DataForSEO `has_micromarkup` is false on all pages, but the rendered HTML contains valid JSON-LD on all 6, including LocalBusiness, Organization, WebSite, BreadcrumbList, FAQPage, and Service. DataForSEO does not detect JSON-LD, so schema is not flagged as missing.
- DataForSEO `frame` is true on the Lehi service-area page because of an embedded map iframe, not a legacy frameset. Not counted as an issue.
- `low_content_rate` is true on the home and services-hub pages. This reflects a low text-to-HTML ratio, not thin content: home 1507 words against a 1200 target, services hub 807 against 800. No content-length issue is flagged.
- `high_loading_time` is true on the homepage in the instant_pages fetch (duration_time 4225ms). That is a single uncached cold-origin request. Lighthouse measured LCP 1125ms and performance 98 on the same URL in the same run. Not counted as an issue, but it is consistent with the 4 hour R2 cache TTL in recommendation 2.
- Run cost: 12 DataForSEO calls (6 Lighthouse at $0.005 each plus 6 instant_pages), approximately $0.04 total, well inside the $0.30 to $0.50 target.
