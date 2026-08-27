# Refresh Recommender - Flood Fixers - 2026-08-27

**Origin:** https://flood-fixers.com (apex)
**URLs evaluated:** 120
**Actions queued:** 0
**GSC enabled:** false (v1 - sitemap + page-date scoring only)

## Summary by action

| Action | Count |
| --- | ---: |
| refresh | 0 |
| audit_then_decide | 0 |
| request_indexing | 0 (deferred to v2) |
| fix_canonical | 0 (deferred to v2) |

## Action: refresh content

No URLs qualified. Nothing on the site has crossed the 305-day aging threshold.

## Action: audit then decide

No URLs qualified. Every candidate resolved a confident date via json_ld_date_modified or sitemap_lastmod, and no flag combinations fired, so there is no ambiguous signal to hand-inspect.

## Freshness distribution

The whole property is inside its first content cycle. Layer 1 inspected 120 URLs and fetched HTML for all 120 with 0 failures.

| Bucket | Count |
| --- | ---: |
| 0-59 days (fresh) | 120 |
| 60-304 days | 0 |
| 305-364 days (aging) | 0 |
| 365+ days (stale_12mo) | 0 |

Oldest URLs on the site, none close to actionable:

| URL | Age (d) | Date source |
| --- | ---: | --- |
| / | 59 | sitemap_lastmod |
| /about/ | 59 | sitemap_lastmod |
| /accessibility/ | 59 | sitemap_lastmod |

Of the 120 candidates, 16 map to money-page archetypes (1 home, 1 contact, 1 service-areas-hub, 14 service-area) and the remainder are service-area-service pages, blog posts, and legal/about pages. Even the oldest money page (the homepage, 59 days, sitemap_lastmod) sits 246 days short of the aging trigger.

## Notes

- URLs skipped because already in content-queue: none. Nine candidate URLs do appear in content-queue.json, but all nine are status published or written, not an active status in queued/in_progress/needs_review. The 15 genuinely active queued items are unpublished and carry no post_url, so there is no System 2 collision this cycle.
- URLs where date extraction failed: none. 96 URLs resolved via json_ld_date_modified and 24 via sitemap_lastmod; failed_html_count is 0.
- Coverage gap: v1 sees publication and modification dates only. It cannot see whether any of these 120 URLs are actually indexed, whether Google selected a different canonical, or whether a page is bleeding impressions and clicks. A page could be fully deindexed today and this layer would still report it as fresh. GSC v2 closes that gap (see docs/system-4-v2-activation.md).
- Coverage observation: 14 url-plan pages are not in the sitemap and so were never scored, including /services/ and all six service-landing pages (water-damage-restoration, flood-damage-restoration, burst-pipe-repair, basement-flooding-cleanup, reconstruction, general-contracting). All 14 are still plan status 'planned'. That is a build backlog item, not a refresh item, but it does mean the site's highest-commercial-intent pages are currently outside this layer's view.

## Recommended next actions (top 5)

1. Take no refresh action on flood-fixers this cycle. Every one of the 120 live URLs is between 0 and 59 days old against a 305-day aging threshold; opening any of them for a rewrite now would churn content Google has barely finished crawling.
2. Build the six planned service-landing pages, starting with /services/water-damage-restoration/ and /services/flood-damage-restoration/. They are the primary commercial targets in url-plan.json, they are currently absent from the sitemap, and the 78 live service-area-service pages are linking into a hub structure that is not yet complete.
3. Activate GSC for this client so the next monthly run can score indexing coverage and demand. With 120 URLs published inside 60 days, the real near-term risk is bulk "Discovered - currently not indexed" on the service-area-service tail, which v1 is structurally blind to. Follow docs/system-4-v2-activation.md.
4. Let the three content-queue items sitting at status 'written' (/blog/how-to-tell-if-you-have-water-damage-behind-walls/, /blog/what-happens-if-water-damage-is-left-untreated/, /blog/how-to-dry-out-a-flooded-house/) finish moving to published in System 2. They are already live URLs in the sitemap at ages 45, 42, and 24 days, so the queue status is lagging the site state and is worth reconciling before it confuses a future dedupe pass.
5. Re-run this recommender on the normal monthly cadence, one day after the next System 3 audit. The earliest any flood-fixers URL can trip the aging flag is roughly 2027-03-06, when the 2026-07-04 cutover cohort reaches 305 days, so expect quiet runs until then unless GSC v2 lands first and introduces demand-side flags.
