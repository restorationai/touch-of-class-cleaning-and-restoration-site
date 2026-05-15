# Rank AI — Onboarding Skill Spec

**Last updated:** 2026-05-09
**Implementation:** `rank-ai/scripts/onboard_client.py`
**Future skill wrapper:** `rank-ai-onboard-client` (interactive, calls the script)

---

## Purpose

Provision Cloudflare infrastructure for a new Rank AI client so the blog routine and website build can proceed without per-client manual setup. Locks in the architecture from `image-hosting-architecture.md`.

## Contract

### Inputs

| Field         | Required | Type   | Notes                                                    |
| ------------- | -------- | ------ | -------------------------------------------------------- |
| display_name  | yes      | string | E.g., "National Restoration Construction"                |
| domain        | yes      | string | Root domain only — no protocol, no `www`, no path        |
| tier          | yes      | enum   | `standard` (default) \| `premium` \| `budget`            |
| contact       | no       | email  | Stored in client record for future use                   |
| slug          | no       | string | Override derived slug; default = leftmost label of domain|

### Outputs

- **Cloudflare zone** for `{domain}` in our account
- **R2 bucket** named `rankai-{slug}`
- **Custom domain** `images.{domain}` bound to the bucket, TLS issued
- **Client record** at `rank-ai/clients/{slug}.json`

### Side effects

- Creates a Cloudflare zone (charged at Cloudflare's free tier by default)
- Creates an R2 bucket (free tier covers ~10GB storage; exceeded charges apply)
- Issues a TLS certificate via Cloudflare Universal SSL (free)
- Writes client record to local repo

## State machine

A client record progresses through these statuses:

```
                     ┌──────────────┐
                     │ (no record)  │
                     └──────┬───────┘
                            │ init (zone created, NS pending)
                            ▼
                     ┌──────────────┐
                     │ pending_ns   │  Zone exists in CF, NS not yet propagated
                     └──────┬───────┘
                            │ mirror-dns (if client has existing live site)
                            │ verify-dns (confirm mirror works against CF NS)
                            │ → user updates NS at registrar
                            │ status (zone polled, NS propagated)
                            ▼
                     ┌──────────────┐
                     │ ns_active    │  CF reports zone status=active
                     └──────┬───────┘
                            │ provision (R2 + custom domain bound + smoke OK)
                            ▼
                     ┌──────────────┐
                     │ active       │  Ready for image uploads & site build
                     └──────────────┘
```

Each transition is idempotent. A re-run at any state advances or no-ops; it never destroys existing resources.

## Live-site preservation strategy (DNS mirror — the default for existing clients)

**This is the default path for any client who has an existing live website and/or active email at their domain.** Only skip if the domain has no live records and no active email (rare).

### Why mirror DNS instead of just flipping nameservers

When you change nameservers at a registrar, GoDaddy (or wherever) stops being authoritative for that domain immediately. Cloudflare becomes authoritative — and if Cloudflare doesn't have copies of the existing records, the website goes down and email stops flowing during the propagation window. **The client experiences an outage.**

The fix: **pre-populate Cloudflare with mirrors of every existing record BEFORE the NS flip**, so when the NS change propagates, Cloudflare serves the same answers GoDaddy was serving. The live site stays up, email keeps flowing, and you can independently build the new site at a staging URL.

### The flow

1. **`init`** — creates the Cloudflare zone, outputs the assigned NS records (does NOT update registrar yet).
2. **Get a zone export from the current DNS provider.** GoDaddy: DNS Management → Export Zone File. Most registrars/DNS providers offer this; if not, manually screenshot every record. Save as a BIND-format text file.
3. **`mirror-dns --from-zonefile <path>`** — parses the zone file, filters records that don't belong on Cloudflare (SOA, NS, GoDaddy-specific `_domainconnect`, stale `_cf-custom-hostname`), and creates Cloudflare DNS records for everything else. All records start as **DNS-only / unproxied** (grey cloud) to minimize risk.
4. **`verify-dns`** — queries Cloudflare's nameservers directly (`@amos.ns.cloudflare.com`) to confirm every critical record resolves correctly. This works *before* the NS flip because we're bypassing the DNS hierarchy and asking Cloudflare directly. If verify-dns passes, we know the NS flip will be a no-op for end users.
5. **User updates nameservers at the registrar.** With the mirror verified, this becomes safe — Cloudflare will resolve every existing query identically.
6. **`status`** — confirms the zone is `active` on Cloudflare.
7. **`provision`** — creates R2 bucket, binds `images.{domain}` custom domain. This subdomain is *net new* and does not affect the live site.

The new site is built at a staging subdomain (e.g., `staging.{domain}` or a Cloudflare Pages preview URL). On launch day, you flip the root `A` record in Cloudflare from the existing hosting IP to the new Cloudflare Pages target — single-record change, propagates in seconds via Cloudflare's edge.

### Records mirrored vs. skipped

Mirrored:
- A, AAAA, CNAME, MX, TXT, SRV records that the client actively uses

Always skipped:
- SOA, NS — Cloudflare manages these
- `_domainconnect` — GoDaddy-specific, useless on Cloudflare
- `_cf-custom-hostname*` — stale records from prior Cloudflare-for-SaaS setups elsewhere

Optional considerations:
- `_acme-challenge*` records — Let's Encrypt validation tokens. Usually safe to mirror; if there's an active cert issuance in flight, dropping them breaks it.
- DKIM CNAME selectors — must be mirrored if email DKIM signing is in use. The mirror-dns subcommand handles whatever's in the zone file; if the export missed DKIM, add manually.

### Proxied vs. DNS-only setting

The mirror command writes everything as **unproxied (DNS-only / grey cloud)** to start. Cloudflare proxying (orange cloud) routes traffic through Cloudflare's CDN and applies WAF rules — useful for performance and security, but can break things that depend on the origin server's actual TLS cert or specific IP routing.

After NS flip + verification that everything still works through Cloudflare:
- Selectively flip the root `A` and `www` CNAME to **proxied** if you want CDN/WAF benefits on the website itself
- Leave all email infrastructure (MX, autodiscover, sip, lyncdiscover, msoid, _domainkey) **unproxied** — Cloudflare's HTTP proxy doesn't carry mail protocols
- Leave admin/cPanel-related CNAMEs **unproxied**

## Subcommands

| Subcommand    | Purpose                                                                              | When to run                                           |
| ------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| `init`        | Create Cloudflare zone, save partial record, output NS records for registrar update  | Once per new client                                   |
| `mirror-dns`  | Parse exported BIND zone file and create Cloudflare DNS records (filter SOA/NS/etc.) | After `init`, before registrar NS flip (live clients) |
| `verify-dns`  | Query Cloudflare NS directly to confirm mirror works                                 | After `mirror-dns`, before registrar NS flip          |
| `status`      | Poll Cloudflare for current zone status; update record's status field                | After updating registrar nameservers                  |
| `provision`   | Verify zone active → create R2 bucket → bind custom domain → wait for TLS → smoke    | After `status` shows `ns_active`                      |
| `list`        | Show all known clients with their status                                             | Anytime                                               |

## Phase A — manual prerequisite (registrar)

Cannot be automated. After `init`:

1. Log into the domain's registrar (GoDaddy, Namecheap, etc.)
2. Replace the current nameservers with the two emitted by `init`
3. Save changes at the registrar
4. Wait 5–60 min for propagation (sometimes longer for stubborn TLDs)
5. Run `status --slug {slug}` periodically; transition to `ns_active` is the green light

**Why this can't be automated:** Cloudflare doesn't have a registrar API for arbitrary registrars. Each registrar's API is different (and most require human auth flow). Phase A is a one-time human action per client.

## Cloudflare API endpoints used

| Step                 | Method | Path                                                                            |
| -------------------- | ------ | ------------------------------------------------------------------------------- |
| Check zone exists    | GET    | `/zones?name={domain}`                                                          |
| Create zone          | POST   | `/zones`                                                                        |
| Poll zone status     | GET    | `/zones/{zone_id}`                                                              |
| Create R2 bucket     | POST   | `/accounts/{account_id}/r2/buckets`                                             |
| Bind custom domain   | POST   | `/accounts/{account_id}/r2/buckets/{bucket}/domains/custom`                     |

Token must have **Zone:Edit** + **Account:Cloudflare R2:Edit** scopes.

## Failure modes & recovery

| Failure                                       | Cause                                                | Recovery                                                                  |
| --------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------- |
| `init` returns "already exists"               | Zone is in another Cloudflare account                | Manually move zone, or use a different domain. No automated path.         |
| `provision` "zone status is pending"          | Nameservers not yet propagated                       | Wait, re-run `status`, then re-run `provision`                            |
| `provision` R2 bucket name collision          | Slug clash (rare; only if two clients have same slug)| Re-run `init --slug {alt-slug} --force`, then `provision`                 |
| `provision` custom domain bind fails          | Zone not active OR DNS conflict OR auth scope        | Surface error verbatim; common fix is re-issuing token with R2:Edit scope |
| `provision` TLS timeout (>3 min)              | Cloudflare TLS issuance backed up                    | Re-run `provision` — idempotent, picks up where it left off               |

## Client record schema

```json
{
  "slug": "narestco",
  "display_name": "National Restoration Construction",
  "domain": "narestco.com",
  "tier": "standard",
  "image_policy": "pro_hero_flash_inline",
  "contact": null,
  "zone": {
    "id": "30f8272d671672a14bae7ed64e0d4d71",
    "name": "narestco.com",
    "status": "pending|active",
    "name_servers": ["amos.ns.cloudflare.com", "anastasia.ns.cloudflare.com"],
    "created_on": "2026-05-10T03:18:58Z"
  },
  "r2": {
    "bucket": "rankai-narestco",
    "custom_domain": "images.narestco.com",
    "public_url": "https://images.narestco.com",
    "provisioned_at": "2026-05-10T..."
  },
  "status": "pending_ns|ns_active|active",
  "created_at": "...",
  "updated_at": "..."
}
```

## Future skill wrapper (Skill 1 — interactive)

The skill wrapper at `~/.claude/skills/rank-ai-onboard/SKILL.md` will:

1. Use `AskUserQuestion` to collect: `display_name`, `domain`, `tier`, optional `contact`
2. Show derived slug, ask user to confirm or override
3. Shell out to `python3 rank-ai/scripts/onboard_client.py init ...`
4. Display the NS records prominently and walk through GoDaddy/Namecheap update (with screenshots if possible)
5. Offer to schedule a check-back via `/loop` to auto-run `status` until `ns_active`
6. When `ns_active`, prompt user "Ready to provision?" → run `provision`
7. On `active`, output a summary block and suggest invoking `rank-ai-plan-site` next

The script does the work; the skill just wraps it in a guided UX.

## Security notes

- The Cloudflare API token is passed via env var, never written to client records
- Client records contain zone IDs but no credentials
- The token must be scoped narrowly (Zone:Edit + R2:Edit on this account only) so a leak is contained
- Rotate the token at least quarterly; the script reads from env so rotation is a one-line export

## What this skill does NOT do (out of scope)

- DNS records beyond the R2 custom domain (those come from Skill 3 — `rank-ai-build-site`)
- Cloudflare Pages project setup (Skill 3)
- Email/MX records (separate flow if needed)
- WAF / security rules (separate)
- Wildcard certificates (Universal SSL covers `*.{domain}` automatically)

---

*Implementation lives at `rank-ai/scripts/onboard_client.py`. State of truth is `rank-ai/clients/{slug}.json`.*
