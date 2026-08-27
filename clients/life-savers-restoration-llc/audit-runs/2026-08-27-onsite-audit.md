# Onsite Audit - Life Savers Restoration LLC - 2026-08-27

**Live origin audited:** https://staging.rankai-life-savers-restoration-llc.pages.dev (staging)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** first audit for this client, no comparison data
**Lighthouse form factor:** desktop

## Environment caveats (read first)

**SEO score is inconclusive this run.** The staging Pages preview returns `x-robots-tag: noindex`, which Cloudflare injects automatically on `*.pages.dev` preview deployments. The Lighthouse `is-crawlable` audit therefore fails on all 6 URLs and drags the SEO category down to 69. This is an artifact of the environment, not a site defect. SEO is recorded in the state file but is **excluded from every verdict in this report**. Verdicts are computed from Performance, Accessibility, and Best Practices only. Re-audit after apex cutover to get a real SEO number.

**Desktop scoring.** Lighthouse ran with `formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`. Mobile scores would typically land 10-20 performance points lower. Do not read these as mobile-first numbers.

**Client record status.** `clients/life-savers-restoration-llc.json` has `status: "onboarding"`, not `"active"`. `build_status` is `pushed_main` and all 6 URLs serve HTTP 200, so the site is live and auditable and the audit proceeded. Logging the deviation rather than failing the run.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98 | n/a |
| Accessibility | 95 | n/a |
| Best Practices | 100 | n/a |
| SEO | 69 (inconclusive) | n/a |

Pages by verdict: green: 0, amber: 0, red: 6, error: 0

The Lighthouse numbers are genuinely strong. The red verdict is not a performance problem. Every one of the 6 pages carries the same high-severity on-page defect described below.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 98 | 96 | 100 | 69 | 1.06s | 0.017 |
| `/services/` | services-hub | red | 98 | 95 | 100 | 69 | 1.13s | 0.003 |
| `/services/water-damage-restoration/` | service-landing | red | 99 | 95 | 100 | 69 | 0.95s | 0.004 |
| `/services/mold-remediation/` | service-landing | red | 98 | 95 | 100 | 69 | 0.98s | 0.004 |
| `/service-areas/las-vegas-nv/` | service-area | red | 98 | 95 | 100 | 69 | 1.06s | 0.004 |
| `/contact/` | contact | red | 98 | 96 | 100 | 69 | 1.06s | 0.056 |

All six Core Web Vitals readings are inside Google's "good" thresholds (LCP under 2.5s, CLS under 0.1, TBT at or under 84ms). No broken internal links, no broken external links, no broken resources, no mixed content, no duplicate titles or descriptions, no missing H1s, and full image alt coverage across all 6 pages.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `canonical` | 6 | high | Site base URL renders as the literal string `None`. Every canonical is `https://none/...`. See root cause below. |
| `has_micromarkup_errors` | 5 | medium | Same root cause: every schema `@id`, `url`, and BreadcrumbList `item` value resolves to `https://None/`. |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is a 6250x3718 PNG (423 KiB) rendered at 134x80 in the header of every page. Resize it. |
| `color-contrast` | 6 | high | Brand primary `#a07828` on white measures 4.02:1 against a 4.5:1 AA requirement. Hits footer phone, email, and `/emergency/` links. |
| `is-crawlable` | 6 | high | Staging noindex artifact. Not a real defect. Resolves at apex cutover. |
| `network-dependency-tree-insight` | 6 | medium | Critical request chain depth. Low practical impact at current LCP of ~1s. |
| `lcp-discovery-insight` | 5 | medium | LCP image not discoverable in the initial HTML on non-home pages. |

### Root cause: the site has no domain configured

`clients/life-savers-restoration-llc.json` has `"domain": null`. The renderer interpolates that null straight into the site base URL, producing the Python string `None`. The damage is site-wide and shows up in four places:

- **Canonical tags:** every page emits `<link rel="canonical" href="https://none/...">`, pointing at a host that does not exist.
- **Open Graph:** `og:url` is `https://None/`, `og:image` is `https://none/images/hero-bg.webp`. Social and AI-answer surfaces that fetch the OG image get nothing.
- **JSON-LD:** every `@id` on Organization, WebSite, LocalBusiness, and Service is `https://None/#organization`, `https://None/#identity`, and so on. BreadcrumbList `item` values are `https://None/` and `https://None/services/`.
- **Micromarkup validation:** DataForSEO flags `has_micromarkup_errors` on the 5 pages that carry Service, FAQPage, or BreadcrumbList blocks. The home page, which carries only Organization, WebSite, and LocalBusiness, is not flagged. The invalid host in the Service and BreadcrumbList URL fields is the most likely trigger, and it should clear once the domain is set. Re-validate after the fix rather than assuming it.

This is one fix. Set the real domain on the client record, re-render, and all four symptoms clear together.

## Money page alerts

All five money pages are red, and all five for the same reason.

- **`/`** (home) - red. Canonical is `https://none/`. Meta description is 186 characters, over the 160 target, so it will be truncated in the SERP. Also the only page flagged for `unsized-images`: the four trust badge images in the credentials strip carry no `width`/`height` attributes.
- **`/services/`** (services-hub) - red. Canonical is `https://none/services/`. Schema validation flagged. Word count is 725 against an 800 target for this archetype, a minor shortfall.
- **`/services/water-damage-restoration/`** (service-landing) - red. Canonical is `https://none/services/water-damage-restoration/`. Schema validation flagged. Content is strong at 2055 words.
- **`/services/mold-remediation/`** (service-landing) - red. Canonical is `https://none/services/mold-remediation/`. Schema validation flagged. 1755 words.
- **`/contact/`** (contact) - red. Canonical is `https://none/contact/`. Schema validation flagged. Highest CLS on the site at 0.056, still inside the good band; the shift comes from the `#estimate` section reflowing after load.

## Regressions vs prior audit

First audit for this client. No comparison data.

## Recommended next actions (priority order)

1. **(money pages, template, blocking)** Set `"domain"` on `clients/life-savers-restoration-llc.json`, which is currently `null`, then re-render and push. This is the same workstream as apex cutover, and it is a hard prerequisite for it: shipping to apex with `https://none/` canonicals would put self-contradicting canonical tags on every indexable page. Then re-audit against the apex origin so the SEO category returns a real number instead of the staging noindex artifact. One change clears all 6 broken canonicals, both broken OG tags, every broken schema `@id`, and probably the 5 micromarkup validation failures.

2. **(template, high impact)** Resize `/images/logo.png`. It is a 6250x3718 PNG weighing 423 KiB, served in the header of all 6 pages, and displayed at 134x80. Export it at roughly 268x160 (2x for retina) as WebP with a PNG fallback. That is 422 KiB of waste removed from every page load on the site, which is between 57 and 100 percent of each page's total image waste.

3. **(template, accessibility)** Darken the brand primary for text on white. `#a07828` on `#ffffff` measures 4.02:1, short of the 4.5:1 WCAG AA minimum for body text. It affects the footer `tel:+17028451325` link, the `mailto:info@lifesaversrestoration.com` link, and the `/emergency/` link on all 6 pages. Darkening to roughly `#8a6620` clears 4.5:1 while staying on-brand. Keep `#a07828` for large headings and non-text accents, where the 3:1 large-text threshold already passes.

4. **(per-page)** Convert the badge and award PNGs on the home page to WebP and add explicit `width`/`height` attributes. `iicrc-certified-firm.png` (67 KiB), `best-of-las-vegas-2023/2024/2025.png` (54, 53, 53 KiB), and `usfcr-verified-vendor.png` (40 KiB) are all near-lossless PNGs displayed at 64x64. This is the remaining 315 KiB of home page image waste and it also clears the `unsized-images` failure.

5. **(per-page)** Trim the home page meta description from 186 characters to under 160. Current text runs to "...Licensed, insured, IICRC-certified. Call (702) 845-1325." Cutting the certification clause keeps the phone number, which is the part that earns the click.

## Notes / caveats

- The `/contact/` on-page scan initially failed inside the 6-URL batch with `40501 Invalid Field: 'url' - duplicate crawl host`, a DataForSEO per-host limit of 5 tasks per instant_pages request. It was re-run on its own and succeeded. All 6 URLs have complete Lighthouse and on-page data. No URL errored out of the audit.
- URLs were auto-derived from `plan/url-plan.json` (Mode B). No `audit-urls.txt` exists for this client. The service-area slot fell back to `/service-areas/las-vegas-nv/`, the first area in the plan, because no plan entry carries `primary: true`. Note that Henderson is the primary service area in `plan-input.json` and is the business's own city, but the url-plan generates no `/service-areas/henderson-nv/` page, so there was no Henderson area page to audit.
- `render-blocking-insight` fails on all 6 pages (a single Astro stylesheet, `_astro/_slug_.DqVUirP7.css`) but did not make the top-5 issue cap on every page, so it does not appear in the template table. Estimated saving is about 50ms. Not worth acting on at a 1.0s LCP.
- The DataForSEO `seo_friendly_url` check reads false on all 6 URLs. The likely cause is the length of the staging hostname. Re-check after apex cutover before treating it as real.
- The dedicated `on_page_lighthouse` and `on_page_instant_pages` MCP tools are not present in the currently connected DataForSEO MCP server, which exposes only `api_request` and the docs tools. This run drove `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` directly through `api_request` and curl. Worth noting for the methodology: the raw endpoint does expose `for_mobile`, so mobile Lighthouse auditing is no longer blocked on an MCP update. This run used `for_mobile: false` to stay consistent with the documented desktop convention across the fleet. Switching the fleet to mobile is a methodology decision, not an audit-time one.
- Run cost: approximately $0.04 (Lighthouse 6 x $0.005, instant_pages 6 x ~$0.0018), well under the $0.30-0.50 target.
