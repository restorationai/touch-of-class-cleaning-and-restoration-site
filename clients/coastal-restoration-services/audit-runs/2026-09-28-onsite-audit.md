# Onsite Audit - Coastal Restoration Services Inc - 2026-09-28

**Live origin audited:** https://callcrs.com (apex)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** 2026-08-26 (staging Pages preview)
**Form factor:** desktop only (see caveats)

> **First apex audit.** The August baseline ran against the Cloudflare Pages staging preview; this run hits the production apex (cutover completed 2026-09-08). No `x-robots-tag` header is present, so SEO counts toward the verdict this month. The SEO jump from 69 to 100 is the staging noindex artifact going away, not a site change. Deltas below compare pages by path across the two origins.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.5 | -1.0 |
| Accessibility | 91.8 | +0.6 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | +31.0 (staging artifact removed) |

Pages by verdict: green: 1, amber: 1, red: 4, error: 0

**How to read this:** Lighthouse scores are excellent on every page (all categories 90 or higher). The four red pages are red for one reason only: they still target **Vandenberg Village instead of Santa Maria** in their title, H1, or meta description. The August cutover fixed the broken canonical and the `https://None` JSON-LD identifiers, but it did not fix the wrong city.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 96 | 100 | 100 | 0.96s | 0.002 | 0ms |
| `/services/` | services-hub | red | 99 | 90 | 100 | 100 | 0.97s | 0.002 | 15ms |
| `/services/water-damage-restoration/` | service-landing | red | 97 | 91 | 100 | 100 | 1.23s | 0.003 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | red | 99 | 91 | 100 | 100 | 0.83s | 0.003 | 0ms |
| `/service-areas/vandenberg-village-ca/` | service-area | amber | 98 | 91 | 100 | 100 | 0.95s | 0.024 | 0ms |
| `/contact/` | contact | red | 99 | 92 | 100 | 100 | 1.04s | 0.017 | 0ms |

INP is not measured in lab runs and is recorded as null.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `rankai_wrong_primary_city_in_metadata` | 4 | high | `plan-input.json` lists Vandenberg Village first and Santa Maria (`primary: true`) second. The renderer reads `service_areas[0]` instead of the `primary: true` entry. Fix the renderer and re-render. |
| `has_micromarkup_errors` | 5 | medium | DataForSEO flags every page that carries FAQPage, BreadcrumbList, or Service JSON-LD. The homepage, which has only Organization, WebSite, and LocalBusiness, passes. Likely causes: the last breadcrumb `ListItem` has no `item`, LocalBusiness `image`/`logo` are relative (`/images/logo.webp`), and Service `areaServed` is just `"CA"`. |
| `color-contrast` | 5 | medium | Breadcrumb links (`text-dark/50`, #888c93 on white) measure 3.37:1 against a 4.5:1 minimum. On the service-area page a `text-slate-400` span (#94a3b8) measures 2.56:1. |
| `target-size` | 6 | medium | Footer `tel:` and `mailto:` links are 17px tall against a 24px minimum. Carried over from August. |
| `image-delivery-insight` | 6 | medium | `logo.webp` is 22KB served into a small header slot (about 20KB wasted per page). `hero-bg.webp` (186KB) wastes 69KB to 129KB on hub, area, and contact pages. |
| `lcp-discovery-insight` | 5 | medium | Hero `<img>` lacks `fetchpriority="high"` on every template except the homepage. Carried over from August. |
| `unused-javascript` | 6 | low | New since August. The GA4 tag `gtag/js?id=G-VHZE6NYBPE` ships about 69KB of unused JS out of 159KB. |
| `cache-insight` | 6 | low | New since August. The Cloudflare Email Obfuscation script (`/cdn-cgi/.../email-decode.min.js`) is served with a 2-day TTL. It is also in the critical request chain. |
| `render-blocking-insight` | 6 | low | `_astro/_slug_.BP1u6yHs.css` (~9KB) blocks first paint. About 50ms on contact and service-area pages. |
| `network-dependency-tree-insight` | 6 | low | Critical chain is document, then `page.CyD_eNI3.js`, the `_slug_` CSS, and `email-decode.min.js`. |
| `forced-reflow-insight` | 2 | low | Fire landing and service-area page. No measurable savings reported. |

## Money page alerts

- **`/services/`** (services-hub) - red. Title "Restoration Services in Vandenberg Village" and the meta description target the wrong city. The plan says "Restoration Services in Santa Maria | Coastal Restoration Services Inc". Also has the heaviest image waste (205KB across 13 images) and schema validation errors. Word count is 788 against an 800 target.
- **`/services/water-damage-restoration/`** (service-landing) - red. Title, H1, and meta all read "Water Damage Restoration in Vandenberg Village". LCP is 1.23s, the slowest in the set (still good, but 435ms slower than in August).
- **`/services/fire-damage-restoration/`** (service-landing) - red. Title, H1, and meta all read "Fire Damage Restoration in Vandenberg Village".
- **`/contact/`** (contact) - red. Meta description reads "restoration services in Vandenberg Village". Also wastes 146KB on images (mostly `hero-bg.webp`).

The homepage is the only money page that is green. It correctly targets Santa Maria.

## Regressions vs prior audit

**Verdict transitions (all improvements):**
- `/` went red to green. The canonical and JSON-LD `@id` fixes cleared its only high-severity issues, and Accessibility rose from 92 to 96 because the brand-gold contrast failures are gone.
- `/service-areas/vandenberg-village-ca/` went red to amber. This page legitimately targets Vandenberg Village. Only the schema validation warning keeps it from green.
- The other four stayed red, now for the wrong-city issue alone.

**Metric regressions:**
- `/services/water-damage-restoration/`: LCP rose 435ms (791ms to 1226ms). The Performance score is 97 (down 3, under the 5-point flag threshold).
- `/contact/`: LCP rose 206ms (829ms to 1035ms).
- Both are still far under the 2.5s "good" threshold. Part of the rise is likely the move from the `pages.dev` preview to the apex through the Cloudflare proxy. The new GA4 tag also adds 159KB of JS. Re-check next month before acting.

**New issues this month:**
- All 6 URLs: `unused-javascript` (the GA4 gtag script, added since August) and `cache-insight` (the Cloudflare Email Obfuscation script, which appeared on the apex zone).
- 5 URLs (all except `/`): `has_micromarkup_errors`. This may not be a true regression. In August, DataForSEO could not detect the JSON-LD at all (`has_micromarkup: false`), so it had nothing to validate.
- `/services/fire-damage-restoration/`, `/service-areas/vandenberg-village-ca/`: `forced-reflow-insight`.
- `/services/water-damage-restoration/`: `largest-contentful-paint` (metric score 0.89).
- `/services/`: `rankai_word_count_below_target` (788 vs 800). This is the same finding reported as `low_character_count` in August, which DataForSEO no longer flags.

**Issues resolved since last audit:** (positive, keep doing this)
- All 6 URLs: `canonical` now self-references `https://callcrs.com/...` correctly (was `https://none/`).
- All 6 URLs: `rankai_jsonld_invalid_entity_id` is fixed. JSON-LD `@id` values now read `https://callcrs.com/#organization`, `#website`, and `#identity`.
- All 6 URLs: `is-crawlable` is resolved. The apex is indexable.
- `/`: `color-contrast` is fully cleared. On other pages it is down to breadcrumb links only (was brand-gold CTAs, eyebrow labels, and the announcement bar).

## Recommended next actions (priority order)

1. **(money pages, template, high impact)** Make the renderer pick the service area with `primary: true` instead of `service_areas[0]`. Re-render and redeploy. As a quick stopgap, move the Santa Maria entry to the top of `service_areas` in `clients/coastal-restoration-services/plan-input.json` and `plan/plan-input.json`. After the rebuild, compare the rendered `<title>`, `<h1>`, and meta description against `plan/url-plan.json` for `/services/`, `/contact/`, and all 14 service landings. This is the second month in a row this issue has been flagged, and it is now on the live production site.
2. **(money pages, template)** Fix the JSON-LD that fails validation. Add `"item"` (the page's own URL) to the last BreadcrumbList `ListItem`. Make LocalBusiness `image` and `logo` absolute (`https://callcrs.com/images/logo.webp`). Set Service `areaServed` to a list of `City` entries (Santa Maria first) instead of `"CA"`. Then run `/services/water-damage-restoration/` through Google's Rich Results Test to confirm zero errors.
3. **(template, performance)** Add `fetchpriority="high"` and remove any `loading="lazy"` from the hero `<img>` in the services-hub, service-landing, service-area, and contact templates. Copy the homepage template, which already does this. On the same pass, export `logo.webp` at 2x its display size (about 20KB saved per page). Add a `srcset`/`sizes` to the `hero-bg.webp` background so the 480w variant is used where it fits (69KB to 129KB saved on hub, area, and contact).
4. **(template, accessibility)** Darken the breadcrumb link color from `text-dark/50` (#888c93, 3.37:1) to at least `text-dark/70` or a token of about #6b6f76 (4.5:1 or better on white). Replace the `text-slate-400` span on service-area pages with `text-slate-600`. Add `py-1 inline-block` (or `min-h-[24px]`) to the footer `tel:` and `mailto:` links so they clear the 24px target size.
5. **(template, low)** Turn off Cloudflare Scrape Shield > Email Obfuscation for the `callcrs.com` zone. The email address is already public in JSON-LD, so the obfuscation protects nothing, and its script sits in the critical chain on every page. Consider loading GA4 via Partytown or after `load` to recover most of the 69KB of unused JS.

## Notes / caveats

- **Origin change.** August audited `staging.rankai-coastal-restoration-services.pages.dev`. September audited `https://callcrs.com` behind the Cloudflare proxy. Score and LCP deltas mix a real code change with a hosting change, so treat small performance deltas with caution.
- **Desktop only.** Lighthouse ran with `for_mobile=false` to stay comparable with the August desktop baseline. Mobile scores typically run 10-20 performance points lower, and `target-size` matters more on mobile. Do not present these as mobile-first scores. The REST endpoint does support mobile if a mobile baseline is wanted.
- **URL selection.** Fire damage, mold remediation, and water damage restoration tie at priority 9.0 in the url-plan. Water and fire were kept, as in August, so the regression comparison stays valid. For the service-area slot, Santa Maria is the `primary: true` area, but it has no service-area page (`/service-areas/santa-maria-ca/` 301-redirects to `/`, which is correct because the homepage is the Santa Maria page). The run fell back to the first area slug, `vandenberg-village-ca`.
- **Schema errors have no detail.** `has_micromarkup_errors` is a boolean from DataForSEO instant_pages with no per-error breakdown. The causes listed above come from reading the rendered JSON-LD by hand. Confirm them with the Rich Results Test before closing the item.
- **MCP deviation.** This DataForSEO MCP build does not expose `on_page_lighthouse` or `on_page_instant_pages`. The run used authenticated REST calls to `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages`.
- **Issue ID provenance.** IDs prefixed `rankai_` are Rank AI derived checks. All other IDs are genuine Lighthouse or DataForSEO IDs.
- **Clean results.** No broken internal or external links, no broken resources, no mixed content, one H1 per page, and self-referencing canonicals on all six pages. All titles are 39-46 characters and all meta descriptions 117-152 characters. No image is missing alt text. Best Practices is 100 and SEO is 100 on every page.
- **Cost.** 6 Lighthouse runs plus 6 instant-pages runs, about $0.04, inside the $0.30-0.50 target.
