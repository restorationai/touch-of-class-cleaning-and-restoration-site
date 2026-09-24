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
