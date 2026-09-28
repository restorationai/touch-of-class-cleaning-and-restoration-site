# Onsite Audit - Reign Restoration - 2026-09-28

**Live origin audited:** https://reign-restoration.com (apex)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** 2026-08-26 (amber)
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.0 | -0.8 |
| Accessibility | 95.3 | 0.0 |
| Best Practices | 100.0 | +2.0 |
| SEO | 100.0 | 0.0 |

Pages by verdict: green: 2, amber: 0, red: 4, error: 0

Lighthouse scores are still excellent. Performance is 98-100 everywhere, SEO is 100, Best
Practices went to 100 on every page, TBT is 0ms, and CLS is under 0.01. The red verdict does
not come from speed. It comes from one config defect: pages fall back to the image
`https://images.reign-restoration.com/brand/hero.webp`, and that file returns **HTTP 404**.
Last month's fix pointed `imagesBase` at the real host, which cleared the DNS failure and the
console errors, but nobody uploaded the file. So the hero image is now broken above the fold
on `/services/`, `/contact/` and every service-area page. Service cards on `/` and
`/services/` are broken too. This is not a new defect. The same `<img>` tags pointed at
`images.None` last month and the prior audit missed them (details under Regressions).

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT | Words |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 98 | 96 | 100 | 100 | 1.07s | 0.005 | 0ms | 1671 |
| `/services/` | services-hub | red | 99 | 95 | 100 | 100 | 0.85s | 0.004 | 0ms | 836 |
| `/services/water-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 100 | 0.88s | 0.006 | 0ms | 1963 |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 100 | 0.90s | 0.006 | 0ms | 1774 |
| `/service-areas/rockwall-tx/` | service-area | red | 99 | 95 | 100 | 100 | 0.83s | 0.006 | 0ms | 1198 |
| `/contact/` | contact | red | 100 | 96 | 100 | 100 | 0.81s | 0.009 | 0ms | 711 |

INP is null on every page. Lab runs have no user interaction to measure, so this is expected.
DataForSEO on-page score is 100 on all six URLs: no broken links, one H1 each, correct
self-referencing canonicals, and word counts above the url-plan target on every page.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `broken_image_404` | 4 of 6 | high | Pages fall back to `${brand.imagesBase}/brand/hero.webp` (e.g. `BaseLayout.astro:38`, `ServicesHubGrid.astro:28`, `service-areas/[area].astro:20`). That URL returns 404. Upload a hero to R2 at `brand/hero.webp`, or point the fallback at `/images/hero-bg.webp` (confirmed 200). |
| `og_image_404` | 4 of 6 | medium | Same root cause and same fix as `broken_image_404`. Shared links show no thumbnail. |
| `color-contrast` | 6 of 6 | medium | Unchanged from last month. Footer links are `#f2b623` on `#ffffff` (1.82:1). The TDLR license link is `#fae5b2` on `#ffffff` (1.24:1). On Rockwall, `text-slate-400` (`#94a3b8`, 2.56:1) also fails. |
| `image-delivery-insight` | 6 of 6 | medium | Unchanged. `/images/logo.png` is 2896x1065 (88.8 KB) but displays at 174x64. 88.5 KB of that is wasted. The homepage also flags `hero-bg.webp` (51 KB compressible) and `team-768w.webp` (10 KB). |
| `unused-javascript` | 6 of 6 | medium | New. GA4 `gtag.js` (G-NBFCYGQXJY) is 159 KB and about 69 KB is unused. It is already `async`, so the cost is bandwidth, not blocking. Acceptable tradeoff for conversion tracking. See action 4. |
| `forced-reflow-insight` | 4 of 6 | low | New and unattributed. Most likely source is the DNI tracking-number swap (fleet rollout `7dbaf5a80`). It walks `document.body` with a TreeWalker on load. Measured reflow: 35-73ms. |
| `lcp-discovery-insight` | 3 of 6 | low | Unchanged. The service-landing hero is missing `fetchpriority="high"`. |
| `render-blocking-insight` | 6 of 6 | low | `/_astro/_slug_.D67O75JN.css` (about 9 KB) blocks first paint by about 50ms. No action at current scores. |
| `cache-insight` | 6 of 6 | low | Cloudflare-injected `email-decode.min.js` has a 2-day TTL. Not under our control. |
| `network-dependency-tree-insight` | 6 of 6 | low | Critical chain is document, then `page.js` / `_slug_.css`. No action. |
| `has_render_blocking_resources` | 6 of 6 | low | DataForSEO view of the same CSS finding. No action. |
| `no_image_title` | 6 of 6 | low | `title` attributes are not an SEO or a11y requirement, and alt text coverage is 100%. No action. |
| `low_content_rate` | 2 of 6 | low | Text-to-HTML ratio on `/` and `/contact/`. Both beat their word targets (1671/1200 and 711/400). This is markup density, not thin content. No action. |

## Money page alerts

- **`/`** (home) - verdict: red. Lighthouse 98/96/100/100. Two service cards below the fold
  (Roofing Installation and Replacement, Water Cleanup) show broken images. `og:image` and
  `twitter:image` return 404, so shared links show no thumbnail. The meta description is
  still 172 chars against a 70-160 target. Its text changed since last month (`24/7` was
  removed) but the length stayed at 172.
- **`/services/`** (services-hub) - verdict: red. The eager-loaded hero image is broken above
  the fold. Four of the service cards are also broken: Roofing, Water Cleanup, Odor Removal,
  and Contents Restoration & Storage. They fall back to the 404 URL because
  `sites/reign-restoration/public/images/services/` has no image for `roofing`,
  `water-cleanup`, `odor-removal` or `contents-restoration-storage`.
- **`/contact/`** (contact) - verdict: red. The eager-loaded hero image is broken above the
  fold, and `og:image` returns 404. The conversion path itself is fast: performance 100,
  LCP 0.81s.

`/service-areas/rockwall-tx/` is red for the same broken hero. It is not a money page, but
the same template renders all 38 service-area pages, so every one is affected.

## Regressions vs prior audit

**Metric regressions:**
- `/`: LCP went from 0.81s to 1.07s (+262ms), which crosses the 200ms threshold. It is still
  well inside the good band (under 2.5s). Observed LCP subparts total about 362ms (TTFB 47ms,
  load delay 64ms, load 57ms, render delay 194ms), so the simulated number is inflated by the
  new `gtag.js` and the DNI script in the dependency graph. Watch it next month. Not urgent.
- No category dropped by 5 or more points on any page. No site-level average dropped by 3 or
  more points.

**Verdict transitions:**
- `/` went amber to red. `/services/`, `/service-areas/rockwall-tx/` and `/contact/` also went
  amber to red. These are not performance regressions. All four come from `broken_image_404`,
  a defect that existed last month and was not caught. In August, `imagesBase` was
  `https://images.None`, so these `<img>` tags pointed at a host that did not exist. Now they
  point at a real host that returns 404. The prior audit only flagged the `og:image` meta tag
  and not the visible images. This run checks the rendered `<img>` URLs directly.

**New issues this month:**
- All 6 URLs: `unused-javascript`, from the GA4 `gtag.js` added since last audit.
- `/`, both service landings, `/service-areas/rockwall-tx/`: `forced-reflow-insight`, likely
  from the DNI phone swap script.
- `/`, `/services/`, `/service-areas/rockwall-tx/`, `/contact/`: `og_image_404` and
  `broken_image_404` (see above).
- `/contact/`: `low_content_rate`. Informational only.

**Issues resolved since last audit:** (positive - keep doing this)
- `/services/`, `/service-areas/rockwall-tx/`, `/contact/`: `errors-in-console` is no longer
  flagged. Best Practices went from 96 to 100 on all three.
- `/`, `/services/`, `/service-areas/rockwall-tx/`, `/contact/`: `og_image_broken_host` is
  fixed. The `images.None` host is gone and `brand.ts:47` now reads
  `imagesBase: "https://images.reign-restoration.com"`. Only the file upload is missing, and
  that is tracked as `og_image_404` above.

## Recommended next actions (priority order)

1. **(template, money pages, highest impact)** Make `/brand/hero.webp` resolve.
   `https://images.reign-restoration.com/brand/hero.webp` returns 404, and
   `sites/reign-restoration/public/images/brand/` does not exist. The quickest fix is to upload
   the existing `public/images/hero-bg.webp` to the R2 bucket behind `images.reign-restoration.com`
   at key `brand/hero.webp`. That needs no code change and no redeploy. The alternative is to
   change the fallback in `BaseLayout.astro:38`, `ServicesHubGrid.astro:28`, `ServicesStrip.astro:31`,
   `pages/index.astro:27`, `pages/services/[slug].astro:18`, `pages/service-areas/[area].astro:20`,
   `pages/service-areas/[area]/[service].astro:31` and the two blog templates to
   `/images/hero-bg.webp`, which returns 200. Either option fixes the broken hero on `/services/`,
   `/contact/` and all 38 area pages, the broken cards, and `og:image` on every page. Verify
   with `curl -sI https://images.reign-restoration.com/brand/hero.webp` returning 200.
2. **(money page, services hub)** Add real service images for `roofing`, `water-cleanup`,
   `odor-removal` and `contents-restoration-storage` in
   `sites/reign-restoration/public/images/services/`. Use the same `{slug}.webp` plus
   `-480w/-768w/-1200w` variants as the other six. Even after action 1, these four cards and
   their landing-page heroes would show the generic brand hero rather than a relevant photo.
3. **(template, accessibility and conversion)** Raise footer link contrast. This was carried
   over from August and is still unfixed. The footer phone link, email, `/services/`,
   `/emergency/` and the TDLR `#MRC2276` license link are `#f2b623` or `#fae5b2` on white
   (1.82:1 and 1.24:1, against a 4.5:1 minimum). These are the footer's primary conversion
   links. Use a darker gold for text on white (around `#8a6410` passes AA), or move the footer
   onto the dark `#0a0b0e` surface.
4. **(template, performance)** Replace `/images/logo.png`. The 2896x1065 PNG (88.8 KB) renders
   at 174x64 in the header and 218x80 in the footer on every page. Export a WebP at about
   440x160 (2x the display size) and update the header and footer `<img>`. That saves about
   85 KB per page view. Also carried over from August.
5. **(money page, home)** Cut the homepage meta description from 172 to under 160 characters.
   Current text: `Reign Restoration provides water, fire, mold, and storm damage restoration across
   Royse City and surrounding areas. Licensed, insured, IICRC-certified. Call (214) 304-0621.`
   Removing `Reign Restoration provides ` and starting with `Water, fire, mold, and storm damage
   restoration across Royse City...` brings it to 145 without losing the phone number or the
   certification.

## Notes / caveats

- **Desktop-only scoring.** Lighthouse 13.4.0 ran with `formFactor: desktop`,
  `cpuSlowdownMultiplier: 1`, `throughputKbps: 10240`. Mobile scores typically land 10-20
  performance points lower. Do not present these numbers to the client as mobile-first.
- **Why vendors missed the 404.** Lighthouse logged the `hero.webp` request with status `-1`
  and no console error. DataForSEO `instant_pages` returned `broken_resources: false`. Both
  `broken_image_404` and `og_image_404` were confirmed with `curl` (HTTP 404 from Cloudflare)
  and are labelled `source: "manual_verification"` in the state file. They are not presented as
  vendor audit IDs.
- **DNI phone swap is working as intended.** Lighthouse's rendered DOM shows footer `tel:` links
  as `+19035277868`, while the raw HTML carries `+12143040621`. This is the source-attribution
  swap script from the fleet DNI rollout, not a NAP defect. The script does add a small forced
  reflow on load (see `forced-reflow-insight`).
- **Client record status mismatch, still open.** `clients/reign-restoration.json` says
  `status: "onboarding"`. The site has been live on the apex since 2026-08-13, and this was
  already flagged last month. Someone should set it to `active`.
- **Apex, not staging.** There is no `x-robots-tag: noindex` on the apex, so SEO counted toward
  the verdict (100 on all pages).
- **Schema is fine.** DataForSEO `has_micromarkup` is false because it does not detect JSON-LD.
  The homepage carries 3 JSON-LD blocks (Organization, WebSite, LocalBusiness with
  AggregateRating).
- **URL selection.** Four service landings tie at url-plan priority 9.0 (water, fire, mold,
  roofing). Water and fire were kept to stay comparable with August. No area page matches the
  business city (Royse City), so the first area, Rockwall, was used again. `/services/roofing/`
  was not audited, but it has no local service image, so it almost certainly has the broken
  hero too.
- **Lighthouse issue lists now include every failing audit** (7-8 per URL) instead of the top 5.
  This stops the month-over-month diff from reporting false new or resolved issues.
- **New Lighthouse category.** Lighthouse 13.4.0 reports `agentic-browsing` (100 on all pages).
  It is recorded under `supplemental_metrics` and does not count toward the verdict.
- **Run cost:** $0.0408 (6 Lighthouse at $0.005, 6 instant_pages at $0.0018), through the raw
  DataForSEO API over curl with responses written to disk.
