# Rank AI — SEO Operations Spec

**Last updated:** 2026-05-16
**Status:** System 1 (keyword-researcher) shipped. Systems 2-4 pending.

This doc is the canonical reference for the ongoing SEO operations layer on top of the per-client launch pipeline. It supersedes the earlier "blog routine" sketch with a richer four-system model adapted from NicoSKOOL's the-four-systems (MIT licensed, 2026) and made multi-client native.

The four launch skills (`rank-ai-onboard`, `rank-ai-plan-site`, `rank-ai-build-site`, plus topology/sync-deploy) ship the client's site. **The four operations systems below run continuously after launch** to grow rankings, refresh stale content, and catch regressions before they hurt traffic.

---

## The four systems

| # | System | Skill name | Cadence | Cost / client / month | Purpose |
| - | --- | --- | --- | --- | --- |
| 1 | Keyword Researcher | `rank-ai-keyword-researcher` | Monthly | ~$0.50 | Find new rankable keywords; queue priority-1 items for the writer |
| 2 | Content Writer | `rank-ai-content-writer` (pending) | 1-2× per week | ~$0.80 | Pull from queue, write one post per run, deploy to staging→main |
| 3 | Onsite Audit | `rank-ai-onsite-audit` (pending) | Monthly | ~$0.20 | Lighthouse + on-page health on homepage + priority URLs |
| 4 | Refresh Recommender | `rank-ai-refresh-recommender` (pending) | Monthly | ~$0.05 | GSC 28-day decay scan; classify each alert; queue refreshes |

**Roughly $1.55/client/month** for all four systems combined. At 50 clients: ~$80/month total. At 100 clients: ~$160/month. The bottleneck is API spend, not infrastructure.

---

## Why these four (and not just one "blog routine")

The naïve approach is to write a single "generate the next blog post" routine. That's System 2 only. But that approach silently fails over time because:

- The blog routine runs out of topics (no fresh seeds → repetitive content)
- Published content decays (Google de-ranks posts that lose engagement signals)
- Performance regresses (CWV drops, schema breaks, links go stale)
- Stale audits hide problems (you don't know what's broken until traffic tanks)

The four-system model decouples these concerns:

- **System 1 feeds System 2** — keyword-bank + content-queue keep the writer pointed at the right work.
- **System 4 feeds System 1** — when refresh-recommender flags refresh-class content, it can also surface new-page suggestions back to System 1 for fresh research.
- **System 3 catches the things content alone can't fix** — Lighthouse regressions, missing schema, broken canonicals.

This is more sophisticated than a single cron and is the actual reason ongoing client retention compounds for productized SEO agencies.

---

## Topology — how it lives in the monorepo

```
rank-ai/
├── templates/restoration/
│   ├── seed-keywords.txt                       # industry-canonical (shared across all clients)
│   └── prompts/
│       ├── keyword-researcher.md               # System 1 source-of-truth prompt
│       ├── content-writer.md                   # System 2 source-of-truth prompt (pending)
│       ├── onsite-audit.md                     # System 3 source-of-truth prompt (pending)
│       └── refresh-recommender.md              # System 4 source-of-truth prompt (pending)
│
├── clients/{slug}/
│   ├── keyword-bank.json                       # System 1 state
│   ├── content-queue.json                      # System 1 → System 2 handoff
│   ├── refresh-queue.json                      # System 4 state
│   ├── onsite-audit.json                       # System 3 state
│   ├── image-style-guide.md                    # Consulted by System 2 image gen
│   ├── plan/                                   # from rank-ai-plan-site (Skill 2)
│   └── keywords/runs/{date}-{seed-slug}.csv    # System 1 audit trail
│
└── scripts/                                    # Python orchestration (System 4 GSC pull lives here)
    └── (master scheduler script, pending)
```

State files are per-client. They live in the pipeline monorepo, NOT in the per-client deploy repos. Operational data ≠ site content.

**Why state in the monorepo:** the four-systems' state is read by orchestration scripts + AI agents (Claude/Antigravity). Keeping it in the same repo as the prompts + scripts means a single agent context has everything it needs. Per-client deploy repos stay clean of operational concerns.

---

## System 1 — Keyword Researcher (shipped)

**Skill:** `rank-ai-keyword-researcher`
**Prompt:** `rank-ai/templates/restoration/prompts/keyword-researcher.md`
**Cadence:** Monthly per client (or on-demand when content queue runs thin)

### What it does

1. Picks a seed from `templates/restoration/seed-keywords.txt` (35 industry-canonical restoration seeds) — defaults to the seed whose `last_researched` date is oldest for THIS client
2. Generates AI fan-out via `mcp__dataforseo__ai_optimization_chat_gpt_scraper` + `keyword_ideas` + `related_keywords` (25-40 base variations)
3. **Multi-client geographic fan-out** — for each base variation, generates city-modified variants using the client's `service_areas[]` (e.g., `water damage Seattle`, `Seattle water damage`, `emergency water damage Tacoma`)
4. Scores intent (transactional / commercial / informational / navigational) and difficulty (KD via DataForSEO bulk endpoint)
5. Strict dedup against the client's existing `keyword-bank.json` (no re-researching what's already been seen)
6. Coverage check against the client's `plan/url-plan.json` (if the keyword maps to an existing URL, drop priority and mark `covered_by`)
7. Updates `clients/{slug}/keyword-bank.json` (every researched keyword, any priority)
8. Pushes up to 5 priority-1 items into `clients/{slug}/content-queue.json` (System 2's input)
9. Writes per-run audit CSV
10. Prints a markdown run report

### State schema — `keyword-bank.json`

```json
{
  "last_updated": "2026-05-16",
  "seeds_researched": [
    {"seed": "water damage restoration", "last_researched": "2026-05-16"},
    {"seed": "mold remediation", "last_researched": "2026-04-12"}
  ],
  "keywords": [
    {
      "keyword": "water damage restoration Seattle",
      "seed": "water damage restoration",
      "intent": "transactional",
      "volume": 590,
      "kd": 38,
      "cpc": 14.20,
      "priority": 1,
      "fan_out_parent": "water damage restoration",
      "city_modifier": "Seattle",
      "covered_by": "/service-areas/seattle-wa/water-damage-restoration/",
      "discovered": "2026-05-16",
      "source": "dataforseo_labs_google_keyword_ideas"
    }
  ]
}
```

### State schema — `content-queue.json`

```json
{
  "items": [
    {
      "id": "2026-05-16-what-to-do-after-water-damage-basement",
      "status": "queued",
      "queued_at": "2026-05-16T15:30:00Z",
      "written_at": null,
      "post_url": null,
      "primary_keyword": "what to do after water damage in basement",
      "intent": "informational",
      "volume": 210,
      "kd": 28,
      "fan_out_cluster": ["basement water damage emergency", "wet basement cleanup steps", ...],
      "suggested_slug": "what-to-do-after-water-damage-basement",
      "suggested_title": "What to do after water damage in your basement",
      "target_word_count": 1400,
      "internal_link_targets": ["/services/water-damage-restoration/", "/services/basement-flooding-cleanup/"],
      "service_tags": ["water-damage-restoration", "basement-flooding-cleanup"],
      "city_anchor": null,
      "external_authority_candidates": [],
      "notes": "Lead with the 24-48 hour mold growth window."
    }
  ]
}
```

---

## System 2 — Content Writer (pending)

**Skill name (planned):** `rank-ai-content-writer`
**Prompt (planned):** `rank-ai/templates/restoration/prompts/content-writer.md`
**Cadence:** 1-2× per week per client

### Planned behavior

1. Pop the next queued item from `clients/{slug}/content-queue.json` (highest priority, oldest queued_at first)
2. Read the client's `clients/{slug}/image-style-guide.md` — every image generation call consults this
3. Read the client's `plan-input.json` for brand context, services list, service areas
4. Generate body content via Anthropic (Sonnet 4.6 default; per-archetype overrides possible)
5. Generate hero image via Nano Banana Pro per the style guide
6. Convert PNG → WebP via `image_utils.py` (the path we already built); upload to R2 at `blog/{YYYY}/{MM}/{post-slug}/hero.webp`
7. Write the markdown to `sites/{slug}/src/content/blog/{post-slug}.md` with proper frontmatter
8. Update `content-queue.json` — mark item as `status: written`, set `written_at` and `post_url`
9. Commit the monorepo
10. `sync-deploy --slug {slug} --branch main` (or `staging` for review-required mode)
11. Cloudflare auto-builds → post is live

### Cost guardrails

- Hero image: ~$0.04 (Pro)
- Optional 2 inline images: ~$0.01 each (Flash)
- LLM body content: ~$0.10
- **Total per post: ~$0.06-0.16**
- At 2×/week × 50 clients = ~$60-160/month for all content writing across the portfolio

### Content quality enforcement

Reuses the strict prompts from `templates/astro-starter/prompts/blog-post.md` (the launch-time prompt). Adapted for the ongoing routine but maintaining the same content-differentiation rules.

---

## System 3 — Onsite Audit (pending)

**Skill name (planned):** `rank-ai-onsite-audit`
**Prompt (planned):** `rank-ai/templates/restoration/prompts/onsite-audit.md`
**Cadence:** Monthly per client

### Planned behavior

1. For each client, audit the homepage + the top 2-3 priority URLs (read from `plan/url-plan.json`, sort by priority descending, take top 3)
2. Call `mcp__dataforseo__on_page_lighthouse` for each URL → CWV scores, performance, accessibility, best practices, SEO
3. Call `mcp__dataforseo__on_page_instant_pages` → on-page health: schema, canonicals, security headers, meta tags
4. Compare against the previous audit (`clients/{slug}/onsite-audit.json` — stores last N audits)
5. Flag regressions: CWV score drop ≥ 10 points, missing schema, broken canonical, security header missing
6. Write actionable recommendations report at `clients/{slug}/audits/onsite-{date}.md`

### Cost: ~$0.05 per URL × 3 URLs × 1 run/month = $0.15/client/month. 50 clients = $7.50/month.

### How this differs from `claude-seo:seo-audit`

The user already has a comprehensive audit skill (`claude-seo:seo-audit`) that crawls up to 500 pages with 15 specialists. That's the quarterly deep dive. This System 3 is the **monthly continuous monitoring** — narrower, faster, catches CWV regressions and on-page health issues early. Both should run; they're different cadences and depths.

---

## System 4 — Refresh Recommender (pending)

**Skill name (planned):** `rank-ai-refresh-recommender`
**Prompt (planned):** `rank-ai/templates/restoration/prompts/refresh-recommender.md`
**Cadence:** Monthly per client

### Planned behavior

Two phases:

**Phase 1 — GSC data pull (Python):**
1. For each client, call Google Search Console API for 28-day current vs 28-day previous
2. For each indexed URL on the client's site, compute: position delta, impressions delta, clicks delta, CTR delta
3. Flag URLs by category:
   - **Decaying**: was getting >50 impressions/month, now down ≥50%
   - **Stuck at position 5-15**: ranking exists but not in top 3 (refresh + better intent match could push it up)
   - **Dropped from top 10**: was top 10 last quarter, now position 11-50
   - **CTR outlier**: top-3 ranking with <2% CTR (title/meta description is wrong)
4. Write to `clients/{slug}/refresh-queue.json` with `flag` and raw data

**Phase 2 — Classification (Claude):**
1. Read `refresh-queue.json` + the prompt at `templates/restoration/prompts/refresh-recommender.md`
2. For each alert, classify as one of:
   - `refresh` → full content refresh (Content Writer System 2 picks up, edits the post in place)
   - `quick_fix` → minor edit (meta description rewrite, internal link addition) — done by hand or by a separate one-shot
   - `new_page` → topic isn't actually covered well; feeds back to System 1 as a manual seed
   - `ignore` → seasonal dip, irrelevant query, etc.
3. Push refresh-class items back into the content queue with `status: queued_for_refresh` and `refresh_target_url`
4. Write a human-readable monthly report

### Prerequisites

- **Google Search Console MCP** must be installed and authenticated (Phase 1 of the GSC setup)
- Each client's domain must be **verified in Google Search Console** (one-time per-client manual step during onboarding)

### Cost: ~$0.05/client/month (Claude classification). GSC API is free within quotas.

---

## How the systems chain on a cron

The eventual master scheduler (Python script + launchd plist):

```
Every 1st of the month, 04:00 AM local:
  For each active client:
    1. Run System 1 (keyword-researcher) — picks oldest unresearched seed
    2. Run System 4 Phase 1 (GSC data pull)
    3. Run System 4 Phase 2 (classification, queues refreshes)
    4. Run System 3 (onsite audit, flags regressions)

Every Monday + Thursday, 09:00 AM local (twice-weekly cadence):
  For each active client:
    5. Run System 2 (content-writer), pops one queued item, writes + deploys

The scheduler logs to ~/Library/Logs/rank-ai/ and sends a daily Slack summary
of what got done across the portfolio.
```

This is the productized service in operation: clients pay for ongoing growth, the four-system loop delivers it without operator intervention, you wake up to a portfolio that just keeps publishing + improving.

---

## Cost summary at scale

| Clients | Monthly cost (all 4 systems) |
| --- | --- |
| 1 | ~$1.55 |
| 10 | ~$15 |
| 50 | ~$80 |
| 100 | ~$160 |
| 500 | ~$800 |

API costs (DataForSEO + Anthropic + Gemini for images) scale roughly linearly. The orchestration layer (Cloudflare Pages, R2 storage, GitHub) is essentially free at this scale.

---

## What's still pending (build order)

1. ✅ **System 1 keyword-researcher** — shipped 2026-05-16
2. ⬜ **System 2 content-writer** — next. Reuses the image style guide we just built. Forks NicoSKOOL's content-writer.md adapted for multi-client.
3. ⬜ **System 3 onsite-audit** — adapt NicoSKOOL's onsite-audit. Smallest of the four.
4. ⬜ **System 4 refresh-recommender** — adapt + install GSC MCP. Requires per-client GSC verification step during onboarding (add to `rank-ai-onboard`).
5. ⬜ **Master scheduler script** — single Python orchestrator that loops all active clients × all systems × cron cadences. Replaces the four-systems' per-system launchd plists.

Build one system at a time, test on narestco, validate cost + output quality, then move to the next.

---

*Spec version 1.0 — 2026-05-16. Bump version when adding/removing systems or changing cadence policy. Source attribution: methodology adapted from [NicoSKOOL/the-four-systems](https://github.com/NicoSKOOL/the-four-systems) (MIT, 2026); multi-client topology + restoration-vertical seeds + per-client geographic fan-out are Rank AI extensions.*
