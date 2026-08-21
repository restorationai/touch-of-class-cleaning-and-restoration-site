# Rank AI Build Queue — canonical reference

Updated 2026-08-20. One client-facing lane + one internal lane at a time.
Current position and deeper context: docs/WORKING-STATE.md.

## Up next (agreed order)

1. ~~**Fran's ten website changes**~~ **DONE 08-20** — all ten shipped + verified on
   staging preview (commit 195e3e42); PAY HERE ported verbatim from
   qualitycontracting.us (no ask needed); domain recorded + https://None healed;
   reply draft at clients/quality-contracting-inc/fran-reply-draft.md awaiting
   Santino's send. Remaining: Fran's nod -> WE flip Hostmonster NS (email-safe
   cutover; creds held; nothing needed from him).
2. **Monica email evolution** (internal lane, in stages):
   a. ~~Video-verification rule~~ DONE 08-20 (contract rule + message-level guard +
      selfcheck; deployed to both Railway services).
   b. ~~Sender map~~ DONE 08-20: is_internal_sender() — any GHL row bearing a
      userId is OURS whatever its direction field says (external-mailbox sends
      sync back as "inbound" WITH the workspace userId; verified on Bobby's
      live thread). Wired into fetch_inbound_since (webhook+poll never answer
      Santino) + fetch_history ('us-human' transcript label, legends updated);
      9 selfcheck cases; deployed to both Railway services.
   c. Second mailbox OAuth: contact@getrestorationai.com into email intake
      (needs Santino's one sign-in; batch with the Bing re-login sitting).
   d. ~~Reply-in-channel~~ DONE 08-20: owed_reply_channel() upgrades compose +
      send_now to email when answering an email; inline replies + acks already
      channel-aware; GHL emailReplyMode=reply threading with Re: fallback.
   e. ~~Upload acks + ledger~~ DONE 08-20: pg_cron upload-event-sweep (10 min)
      -> Railway /upload-event -> ONE deterministic thank-you per burst (all
      send gates; hours-held bursts retry; system artifacts never ack);
      work_log received rows; upload_stranded_check flags pinned upload rows
      planned 72h+ (FIRST RUN: 9 stranded logos, 7-31 days — cards filed).
   f. Pilot watch on Bobby + Fran (2d threading on their next email) before
      calling the email evolution done.
3. **Citations program**: tracker table + Build Stages popup SHIPPED 08-21
   (citation_listings, 33 seed rows + 24 discovered socials; popup v10.1 names
   every missing platform, wrong_data rows carry corrections — Reign pilot;
   MERGED TO PROD 08-21 incl. Social Profiles card on Connect). REMAINING:
   3-per-night creation rotation + per-directory backoff + failure-streak
   watchdog (parked per Santino) + Bing re-login (Santino).
4. **Social discovery**: data pass DONE 08-21 (site-footer crawl, 24 profiles
   found across 15 clients, social_state=found rows). REMAINING: web-search
   pass for the 7 clients with no crawlable site, Monica confirm-asks,
   GSC-sync browser playbook (supervised).
5. **Apple Maps run 2** (rides any night): verify the 3 in-review listings publish,
   create Crew using his GOOGLE LISTING address verbatim (Santino's call, zip debate
   closed), keep watching for Apple's API-access decision email (request submitted
   in-portal during run 1).

## Needs Santino (minutes, batch in one sitting)

- OAuth sign-in as contact@getrestorationai.com (queue 2c)
- Bing Places re-login in the agent browser window (queue 3)
- GSC social-channel clicks per property once discovery fills the worksheet
  (docs/gsc-social-connections.md)
- Send the Bobby email draft (GoDaddy delegate-access version) + Fran reply
  (clients/quality-contracting-inc/fran-reply-draft.md — ready, per-item rundown)
- Decisions pending: BrightLocal spend yes/no; billing-alert escalation yes/no

## Backlog (not yet scheduled)

- MMS ingest gap — texted photos auto-filed with doc-context routing (Jack case)
- Crew's image bucket — images.crew3r.com never provisioned
- Imagery remainder — no-image stage gate; CLIENT DIRECTION from real photos;
  auto-redact text/phone from livery references
- SMS exact-cost billing — Twilio true per-text prices onto invoices
- Reviews tab editor — view/edit the four campaign messages in-app
- Services as Products — browser agent adds product tiles to GBPs (supervised)
- Post-meeting recap messenger — auto recaps after sales/kickoff calls
- Access verification pass — verify claimed domain access before green chips
  (Life Savers "ns_live" stale) + same-day GoDaddy invite-acceptance alerts
- Multi-location profile creator — Sioux City (waits on Iowa DBA watcher + Kyle)
- Visual sitemap generator — per-client Figma-style map for reveals/sales decks
- YouTube buildout — question-videos + shorts cuts + owner-avatar pilot (Kyle)
- Review-photo truck composite for Bobby (photos received; ready to run)
- App polish — Today-tab filter, Ops Attention triage, LSA "Ready" persistence
- Diagnosis agent — parked by Santino
- Yelp claiming playbook — ON ICE (needs code-relay loop + scheduled windows;
  phase 0 when thawed = Monica collects existing Yelp logins)

## SEO queue (from the gap analysis; remaining)

- Small batch leftovers: none — review-card QR wording, GBP deep links, 3rd weekly
  post slot, GSC worksheet all shipped 08-19/20
- BrightLocal long-tail citations — Santino yes/no
- AREA_DEMAND follow-ups from wrong-page-ranks reports (e.g., Home Pride's
  Marion/Kamas/Hoytsville UT expansion ring) — fold into ring updates per client

## Recently DONE (compressed; see WORKING-STATE.md for detail)

08-18/19/20: home-city fix fleet-wide; Monica quiet-window + userId human detection
+ call-promise reversal + California fact; RT Olson 124-page build + hero form +
real photos; Dry County image revamp; safety trilogy (repo guard, scaffold product
guard, mid-build stall alarm); area-page FAQPage schema fleet-wide; wrong-page-ranks
monthly check (+AREA_DEMAND); GBP 3x/week + deep links; hub QR wording + self-hosted
QR + before/after Job Story fields; plumbing render prompts + vertical overlay;
scheduler heartbeat (retired zombie billing job); intake auto-satisfy (brand-kit);
citations wrong-business cleanup; uploads gallery in app; Robert's logo incorporated;
QCI verification timeline established (Google email 4h after connect — do not blame
the client, do not claim innocence).
