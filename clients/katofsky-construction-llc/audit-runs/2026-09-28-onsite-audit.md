# Onsite Audit - Katofsky Construction LLC - 2026-09-28

> **STAGING AUDIT: SEO SCORE IS INCONCLUSIVE.** This run hit the Cloudflare Pages staging preview because the apex cutover has not happened yet. The origin returns `x-robots-tag: noindex` (confirmed with `curl -sI`), so the Lighthouse `is-crawlable` audit fails on every page and SEO scores 69 across the board. That is a staging artifact, not a site defect. SEO is recorded below but was **excluded from every verdict**: inconclusive, staging noindex artifact, re-audit after apex cutover.

**Live origin audited:** https://staging.rankai-katofsky-construction-llc.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit (First audit for this client - no comparison data.)
**Form factor:** desktop only (Lighthouse 13.4.0, cpuSlowdownMultiplier 1, throughputKbps 10240)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 96 | n/a |
| Accessibility | 96 | n/a |
| Best Practices | 100 | n/a |
| SEO | 69 (inconclusive, staging noindex) | n/a |

Pages by verdict: {green: 0, amber: 6, red: 0, error: 0}

The Lighthouse numbers are strong. Every page scores 95 or higher on performance, accessibility, and best practices. LCP is under 1.4s, CLS is 0.024 or lower, and TBT is 0ms. No page has broken links, broken resources, mixed content, missing H1s, or missing alt text. **All six pages are amber for one shared reason: the LocalBusiness JSON-LD in the layout has data-quality problems** (medium severity under the schema-warning rule). Fixing that one component should turn most pages green.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 96 | 100 | 100 | 69* | 1.4s | 0.021 |
| /services/ | services-hub | amber | 97 | 95 | 100 | 69* | 1.3s | 0.003 |
| /services/fire-damage-restoration/ | service-landing | amber | 97 | 95 | 100 | 69* | 1.2s | 0.003 |
| /services/roofing/ | service-landing | amber | 96 | 95 | 100 | 69* | 1.4s | 0.004 |
| /service-areas/penn-hills-pa/ | service-area | amber | 97 | 95 | 100 | 69* | 1.2s | 0.003 |
| /contact/ | contact | amber | 96 | 96 | 100 | 69* | 1.4s | 0.024 |

\* SEO deflated by the staging `x-robots-tag: noindex` header (`is-crawlable` fails). It does not count toward the verdict.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `schema_localbusiness_relative_image_url` | 6 | medium | In the shared LocalBusiness/Organization schema component, turn `image`, `logo`, and `Organization.logo.url` into absolute URLs (`https://katofskyconstruction.com/images/logo.png`) instead of `/images/logo.png`. |
| `rankai_schema_localbusiness_address_quality` | 6 | medium | Normalize the PostalAddress to match the GBP listing exactly: `streetAddress: "150 Leroy St"` (capitalized, no trailing space), `addressLocality: "Pittsburgh"` (not "Pgh"). Replace the geo coordinates (40.4406968, -80.0025666 is the downtown Pittsburgh centroid) with the geocode for 150 Leroy St, 15239. Fix the source in `plan-input.json` `brand.street_address` / `lat` / `lng` and find where "Pgh" enters the build (the same label appears in `geogrid-cities.json`). |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is 682 KB at 1200x800 but displays at 144x96. Export a 288x192 WebP (2x retina) and point the header and footer `<img>` at it. The file is also declared `width="64" height="64"`, which does not match its 3:2 ratio, so fix those attributes too. Lighthouse estimates 450 to 600ms and about 680 KB saved on every page. Also recompress `/images/hero-bg.webp` (184 KB, 92 to 136 KB savings on `/services/` and `/contact/`) and `/images/team.webp` (210 KB, 112 KB savings on `/`). |
| `color-contrast` | 5 | medium | Breadcrumb links use `text-dark/50` (#888c93 on #ffffff, 3.37:1 at 12px). Change the breadcrumb component class to `text-dark/70` or darker to meet 4.5:1. This alone lifts accessibility from 95 to about 100 on five pages. |
| `lcp-discovery-insight` | 5 | medium | The inner-page hero `<img>` (`section.relative > div.absolute > img.w-full`) is eager but lacks `fetchpriority="high"`. The home hero already has it. Add `fetchpriority="high"` to the shared inner-page hero component. |
| `rankai_schema_empty_string_properties` | 6 | low | Stop emitting `foundingDate: ""` and `sameAs: []`. Omit the keys when there is no value, or fill `sameAs` with the GBP, Facebook, and BBB profile URLs once confirmed. |
| `is-crawlable` | 6 | high (staging artifact) | No code fix. Resolves at apex cutover. |
| `largest-contentful-paint` | 6 | low | Scores 0.84 to 0.89 at 1.2 to 1.4s. Fixed as a side effect of the logo and hero fixes above. |

## Money page alerts

- **`/`** (home): amber. Meta description is 185 chars (window 70 to 160) and will truncate in the SERP. LocalBusiness schema carries the template issues above. The 682 KB logo is the largest image transfer.
- **`/services/`** (services-hub): amber. Template schema issues, word count 695 vs url-plan target 800, hero missing `fetchpriority="high"`, breadcrumb contrast 3.37:1.
- **`/services/fire-damage-restoration/`** (service-landing): amber. Template schema issues, hero missing `fetchpriority="high"`, breadcrumb contrast. Content (1,779 words), title (65 chars), and meta (131 chars) are all in range.
- **`/services/roofing/`** (service-landing): amber. Same template issues as above. Content (1,857 words) is in range.
- **`/contact/`** (contact): amber. Template schema issues, hero missing `fetchpriority="high"`, breadcrumb contrast. FCP is 776ms, the slowest of the six (others are about 290ms), and it has the only measurable render-blocking cost (54ms from `/_astro/_slug_.BOM1TY-a.css`).

## Recommended next actions (priority order)

1. **(blocker for SEO scoring)** Cut over the apex domain `katofskyconstruction.com` to the Cloudflare Pages build and re-audit. The apex currently resolves to 3.33.130.190 / 15.197.148.33 and does not serve this site (HTTPS timed out, HTTP returned 403), while every canonical, `og:url`, and JSON-LD `url` already points there. SEO findings are deferred until then, not resolved.
2. **(template, money pages)** Fix the shared LocalBusiness/Organization JSON-LD: absolute logo/image URLs, `addressLocality: "Pittsburgh"`, `streetAddress: "150 Leroy St"`, rooftop geo for 15239, and drop the empty `foundingDate` / `sameAs`. This one component change clears the only medium on-page issue on 5 of 6 pages.
3. **(template, high impact)** Replace `/images/logo.png` (682 KB, 1200x800) with a 288x192 WebP and correct the `width`/`height` attributes. Lighthouse estimates about 680 KB and 450 to 600ms saved on every page.
4. **(template)** Darken the breadcrumb link color from `text-dark/50` to `text-dark/70` or darker, and add `fetchpriority="high"` to the inner-page hero image. Both are one-line component changes that affect 5 pages.
5. **(per-page, home)** Cut the home meta description from 185 to 160 characters or fewer. For example: "24/7 water, fire, mold and storm damage restoration in Pittsburgh. Licensed, insured, IICRC-certified. Call (412) 304-9284." (123 chars). Separately, add about 110 words to `/services/` to reach the 800-word target.

## Notes / caveats

- **Staging noindex.** `curl -sI` on the staging origin returned `x-robots-tag: noindex`. SEO was excluded from all verdicts per the staging correction rule. Real SEO scoring waits for the apex re-audit.
- **Desktop only.** Lighthouse ran with `for_mobile: false` (desktop form factor, no CPU throttling, 10 Mbps). Mobile performance would typically land 10 to 20 points lower, and the oversized logo will hurt more on mobile. Do not read these as mobile-first scores.
- **Client status.** `clients/katofsky-construction-llc.json` reads `status: "onboarding"`, not `active`. `build_status` is `pushed_main` and staging serves 200, so the audit proceeded, following the precedent set by other onboarding clients.
- **DataForSEO false negatives not counted.** instant_pages reports `canonical: false` (the staging URL canonicalizes to the apex on purpose) and `has_micromarkup: false`. The raw HTML shows valid JSON-LD on all 6 pages (Organization, WebSite, LocalBusiness, Service, FAQPage, BreadcrumbList as appropriate). `frame: true` on `/service-areas/penn-hills-pa/` is the intended Google Maps embed.
- **URL selection.** Auto-derived from `plan/url-plan.json` (no `audit-urls.txt`). No service-area carries `primary: true`, and the home city (Pittsburgh) has no area page, so the fallback took the first area in the plan, `/service-areas/penn-hills-pa/`. The two service landings are the first two of several entries tied at priority 9.0.
- **No errors.** All 6 Lighthouse and 6 instant_pages calls returned status 20000.
- **Run cost:** about $0.039 (6 Lighthouse live at $0.005, 6 instant_pages at $0.0015).
