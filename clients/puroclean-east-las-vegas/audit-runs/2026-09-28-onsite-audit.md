# Onsite Audit - PuroClean of East Las Vegas - 2026-09-28

**Live origin audited:** https://purocleaneastlasvegas.com (apex)
**Site verdict:** green (desktop, canonical). Mobile supplementary verdict: **amber** (5 of 6 pages)
**URLs audited:** 6
**Prior audit:** 2026-08-27
**Scoring form factor:** desktop (canonical). A full mobile pass was also captured; see "Mobile pass" below.

> **Headline:** Desktop is still near-perfect. Mobile regressed sharply since last month: average mobile performance fell from 94.7 to 87.7, and 5 of 6 pages dropped from green to amber on mobile. The cause is a new GA4 tag (`gtag/js?id=G-M4N5NVD0WN`) now loaded on every page. It adds 159 KB of script, 70 KB of it unused on first load, and pushed mobile TBT on the homepage from 2 ms to 264 ms. On top of that, none of last month's five fixes have shipped yet. The non-home hero images still load without `fetchpriority`, which is why they now lose the bandwidth race to the new script.

## Site rollup

| Metric | Score (desktop) | Δ vs prior | Score (mobile) | Δ vs prior |
| --- | ---: | ---: | ---: | ---: |
| Performance | 99.0 | -0.7 | 87.7 | **-7.0** |
| Accessibility | 96.0 | 0.0 | 96.2 | 0.0 |
| Best Practices | 100.0 | 0.0 | 100.0 | 0.0 |
| SEO | 100.0 | 0.0 | 100.0 | 0.0 |

Pages by verdict (desktop): green: 6, amber: 0, red: 0, error: 0
Pages by verdict (mobile): green: 1, amber: 5, red: 0, error: 0

On-page health is still clean on all six pages: every page returns 200, has a correct self-referencing canonical and exactly one H1, and has titles (48-63 chars) and meta descriptions (99-143 chars) inside the target ranges. Every page is above its url-plan target word count, and there are zero broken links or resources.

## Per-page scores (desktop, canonical)

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 100 | 100 | 100 | 0.97s | 0.005 |
| `/services/` | services-hub | green | 99 | 95 | 100 | 100 | 0.98s | 0.004 |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 95 | 100 | 100 | 0.90s | 0.007 |
| `/services/mold-remediation/` | service-landing | green | 99 | 95 | 100 | 100 | 0.89s | 0.007 |
| `/service-areas/henderson-nv/` | service-area | green | 99 | 95 | 100 | 100 | 0.87s | 0.004 |
| `/contact/` | contact | green | 99 | 96 | 100 | 100 | 0.90s | 0.043 |

Desktop TBT is 0 ms on all six pages. INP is null everywhere because it is a field metric and a Lighthouse lab run does not produce it.

## Mobile pass (supplementary)

| URL | Verdict | Perf | Δ | A11y | BP | SEO | LCP | Δ LCP | TBT | CLS |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | amber | 86 | -11 | 100 | 100 | 100 | 3.45s | +0.80s | 264 ms | 0.034 |
| `/services/` | amber | 83 | -14 | 95 | 100 | 100 | 4.30s | +1.62s | 183 ms | 0.035 |
| `/services/fire-damage-restoration/` | amber | 87 | -5 | 95 | 100 | 100 | 4.09s | +0.72s | 50 ms | 0.023 |
| `/services/mold-remediation/` | green | 96 | 0 | 95 | 100 | 100 | 2.80s | 0.00s | 58 ms | 0.001 |
| `/service-areas/henderson-nv/` | amber | 88 | -5 | 96 | 100 | 100 | 3.99s | +0.79s | 27 ms | 0.001 |
| `/contact/` | amber | 86 | -7 | 96 | 100 | 100 | 3.95s | +0.71s | 168 ms | 0.020 |

Mobile LCP is now above 4.0s ("poor" per Google's Core Web Vitals) on `/services/` and `/services/fire-damage-restoration/`, and only just below it on `/contact/` and `/service-areas/henderson-nv/`. Last month's mobile TBT was 0-2 ms on every page. It is now 27-264 ms, which fits a new main-thread script.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 5 | high | Breadcrumb `text-dark/50` (#888c93 on white, 3.37:1) fails WCAG AA 4.5:1. Unchanged since last month. See item 3. |
| `unused-javascript` | 6 | medium | **New this month.** `https://www.googletagmanager.com/gtag/js?id=G-M4N5NVD0WN`, 159 KB total, 70 KB unused. See item 2. |
| `image-delivery-insight` | 6 | medium | Hero `<img>` on non-home templates has no `srcset`/`sizes` (contact hero wastes 124 KB on desktop). The logo is a 49 KB PNG shown at 128x56. See items 1 and 4. |
| `lcp-discovery-insight` | 5 | medium | LCP hero `<img>` lacks `fetchpriority="high"` (Lighthouse checklist: `priorityHinted: false`). See item 1. |
| `network-dependency-tree-insight` | 6 | medium | Document to CSS to hero image chain. Mostly fixed by item 1. |
| `cache-insight` | 6 | low | Short cache lifetime on static assets (Lighthouse estimates 0 KiB savings). Informational. |
| `render-blocking-insight` | 6 | low | `/_astro/_slug_.CXeMlxpf.css` (8.8 KB) blocks first paint, up to 150 ms on mobile. |
| `has_render_blocking_resources` | 6 | low | DataForSEO flags the same stylesheet. |
| `has_micromarkup_errors` | 5 | low | Warnings on optional schema fields, plus one real defect: empty `foundingDate`. See item 5. |
| `low_content_rate` | 3 | low | Low text-to-HTML ratio on `/`, `/services/`, `/contact/`. All three are above their word-count targets, so no action needed. |

## Money page alerts

**Desktop: none.** All four money-page archetypes are green on desktop.

**Mobile (supplementary), 4 money pages amber:**

- **`/services/`** (services-hub): mobile performance 83, LCP 4.30s, TBT 183 ms. This is the worst page on the site. The hero `hero-bg.webp` (176 KB) downloads at full size, with no `fetchpriority`, while gtag.js competes for the throttled connection.
- **`/`** (home): mobile performance 86, LCP 3.45s, TBT 264 ms. The home hero is already optimized, so nearly all of this drop comes from gtag.js running on the main thread.
- **`/contact/`** (contact): mobile performance 86, LCP 3.95s, TBT 168 ms. Same bare hero `<img>`; Lighthouse measures 146 KB of wasted image bytes on mobile.
- **`/services/fire-damage-restoration/`** (service-landing): mobile performance 87, LCP 4.09s. The hero lacks `srcset` and `fetchpriority`, costing about 850 ms of LCP by Lighthouse's estimate.

## Regressions vs prior audit

**Verdict transitions (desktop):** none. All 6 pages stayed green.

**Verdict transitions (mobile):** 5 pages went green to amber: `/`, `/services/`, `/services/fire-damage-restoration/`, `/service-areas/henderson-nv/`, `/contact/`. Only `/services/mold-remediation/` held green (96).

**Metric regressions over threshold:**
- Site-level: mobile average performance -7.0 (threshold -3).
- `/service-areas/henderson-nv/`: desktop LCP 0.60s to 0.87s (+269 ms, threshold +200 ms). This is the only desktop regression.
- Mobile performance drops of 5 points or more on 5 pages, mobile LCP up 709-1620 ms on the same 5 pages, and mobile TBT up by 100 ms or more on `/`, `/services/`, `/contact/`. Full numbers are in the mobile table above.

**New issues this month:**
- All 6 pages: `unused-javascript` for the new GA4 gtag.js. This is the root-cause finding for the mobile regression.
- `/service-areas/henderson-nv/`: `forced-reflow-insight`, 49 ms of unattributed forced reflow. Low priority. It may come from gtag or the embedded map iframe.
- `/services/`, `/contact/`: `low_content_rate`. Both pages are above their word-count targets, so this is a ratio shift (likely the added inline gtag bootstrap script), not a content problem.
- `/services/`, fire, mold, henderson, `/contact/`: `cache-insight`. **Not a real new defect.** Last month's state file kept only the top 5 failing audits per URL, and `cache-insight` did show up on the homepage then. This month stores every failing audit, so future diffs will not have this truncation artifact.

**Issues resolved since last audit:**
- `/`: `largest-contentful-paint` no longer fails on desktop (0.97s). Treat this as lab variance, not a real fix. Desktop LCP actually rose about 120 ms.

**Last month's recommendations:** none of the five have shipped. The live HTML was re-checked this run. The non-home hero is still `<img src="/images/hero-bg.webp" ... loading="eager">` with no `srcset`, `sizes` or `fetchpriority`. The breadcrumb still uses `text-dark/50`, the Henderson card span is still `text-slate-400`, the logo is still `/images/logo.png`, and both JSON-LD blocks still emit `"foundingDate":""`.

## Recommended next actions (priority order)

1. **(money pages, template, carried over and now urgent)** Bring the non-home hero `<img>` up to the homepage standard in the `services-hub`, `service-landing`, `service-area` and `contact` templates (selector `main.flex-1 > section.relative > div.absolute > img.w-full`). Add `srcset="/images/hero-bg-480w.webp 480w, /images/hero-bg-768w.webp 768w, /images/hero-bg-1200w.webp 1200w, /images/hero-bg.webp 1478w"`, `sizes="100vw"`, `fetchpriority="high"`, `decoding="async"` and intrinsic `width`/`height`. Do the same for per-service hero images such as `fire-damage-restoration.webp`. The variants already exist on disk. This clears `lcp-discovery-insight` on 5 pages. It also lets the hero win the bandwidth race against gtag.js, which should bring mobile LCP back under 3s on `/services/`, `/contact/` and the service landings.

2. **(money pages, template, new)** Stop GA4 from competing with first paint. The layout currently emits `<script async src="https://www.googletagmanager.com/gtag/js?id=G-M4N5NVD0WN">` in `<head>`. Change it to inject gtag.js after the `load` event, for example `window.addEventListener('load', () => requestIdleCallback(() => { /* append gtag script */ }))`, keeping the inline `dataLayer`/`gtag('config', ...)` stub so no events are lost. The alternative is to run it off the main thread with Partytown (`@astrojs/partytown`, `type="text/partytown"`). Either way, this removes the 70 KB `unused-javascript` finding from the critical path on all 6 pages and should bring homepage mobile TBT from 264 ms back toward 0.

3. **(template, accessibility, carried over)** Change the breadcrumb link class from `text-dark/50` (#888c93, 3.37:1) to `text-dark/70` or `#5f636b` (6.03:1) in the breadcrumb partial. On `/service-areas/henderson-nv/`, change the card-grid `span.text-slate-400` (#94a3b8, 2.56:1) to `text-slate-600` (#475569). These two edits clear `color-contrast` on all 5 affected pages and put accessibility at 100 sitewide.

4. **(template, sitewide, carried over)** Replace `/images/logo.png` (49 KB PNG shown at 128x56, about 46-48 KB wasted on every page) with an SVG, or a 2x WebP at about 256x112. Update both the header (`header.bg-white ... img.h-14`) and footer (`footer.bg-white ... img.h-16`) references.

5. **(template, schema, carried over)** In the Organization and LocalBusiness JSON-LD blocks, drop the `foundingDate` key when it has no value (it is currently serialized as `""` on every page) or fill it with the real founding year. This is the only real defect behind `has_micromarkup_errors`.

## Notes / caveats

- **Apex, not staging.** The client record has no `apex_cutover.completed_at`, but it does have `cut_over_at: 2026-07-23`. `https://purocleaneastlasvegas.com/` returns 200 with no `x-robots-tag`, so the staging-noindex correction does not apply and SEO counts toward the verdict. HSTS, CSP frame-ancestors and referrer-policy headers are present.
- **Desktop is canonical; mobile is supplementary.** The state file's `verdict` is the desktop verdict (green), per methodology. The mobile amber is in `site_rollup.verdict_mobile` and `money_page_alerts_mobile`. It is still the most important finding this month, because Google ranks on mobile-first signals.
- **Lab variance.** These are single Lighthouse runs. Desktop shifts of about 1 point and about 100-150 ms LCP (seen on every page) are within normal run-to-run noise. The mobile regression is well beyond noise and has a clear cause: a new third-party script on every page, `unused-javascript` newly failing on all 6 URLs, and TBT jumping from about 0 to 264 ms. The only mobile page that held steady, `/services/mold-remediation/`, shows gtag still costs 58 ms TBT there. Re-audit after items 1 and 2 ship to confirm the recovery.
- **`has_micromarkup_errors` stays low severity,** as documented in the 2026-08-27 report. The validator messages concern optional fields (FAQPage `Question.text`/`answerCount`, trailing BreadcrumbList `item`). That is not enough to flip money pages to amber.
- **Checks not recorded as issues:** `is_https`, `canonical`, `has_html_doctype`, `has_micromarkup` and the `seo_friendly_url*` family are passes. `no_image_title` is not an SEO requirement (alt coverage is 100%). `frame` on Henderson is the expected map embed.
- **URL set** is the same as last month, derived from `plan/url-plan.json`: the top two service landings by priority in plan order, plus the first service-area slug (`henderson-nv`) because no area is marked `primary: true`.
- **Client record status** is `"live"` rather than `"active"`. `build_status` is `pushed_main` and the apex serves 200, so the audit proceeded.
- **Cost.** 12 Lighthouse live runs (6 desktop, 6 mobile) at $0.005 each and 6 instant_pages at $0.00045 each, about **$0.06** in total.
