# Refresh Recommender — All Pro Plumbing Heating and Air — 2026-08-31

**Origin:** https://allproplumbingheatingandair.com (apex)
**URLs evaluated:** 192
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

No URLs require a content refresh this cycle. Every one of the 192 candidates carries an empty flag list and sits below the 305-day aging threshold. The oldest page on the site is /blog/drain-cleaning-diy-vs-pro/ at 82 days (json_ld_date_modified 2026-06-10). All 31 money pages are 54 days old (sitemap_lastmod 2026-07-08) and none is within 250 days of the aging threshold.

## Action: audit then decide

No URLs require manual audit this cycle. No candidate carries a combined-flag or unclear-signal condition, date extraction succeeded on all 192 URLs, and no candidate has date_source "none", so there is no low-confidence-date case to inspect by hand.

## Notes

- URLs skipped because already in content-queue: none. Seven candidate URLs match content-queue items, but no status is in the active set {queued, in_progress, needs_review}. Four are status=written (/blog/best-emergency-plumbing-company-in-bakersfield-ca/, /blog/how-to-find-a-good-plumber/, /blog/toilet-replacement-cost/, /blog/does-homeowners-insurance-cover-slab-leak-repair/) and three are status=published (/blog/how-much-does-a-plumber-cost-per-hour/, /blog/how-much-does-a-plumber-cost-to-unclog-a-drain/, /blog/air-conditioner-not-cooling/). All seven are fresh, so there was nothing to dedupe. The other 12 content-queue items are still queued with post_url=null.
- URLs where date extraction failed: none. All 192 URLs resolved a date, 151 via json_ld_date_modified and 41 via sitemap_lastmod, with zero HTML fetch failures.
- Layer 1 truncation recurred. The candidates file found in place had inspected_count=120, which is exactly the scorer's default --max-urls (scripts/refresh_scorer.py:527), against a 192-URL sitemap. It was re-run at --max-urls 300 so this report covers the full sitemap. The 2026-07-30 report raised the same defect and the default has not changed.
- Sitemap shrank from 209 to 192 URLs, and the change is healthy. The whole 23-URL /service-areas/bakersfield-ca/ cluster left the sitemap and now 301-redirects: each service page to its /services/{service}/ equivalent (verified on drain-cleaning, ac-repair, emergency-plumbing, water-heater-repair) and the city hub to /. Bakersfield is primary:true in plan-input.json, so the primary city belongs on the 22 /services/ landing pages and the duplicate city cluster was correctly consolidated. Six URLs were added: five System 2 blog posts and /services/plasma-guard-pro/.
- Archetype mapping gap: 11 sitemap URLs are absent from plan/url-plan.json (/certifications/, /emergency/, /reviews/, /services/plasma-guard-pro/, plus 7 System 2 blog posts) and defaulted to non-money.
- Money-page rule scope: the rule covers 31 of 192 candidates. The 132 service-area-service URLs are commercial conversion pages that fall outside it and would score priority 4 when they age.
- Coverage gap: v1 cannot see Google index coverage states, so not_indexed and canonical-conflict problems stay invisible. That matters more than age on this site. Every one of the 31 money pages is dated from sitemap_lastmod 2026-07-08, which is the deploy date rather than a content edit date, so age scoring on the commercial inventory is measuring build recency and cannot go stale before 2027-07-08.

## Recommended next actions (top 5)

1. Take no refresh action this cycle and hold the monthly cadence. /blog/drain-cleaning-diy-vs-pro/ (json_ld_date_modified 2026-06-10, age 82) is the oldest URL and does not cross the 305-day aging threshold until 2027-04-11; the 169-page 2026-07-08 block crosses on 2027-05-09, and nothing on this domain can reach stale_12mo before 2027-06-10. Expect zero-action runs until spring 2027 and treat any earlier non-zero run as a signal that a date source changed.
2. Change the --max-urls default at scripts/refresh_scorer.py:527 from 120 to 300, and log the count of URLs dropped by the cap at scripts/refresh_scorer.py:407. This defect was reported on 2026-07-30, was not fixed, and silently truncated this month's run to 120 of 192 URLs before the re-run. Note that scripts/refresh_cron.py:145 already defaults to 200, which leaves only 8 URLs of headroom against today's 192-URL sitemap; the site added 6 URLs this month, so the cron path will start truncating around November 2026 without the change.
3. Confirm the /service-areas/bakersfield-ca/ 301s are being seen by Google, since v1 cannot check this. The 23 redirects are correct and the destinations are right, but the URLs were live and in the sitemap as recently as 2026-07-30, so they are indexed under the old paths. In GSC, run URL Inspection on /service-areas/bakersfield-ca/water-heater-repair/ and confirm it reports the redirect and that /services/water-heater-repair/ is the indexed canonical.
4. Add /emergency/ and /services/plasma-guard-pro/ to plan/url-plan.json with the service-landing archetype. Both are commercial pages and both currently score as non-money purely because the url-plan has no entry, which would put /emergency/, the 24/7 emergency plumbing landing page, at priority 4 instead of priority 1 the moment it ages.
5. Connect Google Search Console for allproplumbingheatingandair.com per docs/system-4-v2-activation.md. All 31 money pages derive their date from sitemap_lastmod 2026-07-08 rather than a real edit date, so v1 has no freshness signal on the commercial inventory for another ten months. Index coverage is the only System 4 signal that can say anything actionable about those pages this quarter.
