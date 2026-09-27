---
name: call-list-standalone-repo
description: Daily call list split into its own repo restorationai/Rank-AI-Call-List (2026-08-25) for teammate handover; cutover to a new Railway service still pending
metadata: 
  node_type: memory
  type: project
  originSessionId: 7f37e576-865d-47c8-a41b-401a3232f432
  modified: 2026-08-25T00:22:01.724Z
---

**2026-08-25:** the daily call list was split out of `Rank-AI-Pipeline` into its own private repo **`restorationai/Rank-AI-Call-List`** so a teammate can own it without getting write access to the whole business monorepo (Rank-AI-Pipeline is owned by a *user* account, not an org, so collaborators get everything or nothing).

**What moved:** `scripts/callist/` minus the retired `call_autopilot.py`, so 10 files plus a new `callist/env_kv.py` and a new top-level `scheduler.py`. Three jobs: `callist` daily 12:20 UTC, `noshow` daily 13:00 UTC, `callist-notes` every 3h.

**Changes made during the split:**
- `env_kv.py` replaces `from client_concierge import kv_get, load_env` (the only cross-repo import; it pulled a 10k-line module in for two functions). Tree is now fully self-contained: only third-party dep is `requests`, since Anthropic is called over raw urllib. Verified by importing all 11 modules in a venv containing only requests.
- `auto_daily_call_list.load_env_value` now reads env FIRST instead of scraping the hard-coded `/Users/santino/restoration-ai/.env` path (the Aug 4 silent-401 root cause, see [[daily-call-list-automation]]).
- `scheduler.py` has a boot preflight printing where each credential resolved from.
- Santino chose to KEEP the literal cred fallbacks rather than go env-only, so `pit-c75a84bf...` (GHL) is in 3 files and `ntn_5649911157...` (Notion) in 1. **Rotating either key means editing code in TWO repos, not just Railway vars.** SendGrid key is env-only, not baked in.

**2026-09-17 — OLD COPY SWITCHED OFF.** The monorepo ops-worker had kept running the pre-split callist the whole time (nobody ever did the cutover), emailing contact@getrestorationai.com daily; SendGrid confirms delivery Sept 15/16/17. `callist` + `callist-notes` are now commented out in `scripts/ops_scheduler.py` (commit 63e4fa35); `noshow` kept (Fathom routing, unrelated). **There is now NO daily call list at all** until Levi's repo is deployed. Re-enable = uncomment two blocks.

**Levi's takeover stalled:** last commit to Rank-AI-Call-List was 2026-08-30 (`8d043c9`, adds a No-Show stage). His copy targets the IDENTICAL Notion HOME_PAGE_ID, MAIL_TO and GHL location as the monorepo, so if it ever runs it repaints the same page and mails the same box. Also: `get_or_create_persistent_page` reads `persistent_page_id.txt` from local state, so a first run on a fresh machine CREATES A NEW page instead of reusing Santino's; seed that file at deploy or he loses his bookmarked URL.

**Both Railway tokens in rank-ai/.env (`RAILWAY_API_KEY`, `RAILWAY_ACCOUNT_TOKEN`) are rejected as Not Authorized** — expired or mis-scoped. Railway CLI is not installed either, so no service can be inspected or created from the Mac.

**STILL PENDING:**
1. Create the new Railway service pointed at this repo, config-as-code `railway.toml`, volume mounted at `/data`, `RAI_BASE=/data`. Railway CLI is NOT installed on the Mac, so this is dashboard work.
2. Copy volume state (`snooze.json`, `grace.json`, `notion_page_id.txt`) from the ops-worker volume, or the new service paints a fresh Notion page and resurfaces every snoozed suggestion. The `callist-seed` blob in ops_kv is a July snapshot, treat as a floor.
3. Only AFTER the new service is verified: remove `callist`, `noshow`, and `callist-notes` from `DAILY_JOBS`/`JOBS` in `scripts/ops_scheduler.py` in the monorepo. Until then both run; the same-day guard and note-hash dedupe make a brief overlap safe but it will send two emails.
4. Add the teammate as a collaborator on the new repo + invite to the Railway project (project membership, NOT the account-scoped `RAILWAY_API_KEY`, which no callist script reads).

**Also outstanding:** `daily-call-list-PORTABLE-SETUP.md` at the Rank-AI-Pipeline root is stale (July 13, describes the retired Mac launchd setup) and its live SendGrid + GHL + Notion keys are already pushed to GitHub history. Deleting the file will not purge history; rotation is the only real fix.
