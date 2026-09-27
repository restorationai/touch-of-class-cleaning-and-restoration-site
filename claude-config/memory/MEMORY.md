# Memory Index

- [BrightLocal API](brightlocal-api.md) — key LIVE 09-02 (x-api-key, /manage/v1); 500 CB credits confirmed; Listings data API path unknown (ask Harry)
- [Zero-Scan Guard](zero-scan-guard.md) — 09-02 DryCor incident: digest NO-MAP-DATA tripwire + heal fallbacks live; Davis Construction has NO findable GBP, Xtreme Clean has no NAP

- [Working State Doc](working-state-doc.md) — rank-ai/docs/WORKING-STATE.md = leave-and-resume doc (queue position, Bobby Olson state, open loops); read at session start, keep current

- [Single Source of Truth](single-source-of-truth.md) — LAW (09-04): one canonical store per fact, display anywhere; NEVER ask for data we hold (check docs/messages first — EIN pipeline is the template)
- [No Em Dashes](no-em-dashes.md) — LAW (08-05): never use em dashes anywhere in outbound writing; call clients by the name they use (Greg, not Gregory)
- [Verify From Outside The LAN](verify-from-outside-the-lan.md) — LAN intercepts port-53 (identical TTL from every server = the tell, use DoH + curl --resolve); domain-attached-after-scaffold leaves brand.ts https://None on LIVE sites (bit go-green + crew 08-09); launch-path rehydration guard unbuilt
- [Browser Agent Suite](browser-agent-suite.md) — Bing DONE (8/19) + FB harvest DONE + form_fill CURRENT; daytime launchd sweep 11:30am PT (moved 08-31 per Santino; was 21:30 nightly); policies: GBP-primary phones, OAuth=write, 3-supervised-runs rule; gbp-verified card (Go Green SUSPENDED pre-us)

- [Build Queue Jul 30](build-queue-jul30.md) — standing queue: Monthly Summaries tab, lead-audit crash-safety, Monica acks, BrightLocal, launch buttons, GBP range, QCI 8-city go; + human batch worksheet & Santino clicks

- [Setup Ledger / Overseer](setup-ledger-overseer.md) — LIVE 07-28: cross-client ledger + Ops Attention app view + notes→Monica + auto site-builds (cap 4/run) + freshness watchdog + short connect links + escalation ladder; Rank AI plan only; own-domain=launch-now; pending: call tracking, launch buttons, GSC/GBP analytics

- [Phone Activation Pipeline Broken](phone-activation-pipeline-broken.md) — REPAIRED 07-16, app fixes MERGED to main 07-21 (95f4d0d) + migration applied to prod; n8n workflow fixed in prod, Joe +18444930080 LIVE, both Trachawks reconnected
- [Checklist Jul 15](checklist-jul15.md) — Stripe invoice API-version bug FIXED+backfilled (39 rows); signup-alert SMS + gbp_set_cover LIVE; app branch MERGED; a11y+page-weight rollout: narestco 100/100 a11y/BP, 5.4MB->1.0MB, widget iframe lazy-loaded for ALL sites
- [Rank AI Sales Playbook](rank-ai-sales-playbook.md) — 10-phase call script built 2026-07-13 from Born-to-Close video + Fathom calls; recordings live in FATHOM (Notion just indexes links); fix list: gap math, decision-maker Q, one canonical trial policy
- [Crew Hub](crew-hub.md) — LIVE: /hub/{slug}/{token} on-phone review QR + request-a-review (parked) + upload links; tokens via upload_links_sync.py; worker source in repo workers/
- [Client Concierge](client-concierge.md) — Monica HEADLESS on GitHub Actions 07-30 (2x weekday cron + morning digest email); 08-03: Railway ops-worker now workflow_dispatches the 16:07/19:37 slots (GitHub cron drops runs; dedupe via runs-API), confirmed services AUTO-APPLY to GBP+page queue (categories still one-click), domain-access asks seed at rank 1, DND SMS→email fallback, /concierge-preview + app "Preview next message" button; SENDER REVERSED 08-07: Monica sends ONLY from +18053293449 (the 805), toll-free is no longer a sender; 08-18: 60-min human quiet window on EVERY send (GHL userId = human signal; send_now exempt) + Monica NEVER says "Santino will call you", only "I'll pass this along to Santino" (Tony Mendez case)

- [TRG Strategy Jul 15](trg-strategy-jul15.md) — LIVE on therestorationgroup.com 07-22 (940pg, 301 map, email-safe cutover); vendor-stop + Google reconnect open; license 13VH05488600; one-site strategy
- [All Pro + ProRestoration Site State](allpro-prorestoration-site-state.md) — All Pro LIVE on real domain 07-22 (email-safe NS cutover); ProRestoration still preview; Angie = preferred contact; owner = Jack Bispo
- [New-Client Sites July 2026](new-client-sites-jul-2026.md) — MCC/FireDEX/AAA previews ALL LIVE; AAA red-brand revamp w/ real photos done; open: AAA domain+phone questions, 60-min claim decision, MCC domain confirm
- [TDI Builders Onboarding](tdi-builders-onboarding.md) — signed 08-23: Sacramento+Manteca, migrate buildwithtdi.com (Scorpion)→tdiusa.com; client's own 47-pg SOP (~550pg, 30 cities×7 services) ~90% matches our pipeline; open: platform (WP vs our Astro), HubSpot 48033708 wiring, CSLB license missing; docs in clients/tdi-builders/docs/

- [Stripe→App Direct Billing](stripe-app-direct-billing.md) — n8n OUT of Stripe path 2026-07-07; one webhook endpoint; signup idempotent; 07-20 recharge-invoice fix: both n8n recharge workflows now write billing_invoices + receipt links, 23 backfilled; Kenneth Gamble = Paul Davis
- [Audit Lead Magnet](audit-lead-magnet.md) — LIVE on rank.restorationai.io; 2-step stepper → $0.55 full report; landing-page/ repo is canonical prod source (sales/rank-ai DEPRECATED)
- [Free-Audit Lead Magnet](lead-audit-lead-magnet.md) — rank.restorationai.io form → Railway POST /lead-audit → scripts/lead_audit.py → R2-hosted report + SendGrid; PII in private bucket rankai-leads-private; ~$0.55/audit; Pages project `rank-ai-landing-page` is DIRECT-upload (wrangler)
- [Davis Review Campaign State](davis-review-campaign-state.md) — Davis LIVE mid-drip on his OWN approved toll-free +18559017178 (567 rows, step-1 backlog draining at 2/20min)
- [Review Reactivation Engine](review-reactivation-engine.md) — LIVE; 08-23 SENDER POOL: one active campaign per number; RT Olson pinned to ex-client 3 Lions TF +18779194344 (pace 4/20, gate ON, own TF still to submit); Eco Safe/Highridge/Orl Integrity TFs webhook-ready in pool; HydroZ keeps the 3 mid-drip campaigns (QCI/Life Savers/Kenny), never switch mid-drip; gate page redesigned light-theme 08-23 (logo default, big faces); 08-03 policy + fleet TF audit in file; FF own-855 IN_REVIEW (card eac2f0b7)
- [System 5 Video Pilot State](system5-video-pilot-state.md) — first video LIVE UNLISTED awaiting review; flood-fixers channel = "Gabriel Herrera", narestco channel = "Jose Osuna (National Restoration)" — API renames silently ignored, manual rename gates public; pinned action row added
- [NaRestCo Trauma Focus](narestco-trauma-focus.md) — 2026-07-14: 60 trauma pages on STAGING awaiting approval; GBP services held till prod; catalog v0.3.0; ⚠️ scaffold overwrites rendered content (needs guard)
- [NaRestCo Third-Party GBP Poster](narestco-gbp-third-party-poster.md) — daily GBP posts are Merchynt-Paige-like external tool, NOT us (47/49); double-posting decision pending w/ client
- [AI-Search Visibility Program](ai-search-visibility-program.md) — 2026-07-03: two AI answer modes (research=content we win / emergency=Yelp+GBP entity feed we lose); emergency pages, IndexNow, listicle targets, strategist citation loop ALL LIVE; NaRestCo Yelp overhaul is top manual item
- [DataForSEO Balance + APIs](dataforseo-balance-and-apis.md) — DFS account hit $0/402 on 2026-07-01 → NaRestCo's fake map-pack "collapse" (affects ALL clients); geogrid guard + UI fix shipped; Backlinks API unused, now free-worth-adopting
- [NaRestCo Call-Conversion Gap](narestco-call-conversion-gap.md) — ads ARE producing ~2 calls/day (Twilio proof) but Google Ads logs 0 call conversions; click-to-call tracking broken, not the LP — stop cutting budget on the illusion
- [FireDEX Butler Onboarding](firedex-butler-onboarding.md) — water-first despite fire name (4/10 difficulty); GBP category flip is #1 fix; 2.3★ Pittsburgh namesake; intake seeded 07-08, site not yet planned/built
- [Flood Fixers Onboarding](flood-fixers-onboarding.md) — connected Google 2026-06-29; shares Gmail w/ flooring biz (app mislabels as "Luxury Custom Floors"); Ads acct 5252629170, not yet MCC-linked
- [Flood Fixers Site State](flood-fixers-site-state.md) — site build PAUSED 2026-06-30; homepage fully imaged + light theme on localhost:4323/staging; remaining: staging push, CSLB #, production, NS cutover
- [GA4 + Clarity Provisioning](ga4-clarity-provisioning.md) — GA4 via service account (no OAuth needed); per-client measurement IDs; Clarity still manual
- [GBP Optimizer System](gbp-optimizer-system.md) — AI GBP optimizer + page-build automation (gbp.py, app panel, scheduled gbp-maintenance); shipped to prod
- [LSA MCC Access + Launch Blockers](lsa-mcc-access-and-launch-blockers.md) — 08-07: Flood Fixers LSA verified+SERVING but 5 impr/30d & 0 leads (portal job-type layer suspect); 5 clients never got an MCC invite; auto-invite on OAuth NOT built; Go Green + Quality Contracting self-blocked; apex_live flag unreliable
- [LSA Management Capabilities](lsa-management-capabilities.md) — LSA fully API-manageable (budget/bids-above-$1k-cap/service areas) after one-time EU-political-ads declaration; Home Pride LSA at $0.01/day; app LSA panel on feat branch
- [Ads Skills Suite](ads-skills-suite.md) — Six `ads-*` Google Ads skills built for Rank AI restoration clients, full campaign lifecycle
- [Ads Journal System](ads-journal-system.md) — Per-client clients/{slug}/ads-journal.md ops log; read before touching ads, auto-logged on every change; ALSO read docs/ads-playbooks/ (emergency-plumber-intent.md: panic-moment terms restoration names can't claim but ads can, saved 09-10)
- [No Call Whisper](no-call-whisper.md) — RETIRED 08-10: whisper is per-client now (default none; RX keeps its announcement); never a keypress gate
- [NaRestCo Paid + Geo-grid State](narestco-paid-and-geogrid-state.md) — Ads cold-start + conversion fix + geo-grid; time-sensitive: graduate SKAGs ~early July, LSA needs manual work
- [Notion Team Focus Framework](notion-team-focus-framework.md) — Monthly→weekly→daily cascade built in Notion; 3 DBs, integration "Team Ops Framework", views/templates left as UI steps
- [Rank AI Meta Lead-Quality Diagnosis](rank-ai-meta-lead-quality-diagnosis.md) — June 2026 demo collapse: Advantage+ broad targeting floods wrong-industry leads; access creds for GA4/Meta/Stripe/Supabase/GHL
- [Rank AI KPI Dashboard](rank-ai-kpi-dashboard.md) — Zero-backend Command Center at rank-ai/kpi-dashboard/; aggregate.py → monthly JSON snapshots → static index.html; June: 9 demos, 0 closes
- [Call Tracking DNI](call-tracking-dni.md) — LIVE 08-24: sitewide tracking numbers via DNI (source/schema keep NAP); 8-client fleet + narestco verified; GBP tracking-primary already standard; open: citations→real line, provisioning for non-activated
- [Daily Call List Automation](daily-call-list-automation.md) — GHL→Notion cron on Santino's Mac; 9am PT list (SendGrid email, melia removed) + 6pm PT auto note-sync, both M–F
- [Call List Standalone Repo](call-list-standalone-repo.md) — split to restorationai/Rank-AI-Call-List 08-25; OLD copy SWITCHED OFF 09-17 (no call list at all now); Levi stalled 08-30, his version never deployed
- [GBP API Access Reapplication](gbp-api-access-reapplication.md) — GBP API write access now APPROVED (2026-07-01); unlocks GBP posts (shipped 2x/wk) + photos; Q&A feature KILLED by Google late 2025; auth via gbp.py
- [GBP Photo Intake](gbp-photo-intake.md) — public no-login upload links (restorationai.io/gbpphotos/{slug}) for field crews; EXIF/GPS stripped on-device; feeds GBP+site; CF token/account gotchas
- [App Source: GitHub not Desktop](app-source-github-not-desktop.md) — Always read Restoration-AI-APP from its GitHub repo; the desktop -main folder is a stale zip
- [Auto Localhost Testing](auto-localhost-testing.md) — After any app change, auto-serve the branch on localhost:5173 (don't ask); merge to prod only after Santino confirms
- [Kickoff Prep Reminder](kickoff-prep-reminder.md) — LIVE 07-20: GHL webhook -> /kickoff-prep -> Fathom poll -> one SMS+email; dedupe tag kickoff-prep-sent; Derek pre-tagged
- [Client Bootstrap System](client-bootstrap-system.md) — one-command handoff + nightly backstop LIVE 07-21; 5 clients bootstrapped; app fixes on branch await merge
- [Site Build Pipeline](site-build-pipeline.md) — maiden voyage SHIPPED 07-23 (PuroClean + RX on staging, 4 fix-forward rounds); bootstrap auto-seeds city rings; empty-truth-table clients need claims neutralization
- [Site Lead Capture BROKEN](site-lead-capture-broken.md) — 08-07: 12 of 21 client forms 502 and lose every lead (Pages env vars unset, 3 LIVE); Crew GHL webhook live+tested; alias lags deployment URL after env changes; 4 clients have no git-connected Pages project
- [System 0 Content Engine](system-0-content-engine.md) — 4-format AI-citation rotation (best-of/cost/who-to-call/case-study), prioritized-lane gotcha, gsc_register at cutover, active-status gate; 08-26 stall saga: 3 root causes fixed, content_only/only_slug fast-lane dispatch, agents self-commit posts
- [OnlineJobs Hiring Screen](onlinejobs-hiring-screen.md) — 61 SEO applicants scored, awaiting Santino's review before live send; video-intro screening policy
- [GBP Ranking Topics](gbp-ranking-topics.md) — 08-11 saved topics: water-cleanup service/page fleet-wide, GBP name-change suggestion cards, GBP service↔site page parity (Crew case), colloquial search-term pages
- [Fleet Monthly Reports](fleet-monthly-reports.md) — client_report.py + Railway /report front door + monthly cron; Supabase public storage will NOT render HTML
- [Franchise Logo Policy](franchise-logo-policy.md) — franchises (Paul Davis, PuroClean, Servpro...): pull the official brand logo from the franchisor site, never wait on the client
- [Sales Post-Demo Automation](sales-followup-system.md) — LIVE 09-06 approval mode: title+tag gated, fail-closed discernment, Full Audit Sent/Proposal Sent tags; NEEDS Levi Fathom key (FATHOM_SALES_API_KEYS)
- [Registrar Access Human-Only](registrar-access-human-only.md) — 09-06: NO GoDaddy/registrar sessions for browser agents; NS changes stay manual; agent logins = Google + Bing only
- [NaRestCo No More Reviews](narestco-no-more-reviews.md) — 09-07: never propose review campaigns/asks for narestco; standing preference
- [Mac Mini Operator](mac-mini-operator.md) — LIVE 09-07: git = two-machine agent channel (CLAUDE.md → MINI-OPERATOR.md → mini-inbox.md checkboxes → mini-reports/); Google+Bing sessions only; supervised-first
- [Quiet Hours Outbound](quiet-hours-outbound.md) — LAW 09-07: no late-night client sends; queue for their morning; convert GHL UTC timestamps before judging
- [Wix Domains: No NS Change](wix-domains-no-ns-change.md) — Wix-bought domains can never change NS; launch = transfer away to our Cloudflare (~5-7d); start transfer at signing
- [MCC Restoration Dead](mcc-restoration-dead.md) — DEAD 09-19 (Suspended); all lanes gated, video_cron gap fixed; never include in any work
- [Mold Solutionz Dead](mold-solutionz-dead.md) — DEAD client, fully removed 09-09; site kept as templates/mold-restoration-site; never include in any work
- [Per-Client Architecture](per-client-architecture.md) — LAW 09-19: all systems per-client matrix fan-out, never bulk sweeps; content+video converted; roadmap: ops-sync split next, then weekly-maint, gbp-maint, monthly-reports
- [Plumbing-Forward Names](plumbing-forward-names.md) — LAW 09-18: plumbing option = #1 rename recommendation regardless of license confirmation (gray-area stance); license question still rides the pitch; site-copy gate unchanged
- [GBP Keyword Name Strategy](gbp-keyword-name-strategy.md) — house stance 09-10: lead aggressive (24/7 Emergency pattern); 3 synced records (DB suggestions + docs/gbp-rename-candidates.md + rank-ai-gbp-rename skill); 5 clients seeded; OneStop proof + validated volumes
- [Greeting Name Law](greeting-name-law.md) — LAW 09-16 (Ashley/DryCor): greet only the thread's on-file name; wrong-name send guard LIVE; one-shots never hardcode names; recaps 3-4 sentences
- [Monica Never Claims Actions](monica-never-claims-actions.md) — RX/Barbara 09-09: Monica confirmed a removal she can't execute; opt-outs need a real tool or named escalation, never a bare "done"
- [Setup Email Standard](setup-email-standard.md) — 09-09: ALL registrar/delegate accounts + invites use setup@restorationai.io; 09-27: directory signups use setup-{slug}@ dash aliases (Workspace routing rule a68b5 → contact@, verified)
- [Site Design Color Law](site-design-color-law.md) — LAW 09-11: neutral charcoal canvases, brand color in doses, red CTAs; hero grid unconditional; restoration call-first no hero form
- [Anthropic Credit Outage + Canary](anthropic-credit-outage-canary.md) — 09-14 credits died silently, all AI down hrs; canary SMS live in call-intel; call_alerts CI env was broken too
- [RTO/BDA + embed CSP fleet gap](rto-bda-embed-csp.md) — BDA Digital crew IDs + GA4/GTM grants; frame-ancestors blocks /embed/ iframing fleet-wide, only rt-olson fixed
- [CC Owner on Third-Party Emails](cc-owner-on-third-party-emails.md) — LAW 09-17: owner always CCd on vendor/associate threads about their account
- [No-Show Human-Only](noshow-human-only.md) — LAW 09-18 (Amin incident): automation never marks no-show; noshow_checker auto-bury branch must go report-only (fix the standalone Call-List repo)
