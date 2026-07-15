# Onsite Audit — Flood Fixers — 2026-07-15

**Live origin audited:** https://flood-fixers.com (apex)
**Site verdict:** green
**URLs audited:** 6
**Prior audit:** 2026-07-06 (amber)
**Audit form factor:** desktop (see caveats — not mobile-first)
**Lighthouse engine:** 13.4.0

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99 | +1 |
| Accessibility | 91 | +1 |
| Best Practices | 100 | 0 |
| SEO | 100 | 0 |

Pages by verdict: green: 6, amber: 0, red: 0, error: 0

Every audited page is green this month. The site recovered from last month's amber: the homepage accessibility score climbed from 86 to 93, clearing the one page that was dragging the rollup down. No page dropped in any category.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| / | home | green | 97 | 93 | 100 | 100 | 1.3s | 0.012 |
| /services/ | services-hub | green | 99 | 90 | 100 | 100 | 0.9s | 0.002 |
| /services/water-damage-restoration/ | service-landing | green | 100 | 90 | 100 | 100 | 0.8s | 0.002 |
| /services/flood-damage-restoration/ | service-landing | green | 100 | 90 | 100 | 100 | 0.8s | 0.003 |
| /service-areas/san-diego-ca/ | service-area | green | 99 | 91 | 100 | 100 | 0.9s | 0.003 |
| /contact/ | contact | green | 97 | 91 | 100 | 100 | 1.2s | 0.023 |

All Core Web Vitals are in Google's "good" band (LCP under 2.5s, CLS under 0.1, TBT 0ms across the board on desktop).

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `link-name` | 6 | medium | The footer email link renders as `<a href="mailto:">` with no address and no text, so it has no accessible name. Populate the footer email variable (business contact address) in the layout partial. One fix clears this on every page. |
| `color-contrast` | 5 | medium | Breadcrumb links use `text-dark/50` (50% opacity), which fails WCAG AA contrast. Darken the breadcrumb link token to full-opacity `text-dark` or a `text-dark/70`+ shade. On `/contact/`, the form hint text `text-white/40` also fails. |
| `has_render_blocking_resources` | 6 | low | One script plus one stylesheet render-block on every page. Impact is negligible at current scores (all pages 97-100 perf); defer the non-critical script in the layout if convenient, but not urgent. |
| `relative_og_image` | 2 | low | On the two service-landing pages, `og:image` is a relative path (`/images/services/...webp`). Social and AI-answer share previews need an absolute URL. Prefix with the `images.flood-fixers.com` origin in the service-landing template. |
| `cache-insight` | 6 | low | Lighthouse flags short cache lifetimes on some static assets. Low impact; address via Cloudflare cache headers if doing a perf pass. |

## Money page alerts

None. All money pages (home, services-hub, both service-landings, contact) are green this run.

## Regressions vs prior audit

**Verdict transitions:**
- `/` (home) went amber to green. Accessibility recovered from 86 to 93. This is the improvement that flipped the whole site green.

**Core Web Vitals watch:**
- `/contact/` LCP rose from 0.87s to 1.24s (+373ms). Still well inside the "good" band and the page is green, but it crossed the +200ms flag threshold. Likely lab-run variance; worth a glance next month to confirm it is not a trend (contact is a conversion page).

**New issues this month:** none on the on-page checks. On-page issue IDs are identical to the prior run.

**Issues resolved since last audit:** no on-page issue IDs dropped, but the homepage accessibility deficit that caused last month's amber is resolved.

Note: Lighthouse issue-ID diffing is not possible this month. The prior run deferred `full_data` and stored empty `lighthouse_issues` arrays, so the `link-name` and `color-contrast` findings below are newly captured detail, not confirmed month-over-month regressions. They are almost certainly pre-existing.

## Recommended next actions (priority order)

1. **(template, accessibility, high value)** Fix the footer email link. It is currently `<a href="mailto:">` with an empty address and no link text, so it is both broken (clicks open a blank email) and inaccessible on all 6 pages. Set the footer email to the business contact address in the layout partial. This clears `link-name` site-wide and restores a working contact path.
2. **(template, accessibility)** Raise breadcrumb link contrast. Change the `text-dark/50` breadcrumb link class to a full-contrast token (e.g. `text-dark` or `text-dark/70` and darker on hover). This clears `color-contrast` on the 5 interior pages. While in the file, bump the `/contact/` form hint text off `text-white/40`.
3. **(template, service-landing)** Make `og:image` absolute on the service-landing template. Replace the relative `/images/services/{slug}.webp` with the full `https://images.flood-fixers.com/services/{slug}.webp` URL so social and AI share previews resolve.
4. **(per-page)** Trim the homepage meta description from 171 to 160 characters or fewer so it is not truncated in SERP snippets. Current text ends on the phone number, which can be safely shortened.
5. **(per-page)** Add roughly 50-100 words to `/services/` (currently 750 words vs the 800 archetype target). A short intro paragraph above the service grid covers the gap.

## Notes / caveats

- **Audit executed via DataForSEO REST, not the MCP wrapper.** The DataForSEO MCP server did not register its tools in this CI run. The audit hit the identical DataForSEO OnPage endpoints (`on_page/lighthouse/live/json` and `on_page/instant_pages`) directly using the configured credentials. Same data source and same Lighthouse engine; results are equivalent.
- **Desktop-only scoring.** Verified in the Lighthouse report config: `formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`. Mobile scores would typically run 10-20 performance points lower. These are not mobile-first numbers. Mobile auditing is pending an MCP/wrapper update that exposes form factor.
- **Lighthouse 13.4.0 audit IDs.** This engine version reports insight-style IDs (`cache-insight`, `image-delivery-insight`, `render-blocking-insight`, `lcp-discovery-insight`, `network-dependency-tree-insight`) instead of the older opportunity IDs (`render-blocking-resources`, etc.). The IDs recorded are the real IDs emitted by this engine.
- **Schema is present and healthy.** DataForSEO `instant_pages` reported `has_micromarkup=false` on all pages, but direct HTML inspection confirmed valid JSON-LD on every URL (Organization, WebSite, LocalBusiness, Service, FAQPage, BreadcrumbList as appropriate). The DataForSEO flag is a false negative for JS-rendered JSON-LD and was not treated as a missing-schema issue. No money-page schema alert was raised.
- **Broken-link checks not run.** `instant_pages` audits a single URL and does not crawl outbound links, so broken internal/external link detection was out of scope this run. All 6 audited pages returned HTTP 200 for themselves.
- **INP/TBT.** TBT is 0ms on all pages (desktop, light JS). INP is null because the lab Lighthouse run does not emit interaction-to-next-paint. Neither value was invented.
