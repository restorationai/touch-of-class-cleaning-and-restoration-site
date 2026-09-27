---
name: rto-bda-embed-csp
description: "BDA Digital = Bob Olson's paid-ads agency on RT Olson (Jared Shoemaker/Zheng/Mike Bawol); embed form frame-ancestors CSP blocks third-party iframing FLEET-WIDE (only rt-olson fixed 09-17)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 996c1087-a104-44ea-9b1f-03b5fa628483
  modified: 2026-09-17T19:34:12.889Z
---

Two Jareds in our world: Jared Toppenberg (Frontline client) and **Jared
Shoemaker of BDA Digital** (jared@bdadigital.us, 951-201-5199), Bob Olson's
paid-ads agency on RT Olson. BDA crew: Zheng Lin (admin), Mike Bawol
(analytics, mike@bawolppc.com — has GA4 Editor on property 552158566 since
2026-09-17; GTM invite for GTM-PKJQHGRF is a manual UI step). They iframe
our /embed/estimate form on their paid landing pages.

**Fleet gap:** every client site's `public/_headers` sends
`Content-Security-Policy: frame-ancestors 'self' https://app.restorationai.io`
on ALL routes, which silently blocks any third party from iframing
/embed/estimate. Fixed on rt-olson only (commit 44025d91: `/embed/*` rule
with `! Content-Security-Policy` + `frame-ancestors *`). The starter
template and every other client site still have the lockdown — apply the
same override before handing the embed snippet to anyone else.

Related: [[working-state-doc]]
