# Onsite Audit — Flood Fixers — 2026-08-27

**Live origin audited:** https://flood-fixers.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-07-15 (green)
**Form factor:** desktop only (see Notes)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99 | 0 |
| Accessibility | 91 | 0 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

No page dropped a verdict, no Core Web Vital regressed past threshold, and LCP improved on the two pages that were slowest last month.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | green | 98 | 96 | 100 | 100 | 1.04s | 0.018 |
| `/services/` | services-hub | green | 99 | 90 | 100 | 100 | 1.02s | 0.003 |
| `/services/water-damage-restoration/` | service-landing | green | 100 | 90 | 100 | 100 | 0.76s | 0.004 |
| `/services/flood-damage-restoration/` | service-landing | green | 100 | 90 | 100 | 100 | 0.76s | 0.004 |
| `/service-areas/chula-vista-ca/` | service-area | green | 99 | 91 | 100 | 100 | 0.82s | 0.049 |
| `/contact/` | contact | green | 99 | 91 | 100 | 100 | 0.85s | 0.022 |

TBT was 0ms on all six pages. INP is null on all six (lab Lighthouse does not emit it).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `link-name` | 6 | medium | Footer address block renders `<a href="mailto:">` with an empty address and no link text. Populate the email in site data or drop the anchor. |
| `cache-insight` | 6 | low | `images.flood-fixers.com` sends no `Cache-Control` at all and `/_astro/*` sends `max-age=14400, must-revalidate`. Both should be `max-age=31536000, immutable`. |
| `image-delivery-insight` | 6 | low | `brand/hero.webp` ships at 267KB; Lighthouse reports up to 218KB recoverable through compression. Non-home templates also serve it with no `srcset`/`sizes`. |
| `has_render_blocking_resources` | 6 | low | One stylesheet (`/_astro/_slug_.qvOpSyL3.css`, 8.6KB) and one script block render. Measured cost is 52ms; low priority at current scores. |
| `color-contrast` | 5 | medium | Breadcrumb links `a.text-dark/50` are #888c93 on white (3.37:1). On both service landings the phone CTA `a.btn-accent` is white on #2da8dc (2.71:1). |
| `lcp-discovery-insight` | 5 | low | The hero image lacks `fetchpriority="high"` on every template except home. Lighthouse checklist item `priorityHinted` fails on all five. |

## Money page alerts

None. All four money-page archetypes (home, services hub, both service landings, contact) came back green.

Two findings on money pages are worth acting on even though they did not trip a verdict:

- **`/contact/`** carries two empty `mailto:` anchors (footer plus the contact aside). A visitor who clicks the email affordance on the contact page opens a blank compose window.
- **`/services/water-damage-restoration/` and `/services/flood-damage-restoration/`** — the sticky phone CTA button fails WCAG AA contrast at 2.71:1. This is the primary conversion element on both pages.

## Regressions vs prior audit

**Verdict transitions:** none.

**Score deltas:** all four categories flat (performance 99, accessibility 91, best practices 100, SEO 100).

**Core Web Vitals:** no regressions past threshold. Two improvements:

- `/` LCP 1272ms to 1038ms (-234ms)
- `/contact/` LCP 1240ms to 846ms (-394ms)

**New issues this month:**

- `/`: `low_content_rate` — text-to-HTML ratio 9.3%. Recorded for the first time this run because last month's on-page rubric did not map this DataForSEO check. Newly surfaced, not newly broken.

**Issues resolved since last audit:** (positive — keep doing this)

- `/services/water-damage-restoration/`: `relative_og_image` is gone. og:image is now `https://flood-fixers.com/images/services/water-damage-restoration.webp` (verified HTTP 200).
- `/services/flood-damage-restoration/`: same fix, `https://flood-fixers.com/images/services/flood-damage-restoration.webp` (verified HTTP 200).

## Recommended next actions (priority order)

1. **(money page + template, high impact)** Fix the empty email link. Every audited page renders `<a href="mailto:" class="text-primary no-underline hover:underline">` in the footer `<address>` block, and `/contact/` renders a second one as `<a href="mailto:" class="font-bold text-white no-underline break-all">` in the contact aside. The email field feeding the template is empty; the client record has `contact: luxurycustomfloors@gmail.com`. Either bind that value into the template or remove the anchor. This is the single `link-name` failure on all 6 pages and the only thing `agent-accessibility-tree` reports.
2. **(money page, conversion-critical)** Darken the accent CTA. `a.btn-accent` renders white bold 14px on `#2da8dc`, a 2.71:1 ratio against a 4.5:1 requirement. Dropping the accent to `#1c7ea8` (same hue and saturation, lightness 52% to 38.5%) gives 4.57:1 and clears AA without a visual redesign. Currently failing on both service landing pages.
3. **(template, accessibility)** Raise breadcrumb link contrast. `nav.container-wide > ol.flex > li.flex > a.text-dark/50` computes to #888c93 on #ffffff, 3.37:1 at 12px. Moving the token from `text-dark/50` to `text-dark/60` yields #70757d at 4.64:1; `text-dark/65` gives 5.45:1 with more headroom. Affects 5 of 6 pages and is the main drag holding accessibility at 90.
4. **(template, infra)** Set long cache lifetimes on immutable assets. `https://images.flood-fixers.com/brand/hero.webp` returns no `Cache-Control` header and `cf-cache-status: DYNAMIC`, so Lighthouse falls back to a 4-hour heuristic TTL and counts ~182KB re-downloaded per page. `/_astro/_slug_.qvOpSyL3.css` returns `public, max-age=14400, must-revalidate` despite having a content hash in the filename. Add a Cloudflare Cache Rule for `images.flood-fixers.com/*` and `/_astro/*` setting `public, max-age=31536000, immutable`.
5. **(template, LCP)** Add `fetchpriority="high"` to the hero `<img>` in the non-home templates and give them the responsive treatment home already has. The homepage hero uses `hero-fleet.webp` with `srcset` plus `fetchpriority="high"` and passes `lcp-discovery-insight`; the services hub, both service landings, the service area and contact templates all render `<img src="https://images.flood-fixers.com/brand/hero.webp" loading="eager">` with no `srcset`, no `sizes` and no priority hint, and all five fail the `priorityHinted` checklist item. Re-encoding `hero.webp` at a higher compression factor recovers up to 218KB on `/contact/` alone.

## Notes / caveats

- **Audit scope change.** `/service-areas/san-diego-ca/` was in last month's URL set but is a `301` redirect to `https://flood-fixers.com/`. DataForSEO follows redirects silently, so last month's san-diego-ca row was a second measurement of the homepage rather than a distinct page. San Diego is the primary city and has no service-area page in `plan/url-plan.json`. The service-area slot was reassigned to `/service-areas/chula-vista-ca/` (HTTP 200, self-canonical, present in the url-plan). The redirect itself looks deliberate (San Diego intent is served by the homepage) and is not counted as a defect. Because the slot changed pages, it has no prior-run counterpart and is excluded from per-URL deltas.
- **Desktop only.** Lighthouse 13.4.0 ran with `formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`, `rttMs=40` (verified in the report `configSettings`). Mobile would typically score 10-20 performance points lower. These are not mobile-first scores.
- **MCP transport.** The DataForSEO MCP wrapper in this CI run exposes only the generic `api_request` tool, with no `on_page_lighthouse` or `on_page_instant_pages` wrappers. The audit hit the identical REST endpoints (`on_page/lighthouse/live/json` and `on_page/instant_pages`) with the same credentials. Same data source, same engine. Total API cost this run: $0.066.
- **Schema false negative.** instant_pages returned `has_micromarkup=false` on all 6 URLs, but direct HTML inspection found valid JSON-LD everywhere: home has Organization, WebSite, LocalBusiness; the services hub and contact add FAQPage and BreadcrumbList; service landings carry Service, LocalBusiness, FAQPage, BreadcrumbList; the service area carries LocalBusiness, FAQPage, BreadcrumbList. Not treated as a missing-schema issue.
- **Load-time artifact.** instant_pages flagged `high_loading_time` on `/services/flood-damage-restoration/` (dom_complete 3299ms) during its crawl. Three follow-up fetches measured TTFB 33-47ms. Treated as a cold-cache artifact and not recorded as an issue.
- **404 handling verified.** Three nonexistent paths (`/service-areas/definitely-not-a-real-city-zz/`, `/this-page-does-not-exist-zz/`, `/services/not-a-service-zz/`) all return a hard `404` with a real "Page Not Found" template. No soft-404 fallback.
- **Link crawling not performed.** instant_pages audits one URL at a time and does not follow outlinks, so page-level 4xx/5xx link checks were out of scope. All 6 audited URLs returned 200 themselves.
- **Alt text at 100%.** All images across the 6 pages carry a non-empty `alt`. No `no_image_alt` findings.
- **CLS watch item.** `/service-areas/chula-vista-ca/` posted 0.049, the highest of the set and roughly ten times the service landings. Still well inside the 0.1 good threshold, so no action this month, but worth watching if the area template picks up more above-the-fold content.
- **Diff methodology.** Resolved issues are diffed against this run's complete failing-audit set, so they are reliable. New issues use a conservative rule: an ID counts as new only if it appears nowhere in the prior run, because last month persisted only the top 5 audits per URL. Under a raw per-URL diff, `image-delivery-insight` would have looked new on both service landings; it was already failing on 4 other URLs last month, so it is a ranking shuffle and was suppressed. This run also stores the full failing-audit ID list per URL so next month's diff will not need the workaround.
