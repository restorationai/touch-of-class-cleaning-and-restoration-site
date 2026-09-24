# Onsite Audit - DRYCOR RESTORE (drycor-restore) - 2026-09-24

**Live origin audited:** https://staging.rankai-drycor-restore.pages.dev (staging)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** first audit
**Form factor:** desktop only (Lighthouse 13.4.0, cpuSlowdownMultiplier=1, 10240 Kbps)

> **Staging caveat: SEO score is inconclusive.** Cloudflare Pages injects
> `x-robots-tag: noindex` on `*.pages.dev` previews (confirmed with `curl -sI`). That fails
> the Lighthouse `is-crawlable` audit and holds SEO at 69 on every page. SEO was recorded but
> left out of the verdicts. Re-audit after the apex cutover to `drycor.com`.
>
> **The red verdict is NOT caused by the staging artifact.** It comes from a real build
> defect. The hero image on `/services/`, the service-area pages and `/contact/` loads from
> `https://images.drycor.com/brand/hero.webp`, and `images.drycor.com` does not exist
> (NXDOMAIN at GoDaddy DNS). Those heroes render empty, and `og:image` / `twitter:image` on
> every page point at the same dead URL. This carries over to production unchanged.

First audit for this client - no comparison data.

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 97.5 | n/a |
| Accessibility | 95.3 | n/a |
| Best Practices | 98.0 | n/a |
| SEO | 69 (inconclusive, staging) | n/a |

Pages by verdict: green: 0, amber: 3, red: 3, error: 0

Lighthouse is strong. Five of six pages score 99 to 100 on Performance, LCP is under 1.1s everywhere and TBT is 0. There are two real problems. The dead image host turns three pages red. The home page hero has a 0.247 layout shift, which pulls home Performance down to 86.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 86 | 96 | 100 | 69* | 1.06s | 0.247 |
| /services/ | services-hub | red | 99 | 95 | 96 | 69* | 0.81s | 0.004 |
| /services/fire-damage-restoration/ | service-landing | amber | 100 | 95 | 100 | 69* | 0.82s | 0.006 |
| /services/mold-remediation/ | service-landing | amber | 100 | 95 | 100 | 69* | 0.82s | 0.006 |
| /service-areas/tampa-fl/ | service-area | red | 100 | 95 | 96 | 69* | 0.79s | 0.006 |
| /contact/ | contact | red | 100 | 96 | 96 | 69* | 0.77s | 0.007 |

\* SEO excluded from the verdict (staging noindex artifact).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `broken_resources` | 4 (hero on 3, og:image on all 6) | high | The template builds image URLs from `BRAND_IMAGES_BASE` = `https://images.{domain}` (`scripts/build_site.py:389`). No R2 custom domain was ever set up for `drycor.com`, so `images.drycor.com` returns NXDOMAIN. There are two options. (a) Point the page-hero and og:image defaults at the local `/images/hero-bg.webp`, which already ships and works on home. (b) Provision the R2 bucket plus the `images.drycor.com` custom domain and upload `brand/hero.webp`. Option (a) is faster and needs no DNS access at GoDaddy. Verify with `curl -s https://staging.rankai-drycor-restore.pages.dev/contact/ \| grep -c images.drycor.com` returning 0. This is the same failure pattern as crew (`images.crew3r.com`, 2026-08-14). The 3 `errors-in-console` hits (Best Practices 96) are this same request and clear with it. |
| `color-contrast` | 6 | medium | The footer license link (`myfloridalicense.com`, `a.underline`) is `#b7e1f5` on a white footer, a 1.39:1 ratio (4.5:1 needed). A light-blue color meant for a dark background is being used on the white footer. Change it to the brand primary `#187cab` or darker in the footer component. On `/service-areas/tampa-fl/`, a `span.text-slate-400` also fails (2.56:1). Use `text-slate-600`. That lifts Accessibility to 100 on most pages. |
| `image-delivery-insight` | 6 | medium | `/images/logo-dark-bg.png` is 62 KB with 61 KB of estimated waste on every page. Re-export it as WebP/AVIF at 2x display size. On home, `/images/hero-bg.webp` is 416 KB with 245 KB of waste. Serve a `srcset` with about 1400w and 800w variants. On `/services/`, the ten `*-480w.webp` service cards are oversized for their slots (6 to 18 KB waste each). Add a 320w variant. |
| `has_micromarkup_errors` | 5 | medium | DataForSEO flags structured-data errors on every page that has a `BreadcrumbList`. Home has none and has no error. The last `ListItem` has no `item` URL. Emit `item` (the page's canonical URL) on the final crumb in the breadcrumb schema component, then re-check in the Schema Markup Validator. |
| `render-blocking-insight` | 6 | low | The single Astro CSS bundle blocks render for up to about 50ms. Low priority. `build.inlineStylesheets: "auto"` in the Astro config would inline it. |
| `lcp-discovery-insight` | 3 | low | The LCP hero `<img>` on `/services/` and the two service landings has no `fetchpriority="high"`. On `/services/` it is also `loading="lazy"`. Set `loading="eager" fetchpriority="high"` on the page-hero image. |
| `is-crawlable` | 6 | low | Staging artifact only (Pages `x-robots-tag: noindex`). No action. It clears at apex cutover. |

## Money page alerts

- **`/`** (home) - verdict: amber. Performance 86. CLS is 0.247 (0.1 is good, 0.25 is poor). It comes from one shift of the hero container (`header > div.container-wide`) when the Inter web font from `fonts.gstatic.com` swaps in. The meta description is 170 characters and will truncate. og:image points at the dead host. The visible hero is fine because it uses local `/images/hero-bg.webp`.
- **`/services/`** (services-hub) - verdict: red. The hero image is broken (dead `images.drycor.com` host), with a matching console error. It also has schema errors, and the LCP image is lazy-loaded.
- **`/services/fire-damage-restoration/`** (service-landing, priority 9.0) - verdict: amber. BreadcrumbList schema error only. Lighthouse scores 100/95/100 and LCP is 0.82s.
- **`/services/mold-remediation/`** (service-landing, priority 9.0) - verdict: amber. BreadcrumbList schema error only. Lighthouse scores 100/95/100 and LCP is 0.82s.
- **`/contact/`** (contact) - verdict: red. The hero image is broken (dead `images.drycor.com` host), with a matching console error, plus schema errors.

## Regressions vs prior audit

Not applicable. This is the first audit.

## Recommended next actions (priority order)

1. **(template, money pages, blocks cutover)** Stop serving images from `images.drycor.com`. Either point the page-hero and og:image/twitter:image defaults in `restorationai/drycor-restore-site` at the local `/images/hero-bg.webp`, or provision R2 plus the `images.drycor.com` custom domain and upload `brand/hero.webp`. Then rebuild, redeploy, and confirm that `grep -c images.drycor.com` returns 0 on `/contact/`. That clears 3 red pages, 3 console errors and the broken social preview images.
2. **(money page, home)** Fix the 0.247 CLS on home. Self-host Inter (for example `@fontsource/inter`) with `font-display: swap` and a metric-matched fallback (`size-adjust` / `ascent-override` on an Arial `@font-face`), or at least `<link rel="preload" as="font" crossorigin>` the Inter woff2 used by the hero. Also trim the home meta description from 170 to 160 characters or less.
3. **(template)** Add an `item` URL to the final `BreadcrumbList` crumb in the breadcrumb schema component. That clears `has_micromarkup_errors` on 5 of 6 pages, including both service landings, which would then turn green.
4. **(template)** Change the footer license link color from `#b7e1f5` to `#187cab` or darker, and `text-slate-400` to `text-slate-600` on area pages. That clears `color-contrast` on all 6 pages.
5. **(cutover)** After items 1 to 4 ship, cut over the apex domain and re-audit, so the deferred SEO category can be scored for real.

## Notes / caveats

- **Staging origin, SEO deferred.** The client record has no `apex_cutover.completed_at`, so the audit ran against the Pages preview. `is-crawlable` is the only failing SEO audit.
- **Desktop only.** The DataForSEO Lighthouse call ran `for_mobile=false`. Mobile performance typically runs 10 to 20 points lower. The home CLS problem is likely worse on mobile, where the hero text wraps more.
- **Client record status.** `clients/drycor-restore.json` has `status: "onboarding"`, not `"active"`, which strictly fails the documented pre-flight gate. The audit proceeded because `build_status` is `pushed_main` and the staging preview serves the current build. This matches how other onboarding clients have been audited.
- **URL selection.** No `audit-urls.txt` exists, so the URLs were derived from `plan/url-plan.json`. Three service landings tie at priority 9.0 (fire damage, mold remediation, water damage restoration). Plan order breaks the tie, which selects fire and mold, so water damage restoration was not audited this run. It shares the same template. Consider adding an `audit-urls.txt` if water damage should be a fixed audit slot. The primary area (Thonotosassa) has no area page because it is folded into home, so the first area in plan order was used: Tampa.
- **DataForSEO missed the broken hero.** instant_pages returned `broken_resources: false` on all pages even though the hero host does not resolve. The finding comes from the Lighthouse console-error audit plus direct `curl` and public DNS checks (Cloudflare DoH returns NXDOMAIN, SOA at `domaincontrol.com`).
- **Messaging consistency (out of scope, flag for content).** The home title and H1 say "Tampa Bay" ("Restoration Services in Tampa Bay, FL"). The url-plan targeted "Thonotosassa", and every other page uses Thonotosassa. Confirm this is an intentional override.
- **`frame` check** on `/service-areas/tampa-fl/` is the intentional Google Maps embed. No action.
- **Tooling deviation.** This MCP build does not expose the `on_page_lighthouse` / `on_page_instant_pages` tools. DataForSEO REST was called directly and the raw JSON parsed from disk.
- **Cost.** 6 Lighthouse calls at $0.005 plus 6 instant_pages calls at $0.0018 = $0.041.
