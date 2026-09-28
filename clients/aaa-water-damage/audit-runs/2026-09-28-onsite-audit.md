# Onsite Audit - AAA Water Damage Restoration & Carpet Care - 2026-09-28

**Live origin audited:** https://staging.rankai-aaa-water-damage.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26
**Form factor:** desktop (DataForSEO Lighthouse 13.4.0, `formFactor=desktop`). Mobile performance would typically score 10-20 points lower. This is not a mobile-first score.

## Environment caveat - SEO score is inconclusive this run

The apex domain `aaawaterdamagehawaii.com` still does not resolve (no DNS A record; the client record says it is not yet registered) and `apex_cutover` is null, so the Cloudflare Pages preview was audited again. That preview sends `x-robots-tag: noindex` (verified with `curl -sI` today). Lighthouse's `is-crawlable` audit therefore fails on all 6 pages and holds SEO at 69.

**This is not a site defect.** SEO is excluded from every verdict in this report. Verdicts use Performance, Accessibility, and Best Practices only. The SEO score is recorded as measured, with status `inconclusive - staging noindex artifact, re-audit after apex cutover`.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.2 | -0.6 |
| Accessibility | 95.2 | 0 |
| Best Practices | 100 | 0 |
| SEO | 69* | 0 |

\* Staging noindex artifact, excluded from verdicts.

Pages by verdict: {green: 1, amber: 5, red: 0, error: 0}

Month over month, the site has not changed in any way that matters. Every defect from the 2026-08-26 audit is still live. Nothing from last month's action list has been shipped yet.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 100 | 100 | 100 | 69* | 0.82s | 0.003 |
| `/services/` | services-hub | amber | 98 | 95 | 100 | 69* | 1.02s | 0.003 |
| `/services/water-damage-restoration/` | service-landing | amber | 99 | 95 | 100 | 69* | 0.84s | 0.030 |
| `/services/mold-remediation/` | service-landing | amber | 99 | 95 | 100 | 69* | 0.85s | 0.003 |
| `/service-areas/hawaii-kai-hi/` | service-area | amber | 100 | 95 | 100 | 69* | 0.80s | 0.004 |
| `/contact/` | contact | amber | 99 | 91 | 100 | 69* | 0.88s | 0.006 |

TBT was 0ms on every page. INP was not reported (a lab run has no interactions).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 5 | high | The breadcrumb links use `text-dark/50` (#878b95), which gives 3.41:1 contrast against the background. WCAG AA needs 4.5:1. In `src/components/Breadcrumb.astro` lines 8 and 14, change `text-dark/50` to `text-dark/70` or darker. |
| `has_micromarkup_errors` | 5 | medium | Fix the schema in `src/lib/schema.ts`. Line 214 leaves `item` off the last breadcrumb `ListItem`. Lines 52-53 output `LocalBusiness.image`/`logo` as the relative path `/images/logo.webp`. See the schema note below. |
| `unsized-images` | 6 | medium | The header logo `<img>` in `src/components/Header.astro:15` has no `width`/`height`. Add the logo's real pixel dimensions as attributes. |
| `image-delivery-insight` | 6 | medium | The inner-page hero images are larger than they need to be. Wasted bytes: 118KB on `/contact/`, 84KB on `/services/` (`hero-bg.webp` served with no srcset), 56KB on `/services/water-damage-restoration/`. Add `srcset`/`sizes`, as `Hero.astro` already does on the homepage, and re-encode at around q70. |
| `lcp-discovery-insight` | 5 | medium | The inner-page hero `<img>` (the LCP element) has no `fetchpriority="high"`. Add it at `src/pages/services/[slug].astro:60`, `src/pages/service-areas/[area].astro:52`, and `src/pages/[fixed].astro:53`. |
| `largest-contentful-paint` | 6 | low | Scores 0.94-0.98 with LCP at 0.80-1.02s. This is noise. It will clear once the hero fixes above ship. |
| `render-blocking-insight` | 6 | low | The Astro CSS bundle `_astro/_slug_.9z1Y-Y7S.css` blocks render for up to 60ms. Too small to be worth fixing now. |
| `network-dependency-tree-insight` | 6 | low | An informational chain warning on the same CSS bundle. No action needed. |
| `is-crawlable` | 6 | low | Staging noindex artifact. It clears automatically at apex cutover. |

## Money page alerts

- **`/contact/`**: amber. Accessibility 91, the lowest in the set. The page still renders `<a href="mailto:" class="font-bold text-white no-underline break-all">`, an empty mailto link with no text. Lighthouse flags it as `link-name` (high) and `agent-accessibility-tree` (Agentic Browsing 67). The cause is `"contact": null` in `clients/aaa-water-damage.json`. `src/components/FreeEstimateForm.astro:162` renders the email row even when `brand.email` is empty (`Footer.astro:23` handles this correctly). The breadcrumb `color-contrast` failure and `has_micromarkup_errors` also apply here.
- **`/services/`**: amber. Performance 98, Accessibility 95, LCP 1.02s. Causes are breadcrumb `color-contrast` and `has_micromarkup_errors`. The hero is served without srcset (84KB wasted). The page has 755 words against an 800-word target.
- **`/services/water-damage-restoration/`**: amber. Performance 99, Accessibility 95, LCP 0.84s. It has the same two template causes, plus 56KB wasted on the under-compressed `water-damage-restoration.webp` hero.
- **`/services/mold-remediation/`**: amber. Performance 99, Accessibility 95, LCP 0.85s. It has the same two template causes.

## Regressions vs prior audit

**Verdict transitions:** none. Every page has the same verdict as on 2026-08-26 (1 green, 5 amber).

**Site-level score deltas:** no category dropped 3 or more points. Performance -0.6, all others 0.

**Per-page metric regressions (rubric thresholds met):**
- `/services/`: LCP went from 819ms to 1021ms (+202ms). Performance went from 100 to 98.
- `/services/water-damage-restoration/`: LCP went from 454ms to 843ms (+389ms). Performance went from 100 to 99.

Both pages are still well inside the 2.5s "good" LCP threshold. The hero markup and assets have not changed since last month, so this is most likely run-to-run variance on the Pages preview. Re-check next month. If it happens again, investigate.

**New issues this month:**
- `/`: `high_waiting_time` and `high_loading_time`. DataForSEO's single instant fetch measured a TTFB of 4029ms. Three follow-up curl requests measured 0.08-0.11s, and Lighthouse LCP on the same page was 0.82s. The likely cause is a cold Cloudflare Pages edge cache. Low severity, no action.
- `/services/`: `first-contentful-paint` scored 0.99 (just under 1). Noise, no action.

**Issues resolved since last audit:** none.

### Note on `has_micromarkup_errors`

This month, DataForSEO's instant-pages checker reported `has_micromarkup: false` on all 6 pages. Every page actually serves 3-5 JSON-LD blocks (`Organization`, `WebSite`, `LocalBusiness`, plus `FAQPage` and `BreadcrumbList` on inner pages), so the detector did not parse the schema at all. That means the missing error flag is **not a fix**. I parsed the served HTML directly and confirmed the defects are still there:

- The last breadcrumb `ListItem` has no `item` on all 5 inner pages (for example `{"@type":"ListItem","position":2,"name":"Contact"}`).
- `LocalBusiness.image` and `LocalBusiness.logo` are `/images/logo.webp` (relative path) on all 6 pages.
- `LocalBusiness.address` has no `streetAddress`. **This is intentional and should stay that way.** `onboarding_notes.sab` says this is a service-area business whose street address is never published. City-level `PostalAddress` is valid for a service-area business.

The issue is carried forward on the same 5 pages that had it last month. The state file marks it `source: "carried_forward_verified"`, so the verdicts do not wrongly flip to green.

## Recommended next actions (priority order)

1. **(blocker, all pages)** Cut over the apex domain `aaawaterdamagehawaii.com` and re-audit. According to `onboarding_notes.domain_status`, the domain is **not registered yet** and is still on the `awaiting_intake` list. Register it, create the Cloudflare zone, point it at the Pages project, set `apex_cutover.completed_at`, then re-run this audit. The SEO scores are deferred until then, not resolved. Canonicals already point at the apex, so a squatter registering the domain first would take over every canonical on the site. Treat registration as urgent.
2. **(money page)** Fix the empty email link on `/contact/`. Get the client's email and set it in `clients/aaa-water-damage.json` (`contact` is null). Also wrap the email row in `src/components/FreeEstimateForm.astro:158-163` in `{brand.email && (...)}`, matching `Footer.astro:23`, so a missing email hides the row instead of rendering a dead link. This clears `link-name` and `agent-accessibility-tree`. This is the second month this has been flagged.
3. **(template, high)** Darken the breadcrumb link color. Change `text-dark/50` to `text-dark/70` on lines 8 and 14 of `src/components/Breadcrumb.astro`. This clears `color-contrast` on 5 of the 6 audited pages and should bring them to Accessibility 100.
4. **(template, medium)** Repair the schema in `src/lib/schema.ts`. Always set `item` on the last `ListItem` (drop the `!isLast` condition on line 214 and use the current page URL). Prefix `brand.logoUrl` with `brand.canonicalUrl` on lines 52-53 so `image`/`logo` are absolute. Leave `streetAddress` out: this is a service-area business, and the street address is never published.
5. **(template, medium)** Tune the inner-page hero images. Add `fetchpriority="high"` to the hero `<img>` in `services/[slug].astro:60`, `service-areas/[area].astro:52`, and `[fixed].astro:53`, and give it the `srcset`/`sizes` pattern from `ui/Hero.astro`. Add explicit `width`/`height` to the header logo in `Header.astro:15`. This clears `lcp-discovery-insight`, most of `image-delivery-insight`, and `unsized-images`.

## Notes / caveats

- **Source paths** above refer to the monorepo copy at `sites/aaa-water-damage/`. The live deploy repo is `restorationai/aaa-water-damage-site`. The deployed header logo class (`max-w-[42vw]`) differs slightly from the monorepo copy (`max-w-[30vw]`), so confirm which copy is current before editing.
- **URL selection.** There is no `audit-urls.txt`, so the URLs were auto-derived from `plan/url-plan.json`. No service-area page has `primary: true` and the client record has no business address, so the service-area slot kept `/service-areas/hawaii-kai-hi/` from last month for comparability. The two service landings are the two priority-9.0 pages.
- **Client record hygiene.** `status` is still `"pending"` although `build_status` is `pushed_main`. The methodology expects `"active"`. The audit went ahead because the site is live, same as last month. `contact` is still null, which directly causes action 2.
- **`frame` on `/service-areas/hawaii-kai-hi/`** is the intentional Google Maps embed. Low severity, no action.
- **Minor on-page items (low):** the homepage meta description is 164 characters (limit 160), and `/services/` has 755 words against an 800-word target.
- **Cost:** 6 Lighthouse calls ($0.005 each) plus 7 instant-pages calls ($0.0015 each), about $0.04 total.
