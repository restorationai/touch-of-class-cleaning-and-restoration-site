# Refresh Recommender - Life Savers Restoration LLC - 2026-09-07

**Origin:** https://lifesaversrestorationvegas.com (apex)
**URLs evaluated:** 94
**Actions queued:** 0
**GSC enabled:** false (v1 - sitemap + page-date scoring only)

## Summary by action

| Action | Count |
| --- | ---: |
| refresh | 0 |
| audit_then_decide | 0 |
| request_indexing | 0 (deferred to v2) |
| fix_canonical | 0 (deferred to v2) |

No URL on this site met a refresh trigger. Layer 1 returned zero flags across all
94 URLs, and the oldest page on the site is 50 days old against a
305-day aging threshold and a 365-day stale threshold. This is the
expected result for a site scaffolded on 2026-08-05 and cut over to the live domain on
2026-09-04. The queue is intentionally empty rather than padded with low-value work.

## Action: refresh content

None this run.

## Action: audit then decide

None this run.

## Coverage detail

| Metric | Value |
| --- | ---: |
| URLs in sitemap and inspected | 94 |
| HTML fetched successfully | 94 |
| HTML fetch failures | 0 |
| Dates resolved | 94 |
| Money pages (home / contact / services-hub / service-landing / service-area) | 18 |
| Oldest page age (days) | 50 |

Date sources: json_ld_date_modified (66), sitemap_lastmod (28).

Five oldest URLs, all still well inside the fresh window:

| URL | Age (d) | Archetype | Date source |
| --- | ---: | --- | --- |
| /blog/does-homeowners-insurance-cover-water-damage/ | 50 | blog-post | json_ld_date_modified |
| /blog/burst-pipe-emergency-checklist/ | 48 | blog-post | json_ld_date_modified |
| /blog/black-mold-vs-regular-mold/ | 46 | blog-post | json_ld_date_modified |
| /blog/how-to-test-for-mold/ | 46 | blog-post | json_ld_date_modified |
| /blog/signs-of-hidden-mold/ | 46 | blog-post | json_ld_date_modified |

## Notes

- URLs skipped because already in content-queue: none. All 11 active (`queued`) content-queue
  items are unpublished keyword targets with a null `post_url`, so none of them collide with a
  crawled URL. The one `published` item
  (/blog/water-damage-restoration-cost-nv/, age 0) and the one `written` item
  (/blog/best-water-damage-restoration-company-in-henderson-nv/, age 11) are not in an active
  status and are fresh regardless.
- URLs where date extraction failed: none. 66 URLs dated from `json_ld_date_modified` and 28
  from `sitemap_lastmod`, with zero fetch failures.
- Coverage gap: v1 sees age only. It cannot tell you whether any of these 94 URLs are
  actually indexed, whether any are ranking position 8-20 on real demand, or whether any are
  earning impressions without clicks. On a site that has been live for three days that gap is
  the entire story: age-based scoring has nothing to say yet, and the signals that would be
  useful right now are exactly the ones v2 adds.
- Archetype matching: 56 URLs carry archetype `service-area-service` and 1 carries
  `service-areas-hub`. Neither string appears in the money-page list, so both scored as
  non-money. This changes nothing this run, but it will suppress priority-1 and priority-3
  scoring on the bulk of the site the first time aging flags appear.
- 6 crawled URLs have no url-plan entry and therefore a null archetype: /blog/best-water-damage-restoration-company-in-henderson-nv/,
  /blog/water-damage-restoration-cost-nv/, /case-studies/, /certifications/, /emergency/, /reviews/.

## Recommended next actions (top 5)

1. Do not queue refresh work for this client this cycle. Every URL is inside the fresh window;
   any rewrite now would be churn against content that has not had time to rank.
2. Activate the GSC v2 layer for `sc-domain:lifesaversrestorationvegas.com` (verified
   2026-09-04, sitemap https://lifesaversrestorationvegas.com/sitemap-index.xml) per
   docs/system-4-v2-activation.md. Age scoring will return nothing useful on this site until
   roughly 2027-06, whereas `striking_queries` and `not_indexed` become meaningful as soon as
   28 days of GSC data accumulate (approximately 2026-10-02).
3. Confirm whether `service-area-service` and `service-areas-hub` should count as money-page
   archetypes in the Step 3 rubric. They cover 57 of 94 URLs on this site, and as written those
   pages can never reach priority 1 or 3.
4. Add url-plan entries or an explicit archetype for the 6 unmapped URLs (/case-studies/,
   /certifications/, /emergency/, /reviews/ and the two blog posts) so they are classifiable on
   the next run instead of falling through as null.
5. Re-run this recommender on the normal monthly cadence, one day after the next System 3
   audit. Note that the last audit verdict for this client was `red` (2026-08-27,
   audit-runs/2026-08-27-onsite-audit.md); that is an onsite-quality problem, not a freshness
   problem, and it is System 3 work rather than anything this queue can act on.
