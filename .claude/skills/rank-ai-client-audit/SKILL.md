---
name: rank-ai-client-audit
description: >
  Day-one intelligence audit for a new Rank AI client — full online-presence
  analysis (site, GBP, rankings, citations, reviews, brand SERP, AI-answer
  test) whose findings land WHERE THE TEAM WORKS: the client's app account
  (marketing_action_plan + client_intake_items), an intel file in the repo,
  and a branded HTML/PDF report. Run this IMMEDIATELY when a new client signs
  up or is announced — before onboarding, before any build. Use when the user
  says "audit {client}", "new client {name}", "run the client audit",
  "rank-ai-client-audit", or a new signup appears with an empty action plan.
---

# Rank AI Client Audit

The rule this skill enforces: **an audit that lives in a chat thread is lost.**
Every finding must end up in one of three homes, and the app account is the
primary one — logging into a client's account must show everything we know,
everything that's broken, and every open question we're waiting on.

## Inputs

- Company name (required) and, when known: app `company_id` (CO-…), website
  URL, GBP share link / place_id, city/state, owner name + email.
- If the app account exists, read `companies` + `client_intake_items` first so
  questions aren't double-seeded.

## Phase 1 — Collect (DataForSEO + crawl)

Reference examples of the finished product:
`clients/firedex-butler/intel/audit-2026-07-08.md`,
`clients/restoration-groups/intel/audit-2026-07-09.md`,
`clients/aaa-water-damage/intel/audit-2026-07-09.md`.

1. **Site crawl** (if a site exists): platform, page count, last-touched
   signals, schema, titles, content architecture, NAP on site, licenses/certs
   claimed → these seed the claims truth table. Check the GBP website link
   actually points at THEIR site (we found one client whose lapsed domain was
   re-registered by a lead-gen competitor).
2. **GBP** via `business_data_business_listings_search`: primary category
   (the #1 local lever), services list, rating/count/distribution, photos,
   claimed status, place_id/cid.
3. **Rankings** via `serp_organic_live_advanced` from the client's city:
   4-6 money queries (water/flood/fire/mold + vertical-specific). Record local
   pack AND organic; name the winners and what they're doing.
4. **Citations/NAP**: Yelp, BBB, Angi, HomeAdvisor, Houzz, chambers — name
   variants, wrong cities/phones, wrong categories, unbacked badges.
5. **Backlinks** via `backlinks_summary`.
6. **Brand SERP + collisions**: search the bare brand name — namesakes,
   manufacturers, bad-review doppelgangers.
7. **AI-answer test** via `ai_optimization_llm_response` (web search on):
   emergency question from their city ("my basement just flooded in {city},
   who should I call?"). Record who the AI names and what it cites — this is
   both strategy and the strongest sales/retention artifact we produce.

## Phase 2 — Write (all three homes, same session)

1. **Intel file**: `clients/{slug}/intel/audit-{date}.md` — identity, GBP,
   rankings table, citations, collisions, AI test, claims truth table,
   scorecard (website/GBP/reviews/rankings/citations/AI/authority/upside),
   onboarding sequence, intake questions. Commit with the next monorepo commit.
2. **App action plan** — `marketing_action_plan` rows via service role
   (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from rank-ai/.env, curl not
   urllib). Conventions:
   - `action_key` = first 16 hex of sha256("onb:{company_id}:{title}") —
     check existing keys first and skip duplicates (NO on_conflict param;
     the column has no unique constraint).
   - Open questions for the client → `action_type: 'client_input'`, titled
     "ASK:"/"CONFIRM:", pinned when blocking.
   - Findings → typed rows (`gbp_fix`, `entity_fix`, `ai_citation_fix`,
     `nap_fix`, `site_build`, `site_launch`, `review_campaign`, `tracking`,
     `compliance`, `positioning`…), priority = execution order, impact/effort
     high|medium|low, `assigned_system` s1–s5 or manual, `status: 'planned'`,
     `rank_ai_slug` set.
   - 8–12 rows; every one has a `rationale` written for Santino-in-a-hurry:
     the finding, the evidence, why it matters.
3. **Intake questions** — `client_intake_items` for anything the client must
   answer (field_type text/yes_no/select/checklist, `blocks` when it gates
   site_build/review_campaign, `source: 'rank-ai'`). Skip questions already
   seeded. ALWAYS seed one item per social platform separately (Facebook link,
   Instagram link — never one combined "social links" ask), and ALWAYS seed
   the authority-links input "What is your IICRC firm/certification number?".
   DO NOT seed an equipment-supplier question (Santino 2026-08-08: "I actually
   want to stop sending the message of asking what equipment they use. It's not
   necessary."). The dealer-locator backlink is still worth chasing in 3b, but
   we research the supplier ourselves rather than making the owner do it.
3b. **Authority-links sprint row** — every audit seeds ONE
   `marketing_action_plan` row (action_type `authority_links`, effort low,
   impact high): get the client listed on the IICRC firm locator, their
   equipment suppliers' dealer locators (Dri-Eaz/Phoenix/etc. — draft the
   email, client forwards to their rep), and the local chamber of commerce.
   These are the cheapest high-relevance backlinks a restoration company can
   get; the intake answers above feed this row.
4. **Branded report** — HTML+PDF to `~/Desktop/Rank AI Reports/{Client}-Audit`
   using the report CSS pattern (purple #7c3aed accents, Rank AI header/footer;
   see the July 2026 reports for style). markdown→HTML, then headless chrome
   `--print-to-pdf`.

## Phase 3 — Report back

Distilled summary: the one urgent finding first, the verdict/scorecard, what's
blocked on the client (= the pinned client_input rows), recommended sequence.
If the client hasn't paid yet, add the 2-3 strongest closing points the data
supports.

## Notes

- Claims honesty: the truth table from Phase 1 is the ONLY source site copy
  may draw certifications/years/licenses from. Unverified = excluded.
- Companies without an app account yet: do phases 1, 2.1, 2.4; note that
  action-plan + intake seeding runs the moment the account exists.
- The gap this closes: signups used to sit with "No action plan yet" until
  pipeline onboarding. New signup → run this skill the same day.
