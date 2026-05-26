# Refresh Recommender: Davis Construction Contractors (2026-05-25)

**Origin:** https://staging.rankai-davis-construction.pages.dev (staging)
**URLs evaluated:** 60
**Actions queued:** 0
**GSC enabled:** false (v1, sitemap + page-date scoring only)

## Summary by action

| Action | Count |
| --- | ---: |
| refresh | 0 |
| audit_then_decide | 0 |
| request_indexing | 0 (deferred to v2) |
| fix_canonical | 0 (deferred to v2) |

## Action: refresh content

_No URLs require refresh this cycle._

## Action: audit then decide

_No URLs need manual audit this cycle._

## Notes

- URLs skipped because already in content-queue: none
- URLs where date extraction failed: none
- URLs skipped silently because fresh (flags empty, age < 305d): 60
- Coverage gap: v1 cannot see Google Search Console indexing status, so not_indexed and index_warning flags do not fire. GSC will plug in at v2.

## Recommended next actions (top 5)

1. No refresh actions are needed this cycle. The site was rendered on 2026-05-21, so all 60 indexed URLs are 4 days old, well below the 305-day aging threshold.
2. Re-run this recommender monthly. The first real signal will appear around 2027-03-22, when content begins crossing the 305-day aging threshold.
3. Activate System 4 v2 (Google Search Console plug-in) before the first real refresh cycle so not_indexed and index_warning flags can fire on URLs Google has not picked up. See docs/system-4-v2-activation.md.
4. While waiting on age signals, let System 2 (content-queue) drive content publishing on schedule. The currently-queued cost-guide post will become a refresh candidate roughly 12 months after it ships.
5. No client-record changes required besides the refresh.last_run_at stamp written by this run.
