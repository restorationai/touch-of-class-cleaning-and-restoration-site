# Onsite Audit - TDI Builders, Inc. - 2026-09-28

**Live origin audited:** https://staging.rankai-tdi-builders.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-28
**Form factor:** desktop (Lighthouse 13.4.0, `for_mobile: false`). Mobile scores would typically run 10-20 performance points lower. These are NOT mobile-first scores.

## Environment caveat - SEO is inconclusive this run

This audit ran against the Cloudflare Pages staging preview. `curl -sI` confirms it returns `x-robots-tag: noindex`, so the Lighthouse `is-crawlable` audit fails on all 6 URLs and pins SEO at 69 everywhere. That is a preview-host artifact, not a site defect.

**SEO is excluded from every verdict in this report.** It is recorded in the state file as-is. SEO status is `inconclusive - staging noindex artifact, re-audit after apex cutover`. Verdicts are computed from Performance, Accessibility, and Best Practices only.

**Production looks live, but the client record says it isn't.** `https://tdiusa.com/` and `https://www.tdiusa.com/` both return 200 and serve the new Astro build, with no `x-robots-tag`. `www.buildwithtdi.com` now 301s to `www.tdiusa.com`. The client record still has `apex_cutover: null`, so this run audited staging, as the methodology requires. Once the cutover is recorded, the next run will audit production and the SEO category can finally be scored.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.8 | -1.2 |
| Accessibility | 91.0 | +1.0 |
| Best Practices | 100.0 | +1.3 |
| SEO (excluded) | 69.0 | 0.0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

Last month's broken-asset fix worked. `/images/services.webp` no longer 404s, so Best Practices is 100 on every page. The one amber page is the homepage, and only because its meta description is too long. Performance slipped 1-2 points on every page because a Google Analytics tag (`gtag/js?id=G-HCNBG7B9HN`) was added. That cost is expected and small. TBT is still 0ms everywhere and LCP stays under 1s.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 98 | 92 | 100 | 69* | 0.96s | 0.043 | 0ms |
| `/services/` | services-hub | green | 99 | 90 | 100 | 69* | 0.96s | 0.028 | 0ms |
| `/services/home-remodeling/` | service-landing | green | 99 | 91 | 100 | 69* | 0.85s | 0.005 | 0ms |
| `/services/new-construction/` | service-landing | green | 99 | 91 | 100 | 69* | 0.88s | 0.025 | 0ms |
| `/service-areas/roseville-ca/` | service-area | green | 99 | 91 | 100 | 69* | 0.92s | 0.012 | 0ms |
| `/contact/` | contact | green | 99 | 91 | 100 | 69* | 0.91s | 0.013 | 0ms |

\* SEO is excluded from the verdict (staging noindex artifact). INP is null on all pages because Lighthouse navigation mode does not produce it.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `link-name` | 6 | high | Footer still renders `<a href="mailto:">` with no address and no text. `/contact/` also has a second empty `mailto:` in the sidebar contact card (`a.font-bold.text-white`). Root cause: `brand.email` is still `""` in `plan-input.json`. |
| `color-contrast` | 6 | high | Three separate failures: (a) small text in TDI Blue `#0080C4` on white is 4.29:1 (footer `tel:`, `/services/`, `/emergency/` links); (b) breadcrumb links using `text-dark/50` render `#8D8D8D` on white at 3.31:1, on every inner page; (c) `btn-accent` white on `#0080C4` is 4.29:1 at 14px, and the `text-slate-400` "9 Google reviews" label on `/service-areas/roseville-ca/` is 2.56:1. |
| `is-crawlable` | 6 | environment | Staging noindex artifact. No action needed; it clears when the audit moves to production. |
| `unused-javascript` | 6 | low | New this month. About 69 KiB of the 156 KiB GA4 `gtag/js` is unused. The score impact is 1-2 performance points. Not worth acting on at Performance 98-99. |
| `image-delivery-insight` | 6 | low | Hero images could shrink by 13-192 KiB (largest on `/services/` and `/contact/`). This is the next lever if Performance ever drops below 95. |
| `render-blocking-insight` | 6 | low | `_astro/_slug_.C-PcsskP.css` (8.9 KB) blocks rendering for about 40-55ms. No action needed. |
| `network-dependency-tree-insight` | 6 | low | Diagnostic only; no score impact. |
| `agent-accessibility-tree` | 6 | low | Lighthouse 13 agentic-browsing category, which is outside the four scored categories. Recorded only. |
| `lcp-discovery-insight` | 5 | low | Hero LCP image is not discoverable from the initial HTML with high fetch priority. Adding `fetchpriority="high"` to the hero `<img>` in the page-header component would satisfy this. Low priority at sub-1s LCP. |

Verdicts are computed the same way as last month. `link-name` and `color-contrast` are real WCAG failures and are labelled high, but they are already reflected in the Accessibility scores (90-92). Per-URL verdicts use category scores plus on-page issue severity, so the same defect is not counted twice.

## Money page alerts

- **`/`** (home) - verdict: amber. The only driver is a 211-character meta description (target 160 or fewer). Last month it was 231, so it was shortened but is still over the limit. All three Lighthouse categories that count are 92 or higher.

`/contact/` is green, but it still has two empty `mailto:` links. On the conversion page, that is the accessibility defect that matters most.

## Regressions vs prior audit

No thresholds were crossed. Every URL is within -2 points on every category (the regression threshold is -5), LCP rose 78-173ms (threshold 200ms), CLS changed by 0.01 or less, and TBT stayed at 0ms. The site-average performance drop of 1.2 is under the 3-point site threshold.

**Verdict transitions:**
- `/services/` went amber to green (improvement). The `/images/services.webp` 404 is fixed, so Best Practices went from 96 to 100 and the console error is gone.

**New issues this month:**
- All 6 URLs: `unused-javascript` - the new GA4 tag `gtag/js?id=G-HCNBG7B9HN` ships about 69 KiB of unused JS.
- `/`: `forced-reflow-insight` - 78ms of forced reflow, unattributed (most likely the GA script). Informational at TBT 0ms.
- `/services/`: `image-delivery-insight` - the hero image could save about 192 KiB.
- `/service-areas/roseville-ca/`: `frame` - Google Maps `<iframe>` embed. This is expected for a service-area page and is informational only.
- Inner pages: the `color-contrast` audit now also catches the breadcrumb (`text-dark/50`, 3.31:1). The audit ID was already flagged last month, but these nodes are new.

**Issues resolved since last audit:** (positive - keep doing this)
- `/` and `/services/`: `broken_resource` - `/images/services.webp` now serves.
- `/` and `/services/`: `errors-in-console` - cleared by the same asset fix.
- `/`: `low_content_rate` - the homepage grew from 1150 to 1457 words, above its 1200 target.
- `/`: Accessibility went from 86 to 92.

## Recommended next actions (priority order)

1. **(unblocks SEO scoring)** Record the apex cutover and fix the host redirect. Production is already serving on `tdiusa.com` and `www.tdiusa.com`, but `clients/tdi-builders.json` still has `apex_cutover: null`. Set `apex_cutover.completed_at` so the next audit runs against production and SEO gets scored. In the same change, add a 301 from `https://tdiusa.com/*` to `https://www.tdiusa.com/*` at Cloudflare. Right now both hosts return 200, and only the `www` canonical stops duplicate-host indexing. No SEO finding in this report should be treated as resolved. SEO is deferred.

2. **(money page + template, high)** Remove the empty `mailto:` links. They fail WCAG 2.4.4 on all 6 pages and appear twice on `/contact/` (footer plus sidebar card). Make both the footer and the contact-card components skip the email anchor when `brand.email` is empty, and chase the real address from Rob Carpenter. This was flagged last month and is unchanged.

3. **(template, high)** Fix the breadcrumb contrast. Change the breadcrumb link class from `text-dark/50` (`#8D8D8D`, 3.31:1) to a solid gray of at least `#767676` (4.54:1). `text-dark/70` or `text-slate-600` would work. This one class change clears a new failing node on every inner page.

4. **(template, high)** Add a darker small-text variant of TDI Blue. Use about `#0067A0` (about 5.3:1) for footer links and 14px `btn-accent` text, and keep `#0080C4` for large headings and large buttons. This was carried over from last month and is still waiting on Santino to confirm the brand color. In the same pass, change the Roseville review-count label from `text-slate-400` (2.56:1) to `text-slate-600`.

5. **(money page, medium)** Cut the homepage meta description from 211 to 160 characters or fewer. It is the only reason the homepage is amber. Put the phone number CTA before the cut-off point, or drop it.

## Notes / caveats

- `audit-urls.txt` does not exist, so URLs were derived from `plan/url-plan.json` (Mode B). This is the same 6-URL set as 2026-08-28, so every URL has a comparison. Service-landings are the top 2 by `priority` (`/services/home-remodeling/` 9.0, `/services/new-construction/` 8.1; `/services/kitchen-remodeling/` ties at 8.1 and lost on plan order). No service-area has `primary: true`, and Sacramento has no exact area page, so the first area slug (`/service-areas/roseville-ca/`) was used again.
- Staging canonicals now point to `https://www.tdiusa.com/...`. Last month they pointed to `https://tdiusa.com/...`. DataForSEO flags them as off-origin, which is expected on staging and not counted as a defect. They match the host that production actually canonicalizes to.
- DataForSEO `instant_pages` again reported `has_micromarkup: false`. That is a false negative. JSON-LD parses on every page checked: Organization, WebSite, and LocalBusiness everywhere, plus FAQPage and BreadcrumbList on `/services/` and `/contact/`.
- `/services/` is at 705 words against an 800-word plan target (`low_content_rate`, low). Last month it was 798. This is content scope for System 4, noted here only because it moved.
- The client record `status` is still `"onboarding"`, not `"active"`. The audit proceeded because the scheduler's System 3 gate keys on `build_status: pushed_main`, as it did last month.
- The DataForSEO MCP build exposes only the generic `api_request`, so `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` were called directly. Full responses were written to disk and parsed there. Cost: about $0.04 for 12 calls.
- All 6 URLs returned HTTP 200 and audited cleanly. There were no errors and no re-run is needed.
