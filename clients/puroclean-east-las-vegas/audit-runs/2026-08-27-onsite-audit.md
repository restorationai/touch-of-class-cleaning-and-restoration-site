# Onsite Audit - PuroClean of East Las Vegas - 2026-08-27

**Live origin audited:** https://purocleaneastlasvegas.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** first audit for this client - no comparison data
**Scoring form factor:** desktop (canonical). A full mobile pass was also captured this run - see "Mobile pass" below.

## Site rollup

| Metric | Score (desktop) | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.7 | n/a |
| Accessibility | 96.0 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 100.0 | n/a |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

This site is in genuinely good technical health. Every audited page returns 200, carries a correct self-referencing canonical, has exactly one H1, has titles and meta descriptions inside the target length ranges, has 100 percent image alt coverage, exceeds its target word count, and has zero broken internal or external links. Security headers are complete (HSTS with includeSubDomains, nosniff, CSP frame-ancestors, referrer-policy, permissions-policy). robots.txt is clean and points at a sitemap index that returns 200.

The findings below are optimizations on an already-healthy site, not defects to triage. The single highest-value item is an accessibility fix; the second is a template gap that costs up to 0.73 seconds of mobile LCP on the worst-affected pages (`/services/fire-damage-restoration/` at 3.38s against the optimized homepage's 2.65s).

## Per-page scores (desktop, canonical)

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 99 | 100 | 100 | 100 | 0.85s | 0.004 |
| `/services/` | services-hub | green | 100 | 95 | 100 | 100 | 0.81s | 0.002 |
| `/services/fire-damage-restoration/` | service-landing | green | 100 | 95 | 100 | 100 | 0.79s | 0.003 |
| `/services/mold-remediation/` | service-landing | green | 100 | 95 | 100 | 100 | 0.76s | 0.006 |
| `/service-areas/henderson-nv/` | service-area | green | 100 | 95 | 100 | 100 | 0.60s | 0.004 |
| `/contact/` | contact | green | 99 | 96 | 100 | 100 | 0.84s | 0.039 |

TBT is 0 ms on all six pages. INP is null everywhere because it is a field metric and is not produced by a Lighthouse lab run.

## Mobile pass (supplementary)

The methodology assumes Lighthouse can only run desktop because the MCP `on_page_lighthouse` wrapper does not expose a form-factor parameter. This run reached the DataForSEO REST endpoint directly, which does expose `for_mobile`, so a mobile pass was captured for all six URLs at negligible extra cost. Desktop stays canonical for month-over-month comparability; mobile is stored per-URL under `.mobile` in the state file.

| URL | Perf | A11y | BP | SEO | LCP | CLS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | 97 | 100 | 100 | 100 | 2.65s | 0.033 |
| `/services/` | 97 | 95 | 100 | 100 | 2.68s | 0.034 |
| `/services/fire-damage-restoration/` | 92 | 95 | 100 | 100 | 3.38s | 0.023 |
| `/services/mold-remediation/` | 96 | 95 | 100 | 100 | 2.80s | 0.002 |
| `/service-areas/henderson-nv/` | 93 | 96 | 100 | 100 | 3.20s | 0.002 |
| `/contact/` | 93 | 96 | 100 | 100 | 3.24s | 0.018 |

Mobile average performance is 94.7. Every page still scores green, but note the Core Web Vitals detail the composite score hides: **mobile LCP exceeds Google's 2.5s "good" threshold on all six pages**, and sits at 3.2 to 3.4s on `/contact/`, `/service-areas/henderson-nv/`, and `/services/fire-damage-restoration/`. TBT stays at 0 to 2 ms, which is what keeps the composite score high. Item 1 in the recommendations addresses this directly.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `color-contrast` | 5 | high | Breadcrumb link colour fails WCAG AA. Darken `text-dark/50` in the breadcrumb partial. See item 2. |
| `network-dependency-tree-insight` | 6 | medium | Three-deep critical request chain (document to CSS to hero image). Largely resolved by preloading the hero, see item 1. |
| `image-delivery-insight` | 6 | medium | Oversized hero images on 5 pages plus a 49 KiB PNG logo sitewide. See items 1 and 3. |
| `lcp-discovery-insight` | 5 | medium | LCP hero `<img>` is missing `fetchpriority="high"`. See item 1. |
| `render-blocking-insight` | 6 | low | `/_astro/_slug_.BPKrmq6H.css` (8.7 KB) blocks render for ~158 ms on mobile. |
| `has_render_blocking_resources` | 6 | low | DataForSEO's corroboration of the same stylesheet. |
| `has_micromarkup_errors` | 5 | low | Structured-data validator warnings on optional fields. See "Notes / caveats" - mostly a false alarm, but one real empty-string defect is worth fixing (item 4). |

## Money page alerts

None. All four money-page archetypes (`home`, `services-hub`, `service-landing`, `contact`) came back green on both desktop and mobile.

Worth watching rather than alerting: `/contact/` carries the highest desktop CLS of the set at 0.039 and a mobile LCP of 3.24s. Both are inside passing thresholds (CLS good is under 0.1) but they are the weakest numbers on the most conversion-critical page.

## Regressions vs prior audit

First audit for this client - no comparison data. This run establishes the baseline. Next month's audit will diff against `clients/puroclean-east-las-vegas/onsite-audit.json`.

## Recommended next actions (priority order)

1. **(template, high impact)** Give the non-home hero images the same treatment the homepage template already has. The homepage emits a fully optimized hero:

   ```html
   <img src="/images/hero-bg.webp"
        srcset="/images/hero-bg-480w.webp 480w, /images/hero-bg-768w.webp 768w, /images/hero-bg-1200w.webp 1200w, /images/hero-bg.webp 1478w"
        sizes="100vw" width="1478" height="..." loading="eager" fetchpriority="high" decoding="async">
   ```

   The `services-hub`, `service-landing`, `service-area`, and `contact` templates emit a bare tag at selector `main.flex-1 > section.relative > div.absolute > img.w-full`:

   ```html
   <img src="/images/hero-bg.webp" alt="..." class="w-full h-full object-cover" loading="eager">
   ```

   No `srcset`, no `sizes`, no `fetchpriority`, no intrinsic `width`/`height`. The 480w/768w/1200w variants already exist on disk and are already being generated - they are simply not referenced. Consequences measured this run: a 412px-wide mobile viewport downloads the full 176 KiB `hero-bg.webp` (98 KiB wasted on `/contact/`, 86 KiB on `/service-areas/henderson-nv/`, 53 KiB on `/services/`) and the 184 KiB `fire-damage-restoration.webp` (108 KiB wasted). Adding the missing attributes clears `lcp-discovery-insight` on 5 pages, removes the bulk of `image-delivery-insight`, and should pull mobile LCP from 3.2-3.4s toward the homepage's 2.65s.

2. **(template, accessibility)** Fix the breadcrumb link contrast. The class `text-dark/50` resolves to `#888c93` on `#ffffff` at 12px normal weight, a ratio of **3.38:1** against the WCAG AA requirement of 4.5:1. It fails on all five pages that render breadcrumbs (the homepage has none, which is exactly why it scores 100 on accessibility while the rest score 95). Change the breadcrumb link to `text-dark/70` or an explicit `#5f636b` (6.03:1). Separately, on `/service-areas/henderson-nv/` the card-grid element `div.grid > div.bg-white > div.flex > span.text-slate-400` uses `#94a3b8` at 14px, a ratio of **2.56:1** - the worst on the site. Move it to `text-slate-600` (`#475569`, 7.58:1). These two changes take accessibility to 100 across all six pages.

3. **(template, sitewide)** Convert `/images/logo.png` to WebP or SVG. It is a 49 KiB PNG rendered at 128x56, and Lighthouse measures 46 KiB of that as wasted - 94 percent overhead, on every single page of the site. It is the single largest per-page image waste sitewide and the only remaining `image-delivery-insight` contributor once item 1 lands.

4. **(template, schema)** Remove or populate `foundingDate`. Both the `Organization` and `LocalBusiness` JSON-LD blocks emit `"foundingDate": ""` - an empty string - on every page. An empty property should be omitted rather than serialized. This is the one genuine defect behind the `has_micromarkup_errors` flag; the other validator messages are optional-field noise (see caveats).

5. **(per-page, low)** Optionally trim the render-blocking stylesheet. `/_astro/_slug_.BPKrmq6H.css` is 8.7 KB and blocks first paint for ~158 ms on mobile. Given it is small and already the only blocking resource, inlining the critical portion is a modest win and the lowest-priority item here. Do items 1 through 4 first.

## Notes / caveats

- **Apex, not staging.** `https://purocleaneastlasvegas.com/` returns 200 with no `x-robots-tag` header, so the Step 4 staging-noindex correction does not apply and SEO counts toward the verdict. For reference, the staging Pages preview at `staging.rankai-puroclean-east-las-vegas.pages.dev` does return `x-robots-tag: noindex`, which would have deflated SEO had it been the audit target. The client record has no `apex_cutover.completed_at` field, but it does have `cut_over_at: 2026-07-23` and the apex serves the live site, so apex was used.

- **The `has_micromarkup_errors` flag is mostly a false alarm.** DataForSEO reports it on 5 of 6 URLs. Rather than take it at face value, it was validated against the `on_page/microdata` endpoint (crawl task `08270555-1761-0216-0000-10df5c00b265`). The actual messages are: `FAQPage` `Question` missing `text` and `answerCount`, and `BreadcrumbList` trailing `ListItem` missing `item`. All three are **optional** under Google's structured-data requirements - `Question.name` plus `acceptedAnswer.text` are present and sufficient for FAQ rich results, and Google explicitly allows the final breadcrumb to omit `item`. It was therefore recorded as **low** severity rather than the medium that the standard rubric assigns to "schema validation warnings". Had it been recorded as medium it would have flipped four money pages to amber on a false premise and sent someone chasing a non-problem. The one real defect it surfaced is the empty `foundingDate` (item 4).

- **Checks deliberately not recorded as issues.** `is_https`, `canonical`, `has_html_doctype`, `has_micromarkup`, and the `seo_friendly_url*` family are all TRUE as *passes*. `no_image_title` is TRUE on all six pages but is not a defect: the `title` attribute on `<img>` is not an SEO requirement, and alt coverage is 100 percent everywhere (Lighthouse `image-alt` passes on every page). `frame` is TRUE on `/service-areas/henderson-nv/` because of an embedded map, which is expected.

- **Service-area page selection.** The url-plan has no `primary: true` service-area entry, and the primary city from `plan-input.json` is Las Vegas - but `/service-areas/las-vegas-nv/` is not in the url-plan and returns a 301 on the live site. Per the fallback rule the first area slug in plan order was used: `/service-areas/henderson-nv/`. If the Las Vegas area page is meant to exist, that is a url-plan gap worth raising with the build pipeline, not an audit finding.

- **Lighthouse 13.4.0 audit IDs.** This version reports the newer "insight" audits (`render-blocking-insight`, `image-delivery-insight`, `lcp-discovery-insight`, `network-dependency-tree-insight`, `cache-insight`) rather than the classic IDs (`render-blocking-resources`, `uses-responsive-images`). The IDs recorded in the state file are the ones the API actually returned, so next month's regression diff will line up as long as the Lighthouse version does not change underneath us. If DataForSEO upgrades Lighthouse majors, expect a burst of spurious "new issues" and "resolved issues" in the next diff.

- **Scratch-directory contamination was caught and excluded.** The `/tmp/rank-ai-audit` scratch directory was shared with an earlier prorestoration audit run from the same day. Nine leftover prorestoration response files were present and would have silently polluted the averages. Every raw file was checked by `finalUrl` before extraction and the nine were quarantined; all 18 API responses used in this audit resolve to `purocleaneastlasvegas.com`.

- **Client record status.** `clients/puroclean-east-las-vegas.json` has `status: "live"` rather than the `"active"` the pre-flight expects. `build_status` is `pushed_main` and the apex origin serves 200, so the audit proceeded.

- **Cost.** 12 Lighthouse live runs (6 desktop, 6 mobile) at $0.005, 6 instant_pages at $0.0018, plus a 4-page crawl and microdata validation at $0.0006. Total approximately **$0.08**, against the $0.30-0.50 target.
