# Refresh Recommender - DISS Restoration - 2026-09-24

**Origin:** https://dissrestoration.com (apex)
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

None. No URL carries a `stale_12mo` or `aging` flag.

## Action: audit then decide

None. No combined flags and no URL with an undetermined date.

## Notes

- All 120 URLs were fetched successfully (0 HTML failures). Age range is 0 to 68 days, well under the 305-day aging threshold.
- Date sources: sitemap_lastmod (18), json_ld_date_modified (102).
- URLs skipped because already in content-queue: none (no flagged URLs to dedupe).
- URLs where date extraction failed: none.
- Coverage gap: v1 cannot see indexing status, canonical issues, or GSC demand signals (striking queries, low CTR), so a fresh-but-unindexed or underperforming page would not surface here.

## Recommended next actions (top 5)

1. No refresh work is due this cycle. The oldest page is 68 days old; the earliest any page can reach the 305-day aging threshold is roughly 237 days from now, so re-run next month on the normal cadence.
2. Connect Google Search Console for dissrestoration.com (see docs/system-4-v2-activation.md) so the next run can flag striking-distance queries and low-CTR pages, which are the only refresh signals that would matter on a site this new.
