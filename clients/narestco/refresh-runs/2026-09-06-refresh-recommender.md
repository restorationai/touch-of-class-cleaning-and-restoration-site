# Refresh Recommender - National Restoration Construction - 2026-09-06

**Origin:** https://narestco.com (apex)
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

None. No URL on this site has crossed the 305-day aging threshold.

## Action: audit then decide

None. No candidate produced an ambiguous or conflicting signal set this run.

## Notes

- URLs skipped because already in content-queue: none - the 14 live content-queue items are unpublished drafts with no live URL yet, so there is nothing to collide with
- URLs where date extraction failed: none - all 120 URLs resolved a date (106 via json_ld_date_modified)
- URLs skipped because fresh: 120 of 120, age range 0-116 days, median 115 days
- Money pages on site: 6 of 120; oldest money page is / at 115 days
- Archetype spec gap (flagged, not acted on): 70 of the 120 live URLs are `service-area-service` (for example /service-areas/auburn-wa/burst-pipe-repair/). That archetype is not in the money-page list (home, contact, services-hub, service-landing, service-area), so when these pages age past 305 days they will score priority 4, the blog tier, despite being the site's main commercial inventory. No effect this run because zero actions were produced. Recommend widening the money-page list before the first run that produces real actions.
- 22 planned service-landing pages under /services/ are absent from the sitemap, so they were never evaluated. Build coverage rather than a refresh issue, and out of scope here, but it is why no service-landing page appears in this report.
- Coverage gap: v1 cannot see indexing state, impressions, clicks, or position. A page that is live, recent, and completely unindexed looks identical to a healthy page in this run. GSC connection (v2) is what closes that gap.

## Recommended next actions (top 5)

1. Take no refresh action this cycle. The oldest URL on narestco.com is 116 days old against a 305-day aging threshold, so every refresh here would be churn without a decay signal.
2. Connect Google Search Console for narestco.com and set `gsc_enabled: true` so the next run can see indexing coverage and striking-distance queries. Age alone is the only lever v1 has, and on a 116-day-old site that lever does nothing. See docs/system-4-v2-activation.md.
3. Until GSC is live, the 6 money pages are the pages worth watching: they carry the commercial intent and will hit the aging threshold first. Nothing to do yet, but they are the pages that should get the first refresh pass around 2027-03 on current dating.
4. Let System 2 keep working the content queue (14 items queued, 17 written, 8 published). New publishing, not refreshing, is what moves this site right now.
5. Re-run this recommender on the normal monthly cadence, one day after the System 3 audit. First run likely to produce real actions is the one after GSC is connected.
