# Refresh Recommender — The Restoration Group — 2026-07-30

**Origin:** https://therestorationgroup.com (apex)
**URLs evaluated:** 120
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

None. No candidate carried a `stale_12mo` flag, and no money page carried an `aging` flag. The oldest URL on the site is 41 days old (/blog/how-long-does-water-damage-restoration-take/, date_source `json_ld_date_modified`), which is 264 days short of the 305-day aging threshold and 324 days short of the 365-day stale threshold.

## Action: audit then decide

None. Every candidate resolved a date from a real signal, no flag combinations fired, and no candidate had `date_source: none`.

## Age distribution of what was inspected

| Segment | URLs | Oldest (d) | Dominant date source |
| --- | ---: | ---: | --- |
| Blog posts | 12 | 41 | json_ld_date_modified |
| Money pages (home, contact, service-area) | 8 | 19 | sitemap_lastmod |
| Service-area-service pages | 90 | 19 | json_ld_date_modified |
| Other (legal, about, blog-index, unplanned) | 10 | 19 | mixed |

## Notes

- URLs skipped because already in content-queue: none. All 8 active (`queued`) content-queue items are unwritten and have no `post_url`, so they do not map to a live URL. The two content-queue items that do carry a `post_url` (`/blog/best-water-damage-restoration-company-in-kenilworth-nj/`, status `written`; `/blog/ceiling-water-damage-repair/`, status `published`) fall outside the skip set, and both are fresh anyway at 3 and 0 days.
- URLs where date extraction failed: none. All 120 candidates resolved a date, 104 from `json_ld_date_modified` and 16 from `sitemap_lastmod`. `failed_html_count` was 0.
- Coverage gap: the scorer inspected 120 of the 943 URLs in the sitemap (the default `--max-urls` cap), so roughly 87 percent of the site was not age-scored this run. The 16 `service-landing` pages in the url-plan were not sampled at all, and only 6 of 53 `service-area` pages were reached.
- Coverage gap: v1 cannot see indexing state. A page that is live, recently built, and completely unindexed looks identical to a healthy page here. That gap closes when GSC is wired in (see `docs/system-4-v2-activation.md`).
- Money-page dates are build dates, not edit dates. The 8 money pages sampled all resolve age from `sitemap_lastmod`, so any future rebuild resets their apparent age to 0 regardless of whether the copy changed. Adding `dateModified` to the page JSON-LD would make these pages genuinely scoreable.

## Recommended next actions (top 5)

1. No refresh work is due. The site published within the last 41 days, so re-run the scorer next cycle rather than manufacturing edits to pages that Google has barely finished crawling.
2. Raise coverage before the next run: `python3 scripts/refresh_scorer.py --slug restoration-groups --max-urls 950`. The current 120-URL sample missed all 16 `service-landing` pages (`/services/water-damage-restoration/` and siblings), which are the highest-value archetype on the site and the ones the priority rubric treats as priority 1 when they go stale.
3. Add `dateModified` to the JSON-LD on `/`, `/contact/`, `/service-areas/`, and the `/service-areas/{city}/` templates. All 8 money pages currently score off `sitemap_lastmod` (2026-07-11 / 2026-07-18), which tracks the last deploy, so a no-op rebuild will keep them looking permanently fresh and they will never trip the aging flag.
4. Wire GSC for this property so the next run can see indexing coverage and demand signals. This site went live inside the last 30 days, which is exactly when `not_indexed` and `Discovered - currently not indexed` matter most, and v1 is blind to both.
5. Watch `/blog/how-long-does-water-damage-restoration-take/` (41 days, `json_ld_date_modified`). It is the oldest URL on the site and will be the first to reach the 305-day aging threshold around 2026-05-21; nothing to do now, just the leading edge of the queue.
