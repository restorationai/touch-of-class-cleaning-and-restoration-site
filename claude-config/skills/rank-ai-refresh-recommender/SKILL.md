---
name: rank-ai-refresh-recommender
description: Find URLs on a Rank AI client's site that need content refresh by combining sitemap + page-level date extraction (v1) and (in v2) Google Search Console indexing flags. Produces a prioritized refresh queue with per-URL actions — refresh content, fix canonical, request indexing, audit then decide — and dedupes against System 2's content queue so we never recommend work already in flight. Use when the user says "what needs refreshing for {client}", "find stale content", "check indexing for {client}", "run system 4", or "refresh recommender". Wraps `scripts/refresh_scorer.py` (Layer 1) + `templates/restoration/prompts/refresh-recommender.md` (Layer 2). System 4 of 4 in the Rank AI SEO operations layer.
---

# Rank AI — Refresh Recommender (System 4)

System 4 in the Rank AI SEO operations layer. Two-layer architecture:

- **Layer 1** — `rank-ai/scripts/refresh_scorer.py` pulls the sitemap, extracts publish/modify dates per URL (sitemap lastmod, JSON-LD, article meta, `<time>`), and flags `stale_12mo` / `aging`. Outputs `clients/{slug}/refresh-candidates.json`.
- **Layer 2** — `rank-ai/templates/restoration/prompts/refresh-recommender.md` reads the candidates, dedupes against the content queue, classifies actions, prioritizes, and writes the refresh queue + markdown report.

**v1 = sitemap-only.** Google Search Console indexing flags (`not_indexed`, `index_warning`) and their corresponding actions (`request_indexing`, `fix_canonical`) are deferred to v2 when per-client GSC OAuth is set up. The scorer has a `gsc_inspect()` stub that v2 can fill in without restructuring.

## When to invoke

The user says any of:

- "what needs refreshing for {client}" / "find stale content for {client}"
- "refresh recommender" / "system 4"
- "check indexing for {client}" (v2 only — flag if GSC not yet enabled)
- "run the monthly content audit for {client}"

Also invoke unprompted at the start of an SEO ops session if the client's `refresh.last_run_at` is more than 30 days old AND System 3 audit already ran this month.

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — the monorepo. All paths are relative.

## Pre-flight (every invocation)

1. **Determine the client slug.** Ask via `AskUserQuestion` if not provided. List from `clients/*.json`, showing `slug`, `display_name`, `build_status`, `refresh.last_run_at` (or "never"), and `audit.last_audit_at` (System 3 should ideally run first).
2. **Validate** the client has `status: "active"` and `build_status` of `pushed_main` or `pushed_staging`. If not, stop.
3. **Read the prompt** at `rank-ai/templates/restoration/prompts/refresh-recommender.md` FULLY on every invocation. It is the Layer-2 source of truth.

## Run the recommender

### Step A — Run Layer 1 (Python)

```bash
set -a; . /Users/santino/Desktop/mywebsitecode/rank-ai/.env; set +a
python3 /Users/santino/Desktop/mywebsitecode/rank-ai/scripts/refresh_scorer.py --slug {slug}
```

This produces `clients/{slug}/refresh-candidates.json`. Watch for:

- "No sitemap discovered" — fail. The client's site must be live with a sitemap. Tell the user to verify the site or pass `--force-origin`.
- "Inspected: 0" — empty sitemap or all-filter-stripped. Surface the issue.

For Rank AI clients pre-apex-cutover, the scorer hits `staging.rankai-{slug}.pages.dev` by default. Note this in the report — the date extraction will work the same, but if the user wants apex-side data (e.g. they care about legacy URLs on the old host), they need `--force-origin`.

### Step B — Run Layer 2 (the prompt)

Follow `templates/restoration/prompts/refresh-recommender.md` exactly. It walks through:

1. Read candidates + content-queue + url-plan
2. Skip URLs that are fresh, already-handled, or have unresolvable dates
3. Classify each remaining URL into `refresh` or `audit_then_decide` (v1 actions)
4. Assign priority (1-4)
5. Build `refresh-queue.json` (atomic write)
6. Write `refresh-runs/{date}-refresh-recommender.md`
7. Update `clients/{slug}.json` with `refresh.last_run_*` fields
8. Print summary
9. Commit to monorepo (no push to per-client deploy repo)

## Allowed tools

```
Read, Write, Edit, Bash
```

No MCPs required in v1 (the scorer does its own HTTP fetches). v2 will add `mcp__gsc__url_inspection` or equivalent.

## Cost expectation

- Layer 1 (Python): $0 — no paid API calls in v1
- Layer 2 (agent reasoning): ~$0.05-0.15 — classifying a few dozen candidates and writing a markdown report
- **Total: ~$0.05-0.15 per run**
- **Wall clock: 2-5 minutes** (Layer 1 fetches HTML for each URL, paced by network)

Monthly per client × 50 clients = ~$5/month industry-wide. Trivial.

## What to print in interactive mode

After the run completes:

1. Layer 1's stdout summary (it prints flag counts as it runs)
2. Layer 2's Step-7 summary
3. The top of the markdown report (summary block + top 5 recommended actions)
4. A short "what's next" block:
   - **If any priority-1 items exist** → highlight them; offer to push the first one into `content-queue.json` as a refresh task for System 2
   - **If only priority-3/4 items** → tell the user this can wait; suggest checking again next month
   - **If empty queue** → confirm everything is fresh; suggest the next scheduled run date

## Auto-chain rules

- Do NOT auto-push refresh items into `content-queue.json`. The user controls writing cadence. Offer it; let the user say yes.
- For unattended cron mode (master scheduler), the master script can apply a configured policy (e.g. "always enqueue priority-1 refresh items unless content-queue is already > 10 items deep").

## State files this skill writes

| Path | Schema | Lifecycle |
| --- | --- | --- |
| `rank-ai/clients/{slug}/refresh-candidates.json` | Layer 1 output | Overwritten each run (latest canonical) |
| `rank-ai/clients/{slug}/refresh-queue.json` | Layer 2 output | Overwritten each run, preserving items with status `in_progress` or `completed` if still flagged |
| `rank-ai/clients/{slug}/refresh-runs/{date}-refresh-recommender.md` | Per-run markdown report | One per run, never overwritten |
| `rank-ai/clients/{slug}.json` | Client record with `refresh.last_run_*` fields | Merged-updated each run |

All in the monorepo. Not pushed to per-client deploy repos.

## Error handling

- No sitemap discoverable → surface verbatim, suggest `--force-origin`
- All URLs have `date_source: none` → likely the site doesn't expose date metadata. Surface as a known gap, suggest adding JSON-LD `dateModified` to the layout. Empty queue this run.
- Slug not found → list available clients
- Layer 1 script fails → do not proceed to Layer 2. Surface the Python error.
- Filesystem permission errors → fail loudly, do NOT corrupt the existing queue file (atomic writes only)

## Hard rules (also enforced by the prompt)

- Skip URLs already in `content-queue.json` with status `queued|in_progress|needs_review`
- Recommendations must be concrete + specific (no "improve content")
- Cite `date_source` so the user can audit
- No fabricated dates or flags
- Atomic state-file writes
- Never use em dashes or emojis

## What this skill does NOT do (out of scope)

- Actually rewrite content — that's `rank-ai-content-writer` (System 2) acting on a refresh-tagged queue item
- Indexing-status detection in v1 — deferred to v2 with GSC OAuth
- Backlink decay analysis — out of scope (use `claude-seo:seo-backlinks`)
- Content quality scoring — out of scope, different problem

## v2 roadmap (when GSC OAuth gets set up)

The clean hooks are already in place:

1. Fill in `scripts/refresh_scorer.py:gsc_inspect()` to call GSC URL Inspection API per URL
2. Per-client OAuth tokens land in `rank-ai/.env` as `GSC_OAUTH_*_NARESTCO`, etc., or a per-client `clients/{slug}/.gsc-token.json` (gitignored)
3. The Layer-2 prompt already enumerates `request_indexing` + `fix_canonical` actions — they'll start firing automatically once `gsc_enabled: true`
4. Priority-1 not-indexed money pages will surface immediately on the next run

Estimated v2 build: 1-2 hours including GSC OAuth flow + per-client verification helper.
