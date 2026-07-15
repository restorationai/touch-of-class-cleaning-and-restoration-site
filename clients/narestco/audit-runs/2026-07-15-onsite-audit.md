# Onsite Audit — National Restoration Construction — 2026-07-15

**Status: ABORTED — audit not performed.**

**Live origin (intended):** https://narestco.com (apex)
**Site verdict:** not computed (no scan data)
**URLs audited:** 0 of 6 intended
**Prior audit:** 2026-06-22 (amber) — preserved, not overwritten

## Why this run aborted

The DataForSEO MCP server (`dataforseo`) never finished connecting during this
invocation. It was reported "still connecting" at session start and, after
roughly 2.5 minutes of waiting plus repeated tool-discovery retries, it had not
registered any tools. Both `mcp__dataforseo__on_page_lighthouse` and
`mcp__dataforseo__on_page_instant_pages` were unavailable for the entire run, and
broad tool searches (`dataforseo`, `lighthouse`, `on page`, `keyword/serp`)
returned only built-in harness tools.

These two MCP tools are the sole data source for Step 2 (Lighthouse) and Step 3
(on-page instant audit). They are the core of the audit, not an optional
enrichment step. With no way to obtain real Lighthouse scores or Core Web Vitals,
and a hard rule against inventing scores, the run cannot produce a valid audit.

Per the atomic-write rule, no state file was written and no prior artifact was
modified:

- `clients/narestco/onsite-audit.json` — UNCHANGED (prior 2026-06-22 audit intact).
- `clients/narestco.json` — UNCHANGED (audit pointer still 2026-06-22).

## Pre-flight completed successfully (for the record)

The following steps ran cleanly before the blocking failure, so a re-run can pick
up from Step 2 with no re-derivation needed:

- Client record loaded. `status=active`, `build_status=pushed_main`. Auditable.
- Live origin resolved to apex: `apex_cutover.completed_at` is set
  (2026-05-17T22:11:55Z), so the origin is `https://narestco.com`. Not staging;
  no noindex/SEO-exclusion caveat would apply.
- No `clients/narestco/audit-urls.txt` present, so URLs were auto-derived
  (Mode B) from `clients/narestco/plan/url-plan.json`.

Intended 6-URL audit set (priority archetypes, higher `priority` value = more
important; service-landing tie at 9.0 broken by document order):

| Slot | Archetype | URL |
| --- | --- | --- |
| 1 | home | https://narestco.com/ |
| 2 | services-hub | https://narestco.com/services/ |
| 3 | service-landing | https://narestco.com/services/water-damage-restoration/ (priority 9.0) |
| 4 | service-landing | https://narestco.com/services/fire-damage-restoration/ (priority 9.0) |
| 5 | service-area | https://narestco.com/service-areas/federal-way-wa/ (city match: Federal Way, WA; no primary flag set) |
| 6 | contact | https://narestco.com/contact/ |

Note: the current url-plan (regenerated 2026-07-15) selects
`fire-damage-restoration` as the second top-priority service-landing. The prior
2026-06-22 audit used `flood-damage-restoration`. On a successful re-run,
`water-damage-restoration` and `/contact/` (and the other four) remain comparable
for regression detection; `fire-damage-restoration` would be new this cycle and
`flood-damage-restoration` would drop out.

## Recommended next action

1. **(blocking, infra)** Re-run the onsite audit once the DataForSEO MCP server
   is confirmed connected. Verify `mcp__dataforseo__on_page_lighthouse` and
   `mcp__dataforseo__on_page_instant_pages` are discoverable before starting the
   scan. No other changes are needed — pre-flight and URL derivation are
   deterministic and will reproduce the set above.

## Notes / caveats

- audit_form_factor would be `desktop` (MCP wrapper does not expose form_factor).
- This report is date-stamped and will be overwritten by a successful re-run on
  the same day. It does not update the client record's `last_audit_report_path`.
