---
name: single-source-of-truth
description: "LAW (09-04): one canonical store per client fact, surfaced in many places; NEVER ask a client for data we already hold anywhere (incl. inside uploaded documents)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-04T17:47:57.185Z
---

Santino 2026-09-04, after the Curt/Home Pride EIN incident (captured EIN written to company_phone_setup.business_ein was invisible in the app's Business Verification card, which reads companies.ein): "We definitely want things centralized so we prevent having to ask for something twice that we already have access to. If an item is needed in multiple places, it can be displayed or provided in multiple places."

**Why:** Asking a client for something they already gave us burns trust and looks disorganized; split stores make captured data silently invisible.

**How to apply:** (1) Every client fact gets ONE canonical store; other surfaces read from it or are synced writes, never independent stores. (2) Before any automation asks a client for data, it must check every place that fact could already live, including UNSTRUCTURED places: uploaded documents (hub docs, texted photos of paperwork), prior messages, GBP/GHL records. The EIN pipeline is the template: text-regex capture + vision extraction from texted document photos ([[phone-activation-pipeline-broken]] concierge) + nightly Claude scan of hub-uploaded docs (tollfree_autoreg watch) all run before an ask or re-ask fires. (3) When adding a new display of an existing fact, wire a read-fallback, don't fork the storage.
