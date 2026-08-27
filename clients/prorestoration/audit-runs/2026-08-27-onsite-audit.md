# Onsite Audit - ProRestoration Services - 2026-08-27

**Live origin audited:** https://prorestorationca.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client - no comparison data
**Form factor:** desktop (Lighthouse 13.4.0, cpuSlowdownMultiplier 1, throughputKbps 10240). Mobile scores would typically run 10-20 performance points lower.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.7 | n/a |
| Accessibility | 91.3 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 100.0 | n/a |

Pages by verdict: green: 2, amber: 4, red: 0, error: 0

Performance, best practices and SEO are effectively perfect on desktop. Everything holding this site at amber is accessibility (two template-level WCAG failures) and edge cacheability of the HTML.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 99 | 96 | 100 | 100 | 0.77s | 0.041 | 0ms |
| `/services/` | services-hub | amber | 99 | 90 | 100 | 100 | 0.87s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 100 | 90 | 100 | 100 | 0.76s | 0.003 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | green | 100 | 90 | 100 | 100 | 0.81s | 0.005 | 0ms |
| `/service-areas/oildale-ca/` | service-area | amber | 100 | 91 | 100 | 100 | 0.80s | 0.003 | 0ms |
| `/contact/` | contact | amber | 100 | 91 | 100 | 100 | 0.77s | 0.021 | 0ms |

INP is null on every page: Lighthouse lab runs do not emit an INP value without user interaction.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `link-name` | 6 | high | Footer address block renders `<a href="mailto:"></a>` with an empty href and no link text. Root cause: `clients/prorestoration.json` has `contact: null` and `awaiting_intake` still lists "email address", so the template emits the anchor with an empty address. Wrap the email `<div>` in a truthiness guard on the email field, and add the address as link text when it exists. Cloudflare Email Obfuscation rewrites it to `/cdn-cgi/l/email-protection#b1` (a salt with no payload), which decodes back to an empty `mailto:` at runtime. |
| `color-contrast` | 5 | high | Breadcrumb links use `text-dark/50`, which computes to `#888c93` on `#ffffff` at 12px = 3.37:1 (WCAG AA needs 4.5:1). Change the breadcrumb link class to `text-dark/70` or a `#6b7280`-class gray. Also affects `.btn-accent` (`#ffffff` on `#ef4444` at 14px bold = 3.76:1) on the service-landing and service-area CTA blocks: darken the accent to roughly `#dc2626` or bump the button label to 18px. |
| `unsized-images` | 6 | low | Header logo `/images/logo.svg` at `header.bg-white > div.container-wide > a.flex > img.h-14` has no `width`/`height`. Add `width="240" height="64"` to the logo `<img>` in the header layout. |
| `lcp-discovery-insight` | 5 | low | Hero `/images/hero-bg.webp` is the LCP element on every inner-page template and is eager-loaded and discoverable, but has no `fetchpriority="high"`. Add `fetchpriority="high"` to the hero `<img>` in the inner-page hero component. |
| `image-delivery-insight` | 4 | low | The homepage hero ships a responsive `srcset` (`hero-bg-480w/768w/...`); every other template hardcodes the full 165KB `/images/hero-bg.webp`. Port the homepage hero's `srcset`/`sizes` onto the shared inner-page hero. Measured waste: 118KB on `/contact/`, 135KB on `/services/`, 51KB on `/service-areas/oildale-ca/`. On `/services/`, the service card thumbnails also ship 476x268 files into a 403x225 slot. |
| `cache-insight` | 6 | low | Only flagged resource is Cloudflare's own `email-decode.min.js` (952 bytes). This disappears once the empty mailto anchor is removed, because Email Obfuscation will have nothing to rewrite. |
| `render-blocking-insight` / `has_render_blocking_resources` | 6 | low | `/_astro/_slug_.C7jGmKiW.css` (8.7KB) blocks render for a measured 54ms. Low priority at current scores. |
| `high_loading_time` | 3 | medium | The origin sends `cache-control: public, max-age=0, must-revalidate` on HTML, so Cloudflare returns `cf-cache-status: DYNAMIC` and every request is a full origin round-trip. Cold fetches measured 4444ms on `/services/`, 4567ms on `/contact/`, 3318ms on `/service-areas/oildale-ca/` (connection time 280-288ms vs 34-68ms warm). Add a Cloudflare Cache Rule to edge-cache HTML for these static Astro pages, or raise `max-age` on the Pages `_headers` file. |
| `network-dependency-tree-insight` | 6 | low | No origins are preconnected. Marginal at current LCP figures. |
| `no_image_title` | 6 | low | Images carry `alt` but no `title` attribute. Cosmetic. No action recommended. |
| `low_content_rate` | 2 | low | Text-to-HTML ratio 8.5% on `/` and 9.0% on `/services/`. Both pages are markup-heavy hubs. No action. |

## Money page alerts

- **`/`** (home) - verdict: amber. Meta description is 184 characters against a 70-160 target, so it will be truncated in the SERP. Accessibility 96 (empty footer mailto link). Cold-fetch load 461ms, the fastest of the set.
- **`/services/`** (services-hub) - verdict: amber. Accessibility 90 (breadcrumb contrast plus empty footer mailto). Cold-fetch load 4444ms with uncacheable HTML. 135KB of avoidable image weight, mostly the non-responsive hero.
- **`/contact/`** (contact) - verdict: amber. Accessibility 91 with two `link-name` failures on this page: the footer mailto plus a second empty `mailto:` in the contact card (`div.space-y-5 > div.flex > div > a.font-bold`), which is the primary conversion block. Cold-fetch load 4567ms, the slowest of the set. 118KB of avoidable hero weight.

## Plan conformance

`/service-areas/oildale-ca/` renders `LocalBusiness`, `FAQPage` and `BreadcrumbList` JSON-LD, but `plan/url-plan.json` specifies `schema_stubs: [local-business, service, breadcrumb-list]`. The `Service` node is not emitted. Spot-checked `/service-areas/rosedale-ca/` and `/service-areas/delano-ca/`: same gap, so this is template-wide across all 10 service-area pages. Note that `FAQPage` is being emitted here even though the plan does not call for it.

## Regressions vs prior audit

First audit for this client. No comparison data. This run establishes the baseline that the 2026-09 audit will diff against.

## Recommended next actions (priority order)

1. **(money page, high impact)** Fix the empty `mailto:` anchors. There are two on `/contact/` and one in the footer of every page. Each is a keyboard tab stop with no accessible name, which is a WCAG 2.4.4 / 4.1.2 failure on the primary conversion page. Two-part fix: (a) guard the email anchor in the footer and contact-card templates so it only renders when an email exists, and (b) collect the client's email address, which is still open in `onboarding_notes.awaiting_intake`. This single fix is worth roughly 4-6 accessibility points on all 6 pages.
2. **(template, high impact)** Raise breadcrumb link contrast from `text-dark/50` (`#888c93`, 3.37:1) to at least 4.5:1 against white, and darken `.btn-accent` from `#ef4444` (3.76:1 with white 14px bold text) to about `#dc2626`. Affects 5 of 6 audited pages and every breadcrumbed page sitewide.
3. **(infra, money pages)** Add a Cloudflare Cache Rule that edge-caches HTML for `prorestorationca.com`. HTML currently ships `max-age=0, must-revalidate`, producing `cf-cache-status: DYNAMIC` and cold loads of 3.3-4.6s on `/services/`, `/contact/` and the service-area template. Lighthouse does not see this because it measures a warm connection.
4. **(template)** Port the homepage hero's responsive `srcset`/`sizes` onto the shared inner-page hero component and add `fetchpriority="high"`. Saves 118KB on `/contact/`, 135KB on `/services/`, 51KB on `/service-areas/`, and removes the LCP discovery warning on 5 pages.
5. **(per-page)** Trim the homepage meta description from 184 to under 160 characters. Current text ends with "Licensed, insured, IICRC-certified. Call (661) 393-9306." and will be cut off in the SERP.

## Notes / caveats

- Audited the apex production origin, not staging. `GET https://prorestorationca.com/` returns 200 with no `x-robots-tag`, so the staging noindex correction does not apply and SEO counts toward the verdict normally.
- Lighthouse ran desktop only. The DataForSEO MCP server in this environment exposes only `api_request` and the `docs_*` tools, with no `on_page_lighthouse` or `on_page_instant_pages` wrapper, so the audit called `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` directly over REST. `for_mobile: false` was sent explicitly to match the documented System 3 desktop baseline. The REST path does accept `for_mobile: true`, so a mobile baseline can be added whenever the team wants one.
- Two DataForSEO checks were verified and discarded as false positives rather than reported. `has_micromarkup: false` fired on all 6 URLs, but that check only detects microdata/RDFa `itemscope`; fetching the HTML confirmed all 6 pages ship valid JSON-LD, including `aggregateRating` (4.8 / 105) nested inside `LocalBusiness` on the homepage. `is_https: true` is a pass, not a defect.
- `clients/prorestoration.json` carries `status: "pending"` rather than `"active"`. The audit proceeded because `build_status` is `pushed_main` and the apex origin serves 200. The pending status reflects outstanding intake items (NS flip, founded year, email address), not site availability. This matches `mcc-restoration`, which is also `pending` and has been audited.
- First Lighthouse attempt failed on all 6 URLs with `40501 Invalid Field: 'categories:best-practices'` at zero cost. Re-run without the `categories` field succeeded.
- Zero broken links, zero broken resources, zero duplicate titles and zero duplicate descriptions across all 6 URLs. Canonicals are self-referencing and correct everywhere. Word counts clear their `url-plan.json` `target_word_count` on every page except `/services/`, which lands at 795 words against a target of 800. That five-word gap is not worth acting on.
- Estimated DataForSEO spend for this run: 0.061 USD (6 Lighthouse at 0.005, 6 instant_pages at 0.0051).
