---
name: auto-localhost-testing
description: "After any Restoration-AI-APP change, auto-serve it on localhost:5173 for testing — don't ask each time"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4086248c-e0b1-493b-bda1-ff4d4ae1b894
---

When I make a change to **the app** (Restoration-AI-APP frontend), **automatically make it live on localhost:5173** so Santino can test it immediately. Do NOT ask "merge or test?" each time — just serve the branch locally and tell him what to click.

**How to apply (the run loop):**
1. Push the app change to a feature branch on GitHub (code source of truth is the GitHub repo — see [[app-source-github-not-desktop]]).
2. In the **desktop clone** `/Users/santino/Desktop/mywebsitecode/Restoration-AI-APP-main` (it IS a real git clone of the repo, with the working `.env.local` + `node_modules`): `git fetch` + `git checkout <branch>` + `git pull`.
3. Free port 5173 (`lsof -ti tcp:5173 | xargs kill -9`) and restart `npm run dev` in the background (must stay on **5173** — the OAuth redirect URI is registered for `localhost:5173`).
4. Tell Santino to hard-refresh and where to click.

**Only merge to `main` (production) AFTER Santino confirms the localhost test passes.** Backend/edge-function changes still deploy straight to Supabase (they have no localhost equivalent). After a feature merges, switch the desktop clone back to `main`.

**Why:** Santino wants a fast, hands-off test loop — see the change running right away instead of being asked every time.
