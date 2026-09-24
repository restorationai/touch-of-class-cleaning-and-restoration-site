# Refresh Recommender - Quality Contracting, Inc. - 2026-09-24

**Origin:** https://staging.rankai-quality-contracting-inc.pages.dev (staging)
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

None. No URL has reached the 305-day aging threshold or the 365-day stale threshold.

## Action: audit then decide

None. No URL has combined or ambiguous flags, and every URL resolved a date.

## Notes

- URLs skipped because already in content-queue: none. The 7 queued content-queue items (for example "how to fix water damage on ceiling" and "does homeowners insurance cover fire damage") are new posts not yet live, so none overlaps an existing URL.
- URLs where date extraction failed: none. Date sources: 62 json_ld_date_modified, 58 sitemap_lastmod.
- Age range across all 120 URLs: 0-75 days. Oldest: /blog/does-homeowners-insurance-cover-water-damage/ at 75 days (json_ld_date_modified). The site was rebuilt recently, so the earliest aging flags should appear around mid-2027.
- The scorer ran against the staging deploy (origin_source=staging), even though production https://qualitycontracting.us has been live since cutover on 2026-09-10. 42 of 120 HTML fetches failed, so those URLs were dated from sitemap_lastmod only. A sitemap lastmod reflects the latest deploy and can hide older content.
- Coverage gap: v1 cannot see indexing status, canonical problems, or GSC demand signals (striking_queries, low_ctr). A page this new could still be unindexed and v1 would not flag it.

## Recommended next actions (top 5)

1. The site went live on https://qualitycontracting.us (build.status=cut_over, 2026-09-10), but the scorer still picks the staging origin. Change the scorer's origin resolution for this client to production (deploy_url), then re-run `python3 scripts/refresh_scorer.py --slug quality-contracting-inc` so ages come from the live site and not from staging deploy timestamps.
2. Look into the 42 failed HTML fetches on the staging origin (possibly Cloudflare Pages access rules or rate limits) so that more URLs are dated from on-page json_ld_date_modified and fewer from sitemap_lastmod.
3. Turn on GSC v2 (docs/system-4-v2-activation.md) now that the site is live; the client record already shows a verified sitemap at https://qualitycontracting.us/sitemap-index.xml. With every page this fresh, striking_queries and low_ctr signals are the only refresh triggers likely to fire in the next 9 months.
4. Re-run this recommender on the normal monthly cadence, the day after the next System 3 audit. No age-based action is expected until 75-day-old /blog/does-homeowners-insurance-cover-water-damage/ reaches 305 days.
