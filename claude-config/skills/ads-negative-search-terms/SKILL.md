---
name: ads-negative-search-terms
description: Weekly search term pruning for a water damage restoration Google Ads campaign. Pulls wasted search terms via API, filters to statistically meaningful candidates (100+ impressions, $10+ wasted), SERP-checks each one for buyer intent via WebSearch, surfaces a verdict table for human approval, then adds approved terms as campaign-level negatives via ads_manager.py. Never auto-pushes — every negative requires explicit user OK. Read find-and-add-negatives.md as the SOP. Use when the user says "prune negatives", "find wasted search terms", "clean up the campaign", "negative keyword audit", "find money-bleeding terms", or "ads-negative-search-terms".
---

# Ads Negative Search Terms

Weekly search term pruning. Pulls the worst-performing search terms from a campaign, checks each one for buyer intent via Google SERP, and adds the confirmed-bad ones as campaign-level negatives after explicit user approval.

**Source of truth:** `rank-ai/Ads/find-and-add-negatives.md` — read it fully on every invocation.

**Key distinction from `ads-negative-kw`:**

| Skill | What it does | When to run |
|-------|-------------|-------------|
| `ads-negative-kw` | Adds the 150-term universal list to a new campaign | Once, at campaign launch |
| `ads-negative-search-terms` | Finds campaign-specific waste from real search data | Weekly, after spend accumulates |

Campaign-level negatives added here are intentionally NOT added to the shared list — "abbotsford" is bad for a Federal Way campaign but fine elsewhere.

**Exception — promote universal patterns:** if a wasted term reflects a pattern common to ALL restoration clients (DIY self-treatment, product-shopping, symptom/research — e.g. "vinegar", "mold killer", "test kit", "symptoms"), don't just negate it on this one campaign — add it to `Ads/universal-negative-keywords.md` §B.6 so every current and future client inherits it via `ads-negative-kw`. Campaign-specific waste (a competitor name, a wrong city, an off-service query) stays campaign-level.

## When to invoke

- "prune negatives for {client}"
- "find wasted search terms in {campaign}"
- "clean up the campaign spend"
- "weekly negative audit"
- "ads-negative-search-terms"
- Run weekly after a campaign has been live 14+ days

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — all paths below are relative to here.

---

## Pre-flight

Read `Ads/find-and-add-negatives.md` fully before proceeding.

Verify:
- [ ] `python3 scripts/ads_manager.py list-campaigns --slug {slug}` succeeds
- [ ] At least one campaign has been running for 14+ days with real spend

If the campaign is under 14 days old, warn the user: "Less than 14 days of data is too noisy — terms with 0 conversions may just need more time. Recommend waiting."

---

## Intake questions

Ask all before any API calls. Pre-fill from `clients/{slug}/plan-input.json` and `clients/{slug}/ads-structure.json` where possible.

1. **Client slug** — list available clients if not provided
2. **Campaign** — show available campaigns from `ads-structure.json` or run `list-campaigns`. Accept campaign name or resource name. Accept `'all'` to scan every active campaign.
3. **Time window** — default: 30 days. Warn if under 14.
4. **Impression threshold** — default: 100. Warn if under 50 ("too noisy — you'll flag terms that just need more time").
5. **Cost threshold** — default: $10. Terms below this aren't worth the time.

**Confirmation gate:**
> "Confirm: pulling search terms from {campaign} over the last {days} days, filtering to terms with ≥{impressions} impressions and ≥${cost} spent with 0 or low conversions, SERP-checking each candidate for intent, then showing you the list before touching anything. Proceed?"

---

## Step 1 — Pull candidates

```bash
cd ~/Desktop/mywebsitecode/rank-ai
set -a; . .env; set +a

python3 scripts/ads_manager.py report \
  --slug {slug} \
  --days {days}
```

If `ads_manager.py` doesn't have a `search-terms` subcommand yet, generate a script `scripts/find_search_term_candidates.py` that:
1. Queries `search_term_view` filtered to the campaign
2. Joins with conversion and cost data
3. Filters: `impressions >= threshold AND (conversions = 0 OR cost_per_conv > campaign_avg_cost_per_conv * 2)`
4. Returns top 20 ranked by wasted spend

Print the raw candidates:
```
RANK · WASTED  · IMPR · CTR  · TERM
1    · $77.25  · 412  · 1.0% · "water damage diy"
2    · $25.27  · 153  · 1.3% · "water damage certification"
...
```

---

## Step 2 — SERP intent check (per candidate)

For each candidate, use `WebSearch` to run a Google search for the term and inspect the first page of results. Apply the intent rubric from the SOP:

| SERP signal | Verdict |
|-------------|---------|
| Job listings (Indeed, LinkedIn, Glassdoor) | ❌ BAD — career intent |
| YouTube tutorials, how-to articles, DIY guides | ❌ BAD — DIY/learn intent |
| Certification or training school pages | ❌ BAD — education intent |
| Wikipedia, news, definitions | ❌ BAD — informational |
| Free templates, free downloads, free tools | ❌ BAD — free intent |
| Competitor service pages (same niche, same geo) | ✅ KEEP — buyer intent |
| Price comparison, "average cost" articles | ⚠ UNCERTAIN — shopper intent (may convert) |
| Mixed results | ⚠ UNCERTAIN — needs human review |

Write a one-line verdict per term: `BAD - job listings dominate`, `KEEP - competitor service pages`, `UNCERTAIN - mixed results`.

---

## Step 3 — Present verdict table

Show the user a clean table before touching anything:

```
RANK · WASTED  · TERM                              · VERDICT
1    · $77.25  · "water damage diy"                · ❌ BAD - YouTube tutorials, DIY guides
2    · $25.27  · "water damage certification"      · ❌ BAD - training school pages
3    · $22.43  · "water damage near me free"       · ❌ BAD - free service listings
4    · $19.10  · "water damage restoration cost"   · ⚠ UNCERTAIN - cost comparison articles
5    · $12.50  · "emergency water damage seattle"  · ✅ KEEP - competitor service pages
```

Then ask:
> "Which should I add as campaign-level negatives? Reply with rank numbers (e.g. '1, 2, 3'), 'all bad', or 'none'."

**Rules:**
- `'all bad'` = only terms marked ❌ BAD — never auto-includes UNCERTAIN
- UNCERTAIN terms always require an explicit rank number from the user
- KEEP terms are never added regardless of what the user says

---

## Step 4 — Add negatives (only after explicit approval)

For each approved term, use `ads_manager.py add-negatives`:

```bash
python3 scripts/ads_manager.py add-negatives \
  --slug {slug} \
  --campaign "{campaign_resource}" \
  --keywords "{term1},{term2}"
```

Default match type: **phrase** — so `"water damage diy"` also blocks `water damage diy repair`, `water damage diy fix`, etc. Use broad only for single-word terms.

Check before adding: if the term already exists as a negative, log a warning and skip — no duplicates.

Print each addition with resource name:
```
✓ "water damage diy" (phrase) → customers/X/campaignCriteria/{id}
✓ "water damage certification" (phrase) → customers/X/campaignCriteria/{id}
```

---

## Step 5 — Report and save runlog

```
✓ Pulled {N} candidates from {campaign} ({days} days)
✓ SERP-checked {N} terms
✓ Added {N} campaign-level negatives
✓ Estimated monthly spend recovery: ${sum of wasted spend for added terms}
✓ Skipped {N} KEEP terms, {N} UNCERTAIN terms (no action taken)

Next steps:
- Negatives take 1-2 hours to propagate — don't expect zero impressions immediately
- Run again in 7 days — most accounts stabilize at 1-3 new negatives/week after 6 weeks
- If you accidentally negated a buyer term: run ads_manager.py remove-negative --term "X" --campaign Y
```

Save a runlog to `clients/{slug}/ads/search-terms-runlog-{date}.md`:
```markdown
# Search Terms Audit — {campaign} — {date}
Days: {days} | Threshold: {impressions} impressions / ${cost}

## Candidates reviewed: {N}
## Added as negatives: {N}
## Estimated recovery: ${amount}/month

### Added
- "term" (phrase) → resource_name

### Kept (buyer intent confirmed)
- "term" — reason

### Uncertain (deferred)
- "term" — reason
```

---

## Failure modes (from SOP)

| Issue | Fix |
|-------|-----|
| "No candidates above threshold" | Campaign is clean OR threshold too high — lower impression threshold to 50 and re-run |
| "Term already exists as negative" | Script checks before adding, logs warning, skips |
| Negatives not showing immediately | Takes 1-2 hours to propagate — expected |
| Accidentally negated a buyer term | Run `ads_manager.py` with a remove-negative subcommand (reversible) |

## Cost expectation

- WebSearch calls: 1 per candidate (up to 20)
- No Anthropic API calls beyond the agent's own reasoning
- Google Ads API: $0
- Wall clock: ~3-5 minutes including SERP checks and user review
