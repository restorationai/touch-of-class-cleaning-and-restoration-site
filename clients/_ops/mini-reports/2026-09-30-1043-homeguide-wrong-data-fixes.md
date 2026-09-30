# 2026-09-30 10:43–10:57 PDT — HomeGuide wrong-data fixes (unattended, Santino-approved inbox item)

**Ran:** logged into each client's own HomeGuide account (creds homeguide.<slug>) in a SEPARATE
CDP Chrome (`browser_agent/runtime/hg-edit-profile`, port 9333) so the 11:30 sweep keeps the
persistent profile free. Edited `app.homeguide.com/pros/profile/edit-info`, Save, then re-opened
edit-info to confirm the stored values and loaded the public page to confirm what customers see.
No payment pages, no CAPTCHA, no SMS/phone verification prompted on any phone change.

**Finding that shaped the fix:** HomeGuide has TWO phone fields, "Cell phone" (lead
notifications) and "Business phone". The public page's embedded JSON (`"phone":…`) is fed
by the **Cell phone** field. Changing only the Business phone left the tracking number public
(verified on DV), so I changed BOTH fields on every listing that carried a tracking number.

| Client | Field | Before | After | Verified |
|---|---|---|---|---|
| rachelle-elliston (DV) | name | Desert Valley Contracting Inc | Desert Valley Restoration-24/7 Emergency Plumbing, Water and Fire Damage Restoration | edit-info + public H1 (no length cap: the full 84 chars were accepted; HomeGuide's H1 title-cases "And") |
| | cell + business phone | (725) 228-5575 (tracking) | (702) 633-5033 | public JSON phone 7026335033 |
| dry-bros-water-fire-restoration | name | Dry Bros Water & Fire Restoration | Dry Bros - 24/7 Emergency Water Damage Restoration & Mold Remediation | edit-info + public H1 |
| | phones | (877) 379-2767 both | unchanged (already real) | public JSON 8773792767 |
| flood-solutions-inc | cell + business phone | (586) 300-3967 (tracking) | (586) 580-0197 | edit-info only (no public URL, see below) |
| | name | Flood and Fire Solutions | unchanged (rename not final) | |
| aldredo-moreno (ACS) | cell + business phone | (432) 226-6634 (tracking) | (432) 847-4704 | public JSON 4328474704 |
| | name | ACS Enterprise | unchanged (rename not final) | |

**Public URLs / record_listing**
- DV: https://homeguide.com/nv/north-las-vegas/water-damage-restoration/desert-valley-contracting-inc-z30PG1i5H (re-recorded, phone_matches)
- Dry Bros: **NEW URL**, not captured before because the 09-29 sweep said review_needed: https://homeguide.com/il/oak-lawn/water-damage-restoration/dry-bros-water---fire-restoration-eI85o0Jum (recorded). The URL slug keeps the old name; HomeGuide doesn't re-slug on rename.
- ACS: https://homeguide.com/tx/midland/water-damage-restoration/acs-enterprise-hrHUH1zUS (re-recorded, phone_matches)
- Flood Solutions: **still no public URL.** It isn't in HomeGuide search at 48023 or 48042. Provider id yOUYKn7Hv (review link https://homeguide.com/providers/yOUYKn7Hv/review). The provider id is NOT the public URL id (ACS: provider jVXOPCQBy vs URL hrHUH1zUS), so the URL can't be derived from it. No record_listing, only the browser_agent_actions ledger row.

Ledger: 4 lines in mini-ledger.md (pushed one by one) + 4 browser_agent_actions rows (homeguide-wrong-data-fix, done).
Screenshots: browser_agent/runtime/audit/20260930-1744*–1755*-hgfix-*.png (before/filled/after per client, public pages).
Cost/time: ~14 min, no spend.

**Flags**
- Intro text on DV and Dry Bros still uses the OLD names ("Desert Valley Contracting Inc serves…", "Dry Bros Water & Fire Restoration serves chicago…"). The order was name/phone only, so I left these. Editing is a one-field change at /pros/profile/edit-intro if wanted.
- DV's public page JSON has `"noIndex":true` (probably because setup is 1/6 complete), so HomeGuide may not let search engines index it. Worth checking whether completing the profile flips it.
- Flood Solutions' listing address is 10153 Marine City Hwy, 48023, but the companies row has 49118 Shannon Ct, Macomb 48042. Not touched (phone-only order). Someone should confirm which address is right.

**Queue next:** the intro-name edits (if approved); Flood's public URL, to re-check in a day. It may need profile completion before HomeGuide publishes it.
