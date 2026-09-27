---
name: quiet-hours-outbound
description: "LAW (09-07): never send client messages late night — queue for their morning business hours; applies to MY direct GHL/email sends, not just Monica"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-08T05:56:30.255Z
---

Santino (2026-09-07, ~11pm, after I sent Rob Carpenter an SMS at 10:57pm PT): "Its almost 11 pm. These messages should be queued, not sent now. Lets queue a message in the morning."

**Why:** A late-night business text reads as unprofessional and wakes people. Monica's flows already hold for business hours (kickoff_prep after-hours hold, 60-min quiet window); my DIRECT sends via `la._ghl` bypass those guards and must apply the same judgment.

**How to apply:** Before any client-facing send (SMS especially, email too), check the client's local time. Outside ~8am-7pm client-local: draft it, tell Santino it's ready, and either schedule it or send it in their morning. GHL timestamps in threads are UTC — convert before judging (23:09Z = 4:09pm PT, fine; 06:57Z = 10:57pm PT, not fine). Also from same exchange: don't proactively mention scheduling another call in client messages unless Santino asks ([[registrar-access-human-only]] pattern: he decides the personal touches).
