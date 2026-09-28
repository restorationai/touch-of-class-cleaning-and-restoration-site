# Onsite Audit, HomeLyft Restoration MS, 2026-09-28

**Live origin audited:** https://homelyft.net (apex)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** 2026-08-27 (Cloudflare Pages staging preview)
**Form factor:** desktop only (see caveats)

## Read this first

**1. Last month's blocker is fixed.** The `https://None/` canonical is gone. All 6 pages now self-canonicalize to `https://homelyft.net/...`, `og:url` matches, JSON-LD `@id`/`url` use the real domain, and `/sitemap-index.xml` points at `https://homelyft.net/sitemap-0.xml`. The apex serves no `x-robots-tag` header, so SEO counts toward the verdict this month and scores 100 on every page.

**2. The site is still red, for a different single reason: click-to-call is broken on every page.** Every `tel:` link in the header, hero, CTA bands, and footer, plus the `telephone` field in the `Organization` and `LocalBusiness` JSON-LD, is:

```
<a href="tel:+112282845200">
"telephone":"+112282845200"
```

That is a doubled `+1` country code. The stored phone is already E.164 (`+12282845200` in `plan-input.json`) and the template prepends another `+1`. The result is an 11-digit number after the country code, which is not a valid North American number, so a mobile visitor who taps "Call" gets a failed or misrouted call. On a 24/7 emergency restoration site, the phone tap is the primary conversion. Lighthouse and DataForSEO do not check this; it was found by reading the served HTML.

One exception proves the root cause: the inline prose link on `/services/` is correct (`tel:+12282845200`), because it is written from the raw value without the prefix.

Strip this one template issue out and every page would be green on scores alone. Performance is 98-99, Best Practices 100, SEO 100.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.7 | -0.8 |
| Accessibility | 94.7 | -0.6 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | +31.0 (prior was staging noindex artifact) |

Pages by verdict: green: 0, amber: 0, red: 6, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 98 | 96 | 100 | 100 | 1.0s | 0.002 |
| `/services/` | services-hub | red | 98 | 91 | 100 | 100 | 0.9s | 0.002 |
| `/services/water-damage-restoration/` | service-landing | red | 99 | 95 | 100 | 100 | 0.9s | 0.024 |
| `/services/fire-damage-restoration/` | service-landing | red | 99 | 95 | 100 | 100 | 0.8s | 0.030 |
| `/service-areas/eastabuchie-ms/` | service-area | red | 99 | 95 | 100 | 100 | 0.9s | 0.003 |
| `/contact/` | contact | red | 99 | 96 | 100 | 100 | 0.9s | 0.007 |

TBT is 0ms on five pages and 5ms on `/`. INP is null (needs field data, not available in a lab run). All Core Web Vitals are well inside Google's "good" thresholds.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `rankai:tel_link_malformed` | 6 | high | In the phone helper used by the header, hero, CTA band, footer, and JSON-LD, stop prepending `+1` when the stored value already starts with `+`. Emit `tel:+12282845200` and `"telephone":"+12282845200"`. Rebuild and redeploy. |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is still a 24KB 500x500 PNG in a 64x64 slot (23KB wasted on every page). Inner-page heroes on `/services/` and `/contact/` still hardcode `src="/images/hero-bg.webp"` (142KB) with no `srcset`, wasting 50KB and 94KB. The homepage hero already has a correct `srcset`. |
| `unused-javascript` | 6 | medium | New since apex. `googletagmanager.com/gtag/js?id=G-CY001B6T82` loads 159KB with about 69KB unused, costing 70-120ms on every page. Load gtag with `defer` after first paint, or move it behind Cloudflare Zaraz / Partytown. |
| `color-contrast` | 6 | medium | Primary red `#e33e2e` on white is 4.2:1 (needs 4.5:1) on footer links, footer phone/email, and white-on-red CTA buttons. Darken the primary token one step (for example `#c9321f` or the existing `primary-700`). Breadcrumb `text-dark/50` (`#878b95`, 3.41:1) is still failing on inner pages; switch to `text-dark/70`. On `/contact/`, the `/privacy/` and `/terms/` links in the form consent line are `#992014` on `#111827` (2.17:1); use `text-primary-300` or white. |
| `cache-insight` | 6 | low | Only flagged asset is Cloudflare's injected `email-decode.min.js` (1KB, 2-day TTL, 0KB savings). Disable Cloudflare Email Address Obfuscation to remove the script, or ignore. |
| `lcp-discovery-insight` | 5 | low | Inner-page hero `img` lacks `fetchpriority="high"`. Homepage hero already has it and passes. Add the attribute in the section-hero component. |
| `render-blocking-insight` / `network-dependency-tree-insight` | 6 | low | `_astro/_slug_.DKL7az8c.css` (9KB) blocks render for 0-30ms. Acceptable at this size. |
| `low_content_rate` | 2 | low | DataForSEO text-to-HTML ratio flag on `/` and `/services/`. Both pages carry large inline JSON-LD and card grids. Informational; no action needed unless it persists alongside ranking issues. |
| `forced-reflow-insight` | 2 | low | Flagged on the water-damage landing and the service-area page with no attributed source. Informational. |

## Money page alerts

All five money pages are red for the same single cause: the phone CTA dials an invalid number.

- **`/`** (home) red. Broken `tel:` links. Perf 98, A11y 96 (down from 100, the primary-red contrast failure is new here), LCP 1.0s. Meta description is still 174 characters, target 70-160.
- **`/services/`** (services-hub) red. Broken `tel:` links. A11y 91, lowest on the site: breadcrumb contrast, primary-red contrast, and the unstyled inline `tel:` link in prose (`link-in-text-block`). 768 words vs url-plan target 800.
- **`/services/water-damage-restoration/`** (service-landing) red. Broken `tel:` links only. Perf 99, A11y 95.
- **`/services/fire-damage-restoration/`** (service-landing) red. Broken `tel:` links only. Perf 99, A11y 95.
- **`/contact/`** (contact) red. Broken `tel:` links. This is the page where a visitor is most likely to tap the number. LCP rose from 0.6s to 0.9s (see regressions). Hero still ships the full 142KB `hero-bg.webp`.

## Regressions vs prior audit

The prior run audited the staging Pages preview; this run audited the apex behind Cloudflare. Some deltas are environment, not code.

**Verdict transitions:** none. All 6 pages were red last month (unresolvable canonical) and are red this month (malformed phone link). The cause changed; the verdict did not.

**Score and Core Web Vitals regressions:**
- `/contact/`: LCP 636ms to 933ms (+297ms, over the 200ms threshold). Still under 1s and well inside "good". Most likely cause is the new gtag script plus apex/CDN differences, not a content change. No per-URL category dropped 5 or more points; no site average dropped 3 or more.

**New issues this month:**
- All 6 pages: `rankai:tel_link_malformed`. Not in last month's report, but it is not visible to either vendor tool and may have been present on staging undetected.
- All 6 pages: `unused-javascript` from Google Analytics gtag (not present on staging).
- All 6 pages: `cache-insight` from Cloudflare's `email-decode.min.js` (apex-only, Cloudflare injects it).
- `/`: `color-contrast` (primary red `#e33e2e` at 4.2:1). Present on inner pages already via breadcrumbs.
- `/`, `/services/`: `low_content_rate`.
- `/services/water-damage-restoration/`, `/service-areas/eastabuchie-ms/`: `forced-reflow-insight`.

**Issues resolved since last audit:** (positive, keep doing this)
- All 6 pages: `rankai:canonical_host_unresolvable` is gone. Canonical, `og:url`, JSON-LD, and sitemap all use `https://homelyft.net`.
- All 6 pages: `is-crawlable` no longer fails. Apex has no noindex header; SEO is 100 everywhere.
- `/`, `/services/water-damage-restoration/`, `/contact/`: `high_loading_time` no longer flagged.

## Recommended next actions (priority order)

1. **(money page, template, blocking)** Fix the phone formatter so it does not prepend `+1` to an already-E.164 number. After redeploy, confirm `curl -s https://homelyft.net/contact/ | grep -o 'tel:[^"]*' | sort -u` returns only `tel:+12282845200`, and that the JSON-LD `telephone` matches. While in that helper, render the visible number as `(228) 284-5200` instead of the raw `+12282845200` that currently shows in the header, footer, and body copy.
2. **(template, high impact)** Add `srcset`/`sizes` and `fetchpriority="high"` to the inner-page section-hero `img` (copy the homepage hero pattern), and replace `/images/logo.png` with a 160x160 WebP or an SVG. Saves 94KB on `/contact/`, 50KB on `/services/`, 23KB on every page.
3. **(template, accessibility)** Darken the primary red token from `#e33e2e` to a value that clears 4.5:1 on white, change breadcrumbs from `text-dark/50` to `text-dark/70`, and lighten the consent-line links on the `/contact/` form. This lifts accessibility on all 6 pages.
4. **(template, performance)** Defer the Google Analytics gtag load (or move it to Zaraz/Partytown). Removes about 69KB of unused JS and 70-120ms per page, and should pull `/contact/` LCP back toward 0.6s.
5. **(money page, per-page)** Trim the homepage meta description from 174 to under 160 characters, and add `underline` to inline prose links so the `tel:` link on `/services/` stops relying on color alone.

## Notes / caveats

- **Apex, first time.** `apex_cutover.completed_at` is 2026-09-11, so this is the first apex audit. The prior baseline was the staging Pages preview, so small score and LCP deltas partly reflect staging vs apex+CDN, and the +31 SEO delta reflects removal of the staging noindex header, not a code fix.
- **Desktop only.** Lighthouse 13.4.0 ran `formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`. Mobile scores would typically run 10-20 performance points lower. Do not report these numbers as mobile-first.
- **Tooling deviation.** The dedicated `on_page_lighthouse` and `on_page_instant_pages` MCP tools are not in this MCP build. Data came from `/v3/on_page/lighthouse/live/json` (`for_mobile: false`) and `/v3/on_page/instant_pages` over authenticated HTTP, written to disk and parsed out of band. The live Lighthouse endpoint returns full audit detail, so no separate `full_data` call was needed.
- **Issue-ID honesty.** `rankai:tel_link_malformed`, `rankai:meta_description_too_long`, and `rankai:word_count_below_target` are prefixed because no vendor check ID covers them. All were verified directly against the served HTML or url-plan.
- **URL selection.** Same 6 URLs as last month for comparability. `water-damage-restoration` and `fire-damage-restoration` are tied at the top url-plan priority (9.0) with `mold-remediation` and `roofing`. No `primary: true` service area exists and `/service-areas/gulfport-ms/` still 301-redirects, so the fallback `/service-areas/eastabuchie-ms/` was used again.
- **NAP, outside this audit's scope.** The site phone (228-284-5200, 1311 Spring St) still differs from the GBP listing (228-325-1496, 3200 B Ave), as already noted in the client record. This needs reconciling with the client separately from the `tel:` fix.
- **Clean bills of health.** No broken internal or external links, no broken resources, no mixed content, no duplicate titles, exactly one `h1` per page, all titles 57-65 characters, 100% image alt coverage, valid JSON-LD on every page (`Organization`, `WebSite`, `LocalBusiness`, `Service`, `FAQPage`, `BreadcrumbList`), and HSTS, `x-content-type-options`, `referrer-policy`, and `permissions-policy` headers present on the apex.
- **Run cost.** About 0.041 USD (Lighthouse 0.030, instant_pages 0.011), well under the 0.30 to 0.50 target.
