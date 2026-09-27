---
name: anthropic-credit-outage-canary
description: 09-14 credit exhaustion killed ALL AI surfaces silently for hours; credit_canary.py now trips an SMS; call_alerts CI env was also broken
metadata: 
  node_type: memory
  type: project
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-14T23:26:46.789Z
---

2026-09-14 incident: the Anthropic API account ran out of credits at ~9:07am PT. EVERY AI surface died at once with 400 "credit balance too low": Monica composes (concierge), meeting debriefs (Rachelle/Desert Valley kickoff left unprocessed), the dev agent, email intake classification. Clients waited hours with no replies (Tony, Jared, Robert/TDI, Sarah, Amin, Mike/Arch). Nothing alerted anyone; CI-failure emails drowned.

**Fixes shipped:** `scripts/credit_canary.py` rides call-intel.yml (every 30 min): 1-token haiku probe; on credit-400 SMSes Santino's ops cell via GHL (no Anthropic needed), dedupe 4h in ops_kv `credit-canary-alert`, one-time "restored" SMS on recovery. Also fixed call-intel.yml: the call_alerts step had NO env vars and no python-dotenv install, so [[call-tracking-dni]] queue #6 alerts had failed silently on every CI run since shipping.

**Why:** billing-level failures kill everything at once and look like "Monica is broken" per-client. **How to apply:** when multiple unrelated clients all report silence, check `gh run list` FIRST for cross-workflow failures, then probe the API key directly; the failure drains automatically after top-up (failed debriefs are left unprocessed for the next run). Also: outbound sends that don't need composition (send_message via GHL) still work during an outage; Claude-in-session can compose manually.

Related: [[client-concierge]] [[quiet-hours-outbound]]
