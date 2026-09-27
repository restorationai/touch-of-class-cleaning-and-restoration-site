---
name: site-lead-capture-broken
description: "2026-08-07 — 12 of 21 client site forms return 502 and lose every lead (Pages env vars never set); Crew's GHL webhook LIVE; 4 clients have no git-connected Pages project"
metadata: 
  node_type: memory
  type: project
  originSessionId: 6a7501ec-9e6b-4102-8623-fdfc8fa505ff
  modified: 2026-08-08T00:47:22.161Z
---

**Client website estimate forms are silently dropping leads.** Found 2026-08-07
while wiring Crew's GoHighLevel webhook. NOT fixed fleet-wide — awaiting
Santino's go-ahead to write secrets to client production projects.

`functions/api/estimate.ts` needs four Cloudflare Pages env vars:
`SENDGRID_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `COMPANY_ID`.
Email is the primary leg, so when it is missing the handler returns `ok:false`
→ HTTP 502 → the homeowner sees "Something went wrong sending your request."
Nothing is queued, nothing retried, no alert. The lead is simply gone.

- **Configured (4):** narestco, flood-fixers, davis-construction, homepride
- **NOT configured (12):** all-pro-plumbing, restoration-groups,
  restorationxpress (**these three are LIVE and losing leads today**),
  life-savers, reign, diss, go-green, homelyft, mold-solutionz, puroclean,
  quality-contracting, coastal (partial — 3 of 4)
- **Fixed 08-07:** crew-restoration-construction (all 5 incl. GHL)

Verified live: `POST https://therestorationgroup.com/api/estimate` → 502.

**Crew's GHL webhook is LIVE and tested** (`ghl:"sent"`). Driven by a
`GHL_WEBHOOK_URL` env var, never hardcoded, because estimate.ts is identical
across all 21 sites. URL shape is
`/hooks/{locationId}/webhook-trigger/{workflowTriggerId}` — the trigger id only
exists once someone builds an inbound-webhook workflow inside that client's
sub-account, so **per-client URLs CANNOT be derived and are stored nowhere**;
Santino must supply each one. Crew's location `b99VH6ZO70LkuP00ztVk` is Crew's
own sub-account, confirmed different from the agency `GHL_LOCATION_ID`.

**GOTCHA that will waste a session if forgotten:** after setting Pages env vars
or pushing, `staging.rankai-{slug}.pages.dev` keeps serving the PREVIOUS
deployment for several minutes. A test against the alias reported
`skipped:no-key` and looked like a total failure while the deployment-specific
URL (`{hash}.rankai-{slug}.pages.dev`, from the deployments API) was already
correct. **Always verify against the deployment URL, not the alias.**

**4 clients have NO git-connected Pages project:** aaa-water-damage,
firedex-butler, mcc-restoration, prorestoration. They only have legacy
`{slug}-preview` projects that are DIRECT-UPLOAD (no repo attached), frozen at
2026-08-05. `sync-deploy` pushes to their GitHub repo but nothing rebuilds, so
they will silently miss this and every future site change until proper
`rankai-{slug}` projects exist. (probritegen has no form at all.)

Repeat submissions from one phone return `db:error:409` on
`unique_company_phone` — correct dedupe, not a bug.

**RESOLVED 2026-08-07 (same day):** all 12 configured + 7 live production sites
redeployed and each form individually verified `email:sent` on its real domain.
Two clients had a SECOND, different bug — flood-fixers and prorestoration had NO
recipient email anywhere (brand.email "", companies.email NULL,
transfer_primary_email NULL) so they 502'd even with env vars set; set from
records already held (flood-fixers -> luxurycustomfloors@gmail.com per its
client-record `.contact`, CONFIRM with Gabriel; prorestoration ->
jack@prorestorationca.com). resolveRecipient reads at runtime, so no redeploy.
Cloudflare REPLACES our JSON 502 body with its own error page on proxied
domains — "error code: 502" hides the real reason; hit the pages.dev URL to see it.

**CREW CUTOVER — prepped, blocked on the NS flip only (2026-08-07).**
`browser_agent/playbooks/domain_connect.py` is a SCAFFOLD: dry-run resolves the
target NS correctly, but the live path prints "selectors not pinned yet",
ledgers `needs_supervised_run` and returns 2 WITHOUT opening GoDaddy. It is #4
in the build order and #3 (form_fill) is still CURRENT. The agent cannot do a
cutover today, despite citation playbooks working (their selectors exist).
Done instead: zone a38036f0fd2665651a15aa63e3811922 now holds 13 records — 11
mail/identity mirrored (Proofpoint MX, SPF, MS=ms73215058 M365 verification,
autodiscover, email->secureserver, sip/lyncdiscover/msoid, 2 Teams SRV) plus
apex+www CNAME -> pages.dev proxied; crew3r.com + www attached to the Pages
project; Crew pushed to main and verified (`ghl:"sent"`). Remaining: set NS at
GoDaddy to amos.ns.cloudflare.com / anastasia.ns.cloudflare.com. **Records came
from public DNS enumeration, NOT an authoritative zone-file export — get the
GoDaddy zone file and diff before flipping, enumeration cannot prove
completeness.**

Related: [[site-build-pipeline]], [[client-bootstrap-system]],
[[browser-agent-suite]]
