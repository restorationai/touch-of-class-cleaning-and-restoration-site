> **SUPERSEDED (2026-09-27)** for everything about the BrightLocal bought
> layer by docs/CITATIONS-REBUILD.md (the per-client 3-month ladder,
> ordering rules, costs) and scripts/brightlocal.py. Stale here: "$1 per
> listing" (credits are $2.40), "Apple Maps" in the BL pack (Apple is
> never bought via BL; Business Connect only), the yelp-exclusion TODO
> (yelp stays IN BL picks until the owned lane graduates), and the lane
> list (Foursquare/MapQuest/YellowPages are aggregator-covered now). The
> supervised-runs ledger and monitoring-loop sections remain a useful
> history of the Mini program; docs/MINI-OPERATOR.md is the live source.

# Mac Mini Citations Program — state, plan, monitoring (2026-09-14)

The reference doc for the Mini-as-citation-operator program. If context is
ever lost, this file + docs/MINI-OPERATOR.md (the Mini's standing orders) +
clients/_ops/mini-inbox.md (its live queue) reconstruct everything.

## The two-layer citation stack (near-zero overlap, verified 09-14)

- **BrightLocal (bought layer):** ~99-site long-tail volume pack per client
  (Manta/Hotfrog/acompio class + Apple Maps), $1/listing via CB credits.
  Orders gated on the rename gate; hand-pick top-DA is the order default.
  Of our 12 hand-built directory types, ONLY yelp.com also appears in BL's
  menu. TODO: exclude yelp.com from --pick-top auto-picks (owned lane).
- **Mini/browser agents (owned layer)** — what BL structurally cannot do:
  1. Owner-verified session builds: **Bing Places** (GBP import, we own it)
  2. Account-owned marketplaces: **Houzz, HomeGuide, MapQuest**
  3. Editorial/application (AI-citation gold): **ThreeBestRated,
     TrustAnalytica, Expertise.com, ContractorsRanked,
     HomeServices.Review, Quality Business Awards**
  4. Corrections (wrong_data), claims, Yelp profile edits
  5. Anything needing the client's Google account (GSC association)

Fleet counts (citation_listings): trustanalytica/houzz/threebestrated 21
each, homeguide 17, bing 10, one-offs: expertise, contractorsranked,
homeservices_review, quality_business_awards, mapquest, angi, yelp (1 each).
All built from the MacBook-era lane; the Mini has executed ZERO runs so far.

## Client-identity platforms ("yours to set up") — RE-TEST QUEUED

Angi, Nextdoor, Thumbtack, Facebook, Yelp claim/edit, HomeAdvisor
(free-tier check only). Historically owner:'client' because of identity/
phone verification blockers. The toolkit changed since: setup@ identities,
GBP-primary phone policy (verification rings lines we answer), Gmail-helper
code reads, delegate access. The Mini re-test batch (in its inbox,
supervised) attempts each for narestco and files per-platform verdicts:
US-BUILDABLE / NEEDS-CLIENT-STEP (named) / HARD-BLOCKED. Guardrails:
agency-authorized only, never impersonate the owner personally, stop at
payment walls.

## Supervised-runs ledger (3 clean runs per lane ON THE MINI, Santino present)

| Lane | Done | Left |
|---|---|---|
| Sweep / HomeGuide queue | 0 | 3 |
| Houzz creations | 0 | 3 (first pair queued: narestco + crew) |
| Spotify/Apple podcast connects | 0 | 3 (narestco queued) |
| Yelp edits | 0 | 3 (waits on delegate access, queue #8) |
| Wrong-data fixes | 0 | 3 (Reign MapQuest + Yelp queued) |
| Client-identity re-test | 0 | new batch, supervised |
| Bing sweep migration | hold LIFTED 09-14 | step 1 readiness unsupervised |

One sitting at the Mini can take every lane to 1/3. After a lane's third
clean run, MacBook Claude flips it autonomous in MINI-OPERATOR.md.

## Monitoring loop (BUILT 09-14, live)

1. **Heartbeat-first**: every Mini session commits a line to
   clients/_ops/mini-heartbeat.md BEFORE any work (signal first).
2. **Daily report**: clients/_ops/mini-reports/DAILY-YYYY-MM-DD.md with
   exactly Completed / Problems / Flags.
3. **Mirror**: client-ops-sync (daily 7am PT) stamps freshness into
   ops_kv key mini-status.
4. **The dot**: Build Stages header (superadmin) shows "Mini" pulse via
   the build-stages edge fn: glowing green < 26h since heartbeat,
   amber < 50h, red beyond/never. Tooltip: last beat + latest report.
5. **Prove-the-channel task** sits at the top of the Mini inbox:
   unsupervised, no browser, 2 minutes. First signal expected at the
   next session (manual sitting or the 11:30am PT launchd sweep).

## Getting to 100% — remaining steps

1. First heartbeat arrives (proves channel; sweep firing on its own the
   next day proves launchd). If no heartbeat after a full sweep window,
   go to the machine: `launchctl list | grep -i rankai` + run a session
   by hand; the launchd plist likely needs reinstalling.
2. Santino's supervised sitting: sweep 1, Houzz pair, Spotify, re-test
   batch, Bing readiness report.
3. MacBook Claude reads reports -> drops Bing step 2 (launchd install +
   one supervised sweep) -> retires the MacBook sweep job.
4. Lanes graduate at 3/3 -> autonomous daytime sweeps; MacBook side just
   reads DAILY reports + the dot.
5. Fleet rollout order after graduation: HomeGuide gaps -> Bing full
   fleet -> ThreeBestRated/TrustAnalytica for new clients -> editorial
   one-offs fleet-wide -> re-test winners.
