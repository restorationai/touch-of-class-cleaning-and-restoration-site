# Refresh Recommender - Flood Fixers - 2026-09-28

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

No URLs qualified. The oldest URL on the site is 91 days old, 214 days short of the 305-day aging threshold.

## Action: audit then decide

No URLs qualified. Every candidate resolved a date via json_ld_date_modified (97) or sitemap_lastmod (23), and layer 1 raised no flags (flag_counts is empty), so there is no ambiguous signal to hand-inspect.

## Freshness distribution

Layer 1 inspected 120 URLs and fetched HTML for all 120 with 0 failures.

| Bucket | Count |
| --- | ---: |
| 0-59 days | 62 |
| 60-304 days | 58 |
| 305-364 days (aging) | 0 |
| 365+ days (stale_12mo) | 0 |

Oldest URLs on the site, none close to actionable:

| URL | Age (d) | Date source |
| --- | ---: | --- |
| / | 91 | sitemap_lastmod |
| /about/ | 91 | sitemap_lastmod |
| /accessibility/ | 91 | sitemap_lastmod |
| /blog/ | 91 | sitemap_lastmod |
| /blog/basement-flooding-prevention/ | 91 | json_ld_date_modified |

Of the 120 candidates, 13 map to money-page archetypes in url-plan.json (1 home, 1 contact, 11 service-area). The oldest money pages (the homepage and the Encinitas and Escondido service-area pages) are 91 days old. The rest are 73 service-area-service pages, 9 planned blog posts, legal/about/hub pages, and 20 live URLs not present in url-plan.json (15 blog posts plus /case-studies/, /certifications/, /embed/estimate/, /emergency/, /reviews/), which were scored as non-money pages.

## Notes

- URLs skipped because already in content-queue: none. 15 candidate URLs appear in content-queue.json, but all are status published (12) or written (3), not queued/in_progress/needs_review. The 6 queued items have no post_url yet, so there is no System 2 collision this cycle.
- URLs where date extraction failed: none. 97 URLs resolved via json_ld_date_modified and 23 via sitemap_lastmod; failed_html_count is 0.
- Coverage gap: v1 sees publication and modification dates only. It cannot see whether these 120 URLs are indexed, whether Google chose a different canonical, or which pages rank on page 2 for real demand (striking_queries) or earn poor CTR (low_ctr). GSC v2 closes that gap (see docs/system-4-v2-activation.md).
- Coverage observation: 133 url-plan.json entries are status planned and absent from the sitemap, so they were never scored. That includes /services/ and all 7 service-landing pages (water-damage-restoration, flood-damage-restoration, burst-pipe-repair, basement-flooding-cleanup, reconstruction, general-contracting, water-cleanup), 16 service-area pages (Oceanside, Vista, San Marcos, La Mesa, Santee, Poway, National City, Spring Valley, Temecula, and others), and their service-area-service children. This is a build backlog, not a refresh item.

## Recommended next actions (top 5)

1. Take no refresh action on flood-fixers this cycle. All 120 live URLs are 0 to 91 days old against a 305-day aging threshold; rewriting any of them now would churn pages Google is still settling.
2. Build /services/water-damage-restoration/ and /services/flood-damage-restoration/ first, then the other 5 planned service-landing pages and the /services/ hub. They are the highest-intent targets in url-plan.json and are still status planned, so the 73 live service-area-service pages are linking into an incomplete hub structure.
3. Activate GSC for this client (docs/system-4-v2-activation.md). With 120 URLs all under 92 days old, the realistic near-term risk is "Discovered - currently not indexed" across the service-area-service tail, and the biggest upside is striking_queries on the 15 blog posts; v1 cannot see either.
4. Reconcile the 3 content-queue items at status written that are already live: /blog/how-to-tell-if-you-have-water-damage-behind-walls/ (77 days), /blog/what-happens-if-water-damage-is-left-untreated/ (74 days), and /blog/how-to-dry-out-a-flooded-house/ (56 days). Mark them published in System 2 so future dedupe passes read the queue correctly. This is the second run flagging them.
5. Add the 20 live but unplanned URLs (for example /emergency/, /reviews/, /blog/how-much-does-water-damage-restoration-cost/) to url-plan.json with archetypes, so /emergency/ in particular is classified correctly when money-page priority starts to matter. The earliest any URL can trip the aging flag is about 2027-04-30 (305 days after the 2026-06-29 launch cohort), so expect quiet runs until then unless GSC v2 lands first.
