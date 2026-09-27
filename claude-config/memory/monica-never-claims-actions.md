---
name: monica-never-claims-actions
description: "RX/Barbara incident 09-09 - Monica confirmed a list-removal she cannot execute; opt-out requests need an executable path or escalation, never a bare \"done\""
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-09T19:33:18.637Z
---

2026-09-09 Restoration Xpress incident: a review-campaign recipient (Barbara Ilofszky) asked to stop; Roy forwarded it 08-31. Monica replied "Got it, pulling Barbara off the list now" on 09-01 but has NO tool that writes review_requests, filed no note for the promise, and never disambiguated (three Barbaras on RX's list). Step 4 fired 09-09; Roy escalated by text, call, and email. Claude opted her out manually (review_requests.opted_out + contacts.opted_out) and apologized.

**Why:** an AI confirming an operational action it cannot perform is worse than no reply; the client stops watching because they believe it is handled.

**How to apply:** Monica must never claim a state-changing action is done unless a tool actually performed it in that turn. Removal/opt-out requests: either execute via a real opt-out tool or say "passing this to Santino right now" AND file a [TODO-SANTINO] note naming the exact person/number. BUILT 09-09 same day: _maybe_execute_optout hook in client_concierge.py (phone/unique-full-name resolution, verified writes, [FOR MONICA] confirm directive, escalation on ambiguity) + LIST REMOVALS hard rule in CAPABILITY_CONTRACT. Related: [[client-concierge]] (Tony Mendez rule: never promise Santino will call - the 08-31 RX reply violated that too).
