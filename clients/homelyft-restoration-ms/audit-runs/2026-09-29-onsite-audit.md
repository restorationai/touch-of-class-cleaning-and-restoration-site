# Onsite Audit - HomeLyft Restoration MS - 2026-09-29

**Live origin audited:** https://homelyft.net (apex)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** 2026-08-27 (on the staging Pages preview; URLs compared by path)
**Form factor:** desktop only (DataForSEO Lighthouse wrapper does not expose mobile; expect mobile performance 10-20 points lower)

> **Why red when Lighthouse is 99-100:** every audited page ships a broken click-to-call number. All `tel:` links and the LocalBusiness schema `telephone` are `+112282845200` (13 characters, extra leading 1). The correct number is `+12282845200`. Anyone tapping "Call Us Now" on mobile dials a number that does not exist. This is the only high-severity finding. Fix it and the site drops to amber.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.2 | -0.3 |
| Accessibility | 94.7 | -0.6 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | +31.0 |

Pages by verdict: {green: 0, amber: 0, red: 6, error: 0}

SEO +31 comes from the apex cutover removing the staging `x-robots-tag: noindex`. It is not an on-page change. The apex returns no robots header, so SEO counts toward the verdict this run.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 99 | 96 | 100 | 100 | 1.0s | 0.002 |
| `/services/` | services-hub | red | 99 | 91 | 100 | 100 | 0.9s | 0.002 |
| `/services/water-damage-restoration/` | service-landing | red | 99 | 95 | 100 | 100 | 0.9s | 0.024 |
| `/services/fire-damage-restoration/` | service-landing | red | 99 | 95 | 100 | 100 | 0.9s | 0.030 |
| `/service-areas/eastabuchie-ms/` | service-area | red | 100 | 95 | 100 | 100 | 0.8s | 0.003 |
| `/contact/` | contact | red | 99 | 96 | 100 | 100 | 0.8s | 0.007 |

TBT is 0-20 ms everywhere. INP is not reported by desktop lab runs. On-page basics pass on all 6 pages: one H1, titles 57-65 chars, self-referencing canonicals on `https://homelyft.net`, 100 percent image alt coverage, no broken links or resources, no mixed content, and LocalBusiness + BreadcrumbList + FAQPage schema (plus Service on the landings).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `rankai:tel_link_malformed` | 6 | high | `scripts/build_site.py:318` builds `phone_raw = "+1" + digits(brand.phone)`. `plan-input.json` stores `brand.phone` as E.164 `+12282845200`, so the output becomes `+1` + `12282845200`. Set `brand.phone` to `(228) 284-5200` in `clients/homelyft-restoration-ms/plan-input.json` (and `plan/plan-input.json`) and re-render. That also fixes visible copy, which currently prints the raw `+12282845200` in the header, body text and meta descriptions. |
| `color-contrast` | 6 | medium | The red CTA color `#e33e2e` (from the 09-23 rebrand) scores 4.2:1 against white, both as white text on red buttons and as red text links on white. Darken the primary to `#d4382a` (4.77:1) or `#cf3526` (5.01:1). Also: breadcrumb `text-dark/50` (`#878b95`, 3.41:1) should be `text-dark/70` or darker; footer `/privacy/` and `/terms/` links (`#992014` on `#111827`, 2.17:1) should be `#f87171` (6.41:1); the `text-slate-400` span on service-area pages (2.56:1) should be `text-slate-600`. |
| `unused-javascript` | 6 | low | Only offender is `googletagmanager.com/gtag/js` (~69 KB unused of 159 KB). Costs 70-150 ms at most. Load gtag after the `load` event, or leave it. Not worth a template change on its own. |
| `image-delivery-insight` | 6 | low | 32-132 KB savings per page. Serve `/images/logo.png` as WebP/AVIF at display size (it renders at h-20/h-24), and add a smaller `srcset` candidate for `hero-bg.webp` on inner pages. |
| `lcp-discovery-insight` | 5 | low | Inner-page hero `<img src="/images/hero-bg.webp" loading="eager">` lacks `fetchpriority="high"`. Homepage already has it. Add the same attribute to the inner-page hero component. |
| `render-blocking-insight` | 6 | low | One 9 KB stylesheet (`/_astro/_slug_.DKL7az8c.css`), 0-56 ms. Acceptable; no action needed unless mobile scores fall below 90. |
| `cache-insight` | 6 | low | Cloudflare-injected `email-decode.min.js` (<1 KB, 2-day TTL). Not actionable at site level; disabling Cloudflare Email Obfuscation would remove it. |
| `network-dependency-tree-insight`, `forced-reflow-insight` | 6 / 5 | low | Informational at these scores (reflow is 42-95 ms, unattributed). No action. |

## Money page alerts

- **`/`** (home) red. Broken click-to-call and schema telephone. Meta description is still 174 chars (target 70-160) and ends with the raw number. Perf 99, A11y 96, LCP 1.0s.
- **`/services/`** (services-hub) red. Broken click-to-call and schema telephone. A11y 91 from `color-contrast` and `link-in-text-block` (inline `tel:` link in body copy has 1.26:1 contrast with surrounding text; add an underline). Word count 768 vs target 800.
- **`/services/water-damage-restoration/`** (service-landing) red. Broken click-to-call only. Perf 99, A11y 95.
- **`/services/fire-damage-restoration/`** (service-landing) red. Broken click-to-call only. Perf 99, A11y 95.
- **`/contact/`** (contact) red. Broken click-to-call (7 `tel:` links on the page, all wrong). This is the conversion page; fix first.

## Regressions vs prior audit

No score or Core Web Vitals regressions. No per-URL category dropped by 5 or more points, no site average dropped by 3 or more, and LCP rose 53-193 ms (under the 200 ms threshold). Home accessibility went 100 to 96 because of the new red CTA color.

**Verdict transitions:** none. All 6 pages were red last month and are red this month, but for a different reason: last month it was the `https://None/` canonical, this month it is the phone number.

**New issues this month:**
- All 6 URLs: `rankai:tel_link_malformed`. This is not a regression; staging also serves `+112282845200`. The August audit did not check phone links.
- `/`: `color-contrast`, caused by the 09-23 red CTA rebrand (`#e33e2e`, 4.2:1).
- `/`, `/services/`: `low_content_rate` (low text-to-HTML ratio; low severity, ignore unless word counts drop).
- `/service-areas/eastabuchie-ms/`: `bf-cache` (iframe navigation, marked not actionable by Lighthouse).
- All 6 URLs: `unused-javascript`, `cache-insight`; 5 URLs: `forced-reflow-insight`. These come from gtag and Cloudflare scripts that run only on the apex zone. They are environment changes, not code regressions.

**Issues resolved since last audit:** (positive - keep doing this)
- All 6 URLs: `rankai:canonical_host_unresolvable`. Canonicals and `og:url` now point to `https://homelyft.net/...`.
- All 6 URLs: `is-crawlable`. Staging noindex is gone on apex; SEO is 100 on every page.
- `/`, `/services/water-damage-restoration/`, `/contact/`: `high_loading_time` is no longer flagged.

## Recommended next actions (priority order)

1. **(money page, template, high impact)** Fix the phone number. In `clients/homelyft-restoration-ms/plan-input.json` and `plan/plan-input.json`, change `brand.phone` from `+12282845200` to `(228) 284-5200`, then re-render and push. Confirm with `curl -s https://homelyft.net/contact/ | grep -o 'tel:[+0-9]*' | sort -u` returning only `tel:+12282845200`, and the LocalBusiness `telephone` reading `+12282845200`. This flips all 6 pages off red and fixes the visible number format in headers, body copy and meta descriptions.
2. **(template, accessibility)** Darken the primary red from `#e33e2e` to `#d4382a` in the Tailwind theme, change the footer legal links to `#f87171`, and change breadcrumb `text-dark/50` to `text-dark/70`. This clears `color-contrast` on all 6 pages and should put accessibility at 98-100.
3. **(money page)** Rewrite the homepage meta description to 160 characters or fewer, ending with the formatted number, e.g. "Water, fire, mold and storm damage restoration in Gulfport and nearby areas. Licensed, insured, IICRC-certified. Call (228) 284-5200." (133 chars).
4. **(money page)** On `/services/`, underline the inline `tel:` link in body copy to clear `link-in-text-block`, and add about 40 words of hub intro copy to reach the 800-word target.
5. **(template, low)** Add `fetchpriority="high"` to the inner-page hero image and ship `logo.png` as a display-sized WebP. This clears `lcp-discovery-insight` on 5 pages and most of `image-delivery-insight`.

## Notes / caveats

- **First apex audit.** Apex cutover completed 2026-09-11. The prior baseline was the staging Pages preview, so deltas compare the same paths across two origins. The apex adds Cloudflare zone scripts and gtag that staging did not have.
- **URL selection.** Same six paths as August for comparability. Four landings tie at priority 9.0 (fire, mold, roofing, water); water and fire are kept. No service area is marked `primary: true`, and Gulfport (the business city) has no service-area page, so `/service-areas/eastabuchie-ms/` (first area slug) is used again.
- **Other client likely affected by the same phone bug.** `clients/puroclean-east-las-vegas/plan-input.json` also stores `brand.phone` in E.164 (`+17025513040`), so its site probably renders `tel:+117025513040` too. Worth checking in that client's next audit, or hardening `build_site.py:318` to strip a leading country code 1 from 11-digit input.
- **NAP mismatch (out of scope for this audit, recorded for visibility).** The client record notes the GBP listing uses 228-325-1496 at 3200 B Ave, while the site uses 228-284-5200 at 1311 Spring St. This belongs to citations/GBP work, not onsite.
- **Excluded DataForSEO checks:** `no_image_title` (title attribute on images is not a ranking signal; alt coverage is 100 percent) and `has_render_blocking_resources` (duplicate of Lighthouse `render-blocking-insight`). `frame` on the service-area page is the Google Maps embed and is expected.
- **Data source.** The dedicated `on_page_lighthouse` / `on_page_instant_pages` MCP tools are not in this build; data came from `/v3/on_page/lighthouse/live/json` (desktop) and `/v3/on_page/instant_pages` directly. Full Lighthouse JSON was pulled and failing audits extracted on disk. Cost about $0.04.
