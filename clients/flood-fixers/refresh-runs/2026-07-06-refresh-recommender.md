# Refresh Recommender — Flood Fixers — 2026-07-06

**Origin:** https://flood-fixers.com (apex)
**URLs evaluated:** 120
**Actions queued:** 0
**GSC enabled:** false (v1 — sitemap + page-date scoring only)

## Summary by action

| Action | Count |
| --- | ---: |
| refresh | 0 |
| audit_then_decide | 0 |
| request_indexing | 0 (deferred to v2) |
| fix_canonical | 0 (deferred to v2) |

## Action: refresh content

No URLs require a content refresh this cycle. Every candidate is under the 305-day aging threshold with no layer-1 flags.

## Action: audit then decide

No URLs require manual audit this cycle. No candidate carries a combined-flag or unclear-signal condition.

## Notes

- URLs skipped because already in content-queue: none flagged. The one overlapping URL, /blog/what-is-category-3-water-damage/, is fresh (age 0) and its content-queue item is status=published (not an active queued/in_progress/needs_review item), so there was nothing to dedupe.
- URLs where date extraction failed: none. All 120 inspected URLs resolved a date via sitemap_lastmod or json_ld_date_modified; there were zero HTML fetch failures.
- Coverage gap: v1 cannot see Google index coverage states, so not_indexed and canonical-conflict issues would be invisible even if present. GSC is verified for this property (sc-domain:flood-fixers.com, verified 2026-07-04) and can be plugged in for v2 to surface those signals.

## Recommended next actions (top 5)

1. No refresh work is due. This is a newly launched site (cut over 2026-07-04); the oldest content is 7 days old, so the earliest any URL can cross the 305-day aging threshold is roughly 2027-04-30. Re-run this recommender on the normal monthly cadence.
2. Activate System 4 v2 GSC signals for flood-fixers.com. The GSC property is already verified (sc-domain:flood-fixers.com); wiring it in would let the next run flag not_indexed and canonical-conflict URLs, which are the only meaningful risks for a site this fresh (per docs/system-4-v2-activation.md).
3. Watch the money pages for indexing rather than age this cycle. The homepage, /contact/, /service-areas/ hub, and the 78 service-area landing pages (e.g. /service-areas/san-diego-ca/water-damage-restoration/) were all published 2026-06-29; monitor them in GSC for "Crawled - currently not indexed" until v2 automates the check.
4. Let System 2 keep clearing the content-queue. Four blog items remain queued (water-damage-restoration-process, water-damage-behind-walls, water-damage-left-untreated, water-damage-restoration-cost); publishing those is higher-value than any refresh work right now.
5. Confirm sitemap lastmod hygiene going forward. Most URLs report sitemap_lastmod of 2026-06-29 while blog posts carry json_ld_date_modified; keeping json_ld_date_modified accurate on future edits ensures this recommender ages pages from real edit dates, not deploy dates.
