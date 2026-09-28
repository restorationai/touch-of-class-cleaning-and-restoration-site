# Onsite Audit - AAA Water Damage Restoration & Carpet Care - 2026-09-28

**Live origin audited:** https://staging.rankai-aaa-water-damage.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26
**Lighthouse form factor:** desktop (`formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`), Lighthouse 13.4.0

## Environment caveat - SEO score is inconclusive this run

The apex domain `aaawaterdamagehawaii.com` still does not resolve (no DNS A record) and the client record still has `apex_cutover: null`, so this audit ran against the Cloudflare Pages preview again.

`curl -sI` on the preview confirms the response header `x-robots-tag: noindex`. Cloudflare injects this on all `*.pages.dev` preview deployments. The Lighthouse `is-crawlable` audit therefore fails on all 6 URLs and drags the SEO category down to **69 on every page**.

**This is not a site defect.** SEO is excluded from every verdict in this report. Verdicts use Performance, Accessibility, and Best Practices only. The SEO score is recorded in the state file as measured, with status `inconclusive - staging noindex artifact, re-audit after apex cutover`.

Canonical tags and `og:url` on every page correctly point at `https://aaawaterdamagehawaii.com/...`. That domain is not resolving yet, which is expected before cutover and is not counted as a canonical issue.

## Headline: nothing changed in 33 days

Scores, failing audits, and the served HTML are effectively identical to 2026-08-26. **None of the five recommendations from last month have been applied.** The empty `mailto:` link on `/contact/`, the breadcrumb contrast failure, the inner-page hero markup, the logo sizing, and the schema defects are all still live. The list below carries them forward unchanged. This month is about getting them shipped, not finding new issues.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.7 | -0.1 |
| Accessibility | 95.2 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 69.0 (inconclusive) | 0.0 |

Pages by verdict: green: 1, amber: 5, red: 0, error: 0

All 6 pages returned HTTP 200 on both Lighthouse and instant_pages. We found no broken internal or external links, no broken resources, and no mixed content. Every page has exactly one H1, every title is 30-65 characters, and every image has alt text. DataForSEO `onpage_score` is 97.44 on all six.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 100 | 100 | 100 | 69* | 0.77s | 0.003 | 0ms |
| `/services/` | services-hub | amber | 100 | 95 | 100 | 69* | 0.78s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | amber | 100 | 95 | 100 | 69* | 0.80s | 0.031 | 0ms |
| `/services/mold-remediation/` | service-landing | amber | 100 | 95 | 100 | 69* | 0.79s | 0.004 | 0ms |
| `/service-areas/hawaii-kai-hi/` | service-area | amber | 99 | 95 | 100 | 69* | 0.80s | 0.004 | 0ms |
| `/contact/` | contact | amber | 99 | 91 | 100 | 69* | 0.80s | 0.006 | 0ms |

\* SEO is excluded from the verdict because of the staging noindex artifact. INP is null on every page because a desktop lab run with no user flow does not measure it.

Core Web Vitals pass with a wide margin on every page on desktop.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 5 | high | Breadcrumb link `a.text-dark/50` still renders `#878b95` on `#ffffff` at 12px, a 3.41:1 ratio against the 4.5:1 minimum. Change it to `text-dark/70` or darker in the shared breadcrumb component. It is absent only on `/`, which has no breadcrumb. |
| `unsized-images` | 6 | medium | The header `<img src="/images/logo.webp">` still has no `width`/`height`. The footer logo has `width="48" height="48"`; add the same kind of attributes to the header instance. |
| `image-delivery-insight` | 6 | medium | (1) `logo.webp` is 12.5 KB, and 12.1 KB of that is wasted on every page. (2) The 175 KB `hero-bg.webp` wastes 84 KB on `/services/`, 59 KB on the service-area page, and 118 KB on `/contact/`. (3) New this month: `/services/` now shows service-card thumbnails, and the `*-480w.webp` variants are oversized for their slots, wasting about 74 KB more across 9 card images (largest: `flood-equipment-rental-480w.webp` at 15.6 KB wasted and `carpet-cleaning-480w.webp` at 13.9 KB). (4) `services/water-damage-restoration.webp` is 173 KB and wastes 56 KB. |
| `lcp-discovery-insight` | 5 | medium | The inner-page hero `<img ... class="w-full h-full object-cover" loading="eager">` still has no `fetchpriority="high"`, `srcset`, or `sizes`. The homepage hero already has all three. |
| `has_micromarkup_errors` | 5 | medium | The same five pages that emit `BreadcrumbList` and `FAQPage` still have the same defects. The terminal `ListItem` has no `item` property, and `LocalBusiness.image`/`logo` are relative `/images/logo.webp` paths. See the caveats for why this was verified by parsing the HTML directly. |
| `render-blocking-insight` | 6 | low | The Astro CSS bundle blocks render for about 50ms. Leave it alone at current scores. |
| `network-dependency-tree-insight` | 6 | low | This is an informational chain-depth warning on the same CSS bundle. No action needed. |
| `largest-contentful-paint` | 6 | low | Scores 0.98 at about 0.8s. This is noise, and the hero fix resolves it. |
| `is-crawlable` | 6 | low | Staging noindex artifact. It clears automatically at apex cutover. |
| `first-contentful-paint`, `speed-index` | 2 | low | Scores 0.95 and 0.99 on `/service-areas/hawaii-kai-hi/` and `/contact/` (simulated FCP about 0.8s). Borderline. The hero fix covers it too. |

## Money page alerts

- **`/contact/`** - amber, and still the most important page in this report. Accessibility is 91. The page still renders `<a href="mailto:" class="font-bold text-white no-underline break-all">`, an **empty `mailto:` with no link text**. This fails `link-name` (high) and `agent-accessibility-tree` (Agentic Browsing 67). The root cause is unchanged: `"contact": null` in `clients/aaa-water-damage.json`. `hero-bg.webp` also wastes 115 KB here.
- **`/services/`** - amber. Accessibility is 95 because of the breadcrumb contrast failure, plus `has_micromarkup_errors`. Image waste went up to 166 KB (from 84 KB) because the service-card thumbnails are new and oversized. Content is 755 words against an 800-word target.
- **`/services/water-damage-restoration/`** - amber. Accessibility 95 (breadcrumb contrast) and `has_micromarkup_errors`. The 173 KB hero wastes 56 KB.
- **`/services/mold-remediation/`** - amber. Same two template causes: breadcrumb contrast and `has_micromarkup_errors`.

## Regressions vs prior audit

**Site-level:** no category average dropped by 3 or more points. The largest move is Performance, down 0.1.

**Verdict transitions:** none. All six pages kept last month's verdict: `/` green, the other five amber.

**Per-URL flags:**
- `/services/water-damage-restoration/`: LCP went from 454ms to 805ms (+351ms), which crosses the 200ms threshold. **This is simulation variance, not a site change.** The LCP element is still the same `services/water-damage-restoration.webp` hero. Its observed load breakdown is about 258ms total (TTFB 62ms, load delay 30ms, load 33ms, render delay 133ms). The simulated 805ms now matches the other five pages (769-802ms). No action beyond the hero fix already listed.

**New issues this month:**
- `/service-areas/hawaii-kai-hi/` and `/contact/`: `first-contentful-paint` (0.95) and `speed-index` (0.99) score just under 1. Both are low severity and come from the same unprioritized hero image.
- `/services/`: new `image-delivery-insight` waste from the service-card thumbnails (the issue ID is carried over, the cause is new).

**Issues resolved since last audit:** none.

## Recommended next actions (priority order)

1. **(money page, high)** Fix the empty `mailto:` link on `/contact/`. Get the client's email and set `contact.email` in `clients/aaa-water-damage.json`, where `contact` is still `null`. Also make the contact template skip the email block when no address is set, instead of emitting `href="mailto:"`. This clears `link-name`, raises `/contact/` accessibility from 91, and restores Agentic Browsing from 67 to 100. **Carried over from 2026-08-26.**
2. **(template, high)** Darken the breadcrumb link from `text-dark/50` to `text-dark/70` or darker in the shared breadcrumb component. That fixes the 3.41:1 `color-contrast` failure on 5 of 6 audited pages and on every other page with a breadcrumb. **Carried over.**
3. **(template, high impact)** Port the homepage hero markup to the inner-page hero component: `srcset` pointing at the existing `hero-bg-480w.webp`/`hero-bg-768w.webp` variants, `sizes="100vw"`, `fetchpriority="high"`, and `decoding="async"`. Do the same for the per-service hero images (for example `services/water-damage-restoration.webp`, 173 KB). This clears `lcp-discovery-insight` on 5 pages and saves 56-118 KB per page. While you are in there, add a `sizes` attribute to the new `/services/` card thumbnails that matches their rendered width, so the 480w files stop being oversized.
4. **(template, medium)** Repair the schema: add `item` to the terminal `BreadcrumbList` `ListItem`, make `LocalBusiness.image` and `LocalBusiness.logo` absolute (`https://aaawaterdamagehawaii.com/images/logo.webp`). Do **not** populate `nap.street`: `onboarding_notes.sab` in the client record says this is a service-area business whose street address is never published. The city-level `PostalAddress` (locality, region, postal code) is correct as it is. This corrects last month's report, which recommended adding a street address. Should clear `has_micromarkup_errors` on 5 pages. **Carried over (revised).**
5. **(template, medium)** Add `width`/`height` to the header logo `<img>` and ship a 128x128 `logo.webp` in place of the 360x360 file. This clears `unsized-images` on all 6 pages and saves 12 KB per page. **Carried over.**

After these land, cut over the apex domain and re-audit. SEO findings stay deferred until then. The real blocker is that `onboarding_notes.domain_status` says `aaawaterdamagehawaii.com` is **not yet registered**, and registering it is the first item in `awaiting_intake`. Until it is registered, every monthly audit runs against staging and SEO stays inconclusive.

## Notes / caveats

- **Nothing was fixed between audits.** All five 2026-08-26 action items are still open, and 4 of the 5 are one-line template or data changes. If the build queue is blocked on this client, that is worth escalating.
- **Detector change on schema.** DataForSEO `instant_pages` returned `has_micromarkup: false` and `has_micromarkup_errors: false` on all 6 pages this run. Last month it returned `has_micromarkup: true`. Every page still serves valid-JSON JSON-LD (checked by parsing the served HTML). Home has `Organization`, `WebSite`, and `LocalBusiness`; the other five add `FAQPage` and `BreadcrumbList`, and the service landings add `Service`. Because the markup exists and the defects are unchanged, the `false` is a detector change, not a fix. `has_micromarkup_errors` is carried forward on the same 5 pages with `source: html_parse` in the state file. If we did not do this, 4 money pages would have been falsely promoted to green.
- **Amber does not mean low urgency on `/contact/`.** A high-severity Lighthouse accessibility failure (`link-name`) does not trip the red rubric, which only counts category scores below 70 and high-severity on-page issues. Action 1 is still the top priority.
- **Client record hygiene.** `status` is still `"pending"` while `build_status` is `pushed_main`. Pre-flight expects `"active"`. The audit ran anyway, as it did last month, because the site is live and auditable. `contact` is still `null`, and that directly causes action 1.
- **Desktop only.** Mobile performance typically lands 10-20 points lower. The un-prioritized 175 KB inner-page hero will hurt far more on a throttled mobile connection. No mobile-first claim is made.
- **URL selection.** There is no `audit-urls.txt`, so the URLs were auto-derived from `plan/url-plan.json` and match last month's set. `water-damage-restoration` and `mold-remediation` tie at priority 9.0. The service-area slot fell back to the first area slug (`hawaii-kai-hi`) because no entry has `primary: true` and the client record has no `business.address.city`. `/service-areas/urban-honolulu-hi/` exists and is the closest match to the business city. Consider marking it `primary: true` or listing it in `audit-urls.txt`, but only as a deliberate switch, because changing it breaks month-over-month comparison for that slot.
- **Issue lists.** `lighthouse_issues[]` is capped at 5 per URL. `lighthouse_failing_audit_ids` (new this run) and `site_rollup.template_issues` count every audit scoring below 1.
- **`frame` on `/service-areas/hawaii-kai-hi/`** is the intentional Google Maps embed. Low severity, no action.
- **Cost.** 6 Lighthouse live calls at $0.005 plus 6 `instant_pages` calls at $0.00015 comes to **$0.031**, under target. The `mcp__dataforseo__on_page_lighthouse` and `on_page_instant_pages` tools were not exposed in this session, so the calls went directly to the authenticated DataForSEO REST API (`/v3/on_page/lighthouse/live/json` with `for_mobile: false`, and `/v3/on_page/instant_pages`). That returned the full `audits` object inline, so no separate `full_data` call was needed.
