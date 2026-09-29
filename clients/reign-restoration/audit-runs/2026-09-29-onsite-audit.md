# Onsite Audit - Reign Restoration - 2026-09-29

**Live origin audited:** https://reign-restoration.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26 (amber)
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.5 | -1.3 |
| Accessibility | 95.3 | 0.0 |
| Best Practices | 100.0 | +2.0 |
| SEO | 100.0 | 0.0 |

Pages by verdict: green: 0, amber: 6, red: 0, error: 0

The site is still technically strong. Performance is 97-99 on every page, SEO is 100 everywhere,
CLS stays under 0.01, and TBT is 0-4ms. Best Practices went up to 100 on all six pages because
the `images.None` console errors from last month are gone. On-page is clean: DataForSEO gives
onpage_score 100 on every URL, with no broken links or resources, correct self-referencing
canonicals, one H1 per page, 100% image alt coverage, and word counts above target everywhere.

Every page is amber because of three medium-severity template defects. Two of them are one-line
fixes: empty `foundingDate` in the schema, and an og:image that now points at a real host but
a file that does not exist. The site did not get worse. The two service landings moved from
green to amber only because DataForSEO started flagging a schema defect that was already there
last month.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT | Words |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 97 | 96 | 100 | 100 | 1.23s | 0.005 | 4ms | 1671 |
| `/services/` | services-hub | amber | 98 | 95 | 100 | 100 | 0.90s | 0.004 | 0ms | 836 |
| `/services/water-damage-restoration/` | service-landing | amber | 99 | 95 | 100 | 100 | 0.94s | 0.005 | 0ms | 1963 |
| `/services/fire-damage-restoration/` | service-landing | amber | 99 | 95 | 100 | 100 | 0.88s | 0.005 | 0ms | 1774 |
| `/service-areas/rockwall-tx/` | service-area | amber | 99 | 95 | 100 | 100 | 0.83s | 0.006 | 0ms | 1198 |
| `/contact/` | contact | amber | 99 | 96 | 100 | 100 | 0.81s | 0.009 | 0ms | 711 |

INP is null on every page. Lighthouse lab runs cannot measure INP because nobody interacts with
the page, so this is expected.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `has_micromarkup_errors` | 5 of 6 | medium | Organization and LocalBusiness JSON-LD output `"foundingDate": ""`. The source is `sites/reign-restoration/src/lib/brand.ts:32` `foundedYear: ""`, used in `src/lib/schema.ts:81` and `:124`. Set the real founding year, or leave `foundingDate` out when the value is empty. |
| `og_image_broken_host` | 4 of 6 | medium | `images.reign-restoration.com` resolves now, but `/brand/hero.webp` returns HTTP 404. Either upload `brand/hero.webp` to the images bucket, or change the fallback in `src/layouts/BaseLayout.astro:37` to `/images/hero-bg.webp`, which already exists on the apex. |
| `color-contrast` | 6 of 6 | medium | Still open from last month. Footer phone, email, and service links use `text-primary` (`#f2b623`) on white at 1.82:1 (`src/components/Footer.astro:24-25`). Rockwall also has a `text-slate-400` span at 2.56:1. |
| `unused-javascript` | 6 of 6 | medium | New. The GA4 `gtag/js?id=G-NBFCYGQXJY` script (added 2026-08-31) is 155.6 KB, and 68.8 KB of it goes unused on page load. Lighthouse estimates up to 200ms of LCP savings on `/`. |
| `image-delivery-insight` | 6 of 6 | medium | Still open from last month. `/images/logo.png` is 86.7 KB and 86.4 KB of it is wasted. It loads in the header on every page. The homepage hero `hero-bg.webp` wastes another 50.2 KB. |
| `forced-reflow-insight` | 3 of 6 | low | New. 31-104ms of forced reflow from an unattributed inline script. The likely sources are the DNI phone-swap script (`querySelectorAll('a[href^="tel:"]')` followed by DOM writes) or the GA4 inline block. |
| `lcp-discovery-insight` | 3 of 6 | low | Still open. Hero images on the service landings and `/services/` have no `fetchpriority="high"`. `Hero.astro` already has it, but the service-landing hero section does not. |
| `render-blocking-insight` | 6 of 6 | low | `/_astro/_slug_.D67O75JN.css` (about 9 KB) blocks rendering for up to 53ms. Not worth fixing at these scores. |
| `cache-insight` | 6 of 6 | low | Cloudflare's `email-decode.min.js` has a 2-day TTL, and the Rockwall map uses Google Maps assets. Neither is under our control. |
| `network-dependency-tree-insight` | 6 of 6 | low | Critical chain is document, then `page.js` and `_slug_.css`. No action. |
| `has_render_blocking_resources` | 6 of 6 | low | DataForSEO's version of the render-blocking CSS finding above. No separate action. |
| `no_image_title` | 6 of 6 | low | Images have no `title` attribute. Alt coverage is 100%, and `title` is not an SEO or accessibility requirement. No action. |
| `low_content_rate` | 2 of 6 | low | The text-to-HTML ratio is low because the pages carry heavy markup. Word counts beat target on both pages. No action. |

## Money page alerts

- **`/`** (home) - verdict: amber. Lighthouse 97/96/100/100. og:image and twitter:image point
  at `https://images.reign-restoration.com/brand/hero.webp`, which returns 404, so homepage shares
  still show no thumbnail. The meta description is still 172 chars against a 160 limit. LCP rose
  from 0.81s to 1.23s (see regressions).
- **`/services/`** (services-hub) - verdict: amber. Same 404 og:image, plus the empty
  `foundingDate` schema error.
- **`/services/water-damage-restoration/`** and **`/services/fire-damage-restoration/`**
  (service-landing) - verdict: amber. The only medium finding on either page is the empty
  `foundingDate` schema error. Their og:image is correct because each page sets its own image.
- **`/contact/`** (contact) - verdict: amber. Same 404 og:image and schema error. Performance
  99, LCP 0.81s, so the conversion path loads fast.

## Regressions vs prior audit

**Core Web Vitals regression:**
- `/`: LCP went from 805ms to 1231ms (+426ms, threshold is 200ms). Performance went from 100 to 97.
  The LCP element is the same hero image (`/images/hero-bg.webp`). The only new code on the page
  since last month is the GA4 `gtag.js` script, added 2026-08-31. Lighthouse lists it under
  `unused-javascript` with an estimated 200ms LCP savings on this page, and a new 104ms
  `forced-reflow-insight` shows up here too. This is one lab run, so some variance is possible.
  All the other pages slowed by only 37-171ms, below the threshold.

**Verdict transitions:**
- `/services/water-damage-restoration/` went green to amber.
- `/services/fire-damage-restoration/` went green to amber.
  In both cases the only new medium finding is DataForSEO `has_micromarkup_errors`. The cause,
  `foundingDate: ""`, has been in `src/lib/schema.ts` since 2026-08-03, so it was present during
  last month's green audit. The detection changed, not the site. It is still a real defect.

**New issues this month:**
- All 6 URLs: `unused-javascript`. The GA4 tag loads 155.6 KB and leaves 68.8 KB unused.
- 5 URLs (all except `/`): `has_micromarkup_errors`, from the empty `foundingDate` described above.
- `/`, `/services/water-damage-restoration/`, `/service-areas/rockwall-tx/`:
  `forced-reflow-insight` (31-104ms).
- `/contact/`: `low_content_rate`. Word count went up to 711 (target 400). This is a markup-ratio
  flag, not thin content.

**Issues resolved since last audit:** (positive, keep doing this)
- `/services/`, `/service-areas/rockwall-tx/`, `/contact/`: `errors-in-console` no longer
  appears. The `imagesBase` fix in `src/lib/brand.ts:47` (now `https://images.reign-restoration.com`)
  removed the failed DNS lookup for `images.None`. Best Practices is 100 on all three pages,
  up from 96.
- `og_image_broken_host` has only been partly fixed. The host resolves now, but the file is
  missing. See action 1.

## Recommended next actions (priority order)

1. **(money pages, template)** Make the fallback og:image resolve. Right now
   `https://images.reign-restoration.com/brand/hero.webp` returns 404 on `/`, `/services/`,
   `/contact/`, and every service-area page. The fastest fix is to change the fallback in
   `sites/reign-restoration/src/layouts/BaseLayout.astro:37` from
   `${brand.imagesBase}/brand/hero.webp` to `/images/hero-bg.webp`. That file is already served
   on the apex, and the existing absolute-URL logic on lines 40-42 will expand it. The other
   option is to upload `brand/hero.webp` to the images bucket. Then redeploy and check with
   `curl -sI https://images.reign-restoration.com/brand/hero.webp` or the Facebook Sharing
   Debugger.
2. **(money pages, template)** Fix the empty `foundingDate`. Set `foundedYear` in
   `sites/reign-restoration/src/lib/brand.ts:32` to Reign's actual founding year. If nobody knows
   it, change `src/lib/schema.ts:81` and `:124` to leave `foundingDate` out when the value is
   empty. This clears `has_micromarkup_errors` on 5 of 6 pages and puts both service landings
   back to green.
3. **(template, homepage LCP)** Defer GA4 until after the page loads. Remove the
   `<script async src=".../gtag/js?id=G-NBFCYGQXJY">` tag from the head and inject it from a
   `requestIdleCallback` (or `window.load`) handler. Keep the `dataLayer`/`gtag()` stub and the
   delegated `click_to_call`/`generate_lead` listeners inline so no conversions are lost. This
   targets the +426ms homepage LCP regression and the 68.8 KB of unused JS on every page.
4. **(template, accessibility)** Still open from last month. Replace `text-primary` on the footer
   phone, email, and service links in `src/components/Footer.astro:24-25`. `#f2b623` on white is
   1.82:1, and WCAG AA needs 4.5:1. Use a darker yellow for text on white (around `#8a6410`), or
   put the footer on the dark `#0a0b0e` surface. Also change the Rockwall `text-slate-400` span to
   `text-slate-600`.
5. **(money page)** Cut the homepage meta description from 172 chars to under 160. Still open
   from last month. Removing `insured, ` and one adjective from the text ending
   `Licensed, insured, IICRC-certified. Call (214) 304-0621.` gets it under the limit.

Lower priority carry-over: convert `/images/logo.png` (86.7 KB, 99% wasted) to WebP at its
displayed size, and add `fetchpriority="high"` to the service-landing hero image.

## Notes / caveats

- **Desktop-only scoring.** Lighthouse 13.4.0 ran with `formFactor: desktop`,
  `cpuSlowdownMultiplier: 1`, and `throughputKbps: 10240`. Mobile performance scores are usually
  10-20 points lower. Do not present these to the client as mobile-first numbers.
- **Apex, not staging.** `curl -sI https://reign-restoration.com/` shows no `x-robots-tag:
  noindex`, so the staging SEO exclusion does not apply. SEO counted toward the verdict.
- **Client record status mismatch, still open.** `clients/reign-restoration.json` still says
  `status: "onboarding"`. The site has been live on the apex since 2026-08-13, so it was
  audited anyway. Someone should change the status to `active`.
- **The tracking phone number in the Lighthouse snapshots is intentional.** Lighthouse saw footer
  `tel:` links as `+19035277868` because the Rank AI DNI script swaps in a tracking number after
  load (`tpr = "+19035277868"`). The static HTML and the JSON-LD `telephone` are both
  `+12143040621`. This is not a NAP inconsistency.
- **DataForSEO `has_micromarkup: false` is still a false negative.** Its check does not detect
  JSON-LD. Every page has 3-5 JSON-LD blocks that parse cleanly. The separate
  `has_micromarkup_errors` flag is real (see action 2).
- **Issue IDs from manual checks.** `og_image_broken_host` and `meta_description_too_long` are
  marked `source: "manual_verification"` because neither vendor has a check for them. Every
  other ID is a real Lighthouse audit ID or DataForSEO check key.
- **How new issues were detected.** Last month's state file kept only the top 5 Lighthouse issues
  per URL. To avoid false "new issue" flags, any template issue last month recorded on 6 of 6 URLs
  (for example `render-blocking-insight` and `image-delivery-insight`) was counted as present on
  every prior URL.
- **URL selection** came from `plan/url-plan.json` (no `audit-urls.txt`). Water and fire are
  among the four service landings tied at the top priority (9.0) and match last month's set, so
  the before/after comparison is like-for-like. Rockwall is the same service-area page as last
  month.
- **Run cost:** $0.0309 (6 Lighthouse at $0.005, 6 instant_pages at $0.00015). The raw
  DataForSEO API was called directly, so full Lighthouse detail came with the base call.
