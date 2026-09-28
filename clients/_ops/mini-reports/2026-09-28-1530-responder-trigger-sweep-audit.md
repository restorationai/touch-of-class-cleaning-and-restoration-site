# Mini run — responder trigger 1790633929 (2026-09-28 15:22–15:35 PDT, UNSUPERVISED)

## What ran
- Heartbeat pushed (kill switch OFF), `git pull` clean.
- Trigger cause: the daily responder canary (NEED-CANARY-202609282216, answered
  22:18 UTC). No new inbox item and no answer to any parked Need, so there is
  nothing to resume.
- Inbox walk (no browser work this session):
  - ALL-DAY BLITZ (09-27): dated for 09-27 and wrapped yesterday. No blitz item
    for today, so I did not rerun it. Houzz is still waiting on
    NEED-20260927-1305-houzz-namecap.
  - APPLE PODCASTS: still parked on NEED-20260927-1417-apple-media-activation
    (payment method + Apple Media terms), which has no answer yet.
  - BBB CLAIM DV, Bing step 2, client-identity re-test: supervised, skipped.
- Default work: I checked today's 11:30 launchd sweep log (/tmp/rankai-mini-sweep.log,
  finished ~11:41). It had not been reported or ledgered, so I audited it.

## Today's 11:30 sweep, per client
| client | lane | outcome |
|---|---|---|
| rachelle-elliston (Desert Valley) | HomeGuide create | LIVE: https://homeguide.com/nv/north-las-vegas/water-damage-restoration/desert-valley-contracting-inc-z30PG1i5H. **Wrong NAP:** phone 725-228-5575 (TRACKING) and name "Desert Valley Contracting Inc" (not the settled DBA). |
| flood-solutions-inc | HomeGuide create | review_needed. Wizard completed with phone 586-300-3967 (TRACKING, activated 09-11), not found in search after 4 tries, no URL. |
| Reign Restoration | Yelp/MapQuest corrections | SUPERVISED, not run |
| — | Bing | "not signed in after sso" |
| — | LSA phone pass | skipped (Mini policy) |
| — | gbp-seat | 36 checked, 3 need owner (puroclean-east-las-vegas, restoration-groups, homelyft-restoration-ms) |

## Failures / root cause
`browser_agent/sweep.py` `_gbp_primary()` still follows the 07-31 GBP-primary
phone rule. On clients with active call tracking, GBP primaryPhone is the
tracker, which the 09-26 CORRECTED policy (docs/CITATIONS-REBUILD.md §3)
forbids on citations. The sweep also takes the business name from GBP/companies,
not the settled DBA. The 09-27 creations (katofsky, heritage) used companies_row
phones, so they are probably fine, but they are worth a spot check.

I did NOT edit sweep.py (outside my allowed scope) and did NOT unload the plist
(Santino graduated it to unattended). Both are decisions for MacBook Claude and
Santino. Next queued: aldredo-moreno and dry-bros at 11:30 tomorrow.

## Ledger / Needs
- Ledger: 2 lines (DV live with wrong NAP, Flood Solutions review_needed).
- Structured Need: NEED-20260928-1530-sweep-tracking-phone (type=human, urgent before 11:30 09-29).

## Needs
- Sweep phone/name source fix, or pause the sweep until it's patched, plus approval for supervised HomeGuide wrong-data fixes for DV and Flood Solutions (NEED-20260928-1530-sweep-tracking-phone).
- Still open from 09-27: Houzz 50-char name, Apple media activation, BBB Heritage address loop, chamber Dry Bros captcha retry.

## Cost / time
About 13 min, no browser, no API spend.

## Next I'd queue
Once the Need is answered: supervised HomeGuide edits (DV → 702-633-5033 + DBA;
Flood Solutions → real line), then resume the sweep.
