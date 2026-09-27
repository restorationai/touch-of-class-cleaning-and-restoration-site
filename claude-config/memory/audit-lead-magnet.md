---
name: audit-lead-magnet
description: "Free-audit lead magnet LIVE on rank.restorationai.io (2026-07-05): 2-step stepper (business name → GBP match picker → contact) → Railway POST /lead-audit → full report (~$0.55, ~3-5min); landing-page/ repo is the ONLY prod source (sales/rank-ai is DEPRECATED — an agent once deployed it over prod)"
metadata:
  type: project
---

Live 2026-07-05. Flow: rank.restorationai.io "See Where You Rank Free" card → GET business-lookup (DFS listings, top-3 GBP match cards) → contact (first/email/mobile) → POST /lead-audit (Railway rank-ai-api) → job (marketing_jobs type=lead_audit; limits 10/day global, 3/IP, 2/domain; lookup 60/15) → scripts/lead_audit.py: Claude site profile + pinned GBP identity + 9 organic queries + 5x5 mini geo-grid heatmaps (R2) + ChatGPT/AIO citation checks (names real competitors) + reviews compare + revenue RANGES → HTML report on public R2 lead-audits/ + email via SendGrid (lead + notify contact@). "Why this matters" stats ONLY from docs/audit-stats-library.md (13 sourced entries). PII → private bucket rankai-leads-private.

**How to apply:** (1) landing-page/ (own git repo, push-to-main auto-deploys) is the canonical rank.restorationai.io source — NEVER edit/deploy sales/rank-ai (DEPRECATED.md marks it; caused a prod overwrite+rollback on 07-05). (2) SMS report delivery auto-enables when ESTIMATE_SMS_FROM/SID/TOKEN get set on the rank-ai-api Railway service after tollfree +18338056699 (HH2a1acd…) clears PENDING_REVIEW. (3) Review links display restorationai.io/r/* via worker 'review-link-redirect' → 302 → app. (4) Known polish items: branded reports domain instead of r2.dev; stuck-job sweeper (Railway redeploys kill in-flight audits). See [[review-reactivation-engine]].
