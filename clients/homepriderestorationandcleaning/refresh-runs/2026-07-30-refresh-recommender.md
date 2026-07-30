# Refresh Recommender - Home Pride Restoration and Cleaning LLC - 2026-07-30

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

None. No URL on the site has crossed the 305-day aging threshold or the 365-day stale threshold.

## Action: audit then decide

None. Every candidate returned a usable date and no candidate carried a mixed or low-confidence flag combination.

## Age distribution

| Bucket | URLs |
| --- | ---: |
| 0-29 d | 11 |
| 30-89 d | 109 |

## Notes

- URLs skipped because already in content-queue: none. The five content-queue items in status queued have no post_url yet, so none of them collides with a live URL in this run.
- URLs where date extraction failed: none. All 120 URLs returned a date (105 from json_ld_date_modified, 15 from sitemap_lastmod), and 0 of 120 HTML fetches failed.
- URLs skipped as fresh: 120. The whole site was built or last modified between 2026-06-15 and 2026-07-30, so the oldest page is 45 days old against a 305-day aging threshold.
- Coverage gap: v1 sees page dates only. It cannot see whether Google has actually indexed these 120 URLs, whether any page is losing impressions, or whether any page sits at position 8-20 for a query that a targeted refresh would win. On a site this new, indexing coverage is the real risk and age scoring cannot detect it. See docs/system-4-v2-activation.md to plug in GSC.

## Recommended next actions (top 5)

1. Take no refresh action on any of the 120 live URLs this cycle. The oldest page (https://homepriderestorationandcleaning.com/, 45 days, sitemap_lastmod) is 260 days short of the 305-day aging threshold; refreshing a page that Google crawled six weeks ago resets nothing and risks churn on a site still establishing its crawl pattern.
2. Activate GSC for this client (docs/system-4-v2-activation.md) before the next monthly run. Age scoring has nothing to say about a site launched in June 2026, but the 105 blog and service URLs carrying json_ld_date_modified need indexing confirmation, and only the v2 URL Inspection layer can tell you which of them Google has actually taken.
3. Ship the five queued content-queue items (best water damage restoration in Saratoga Springs UT, does-homeowners-insurance-cover-mold, what-kills-mold-permanently, when-is-mold-remediation-required, what-is-mold-remediation) through System 2. New coverage beats refreshing 45-day-old pages, and those five will be the pages this recommender scores next spring.
4. Watch the 15 sitemap_lastmod URLs (/, /about/, /accessibility/, /blog/, /contact/ and the other structural pages). They have no json_ld_date_modified, so their age signal will follow whatever the build stamps into the sitemap. If a rebuild bumps every lastmod, this recommender will report them as permanently fresh and never flag the money pages. Confirm the build writes a real content-change date rather than a build timestamp.
5. Schedule the next refresh run for the last week of August 2026, one day after the System 3 audit. The first page will not reach the 305-day aging threshold until roughly April 2027, so until GSC is live the monthly runs will be no-ops and their only job is to confirm the date pipeline is still healthy.
