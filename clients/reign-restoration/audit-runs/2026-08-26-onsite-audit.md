# Onsite Audit - Reign Restoration - 2026-08-26

**Live origin audited:** https://reign-restoration.com (apex)
**Site verdict:** amber
**URLs audited:** 6
**Prior audit:** first audit for this client - no comparison data
**Form factor:** desktop only (see caveats)

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.8 | n/a |
| Accessibility | 95.3 | n/a |
| Best Practices | 98.0 | n/a |
| SEO | 100.0 | n/a |

Pages by verdict: green: 2, amber: 4, red: 0, error: 0

The technical baseline here is genuinely strong. Every page scores 99-100 on performance,
100 on SEO, LCP is under 0.9s everywhere, CLS is under 0.01, and total blocking time is 0ms
across all six pages. On-page is equally clean: DataForSEO returns onpage_score 100 on every
URL, with no broken links, no broken resources, correct self-referencing canonicals, exactly
one H1 per page, no duplicate titles or descriptions, 100% image alt coverage, and word counts
that beat the url-plan targets on all six pages.

The amber verdict comes from two template defects, not from a weak site.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT | Words |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | amber | 100 | 96 | 100 | 100 | 0.81s | 0.004 | 0ms | 1661 |
| `/services/` | services-hub | amber | 99 | 95 | 96 | 100 | 0.82s | 0.003 | 0ms | 836 |
| `/services/water-damage-restoration/` | service-landing | green | 100 | 95 | 100 | 100 | 0.76s | 0.005 | 0ms | 1963 |
| `/services/fire-damage-restoration/` | service-landing | green | 100 | 95 | 100 | 100 | 0.76s | 0.005 | 0ms | 1774 |
| `/service-areas/rockwall-tx/` | service-area | amber | 100 | 95 | 96 | 100 | 0.77s | 0.005 | 0ms | 1198 |
| `/contact/` | contact | amber | 100 | 96 | 96 | 100 | 0.78s | 0.008 | 0ms | 692 |

INP was null on every page. Lighthouse lab runs do not produce INP without user interaction,
so this is expected, not a gap in the data.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `og_image_broken_host` | 4 of 6 | medium | `sites/reign-restoration/src/lib/brand.ts:25` has `imagesBase: "https://images.None"`. Set it to `https://images.reign-restoration.com` and redeploy. |
| `color-contrast` | 6 of 6 | medium | Footer links use brand yellow `#f2b623` on `#ffffff` at 1.82:1. Darken the footer link color or put the footer on the dark surface. |
| `image-delivery-insight` | 6 of 6 | medium | `/images/logo.png` is an 88.8 KB PNG with 88.5 KB flagged as wasted. Convert to WebP and resize to displayed dimensions. |
| `errors-in-console` | 3 of 6 | medium | Same root cause as `og_image_broken_host` - the browser tries to fetch `https://images.None/brand/hero.webp` and the host does not resolve. Fixed by the same one-line change. |
| `lcp-discovery-insight` | 3 of 6 | low | Service-landing hero images are missing `fetchpriority="high"`. |
| `render-blocking-insight` | 6 of 6 | low | `/_astro/_slug_.DQbX6XYm.css` (8.8 KB) blocks first paint by ~54ms. Not worth acting on at current scores. |
| `cache-insight` | 6 of 6 | low | Cloudflare's own injected `email-decode.min.js` carries a 2-day TTL. Not under our control. |
| `network-dependency-tree-insight` | 6 of 6 | low | Critical chain is document then `page.js` / `_slug_.css`, all inside 170ms. No action. |
| `no_image_title` | 6 of 6 | low | Images have no `title` attribute. Alt text is at 100%, and `title` is not an SEO or accessibility requirement. No action recommended. |

## Money page alerts

- **`/`** (home) - verdict: amber. Lighthouse is perfect (100/96/100/100). Two meta defects:
  `og:image` and `twitter:image` both resolve to `https://images.None/brand/hero.webp`, and the
  meta description is 172 chars against a 70-160 target. Every share of the homepage on Facebook,
  LinkedIn, iMessage, or Slack renders with no thumbnail.
- **`/services/`** (services-hub) - verdict: amber. Same broken `og:image`. Best Practices is 96
  rather than 100 purely because of the resulting console network error.
- **`/contact/`** (contact) - verdict: amber. Same broken `og:image`. Best Practices 96 for the
  same reason. Performance is 100 and LCP is 0.78s, so the conversion path itself is healthy.

`/service-areas/rockwall-tx/` is also amber on the same `og:image` defect but is not classified
as a money page.

## Regressions vs prior audit

First audit for this client. No comparison data. This run establishes the baseline that next
month's audit will diff against.

## Recommended next actions (priority order)

1. **(template, money pages, highest impact)** Fix `imagesBase` in the site's brand config.
   `sites/reign-restoration/src/lib/brand.ts:25` reads `imagesBase: "https://images.None"` while
   `canonicalUrl` on line 11 is correctly `https://reign-restoration.com`. A Python `None`
   f-stringed into the token at build time via `scripts/build_site.py:325`
   (`f"https://images.{domain}"`) when the client record had no domain. `BaseLayout.astro:37`
   uses `${brand.imagesBase}/brand/hero.webp` as the og:image fallback, so every page without a
   per-page hero inherits the dead URL. Confirmed broken on `/`, `/services/`, `/about/`,
   `/service-areas/`, `/blog/`, `/contact/`, and all 16 service-area pages. The two service
   landings escape it only because they set a per-service image. Set the value to
   `https://images.reign-restoration.com`, or rerun token resolution now that the domain is
   populated, then redeploy. One line, roughly 130 pages fixed, and it clears the
   `errors-in-console` finding at the same time.
2. **(template, accessibility)** Raise footer link contrast. `#f2b623` on `#ffffff` measures
   1.82:1 and the license link `#fae5b2` on `#ffffff` measures 1.24:1, against a WCAG AA minimum
   of 4.5:1. Affected elements are the footer phone `(214) 304-0621`, the email link, the
   `24/7 Emergency` link, and the `#MRC2276` license link. These are the primary conversion
   links in the footer, so this is a conversion issue as much as a compliance one. Either
   introduce a darker yellow for text on white (around `#8a6410` clears AA) or move the footer
   onto the dark `#0a0b0e` surface where the brand yellow already passes.
3. **(template, performance)** Replace `/images/logo.png`. It is 88.8 KB and Lighthouse flags
   88.5 KB of that as wasted, meaning it is served far larger than it renders. It loads in the
   header on every page. Convert to WebP at the displayed dimensions. Also note
   `sites/reign-restoration/src/lib/brand.ts:30` still carries a `switch to images.{domain} at
   production cutover` comment, and cutover completed 2026-08-13, so the logo path is overdue
   for the same treatment as item 1.
4. **(money page)** Shorten the homepage meta description from 172 to under 160 chars. Current
   text ends `Licensed, insured, IICRC-certified. Call (214) 304-0621.` Dropping `insured, ` and
   one adjective brings it in range without losing the phone number or the certification signal.
5. **(per-page, low)** Add `fetchpriority="high"` to the hero image on the service-landing
   template. Lighthouse reports `fetchpriority=high should be applied: false` on both audited
   service landings. LCP is already 0.76s so the gain is small, but it is a one-attribute change
   in a template that serves six pages.

## Notes / caveats

- **Desktop-only scoring.** Lighthouse 13.4.0 ran with `formFactor: desktop`,
  `cpuSlowdownMultiplier: 1`, `throughputKbps: 10240`. Mobile scores typically land 10-20
  performance points lower. Do not present these numbers to the client as mobile-first.
- **Client record status mismatch.** `clients/reign-restoration.json` has `status: "onboarding"`,
  not `"active"`. The methodology's pre-flight expects `active`. Since `build_status` is
  `pushed_main` and `apex_cutover.completed_at` is 2026-08-13, the site is live and the audit
  ran against the apex. Someone should reconcile the status field.
- **Apex, not staging.** `curl -sI https://reign-restoration.com/` returned no `x-robots-tag:
  noindex`, so the staging SEO-exclusion correction does not apply. SEO counted toward the
  verdict and scored 100 on all six pages.
- **DataForSEO schema detection is a false negative.** `has_micromarkup` came back `false` on
  every page. Direct inspection of the HTML found 3 to 5 valid JSON-LD blocks per page
  (Organization, WebSite, LocalBusiness, Service, FAQPage, BreadcrumbList) with zero parse
  errors. DataForSEO's check looks for microdata and RDFa attributes and does not see JSON-LD.
  Schema is fine. Not reported as a finding.
- **Two issue IDs are not vendor IDs.** `og_image_broken_host` and `meta_description_too_long`
  are marked `source: "manual_verification"` in the state file. Neither Lighthouse nor
  DataForSEO exposes a check for these conditions, and inventing a plausible-looking vendor
  audit ID would be worse than labelling them honestly. Every other ID in this report is a real
  Lighthouse audit ID or a real DataForSEO on-page check key.
- **`low_content_rate` on the homepage** reflects a 9.03% text-to-HTML ratio. With 1661 words
  against a 1200-word target, this is a markup-density artifact of the component-heavy homepage,
  not thin content. No action.
- **`frame` on `/service-areas/rockwall-tx/`** is the embedded map. Expected.
- **The `images.None` defect is not unique to this client.** `sites/life-savers-restoration-llc`,
  `sites/restorationxpress`, `sites/dry-county-restoration`, and `sites/quality-contracting-inc`
  all carry the same `https://images.None` value in their README token tables. Worth a fleet-wide
  sweep rather than six separate one-line fixes. Out of scope for this audit.
- **Run cost:** $0.0606 (6 Lighthouse at $0.005, 6 instant_pages at $0.0051). Under the
  $0.30-0.50 target because the raw DataForSEO API was called directly over curl with responses
  written to disk, so full Lighthouse detail came free with the base call rather than needing a
  second `full_data` pass.
- **Tooling note.** The DataForSEO MCP server no longer exposes named tools like
  `on_page_lighthouse`; it presents a single generic `api_request`. This run used
  `/v3/on_page/lighthouse/live/json` and `/v3/on_page/instant_pages` over curl with the
  `DATAFORSEO_USERNAME` / `DATAFORSEO_PASSWORD` env credentials. That path also exposes a
  `for_mobile` parameter, so mobile auditing is now available whenever the methodology is
  updated to want it.
