# Refresh Recommender — Home Pride Restoration and Cleaning LLC — 2026-06-24

**Origin:** https://homepriderestorationandcleaning.com (apex)
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

None. No URL has reached refresh age.

## Action: audit then decide

None. No candidate fired ambiguous or combined flags.

## Notes

- URLs skipped because already in content-queue: none. The only live content-queue URL, `/blog/ice-dam-removal-park-city/`, has status `written` (not in `{queued, in_progress, needs_review}`) and is also fresh at age 0. The other four content-queue items are still `queued` with no published URL, so there is nothing to dedupe against.
- URLs where date extraction failed: none. All 120 inspected URLs resolved a date via `sitemap_lastmod` or `json_ld_date_modified`; no `age_days: null` and no `date_source: "none"`.
- Why the queue is empty: the site was created 2026-06-15 and cut over to apex on 2026-06-18. The oldest content is the seed blog set at `age_days = 9` (`json_ld_date_modified` 2026-06-15); every other URL is `age_days = 0` via `sitemap_lastmod`. Nothing is near the 305-day aging threshold or the 365-day stale threshold. Layer-1 `flag_counts` is empty (0 flags across 120 candidates).
- Coverage gap: v1 cannot see indexing status. `not_indexed` (e.g. "Crawled - currently not indexed") and canonical warnings are invisible until GSC is wired in for v2. GSC is verified for this property (`sc-domain:homepriderestorationandcleaning.com`, verified 2026-06-24), so v2 activation is unblocked when the indexing layer ships. See `docs/system-4-v2-activation.md`.

## Recommended next actions (top 5)

1. No refresh work this cycle. The whole site is under 10 days old, so the correct action is to let content accumulate ranking history rather than refresh it.
2. Re-run this recommender on the next monthly cadence (target ~2026-07-22, one day after the System 3 audit) — the same seed blog set will be ~37 days old then and still fresh, so expect another empty queue until roughly Q2 2027 when the first posts approach the 305-day aging mark.
3. Prioritize System 2 net-new content over refresh: four content-queue items (`how-to-prevent-ice-dams-heber-city`, `does-homeowners-insurance-cover-frozen-pipes-park-city`, `frozen-pipe-damage-heber-city`, `water-damage-restoration-cost-park-city`) are still `queued`. Growing the indexed footprint matters more than refreshing 9-day-old pages right now.
4. Activate System 4 v2 (GSC indexing layer) for this client. GSC is already verified, so the highest-value next signal is coverage state (not_indexed / index_warning) on the 120 brand-new URLs — that is the real risk for a freshly cut-over site, not content decay. Track via `docs/system-4-v2-activation.md`.
5. After the next System 3 audit run, confirm the audit verdict (currently `amber`, 2026-06-22) is not surfacing date or freshness issues that this age-based layer cannot see; if it is, fold those URLs in manually as `audit_then_decide` candidates.
