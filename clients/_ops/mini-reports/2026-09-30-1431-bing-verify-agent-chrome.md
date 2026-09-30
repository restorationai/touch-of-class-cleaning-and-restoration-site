# 2026-09-30 14:31 PDT — Bing Places verify in agent Chrome (read-only)

Trigger: claude-inbox-1790803743 (UNSUPERVISED), the answer to NEED-20260930-1425-bing-signin-agent-chrome.
Heartbeat pushed and pulled. Kill switch off.

## Result: PARTIAL. It works in one tab only, not in the profile.

- **The existing tab: YES.** The agent Chrome (port 9223, `~/.rankai/agent-chrome`) has a tab Santino left open at
  `bing.com/forbusiness/multipleEntities`. It shows the signed-in dashboard: "SV" avatar, 20 total listings,
  12 published, 0 need review, 0 suspended, synced with Google 3 weeks ago. The list includes Flood Fixers,
  ProRestoration, Restoration Xpress (Duplicate), NaRestCo, Home Pride, Coastal, Crew, Reign, and others.
  Screenshot: browser_agent/runtime/audit/20260930-1434-bing-multipleEntities-tab.png
- **A fresh tab: NO.** A new tab to bing.com/forbusiness in the same Chrome shows the public landing page
  with "Sign in". Screenshot: browser_agent/runtime/audit/20260930-1432-bing-forbusiness-agent-chrome.png
- **Why:** the profile holds NO Microsoft auth cookies. The only bing.com cookies are anonymous ones
  (MUID, SRCHD, SRCHUID, SRCHUSR, SRCHHPGUSR, _EDGE_S, _SS, SRM_B, MUIDB). There's no _U, WLS or KievRPSSecAuth, and
  there are no login.live.com or login.microsoftonline.com cookies at all. The session seems to live only in that
  tab (in memory or tab-scoped storage), so it won't survive a Chrome restart, and the sweep (which opens its
  own pages) will very likely see signed-out Bing.
- The profile has no cookie-blocking settings (no cookie_controls_mode, no exceptions). Launch flags are
  standard (`--restore-last-session`, port 9223).

## What I did NOT do
- I did not reload, navigate or close Santino's signed-in tab. A reload could drop the only live session.
- No edits in Bing Places. No sweep run: sweep.py has no bing-only flag (only `--skip-bing`), and per the
  answer that means report only.

## Next (ask, in mini-needs)
- NEED-20260930-1431-bing-session-not-persisted: Santino should sign in again in the agent Chrome with
  "Stay signed in? → Yes" (KMSI), then open a NEW tab to bing.com/forbusiness to confirm it holds.
  Alternatively, put microsoft:agency creds in ~/.rankai/portal-creds.json.
- The tab stays open in the meantime. Anything that must run on Bing today can use that tab while it lives.

Time: ~5 min. Cost: negligible.
