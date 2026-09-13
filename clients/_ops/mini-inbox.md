# Mini inbox — current assignments (newest at top)

- [ ] **PROVE THE CHANNEL (do this first, unsupervised, 2 minutes):**
  follow the new step 0 in docs/MINI-OPERATOR.md — append a heartbeat line
  to `clients/_ops/mini-heartbeat.md`, commit, push. Then write your first
  `clients/_ops/mini-reports/DAILY-<today>.md` (three sections: Completed /
  Problems / Flags — even if the only completed item is this one) and push
  that too. This proves the git channel + your launchd sweep are alive; the
  MacBook is watching for it. No browser work needed for this item.

- [ ] **ON HOLD (Santino 2026-09-09, do not start): Bing sweep migration,
  step 1 of 2: readiness check** (can run
  unsupervised; report only, change nothing). The daily browser-agent sweep
  (`python3 -m browser_agent.sweep`) still runs on Santino's MacBook at
  11:30am PT and we are moving it to this machine. Before we install
  anything, verify and report:
  1. `git pull` this repo, then confirm `browser_agent/` imports:
     `cd <repo> && python3 -c "import browser_agent.sweep"` (report any
     missing pip packages by name, do not install them yet).
  2. Confirm the persistent Chrome profile on this machine has a LIVE
     Bing/Microsoft session: open bing.com/webmasters (or the Bing places
     dashboard the playbooks use) and report logged-in account email, or
     "not logged in".
  3. Confirm `.env` exists at the repo root here and report ONLY which of
     these keys are present (never their values): SUPABASE_URL,
     SUPABASE_SERVICE_ROLE_KEY, ANTHROPIC_API_KEY.
  4. Report your macOS username (`whoami`) and repo path (`pwd`) so the
     launchd plist can be written with correct paths.
  Write the report to clients/_ops/mini-reports/ as usual. Step 2 (launchd
  install + one supervised sweep) will be dropped into this inbox after
  MacBook Claude reads the report. The MacBook job stays on until this
  machine completes one clean sweep — do not touch anything outside this
  checklist.

- [ ] **Spotify connect: narestco** (supervised — Santino present). Open
  podcasters.spotify.com in Chrome on the persistent profile. Santino logs in
  (creating the agency account with contact@restorationai.io if needed). Then
  add an existing podcast by RSS with exactly this feed URL:
  `https://podcasts.restorationai.io/narestco/feed.xml` — the ownership code
  emails to contact@restorationai.io; ask Santino for it. Category Education,
  finish submission. Touch nothing else in the Spotify account. Report the
  show URL + review status.

- [ ] **Houzz creations, first supervised batch of 2** (only after Spotify,
  only with Santino present): run the houzz playbook for `narestco` and
  `crew-restoration-construction`. The email verification code can be read
  with the repo's Gmail helpers (token in ~/.config/rankai). If Houzz blocks
  or asks for a phone, stop that client and note it — do not improvise.

<!-- completed items get [x] + a one-line result; MacBook Claude prunes -->
