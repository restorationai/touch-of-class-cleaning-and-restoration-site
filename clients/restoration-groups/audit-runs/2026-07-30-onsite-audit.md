# Onsite Audit - The Restoration Group - 2026-07-30

**Live origin audited:** https://therestorationgroup.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client, no comparison data

**Form factor:** desktop only. The DataForSEO MCP wrapper does not expose a `form_factor` parameter, so every score below is a desktop run (`cpuSlowdownMultiplier=1`, `throughputKbps=10240`, Lighthouse 13.4.0). Mobile scores would typically land 10 to 20 performance points lower. Do not quote these as mobile-first numbers.

Apex cutover completed 2026-07-23, and `curl -sI` confirmed no `x-robots-tag: noindex` on the origin, so the SEO category counts toward every verdict. The staging-noindex correction did not apply to this run.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.7 | n/a |
| Accessibility | 94.8 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 100.0 | n/a |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

This is a technically healthy build. Performance is near-perfect across the board, total blocking time is 0 ms on all six pages, and there are no broken links, no mixed content, no missing or duplicate titles, H1s or meta descriptions, no canonical problems, and 100 percent image alt coverage. The single amber is the homepage, and it is amber on one narrow issue described below.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 99 | 93 | 100 | 100 | 0.86s | 0.003 | 0ms |
| `/services/` | services-hub | green | 99 | 95 | 100 | 100 | 0.89s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 100 | 95 | 100 | 100 | 0.77s | 0.003 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | green | 100 | 95 | 100 | 100 | 0.79s | 0.003 | 0ms |
| `/service-areas/kenilworth-nj/` | service-area | green | 99 | 95 | 100 | 100 | 0.82s | 0.003 | 0ms |
| `/contact/` | contact | green | 95 | 96 | 100 | 100 | 0.81s | 0.127 | 0ms |

INP is not measurable in a Lighthouse lab run and is recorded as null in the state file rather than estimated.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 6 | medium | Two distinct failures. Breadcrumb links use `text-dark/50` which renders `#8f949d` on white at 3.04:1 against a 4.5:1 requirement (5 pages). The homepage trust-bar paragraphs use `text-dark/60` which renders `#787f89` at 4.04:1 (5 nodes). Raise both to `text-dark/70` (`#626a75`, 5.47:1) in the shared layout. `text-dark/65` also passes at 4.67:1 but leaves no margin. |
| `render-blocking-insight` | 6 | medium | `/_astro/_slug_.8ogNlefX.css` (8.7 KB) blocks first paint on every page. Measured cost is only 55 ms on `/contact/`, so inline it as critical CSS rather than restructuring the pipeline. |
| `lcp-discovery-insight` | 5 | medium | The LCP image is discoverable in the initial document and is not lazy-loaded, but `fetchpriority="high"` is missing. The homepage already applies it correctly. Copy that hero pattern into the services-hub, service-landing and service-area templates. |
| `image-delivery-insight` | 4 | medium | `hero-bg.webp` is a single 297 KB file reused at every viewport, wasting 131 KB on `/`, 207 KB on `/services/`, 183 KB on `/service-areas/` and 214 KB on `/contact/`. Generate responsive widths and serve via `srcset`. |
| `cache-insight` | 6 | low | The only flagged asset is Cloudflare's injected `email-decode.min.js` on a 2-day TTL, worth 288 bytes. Cloudflare controls this TTL. No action available; noted so it is not re-investigated next month. |
| `network-dependency-tree-insight` | 6 | low | The critical request chain runs through `fonts.gstatic.com`. Self-hosting Inter would remove the third-party hop and also fix the `/contact/` layout shift below. |
| `has_render_blocking_resources` | 6 | low | DataForSEO's own view of the same Astro CSS bundle above. One fix clears both. |
| `no_image_title` | 6 | low | Images carry no `title` attribute. Alt coverage is 100 percent, and `title` is not a ranking factor. Cosmetic, listed for completeness only. |
| `low_content_rate` | 2 | low | Text-to-HTML ratio is low on `/` and `/services/`. Both are image and card heavy by design; word counts are healthy. No action. |

## Money page alerts

- **`/`** verdict: amber. The only thing keeping the homepage off green is a meta description of 188 characters against the 70 to 160 target, which Google will truncate by roughly the last 28 characters. Accessibility is also the site's lowest at 93, from the 4.04:1 contrast failure on the five trust-bar paragraphs. Performance is 99 with a 0.86s LCP, so this is a metadata and contrast fix, not a speed problem.

All other money pages (`/services/`, both service landings, `/contact/`) came back green.

## Regressions vs prior audit

Not applicable. No `clients/restoration-groups/onsite-audit.json` existed before this run, so this is the client's first audit and regression detection was skipped. Next month's run will have a baseline to compare against.

## Recommended next actions (priority order)

1. **(money pages, needs owner decision before anything else)** The `LocalBusiness` JSON-LD on all six pages publishes `8 Harlow Crescent, Fair Lawn, NJ 07410` and links `sameAs` to the Fair Lawn GBP (`cid 5612453956771500683`), while every page title, H1 and meta description targets Kenilworth and the client record's `nap` block says `500 S 31st St, Kenilworth, NJ 07033` with the Kenilworth GBP (`cid 8008820373441604497`). Structured data and on-page targeting currently point at two different cities. Note the ambiguity is real: the client record's own `gbp_inventory_2026_07_15` note says the Fair Lawn listing is the app-connected and selected one, so the schema may be deliberate and the `nap` block stale. Confirm which location is canonical, then align schema, `nap`, and page targeting to match. Do this before any citation building.
2. **(money pages, same decision)** Every page renders `tel:+19089708533` (five tel links on `/contact/` alone) and sets schema `telephone` to the same number, but the client record's `phone_discipline` note mandates one number everywhere: the GBP line `(855) 650-7422`. Either the site is on a rogue number or the record is out of date. Resolve alongside item 1.
3. **(template, high impact)** Raise `text-dark/50` on breadcrumb links and `text-dark/60` on the homepage trust-bar paragraphs to `text-dark/70` in the shared layout. This is the only accessibility failure on the site and clearing it should take all six pages to roughly 100 accessibility from the current 94.8 average.
4. **(money page)** Fix the 0.127 CLS on `/contact/`, the worst Core Web Vital on the site and the only metric outside Google's "good" thresholds. The single culprit is `section.section-first` reflowing when Inter swaps in from `fonts.gstatic.com`. Self-host Inter and preload the woff2, or add `size-adjust`, `ascent-override` and `descent-override` to a matched local fallback so the swap is metric-neutral. This also resolves the `network-dependency-tree-insight` third-party hop on all six pages.
5. **(template)** Generate responsive widths for `hero-bg.webp` and serve via `srcset`, and add `fetchpriority="high"` to the hero image in the hub, service-landing and service-area templates. Together these recover up to 214 KB per page and clear `lcp-discovery-insight` on five pages.

Trimming the homepage meta description from 188 to 160 characters or fewer is a one-line change that flips the site verdict from amber to green. It sits below the five items above on impact, but it is the cheapest win here.

## Notes / caveats

- **Desktop-only scoring.** Repeated from the header because it changes how these numbers should be read: mobile would score materially lower, particularly on performance. Treat 98.7 as a desktop ceiling, not a mobile result.
- **`has_micromarkup: false` is a false alarm, do not action it.** DataForSEO reports no microdata on all six pages. Manual verification of the rendered HTML confirms valid JSON-LD is present on every page: `LocalBusiness`, `Organization`, `WebSite`, `PostalAddress`, `GeoCoordinates`, `OpeningHoursSpecification`, plus `BreadcrumbList` on inner pages and `Service` with a five-question `FAQPage` on the service landings. The check only detects microdata and RDFa, not JSON-LD. Schema coverage is genuinely good.
- **`(555) 555-5555` on `/contact/` is not a leaked placeholder number.** It is the `placeholder` attribute on the contact form's phone input, which is correct UX. Flagged here only because a text search of the page will surface it.
- **Verdict methodology.** All six pages passed every Lighthouse category comfortably and none carry a high-severity on-page issue under the rubric, so five are green. The homepage is amber on the meta-description length issue, which maps to the rubric's medium "title length off" tier. Site verdict is the worst per-URL verdict, hence amber.
- **Severity call on render-blocking.** `has_render_blocking_resources` fires on all six pages but is recorded as low, not medium. The blocking asset is an 8.7 KB CSS bundle with a measured cost of 55 ms, and Lighthouse's own `render-blocking-insight` scored it 0.5 rather than 0. Grading it medium would have flipped all six pages to amber and misrepresented a site scoring 95 to 100 on performance.
- **Items 1 and 2 sit outside the automated rubric.** Both are recorded in the state file under `manual_findings` with `needs_owner_decision: true` rather than in `onpage_issues`, because they came from manual verification of the rendered HTML and JSON-LD and have no real DataForSEO check ID. They did not flip any verdict, since determining which location and phone number is correct is a business decision, not a technical one. They are ranked first anyway because they carry the most commercial risk on this list.
- **Schema `sameAs` still points at pre-rebrand socials** (`facebook.com/EliteRestorationGroups`, `instagram.com/eliterestorationgroup`). Expected: the client record lists post-rebrand social URLs as still awaiting intake. Worth closing out when those arrive.
- `robots.txt` is clean and references `https://therestorationgroup.com/sitemap-index.xml`, which returns 200. `/sitemap.xml` returns 404, which is correct for an Astro sitemap-index setup and is not an issue.
- **Run-to-run variance.** Scores here come from the `full_data` Lighthouse run. A reduced-response run minutes earlier differed within normal noise (homepage performance 98 vs 99, homepage LCP 902 ms vs 860 ms). Treat sub-2-point movements next month as noise, not signal.
- **Cost.** Roughly $0.041 for the run: $0.030 in Lighthouse `full_data` calls and $0.011 in `instant_pages`, comfortably under the $0.30 to $0.50 target. Full Lighthouse payloads (about 7 MB total) were streamed to disk at `/tmp/rank-ai-audit/raw/` and parsed with `python3` rather than read into context.
