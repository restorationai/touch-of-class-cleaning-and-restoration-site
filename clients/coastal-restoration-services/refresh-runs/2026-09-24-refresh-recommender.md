# Refresh Recommender - Coastal Restoration Services Inc - 2026-09-24

**Origin:** https://callcrs.com (apex)
**URLs evaluated:** 120
**Actions queued:** 1
**GSC enabled:** true (scorer v2 GSC URL Inspection data present; no search_signals on any candidate)

## Summary by action

| Action | Count |
| --- | ---: |
| refresh | 0 |
| audit_then_decide | 1 |
| request_indexing | 0 |
| fix_canonical | 0 |

## Action: refresh content

None. Every URL is between 2 and 73 days old (aging threshold 305, stale threshold 365). The site was rebuilt in July 2026, so the first age-based refresh wave is not expected before about May 2027.

## Action: audit then decide

| Priority | URL | Flags | Why |
| ---: | --- | --- | --- |
| 3 | /service-areas/avila-beach-ca/mold-remediation/ | none (gsc coverage: Discovered - currently not indexed) | 56 days old (json_ld_date_modified) but Google has discovered it and never crawled it; the scorer left it unflagged because index_status is UNKNOWN, not FAIL |

## Notes

- URLs skipped because already in content-queue: none (10 active queue items, none overlap live URLs)
- URLs where date extraction failed: none (101 json_ld_date_modified, 19 sitemap_lastmod)
- Fresh and skipped: 119 URLs, all GSC 'Submitted and indexed'
- Coverage gap: refresh_scorer.py flags not_indexed only on index_status FAIL, so 'Discovered - currently not indexed' (UNKNOWN) goes unflagged; no striking_queries or low_ctr signals were present this run

## Recommended next actions (top 5)

1. /service-areas/avila-beach-ca/mold-remediation/: confirm it returns 200, is self-canonical, has no noindex, and is in the sitemap. Check that the copy for 'mold remediation avila beach' is not a near-duplicate of the Arroyo Grande, Atascadero, and Grover Beach mold remediation pages. Add contextual links to it from /service-areas/avila-beach-ca/ and /services/mold-remediation/, then request indexing in GSC URL Inspection.
2. Pipeline fix: update scripts/refresh_scorer.py so index_status UNKNOWN with coverage states 'Discovered - currently not indexed' or 'Crawled - currently not indexed' raises not_indexed. Future runs will then route this case to request_indexing automatically.
