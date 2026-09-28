# Refresh Recommender - RT Olson Plumbing, Heating and Air Conditioning - 2026-09-28

**Origin:** https://rtolsonplumbing.com (apex)
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

No URLs qualify. No page has reached the 305-day aging threshold or the 365-day stale threshold.

## Action: audit then decide

No URLs qualify. Every candidate has a usable date and no layer-1 flags.

## Notes

- URLs skipped because already in content-queue: none
- URLs where date extraction failed: none
- Freshness: all 120 URLs are between 0 and 69 days old (oldest: https://rtolsonplumbing.com/blog/drain-cleaning-diy-vs-pro/, 69 days via json_ld_date_modified). Date sources: sitemap_lastmod (20), json_ld_date_modified (100). 10 URLs map to money-page archetypes in the url-plan.
- Coverage gap: v1 cannot see indexing or canonical problems, so a fresh page that Google has not indexed would not surface here until GSC (v2) is connected.

## Recommended next actions (top 5)

1. No refresh work is due this cycle. The site was rebuilt recently, so the earliest pages will enter the aging window (305 days) around 2027-05-22; re-run monthly as scheduled.
2. The GSC property sc-domain:rtolsonplumbing.com is already verified in the client record; enable the v2 scorer (see docs/system-4-v2-activation.md) so the next run can detect not-indexed and canonical issues on the 10 money pages, which age scoring alone cannot catch.
