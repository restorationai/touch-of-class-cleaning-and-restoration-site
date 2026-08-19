# Standing Build Queue (pre-dates the SEO-videos queue)

The maintained queue as of 2026-08-18, before the SEO gap-analysis items took the
foreground. Executed one item at a time on Santino's "go" / "begin X". The SEO queue
lives in docs/seo-videos-gap-analysis-2026-08.md; current position in docs/WORKING-STATE.md.

## Build items

1. **MMS ingest gap** — texted photos that never auto-file into client storage (the Jack
   case: doc-context MMS routing); close the hole.
2. **Crew's image bucket** — never provisioned at onboarding; images.crew3r.com NXDOMAIN.
3. **Imagery as a standard build step** — partially DONE 08-18/19: site-build workflow now
   runs gen_site_images natively; photo_harvest apply re-applies when files are missing.
   Remaining: stage-check that fails a build with no images; CLIENT DIRECTION block from
   real photos before generating; auto-redact text/phone from livery references.
4. **Billing-alert escalation** — vendor "payment failed/suspended" emails ping Santino
   same-hour (pending his yes; born from the Twilio suspension).
5. **Scheduler heartbeat** — silence-watchdog checks the pg_cron pulse directly.
6. **SMS exact-cost billing** — Twilio true per-text prices onto invoices (no n8n).
7. **Reviews tab editor** — view/edit each client's four campaign messages in-app.
8. **Services as Products** — browser agent adds product tiles to GBPs (no API exists);
   supervised runs.
9. **Post-meeting recap messenger** — auto recaps after sales/kickoff calls.
10. **Citations record cleanup** — purge wrong-business audit entries.
11. **Self-hosted QR codes** — replace the api.qrserver.com dependency.
12. **Access verification pass** — verify client-claimed domain access before green chips
    (Life Savers "ns_live" is stale/wrong) + same-day GoDaddy invite-acceptance alerts.
13. **Intake auto-satisfy rule** — live branded site closes brand-kit intake questions
    (the Kyle case).
14. **Multi-location profile creator** — Sioux City listing (waits on Iowa DBA approval +
    Kyle's name decision; registry watcher runs nightly).
15. **Apple Maps runs 2 & 3** — verify the 3 in-review listings, create Crew (needs the
    57105-vs-57110 zip answer), watch the API-access decision email.
16. **Diagnosis agent** — parked by Santino's explicit call.
17. **App polish** — Today-tab filter, Ops Attention triage, LSA "Ready" persistence.

## Added during the Bobby Olson arc (08-18/19)

18. **Job Stories before/after photo fields** on the hub form (promised to Bobby).
19. **Bing/citations creation for post-08-09 clients** (RT Olson + Dry County missed by
    the nightly sweep — find out why, then run them).
20. **Repo lock** — local crons must not run git operations while a session is working
    (the orphaned-commits/merge-marker incident).
21. **Scaffold guard** — never overwrite rendered:true content files (long-standing
    NaRestCo gotcha, hit again on RT Olson).
22. **Plumbing template completion** — port proper render prompts (_system + archetype
    briefs) into templates/plumbing/ instead of restoration hand-me-downs.
23. **Review-photo truck composite** for Bobby (awaiting his selfie).

## Waiting on humans (as of 2026-08-19)

- Sarha (Air Care): reveal + WordPress NS flip (panel has the pair).
- Todd (Go Green): utility bill arrived path done; COI promised; then listing address
  update + appeal submission (combined text ready).
- Kyle (Crew): Iowa DBA approval (watcher), trade-name answer, Crew zip decision.
- Fran (QCI): reviewing preview with team; launch go = Hostmonster NS flip (creds held).
- Bobby (RT Olson/Dry County): GoDaddy NS flip, customer list, selfies, job stories,
  audit doc forward, real Dry County van photos.
- Jack: insurance certificate. Stuti: email for Crew contact card.
- Santino: BrightLocal yes/no; billing-alert escalation yes/no.
