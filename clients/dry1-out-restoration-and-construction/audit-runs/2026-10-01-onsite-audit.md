# Onsite Audit - Dry1 Out Restoration and Construction - 2026-10-01

**Live origin audited:** https://staging.rankai-dry1-out-restoration-and-construction.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit. First audit for this client - no comparison data.
**Form factor:** desktop (Lighthouse 13.4.0, for_mobile=false). Mobile scores would typically run 10-20 performance points lower. These are NOT mobile-first scores.

## Environment caveat - SEO is inconclusive on staging

The staging preview returns `x-robots-tag: noindex` (checked today). Because of that, the Lighthouse `is-crawlable` audit fails on all 6 URLs and holds SEO at 69 on every page. `is-crawlable` is the only failing SEO audit. This comes from the preview host and is not a defect in the site.

**SEO is excluded from every verdict in this report.** The score is still recorded in the state file. SEO status: `inconclusive - staging noindex artifact, re-audit after apex cutover`. Verdicts use Performance, Accessibility and Best Practices only.

The apex has not been cut over. `dry1out.com` 301-redirects to `www.dry1out.com`, which still serves the legacy WordPress site.

## Read this: the hero image is broken on every page

Lighthouse scores are high, but there is a visible defect on all 6 pages. Every page loads its hero `<img>`, `og:image` and `twitter:image` from `https://images.dry1out.com/brand/hero.webp`. That hostname has no DNS record, and it fails both from Lighthouse and from the runner. The homepage also requests `/images/hero-bg.webp` (its above-the-fold background) and `/images/team.webp`, and both return 404.

As a result, visitors see no hero photo, and social shares have no preview image. The scoring rubric only counts this through the Best Practices score (`errors-in-console`, 96), so the pages still score green. Treat it as the top fix anyway.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.5 | n/a |
| Accessibility | 95.3 | n/a |
| Best Practices | 96.0 | n/a |
| SEO (excluded) | 69.0 | n/a |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 98 | 96 | 96 | 69* | 1.13s | 0.005 |
| `/services/` | services-hub | green | 98 | 95 | 96 | 69* | 1.15s | 0.026 |
| `/services/fire-damage-restoration/` | service-landing | green | 98 | 95 | 96 | 69* | 1.15s | 0.005 |
| `/services/mold-remediation/` | service-landing | green | 99 | 95 | 96 | 69* | 0.79s | 0.009 |
| `/service-areas/san-diego-ca/` | service-area | green | 99 | 95 | 96 | 69* | 0.80s | 0.005 |
| `/contact/` | contact | green | 99 | 96 | 96 | 69* | 0.82s | 0.004 |

\* SEO is excluded from the verdict because of the staging noindex artifact. TBT is 0ms on every page. INP is null because Lighthouse navigation mode does not measure it.

On-page checks were clean on all 6 pages:

- Every page has exactly one H1.
- All titles are 36-65 characters.
- All canonicals are self-referencing on `https://dry1out.com/...`, which is expected before cutover.
- There are no broken links, no mixed content and no images missing alt text.
- JSON-LD parses on every page. The home page has Organization, WebSite and LocalBusiness. The landings have Service, LocalBusiness and BreadcrumbList, plus FAQPage on mold. The area page has LocalBusiness and BreadcrumbList. DataForSEO's `has_micromarkup: false` is a false negative.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `errors-in-console` | 6 | high | `images.dry1out.com` does not resolve. Bind it as the custom domain of the client's R2 image bucket (`dry1out.com` is already on Cloudflare nameservers), or have the build emit an image host that works before cutover. Home also needs `/images/hero-bg.webp` and `/images/team.webp`, which are both 404. |
| `image-delivery-insight` | 6 | medium | `/images/logo.png` is 856 KB at 1814x867 but displays at 134x64 (167x80 on some pages). This one file is 80% of every page's ~1.0 MB weight. Ship a 2x WebP (about 340x160, under 20 KB) with explicit width and height. Lighthouse estimates up to 650ms LCP savings on the slower pages. |
| `color-contrast` | 6 | medium | The footer CSLB license link (`footer ... a.underline`) is `#d6d6d6` on `#ffffff` at 12px, a 1.45:1 ratio. Change it to `text-slate-600` (`#475569`) or darker. The area page also has `span.text-slate-400` at 2.56:1; change it to `text-slate-600`. |
| `low_content_rate` | 5 | low | Hub 92/800 words, fire damage 161/1100, San Diego 138/900, contact 170/400, home 664/1200. Mold remediation (1346) is the only page that has been written. This belongs to the content pipeline and is not a template fix. |
| `render-blocking-insight` | 6 | low | `_astro/_slug_.EwSzLEnj.css` (9 KB), estimated at 0-50ms. Not worth acting on at Performance 98-99. |
| `network-dependency-tree-insight` | 6 | low | Diagnostic only, with no score impact. |
| `is-crawlable` | 6 | environment | Caused by the staging noindex header. Re-audit after apex cutover. |

## Money page alerts

- **`/`** (home) - verdict: amber. Performance 98, Accessibility 96 and Best Practices 96 are all strong. The only reason for amber is the meta description, which is 192 characters (target 70-160). The home page also has the broken hero background (`/images/hero-bg.webp` 404 and `images.dry1out.com` unresolved) and the broken `/images/team.webp`. It is the only page with 3 console errors.

## Regressions vs prior audit

Not applicable. This is the first audit for this client.

## Recommended next actions (priority order)

1. **(money page + template, high)** Fix the hero image on every page. Add a DNS record and R2 custom-domain binding for `images.dry1out.com` (the zone is already on Cloudflare), then confirm `https://images.dry1out.com/brand/hero.webp` returns 200. Also upload `/images/hero-bg.webp` and `/images/team.webp` to the site's public images, or remove those references from the homepage template. This clears `errors-in-console` on all 6 pages and restores the hero and social preview images. `images.{domain}` also fails to resolve for katofsky, drycor and dry-county, so check the image-host step of the pipeline as well, not just this client.
2. **(money page, medium)** Shorten the homepage meta description in `plan/url-plan.json` / `plan-input.json` from 192 to 160 characters or fewer. Keep "(888) 379-1688" and "24/7" within the first 155 characters. This is the only thing keeping `/` amber.
3. **(template, medium)** Replace `/images/logo.png` (856 KB, 1814x867) with a resized WebP of about 340x160, and set `width`/`height` on the header and footer `<img>`. This cuts every page from about 1.0 MB to about 0.2 MB.
4. **(template, medium)** Change the footer CSLB license link color from `#d6d6d6` to `text-slate-600`, and change `text-slate-400` on the service-area template to `text-slate-600`. This clears `color-contrast` on all 6 pages.
5. **(unblocks SEO scoring)** Schedule the apex cutover from the legacy WordPress site at `www.dry1out.com`. After cutover, record `apex_cutover.completed_at` and re-audit on `https://dry1out.com` so SEO counts toward the verdict.

## Notes / caveats

- URLs came from `plan/url-plan.json` (Mode B, since there is no `audit-urls.txt`). Three landings are tied at priority 9.0, so the first two in plan order were used: fire damage and mold remediation. Water damage was not audited. No service area has `primary: true`, and there is no Vista area page (`/service-areas/vista-ca/` returns 404), so the first area slug, `/service-areas/san-diego-ca/`, was used as the fallback. Add `primary: true` to an area so this choice stays the same each month.
- Client `status` is `onboarding`, not `active`. The audit went ahead because `build_status` is `pushed_main` and staging is reachable. This matches prior audits of other onboarding clients.
- Lighthouse failures (`errors-in-console`, `color-contrast`, `image-delivery-insight`) are already reflected in the category scores, so they were not counted a second time as on-page severity. This follows the precedent of earlier audits.
- The `on_page_lighthouse` and `on_page_instant_pages` MCP tools are not available in this MCP build. The raw endpoints `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` were called directly, and the full Lighthouse JSON was parsed on disk. Total API cost was $0.041.
- All 6 URLs returned HTTP 200 and audited without errors. No re-runs were needed.
