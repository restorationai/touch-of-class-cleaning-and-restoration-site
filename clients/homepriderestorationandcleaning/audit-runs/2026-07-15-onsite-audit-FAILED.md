# Onsite Audit — Home Pride Restoration and Cleaning LLC — 2026-07-15 (RUN ABORTED)

**Status:** FAILED — no scan performed. No scores were collected.
**Reason:** The DataForSEO MCP server (`dataforseo`) never finished connecting in this CI environment. The two required tools, `mcp__dataforseo__on_page_lighthouse` and `mcp__dataforseo__on_page_instant_pages`, did not register after repeated retries over roughly two minutes, so Step 2 (Lighthouse scan) and Step 3 (on-page instant audit) could not run.

Per the audit hard rules ("Never invent scores" and "Atomic state-file writes only — a failed run should not corrupt the prior audit"), this run made no fabricated data and did not overwrite the canonical state file or the client record. The prior audit remains authoritative.

## Pre-flight results (these did complete)

- **Client record:** `status = active`, `build_status = pushed_main`. Valid for audit.
- **Live origin:** apex production. `apex_cutover.completed_at = 2026-06-18T00:06:15Z`, so `live_origin = https://homepriderestorationandcleaning.com` (`live_origin_source = apex`).
- **Apex reachability:** `curl -sI https://homepriderestorationandcleaning.com/` returned HTTP 200 with no `x-robots-tag: noindex` header, so no staging SEO-exclusion correction would have applied. SEO would have counted toward the verdict.
- **URL mode:** No `clients/homepriderestorationandcleaning/audit-urls.txt` present, so Mode B (auto-derive from `url-plan.json`) was used.
- **Prior audit:** `clients/homepriderestorationandcleaning/onsite-audit.json` exists (generated 2026-06-22T19:40:00Z, verdict amber). Regression detection was armed and would have run.

## URL set that would have been audited (6)

| Slot | Archetype | URL |
| --- | --- | --- |
| 1 | home | https://homepriderestorationandcleaning.com/ |
| 2 | services-hub | https://homepriderestorationandcleaning.com/services/ |
| 3 | service-landing | https://homepriderestorationandcleaning.com/services/water-damage-restoration/ (priority 9.0) |
| 4 | service-landing | https://homepriderestorationandcleaning.com/services/fire-damage-restoration/ |
| 5 | service-area | https://homepriderestorationandcleaning.com/service-areas/saratoga-springs-ut/ |
| 6 | contact | https://homepriderestorationandcleaning.com/contact/ |

## What was NOT written

- `clients/homepriderestorationandcleaning/onsite-audit.json` — left unchanged (prior 2026-06-22 audit preserved).
- `clients/homepriderestorationandcleaning.json` `audit` block — left unchanged.

## Remediation

Re-run this audit once the DataForSEO MCP server is reachable (verify credentials/connectivity for the `dataforseo` MCP server in the CI runner). The pre-flight above is deterministic and will reproduce the same 6-URL set.

## Notes / caveats

- No em dashes or emojis are used per report style rules.
- This is a non-canonical failure note; it does not replace the state file the master scheduler consumes.
