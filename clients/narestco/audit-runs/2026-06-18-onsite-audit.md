# Onsite Audit — National Restoration Construction — 2026-06-18

**Status: ABORTED — scanner backend unavailable. No scores produced.**

**Live origin (intended):** https://narestco.com (apex, post-cutover)
**Site verdict:** not computed (no scan data)
**URLs audited:** 0 of 6 intended
**Prior audit:** 2026-05-17 (apex baseline, verdict amber) — left untouched by this run

## What happened

This run could not execute. The DataForSEO MCP server (`mcp__dataforseo__*`)
did not connect in this CI environment. Both core scan tools the audit depends
on were unavailable after roughly two minutes of connection retries:

- `mcp__dataforseo__on_page_lighthouse` (Lighthouse headline scores + Core Web Vitals)
- `mcp__dataforseo__on_page_instant_pages` (on-page technical checks)

Per the audit hard rules, scores are never invented and a failed run must not
corrupt the prior baseline. No Lighthouse or on-page numbers were fabricated,
the canonical state file `clients/narestco/onsite-audit.json` was left in place
(still the 2026-05-17 apex baseline), and the client record `audit` block was
not modified. This run produced no verdict.

## Independent live-origin check (not from DataForSEO)

A direct HTTP check confirms the site itself is healthy and that the failure is
isolated to the scanner backend, not the client site:

- `GET https://narestco.com/` returned `HTTP/2 200`, served by Cloudflare.
- No `x-robots-tag: noindex` header is present, which is correct for the apex
  production origin (the staging-noindex caveat does not apply to this client).
- Security headers present: `x-content-type-options: nosniff`,
  `referrer-policy: strict-origin-when-cross-origin`.

## URL set that would have been audited

Derived from `clients/narestco/plan/url-plan.json` (no `audit-urls.txt` present),
using the standard 6-URL archetype selection:

| Slot | Archetype | URL |
| --- | --- | --- |
| 1 | home | https://narestco.com/ |
| 2 | services-hub | https://narestco.com/services/ |
| 3 | service-landing | https://narestco.com/services/water-damage-restoration/ |
| 4 | service-landing | https://narestco.com/services/flood-damage-restoration/ |
| 5 | service-area | https://narestco.com/service-areas/federal-way-wa/ |
| 6 | contact | https://narestco.com/contact/ |

This set matches the prior (2026-05-17) audit exactly, so a successful re-run
will produce clean month-over-month deltas against the existing baseline.

## Recommended next actions (priority order)

1. **(blocker)** Re-run this audit once the DataForSEO MCP server is reachable in
   the CI environment. Verify the `dataforseo` MCP server is configured and its
   credentials are present before invoking. Nothing else can proceed without it.
2. **(no-op)** No site changes are warranted from this run. The 2026-05-17 apex
   baseline (verdict amber, two template-level issues: title length over 65 chars
   on all 6 pages, and one render-blocking script plus one render-blocking
   stylesheet in the layout on all 6 pages) remains the last known state and is
   the action list until a fresh scan supersedes it.

## Notes / caveats

- No state file was written this run (atomic-write rule: a failed run must not
  overwrite the prior audit). `clients/narestco/onsite-audit.json` is unchanged.
- The client record `clients/narestco.json` `audit` block is unchanged; it still
  reflects the 2026-05-17 apex baseline.
- Cost for this run was effectively zero: no Lighthouse or instant_pages calls
  were billed because the scanner backend never connected.
