# Implementation Queue

STATUS 2026-09-24: Santino APPROVED sections 1, 2, 2b, 3, and 4 for build
("everything else sounds good"), with ONE exception: spam-shield
AI-dispatcher absorption is PARKED (do not build yet). Section 5 unchanged.

Living queue of approved-for-build items. Each entry: what, why (the incident),
and the shape of the fix. Check off + date when shipped. Santino curates
priority; agents work top-down unless told otherwise.

## 1. Build Pipeline GBP board  [SHIPPED 09-24: edge fn live; UI on branch gbp-board-health @ localhost:5173 awaiting Santino merge] — truthful stages + health visibility
- [x] (2026-09-24) **Fix the 1,000-row truncation** in the build-stages edge function:
      2,285 open `marketing_gbp_suggestions` rows fleet-wide vs PostgREST's
      1,000-row cap — clients whose rows fall past the cap read as "0 open
      items" and float into "Listing optimized" (Arch: 20 open service items
      + score 62; Heritage: 24 open). Fix server-side: per-company aggregate
      counts (SQL group-by / RPC), never raw rows.
- [x] (2026-09-24) **GBP health chip on every board card**: ONE number (the worse of
      conversion/ranking sub-scores), color-banded — >=90 green "dialed",
      75-89 neutral, 60-74 amber "needs work", <60 red "needs attention".
      Click-through = Profile Health card with both sub-scores + components.
      Board shows one number for glanceability; detail lives one click in.
- [x] (2026-09-24) **Stage gate**: "Listing optimized" additionally requires health >= 75
      when an audit exists (no-audit-yet clients keep item-count-only gate).
      NOT a 100-only bar: always-red signals die; the optimizer's component
      model (photo counts, review velocity) makes 100 a moving target.
- [x] (2026-09-24) Kick fresh Heritage GBP sync + face audit (their 09-16 sync is thin:
      no rating/review_count captured; no face audit row at all).

## 2. Monica — attachments and action claims
- [x] (2026-09-24) **Widen the bodyless-attachment gate** (client_concierge ~11295):
      screenshots/documents/contact-cards that ingest fine currently still
      ping Santino "couldn't auto-file". Treat ANY successfully-filed kind as
      handled — synthesize a body from the vision tag so Monica answers it
      herself; escalate only when ingest genuinely failed.
- [x] (2026-09-24) **Email-endpoint attachments**: messages whose attachments ride the
      email endpoint (body AND attachments null in the SMS payload) show
      media zeros -> false "couldn't auto-file" pings (DISS 09-24). Fetch
      via the email endpoint before deciding.
- [x] (2026-09-24) **Execution-or-escalation contract**: Monica may not acknowledge an
      action request ("we're getting Chris added now") unless the same turn
      either (a) invokes a real tool that does it, or (b) files an ops task
      + says "passing this to Santino". Wire an allowlist of doable actions;
      everything else = (b). Incidents: Chris Pappas add (BCP/Scott 09-23,
      never executed), RX/Barbara opt-out 09-09.
- [x] (2026-09-24) **New tool: add secondary contact** (the Chris Pappas class): create
      contact on the account, mark as additional point of contact, add to
      concierge allowlist. Then actually add Chris Pappas (910-448-2930).
- [x] (2026-09-24) **Attachment-first resolution rule**: when a client sends photo proof
      contradicting a Monica claim, Monica must read the image BEFORE
      re-asserting (DISS/Addi 09-24; her screenshot was the site's own
      footer and she was right).

## 2b. Footer NAP template bug (DISS/Addi 09-24 — root cause of the above)
Footer.astro (BOTH templates) renders `{brand.streetAddress}` +
`{brand.primaryCity}, {brand.primaryState} {brand.postalCode}` — the street
paired with the MARKETING city, not the address city. Schema JSON-LD uses the
correct pair, so the visible footer and the structured data disagree on the
same page. Six live sites diverge; two cross-city, one cross-STATE:
  diss-restoration (Youngstown OH shown, Farrell PA real — impossible
  "Youngstown, OH 16121" line), flood-fixers (San Diego vs San Marcos),
  flood-solutions-inc (Macomb vs Ira), katofsky ("Pgh"), air-care +
  dry-bros (case-only).
- [x] (2026-09-24) Fix Footer in both templates: address block uses the ADDRESS pair
      (addressCity/state/zip); marketing city stays in the tagline line
      only. Re-scaffold + deploy the 6 affected sites (DISS first).
- [x] (2026-09-24) **NAP parity watchdog**: nightly check — rendered footer NAP vs
      schema PostalAddress vs GBP address; any pairing mismatch = pipeline
      alert. This is the guard that makes this class unmissable.
- [x] (2026-09-24) **Monica render-level verification tool**: before confirming any
      "does the site show X" claim, fetch the live page, extract the
      rendered NAP/target string, and quote what was actually verified.
      No tool result = no confirmation (falls to escalation contract).

## 3. Arch Environmental — profile rename
- [ ] DBA status: NOT filed as of 09-24. Santino asked Mike to file the
      revised string "Arch Environmental - Mold Testing, Asbestos Testing,
      Lead and Air Quality Testing" (drops "Group"); awaiting confirmation.
- [x] (2026-09-24) **Add INSERT RLS policy** on `marketing_gbp_suggestions`: table has
      SELECT + UPDATE policies only — NO insert policy exists, so the app's
      "Add" button RLS-fails for every user. Company-scoped WITH CHECK
      (company_id = get_effective_company_id()), item_type='name',
      source='manual', status='candidate' defaults via the app.
- [ ] Once Mike confirms the filing: update the chosen DB name row + sync
      docs/gbp-rename-candidates.md + the rank-ai-gbp-rename skill records
      (three-record law), then normal rename sequence (citations -> GBP).

## 4. Spam shield v2 (clients report "calls from Google", ~8/day at Arch)
Context: E1 (repeat-caller blocklist) works — 263 numbers blocked. E2
(first-time Nomorobo lookup) has blocked 0 of 476 lookups — add-on works but
scores rotating lead-farm numbers 0; wrong data source for this spam class.
Arch: 17 of last 25 GBP-line calls are short-duration spam-pattern.
- [x] (2026-09-24) **Lookup v2 upgrade**: line_type_intelligence + SHAKEN/STIR
      attestation; VOIP + attestation C on first contact -> risk pool.
- [x] (2026-09-24) **Prefix-velocity blocking**: 3+ spam-classified calls from one
      NPA-NXX within 7 days -> auto-block that prefix on GBP lines (allow
      known-customer numbers through by CRM match).
- [x] (2026-09-24) **Instant E1 feed**: verify call-intel spam verdicts land in the
      blocklist on the immediate post-call run (not just the 30-min cron).
- [ ] PARKED (Santino 09-24, do not build yet): **AI-dispatcher absorption**: clients with the AI receptionist —
      route first-time risk-pool callers to the AI line first; real
      customers get handled, farms hang up. NO keypress gates (law 08-10).
- [x] (2026-09-24) Seed the blocklist from Arch's current wave (classification pass over
      their last ~50 calls) so Mike feels the drop this week.

## 5. Carried from 09-23/24 sessions
- [ ] Remaining ~9 n8n dispatcher lanes still hardcode restorationai.io/s/
      short links (Post Call Analysis is fixed + verified; per-lane audit in
      WORKING-STATE.md). Supervised pass — live emergency dispatch lanes.
- [ ] Optional: API skips call-intel workflow_dispatch when a run is already
      queued (quiets the cancelled-run noise in Actions; no lost work today).
- [ ] HomeLyft Meet-the-Team section when Josiah sends headshots/bios.

## 6. Meeting analyzer — kickoff follow-up booked on the sales calendar
Incident (Daniel Restum / RestoPros of Central Maryland, 09-24): after the
KICKOFF call, fathom_sync booked the agreed follow-up on the Follow Up
(sales) calendar instead of LIVE Support. Root cause: fathom_sync matches
meetings to clients by SLUG (clients/*.json); RestoPros signed so recently
that bootstrap hadn't created their slug yet (their companies row appeared
16:19 UTC — mid-kickoff). Unmatched meeting -> handle_unmatched -> classified
as a sales PROSPECT -> prospect lane books on the Follow Up calendar by
design (Patti Collins lane, 09-11). A brand-new client is indistinguishable
from a prospect during the bootstrap race, and the kickoff call is exactly
when that race fires.
- [x] (2026-09-24) **Client-signal check before the prospect lane**: in handle_unmatched,
      before classifying as prospect: (a) if the meeting's appointment
      anchor is the Kick Off (or LIVE Support) calendar -> it IS a client;
      (b) else match invitee email/name against the companies table (an
      Active company row = client). Either hit -> book LIVE Support 30-min
      + raise "client meeting but bootstrap missing" alarm instead of the
      prospect flow.
- [x] (2026-09-24) Extend the bootstrap-missing alarm to the fathom lane (digest already
      flags slugless companies; the meeting path should too).
- [x] (2026-09-24) Cleanup: move Daniel's booked follow-up from the Follow Up calendar
      to LIVE Support (verify time + attendee unchanged).

## 7. Group chat for client outreach (queued 09-24, phased)
GHL now supports native Group Chat for SMS: up to 9 contacts, one true
thread, US/CA numbers, LONG-CODE senders only (toll-free cannot group-text;
Monica's 805 qualifies). Public API support for group threads is
UNDOCUMENTED — Phase 0 doubles as the API experiment. Monica's rails are
all contact-scoped (wrong-name guard, reply attribution, quiet-window,
send-locks, canary) so group support is a model change, phased:
- [ ] Phase 0: manual pilot — group thread in GHL UI for BCP Flood Pros
      (Santino + Scott + Chris), human-driven, Monica out. Inspect what
      the v2 API exposes for the thread (conversation shape, send path).
- [ ] Phase 1: Monica READ-ONLY — group messages ingest into company
      context; no group sends.
- [ ] Phase 2: Monica announce-only in groups (previews, completions):
      no personal greeting in groups; decisions/asks stay 1:1 with the
      preferred contact (group = visibility channel, 1:1 = decision
      channel). Per-client opt-in, never fleet default.

## 8. Board counts: KEEP-verdict noise  [SHIPPED 09-24: backfill done (2336->804 open), generator writes noted, board+edge on branch, KEEP button label fixed]
The pagination fix made counts COMPLETE and exposed a semantics bug: 1,532
of 2,336 open suggestion rows fleet-wide are verdict=KEEP — informational
audit records ("this service is correct"), not actions. They inflate the
board (RX badge "45" = 40 KEEP + 5 NEEDS-REVIEW; the Profile page correctly
shows only the 5) and pin every client in "Listing synced".
- [x] (09-24) Board gate + chip count only ACTIONABLE open rows (verdict != KEEP);
      relabel chip "N awaiting review" (they are not auto-apply — the
      auto-safe lane already applied its items; RX: 47 applied).
- [x] (09-24) Data hygiene: audit lanes write KEEP rows as status 'noted' (not
      'open'), + one-time backfill closing the 1,532 open KEEPs.

## 9. Profile Health score v2 — "100 means nothing left" (Santino 09-24)
Coastal case: health 100 while reviews=29, no keyworded name applied, and
5 actionable items open. The score today measures PROFILE COMPLETENESS
(hours/photos/description/services-parity/category); it ignores review
volume, the rename opportunity, and service breadth. Proposal:
- [ ] Review-volume component: tiered (e.g., <20 none, 20-49 partial,
      50+ full) — a thin review base caps the score below the >=90 gate;
      the review campaign is the lever that lifts it.
- [ ] Rename-opportunity component: no APPLIED keyworded name while the
      rename lane has candidates (incl. only-dismissed) = deduction. The
      name is the strongest ranking field (house law 09-10).
- [ ] Service-breadth component: scored against the vertical catalog +
      validated long-tail phrases — not a flat "100 services" bar.
- [ ] Effect: 100 becomes rare and earned; the >=90 optimized gate then
      means "genuinely nothing left that we know how to improve."

## 10. Monica reply conflation (Jim Salsbury 09-24)  [SHIPPED same day]
Monica pitched LSA; Jim replied "How much is it?" 20 seconds later; the
answer came back about the DBA filing fee (he had already FILED — receipt
photo on 09-21). Prior nets (reply_to outbox, already-answered) matched
messages, not TOPICS.
- [x] (09-24) REPLY BINDING in the composer: newest client message within
      15 min of our message + short/deictic -> hard-bound to THAT message's
      topic in the prompt; pronouns resolve against it only.
- [x] (09-24) scripts/reply_binding_audit.py: post-hoc Haiku judge over
      (our question -> short reply -> our answer) triples from the outbox;
      first live run found 2 more conflations (RT Olson, Heritage) — in
      the 4h watcher loop now.
- [x] (09-24) Jim corrected (LSA is pay-per-lead, no setup fee).
- [ ] Review the 2 new conflation hits' threads for needed corrections.

## 11. Housekeeping found 09-24
- [ ] mold-solutionz (DEAD client) still has a live google integration row
      and got face-audited at 100 — remove dead clients from audit
      enumeration + drop the stale integration row.

## 12. Cover photo set (Arch 09-24)  [core FIXED same day]
Three app attempts failed silently: Google requires EXACT 16:9 for COVER
(rejects 1080x1080 and even a 1.7792 crop), the square candidate slipped
past the landscape filter (media item had no dimensions), and the bytes
flow 400s "invalid or corrupt" for COVER on some accounts.
- [x] (09-24) set_cover_photo: googleusercontent sourceUrl + =w1280-h720-c
      crop directive (Google's CDN serves the exact ratio) as primary;
      exact-1280x720 PIL normalize for non-Google URLs. Arch cover LIVE,
      verified via re-audit (COVER:1, score 51.5 -> 60).
- [ ] App: the cover picker toasts success on job QUEUE, then silently
      shows "no cover" when the job fails. Poll marketing_jobs status
      after the 30s refetch and toast the job error on failure.
- [ ] Candidate filter: exclude media items with MISSING dimensions from
      cover candidates (they may be square/portrait), or trust the new
      crop directive and drop the landscape filter entirely.

## 13. Parity engine: site service images -> GBP photos (proposed 09-24)
Santino uploads site service images to client GBPs by hand today. Build it
into gbp-maintenance as a parity extension (page <-> service <-> photo):
- [ ] 30-day soak per image (git age of the asset + site out of active
      revision rounds) — Santino's "wait a month" gate, automated.
- [ ] Drip 3-4/client/month (freshness signal; never a bulk dump), only
      for services that exist on the GBP, category ADDITIONAL.
- [ ] Real-photos-first: skip the drip when the client's gbpphotos intake
      is producing real uploads; generated fills gaps, never displaces.
- [ ] sha1 provenance state (face-audit pattern) so nothing re-uploads;
      every upload logged to marketing_gbp_changes; per-client opt-out.
- [ ] Policy note: Google prefers photos representing the real business;
      drip + brand-matched realism keeps the profile consistent with the
      manual practice already in place.

## 14. Email intake: staff/team photo routing (Jaziel/RX 09-24)
Jaziel emailed 8 staff photos; intake ingested + ack'd + noted them but
filed ALL into branding/{cid}/docs/ where no team-photo consumer looks.
- [x] (09-24) The 8 copied to branding/CO-1784745317157/team/.
- [x] (09-24) Vision routing SHIPPED: emailed images are classified from
      the IMAGE (team_photo/job_photo/logo/document_scan), routed to
      team/, job-photos/inbox/, brand/, docs/; error fallback goes to
      job-photos/inbox (human-visible), never the docs shelf. Verified
      against Jaziel's actual photos: all -> team_photo.

## 15. Review sender policy evolution (Santino 09-24)
- [ ] Once the CRW A2P-local pilot completes (trust bundle -> brand ->
      campaign), consider flipping review-sender preference to A2P-verified
      LOCAL numbers where available (conversion play); toll-free approved
      stays the floor. sender_preflight already hard-gates activation on an
      approved sender — this only changes which approved sender wins.

## 16. Rename Intelligence v2 — priority ladder + brand compression + exact-phrase engineering (OUTLINED 2026-09-25, awaiting go)

Trigger: PuroClean LV autoseed led every option with mold (NV volume 480/mo beats water 320/mo; `rename_autoseed.py` sorts covered terms purely by volume — the unused `water_first` variable shows the intent existed but was never wired). Arch's good name ("Arch Environmental - Mold Testing, Asbestos Testing, Lead and Air Quality Testing") had to be hand-added; system kept "Group" and compacted to one "Testing".

Santino's doctrine (2 reference cases: PuroClean LV, Arch):
1. CATEGORY PRIORITY LADDER (restoration): 24/7 Emergency Plumbing (UNCONDITIONAL for restoration — Santino 09-25: always present as a suggestion, drop the autoseed HARD GATE language) → Water Damage Restoration → Fire Damage Restoration → then mold/others. Volume breaks ties INSIDE the ladder, never reorders it. Mold trails even when volume is higher.
2. BRAND COMPRESSION: trim non-identity words to buy characters — "Group", "LLC", "of", optionally narrow geo ("East Las Vegas"→"Las Vegas"). Reason field must list what was trimmed.
3. EXACT-PHRASE ENGINEERING: descriptors are complete search phrases; repeat the noun when budget allows ("Mold Testing, Asbestos Testing" beats "Mold, Asbestos ... Testing"). Maximize count of complete high-volume phrases within 90.
4. COVERAGE-FIRST: top option = max sold-lane coverage within 90 chars (also kills Send Pitch coverage-gap refusals at the source).
5. 90-char budget algorithm: compressed brand stem + ladder-ordered phrases until budget spent; emit full-coverage / plumbing+water / water+fire / conservative variants.

Touch points (all 3 synced records + seeder): scripts/rename_autoseed.py (composition rewrite), ~/.claude/skills/rank-ai-gbp-rename/SKILL.md (doctrine section), docs/gbp-rename-candidates.md (canonical record), optional: char counter on the app rename card.
Then: reseed PuroClean with the 4 Santino examples, he clicks Send Pitch, monitor end-to-end.

## 17. Topic Discipline Engine — thread topic ledger + agenda quarantine + departure gate (OUTLINED 2026-09-25, DO NOT BUILD YET)

Trigger: Air Care / Sarah Boyd 09-25 (3rd rename-agenda hijack: Jim Salsbury LSA->DBA fee, Air Care 09-14 verification->names, Air Care 09-25 LSA->DBA). Common shape: the RENAME agenda state (stage=pitched + pending options) is injected into every compose and seizes any ambiguous inbound. REPLY BINDING only covers short/deictic replies <=15min; Sarah's 26-word LSA follow-up sailed past it.

Strategy (gates, not prompting — prompting has failed 3x):
1. THREAD TOPIC LEDGER: per contact-thread, Haiku classifies last ~6 messages every turn -> {topic, client_initiated_turn, confidence} in ops_kv thread-topic:{contact_id}. (Santino's own spec: "go back and evaluate a few messages before to determine what the conversation is about.")
2. AGENDA QUARANTINE: program agendas (rename options, review asks, etc.) excluded from the compose context while a topic is live; eligible only when thread idle or topic explicitly closed, with an explicit "Separately, ..." transition.
3. TOPIC-DEPARTURE GATE (the enforcement): post-compose deterministic check — draft topic vs ledger topic; mismatch without explicit client invitation = block + recompose with hard constraint. Same class as canary/link/claim gates.
4. STAMP-AFTER-SEND: rename-convo last_outbound currently stamped PRE-gate (client_concierge.py ~10406) — Monica's blocked 21:08 message is recorded as said; Sarah never got it. Move stamp post-send-confirm. (Monica-never-claims-actions, internal-state edition.)
5. PER-CONTACT AWARENESS: program states record which contact_id saw them; never assume company-level context in a thread whose contact hasn't seen it. Also dedupe Sarah Boyd's two GHL contact rows.
6. WATCHER: extend reply_binding_audit into a topic-departure audit (retro-scan sends for topic switches without invitation).

Flagged same-day: Air Care rename agenda should be PAUSED regardless (trust shaky); Sarah owed a human recovery message + a precise LSA-timeline answer.
