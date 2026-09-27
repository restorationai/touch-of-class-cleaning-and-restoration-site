---
name: brightlocal-api
description: "BrightLocal API key LIVE 09-02 (x-api-key, api.brightlocal.com/manage/v1); 500 CB credits confirmed; Listings data API path still unknown"
metadata: 
  node_type: memory
  type: reference
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-04T05:37:44.033Z
---

BrightLocal API working as of 2026-09-02. Key in rank-ai/.env BRIGHTLOCAL_API_KEY + repo secret BRIGHTLOCAL_API_KEY (Rank-AI-Pipeline). Auth: `x-api-key` header ONLY (Bearer/api-key 401). Base: https://api.brightlocal.com

Confirmed live:
- GET/POST /manage/v1/locations (+ /{id}) — full NAP CRUD; account has 1 location: "Restoration AI" (Atascadero, location_id 4140336, customer_id 521605)
- GET /manage/v1/citation-builder (+ /{campaign_id}) — campaign detail incl. available_citations, available_publishers, per-citation submission status (ordered/submitted/pending/live), generated credentials (email_password/directories_password per campaign)
- GET /manage/v1/citation-builder/credits — {"credits":500} (the purchased Quick credits, API-spendable)
- Draft CB campaign 996268 exists for the Restoration AI location (created 09-01, status saved, unpaid, 0 ordered) — Santino's manual test, usable as the ordering guinea pig

ORDERING CRACKED 09-03 (supervised test PASSED, 500→490 credits): the pay-with-credits endpoint is `PUT /manage/v1/citation-builder/{id}/confirm` with {package_id: cb10|cb15|cb25|cb30|cb50|cb75|cb100, auto_select, citations[], publishers[], remove_duplicates, express, notes}. `/purchase` is a DIFFERENT endpoint (card?) whose validator reads saved campaign state — dead end, don't use. One CB campaign per location; top-ups via create-secondary-campaign (unwired). Aggregator publishers cost extra credits; we default to none. Gotchas: Cloudflare 403 code 1010 on python-urllib UA (send curl UA); locations POST needs region as FULL state name + region_code as abbrev; business_category_id 967 = Water damage restoration service; SAB note in `notes` asks to hide address.

Docs trick: developer.brightlocal.com is JS-only — render with playwright (chromium at ~/Library/Caches/ms-playwright/chromium_headless_shell-1217, launch with executablePath). Listings data API doc EXISTS: developer.brightlocal.com/docs/data-apis/8owbgtne72ygc-listings-api (Harry never needed).

Tooling: scripts/brightlocal.py (audit/setup/order/status; state in clients/{slug}.json "brightlocal"). 19 clients NAP-ready via brand.ts (canonical line, never DNI). Restoration AI own campaign 996268 ORDERED cb10 09-03 (ETA 09-18). Greg (PuroClean ELV): location 4147029, campaign 997242, package size TBD by Santino (40 not native: cb30/cb50/25+15).
