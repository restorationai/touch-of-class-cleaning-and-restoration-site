# Refresh Recommender — ProBrite Gen — 2026-05-18

**Origin:** https://probritegen.com (apex)
**URLs evaluated:** 16
**Actions queued:** 0
**GSC enabled:** false (v1 — sitemap + page-date scoring only)

## Summary

All 16 URLs report `date_source: sitemap_lastmod` with today's date because
probritegen just rebuilt with `@astrojs/sitemap` integration. The aging
threshold (305+ days) cannot fire on fresh sitemap timestamps.

This will NOT produce useful aging signals until either:
1. JSON-LD `datePublished` is added to each page (then aging reflects
   when content was AUTHORED, not when sitemap was REGENERATED), or
2. System 4 v2 is activated for probritegen with GSC URL Inspection
   (then the `not_indexed` and `index_warning` flags fire independent
   of dates) — see `docs/system-4-v2-activation.md`

## Recommended next actions

None this run.

For meaningful refresh signals starting next month:
1. Add JSON-LD Article schema with `datePublished` to each `blog-post-N.astro`
   page. Use the original content creation date (probably May 2026).
2. Re-run refresh_scorer in ~30 days to see aging fire correctly.

## Next scheduled run

30 days out: 2026-06-17.
