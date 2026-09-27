---
name: rank-ai-keyword-researcher
description: Find new SEO-rankable keywords for a Rank AI restoration client via AI fan-out + DataForSEO scoring. Deduplicates against the client's existing keyword bank and content queue. Pulls per-client geography from plan-input.json to generate city × service keyword variations. Adds priority-1 items to the client's content queue for Skill `rank-ai-content-writer` to write next. Use when the user says "research keywords for {client}", "find new topics", "fill the content queue", "expand keyword coverage", or "what should we write about". Wraps `templates/restoration/prompts/keyword-researcher.md` and the dataforseo MCP. System 1 of 4 in the Rank AI SEO operations layer.
---

# Rank AI — Keyword Researcher (System 1)

Skill 1 in the Rank AI SEO operations layer. Driven by `rank-ai/templates/restoration/prompts/keyword-researcher.md` — that prompt is the source of truth for methodology, scoring, dedup, and output schemas. Read it first on every invocation.

## When to invoke

The user says any of:

- "research keywords for {client}" / "find topics for {client}"
- "fill the content queue for {client}"
- "what should we write about for {client}"
- "expand keyword coverage on {seed}"
- "run keyword researcher" / "system 1"

Also invoke unprompted at the start of an SEO operations session if the client's content queue has fewer than 5 priority-1 items.

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — the monorepo. All paths in this skill are relative to here.

## Pre-flight (every invocation)

1. **Determine the client slug.** Ask the user via `AskUserQuestion` if not provided. Show available clients by listing `rank-ai/clients/*.json` files (excluding subdirectories). For each, show: slug, display_name, status, plan_status, and the count of priority-1 items already in their content queue (read `clients/{slug}/content-queue.json` if it exists, else 0).
2. **Validate** the client record has `status: "active"` and `plan_status: "planned"`. If either is missing, stop and tell the user which prerequisite skill to run (`rank-ai-onboard` or `rank-ai-plan-site`).
3. **Read the prompt** at `rank-ai/templates/restoration/prompts/keyword-researcher.md`. Read it FULLY on every invocation. It is the source of truth.

## Determine the seed

Three modes:

1. **User-specified seed** ("research keywords for narestco on water damage") → use the explicit seed.
2. **Pick oldest from industry list** (default — most common) → read `rank-ai/templates/restoration/seed-keywords.txt` and pick the seed whose `last_researched` date in the client's `clients/{slug}/keyword-bank.json -> seeds_researched[]` is oldest or never. Tell the user which seed you picked and why.
3. **Force re-research** → user explicitly says "re-research X" or includes "--force". Bypass the 30-day cooldown but flag it.

## Run the researcher

Follow the prompt EXACTLY. Key steps the prompt walks through:

1. Load the per-client keyword bank + content queue
2. AI fan-out via `mcp__dfs-mcp__ai_optimization_chat_gpt_scraper`, `mcp__dfs-mcp__dataforseo_labs_google_keyword_ideas`, `mcp__dfs-mcp__dataforseo_labs_google_related_keywords`
2b. **PPC money-keyword feed (NEW)** — if `clients/{slug}/keyword-research.json` exists (written by the ads side via Google Ads `KeywordPlanIdeaService`), fold its keywords into the candidate pool. These carry REAL Google search volume + CPC and are already commercially validated — no need to estimate their value. No-op if the file doesn't exist.
3. **Geographic fan-out** — generate `{variation} {city}` and `{city} {variation}` versions using the client's `service_areas[]` (this is the Rank AI multi-client adaptation)
4. Batch keyword difficulty via `mcp__dfs-mcp__dataforseo_labs_bulk_keyword_difficulty`
5. Classify intent (transactional / commercial / informational / navigational)
6. Score priority (1 = queue, 2 = bank only, 3 = park).
   **Money-keyword rule (NEW):** if a term is BOTH high-volume AND high-CPC for the client's service (top CPC tier — someone's paying real money to rank for it), treat it as strong buyer intent → bump to priority 1 and tag `ppc_validated` in the keyword bank, so we write a page and rank for it organically too.
7. Coverage check against `clients/{slug}/plan/url-plan.json` (and live sitemap if cut-over)
8. Update `clients/{slug}/keyword-bank.json`
9. Push up to 5 priority-1 items into `clients/{slug}/content-queue.json`
10. Write CSV audit trail to `clients/{slug}/keywords/runs/{date}-{seed-slug}.csv`
11. Write a markdown run report (printed to stdout)

## Allowed tools

```
Read, Write, Edit, Bash, WebFetch,
mcp__dataforseo__ai_optimization_chat_gpt_scraper,
mcp__dataforseo__dataforseo_labs_google_keyword_ideas,
mcp__dataforseo__dataforseo_labs_google_keyword_suggestions,
mcp__dataforseo__dataforseo_labs_google_related_keywords,
mcp__dataforseo__dataforseo_labs_google_keyword_overview,
mcp__dataforseo__dataforseo_labs_bulk_keyword_difficulty,
mcp__dataforseo__dataforseo_labs_search_intent
```

(Note: our DataForSEO MCP prefix in `~/.claude.json` is `mcp__dataforseo__`, not `mcp__dfs-mcp__` as in NicoSKOOL's original. Reference the right namespace.)

## Cost expectation

- 1 seed × ~25-40 fan-out variations × 8-10 cities = ~200-400 candidate keywords pre-dedup
- DataForSEO calls: ~5-8 per run
- Anthropic API for the agent's reasoning: ~$0.30-0.80 per run
- Total per run: ~$0.40-1.00
- Wall clock: 5-10 minutes

If you run this monthly per client × 50 clients = ~$25/month industry-wide. Trivial.

## What to print in interactive mode

After the run completes, show the user:

1. The run report (from the prompt's Step 9 — it generates this)
2. A short "what's next" block:
   - **If the content queue now has ≥ 5 priority-1 items** → offer to invoke `rank-ai-content-writer` (System 2) to write the next post
   - **If the queue is still thin (< 5)** → tell the user the next seed in line and offer to run again immediately
   - **If the queue is healthy and we're done for the month** → suggest setting up the scheduled cron via `/schedule create` (or pointing to the master scheduler when System 4 is shipped)

## Auto-chain rules

- After a successful run, the queue depth check determines the next-step suggestion (see above)
- Don't auto-invoke the content-writer skill — surface it as a suggestion. The user controls writing cadence
- For unattended cron mode (when System 4 + master scheduler ships), the master script will chain automatically

## State files this skill writes

| Path | Schema | Lifecycle |
| --- | --- | --- |
| `rank-ai/clients/{slug}/keyword-bank.json` | `{keywords: [...], seeds_researched: [...], last_updated}` | Created on first run; appended on every subsequent run |
| `rank-ai/clients/{slug}/content-queue.json` | `{items: [...]}` | Created on first run; appended only with priority-1 items |
| `rank-ai/clients/{slug}/keywords/runs/{date}-{seed-slug}.csv` | Per-run audit trail | One per run, never overwritten |

The pipeline monorepo commits these via the normal `git add` + `git commit` flow. They are NOT pushed to per-client deploy repos (this is operational data, not site content) — they live only in the monorepo at `github.com/restorationai/Rank-AI-Pipeline`.

## Error handling

- DataForSEO outage or quota error → surface verbatim, suggest retrying later
- Slug not found → list available clients
- Client `plan_status` not "planned" → tell user to run `rank-ai-plan-site` first
- Seed already researched within 30 days → tell user, suggest different seed or `--force`
- AI fan-out returned zero usable variations → log under `## Notes` in the report and either re-roll with a related seed or end the run cleanly

## Hard rules (also enforced by the prompt)

- One seed per run. Stop after one seed.
- Maximum 5 queue items added per run (queue should grow steadily, not in bursts).
- Never write outside the slug's own files.
- Never fabricate DataForSEO data. Real responses only, null if unknown.
- Never use em dashes or emojis.

## What this skill does NOT do (out of scope)

- Write blog posts — that's `rank-ai-content-writer` (System 2)
- Onsite audits — that's `rank-ai-onsite-audit` (System 3)
- Content refresh / decay detection — that's `rank-ai-refresh-recommender` (System 4)
- Generate images — image gen is per-client and triggered by the writer skill
- Cross-client analysis — each client's keyword bank is isolated. To do portfolio-level analysis, the master scheduler or a separate analytics skill would aggregate
