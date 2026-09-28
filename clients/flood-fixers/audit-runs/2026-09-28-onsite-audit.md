# Onsite Audit: Flood Fixers, 2026-09-28

**Live origin audited:** https://flood-fixers.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-08-27 (green)
**Form factor:** desktop only (see Notes)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98 | -1 |
| Accessibility | 95 | +4 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

All six pages stayed green. Accessibility went up because last month's contrast fixes landed: the breadcrumb and the accent phone CTA now pass on four pages. Performance slipped a little. The main cause is a new site-wide GA4 tag (`gtag.js`, 159KB, about 44% of it unused), which showed up on every page this month. LCP rose by 321 to 488ms on four pages but is still under 1.35s everywhere. The "good" threshold is 2.5s.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 96 | 100 | 100 | 0.95s | 0.039 |
| `/services/` | services-hub | green | 96 | 95 | 100 | 100 | 1.34s | 0.004 |
| `/services/water-damage-restoration/` | service-landing | green | 96 | 95 | 100 | 100 | 1.25s | 0.006 |
| `/services/flood-damage-restoration/` | service-landing | green | 98 | 95 | 100 | 100 | 1.18s | 0.006 |
| `/service-areas/chula-vista-ca/` | service-area | green | 97 | 91 | 100 | 100 | 1.19s | 0.050 |
| `/contact/` | contact | green | 99 | 96 | 100 | 100 | 0.97s | 0.036 |

TBT was 0ms on all six pages. INP is null on all six because lab Lighthouse does not report it.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `link-name` | 6 | medium | The footer `<address>` email anchor has an empty address and no text. Cloudflare Email Obfuscation now rewrites it to `/cdn-cgi/l/email-protection#..`, but it still decodes to `mailto:` with no address. `/contact/` has a second empty anchor in the contact aside. |
| `unused-javascript` | 6 | low | New this month. `https://www.googletagmanager.com/gtag/js?id=G-BPB9R60M10` ships 159KB, of which 66-70KB is unused. Estimated savings are 80-190ms per page. |
| `image-delivery-insight` | 6 | low | The header logo `/images/logo.webp` is 21KB but renders at 36x36 (21KB recoverable on every page). Hero images are over-sized: `brand/hero.webp` on the hub, area and contact pages (up to 218KB recoverable on `/contact/`), and the new per-service heroes `water-damage-restoration.webp` (177KB, 83KB recoverable) and `flood-damage-restoration.webp` (228KB, 133KB recoverable). |
| `cache-insight` | 6 | low | `images.flood-fixers.com/brand/hero.webp` and `hero-480w.webp` are served with a 4-hour cache lifetime, so about 182KB is re-downloaded per page on repeat visits. |
| `render-blocking-insight` / `has_render_blocking_resources` | 6 | low | One stylesheet (`/_astro/_slug_.CURUGAg3.css`, 9KB) and one script block rendering. Measured cost is 50-60ms. Low priority. |
| `network-dependency-tree-insight` | 6 | low | The request chain goes HTML to CSS to Google Fonts CSS to the Inter woff2 file. It is the same root cause as the font-swap CLS below. |
| `has_micromarkup_errors` | 5 | low | The DataForSEO validator wants `answerCount` on each FAQPage `Question`. That is a QAPage property that Google's FAQPage spec does not require, so it does not count toward the verdict (see Notes). |
| `lcp-discovery-insight` | 5 | low | The hero `<img>` has `loading="eager"` but no `fetchpriority="high"` on every template except home. It fails the `priorityHinted` check on all five. |
| `low_content_rate` | 2 | low | Text-to-HTML ratio is 7.1% on `/` and 9.1% on `/contact/`. This is informational for these archetypes. |

## Money page alerts

None. The home page, the services hub, both service landings and the contact page all came back green.

These money-page findings are worth acting on even though none of them changed a verdict:

- **`/contact/`**: the two email links are still empty. A visitor who clicks the email line on the contact page gets a blank compose window.
- **`/services/water-damage-restoration/` and `/services/flood-damage-restoration/`**: this is where performance fell the most (100 to 96 and 100 to 98). LCP went from 0.76s to 1.25s and 1.18s. Both pages now use service-specific hero images, which are uncompressed and have no `srcset` or priority hint, and GA4 loads on top of that.

## Regressions vs prior audit

**Verdict transitions:** none.

**Score deltas:** no page lost 5 or more points in any category. The biggest drops were `/services/water-damage-restoration/` performance (100 to 96) and `/services/` performance (99 to 96).

**Core Web Vitals regressions past threshold:**

- `/services/` LCP 1022ms to 1343ms (+321ms)
- `/services/water-damage-restoration/` LCP 758ms to 1246ms (+488ms)
- `/services/flood-damage-restoration/` LCP 759ms to 1184ms (+425ms)
- `/service-areas/chula-vista-ca/` LCP 823ms to 1188ms (+365ms)
- `/` CLS 0.018 to 0.039 (+0.021). The shift comes from the hero content container when the Inter webfont swaps in (`fonts.googleapis.com` stylesheet loaded async with `display=swap`).

All five values are still well inside Google's "good" thresholds (LCP 2.5s, CLS 0.1).

**New issues this month:**

- All 6 pages: `unused-javascript`. The GA4 tag `G-BPB9R60M10` is new site-wide and about 44% of it goes unused on load.
- `/`: `forced-reflow-insight`. 62ms of unattributed forced reflow, probably from the GA or Cloudflare email-decode scripts.
- `/contact/`: `low_content_rate`. Text-to-HTML ratio is 9.1%.
- 5 pages with FAQPage: `has_micromarkup_errors`. This is the first run with micromarkup validation turned on, so these were newly found, not newly broken.
- `/service-areas/chula-vista-ca/`: `color-contrast` has the same ID as last month but a different element. The breadcrumb now passes. The failing element is the "· 9 Google reviews" label (`span.text-slate-400`, #94a3b8 on white, 2.56:1).

**Issues resolved since last audit:** (positive, keep doing this)

- `/services/`, `/services/water-damage-restoration/`, `/services/flood-damage-restoration/`, `/contact/`: `color-contrast` is no longer flagged. The breadcrumb and `a.btn-accent` changes worked, and accessibility went from 90-91 to 95-96 on those four pages.

## Recommended next actions (priority order)

1. **(money page + template, medium)** Fix the empty email link, which has been open for two months. Every page renders an empty mailto anchor in the footer `<address>`, and `/contact/` has a second one in the contact aside (`a.font-bold.text-white`). This is the only `link-name` failure left on all 6 pages. **Do not just bind the client record's `contact` field:** it holds `luxurycustomfloors@gmail.com`, which looks like another business's inbox. Confirm the real Flood Fixers email with the client and set it in site data. If there isn't one, remove the anchor from both templates.
2. **(money page, LCP)** Compress the new service-landing heroes and add responsive delivery. `/images/services/water-damage-restoration.webp` (177KB) and `/images/services/flood-damage-restoration.webp` (228KB) are the LCP elements on both landing pages. Re-encode them at about q70 (83KB and 133KB recoverable). Generate 480w/768w/1200w variants with `sizes="100vw"`, as the home hero already does, and add `fetchpriority="high"`. Do the same for `brand/hero.webp` on the hub, area and contact templates (up to 218KB recoverable on `/contact/`). That closes both `image-delivery-insight` and `lcp-discovery-insight` on 5 pages.
3. **(template, performance)** Load GA4 after the page has rendered. The new `gtag.js` (159KB, 66-70KB unused) loads on every page and is the only new cost this month. Either move it to a Cloudflare Zaraz / Partytown worker, or inject it on `requestIdleCallback` / the first user interaction instead of in `<head>`. Check that GA4 events still fire after the change.
4. **(template, infra)** Set long cache lifetimes on the image CDN. `images.flood-fixers.com/brand/*` is served with a 4-hour TTL. Add a Cloudflare Cache Rule for `images.flood-fixers.com/*` that sets `Cache-Control: public, max-age=31536000, immutable`. This was open last month too.
5. **(per-page + schema hygiene, low)** On `/service-areas/chula-vista-ca/`, change the review-count label from `text-slate-400` to `text-slate-500` (#64748b, 4.76:1) so it passes AA. That is the last contrast failure on the site. In the same template pass, remove the empty `email`, `foundingDate`, `address.streetAddress` and `address.postalCode` properties from the LocalBusiness/Organization JSON-LD rather than emitting `""`. Also make `image`/`logo` absolute (`https://flood-fixers.com/images/logo.webp`).

## Notes / caveats

- **Live origin.** The client record stores the apex cutover as top-level `cut_over_at: 2026-07-04T20:30:00Z`, not as `apex_cutover.completed_at`. The apex is live (HTTP 200, no `x-robots-tag`) and both prior audits used it, so it was audited again. The staging preview still returns `x-robots-tag: noindex` and was not audited.
- **Desktop only.** Lighthouse 13.4.0 ran with `formFactor=desktop`. Mobile would typically score 10-20 performance points lower. These are not mobile-first scores.
- **MCP transport.** The DataForSEO MCP wrapper in this CI run only exposes the generic `api_request` tool. The audit called the same REST endpoints directly (`on_page/lighthouse/live/json`, `on_page/instant_pages`), plus one single-page `on_page/task_post` crawl to see the micromarkup validation details. Total API cost for this run was $0.041.
- **Schema validation.** The JSON-LD on all 6 pages parses cleanly. Home has Organization, WebSite and LocalBusiness. The hub and contact pages add FAQPage and BreadcrumbList. The landings have Service, LocalBusiness, FAQPage and BreadcrumbList. The area page has LocalBusiness, FAQPage and BreadcrumbList. The only "error" DataForSEO reports is a missing `answerCount` on FAQPage Questions. That property comes from QAPage, and Google's FAQPage spec does not ask for it, so it was recorded as low severity and does not change the verdict. If you would rather clear the flag than argue with the validator, adding `"answerCount": 1` to each Question is harmless.
- **Link crawling not performed.** instant_pages audits one URL at a time and does not follow outbound links, so link-level 4xx/5xx checks were not in scope. All 6 audited URLs returned 200. No `http://` resources were found (no mixed content), and image alt coverage is 100% on every page.
- **Word count.** `/services/` has 751 words against the url-plan target of 800 (`content_below_target_word_count`, low, carried over from last month). All other pages meet their targets.
- **LCP variance.** A single desktop lab run can vary by 100-300ms. The LCP increases are consistent across four pages and line up with GA4 arriving and the landings switching to heavier hero images, so they are reported as real. Re-check next month after actions 2 and 3.
- **Excluded checks.** `agent-accessibility-tree` (agentic-browsing category, not scored) fails on all 6 pages for the same reason as `link-name`. `no_image_title` (instant_pages) is not part of the audit rubric. Neither is recorded as an issue.
