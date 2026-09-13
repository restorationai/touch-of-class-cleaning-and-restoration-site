# Rank AI — Build Queue

Canonical priority list. Updated 2026-09-11 (post attribution-suite +
call-intel + fleet-DNI night). Keep this file current when items ship or
reprioritize; the session todo mirrors it, this file is the durable truth.

## Ground rules that bind everything below

- **Hands-off clients**: Paul Davis Charleston and Go Green NC get NO work of
  any kind. Do not touch their GBP, site, ads, or records.
- **No em dashes in any client-visible text** (emails, SMS, site copy).
  Internal docs like this one are exempt.
- **Quiet hours**: no client sends outside their local daytime. Queue for
  their morning. GHL timestamps are UTC; convert before judging.
- **Registrar/NS work is human-only.** Browser agents get Google + Bing
  sessions only. setup@restorationai.io is the identity for all registrar
  and delegate accounts; contact@restorationai.io is the Google/Ads login.
- **Approval-gated sends**: Monica never claims/confirms what she can't
  verify (three incidents the week of 09-08). Anything novel she'd send
  goes out in approval mode first.
- **Single source of truth**: one canonical store per fact. Never ask a
  client for data we already hold. Never create a second copy of state.
- **GBP renames are never auto-pushed**: DBA first, then citations/signage,
  then ONE profile edit. NaRestCo never gets review campaigns.
- Monorepo `~/Desktop/mywebsitecode/rank-ai` (this repo). App repo clone at
  `~/Desktop/mywebsitecode/app-work` (never read the stale Desktop -main
  zip). App changes: serve the branch on localhost:5173, merge to main only
  after Santino confirms. `sync-deploy` needs a CLEAN tree and stamps
  clients/{slug}.json after each deploy: commit the stamp or the NEXT
  deploy silently refuses (error prints before the banner; easy to miss).

## Priority builds (reordered by Santino + Claude, 2026-09-12 PM)

VERIFIED 09-12 PM: BOTH email lanes live — contact@restorationai.io AND
contact@getrestorationai.com are polled by email_intake (dry run shows
both), Monica replies from whichever address the client wrote to, the
2-day stale backstop covers both, and emailed change requests now
dispatch to the build lane (feedback_router) identically to texts.
Inbound media rides vision analysis (the model reads the photo,
including any text in it) and auto-files to branding.

1. **Monica rename conversations — THE scale unlock (build next)**
   WHY: 24+ clients carry data-backed name candidates; every decision
   currently needs Santino in a meeting. Text gives a written consent
   trail for the exact string — precisely what the DBA/GBP defense wants.
   BUILD on existing rails:
   (a) RENAME_TRUTH knowledge block (DOMAIN_ACCESS_TRUTH pattern) in
       COMPOSE/REPLY: why keyworded names rank (OneStop, honest framing);
       the sequence — confirm the exact name -> CLIENT files the DBA for
       that exact string (state nuance: CA county FBN ~$50, MA town clerk
       certificate, WA statewide trade name; Monica can share several
       ranked names but the filing must match the confirmed one verbatim)
       -> citations built with the NEW name -> ONE GBP create/change ->
       reverification, if triggered, handled by us. Honest reverification
       risk framing, never scare, never oversell.
   (b) THE ASK, preframed as delivered work (Santino's copy direction):
       "We've been doing research and have determined a few different
       profile names that we believe are going to really help increase
       your visibility for high-intent jobs." Never a cold "would you be
       open to...". Paced by the normal nudge cadence; APPROVAL MODE for
       the first cohort.
   (c) Options on request: Monica quotes TOP candidates verbatim from
       marketing_gbp_suggestions — never composes names in-chat.
       RESTORATION-CATEGORY CLARIFICATIONS ride the same conversation:
       plumbing = always ask whether they're open to plumbing in the
       title AND whether they hold/can meet the licensing requirements
       (see LICENSE KNOWLEDGE below); service-term gaps (Dry Bros mold
       pattern) become natural questions — "are you planning to offer
       mold remediation?" — whose answers auto-write companies.services
       yes/no via the same clarify mechanic as the app buttons, which
       auto-stands or auto-dismisses the matching candidates.
   (d) NATURAL confirmation capture (no "reply YES" robotics — clients
       believe they are texting a human and must keep believing it):
       Monica names the exact string conversationally ("perfect, so we'll
       move forward with 'X'"), and the classifier accepts ANY natural
       affirmative tied to that specific candidate. On confirmation:
       suggestion status=chosen + rename_intent=rename + ops note QUOTING
       their words + FYI card. Then the existing machinery: DBA-filed
       capture (string-bound), citations gate, citations-before-GBP,
       never-auto-push.
   (e) Guards: chosen only ever written off a client confirmation tied to
       one exact string; no GBP edit from this lane; hands-off + franchise
       clients excluded.
   LICENSE KNOWLEDGE (plumbing-in-the-name): the NAME is advertising. In
   strict-license states (CA BPC 7027.1 class advertising rules, IL
   Plumbing License Law, WA specialty registration), advertising plumbing
   requires the ADVERTISER to hold the license — subcontracting to a
   licensed plumber generally does NOT cure the advertising violation.
   Safe structures: their own license; a licensed-partner arrangement
   where the partner's license number is displayed; or the sibling-entity
   play (the plumbing entity holds the license and its own profile). Not
   legal advice — confirm with the client's state board per case.
   CORE SHIPPED 2026-09-12 PM (scripts/client_concierge.py): RENAME_TRUTH
   knowledge block; `rename-pitch --company CO-… [--send]` CLI opens the
   conversation (Santino's preframe verbatim, quiet-hours + canary +
   outbound-guard gated) and arms per-company rename_convo state;
   handle_rename_reply consumes replies ahead of the generic flow
   (after booking, returns False on off-topic so normal Monica answers):
   interest -> deterministic options text (candidates QUOTED VERBATIM
   from marketing_gbp_suggestions, plumbing option always paired with
   the license question on restoration vertical only, service-gap
   clarify lines for mold/sewage/etc.); natural confirmation (never
   "reply YES") -> string-bound write: suggestion status=chosen +
   integration_settings.rename_intent.decision=rename + ops note
   QUOTING the client's words + ping; no exact candidate match = no
   write, Monica re-asks. Decline -> rename_intent=keep (citations
   unblock). Service/license answers write companies.services or
   dismiss candidates (same clarify mechanic as the app buttons).
   "DBA is filed" claims NEVER auto-mark: Monica asks for a photo of
   the paperwork + pings a human to verify and tick the Citations card.
   Smoke-tested 4 conversation rounds against live Dry Bros data.
   REMAINING: (a) DBA document intake, see item 2b below; (b) fleet
   rollout after the pilot (seed the ask into the ledger cadence);
   (c) knowledge block into the generic REPLY prompt if clients raise
   renames outside an armed conversation (today that escalates, fine).
   PILOT (Santino 2026-09-12): DRY BROS first — Monica runs the whole
   conversation with Amin in approval mode (candidates already seeded,
   mold confirmed as a service, plumbing gated on the license question).
   On his confirmed string: DBA guidance -> DBA-filed capture ->
   citations (item 2's tester order) -> GBP created under the final name.
   CHAINS WITH #2: decision -> DBA -> auto citation order -> GBP change.

2. **BrightLocal CB pipeline remainder**
   Done already: opening-hours fix (all 21 locations healed), rename gate
   on orders (string-bound DBA mark). REMAINING: (a) poll
   citations_submission_status into citation_listings so the app's
   Citations board shows CB progress per directory; (b) auto setup+order
   at client launch (gated on the rename gate); (c) TESTER = Dry Bros,
   blocked only on Amin's DBA string (mold now confirmed as a service);
   TRG's paid cb25 sits on_hold and resumes after their name decision
   (flip the BL location business_name first if renaming).
   scripts/brightlocal.py has the whole recipe; ~422 credits remain.
   PILOT: Dry Bros — the citation order fires as the direct output of the
   item-1 Monica conversation the moment Amin's string is confirmed +
   DBA marked filed.

2b. DBA DOCUMENT INTAKE (Santino 2026-09-12, NEW). CORE SHIPPED same
   night: _verify_dba_document in client_concierge.py — a texted photo
   during the rename flow's awaiting_dba stage rides vision (DBA_EXTRACT_
   SYSTEM), the registered name is extracted character for character,
   and an exact normalized match against the CHOSEN candidate auto-
   writes rename_intent.dba_filed + dba_name + dba_filed_at +
   dba_verified=vision_auto (the exact shape brightlocal.rename_gate
   checks, so the citations gate clears with zero clicks) + a Monica
   confirmation text + FYI ping. Mismatch: escalation with both strings
   side by side, Monica asks the client to double check, gate stays
   shut. Unreadable doc or bare text claim: never auto-marks, human
   ping. Smoke-tested match + mismatch on synthetic IL certificates.
   NOTE the MMS media intake ALREADY files texted paperwork to
   branding/{cid}/docs/inbox/ (document class), so storage is covered.
   STORES: primary-GBP DBA lives in integration_settings.rename_intent
   (canonical: gate + Build board + Monica all read it). The Locations
   tab / Location Scout checklist.dba (company_locations, fields name/
   filed_at/doc_url) is the SEPARATE store for EXPANSION locations
   (Crew's Sioux City) — same concept, different fact, per the
   single-source law each DBA lives with its own location. Do NOT
   merge them; if the primary's DBA should display in the Locations
   tab later, render it read-only from rename_intent.
   COMPLETE 2026-09-13: all three remaining pieces shipped + deployed.
   (a) HUB TILE LIVE: red-bordered "DBA / Trade Name Certificate" tile
   on every client hub (workers/gbpphotos-proxy.js, deployed via the
   content-only API PUT that preserves bindings/secrets; verified
   rendering on Dry Bros' live hub). Uploads POST to /gbpphotos/{slug}
   ?cat=dba -> job-photos edge fn (deployed) -> branding/{cid}/docs/
   dba/. (b) SWEEP VERIFY: upload_event peels docs/dba/ arrivals off
   the generic thank-you and runs _verify_dba_upload (download ->
   vision extract -> _dba_apply); docs/dba/verified-* is the system-
   write prefix the sweep skips; dba_processed_paths dedupes; a
   SendBlocked text never kills the sweep (writes+pings still land).
   Email lane: _email_inline_vision fallback inside the same verifier.
   (c) DOC LINK: every verified filing stores a durable copy (texted
   lane re-uploads to docs/dba/verified-*.jpg; hub lane links the
   upload itself), dba_doc_url rides rename_intent, and the Profile
   Rename card shows "DBA filed <date>, verified · View filing
   document" under the chosen candidate. Storage lane smoke-tested end
   to end on a synthetic IL certificate (match verdict, clickable doc
   URL in the ping). ONE ARCHITECTURE: texted, emailed and hub-
   uploaded filings all converge on _dba_apply.
   The rename flow ends
   with the client holding a state DBA filing; today the proof arrives as
   a texted photo or email attachment; the seamless version:
   - Client hub (restorationai.io/hub/{slug}/{token}, worker source in
     workers/): add a dedicated, visually loud (red-bordered) upload tile
     "DBA / Trade Name Certificate" so the client can drop the PDF/photo
     from the same link they already use for job photos.
   - Processor (works for hub uploads AND texted MMS AND email
     attachments, all three already land in our intake): vision-read the
     document, extract the registered trade name + state + filing date,
     store the doc under the client's docs/ (single source of truth).
   - Auto-verify: normalized compare of the extracted name against the
     CHOSEN candidate string. EXACT match -> auto-write rename_intent.
     dba_filed=true + dba_name=<extracted string> (same string-bound
     shape brightlocal.rename_gate checks) + FYI note; the citations
     gate then clears itself and item 2's order can fire. MISMATCH ->
     escalation ping with both strings side by side (client filed the
     wrong name = the exact failure the gate exists to catch).
   - Never auto-mark from a text CLAIM without the document; the doc is
     the trigger.

3. **All Pro homepage fixes (Angie, 09-11) — SHIPPED 2026-09-13 (tester
   run of the full feedback loop, all AI hands, zero humans)**
   DONE + LIVE on allproplumbingheatingandair.com, Angie replied-to on
   her thread with the link: real full-size Transit vans (AI scene +
   the REAL logo composited pixel-crisp with PIL after the model kept
   garbling "HEATING & AIR"; patch-paint the old logo area, then paste
   with drop shadow), no stripes/lines, dark ramp retinted navy so the
   page is red/white/blue with no black, hero text/CTAs left with vans
   center-right. BONUS ENTITY FIX found during audit: the live site
   carried 8 sameAs URLs belonging to THREE different same-name
   companies (Oceanside CA, Ontario CA, St. George UT "All Pro
   Plumbing") — purged from brand.ts, nap_audit rows marked
   wrong_entity so the nightly sync can't re-add them. FOLLOW-UP for
   the audit guard: same-name-different-city collisions need a city
   check in citations_audit (this class of wrong-entity sameAs may
   exist on other clients — sweep worth running).
   ORIGINAL ITEM (for context):
   The SYSTEM gap that let her emailed list sit is FIXED 09-12: emailed
   change requests now dispatch through feedback_router exactly like
   texts (email_intake routes client_feedback; her email had arrived
   before the getrest inbox was even polled). STILL OWED, the actual
   fixes on sites/all-pro-plumbing: new van/fleet hero images (current
   ones read as wind-up toys; regenerate per image-style-guide with the
   real logo), remove the red+blue lines, palette red/white/blue only (no
   black), phone + estimate CTA left (check the now-unconditional hero
   grid first — may already be solved). Then reply on her getrest email
   thread with the preview link.

3b. **Feedback closed loop: implemented -> tell the client (09-13)**
   Today: client change requests route to the build lane automatically
   (SMS + email), an AI agent implements them, work_log records it — but
   NOTHING automatically tells the client their revisions are live. The
   loop Santino wants: request captured -> implemented when the build
   runs -> Monica replies on the SAME thread ("those changes are in,
   here's the preview, let us know if anything else") -> their reply
   routes as fresh feedback. BUILD: when a routed feedback item's work
   completes (work_log row referencing the feedback), queue a Monica
   reply on the originating thread (email or SMS), gated by the outbound
   guard's done-claim evidence rule (the work_log row IS the evidence).
   No humans anywhere in this loop.

4. **NaRestCo flood/storm/biohazard/crime-scene off-page sprint**
   Pages all exist (verified); the gap is off-page: (a) add those
   services to the GBP + audit categories (gbp.py, write access live);
   (b) internal links from home/services hub; (c) add the terms to
   clients/narestco/geogrid-keywords.txt; (d) Yelp overhaul (top manual
   item — emergency-intent AI answers pull Yelp+GBP feeds); (e) seed
   terms into GBP review REPLIES. LAWS: no review campaigns ever;
   don't double-post GBP (client runs a third-party poster).
   4a SHIPPED 2026-09-13 PM: client_analyzer.py emit_gameplan() — on
   each client's FIRST analyzer run of the month (weekly Sunday cron) an
   LLM pass turns the analysis into a Game Plan: one narrative row
   (action_type=gameplan, action_key gameplan-YYYY-MM) + 3-6 step rows
   (gameplan_step, assigned_system auto-system|manual, sanitized enums,
   uniform bulk keys — PostgREST rejects mixed-key batches, and insert
   failures now RAISE instead of printing false success). --gameplan
   forces a regeneration. APP (MarketingActionPlan.tsx, deployed): Game
   Plan narrative card atop the Action Plan tab; steps flow into the
   existing waiting/automatic sections; ADMIN-ONLY auto/manual badges +
   a green "Completed" button on manual rows (auto rows only complete
   from evidence, never clicks); clients see uniform task language.
   PILOT PROOF: narestco's September plan generated from live data
   independently converged on the manual audit's five steps (GBP
   services p4, geo-grid expansion p5, citations p3, review-reply
   seeding + Yelp audit p6 manual) plus two data-found wins (Tacoma
   wrong-page fix, 8 striking-distance queries); the internal-links
   step seeded alongside (p2, site).
   4b REMAINING (the execution sprint): actually run the narestco
   steps — mechanical ones (GBP services/categories via gbp.py,
   internal links in sites/narestco, geogrid-keywords.txt additions)
   auto-complete their rows via work_log; manual ones (Yelp overhaul,
   review-reply seeding) get done and marked by hand. Auto-dispatch
   wiring (step row -> build-lane task) is the follow-on build.
   AUTO-DISPATCH SPLIT (Santino 2026-09-13): findings divide in two.
   MECHANICAL ones (internal links between existing pages, geogrid
   keyword additions, GBP service/category adds) should not just appear
   as rows — they should DISPATCH to the build lane automatically the
   way feedback_router dispatches client requests, and the row shows
   "queued/done". JUDGED ones (Yelp overhaul, content strategy, anything
   client-visible in tone) stay as visible rows a human/agent picks up
   deliberately. The Action Plan tab then reads as a live system, not a
   to-do list.

5. **Railway git checkout**
   The app's "Push site to production" button dispatches site_push_main
   to the Railway worker — but /app has NO git clone, so the job cannot
   actually work. Bake a monorepo clone + GitHub PAT into the Railway
   image, make site_push_main checkout -> sync-deploy, and add the agency
   GSC token + googleapiclient while in there. Payoff: launches (deploy,
   cutover stamps, GSC registration) run entirely from the app with zero
   dependence on Santino's Mac being awake.

6. **Missed-opportunity / callback alerts**
   call_intel.py already transcribes every tracked call (Whisper
   dual-channel) and labels outcomes INCLUDING missed_opportunity and
   callback_needed into marketing_tracked_calls.analysis — today nothing
   surfaces them, so a client can miss a job and never know. BUILD:
   (a) near-real-time alert to the client when a call is labeled
   missed/callback — SENDER RULE (Santino 2026-09-12): these send from
   the CLIENT'S OWN toll-free approved number (their SMS-campaign sender
   in company_phone_setup / their Twilio subaccount), NEVER our concierge
   or company numbers; (b) fold outcome counts into the monthly report
   (client_report.py). Pure surfacing of data we already produce.

7. **Repiping default-on for plumbing plans**
   plan_site.py service selection should include repiping for every
   plumbing-vertical client by default (template already carries the
   service; high-margin line every plumber does). Small change.

8. **Yelp-listing tracking numbers**
   Tim/Icatch confirmed the pattern: Yelp's own rep can backend-code a
   tracking number onto the listing so the PUBLIC NAP stays consistent
   (normally a tracking number on Yelp would break NAP — this is the one
   sanctioned way). Each client already owns a provisioned "yelp"
   tracking number in integration_settings.call_tracking, currently
   unused. Work = per-client requests through the Yelp rep; RT Olson
   first (his Yelp Biz access is handy). External-dependency item, not
   code.

REMOVED 2026-09-12 (Santino): fleet-attribution follow-up emails (watch
continues informally), Tony/Coastal linktree, DISS launch, Xtreme Clean
(client inactive — tracking question moot, numbers already released).

## Standing watches

- **DryCor preview send** — one-shot launchd job
  io.restorationai.drycor-preview-send fires Sat 9/12 9:32am PT (12:32pm
  ET, their morning), runs `client_concierge.py compose --company
  CO-1788205391336 --send`, logs to /tmp/drycor-preview-send.log, then
  deletes itself. Dry-run verified: SMS to Ashley Showalter with
  https://staging.rankai-drycor-restore.pages.dev. AFTER it fires: confirm
  in the log + GHL thread. Site state being previewed: 26 city pages, 234
  cross pages, charcoal canvas (#16181d, Santino's pick over the brand-kit
  petrol), red CTAs #e4002b, brand-kit orange as micro-accent, curated
  horizontal logo, no hero form (restoration = call-first).
- **RGP/Chesney (DryCor LSA handover)** — Carrie (carrie.price@drycor.com)
  asked us to take over LSA from Restoration Growth Partners; Robert told
  RGP "pause the leads" so DryCor's lead flow is STOPPED (time-sensitive).
  Facts: our MCC (201-884-4125) is already linked to LSA CID 816-134-6241
  BUT that account has ZERO leads all-time = a shell under the legal name
  "Showalter Construction & Restoration LLC"; RGP's real lead-carrying
  account is a different, unknown CID. Google is also warning the shell
  has no matching GBP — NEVER click "Create profile" (would duplicate
  their real GBP). Correction email sent 09-11: access must go to
  contact@restorationai.io (Chesney was about to send it to the TYPO
  domain contact@getresorationai.com from Carrie's original email). Watch
  the "DRYCOR Restore & RGP: Main Thread" (getrest inbox) for: the real
  CID, admin access grant, billing profile answer (if it bills RGP's card,
  move billing to DryCor before unpausing), verifications kept intact.
- **PuroClean day-7 search-term review (2026-09-15)** — campaign
  "PuroClean ELV - Biohazard Division" (id 24234476311, Ads CID
  1813437945). CRITICAL context: bids were broken from launch (all
  keywords unset -> $0.01 effective; found+fixed 09-12), so 9/15 is the
  FIRST window with real data. Current: Biohazard+Trauma $50 keyword caps,
  Crime Scene $30, budget $60/day, 10 job-seeker negatives added. Decide
  then: competitor-brand terms (bio one / 911 bio clean / aftermath
  cleaning) — negative them only on clicks-without-calls evidence. Journal:
  clients/puroclean-east-las-vegas/ads-journal.md (read before touching,
  append after). google-ads lib is NOT installed locally — use REST v25
  (narestco token + login-customer-id MCC works; see journal 09-12 entry).
- **Patti Collins follow-up (Thu 9/17 9:00am PT, CONFIRMED)** — AFC
  Cleaning and Restoration, Kansas City (GHL XRllC1w6ebN99NH563f2,
  pcollins@afcclean.com). Sales prospect from Levi's lane; recording
  fathom.video/calls/820426516. Deal shape quoted: $1,497 site build +
  $1,997/mo; they want to replace PPC+RealWorks with one provider, GBP/DBA
  multi-location strategy for KC metro, review program. Their internal
  steps before Thursday: RealWorks cancellation review (Tuesday), customer
  list export. Ours: proposal + GBP naming/DBA outline + mobile-first site
  examples + LSA competitive snapshot.
- **DIS toll-free verification** — +18448757718 rejected (business
  registration/EIN 20-2720165 flagged); EIN-CONFIRM ask is in Monica's
  flow; resubmit chain is automatic once the client confirms the correct
  EIN/legal name.
- **Kyle/Crew Sioux City GBP** — waiting on the Iowa state filing doc
  (Tonya digging); when it lands, create the second profile with Kyle as
  OWNER (not manager) and name it keyworded AT CREATION (see
  marketing_gbp_suggestions note for crew).
- **Amin / Dry Bros** — TWO open items from 09-10: Twilio TF verification
  rejected (+18336817307), and his G-Suite question WAS answered 09-10 3:38pm ("Yes, can you create that please?") — now WAITING on Amin to confirm info@drybros.com exists, then resubmit the TF (rejection code 3048) with the branded email. Site is pre-staging; DNI fills at first deploy.
- **Angie/All Pro** — preview link owed when queue item 3 lands (her
  thread lives in the getrest inbox).
- **Mac Mini runs** — the Mini is the browser-agent box (git-synced inbox:
  docs/MINI-OPERATOR.md -> mini-inbox.md -> mini-reports/). The LOCAL
  duplicate browser-agent sweep on Santino's Mac was disabled 09-12
  (~/Library/LaunchAgents/io.rankai.browser-agent-sweep.plist.disabled).
- **Frontline** — Monica's site-live announcement + EIN-CONFIRM ask ride
  her normal runs; the TF resubmit chain is automatic once the client
  replies. Site launched 09-10 on frontlinefireflood.com (26 cities).
- **Email intake (both mailboxes)** — as of 09-11 email_intake polls BOTH
  contact@restorationai.io AND contact@getrestorationai.com and Monica
  replies FROM whichever address the client wrote to; the 2-day stale
  backstop covers both. The local 5-min launchd poller is NOT loaded —
  replies ride the CI schedule (weekday concierge runs + daily ops sync),
  so weekend/inter-run email replies lag unless run manually.

## Recently shipped (context)

- 2026-09-11 day: HomeLyft launched app-native + GSC; TDI www live with
  entity rename to TDI USA, mitigation suppressed sitewide (SERVPRO
  conflict, central suppressedServices.ts), Manteca footer NAP; Frontline
  tier-2 territory build (9 -> 26 cities) + hub lists full 164-city
  5-county territory; bootstrap now seeds site cities FROM wizard
  service_areas (top 15-20 + expansion tiers recorded) instead of AI
  guessing; Kyle/Crew Sioux City GBP thread answered (DBA confirm +
  signage); QCI second-entity roadmap sent (QCI Restoration + triple-stack
  name option, qcirestoration.com)

- Source-attribution suite fleet-wide: 9 numbers/client (196 verified
  routes), DNI edge maps, form attribution, per-submission Website Leads,
  channel-filtered Calls tab
- Call intelligence: Whisper diarized transcripts (dual-channel split) +
  Haiku analysis on every recorded call, receptionist-style drawer, CSV
  exports, unified outcome column
- provision-all standard in onboarding; template-sourced DNI block
- Tollfree EIN rejections route to Monica (ask/confirm -> capture ->
  auto-resubmit with ladder reset)
- Monica: vision credential capture; apex-live probe self-healing;
  cutover panel provision-only job; Frontline launched end-to-end
