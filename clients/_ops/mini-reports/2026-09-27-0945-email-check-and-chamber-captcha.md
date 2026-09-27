# Mini run — 2026-09-27 09:34–09:45 PDT — email self-check + chamber CAPTCHA test

Trigger: `email-check-1790526844` (UNSUPERVISED). Kill switch off. Heartbeat pushed first.
Worked the two UNSUPERVISED inbox items; all supervised items skipped.

Note: the 09:29 CAPTCHA-test trigger (f9c814b63) never fired on its own. The
09:34 email-check trigger overwrote `clients/_ops/mini-trigger` before the
5-minute watcher consumed it (`~/.rankai-mini-trigger-consumed` holds only
`email-check-1790526844`). I picked the CAPTCHA item up from the inbox in
this session. Two triggers pushed less than 5 minutes apart will collapse into one.

## 1. Email access self-check (read-only): PASS

| Check | Result |
|---|---|
| 1. Access token mint (`email_intake.access_token("main")`) | **OK** (token not printed or stored) |
| 2. Scope / mailbox | `https://www.googleapis.com/auth/gmail.modify` / **contact@restorationai.io** (5,010 messages) |
| 3. 5 newest `to:setup@restorationai.io` | see below. All 5 have setup@ in To/Delivered-To, so the alias lands in the readable mailbox |
| 4. Plus-address (setup+test@) found by code reader? | **Yes for the code reader; unproven for intake's setup@ sweep** (see below) |

Newest 5 to setup@ (subjects + dates only):
- Sun 27 Sep 2026 15:07 UTC: "Your Free BBB Business Profile Is on Its Way"
- Wed 23 Sep 2026 18:30 UTC: "Hire a design expert"
- Tue 22 Sep 2026 17:25 UTC: "[Alert] Your access to Rob@tdiusa[.]com's Account has been revoked"
- Tue 22 Sep 2026 17:14 UTC: "[Invitation] Join the Rob@tdiusa[.]com's Account account"
- Tue 22 Sep 2026 17:14 UTC: "Verify your email."

Plus-address analysis (query logic checked, nothing sent):
- `scripts/mini/spotify/gmail_code.py` `find_code()` / `list_recent()` query is
  `from:<sender> after:<epoch>`. It does **not** filter on recipient, so any
  plus-addressed mail that reaches the mailbox is found. Same for today's ad-hoc
  chamber read (`chamberofcommerce newer_than:1d`).
- `scripts/email_intake.py` `q_setup = to:setup@restorationai.io`. Whether
  Gmail's `to:` matches `setup+test@` is **unverified**. The mailbox has zero
  plus-addressed mail today (`to:setup+test@…` returned 0 hits and `"setup+"` returned 0 hits), so it
  can't be tested read-only. The broad sweep (`in:inbox newer_than:3d`) would
  still catch such mail, but it would get the lenient "broad" handling, not the
  strict setup@ path.
- Also unverified: whether Workspace delivers `setup+x@` for an alias at all.
  Settling this takes one test send (MacBook side, since the Mini never sends).

## 2. CAPTCHA checkbox test, chamberofcommerce.com Desert Valley: CHECKBOX PASSED; listing DUPLICATE-FLAGGED

Timeline (CDP 9223, held suite profile):
1. Form still filled (DBA name, 3808 N Octagon Rd, 89030, 7026335033, cat 3312, setup@, password set). reCAPTCHA widget unchecked.
2. **ONE normal click** on the "I'm not a robot" checkbox (mouse move + single click). It **resolved green immediately with no image or audio challenge** (bframe 0×0, token 2,468 chars). No retry was needed. The widget reads "This site is exceeding reCAPTCHA Enterprise free quota", so the site's reCAPTCHA may be running in a degraded or low-friction mode.
3. Clicked "Add My Business" (an `<a>`, not a `<button>`; my first locator timed out, and the second attempt landed well inside the token window). Landed on `/members/activate-my-account` at **09:37 PDT**.
4. Activation email arrived at setup@ within seconds ("ChamberofCommerce.com Activation Email" from membership@noreply). I read the key with the Gmail helper, entered it, and the **account activated at 09:39**. This is the first end-to-end unattended email-code read.
5. **Problem:** chamber then showed **"Duplicate Business Found"** in My Businesses. Our record `my.chamberofcommerce.com/business/USA/2034512140` now carries OLD data, not what we submitted:
   - name "Desert Valley Contracting" (not the DBA), address "3808 Octagon Rd Suite 2", 89030
   - phone **725-228-5575** (not the real 702-633-5033), website desertvalleycontracting.net, "95 Reviews"
   - Its public "View Business" link (`…/contractor/2034512140-desert-valley-contracting`) **redirects to a different, pre-existing UNCLAIMED listing**:
     https://www.chamberofcommerce.com/business-directory/nevada/north-las-vegas/contractor/37998255-desert-valley-contracting
     (3395 W Cheyenne Ave Ste 107, 89032, 702-633-5033, 56 reviews, "CLAIM YOUR LISTING").
   - The 09-27 morning dedupe ("no existing DV listing found") missed both older records.
6. **Stopped.** No edits saved on the listing editor. `record_listing` was **not** called because there is no clean URL that represents our submission. Chamber's duplicate-help link: https://my.chamberofcommerce.com/member-services?help=duplicatebusiness&country=USA&id=2034512140

Screenshots: `browser_agent/runtime/audit/2026-09-27-chamber-dv-01…10-*.png` (before/after click, after submit, editor, My Businesses, public view).

## 3. Quit held Chrome: DONE (profile lock released)
- Browser.close and then SIGTERM were ignored. Cause: open tabs with beforeunload handlers, including the leftover BBB `get-listed/business` form. I closed each tab with `run_before_unload=False` and then ran Browser.close, and Chrome exited.
- Chrome then **auto-relaunched itself** (a pending update: 152 → 154) with identical args at 09:41 and no windows. I closed it once more with Browser.close. After 20 s: no process on the profile and no Singleton lock files. The 11:30 sweep can open the profile.
- Bing session was not re-verified (would need reopening Chrome). The sweep will show whether Santino's 09-27 Microsoft sign-in persisted.

## Cost / time
~11 min wall clock. No paid actions. One account activated (chamberofcommerce agency, DV). Two ledger lines pushed as events happened.

## Queue next
1. Human decision on the chamber duplicate (options below, in Needs).
2. 11:30 scheduled sweep, which is the first test of the Bing session from Santino's sign-in.
3. One MacBook-side test send to `setup+test@restorationai.io` to settle plus-address delivery and `to:` matching.
