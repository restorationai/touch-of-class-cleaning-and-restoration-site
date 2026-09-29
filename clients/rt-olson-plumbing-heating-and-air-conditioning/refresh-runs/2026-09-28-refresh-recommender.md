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

None this run. No URL carries a `stale_12mo` or `aging` flag.

## Action: audit then decide

None this run. Every URL has a resolved date (100 from json_ld_date_modified, 20 from sitemap_lastmod) and no combined or conflicting flags.

## Oldest URLs (watch list, not queued)

| URL | Age (d) | Date source | Crosses 305-day aging threshold |
| --- | ---: | --- | --- |
| /blog/drain-cleaning-diy-vs-pro/ | 69 | json_ld_date_modified | 2027-05-22 |
| /blog/signs-of-a-slab-leak/ | 63 | json_ld_date_modified | 2027-05-28 |
| /blog/water-heater-lifespan-repair-or-replace/ | 61 | json_ld_date_modified | 2027-05-30 |
| /blog/hydro-jetting-vs-snaking/ | 56 | json_ld_date_modified | 2027-06-04 |
| /blog/furnace-repair-or-replace/ | 53 | json_ld_date_modified | 2027-06-07 |

## Notes

- URLs skipped because already in content-queue: none. The 9 active content-queue items (2026-09-06-cooling, 2026-09-06-heating, 2026-09-06-water-treatment, 2026-09-06-water-heaters, 2026-09-28-emergency-plumber-cost, 2026-09-28-what-to-do-if-you-smell-gas-in-your-house, 2026-09-28-how-to-shut-off-main-water-valve, 2026-09-28-how-to-stop-a-toilet-from-overflowing, 2026-09-28-what-is-considered-a-plumbing-emergency) are net-new posts without a published URL, so none overlap the evaluated set.
- URLs where date extraction failed: none.
- Coverage gap: v1 cannot see indexing status or canonical problems; a freshly built site like this one is most at risk of "Discovered - currently not indexed", which only GSC (v2) will surface.

## Recommended next actions (top 5)

1. No refresh work is due. The site was rebuilt between 2026-07-21 and 2026-09-28, so the oldest URL (/blog/drain-cleaning-diy-vs-pro/, 69 days, json_ld_date_modified) will not enter the aging window until 2027-05-22.
2. Activate the System 4 v2 GSC layer (docs/system-4-v2-activation.md) for rtolsonplumbing.com so the next run can flag not-indexed and canonical issues on the 120 new URLs, which is the real risk for a site this young.
3. Keep System 2 working the 9 queued posts; when /blog/drain-cleaning-diy-vs-pro/ and /blog/signs-of-a-slab-leak/ are linked from the new emergency-plumber cluster posts, update their dateModified so the recency signal stays accurate.
4. Re-run this recommender monthly after the System 3 audit; expect the first `aging` blog flags around 2027-05-22 and first money-page flags shortly after, since the service pages share the same August 2026 build dates.
