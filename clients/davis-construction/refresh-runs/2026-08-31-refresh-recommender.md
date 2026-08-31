# Refresh Recommender - Davis Construction Contractors - 2026-08-31

**Origin:** https://davisconstructioncontractors.com (apex)
**URLs evaluated:** 71
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

None this cycle. No candidate carried a `stale_12mo` flag, and no money page carried an `aging` flag. The oldest URL on the site is 102 days old, which is 203 days short of the 305-day aging threshold and 263 days short of the 365-day stale threshold.

## Action: audit then decide

None this cycle. No candidate produced a combined or ambiguous flag set, no candidate returned `date_source == "none"`, and all 71 HTML fetches succeeded (0 failures), so there were no unresolved date signals to hand back for manual inspection.

## Age distribution (why nothing fired)

| Age band | URLs | Threshold status |
| --- | ---: | --- |
| 0-102 days | 71 | fresh |
| 305-364 days (`aging`) | 0 | not reached |
| 365+ days (`stale_12mo`) | 0 | not reached |

Date sources: 49 URLs from `json_ld_date_modified` (all blog posts and service-area-service pages), 22 URLs from `sitemap_lastmod` (home, contact, services hub, service landings, service areas, about, legal, blog index, certifications, reviews).

## Notes

- URLs skipped because already in content-queue: none. The content queue holds 11 open items (all `status: queued`), but every one has `post_url: null`, so none of them resolve to a live site URL that could collide with a refresh recommendation. The remaining 19 items are `written` (12) or `published` (7).
- URLs where date extraction failed: none. All 71 candidates resolved a date, and `failed_html_count` was 0.
- Coverage gap: v1 cannot see indexing state. A page that is live, dated today, and completely absent from Google's index looks identical to a healthy page in this report. `not_indexed` and `index_warning` need the GSC URL Inspection API, which is the v2 layer (see `docs/system-4-v2-activation.md`).
- Second coverage gap: all 14 money pages inherit their age from `sitemap_lastmod`, frozen at 2026-05-21. That timestamp reflects the original site build, not any subsequent content edit. If the build pipeline keeps emitting a static lastmod, these pages will trip `aging` on 2027-03-23 and `stale_12mo` on 2027-05-22 purely as a clock artifact, regardless of whether their content actually decayed. Conversely, a real edit to a money page today would not move its age at all.

## Recommended next actions (top 5)

1. Add `dateModified` to the JSON-LD on the 14 money pages so their freshness signal reflects real edits. The blog posts and the 18 service-area-service pages already emit `json_ld_date_modified`; the home, contact, services-hub, service-landing, and service-area templates do not, which is why all 14 sit at a hardcoded 102 days. Fixing this at the template level before the next cycle prevents a false `aging` wave on 2027-03-23.
2. Make the sitemap emit a per-URL `lastmod` that tracks content changes rather than build time. Every one of the 22 sitemap-dated URLs currently reports `2026-05-21T22:57:47.662Z`, the original render timestamp, even though `build.last_pushed_main_at` is 2026-08-31. Until this is decoupled, Layer 1 cannot distinguish an edited page from an untouched one.
3. Leave the 11 open content-queue items to System 2 and do not enqueue refresh work this cycle. There is no overlap to dedupe and no stale URL to rewrite, so any refresh-tagged item added now would be manufactured work.
4. Schedule the v2 GSC activation ahead of the next monthly run. GSC is already verified for this property (`sc-domain:davisconstructioncontractors.com`, verified 2026-05-28) and the sitemap is submitted, so the indexing-coverage signal is available as soon as the URL Inspection call is wired in. On a site this young, `not_indexed` on the 19 recently published blog posts is a far more likely real problem than age decay.
5. Re-run this recommender on the normal monthly cadence (next: 2026-09-30, one day after the System 3 audit). The oldest URL will be roughly 132 days then, still short of any threshold, so expect another zero-action run unless v2 GSC signals are live by then.
