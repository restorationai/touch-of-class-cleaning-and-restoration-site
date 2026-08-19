# Working State — leave-and-resume doc

Updated: 2026-08-19 (UTC). Keep this current when a work thread pauses.
Deeper context: docs/seo-videos-gap-analysis-2026-08.md (SEO queue),
docs/bobby-olson-call-plan-2026-08-18.md (Bobby items + statuses),
docs/rt-olson-hvac-split-memo-2026-08.md (split recommendation).

## Latest (2026-08-19): safety trilogy SHIPPED, Yelp ON ICE

- **Pipeline safety trilogy done + reviewed**: (1) scripts/repo_git_guard.py — every
  automation git sync (cutover_execute, content_writer, ads_provision,
  case_study_intake) skips active sessions, aborts stranded rebases, never raises;
  (2) scaffold product guard — copy_starter merges code but preserves rendered
  content .md, public/images, image-meta.json, prompts/ (plus a rendered:true guard
  in write_content_md); (3) stage_checker MID-BUILD STALL alarm — 2d+ in building
  with a started-but-unfinished build alarms as Santino-owned (dwell-anchored, loop-proof).
  Review pass fixed: timeout leak in the guard, queued-behind-cap false alarms, and a
  test-inflicted empty image registry (restored, staging redeployed + verified).
- **Yelp playbook ON ICE (Santino + my recommendation agreed)**: needs a live
  code-relay loop + scheduled verification windows; runs LOCAL (Yelp bot defenses
  make cloud browsers impractical). When un-iced: phase 0 = Monica collects existing
  Yelp logins via secure share (skips the claim dance entirely for already-claimed
  pages); phase 1 = unattended audit + email-verifiable claims; phase 2 = phone-code
  windows. Fran incident fixed on the way: Monica's human-defer now keys on GHL
  userId everywhere (she was deferring to her own unrecorded webhook reply).
- Uploads gallery MERGED to app production.

## Where we were before the Bobby Olson sidetrack

Working the SEO gap-analysis queue, one item per Santino "go":
1. ~~Home-city cannibalization fix~~ **DONE 08-18**: plan_site skips the primary area
   for all new builds; 23 sites migrated with 301s, deployed main+staging fleet-wide,
   live-verified on 5 domains, work_log lines written.
2. **Yelp claiming playbook** (browser agent, supervised runs) ← NEXT on "go"
3. Area-page FAQs (FAQPage schema on area hubs)
4. Wrong-page-ranks monthly check (DataForSEO + GSC)
5. Small batch: review-card wording, GBP post deep links, 3rd weekly post slot, GSC social connections
6. Santino yes/no: BrightLocal spend for long-tail citations
New queue items from that session: YouTube buildout (question-videos + shorts + owner-avatar
pilot with Kyle), social-channel connections (phase 1 = handle fields + we click GSC; phase 2 =
Meta OAuth), citations program (agent + BrightLocal + tracking), visual sitemap generator
(post-#1, reveal-deck artifact).

## Bobby Olson (RT Olson + Dry County) — current state

- **RT Olson site**: 124 pages LIVE on staging preview, hero lead form, real van hero
  (wrapped Sprinter), real crew team photo, zero placeholders. Promised: done Friday,
  live before next Tue (follow-up call booked Tue). Production push NOT yet done.
- **Go-live blocker**: GoDaddy NS flip to amos + anastasia.ns.cloudflare.com (zone
  provisioned, email-safe, we hold no GoDaddy access — ask is with Bobby via Monica).
- **Monica directive filed** (note 89b734d8): emails Bobby preview + findings + NS ask
  during his business hours.
- **Review request test**: sent 9:00:01 AM his time, he clicked it. Step 2 drips Thu
  unless parked. Hub worker fixed: submissions now arm immediately (were parked forever).
- **Geo-grid**: 8 plumbing keywords x 5 cities configured, baseline scan stored 08-18.
- **Citations**: NEVER created for either company — queued for browser-agent runs; also
  investigate why nightly sweep skips post-08-09 clients.
- **Uploads gallery**: app shows team/ + docs/ + job-photos now — branch
  `feat/uploaded-gallery` on localhost:5173, AWAITING SANTINO CONFIRM before main push.
- **HVAC split memo**: drafted (one site + one GBP; ads-only domain fine). Bobby's
  agency audit went to getrestorationai.com inbox — Santino to forward to contact@.
- Waiting on Bobby: customer list, review selfies (him+Tim by truck, both companies),
  job stories from Jenny, real Dry County van photos (supersede invented fleet), the
  audit doc, GoDaddy NS change.
- 2 content-review lint flags open: santa-ana-ca lead-paint line, slab-leak blog
  insurance wording.

## Incidents this session (fixes shipped, lessons queued)

- rt-olson gitlink loop (8 nights of re-scaffold): fixed + guards in both workflows +
  scaffold try/finally.
- site-build scaffold-skip bug (brief plants logo first): check keys on package.json now.
- Plumbing template gaps: services-hub archetype added; site prompts patched in-place —
  QUEUED: port proper render prompts into templates/plumbing/.
- Scaffold clobbers rendered content (known NaRestCo gotcha, hit again): QUEUED guard.
- Local automation ran git pull mid-session → orphaned commits, 48 files shipped with
  merge markers, core images lost: all recovered; QUEUED: repo lock so crons don't do
  git ops while a session works.
- photo_harvest apply now re-applies when manifest says done but file missing (was the
  invisible-hero bug).

## Standing watchers / crons to be aware of

- Monica: 60-min human quiet window on every send; call requests = pass-along only.
- Ops pings → Santino's 808 (reverted from travel 805-539).
- Dry County dev-agent revamp SHIPPED (3-van hero live); optional van-lettering regen
  once Bob's real van photos arrive.
- Iowa DBA registry watcher (Kyle/Crew Sioux City) nightly; Apple Maps 3 listings in
  review (runs 2-3 pending); Air Care reveal + WordPress NS flip pending Sarha.
