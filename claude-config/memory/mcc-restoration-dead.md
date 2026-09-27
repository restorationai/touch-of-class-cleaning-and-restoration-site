---
name: mcc-restoration-dead
description: "MCC Restoration = DEAD client (status Suspended, confirmed 09-19); no work of any kind — content, video, GBP, DFS, rename all gated off"
metadata: 
  node_type: memory
  type: project
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-19T23:19:02.301Z
---

Santino 2026-09-19: "MCC is a dead client. Shouldn't be doing anything for
their account." Company CO-1783376797396, slug mcc-restoration, DB status
Suspended.

Gate audit (09-19): master_scheduler (content) excludes "suspended" ✓;
gbp.py + geogrid_cron (DFS spend) exclude it ✓; gbp_parity uses
status=eq.Active ✓; rename_pipeline Active-only ✓; video_cron was one gap ("suspended" added 09-19). SECOND LEAK found 09-21:
weekly-maintenance's run-due step had NO Supabase env, so the DB-status
check failed OPEN and content published for MCC. Fixed: step env added AND
master_scheduler now hard-dies without SUPABASE_URL (missing env =
misconfiguration, never fail-open). The 09-18 post predated suspension.

Their open rename candidate rows still exist in marketing_gbp_suggestions
but are unreachable (board + pipeline are Active-only). Site sites/
mcc-restoration and clients/mcc-restoration/ remain in the repo as
inert history, like [[mold-solutionz-dead]] before its removal.
