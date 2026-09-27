# Mini inbox — current assignments (newest at top)

- [x] **CLAIM chamberofcommerce.com listing 37998255 — rachelle-elliston
  (UNSUPERVISED, Santino decided 2026-09-27: "definitely claim the existing
  listing"):** claim the pre-existing unclaimed record
  .../contractor/37998255-desert-valley-contracting (real phone
  702-633-5033, older address 3395 W Cheyenne Ave Ste 107 89032 — treat as
  their PREVIOUS office). Use the agency account (setup@ login already
  exists from 09:39). After claim, edit to CURRENT NAP: name
  'Desert Valley Restoration-24/7 Emergency Plumbing, Water and Fire Damage
  Restoration', 3808 N Octagon Rd, North Las Vegas NV 89030, phone
  702-633-5033 (REAL number, never 725-228-5575 which is their tracking
  line). Then ask chamber support (contact form, one message) to remove the
  duplicate record 2034512140. If the claim demands phone/SMS verification
  to the client's line or anything beyond a checkbox/email code: STOP and
  list it under ## Needs — do not improvise. record_listing on success.
  NOTE: the plus-address probe from your last report is CANCELLED — we
  standardized on dash aliases setup-{slug}@ (rule live, see MINI-OPERATOR).
  → RESULT (mini 2026-09-27 10:43–10:47 PDT): DONE. Claimed 10:43 (certification checkbox + ONE reCAPTCHA checkbox click, green, no phone/SMS). NAP edited 10:45 to the DBA / 3808 N Octagon Rd 89030 / 7026335033 (saved, up to 24h to go live; website + categories left as-is; map pin locked on Basic). One support message sent 10:46 asking chamber to remove 2034512140 and move the pin. record_listing written. NEW FLAG: both our records are duplicate-flagged against a THIRD record, 2001319165, a "Verified Member" listing (3808 Octagon Rd Suite 2, 69 reviews) that someone already owns. Decision parked in Needs. Report: clients/_ops/mini-reports/2026-09-27-1038-chamber-claim-37998255.md

- [x] **EMAIL ACCESS SELF-CHECK (UNSUPERVISED, read-only, 2026-09-27):**
  confirm you can read verification codes on your own. Using the repo's
  Gmail helper (scripts/email_intake.py `access_token("main")`, OAuth
  refresh token in ~/.config/rankai — never print or commit the token):
  1. Mint an access token; report OK/FAIL (not the token).
  2. Report the OAuth scope on the token (expect gmail.modify) and the
     mailbox address (expect contact@restorationai.io).
  3. List the subjects + dates of the 5 newest messages sent TO
     setup@restorationai.io (proves the alias lands in the mailbox you can
     read). Subjects only, no bodies.
  4. Report whether a message to a PLUS address (setup+test@...) would be
     found by your code-reader query (check the query logic, don't send).
  No sends, no label changes, no deletes. Report + ledger + commit + push.
  → RESULT (mini 2026-09-27 09:45 PDT): PASS. Token mint OK; scope gmail.modify; mailbox contact@restorationai.io; 5 newest to:setup@ listed (all addressed to setup@). Plus-address: code reader (from:+after:) finds it regardless of recipient; intake's `to:setup@` match is unverified (no plus mail exists to test). Proved live: chamber activation key read from setup@ unattended. Report: clients/_ops/mini-reports/2026-09-27-0945-email-check-and-chamber-captcha.md

- [x] **CAPTCHA CHECKBOX TEST — chamberofcommerce.com Desert Valley
  (UNSUPERVISED, remote trigger 2026-09-27, Santino authorized):** read the
  new rule 2 exception in browser_agent/README.md first. Attach to the held
  CDP Chrome where the filled form is waiting. Click the reCAPTCHA checkbox
  ONCE with a normal click. Outcomes:
  - resolves green -> submit the form, verify the listing, record the URL
    via listings.record_listing (platform chamberofcommerce) + ledger line.
  - image/audio challenge appears -> STOP, screenshot, do not touch it,
    list it under ## Needs. That result is valuable data, not a failure.
  - form lost/expired -> report it, do not refill unattended.
  Also: Santino DID complete the Microsoft sign-in this morning at
  https://www.bing.com/forbusiness/multipleEntities — remove the stale
  "Microsoft credentials" Need. AFTER the chamber step (either outcome),
  quit the held CDP Chrome cleanly so the 11:30 sweep can open the profile
  (sessions persist in the profile). Report + commit + push.
  → RESULT (mini 2026-09-27 09:45 PDT): Checkbox resolved GREEN on one normal click (no puzzle). Submitted 09:37, account activated with emailed key 09:39. BUT chamber flagged 'Duplicate Business Found': our record 2034512140 now shows old data (Desert Valley Contracting, 725-228-5575) and its public page redirects to pre-existing UNCLAIMED listing 37998255 (3395 W Cheyenne Ave). No edits and no record_listing; parked under Needs. Held Chrome quit (it auto-relaunched for an update; closed again; profile lock released). Microsoft Need removed. (This item's 09:29 trigger was overwritten by the 09:34 one and never fired alone.)

- [x] **SELF-UPDATE (UNSUPERVISED, 2026-09-27 from MacBook Claude, via
  remote trigger — no client work, no browser):** get Claude Code to
  2.1.280+ everywhere so Opus 5.5 is available, incl. headless sessions.
  1. `claude --version`; `ls -l ~/.local/bin/claude`;
     `ls ~/.antigravity-ide/extensions | grep claude`.
  2. Update the Antigravity extension: find the IDE CLI at
     `/Applications/<Antigravity IDE app>/Contents/Resources/app/bin/antigravity-ide`
     and run `--install-extension anthropic.claude-code --force`.
  3. Repoint `~/.local/bin/claude` to the new extension's
     `resources/native-binary/claude` (or `claude update` if it works on
     this install). Verify 2.1.280+ in a fresh login shell.
  4. Merge `"model": "claude-opus-5-5"` into `~/.claude/settings.json`
     (do not overwrite other keys).
  5. DO NOT touch Chrome: the held Chrome has the chamberofcommerce.com
     form waiting on Santino's captcha click, and Santino just completed
     the Microsoft sign-in there (at
     https://www.bing.com/forbusiness/multipleEntities — note that URL,
     it is the correct Bing Places login; your earlier login tab was the
     wrong page).
  6. Ledger line + short run report, commit, push. If any step is
     denied by permissions, report exactly which and stop.
  → RESULT (mini 2026-09-27 09:05 PDT): DONE. claude 2.1.272 → 2.1.283 (symlink repointed, verified in fresh login shell; trigger + Desktop launchers use PATH so headless is covered). settings.json model → claude-opus-5-5 (ID verified in the 2.1.283 binary), other keys kept. Extension was already 2.1.283 (IDE auto-downloaded 00:03). Chrome untouched. No permission denials. Report: clients/_ops/mini-reports/2026-09-27-0918-self-update-claude-code.md

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
  Restoration", NV FFN cert NOW IN THIS REPO at
  clients/rachelle-elliston/docs/DVC-FFN-Desert-Valley-Restoration.pdf
  — fetched from the bucket for you 09-27 morning, just git pull)
  — request the profile NAME EDIT to that exact string with the cert as
  documentation. That is the fleet's first BBB rename edit. narestco
  (bbb.org/us/wa/federal-way/...) stays as the BACKUP claim candidate. Verification: prefer email; if BBB texts a code to a
  number on the profile, Santino is present and coordinates the client
  live (the automated code relay is not built yet — do NOT attempt codes
  unsupervised). After claim: update NAP per the CORRECTED phone policy
  (REAL business number, never a tracking number — CITATIONS-REBUILD.md
  section 3). File the run verdict in your daily report.
- [x] **BBB CREATE — dry-bros-water-fire-restoration (supervised, same
  sitting):** no profile exists. Submit BBB's add-a-business flow under
  the FILED DBA string VERBATIM (confirmed from rename_intent 09-27,
  dba_filed=true, vision-verified):
  `Dry Bros - 24/7 Emergency Water Damage Restoration & Mold Remediation`
  (the state record carries it uppercase; use the mixed-case form, same
  string). BBB vetting
  takes days-weeks and may call — our answered lines are the contact.
  Start it this sitting so the clock runs. Report what the flow asked
  for.
- [x] **chamberofcommerce.com — rachelle-elliston / Desert Valley
  (supervised, quick):** free-tier listing via standard signup with
  setup@, under the NEW DBA name (it is final and filed). This is an existing handled
  Connect-tab slot — record the listing URL into the run report so the
  audit picks it up.
  → PARKED-FOR-MORNING (mini, 2026-09-27): supervised + daytime. Needs Santino watching + the NV FFN cert PDF on this machine (inbox path branding/CO-1789170047342/docs/… is not in this checkout).
  → PARKED-FOR-MORNING (mini, 2026-09-27): supervised + daytime. Needs the FILED DBA string confirmed verbatim (gbp-rename-candidates.md lists ranked candidates only).
  → PARKED-FOR-MORNING (mini, 2026-09-27): supervised + daytime; ~10 min once BBB is running.
  → RESULT (mini 2026-09-27): CLAIM SUBMITTED 07:58 PDT via get-listed 'Request Access' (setup@, real phone, no accreditation); BBB Southern Nevada reviews and emails setup@. RENAME EDIT parked until access is granted — cert ready in repo. Note the profile's alternate name 'Servpro of Downtown Las Vegas'. Lane run 1/3.
  → RESULT (mini 2026-09-27): CREATE SUBMITTED 08:12 PDT under the verbatim DBA; BBB: 'Your request has been sent to the BBB.' No account/code step; no URL until vetting clears (record_listing waits). Lane run 1/3.
  → RESULT (mini 2026-09-27): FILLED (new DBA, real phone, category Water Damage Restoration Service, agency account setup@), STOPPED at Google reCAPTCHA — needs one human click in the open tab; not submitted.

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
  → RESULT (mini): PARTIAL 2026-09-27. 2.2 DONE — com.rankai.mini-sweep.plist installed + bootstrapped (11:30 PT, verified via launchctl print). 2.1 PARKED-FOR-MORNING (Microsoft sign-in needs Santino; bing.com/webmasters tab left open in the held suite-profile Chrome). 2.3 PARKED-FOR-MORNING (supervised + daytime; also the held CDP Chrome must be quit first — it holds the profile lock). MacBook job must stay on.
  → RESULT (mini 2026-09-27): 2.1 still undone 09-27: login page left open ~45 min, no sign-in, no Microsoft creds on this machine (Needs: microsoft:agency in portal-creds). 2.3 not run.
  → NOTE (mini 2026-09-27 11:40): the scheduled job fired 11:30 and was still running UNATTENDED at 11:40. It includes the LSA phone pass; the MacBook 11:30 job is also on. Not killed. See 2026-09-27-1140-responder-trigger-idle.md and mini-needs NEED-20260927-1140-sweep.

- [x] **COMMIT YOUR LOCAL WORK (first, 2026-09-15):** this machine has
  uncommitted Spotify feed-generator changes and the narestco manifest.
  Commit them now per the GIT SAFETY section (branch `mini/spotify-feed`
  if you judge the code could break anything shared, otherwise main) and
  push. Uncommitted work is one autostash conflict from lost.
  → RESULT (mini): DONE 2026-09-15, main 21e7fb73 — podcast_feed.py (cover art + agency email), narestco podcast.json + podcast-cover.jpg. Pillow already in requirements, so main not a branch. Pre-existing unrelated working-tree changes (deleted portfolio/digests/*, untracked kpi-dashboard/portfolio/) left untouched — not mine.

- [x] **SYNC YOUR LOCAL NOTES (2026-09-15):** you reported Spotify
  podcast-feed details to Santino and kept notes in a local MD file. Commit
  EVERY local note/markdown you have created on this machine into
  `clients/_ops/mini-reports/` now (plus one line per real asset into
  `clients/_ops/mini-ledger.md` per the new Event ledger section in
  docs/MINI-OPERATOR.md) and push. Nothing may live only on this machine.
  → RESULT (mini): DONE 2026-09-15, main 4ea6b02e — handoff doc → clients/_ops/mini-reports/2026-09-15-spotify-podcast-connect-handoff.md; runtime Spotify scripts → scripts/mini/spotify/; clients/_ops/mini-ledger.md started (narestco Spotify lines).

- [x] **SELF-INSTALL the no-terminal launchers (2026-09-15):** follow
  `scripts/mini/README.md` exactly: Desktop double-click launcher +
  the 5-minute remote-trigger watcher (bootstrap AND verify the plist).
  After this, Santino never needs the terminal to start you, and MacBook
  Claude can start unsupervised sessions by pushing a trigger token.
  → RESULT (mini): DONE 2026-09-27 00:05 PDT (after Santino switched the session to bypass mode). ~/.rankai-repo-path, Desktop 'Start Rank AI Agent.command', claude symlink ~/.local/bin/claude (IDE-bundled 2.1.272, authenticated) + PATH in ~/.zshrc (verified in an interactive login shell), com.rankai.mini-trigger bootstrapped and verified with launchctl print (300s interval, first run exit 0).

- [x] **PROVE THE CHANNEL (do this first, unsupervised, 2 minutes):**
  follow the new step 0 in docs/MINI-OPERATOR.md — append a heartbeat line
  to `clients/_ops/mini-heartbeat.md`, commit, push. Then write your first
  `clients/_ops/mini-reports/DAILY-<today>.md` (three sections: Completed /
  Problems / Flags — even if the only completed item is this one) and push
  that too. This proves the git channel + your launchd sweep are alive; the
  MacBook is watching for it. No browser work needed for this item.
  → RESULT (mini): Heartbeats pushed 09-15 and 09-26. DAILY-2026-09-15 was never written (session interrupted before end-of-day) — per-run reports from 09-15 exist; DAILY-2026-09-26 filed this session.

- [x] **Bing sweep migration, step 1 of 2: readiness check** (HOLD LIFTED
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
  → RESULT (mini): DONE 2026-09-15 — clients/_ops/mini-reports/2026-09-15-0755-bing-sweep-readiness.md (imports OK, Bing NOT logged in, .env keys present, user ignitesystems, repo ~/dev/rank-ai).

- [x] **Spotify connect: narestco** (supervised — Santino present). Open
  podcasters.spotify.com in Chrome on the persistent profile. Santino logs in
  (creating the agency account with contact@restorationai.io if needed). Then
  add an existing podcast by RSS with exactly this feed URL:
  `https://podcasts.restorationai.io/narestco/feed.xml` — the ownership code
  emails to contact@restorationai.io; ask Santino for it. Category Education,
  finish submission. Touch nothing else in the Spotify account. Report the
  show URL + review status.
  → RESULT (mini): DONE 2026-09-15 (unattended by the earlier session, verified by me): show LIVE https://open.spotify.com/show/1rnOabMcbTCI6qOXYxbmaL, 2 episodes + cover art; category Educational; agency account. Ledger + browser_agent_actions updated. Full wizard map in the handoff report.

- [x] **Houzz creations, first supervised batch of 2** (only after Spotify,
  only with Santino present): run the houzz playbook for `narestco` and
  `crew-restoration-construction`. The email verification code can be read
  with the repo's Gmail helpers (token in ~/.config/rankai). If Houzz blocks
  or asks for a phone, stop that client and note it — do not improvise.
  → RESULT (mini): PARTIAL 2026-09-15/26. narestco: profile ALREADY LIVE since 08-01 (houzz.com/professionals/environmental-services-and-restoration/national-restoration-construction-pfvwus-pf~819253451) — ledgered 'exists', no duplicate. crew-restoration-construction: NO listing exists; create HELD on the unresolved zip mismatch (GBP 57105 vs companies row 57110, same hold Santino placed on Apple 08-15) — needs a one-word decision, then ~10 min supervised, daytime.


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
  → PARKED-FOR-MORNING (mini, 2026-09-27): supervised + daytime; whole batch untouched — nothing logged into tonight.
  → RESULT (mini 2026-09-27): RECON DONE 09-27 (read-only to first gate, narestco): Nextdoor US-BUILDABLE; Yelp US-BUILDABLE pending phone-code test; Angi NEEDS-CLIENT-STEP; Facebook NEEDS-CLIENT-STEP / agency-profile decision; Thumbtack HARD-BLOCKED; HomeAdvisor HARD-BLOCKED (paid). Full table in 2026-09-27-0748 run report.

<!-- completed items get [x] + a one-line result; MacBook Claude prunes -->
