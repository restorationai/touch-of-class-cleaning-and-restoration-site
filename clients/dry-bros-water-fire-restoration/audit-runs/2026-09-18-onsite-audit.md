# Onsite Audit - Dry Bros Water & Fire Restoration - 2026-09-18

**Live origin audited:** https://drybros.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** first audit
**Form factor:** desktop only (Lighthouse 13.4.0, cpuSlowdownMultiplier=1, 10240 Kbps, 1350x940)

> Scores below are DESKTOP. Mobile would typically land 10 to 20 performance points lower. Do not quote these as mobile-first numbers.

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 98.3 | n/a |
| Accessibility | 95.2 | n/a |
| Best Practices | 100 | n/a |
| SEO | 100 | n/a |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | Words |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 98 | 100 | 100 | 100 | 1.1s | 0.004 | 1149/1200 |
| `/services/` | services-hub | green | 98 | 91 | 100 | 100 | 1.1s | 0.003 | 777/800 |
| `/services/water-damage-restoration/` | service-landing | green | 98 | 95 | 100 | 100 | 1.2s | 0.024 | 1870/1100 |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 100 | 1.0s | 0.030 | 1857/1100 |
| `/service-areas/naperville-il/` | service-area | green | 98 | 95 | 100 | 100 | 1.1s | 0.003 | 1288/900 |
| `/contact/` | contact | green | 99 | 95 | 100 | 100 | 1.0s | 0.006 | 711/400 |

All six pages returned HTTP 200. No broken internal links, no broken external links, no broken resources, no mixed content, no duplicate titles or descriptions. Every page has exactly one H1, a correct self-referencing canonical, full image alt coverage, and a valid JSON-LD block.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is an 800x433 8-bit RGB PNG weighing 437 KB and is rendered at roughly 130x72 CSS px. Re-export as WebP at 2x display size. Saves about 425 KB on every page. |
| `color-contrast` | 5 | high | Breadcrumb links (`a.text-dark/50`) render #888c93 on #ffffff = 3.37:1 at 12px, below the WCAG AA 4.5:1 floor. Accent CTA (`a.btn-accent`) renders #ffffff on #fd8b00 = 2.36:1. |
| `lcp-discovery-insight` | 5 | high | The LCP hero image (`main > section.relative > div.absolute > img.w-full`) has no priority hint. Add `fetchpriority="high"` to the hero `<img>` in the layout. |
| `network-dependency-tree-insight` | 5 | high | Critical request chain has no `preconnect` hints. Add `<link rel="preconnect">` for the font and Cloudflare asset origins. |
| `render-blocking-insight` | 4 | high | `_astro/_slug_.FQt5HprV.css` (8.9 KB) blocks first paint for a measured 52 ms. Inline the critical subset or preload the route stylesheet. |
| `has_render_blocking_resources` | 6 | low | Same root cause as `render-blocking-insight`. One stylesheet plus one script per page. |
| `no_image_title` | 6 | low | Images carry no `title` attribute. Cosmetic only; alt text is present and complete on every image. No action needed. |
| `cache-insight` | 3 | medium | Cloudflare's injected `email-decode.min.js` has a short cache lifetime. Third-party, not fixable in the template. |
| `high_loading_time` | 3 | low | DataForSEO's crawler measured TTFB of 780 to 1718 ms on a cold edge fetch. Lighthouse measured LCP near 1.1s on the same pages, so this is cold-cache variance, not a persistent origin problem. |
| `word_count_below_target` | 2 | low | `/` is at 1149/1200 words and `/services/` at 777/800. Both within 4 percent of target. Content task, not technical. |

## Money page alerts

None. All four money-page archetypes audited (`/`, `/services/`, the two top service landings, and `/contact/`) came back green.

The one caveat worth tracking: the `.btn-accent` call-to-action button fails WCAG AA contrast at 2.36:1 on `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`, and `/service-areas/naperville-il/`. It does not flip the verdict because accessibility still scores 95, but it is the primary conversion control on those pages.

## Regressions vs prior audit

First audit for this client. No comparison data. This run is the baseline for next month.

## Recommended next actions (priority order)

1. **(template, high impact)** Replace `/images/logo.png`. It is an 800x433 8-bit RGB PNG with no alpha channel, 437 KB, served on all six audited pages and rendered at roughly 130x72 CSS px. Re-export as WebP at about 260px wide (2x) and it drops to single-digit KB, saving roughly 425 KB per page load. While editing, fix the markup: the header `<img>` declares `width="64" height="64"` on an image whose intrinsic ratio is 1.85:1, so the declared aspect ratio is wrong.
2. **(money page, conversion)** Darken the accent CTA. `a.btn-accent` renders #ffffff on #fd8b00 at 2.36:1, failing WCAG AA for 14px bold text. Either darken the button background to about #b35f00 for white text, or keep #fd8b00 and switch the label to #021939 (the brand navy). Affects the two top service landings and the service-area page.
3. **(template, accessibility)** Darken breadcrumb links. `a.text-dark/50` resolves to #888c93 on white = 3.37:1 at 12px. Raise the token to at least #64696f to clear 4.5:1. This is the single audit costing accessibility 5 points on five of six pages.
4. **(template, LCP)** Add `fetchpriority="high"` to the hero image in the shared section layout. Lighthouse `lcp-discovery-insight` reports `priorityHinted: false` on five pages; the image is already eagerly loaded and discoverable in the initial document, so the priority hint is the only missing piece.
5. **(per-page, accessibility)** On `/services/`, the `tel:8773792767` link inside `div.prose-body > p` is distinguishable from surrounding text by color alone (`link-in-text-block`). Add an underline to inline body links. This is the extra audit that puts `/services/` at 91 accessibility instead of 95.

## Notes / caveats

- **Desktop only.** The DataForSEO Lighthouse call ran `formFactor=desktop` with `cpuSlowdownMultiplier=1` and `throughputKbps=10240`. Mobile scores are not covered by this run.
- **Client record status.** `clients/dry-bros-water-fire-restoration.json` has `status: "onboarding"`, not `"active"`. The audit proceeded because `build_status` is `pushed_main` and `apex_cutover.completed_at` is set, so the site is live and auditable. Ops owner should flip the status to `active`.
- **Schema false negative.** DataForSEO's `has_micromarkup` check returns false on all six pages. This is wrong. Each page serves a valid JSON-LD block (LocalBusiness, Organization, WebSite, BreadcrumbList, FAQPage, Service, PostalAddress, GeoCoordinates). The check only detects Microdata and RDFa attributes, not JSON-LD. No missing-schema issue was recorded, and none should be opened.
- **Fresh deploy.** Apex cutover completed at 18:53 UTC and a main-branch deploy landed at 23:01 UTC on the same day as this scan. Scores reflect that build on a warm Cloudflare edge.
- **URL selection.** No `audit-urls.txt` exists, so the six URLs were auto-derived from `plan/url-plan.json`. The two service landings are the joint-highest priority entries (9.0): water damage and fire damage. No `service-area` entry carries `primary: true` and there is no Chicago service-area page to match the business city, so the rule fell through to the first area in plan order, Naperville.
- **Tooling deviation.** The `on_page_lighthouse` and `on_page_instant_pages` MCP tools are not exposed by this MCP server build, which only provides generic `api_request`. The audit called the DataForSEO REST API directly at `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` with the same desktop settings. Raw responses were written to disk and parsed, never read into context.
- **Cost.** 6 Lighthouse calls at $0.005 plus 6 instant_pages calls at $0.0051 = $0.0606 total, well under the $0.30 to $0.50 target.
