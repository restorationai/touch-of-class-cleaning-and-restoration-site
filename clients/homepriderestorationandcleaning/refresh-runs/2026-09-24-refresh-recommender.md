# Refresh Recommender - Home Pride Restoration and Cleaning LLC - 2026-09-24

**Origin:** https://homepriderestorationandcleaning.com (apex)  
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

None. No URL has crossed the 305-day aging threshold or the 365-day stale threshold. The oldest page is 101 days old.

## Action: audit then decide

None. Every candidate returned a usable date and no candidate carried a flag.

## Age distribution

| Bucket | URLs |
| --- | ---: |
| 0-29 d | 69 |
| 30-89 d | 10 |
| 90-179 d | 41 |

## Notes

- URLs skipped because already in content-queue: none. The 10 queued content-queue items have no post_url yet, so none collides with a live URL.
- URLs where date extraction failed: none. All 120 URLs returned a date (105 json_ld_date_modified, 15 sitemap_lastmod); 0 of 120 HTML fetches failed.
- URLs skipped as fresh: 120.
- GSC regression: the 2026-08-31 run had GSC data (gsc_enabled true, 11 demand-driven actions). This run has gsc: null and search_signals: null on all 120 candidates even though the client record holds a verified property (sc-domain:homepriderestorationandcleaning.com, verified 2026-06-24). The scorer fails soft to sitemap-only when GSC credentials are unavailable, which is what happened here.
- Dropped August items: the 11 queued items from 2026-08-31 (8 striking_queries refreshes, 1 title-meta-rewrite, 2 request_indexing for Eagle Mountain water damage and burst pipe pages) are no longer in the queue. They were dropped because this run could not see GSC, not because they were confirmed fixed.
- Date restamp: 57 URLs now carry a 2026-09-23 date (55 json_ld_date_modified, 2 sitemap_lastmod), most of which read 2026-06-15 last run. That looks like a site-wide build restamp of dateModified, not 57 real content edits.
- Coverage gap: without GSC, v1 cannot see indexing coverage, striking-distance queries, or low-CTR pages. On a site this young those are the only refresh signals that matter.

## Recommended next actions (top 5)

1. Restore GSC access for the scorer and re-run `python3 scripts/refresh_scorer.py --slug homepriderestorationandcleaning` followed by this recommender. The client has a verified property, so the missing signals are an environment/credential problem (GSCClient.is_configured returned false or the API call failed soft), and the August demand-driven queue cannot be re-evaluated until it is fixed.
2. Until that re-run lands, keep working the 2026-08-31 action list from the prior report manually. In particular, check https://homepriderestorationandcleaning.com/service-areas/eagle-mountain-ut/water-damage-restoration/ and /service-areas/eagle-mountain-ut/burst-pipe-repair/ in GSC URL Inspection and request indexing if they are still not indexed; nothing in this run shows they were fixed.
3. Check why 55 pages now show json_ld_date_modified 2026-09-23. If the build injects the build date into dateModified, change it to the last real content-edit date. Otherwise every rebuild resets the age clock, this recommender will never flag those pages, and Google gets a dateModified that doesn't match any visible change.
4. Take no age-driven refresh action on any of the 120 URLs. The homepage (101 days, sitemap_lastmod 2026-06-15) is the oldest page and is 204 days short of the 305-day aging threshold.
5. Ship the 10 queued content-queue items through System 2 before the next monthly run. New coverage is worth more than refreshing pages under four months old, and the next run should come one day after the System 3 audit in late October 2026.
