---
name: ads-negative-kw
description: One-time setup — build a tailored negative keyword list for a water damage restoration client by reading universal-negative-keywords.md (sections A universal + B.1 trades + C geographic), preview the full list for approval, then push to Google Ads via ads_manager.py. Run once per campaign at setup time. Not for weekly search-term pruning — that's the find-and-add-negatives workflow. Use when the user says "add negatives", "add negative keywords", "set up negatives for {client}", or "ads-negative-kw".
---

# Add Negatives (One-Time Campaign Setup)

Reads `Ads/universal-negative-keywords.md`, builds a tailored list for the client, previews it, then pushes to Google Ads via `scripts/ads_manager.py add-negatives`. Run **once per campaign** at launch — not for weekly maintenance.

**Source of truth:** `rank-ai/Ads/universal-negative-keywords.md` — read it fully on every invocation.

## When to invoke

- "add negatives for {client}"
- "set up negative keywords for the {service} campaign"
- "add the universal negative list to {client}"
- "add-negatives"
- Automatically after `generate-ads` completes if the campaign is being set up for the first time

**Not this skill:** if the user says "find search terms bleeding money", "prune negatives", "weekly negative review" — that's `find-and-add-negatives` (Step 7 workflow).

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — all paths below are relative to here.

## Pre-flight

1. **Read `Ads/universal-negative-keywords.md` fully** before doing anything else.
2. **Determine inputs.** Ask via `AskUserQuestion` if not provided:
   - `slug` — client slug
   - `campaign` — Google Ads campaign resource name (`customers/{cid}/campaigns/{id}`). If unknown, run `python3 scripts/ads_manager.py list-campaigns --slug {slug}` to find it.
3. **Load client context** from `clients/{slug}/plan-input.json` to get `service_areas` (for geographic negatives) and `competitors` if present.
4. **Check if already run.** Look for `clients/{slug}/ads/negatives-applied.json`. If it exists, warn the user: "Negatives were already applied on {date}. Run find-and-add-negatives for weekly pruning instead." Proceed only if user confirms.
5. **Source env:** `set -a; . rank-ai/.env; set +a`

## Build the keyword list

Assemble from the spec file in 4 layers:

**Layer 1 — Section A (Universal, always include all 150 terms)**
All 7 sub-sections: job seekers, DIY/how-to, education/training, free/discount, informational research, customer support, restricted/unsafe.

**Layer 2 — Section B.1 (Trades — always include for restoration clients)**
The plumbing/HVAC/electrical/roofing block: parts, supplies, wholesale, fitting, diagram, schematic, manual, spec sheet, etc.

**Layer 2b — Section B.6 (Restoration DIY/product/symptom — ALWAYS include for restoration clients)**
The water/fire/mold self-treatment + product-shopping + symptom block: vinegar, bleach, borax, mold killer, mold remover, test kit, symptoms, what kills mold, etc. (42 terms). This is the cluster that bleeds restoration budget on DIY researchers — the generic A.2 DIY list misses it. Chosen so none block a service ("test kit" ≠ "mold testing", "mold remover" ≠ "mold removal").

**Layer 3 — Section C (Geographic — generate from client's service areas)**
Pull `service_areas` from `clients/{slug}/plan-input.json`. Block all major cities/regions in the same country that are NOT in the service area. Use the template from §C.

**Layer 4 — Section D (Competitor brands — case-by-case)**
If `clients/{slug}/plan-input.json` has a `competitors` field, ask the user: "Add competitor brand names as negatives on this campaign? (Only do this if you don't have a separate Conquest campaign.)"

## Match type rules (from §E of the spec)

- Single words → **broad** (e.g. `jobs`, `free`, `diy`)
- Multi-word phrases → **phrase** with quotes (e.g. `"how to fix"`, `"plumber salary"`)
- Precise queries to block without blocking variants → **exact** with brackets

## Preview before pushing

Output the assembled list to `clients/{slug}/ads/negatives-preview-{date}.txt`:

```
# Negative Keywords Preview — {client} · {campaign} · {date}
# Total: {N} keywords
# Layers: Universal (150) + Trades (19) + Geographic ({N}) + Competitor ({N})

## Match type: BROAD
jobs
free
diy
...

## Match type: PHRASE
"how to fix"
"license requirements"
...

## Match type: EXACT
[not applicable for this run]

## Geographic negatives (outside service area)
calgary
edmonton
...

## DO NOT ADD (buyer-intent terms — from §F of spec)
# affordable, near me, quote, price, cost, best, hire, local, emergency
# These are NOT negatives — they're high-intent buyer signals
```

**Stop here and show the preview.** Ask: "Ready to push {N} negative keywords to campaign `{campaign}`?"

## Push to Google Ads (only after explicit user approval)

The `add-negatives` subcommand takes a comma-separated keyword string:

```bash
cd ~/Desktop/mywebsitecode/rank-ai
set -a; . .env; set +a

python3 scripts/ads_manager.py add-negatives \
  --slug {slug} \
  --campaign "{campaign_resource}" \
  --keywords "{comma_separated_keyword_list}"
```

If the list exceeds ~200 keywords, batch into multiple calls of ~100 each to stay within API limits.

Confirm: print the count of negatives added.

## Mark as done

Write `clients/{slug}/ads/negatives-applied.json`:

```json
{
  "applied_at": "{ISO date}",
  "campaign": "{campaign_resource}",
  "total_keywords": {N},
  "layers": {
    "universal": 150,
    "trades": 19,
    "restoration_diy": 42,
    "geographic": {N},
    "competitors": {N}
  },
  "preview_file": "ads/negatives-preview-{date}.txt"
}
```

## What this skill does NOT do

- **Weekly search-term pruning** — that's `find-and-add-negatives` (reads the Search Terms report, finds spend with 0 conversions, proposes additions with verdicts before touching anything)
- **Shared Negative Keyword Lists** — `ads_manager.py add-negatives` adds campaign-level negatives directly. If you later want a Shared List (Tools → Shared Library in Google Ads UI), do that manually and reuse the `negatives-preview-{date}.txt` file as the paste source.

## Cost expectation

- No Anthropic API calls
- Google Ads API write: $0
- Wall clock: ~3 minutes including preview review
