# Onsite Audit - AAA Water Damage Restoration & Carpet Care - 2026-09-28

**Live origin audited:** https://staging.rankai-aaa-water-damage.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26
**Lighthouse form factor:** desktop (Lighthouse 13.4.0, `formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`)

## Environment caveat - SEO score is inconclusive this run

The apex domain `aaawaterdamagehawaii.com` still does not resolve (no DNS A record), and the client record has no `apex_cutover`, so this audit ran against the Cloudflare Pages preview again.

`curl -sI` on the preview confirms the response header `x-robots-tag: noindex`. Cloudflare adds this header to every `*.pages.dev` preview. Because of it, the Lighthouse `is-crawlable` audit fails on all 6 URLs and pulls the SEO category down to **69 on every page**.

**This is not a site defect.** SEO is left out of every verdict in this report. Verdicts use Performance, Accessibility, and Best Practices only. The state file records the SEO score as measured, with status `inconclusive - staging noindex artifact, re-audit after apex cutover`.

Canonical tags, schema `url`, and `og:url` point at the apex domain, which is correct for a site before cutover. They are not counted as issues.

**The site has been on `main` since 2026-08-26 and was pushed again today (2026-09-28), but the apex has still not been cut over.** According to `onboarding_notes.domain_status` and `awaiting_intake`, `aaawaterdamagehawaii.com` has never been registered: there is no Cloudflare zone and no DNS. Registering the domain and cutting over is now the most useful single step for this client. Until then, SEO cannot be measured and none of the site's pages can be indexed.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.5 | -0.3 |
| Accessibility | 95.2 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 69.0 (inconclusive) | 0.0 |

Pages by verdict: green: 1, amber: 5, red: 0, error: 0

Every page returned HTTP 200. The audit found:

- no broken internal links, broken external links, or broken resources
- no mixed content
- no duplicate titles or descriptions
- exactly one H1 per page
- full image alt coverage

DataForSEO `onpage_score` was 97.44 on all six pages, the same as last month. The amber rollup comes from the same two template defects reported last month (schema validation and breadcrumb contrast), not from general page health.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 100 | 100 | 69* | 0.82s | 0.003 | 0ms |
| `/services/` | services-hub | amber | 99 | 95 | 100 | 69* | 0.81s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | amber | 99 | 95 | 100 | 69* | 0.87s | 0.031 | 0ms |
| `/services/mold-remediation/` | service-landing | amber | 100 | 95 | 100 | 69* | 0.79s | 0.003 | 0ms |
| `/service-areas/hawaii-kai-hi/` | service-area | amber | 100 | 95 | 100 | 69* | 0.79s | 0.004 | 0ms |
| `/contact/` | contact | amber | 100 | 91 | 100 | 69* | 0.79s | 0.004 | 0ms |

\* SEO is excluded from the verdict because of the staging noindex artifact. INP was null on every page, because a desktop lab run with no user flow does not measure it.

On desktop, every page passes the LCP, CLS, and TBT thresholds with a wide margin.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 5 | high | **Not fixed since last month.** Breadcrumb links still use `text-dark/50`, which renders `#878b95` on `#ffffff` at 12px. That is a 3.41:1 ratio; WCAG AA requires 4.5:1. Change the breadcrumb link class to `text-dark/70` or darker in the shared breadcrumb component. The homepage passes only because it has no breadcrumb. |
| `has_micromarkup_errors` | 5 | medium | **Not fixed.** It appears on exactly the 5 pages that output `FAQPage` + `BreadcrumbList`. The served JSON-LD still has three defects: (1) the last breadcrumb `ListItem` has no `item` (for example `{"@type":"ListItem","position":2,"name":"Contact"}`); (2) `LocalBusiness.image` and `LocalBusiness.logo` are the relative path `/images/logo.webp`; (3) `LocalBusiness.address` has no `streetAddress`. This one is intentional: the client is a service-area business whose street address is never published (`onboarding_notes.sab`). It may be part of what the validator flags, but it must not be "fixed" by adding a street. |
| `lcp-discovery-insight` | 5 | medium | **Not fixed.** The hero on inner pages is still a plain `<img src="/images/hero-bg.webp" class="w-full h-full object-cover" loading="eager">`, with no `srcset`, `sizes`, or `fetchpriority="high"`. Lighthouse confirms `priorityHinted: false` on each of the 5 pages. The homepage hero already uses the correct markup. |
| `unsized-images` | 6 | medium | **Not fixed.** The header `<img src="/images/logo.webp">` still has no `width`/`height` attributes. |
| `image-delivery-insight` | 6 | medium | **Not fixed.** `logo.webp` is 12.5KB at 360x360 but displays at 64x64, wasting 12KB on every page. The 175KB `hero-bg.webp` on inner pages wastes 84KB on `/services/`, 59KB on the service-area page, and 118KB on `/contact/`. `services/water-damage-restoration.webp` (173KB) wastes 56KB. |
| `largest-contentful-paint` | 6 | low | Scores 0.97 to 0.98 at about 0.8s. This is noise at desktop speed, and the hero fix above clears it. It now shows on the water-damage landing as well (see Regressions). |
| `render-blocking-insight` | 6 | low | `_astro/_slug_.9z1Y-Y7S.css` (8.8KB) blocks rendering for 40 to 56ms. It can be left alone. |
| `network-dependency-tree-insight` | 6 | low | Informational warning about request-chain depth on the same CSS bundle. No action needed. |

## Money page alerts

- **`/contact/`** (amber) is the top priority. Accessibility is still 91, the lowest in the set. The page still renders `<a href="mailto:" class="font-bold text-white no-underline break-all">`, an **empty `mailto:` link with no text**. This triggers `link-name` (high) and `agent-accessibility-tree`, and holds Agentic Browsing at 67. The cause is unchanged: `"contact": null` in `clients/aaa-water-damage.json`. The page also has the breadcrumb contrast issue and schema errors, and its un-optimized hero wastes 118KB.
- **`/services/`** (amber) has Accessibility 95 and LCP 0.81s. The causes are breadcrumb `color-contrast`, `has_micromarkup_errors`, and the 84KB of wasted hero bytes. Word count is 755 against an 800-word target (low).
- **`/services/water-damage-restoration/`** (amber) has Accessibility 95 and LCP 0.87s. The causes are the same breadcrumb contrast and schema issues, plus a hero image that is 173KB and under-compressed.
- **`/services/mold-remediation/`** (amber) has Accessibility 95 and LCP 0.79s. It has the same two template causes.

`/` is green.

## Regressions vs prior audit

**Verdict transitions:** none. All six pages kept their 2026-08-26 verdicts (one green, five amber).

**Score deltas:** no category moved by more than 1 point on any page. The site-level averages moved by -0.3 or less, well inside the 3-point flag threshold.

**Core Web Vitals flag:**
- `/services/water-damage-restoration/`: LCP rose from 454ms to 873ms (+419ms), which crosses the 200ms flag threshold. This is **most likely lab variance, not a code change.** The LCP element is the same `<img src="/images/services/water-damage-restoration.webp" loading="eager">` as last month, with the same missing `fetchpriority`. The measured LCP breakdown adds up to only about 240ms (TTFB 90ms, load delay 7ms, load 82ms, render delay 61ms). 873ms is in line with the other five pages (786 to 825ms), which suggests last month's 454ms was the outlier. Check it next month; the hero fix in action 3 removes the risk either way.

**New issues this month:**
- `/services/water-damage-restoration/`: `largest-contentful-paint` (score 0.97). This follows from the LCP change above.
- `/services/`: `first-contentful-paint` (score 0.94, 810ms) and `speed-index` (score 0.99). On this page FCP equals LCP because the hero paints first. Last month's per-URL list was capped at 5 issues and last month's LCP was nearly the same (819ms), so both were probably present last month without being recorded. Treat them as low.

**Issues resolved since last audit:**
- `/service-areas/hawaii-kai-hi/`: `bf-cache` now passes. Last month the Google Maps iframe blocked back/forward cache restoration. The iframe is still on the page (`frame` is still flagged, low), so the fix was on the embed side and not something we changed.

**None of last month's five recommended actions has shipped.** All eight template issues remain, and the served markup matches last month exactly.

## Recommended next actions (priority order)

1. **(money page, high)** Fix the empty `mailto:` link on `/contact/`. Get the client's email address and fill in `contact.email` in `clients/aaa-water-damage.json` (currently `null`). Also change the contact template so it leaves the email block out entirely when no address is set, instead of outputting `href="mailto:"`. This clears `link-name` and `agent-accessibility-tree`, and should lift `/contact/` accessibility from 91 and Agentic Browsing from 67. This is the second month in a row this has been flagged.
2. **(template, high)** Change the breadcrumb link class from `text-dark/50` to `text-dark/70` (or darker) in the shared breadcrumb component. Then check that the ratio is at least 4.5:1 against `#ffffff` at 12px. This clears `color-contrast` on 5 of the 6 audited pages, and on every other breadcrumb page on the site.
3. **(template, high impact)** Copy the homepage hero markup into the inner-page hero component: `srcset` pointing at the existing `hero-bg-480w.webp` / `hero-bg-768w.webp` variants, `sizes="100vw"`, `fetchpriority="high"`, and `decoding="async"`. Do the same for service-specific heroes such as `services/water-damage-restoration.webp`, which already has `-480w` variants deployed. This clears `lcp-discovery-insight` on 5 pages, removes 56 to 118KB per page, and removes the water-landing LCP risk.
4. **(template, medium)** Fix the three schema defects:
   - add `item` (the page URL) to the last breadcrumb `ListItem`
   - make `LocalBusiness.image` and `LocalBusiness.logo` absolute URLs (`https://aaawaterdamagehawaii.com/images/logo.webp`)
   - **do not add a street address.** The client record's `onboarding_notes.sab` says this is a service-area business whose street address is never to be published. Keep `PostalAddress` at city, region, and ZIP, and add an `areaServed` list (the Oahu service-area cities) to `LocalBusiness` so the business location is expressed without a street.

   Then re-run and confirm whether `has_micromarkup_errors` clears on all 5 pages. If it still fires after the first two fixes, call the `/v3/on_page/microdata` endpoint to get the exact validator message before making further changes.
5. **(template, medium)** Add `width="128" height="128"` to the header logo `<img>` and ship a 128x128 `logo.webp` variant. This clears `unsized-images` on all 6 pages and saves 12KB per page site-wide.

Registering `aaawaterdamagehawaii.com` and cutting over the apex (see the environment caveat) is still the step that unblocks any SEO scoring. Re-run this audit against `https://aaawaterdamagehawaii.com` once `apex_cutover.completed_at` is set.

## Notes / caveats

- **The `/contact/` amber verdict understates the problem.** Under the rubric, a page turns red only when a counted category falls below 70 or there is a high-severity on-page (DataForSEO) issue. The broken `mailto:` is a high-severity Lighthouse accessibility failure on the main conversion page, so action 1 matters more than the amber label suggests.
- **The client record needs cleanup.** `clients/aaa-water-damage.json` still has `status: "pending"`, while `build_status` is `pushed_main` and `last_pushed_main_at` is 2026-09-28. The audit went ahead because the site is live and can be audited, as it did in August. `contact` is still `null`, which directly causes action 1. `nap.street` is empty on purpose (service-area business), so leave it empty. Last month's report recommended filling it in; this report replaces that advice.
- **The instant_pages call was re-run.** The first `instant_pages` pass left out `validate_micromarkup=true` and returned `has_micromarkup=false` on every page. That was a false negative: all 6 pages serve 3 to 5 JSON-LD blocks, confirmed by fetching the HTML. It was re-run with `validate_micromarkup=true`, `enable_javascript=true`, `load_resources=true` to match the August baseline, and only that run's data is used here. The discarded pass cost $0.0009 plus $0.0108 for an intermediate try.
- **Desktop only.** Mobile performance usually lands 10 to 20 points lower, and the un-optimized inner-page hero will hurt more on a throttled mobile connection. Desktop was kept to match the baseline for month-over-month comparison.
- **URL selection.** There is no `audit-urls.txt`, so the URLs came from `plan/url-plan.json`. The set is the same 6 URLs as August: the two highest-priority landings (both priority 9.0), and `hawaii-kai-hi` as the first service-area slug. No area has `primary: true`, and the plan has no Honolulu area page.
- **Regression baseline.** Last month's per-URL issue lists were capped at 5. To find new and resolved issues, the full prior failing set was rebuilt from those lists, `site_rollup.template_issues`, and the prior report's notes (`is-crawlable` on all pages, `bf-cache` on the service-area page).
- **Cost.** 6 Lighthouse live calls at $0.005 each plus 6 `instant_pages` calls at $0.0018 each come to $0.041 for the data used. With the discarded instant_pages passes, the total was about $0.053, well under the $0.30-0.50 target. The `on_page_lighthouse` / `on_page_instant_pages` MCP tools are not available in this environment, so the calls went directly to the authenticated DataForSEO REST API, which returned the full `audits` array inline.
