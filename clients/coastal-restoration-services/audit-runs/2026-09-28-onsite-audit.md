# Onsite Audit - Coastal Restoration Services Inc - 2026-09-28

**Live origin audited:** https://callcrs.com (apex)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** 2026-08-26 (staging Pages preview, so SEO and small performance deltas are not like-for-like)
**Form factor:** desktop only (DataForSEO Lighthouse wrapper). Mobile performance would typically run 10-20 points lower.

> **Why red when every score is 90+:** the site's Lighthouse health is excellent (desktop performance 99, best practices 100, SEO 100 on every page). The red verdict comes from one bug that was already flagged last month and is still live: the services hub, both service landings and the contact page target **Vandenberg Village** in their title, meta description and H1, not the HQ city **Santa Maria**. That is a ranking problem on the pages that bring in money, not a speed problem.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99 | -0.5 |
| Accessibility | 91.8 | +0.6 |
| Best Practices | 100 | +0 |
| SEO | 100 | +31 (staging noindex artifact last month; not comparable) |

Pages by verdict: green: 1, amber: 1, red: 4, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 96 | 100 | 100 | 0.94s | 0.002 |
| `/services/` | services-hub | red | 99 | 90 | 100 | 100 | 0.93s | 0.002 |
| `/services/water-damage-restoration/` | service-landing | red | 99 | 91 | 100 | 100 | 0.85s | 0.003 |
| `/services/fire-damage-restoration/` | service-landing | red | 99 | 91 | 100 | 100 | 0.87s | 0.003 |
| `/service-areas/vandenberg-village-ca/` | service-area | amber | 99 | 91 | 100 | 100 | 0.91s | 0.024 |
| `/contact/` | contact | red | 99 | 92 | 100 | 100 | 0.87s | 0.017 |

TBT is 0ms on all six pages. INP was not reported (lab run, no interaction).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `rankai_wrong_primary_city_in_metadata` | 4 | high | Renderer must use the `primary: true` service area (Santa Maria), not `service_areas[0]` |
| `image-delivery-insight` | 6 | medium | Give the hero `<img>` on the services-hub, contact and service-area templates the same srcset/sizes the homepage uses; resize the header logo |
| `target-size` | 6 | medium | Add `py-1` / min-height 24px to the footer tel: and mailto: links |
| `color-contrast` | 5 | medium | Change breadcrumb `text-dark/50` to `text-dark/70` or darker (4.5:1) |
| `lcp-discovery-insight` | 5 | medium | Add `fetchpriority="high"` to the hero `<img>` on non-home templates |
| `has_micromarkup_errors` | 5 | medium | Add `item` URL to the last BreadcrumbList entry; strip markdown from FAQ answer text |
| `unused-javascript` | 6 | low | Load gtag.js after first interaction or move GA4 to Cloudflare Zaraz |
| `network-dependency-tree-insight` | 6 | low | No action; 0ms estimated savings |
| `cache-insight` | 6 | low | No action; Cloudflare email-decode script, 0 KiB savings (or disable Email Obfuscation) |
| `render-blocking-insight` | 6 | low | Inline the ~9KB Astro stylesheet (`build.inlineStylesheets: 'always'`) |

## Money page alerts

- **`/services/`** (services-hub) - verdict: red. Title "Restoration Services in Vandenberg Village" and meta description "Full-service restoration in Vandenberg Village...". Plan: "Restoration Services in Santa Maria | Coastal Restoration Services Inc". Also the heaviest image waste of the set: ~205KB (hero-bg.webp served full-size at 186KB with no srcset, plus 12 service-card thumbnails).
- **`/services/water-damage-restoration/`** (service-landing) - verdict: red. Title and H1 "Water Damage Restoration in Vandenberg Village"; meta description names Vandenberg Village. Plan: "Water Damage Restoration in Santa Maria".
- **`/services/fire-damage-restoration/`** (service-landing) - verdict: red. Title and H1 "Fire Damage Restoration in Vandenberg Village"; meta description names Vandenberg Village. Plan: "Fire Damage Restoration in Santa Maria".
- **`/contact/`** (contact) - verdict: red. Meta description "Call (805) 345-7440 for restoration services in Vandenberg Village...". Plan says Santa Maria. Also ~146KB of image waste: the 186KB hero-bg.webp is served full-size with no srcset.

The homepage is the only money page that is correct ("Restoration Services in Santa Maria, CA"), which shows the fix already exists for one template and just needs to reach the others. Since 12 of the 14 service landings use the same template, the wrong city almost certainly carries across all of them, not just the two audited here.

## Regressions vs prior audit

No score or Core Web Vitals regressions. No URL dropped 5+ points in any category, and no LCP (+200ms), CLS (+0.02) or TBT (+100ms) thresholds were crossed. LCP runs 43-127ms slower than last month's staging run on every page (still 0.85-0.94s). That is consistent with the apex+CDN vs Pages preview difference and GA4 now loading, not a code regression.

**Verdict transitions (both improvements):**
- `/` went red to green: canonical and JSON-LD `https://None` bugs fixed, brand-gold contrast failures gone, accessibility 92 to 96.
- `/service-areas/vandenberg-village-ca/` went red to amber: canonical and JSON-LD fixed; held at amber by the new `has_micromarkup_errors` flag.

The other four pages stayed red, now for the wrong-city bug alone.

**New issues this month:**
- All 6 pages: `unused-javascript`: GA4 gtag.js (G-VHZE6NYBPE) is now live on production; ~69KB of its 159KB is unused per page. Expected once analytics went live; low priority.
- All 6 pages: `cache-insight`: Cloudflare's email-obfuscation script has a 2-day cache TTL. 0 KiB estimated savings; informational.
- 5 pages (all except `/`): `has_micromarkup_errors`: DataForSEO flags JSON-LD validation errors on every template that carries FAQPage + BreadcrumbList. The final breadcrumb ListItem has no `item` URL, and FAQ answers contain raw markdown (`**(805) 345-7440**`).
- `color-contrast` changed cause: the brand-gold button failures from last month are fixed, but breadcrumb links (`text-dark/50`, #888c93, 3.37:1) now fail on 5 pages, plus the "29 Google reviews" label (#94a3b8, 2.56:1) on the service-area page.

**Issues resolved since last audit:** (positive - keep doing this)
- All 6 pages: `canonical`: rel=canonical now self-references `https://callcrs.com/...` (was `https://none/`).
- All 6 pages: `rankai_jsonld_invalid_entity_id`: JSON-LD @id values now resolve to `https://callcrs.com/#organization`, `#website`, `#identity`.
- All 6 pages: `is-crawlable`: no noindex on the apex; SEO is 100 everywhere.
- `/`: `color-contrast` no longer flagged (brand-gold contrast fixed).
- Header logo waste dropped from ~66KB to ~20KB per page.

## Recommended next actions (priority order)

1. **(money pages, template, high impact)** Fix primary-city selection in the site renderer. `plan-input.json` lists `service_areas[0]` = Vandenberg Village and `service_areas[1]` = Santa Maria with `primary: true`; the services-hub, service-landing and contact templates still read index 0. Switch them to the `primary: true` entry (the home template already does this correctly), re-render, and push. Then add a build assertion that diffs each rendered `<title>`, meta description and `<h1>` against `plan/url-plan.json` so it cannot regress silently. This single fix turns 4 red pages green. Note that live titles also drop the plan's "| Coastal Restoration Services Inc" suffix, so the same diff will catch that.
2. **(money pages, template)** On the services-hub, contact and service-area templates, give the hero `<img src="/images/hero-bg.webp">` the same `srcset` (480w/768w/...) and `sizes="100vw"` the homepage uses, and add `fetchpriority="high"` to the hero `<img>` on every non-home template. That removes ~95-129KB per page on `/services/` and `/contact/` and fixes `lcp-discovery-insight` on 5 pages. Resize `/images/logo.webp` to a 2x asset for its rendered slot (~20KB saved site-wide).
3. **(template, schema)** In the BreadcrumbList JSON-LD, add `item` (the page URL) to the final ListItem. In the FAQPage JSON-LD, strip markdown (`**...**`) from `acceptedAnswer.text` before serializing. Re-check one page in the Google Rich Results Test to confirm `has_micromarkup_errors` clears.
4. **(template, accessibility)** Change breadcrumb link class `text-dark/50` to `text-dark/70` or darker (needs 4.5:1 on white). Change the "29 Google reviews" label from slate-400 (#94a3b8) to slate-600. Give the footer tel: and mailto: links a 24px minimum tap height (e.g. `inline-block py-1`). This clears `color-contrast` and `target-size` on all 6 pages.
5. **(template, low)** Defer GA4: load gtag.js on first user interaction or move it to Cloudflare Zaraz to drop ~69KB of unused JS per page. Optional; performance is already 99.

## Notes / caveats

- First audit on the apex production site. SEO now counts toward the verdict (no x-robots-tag on any URL, all HTTP 200, HSTS/nosniff/referrer-policy/permissions-policy/frame-ancestors CSP present).
- URL set matches the 2026-08-26 baseline. Three service landings tie at priority 9.0 (fire, mold, water); water and fire were kept for comparability. The url-plan has no `primary: true` service-area page (Santa Maria, the HQ city, has no area page), so the first area, Vandenberg Village, was used. Its Vandenberg Village metadata is correct by design.
- `/services/` renders 788 words against an 800-word plan target (`low_character_count`, low).
- DataForSEO does not name the exact failing schema property for `has_micromarkup_errors`. The causes in action 3 come from manually inspecting the rendered JSON-LD, and need confirming in the Rich Results Test.
- Lighthouse detail was captured with `full_data: true` via direct REST calls, because the named MCP Lighthouse and instant_pages tools are not exposed in this build. Total API cost was about $0.04.
- Dropped as noise: DataForSEO `no_image_title`, `low_content_rate`, and `has_render_blocking_resources` (the last duplicates Lighthouse `render-blocking-insight`). The service-area page's `frame` flag (map iframe) is informational.
