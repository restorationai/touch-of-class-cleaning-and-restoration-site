# Onsite Audit: Go Green Restoration of NC, 2026-09-29

**Live origin audited:** https://gogreenrestorationofnc.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-08-27 (green)

**Form factor:** DESKTOP only (`formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`). Mobile scores typically run 10 to 20 performance points lower and are not represented in this report.

**Headline:** The site is still green on every page, but it is slower than last month. A Google Analytics 4 tag (`G-FB7ZB4MR6V`) was added to the layout since the baseline. It loads 159 KB of JavaScript on every page, and 69 KB of that goes unused. LCP rose 96 to 235 ms on all six pages. Separately, `/contact/` now shows a layout shift of 0.103 CLS. That is above Google's 0.1 "good" threshold, and it happens on the estimate form.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.3 | -1.0 |
| Accessibility | 96.0 | 0 |
| Best Practices | 96.0 | 0 |
| SEO | 100.0 | 0 |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

No site-level average dropped by 3 or more points. The apex is indexable (no `x-robots-tag: noindex`), so SEO counts toward the verdict. Every page returned HTTP 200 and has:

- a correct self-referencing canonical
- exactly one H1
- a title of 60 to 65 characters
- a meta description of 109 to 144 characters
- zero broken links and zero broken resources

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 100 | 96 | 100 | 1.04s | 0.012 |
| `/services/` | services-hub | green | 98 | 95 | 96 | 100 | 1.07s | 0.010 |
| `/services/water-damage-restoration/` | service-landing | green | 99 | 95 | 96 | 100 | 0.86s | 0.014 |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 95 | 96 | 100 | 1.01s | 0.014 |
| `/service-areas/raleigh-nc/` | service-area | green | 99 | 95 | 96 | 100 | 1.03s | 0.015 |
| `/contact/` | contact | green | 96 | 96 | 96 | 100 | 1.02s | 0.103 |

TBT was 0 ms on all six pages. This Lighthouse run did not report INP, so it is recorded as null.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `unused-javascript` | 6 | medium | **New this month.** `googletagmanager.com/gtag/js?id=G-FB7ZB4MR6V` is 159 KB with 69 KB unused, and costs an estimated 50 to 100 ms of LCP per page. Load gtag after the `load` event or on first interaction, or move it into a Partytown worker. |
| `image-delivery-insight` | 6 | medium | The header `logo.png` is 105 KB and wastes 97 KB on every page: 863x159 source for a 521x96 slot, PNG format. The inner-page heroes (`hero-bg.webp`, `services/*.webp`) have no `srcset`, and Lighthouse finds 94 to 221 KB of recompression savings in `hero-bg.webp`. |
| `has_render_blocking_resources` | 6 | low | One 9 KB Astro stylesheet (`_slug_.DLUF6T80.css`) blocks render for roughly 30 to 57 ms. Also in the `<head>`: the Google Fonts Inter stylesheet is included twice, once async (`media="print" onload`) and once as a plain blocking `<link>`. The blocking copy cancels out the async trick. |
| `image-aspect-ratio` | 5 | medium | The footer logo declares `width="48" height="48"` but its true ratio is 863x159 and it renders at 386x80. Unchanged since last month. |
| `color-contrast` | 5 | medium | Breadcrumb links use `a.text-dark/50`, which is `#888c93` on `#ffffff`: 3.37:1 at 12px, below the 4.5:1 WCAG AA minimum. Unchanged since last month. This is the only thing holding accessibility at 95. |
| `lcp-discovery-insight` | 3 | low | The inner-page hero `<img>` is `loading="eager"` but has no `fetchpriority="high"` (seen on `/services/`, fire landing, and `/contact/`). The homepage hero already has the correct markup. |

## Money page alerts

None by verdict: all four money-page archetypes are green. One money-page metric is out of range even though the verdict is green:

- **`/contact/`**: CLS 0.103, up from 0.026. This is the only page above Google's 0.1 "good" threshold. The element that shifts is `section#estimate`, the Request Your Free Estimate form, which is the conversion point. Lighthouse lists two causes:
  - the Inter web font swapping in (`display=swap`), which reflows the large uppercase heading and form labels
  - the unsized footer logo (`width="48" height="48"` against the real 863x159 ratio)

## Regressions vs prior audit

**Verdict transitions:** none. All six pages were green and are still green.

**Metric regressions (past threshold):**
- `/contact/`: CLS rose from 0.026 to 0.103 (+0.077; the threshold is +0.02). Performance fell from 99 to 96.
- `/services/fire-damage-restoration/`: LCP rose from 771 ms to 1006 ms (+235 ms; the threshold is +200 ms).

**Below threshold but on every page:** LCP is up on all six pages. Home +96 ms, services hub +169 ms, water landing +104 ms, Raleigh +134 ms, contact +150 ms. The timing matches the new gtag script, since it is the only new third-party request.

**New issues this month:**
- All 6 URLs: `unused-javascript`. The new GA4 gtag script ships 69 KB of unused JS.
- `/contact/`: `cumulative-layout-shift`, `layout-shifts`, `cls-culprits-insight`. This is the estimate-section shift described above.
- `/services/`: `forced-reflow-insight`. 32 ms of unattributed forced reflow; minor.
- `/`: `low_content_rate` (DataForSEO). Low text-to-HTML ratio. Word count is 1187, essentially the same as last month's 1181. The likely cause is added markup such as the inline gtag bootstrap, not lost content. Low priority.
- `/services/water-damage-restoration/` and `/services/fire-damage-restoration/`: `image-delivery-insight` now falls inside the top failing audits. It may simply have been cut from last month's top-5 list (see Notes).

**Issues resolved since last audit:** none. Every issue flagged in August is still present in this run's full failing-audit list.

## Recommended next actions (priority order)

1. **(money page)** Stop the layout shift on the `/contact/` estimate form. Two parts:
   - Self-host Inter with `<link rel="preload" as="font" crossorigin>`, or add a metric-matched fallback: an `@font-face` for Arial with `size-adjust`, `ascent-override`, and `descent-override` set for Inter.
   - Delete the duplicate blocking Google Fonts `<link>` from the layout `<head>`.

   The goal is CLS under 0.1 on the page that converts leads.
2. **(template, high impact)** Defer the GA4 gtag script. Load `gtag/js?id=G-FB7ZB4MR6V` after `window.load` or on first user interaction, or run it off the main thread with Partytown. This recovers the 69 KB of unused JS on all six pages and most of the 100 to 235 ms LCP increase since August.
3. **(template)** Fix the logo in one pass:
   - Export `logo.png` as WebP at 2x display size (about 1042x192).
   - Set the header `<img>` `width`/`height` to the real ratio.
   - Change the footer `<img>` from `width="48" height="48"` to `width="863" height="159"`, or matching scaled values.

   This clears `image-aspect-ratio` on 5 pages, saves about 97 KB per pageview, and removes one of the two `/contact/` CLS causes.
4. **(money page, carried over)** Give the inner-page hero component the homepage hero markup: `srcset` with the existing `hero-bg-480w/768w` variants, `sizes="100vw"`, and `fetchpriority="high"`. `/contact/` still ships the full 269 KB `hero-bg.webp` into a 1350x207 band, wasting 221 KB.
5. **(template, accessibility, carried over)** Change the breadcrumb link class from `text-dark/50` to `text-dark/70` or darker, to reach 4.5:1 contrast. This lifts accessibility from 95 to 100 on five pages.

## Notes / caveats

- **Desktop-only scoring.** These are desktop Lighthouse numbers. On mobile, the gtag cost and the font-swap shift would both be larger.
- **The GA4 addition was inferred, not confirmed.** The August audit's third-party findings listed only Cloudflare's `email-decode.min.js`. This month, `gtag/js?id=G-FB7ZB4MR6V` appears on every page. Confirm the tag ID belongs to this client's GA4 property before changing how it loads. Deferring it keeps tracking intact.
- **Comparison limitation.** Last month's state file kept only the top 5 Lighthouse audits per URL. Some low-savings audits listed as "new" may have been present but cut off, most likely `image-delivery-insight` on the landings and `forced-reflow-insight`. The `unused-javascript` and CLS findings are genuinely new: they have measurable savings and would have made any top-5 list. This run stores the full failing-audit ID list per URL (`lighthouse_failing_audit_ids_all`), so next month's diff will be exact.
- **DataForSEO false positives.** `no_image_title` (all pages) and `frame` (Raleigh, a lazy-loaded Google Maps embed with a `title`) were excluded from verdicts, the same treatment as last month. The three checks that misfired in August (`has_micromarkup`, `has_meta_title`, `from_sitemap`) did not fire this run.
- **Word counts against url-plan targets.** Home has 1187 words (target 1200) and the services hub has 774 (target 800). Both are within about 3 percent of target and are unchanged from August, so they are not flagged as issues. The landings (1737 to 1861 against 1100), Raleigh (1336 against 900) and contact (689 against 400) all clear their targets.
- **Severity calibration.** Lighthouse 13 `*-insight` audits score 0 even when they measure 0 ms of savings. Severity here reflects measured savings, as it did last month.
- **URL selection.** Mode B (url-plan). Three service landings tie at priority 9.0: water, fire, and mold. Water and fire were kept so the comparison with August is like for like.
- **Carried-over items not re-listed above:**
  - Client status is still `onboarding` rather than `active`.
  - There is no `apex_cutover.completed_at` field; the apex was inferred from `cut_over_at` 2026-08-09.
  - `/sitemap.xml` still returns 404. The canonical `/sitemap-index.xml` is fine.
  - There is no Middlesex service-area page. `/service-areas/middlesex-nc/` 301-redirects to `/`.
- **Run cost:** 0.0309 USD (6 Lighthouse live calls at 0.005, 6 instant_pages calls at 0.00015).
