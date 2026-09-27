---
name: setup-email-standard
description: LAW (09-09) — setup@restorationai.io is THE identity for all registrar accounts and delegate-access invites; Squarespace account exists under it
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 996c1087-a104-44ea-9b1f-03b5fa628483
  modified: 2026-09-27T16:52:18.820Z
---

Santino (2026-09-09): "I have created the restorationai.io Squarespace account and I will use this moving forward even for GoDaddy and every other account."

**Why:** Frontline's Squarespace invite bounced ("account email doesn't match invite email") because the invite went to setup@ but no Squarespace account existed under that email. One registrar identity = invites always accept, one monitored inbox (domain_access_email.py watches it), survives personnel changes.

**How to apply:** Every delegate invite is requested TO setup@restorationai.io; every new registrar account gets CREATED under setup@restorationai.io. Existing personal accounts aren't churned retroactively. Squarespace account under setup@ exists as of 09-09 — accept pending Frontline invite from it.

**Exception (Santino 2026-09-22, TDI):** Cloudflare client-account memberships use contact@restorationai.io "for now" — when a client owns their own Cloudflare account and invites us as a member (TDI/Rob Carpenter was the first), the invite goes to contact@, NOT setup@, because contact@ is our existing Cloudflare login and accepts with one click. setup@ mail routes into the contact@ inbox, so misdirected invites are still visible. TDI model: client-owned CF account, we're Administrator member, site hosting stays in our Pages.

**Citation/directory signups (Santino 2026-09-27):** per-client dash aliases setup-{slug}@restorationai.io are the signup standard (Santino chose dash over plus: accepted by every form, looks like a real business inbox to BBB/directory reviewers). Workspace routing rule a68b5, pattern `(?i)^setup-[a-z0-9-]+@restorationai\.io$` → contact@ with X-Gm-Original-To header (verified live 09-27). No per-client creation ever. Agent must NOT get Workspace admin to manage this — Santino owns the admin console. Plain setup@ stays on the three 09-27 listings created with it (no migration). Login email = ours permanently; public business-email fields = client's own address.
