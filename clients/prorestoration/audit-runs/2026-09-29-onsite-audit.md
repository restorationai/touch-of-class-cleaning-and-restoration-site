# Onsite Audit - ProRestoration Services - 2026-09-29

**Live origin audited:** https://prorestorationca.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** 2026-08-27 (amber)
**Form factor:** desktop (Lighthouse 13.4.0, cpuSlowdownMultiplier 1, throughputKbps 10240). Mobile scores would typically run 10-20 performance points lower.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.0 | -0.7 |
| Accessibility | 91.3 | 0.0 |
| Best Practices | 100.0 | 0.0 |
| SEO | 100.0 | 0.0 |

Pages by verdict: green: 5, amber: 1, red: 0, error: 0

Headline scores are flat month over month. The site stays amber because of one per-page item on the homepage (184-character meta description). Two template changes shipped since the last audit and both added page weight: a GA4 tag (`G-LQE0DXHG08`) now loads on every page, and the header/footer logo moved from `/images/logo.svg` to a 104 KiB `/images/logo.png`. None of the August accessibility fixes (empty mailto link, breadcrumb contrast) have shipped yet.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 98 | 96 | 100 | 100 | 1.06s | 0.023 | 0ms |
| `/services/` | services-hub | green | 99 | 90 | 100 | 100 | 0.97s | 0.004 | 0ms |
| `/services/water-damage-restoration/` | service-landing | green | 99 | 90 | 100 | 100 | 0.96s | 0.005 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | green | 100 | 90 | 100 | 100 | 0.80s | 0.005 | 0ms |
| `/service-areas/oildale-ca/` | service-area | green | 99 | 91 | 100 | 100 | 1.03s | 0.005 | 0ms |
| `/contact/` | contact | green | 99 | 91 | 100 | 100 | 1.03s | 0.025 | 0ms |

INP is null on every page: Lighthouse lab runs do not emit INP without user interaction. All LCP values remain well inside the 2.5s "good" threshold.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `link-name` | 6 | high | Still open from August. Footer `address.not-italic > div > a.text-primary` renders `<a href="mailto:">` with no text because `clients/prorestoration.json` has `contact: null` and "email address" is still in `onboarding_notes.awaiting_intake`. Guard the anchor on a truthy email field in the footer and in the `/contact/` contact card (`div.space-y-5 > div.flex > div > a.font-bold`, a second empty mailto on that page). |
| `color-contrast` | 5 | high | Still open from August. Breadcrumb links `a.text-dark/50` compute to `#888c93` on `#ffffff` at 12px = 3.37:1 (needs 4.5:1). Change to `text-dark/70` or `#6b7280`. New on `/service-areas/oildale-ca/`: `span.text-slate-400` in the card grid (`div.grid > div.bg-white > div.flex`) is `#94a3b8` on white at 14px = 2.56:1; change to `text-slate-600`. The August `.btn-accent` contrast failure is no longer flagged. |
| `image-delivery-insight` | 6 | medium | New site-wide driver: `/images/logo.png` is 1688x646 (104 KiB) rendered at 251x96, wasting 102 KiB on every page load. Replace with the prior SVG, or export a 502x192 WebP (2x) and add a `srcset`. Second driver unchanged from August: the inner-page hero hardcodes `/images/hero-bg.webp` (248 KB, no `srcset`), wasting 195 KiB on `/contact/`, 153 KiB on `/services/`, 128 KiB on `/service-areas/oildale-ca/`. Port the homepage hero's `srcset`/`sizes` to the shared inner hero. |
| `unused-javascript` | 6 | medium | New this month. `https://www.googletagmanager.com/gtag/js?id=G-LQE0DXHG08` (156 KiB) ships about 69 KiB of unused code on every page. It already loads `async`. Defer initialisation until after `load` or first interaction, or move GA4 to Cloudflare Zaraz so the tag runs off the main thread. |
| `cache-insight` | 6 | low | Only resource flagged is Cloudflare's `email-decode.min.js` (955 bytes), injected because Email Obfuscation finds the empty mailto anchor. Disappears when `link-name` is fixed. |
| `render-blocking-insight` / `has_render_blocking_resources` | 6 | low | `/_astro/_slug_.B_qI-cHQ.css` (about 9 KiB) blocks render for 30-56ms. Low priority at current scores. |
| `network-dependency-tree-insight` | 6 | low | No preconnect for `www.googletagmanager.com`. Add `<link rel="preconnect" href="https://www.googletagmanager.com">` in the layout head now that GA4 is live. |
| `no_image_title` | 6 | low | Images carry `alt` but no `title`. Cosmetic, no action. |
| `lcp-discovery-insight` | 5 | low | Inner-page hero `<img src="/images/hero-bg.webp" loading="eager">` has no `fetchpriority="high"` (the homepage hero does). Add it to the shared inner hero component. |
| `forced-reflow-insight` | 2 | low | New on `/services/` (37ms) and `/services/fire-damage-restoration/` (61ms), unattributed. Appeared at the same time as the GA4 tag. Re-check after GA4 deferral before investigating further. |
| `low_content_rate` | 2 | low | Text-to-HTML ratio 7.7% on `/` and 6.0% on `/services/`. Markup-heavy hubs, no action. |

## Money page alerts

- **`/`** (home) - verdict: amber. Meta description is 184 characters against a 70-160 target and will truncate in the SERP (unchanged since August). Accessibility 96 from the empty footer mailto link. 261 KiB of image waste: logo.png 102 KiB, `team-768w.webp` 82 KiB (768x769 shown at 587x734), `hero-bg.webp` 77 KiB. LCP up 299ms to 1.06s.

## Regressions vs prior audit

**Verdict transitions:**
- `/services/`, `/service-areas/oildale-ca/`, `/contact/` went amber to green. Caution: this is because DataForSEO's `high_loading_time` check did not fire this run (fetches finished in 29-66ms vs 3.3-4.6s in August). The cause is not fixed. HTML still returns `cache-control: public, max-age=0, must-revalidate` and `cf-cache-status: DYNAMIC` on all four spot-checked pages.
- No pages got worse. `/` stays amber.

**Core Web Vitals regressions (LCP up 200ms or more):**
- `/`: LCP 765ms to 1064ms (+299ms)
- `/contact/`: LCP 771ms to 1031ms (+260ms)
- `/service-areas/oildale-ca/`: LCP 801ms to 1033ms (+232ms)
- `/services/water-damage-restoration/` just missed the threshold (+196ms). Likely cause on all four: the new eager 104 KiB `logo.png` and 156 KiB GA4 script now compete for bandwidth with the hero image in the simulated load. No category score dropped by 5 or more points, and CLS and TBT did not regress.

**New issues this month:**
- All 6 pages: `unused-javascript` - GA4 gtag.js, about 69 KiB unused
- `/services/water-damage-restoration/`, `/services/fire-damage-restoration/`: `image-delivery-insight` - newly flagged solely because of the oversized `logo.png`
- `/services/`, `/services/fire-damage-restoration/`: `forced-reflow-insight`
- `/service-areas/oildale-ca/`: new `color-contrast` element (`span.text-slate-400`, 2.56:1) inside the existing `color-contrast` failure

**Issues resolved since last audit:**
- All 6 pages: `unsized-images` no longer flagged. Caveat: the new logo `<img>` carries `width="64" height="64"` on a 2.6:1 image. Set the attributes to the real ratio (for example `width="251" height="96"`).
- `/services/`, `/service-areas/oildale-ca/`, `/contact/`: `high_loading_time` no longer flagged (see caution above; not a real fix)

## Recommended next actions (priority order)

1. **(money page, template, high impact)** Remove the empty `mailto:` anchors: the footer link on all pages, plus the contact-card link on `/contact/`. Wrap both in a truthiness check on the email field and collect the email from the client (still in `awaiting_intake`). This is worth about 4-6 accessibility points on every page and also removes the Cloudflare `email-decode.min.js` injection. Carried over from August.
2. **(money page)** Rewrite the homepage meta description to under 160 characters. This is the only item keeping the site amber. The current text ends "Licensed, insured, IICRC-certified. Call (661) 393-9306." Update both the rendered page and the `meta_description` for `/` in `plan/url-plan.json`.
3. **(template, high impact)** Replace `/images/logo.png` (1688x646, 104 KiB) with the previous `/images/logo.svg`, or a 502x192 WebP, in both the header and footer. Fix the `width`/`height` attributes to match the real aspect ratio. This saves 102 KiB on every page and is the most likely cause of this month's LCP regressions.
4. **(template)** Raise breadcrumb contrast from `text-dark/50` to `text-dark/70`, and change `span.text-slate-400` on the service-area card grid to `text-slate-600`. Affects 5 of 6 audited pages and every breadcrumbed page sitewide.
5. **(template)** On the shared inner-page hero, add the homepage's `srcset`/`sizes` plus `fetchpriority="high"`, and add a preconnect to `www.googletagmanager.com` in the layout head. This saves 128-195 KiB on `/contact/`, `/services/` and service-area pages and clears `lcp-discovery-insight` on 5 pages.

## Notes / caveats

- Audited the apex production origin (cut over 2026-08-09). `HEAD https://prorestorationca.com/` returns 200 with no `x-robots-tag`, so the staging noindex correction does not apply and SEO counts toward the verdict.
- Lighthouse ran desktop only via direct REST calls to `/v3/on_page/lighthouse/live/json` (`for_mobile: false`) and `/v3/on_page/instant_pages`. The MCP server in this environment exposes only `api_request` and `docs_*`. Full Lighthouse JSON was parsed from disk, and every failing audit was retained so the month-over-month diff is complete.
- URL selection: five service-landing pages tie at priority 9.0 in `url-plan.json`. I kept water-damage-restoration and fire-damage-restoration from the August baseline so the deltas compare like for like. No service area is marked `primary`, and Bakersfield (the business city) has no service-area page, so `/service-areas/oildale-ca/` was kept.
- `description_length_out_of_range` on `/` comes from the System 3 rubric (70-160 characters) applied to DataForSEO's measured `description_length` of 184. DataForSEO's native check did not fire this run.
- Still open plan-conformance gap: service-area pages emit `LocalBusiness`, `FAQPage` and `BreadcrumbList` JSON-LD, but `url-plan.json` calls for a `Service` node, which is still missing on `/service-areas/oildale-ca/`. It was template-wide in August.
- Edge caching is still unaddressed: HTML is `max-age=0, must-revalidate` / `cf-cache-status: DYNAMIC`. This run's fast fetches hid it, and August measured 3.3-4.6s cold loads. A Cloudflare Cache Rule for HTML remains recommended once the higher-priority items above are done.
- False positives excluded as in August: `has_micromarkup: false` (JSON-LD is present and verified in the fetched HTML), and `is_https: true` (a pass).
- Zero broken links, zero broken resources, zero duplicate titles or descriptions. Canonicals are self-referencing everywhere, and titles are all 61-65 characters. Word counts meet `target_word_count` everywhere except `/services/` at 795 against 800, which is not worth acting on.
- `clients/prorestoration.json` is `status: pending`. The audit proceeded because `build_status` is `pushed_main` and the apex serves 200, the same basis as August.
- Estimated DataForSEO spend: 0.041 USD (6 Lighthouse at 0.005, 6 instant_pages at 0.0018).
