# Onsite Audit - Arch Enviornmental Group LLC - 2026-09-21

**Live origin audited:** https://staging.rankai-arch-enviornmental-group-llc.pages.dev (staging)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client, no comparison data
**Form factor:** desktop only (Lighthouse 13.4.0)

> **Environment caveat - SEO score is inconclusive this run.**
> This audit ran against the Cloudflare Pages staging preview, because the client
> record has no `apex_cutover.completed_at`. The preview returns
> `x-robots-tag: noindex`, which fails the Lighthouse `is-crawlable` audit and
> deflates the SEO category to **69 on all 6 URLs**. That is a staging artifact,
> not a site defect. The SEO score is recorded as-is in the state file but is
> **excluded from every verdict** in this report, which is computed from
> performance, accessibility and best practices only. SEO status is
> `inconclusive - re-audit after apex cutover`.
>
> Note also that the apex (`https://archenviroservice.com`) already responds 200
> and does **not** carry the noindex header, so the cutover record is what is
> missing here, not the live site.

> **Desktop-only scoring.** The DataForSEO Lighthouse wrapper runs desktop
> (`formFactor=desktop`, `cpuSlowdownMultiplier=1`, `throughputKbps=10240`).
> Mobile would typically land 10-20 performance points lower. Do not read these
> numbers as mobile-first.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 95 | n/a |
| Accessibility | 96 | n/a |
| Best Practices | 100 | n/a |
| SEO | 69 (inconclusive, excluded) | n/a |

Pages by verdict: green: 3, amber: 3, red: 0, error: 0

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 89 | 100 | 100 | 69 | 0.74s | 0.003 | 268ms |
| `/services/` | services-hub | amber | 94 | 95 | 100 | 69 | 0.99s | 0.002 | 137ms |
| `/services/mold-inspection-testing/` | service-landing | green | 96 | 95 | 100 | 69 | 1.05s | 0.004 | 0ms |
| `/services/indoor-air-quality-testing/` | service-landing | amber | 99 | 95 | 100 | 69 | 0.84s | 0.004 | 0ms |
| `/service-areas/fresno-ca/` | service-area | green | 95 | 95 | 100 | 69 | 0.98s | 0.015 | 164ms |
| `/contact/` | contact | green | 99 | 96 | 100 | 69 | 0.90s | 0.006 | 0ms |

INP is null on every page. Lighthouse lab runs do not emit interaction-to-next-paint; it needs field data.

This is a healthy site. Core Web Vitals pass comfortably everywhere on desktop:
LCP is under 1.1s on all 6 pages and CLS is under 0.02 on all 6. Best practices
is a clean 100 across the board. No broken links, no broken resources, no mixed
content, no duplicate titles or descriptions, no duplicate content, one `h1` per
page, and 100 percent image alt coverage. The amber verdicts below are driven by
two narrow template defects and three overlong meta descriptions, not by
anything structural.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `image-delivery-insight` | 6 | high | `/images/logo.png` is a 1080x1080 PNG (108KB) rendered at 96x96 in the sitewide header. Export a 192x192 WebP (2x retina) or an SVG. Saves ~107KB on every page. |
| `render-blocking-insight` | 6 | medium | `/_astro/_slug_.*.css` (8.8KB) blocks first paint for 59-101ms. Inline the above-the-fold rules and load the rest with a non-blocking `<link rel="preload" as="style">` swap. |
| `color-contrast` | 5 | medium | Breadcrumb links use `text-dark/50`, which composites to `#888c93` on `#ffffff` at 12px for a 3.37:1 ratio against the 4.5:1 WCAG AA floor. Change the token to `text-dark/65` (`#646973`, 5.51:1). `/60` is the bare minimum at 4.68:1; `/65` leaves headroom. |
| `lcp-discovery-insight` | 5 | medium | The hero image is not discoverable in the initial HTML scan. Add `fetchpriority="high"` and a `<link rel="preload" as="image">` for the hero in the layout, and make sure the hero is not `loading="lazy"`. |
| `network-dependency-tree-insight` | 6 | low | Critical request chain depth. Largely resolved by the render-blocking and LCP-preload fixes above. |
| `total-blocking-time` / `max-potential-fid` | 3 | medium | Only material on `/` (268ms TBT). See the money page note below. |
| `description_length_out_of_range` | 3 | medium | Three meta descriptions exceed the 160-char SERP truncation point. See recommendations 4 and 5. |
| `largest-contentful-paint`, `speed-index`, `first-contentful-paint` | 6 / 5 / 3 | low | Near-pass scores (0.84-0.99). No action needed; these clear once the image and render-blocking fixes land. |
| `is-crawlable` | 6 | low | **Not a real issue.** Staging `x-robots-tag: noindex` artifact. Do not "fix". Resolves at apex cutover. |

## Money page alerts

- **`/` (home) - amber.** Performance 89, the only page below 90. Total Blocking
  Time is 268ms, the worst on the site, and max-potential-FID is 170ms. The page
  loads `/images/logo.png` (108KB for a 96px slot), `/images/team.webp` (187KB,
  89KB of it wasted on oversizing) and `/images/hero-bg.webp` (190KB). Fixing the
  logo plus resizing `team.webp` to its rendered box recovers ~199KB on the most
  important page on the site. Meta description is also 237 chars.
- **`/services/` (services-hub) - amber.** Scores are fine (94/95/100). Amber is
  driven by the 176-char meta description plus the breadcrumb contrast failure.
  Also the heaviest page for images: 17 images totalling 1.05MB, with
  `hero-bg.webp` wasting 98KB on oversizing and the `-480w` service thumbnails
  wasting 12-14KB each. Content is 768 words against an 800-word plan target.
- **`/services/indoor-air-quality-testing/` (service-landing) - amber.** Scores
  are the best on the site (99/95/100). This page is amber **only** because its
  meta description is 166 chars, six over the threshold. Lowest-effort amber to
  clear on the site.

## Regressions vs prior audit

First audit for this client. No prior `onsite-audit.json` existed, so regression
detection was skipped. This run is the baseline that next month compares against.

## Recommended next actions (priority order)

1. **(template, high impact)** Replace `/images/logo.png` with a 192x192 WebP or
   an SVG. It is a 1080x1080 108KB PNG rendered into a 96x96 header slot on all
   6 audited pages, and 109,906 of its 110,781 bytes are wasted. This is the
   single biggest win available and it is one file.
2. **(money page)** On `/`, resize `/images/team.webp` (187KB, 89KB wasted) to its
   rendered dimensions and add `fetchpriority="high"` plus an image preload for
   `hero-bg.webp`. Home is the only page under performance 90 and carries the
   site's worst TBT at 268ms.
3. **(template, accessibility)** Change the breadcrumb link class from
   `text-dark/50` to `text-dark/65` in the breadcrumb component. The `/50`
   opacity composites `text-dark` (`#111827`) over white to `#888c93`, a 3.37:1
   ratio at 12px that fails WCAG AA on 5 of 6 pages. `/65` composites to
   `#646973` at 5.51:1. This is a one-token change and it lifts accessibility
   from 95 to an expected 100 sitewide, since `color-contrast` is the only
   failing accessibility audit on every affected page.
4. **(per-page)** Trim the `/` meta description from 237 to under 160 chars. It is
   currently truncated in SERPs, losing the "Certified inspectors, accredited lab
   analysis. Call (559) 296-2088" call to action that sits at the end.
5. **(per-page, trivial)** Trim the `/services/` description from 176 chars and
   `/services/indoor-air-quality-testing/` from 166 chars to under 160. That
   clears both pages to green.

Deliberately **not** on this list: anything framed as "fix SEO". The SEO score of
69 is a staging noindex artifact. The action that resolves it is the apex cutover
plus a re-audit, which is tracked below rather than as an onsite fix.

## Notes / caveats

- **Cut over the apex domain and re-audit.** This is the prerequisite for any
  trustworthy SEO number on this client. The apex already serves 200 without a
  noindex header, but `clients/arch-enviornmental-group-llc.json` has no
  `apex_cutover.completed_at`, so this audit was pinned to staging per the
  methodology. Once cutover is recorded, re-run to get real SEO scores. Expect
  SEO to jump from 69 to roughly 100 with no code change, since `is-crawlable`
  is the only failing SEO audit.
- **Two DataForSEO flags were investigated and rejected as false positives.**
  `instant_pages` returned `checks.canonical=false` and
  `checks.has_micromarkup=false` on all 6 URLs. Both were checked against the
  served HTML. Every page has a canonical (pointing at the apex, which is correct
  and intended for a staging preview: `checks.canonical` means "is
  self-canonical", not "has a canonical tag") and every page carries valid JSON-LD
  spanning LocalBusiness, Organization, WebSite, Service, FAQPage, BreadcrumbList,
  AggregateRating and PostalAddress. Neither was reported as a finding. Schema and
  canonical coverage on this site are good.
- **Length and word-count findings are derived metrics.** DataForSEO exposes
  `meta.description_length`, `meta.title_length` and
  `meta.content.plain_text_word_count` as numbers but has no native pass/fail
  check for them, so those issue IDs are Rank AI derived rather than upstream
  check IDs. All Lighthouse IDs quoted in this report are genuine Lighthouse
  13.4.0 audit IDs.
- **Client status is `onboarding`, not `active`.** The methodology's pre-flight
  expects `status == "active"`. The audit proceeded because `build_status` is
  `pushed_main` and all 6 URLs returned 200, so the site was fully auditable, but
  flagging the precondition mismatch for the operator.
- `/service-areas/fresno-ca/` embeds a Google Maps iframe. It is the only page
  with a `frame` flag and the only page with a third-party caching finding
  (`cache-insight`, ~30KB from `maps.googleapis.com` with a 24h TTL). Third-party
  cache headers are not under our control. It is also the highest-CLS page at
  0.015, still well inside the 0.1 threshold. No action needed.
- All 6 Lighthouse calls and all 6 instant_pages calls returned status 20000. No
  URL errored. Total API cost for this run was approximately $0.07, under the
  $0.30-0.50 target.
- Titles are healthy sitewide: all 6 fall within the 30-65 char target (35-56).
- Word counts beat plan targets on 5 of 6 pages, sometimes substantially
  (`/services/mold-inspection-testing/` is 1886 words against an 1100 target).
  Only `/services/` is short, by 32 words.
