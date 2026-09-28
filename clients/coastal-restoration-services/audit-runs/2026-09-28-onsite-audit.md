# Onsite Audit - Coastal Restoration Services Inc - 2026-09-28

**Live origin audited:** https://callcrs.com (apex)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** 2026-08-26 (Cloudflare Pages staging preview)
**Form factor:** desktop (DataForSEO Lighthouse, `formFactor=desktop`). Mobile performance would typically score 10-20 points lower. This is not a mobile-first score.

This is the first audit on the production apex. The cutover completed 2026-09-08. `curl -sI https://callcrs.com/` returns no `x-robots-tag`, so SEO counts toward the verdict this run. Last month SEO was excluded as a staging artifact.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.3 | -1.2 |
| Accessibility | 91.8 | +0.6 |
| Best Practices | 100 | 0 |
| SEO | 100 | +31.0* |

\* Most of the SEO gain is the staging `noindex` header going away at cutover, not a code change.

Pages by verdict: {green: 2, amber: 0, red: 4, error: 0}

**Read this correctly:** Lighthouse scores are excellent on every page. The site is red for one reason only. Four money pages still target the wrong city in their title, H1, and meta description (Vandenberg Village instead of Santa Maria). Two of last month's three high-severity defects (`https://None` canonicals and JSON-LD IDs) are fixed.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 98 | 96 | 100 | 100 | 0.95s | 0.002 |
| `/services/` | services-hub | red | 98 | 90 | 100 | 100 | 0.99s | 0.002 |
| `/services/water-damage-restoration/` | service-landing | red | 99 | 91 | 100 | 100 | 0.84s | 0.003 |
| `/services/fire-damage-restoration/` | service-landing | red | 99 | 91 | 100 | 100 | 0.87s | 0.003 |
| `/service-areas/vandenberg-village-ca/` | service-area | green | 97 | 91 | 100 | 100 | 1.24s | 0.024 |
| `/contact/` | contact | red | 99 | 92 | 100 | 100 | 0.89s | 0.017 |

TBT was 0ms on every page. INP was not reported (a lab run has no interactions) and is recorded as null.

## Root cause of the red verdict

`plan/url-plan.json` was regenerated on 2026-09-23 and now has the correct Santa Maria titles, H1s, and meta descriptions. The live pages were never re-rendered from it. `scripts/build_site.py:964-981` (the RENDERED-CONTENT GUARD) skips any content file whose frontmatter already has `rendered: true`. The old Vandenberg Village frontmatter survived the 2026-09-28 push to main. The code comment spells out the fix: run a targeted `render --url ... --force` per page. Re-scaffolding will not fix it.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `rankai_wrong_primary_city_in_metadata` | 4 | high | Force re-render `/services/`, every `/services/{slug}/` landing, and `/contact/` from the current url-plan. Then check that the live `<title>` matches the plan title. |
| `target-size` | 6 | medium | Footer `tel:+18053457440` (110x17px) and `mailto:tony@callcrs.com` (118x17px) links are under the 24px minimum. Add `py-1` or `inline-block min-h-[24px]` to the footer contact links. |
| `image-delivery-insight` | 6 | medium | `hero-bg.webp` has no srcset on inner pages, which wastes 126KB on `/contact/`, 93KB on `/services/` and 68KB on `/service-areas/vandenberg-village-ca/`. `logo.webp` wastes 20KB on every page. Add `srcset`/`sizes` to the inner hero and ship a 2x logo (about 134x128). |
| `color-contrast` | 5 | medium | Only the breadcrumbs still fail. `text-dark/50` (#888c93) on white measures 3.37:1 against a 4.5:1 minimum. Change the breadcrumb link class to `text-dark/70`. The service-area page also has a `text-slate-400` span at 2.56:1. Change it to `text-slate-600`. |
| `lcp-discovery-insight` | 5 | medium | The inner-page hero `<img>` has no `fetchpriority="high"`. The homepage template already passes this check. Copy its hero attributes to the hub, landing, area, and contact templates. |
| `unused-javascript` | 6 | low | New since cutover. Google Analytics `gtag.js` (G-VHZE6NYBPE) ships 66-69KB of unused JS. Load it with `async` after `load`, or move it to Partytown. Savings are 50-200ms on desktop. |
| `cache-insight` | 6 | low | New since cutover. Cloudflare Email Obfuscation injects `/cdn-cgi/scripts/.../email-decode.min.js` with a short TTL. It is negligible. To remove it, turn off Email Obfuscation in the zone's Scrape Shield settings. |
| `rankai_jsonld_relative_image_url` | 6 | low | LocalBusiness/Organization `image` and `logo` emit `/images/logo.webp`. Emit the absolute `https://callcrs.com/images/logo.webp` instead. |
| `forced-reflow-insight` | 3 | low | New since cutover, on `/services/`, the water landing, and `/contact/`. It most likely comes from the injected third-party scripts. Re-check after the gtag change. |
| `render-blocking-insight` / `network-dependency-tree-insight` | 6 | low | The 9KB Astro CSS bundle blocks paint. Too small to be worth fixing now. |

## Money page alerts

- **`/services/`** (services-hub): red. The title is "Restoration Services in Vandenberg Village". The plan says "Restoration Services in Santa Maria \| Coastal Restoration Services Inc". The meta description also says Vandenberg Village. This page also has the heaviest image waste (205KB) and 788 words against an 800 target.
- **`/services/water-damage-restoration/`** (service-landing): red. The title, H1, and meta description all say "Vandenberg Village". The plan H1 is "Water Damage Restoration in Santa Maria". This is the client's highest-priority service (plan priority 9.0).
- **`/services/fire-damage-restoration/`** (service-landing): red. It has the same three-field wrong-city defect.
- **`/contact/`** (contact): red. The meta description reads "restoration services in Vandenberg Village". The plan says Santa Maria. The page also wastes 146KB on the hero image.

Santa Maria is the HQ city and the primary market. Vandenberg Village is a small outlying community. Every top service page is currently optimized for the wrong city, and now it is on the indexable production domain.

## Regressions vs prior audit

The origin changed from staging to apex, so pages were matched by path.

**Verdict transitions:** none got worse. Two pages improved:
- `/` went red to green. The canonical and JSON-LD fixes cleared it, and the brand-gold contrast failures are gone (Accessibility 92 to 96).
- `/service-areas/vandenberg-village-ca/` went red to green. The canonical and JSON-LD fixes cleared it.

**Score deltas:** no category dropped 3 or more points site-wide. No page dropped 5 or more points in any category.

**Per-page metric regression (rubric threshold met):**
- `/service-areas/vandenberg-village-ca/`: LCP went from 781ms to 1240ms (+459ms), and Performance went from 100 to 97. It is still inside the 2.5s good threshold. This is the only page with a heavier un-srcset hero (68KB wasted), and it is the first run behind the apex CDN. Re-check next month.

**New issues this month:**
- All 6 pages: `unused-javascript` (gtag.js) and `cache-insight` (Cloudflare email-decode.min.js). Both come from things added at cutover, not from template changes.
- `/services/`, `/services/water-damage-restoration/`, `/contact/`: `forced-reflow-insight`.
- `/`, `/services/`: `low_content_rate` (DataForSEO text-to-HTML ratio, low).
- All 6 pages: `rankai_jsonld_relative_image_url`. This is flagged for the first time. It was probably also present last month, hidden behind the `https://None` IDs.
- `/service-areas/vandenberg-village-ca/`: `largest-contentful-paint` (score 0.88, see above).

**Issues resolved since last audit:** (positive, keep doing this)
- All 6 pages: `canonical` is fixed. `rel=canonical` now self-references `https://callcrs.com/...`.
- All 6 pages: `rankai_jsonld_invalid_entity_id` is fixed. No `https://None` identifiers remain in any JSON-LD block.
- All 6 pages: `is-crawlable` passes. The staging noindex cleared at apex cutover.
- `/`: `color-contrast` passes. The gold-on-white CTA and eyebrow failures are fixed site-wide. Only the breadcrumb failure is left on inner pages.

## Recommended next actions (priority order)

1. **(money pages, template, high impact)** Force re-render the stale pages from the current url-plan. For `/services/`, all 15 `/services/{slug}/` landings, and `/contact/`, run the targeted render with `--url <path> --force`, then push to main. The scaffold's rendered-content guard (`scripts/build_site.py:971`) will not touch them otherwise. Afterwards, `curl -s https://callcrs.com/services/water-damage-restoration/ | grep -o '<title>[^<]*'` must return "Water Damage Restoration in Santa Maria | Coastal Restoration Services Inc".
2. **(money pages, template)** Add `fetchpriority="high"` and `srcset`/`sizes` to the inner-page hero `<img>`, copying the homepage hero markup. This removes 126KB on `/contact/` and 93KB on `/services/`, and clears `lcp-discovery-insight` on 5 pages.
3. **(template, accessibility)** In the breadcrumb component, change `text-dark/50` to `text-dark/70`. Give the footer `tel:`/`mailto:` links at least 24px height (`inline-block py-1`). Together these clear `color-contrast` and `target-size` on every inner page and lift Accessibility from 90-92 toward 100.
4. **(site-level)** Add a Cloudflare redirect rule so `https://www.callcrs.com/*` returns 301 to `https://callcrs.com/$1`. Right now www serves a full 200 duplicate, and only rel=canonical keeps it in check.
5. **(template, low)** Emit absolute URLs for JSON-LD `image`/`logo` (`https://callcrs.com/images/logo.webp`), and defer `gtag.js` until after `load`.

## Notes / caveats

- **Apex, not staging.** `apex_cutover.completed_at` = 2026-09-08T17:52:50Z. Scores now include the Cloudflare CDN. The comparison with last month's staging scores is therefore not exactly like-for-like, especially for LCP.
- **Desktop only.** Lighthouse ran with `formFactor=desktop`. Mobile would typically score 10-20 performance points lower. `target-size` matters more on mobile than the medium severity here suggests.
- **Same URL set as last month.** Water and fire landings were kept (mold is tied at priority 9.0) so the comparison holds. The url-plan has no Santa Maria service-area page (the HQ city is served by the home and service pages), so `vandenberg-village-ca` stays as the service-area slot. Its Vandenberg Village metadata is correct for that page.
- **Schema detector.** DataForSEO again reported `has_micromarkup: false` even though 3-5 JSON-LD blocks are on every page. Schema was checked by parsing the served HTML directly.
- **Issue ID provenance.** IDs prefixed `rankai_` are Rank AI derived checks. All other IDs are genuine Lighthouse or DataForSEO on-page IDs.
- **Clean results.** No broken links or resources, no mixed content, one H1 per page, titles 39-46 chars, meta descriptions 117-152 chars, canonicals self-referencing on the apex, no missing alt text.
- **Method.** Direct DataForSEO REST (`on_page/lighthouse/live/json` with `for_mobile=false`, `on_page/instant_pages`). Cost was about $0.039 (6 x $0.005 + 6 x $0.0015).
