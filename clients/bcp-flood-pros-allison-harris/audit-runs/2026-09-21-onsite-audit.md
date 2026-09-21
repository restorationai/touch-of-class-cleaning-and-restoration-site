# Onsite Audit - FIX Restoration - 2026-09-21

**Live origin audited:** https://staging.rankai-bcp-flood-pros-allison-harris.pages.dev (staging)
**Site verdict:** red
**URLs audited:** 6
**Prior audit:** first audit for this client, no comparison data
**Form factor:** desktop only (Lighthouse 13.4.0, cpuSlowdownMultiplier=1)

## Environment caveat: read before acting on SEO numbers

This run audited the Cloudflare Pages staging preview, not the apex domain. Pages
injects `x-robots-tag: noindex` on every `*.pages.dev` response, and that was
verified present on this run. The Lighthouse `is-crawlable` audit therefore fails
on all 6 URLs and drags the SEO category down to 69 everywhere.

**The SEO score of 69 is inconclusive this run: it is a staging noindex artifact,
not a site defect.** Re-audit after apex cutover to get a real SEO number. Every
verdict below was computed from performance, accessibility and best practices only.

Separately, Lighthouse ran desktop only. The DataForSEO wrapper for this endpoint
does expose `for_mobile`, but this run was kept on desktop to stay comparable with
the rest of the fleet's audit history. Mobile performance would typically land
10 to 20 points lower. Do not read these numbers as mobile-first scoring.

## Site rollup

| Metric | Score | Δ vs prior |
| --- | ---: | ---: |
| Performance | 99.7 | n/a |
| Accessibility | 94.8 | n/a |
| Best Practices | 100.0 | n/a |
| SEO | 69.0 (inconclusive) | n/a |

Pages by verdict: green: 0, amber: 0, red: 6, error: 0

Every page is red for one reason: a high-severity canonical defect that affects the
whole site. The raw performance and best-practices engineering on this build is
excellent (performance 99 to 100, best practices 100, LCP under 0.9s, TBT 0ms
everywhere). This is not a slow site. It is a correctly built site pointed at the
wrong domain.

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS | TBT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red | 99 | 93 | 100 | 69* | 0.8s | 0.016 | 0ms |
| `/services/` | services-hub | red | 99 | 95 | 100 | 69* | 0.8s | 0.003 | 0ms |
| `/services/water-damage-restoration/` | service-landing | red | 100 | 95 | 100 | 69* | 0.8s | 0.004 | 0ms |
| `/services/fire-damage-restoration/` | service-landing | red | 100 | 95 | 100 | 69* | 0.8s | 0.004 | 0ms |
| `/service-areas/provo-ut/` | service-area | red | 100 | 95 | 100 | 69* | 0.8s | 0.004 | 0ms |
| `/contact/` | contact | red | 100 | 96 | 100 | 69* | 0.8s | 0.027 | 0ms |

`*` SEO excluded from verdict, staging noindex artifact. INP was not reported by
Lighthouse on any URL (no interaction trace in a lab run), so it is null in state.

## Template-level issues (fix once, lift many pages)

| Issue | Affected URLs | Severity | Recommended fix |
| --- | ---: | --- | --- |
| `canonical` | 6 | high | Set the build's site URL to `https://fixofutah.com`. Currently `https://bcp-flood-pros-allison-harris.invalid`. |
| `color-contrast` | 6 | high | Darken `.text-primary` footer links and the `.btn-accent` CTA to reach 4.5:1. |
| `is-crawlable` | 6 | high | No action. Staging noindex artifact, disappears at apex. |
| `image-delivery-insight` | 6 | medium | Serve `/images/logo.webp` at its display size. 37.4KB wasted on every page. |
| `lcp-discovery-insight` | 5 | medium | Add `fetchpriority="high"` to the hero `<img>` in the layout. |
| `has_micromarkup_errors` | 5 | medium | Fix FAQPage / BreadcrumbList schema validation errors. |
| `network-dependency-tree-insight` | 5 | low | Informational. Longest request chain is 155ms, no action needed. |

`render-blocking-insight` also fires on all 6 URLs (`/_astro/_slug_.Bjlw1eTu.css`,
about 9KB, roughly 50ms) but is capped out of the per-URL top 5 by higher-severity
findings. At 50ms it is not worth a code change.

## Money page alerts

All five money pages came back red. The cause is identical on each, so treat this as
one fix, not five.

- **`/`** (home) - canonical is `https://bcp-flood-pros-allison-harris.invalid/`, so
  the page cannot be indexed once apex goes live. Accessibility 93, the lowest of the
  set, from a `p.text-sm text-dark/60` body paragraph at 4.45:1 plus the shared footer
  link failures.
- **`/services/`** (services-hub) - same canonical defect. Accessibility 95. Heaviest
  image payload of the set at 534KB across 13 images, 93KB of that recoverable.
- **`/services/water-damage-restoration/`** (service-landing) - same canonical defect.
  Also the only URL DataForSEO flagged `high_loading_time`, and its on-page score is
  90.39 against 97.44 everywhere else. The click-to-call hero button fails contrast at
  2.45:1.
- **`/services/fire-damage-restoration/`** (service-landing) - same canonical defect.
  `fire-damage-restoration.webp` is 177KB with 52.7KB recoverable, the single largest
  image on the audited set.
- **`/contact/`** (contact) - same canonical defect. Highest CLS of the set at 0.027
  (still well inside the 0.1 threshold, no action needed). Two FAQ schema answers
  contain unrendered markdown bold around the phone number.

## Regressions vs prior audit

First audit for this client. No comparison data, no regression detection performed.
This run establishes the baseline that next month's audit will diff against.

## Recommended next actions (priority order)

1. **(blocker, template, affects all 124 pages)** Set the site build's base URL from
   `https://bcp-flood-pros-allison-harris.invalid` to `https://fixofutah.com` and
   redeploy. This one placeholder value is poisoning: every page's `<link rel="canonical">`,
   `og:url` and `og:image`, the `Sitemap:` line in `robots.txt`, `sitemap-index.xml`,
   all 129 URLs inside `sitemap-0.xml`, and every JSON-LD `@id`, `url` and
   `BreadcrumbList` `item` value. If apex cutover happens before this is fixed, Google
   will see 124 pages all canonicalized to a domain that does not resolve, and will
   index none of them. Note this is not a staging artifact: peer clients still on their
   `*.pages.dev` preview (`arch-enviornmental-group-llc`, `california-restoration-west`)
   already emit their correct apex canonical, so this client's build config was simply
   never populated. The client record already carries `domain: fixofutah.com` and
   `cutover_prep` is complete with 57 redirects mapped, so the value to use is known.

2. **(money page, template, all 6 pages)** Darken the footer link color. `.text-primary`
   renders `#ee4305` on `#ffffff` at 3.85:1, below the 4.5:1 WCAG AA minimum. It hits
   the footer phone link, the email link, the `/services/` link and the `/emergency/`
   link on all six pages. Swap those links to the existing `primary-700` token rather
   than changing the brand `#ee4305` itself, so the hero and headings keep their color.
   While in the same file, bump the breadcrumb `a.text-dark/50` (`#9c8b85` on white,
   3.25:1 at 12px) to `text-dark/70` or darker. That fixes 5 pages in the same pass.

3. **(money page, conversion-critical)** Fix the `.btn-accent` click-to-call button.
   White text on `#f38c08` is 2.45:1, the worst contrast failure on the site, and it is
   the primary phone CTA in the hero on `/services/water-damage-restoration/`,
   `/services/fire-damage-restoration/` and `/service-areas/provo-ut/`. Do not darken
   the accent background, it is brand. Switch the button label to the existing
   `dark` token `#38160a`, which clears AA against `#f38c08` comfortably.

4. **(template, 5 pages)** Fix the schema validation errors. `has_micromarkup_errors`
   fires on exactly the 5 URLs that render FAQPage plus BreadcrumbList, and the homepage,
   which renders neither, is clean. That isolates the defect to those two templates. Most
   likely candidate is the final `BreadcrumbList` `ListItem`, which omits `item`. Google
   permits that, but DataForSEO's validator flags it, so add the self URL to the last
   crumb to satisfy both. Separately, two FAQ answers on `/contact/` contain literal
   markdown bold, for example `**(801) 930-9750**`, which will render asterisks in a
   rich result. Strip markdown before injecting answer text into JSON-LD. Re-verify with
   Google's Rich Results Test after the fix in step 1 lands, since the `@id` values
   change too.

5. **(template, page weight)** Serve `/images/logo.webp` at its display size. It is
   39.7KB with 37.4KB recoverable on all six pages, making it the single most wasteful
   asset on the site. Then compress the two worst hero images:
   `fire-damage-restoration.webp` (177KB, 52.7KB recoverable) and `hero-bg.webp` on
   `/contact/` (93.8KB, 45.4KB recoverable). Finally, add `fetchpriority="high"` to the
   hero `<img>` in the layout. Lighthouse's `lcp-discovery-insight` reports
   `priorityHinted: false` on 5 of 6 pages, and the hero is the LCP element on each.
   This is polish, not a fix: performance is already 99 to 100 on desktop. It matters
   because mobile was not measured this run and image weight is what hurts mobile most.

## Notes / caveats

- SEO scores are not usable this run. Re-audit after apex cutover to `fixofutah.com`
  to get real SEO numbers and to confirm step 1 landed.
- Desktop-only scoring. Mobile was not measured. Given the image weight noted in step 5,
  mobile performance is the main unknown on this site.
- Lighthouse 13.4 reports performance findings as weight-0 `*-insight` diagnostic audits.
  Several show a raw score of 0 while the performance category still scores 99 to 100.
  They are recorded at medium and low severity in the state file rather than high, so the
  report does not overstate them. Nothing here indicates a slow site.
- The rendered `tel:` links resolve to `(435) 602-8416` while the raw HTML and the schema
  `telephone` property carry `(801) 930-9750`. This is the intentional call-tracking
  number swap script, not a NAP inconsistency. No action.
- `frame` fires on `/service-areas/provo-ut/`. That is the Google Maps service-area embed
  and is expected. The same page's `cache-insight` finding is entirely third-party Google
  Maps resources with a 24 hour TTL that we do not control. No action on either.
- All 6 URLs returned HTTP 200. No broken internal links, no broken external links, no
  broken resources, no mixed content, no duplicate titles or descriptions, and no
  duplicate or missing `<h1>` anywhere. Image alt coverage passed on all 6. Titles ran
  51 to 59 characters and meta descriptions 110 to 156, all inside target. Word counts
  met or exceeded the url-plan target on 5 of 6 pages; `/` came in at 1192 against a
  1200 target, an 8 word shortfall that is not worth acting on.
- URL selection used Mode B, auto-derived from `plan/url-plan.json`, because no
  `audit-urls.txt` exists for this client. No `service-area` page carries `primary: true`,
  and the plan contains no page for the HQ city of American Fork at all, since the
  homepage covers it. Per the fallback rule the first area slug was used, giving
  `/service-areas/provo-ut/`. Two `service-landing` slots went to the joint top-priority
  pages at 9.0, water damage and fire damage. Mold remediation also sits at 9.0 and was
  not audited.
- Pre-flight deviation, logged and continued: the client record has `status: "onboarding"`,
  not `"active"`. The audit proceeded because `build_status` is `pushed_main`, so the site
  is live and auditable, and because this matches existing fleet practice, where most
  clients under `clients/` carrying an `audit` block are also `onboarding`.
