# Onsite Audit - RT Olson Plumbing, Heating and Air Conditioning - 2026-09-28

**Live origin audited:** https://rtolsonplumbing.com (apex, cut over 2026-09-08)
**Site verdict:** amber
**URLs audited:** 6 (auto-derived from `plan/url-plan.json`)
**Prior audit:** first audit. No comparison data.
**Form factor:** DESKTOP only (Lighthouse 13.4.0 via DataForSEO). Mobile performance is typically 10-20 points lower; do not read these as mobile scores.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 91.7 | n/a |
| Accessibility | 96.0 | n/a |
| Best Practices | 96.0 | n/a |
| SEO | 100.0 | n/a |

Pages by verdict: {green: 2, amber: 4, red: 0, error: 0}

No high-severity on-page issues: no broken links, no mixed content, canonicals self-reference correctly on all 6 pages, and valid JSON-LD is present on every page (LocalBusiness, Service, FAQPage, BreadcrumbList, AggregateRating).

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | amber | 88 | 100 | 96 | 100 | 1.3s | 0.012 | 241ms |
| /services/ | services-hub | green | 93 | 95 | 96 | 100 | 1.2s | 0.025 | 174ms |
| /services/emergency-plumbing/ | service-landing | amber | 95 | 95 | 96 | 100 | 1.3s | 0.003 | 124ms |
| /services/drain-cleaning/ | service-landing | amber | 94 | 95 | 96 | 100 | 1.6s | 0.002 | 39ms |
| /service-areas/riverside-ca/ | service-area | amber | 85 | 95 | 96 | 100 | 1.5s | 0.002 | 255ms |
| /contact/ | contact | green | 95 | 96 | 96 | 100 | 1.5s | 0.004 | 46ms |

INP: not reported by lab Lighthouse (null on all pages).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `unused-javascript` | 6 | high | About 425 KiB of unused JS on every page, all third-party tracking: two GA4 properties (`G-D2RXDRWJ8D`, `G-C9KFMJP114`), two Google Ads tags (`AW-403585518`, `AW-661924638`), GTM container `GTM-PKJQHGRF`, and the Meta Pixel. Each gtag library is 150-190 KB. Pick one GA4 property and one Ads account, fire both through the GTM container only, and remove the hard-coded duplicate `gtag/js` loaders from the layout. |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is a 720x864 PNG weighing 522 KB, shown at about 64px tall in the header and footer. Export a 128px-tall WebP/AVIF (target under 10 KB) and update the header and footer `<img>` tags. This one file is 509-712 KiB of the flagged savings on every page. Also fix the `width`/`height` attributes (64x64 and 48x48) so they match the real 5:6 aspect ratio. |
| `errors-in-console` | 6 | medium | `ReferenceError: jQuery is not defined`, thrown by a Custom HTML tag inside `GTM-PKJQHGRF`. The Astro site does not load jQuery. In GTM, find the tag that calls `jQuery(...)` / `$(...)` (probably a legacy form or click tracker from the old site), then rewrite it in vanilla JS or pause it. Check whether it was a conversion tag, because if so it is not firing now. |
| `has_render_blocking_resources` | 6 | low | One 9 KB stylesheet (`/_astro/_slug_.*.css`) blocks render; Lighthouse estimates only 0-50ms of savings. Low priority. Leave it unless you are already editing the layout. |
| `color-contrast` | 5 | medium | The breadcrumb links use `text-dark/50`, which renders as #888c93 on white at 12px (ratio under 4.5:1). Change it to `text-dark/70` (or `text-slate-600`) in the breadcrumb component. On `/service-areas/*` there is also a `text-slate-400` span (#94a3b8) that needs `text-slate-600`. |
| `lcp-discovery-insight` | 5 | medium | On every non-home page the LCP element is the hero `<img src="/images/hero-bg.webp">`, and it has no `fetchpriority="high"` and no `srcset`. Copy the home hero markup, which already has `fetchpriority="high"` plus the 480w/768w/... srcset, into the shared page-hero component. |
| `low_content_rate` | 3 | low | Low text-to-HTML ratio, mostly caused by inline Tailwind classes and JSON-LD. Informational only; the word counts are healthy. |
| `high_loading_time` | 3 | low | DataForSEO's crawler measured 3.9-4.5s total load on the landing and contact pages, but Lighthouse LCP is 1.3-1.6s. The difference is the third-party tag load, which the `unused-javascript` fix addresses. |
| `title_too_short` | 2 | medium | See the money page alerts. The layout drops the brand suffix from the planned titles. |

## Money page alerts

- **`/`** (home). Verdict: amber. Performance 88, TBT 241ms, and the meta description is 202 chars, so Google will truncate it mid-sentence. The TBT comes from the tracking scripts above (the gtag and fbevents bootup is about 350ms of main-thread time) plus 179ms of forced reflow.
- **`/services/emergency-plumbing/`**. Verdict: amber. The live `<title>` is "Emergency Plumbing in Corona" (28 chars). The url-plan title is "Emergency Plumbing in Corona | RT Olson Plumbing, Heating and Air Conditioning" (79 chars), and the layout appears to drop the suffix because it goes over the length cap.
- **`/services/drain-cleaning/`**. Verdict: amber. Same cause: the live title is "Drain Cleaning in Corona" (24 chars) and the brand suffix is missing.

`/contact/` and `/services/` are green.

## Regressions vs prior audit

First audit for this client. No comparison data. This run is the baseline for next month.

## Recommended next actions (priority order)

1. **(money page, template)** Change the title template so it appends a short brand suffix, ` | RT Olson Plumbing` (20 chars), when the full legal name would push the title over 65 chars. Result: "Emergency Plumbing in Corona | RT Olson Plumbing" (48 chars) and "Drain Cleaning in Corona | RT Olson Plumbing" (44 chars). This clears `title_too_short` on both landings and also applies to the other 10 service landings.
2. **(money page)** Rewrite the home meta description in `url-plan.json` and the rendered page to 160 chars or less. Suggested: "24/7 emergency plumbing, heating and air conditioning in Corona and nearby cities. Licensed and insured. Call RT Olson at (951) 344-5596." (137 chars).
3. **(template, high impact)** Replace `/images/logo.png` (522 KB) with a roughly 128px-tall WebP under 10 KB, and correct its width/height attributes. This saves about 510 KB on every page on the site.
4. **(template, high impact)** Consolidate tracking. Remove the duplicate GA4 property and the unused Google Ads tag (confirm with the client which `G-` and `AW-` IDs are live), load everything through GTM only, and fix or pause the GTM Custom HTML tag that throws `jQuery is not defined`. This cuts about 425 KiB of JS, lowers TBT on home (241ms) and Riverside (255ms), and clears `errors-in-console` sitewide.
5. **(template)** Add `fetchpriority="high"` and the responsive `srcset` to the shared inner-page hero image, and darken the breadcrumb link color from `text-dark/50` to `text-dark/70`. Together these clear `lcp-discovery-insight` and `color-contrast` on 5 of 6 pages.

## Notes / caveats

- **Desktop only.** The DataForSEO Lighthouse endpoint ran `formFactor=desktop`. The Riverside page (85) and home (88) would probably fall below 80 on mobile, which makes items 3 and 4 more urgent than the desktop numbers suggest.
- **Service-area slot:** no url-plan entry has `primary: true`, and there is no Corona (HQ city) page under `/service-areas/`, so the audit fell back to the first area slug, `/service-areas/riverside-ca/`.
- **Rank AI rubric checks:** `rankai_description_length` and `rankai_low_word_count` are Rank AI checks (DataForSEO has no native ID for them), computed from DataForSEO instant_pages meta fields. `/services/` has 784 words against an 800 target (low severity).
- **Schema:** DataForSEO returned `has_micromarkup=false` on every page, but a direct HTML fetch confirms parseable JSON-LD on all 6 pages. This is a detection gap in DataForSEO, not a site issue.
- **Alt text:** 100% coverage on content images. The only alt-less `<img>` is the Meta Pixel noscript 1x1 beacon.
- **Security headers:** HSTS, `x-content-type-options`, `referrer-policy`, `permissions-policy`, and a `frame-ancestors` CSP are all present on the apex.
- **Run cost:** about $0.04 (6 Lighthouse calls plus 6 instant_pages calls).
