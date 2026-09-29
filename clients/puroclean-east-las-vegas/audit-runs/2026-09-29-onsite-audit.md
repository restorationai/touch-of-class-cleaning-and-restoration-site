# Onsite Audit - PuroClean of East Las Vegas - 2026-09-29

**Live origin audited:** https://purocleaneastlasvegas.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-08-27
**Form factor:** desktop (canonical). A supplementary mobile pass is included for context only.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 98.3 | -1.4 |
| Accessibility | 96.0 | 0 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |
| Performance (mobile, supplementary) | 87.7 | -7.0 |

Pages by verdict: {green: 6, amber: 0, red: 0, error: 0}

## Per-page scores (desktop)

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | Mobile Perf |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | green | 99 | 100 | 100 | 100 | 0.95s | 0.004 | 90 |
| /services/ | services-hub | green | 99 | 95 | 100 | 100 | 0.99s | 0.005 | 88 |
| /services/fire-damage-restoration/ | service-landing | green | 98 | 95 | 100 | 100 | 0.94s | 0.005 | 97 |
| /services/mold-remediation/ | service-landing | green | 98 | 95 | 100 | 100 | 0.90s | 0.010 | 83 |
| /service-areas/henderson-nv/ | service-area | green | 98 | 95 | 100 | 100 | 0.93s | 0.006 | 87 |
| /contact/ | contact | green | 98 | 96 | 100 | 100 | 0.92s | 0.005 | 81 |

TBT is 0 ms on every page (desktop). On-page basics all pass: one H1 per page, titles 48-63 chars, meta descriptions 99-143 chars, self-referencing canonicals, no broken links or resources, word counts above the url-plan target on every page.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `unused-javascript` | 6 | medium | Google tag `gtag/js?id=G-M4N5NVD0WN` ships ~69 KiB of unused JS on every page. Load it after first interaction or on `requestIdleCallback`, or move it to a Partytown worker. |
| `image-delivery-insight` | 6 | medium | `/images/logo.png` is 50 KiB and ~48 KiB of that is waste on every page. Export a correctly sized WebP/SVG logo. Serve `hero-bg.webp` (180 KiB) via `srcset` so desktop and mobile get appropriately sized files. |
| `network-dependency-tree-insight` | 6 | medium | Chain is HTML -> `_astro/_slug_.*.css` -> Google Fonts. Self-host the font files and preload the primary woff2. |
| `cache-insight` | 6 | low | Only flagged asset is Cloudflare `email-decode.min.js` (under 1 KiB). Turn off Email Obfuscation in Cloudflare Scrape Shield to remove the script entirely. |
| `render-blocking-insight` / `has_render_blocking_resources` | 6 | low | Single 8.8 KiB stylesheet `_astro/_slug_.*.css`. Inline it (Astro `build.inlineStylesheets: "always"`). |
| `color-contrast` | 5 | high | Breadcrumb links use `text-dark/50` (#888c93 on white, 3.37:1, needs 4.5:1). Change to `text-dark/70` or darker in the breadcrumb component. Only page without it is `/` (no breadcrumb). |
| `lcp-discovery-insight` | 5 | medium | The hero `<img>` is eager and discoverable but lacks `fetchpriority="high"`. Add it to the hero image component. |
| `forced-reflow-insight` | 3 | medium | ~63 ms of unattributed forced reflow on `/`, fire, and mold pages. Check layout reads (offsetHeight, getBoundingClientRect) in header/FAQ scripts after DOM writes. |
| `low_content_rate` | 3 | low | Text-to-HTML ratio on `/`, `/services/`, `/contact/`. Informational; word counts already meet target. No action needed. |

## Money page alerts

None. All four money-page archetypes (home, services hub, 2 service landings, contact) are green on desktop.

## Regressions vs prior audit

**Verdict transitions:** none (6 green -> 6 green).

**Score and Core Web Vitals regressions (thresholds: category -5, LCP +200 ms, CLS +0.02, TBT +100 ms):**
- `/service-areas/henderson-nv/`: LCP rose 603 ms -> 927 ms (+324 ms). Still well under 2.5 s; no category dropped more than 2 points.
- Site-level category averages: no drop of 3 or more points (performance -1.4).
- LCP rose 73-180 ms on the other 5 pages (below threshold), consistent with the new Google tag payload.

**New issues this month:**
- All 6 pages: `unused-javascript` (Google tag gtag.js, ~69 KiB unused). This was not flagged in August.
- `/`, `/services/fire-damage-restoration/`, `/services/mold-remediation/`: `forced-reflow-insight`.
- `/services/`, `/contact/`: `low_content_rate` (informational).
- `/service-areas/henderson-nv/`: `frame` (the lazy-loaded Google Maps embed; intentional, low).
- `cache-insight` on 5 pages: likely an artifact of last month's top-5 issue cap, not a real change.

**Issues resolved since last audit:** (positive, keep doing this)
- 5 pages: `has_micromarkup_errors` is no longer raised by DataForSEO (FAQPage / BreadcrumbList warnings cleared).
- `/`: `largest-contentful-paint` is no longer flagged.
- `/contact/`: CLS improved 0.039 -> 0.005.

## Recommended next actions (priority order)

1. **(template, high)** Fix breadcrumb contrast: swap `text-dark/50` for `text-dark/70` (or a solid color at 4.5:1 or better) in the breadcrumb component. Lifts accessibility from 95/96 to 100 on 5 pages including all money pages except home.
2. **(template, medium, new)** Defer the Google tag (`G-M4N5NVD0WN`): load gtag.js on first user interaction or via Partytown. Removes ~69 KiB unused JS on every page and is the most likely cause of the mobile performance drop from 94.7 to 87.7 (contact is at 81 on mobile).
3. **(template, medium)** Add `fetchpriority="high"` to the hero `<img>` and serve `hero-bg.webp` with a responsive `srcset` (up to 124 KiB waste on `/contact/`).
4. **(template, medium)** Replace the 50 KiB `/images/logo.png` with a right-sized WebP or SVG (saves ~48 KiB on every page).
5. **(template, low)** Populate or remove the empty `foundingDate: ""` on the Organization and LocalBusiness JSON-LD (still present on every page; no DataForSEO check ID covers it).

## Notes / caveats

- Audited the apex. The client record has `apex_cutover: null` and `status: "live"` (not "active"), but the apex serves 200 with no `x-robots-tag` and last month's baseline was also on the apex, so the apex was used and SEO counts toward the verdict.
- Desktop is canonical (DataForSEO Lighthouse 13.4.0, formFactor desktop). Mobile scores are supplementary and do not drive the verdict. Mobile LCP is 2.5-4.1 s, so the mobile gap is where the real headroom is.
- This month every failing Lighthouse audit is recorded (up to 8 per URL) instead of a top-5 cap, so some low-severity "new" items reflect last month's cap rather than real changes.
- INP is null everywhere; it is a field metric and not produced by a lab run.
- Cost: 12 Lighthouse calls (6 desktop + 6 mobile at $0.005) plus 6 instant_pages ($0.0018), about $0.07 total.
