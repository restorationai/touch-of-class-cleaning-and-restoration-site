# Onsite Audit - TDI Builders, Inc. - 2026-08-28

**Live origin audited:** https://staging.rankai-tdi-builders.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client - no comparison data
**Form factor:** desktop (Lighthouse 13.4.0, cpuSlowdownMultiplier=1, throughputKbps=10240). Mobile scores would typically run 10-20 performance points lower. These are NOT mobile-first scores.

## Environment caveat - SEO is inconclusive this run

This audit ran against the Cloudflare Pages staging preview, which returns `x-robots-tag: noindex`. The Lighthouse `is-crawlable` audit therefore fails on all 6 URLs and pins the SEO category at 69 everywhere. That is a preview-host artifact, not a site defect.

**SEO has been excluded from every verdict in this report.** It is recorded in the state file as-is. SEO status is `inconclusive - staging noindex artifact, re-audit after apex cutover`. Verdicts are computed from Performance, Accessibility, and Best Practices only.

Two related notes:

- Canonicals correctly point at the future apex (`https://tdiusa.com/...`) rather than the staging host. That is right for a pre-cutover preview and is not counted as an offsite-canonical defect. Be aware that `tdiusa.com` currently 302-redirects to `www.buildwithtdi.com` (the old Scorpion site), so those canonicals do not resolve to the new build yet.
- DataForSEO `instant_pages` reported `has_micromarkup: false`. That is a false negative. JSON-LD is present and parses on every page (Organization, WebSite, LocalBusiness), verified directly against the served HTML. No schema defect exists.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 100.0 | n/a |
| Accessibility | 90.0 | n/a |
| Best Practices | 98.7 | n/a |
| SEO (excluded) | 69.0 | n/a |

Pages by verdict: green: 4, amber: 2, red: 0, error: 0

Performance is genuinely excellent: every page scores 100, LCP sits between 766ms and 794ms, and Total Blocking Time is 0ms across the board. The work on this site is accessibility and two small asset/meta defects, not speed.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 100 | 86 | 96 | 69* | 0.79s | 0.033 | 0ms |
| `/services/` | services-hub | amber | 100 | 90 | 96 | 69* | 0.79s | 0.028 | 0ms |
| `/services/home-remodeling/` | service-landing | green | 100 | 91 | 100 | 69* | 0.78s | 0.005 | 0ms |
| `/services/new-construction/` | service-landing | green | 100 | 91 | 100 | 69* | 0.77s | 0.025 | 0ms |
| `/service-areas/roseville-ca/` | service-area | green | 100 | 91 | 100 | 69* | 0.77s | 0.011 | 0ms |
| `/contact/` | contact | green | 100 | 91 | 100 | 69* | 0.77s | 0.011 | 0ms |

\* SEO excluded from verdict - staging noindex artifact. INP is null on all pages (not produced in Lighthouse navigation mode).

## Template-level issues (fix once, lift many pages)

Every issue found is template-level, which is expected for a fresh template build and good news: there are only four real fixes here, not twenty-four.

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `link-name` | 6 | high | Footer renders `<a href="mailto:">` with no href value and no text. Suppress the anchor when `brand.email` is empty, or populate the email. |
| `color-contrast` | 6 | high | TDI Blue `#0080C4` on white measures 4.29:1, under the WCAG AA 4.5:1 floor for 10.5pt footer links. Darken the small-text variant or enlarge the text. |
| `errors-in-console` | 2 | medium | Caused solely by the `/images/services.webp` 404 below. Fixing the asset clears this. |
| `broken_resource` | 2 | medium | `/images/services.webp` is referenced on `/` and `/services/` but returns 404. Ship the asset or correct the path. |
| `is-crawlable` | 6 | environment | Staging noindex artifact. No action; resolves at apex cutover. |
| `render-blocking-insight` | 6 | low | `_astro/_slug_.4mppLAZ1.css` (8.8KB) blocks for ~60ms. Not worth acting on at Performance 100. |
| `image-delivery-insight` | 5 | low | Hero image, ~94 KiB of theoretical savings. Not worth acting on at Performance 100. |
| `network-dependency-tree-insight` | 6 | low | Diagnostic only, no score impact. |
| `agent-accessibility-tree` | 6 | low | Belongs to Lighthouse 13's new `agentic-browsing` category, which is outside this methodology's four scored categories. Recorded, not counted. |
| `low_content_rate` | 2 | low | `/` at 1150 words vs 1200 target and `/services/` at 798 vs 800. Both within measurement noise. No action. |

Note on how verdicts were computed: `color-contrast` and `link-name` are labelled high because they are real WCAG failures, but they are not what drove the amber verdicts. Those Lighthouse failures are already reflected in the Accessibility scores (86-91). Counting their severity a second time in the verdict would penalise the same defect twice, so per-URL verdicts use category scores plus on-page issue severity only.

## Money page alerts

- **`/`** (home) - verdict: amber. Accessibility 86, the lowest on the site. Three color-contrast nodes plus the empty footer `mailto:`. Also carries a 231-character meta description and the `/images/services.webp` 404.
- **`/services/`** (services-hub) - verdict: amber. Accessibility 90 and Best Practices 96. Driven by the same `/images/services.webp` 404, which logs a console error.

`/contact/` came back green, but note it carries the empty `mailto:` twice, so the footer fix matters most there for conversion.

## Regressions vs prior audit

First audit for this client. No comparison data. This run establishes the baseline at `clients/tdi-builders/onsite-audit.json`.

## Recommended next actions (priority order)

1. **(blocked externally, unblocks SEO scoring)** Complete the apex cutover to `tdiusa.com` and re-audit. Until then the SEO category cannot be measured, since the staging preview forces `is-crawlable` to fail. Cutover is currently blocked on the pending CSLB license. No SEO finding in this report should be treated as resolved or as absent - it is deferred.

2. **(money page + template, high)** Remove or populate the empty footer email link. The footer renders `<a href="mailto:" class="text-primary no-underline hover:underline">` with an empty `href` and no accessible name, failing WCAG 2.4.4 on all 6 pages and twice on `/contact/`. Root cause is `brand.email: ""` in `clients/tdi-builders/plan-input.json`, which traces to the contact email still pending from Rob Carpenter. Preferred fix: make the footer template skip the anchor entirely when `brand.email` is empty, so the defect cannot reappear on other clients with the same gap. Populating the real email fixes it too.

3. **(template, high)** Raise small-text contrast off the brand blue. `#0080C4` on `#FFFFFF` measures 4.29:1, below the 4.5:1 AA floor for text under 14pt. It affects 3 to 7 nodes per page, all in the footer address and link columns (`tel:` link, services links, `/emergency/` link). Darken the small-text token to roughly `#0067A0` (about 5.3:1) while leaving `#0080C4` for buttons and large headings, which pass at their size. This is a documented brand color from the client's TDI Branding Guidelines, so confirm the darker small-text variant with Santino before shipping. This single change should move Accessibility from 90 to the mid-90s sitewide.

4. **(money page, medium)** Ship or repath `/images/services.webp`. It is referenced in the HTML on `/` and `/services/` and returns 404, which is the only thing logging a browser console error and the only reason Best Practices sits at 96 on those two pages rather than 100.

5. **(per-page, medium)** Trim the homepage meta description from 231 characters to 160 or fewer. It currently runs about 70 characters past the SERP truncation point, so the closing "Free estimates. Call (877) 688-0866." call to action is cut off. Every other audited page is within range at 141-155.

## Notes / caveats

- The `mcp__dataforseo__on_page_lighthouse` and `mcp__dataforseo__on_page_instant_pages` tools are not present in this MCP build, which exposes only a generic `api_request`. The endpoints were called directly at `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages`, with full responses written to disk and parsed there to keep context bounded. Results are equivalent.
- Because the raw endpoint was used, `for_mobile` is in fact available. This run set `for_mobile: false` to stay consistent with prior desktop audits, but mobile-form-factor auditing is no longer blocked on an MCP update if the methodology wants to adopt it.
- `audit-urls.txt` does not exist for this client, so URLs were auto-derived from `plan/url-plan.json` (Mode B). The two service-landings are the top 2 of 12 by `priority`: `/services/home-remodeling/` (9.0) and `/services/new-construction/` (8.1).
- No `service-area` page carries `primary: true`, and the client's home city of Sacramento has no exact service-area page among the 14 (only `west-sacramento-ca`). Per the fallback rule the first area slug was used: `/service-areas/roseville-ca/`. Consider setting a `primary: true` flag so this selection is deterministic across months.
- The client record has `status: "onboarding"`, not `"active"`. The audit proceeded because the pipeline's own System 3 gate (`scripts/master_scheduler.py:290`) keys on `build_status` (`pushed_main`), and `crew-restoration-construction`, also `onboarding`, was audited under that same gate on 2026-08-26. Flagging the discrepancy between the written methodology and the scheduler so one of the two can be reconciled.
- Two on-page checks in this report (`meta_description_too_long`, `low_content_rate` against plan targets) were computed from the returned `meta` object rather than emitted as DataForSEO check flags, because the `checks` payload contains no description-length or plan-relative word-count key. They are marked `"source": "computed"` in the state file to keep provenance honest.
- All 6 URLs returned HTTP 200 and audited cleanly. No errors, no timeouts, no re-run needed.
