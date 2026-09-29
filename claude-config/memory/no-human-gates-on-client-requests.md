---
name: no-human-gates-on-client-requests
description: "LAW (09-28) — clear client change requests auto-run; replace approval holds with knowledge in Monica's classifier + dev_agent.md, never add new gates"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 996c1087-a104-44ea-9b1f-03b5fa628483
  modified: 2026-09-28T17:01:47.058Z
---

Santino (2026-09-28, TDI/Rob footer numbers): "If he requests it, we can just do it. I don't want to have to oversee something when someone makes a request like this anymore... It can just go through as long as Monica deems it necessary. We can add anything to Monica's knowledge base."

**Why:** The phone-number hold in feedback_router parked Rob's explicit request as TODO-PROPOSED while the rest of his message shipped; the "done" text omitted it and he had to ask twice. Held items have no escalation, so they rot.

**How to apply:** When a gate blocks clear client requests, remove it and move the safety into judgment: CLASSIFY_SYSTEM (client_concierge.py) decides what is a real request; scripts/dev_agent.md says how to execute safely. Only true complaints still route to a human. Relates to [[monica-never-claims-actions]] and [[call-tracking-dni]].
