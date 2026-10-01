# Refresh Recommender - All Pro Plumbing Heating and Air - 2026-10-01

**Origin:** https://allproplumbingheatingandair.com (apex)
**URLs evaluated:** 453
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

No URLs need a content refresh this cycle. All 453 candidates have an empty flag list and are under the 305-day aging threshold. The oldest page on the site is /blog/drain-cleaning-diy-vs-pro/ at 113 days (json_ld_date_modified 2026-06-10). The oldest of the 42 money pages are 85 days old (sitemap_lastmod 2026-07-08, shared by 31 of them). The other 11 money pages were dated 2026-09-25 or 2026-09-26.

## Action: audit then decide

No URLs need a manual audit this cycle. No candidate has a combined-flag or unclear-signal condition. Date extraction succeeded on all 453 URLs and no candidate has date_source "none".

## Notes

- URLs skipped because already in content-queue: none. 14 candidate URLs match content-queue items, but none has a status in the active set {queued, in_progress, needs_review}. Five are status=written (/blog/best-emergency-plumbing-company-in-bakersfield-ca/, /blog/how-to-find-a-good-plumber/, /blog/toilet-replacement-cost/, /blog/does-homeowners-insurance-cover-slab-leak-repair/, /blog/why-is-my-ac-not-turning-on/). Nine are status=published. All 14 are fresh. The six queued content-queue items still have post_url=null and no live URL.
- URLs where date extraction failed: none. All 453 URLs resolved a date: 400 via json_ld_date_modified and 53 via sitemap_lastmod. There were zero HTML fetch failures.
- Layer 1 truncation came back for the third month in a row. The candidates file already in place had inspected_count=120, which matches the scorer's default --max-urls (scripts/refresh_scorer.py:527). A re-run at --max-urls 400 also hit its cap. The final run at --max-urls 3000 found the real sitemap size, 453 URLs, and this report covers all of them. Without the re-run, this month's report would have missed 333 URLs (74 percent of the site).
- The sitemap grew from 192 to 453 URLs since 2026-08-31. Most of the growth came from 242 new service-area-service pages published between 2026-09-21 and 2026-09-27. The site now has 17 cities times 22 services (374 pages), up from 132. It also has 17 service-area hubs (was 6) and 27 blog URLs, including 2 new System 2 posts. Every new page is under 11 days old.
- Archetype mapping gap: 19 sitemap URLs are not in plan/url-plan.json and were counted as non-money by default. They are /case-studies/, /certifications/, /emergency/, /reviews/, /services/plasma-guard-pro/, and 14 System 2 blog posts.
- Money-page rule scope: the rule covers 42 of 453 candidates. The 374 service-area-service URLs are commercial conversion pages outside the rule, so they would score priority 4 when they age.
- Coverage gap: v1 cannot see Google index coverage states, so not_indexed and canonical-conflict problems stay invisible. That matters more now than last month. 242 thin-template city-service pages went live in one week, and index coverage, not age, is the risk for that inventory.

## Recommended next actions (top 5)

1. Hold the monthly cadence and take no refresh action this cycle. /blog/drain-cleaning-diy-vs-pro/ (json_ld_date_modified 2026-06-10, age 113) is the oldest URL. It crosses the 305-day aging threshold on 2027-04-11. The 169-URL 2026-07-08 block crosses on 2027-05-09, and nothing on this domain can reach stale_12mo before 2027-06-10. Expect zero-action runs until spring 2027. Treat any earlier non-zero run as a sign that a date source changed.
2. Raise the --max-urls default at scripts/refresh_scorer.py:527 from 120 to at least 1000, and log the number of URLs dropped by the cap at scripts/refresh_scorer.py:407. This defect was reported on 2026-07-30 and 2026-08-31 and is still unfixed. This month it hid 333 of 453 URLs. The cron default at scripts/refresh_cron.py:145 (200) now truncates this client too, dropping 253 URLs on every scheduled run.
3. Check indexing for the 242 new city-service pages, since v1 cannot see it. In GSC, run URL Inspection on one page from each publish day, for example /service-areas/delano-ca/water-heater-repair/ and /service-areas/tehachapi-ca/drain-cleaning/. Then check the Pages report for "Crawled - currently not indexed" on the /service-areas/ path. If more than a small share of the new pages are excluded, put local proof (jobs, reviews, photos per city) ahead of publishing more cities.
4. Add /emergency/ and /services/plasma-guard-pro/ to plan/url-plan.json with the service-landing archetype, and add the 14 System 2 blog posts as blog-post. Without a url-plan entry, /emergency/ (the 24/7 emergency plumbing landing page) scores as non-money, so it would land at priority 4 instead of priority 1 once it ages.
5. Connect Google Search Console for allproplumbingheatingandair.com per docs/system-4-v2-activation.md. With 374 city-service pages live, index coverage is the only System 4 signal that can say anything actionable this quarter. The age signal on 139 of those pages is just the 2026-07-08 deploy date.
