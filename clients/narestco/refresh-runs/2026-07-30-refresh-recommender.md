# Refresh Recommender - National Restoration Construction - 2026-07-30

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

None this run. No candidate carried a `stale_12mo` flag, and no money page carried an `aging` flag.

## Action: audit then decide

None this run. No candidate carried a combined or low-confidence flag set.

## Notes

- URLs skipped because already in content-queue: none. The 9 open System 2 items (statuses `queued`) have no `post_url` yet, so none of them collide with a live candidate URL.
- URLs where date extraction failed: none. All 120 URLs resolved a date - 106 from `json_ld_date_modified` and 14 from `sitemap_lastmod`.
- URLs skipped because fresh (age < 305 days, no flags): 120. The oldest page on the site is 78 days old (the 2026-05-13 blog cohort: `/blog/black-mold-vs-regular-mold/`, `/blog/burst-pipe-emergency-checklist/`, `/blog/signs-of-hidden-mold/` and 5 siblings). Nothing on narestco.com is close to either threshold: `aging` starts at 305 days, `stale_12mo` at 365.
- Coverage gap: v1 sees publish/modify dates only. It cannot tell you that a page is crawled-but-not-indexed, that a canonical is pointing somewhere unintended, or that a page sits at position 8-20 for queries with real impressions. On a site this young, that indexing and demand data is the signal that actually matters, and none of it is visible until GSC is wired in (`docs/system-4-v2-activation.md`).

## Recommended next actions (top 5)

1. Activate GSC v2 for narestco per `docs/system-4-v2-activation.md`. Age-based scoring will produce zero actions on this site until roughly 2027-03-14, so every refresh run between now and then is a no-op unless indexing and striking-query signals are switched on.
2. Once GSC is live, re-run Layer 1 and check indexing coverage on the three pages published today with `sitemap_lastmod` dates and no JSON-LD date at all: `/certifications/`, `/emergency/`, `/reviews/`. New URLs with no on-page date are the likeliest to sit in "Discovered - currently not indexed".
3. Audit why 14 URLs fall back to `sitemap_lastmod` while 106 emit `json_ld_date_modified`. The gap is the non-blog templates (`/`, `/about/`, `/contact/`, `/service-areas/*`). Adding `dateModified` to those page templates makes the money pages auditable by date instead of by sitemap timestamp, which is the weaker signal.
4. Leave the 9 open `queued` content-queue items to System 2. Four of them (`flooded basement what to do`, `how to prevent basement flooding during heavy rain`, `flooded basement cleanup cost`, `my basement flooded what will insurance cover`) form a basement-flooding cluster. When they publish, add internal links from the existing `/blog/mold-after-water-damage/` and `/blog/burst-pipe-emergency-checklist/` posts so the new cluster inherits internal authority rather than waiting on a future refresh pass to do it.
5. Skip next month's run if GSC is still off. The next date on which any URL can flag is 2027-03-14 (`aging` on the 78-day blog cohort), with `stale_12mo` first reachable 2027-05-13. Nothing between now and then changes the output.
