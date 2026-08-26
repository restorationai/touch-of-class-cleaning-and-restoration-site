# Onsite Audit - Crew Restoration & Construction - 2026-08-26

**Live origin audited:** https://crew3r.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client - no comparison data
**Form factor:** desktop only (see Notes)

> **Read the amber correctly.** Every counted Lighthouse category is at or near
> 100 across all six pages, no page has a high-severity on-page issue, and no page
> errored. Five of six pages are amber for exactly one reason: a single missing
> property in the BreadcrumbList JSON-LD emitted by the shared layout. Fix that one
> template and five of the six pages go green on the next run. This is a healthy
> site with one narrow defect, not a site in trouble.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.8 | n/a |
| Accessibility | 96.3 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 100.0 | n/a |

Pages by verdict: green: 1, amber: 5, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 100 | 100 | 100 | 100 | 0.58s | 0.006 | 0ms |
| `/services/` | services-hub | amber | 99 | 95 | 100 | 100 | 0.85s | 0.002 | 0ms |
| `/services/water-damage-restoration/` | service-landing | amber | 100 | 96 | 100 | 100 | 0.81s | 0.003 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | amber | 100 | 96 | 100 | 100 | 0.80s | 0.003 | 0ms |
| `/service-areas/brookings-sd/` | service-area | amber | 100 | 95 | 100 | 100 | 0.56s | 0.003 | 0ms |
| `/contact/` | contact | amber | 100 | 96 | 100 | 100 | 0.49s | 0.005 | 0ms |

Core Web Vitals are comfortably inside the "good" thresholds on every page on
desktop: LCP well under 2.5s, CLS effectively zero, TBT zero everywhere. INP was
not reported by Lighthouse (it needs field data or a simulated interaction) and is
recorded as null rather than guessed.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is a 640x640 PNG (78.9 KB) rendered at 64x64 in the header on every page. Export a 128x128 WebP and swap the header `<img>` to it. Roughly 78 KB of the 120-140 KB flagged per page is this one file. |
| `network-dependency-tree-insight` | 6 | high | Critical chain is document to `/_astro/_slug_.ZcyYff39.css` (8.8 KB), 146-201ms. Inline the above-the-fold rules and load the rest with `media="print" onload="this.media='all'"`. Low absolute payoff here since the chain is already short. |
| `cache-insight` | 6 | medium | The only flagged asset is Cloudflare's own `/cdn-cgi/scripts/.../email-decode.min.js` at a 2-day TTL. Not editable by us. Turn off Email Address Obfuscation in the Cloudflare dashboard if you want it gone, otherwise ignore. |
| `color-contrast` | 5 | high | Breadcrumb links use `text-dark/50` (50% opacity) and fail WCAG AA against the page background. `.btn-accent` on the `tel:+18444917560` CTA and `text-slate-400` on the service-area template fail too. Raise breadcrumbs to `text-dark/70` or darker and darken the `.btn-accent` background. |
| `lcp-discovery-insight` | 5 | high | Every non-home template renders the hero as a bare `<img src="/images/hero-bg.webp" loading="eager">` with no `fetchpriority="high"` and no `srcset`. The homepage template already does it right and is the only page scoring 1 on this audit. Copy the homepage hero markup into the other templates. |
| `has_micromarkup_errors` | 5 | medium | The terminal `BreadcrumbList` `ListItem` has `name` and `position` but no `item`. Add the self URL to the last item in the breadcrumb component. |
| `low_content_rate` | 2 | low | Text-to-HTML ratio flagged on `/` and `/services/`. Both pages exceed their word-count targets (1360 vs 1200, 804 vs 800), so this is markup weight, not thin content. No action needed. |

## Money page alerts

- **`/services/`** - verdict: amber. Accessibility 95, BreadcrumbList schema validation error. The breadcrumb `<a href="/">` uses `text-dark/50` and fails contrast. Performance 99, LCP 0.85s (highest of the six, hero has no `fetchpriority`).
- **`/services/water-damage-restoration/`** - verdict: amber. Accessibility 96, BreadcrumbList schema validation error. Three failing contrast nodes: the two breadcrumb links plus the `tel:` button using `.btn-accent`.
- **`/services/fire-damage-restoration/`** - verdict: amber. Accessibility 96, BreadcrumbList schema validation error. Same three contrast nodes as the water page, confirming these are layout-level and not page-level.
- **`/contact/`** - verdict: amber. Accessibility 96, BreadcrumbList schema validation error. Conversion path itself is clean: HTTP 200, canonical correct, no broken links, LCP 0.49s. One extra note, the logo on this page is `loading="lazy"` at 640x640 for an 80x80 slot, 77.8 KB wasted.

`/` is green and `/service-areas/brookings-sd/` is amber but is not a money archetype.

## Regressions vs prior audit

First audit for this client. No prior `clients/crew-restoration-construction/onsite-audit.json` existed, so regression detection was skipped. This run becomes the baseline for the September comparison.

## Recommended next actions (priority order)

1. **(money page + template, high impact)** Add the `item` property to the final
   `ListItem` in the BreadcrumbList JSON-LD emitted by the shared breadcrumb
   component. Today the last crumb is
   `{"@type":"ListItem","position":3,"name":"Water Damage Restoration"}` with no
   `item`. Set it to the page's own canonical URL. This is the sole cause of the
   amber verdict on all four money pages and on the service-area page, and it
   propagates across all 280 built pages.
2. **(money page + template, high impact)** Give the hero image
   `fetchpriority="high"` and a `srcset`/`sizes` pair in the services-hub,
   service-landing, service-area and contact templates. The homepage template
   already emits
   `<img src="/images/hero-bg.webp" srcset="...480w, ...768w" sizes="100vw" loading="eager" fetchpriority="high">`
   and is the only page passing `lcp-discovery-insight`. The other five emit a bare
   `<img ... loading="eager">`. Copy the homepage pattern.
3. **(template, high impact)** Replace the header logo. `/images/logo.png` is a
   640x640 PNG weighing 78.9 KB and is displayed at 64x64 (80x80 on `/contact/`).
   Export a 128x128 WebP, which should land near 3-5 KB, and update the header
   partial. That is about 78 KB removed from every page load site-wide, the single
   largest byte win available.
4. **(template, accessibility)** Fix the three failing contrast styles in the
   layout: breadcrumb links `text-dark/50` to `text-dark/70` or darker, the
   `.btn-accent` background used by the `tel:+18444917560` CTA, and
   `text-slate-400` on the service-area template. This is worth 4-5 accessibility
   points on five pages and is the only thing keeping accessibility off 100.
5. **(template, schema hygiene)** Clean two defects in the `LocalBusiness` block
   that ships on all six pages. `image` and `logo` are relative
   (`/images/logo.png`) where schema.org expects absolute URLs, and
   `foundingDate` is an empty string. Set the URLs to
   `https://crew3r.com/images/logo.png` and either populate `foundingDate` with
   `1974` (the homepage already says "Our Story - Since 1974") or drop the key.
   DataForSEO does not currently flag these, but empty and relative values are
   real defects that Google's Rich Results test will pick up.

## Notes / caveats

- **Origin.** Audited the apex production domain. The client record has no
  `apex_cutover.completed_at` key, but it carries `cut_over_at 2026-08-08` with the
  note "crew3r.com live 08-08". The apex returned HTTP 200 on all six URLs and
  carries no `x-robots-tag: noindex`, while the staging Pages preview does. Apex is
  therefore the correct origin and the staging SEO-exclusion correction does not
  apply. All four categories counted toward the verdicts.
- **Form factor.** Lighthouse ran desktop only (`formFactor=desktop`,
  `cpuSlowdownMultiplier=1`, `throughputKbps=10240`, `rttMs=40`). The DataForSEO MCP
  wrapper does not expose a mobile form factor. Mobile performance would typically
  land 10-20 points lower, and the 640x640 logo and non-prioritized hero would both
  hurt more there than they do here. Do not quote these as mobile scores.
- **Client record status.** `clients/crew-restoration-construction.json` still says
  `status: "onboarding"` while `build_status` is `pushed_main` and the apex has been
  live since 2026-08-08. The audit proceeded because the site is demonstrably live
  and auditable, but the status field looks stale and should be corrected to
  `active`.
- **Tooling.** The `on_page_lighthouse` and `on_page_instant_pages` MCP tools are
  not exposed by this DataForSEO MCP build. Used authenticated REST calls to
  `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages`, piped to disk
  and parsed. Equivalent data, same cost basis. Total spend for this run was about
  $0.08.
- **Schema error attribution.** DataForSEO reports `has_micromarkup_errors: true`
  on the five pages carrying BreadcrumbList plus FAQPage and `false` on the
  homepage, which carries neither. The vendor does not return the error text on the
  `instant_pages` endpoint; the microdata endpoint needs a full crawl task, which
  is out of scope for a six-URL run. Manual inspection of the rendered JSON-LD shows
  every block parses cleanly, and the only structural defect unique to those five
  pages is the terminal ListItem with no `item`. That is the basis for
  recommendation 1. If the September audit still flags it after the fix, escalate to
  a full `on_page` crawl task to get the vendor's error text.
- **`frame` false positive.** DataForSEO's `frame` check fires on
  `/service-areas/brookings-sd/`. That page contains one `<iframe>` (a map embed)
  and zero `<frame>`/`<frameset>` elements. Not reported as an issue.
- **Not double-counted.** DataForSEO `has_render_blocking_resources` and
  `high_loading_time` fired on several URLs. They are not in the on-page check list
  for this skill and the same ground is covered by Lighthouse
  `render-blocking-insight` and the LCP audits, so they were not recorded twice.
- **Clean bill on the basics.** Across all six URLs: HTTP 200, correct
  self-referencing canonicals, exactly one H1 each, titles 41-46 chars, meta
  descriptions 110-151 chars, no duplicate titles or descriptions, no broken
  internal or external links, no broken resources, no mixed content, full image alt
  coverage (Lighthouse `image-alt` passed everywhere), and every page above its
  `target_word_count`.
- **URL selection.** Derived from `plan/url-plan.json` (no `audit-urls.txt`
  present). No `service-area` entry in the plan has `primary: true`, and the plan
  contains no Sioux Falls area page to match the business city, so the first
  `service-area` in plan order was used: `/service-areas/brookings-sd/`. The two
  service landings are the joint-highest priority 9.0 entries in plan order,
  water damage and fire damage.
