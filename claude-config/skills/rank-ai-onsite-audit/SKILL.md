---
name: rank-ai-onsite-audit
description: Run an onsite SEO health audit on a Rank AI client's live site via DataForSEO Lighthouse + on_page_instant_pages. Audits ~6 priority URLs (homepage, services hub, top 2 service-landing pages, primary service-area, contact) and produces a green/amber/red verdict with per-page issues, template-level fixes, money-page alerts, and month-over-month regression detection vs the prior audit. Use when the user says "audit {client}", "site health for {client}", "lighthouse for {client}", "is {client}'s site healthy", "check technical SEO", or "run system 3". Wraps `templates/restoration/prompts/onsite-audit.md`. System 3 of 4 in the Rank AI SEO operations layer.
---

# Rank AI — Onsite Audit (System 3)

System 3 in the Rank AI SEO operations layer. Driven by `rank-ai/templates/restoration/prompts/onsite-audit.md` — that prompt is the source of truth for methodology, scoring thresholds, state schema, and report format. Read it first on every invocation.

## When to invoke

The user says any of:

- "audit {client}" / "run an audit on {client}"
- "onsite audit" / "system 3" / "site health"
- "lighthouse" / "page speed audit" / "performance audit for {client}"
- "is {client}'s site healthy" / "check technical SEO"

Also invoke unprompted at the start of an SEO ops session if the client's last audit (`clients/{slug}.json -> audit.last_audit_at`) is more than 30 days old.

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — the monorepo. All paths in the prompt are relative to here.

## Pre-flight (every invocation)

1. **Determine the client slug.** Ask via `AskUserQuestion` if not provided. List available clients from `clients/*.json` (excluding subdirectories), showing for each: slug, display_name, build_status, last_audit_at (or "never audited"), and last_audit_verdict.
2. **Validate** the client has `status: "active"` and `build_status` of `pushed_main` or `pushed_staging`. If not, stop and tell the user to run the appropriate earlier skill first (`rank-ai-onboard`, `rank-ai-plan-site`, or `rank-ai-build-site`).
3. **Read the prompt** at `rank-ai/templates/restoration/prompts/onsite-audit.md` FULLY on every invocation. It is the source of truth.

## Run the audit

Follow the prompt exactly. Summary of steps the prompt walks through:

1. Determine the live origin (apex if cut over, else staging Pages preview)
2. Determine the URL list (per-client `audit-urls.txt` if present, else default 6-URL set from `url-plan.json` archetypes)
3. Lighthouse scan per URL via `mcp__dataforseo__on_page_lighthouse` (mobile strategy)
4. On-page instant audit per URL via `mcp__dataforseo__on_page_instant_pages`
5. Aggregate per-URL and site-level verdicts (green / amber / red / error)
6. Detect regressions vs the prior `onsite-audit.json` (verdict transitions, score deltas, new + resolved issues)
7. Write atomic state file at `clients/{slug}/onsite-audit.json`
8. Write markdown report at `clients/{slug}/audit-runs/{YYYY-MM-DD}-onsite-audit.md`
9. Update client record `clients/{slug}.json` with `audit.last_audit_at`, `audit.last_audit_verdict`, `audit.last_audit_report_path`
10. Commit the state file + report + client record to the monorepo (no push to per-client deploy repo — this is operational data, not site content)

## Allowed tools

```
Read, Write, Edit, Bash, WebFetch,
mcp__dataforseo__on_page_lighthouse,
mcp__dataforseo__on_page_instant_pages,
mcp__dataforseo__on_page_content_parsing
```

(Our DataForSEO MCP prefix in `~/.claude.json` is `mcp__dataforseo__`, not `mcp__dfs-mcp__` as in NicoSKOOL's original.)

## Cost expectation

- DataForSEO Lighthouse: ~$0.05 per URL × 6 URLs = $0.30
- DataForSEO instant_pages: ~$0.01 per URL × 6 URLs = $0.06
- Anthropic agent reasoning: ~$0.05-0.15
- **Total: ~$0.40-0.55 per run**
- **Wall clock: 4-8 minutes** (Lighthouse is the bottleneck — DataForSEO's Lighthouse endpoint takes 20-40s per URL)

Monthly per client × 50 clients = ~$25/month industry-wide. Trivial.

## What to print in interactive mode

After the run completes:

1. The summary block from the prompt's Step 9
2. The top section of the markdown report (site rollup + recommended next actions)
3. A short "what's next" block:
   - **If verdict is red or any money-page alert exists** → flag the urgency, ask if the user wants a follow-up Plan to fix the top issue
   - **If verdict is amber** → list the top 1-2 template fixes the user could ship this week
   - **If verdict is green and no regressions** → confirm everything is healthy, suggest the next scheduled run date (30 days out)

## Auto-chain rules

- Do NOT auto-invoke another skill. Onsite audit findings inform human decisions — present them, don't act on them.
- For unattended cron mode (when System 4 + master scheduler ships), the master script aggregates audit verdicts across all clients for the portfolio dashboard.

## State files this skill writes

| Path | Schema | Lifecycle |
| --- | --- | --- |
| `rank-ai/clients/{slug}/onsite-audit.json` | See `templates/restoration/prompts/onsite-audit.md` Step 6 | Overwritten each run (atomic) — only the LATEST audit is canonical |
| `rank-ai/clients/{slug}/audit-runs/{date}-onsite-audit.md` | Per-run markdown report | One per run, never overwritten |
| `rank-ai/clients/{slug}.json` | Client record with `audit.last_audit_*` fields | Merged-updated each run |

The audit state lives only in the pipeline monorepo (`github.com/restorationai/Rank-AI-Pipeline`). It is NOT pushed to per-client deploy repos.

## Error handling

- DataForSEO outage or quota error → surface verbatim, suggest retrying in 10-15 minutes
- Per-URL audit failure (timeout, 4xx, 5xx) → record as `verdict: "error"` with the failure reason. Site rollup proceeds with remaining URLs but flagged
- Slug not found → list available clients
- Client `build_status` not `pushed_*` → tell user to ship the site first
- `url-plan.json` missing AND `audit-urls.txt` missing → ask the user to either run `rank-ai-plan-site` or provide a manual URL list
- Live origin unreachable (DNS/CDN error before Lighthouse even starts) → abort cleanly, do NOT write a partial state file

## Hard rules (also enforced by the prompt)

- ~6 URLs per run by default. Never auto-expand beyond `audit-urls.txt` or the prompt's default archetype set.
- Mobile strategy only (mobile-first indexing is Google's primary ranking signal).
- Real Lighthouse audit IDs only. No paraphrasing.
- Recommendations must be specific and actionable.
- Both state JSON AND markdown report written every successful run.
- Atomic state-file writes. A failed run leaves the prior state intact.
- Never use em dashes or emojis.

## What this skill does NOT do (out of scope)

- Content quality / keyword decay analysis — that's `rank-ai-refresh-recommender` (System 4)
- Backlink audit — out of vertical scope (use `claude-seo:seo-backlinks` if needed)
- Local SEO grid / GBP audit — out of scope (use `claude-seo:seo-maps`)
- Schema validation beyond presence/syntax — for deep schema work use `claude-seo:seo-schema`
- Implementing the recommended fixes — the audit informs, humans (or a different agent in a separate session) execute
