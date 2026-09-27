# Rank AI Browser Agent

Terminal-driven Playwright automation over a PERSISTENT logged-in Chromium
profile (pattern adapted from the Skool Automation reference, 2026-08-01).
One chassis owns the safety machinery; each portal task is a thin playbook.

## Architecture
- `chassis.py`  — persistent profile, live-write gates, audit screenshots,
                  action ledger (Supabase `browser_agent_actions`), kill switch
- `playbooks/`  — one module per portal task (bing_places, domain_connect, …)
- `runtime/`    — gitignored: browser profile, audit screenshots

## Safety rules (binding — mirror of the reference AGENTS.md)
1. DRY-RUN by default. Live writes require `--live` AND the kill switch off
   (`ops_kv key 'browser-agent-paused'` empty). No exceptions.
2. NEVER bypass CAPTCHAs, login prompts, 2FA, or anti-abuse controls. On any
   security challenge: screenshot, pause the run, file a [TODO-SANTINO] note.
   ONE NARROW EXCEPTION (Santino 2026-09-27, for unattended operation): the
   agent MAY click a reCAPTCHA / Turnstile "I'm not a robot" CHECKBOX once,
   with a normal click, from its own persistent signed-in profile — that is
   ordinary use of the page. If the checkbox resolves green, continue. If it
   escalates to an image/audio puzzle or any other challenge: do NOT attempt
   it, never use a solving service or human-mimicry tricks — screenshot,
   park, and file it under ## Needs. One attempt per form, no retry loops.
3. Audit screenshots before and after every live write → runtime/audit/.
4. Every action (attempted or done) is ledgered with company_id + playbook +
   outcome; a playbook marks its setup-ledger item done ONLY after verified
   completion (the board is the human's oversight — never pre-clear it).
5. Credentials: registrar/portal creds live in ~/.rankai/portal-creds.json
   (chmod 600, NEVER in the repo). Google agency login lives only inside the
   persistent profile — log in once via `python3 -m browser_agent login`.
6. NAP source of truth = the client's Business Information card (companies
   row / plan-input brand). Phone = the client's GBP PRIMARY number — Santino
   2026-07-31: tracking numbers are ACCEPTED on citations (NAP consistency
   means matching GBP); citations_audit's ok_phones mirrors this.

## First run (needs Santino at the keyboard once)
    pip install playwright && playwright install chromium
    python3 -m browser_agent login          # opens the profile; log into the
                                            # agency Google + Bing + registrars
    python3 -m browser_agent run --playbook bing-places --slug narestco        # dry-run
    python3 -m browser_agent run --playbook bing-places --slug narestco --live # gated live

## Playbooks (build order)
1. bing_places    — DONE 2026-08-01 (8/19 listed, weekly Google sync ON);
                    nightly sweep.py runs the Sync click — the one earned-
                    unattended step so far
2. facebook_grab  — DONE 2026-08-01: Go Green harvest (50 photos -> repo +
                    branding bucket, 2 video URLs in manifest)
3. form_fill      — CURRENT: Houzz / Porch / HomeGuide / BBB free listings
                    (playbooks/form_fill.py PORTALS registry; supervised
                    until 3 clean completions EACH; aggregators parked)
4. domain_connect — registrar NS cutover: GoDaddy delegate access (BROWSER,
                    not API — delegate email access grants no API), Bluehost
                    via client-provided creds; registrar logged per client in
                    ~/.rankai/portal-creds.json
5. apple_maps     — IN PROGRESS, supervised run 1/3 DONE 2026-08-16. Agency
                    account approved ~08-15 (portal rebranded to "Apple
                    Business", business.apple.com). Run 1: supervised login
                    completed (Santino relayed the SMS 2FA code live), THREE
                    locations created and sitting in Apple's "In Review"
                    queue (up to 5 days, publishes on approval, no
                    verification step demanded): narestco, restorationxpress,
                    homepriderestorationandcleaning — each under its own
                    brand, category "Damage Restoration Service", 24/7 hours,
                    GBP-primary phones. crew-restoration-construction HELD on
                    a zip discrepancy (GBP 57105 vs companies row 57110 —
                    note filed). API access REQUESTED from the portal the
                    same session (staged pipeline: integration -> data
                    qualification -> production; decision arrives by email).
                    Full wizard selectors + traps pinned in the playbook's
                    run-1 notes. Chassis gained CDP attach
                    (Session.start(cdp_url=...), `run --cdp URL`). Apple
                    sessions do NOT survive browser restart (2FA
                    re-challenges even after Trust) — every run starts with
                    a supervised login + held-open browser (pattern in the
                    playbook). NEXT RUN: login (code relayed live), check the
                    In Review three -> record_listing on publish, create crew
                    once the zip answer lands. NOT in the nightly sweep
                    (3-supervised-runs rule).
6. lsa_portal     — job-type enrollment toggles + license/insurance doc submission
7. onlinejobs_ph  — hiring: screens applicants on a job post and answers them.
                    Reads via the SPA's own JSON API (the UI list is virtualized
                    and walking it costs ~30s per stale row); writes through the
                    real Trix editor + SEND MESSAGE button. Rubric and copy live
                    in playbooks/onlinejobs_ph_config.json, never in the .py.

## onlinejobs_ph notes
- Session host is `v2.onlinejobs.ph`. `www.onlinejobs.ph` is a separate,
  logged-out origin; a link followed onto www lands on the login page.
- Login is done ONCE by a human into the persistent profile. Automated form
  submission was silently rejected (POST to /authenticate bounced back to
  /login with no error), so do not build a login path here.
- Dedupe is ground truth, not bookkeeping: a thread's messages carry their
  sender, and our contact id is `thread.contacts` minus the applicant's. If the
  thread already holds a message from us, the applicant is skipped, which also
  covers replies Santino sent by hand.
- The API rate-limits under a fast loop. 429s are retried with backoff; an
  applicant that still cannot be read is NAMED in a warning, never silently
  dropped, because a dropped applicant is one who never gets contacted.

    python3 -m browser_agent.playbooks.onlinejobs_ph --harvest-only   # scrape only
    python3 -m browser_agent.playbooks.onlinejobs_ph                  # score, write review
    python3 -m browser_agent.playbooks.onlinejobs_ph --live --only shortlist
