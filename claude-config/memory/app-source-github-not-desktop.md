---
name: app-source-github-not-desktop
description: "Always read the Restoration-AI-APP from its GitHub repo, never the stale desktop copy"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4086248c-e0b1-493b-bda1-ff4d4ae1b894
---

When inspecting or changing "the app" (the client-facing React dashboard, Restoration-AI-APP), **always pull the latest from GitHub**, NOT the desktop folder.

- Canonical source: **https://github.com/restorationai/Restoration-AI-APP** (private; clone with `GITHUB_PERSONAL_ACCESS_TOKEN`).
- Do NOT use `/Users/santino/Desktop/mywebsitecode/Restoration-AI-APP-main` — it's a stale zip download and may be out of date.

**Why:** the desktop copy drifts from production; the GitHub repo is the live truth.
**How to apply:** `git clone --depth 1 https://${GITHUB_PERSONAL_ACCESS_TOKEN}@github.com/restorationai/Restoration-AI-APP.git <tmp>` and read from there each time.

App stack: Vite + React + TS, Supabase (auth + `user_integrations` for OAuth tokens + `marketing_*` tables), Netlify, some Supabase edge functions + n8n webhooks. OAuth (Google Ads/GBP/Search Console via one "Connect Google" button, YouTube separate) lives in `components/AIMarketing.tsx` + `components/GoogleOAuthCallback.tsx` + `supabase/functions/google-oauth-exchange/`. The pipeline's [[gbp-api-access-reapplication]] business.manage scope is already wired here.
