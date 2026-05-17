# Onsite Audit — National Restoration Construction — 2026-05-17

**Live origin audited:** `https://staging.rankai-narestco.pages.dev` (staging)
**Site verdict:** red (URGENT)
**URLs audited:** 6
**Prior audit:** first audit for this client (no comparison data)

> ## CRITICAL CAVEAT — read before acting
>
> **SEO=61 on every page is a staging environment artifact, NOT a real issue.**
> Cloudflare Pages preview deployments inject `X-Robots-Tag: noindex` on all
> `*.pages.dev` subdomains. Lighthouse correctly flags this as "Page is blocked
> from indexing" → drives SEO score from ~95 (expected) to 61.
>
> The site itself is healthy: `robots.txt` allows all, all canonicals point to
> the production apex `https://narestco.com/`, structured data is in place.
>
> **Re-audit after apex cutover for true SEO scores.** Today's SEO findings
> should be treated as inconclusive until the apex is live.

> ## Secondary caveats
>
> - DataForSEO Lighthouse MCP runs **desktop only** (no `form_factor` parameter
>   exposed). Mobile scores would typically be 10-20 points lower for
>   performance. Treat performance numbers as a ceiling.
> - Per-URL "top 5 failing audits" requires a `full_data: true` re-call
>   (5-15MB JSON each). Skipped this run to avoid context overflow.
>   The orchestrator script can fetch on demand for any flagged URL.

## Site rollup

| Metric | Score |
| --- | ---: |
| Performance | 97.3 |
| Accessibility | 83 |
| Best Practices | 80.8 |
| SEO | 61 (artificially deflated — see caveat) |

Pages by verdict: 0 green, 0 amber, 6 red, 0 error

## Per-page scores

| URL | Archetype | Verdict | Perf | A11y | BP | SEO | LCP | CLS |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | home | red (URGENT) | 90 | 77 | 77 | 61 | 2.0s | 0.006 |
| `/services/` | services-hub | red (URGENT) | 99 | 87 | 100 | 61 | 0.9s | 0.006 |
| `/services/water-damage-restoration/` | service-landing | red (URGENT) | 99 | 82 | 77 | 61 | 0.8s | 0.003 |
| `/services/flood-damage-restoration/` | service-landing | red (URGENT) | 98 | 82 | 77 | 61 | 0.9s | 0.003 |
| `/service-areas/federal-way-wa/` | service-area | red (URGENT) | 99 | 82 | 77 | 61 | 0.8s | 0.003 |
| `/contact/` | contact | red (URGENT) | 99 | 88 | 77 | 61 | 0.8s | 0.028 |

## Template-level issues (fix once, lift many pages)

| Issue ID | Affected URLs | Severity | Description |
| --- | ---: | --- | --- |
| `title_length_over_65` | 6 | medium | Title is 75 chars (over 65) |
| `render_blocking_resources` | 6 | medium | 2 render-blocking resource(s) (likely the layout font CSS + analytics script) |

## Money page alerts

All money pages currently flag as `red` due to the staging noindex caveat above.
Once that is resolved (apex cutover), the realistic verdicts based on the rest
of the data are:

- **`/`** (home) — likely amber. Performance 90 (good), accessibility 77
  (medium — homepage has more interactive elements than other pages, likely a
  missing form-label or aria-label). Total page weight is 5.3MB (heavy hero +
  gallery); LCP 2.0s borderline.
- **`/services/`** (services-hub) — likely green. Already 99/87/100 on the
  three non-SEO categories.
- **`/services/water-damage-restoration/`** (service-landing) — likely amber.
  Best-practices 77; og:image is a relative URL (some social platforms reject).
- **`/services/flood-damage-restoration/`** (service-landing) — likely amber.
  Best-practices 77.
- **`/contact/`** (contact, money page) — likely amber. Best-practices 77;
  CLS=0.028 is borderline (good is ≤0.1, but worse than other pages).

## Recommended next actions (priority order)

1. **(blocker) Cut narestco.com apex over to Cloudflare Pages and re-audit.**
   The current staging audit cannot give you true SEO scores. Without this,
   most of the recommendations below are inconclusive. The apex cutover is
   already a planned step in the Rank AI onboarding.

2. **(template, all 6 pages) Shorten page titles to ≤ 65 characters.** Current
   titles are 71-75 chars and will truncate in Google SERPs. Fix in the Astro
   layout/templates so all archetypes inherit the tighter limit. Example:
   change "National Restoration Construction | Restoration Services in Federal
   Way, WA" (75ch) → "Restoration Services Federal Way | NRC" (38ch).

3. **(template, all 6 pages) Defer or async non-critical render-blocking
   resources.** Every page has 1 blocking script + 1 blocking stylesheet.
   On a Pages-CDN-served site this costs ~400-600ms LCP. Audit the layout
   `<head>` and move analytics/3rd-party scripts to `defer` or `async`.

4. **(homepage) Reduce homepage page weight.** 5.3MB total is roughly 3× the
   other pages. Likely the gallery section eagerly loads all images. Add
   `loading="lazy"` to gallery images below the fold and check that the hero
   WebP is the only eager image.

5. **(water-damage-restoration page) Fix og:image to absolute URL.** Currently
   `/images/services/water-damage-restoration.webp` — should be
   `https://images.narestco.com/services/water-damage-restoration.webp`.
   LinkedIn, Pinterest, and some Discord embeds reject relative og:image.

## What this audit did NOT cover (out of scope by design)

- Content quality / E-E-A-T (that's System 4 — refresh-recommender, pending)
- Keyword ranking analysis (System 4 + GSC integration, pending)
- Backlink profile (use `claude-seo:seo-backlinks` if needed)
- Local SEO / GBP grid (use `claude-seo:seo-maps` if needed)

## Next scheduled audit

30 days out: ~2026-06-01 (or sooner if apex cutover happens)
