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
| Kenny (Veterans) 850 numbers: Santino promised it on the 09-28 call; the dev agent stops because buying numbers costs money (~$1.15/number/month). call_tracking.py picks the area code from his real 337 line, so it needs an area-code override + a site DNI swap; keep the 337s forwarding 30 days | scripts/call_tracking.py | Santino says go |
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

## Onboarding pipeline repairs (10-01)

- Auto site builds no longer render inside ops-sync: the ledger plans, commits and dispatches site-build.yml (300-min budget, commits itself). Partial renders (some pages non_json) still commit + deploy; the render sweep retries stragglers.
- Ops-sync + bootstrap commit with `if: always()`, alert on cancel, unbuffered logs; ops-sync budget 120 min. Pipeline watchdog has its own schedule (8:30 am/pm PT).
- Rename pitch auto-queues ~20h after the kickoff call for new clients (rename_autoseed autopitch; kill switch ops_kv rename-autopitch).
- Per-client reveal date: clients/{slug}.json `preview_reveal_on` (PT date) overrides the 10-day soak. Bionic = 2026-10-04.
- Open (from the 10-01 audit): duplicate-checkout stub companies (logan t olsen, Daniel Restum) hold the real subscriptions; phone swap proceeds on a mismatch; pre-kickoff Monica asks; Katofsky Google never connected; Paul Davis Charleston missing prompts/_system.md.

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
Deploy guard (09-29): production sync-deploy refuses automated rewrites of layouts/components/pages/styles/brand.ts/tailwind, automated page deletions, automated changes to existing public/images, and rollbacks of a fresh live deploy this checkout lacks (`scripts/deploy_guard.py`, dry run `--all`). Human, DEV AGENT and `[design-change]` commits pass; `--allow-design-change` overrides and is logged to ops_kv deploy-guard-log.
Site structure (09-30, `scripts/site_structure.py`): GBP services map onto existing pages (`clients/{slug}/gbp-service-map.json`); a new page only for a distinct offered service with >= 20/mo in the client's city (DataForSEO) or >= 5,000/mo nationally incl. "near me" when the city shows only the floor bucket, max 2 per client per night; same-service twin pages merge by static 301s (`scripts/service_merge.py`, ON HOLD pending Santino's review) unless the twin's head + "near me" is >= 10,000/mo nationally. The homepage strip is plan-input `homepage_services` only, parity pages never land there. Water: "get the water out now" is one page, `/services/emergency-water-removal/` ("Emergency Water Removal & Cleanup in {City}"), water-cleanup 301s to it; water damage restoration stays separate. Graffiti (09-30): Graffiti Removal is the canonical page ("Graffiti Removal & Vandalism Cleanup in {City}", `/services/vandalism-graffiti-removal/`); vandalism-cleanup 301s to it, never the reverse (`scripts/graffiti_reversal.py` fixed Air Care + Coastal). Upholstery (09-30): a client whose truth table lists upholstery cleaning keeps a dedicated `/services/upholstery-cleaning/` page; Carpet Cleaning stays its own page.
Emergency plumbing gate (10-01, `scripts/plumbing_gate.py`): emergency-plumbing and every plumbing-claim service are OFF the restoration core floor. A restoration client's site carries plumbing only when (a) the GBP rename with plumbing in the name is confirmed (live GBP title has plumbing, or rename_intent records the rename executed), (b) a DBA filing including plumbing has been uploaded and verified (rename_intent.dba_filed / dba_verified; the name is rename_intent.dba_name or the chosen suggestion), or (c) the client is a licensed plumbing company (plumbing vertical, plumbing license type, or a license shared with a plumbing client: RT Olson, All Pro, ProRestoration). A chosen-but-unfiled plumbing name does not pass. Until then plan_site holds the slug out (even when plan-input lists it), a GBP "Emergency Plumbing"/"Plumbing" service maps to water damage restoration (`gbp_service_map.py`, source plumbing-gate) and is left off the "Services We Handle" list, and the service bank does not stage plumbing variants. Removal on a gated site: placeholders deleted, rendered pages 301 (static) to the water damage restoration equivalent (`plumbing_gate.py --remove --apply`). Never remove plumbing from a client that meets the gate.
City pages must make sense (10-01, `scripts/city_page_gate.py`): plan_site plans /service-areas/{city}/{service}/ only when (i) the client actually offers the service (truth table, pre-core-floor plan-input, explicit non-core service, or a GBP service in the client's own words; a core-floor default keeps its single service page and gets no city pages), (ii) the city is a service area, and (iii) the combo is plausible (per-site Claude pass: no basement flooding where basements are rare, no industrial restoration in a small residential suburb) AND has local demand ("{service} {city}" >= 10/mo nationally per DataForSEO, or the head term + "near me" >= 1,000/mo in the metro, metro = the service-area city with the most "water damage restoration {city}" searches) or a genuine local angle named by the Claude pass. Water damage restoration (plumbing: emergency plumbing) passes in every service-area city. Decisions persist in `clients/{slug}/city-page-gate.json` (src manual is never re-decided; a client confirming a service = add it under "offered" with a client_request note), so the nightly re-plan never recreates a failed combo; undecided combos are held, never planned blind. Rendered pages are never dropped: rendered failures are kept and reported.
GBP parity on the page (09-30): every GBP service mapped onto a page is named on that page in a "Services We Handle" list (customer-language names, deduped, declined/undecided never listed) and in its Service schema (`hasOfferCatalog`). The list is `sites/{slug}/src/data/gbp-services.json`, regenerated from `clients/{slug}/gbp-service-map.json` on every map save (`site_structure.write_page_services`); wiring: `scripts/services_we_handle_rollout.py`.
Emergency naming (09-30, `scripts/emergency_naming.py`): URGENT services only (water damage, emergency water removal, flood, burst pipe / leak, sewage, fire, smoke, storm, emergency board-up / tarping, biohazard / trauma, emergency plumbing when plumbing-licensed). Title + H1 lead with "24/7 Emergency" when plan-input brand.hours says 24/7, else "Emergency" ("24/7 Emergency Water Damage Restoration in {City}"); never doubled; the headline before " | Brand" stays under ~60 chars, dropping "24/7" first, then ", ST". The meta carries the same lead and the body opens with one emergency-response line ("We answer 24/7" only on 24/7 truth, an on-site time only when brand.response_minutes is set). Never mold, remodeling, carpet/upholstery, air ducts, GC, testing or insurance pages; clients with explicit non-24/7 business hours (Davis) get none. plan_site.py applies it to planned titles, build_site.py render pins the opening line, `--all --apply` re-applies to existing pages.
Our Work vs Case Studies (09-30): "Our Work" = the homepage before/after sliders (BeforeAfterSection, `src/data/work.ts`, anchor `/#our-work`); "Case Studies" = its own nav item and `/case-studies/`, fed only by real job stories (Client Hub "Add a Job Story" -> `scripts/case_study_intake.py`). Audit both with `scripts/site_structure_audit.py`.
Site watcher (09-29): `scripts/site_regression_watch.py` (workflow site-regression-watch, per client, nightly and after deploy lanes) fingerprints each live site (nav, homepage sections, videos, logo, service images, sitemap count) into ops_kv site-fingerprint/{slug}. A regression files one System Errors card naming the Cloudflare deploy. Resolving the card, or `--accept SLUG`, adopts the current page.

### Every client action logs (09-29)
Any system that changes a client's Google profile, site, listings or ads, or
delivers research to them, writes one plain client-readable line: Google
profile edits via `gbp.log_change` (marketing_gbp_changes), everything else
via `work_log()` (marketing_work_log). Fail-soft, never the plan, only what
Google or the site actually accepted. `monthly_summary.py` maps it into the
Reports tab.

### Approved site images are never silently replaced (09-29)
A live image changes only when the client asked about that specific image.
The change is recorded with `scripts/image_guard.py approve` (client's words,
who asked, when), which archives the old file under
`clients/{slug}/image-archive/`. `gen_site_images.py --redo/--force` refuse
to run without `--request`. Anything else is reverted to the live version by
the image guard inside `build_site.py sync-deploy`, with the rejected file
archived. The guard also rebuilds stale -480w/-768w/-1200w variants. No hue-shift
recolors of people: skin shares red's hue, so it turns blue (ProRestoration,
11 images). New service pages get their own image through the nightly render
sweep (`gen_site_images --services`, which only adds), never the shared
`services.webp` fallback.

### Search engines every week: Google + Bing (10-01)
Every Monday `.github/workflows/index-watch.yml` runs one job per live site
(stalest first). Google: `gsc_register.py` makes sure the site is a verified
Search Console property (TXT through our Cloudflare zone), submits
`sitemap-index.xml` and writes `gsc_property_url` / `gsc_sitemap_url` back to
marketing_sites; then `index_watchdog.py` samples URL Inspection (50 pages,
1500 in the first week of the month), re-submits the sitemap, IndexNow-pings
pages Google has not indexed, and runs the rescue ladder. Bing:
`bing_webmaster.py` submits the sitemap and a URL batch and records crawl and
index stats in ops_kv bing-watch:{slug}; it does nothing until the
`BING_WEBMASTER_API_KEY` secret exists. IndexNow on every deploy continues.
Heartbeat: any live site whose last successful Google check is older than 8
days raises one System Errors card per site (`pipeline_watchdog.check_index_watch`).
