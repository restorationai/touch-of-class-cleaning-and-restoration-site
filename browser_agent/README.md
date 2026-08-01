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
3. Audit screenshots before and after every live write → runtime/audit/.
4. Every action (attempted or done) is ledgered with company_id + playbook +
   outcome; a playbook marks its setup-ledger item done ONLY after verified
   completion (the board is the human's oversight — never pre-clear it).
5. Credentials: registrar/portal creds live in ~/.rankai/portal-creds.json
   (chmod 600, NEVER in the repo). Google agency login lives only inside the
   persistent profile — log in once via `python3 -m browser_agent login`.
6. NAP source of truth = the client's Business Information card (companies
   row / plan-input brand). REAL phone number always — never tracking numbers
   on citations.

## First run (needs Santino at the keyboard once)
    pip install playwright && playwright install chromium
    python3 -m browser_agent login          # opens the profile; log into the
                                            # agency Google + Bing + registrars
    python3 -m browser_agent run --playbook bing-places --slug narestco        # dry-run
    python3 -m browser_agent run --playbook bing-places --slug narestco --live # gated live

## Playbooks (build order)
1. bing_places    — create/claim Bing Places listings (imports from GBP)
2. domain_connect — registrar NS cutover: GoDaddy delegate access (BROWSER,
                    not API — delegate email access grants no API), Bluehost
                    via client-provided creds; registrar logged per client in
                    ~/.rankai/portal-creds.json
3. apple_maps     — Business Connect agency claims
4. bbb            — request-form listings
5. lsa_portal     — job-type enrollment toggles + license/insurance doc submission
6. facebook_grab  — Go Green photo/video harvest
