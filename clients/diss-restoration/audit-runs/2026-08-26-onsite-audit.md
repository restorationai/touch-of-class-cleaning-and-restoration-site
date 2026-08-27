# Onsite Audit - DISS Restoration - 2026-08-26

**Live origin audited:** https://staging.rankai-diss-restoration.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client, no comparison data
**Form factor:** desktop only (Lighthouse 13.4.0, `for_mobile=false`)

> **Staging environment caveat, read before acting on SEO.**
> The apex `dissrestoration.com` still 301s to the old Wix site (`server: Pepyaka`), so this audit ran against the Cloudflare Pages preview. Pages injects `x-robots-tag: noindex` on every `*.pages.dev` response, which fails the Lighthouse `is-crawlable` audit and pins the SEO category to **69 on all 6 URLs**. That is an environment artifact, not a site defect. **SEO is recorded below but excluded from every verdict in this report.** SEO status for this client is inconclusive until the apex cutover. Do not open "fix SEO" work off this run.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 93.2 | n/a |
| Accessibility | 96.0 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 69.0 (inconclusive) | n/a |

Pages by verdict: green: 3, amber: 3, red: 0, error: 0

Verdict basis: performance, accessibility, best practices. SEO excluded (staging noindex artifact).

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 88 | 100 | 100 | 69 | 1.6s | 0.153 |
| `/services/` | services-hub | green | 92 | 95 | 100 | 69 | 1.9s | 0.003 |
| `/services/water-damage-restoration/` | service-landing | amber | 93 | 95 | 100 | 69 | 1.8s | 0.004 |
| `/services/fire-damage-restoration/` | service-landing | amber | 93 | 95 | 100 | 69 | 1.7s | 0.004 |
| `/service-areas/warren-oh/` | service-area | green | 93 | 95 | 100 | 69 | 1.8s | 0.003 |
| `/contact/` | contact | green | 100 | 96 | 100 | 69 | 0.8s | 0.024 |

Total blocking time was 0 ms on all six pages. INP was not reported by this Lighthouse run (lab mode, no interaction trace) and is recorded as null rather than estimated.

On-page hygiene came back clean across all six: no broken internal or external links, no broken resources, no duplicate titles or descriptions, no duplicate content, no mixed content, 100 percent image alt coverage, exactly one H1 per page, and a self-consistent canonical on every URL. Titles run 53 to 57 characters and meta descriptions 120 to 176 characters, all inside target. DataForSEO on-page scores were 90.39 to 97.44.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is a 1200x1078 PNG weighing 1,423,236 bytes, rendered at 71x64 in the header and 89x80 in the footer. Re-export as WebP at 240x216 and swap the tag. |
| `render-blocking-insight` | 6 | medium | `/_astro/_slug_.Bzo-rkx6.css` (8.8 KB) blocks first paint for about 50 ms on every page. Inline the above-the-fold rules and defer the rest. |
| `color-contrast` | 5 | medium | Breadcrumb links `nav.container-wide > ol.flex > li.flex > a.text-dark/50` render #888c93 on #ffffff at 12px, a 3.37:1 ratio against the 4.5:1 requirement. |
| `lcp-discovery-insight` | 5 | medium | The hero `<img src="/images/hero-bg.webp">` on the non-home layout has no `fetchpriority="high"`. The homepage hero has it; nothing else does. |
| `largest-contentful-paint` | 4 | medium | LCP of 1.7 to 1.9 s scores 0.67 to 0.75. Fixing the logo and the priority hint above addresses both causes. |
| `high_loading_time` | 3 | medium | DataForSEO's crawler recorded `dom_complete` of 3.4 s on `/`, 4.2 s on `/services/water-damage-restoration/` and 5.1 s on `/services/fire-damage-restoration/`. Same root cause: the 1.39 MB logo. |
| `is-crawlable` | 6 | info | Staging noindex artifact. No action. Resolves on apex cutover. |

## Money page alerts

- **`/`** (home) - verdict amber. Performance 88, and CLS 0.153 is past the 0.1 "poor" boundary. Lighthouse attributes 0.1527 of that shift to `header.relative > div.container-wide`, the H1 and intro paragraph block, reflowing when the Inter woff2 arrives from `fonts.gstatic.com`. Accessibility is a clean 100 here because the homepage has no breadcrumb nav.
- **`/services/water-damage-restoration/`** (service-landing) - verdict amber. Lighthouse scores are fine at 93/95/100, but DataForSEO's crawl recorded `dom_complete` of 4,226 ms. This is the highest-priority service page in the url-plan (priority 9.0).
- **`/services/fire-damage-restoration/`** (service-landing) - verdict amber. Same profile, `dom_complete` 5,051 ms, the slowest page in the set. Also priority 9.0.

`/contact/` is the healthiest page audited: performance 100, LCP 0.8 s, and it is not on this list.

## Regressions vs prior audit

First audit for this client. No comparison data. This run becomes the baseline for next month.

## Recommended next actions (priority order)

1. **(template, high impact)** Replace `/images/logo.png`. It is 1,423,236 bytes of a 1200x1078 PNG that never renders larger than 89x80. It is the single largest asset on all six audited pages, accounting for roughly 1.39 MB of each page's 1.6 to 1.9 MB total weight, and it is the entire source of the 1,389 to 1,542 KiB image-delivery savings Lighthouse reports. Export WebP at 240x216 (2x the largest CSS box), keep a sub-20 KB PNG fallback, and leave the existing `width`/`height` attributes in place. This one change should lift performance on every page and clear the `high_loading_time` flag on the three slow pages.
2. **(money page)** Kill the 0.153 CLS on the homepage. The hero text container reflows when Inter loads via `media="print" onload="this.media='all'"` with `display=swap`. Add an `@font-face` fallback declaration with `size-adjust` and `ascent-override` metric-matched to Inter so the swap is dimensionally neutral, or set an explicit `min-height` on `header.relative > div.container-wide`. Homepage CLS is the only Core Web Vital in the whole set that is outside its "good" threshold.
3. **(template)** Add `fetchpriority="high"` to the hero image in the non-home layout. `/services/`, both service landings, `/service-areas/warren-oh/` and `/contact/` all render `<img src="/images/hero-bg.webp" ... loading="eager">` with no priority hint, which is exactly why `lcp-discovery-insight` fails on 5 of 6 pages while the homepage passes it. One attribute in the shared hero component.
4. **(template, accessibility)** Darken the breadcrumb links. `text-dark/50` resolves to #888c93 on white at 12px, 3.37:1 where WCAG AA needs 4.5:1. Move to roughly `text-dark/70` or darker. This is the only accessibility failure on the site and it costs 5 points on every page that has breadcrumbs.
5. **(money page)** Add FAQPage JSON-LD to the homepage. It renders a full "Frequently Asked Questions" section but ships only Organization, WebSite and LocalBusiness. `/services/`, `/contact/`, both service landings and `/service-areas/warren-oh/` all already emit FAQPage, so the component exists and just is not wired into the home template.

## Notes / caveats

- **Apex cutover is the gating item.** `apex_cutover.completed_at` is unset, `dissrestoration.com` still resolves to Wix, and `cutover_prep` was harvested on 2026-08-16 with 3 redirects mapped. Until cutover, SEO findings for this client are deferred, not resolved. Re-audit after cutover to get a real SEO number.
- **Schema is present. DataForSEO says otherwise and is wrong.** The on-page API returned `has_micromarkup: false` on all 6 URLs. Verified against the served HTML: home ships Organization, WebSite and LocalBusiness; `/services/` and `/contact/` ship Organization, WebSite, LocalBusiness, FAQPage and BreadcrumbList; the service landings ship Service, LocalBusiness, FAQPage and BreadcrumbList; `/service-areas/warren-oh/` ships LocalBusiness, FAQPage and BreadcrumbList. All parse cleanly. Treated as a vendor false negative and not reported as an issue.
- **Canonicals point at the apex on purpose.** Every audited page canonicalises to `https://dissrestoration.com/...` rather than the staging host. That is the intended production canonical and is not counted as a defect here.
- **Desktop only.** The DataForSEO Lighthouse run used `for_mobile=false` to stay comparable with the rest of the fleet. Mobile scores typically land 10 to 20 performance points lower, and the 1.39 MB logo would hurt considerably more on a throttled mobile connection. Do not quote these numbers as mobile scores.
- **Two measurement environments disagree on load time and both are recorded.** Lighthouse LCP came in at 1.6 to 1.9 s while DataForSEO's crawler saw `dom_complete` of 3.4 to 5.1 s on three pages. Different network conditions, same root cause. Neither number was adjusted.
- `/services/` has 692 words against a url-plan `target_word_count` of 800. Low severity, flagged for System 4 rather than actioned here. Every other page exceeds its target: home 1,272 of 1,200, water damage 1,948 of 1,100, fire damage 1,703 of 1,100, Warren 1,329 of 900, contact 654 of 400.
- The Google Maps embed on `/service-areas/warren-oh/` is `loading="lazy"` and did not affect any metric.
- Client record `status` is `onboarding`, not `active`. `build_status` is `pushed_main` and all 6 URLs returned HTTP 200, so the run proceeded rather than skipping. Flagged for visibility.
- URLs were auto-derived from `plan/url-plan.json`; no `audit-urls.txt` exists for this client. The two service landings are the joint-highest priority entries (9.0). No `service-area` page carries `primary: true` and the business city (Farrell, PA) has no area page, so the first area slug in the plan, `warren-oh`, was used per the fallback rule.
- Run cost: $0.0606 across 12 API calls (6 Lighthouse, 6 instant_pages), against a $0.30 to $0.50 target.
