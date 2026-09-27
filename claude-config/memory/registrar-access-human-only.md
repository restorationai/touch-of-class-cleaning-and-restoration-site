---
name: registrar-access-human-only
description: Santino 09-06 — browser agents get NO registrar (GoDaddy) sessions for now; nameserver changes stay human-performed; revisit later
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-07T05:21:44.193Z
---

Santino (2026-09-06, during Mac Mini setup): "NO, a human will still do this, for now. Eventually, we'll add this in" — regarding giving the Mini's browser agent a GoDaddy session.

**Why:** Registrar access = power to move any delegated client domain. He wants that action human-performed for now, even though the domain_connect playbook exists in [[browser-agent-suite]].

**How to apply:** Don't ask for or establish registrar portal sessions on agent machines. Agent login scope = agency Google + Bing Places only. Nameserver cutovers at launch remain manual steps Santino performs. When he says he's ready, add the GoDaddy session to the Mini's persistent profile and enable domain_connect there.
