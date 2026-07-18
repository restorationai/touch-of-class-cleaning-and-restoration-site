# Full SEO Audit — nicsar-restoration.com

**Business:** Nicsar Restoration Contractors Inc. — water/fire damage restoration (SAB), Hoffman Estates, IL, serving ~14 Chicagoland suburbs
**Audit date:** 2026-07-12 · **Pages crawled:** 36/36 (all HTTP 200) · **Platform:** WordPress 7.0.1 + Elementor Pro + Yoast, behind Cloudflare
**Detailed per-category findings:** `technical.md`, `content.md`, `schema.md`, `local.md`, `geo.md`, `performance.md`, `sxo.md`, `backlinks.md`, `dataforseo.md` (same folder)

---

## Executive Summary

### SEO Health Score: 40 / 100

| Category | Weight | Score | Weighted |
|---|---|---|---|
| Technical SEO | 22% | 51 | 11.2 |
| Content Quality | 23% | 34 | 7.8 |
| On-Page / SXO | 20% | 49 | 9.8 |
| Schema / Structured Data | 10% | 18 | 1.8 |
| Performance (CWV, lab-estimated) | 10% | 35 | 3.5 |
| AI Search Readiness | 10% | 28 | 2.8 |
| Images | 5% | 55 | 2.8 |
| **Total** | | | **≈ 40** |

Supplementary (unweighted): Local SEO 34/100 · Backlinks: insufficient data (thin profile, 43 referring domains, low quality)

### The headline

Nicsar already holds **local pack position #3 and organic ~#5** for "water damage restoration hoffman estates il" — a real, monetizable foothold. But the position is held together with tape: **2 Google reviews vs. 79 and 219 for the two competitors above them**, a **phone button hidden on mobile**, a city page **serving the wrong city's content**, and **three different cities listed across their own GBP/BBB properties**. The site is not broken so much as unfinished — most critical fixes are hours, not months.

### Top 5 Critical Issues

1. **Mobile click-to-call is broken.** Header phone button carries `elementor-hidden-mobile elementor-hidden-tablet` classes; city-page sidebar phone is static text, not a `tel:` link. Emergency searches are overwhelmingly mobile — this loses calls *today*.
2. **Review gap is existential for the map pack.** 5.0★ but only 2 reviews vs 79 (Zero Water) and 219 (Mold Genius). The #3 pack position will not survive any competitor review velocity.
3. **`/fire-damage-restoration-barrington-hills-il/` serves Lemont content** — title, H1, schema, body all say Lemont. The city-substitution step never ran. Meanwhile no real Lemont fire page exists.
4. **NAP chaos across owned properties:** GBP address = Hoffman Estates, GBP *description* = "Located in Carpentersville, IL", BBB listing = Plainfield, IL with primary category "Kitchen Remodel". Three cities, one business.
5. **Homepage has zero H1** (hero heading is an H3 via Elementor) **and its title tag exactly duplicates the Hoffman Estates water damage page**, cannibalizing the #1 money keyword.

### Top 5 Quick Wins (≤1 day total)

1. Un-hide the header phone on mobile + wrap sidebar numbers in `tel:` links (~1 hr)
2. Fix GBP description city (5 min) + correct the BBB address/category (~30 min)
3. Set the hero heading widget to H1 on the homepage; rewrite homepage title as a brand/services-hub title (~30 min)
4. Batch-add meta descriptions to all 14 fire city pages in Yoast (~30 min)
5. Enable Cloudflare APO or install WP Rocket — cache-miss TTFB drops from 2.7s to ~0.2s sitewide (~1 hr)

---

## Live Market Position (DataForSEO, 2026-07-12)

**"water damage restoration hoffman estates il"** (geo: Hoffman Estates):
- Local pack: 1) Zero Water Restoration 5.0/79 · 2) The Mold Genius 4.9/219 · 3) **Nicsar 5.0/2**
- Organic: ServPro, A Plus Restoration, Yelp, Excel Dryout, **Nicsar city page (#5)**, Procare, BBB, ZeroMold…
- Nicsar city pages are **not visible in the top 10 for Schaumburg or Naperville** despite pages existing (templated content isn't differentiating).
- SERP pattern: every ranking independent states a concrete response time ("30-minute response", "arrives within 60 minutes"). Nicsar says "Fast Response" with no number, anywhere.

**GBP:** claimed; correct primary category (Water damage restoration service) + fire secondary; 24/7 hours; only 5 photos; description contradicts address; website field points to `www.` while the site canonicals to non-www (2-hop redirect chain www→https→non-www).

---

## Technical SEO (51/100)

**Working:** clean HTTPS, consistent self-canonicals on all 36 pages, valid Yoast sitemap (36/36 coverage), SSR HTML, sane URL structure, `index,follow` everywhere.

**Critical/High:**
- Barrington Hills fire page = Lemont content (also in schema + OG tags)
- Homepage: 0 H1; insurance-claims + storm-flood pages: 2 H1s each
- Homepage title duplicates the Hoffman Estates water page title exactly
- No HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy (all one Cloudflare Transform Rule)
- `readme.html` publicly discloses WordPress version (also in generator meta)
- www→non-www chains through 2 hops (and GBP links to www)
- 14 fire pages: null meta descriptions; 2 titles >70 chars truncating

**Medium:** IndexNow off in Yoast; external Quicksand font; uncached HTML on most pages.

---

## Content Quality (34/100) — E-E-A-T composite 43/100

- **Doorway-page pattern (Critical):** the 28 city pages share **88–92% identical text** city-to-city (measured). All 28 share one verbatim testimonial ("Michael R."), an identical 5-step process, identical FAQ answers, the same 4 stock photos, and a Google Map pinned to Hoffman Estates regardless of target city. Hidden form field always posts the homepage ID.
- **Thin trust pages:** gallery 26 words, contact 36 (no address, no hours), reviews 161 (3 hardcoded testimonials), services hub 254 — with "Read More" buttons linking to *Carpentersville* URLs that aren't in the sitemap (stale links from the old site).
- **E-E-A-T voids:** no street address anywhere on-site; no named humans; "Certified Team" with no certifying body (IICRC never mentioned); no license numbers; "20+ years" claim buried in an icon widget.
- **Emergency-intent gap:** "24/7" and "emergency" appear nowhere in body copy; no response-time promise — the single most-cited stat in the category.

---

## On-Page / SXO (49/100)

- Page-type mismatch: pages are informational; the SERP rewards conversion-first local pages (tappable phone, response time, verifiable proof above the fold).
- Persona scores: 2am emergency homeowner **42/100** (broken mobile call path), insurance-claim researcher 64/100, commercial property manager 43/100 (no commercial page at all).
- 5-field quote form is the only CTA pattern ("Request A Quote" — no emergency language).
- FAQ content exists on every city page but is rendered as H6 headings with 20–25-word answers and no markup — invisible to rich results and AI.

---

## Schema / Structured Data (18/100)

- Yoast @graph (WebSite/WebPage/Organization/BreadcrumbList) is valid but the Organization node is a stub: no telephone, address, geo, hours, areaServed, sameAs; not typed LocalBusiness.
- Reviews page: orphaned `Rating` microdata with no parent Review, `worstRating: 0` — unparseable.
- Missing entirely: LocalBusiness/EmergencyService, Service (×28 pages), FAQPage, AggregateRating.
- **Ready-to-paste JSON-LD generated** in `schema.md`: (a) LocalBusiness w/ full NAP + geo + 24/7 + 14-city areaServed + hasMap, (b) Service template for city pages, (c) FAQPage from existing on-page Q&A.

---

## Performance (est. 30–40/100 mobile; PSI quota-limited, lab estimate)

- **No page caching**: `cf-cache-status: DYNAMIC`, no caching plugin, no APO → 2.7s TTFB on misses (0.2s on hits).
- 32 render-blocking stylesheets; Font Awesome loaded **6×** (minified + unminified via Elementor & UAEL).
- jQuery + jquery-migrate synchronous in `<head>`.
- LCP hero is a JS-injected Elementor slideshow (undiscoverable by preloader); logo has `fetchpriority=high` but isn't the LCP.
- Two ~400KB JPEG slides (`full-restotation-services.jpg` 408KB, `restore-after-water-damage.jpg` 382KB) need WebP.
- Quicksand from Google Fonts with `display=auto` (FOIT) and 18 variants; no preconnect.
- reCAPTCHA v3 loads on all 36 pages, undeferred.

## Images (55/100)

Alt text present on all `<img>` tags (good); but 2 unoptimized 400KB JPEGs, 8 gallery images without width/height (CLS), gallery has zero descriptive text/captions, hero images not preloadable.

---

## AI Search Readiness (28/100)

- **robots.txt misfire (Cloudflare managed rules):** blocks retrieval bots **GPTBot (ChatGPT Search: 5/100) and ClaudeBot (Claude: 5/100)** while NOT blocking the `anthropic-ai` training crawler it presumably wanted stopped. Google AI Overviews unaffected (uses Googlebot; Google-Extended only gates Gemini training). PerplexityBot allowed (40/100) but Perplexity leans on Yelp — and Nicsar has **no Yelp listing found**.
- No llms.txt. FAQ answers too short/unstructured to cite. Zero sourced statistics. Footer Facebook icon has **no href**; no third-party footprint for AI systems to triangulate.
- Fix: remove the GPTBot + ClaudeBot Disallow blocks (keep training-bot blocks + Content-Signal), add llms.txt, mark up + expand FAQs, create/claim Yelp.

---

## Local SEO (34/100)

- GBP claimed w/ correct categories and 24/7 hours (the fundamentals are right).
- Reviews 10/100 — the defining gap (2 vs 79/219).
- Citations: BBB A+ but wrong city (Plainfield) and wrong category (Kitchen Remodel); no Yelp/Angi/HomeAdvisor/Nextdoor confirmed; no IICRC directory.
- Only 5 GBP photos; no GBP posts observed.
- No LocalBusiness schema anywhere (see Schema).

## Backlinks (insufficient data tier — Common Crawl + DataForSEO domain level)

- 88 backlinks / 43 referring domains, mostly blog/CMS-type with spam-signal TLDs (.party, .world, .fyi); domain rank 149; below Common Crawl centrality threshold.
- **Domain age correction:** whois says Feb 2025 but Wayback shows the site live in July 2023 on **Duda** (later migrated to WordPress) with content dated 2021 — a 4–5-year-old business web presence, positive for trust once citations are cleaned up.
- No blog/guides/linkable assets → structural link ceiling.

---

## Method notes & limitations

- PSI API hit keyless quota (429) — performance is lab/static estimate, no CrUX field data. GSC/GA4 not connected (no owner access — prospect audit).
- SERP snapshot is a single desktop query per keyword via DataForSEO; rank tracking over time requires geo-grid setup.
- One inter-agent conflict resolved: city-page duplication was *measured* at 88–92% shared text (content agent) — the local agent's "genuinely differentiated" impression was based on spot-reading and is superseded.
