# Refresh Recommender — National Restoration Construction — 2026-05-25

**Origin:** https://narestco.com (apex)
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

No URLs reached the 12-month staleness threshold this cycle. The narestco apex cutover completed on 2026-05-17, so every indexable page has an age between 8 and 12 days. There is nothing to refresh.

## Action: audit then decide

No URLs require manual audit this cycle. Layer 1 produced a clean signal: every candidate has a valid `sitemap_lastmod` or `json_ld_date_modified` date and zero scorer flags fired.

## Notes

- URLs skipped because already in content-queue: 0
- URLs where date extraction failed: 0
- URLs skipped because fresh (age < 305d, no flags): 120 (100% of inspected pages)
- Coverage gap: v1 cannot detect not_indexed or canonical warnings; GSC integration is deferred to System 4 v2. Until then, indexing health relies on manual GSC Coverage spot-checks.

## Recommended next actions (top 5)

1. No refresh actions are needed on narestco this cycle. Re-run the Layer 1 scorer on the next monthly cadence (target: 2026-06-25) and the first commercial pages will start crossing the 305-day aging threshold in late February 2027 (305 days after the 2026-05-17 cutover).
2. Plan ahead for the v2 GSC activation per docs/system-4-v2-activation.md so that by the time pages reach the 305-day aging threshold, indexing-status signals (`not_indexed`, `index_warning`) feed into Layer 2 alongside the page-age signals.
3. Continue burning down the System 2 content-queue. Three queued blog drafts (`average-insurance-payout-for-water-damage`, `does-homeowners-insurance-cover-broken-pipes-under-foundation`, `does-homeowners-insurance-cover-water-damage-from-rain`) are still in `status: queued` from the 2026-05-17 batch; getting them written before the next refresh cycle keeps the publish stream healthy.
4. After the next monthly System 3 onsite audit, re-run this Layer 2 recommender the following day to keep the cadence aligned. The current audit verdict is amber (apex baseline); rerun ordering should be audit then refresh-recommender, not the other way around.
5. Verify that `json_ld_date_modified` is being emitted on the 18 service-landing pages and 10 service-area pages on narestco.com. Layer 1 currently relies on `sitemap_lastmod` for most non-blog pages (age 8 days, source `sitemap_lastmod`). Once these pages start carrying first-party `dateModified` JSON-LD, future age computations will be more precise than the sitemap-wide lastmod, which can be noisy after bulk redeploys.
