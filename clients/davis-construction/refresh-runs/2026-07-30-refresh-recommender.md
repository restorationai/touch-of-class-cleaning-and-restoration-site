# Refresh Recommender - Davis Construction Contractors - 2026-07-30

**Origin:** https://davisconstructioncontractors.com (apex)
**URLs evaluated:** 76
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

None this cycle. No candidate carried a `stale_12mo` flag, and no money page carried an `aging` flag.

| Priority | URL | Age (d) | Date source | Why refresh now |
| ---: | --- | ---: | --- | --- |
| - | (none) | - | - | - |

## Action: audit then decide

None this cycle. No candidate produced a combined or ambiguous flag set, and no candidate had `date_source: none`.

| Priority | URL | Flags | Why |
| ---: | --- | --- | --- |
| - | (none) | - | - |

## Freshness picture

Thresholds this run: aging at 305 days, stale at 365 days.

| Age bucket (days) | URLs |
| --- | ---: |
| 0-29 | 9 |
| 30-59 | 6 |
| 60-89 | 61 |
| 90+ | 0 |

Oldest URLs in the set (all 70 days, dated 2026-05-21, the site build date):

| URL | Archetype | Money page | Age (d) | Date source | Crosses aging | Crosses stale |
| --- | --- | :---: | ---: | --- | --- | --- |
| / | home | yes | 70 | sitemap_lastmod | 2027-03-22 | 2027-05-21 |
| /services/ | services-hub | yes | 70 | sitemap_lastmod | 2027-03-22 | 2027-05-21 |
| /contact/ | contact | yes | 70 | sitemap_lastmod | 2027-03-22 | 2027-05-21 |
| /service-areas/madison-al/ | service-area | yes | 70 | sitemap_lastmod | 2027-03-22 | 2027-05-21 |
| /blog/basement-flooding-prevention/ | blog-post | no | 70 | json_ld_date_modified | 2027-03-22 | 2027-05-21 |

Archetype spread across the 76 evaluated URLs: 27 service-area-service, 26 blog-post, 9 service-landing, 3 service-area, 3 legal, 2 unclassified, and one each of home, contact, services-hub, service-areas-hub, blog-index, about. 15 of the 76 are money pages under the home / contact / services-hub / service-landing / service-area rule.

## Notes

- URLs skipped because already in content-queue: none. The content-queue holds 5 items with status `queued`, but all 5 are unwritten posts with no `post_url`, so none of them corresponds to a live URL in the candidate set. No System 2 collision this cycle.
- URLs where date extraction failed: none. All 76 candidates resolved a date (53 from `json_ld_date_modified`, 23 from `sitemap_lastmod`), and `failed_html_count` was 0 across 76 fetches.
- Coverage gap: v1 cannot see indexing state, so a page that is live, fresh, and completely absent from Google's index looks identical to a healthy page here. Every URL on this site is under 90 days old, which is exactly the window where index coverage problems are most likely and least visible to this layer.
- Second coverage gap specific to this site: all 15 money pages fall back to `sitemap_lastmod` because their HTML carries no `json_ld_date_modified` or `article_modified_time`. A template redeploy rewrites that lastmod and resets their apparent age, so a money page whose copy has not changed in a year can keep reporting as fresh indefinitely. Blog posts are unaffected; all 53 of them carry a real `json_ld_date_modified`.
- 16 live URLs are not in `plan/url-plan.json`: 14 blog posts published by System 2 since the plan was generated on 2026-05-21, plus `/reviews/` and `/certifications/`, which fell back to the `other` archetype.

## Recommended next actions (top 5)

1. Take no refresh or rewrite action on any of the 76 URLs. The next monthly run (target 2026-08-30, one day after the System 3 audit) is the right checkpoint: the oldest URLs will be 101 days old, still 204 days short of the 305-day aging threshold. The first genuine threshold crossing for this site is 2027-03-22, when the 61 URLs dated 2026-05-21 hit `aging` together.
2. Emit `dateModified` into the JSON-LD of the 15 money pages in the site template, starting with `/`, `/services/`, `/contact/`, and the three service-area hubs (`/service-areas/madison-al/`, `/service-areas/huntsville-al/`, `/service-areas/athens-al/`). Right now those pages score off `sitemap_lastmod` alone, so the 2027-03-22 cohort crossing above is really a build-date artifact rather than a content-age reading, and it will fire for all 61 URLs on the same day whether or not the copy actually went stale.
3. Activate GSC v2 for this client. `clients/davis-construction.json` already shows a verified property (`sc-domain:davisconstructioncontractors.com`, verified 2026-05-28) with the sitemap index registered, so the per-client half of `docs/system-4-v2-activation.md` is done. Confirm agency access with `python3 scripts/gsc_setup.py --test-slug davis-construction` and re-run the scorer, which turns on `not_indexed` and `index_warning` detection for the 14 blog posts published in the last 61 days.
4. Add `/reviews/` and `/certifications/` to `clients/davis-construction/plan/url-plan.json` with real archetypes, and backfill the 14 off-plan blog posts (`/blog/water-damage-restoration-cost-guide/`, `/blog/what-to-do-after-a-house-fire/`, `/blog/fire-damage-restoration-process/`, and 11 more). Until they are in the plan, this layer classifies them by path heuristic, and `/reviews/` in particular is a conversion asset being scored as `other`.
5. Spot-check the three newest money-adjacent commercial posts against the SERP even though none are flagged: `/blog/how-much-does-a-general-contractor-cost/` (10 days), `/blog/how-to-choose-a-general-contractor/` (7 days), and `/blog/licensed-vs-unlicensed-contractor-alabama/` (3 days). Cost and licensing pages decay on regulation and pricing changes rather than on a 305-day clock, so age-based scoring will never surface them in time.
