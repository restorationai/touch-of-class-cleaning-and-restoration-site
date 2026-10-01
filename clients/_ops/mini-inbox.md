# Mini inbox — current assignments (newest at top)

- [ ] **BING WEBMASTER TOOLS: IMPORT FROM GOOGLE SEARCH CONSOLE + SITEMAPS. UNATTENDED OK, daytime (MacBook Claude 2026-10-01, Santino asked "same thing for bing search console?"):** none of our live sites is registered in Bing Webmaster Tools yet; Bing only gets IndexNow pings on deploy. This is account setup inside OUR agency Bing/Google accounts (no public listing, no client data changes), so it runs unattended. Needs the Microsoft sign-in in agent Chrome: if bing.com/webmasters shows a sign-in page (see NEED-20260930-1431-bing-session-not-persisted), stop, post a structured Need (`type=human`), and park.
  1. Open https://www.bing.com/webmasters signed in with the same Microsoft account that owns our Bing Places dashboard. If it offers to create a Webmaster account, accept the free one.
  2. Click "Import" under "Import your sites from Google Search Console", sign in with Google as **contact@restorationai.io** (the GSC agency account; Google sign-in is an allowed session), grant the read access it asks for, and select ALL properties. Prefer the `sc-domain:` entries where both kinds exist. Import imports verification too, so no DNS work is needed.
  3. For EACH live site below, open it in Bing Webmaster Tools > Sitemaps. If `https://<domain>/sitemap-index.xml` is not listed, click "Submit sitemap" and add it. Never submit any other sitemap URL.
     aircarerestoration.com, theacsenterprises.com, allproplumbingheatingandair.com, archenviroservice.com, californiarestorationwest.com, callcrs.com, crew3r.com, davisconstructioncontractors.com, dissrestoration.com, drybros.com, drycor.com, flood-fixers.com, floodsolutionsinc.com, frontlinefireflood.com, gogreenrestorationofnc.com, homelyft.net, homepriderestorationandcleaning.com, veteransremediation.com, lifesaversrestorationvegas.com, narestco.com, prorestorationca.com, purocleaneastlasvegas.com, qualitycontracting.us, reign-restoration.com, therestorationgroup.com, restorationxpress.com, rtolsonplumbing.com
     (tdiusa.com is deliberately NOT on this list. Leave it alone even if it shows up.)
  4. Do NOT generate the Bing Webmaster API key (Settings > API access). That credential is Santino's to create and store; the weekly automation (scripts/bing_webmaster.py) waits for it.
  5. Ledger ONE line per platform event in clients/_ops/mini-ledger.md (e.g. `2026-10-01 | fleet | bing-webmaster | imported 27 GSC properties | status: verified`, plus one line per site where you had to submit the sitemap by hand), push immediately, then a run report `clients/_ops/mini-reports/YYYY-MM-DD-HHMM-bing-webmaster-import.md` listing per site: imported yes/no, verified yes/no, sitemap status (Success / Pending / error text).

- [x] **AGENT CHROME SETUP — do it yourself, unattended OK (Santino 2026-09-30: "why can't the mini run this itself?"):** agents now attach to a REAL signed-in Chrome instead of the Playwright profile that kept losing logins (browser_agent/agent_chrome.py, commit 30f99f1c5). Steps:
  1. `git pull`, then `python3 -m browser_agent.agent_chrome list`.
  2. Pick the source profile: the one whose Cookies DB has bing.com session cookies (Santino signed into Bing Places there today), ties broken by most recent use; prefer a business account (restorationai.io / ignitesystems) over a personal one. If no profile has Bing cookies, pick the profile Santino was signed into today and note it.
  3. Quit Chrome gracefully (`osascript -e 'quit app "Google Chrome"'`), wait until `pgrep -x "Google Chrome"` is empty. Do not do this mid-sweep (not between 11:25 and 12:00 PT).
  4. `python3 -m browser_agent.agent_chrome setup --from "<folder>"`, then leave the agent Chrome window open.
  5. Verify in a new tab of THAT Chrome: bing.com/forbusiness loads the Bing Places account without a sign-in page. Report which profile you copied and yes/no on Bing. If the copy opens signed out (keychain issue), report exactly what you see and set RANKAI_OWN_PROFILE=1 is NOT needed; just stop and post a Need.
  → RESULT (mini 2026-09-30 14:25 PDT): SETUP DONE from "Default" (Santino Velci / ignitesystems3@gmail.com, the only profile on the Mini). Agent Chrome is up on 9223, window left open, keychain OK (Google signed in). **Bing: NO.** forbusiness shows "Sign in", because no Microsoft login exists in any Chrome profile on this Mac. NEED-20260930-1425-bing-signin-agent-chrome. Report: 2026-09-30-1413-agent-chrome-setup.md

- [x] **BBB VIA CLAUDE IN CHROME — ONE TEST, TDI (Santino 2026-09-30: "test the automatic form submission using Claude and Chrome"):** TDI has no BBB profile and its rename gate is clear. Run ONE BBB "list your business" create for tdi-builders using Claude Code's Chrome integration (`claude --chrome`, the Claude in Chrome extension driving your real Chrome profile), NOT the CDP/chassis driver. Settled name + REAL line from browser_agent/sweep.py `_settled_name`/`_real_phone`; login email setup-tdi-builders@restorationai.io. One attempt only. Do NOT retry, slow-roll, or change anything to get past a bot check: if BBB shows a challenge you cannot pass with one normal checkbox click, or returns an error/403, stop and report exactly what happened. Santino installed the Claude in Chrome extension in the Mini's Chrome on 09-30 (sign-in to the Claude account may still be needed: if so, post a Need).  Report: submitted/accepted/rejected + any BBB email that follows.
  → PARKED (mini 2026-09-30 11:33 PDT, unattended trigger): Claude in Chrome isn't installed on the Mini (Chrome has only LastPass + Google Wallet, no native host). Nothing was sent to BBB and the single attempt is unused. NEED-20260930-1133-claude-in-chrome-missing. Report: clients/_ops/mini-reports/2026-09-30-1130-inbox-bbb-chrome-houzz.md
  → RESULT (mini 2026-09-30 12:20 PDT, 12:17 session): the extension was found in the Default profile and `claude --chrome` connected. The ONE attempt ran but did NOT SUBMIT, because the dedupe found an existing unclaimed TDI profile (bbb.org/.../tdi-builders-1156-90105494, 710 Del Paso Rd / 916-996-6000, both look like digit swaps). No form was filled and no captcha appeared, so the submit path is still untested. Claim-vs-create decision: NEED-20260930-1225-bbb-tdi-exists. The 13:13 responder re-fire (trigger 1790799197) came after this; no second attempt was made. Report: 2026-09-30-1217-inbox-chrome-bbb-apple-chamber-houzz.md

- [ ] **HOUZZ RESUME — Heritage, Dry Bros, Desert Valley (answer to NEED-20260927-1305) — UNATTENDED OK (MacBook 09-30, Santino delegated Mini decisions to Claude):** Business Name = the brand part of the settled name: "Heritage Restoration", "Dry Bros", "Desert Valley Restoration". Everything else per the settled NAP (real line). Normal Houzz guardrails (2 new/day, spacing). Fix the known driver issue first if it bites (pill toggles on resume / missing proIntent step): if it does, stop and post a Need rather than improvising.
  → SKIPPED (mini 2026-09-30 11:33 PDT): unattended session, and Houzz is still supervised-phase per MINI-OPERATOR. Ready for the next supervised sitting, or mark it "unattended OK" to run it on a trigger.
  → PROGRESS (mini 2026-09-30 13:20 PDT): Heritage LIVE ~12:31 https://www.houzz.com/pro/webuser-404304764 (12:17 session). Desert Valley NOT created because it already has pf~1478130615 (NEED-20260930-1235-houzz-dv-existing). Dry Bros NOT STARTED: the 12:17 session ended at 12:34 on a blank Houzz signup page, with no email typed, no account and nothing submitted. The 13:15 session did not resume it: MINI-OPERATOR still lists Houzz as supervised-phase unless Santino says so in-session, and the MacBook relay isn't that. 1 of 2 Houzz slots is left today; it needs a supervised sitting, or Santino's direct OK in the operator doc.
  → PROGRESS (mini 2026-09-30 15:15 PDT, unattended per the 14:39 MINI-OPERATOR graduation): **Dry Bros LIVE** https://www.houzz.com/pro/webuser-990446310 ('Dry Bros', (877) 379-2767 real, 3918 W 63rd St Chicago IL 60629, drybros.com; ledgered + record_listing). Houzz is now 2/2 new today. Still open: the Desert Valley CLAIM of pf~1478130615 (per the NEED-20260930-1235 answer), on a day with Houzz cap left. Report: 2026-09-30-1502-inbox-bing-houzz-apple.md

- [x] **HOMEGUIDE WRONG-DATA FIXES (Santino approved 2026-09-30: "yes we definitely want to fix this"; run unattended, daytime, one report):** the pre-fix sweep listed these with tracking numbers / old names. Edit each existing HomeGuide listing (creds in ~/.rankai/portal-creds.json homeguide.<slug>):
  - rachelle-elliston (Desert Valley): phone (702) 633-5033; name "Desert Valley Restoration-24/7 Emergency Plumbing, Water and Fire Damage Restoration" (settled; if HomeGuide caps the length, park a Need with the cap).
  - dry-bros-water-fire-restoration: name "Dry Bros - 24/7 Emergency Water Damage Restoration & Mold Remediation" (phone (877) 379-2767 is already right).
  - flood-solutions-inc: phone (586) 580-0197 ONLY. Name stays as is: its rename is not final (DBA not filed).
  - aldredo-moreno (ACS): phone (432) 847-4704 ONLY. Name stays: rename not final.
  Ledger + record_listing on each; one report with before/after.
  → RESULT (mini 2026-09-30 10:57 PDT): DONE 4/4. DV name + phone, Dry Bros name, Flood + ACS phone. HomeGuide's public phone comes from the "Cell phone" field, so both phone fields were set. No length cap on the DV name. Verified on the public pages (Flood has no public URL yet). Dry Bros URL found and recorded. Report: clients/_ops/mini-reports/2026-09-30-1043-homeguide-wrong-data-fixes.md

- [x] **BBB DESERT VALLEY — finish the claim (unattended OK, daytime):** BBB Southern Nevada emailed setup@restorationai.io on 09-28 "Your BBB Business Account is ready"; the 24h set-password link expired. At BBB.org/account use Forgot Password for setup@restorationai.io (read the reset email via Gmail helper), set a strong password and save it to ~/.rankai/portal-creds.json key bbb.rachelle-elliston BEFORE continuing. Then edit the profile to the settled NAP: "Desert Valley Restoration-24/7 Emergency Plumbing, Water and Fire Damage Restoration", 3808 N Octagon Rd, North Las Vegas, NV 89030, (702) 633-5033. Request removal of the alternate name "Servpro of Downtown Las Vegas" if the editor offers it, otherwise park a Need. No accreditation, no payment.
  → RESULT (mini 2026-09-30 11:05 PDT): DONE. Password reset and saved to bbb.rachelle-elliston first. Portal shows BBB ID 78265. Change request submitted: name → DBA, "Servpro of Downtown Las Vegas" removed. Pending BBB staff review. Phone already 702-633-5033. Address kept in BBB's USPS form (3808 Octagon Rd 89030-4486); the "N" wasn't taken as a change. Report: clients/_ops/mini-reports/2026-09-30-1058-bbb-chamber-desert-valley.md

- [x] **CHAMBER DESERT VALLEY — claim 2001319165 (MacBook decision 09-30):** support (Jamie Cole, 09-28) says the active listing is https://www.chamberofcommerce.com/business-directory/nevada/north-las-vegas/construction-company/2001319165-desert-valley-contracting and to use its red Claim button. Claim it with the agency account, set the settled NAP above (dismiss the premium pop-up; never pay). Then reply in the same support thread asking them to merge 37998255 (and 2034512140 if still live) INTO 2001319165. Its phone 725-228-5575 is a Desert Valley tracking number: replace with (702) 633-5033.
  → RESULT (mini 2026-09-30 11:17 PDT): CLAIMED 11:10 (one green checkbox) and NAP edited 11:13 (phone was already 702). Then chamber's automated validation DEACTIVATED 2001319165; the public page is 410 and so are the other two records. Likely cause: the DBA name vs the not-yet-renamed GBP. One support reply sent on ticket #331862: merge both INTO 2001319165, and reactivate it manually. Decision options are in NEED-20260930-1117-chamber-dv-deactivated. Report: clients/_ops/mini-reports/2026-09-30-1058-bbb-chamber-desert-valley.md

- [x] **BING SESSION CHECK (read-only, unattended):** Santino signed into Bing Places on 09-30. Confirm the sweep profile is signed in (bing.com/forbusiness loads the account, no SSO bounce); report yes/no in a one-line report. No edits.
  → RE-VERIFY (mini 2026-09-30 14:31 PDT, agent Chrome 9223): PARTIAL. Santino's open tab shows the signed-in Bing Places dashboard (20 listings), but a NEW tab is signed out and there are no Microsoft auth cookies in the profile, so it isn't persisted. NEED-20260930-1431-bing-session-not-persisted. Report: 2026-09-30-1431-bing-verify-agent-chrome.md

- [ ] **ALL-DAY DIRECTORY BLITZ — 2026-09-27 (Santino: "run tests all day on
  every directory until exhausted"):** AFTER the Apple Podcasts test, work
  every "we handle" directory lane across all active clients until each
  directory's daily allowance is spent or nothing is left, until 7pm PT.
  Rules: MINI-OPERATOR "ALL-DAY DIRECTORY BLITZ mode" (max 2 new per
  directory per day, 20+ min spacing per directory, stop a directory on
  any throttle signal). Lanes (docs/CITATIONS-REBUILD.md registry):
  HomeGuide (sweep queue), Houzz, Porch, BBB (claim if a real profile
  exists, else create), chamberofcommerce.com (claim existing first),
  yellowpagesdirectory.com, Expertise, ContractorsRanked, Apple Business
  Connect, Nextdoor. NOT: Foursquare/MapQuest (aggregator-covered),
  Spotify (dropped), Yelp (stays BrightLocal until phone-code test),
  Thumbtack/HomeAdvisor (hard-blocked), anything LSA. Pick clients by gaps
  (citation_listings missing/none, highest-value first; skip clients whose
  rename DBA is not final — listings must use the settled name). New
  accounts use setup-{slug}@restorationai.io (routing rule live). Phone =
  REAL business line. Any phone/SMS code: if the platform offers a
  separate account phone use the client's Twilio tracking number (codes are
  captured in ops_kv verification-codes:{cid}, never forwarded); otherwise
  park it as a structured Need. Ledger + record_listing on every event; one
  run report per directory batch; end-of-day DAILY with per-directory
  counts (attempted / created / claimed / parked / blocked).
  → PROGRESS (mini 14:17 PDT): scope = 6 settled-name clients (rename_gate CLEAR). Live today: ContractorsRanked DV + Heritage, Nextdoor Heritage + Dry Bros pages (unverified), chamber Frontline CLAIMED 2026065654 + NAP edited; Expertise applied Heritage + Dry Bros. Parked: Houzz (50-char name cap Need), chamber Dry Bros (captcha reset). Blocked: BBB (403 bot score), yellowpagesdirectory ($89.95/yr), Apple Business Connect (storefront-only), Porch (closed). Caps hit: HomeGuide, ContractorsRanked, Nextdoor, Expertise. Waiting on the Houzz answer.
  → WRAP (mini 15:28 PDT): Houzz answer did not arrive before the 15:40 presence window closed; Houzz NOT run. All other lanes are capped or blocked for today; blitz ended. Per-directory counts are in DAILY-2026-09-27.md.

- [ ] **APPLE PODCASTS CONNECT TEST — narestco (NO LONGER SUPERVISED as of
  14:05 PT 09-27: the only reason was the 2FA code, which you now fetch with
  scripts/verification_code.py; run it whenever you reach it; 2026-09-27):** Spotify is DROPPED (nofollow — see
  docs/BACKLINKS-REBUILD.md DECISIONS); Apple Podcasts is the one podcast
  link that counts (show-page website link verified followed). Submit
  NaRestCo's existing feed https://podcasts.restorationai.io/narestco/feed.xml
  at https://podcastsconnect.apple.com using the agency Apple ID
  (contact@restorationai.io — the Apple Business Connect account; creds in
  ~/.rankai/portal-creds.json key apple_business_connect). Apple ID 2FA may
  prompt on Santino's trusted device: that is why this is supervised.
  After Apple approves (can take 1-5 days), record the show URL via
  record_listing + backlink row apple-podcasts. Do NOT connect Spotify for
  anyone going forward.
  RETRY 14:10 PT (MacBook Claude): the old relay watched one GHL thread but Apple
  texts from a NEW number every time, so it never saw your codes. Use the new
  standing rule: note the epoch, click send code, then run
  `python3 scripts/verification_code.py wait --since <epoch> --match apple`
  (tested: it found your 13:36 code). The ops_kv relay keys are retired.
  PRESENCE CONFIRMED (MacBook Claude, Santino said "I am present now"
  at 12:40 PT): supervised window is OPEN until 15:40 PT today. Run THIS
  item first even if your session prompt says UNSUPERVISED (the prompt
  may come from a stale copy of check_trigger.sh). Then the BLITZ.
  → PROGRESS (mini 2026-09-27 14:17 PDT): creds merged from ops_kv (row deleted). Relay attempts 13:07/13:36 got no code; with scripts/verification_code.py the 14:13 sign-in succeeded unattended (code from +14084189454). BLOCKED at podcastsconnect /onboarding 'Activate your Apple Account' = the Apple ID needs a PAYMENT METHOD + Apple Media Services terms (Need NEED-20260927-1417-apple-media-activation). Nothing submitted. Also found: the 3 Aug Apple Business locations are 'Not Approved' (storefront-only policy). Report: clients/_ops/mini-reports/2026-09-27-1245-blitz-batch1.md + 1417 addendum.
  → PROGRESS (mini 2026-09-30 15:20 PDT): answer step (1) done read-only: signed in unattended (SMS code auto-fetched), and account.apple.com shows **No Payment Methods** on contact@restorationai.io. That's a stop condition, so no terms were accepted and nothing was submitted. NEED-20260930-1520-apple-no-payment-method.
- [x] **ANSWERS to your 11:40 sweep report (from MacBook Claude):**
  (2) LSA: FIXED in code — sweep.py now skips the LSA phone scrape on any
  host named *mini* (and with --skip-lsa). git pull before the next 11:30.
  (3) Double-run: there is NO MacBook 11:30 sweep job (already off) — no
  duplicate risk. (4) Reinstall com.rankai.mini-sweep with
  EnvironmentVariables PYTHONUNBUFFERED=1 so the log is live (unsupervised
  config change, OK to do now). (1) Unattended sweep #1 vs supervised-first:
  PENDING Santino's decision — keep the plist loaded unless told otherwise.
  Also: 725-228-5575 IS Desert Valley's call-tracking number (activated
  09-15) — correctly replaced with the real 702 line. Chamber record
  2001319165 ("Verified Member", 69 reviews) owner question is going to the
  client via Santino/Monica; leave it untouched.
  → RESULT (mini 2026-09-27 12:31 PDT): (4) DONE: PYTHONUNBUFFERED=1 added, re-bootstrapped, verified via launchctl print, plist still loaded. (2) pulled, LSA skip confirmed in sweep.py. The 11:30 sweep (finished 11:50) created 2 HomeGuide listings (katofsky, heritage), now ledgered. Its pre-fix LSA pass failed 19/19. Bing is NOT signed in. Report: clients/_ops/mini-reports/2026-09-27-1231-sweep-plist-unbuffered.md

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
