---
name: wix-domains-no-ns-change
description: "Wix-purchased domains can NEVER change nameservers (confirmed 09-09, DISS) — launch path = transfer domain away (to our Cloudflare account), ~5-7 days"
metadata: 
  node_type: memory
  type: reference
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-09T14:43:01.295Z
---

Confirmed 2026-09-09 (DISS Restoration launch): Wix does not allow nameserver changes on Wix-purchased domains — not in the UI and not by support request (their "Request NS change" help article is just a feature-request vote collector). DNS-record pointing IS allowed, but Cloudflare Pages apex needs CF DNS, so pointing doesn't fit our stack.

**Launch path for Wix-registered domains:** transfer the domain away — cleanest destination is OUR Cloudflare account (zone already exists there pre-launch; NS flip happens automatically at transfer completion). Steps: Wix → Domains → Transfer Away → unlock + get EPP/auth code (can take up to ~2 days to email) → initiate transfer in Cloudflare Registrar → ~5-7 days. ICANN 60-day lock applies only if registered/transferred/contact-edited within 60 days. Wix domains are a launch-lead-time edge case: start the transfer the day the client signs. Registrar work = Santino per [[registrar-access-human-only]].
