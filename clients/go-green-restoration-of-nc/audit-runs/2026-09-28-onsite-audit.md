# Onsite Audit: Go Green Restoration of NC, 2026-09-28

**Live origin audited:** https://gogreenrestorationofnc.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-08-27 (green)

**Form factor:** DESKTOP only. The Lighthouse run used `formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`. Mobile scores typically run 10 to 20 performance points lower and are not represented anywhere in this report. Do not quote these numbers as mobile scores.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.5 | -0.8 |
| Accessibility | 96.0 | 0 |
| Best Practices | 96.0 | 0 |
| SEO | 100.0 | 0 |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

The apex is live and indexable (no `x-robots-tag: noindex`), so SEO counts toward the verdict in full. All six pages returned HTTP 200 and had a correct self-referencing canonical, exactly one H1, a title of 60 to 65 characters, a meta description of 109 to 144 characters, 100 percent image alt coverage, zero broken links, zero broken resources, and zero mixed content. JSON-LD was re-verified on every page (3 to 5 blocks each).

The main change this month is that a GA4 tag (`G-FB7ZB4MR6V`) was added to the site-wide layout. It is behind both new Lighthouse findings, and it is the likely cause of a small, consistent rise in LCP on every page. None of the changes crossed a regression threshold.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 98 | 100 | 96 | 100 | 1.01s | 0.007 |
| `/services/` | services-hub | green | 99 | 95 | 96 | 100 | 1.03s | 0.007 |
| `/services/water-damage-restoration/` | service-landing | green | 99 | 95 | 96 | 100 | 0.92s | 0.014 |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 95 | 96 | 100 | 0.96s | 0.007 |
| `/service-areas/raleigh-nc/` | service-area | green | 98 | 95 | 96 | 100 | 1.04s | 0.009 |
| `/contact/` | contact | green | 98 | 96 | 96 | 100 | 1.06s | 0.040 |

Total blocking time was 0 ms on five pages and 24 ms on the homepage. This run did not report INP, so it is recorded as null rather than estimated.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | medium | Still open from last month. `logo.png` (103 KB PNG) wastes 95 KiB on every page. The inner-page hero `hero-bg.webp` (263 KB) has no `srcset` and wastes 216 KiB on `/contact/`, 174 KiB on `/services/`, and 149 KiB on `/service-areas/raleigh-nc/`. |
| `image-aspect-ratio` | 6 | medium | Still open. The footer logo `img.h-16` declares `width="48" height="48"` but renders at 386x80. |
| `unused-javascript` | 6 | medium | **New.** GA4 `gtag/js?id=G-FB7ZB4MR6V` loads about 159 KB and 43 percent of it goes unused (66 to 69 KiB per page). Lighthouse estimates 50 to 90 ms of LCP savings. |
| `render-blocking-insight` | 6 | low | One 8.9 KB Astro stylesheet (`_slug_.DLUF6T80.css`) blocks render for about 55 ms. Marginal. |
| `has_render_blocking_resources` | 6 | low | DataForSEO's counterpart to the check above, flagging the same stylesheet. |
| `cache-insight` | 6 | low | Cloudflare's injected `email-decode.min.js`, about 288 bytes of waste. Cloudflare injects this file, so the template can't fix it. |
| `network-dependency-tree-insight` | 6 | low | Diagnostic only. Lighthouse measures 0 ms of savings. No action needed. |
| `color-contrast` | 5 | medium | Still open. The breadcrumb link `a.text-dark/50` renders `#888c93` on `#ffffff`, a 3.37:1 ratio at 12px. WCAG AA requires 4.5:1. |
| `lcp-discovery-insight` | 5 | low | Still open. The inner-page hero `<img>` has no `fetchpriority="high"`. The homepage hero already has it. |
| `forced-reflow-insight` | 3 | low | **New.** About 41 ms of forced reflow that Lighthouse couldn't trace to a source, on `/services/`, `/services/water-damage-restoration/`, and `/service-areas/raleigh-nc/`. It appeared at the same time as the GA4 tag. |

## Money page alerts

None. All four money-page archetypes (`home`, `services-hub`, `service-landing`, `contact`) came back green.

## Regressions vs prior audit

**Verdict transitions:** none. All six pages stayed green.

**Threshold regressions:** none. No category dropped 5 or more points, and no Core Web Vital crossed its threshold (LCP +200 ms, CLS +0.02, TBT +100 ms).

**Watch item: LCP moved up on every page.** Each page is below the threshold, but they all moved the same way, which points to a site-wide change rather than noise:

| URL | LCP prior | LCP now | Δ |
| --- | ---: | ---: | ---: |
| `/` | 942 ms | 1008 ms | +66 ms |
| `/services/` | 898 ms | 1033 ms | +135 ms |
| `/services/water-damage-restoration/` | 759 ms | 916 ms | +157 ms |
| `/services/fire-damage-restoration/` | 771 ms | 961 ms | +190 ms |
| `/service-areas/raleigh-nc/` | 900 ms | 1037 ms | +137 ms |
| `/contact/` | 865 ms | 1064 ms | +199 ms |

`/contact/` is 1 ms below the regression threshold, and its CLS went from 0.026 to 0.040. Both are still well inside "good" territory, but next month's audit could flag this page if nothing changes.

**New issues this month:**
- All 6 pages: `unused-javascript`. The new GA4 gtag.js loads about 68 KiB of unused code.
- `/services/`, `/services/water-damage-restoration/`, `/service-areas/raleigh-nc/`: `forced-reflow-insight`, about 41 ms of forced reflow with no traced source.
- `/`: `low_content_rate` (DataForSEO). The text-to-HTML ratio is 0.096, just under the 0.10 threshold. 19 KB of the 75 KB page is 47 inline SVG icons. Low severity.

**Issues resolved since last audit:** none. All five recommendations from 2026-08-27 are still open.

## Recommended next actions (priority order)

1. **(money page + template)** Add `srcset`/`sizes` and `fetchpriority="high"` to the inner-page hero `<img>` component. `/contact/` still ships the full 263 KB `hero-bg.webp` into a 1350x207 band, wasting 216 KiB on the most conversion-critical page. The same component wastes 174 KiB on `/services/` and 149 KiB on `/service-areas/raleigh-nc/`. Copy the homepage hero markup, which already references `hero-bg-480w.webp` / `hero-bg-768w.webp` variants with `fetchpriority="high"`. This fixes `image-delivery-insight` and `lcp-discovery-insight` on five pages, and it is the best way to recover the LCP drift on `/contact/`.
2. **(template, new this month)** Delay GA4 so it no longer competes with first paint. It already has `async`. Next, inject the gtag.js `<script>` after the `load` event or on first user interaction, or move it to a web worker with `@astrojs/partytown` (`type="text/partytown"`). Keep the tag: it was added on purpose via `plan-input.json`. After the change, confirm in GA4 DebugView that the `generate_lead` event with `transport_type: 'beacon'` still fires on form submission. This targets the new `unused-javascript` and `forced-reflow-insight` findings and the +66 to +199 ms LCP drift.
3. **(template)** Convert `/images/logo.png` to WebP (or a compact SVG) and correct the footer logo's `width`/`height` to its real aspect ratio (roughly 386x80, not 48x48). The logo loads on all six pages and wastes 95 KiB each time. This fixes both `image-delivery-insight` for the logo and `image-aspect-ratio` across the site.
4. **(template, accessibility)** Darken the breadcrumb link class from `text-dark/50` to at least `text-dark/70` to clear 4.5:1. This is the only reason accessibility is 95 to 96 instead of 100 on five of six pages.
5. **(housekeeping)** Add a 301 from `/sitemap.xml` to `/sitemap-index.xml`, for example with a `/sitemap.xml /sitemap-index.xml 301` line in the Pages `_redirects` file. `/sitemap.xml` still returns 404. The canonical sitemap and the `robots.txt` reference are correct, but many crawlers and audit tools check the conventional path first.

## Notes / caveats

- **Desktop-only scoring.** Repeated because it matters: these are desktop Lighthouse numbers. A mobile run would score noticeably lower on performance, and the GA4 cost in particular grows on a throttled mobile CPU.
- **DataForSEO false positives excluded again.** Each one was re-checked against the live HTML on 2026-09-28 and is recorded per URL under `excluded_false_positives`. `has_micromarkup` (JSON-LD is present on all 6 pages), `has_meta_title` (every page has a valid `<title>`; the check looks for the non-standard `<meta name="title">`), `from_sitemap` (all 6 URLs are in `/sitemap-0.xml`; the check probes only `/sitemap.xml`), `no_image_title` (image `title` attributes are not a ranking signal; alt coverage is 100 percent), and `frame` on the Raleigh page (a single lazy-loaded Google Maps embed with a `title` attribute).
- **Severity was calibrated to measured impact,** as in the prior audit. Lighthouse 13 `*-insight` audits score 0 even when they measure 0 ms of savings. Nothing on this site rises to high severity.
- **Word count vs plan target.** The homepage has 1187 words against a 1200 target, and `/services/` has 774 against 800. Both are within 3.5 percent of target and unchanged from last month. This belongs to content planning (System 4), not technical health, and DataForSEO has no check ID for it, so it is noted here rather than logged as an issue.
- **Audit-history note.** The 2026-08-27 baseline stored only the top 5 Lighthouse issues per URL. This run also stores the full failing list (`lighthouse_failing_audit_ids`), so future new/resolved diffs will be exact. This month's "new issues" list only includes IDs that appeared nowhere in the prior audit.
- **Client record status is still `onboarding`, not `active`.** The audit went ahead because `build_status` is `pushed_main` and the apex serves HTTP 200. This was flagged last month and hasn't changed. Someone should confirm whether the field is stale.
- **Apex selection was inferred.** The client record has no `apex_cutover.completed_at`. The apex was chosen based on `cut_over_at` (2026-08-09), a live 200 response, and the absence of a noindex header. The staging Pages preview still carries `x-robots-tag: noindex`, so the staging correction was not needed.
- **URL set held constant for comparability.** Water damage, fire damage, and mold remediation are tied at the top service-landing priority (9.0). The first two were kept to match the baseline. The service-area slot uses `/service-areas/raleigh-nc/` because the plan still has no page for Middlesex, the business's home base. That gap in the URL plan was flagged last month and is still open.
- **Run cost:** about $0.04 (6 Lighthouse calls at $0.005, 6 instant_pages calls at $0.0015).
