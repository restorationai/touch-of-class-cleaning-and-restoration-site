# Onsite Audit - Crew Restoration & Construction - 2026-09-28

**Live origin audited:** https://crew3r.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-26
**Form factor:** desktop only (see Notes)

> **Read this month correctly.** The verdict is unchanged: amber, same 1 green / 5 amber
> split, no red pages, no errors. None of the five August recommendations have shipped.
> The BreadcrumbList schema defect, the contrast failures, the non-prioritized hero and
> the 640x640 logo are all still live, byte for byte. The one real change is new: a
> Google Analytics 4 tag (`G-GCKPEW6C00`) now loads on every page, and it brings
> 69 KiB of unused JavaScript with it. LCP rose 235-383ms on three pages in the same
> window. Every page is still under 1 second LCP on desktop, so this is a trend to
> contain, not an emergency.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.2 | -0.6 |
| Accessibility | 96.0 | -0.3 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | 0.0 |

Pages by verdict: green: 1, amber: 5, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 100 | 100 | 100 | 0.91s | 0.003 | 0ms |
| `/services/` | services-hub | amber | 99 | 95 | 100 | 100 | 0.91s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | amber | 99 | 95 | 100 | 100 | 0.91s | 0.003 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | amber | 99 | 95 | 100 | 100 | 0.89s | 0.003 | 0ms |
| `/service-areas/brookings-sd/` | service-area | amber | 100 | 95 | 100 | 100 | 0.79s | 0.003 | 0ms |
| `/contact/` | contact | amber | 99 | 96 | 100 | 100 | 0.87s | 0.005 | 0ms |

Core Web Vitals are inside the "good" thresholds on every page on desktop. INP was not
reported by Lighthouse (it needs field data or a scripted interaction) and is recorded
as null.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | Still led by `/images/logo.png`: a 640x640 PNG (78.9 KB, 77.3 KB wasted) rendered at 64x64 in the header. Export a 128x128 WebP and swap the header `<img>`. Secondary items are page-specific (for example `water-damage-restoration.webp` at 186 KB with 62 KB wasted). |
| `unused-javascript` | 6 | high | New this month. `https://www.googletagmanager.com/gtag/js?id=G-GCKPEW6C00` ships 159 KB with about 69 KiB unused on every page. It already loads `async`. Delay injection until after `load` or first user interaction, or move it to a Partytown web worker (Astro has an official integration). |
| `render-blocking-insight` | 6 | high | `/_astro/_slug_.DEXtdMVo.css` (about 9.1 KB) blocks first render. It now scores 0 with about 50-59ms savings on water, fire and contact, up from 0.5 on the homepage only in August. Inline the above-the-fold rules and defer the rest. |
| `network-dependency-tree-insight` | 6 | high | Same critical chain as August: document to the Astro CSS bundle plus `/_astro/page.CyD_eNI3.js`. Shrinks when the render-blocking fix above lands. |
| `cache-insight` | 6 | medium | Only flags Cloudflare's own `email-decode.min.js` at a 2-day TTL (0 KiB real savings). Turn off Email Address Obfuscation in Cloudflare, or ignore. |
| `color-contrast` | 5 | high | Unchanged. Breadcrumb links use `text-dark/50` at 12px on white. The `.btn-accent` `tel:+16059652727` CTA (white on `#e9292f`, 14px bold) and `text-slate-400` on the service-area template also fail 4.5:1. |
| `lcp-discovery-insight` | 5 | high | Unchanged. Every non-home template still emits the hero without `fetchpriority="high"` or `srcset`. The homepage already does it correctly. |
| `has_micromarkup_errors` | 5 | medium | Unchanged. The final BreadcrumbList `ListItem` is still `{"@type":"ListItem","position":3,"name":"Water Damage Restoration"}` with no `item`. |
| `low_content_rate` | 3 | low | `/`, `/services/`, `/contact/`. All three are above their word-count targets (1366/1200, 804/800, 619/400), so this is markup weight, not thin content. No action. |
| `forced-reflow-insight` | 2 | high | New on `/` (97ms) and `/services/` (45ms), unattributed. Most likely the GA4 bootstrap reading layout. Should drop out with the gtag delay above. Re-check next month before chasing it separately. |

## Money page alerts

- **`/services/`** - verdict: amber. Accessibility 95 (breadcrumb `<a href="/">` contrast), BreadcrumbList schema validation error. LCP 0.91s, hero has no `fetchpriority`.
- **`/services/water-damage-restoration/`** - verdict: amber. Accessibility 95, down 1 from August. Three contrast nodes (two breadcrumb links plus the `.btn-accent` `tel:` button), BreadcrumbList schema error, render-blocking CSS now costing about 59ms.
- **`/services/fire-damage-restoration/`** - verdict: amber. Same three contrast nodes and schema error as water. Accessibility 95, down 1 from August.
- **`/contact/`** - verdict: amber. Accessibility 96, BreadcrumbList schema error. LCP 0.87s, up from 0.49s. The conversion path itself is clean: HTTP 200, canonical correct, no broken links.

`/` is green. `/service-areas/brookings-sd/` is amber but is not a money archetype.

## Regressions vs prior audit

**Verdict transitions:** none. Every URL holds its August verdict.

**Score regressions (5+ points):** none. The largest per-page drop is 1 point (performance 100 to 99 on four pages, accessibility 96 to 95 on water and fire). No site average dropped 3+ points.

**Core Web Vitals regressions (LCP +200ms or more):**
- `/`: LCP 577ms to 907ms (+330ms)
- `/contact/`: LCP 492ms to 875ms (+383ms)
- `/service-areas/brookings-sd/`: LCP 560ms to 795ms (+235ms)

The other three pages rose 61-104ms. CLS and TBT did not regress anywhere. The site-wide rise lines up with the new GA4 tag competing for bandwidth during load. Some of it may be run-to-run Lighthouse variance, so confirm on the next audit after the gtag change.

**New issues this month:**
- All six pages: `unused-javascript` (GA4 gtag, about 69 KiB unused). On fire it is present but ranks outside the top 5.
- `/`, `/services/`: `forced-reflow-insight` (97ms and 45ms of unattributed reflow)
- `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`, `/contact/`: `render-blocking-insight` got worse and now scores 0 with about 50ms of estimated savings
- `/contact/`: `low_content_rate` (informational, page is above its word target)

**Issues resolved since last audit:** none. Every issue flagged in August is still failing.

## Recommended next actions (priority order)

1. **(money page + template, high impact, carried from August)** Add `"item"` with the
   page's own canonical URL to the final `ListItem` in the shared breadcrumb component's
   BreadcrumbList JSON-LD. This is still the only reason `/services/`, both service
   landings, `/contact/` and the service-area page are amber and not green. It is a
   one-line fix in one component and it applies to every built page.
2. **(money page + template, accessibility, carried from August)** Change breadcrumb
   links from `text-dark/50` to `text-dark/70` or darker. Darken the `.btn-accent`
   background from `#e9292f` to a red that passes 4.5:1 with white (about `#c81e24`).
   Replace `text-slate-400` on the service-area template with `text-slate-600`. This
   brings accessibility to 100 on five pages.
3. **(template, new this month)** Delay the GA4 tag. Load
   `gtag/js?id=G-GCKPEW6C00` after `window.load` or first interaction, or run it through
   `@astrojs/partytown`. This targets the new `unused-javascript` and
   `forced-reflow-insight` flags and the LCP creep on `/`, `/contact/` and the
   service-area page. Confirm GA4 still records page views after the change.
4. **(money page + template, carried from August)** Copy the homepage hero markup
   (`srcset`, `sizes="100vw"`, `fetchpriority="high"`) into the services-hub,
   service-landing, service-area and contact templates. This clears
   `lcp-discovery-insight` on five pages.
5. **(template, carried from August)** Replace the 640x640 `/images/logo.png` (78.9 KB)
   in the header with a 128x128 WebP (about 3-5 KB). This saves about 77 KB on every
   page load. Also make the `LocalBusiness` `image` and `logo` absolute
   (`https://crew3r.com/images/logo.png`). They are still relative.

## Notes / caveats

- **August recommendations did not ship.** The rendered HTML on 2026-09-28 still
  shows: the terminal breadcrumb `ListItem` without `item`, `text-dark/50` breadcrumbs,
  the 640x640 PNG logo, bare heroes on non-home templates, and relative `LocalBusiness`
  `image`/`logo`. Unless those fixes are queued in the client deploy repo, the
  October audit will say the same thing.
- **One August item partly addressed.** `LocalBusiness.foundingDate` was an empty
  string in August and is now `"2015"`, which matches the homepage's current
  "Since 2015" copy. DataForSEO never flagged it, so it does not show under resolved
  issues. The published phone number also changed to `+16059652727`. That is noted
  only because it appears in the contrast-failing CTA.
- **Origin.** Audited the apex. The client record has no `apex_cutover.completed_at`
  but has `cut_over_at 2026-08-08`. All six URLs returned HTTP 200 with no
  `x-robots-tag: noindex`, so the staging SEO-exclusion correction does not apply and
  all four categories counted.
- **Form factor.** Desktop only (DataForSEO `for_mobile=false`). Mobile performance
  would typically land 10-20 points lower. The GA4 payload and the unprioritized hero
  both cost more on mobile. Do not quote these as mobile scores.
- **Client record status.** Still `status: "onboarding"` with `build_status: pushed_main`
  and a live apex since 2026-08-08. This was flagged last month and is still stale.
  The audit proceeded because the site is live and auditable.
- **Tooling.** The `on_page_lighthouse` / `on_page_instant_pages` MCP tools are not
  exposed by this DataForSEO MCP build. Used authenticated REST calls to
  `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages`. Total spend was
  about $0.04.
- **Comparison method.** August stored only the top 5 failing audits per URL. This run
  stores the top 5 plus the full failing set (`lighthouse_failing_audits`), so October
  gets a clean diff. An August issue counts as resolved only if it is absent from the
  full current failing set. `cache-insight` still fails everywhere but now ranks
  outside the top 5 on most pages.
- **URL selection.** Held identical to August for comparability (derived from
  `plan/url-plan.json`, no `audit-urls.txt`). Four service landings tie at priority
  9.0 (fire, mold, roofing, water). Water and fire were kept.
- **Vendor false positive.** The DataForSEO `frame` check again fires on
  `/service-areas/brookings-sd/` for its map `<iframe>`. Not reported.
- **Clean bill on the basics.** Across all six URLs: HTTP 200, correct self-referencing
  canonicals, exactly one H1 each, titles 41-46 chars, meta descriptions 110-151 chars,
  no duplicate titles or descriptions, no broken links or resources, no mixed content,
  `image-alt` passing everywhere, and every page above its `target_word_count`.
