# Refresh Recommender - Frontline Fire & Flood - 2026-09-28

**Origin:** https://frontlinefireflood.com (apex)
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

No URLs qualify. Every URL is under the 305-day aging threshold.

## Action: audit then decide

No URLs qualify. No flag combinations or missing dates were found.

## Notes

- All 120 URLs are fresh: ages range 0 to 42 days (date sources: json_ld_date_modified 100, sitemap_lastmod 20).
- URLs skipped because already in content-queue: none
- URLs where date extraction failed: none
- Coverage gap: v1 cannot see indexing status, canonical conflicts, or striking-distance queries without GSC data, so a fresh page that is not indexed or underperforming would not surface here.

## Recommended next actions (top 5)

1. No refresh work is due this cycle; the oldest URL is 42 days old. Keep the monthly run on schedule, but at current ages the first pages will not reach the 305-day aging threshold until roughly mid-2027.
2. Connect Google Search Console for frontlinefireflood.com (see docs/system-4-v2-activation.md) so the next run can surface striking_queries and low_ctr pages, which are the only refresh signals likely to fire on a site this new.
