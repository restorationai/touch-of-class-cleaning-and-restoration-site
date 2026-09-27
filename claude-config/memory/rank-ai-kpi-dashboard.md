---
name: rank-ai-kpi-dashboard
description: Rank AI Command Center — zero-backend KPI dashboard aggregating Meta/GHL/Stripe/GA4/Supabase
metadata: 
  node_type: memory
  type: project
  originSessionId: 4a2c22a5-6f10-4b5f-b214-ad0f26ff204b
---

Built June 2026 at `rank-ai/kpi-dashboard/`. Zero-backend design (user explicitly did NOT want a full app): Python `aggregate.py` pulls 5 sources → writes one permanent JSON snapshot per month to `data/YYYY-MM.json` (+ `data/index.json`); static `index.html` renders the scoreboard. History = git-versioned monthly files (no DB — Supabase is a *source*, not storage). Secrets in `config.env` (gitignored, never deployed); only aggregates published (no PII/keys).

Scoreboard centers on REAL KPIs (not CTR/CPC vanity): Demo→Close %, Cost/Demo, Cost/Client, CAC, Lead→Demo, MRR. Run: `python3 aggregate.py [YYYY-MM]`.

**First readout (June 2026):** ad spend $2,269, 17 leads ($133/lead), 9 demos booked, **0 clients signed → 0% demo→close**, lead→demo 53% (healthy), MRR $9,483 / 20 active subs. Insight: top of funnel works; the leak is demo→close (unqualified bookings not closing) — sharpens [[rank-ai-meta-lead-quality-diagnosis]]. NOTE: contradicts user's perception of "no demos" — CRM shows 9 booked.

Source quirks solved: GHL blocks urllib UA (Cloudflare err 1010) → set browser User-Agent. GHL Sales Pipeline id hPnHBxO63YMecyG219V5, "Demo Meeting Booked" stage 5256e690. Supabase count via Prefer:count=exact + Content-Range; companies date col created_at.

**Deploy (not yet done):** `wrangler pages deploy . --project-name rank-ai-command-center` + Cloudflare Access (@restorationai.io only) since it shows revenue. Auto-refresh via weekly GitHub Action (not yet scaffolded). Should feed the monthly objective into [[notion-team-focus-framework]].
