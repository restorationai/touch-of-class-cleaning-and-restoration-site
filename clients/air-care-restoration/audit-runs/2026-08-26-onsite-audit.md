# Onsite Audit - Air Care Restoration - 2026-08-26

**Live origin audited:** https://aircarerestoration.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client, no comparison data
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Delta vs prior |
| --- | ---: | ---: |
| Performance | 98 | n/a |
| Accessibility | 95 | n/a |
| Best Practices | 100 | n/a |
| SEO | 100 | n/a |

Pages by verdict: green: 2, amber: 4, red: 0, error: 0

Nothing is broken. Every page returns 200, every category scores 93 or better, and the SEO and Best Practices categories are perfect across all six URLs. The amber verdict comes from two template defects that repeat on every page (an oversized header logo and a set of WCAG AA contrast failures) plus one Core Web Vitals miss on the homepage.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 93 | 96 | 100 | 100 | 0.65s | 0.157 | 0ms |
| `/services/` | services-hub | amber | 99 | 95 | 100 | 100 | 0.93s | 0.029 | 0ms |
| `/services/water-damage-restoration/` | service-landing | amber | 100 | 95 | 100 | 100 | 0.64s | 0.025 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | amber | 99 | 95 | 100 | 100 | 0.83s | 0.025 | 0ms |
| `/service-areas/sweetwater-tx/` | service-area | green | 99 | 95 | 100 | 100 | 0.85s | 0.010 | 0ms |
| `/contact/` | contact | green | 100 | 96 | 100 | 100 | 0.78s | 0.029 | 0ms |

INP returned null on all six URLs (no interaction was simulated in the lab run).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is a 175 KB PNG at 878x500 intrinsic, rendered at 169x96. Export `logo-192w.webp` and `logo-384w.webp`, add `srcset`/`sizes`, and correct the `width`/`height` attributes. 173 KB wasted per page. |
| `color-contrast` | 6 | high | 35 failing text elements sitewide, all from three token choices: accent orange as text, `text-dark/50`, `text-dark/60`. Exact replacements below. |
| `lcp-discovery-insight` | 5 | medium | The inner-page hero `<img>` has no `fetchpriority="high"`, no `srcset` and no `decoding="async"`. The homepage hero has all three. Bring the shared hero component up to parity. |
| `high_loading_time` | 4 | medium | DataForSEO's crawler recorded `dom_complete` of 3.3s to 3.7s on these four pages against 1.2s on the service-area page. Driven by total image weight (374 KB to 712 KB per page), most of which is the header logo. Resolves with the logo fix. |
| `render-blocking-insight` | 6 | low | `/_astro/_slug_.Dh-igo42.css`, 8.9 KB, cost 52ms on one page and nothing measurable elsewhere. Leave it. |
| `cache-insight` | 6 | low | The only short-TTL resource is Cloudflare's own injected `cdn-cgi/scripts/.../email-decode.min.js` (949 bytes, 48h TTL, 285 bytes of theoretical savings). Not ours to fix. |
| `network-dependency-tree-insight` | 6 | low | Longest critical chain is 162ms. Flagged on the tree shape, not on latency. No action. |
| `no_image_title` | 6 | low | DataForSEO flags `<img>` elements with no `title` attribute. A `title` on an image is not an SEO or accessibility requirement and all images already carry meaningful `alt` text. Logged for completeness, no action. |

Note on severity and verdicts: `color-contrast` and `image-delivery-insight` are rated high severity as template issues, but under the verdict rubric only category scores and on-page issue severities move a page's verdict. That is why pages carrying a high-severity Lighthouse issue can still read amber or green. Accessibility still scores 95 to 96 because the failures are concentrated in small supporting text rather than primary content.

## Money page alerts

- **`/` (home)** verdict: amber. Performance 93, LCP 0.65s, but **CLS 0.157** fails the Core Web Vitals "good" threshold of 0.10. Lighthouse attributes 0.154 of that 0.157 to a single element: `main.flex-1 > header.relative > div.container-wide`, the hero copy block, reflowing when three Poppins woff2 subsets finish loading. Two smaller shifts follow in the `h1` (0.0028) and the desktop `nav` (0.0010). Also carries a 177-character meta description, which Google will truncate.
- **`/services/` (services-hub)** verdict: amber. Performance 99 and LCP 0.93s are fine. Flagged for `high_loading_time` (crawler `dom_complete` 3.40s) and the missing hero `fetchpriority`. This page carries 14 images totalling 712 KB, the heaviest of the six, with 247 KB of that recoverable.
- **`/services/water-damage-restoration/` (service-landing)** verdict: amber. Performance 100, LCP 0.64s. Flagged for `high_loading_time` (crawler `dom_complete` 3.43s) and the missing hero `fetchpriority`.
- **`/services/fire-damage-restoration/` (service-landing)** verdict: amber. Performance 99, LCP 0.83s. Same two flags. Its hero `/images/services/fire-damage-restoration.webp` is 126 KB with 9 KB recoverable through higher compression.

## Regressions vs prior audit

First audit for this client. No comparison data. This run becomes the baseline for the September audit.

## Recommended next actions (priority order)

1. **(template, high impact)** Replace the header logo. `/images/logo.png` is 175 KB, 878x500 intrinsic, and renders at 169x96 CSS pixels. It ships on all 366 pages in the plan. Export WebP at `192w` and `384w`, wire up `srcset="/images/logo-192w.webp 192w, /images/logo-384w.webp 384w"` with `sizes="(min-width: 768px) 192px, 160px"`, and fix the attributes: the tag currently declares `width="64" height="64"` against a real 1.756:1 aspect ratio, so the reserved box is wrong and contributes to the header `nav` shift. Expected result: about 173 KB saved per page, and the `high_loading_time` flag on four pages should clear.

2. **(template, accessibility)** Fix the 35 WCAG AA contrast failures. All of them trace to three token decisions, with exact replacements:
   - Accent orange as text (`.eyebrow`, `.text-accent`): `#ff6901` on white is 2.89:1 and on `#f9fafb` is 2.76:1. Use `#c25001`, which measures 4.73:1 on white and 4.52:1 on `#f9fafb` and keeps the same hue. 17 elements.
   - `.btn-accent`: white text on `#ff6901` is 2.88:1 at 14px bold, which is not large text, so it needs 4.5:1. Either keep the vivid orange background and switch the label to the primary navy `#02255d` (5.10:1), or darken the background to `#c75201` and keep white text (4.53:1). The navy-on-orange option preserves brand vibrancy. 4 elements.
   - Muted body copy: `text-dark/50` renders as `#8192ae` (3.15:1) and `text-dark/60` as `#677c9e` (4.23:1). Move both to `text-dark/70`, which renders `#4e668e` at 5.81:1. Affects the process-step paragraphs and the footer link column. 13 elements.
   - One `text-slate-400` (`#94a3b8`, 2.56:1) on the service-area template. Move to `text-slate-500` or darker. 1 element.

3. **(money page, Core Web Vitals)** Fix the homepage CLS of 0.157. Two changes, do both:
   - Delete the duplicate Google Fonts stylesheet. The `<head>` loads the identical URL twice: once as `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Poppins:wght@400;500;600;700;800;900&display=swap" media="print" onload="this.media='all'">` (the async pattern) and once as a plain blocking `<link rel="stylesheet">` with the same href. The blocking copy defeats the async one and double-fetches. Remove the blocking duplicate. Present on all six pages.
   - Self-host Poppins and Anton as same-origin woff2 and pair `font-display: swap` with a metric-matched fallback (`@font-face` with `size-adjust`, `ascent-override`, `descent-override` over Arial) so the swap does not resize the hero copy block. Preconnects to both `fonts.googleapis.com` and `fonts.gstatic.com` are already in place, so the remaining cost is the cross-origin round trip itself.

4. **(template, LCP)** Bring the inner-page hero `<img>` up to homepage parity. The homepage hero is `<img src="/images/hero-bg.webp" srcset="... 480w, 768w, 1200w, 1376w" sizes="100vw" loading="eager" fetchpriority="high" decoding="async">`. The shared hero used by `/services/`, both service landings, the service-area template and `/contact/` is only `<img src="..." class="w-full h-full object-cover" loading="eager">`. Add `fetchpriority="high"`, the responsive `srcset`/`sizes`, and `decoding="async"`. This is the `lcp-discovery-insight` failure on 5 of 6 pages and by extension on all 365 non-home pages.

5. **(per-page)** Trim the homepage meta description from 177 characters to 160 or fewer. Current text: "Air Care Restoration provides 24/7 water, fire, mold, and storm damage restoration across Abilene and surrounding areas. Licensed, insured, IICRC-certified. Call (325) 339-8723." Dropping "Licensed, insured, " brings it to 158. The other five pages are between 124 and 137 characters and need nothing.

## What is already correct (do not regress these)

- **Schema:** every page carries valid, parseable JSON-LD. `LocalBusiness` plus `AggregateRating`, `PostalAddress`, `GeoCoordinates` and `OpeningHoursSpecification` sitewide; `Organization` and `WebSite` on `/`, `/services/` and `/contact/`; `Service` on both service landings; `BreadcrumbList` and `FAQPage` on all five non-home pages. Zero parse errors across 24 blocks.
- **Titles and canonicals:** all six titles fall between 54 and 61 characters. Every canonical is self-referencing and absolute. Exactly one `h1` per page. No duplicate titles, descriptions or content.
- **Links and resources:** zero broken internal links, zero broken external links, zero broken resources, zero resource errors, zero `http://` references (no mixed content).
- **Image alt text:** 100 percent coverage with non-empty, descriptive alt attributes on all 37 images across the six pages.
- **Content depth:** every page exceeds its `url-plan.json` target. Home 1733 words against 1200, services hub 861 against 800, water damage 1843 against 1100, fire damage 1938 against 1100, Sweetwater 1324 against 900, contact 658 against 400.
- **Security headers:** `strict-transport-security: max-age=31536000; includeSubDomains`, `x-content-type-options: nosniff`, `content-security-policy: frame-ancestors`, `permissions-policy` locking geolocation, microphone and camera, and `referrer-policy: strict-origin-when-cross-origin`. Best Practices scores 100 on all six URLs.
- **The Google Maps embed** on the service-area template already carries `loading="lazy"`. DataForSEO's `frame` check fires on its presence, which is expected and not a defect.

## Notes / caveats

- **Desktop only.** The DataForSEO Lighthouse run used `formFactor: desktop` with `cpuSlowdownMultiplier: 1` and `throughputKbps: 10240`. Mobile scores typically land 10 to 20 performance points lower, and the CLS and image-weight findings above will hit harder on mobile because the logo is served at `max-w-[55vw]` there. Do not report these numbers as mobile-first scoring. Lighthouse version 13.4.0.
- **Mobile auditing is now available.** The methodology notes that the MCP wrapper does not expose `form_factor`. This run went directly to `/v3/on_page/lighthouse/live/json`, which does accept `for_mobile`. Desktop was kept for this run so the September audit has a like-for-like baseline, but a mobile pass is a one-parameter change whenever the cadence is ready for it.
- **Client record status is stale.** `clients/air-care-restoration.json` still reads `status: "onboarding"`. The apex cutover completed 2026-08-21 and the last push to main was 2026-08-26, so the site is live and auditable. The audit proceeded on that basis. Worth flipping the status field to `active`.
- **Two `high_loading_time` signals disagree with Lighthouse and both are right.** Lighthouse reports LCP under 1s and performance 93 to 100, while DataForSEO's crawler reports `dom_complete` of 3.3s to 3.7s on four pages. Lighthouse measures paint of the above-the-fold hero; the DataForSEO crawler waits for every resource including the 175 KB logo and, on `/services/`, 14 service tile images. The logo fix in action 1 addresses both readings.
- **No URLs errored.** All 6 Lighthouse calls and all 6 instant-pages calls returned status 20000.
- **URL selection:** auto-derived from `plan/url-plan.json` because no `audit-urls.txt` exists. No `service-area` page carries `primary: true` and there is no `/service-areas/abilene-tx/` page (Abilene is the home city, covered by `/`), so the fallback rule selected the first area in the plan, `/service-areas/sweetwater-tx/`. The two service landings are the joint-highest priority entries at 9.0.
- **Run cost:** about $0.061 (6 Lighthouse live calls at $0.005, 6 instant-pages calls at about $0.005). Well inside the $0.30 to $0.50 target.
