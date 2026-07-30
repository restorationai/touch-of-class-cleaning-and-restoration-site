# Refresh Recommender — All Pro Plumbing Heating and Air — 2026-07-30

**Origin:** https://allproplumbingheatingandair.com (apex)
**URLs evaluated:** 209
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

No URLs require a content refresh this cycle. Every candidate carries an empty flag list and sits far below the 305-day aging threshold. The oldest page on the site is /blog/drain-cleaning-diy-vs-pro/ at 50 days (json_ld_date_modified 2026-06-10); the 32 money pages are all 22 days old or newer (sitemap_lastmod 2026-07-08).

## Action: audit then decide

No URLs require manual audit this cycle. No candidate carries a combined-flag or unclear-signal condition, and date extraction succeeded on all 209 URLs, so there is no low-confidence-date case to inspect by hand.

## Notes

- URLs skipped because already in content-queue: none. Two candidate URLs overlap content-queue items, /blog/best-emergency-plumbing-company-in-bakersfield-ca/ (status=written, age 3) and /blog/how-much-does-a-plumber-cost-per-hour/ (status=published, age 0). Neither status is in the active set {queued, in_progress, needs_review}, and both are fresh, so there was nothing to dedupe. The remaining 9 content-queue items are still queued with post_url=null and have no live URL yet.
- URLs where date extraction failed: none. All 209 URLs resolved a date, 168 via json_ld_date_modified and 41 via sitemap_lastmod, with zero HTML fetch failures.
- Layer 1 coverage correction: the scorer had run at its default --max-urls 120 against a 209-URL sitemap, silently dropping 89 URLs including all 22 /services/ service-landing money pages and the /services/ hub. It was re-run at --max-urls 300 for this report, so the numbers above cover the full sitemap. The re-run changed nothing about the verdict (still zero flags), but the first pass could not have seen a stale money page if one existed.
- Archetype mapping gap: 5 sitemap URLs are not present in plan/url-plan.json (/certifications/, /emergency/, /reviews/, plus the two System 2 blog posts) and were therefore classified as non-money pages by default.
- Coverage gap: v1 cannot see Google index coverage states, so not_indexed and canonical-conflict problems are invisible even when present. On a site that cut over to the apex only 7 days ago (2026-07-23), indexing status is the real risk right now, and age-based scoring cannot measure it.

## Recommended next actions (top 5)

1. Take no refresh action on content this cycle, and record the first date any URL can become actionable. /blog/drain-cleaning-diy-vs-pro/ (json_ld_date_modified 2026-06-10, age 50) is the oldest URL on the site and crosses the 305-day aging threshold on 2027-04-11; the 192-page 2026-07-08 build block crosses it on 2027-05-09. Nothing on this domain can reach stale_12mo before 2027-06-10, so keep the monthly cadence and expect zero-action runs until spring 2027.
2. Raise the refresh scorer's URL cap before the next scheduled run, or this finding recurs silently. scripts/refresh_scorer.py:527 defaults --max-urls to 120 while the sitemap holds 209 URLs, and the cap is applied at line 407 with no warning when URLs are dropped. Either raise the default or pass --max-urls explicitly in railway.refresh-cron.toml, and consider logging the count of URLs discarded by the cap so a truncated run is visible in the report rather than inferred.
3. Map /emergency/, /certifications/, and /reviews/ into plan/url-plan.json with real archetypes. /emergency/ is a commercial landing page for 24/7 emergency plumbing and should almost certainly carry the service-landing archetype, which would make it a money page and move it from priority 4 to priority 3 (aging) or priority 1 (stale_12mo) the moment it ages. Today it scores as non-money purely because the url-plan has no entry for it.
4. Connect Google Search Console for allproplumbingheatingandair.com and activate the System 4 v2 signals per docs/system-4-v2-activation.md. Every money page on this site relies on sitemap_lastmod (the 2026-07-08 deploy date) rather than a real edit date, so age scoring on those 32 URLs is measuring deploy recency, not content freshness. Index coverage is the only signal that would tell you anything actionable about them this quarter.
5. Let System 2 keep clearing the content queue instead of scheduling refresh work. Nine items remain queued (how-to-find-a-good-plumber, toilet-replacement-cost, does-homeowners-insurance-cover-slab-leak-repair, how-much-does-a-plumber-cost-to-unclog-a-drain, plus five HVAC posts queued 2026-07-30); publishing those is strictly higher value than any refresh action available on a site whose oldest page is 50 days old.
