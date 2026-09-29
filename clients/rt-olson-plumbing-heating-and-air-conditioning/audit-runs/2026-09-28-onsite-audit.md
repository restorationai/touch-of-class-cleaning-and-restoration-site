# Onsite Audit - RT Olson Plumbing, Heating and Air Conditioning - 2026-09-28

**Live origin audited:** https://rtolsonplumbing.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit
**Form factor:** desktop (the DataForSEO Lighthouse wrapper runs desktop only; expect mobile performance to score 10-20 points lower)

First audit for this client, so there is no comparison data.

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 93.3 | n/a |
| Accessibility | 96.0 | n/a |
| Best Practices | 96.0 | n/a |
| SEO | 100.0 | n/a |

Pages by verdict: {green: 0, amber: 6, red: 0, error: 0}

The site is healthy overall. No URL scored below 89 in any category. There are no broken links, no mixed content, canonicals are all self-referencing, and every page has exactly one H1. Every page is amber rather than green because of a few small, fixable template issues, not because of any serious problem.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 89 | 100 | 96 | 100 | 1.3s | 0.012 | 226ms |
| /services/ | services-hub | amber | 96 | 95 | 96 | 100 | 1.4s | 0.024 | 28ms |
| /services/emergency-plumbing/ | service-landing | amber | 95 | 95 | 96 | 100 | 1.5s | 0.002 | 0ms |
| /services/drain-cleaning/ | service-landing | amber | 94 | 95 | 96 | 100 | 1.5s | 0.011 | 100ms |
| /service-areas/riverside-ca/ | service-area | amber | 96 | 95 | 96 | 100 | 1.4s | 0.004 | 88ms |
| /contact/ | contact | amber | 90 | 96 | 96 | 100 | 1.5s | 0.004 | 182ms |

INP: not reported by lab Lighthouse (null on all URLs).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is 521 KB and renders as a small header logo. Export it as WebP/SVG at display size (under 20 KB). On inner pages, `/images/hero-bg.webp` (162 KB) also wastes 70-98 KB; serve the srcset width that matches the rendered size. |
| `unused-javascript` | 6 | high | GTM loads 5 Google tag containers (GTM-PKJQHGRF, G-D2RXDRWJ8D, G-C9KFMJP114, AW-403585518, AW-661924638), wasting about 345 KB of JS on every page. Merge the two GA4 properties into one, move the AW tags inside GTM-PKJQHGRF instead of loading them separately, and delete tags from the old site that are no longer needed. |
| `errors-in-console` | 6 | medium | A Custom HTML tag in GTM-PKJQHGRF calls `jQuery`, but the new Astro site does not load jQuery (`ReferenceError: jQuery is not defined`). Rewrite that tag in plain JS or remove it. It is left over from the legacy site, and whatever it tracked is currently broken. |
| `color-contrast` | 5 | medium | Breadcrumb links (`nav.container-wide > ol > li > a.text-dark/50`) render #888c93 on white, a contrast ratio of 3.37:1. Change the class to `text-dark/70` or darker to reach 4.5:1. |
| `lcp-discovery-insight` | 5 | medium | The inner-page hero `<img src="/images/hero-bg.webp">` is the LCP element but does not have `fetchpriority="high"`. The home page hero already has it; add the same attribute to the inner-page hero component. |
| `has_micromarkup_errors` | 5 | medium | Only pages with the BreadcrumbList + FAQPage JSON-LD fail validation (the home page has neither and passes). The most likely cause is the last BreadcrumbList `ListItem`, which has no `item` URL. Add the page's canonical URL as `item`. Also make `LocalBusiness.image` and `logo` absolute URLs (they are currently `/images/logo.png`). Confirm with Google's Rich Results Test. |
| `title_too_short` | 2 | medium | Service-landing titles are under 30 chars (emergency-plumbing 28, drain-cleaning 24). The planned titles include "\| RT Olson ..." and a city, but the rendered titles drop them. Check the service-landing title template. |
| `total-blocking-time` | 2 | high | Home (226ms) and contact (182ms). Almost all of it comes from the GTM/gtag/Facebook Pixel scripts. The tag consolidation above is the fix. |

## Money page alerts

- **`/`** (home): amber. Performance 89, TBT 226ms. Main causes are third-party tag JS and the 521 KB logo. The meta description is 202 chars (target 70-160), so Google will cut it off in search results.
- **`/services/`**: amber. Structured data validation errors. Word count 784 is just under the 800 target.
- **`/services/emergency-plumbing/`**: amber. Structured data errors, and the title is 28 chars.
- **`/services/drain-cleaning/`**: amber. Structured data errors, and the title is 24 chars.
- **`/contact/`**: amber. Performance 90, TBT 182ms from tag scripts. Structured data errors.

## Regressions vs prior audit

First audit for this client, so there is no comparison data.

## Recommended next actions (priority order)

1. **(money page + template, high impact)** Consolidate tags in GTM-PKJQHGRF. Merge the two GA4 IDs into one, load both Google Ads conversion tags through the single GTM container, and remove the jQuery-dependent Custom HTML tag or rewrite it in plain JS. This fixes `unused-javascript`, `errors-in-console`, and most of the TBT on home and contact.
2. **(template, high impact)** Replace `/images/logo.png` (521 KB) with a WebP or SVG logo sized for display. This saves about 510 KB on every page on the site.
3. **(money page + template)** Fix the BreadcrumbList JSON-LD (add `item` to the final ListItem) and make the `LocalBusiness` image/logo URLs absolute. Then check `/services/drain-cleaning/` in the Rich Results Test.
4. **(money page)** Fix the service-landing title template so it renders the planned format ("Drain Cleaning in Corona | RT Olson Plumbing, Heating and Air Conditioning", or similar, 30-65 chars). Shorten the home meta description from 202 to 160 chars or fewer.
5. **(template)** Add `fetchpriority="high"` to the inner-page hero image, and change the breadcrumb link color from `text-dark/50` to `text-dark/70`.

## Notes / caveats

- The apex has been live since the 2026-09-08 cutover, so SEO counts toward the verdict. The noindex header is not present.
- Lighthouse runs are desktop-only. Scores vary from run to run: an earlier headline-only run on the home page scored performance 96 and TBT 65ms, compared with 89 and 226ms in the full-data run recorded here. Home is close to the 90 threshold, and the tag cleanup should move it clearly into green.
- The only image missing alt text on every page is the Facebook Pixel `<noscript>` 1x1 tracking image, so it was not flagged. Content-image alt coverage is 100%.
- `has_micromarkup_errors` is a DataForSEO boolean check and does not include per-error detail. The breadcrumb diagnosis above is inferred from the difference between passing and failing pages. Verify it before closing the ticket.
- URL selection: Mode B (url-plan). No `service-area` entry is marked `primary`, and there is no Corona area page (Corona is the home city), so the first area in the plan (`/service-areas/riverside-ca/`) was used.
- Issue IDs prefixed `rankai_` in the state file are Rank AI methodology checks with no native DataForSEO check ID.
- API cost this run: about $0.035 (6 Lighthouse full-data + 6 instant_pages + 1 headline Lighthouse).
