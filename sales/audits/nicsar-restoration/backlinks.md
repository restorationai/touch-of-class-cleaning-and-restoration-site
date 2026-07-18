# Backlink Profile Analysis: nicsar-restoration.com
**Date:** 2026-07-12
**Tier:** 0 (Common Crawl + site crawl only — no Moz, no Bing)
**Overall Confidence:** Low (0.50, domain-level CC only)
**Health Score:** INSUFFICIENT DATA (1 of 7 scoring factors have data sources)

---

## Credential Check

| Service | Status |
|---------|--------|
| Common Crawl | Available (public) |
| Moz API | Not configured |
| Bing Webmaster | Not configured |
| DataForSEO | Not available |

---

## Domain Age & Registration

| Field | Value | Source |
|-------|-------|--------|
| Registrar | NameCheap, Inc. | whois (authoritative) |
| Current Registration Date | 2025-02-18 | whois (authoritative) |
| Registry Expiry | 2027-02-18 | whois (authoritative) |
| DNS | Cloudflare (bayan.ns / rose.ns) | whois (authoritative) |
| Earliest Wayback Capture | 2023-07-22 | Wayback CDX (0.95) |
| WordPress datePublished | 2021-04-28 | Live schema parse (0.95) |

**Critical domain history flag:** The whois shows a February 2025 registration date, but Wayback Machine has captures from July 2023 and the WP schema records content published April 2021. This is consistent with one of two scenarios:

1. The domain was registered earlier under a different registrar and transferred/re-registered to NameCheap in Feb 2025 (most likely — the 2023 Duda-platform captures show `SiteAlias: '2f0e4b7c'` and `NotificationSubDomain: 'nicsar-restoration'`, confirming the business operated this domain since at least 2021-2023 on Duda, then migrated to WordPress).
2. Less likely: a domain drop and re-registration, which would reset any link equity.

**Implication:** The domain is likely 4-5 years old in practice (since ~2021), not the 17 months the current whois suggests. This is a meaningful difference for local SEO trust signals. The platform migration (Duda → WordPress/Elementor) is confirmed by the 2023 Wayback showing Duda JS globals and the current live site using wp-content paths with Elementor Pro.

---

## Common Crawl Domain Graph

| Metric | Value | Source |
|--------|-------|--------|
| In CC crawl (2026 Q1) | Yes | Common Crawl graph (0.50) |
| In PageRank rankings | No — below threshold | Common Crawl graph (0.50) |
| Harmonic centrality | Not ranked | Common Crawl graph (0.50) |
| Referring domains (CC sample) | 0 found in graph | Common Crawl graph (0.50) |
| CC release used | cc-main-2026-jan-feb-mar | Common Crawl graph (0.50) |

**Interpretation (per validator info):** "Below ranking threshold" does not mean zero authority. It means the domain's inbound link volume falls below the floor CC uses to include a domain in its PageRank/harmonic centrality rankings. For a local restoration SAB with ~4 years of history, this is consistent with a thin backlink profile — not evidence of a penalty or of no links at all.

CC index searches across crawls CC-MAIN-2025-18 and CC-MAIN-2025-13 returned no captures for the domain root, and CC-MAIN-2024-51 / CC-MAIN-2024-38 returned 503 (index temporarily unavailable). The domain was not indexed in those specific CC crawl indexes at query time.

---

## Site Architecture (Live Crawl)

| Signal | Value | Source |
|--------|-------|--------|
| Platform | WordPress + Elementor Pro | wp-content paths (0.95) |
| Total sitemap pages | 36 | Sitemap parse (0.95) |
| Blog / news section | None detected | Internal link parse (0.95) |
| H1 on homepage | None found | Live HTML parse (0.95) |
| Social profiles linked | None | Live HTML parse (0.95) |
| Phone | (773) 220-6751 | Live HTML parse (0.95) |
| Google Maps embed | Present | Live HTML parse (0.95) |
| Schema: Organization | Present (no LocalBusiness type) | Live schema parse (0.95) |
| Schema: Review/AggregateRating | Not present | Live schema parse (0.95) |

**Page content breakdown (36 pages):**
- City service pages (water damage): ~14 cities (Hoffman Estates, Schaumburg, Carpentersville, Barrington, Barrington Hills, Lemont, Mokena, Westmont, Hinsdale, Burr Ridge, Homer Glen, Naperville, Bolingbrook, Orland Park, Tinley Park, Downers Grove)
- City service pages (fire damage): same ~14 cities
- Insurance claims pages: 2 (Hoffman Estates, Carpentersville)
- Storm/flood restoration: 2 (Hoffman Estates, Carpentersville)
- Core pages: Home, About, Services, Reviews, Contact, Gallery

The site has a wide city-page strategy but no blog, no case studies, and no linkable editorial content.

---

## Citation Search (Best-Effort)

CC index searches for "nicsar" mentions on major citation directories (Yelp, BBB, YellowPages, Angi, Thumbtack) returned no results in the CC-MAIN-2025-18 index. This does not confirm absence — citation pages are often behind JS or not captured in a given CC snapshot — but it is consistent with a thin or incomplete citation profile.

| Directory | CC Result |
|-----------|-----------|
| yelp.com | No captures found |
| bbb.org | No captures found |
| yellowpages.com | No captures found |
| angi.com | No captures found |
| thumbtack.com | No captures found |

---

## Backlink Health Score

**Score: INSUFFICIENT DATA**

Only 1 of 7 scoring factors has any data source available at Tier 0:

| Factor | Weight | Data Available | Source |
|--------|--------|---------------|--------|
| Referring domain count | 20% | No (CC: below threshold, 0 found) | CC (0.50) |
| Domain quality distribution | 20% | No | None |
| Anchor text naturalness | 15% | No | None |
| Toxic link ratio | 20% | No | None |
| Link velocity trend | 10% | No | None |
| Follow/nofollow ratio | 5% | No | None |
| Geographic relevance | 10% | No | None |

A numeric score with this data density would be misleading. Reporting INSUFFICIENT DATA per Tier 0 rules.

---

## Expected Link Profile for a Local Restoration SAB (What's Likely Missing)

For a water/fire restoration company in Hoffman Estates IL (~4 years old), the expected backlink profile should include:

**Standard citation base (typically 40-80 listings for a 4-year-old local business):**
- Google Business Profile (inherent, not a backlink but foundational)
- Yelp, BBB, YellowPages, Angi, HomeAdvisor / Thumbtack
- IICRC member directory (if certified — restoration-specific authority signal)
- Illinois state contractor license directories
- Chicagoland chamber of commerce listings
- Local homeowner association resource pages
- Insurance company preferred vendor directories (Allstate, State Farm, Farmers local pages)

**What this site is likely missing (structural diagnosis):**
1. **No linkable assets** — Zero blog, no guides ("what to do after a pipe burst"), no before/after galleries as standalone shareable pages. Nothing earns organic editorial links.
2. **No H1 on homepage** — Both an on-page SEO issue and a signal that the page structure may confuse crawlers assessing content relevance.
3. **No social profiles** — No Facebook, Instagram, or Nextdoor presence linked from site. These platforms often serve as indirect citation signals and Nextdoor in particular drives local referral links.
4. **Schema gap** — Organization schema present but no LocalBusiness type, no AggregateRating schema, no Service schema. This is a missed structured data opportunity.
5. **City-page overreach vs. link acquisition** — 14+ city pages with no inbound links pointing to any of them. City pages without topical authority or backlinks are thin-content risk.
6. **No industry associations** — IICRC, RIA (Restoration Industry Association), or NADCA membership pages are high-authority, restoration-specific link sources that most competitors in the Chicagoland area would have.

---

## Validator Output

Status: PASS (0 errors, 0 warnings, 1 info)
Info: Domain in CC crawl but not in rankings — correctly reported as "below threshold," not "no authority."

---

## Recommendations (Priority Order)

| Priority | Action | Estimated Impact |
|----------|--------|-----------------|
| Critical | Get Moz API key (free tier: 2,500 rows/month) to unlock DA/PA, spam score, and referring domain count — current data is too thin for any scoring | Unlocks Tier 1 analysis |
| High | Audit citation completeness — manually check Yelp, BBB, Angi, HomeAdvisor for existing listings and NAP consistency | Local pack ranking |
| High | Add LocalBusiness schema with AggregateRating and telephone to homepage | Trust signal |
| High | Fix missing H1 on homepage | On-page + crawl signal |
| Medium | Create one linkable asset (minimum: "What to Do Immediately After Water Damage" guide) | Earns first editorial links |
| Medium | Apply for IICRC or RIA directory listing if certified | High-authority niche link |
| Medium | Build Nextdoor Business Page for Hoffman Estates | Local citation + referral |
| Low | Add social profiles (Facebook minimum) and link from site | Citation completeness |

**Do not run seo-backlinks again at Tier 0 for this domain** — the data ceiling is hit. Upgrade to Tier 1 (Moz free key) before re-auditing.

---

## Data Freshness Notes

- Common Crawl: cc-main-2026-jan-feb-mar (quarterly cadence, ~3-6 months lag)
- Wayback CDX: Near-realtime archive index
- Live site crawl: 2026-07-12 (today)
- whois: Authoritative as of 2026-07-12

---

## Cross-Skill Recommendations

- For E-E-A-T and content quality assessment of the 36 pages: run `/seo content nicsar-restoration.com`
- For crawlability, Core Web Vitals, and the H1 absence: run `/seo technical nicsar-restoration.com`
- For toxic link pattern deep-dive (when Moz data is available): load `references/backlink-quality.md`
