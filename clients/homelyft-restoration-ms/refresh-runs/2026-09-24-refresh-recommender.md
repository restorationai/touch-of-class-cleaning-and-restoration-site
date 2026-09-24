# Refresh Recommender - HomeLyft Restoration MS - 2026-09-24

**Origin:** https://homelyft.net (apex)
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

None. No URL carries a stale_12mo or aging flag.

## Action: audit then decide

None. No combined or unclear flag sets, and every URL has a resolvable date.

## Notes

- All 120 URLs are fresh: age range 0 to 71 days against a 305-day aging threshold and 365-day stale threshold. Date sources: 103 json_ld_date_modified, 17 sitemap_lastmod.
- URLs skipped because already in content-queue: none (the 10 queued content-queue items are new-article briefs with no live URL yet).
- URLs where date extraction failed: none (120 of 120 HTML fetches succeeded).
- Coverage gap: v1 cannot see indexing status, canonical conflicts, or GSC demand signals (striking queries, low CTR), so a fresh page that is not indexed or under-clicked would not surface here.

## Recommended next actions (top 5)

1. No refresh work is due. The oldest URL on homelyft.net is 71 days old; the earliest any page can reach the 305-day aging threshold is roughly 2027-05-16, so the next monthly run is sufficient.
2. Connect Google Search Console for homelyft.net (see docs/system-4-v2-activation.md) so the next run can surface striking_queries and low_ctr pages, which are the only refresh triggers likely to fire on a site this new.
