# Refresh Recommender - Davis Construction Contractors - 2026-10-01

**Origin:** https://davisconstructioncontractors.com (apex)
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

None this cycle. No candidate carried a `stale_12mo` flag, and no money page carried an `aging` flag. The oldest URL on the site is 133 days old, which is 172 days short of the 305-day aging threshold and 232 days short of the 365-day stale threshold.

## Action: audit then decide

None this cycle. No candidate produced a combined or ambiguous flag set, no candidate returned `date_source == "none"`, and all 120 HTML fetches succeeded (0 failures), so there were no unresolved date signals to hand back for manual inspection.

## Age distribution (why nothing fired)

| Age band | URLs | Threshold status |
| --- | ---: | --- |
| 0-30 days | 62 | fresh |
| 31-90 days | 12 | fresh |
| 91-133 days | 46 | fresh |
| 305-364 days (`aging`) | 0 | not reached |
| 365+ days (`stale_12mo`) | 0 | not reached |

Date sources: 97 URLs from `json_ld_date_modified` (blog posts and service-area-service pages), 23 URLs from `sitemap_lastmod` (home, contact, about, legal, blog index, service-areas hub, 11 service-area pages, case studies, certifications, emergency, reviews, estimate embed). The site grew from 71 to 120 sitemap URLs since the 2026-08-31 run.

Money pages present in the candidate set: 13 (home, contact, 11 service-area pages). All 13 are flag-free.

## Notes

- URLs skipped because already in content-queue: none. The content queue holds 6 open items (all `status: queued`, e.g. `2026-09-23-decks-pergolas-fences-cost-al`, `2026-09-19-how-much-value-does-a-kitchen-remodel-add`), but every one has `post_url: null`, so none of them resolve to a live site URL that could collide with a refresh recommendation. The rest of the queue is `written` (14), `published` (11), or `banked` (6).
- URLs where date extraction failed: none. All 120 candidates resolved a date, and `failed_html_count` was 0.
- Coverage gap: v1 cannot see indexing state. A page that is live, recently dated, and absent from Google's index looks identical to a healthy page in this report. `not_indexed` and `index_warning` need the GSC URL Inspection API, which is the v2 layer (see `docs/system-4-v2-activation.md`).
- Date-signal gap, partially resolved: 9 of the 11 service-area pages now report `sitemap_lastmod` 2026-09-30, so the sitemap is emitting change-aware lastmods for some templates. Home, contact, `/service-areas/athens-al/` and `/service-areas/huntsville-al/` still report `sitemap_lastmod` 2026-05-21 (133 days), as do about, privacy, accessibility, blog index and the service-areas hub. If those stay frozen, the money pages among them trip `aging` on 2027-03-22 and `stale_12mo` on 2027-05-21 purely as a clock artifact.
- Planned money pages missing from the sitemap: `plan/url-plan.json` lists `/services/` (services-hub) and 14 `/services/*/` service-landing pages, all `status: planned`. None of them appear in the 120 sitemap candidates, so Layer 1 is not scoring them at all.

## Recommended next actions (top 5)

1. Confirm whether the 15 planned `/services/` pages (hub plus 14 service landings such as `/services/roofing/`, `/services/home-remodeling/`, `/services/water-damage-restoration/`) are live. If they are live, add them to the sitemap so Layer 1 can score them; if they are not built, that is a bigger gap than any refresh item, because they are the core money pages in the url-plan.
2. Fix the frozen `sitemap_lastmod` on `/` and `/contact/` (both still 2026-05-21, `sitemap_lastmod`), and add `dateModified` to their JSON-LD the way the blog and service-area-service templates already do. Otherwise the homepage will false-flag `aging` on 2027-03-22.
3. Find out why `/service-areas/athens-al/` and `/service-areas/huntsville-al/` kept the 2026-05-21 lastmod while the other 9 service-area pages moved to 2026-09-30. Those two are the main cities, and they also own the 2026-05-21 `json_ld_date_modified` service-area-service pages (18 of them), so check whether their content was skipped in the 2026-09-30 regeneration.
4. Leave the 6 open content-queue items to System 2 and do not enqueue refresh work this cycle. Nothing overlaps and no URL is stale, so any refresh-tagged item added now would be manufactured work.
5. Wire up the v2 GSC URL Inspection layer before the next monthly run (about 2026-10-31). With 49 new URLs added since the last cycle and 62 URLs under 30 days old, `not_indexed` on new blog and city pages is a far more likely real problem than age decay. The oldest URL will be about 163 days old by then, so expect another zero-action v1 run.
