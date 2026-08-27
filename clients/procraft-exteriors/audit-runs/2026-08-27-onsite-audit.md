# Onsite Audit - ProCraft Exteriors - 2026-08-27

**Live origin audited:** https://staging.rankai-procraft-exteriors.pages.dev (staging)
**Site verdict:** red
**URLs audited:** 5
**Prior audit:** first audit
**Form factor:** desktop (Lighthouse desktop config, cpuSlowdownMultiplier=1)

> **Staging environment caveat.** This run hit the Cloudflare Pages staging preview because the client record has `domain: null` and no apex cutover. `curl` confirmed `x-robots-tag: noindex` on that origin, so the Lighthouse `is-crawlable` audit fails and the SEO category is pinned at 69 on every page. **SEO is inconclusive for this run and was excluded from all verdicts** - verdicts below use performance, accessibility and best practices only. Do not read the 69 as an SEO problem.

> **Separate from that caveat**, this audit found two genuine build defects that would ship to the apex domain unchanged. They are the reason the site verdict is red. See "Template-level issues".

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 100.0 | n/a |
| Accessibility | 96.2 | n/a |
| Best Practices | 96.0 | n/a |
| SEO | 69.0 (inconclusive) | n/a |

Pages by verdict: green: 0, amber: 0, red: 5, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 100 | 100 | 96 | 69* | 0.48s | 0.0143 | 0ms |
| `/services/` | services-hub | red | 100 | 95 | 96 | 69* | 0.47s | 0.002 | 0ms |
| `/services/storm-damage-restoration/` | service-landing | red | 100 | 95 | 96 | 69* | 0.48s | 0.003 | 0ms |
| `/service-areas/st-louis-mo/` | service-area | red | 100 | 95 | 96 | 69* | 0.48s | 0.0029 | 0ms |
| `/contact/` | contact | red | 100 | 96 | 96 | 69* | 0.48s | 0.0201 | 0ms |

*SEO column is a staging artifact, excluded from verdicts. INP is null on all pages (no lab value on a cold load).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `errors-in-console` | 5 | high | Generate and deploy the missing image assets. `/images/hero-bg.webp` 404s on all 5 pages, `/images/services.webp` and `/images/team.webp` 404 on `/` and `/services/`. `photo-manifest.json` has empty `assets` and `slots`, so no photos were ever produced for this client. |
| `canonical` | 5 | high | Set `domain` in `clients/procraft-exteriors.json` (currently `null`) and re-render. The build falls back to `procraft-exteriors.invalid`, which poisons `<link rel=canonical>`, the JSON-LD `@id` anchors (`#organization`, `#website`, `#identity`), `og:image`, and the logo `<img src>` on every page. |
| `render-blocking-insight` | 5 | low | Inline the 8.7KB `_astro/_slug_.*.css` bundle in `<head>` or preload it. Costs 52-54ms per page. Low priority: performance is already 100. |
| `is-crawlable` | 5 | low | No action. Staging-only `x-robots-tag: noindex`, injected by Cloudflare Pages on `*.pages.dev` previews. Resolves at apex cutover. |
| `color-contrast` | 4 | medium | Change the breadcrumb link class from `text-dark/50` (#888c93 on #ffffff, 3.37:1 at 12px) to at least `text-dark/70`. Needs 4.5:1 to pass WCAG AA. |
| `low_character_count` | 2 | low | Expand `/` to 1200 words (currently 1095) and `/services/` to 800 (currently 793). Both are marginal. |

## Money page alerts

- **`/`** (home) - verdict: red. Lighthouse is clean (perf 100, a11y 100, BP 96, LCP 0.48s). Red is driven entirely by the two template defects: canonical points to `https://procraft-exteriors.invalid/`, and the page logs broken resource loads for the logo host `images.procraft-exteriors.invalid` and `/images/hero-bg.webp`.
- **`/services/`** (services-hub) - verdict: red. Lighthouse is clean (perf 100, a11y 95, BP 96, LCP 0.47s). Red is driven entirely by the two template defects: canonical points to `https://procraft-exteriors.invalid/services/`, and the page logs broken resource loads for the logo host `images.procraft-exteriors.invalid` and `/images/hero-bg.webp`.
- **`/services/storm-damage-restoration/`** (service-landing) - verdict: red. Lighthouse is clean (perf 100, a11y 95, BP 96, LCP 0.48s). Red is driven entirely by the two template defects: canonical points to `https://procraft-exteriors.invalid/services/storm-damage-restoration/`, and the page logs broken resource loads for the logo host `images.procraft-exteriors.invalid` and `/images/hero-bg.webp`.
- **`/contact/`** (contact) - verdict: red. Lighthouse is clean (perf 100, a11y 96, BP 96, LCP 0.48s). Red is driven entirely by the two template defects: canonical points to `https://procraft-exteriors.invalid/contact/`, and the page logs broken resource loads for the logo host `images.procraft-exteriors.invalid` and `/images/hero-bg.webp`.

The service-area page `/service-areas/st-louis-mo/` is red for the same two reasons but is not a money-page archetype.

## Regressions vs prior audit

First audit for this client - no comparison data. This state file becomes next month's baseline.

## Recommended next actions (priority order)

1. **(template, blocker)** Set `domain` in `clients/procraft-exteriors.json`. It is `null`, so the renderer emits the RFC-2606 placeholder `procraft-exteriors.invalid` into every canonical tag, every JSON-LD `@id`, the `og:image` URL, and the header logo `src`. Every page currently canonicalizes to a host that does not resolve. Nothing this site publishes can be indexed correctly until this is fixed and the site is re-rendered and re-pushed.
2. **(template, blocker)** Produce the missing image assets. `/images/hero-bg.webp` 404s on all 5 audited pages; `/images/services.webp` and `/images/team.webp` 404 on the homepage and services hub. `clients/procraft-exteriors/photo-manifest.json` has `"assets": {}` and `"slots": {}`, so the photo pipeline never ran for this client. Every audited page renders with a broken hero background and a broken logo.
3. **(money pages, accessibility)** Fix the breadcrumb contrast. `nav.container-wide > ol.flex > li.flex > a.text-dark/50` renders #888c93 on #ffffff at 12px = 3.37:1, below the 4.5:1 WCAG AA threshold. Affects `/services/`, `/services/storm-damage-restoration/`, `/service-areas/st-louis-mo/` and `/contact/`. One class change in the breadcrumb component.
4. **(process)** Cut over the apex domain, then re-audit to get a real SEO score. SEO is inconclusive this run. Note that `https://rankai-procraft-exteriors.pages.dev` already serves this same build without the noindex header, so it can be audited for a true SEO reading before cutover if needed.
5. **(per-page, low)** Bring `/` up to its 1200-word target (currently 1095) and `/services/` to 800 (currently 793). Both are marginal and neither affects the verdict.

## Notes / caveats

- Audited the Cloudflare Pages staging preview because clients/procraft-exteriors.json has domain=null and no apex_cutover.completed_at. curl confirmed x-robots-tag: noindex on the staging origin, so the Lighthouse SEO category (69 on every page) is deflated by a failing is-crawlable audit. SEO was EXCLUDED from every verdict; verdicts use performance, accessibility and best_practices only. SEO score is inconclusive until apex cutover.
- The production Pages origin https://rankai-procraft-exteriors.pages.dev serves the same build WITHOUT the noindex header (build_status is pushed_main). A future run could target it for a real SEO score before apex cutover.
- Client record status is "onboarding", not "active". Audit proceeded because build_status is pushed_main and all 5 URLs returned HTTP 200.
- url-plan.json contains only one service-landing archetype, so slot 3 yielded 1 URL instead of 2. Total audited set is 5 URLs, not 6.
- plan-input.json marks chesterfield-mo as the primary service area, but url-plan.json generates no /service-areas/chesterfield-mo/ page (the homepage carries Chesterfield). Slot 4 fell back to the first area slug, st-louis-mo.
- DataForSEO instant_pages reported has_micromarkup=false, but raw HTML inspection confirms JSON-LD (LocalBusiness, Organization, WebSite, BreadcrumbList, FAQPage, Service) on all 5 pages. Treated as a DataForSEO false negative, not a missing-schema finding.
- Lighthouse ran DESKTOP only (formFactor=desktop, cpuSlowdownMultiplier=1). Mobile scores would typically run 10-20 performance points lower.
- INP is null on every page: the inp-breakdown-insight audit returned no value on a cold lab load. TTI was not substituted for INP.

What passed cleanly and needs no action: performance is 100 on all 5 pages (LCP 0.47-0.48s, TBT 0ms, CLS 0.002-0.020); titles are 56-62 chars and meta descriptions 112-158 chars, all in range; every page has exactly one H1; no duplicate titles or descriptions; image alt coverage is 100 percent; no broken internal or external links; no mixed content; JSON-LD schema is present and typed correctly on all 5 pages.
