---
name: rank-ai-onboard
description: Onboard a new Rank AI client end-to-end — create Cloudflare zone, mirror existing DNS records if the client has a live site, guide the user through the registrar nameserver update, wait for propagation, provision the R2 bucket and bind images.{domain} as a custom domain. Use whenever the user says "onboard a new client", "new Rank AI client", "rank-ai-onboard", or starts setting up infrastructure for a new restoration-industry client. Wraps rank-ai/scripts/onboard_client.py.
---

# Rank AI — Onboard a New Client

You are running the multi-step onboarding flow for a new Rank AI client. This skill drives `rank-ai/scripts/onboard_client.py` and guides the user through the manual nameserver-update step at their registrar.

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/`

Change to this directory at the start.

## Pre-flight context

Before doing anything, read these two files so you have the full architectural context:

- `rank-ai/docs/image-hosting-architecture.md`
- `rank-ai/docs/onboarding-skill-spec.md`

## Credentials

The Cloudflare API token and account ID live in `~/.claude.json` under `mcpServers.cloudflare.env`. Read them once at the start and set as environment variables for every script invocation:

```bash
export CLOUDFLARE_API_TOKEN='<from ~/.claude.json>'
export CLOUDFLARE_ACCOUNT_ID='<from ~/.claude.json>'
```

Or pass them inline on each script call.

## Step 1 — Collect inputs

Use `AskUserQuestion` to collect, in order:

1. **Company name** (display name, e.g. "Acme Restoration")
2. **Domain** (root only — no `https://`, no `www`, no trailing slash)
3. **Tier** — `standard` (Pro hero/OG, Flash inline) / `premium` (Pro all) / `budget` (Flash all). Default: `standard`.
4. **Has existing live website?** (yes / no) — affects whether DNS mirroring is needed.
5. **If yes** — ask for the path to the exported zone file (typically `~/Downloads/<domain>.txt` from GoDaddy's "Export Zone File" feature).

After collecting, echo back a summary and ask for one-shot confirmation before proceeding.

## Step 2 — Run init

```bash
python3 scripts/onboard_client.py init \
  --name "<company>" --domain <domain> --tier <tier>
```

The output includes two Cloudflare nameservers. Keep them in context — you'll show them to the user in Step 4.

## Step 3 — If existing live site: mirror DNS

Skip this entire step if Q4 was "no."

First, dry-run so the user can review what will be added:

```bash
python3 scripts/onboard_client.py mirror-dns \
  --slug <slug> --from-zonefile <path> --dry-run
```

Show the dry-run summary (added / skipped counts; the skipped records with reasons). Ask the user to confirm. Then run for real (drop `--dry-run`).

After mirror, verify:

```bash
python3 scripts/onboard_client.py verify-dns --slug <slug>
```

If any record fails (returns "(no answer)"), **wait 30 seconds and retry once** — newly-created Cloudflare records can take a moment to propagate to all of Cloudflare's edge POPs. If retry still fails, STOP and surface the failures. Do not proceed to Step 4. The user should not flip nameservers until verify-dns is clean.

## Step 4 — Manual nameserver update at the registrar

Tell the user clearly:

> At the registrar for **<domain>**, replace the current nameservers with these two:
> 
>     <ns1>
>     <ns2>
> 
> Save the changes. Propagation usually takes 5–60 minutes.

Then **pause and wait for the user to confirm** they've updated the nameservers. Use `AskUserQuestion` with options like "Done — nameservers updated" / "Need help / want to walk through GoDaddy" / "Cancel onboarding".

## Step 5 — Wait for propagation

Once the user confirms the NS update, poll status:

```bash
python3 scripts/onboard_client.py status --slug <slug>
```

If status is still `pending_ns`, tell the user propagation hasn't completed and offer to:
- Wait 5 minutes and retry automatically (use a sleep + retry loop, max 30 min)
- Pause and have them come back to the session later

When status flips to `ns_active`, proceed to Step 6.

## Step 6 — Provision

```bash
python3 scripts/onboard_client.py provision --slug <slug>
```

This creates the R2 bucket `rankai-<slug>`, binds `images.<domain>` as the custom domain, and smoke-tests TLS+DNS.

If provision fails, surface the full error. Common cause: zone status not actually active yet — re-run status, wait, retry provision.

## Step 7 — Output summary + auto-chain to plan-site

Once `provision` succeeds, give the user:

```
==> Onboarding complete for <company>

  Slug:           <slug>
  Domain:         <domain>
  Cloudflare zone: <zone_id>
  R2 bucket:      rankai-<slug>
  Image URL base: https://images.<domain>/
  Image policy:   <image_policy from client record>
  Client record:  rank-ai/clients/<slug>.json
  Old live site:  https://<domain>/ (still served from legacy host — no impact yet)
```

Then ask: **"Ready to plan the site now? (yes / not yet)"**

- If yes → invoke `rank-ai-plan-site` skill with the same slug. The plan skill takes over (gather services + areas + brand, generate URL plan + content map). When planning is done, it auto-chains to `rank-ai-build-site`.
- If they want to defer → tell them where the client record lives and stop. They can resume by invoking `rank-ai-plan-site` whenever.

The skill chain is: **onboard → plan-site → build-site → (cut-over within build-site)**. Each skill suggests the next so the operator just confirms transitions. The whole launch (onboarding through go-live) happens in one continuous session if the user wants, or can be paused at any boundary.

The full multi-client workflow is documented at `rank-ai/docs/multi-client-workflow.md` — read it once to understand the topology (monorepo + per-client deploy repos via subtree push).

## Error handling rules

- Always surface the full error message from the script. Never summarize errors away — the user needs the raw message to debug.
- The script is idempotent. If anything fails partway, re-running the same subcommand picks up where it stopped.
- If the user wants to start over completely, the `init` subcommand has a `--force` flag.

## Google Maps Embed API key (collect during plan-site, not onboarding)

The site template includes a `GoogleMap` component on all service-area pages. It needs a browser-restricted Google Maps Embed API key. **Do NOT collect or create this during onboarding** — it is collected in Step 2 of `rank-ai-plan-site` as part of brand-details gathering.

When that step arrives, the key setup is:
1. Google Cloud Console → APIs & Services → Enable **Maps Embed API** for the project
2. APIs & Services → Credentials → **Create Credentials → API key**
3. Edit the key → Application restrictions: **Websites** → add `https://*.{domain}/*` and `http://localhost:*/*`
4. API restrictions → Restrict key → select **Maps Embed API**
5. Copy the key (starts with `AIza`) → add to `plan-input.json` under `brand.google_maps_api_key`
6. Add to `rank-ai/.env` as `GOOGLE_MAPS_API_KEY={key}` (optional — only needed if scripts use it directly)

The `GoogleMap` component falls back gracefully to a "View on Google Maps" text link if the key is empty, so this is non-blocking. The key is NOT an OAuth client ID and NOT a service account — it is a plain browser API key.

## What this skill does NOT do (out of scope)

- Site building (Astro scaffold) — that's `rank-ai-build-site`
- Content planning (URL structure, keyword research) — that's `rank-ai-plan-site`
- Blog post generation — that's `rank-ai-blog-routine`
- Email infrastructure changes
- DNS records beyond what was in the original zone file
