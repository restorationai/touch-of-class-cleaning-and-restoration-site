# Mini run 2026-10-01 18:11 PDT: Apple Podcasts, narestco, on the Ignite Apple ID

Trigger: apple-ignite-1790903247 (UNSUPERVISED). It answers NEED-20260930-1520 (MacBook 2026-10-02T01:07Z: switch to the
Ignite Systems Apple ID). The inbox item has been marked "NO LONGER SUPERVISED" since 09-27, so it ran.

## What ran
1. Heartbeat pushed (57d6bfd13), kill switch off, pulled.
2. ops_kv `mini-handoff:portal-creds:apple_id_ignite` was merged into `~/.rankai/portal-creds.json` as `apple_id_ignite`
   (chmod 600, not in git). Then the ops_kv row was DELETED (verified 0 rows).
3. Opened a NEW agent Chrome tab (9223) at podcastsconnect.apple.com and got the Apple sign-in. The field was prefilled with
   contact@restorationai.io; I replaced it with ignitesystems3@gmail.com.
4. Password #1 was rejected ("Check the account information you entered and try again").
5. Password #2 (one attempt, as the rule allows) was ACCEPTED. Only #2 is kept in portal-creds; #1 was discarded.
6. 2FA screen: "Enter the verification code sent to your Apple devices." It went to a trusted device, with no SMS and no
   number shown. Per the answer, I STOPPED here. I did not click "Can't get to your devices?" or "Resend", and the tab is
   left open.

## Outcome (narestco)
PARKED at Apple 2FA (trusted device). Nothing was submitted to Podcasts Connect. No Media Services terms were accepted and
no payment details were touched. contact@restorationai.io was left alone.
NEED-20261001-1814-apple-ignite-device-2fa.

Screenshots: runtime/audit/20261001-181249-apple-ignite-01-connect.png, -02-after-username, -03-after-pw1,
20261001-181345-apple-ignite-04-after-pw2.png (2FA screen).

## Cost / time
18:11-18:16 PDT, $0. 2 password attempts used (the max). No CAPTCHA.

## Next
- When the Need is answered: enter the device code (or the SMS route if B is OK'd), accept the Apple Media Services terms if
  asked, and submit https://podcasts.restorationai.io/narestco/feed.xml. Ledger it, and once approved, record_listing plus
  the backlink row apple-podcasts.
- Note: it's 18:1x PT and the 7pm window is close. If the code comes later tonight, the submission itself isn't a citation
  directory, but I'd still run it on the next daytime trigger unless told otherwise.
