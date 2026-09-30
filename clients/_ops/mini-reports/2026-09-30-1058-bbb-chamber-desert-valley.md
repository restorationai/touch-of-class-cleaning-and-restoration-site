# 2026-09-30 10:58–11:17 PDT — BBB claim finish + chamber claim 2001319165 (Desert Valley)

Both ran in the separate CDP Chrome (runtime/hg-edit-profile), not the sweep profile. That Chrome is now closed and the sweep profile is free for 11:30.

## BBB: DONE (claim finished, name edit submitted, pending BBB staff review)
- Forgot Password at bbb.org/account for setup@. The reset email was read with the Gmail helper. I saved a new 19-char password to `~/.rankai/portal-creds.json` → `bbb.rachelle-elliston` BEFORE submitting it.
- BBB offered SMS codes; kept **email**. Login needs an email MFA code every time; the Gmail helper read it unattended.
- The account opens the BBB Business Portal for **Desert Valley Contracting Inc, BBB ID 78265**, so the claim is real.
- "Update Your Business Information" (Edit All → Review → Save Changes). Submitted:
  - Business Name: Desert Valley Contracting Inc → **Desert Valley Restoration-24/7 Emergency Plumbing, Water and Fire Damage Restoration**
  - Additional Business Name **"Servpro of Downtown Las Vegas" REMOVED**. The editor offered it, so no Need was required.
  - Legal name kept as Desert Valley Contracting Inc. Accreditation box left unchecked. Nothing paid.
  - Submitted by "Rank AI, authorized marketing agency for Desert Valley" / Marketing Agent / setup@, with the certification box ticked.
  - BBB: "Thank you for the update - BBB will review and respond as needed."
- Address: BBB stores `3808 Octagon Rd, North Las Vegas NV 89030-4486` (USPS form). I typed `3808 N Octagon Rd…`, but BBB did not treat it as a change (it wasn't in the review table). Same place; left as is.
- Primary phone was already (702) 633-5033. record_listing: bbb profile URL (status claimed).
- **Flags (not in scope, not touched):** the profile still lists extra phone 702-778-9451, additional URL https://www.servprodowntownlasvegas.com, and two old locations as "Additional Locations" (3445 W Lake Mead Blvd STE 100 and 3395 W Cheyenne Ave STE 107). The editor can delete them with a checkbox if wanted.

## Chamber 2001319165: CLAIMED + NAP EDITED, then AUTO-DEACTIVATED (support asked)
- The listing now has the red "Claim Your Listing" button that support described. Logged in as the agency (setup@).
- Claim gate: certification checkbox (real mouse click), then **ONE reCAPTCHA checkbox click, which went green with no puzzle** (token 2468 chars). Claimed 11:10.
- Editor: name → DBA, address `3808 N Octagon Rd` ("Suite 2" dropped), 89030 North Las Vegas NV. Phone was **already 7026335033** (not the 725 tracking number support mentioned). Suppress stayed off. Closed the premium pop-up twice. Saved 11:13 and read back after a reload.
- **Then, within minutes:** My Businesses shows 2001319165 as **"Business Deactivated — automated systems inability to confirm the legitimacy of your business… confirm it is listed on Google My Business, then Recheck"**. The public page (69 reviews) now returns **410**. 37998255 and 2034512140 also return 410 publicly and still show "Duplicate Business Found". So DV currently has **no live chamber page**.
- Most likely cause: the DBA name no longer matches DV's GBP name. In the citations-first rename flow, GBP is renamed after citations, so it still has the old name.
- I did **not** click Recheck (it would fail the same way; no retry loops), did **not** revert the name (judgment call), and did **not** use "Upgrade to bypass validation" (paid).
- **Sent ONE reply in support ticket #331862** (Gmail thread 1a0e8828a88910ff, from contact@ because the mailbox has no send-as for setup@) asking them to (1) merge 37998255 + 2034512140 INTO 2001319165, and (2) validate and reactivate 2001319165 manually. The DBA is filed with NV; I offered the cert but did not attach it.
- record_listing: the chamber slot on the citations card still points to 37998255, which now returns 410. record_listing won't overwrite a slot someone already set. Needs a manual update once support settles which record survives.
- Structured Need: NEED-20260930-1117-chamber-dv-deactivated (options a/b/c).

## Lesson for the rename flow (worth a doc line)
chamberofcommerce.com re-validates a listing against Google Business Profile after an edit. Renaming a chamber listing to the DBA **before** the GBP rename gets it deactivated. The 37998255 rename on 09-27 probably hit the same check, which would explain why it is 410 too. Houzz/Yelp-style validators may behave the same way. Consider holding chamber renames until the GBP rename has happened.

Screenshots: browser_agent/runtime/audit/20260930-1758*–1815*-hgfix-bbb-*.png / -chamber-*.png
Cost/time: ~20 min, no spend. Ledger lines pushed live: BBB login, BBB edit, chamber claim, chamber NAP, chamber deactivation.
