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

No URLs qualified. The oldest URL on the site is 91 days old against a 305-day aging threshold and a 365-day stale threshold.

## Action: audit then decide

No URLs qualified. Every candidate resolved a date via json_ld_date_modified or sitemap_lastmod, and no flags fired, so there is no ambiguous signal to hand-inspect.

## Freshness distribution

Layer 1 inspected 120 URLs and fetched HTML for all 120 with 0 failures.

| Bucket | Count |
| --- | ---: |
| 0-59 days | 62 |
| 60-304 days | 58 |
| 305-364 days (aging) | 0 |
| 365+ days (stale_12mo) | 0 |

Oldest URLs, none close to actionable:

| URL | Age (d) | Date source |
| --- | ---: | --- |
| / | 91 | sitemap_lastmod |
| /contact/ | 91 | sitemap_lastmod |
| /service-areas/carlsbad-ca/ | 91 | sitemap_lastmod |
| /service-areas/escondido-ca/water-damage-restoration/ | 91 | json_ld_date_modified |
| /service-areas/escondido-ca/burst-pipe-repair/ | 91 | json_ld_date_modified |

13 candidates map to money-page archetypes (1 home, 1 contact, 11 service-area). The oldest, the homepage at 91 days (sitemap_lastmod), is 214 days short of the aging trigger.

## Notes

- URLs skipped because already in content-queue: none. 15 candidate URLs appear in content-queue.json, but all are status published (12) or written (3). The 6 active queued items (commercial water damage, ceiling water damage repair, ceiling leak, water spots on ceiling, condo insurance, apartment flooded rights) have no post_url yet, so there is no System 2 collision.
- URLs where date extraction failed: none. 97 URLs resolved via json_ld_date_modified and 23 via sitemap_lastmod; failed_html_count is 0.
- Coverage gap: v1 sees publication and modification dates only. It cannot see indexing status, Google-selected canonicals, or impression/click decay. A deindexed page would still read as fresh here. GSC v2 closes that gap (see docs/system-4-v2-activation.md).
- Coverage observation: url-plan.json has grown since the 2026-08-27 run and now lists 133 planned pages not in the sitemap, including /services/, all 7 service-landing pages, 16 new service-area pages (Oceanside, Vista, San Marcos, La Mesa, Santee, Poway, Temecula and others) with their service-area-service children, and /terms/. Separately, 20 live URLs (15 blog posts plus /case-studies/, /certifications/, /embed/estimate/, /emergency/, /reviews/) have no url-plan entry; none are money-page archetypes by URL pattern except possibly /emergency/, which is fresh regardless.

## Recommended next actions (top 5)

1. Take no refresh action on flood-fixers this cycle. All 120 live URLs are 0 to 91 days old; rewriting any of them now would churn content Google has only recently crawled.
2. Build the planned service-landing pages, starting with /services/water-damage-restoration/ and /services/flood-damage-restoration/, plus the /services/ hub. They remain absent from the sitemap and are the highest-intent commercial targets in url-plan.json.
3. Activate GSC for this client so the next run can score indexing and demand. With 120 URLs launched inside 91 days, the likely near-term risk is "Discovered - currently not indexed" across the 73 service-area-service pages, which v1 cannot detect. Follow docs/system-4-v2-activation.md.
4. Reconcile the 3 content-queue items still at status written (/blog/how-to-tell-if-you-have-water-damage-behind-walls/ at 77 days, /blog/what-happens-if-water-damage-is-left-untreated/ at 74 days, /blog/how-to-dry-out-a-flooded-house/ at 56 days). They are live in the sitemap, so moving them to published keeps future dedupe passes accurate.
5. Add url-plan entries for /emergency/, /reviews/, /certifications/ and /case-studies/ so the recommender can classify them by archetype (/emergency/ is likely a money page). Then keep the monthly cadence; expect quiet runs until about 2027-04-30 unless GSC v2 introduces demand-side flags first.
