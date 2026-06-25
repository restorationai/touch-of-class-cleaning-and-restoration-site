# Refresh Recommender — Davis Construction Contractors — 2026-06-25

**Origin:** https://davisconstructioncontractors.com (apex)
**URLs evaluated:** 66
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

No URLs require a content refresh this cycle. Every inspected URL is within the freshness window.

## Action: audit then decide

No URLs require manual audit this cycle. No combined flags, low-confidence dates, or contradictory signals were present.

## Notes

- All 66 inspected URLs carry empty flags. The oldest page is 35 days old (the 24 blog posts dated 2026-05-21 via json_ld_date_modified); every other URL derives its date from sitemap_lastmod at 3 days. Nothing approaches the 305-day aging threshold, let alone the 365-day stale threshold.
- URLs skipped because already in content-queue: none. The five queued content-queue items (mold-remediation/mold-inspection/attic/crawl-space/insurance posts) have no live post_url yet, so they do not collide with any candidate URL. The six written items are all recent (most recent age 3 days) and fall well inside the freshness window.
- URLs where date extraction failed: none. All 66 URLs resolved a date (json_ld_date_modified on the 18 blog posts, sitemap_lastmod on the remaining 48 structural and money pages).
- Coverage gap: with gsc_enabled false, v1 cannot see indexing coverage. A recently published page that Google has crawled-but-not-indexed, or a money page silently dropped to "Alternate page with proper canonical tag," would be invisible to this run. Those signals (not_indexed, index_warning) activate when GSC is wired in at v2.

## Recommended next actions (top 5)

1. No refresh or audit actions are warranted. The site is newly built (cut over 2026-05-28) and all content is under 36 days old, so the correct action this cycle is to take none and re-run on the normal monthly cadence.
2. Re-run Layer 1 (`python3 scripts/refresh_scorer.py --slug davis-construction`) followed by this recommender on or about 2026-07-25 (one day after the next System 3 audit). The first refresh candidates will not begin aging into the 305-day window until roughly March 2027 for the 2026-05-21 blog cohort.
3. Prioritize GSC v2 activation (see docs/system-4-v2-activation.md). The GSC property `sc-domain:davisconstructioncontractors.com` is already verified (2026-05-28), so wiring URL Inspection into Layer 1 would immediately surface not_indexed and index_warning states that v1 is blind to — far more valuable on a 1-month-old site than age-based staleness.
4. Let System 2 finish the five queued mold posts (mold-remediation-cost-madison, mold-inspection-cost-huntsville, attic-mold-removal-athens, crawl-space-mold-removal-madison, does-insurance-cover-mold-remediation-huntsville). They are net-new content, not refresh work, and owning fresh publication dates keeps them out of this queue for a year.
5. No money page is flagged. The home, contact, services-hub, 10 service-landing, and service-area money pages all read 3 days old from sitemap_lastmod and need no intervention this cycle.
