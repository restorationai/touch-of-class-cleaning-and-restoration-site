---
name: rank-ai-meta-lead-quality-diagnosis
description: "Why Rank AI's demos collapsed in June 2026 — Meta Advantage+ broad targeting flooding wrong-industry leads"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4a2c22a5-6f10-4b5f-b214-ad0f26ff204b
---

June 2026: Rank AI (restoration-contractor marketing product) demo bookings collapsed to ~zero qualified; leads were dog groomers/electricians. Diagnosed via Meta Ads API + GA4.

**Root cause:** All ACTIVE Meta ad sets run `advantage_audience=1` (Advantage+ audience ON), NO detailed targeting, age 18-65, entire US, optimizing `OFFSITE_CONVERSIONS` on a shallow quiz-completion event. Meta optimizes for cheapest conversions → floods non-restoration SMBs. Creative IS correctly restoration-specific ("High-Profit Emergency Restoration Jobs"), so it's a targeting/optimization problem, not messaging. No qualifying gate in funnel. Ad account is "Ignite Systems Reviews" (act_1822880824941953) — polluted pixel history from a prior reviews product (paused "Los Angeles - Get Free Reviews" campaigns) drags Advantage+ toward general SMBs.

**Timeline:** biggest-spending active ad set = "New Testing - May 21st - Website"; took over budget ~30 days before the June 21 collapse. Last 30d: ~$2,700 spend, 25 leads (~$108 CPL), "NEW Testing Campaign" outspends real "Restoration AI - Prospecting".

**Recommended monthly focus:** "Restore qualified lead flow — fix Meta targeting + funnel qualification." Fixes: turn off Advantage+ expansion + add restoration detailed targeting; add industry disqualifier question to quiz/funnel; pause NEW Testing Campaign + consolidate; optimize for booked/qualified event; clean/replace pixel-polluted ad account; add GA+Pixel tags to quiz funnel (currently untracked — both GA props near-empty).

**Access (verified working):**
- GA4: service-account key at `Restoration-AI-website-2026-main/.ga4-sa.json` (claude@restoration-ai-analytics.iam.gserviceaccount.com), now ACCOUNT-level Viewer on "Restoration AI" (397914758) → all props incl. restorationai.io (541541035) + Opt Digital Funnel (542407905, not launched).
- Meta: token + act_1822880824941953 (portfolio "Ignite Systems"); pixel 640413502453389. Use Ignite app to mint system-user token. ads_read works.
- Stripe + Supabase service-role in `Restoration-AI-APP-main/.env.local` — NOT yet queried; next step to confirm actual signup industries.
- GHL pit token works but needs correct 22-char Location ID (UI account# 0-398-685 is wrong format).

Related: [[notion-team-focus-framework]] (this diagnosis should set the Notion monthly focus), [[narestco-paid-and-geogrid-state]].
