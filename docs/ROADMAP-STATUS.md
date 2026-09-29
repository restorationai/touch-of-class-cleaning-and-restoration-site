# Roadmap Status: what's built, what's next, what waits on Santino

Santino 2026-09-29: "add this to an MD file to reference in case your memory
gets overloaded or replaced." This is that file. Read it at session start
alongside docs/WORKING-STATE.md, and update it whenever a phase item ships,
a decision lands, or something starts or stops waiting on Santino.

Last updated: 2026-09-29 (evening).

---

## The three follow-through phases

Origin: the 09-28 Katofsky / RestoPros / Go Green audit found 7 failure
modes (lost first calls, untracked promises, stalled renames, silent
at-risk accounts). The fix was split into three phases. Each one is built,
tested on real clients, and approved before the next starts.

### Phase 1: Never lose a call or a promise (DONE 09-29)
Details: docs/FOLLOW-THROUGH-SYSTEM.md.
- Unmatched calls are re-checked for 7 days, matching by attendee email,
  phone and name.
- New clients are linked at signup (this also fixed a bootstrap job that had
  been timing out for 5 days).
- Promise tracker: `public.client_commitments` + `scripts/promise_tracker.py`,
  hourly. It reads full transcripts and Santino's texts, and a promise closes
  only with proof. Reminders go out the day before and when overdue, and the
  digest opens with PROMISES.
- Monica doesn't nudge a client while we owe them something (promises from
  09-29 on).
- Monica autosend of simple promises: BUILT, OFF (`PROMISES_MONICA_AUTOSEND`
  unset, notify-only). Waiting on Santino.

### Phase 2: Every client moves through the rename (NOT STARTED)
1. **FIRST:** Monica follows up on her own "I'll check with Santino and get
   back to you." Today nothing tracks it, so it never leads her next message
   (Dan's mold question). Held webhook replies are also never retried.
2. Name options for every client, with or without a Google profile.
3. A no-profile path: DBA, then site and listings, then create the profile
   with the GBP Planner.
4. The rename pitch auto-sends about 2 days after the options are ready.
5. Stall alerts: options ready but not pitched for 3 days, or waiting on the
   DBA for 7 days.

### Phase 3: Keep clients engaged, catch at-risk accounts (NOT STARTED)
1. A weekly Monica update to every client: what we did, what's next, what we
   need.
2. Monica stops asking for things that aren't due yet or that we already hold
   (Katofsky's customer list, Go Green's EIN).
3. A "paying but no results" alert before renewal (would have caught Go
   Green).
4. Failed payments go into a Monica sequence before the account is suspended
   (would have caught Heritage).

---

## Built, waiting on Santino's OK

| Item | Where to look | What happens on "yes" |
|---|---|---|
| Ops Attention fix (render crash, all-notes paging, preview cards only for sites not yet live, inactive clients hidden) | localhost:5174, app branch `fix/ops-attention-render` | merge to app main (Netlify deploys) |
| GBP Profile Planner (mock profile, Create Listing / Update & verify, service pills, phone phase, photos) | localhost:5173, app branch `feat/gbp-planner` | merge |
| Planner phone swap (real number primary during verification, DNI tracking primary 3 days after) | edge fn `gbp-planner` | `supabase secrets set GBP_PLANNER_PHONE_SWAP=1` |
| Monica promise autosend | `scripts/promise_tracker.py` | set `PROMISES_MONICA_AUTOSEND=1` |
| Dan (RestoPros) mold name reply | draft below | send via `monica_oneoff.py` |
| GBP cover from site hero, every client | `scripts/gbp_cover_sync.py` (built 09-29, 77bacfd42, nightly in report mode), gallery https://claude.ai/artifact/K7YfDY1yQNGwqfAubMaSjM | set repo var `GBP_COVER_SYNC_WRITE=1` after he approves; per-client flags `--replace-owner-cover`, `--allow-ai-branding` |
| September report gaps (the 09-01 send reached 27 clients; the link text never reached Bob (Dry County + RT Olson, one contact), Go Green or TDI; Home Pride has no email on file). July reports were never sent to anyone, and no backfill is planned | `client-reports.yml` | 3 texts via monica_oneoff + Home Pride email once we have an address |
| Frontline's new address (also the NAP-drift system error) | Santino to confirm the address | update GBP + site + citations |
| PRNow test, Apple Podcasts card | | |
| Air Care LSA (09-29): stuck at verification 25 days. The API shows only the 09-04 background check (NO_SUBMISSION, the Jennifer-name one); Sarha's 09-26 Evident redo is not registered, and there's no license or insurance on file. Budget is $19,000/DAY with nothing on record agreeing to it | LSA portal + Google Ads support, customer 651-449-5227 | Santino calls Google; decide the real budget before verification clears |
| 10 prospect audits failed in Sept (8 killed by deploy restarts before the 09-29 guard, 2 in the 09-14 credit outage): Titan (AZ), Magic Clean, AFC Cleaning, United Water, Doctor Dry, We Do It All, Money for Repairs, + 2 no-website | marketing_jobs | re-run for sales if still warm |

**Dan's draft** (no plumbing, no pushback, per Santino 09-29):
> Great pick, and mold is a smart swap. In Maryland about 1,600 people a
> month search "mold remediation" vs about 140 for "fire damage
> restoration." So we'd go with: "RestoPros of Central Maryland - 24/7
> Emergency Water Damage Restoration & Mold Remediation". Want to lock that
> in? Once you confirm, file it as a DBA exactly like that and send us the
> filing.

Context: 09-28 Dan picked "RestoPros of Central Maryland- 24/7 emergency
water & fire damage restoration" and asked "Can we possibly add mold to the
name? We do more mold than fire." Monica answered "passing the mold question
to Santino" and nothing has gone out since.

---

## GBP Profile Planner: client decisions

- **Veterans (CO-1788378820811):** the plan title was the shorter 09-20 pick
  ("...24/7 Mold, Water & Fire Damage Restoration"), but the DBA was FILED
  (verified via the state email) as "VETERANS REMEDIATION & RESTORATION -
  24/7 MOLD REMEDIATION, WATER AND FIRE DAMAGE RESTORATION", and the live
  GBP already shows that. On 09-29 the plan title was set to the filed DBA
  word for word ("Veterans Remediation & Restoration - 24/7 Mold Remediation,
  Water and Fire Damage Restoration"), so the planner never proposes a rename
  away from the filed name. Rule: **the planner title always equals the filed
  DBA.**
- **Dry Bros (CO-1788898034500):** plan title = DBA ("Dry Bros - 24/7
  Emergency Water Damage Restoration & Mold Remediation"). The planned cover
  is the site hero (drybros.com/images/hero-bg.webp). It is AI-generated and
  shows invented van branding. Swap it for real van/crew photos from Amin's
  call when he sends them; until then the AI hero is the placeholder.

## GBP cover photo standard (Santino 09-29)
Every client's GBP cover = their site hero, smart-cropped to exact 16:9
(1920x1080, the key subject kept in the central ~70% because Google crops
further on mobile). RestorationXpress is the reference look. The system runs
per client nightly and refreshes the cover when the site hero changes.
Open policy question: replace a cover the OWNER set themselves? The default
is to skip those and list them for Santino.

---

## Ops Attention: what the numbers mean (09-29)

**System Errors (red card)** = `[PIPELINE ALERT]` notes from
`pipeline_watchdog`. They refresh in place and auto-resolve when the
condition clears. On 09-29, 3 stale ones were resolved (RestoPros bootstrap,
monthly-reports, Paul Davis cadence). What remains:
- gbp-maintenance: a rerun is in flight, and the alert auto-resolves if it
  passes.
- LSA silent x3 (HomeLyft, Flood Fixers, PuroClean East LV): serving but 0
  leads in 14 days. Real.
- heartbeat:ai-scan: dead 10 days. Real.
- Optimizer SLA x5 (Veterans, Dry Bros, FIX, AAA, Go Green): unverified,
  no-access or suspended profiles. The apply is now blocked-aware (commit
  e7914892a), so these clear as the SLA learns to skip them.
- NAP drift x2: Frontline (address change pending Santino) and
  restoration-groups (GBP says Fair Lawn, site says Kenilworth). Real.

**Today (~419)** = 4 piles:
1. ~171 "we owe" setup-ledger items (citations-build 43, gbp-suggestions 40,
   site-imagery 31, site-finished 28, map-rankings 14...). Machine-tracked
   fleet backlog that auto-closes when the work lands. Not a to-do list for
   Santino.
2. 41 "website preview ready" cards, 27 of them for sites already live and 2
   for dead clients. App fix on the ops branch: 41 -> 9.
3. ~245 tagged notes: [TODO-SANTINO] 189, [TODO-PROPOSED] 53, other 3.
   - ~80 are "Dev agent NEEDS INPUT", mostly "CI has no Google/DataForSEO
     credentials". That's a system gap (the nightly dev agent can't reach
     the APIs), not a decision for Santino. Fix: route those tasks to a
     runner with the credentials, then close them as a group.
   - 49 are "CALL COMMITMENT" client asks from the last 2 weeks. They
     overlap the promise tracker. Merge them into `client_commitments` (one
     canonical store) instead of keeping two lists.
   - The rest are real: toll-free rejections, hub uploads to review, a
     handful of decisions.
4. Monica escalations from the last 7 days.

---

## Queued for later (not phases)
- Expansion system: landlord outreach, a separate identity for each location
  (docs/EXPANSION-SYSTEM.md, queue 22).
- Awards pipeline scheduled for every client (queue 20).
- Facebook + LinkedIn page connection (queue 21).

## Standing rules this doc relies on
Single source of truth. No em dashes in client copy. Quiet hours. One-offs
only via `scripts/monica_oneoff.py` or `scripts/scheduled_sends.py`. Dan and
RestoPros: no plumbing, no pushback. App changes: localhost first, merge only
after Santino confirms.

### Every client action logs (09-29)
Any system that changes a client's Google profile, site, listings or ads, or
delivers research to them, writes one plain client-readable line: Google
profile edits via `gbp.log_change` (marketing_gbp_changes), everything else
via `work_log()` (marketing_work_log). Fail-soft, never the plan, only what
Google or the site actually accepted. `monthly_summary.py` maps it into the
Reports tab.
