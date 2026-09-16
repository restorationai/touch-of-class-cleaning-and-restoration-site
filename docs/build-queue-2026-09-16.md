# Build Queue — 2026-09-16

Saved from the citations/rename/PR working session (Santino + Claude,
night of 09-15 → 09-16). Attack order: A1+A2 first (hardens the three
live campaigns + every future rename), then C9–C11, then E18, with A3–A5
landing before Amin's citations go live.

## A. Citations & Rename program (highest leverage — 35 clients gated)
- [x] **A1. BL location enrichment sync** — logo + 3 photos (auto-normalized
      to BL spec: JPEG/PNG from webp, 10KB–5MB, ≥250px), description,
      services list, social links, contact fields pushed to every BL
      location BEFORE ordering; backfill Dry Bros + Frontline immediately.
- [x] **A2. Rename site-sync** — footer legal line ("[LLC] doing business
      as [DBA]"), schema legalName/name/alternateName, title metadata;
      runs at DBA-verification; Frontline first (live site, campaign live).
- [x] **A3. Aggregator submissions at order time** — Data Axle / Neustar /
      Foursquare add-on in every post-DBA order.
- [x] **A4. Phase 3c** — GBP verification auto-poll after renames execute
      (due before the first ready_for_rename prompt fires).
- [x] **A5. Rename press-release template** — "formerly known as" mode in
      press_release.py, published the same week as each GBP change.
- [ ] **A6. Dry Bros site cutover acceleration** — drybros.com (his old
      site) can't corroborate the DBA; our built site can, once live.

## B. PR vendors
- [ ] **B7. PRNow follow-up** — credits-per-package + guaranteed
      placements per tier; Santino eyeballs their sample report links.
- [ ] **B8. Comparison table** as the other six reply; EIN still pending.
- WATCH: 38D demoted (never use); PRNow reseller tiers on file
      ($0.90/$0.83/$0.76 per credit at 250/500/1,000).

## C. Forms (remaining)
- [x] **C9. Post-submit "Call Now" screen + consent checkbox + prospect
      SMS** (one form change; Bob asks).
- [x] **C10. Embeddable forms with source tags** (BDA landing pages).
- [x] **C11. Agency fallback SMS provisioning** (ESTIMATE_SMS_* on Pages)
      — the enabler for office SMS before a client's toll-free clears.
- [ ] **C12. Spam sentinel + nightly Pages env sweep.**
- [ ] **C13. Auto-reply to the lead.**

## D. DNI (remaining)
- [ ] **D14. Call-alert recipients list + held-alert visibility card.**
- [ ] **D15. Non-activated client provisioning sweep.**
- [ ] **D16. Number edit/release in-app; Bob's CallRail port kickoff.**
- [ ] **D17. Call-side gclid stamping** (paid-vs-organic referee).

## E. Cross-cutting
- [ ] **E18. GA4 auto-wiring** — Admin API key events + Ads link, fired
      on connect (kills the "mark conversions manually" work forever).
- [ ] **E19. Unified Leads view** (forms + calls, per-source).
- [ ] **E20. Subdomain self-serve card** (Site tab).

## Shipped 09-16 (overnight)
- C9: consent checkbox (unchecked default, recorded per submission) + post-submit Call-Now panel (uses the DNI-swapped number) + prospect confirmation SMS via shared sender ladder; E2E green on rtolsonplumbing.com
- C10: /embed/estimate iframe page (noindex, chrome-free) w/ ?source= channel tag; template + rt-olson; snippet ready for BDA
- C11: agency TF verification RESUBMITTED (EIN digits-only + restorationai.io/sms-consent + app consent microcopy) — IN_REVIEW; agency_tf_watch.py auto-sets ESTIMATE_SMS_* fleet-wide at approval
- A3: aggregators (Data Axle + Neustar + YP Network, SAB-supported; Foursquare/GPS are NOT) ride every citation order by default, 15cr each w/ ladder discount, itemized pre-charge; OPEN: retrofit for the 4 pre-A3 campaigns = BL-support question sent + ~43cr/campaign spend decision for Santino once they answer
- A4: phase 3c GBP verification poll live in rename_pipeline sync (live title vs chosen; auto-stamps verified)
- A5: press_release.py --kind rename ('formerly known as' lint-enforced, truth-gated); auto-drafts at ready_for_rename; Frontline rename-2026 draft SAVED to the app
- A6 partial: Dry Bros pushed to STAGING (56 pages, DBA surfaces included) — staging review -> main push -> apex cutover are Santino gates; domain situation (drybros.com host/registrar) still unmapped
- A1 enrichment SYSTEM: in-order + nightly + fleet backfill (28/28); GBP business description now the description source (2 -> 26 locations covered)
- A1 residue: BL image upload has NO API endpoint — question sent to BL support 09-16
- A2 rename site-sync SYSTEM: footer 'doing business as' line + schema DBA-as-name (old names preserved as alternateName); rename_site_sync.py sweeps behind DBA vision-verify, rides client-ops-sync, self-deploys live sites; Frontline LIVE-verified on frontlinefireflood.com, Dry Bros source-synced (A6 cutover carries it)

## Shipped 09-15 (for the record)
Self-serve tracking numbers (fn + card + 10/$2 pricing + wallet billing) ·
rename pipeline phases 1/2/3a/3b (board tab live, 33 staged) · Lead
Notifications recipients card · office SMS via own TF · notify_status per
lead + delivery dots · Send Test Lead button (verified E2E on RT Olson) ·
call_alerts CI actually working (first real alert sent) · 4 anti-double-
send mechanisms · citations menu backfill (44 clients) · hub DBA tile fix ·
team-photo never-overwrite + Review Request Photo relabel.

## Open BL tickets
- 999576 (Dry Bros) hold release — DBA evidence supplied.
- 43-credit discrepancy (~$103): 128 debited vs 85 itemized.
