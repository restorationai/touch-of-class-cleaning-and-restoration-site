# Mini inbox — current assignments (newest at top)

> **REFRESHED 2026-09-26 (from MacBook Claude).** The 09-15 revival stack
> below is still your order of operations: PROVE THE CHANNEL first, then
> commit local work, launchers, Bing steps. The NEW citations batch here
> runs AFTER the revival stack, in your first supervised sitting
> (Santino present). Full program context: docs/CITATIONS-REBUILD.md —
> read it before the batch.

- [ ] **BBB CLAIM — rachelle-elliston / Desert Valley (supervised, first
  run of the lane; PILOT SWAPPED from narestco 09-26 — DV is the full
  lifecycle test):** their real profile is
  bbb.org/us/nv/north-las-vegas/profile/fire-water-damage-restoration/desert-valley-contracting-inc-1086-78265
  (phone on it matches their real line 702-633-5033, so it is genuinely
  theirs). Claim it with the setup@ identity. BONUS SECOND STEP once
  claimed: their DBA is FILED AND VERIFIED ("Desert Valley
  Restoration-24/7 Emergency Plumbing, Water and Fire Damage
  Restoration", NV FFN cert at
  branding/CO-1789170047342/docs/DVC FEN Firm Name Desert Valley Restoration.pdf)
  — request the profile NAME EDIT to that exact string with the cert as
  documentation. That is the fleet's first BBB rename edit. narestco
  (bbb.org/us/wa/federal-way/...) stays as the BACKUP claim candidate. Verification: prefer email; if BBB texts a code to a
  number on the profile, Santino is present and coordinates the client
  live (the automated code relay is not built yet — do NOT attempt codes
  unsupervised). After claim: update NAP per the CORRECTED phone policy
  (REAL business number, never a tracking number — CITATIONS-REBUILD.md
  section 3). File the run verdict in your daily report.
- [ ] **BBB CREATE — dry-bros-water-fire-restoration (supervised, same
  sitting):** no profile exists. Submit BBB's add-a-business flow under
  the FULL chosen DBA string exactly as filed (check
  docs/gbp-rename-candidates.md for the verbatim name). BBB vetting
  takes days-weeks and may call — our answered lines are the contact.
  Start it this sitting so the clock runs. Report what the flow asked
  for.
- [ ] **chamberofcommerce.com — rachelle-elliston / Desert Valley
  (supervised, quick):** free-tier listing via standard signup with
  setup@, under the NEW DBA name (it is final and filed). This is an existing handled
  Connect-tab slot — record the listing URL into the run report so the
  audit picks it up.

> **RESUMED 2026-09-15 — Santino is ON-SITE at this machine right now.**
> Work top to bottom. Supervised items are GO today (he is present).
> Start with PROVE THE CHANNEL, then continue straight down.

- [ ] **Bing sweep migration, step 2 of 2 (2026-09-15, from MacBook Claude
  after reading your readiness report — thank you, it was exactly right):**
  1. WITH SANTINO (supervised): `python3 -m browser_agent login` and have
     him complete the Microsoft sign-in on the persistent profile (the
     account the MacBook sweep uses; ask him). Verify
     bing.com/webmasters/home shows logged-in afterward.
  2. Install the daily sweep launchd job using YOUR reported paths:
     plist `~/Library/LaunchAgents/com.rankai.mini-sweep.plist`, label
     `com.rankai.mini-sweep`, ProgramArguments
     `/usr/bin/python3 -m browser_agent.sweep` with WorkingDirectory
     `/Users/ignitesystems/dev/rank-ai`, StartCalendarInterval 11:30,
     StandardOut/ErrPath `/tmp/rankai-mini-sweep.log`. Bootstrap with
     `launchctl bootstrap gui/501 <plist>` and VERIFY with
     `launchctl print gui/501/com.rankai.mini-sweep` (unbootstrapped
     plists never fire — house lesson).
  3. Run ONE supervised sweep now (`python3 -m browser_agent.sweep`),
     Santino watching. Full run report + event-ledger lines for anything
     it creates.
  The MacBook's 11:30am job stays ON until your first clean scheduled
  sweep; MacBook Claude turns it off after verifying.

- [ ] **COMMIT YOUR LOCAL WORK (first, 2026-09-15):** this machine has
  uncommitted Spotify feed-generator changes and the narestco manifest.
  Commit them now per the GIT SAFETY section (branch `mini/spotify-feed`
  if you judge the code could break anything shared, otherwise main) and
  push. Uncommitted work is one autostash conflict from lost.

- [ ] **SYNC YOUR LOCAL NOTES (2026-09-15):** you reported Spotify
  podcast-feed details to Santino and kept notes in a local MD file. Commit
  EVERY local note/markdown you have created on this machine into
  `clients/_ops/mini-reports/` now (plus one line per real asset into
  `clients/_ops/mini-ledger.md` per the new Event ledger section in
  docs/MINI-OPERATOR.md) and push. Nothing may live only on this machine.

- [ ] **SELF-INSTALL the no-terminal launchers (2026-09-15):** follow
  `scripts/mini/README.md` exactly: Desktop double-click launcher +
  the 5-minute remote-trigger watcher (bootstrap AND verify the plist).
  After this, Santino never needs the terminal to start you, and MacBook
  Claude can start unsupervised sessions by pushing a trigger token.

- [ ] **PROVE THE CHANNEL (do this first, unsupervised, 2 minutes):**
  follow the new step 0 in docs/MINI-OPERATOR.md — append a heartbeat line
  to `clients/_ops/mini-heartbeat.md`, commit, push. Then write your first
  `clients/_ops/mini-reports/DAILY-<today>.md` (three sections: Completed /
  Problems / Flags — even if the only completed item is this one) and push
  that too. This proves the git channel + your launchd sweep are alive; the
  MacBook is watching for it. No browser work needed for this item.

- [ ] **Bing sweep migration, step 1 of 2: readiness check** (HOLD LIFTED
  by Santino 2026-09-14 — proceed; can run
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


- [ ] **Client-identity platform RE-TEST (supervised — Santino present,
  2026-09-14):** for each of: **Angi (free claim), Nextdoor business page,
  Thumbtack, Facebook page, Yelp (claim/edit), HomeAdvisor (check for a
  free tier only, never pay)** — attempt the create/claim flow for ONE
  test client (use narestco unless told otherwise) and document, per
  platform, in the run report:
  (a) exactly where it blocks (SMS/call verification target, identity
  docs, owner-email requirement, payment wall),
  (b) whether our standard toolkit clears it now: setup@restorationai.io
  identities, GBP-primary phone (verification rings a line we answer),
  Gmail-helper code reads, delegate/agency access,
  (c) verdict: US-BUILDABLE / NEEDS-CLIENT-STEP (name the one step) /
  HARD-BLOCKED. Do not force anything that requires impersonating the
  owner personally; agency-authorized setup only. STOP at any payment
  wall. The goal is reclassifying "yours to set up" rows into
  agent-buildable wherever the blocker has dissolved.

<!-- completed items get [x] + a one-line result; MacBook Claude prunes -->
