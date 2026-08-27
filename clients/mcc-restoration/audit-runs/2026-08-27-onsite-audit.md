# Onsite Audit - MCC Restoration and Contracting Services - 2026-08-27

**Live origin audited:** https://staging.rankai-mcc-restoration.pages.dev (staging)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** first audit for this client - no comparison data
**Form factor:** desktop (Lighthouse 13.4.0, cpuSlowdownMultiplier=1, throughputKbps=10240)

## Environment caveat - read this before acting on the SEO number

This run audited the Cloudflare Pages staging preview, not the production apex. `mccrestoration.com` is still unregistered (see `onboarding_notes.domain_pending`) and there is no `apex_cutover` on the client record.

`staging.rankai-mcc-restoration.pages.dev` returns `x-robots-tag: noindex`, which Cloudflare Pages injects on every `*.pages.dev` preview deployment. The Lighthouse `is-crawlable` audit therefore fails on all 6 URLs and drags the SEO category down to 69 everywhere. **That is a preview-host artifact, not a site defect.** SEO is recorded in the state file but is EXCLUDED from every verdict in this report. SEO status: **inconclusive - staging noindex artifact, re-audit after apex cutover.**

Two more staging artifacts were checked by hand and ruled out as issues:

- DataForSEO reports `checks.canonical = false` on all 6 URLs. Every page canonicalises to `https://mccrestoration.com/...`, which is the correct production target, but it is cross-origin relative to the staging host so the self-canonical check cannot pass. Not counted.
- DataForSEO reports `checks.has_micromarkup = false` on all 6 URLs. Verified against the live HTML: every page ships one valid `application/ld+json` block (LocalBusiness, Organization, WebSite, plus BreadcrumbList / FAQPage / Service where the url-plan calls for them). The DataForSEO check only detects microdata and RDFa, not JSON-LD. Not counted.

Client record `status` is `pending`, not `active`. `build_status` is `pushed_main` and all 6 URLs returned HTTP 200, so the site is live and auditable. The audit proceeded and the deviation is logged in the state file.

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 100 (99.8) | n/a |
| Accessibility | 90 (89.7) | n/a |
| Best Practices | 100 | n/a |
| SEO | 69 (excluded - staging artifact) | n/a |

Pages by verdict: green: 0, amber: 0, red: 6, error: 0

Performance is genuinely excellent on this build. Every page returns TBT of 0 ms, CLS under 0.015, and LCP under 850 ms on desktop. The red verdict is driven entirely by two accessibility defects that appear on every page in the template, not by speed.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT | Words |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 100 | 86 | 100 | 69 | 0.82s | 0.015 | 0ms | 1193 |
| `/services/` | services-hub | red | 99 | 90 | 100 | 69 | 0.84s | 0.004 | 0ms | 790 |
| `/services/water-damage-restoration/` | service-landing | red | 100 | 90 | 100 | 69 | 0.77s | 0.005 | 0ms | 1652 |
| `/services/fire-damage-restoration/` | service-landing | red | 100 | 90 | 100 | 69 | 0.77s | 0.004 | 0ms | 1549 |
| `/service-areas/dallas-tx/` | service-area | red | 100 | 91 | 100 | 69 | 0.76s | 0.005 | 0ms | 1403 |
| `/contact/` | contact | red | 100 | 91 | 100 | 69 | 0.79s | 0.004 | 0ms | 742 |

INP is null on every page: Lighthouse lab runs do not produce an INP value without field data.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `link-name` | 6 | high | Footer address block renders `<a href="mailto:">` with an empty href and empty link text because the client email is still unfilled. Suppress the element when email is null. |
| `color-contrast` | 6 | high | Breadcrumb links at `text-dark/50` measure 3.04:1 and the homepage trust-row paragraphs at `text-dark/60` measure 4.04:1, both under the 4.5:1 WCAG AA minimum. Raise both to `text-dark/70`. |
| `image-delivery-insight` | 6 | medium | Inner-page hero serves the full 182.9 KB `/images/hero-bg.webp` with no `srcset`. Wastes 14 to 147 KiB per page. |
| `unsized-images` | 6 | medium | Header logo `/images/logo.webp` ships with no `width` and `height` attributes. |
| `lcp-discovery-insight` | 5 | medium | Inner-page hero image is the LCP element but has no `fetchpriority="high"`. The homepage hero has it; the shared inner-page hero does not. |
| `plain_text_word_count` | 2 | low | `/` is 1193 words against a 1200 target and `/services/` is 790 against 800. Both are inside extraction noise; no action needed. |

## Money page alerts

All five money pages came back red. The cause is identical on every one of them: the sitewide `link-name` failure. Accessibility scores are otherwise close to passing.

- **`/`** (home) - red. Accessibility 86, the lowest on the site. One empty `mailto:` link plus five `text-dark/60` paragraphs at 4.04:1 contrast.
- **`/contact/`** (contact) - red. Accessibility 91. **Two** empty `mailto:` links here, not one: the footer instance plus a second in the contact card (`<a href="mailto:" class="font-bold text-white no-underline break-all">`). This is the highest-value fix on the site because a visitor who clicks the email address on the contact page gets a blank compose window with no recipient.
- **`/services/`** (services-hub) - red. Accessibility 90. Empty `mailto:` plus a 3.04:1 breadcrumb link. Also the worst image waste on the site at 147 KiB.
- **`/services/water-damage-restoration/`** (service-landing) - red. Accessibility 90. Empty `mailto:` plus two 3.04:1 breadcrumb links.
- **`/services/fire-damage-restoration/`** (service-landing) - red. Accessibility 90. Same as above.

## Regressions vs prior audit

First audit for this client. No comparison data. This run becomes the baseline for the next monthly audit.

## Recommended next actions (priority order)

1. **(money page, template, high)** Remove the empty `mailto:` links. The footer address partial and the `/contact/` contact card both emit `<a href="mailto:">` with an empty href and no link text, because `email` is still on the `awaiting_intake` list in the client record. Wrap both in a conditional so the anchor is not rendered at all when email is unset, and fall back to the phone number `(682) 772-9123` as the displayed contact method. This clears `link-name` on all 6 pages and, once the pages are otherwise clean, moves the whole site from red to green. Chase Jeff Sibley for the business email in the same pass so the link can come back properly.

2. **(template, high)** Fix the two contrast failures in the shared layout. Breadcrumb links use `text-dark/50`, which renders `#8f949d` on `#ffffff` at 12px for a measured 3.04:1 against the 4.5:1 AA minimum. The homepage trust-row paragraphs use `text-dark/60`, rendering `#787f89` on white at 14px for 4.04:1. Raise both utilities to `text-dark/70` (approximately 6:1 on white) and re-audit to confirm. This is the difference between accessibility 86 to 91 and accessibility 100.

3. **(template, medium)** Give the inner-page hero the same image treatment the homepage hero already has. The homepage renders `<img src="/images/hero-bg.webp" srcset="...480w, ...768w, ...1200w, ...1376w" sizes="100vw" loading="eager" fetchpriority="high" decoding="async">`. Every other page renders `<img src="/images/hero-bg.webp" class="w-full h-full object-cover" loading="eager">` with no srcset, no sizes, and no fetchpriority, so it downloads the full 182.9 KB original for a band that is only 247 to 392 px tall. Copying the homepage attributes onto the shared inner hero component closes both `image-delivery-insight` (up to 147 KiB saved on `/services/`) and `lcp-discovery-insight` in one change.

4. **(template, medium)** Add `width="380" height="247"` to the header logo `<img>` for `/images/logo.webp`. Those are its intrinsic dimensions. This closes `unsized-images` on all 6 pages and removes the last layout-shift source; CLS on the homepage is currently 0.015 versus 0.004 elsewhere.

5. **(process)** Cut over the apex domain and re-audit. `mccrestoration.com` is unregistered, so this audit could only run against the Pages preview, where the injected `noindex` header makes SEO unmeasurable and the self-canonical check unfixable. Nothing in the SEO category can be confirmed or cleared until the apex is live. Until then, treat the SEO 69 as deferred, not as a problem to solve.

## Notes / caveats

- Lighthouse ran DESKTOP only. The DataForSEO MCP wrapper in use does not expose a mobile form factor for this pipeline, so these are desktop numbers. Mobile performance would typically land 10 to 20 points lower, though with TBT at 0 ms and LCP under 850 ms there is a lot of headroom.
- Verdict rule applied this run: a high-severity issue from either source, Lighthouse or DataForSEO on-page, forces red. `link-name` is the high-severity driver on all 6 URLs. Without it, the site would sit at amber on the strength of the homepage's accessibility 86.
- `is-crawlable` is recorded at low severity rather than high, because SEO is excluded from the verdict this run and the failure is the staging `noindex` header. It appears in the per-URL issue list only for `/`, where the top-5 cap left room for it.
- DataForSEO `checks.frame = true` on `/service-areas/dallas-tx/` is the Google Maps embed. It is `loading="lazy"` and carries a `title` attribute, so it is recorded at low severity for the record only. No action needed.
- `onpage_score` from DataForSEO is 97.44 on all 6 URLs. No broken internal links, no broken external links, no broken resources, no mixed content, no duplicate titles or descriptions, no missing alt text, and all title and meta description lengths are inside the target ranges.
- `render-blocking-insight` flags `/_astro/_slug_.WYPPNaa1.css` at 8.8 KB for an estimated 50 to 57 ms. With performance already at 99 to 100, this is not worth a recommendation slot. Revisit only if performance drops.
- API cost for this run: $0.039 (6 Lighthouse live calls at $0.005, 6 instant_pages calls at $0.0015).
