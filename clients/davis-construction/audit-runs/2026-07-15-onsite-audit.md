# Onsite Audit - Davis Construction Contractors - 2026-07-15

**Live origin audited:** https://davisconstructioncontractors.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-06-25 (amber)
**Form factor:** desktop (DataForSEO Lighthouse runs desktop only; mobile scores typically run 10-20 performance points lower)

This month the site cleared every red and amber flag from the June audit. All six audited pages are now green, driven by the main deploy pushed 2026-07-15. Accessibility and best-practices in particular recovered sharply (button-name, color-contrast on most pages, third-party-cookies, and Chrome DevTools inspector issues are all gone). What remains is low-impact performance headroom plus one accessibility item on the contact page.

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 99 | +4 |
| Accessibility | 99 | +10 |
| Best Practices | 100 | +20 |
| SEO | 100 | 0 |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | green | 99 | 100 | 100 | 100 | 0.9s | 0.015 |
| /services/ | services-hub | green | 98 | 100 | 100 | 100 | 1.1s | 0.001 |
| /services/home-remodeling/ | service-landing | green | 99 | 100 | 100 | 100 | 0.9s | 0.002 |
| /services/roofing/ | service-landing | green | 99 | 100 | 100 | 100 | 1.0s | 0.008 |
| /service-areas/madison-al/ | service-area | green | 98 | 100 | 100 | 100 | 1.1s | 0.002 |
| /contact/ | contact | green | 99 | 96 | 100 | 100 | 1.0s | 0.006 |

TBT is 0ms on every page. INP is not measured in the DataForSEO lab run (reported null).

## Template-level issues (fix once, lift many pages)

All template issues this month are performance diagnostics on an already-fast site. None drop a category below 98, so none affect the green verdict; they are optimization headroom.

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `cache-insight` | 6 | medium | Set a long-lived `Cache-Control` (e.g. `public, max-age=31536000, immutable`) on hashed static assets via the Pages `_headers` file. Up to 150ms LCP on /contact/ and /services/roofing/. |
| `image-delivery-insight` | 6 | medium | Serve right-sized, compressed images (AVIF/WebP at display dimensions) for hero and gallery images from the R2 image domain. Up to 150ms LCP on /services/roofing/. |
| `unused-javascript` | 6 | low | Defer or code-split the non-critical scripts loaded in the shared layout. 50-90ms per page. |
| `largest-contentful-paint` | 5 | low | LCP element already renders under 1.2s everywhere; minor headroom only, monitor. |
| `render-blocking-insight` | 3 | low | Inline critical CSS and defer the remaining non-critical CSS/JS in the layout. |
| `forced-reflow-insight` | 2 | low | Batch DOM reads and writes in layout scripts to avoid synchronous reflow. |
| `content_below_target_word_count` | 2 | low | On-page: top up thin copy on / (1191 vs 1200) and /services/ (756 vs 800). |

## Money page alerts

None. Every money page (home, services hub, both service landings, contact) came back green.

The one item worth flagging on a conversion page is a single `color-contrast` accessibility failure on /contact/ (accessibility 96). It does not trip the verdict but is the only genuine correctness issue left on a money page - see recommendation 1.

## Regressions vs prior audit

Net direction is strongly positive: all six pages moved amber to green, and the average scores rose across performance (+4), accessibility (+10), and best practices (+20).

**Verdict transitions (all improvements):**
- `/` home: amber to green
- `/services/` services-hub: amber to green
- `/services/home-remodeling/` service-landing: amber to green
- `/services/roofing/` service-landing: amber to green
- `/service-areas/madison-al/` service-area: amber to green
- `/contact/` contact: amber to green

**Issues resolved since last audit (positive - keep doing this):** 33 total, including on most or all pages:
- `button-name` (buttons now have accessible names) - all 6 pages
- `color-contrast` - resolved on 5 of 6 pages (still present on /contact/ only)
- `third-party-cookies` - all pages that had it
- `inspector-issues` (Chrome DevTools issues) - all 6 pages
- `title_too_long` - /, /services/roofing/, /service-areas/madison-al/, /contact/
- `meta_description_length_out_of_range` - / (home title and meta now in range)
- `server-response-time` - /services/roofing/
- `network-dependency-tree-insight` - /services/, /services/home-remodeling/, /service-areas/madison-al/, /contact/

**New items this month (29):** predominantly the new Lighthouse "Insights" diagnostic audits (`cache-insight`, `image-delivery-insight`, `lcp-discovery-insight`, `render-blocking-insight`, `forced-reflow-insight`) plus `unused-javascript` and the marginal `content_below_target_word_count` on / and /services/. These carry 150ms or less of savings on pages already scoring 98-100. Several appear as "new" only because this Lighthouse version emits a different audit set than the June run - they are low-impact optimization headroom, not genuine regressions.

## Recommended next actions (priority order)

1. **(money page, accessibility)** Fix the low-contrast element on `/contact/`. `color-contrast` is the only remaining WCAG AA failure on the site and it sits on the conversion page (accessibility 96). Adjust the affected text and background colors to reach at least a 4.5:1 ratio, which should return contact to 100.
2. **(template, medium)** Add long-lived cache headers on static assets. `cache-insight` flags all 6 pages, up to 150ms LCP on /contact/ and /services/roofing/. Set `Cache-Control: public, max-age=31536000, immutable` for content-hashed assets in the Pages `_headers` file.
3. **(template, medium)** Compress and right-size images. `image-delivery-insight` flags all 6 pages, up to 150ms LCP on /services/roofing/. Serve AVIF or WebP at actual display dimensions for hero and gallery images from the R2 image domain.
4. **(template, low)** Trim unused JavaScript in the shared bundle. `unused-javascript` flags all 6 pages (50-90ms each). Defer or code-split the non-critical scripts loaded in the layout.
5. **(per-page, low)** Top up thin copy to clear archetype targets: home is 1191 words vs a 1200 target, /services/ is 756 vs 800. A short added paragraph on each clears it.

## Notes / caveats

- Audited on the apex production origin (https://davisconstructioncontractors.com), so SEO counts toward the verdict. No staging noindex correction needed. Confirmed no `x-robots-tag: noindex` header on the apex home page.
- Lighthouse ran DESKTOP only via the DataForSEO wrapper (`audit_form_factor: desktop`). Mobile performance would likely score 10-20 points lower and is not represented here.
- The `mcp__dataforseo` MCP wrapper did not expose tools this run. The audit used the DataForSEO OnPage Lighthouse (`/v3/on_page/lighthouse/live/json`) and Instant Pages (`/v3/on_page/instant_pages`) REST endpoints with the same account credentials - identical data source to the MCP wrapper.
- DataForSEO reported `has_micromarkup=false` on all 6 pages, but JSON-LD was verified present in the served HTML of every page (LocalBusiness, Organization, WebSite, Service, FAQPage, BreadcrumbList). `has_micromarkup` does not detect JSON-LD, so missing-schema was correctly NOT flagged.
- This Lighthouse version emits the new "Insights" diagnostic audits, which is why several low-impact performance audit IDs appear as "new" versus the June run despite the site improving overall.
