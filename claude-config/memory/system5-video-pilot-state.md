---
name: system5-video-pilot-state
description: "First-ever System 5 video LIVE UNLISTED (flood-fixers, youtu.be/YSd47aUhq_c) awaiting Santino review; channel is personal 'Gabriel Herrera' — MUST rename/brand before public; publish cmd ready; geo mode built"
metadata: 
  node_type: memory
  type: project
  originSessionId: b7646e8b-4a3a-42b9-809a-4dc1c55c9f5c
---

2026-07-05: System 5 produced its first video ever. Pilot: https://youtu.be/YSd47aUhq_c (unlisted, 2:15, flood-fixers "First 24 Hours After Water Damage in San Diego", cost ~$0.78). Auth works headless via app user_integrations refresh token (CO-1775605259504) + GOOGLE_OAUTH_CLIENT_ID/SECRET in .env.

**Blockers before public:** (1) uploads land on personal channel "Gabriel Herrera" (UClRvoLXQXdnc_bNCu-J9CKQ) — rename to Flood Fixers or migrate to brand channel; (2) channel needs phone verification (youtube.com/verify) for custom thumbnails.

**CORRECTION 2026-07-10 (per Santino): the narestco channel is "Jose Osuna (National Restoration)" (@cheosuna19, UCI9Mhaf4PhSSaCWeREaovqw) — NOT "Gabriel Herrera"** (Gabriel = flood-fixers only). YouTube **silently ignores API renames on personal channels** — rename MUST be manual: studio.youtube.com → Settings → Channel → Basic info. Pinned marketing_action_plan row (action_key d29dd624963f0e86, CO-1771290587387) now tracks the narestco rename; it gates making narestco videos public.

**After Santino approves:** `python3 scripts/video_maker.py publish --slug flood-fixers --post what-to-do-first-24-hours-water-damage --video-id YSd47aUhq_c` (flips public + writes youtube_id frontmatter → embed + VideoObject schema + deploys).

**Geo mode built** (Merchynt-style standalone rankers): `video_maker.py geo --slug X --service Y --city Z` — claims-gated proof points, "{Service} {City} | {Brand}" titles. Dry-run verified, nothing uploaded. Target cadence once trusted: 1 blog video + 2-3 geo videos/wk/client via [[ads-journal-system]]-style pacing in video_cron.py. Fix queued: narration overshoots 90s target (cap words tighter).
