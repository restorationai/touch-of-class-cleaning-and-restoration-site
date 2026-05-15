# New Client Onboarding — Prompt Template

Fallback / manual mode for onboarding a new Rank AI client without the `rank-ai-onboard` skill. Useful when working outside Claude Code, or when the skill isn't installed on a particular machine.

## How to use

Fill in the five bracketed values at the top, paste the whole block into a fresh Claude session at `/Users/santino/Desktop/mywebsitecode/rank-ai/`, and let Claude walk you through it. If using the script directly without Claude, follow the steps yourself.

## The prompt

```
New Rank AI client onboarding.

Client info:
  Company name:                  [Display Name, e.g. "Acme Restoration"]
  Domain:                        [acme.com — root only, no https://, no www]
  Tier:                          [standard | premium | budget]
  Has existing live website?     [yes | no]
  Zone file path (if yes):       [~/Downloads/acme.com.txt]

Project root: /Users/santino/Desktop/mywebsitecode/rank-ai/
Before starting, read these for context:
  - rank-ai/docs/image-hosting-architecture.md
  - rank-ai/docs/onboarding-skill-spec.md

Cloudflare credentials are in ~/.claude.json under mcpServers.cloudflare.env
(CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID).

Walk me through this sequence, pausing for confirmation between major steps:

1. Run onboard_client.py init with the client info above.
2. If existing live site is YES:
   a. mirror-dns with the zone file path (do --dry-run first, show output, then real run)
   b. verify-dns to confirm Cloudflare mirrors the original DNS provider's answers
   c. Only after verify passes, tell me to update nameservers at the registrar
3. If existing live site is NO:
   a. Tell me to update nameservers at the registrar immediately
4. Poll status until ns_active (DNS propagation typically 5-60 min).
5. Run provision to create R2 bucket + bind images.<domain>.
6. Confirm provisioning succeeded, output a summary, and stop.
```

## Direct script usage (no Claude)

```bash
export CLOUDFLARE_API_TOKEN='...'        # from ~/.claude.json
export CLOUDFLARE_ACCOUNT_ID='...'

cd /Users/santino/Desktop/mywebsitecode/rank-ai/

# 1. Init
python3 scripts/onboard_client.py init \
  --name "Acme Restoration" \
  --domain acme.com \
  --tier standard

# 2. (Optional, only if existing live site)
python3 scripts/onboard_client.py mirror-dns \
  --slug acme --from-zonefile ~/Downloads/acme.com.txt --dry-run
python3 scripts/onboard_client.py mirror-dns \
  --slug acme --from-zonefile ~/Downloads/acme.com.txt
python3 scripts/onboard_client.py verify-dns --slug acme

# 3. Update nameservers at the registrar — manual step

# 4. Wait, then check status
python3 scripts/onboard_client.py status --slug acme

# 5. Once ns_active
python3 scripts/onboard_client.py provision --slug acme
```
