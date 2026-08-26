# Onsite Audit - Coastal Restoration Services Inc - 2026-08-26

**Live origin audited:** https://staging.rankai-coastal-restoration-services.pages.dev (staging)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** first audit for this client - no comparison data
**Form factor:** desktop only (see caveats)

> **Staging environment correction applied.** The Cloudflare Pages preview returns `x-robots-tag: noindex`, which fails the Lighthouse `is-crawlable` audit and deflates the SEO category to 69 on every URL. That is an artifact of the preview host, not a site defect. **SEO is excluded from every verdict in this report** and its status is `inconclusive - re-audit after apex cutover`. Verdicts are computed from Performance, Accessibility, and Best Practices only.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.5 | n/a |
| Accessibility | 91.2 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 69.0 (inconclusive) | n/a |

Pages by verdict: green: 0, amber: 0, red: 6, error: 0

**Read this correctly:** the Lighthouse category scores are excellent. Every page is red because of template-level metadata defects found by the on-page audit, not because of performance or accessibility scoring. Three high-severity template bugs affect all six pages, and all three trace back to one root cause.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 99 | 92 | 100 | 69* | 0.84s | 0.003 | 0ms |
| `/services/` | services-hub | red | 99 | 90 | 100 | 69* | 0.84s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | red | 100 | 91 | 100 | 69* | 0.79s | 0.003 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | red | 100 | 91 | 100 | 69* | 0.78s | 0.003 | 0ms |
| `/service-areas/vandenberg-village-ca/` | service-area | red | 100 | 91 | 100 | 69* | 0.78s | 0.024 | 0ms |
| `/contact/` | contact | red | 99 | 92 | 100 | 69* | 0.83s | 0.002 | 0ms |

\* SEO excluded from verdict - staging noindex artifact.

Core Web Vitals are strong across the board on desktop: LCP 0.78s to 0.84s, CLS at or below 0.024, TBT 0ms on all six pages. INP is not reported in lab runs and is recorded as null.

## Root cause: `domain` is null in the client record

`clients/coastal-restoration-services.json` has `"domain": null`. The site build interpolates that null into every absolute URL as the literal string `None`. This single missing field produces three of the four high-severity findings below.

The correct apex is discoverable: the deployed `robots.txt` already declares `Sitemap: https://callcrs.com/sitemap-index.xml`, and `https://callcrs.com` resolves (301 to `https://www.callcrs.com`, HTTP 200). The build knows the domain in one place and not in another.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `canonical` | 6 | high | `rel=canonical` and `og:url` render as `https://None/...`. Set `domain` in the client record and rebuild. |
| `rankai_jsonld_invalid_entity_id` | 6 | high | JSON-LD `@id`/`url` on Organization, WebSite, LocalBusiness, Service and BreadcrumbList all read `https://None`. Same fix as above. |
| `color-contrast` | 6 | high | Brand gold `#e6ac1a` and hover shade `#af8213` behind white bold text measure 2.04:1 to 3.48:1 against a 4.5:1 requirement. 9 to 24 elements per page. |
| `rankai_wrong_primary_city_in_metadata` | 4 | high | Global pages are geo-targeted to Vandenberg Village instead of Santa Maria. Renderer reads `service_areas[0]` instead of the entry flagged `primary: true`. |
| `target-size` | 6 | medium | Footer `tel:` and `mailto:` links render 17px tall against a 24px minimum. Add vertical padding. |
| `image-delivery-insight` | 6 | medium | Header logo is served at 220x209 for a 67x64 slot (~66KB wasted per page). Hero JPEG/WebP under-compressed. |
| `lcp-discovery-insight` | 5 | medium | LCP hero image is missing `fetchpriority="high"` on every template except the homepage. |
| `render-blocking-insight` | 6 | low | `_astro/_slug_.BT6bhdIk.css` (~9KB) blocks first paint. |
| `network-dependency-tree-insight` | 6 | low | Longest critical chain 143ms to 244ms (document then CSS/JS). Low real impact on desktop. |

`is-crawlable` also fails on all six URLs and is deliberately excluded - it is the staging noindex artifact described above.

## Money page alerts

All five money pages are red. Every one of them carries the broken canonical and the invalid JSON-LD entity IDs.

- **`/`** (home) - red. Canonical `https://none/`, JSON-LD `@id` `https://None`. Lighthouse scores are clean (99/92/100). 11 contrast failures.
- **`/services/`** (services-hub) - red. Plus: title reads "Restoration Services in Vandenberg Village" where the approved url-plan specifies "Restoration Services in Santa Maria | Coastal Restoration Services Inc". Also the heaviest image payload of the set: ~244KB of avoidable image bytes across 12 images.
- **`/services/water-damage-restoration/`** (service-landing) - red. H1 reads "Water Damage Restoration in Vandenberg Village"; plan specifies Santa Maria.
- **`/services/fire-damage-restoration/`** (service-landing) - red. H1 reads "Fire Damage Restoration in Vandenberg Village"; plan specifies Santa Maria.
- **`/contact/`** (contact) - red. Meta description reads "in Vandenberg Village"; plan specifies Santa Maria. ~194KB of avoidable image bytes, the second heaviest.

The wrong-city defect is the most commercially damaging item here. Vandenberg Village is a small outlying community; Santa Maria is the HQ city and the primary market. Twelve service landing pages, the services hub, and the contact page are all currently optimized for the wrong city, and they contradict the approved url-plan.

## Regressions vs prior audit

First audit for this client. No comparison data. This run establishes the baseline for next month.

## Recommended next actions (priority order)

1. **(money pages, template, high impact)** Set `"domain": "callcrs.com"` in `clients/coastal-restoration-services.json` and rebuild/redeploy. This one field fixes `rel=canonical`, `og:url`, and the JSON-LD `@id`/`url` on all 6 audited pages and on all 419 planned pages. Right now every page canonicalizes to a nonexistent host, which will suppress indexation the moment the site is crawlable.

2. **(money pages, template, high impact)** Fix the primary-city selection in the renderer. It currently uses `service_areas[0]` (Vandenberg Village); it must use the entry with `primary: true` (Santa Maria). Verify against `plan/url-plan.json`, which already carries the correct Santa Maria titles, H1s, and meta descriptions for `/services/`, `/contact/`, and all 12 service landings. Re-render and diff the rendered `<title>` against the plan value as a build assertion so this cannot regress silently.

3. **(template, accessibility)** Darken the brand gold for text use. `#e6ac1a` on white is 2.04:1 and `#af8213` behind white text is 3.48:1; both fail WCAG AA. Introduce a text-only token around `#7a5c0e` (which clears 4.5:1 on white) and keep `#e6ac1a` for large non-text fills. Affected components: the top announcement bar, the header CTA button, hero `tel:` CTAs, footer contact links, `.eyebrow` labels, and breadcrumb links (`#8a8aa5` on white, 3.35:1). This is the only thing holding Accessibility at 90-92 instead of 100.

4. **(template, performance)** Add `fetchpriority="high"` to the hero `<img>` in the services-hub, service-landing, service-area, and contact templates. The homepage template already does this correctly; copy that pattern. Then resize the header logo to a 2x asset (roughly 134x128) and serve it as WebP, which removes ~66KB per page site-wide.

5. **(per-page, low)** `/services/` renders 790 words against a url-plan target of 800. Marginal, but the closest page to its floor. Worth topping up when the hub copy is next touched.

## Notes / caveats

- **Staging, not apex.** `domain` is null and there is no `apex_cutover.completed_at`, so per methodology this run audited the Cloudflare Pages preview. Scores on apex plus CDN will differ. The three high-severity metadata defects are NOT staging artifacts and will persist at cutover unless fixed.
- **Desktop only.** Lighthouse ran with `formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`. Mobile scores typically run 10-20 performance points lower, and `target-size` matters considerably more on mobile than the medium severity assigned here implies. Do not present these as mobile-first scores.
- **Vendor false negative on schema.** DataForSEO reported `has_micromarkup: false` for all six URLs. That was verified manually against the rendered HTML and is wrong: JSON-LD is present on every page (Organization, WebSite, LocalBusiness, Service, FAQPage, BreadcrumbList). No missing-schema issue was raised. The real schema problem is the `https://None` identifiers, reported separately.
- **Issue ID provenance.** IDs prefixed `rankai_` are Rank AI derived checks, not vendor audit IDs. Every unprefixed ID (`color-contrast`, `target-size`, `image-delivery-insight`, `render-blocking-insight`, `lcp-discovery-insight`, `network-dependency-tree-insight`, `is-crawlable`, `canonical`, `frame`, `low_character_count`) is a genuine Lighthouse or DataForSEO on-page ID.
- **MCP deviation.** This DataForSEO MCP build does not expose the `on_page_lighthouse` or `on_page_instant_pages` tools, only a generic `api_request`. The audit used authenticated REST calls to `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages`, piped to disk. Same data, same cost basis. Note that the REST path does accept a `for_mobile` flag, so mobile auditing is now technically available and no longer blocked on an MCP update; it was left off this run to keep the desktop baseline comparable.
- **Client status.** The client record says `status: "onboarding"`, not `"active"`. The audit proceeded because `build_status` is `pushed_main` and all six URLs returned HTTP 200. Worth confirming the record should not now read `active`.
- **Clean results worth noting.** No broken internal or external links, no broken resources, no mixed content, no duplicate titles/descriptions/content, exactly one H1 per page, all titles 39-46 chars and all meta descriptions 117-152 chars (both inside target ranges), and no missing image alt text on any of the six pages.
- **Cost.** 6 Lighthouse runs plus 6 instant-pages runs plus 2 probes, approximately $0.046 total, inside the $0.30-0.50 target.
