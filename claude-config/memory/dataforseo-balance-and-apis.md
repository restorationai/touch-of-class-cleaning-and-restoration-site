---
name: dataforseo-balance-and-apis
description: "DataForSEO account ran out of prepaid balance (402) — caused NaRestCo's fake \"ranking collapse\"; which DFS APIs we use"
metadata: 
  node_type: memory
  type: project
  originSessionId: acdb19a7-afd6-4946-9442-cbe973522dd1
---

On 2026-07-01 the shared DataForSEO account hit **$0 / negative balance** (`-$0.0016`), returning **HTTP 402 Payment Required**. This — not a real ranking drop — caused NaRestCo's geo-grid to show an all-red / avg-0.0 map pack. The bi-weekly geo-grid cron (`railway.geogrid-cron.toml`, 1st & 15th 08:00 UTC) and AI-search scans hit the same wall for **every client**, so scans stay stale until the balance is topped up. Check balance via `GET /v3/appendix/user_data` (`money.balance`); creds live in `~/.claude.json` MCP env (`DATAFORSEO_USERNAME/PASSWORD`), not the pipeline `.env`.

**Fixes shipped (both pushed to main):**
- Pipeline guard in `scripts/geogrid_store.py` `scan_and_store`: retries $0-cost (errored) points once, and **raises if >40% still errored** so the cron skips the write and keeps the last good scan — no more poison rows. Key tell: an errored point bills **$0**; a genuine "not ranking here" still bills **>$0**. That's how failed-scan vs real-zero are distinguished.
- App UI ([[rank-ai-kpi-dashboard]] adjacent): `GeogridOverviewCard` + `GeogridCompareView` now separate "couldn't measure" (grey) from "not ranking" (red), and the compare view no longer coerces null→0.0 and mislabels a failed scan as "improved 5.0".

**Which DataForSEO APIs we use:** SERP/Maps (geo-grid) and **AI Optimization `llm_responses`** (powers the AI Search tab, `scripts/ai_search_scan.py`). We do **NOT** use the **Backlinks API** at all, nor AI Optimization **`llm_mentions`** (top_domains/top_pages/share-of-voice). DataForSEO made Backlinks + AI Optimization **free (usage-based, no monthly subscription)** as of ~2026-07 — worth adopting: Backlinks for competitor link-gap → action plan; `llm_mentions` to find which domains to get cited on to lift AI-search visibility. (402 is about pay-as-you-go **balance**, separate from the subscription change — still must fund the account.)

To backfill NaRestCo once funded: `python3 scripts/geogrid_cron.py --slug narestco` (or `/tmp/narestco_rescan.py` for just the failed keywords). NaRestCo is actually **improving** where measured (water/fire/mold-remediation top-3 coverage up vs June). Company id `CO-1771290587387`.
