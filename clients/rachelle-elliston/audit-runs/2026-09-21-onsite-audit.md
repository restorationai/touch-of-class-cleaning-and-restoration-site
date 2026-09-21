# Onsite Audit - Desert Valley Contracting Inc - 2026-09-21

**Live origin audited:** https://staging.rankai-rachelle-elliston.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit

> **Staging environment caveat - read before acting on SEO.**
> This audit ran against the Cloudflare Pages preview. Cloudflare injects
> `x-robots-tag: noindex` on every `*.pages.dev` response (verified on `/`,
> `/services/`, and `/contact/`). That fails the Lighthouse `is-crawlable`
> audit and pins the SEO category at 69 on all six pages. The SEO score is
> **inconclusive - staging noindex artifact, re-audit after apex cutover**.
> SEO was excluded from every verdict in this report. Do not open SEO
> remediation tickets off this run.

> **Desktop-only scoring.** Lighthouse ran desktop only
> (`formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`).
> Mobile would typically score 10-20 performance points lower. These are not
> mobile-first numbers.

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 98.7 | n/a |
| Accessibility | 96.0 | n/a |
| Best Practices | 96.0 | n/a |
| SEO | 69.0 (inconclusive) | n/a |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 100 | 100 | 96 | 69* | 0.55s | 0.003 |
| `/services/` | services-hub | green | 97 | 95 | 96 | 69* | 1.22s | 0.003 |
| `/services/water-damage-restoration/` | service-landing | green | 99 | 95 | 96 | 69* | 1.04s | 0.004 |
| `/services/fire-damage-restoration/` | service-landing | green | 99 | 95 | 96 | 69* | 0.95s | 0.004 |
| `/service-areas/las-vegas-nv/` | service-area | green | 98 | 95 | 96 | 69* | 1.05s | 0.003 |
| `/contact/` | contact | green | 99 | 96 | 96 | 69* | 0.80s | 0.037 |

\* SEO excluded from verdict - staging noindex artifact.

TBT and INP are null for all pages: the MCP Lighthouse digest does not return
`total-blocking-time` or INP. They were left null rather than estimated.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `render-blocking-resources` | 6 | low | Every page ships 1 render-blocking script and 1 render-blocking stylesheet. This is **not** currently a Lighthouse failure (desktop perf 97-100), but it is the single biggest mobile-scoring risk. Add `defer` to the one layout script and inline the critical CSS for the hero, deferring the remainder. |

No genuine multi-page defects were found beyond the above. Two DataForSEO
signals that look like template issues were checked and dismissed as
false positives - see Notes.

## Money page alerts

- **`/`** (home) - verdict: amber. Performance is perfect (100, LCP 0.55s);
  the amber is entirely metadata. The `<title>` is 29 characters
  ("Desert Valley Contracting Inc"), one character under the 30-character
  floor, and carries no service or geo term. The meta description is 195
  characters and will truncate in the SERP around 160.

## Regressions vs prior audit

First audit for this client - no comparison data. This run becomes the
baseline for next month's regression detection.

## Recommended next actions (priority order)

1. **(money page, home)** Rewrite the homepage `<title>`. It is currently
   "Desert Valley Contracting Inc" (29 chars) with no service or city term,
   on the highest-value page on the site. Use something like
   "Restoration Services in North Las Vegas | Desert Valley Contracting"
   (67 chars, trim to land in 30-65). Every other page already follows the
   "{Service} in {City}" pattern, so the homepage is the outlier.
2. **(money page, home)** Trim the homepage meta description from 195 to
   under 160 characters. Current text repeats the full business name and the
   phone number; drop the trailing "Call (702) 633-5033." and the duplicated
   brand name to land near 155.
3. **(cutover, unblocks SEO)** Cut over the apex domain and re-audit. The
   apex `desertvalleycontracting.net` still serves the previous Duda site
   (301 to `www`, `server: nginx`). Until cutover, SEO scoring is
   unmeasurable and canonicals point at a domain that serves someone else's
   markup. This is the gating item for a real SEO verdict.
4. **(template, mobile risk)** Defer the single layout script and inline
   critical hero CSS. Harmless on desktop today, but this is what will cost
   points the moment mobile scoring is available.
5. **(per-page)** Bring `/services/` up to its planned depth. It has 640
   words against a `target_word_count` of 800 in the url-plan. It is the
   shallowest page audited and the hub that links to all nine service
   landings.

## Notes / caveats

- **Schema is present - the DataForSEO "missing schema" signal is a false
  negative.** `checks.has_micromarkup` returned `false` on all six pages.
  Verified directly against the raw HTML: every page ships exactly one
  `application/ld+json` block containing `LocalBusiness`, `Organization`,
  `WebSite`, `Service`, `FAQPage`, `BreadcrumbList`, `AggregateRating`,
  `PostalAddress`, and `GeoCoordinates` as appropriate to the archetype.
  DataForSEO's micromarkup check does not reliably detect JSON-LD. No
  missing-schema issue was recorded, and none should be ticketed.
- **Canonicals are correct - the `checks.canonical=false` signal is expected.**
  All six pages canonicalize to the future apex
  (`https://desertvalleycontracting.net/...`). Crawled on the staging host
  that reads as a cross-origin canonical, hence the false flag. This is the
  correct pre-cutover configuration. Do not "fix" it.
- **Lighthouse detail deferred.** The DataForSEO MCP wrapper returns an empty
  `result` object in full-data mode (confirmed twice, via both `path` and
  absolute `url`), so per-audit `opportunities`/`diagnostics` arrays could not
  be retrieved. Headline scores and Core Web Vitals are unaffected. Recorded
  in the state file as `lighthouse_detail: deferred`. Given scores of 96-100
  across the counted categories, there is little detail to recover this month.
- **Client record status is `onboarding`, not `active`.** The methodology
  pre-flight calls for `status == "active"`. `build_status` is `pushed_main`
  and the site is live and auditable, so the audit proceeded, matching the
  precedent already set by `flood-solutions-inc`. Flagging so the discrepancy
  is a decision, not an oversight.
- **Planning gap worth a look (out of scope for this system).** The url-plan
  has no `/service-areas/north-las-vegas-nv/` page even though North Las Vegas
  is the HQ city and the `primary: true` area in `plan-input.json`. The 14
  service-area pages cover Las Vegas, Henderson, Paradise and others, but not
  the home city. Per the selection rules this run fell back to the first area
  slug, `/service-areas/las-vegas-nv/`. Routing to whoever owns url-plan
  generation.
- `/service-areas/las-vegas-nv/` embeds a Google Maps iframe
  (`checks.frame=true`), which puts it at 1.27MB versus the ~0.81MB site norm.
  Performance still scored 98, so no action needed now; worth watching if the
  same embed lands on more area pages.
- Infrastructure checks passed: HTTPS on all pages, `robots.txt` present and
  permissive, `/sitemap-index.xml` and `/sitemap-0.xml` both 200, no broken
  links or broken resources on any page, image alt coverage 100 percent
  (34 of 34 `<img>` tags), no mixed content, no duplicate titles or
  descriptions, single `<h1>` per page.
- Estimated API spend this run: about $0.05 (6 Lighthouse live at $0.005, 7
  instant_pages at $0.0018, plus 2 discarded full-data Lighthouse attempts).
  Under the $0.30-0.50 target.
