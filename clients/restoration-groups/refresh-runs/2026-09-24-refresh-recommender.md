# Refresh Recommender - The Restoration Group - 2026-09-24

**Origin:** https://therestorationgroup.com (apex)
**URLs evaluated:** 120
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

None. No candidate carried a `stale_12mo` flag, and no money page carried an `aging` flag. The oldest inspected URL is 97 days old (/blog/how-long-does-water-damage-restoration-take/, date_source `json_ld_date_modified`), which is 208 days short of the 305-day aging threshold and 268 days short of the 365-day stale threshold.

## Action: audit then decide

None. Every candidate resolved a date from a real signal, no flag combinations fired, and no candidate had `date_source: none`.

## Age distribution of what was inspected

| Archetype | URLs | Oldest (d) | Dominant date source | Money page |
| --- | ---: | ---: | --- | --- |
| service-area-service | 82 | 75 | json_ld_date_modified | no |
| unmapped | 14 | 59 | json_ld_date_modified | no |
| blog-post | 12 | 97 | json_ld_date_modified | no |
| service-area | 5 | 75 | sitemap_lastmod | yes |
| legal | 2 | 75 | sitemap_lastmod | no |
| home | 1 | 75 | sitemap_lastmod | yes |
| about | 1 | 75 | sitemap_lastmod | no |
| blog-index | 1 | 75 | sitemap_lastmod | no |
| contact | 1 | 75 | sitemap_lastmod | yes |
| service-areas-hub | 1 | 75 | sitemap_lastmod | no |

## Notes

- URLs skipped because already in content-queue: none. The 10 active content-queue items are all `queued` with no post_url yet, so none maps to a live URL.
- URLs where date extraction failed: none (103 json_ld_date_modified, 17 sitemap_lastmod).
- Date-signal gap: 17 URLs (home, contact, sampled service-area pages) are dated only by sitemap_lastmod, so their age reflects the last site build, not the last content edit.
- Coverage gap: v1 has no GSC data (no indexing, striking-query, or CTR signals), and the scorer sampled 120 of 1301 planned URLs, so most service-area-service and service-landing pages were not age-scored.

## Recommended next actions (top 5)

1. No refresh work this cycle. Re-run on the next monthly cadence; the earliest any blog post can hit the 305-day aging line is roughly 208 days out, starting with /blog/how-long-does-water-damage-restoration-take/.
2. Add `dateModified` to the JSON-LD on the home, contact, and service-area templates so the scorer measures real content edits instead of sitemap_lastmod build dates.
3. Re-run `python3 scripts/refresh_scorer.py --slug restoration-groups --max-urls 1500` once to age-score the full url-plan, including the service-landing pages that fell outside the default 120-URL sample.
4. Connect GSC (see docs/system-4-v2-activation.md) so striking_queries and low_ctr signals can drive refreshes on the blog posts, which are otherwise too young to flag on age.
5. Leave the 10 queued content-queue items with System 2; none overlaps a live URL, so there is nothing to dedupe.
