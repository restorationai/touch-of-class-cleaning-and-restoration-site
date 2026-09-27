---
name: narestco-trauma-focus
description: Jose/NaRestCo pivoted to trauma focus 2026-07-14 — 60 pages rendered to STAGING awaiting Santino approval; GBP services + prod push held
metadata: 
  node_type: memory
  type: project
  originSessionId: 7c766860-0208-4520-89d3-5397f910f813
---

Jose Osuna (NaRestCo) wants to focus on trauma. Executed 2026-07-14:
- Template catalog v0.3.0: added trauma-scene-cleanup + unattended-death-cleanup (biohazard-cleanup de-overlapped — trauma/death phrases removed from its secondary keywords). crime-scene-cleanup + hoarding-cleanup already existed.
- narestco plan regenerated: 22 services × 14 areas = 365 URLs; 60 new trauma pages rendered ($2.12, claims lint clean, sensitive tone verified) — **on STAGING (staging.rankai-narestco.pages.dev), awaiting Santino's copy approval before prod push**.
- Content queue: 4 prioritized research-mode trauma posts queued (insurance/who-pays/unattended-death-guide/how-long) with compassionate-tone notes.
- Geo-grid: added "crime scene cleanup" + "trauma cleanup" (12 keywords now).
- HELD until pages are in prod: `gbp.py add-services --slug narestco` for the 4 trauma services (one service per intent; synonyms in descriptions — never keyword-stuff variants).
- Trauma economics: WA volumes tiny (10-140/mo) but CPCs $56-122; win via coverage + AI answers + referral layer (coroner/ME lists, funeral homes). Optional: micro-SKAG $10-15/day exact-match.

**⚠️ scaffold bug**: `build_site.py scaffold` OVERWRITES rendered content + custom files (functions/twilio/voice.ts!) despite skill doc claiming it preserves. Recovered via `git checkout -- sites/narestco/`. Needs a skip-existing guard before any future incremental build.

Also 2026-07-14: [[rank-ai-sales-playbook]] gained sales/what-is-rank-ai.html+pdf (canonical explainer, pricing canon). gbp_post.py now rotates job photos (fresh-first, LRU) — NaRestCo has only ONE photo, so pool must be filled (crew upload link or seed from images.narestco.com) for rotation to matter.
