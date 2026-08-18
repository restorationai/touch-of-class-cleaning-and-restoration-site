# Bobby Olson Call — Investigate/Fix Plan (2026-08-18)

Source: Fathom call 789244711 ("Bobby Olson - 20 Water Damage Jobs Guarantee"), recorded 2026-08-18.
Two companies, one owner: RT Olson Plumbing, Heating & Air (priority) + Dry County Restoration.
Follow-up call booked: next Tuesday, same time. Site promised DONE by Friday, live before Tuesday.

## A. Bugs Bobby hit live on the call (fix first, on-call promises)

1. **Client Hub photo uploads vanish** (both companies)
   - Jenny's Dry County uploads invisible; Bobby's uploads "didn't go through"; no way to
     see what's uploaded already (duplicate fear; CompanyCam = 70 photos/job incoming).
   - Investigate: did uploads land in branding/{cid}/job-photos at all? Test both upload
     links end to end. App Photos tab shows GBP media only, never hub uploads.
   - Fix: upload path if broken + an "already uploaded" gallery in the hub/app.
2. **RT Olson: "no business profile selected" on Connect + empty Map Rankings**
   - Promised fixed within 8-12 hours ON THE CALL. Likely cause: Bob's Google connection
     lives on Dry County only; RT Olson company row has no GBP link, so geo-grid never ran.
   - Fix: link GBP (place_id already in client record), seed plumbing geo-grid keywords
     (drain cleaning, water heater repair/replacement, leak detection, plumber corona),
     run baseline scan.
3. **Citations "not populating" in the app**
   - Told Bobby: display bug, Bing Places already created. VERIFY both claims for both
     companies; fix the app display.
4. **Communication gap: only Dry County links ever reached him**
   - Root cause known: 8-night gitlink loop meant RT Olson never hit preview_ready, so
     Monica never offered the preview; no watchdog catches "always looks fresh" loops.
   - Fix: Monica sends RT Olson preview today (after the 60-min human quiet window) +
     check two-companies-one-owner doesn't confuse enrollment or double-text him.

## B. Promised on the call, with deadlines

5. **RT Olson site done by Friday, live before next Tuesday**
   - DONE already: 124 pages rendered, hero lead form live on staging, redirect map for
     all 183 old URLs, Pages env vars set.
   - Remaining: 2 content-review flags (Santa Ana lead-paint line; slab-leak blog
     insurance wording), production push, cutover readiness for rtolsonplumbing.com
     (registrar/NS access unconfirmed).
6. **Findings report to Bobby** — written report of what we find in A.1-A.3. Draft after
   diagnosis; Monica delivers.
7. **Plumbing vs HVAC split recommendation (before Friday)**
   - Other agency proposes separate rtohvac.com + plumbing-only main site; called our
     city pages "old-school SEO". Bobby emailed their audit to contact@ — retrieve it.
   - Our new site includes ac-repair/furnace-repair/indoor-air-quality pages, which
     conflicts with a plumbing-only architecture. Decision needed before production.
   - Include: GBP name idea ("RT Olson Plumbers" DBA) with honest suspension-risk
     assessment (we are living that risk with Todd/Go Green right now).
   - Facts from call: separate technicians, separate entity/partnership, separate bank
     accounts on HVAC; Facebook page + GBP are shared; his HVAC Facebook ads do 9.5x
     ROAS; Google Ads plumbing $6k -> 24 conversions (landing-page problem).
8. **Before/after photos on Job Stories** — promised "up and running soon". Hub form gets
   add-before-photos / add-after-photos fields; feeds site case-study pages + GBP posts.
9. **Sister-company cross-links** (Dry County on plumbing site's water-adjacent pages).
   - Plumbing template supports brand.sister_company already. Blocked on: Dry County has
     NO domain on file (record domain: None) — resolve his domain question first.
10. **Review-photo truck edit** — his selfie with Tim + branded work truck composited
    behind (one per company) for the review-campaign contact photo.

## C. Waiting on Bobby (Monica tracks as intake items)

11. Customer list upload (review campaign; verify his review-filter toggle persisted;
    verify RT Olson has a provisioned review sender — most fleet TFs never submitted).
12. Review selfies (both companies); job stories from Jenny; the other agency's audit doc
    (already emailed to contact@ — retrieve).

## D. From our own analysis

13. **Keyword report he explicitly asked for**: Corona plumbing keyword research vs
    One Stop Plumbers / Option One; feed geo-grid + missing pages (slab-leak candidate).
14. **LSA audit**: he never appears in LSA rotation; competitors at 1.8k reviews.
15. **Jenny as contact**: add to integration_settings.contacts + portal account
    (day-to-day operator for Dry County mitigation content).
16. **Meta ads opportunity**: asked point-blank if we run Facebook ads (9.5x ROAS there
    with another vendor). Revenue conversation, not a fix.

## Status (2026-08-18, same day)

- A.1 DIAGNOSED: uploads WORK and always did — Bobby's 08-09 batch (incl. the van hero
  photo), Jenny's team photo (08-13) and an 08-18 job photo are all in the bucket. The gap
  is DISPLAY ONLY: the app Photos tab shows GBP media, never hub uploads. Fix queued:
  uploaded-photos gallery (app/hub build). Nothing lost, no re-uploads needed.
- A.2 SPLIT FINDING: both companies are fully Google-connected WITH locations selected
  (tokens + selected_location_id present since 08-08) — the call's "no business profile
  selected" was a UI false negative we could not reproduce server-side; re-check in the app.
  The REAL gap was geo-grid never configured: now applied (8 plumbing keywords x Corona,
  Riverside, Norco, Chino, Ontario) and the baseline scan is running.
- A.3 VERIFIED HONESTLY: Bing/citations were NEVER created for either company (only 2
  homeguide actions for Dry County exist). The app display is truthful. Creation queued for
  both via the browser-agent citation playbooks; also investigate why the nightly sweep
  skipped clients onboarded after 08-09.
- B.5 PROVISIONED: Cloudflare zone created for rtolsonplumbing.com. NS pair to set at
  GoDaddy: amos.ns.cloudflare.com + anastasia.ns.cloudflare.com. No MX on the domain =
  email-safe flip (his email lives on rtoplumbing.com). We hold NO GoDaddy access — the ask
  is with Bobby (Monica directive filed).
- B.6 DONE: report filed as a [FROM SANTINO] directive (note 89b734d8) — Monica emails
  Bobby the preview + findings + NS ask during his business hours.
- B.7 DRAFTED: docs/rt-olson-hvac-split-memo-2026-08.md (one organic site + one GBP,
  ads-only domain fine, no 16-page shrink, GBP name change parked). Audit doc itself went
  to the getrestorationai.com inbox — Santino to forward to contact@ for verification.
- Queued builds added: hub/app uploaded-photos gallery; before/after fields on Job Stories;
  Bing/citations run for both companies; review-photo truck composite (awaiting selfie).

## Suggested order

Tonight: A.2 (hard 8-12h promise) -> A.1 -> A.3, then draft B.6 report.
Tomorrow AM (his time): Monica sends RT Olson preview + report (A.4/B.6).
Before Friday: B.7 HVAC-split memo (decision gates production), B.5 completion.
Normal queue: B.8, B.9, B.10, D.13-15.
