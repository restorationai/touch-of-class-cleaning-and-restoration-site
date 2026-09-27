---
name: per-client-architecture
description: "LAW 09-19 — all systems move to per-client isolated execution (matrix fan-out), never bulk sweeps with shared clocks; conversion roadmap inside"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-19T15:25:14.953Z
---

Santino 2026-09-19: "I really want us to move towards being on a
per-client basis for ALL of our systems... will not break as we acquire
more clients." Follows the per-client SLA ruling of 09-17.

**Why:** Bulk sweeps share one wall clock — capacity is fixed while the
fleet grows, and one slow client starves others (narestco 9 days
postless; video runs cancelled at 3h after publishing 16-24). Per-client
jobs scale by adding parallelism and fail with the client's name on the
alert.

**How to apply:** The house pattern is plan-job (cheap `list-due`
emitting JSON slugs) + GH Actions matrix (one isolated job per client,
max-parallel 5-6, per-client timeout, per-client commit scoped to that
client's paths with pull-rebase-retry x5 + jitter). Converted so far:
content-daily (09-19, validated 15 jobs/0 fail), video-automation
(09-19). Judging/advancing already per-client: watchdog SLA, A2P hourly
advance, rename workers.

**Remaining bulk (conversion roadmap, rough priority):**
1. client-ops-sync nightly — biggest bundle; split per-client steps
   (ledger/checklist, gbp_auto_apply, gbp_parity, photo harvest, site
   audit) into a matrix; keep truly fleet-level steps (agency_tf_watch,
   watchdog, cutover harvest) in a small serial job.
2. weekly-maintenance — AI scan is bulk-with-budget shards; works, but a
   matrix would retire the budget math. Also still needs the clean-exit
   treatment (concludes 'cancelled' while succeeding).
3. gbp-maintenance weekly (posts/photos loop) — cheap units, lower urgency.
4. monthly-reports — per-client loop, minutes total; lowest urgency.
Leave event-driven loops alone (concierge inbound/email/nudge — work is
already per-message; supabase-sync backstop is cheap).
