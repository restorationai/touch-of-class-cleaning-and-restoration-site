---
name: ads-setup
description: Full Google Ads setup orchestrator for a Rank AI restoration client. Runs all 5 setup skills in sequence — ads-campaigns → ads-generate-ads → ads-negative-kw → ads-landing-page → ads-tracking — collecting all inputs upfront in one consolidated pass, then executing each phase with clear progress markers and natural approval gates. Run this instead of invoking each skill manually. Does NOT include ads-negative-search-terms (that runs weekly after 14+ days of live data). Use when the user says "set up ads for {client}", "run the full ads setup", "launch ads for {client}", "ads-setup", or "set up Google Ads end to end".
---

# Ads Setup — Full Launch Orchestrator

Runs the complete Google Ads launch sequence for a restoration client in one session:

| Phase | Skill | What it does |
|---|---|---|
| 1 | `ads-campaigns` | Scaffold campaigns, ad groups (city + intent), keywords, placeholder RSAs |
| 2 | `ads-generate-ads` | Replace placeholder RSAs with optimized 3-angle copy for all ad groups |
| 3 | `ads-negative-kw` | Add the 150-term universal negative keyword list to every campaign |
| 4 | `ads-landing-page` | Generate city + intent landing pages, deploy to Cloudflare |
| 5 | `ads-tracking` | Create click-to-call conversion action, wire gadsId + call label into brand.ts, warm-pixel audience |

**Not included:** `ads-negative-search-terms` — that runs weekly after the campaign has 14+ days of live data. Remind the user of this at the end.

## When to invoke

- "set up Google Ads for {client}"
- "run the full ads setup for {client}"
- "launch ads for {client}"
- "ads-setup"

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — all paths below are relative to here.

---

## Pre-flight — read all sub-skill files

Before doing anything else, read all 5 sub-skill files in full. They are the source of truth for each phase — this orchestrator only controls sequencing and input collection.

```
rank-ai/Ads/build-your-first-skag.md
rank-ai/Ads/anatomy-of-a-good-ad.md
rank-ai/Ads/ad-assets-best-practices.md
rank-ai/Ads/universal-negative-keywords.md
rank-ai/Ads/setup-conversion-tracking-and-audience.md
```

Also load:
- `clients/{slug}/plan-input.json` — services, service_areas, domain, brand, ads_customer_id
- `clients/{slug}/ads-structure.json` — existing scaffold state (skip phases that are already done)

---

## Step 0 — Consolidated intake (ask everything upfront)

Ask for the client slug first. Then load `clients/{slug}/plan-input.json` and pre-fill every field you can from it. Only ask about fields that are missing or that the user may want to change.

Present all intake questions in **one single `AskUserQuestion` batch** — do not interrupt the user between phases for questions that can be answered now.

### Questions to ask (skip any already in plan-input.json)

1. **Country** — for geo targeting + country exclusions
2. **Service areas + radius** — confirm or extend `service_areas[]` from plan-input.json
3. **Services to advertise** — confirm or narrow `services[]` from plan-input.json (user may want to start with a subset)
4. **Website URL / domain** — for Final URLs and landing pages
5. **Daily budget per campaign** — default $50/day if unsure
6. **Target CPA** — skip if unknown (start with Maximize Conversions)
7. **Google Ads Customer ID** — check `ads_customer_id` in plan-input.json first
8. **Lead value** — for the click-to-call conversion action. Ask: "What's a phone lead worth in dollars? Use: average job value × close rate (e.g. $3,000 job × 30% close = $900)."

### Confirmation gate before any API calls

Show a summary table covering all 5 phases, then ask once:

```
=== Ads Setup Plan — {display_name} ===

Phase 1 · Campaign Structure
  Services:      {N} ({list})
  Cities:        {M} ({list})
  Ad groups:     {N × M city SKAGs} + {N × 7 intent SKAGs} = {total}
  Budget:        ${budget}/day per campaign
  Bidding:       Maximize Conversions (no target CPA)
  Customer ID:   {id}

Phase 2 · RSA Generation
  Ad groups:     {total} ad groups × 3 RSAs each = {N} RSAs to generate
  Estimated cost: ~$0.05–0.15 per ad group (Anthropic API)

Phase 3 · Negative Keywords
  Universal list: 150 terms + trades block + geographic exclusions
  Applied to:    all {N} campaigns

Phase 4 · Landing Pages
  City pages:    {N × M} pages
  Intent pages:  {N × 7} pages
  Total:         {total} pages → /lp/{slug}/
  Deploy:        Cloudflare Pages via sync-deploy

Phase 5 · Conversion Tracking (click-to-call)
  Conversion action: Lead · Phone Call · ${lead_value} value
  Warm-pixel audience: 540 days · attached at +50% bid
  Fires on: tap of any phone CTA (tel: link) on the LPs

Everything in Phases 1–2 will be created PAUSED until you explicitly unpause.
```

Ask: "Ready to begin the full setup? This will take approximately 15–30 minutes."

Do not proceed until the user confirms.

---

## Phase 1 — Campaign Structure (`ads-campaigns`)

Follow `ads-campaigns/SKILL.md` exactly. Use the inputs collected in Step 0 — do not re-ask questions already answered.

Progress marker at start:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1 OF 5 · Campaign Structure
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Key steps:
1. Update `clients/{slug}/plan-input.json` with any new fields from intake
2. Run dry run: `python3 scripts/ads_manager.py scaffold --slug {slug} --dry-run`
3. Show dry-run output. Ask: "Does this structure look right? Proceed with the real build?"
4. Run real scaffold: `python3 scripts/ads_manager.py scaffold --slug {slug}`
5. Save structure to `clients/{slug}/ads-structure.json`

At completion, print:
```
✓ Phase 1 complete — {N} campaigns, {total} ad groups scaffolded (all PAUSED)
```

---

## Phase 2 — RSA Generation (`ads-generate-ads`)

Follow `ads-generate-ads/SKILL.md` exactly. The slug and matrix are already known — skip the intake questions, go straight to generation.

Progress marker:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2 OF 5 · RSA Generation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Key steps:
1. Read both spec files (`anatomy-of-a-good-ad.md`, `ad-assets-best-practices.md`)
2. Read `clients/{slug}/ads-structure.json` for ad group resource names
3. Generate 3 RSAs (Speed / Trust / Value) for every ad group in the matrix
4. Output consolidated preview to `clients/{slug}/ads/preview-all-{date}.md`
5. Ask: "Ready to push all RSAs as paused ads?"
6. Push on approval

At completion:
```
✓ Phase 2 complete — {N} RSAs pushed (paused) across {total} ad groups
```

---

## Phase 3 — Negative Keywords (`ads-negative-kw`)

Follow `ads-negative-kw/SKILL.md` exactly. Pull campaign resource names from `clients/{slug}/ads-structure.json`.

Progress marker:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3 OF 5 · Negative Keywords
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Key steps:
1. Read `Ads/universal-negative-keywords.md`
2. Build the 4-layer list (Universal + Trades + Geographic + Competitor)
3. Output preview to `clients/{slug}/ads/negatives-preview-{date}.txt`
4. Ask: "Ready to push {N} negative keywords to all {N} campaigns?"
5. Push on approval — loop over every campaign in the structure

At completion:
```
✓ Phase 3 complete — {N} negative keywords applied to {N} campaigns
```

---

## Phase 4 — Landing Pages (`ads-landing-page`)

Follow `ads-landing-page/SKILL.md` exactly.

Progress marker:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 4 OF 5 · Landing Pages
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

The LPs are phone-call-only (no form, no thank-you page, no Cloudflare function). The layout components are pre-built `split-test-*` templates the skill owns — this phase deploys them, generates per-client imagery, and populates the manifest.

Key steps:
1. Ensure the `split-test-*` LP layouts exist in `sites/{slug}/src/components/lp/` (copy from the skill templates if missing) + the `lp/[slug].astro` router
2. Generate per-client photos via Nano Banana (`mcp__nanobanana-mcp__gemini_generate_image`, model `pro`) from each template's `image-prompts.json`, saving to `sites/{slug}/public/images/lp/` (one filename each — don't overwrite)
3. Build `lp-manifest.json` (city pages + intent pages) with keyword H1s + the image paths wired in
4. Preview first city page + first intent page for user review
5. Ask: "Ready to commit and deploy {N} landing pages?"
6. Commit + sync-deploy to Cloudflare

After deploy confirms, update Final URLs in Google Ads:
```bash
# Loop over all ad groups in ads-structure.json and update their Final URL
python3 scripts/ads_manager.py update-final-url \
  --slug {slug} \
  --ad-group "{resource}" \
  --final-url "https://{domain}/lp/{slug}/"
```

If `update-final-url` isn't implemented yet, output a table of resource name → Final URL for the user to paste in the Google Ads UI.

At completion:
```
✓ Phase 4 complete — {N} landing pages live at https://{domain}/lp/
```

---

## Phase 5 — Conversion Tracking (`ads-tracking`) — click-to-call

Follow `ads-tracking/SKILL.md` exactly. The lead value was collected in Step 0. The ad group for RLSA can now be resolved from `ads-structure.json` — suggest the primary service × primary city ad group, but ask the user to confirm.

The LPs are phone-call-only — the conversion fires on a **tap of any phone CTA** (`tel:` link), not a form/thank-you page. The gtag loader + tel-click handler are already baked into the LP layouts; this phase only creates the conversion action and writes two fields into `brand.ts`.

Progress marker:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 5 OF 5 · Conversion Tracking (click-to-call)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Key steps:
1. Read `Ads/setup-conversion-tracking-and-audience.md`
2. Verify `lp-manifest.json` has entries and the LP layouts contain the click-to-call handler (from Phase 4)
3. Present confirmation gate with lead value + audience settings
4. Create the click-to-call conversion action via API (`category: PHONE_CALL_LEAD`)
5. Wire `gadsId` + `gadsCallConversionLabel` into `brand.ts` (no `.astro` edits needed — the layouts read these fields)
6. Verify the conversion fires by simulating a phone-CTA tap (Playwright or Tag Assistant fallback)
7. Create warm-pixel audience (540 days)
8. Attach to primary ad group at +50% bid (Observation mode)
9. Commit + deploy

At completion:
```
✓ Phase 5 complete — click-to-call tracking live, warm-pixel audience attached
```

---

## Final summary

After all 5 phases complete, print:

```
╔══════════════════════════════════════════════════════╗
║        ADS SETUP COMPLETE — {display_name}          ║
╚══════════════════════════════════════════════════════╝

✓ Phase 1 · {total} ad groups scaffolded across {N} campaigns (PAUSED)
✓ Phase 2 · {N} optimized RSAs generated and pushed (PAUSED)
✓ Phase 3 · {N} negative keywords applied to all campaigns
✓ Phase 4 · {N} landing pages live at https://{domain}/lp/
✓ Phase 5 · Click-to-call tracking live · warm-pixel audience active

━━━ Before you unpause ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
□  Verify the click-to-call conversion fires (tap a phone CTA on a live LP)
□  Check Google Ads UI — confirm all settings from the checklist below are OFF
□  Confirm Final URLs resolve to real pages (no 404s)
□  Review Ad Strength on a sample of ad groups (target: Good or Excellent)

━━━ Settings to KEEP OFF in Google Ads UI ━━━━━━━━━━━━
□  AI Max for Search campaigns
□  Dynamic Search Ads (DSA)
□  Automatically created assets
□  Final URL expansion
□  Broad match keyword inclusion
□  Search Partners

━━━ After the campaign goes live ━━━━━━━━━━━━━━━━━━━━━
Run /ads-negative-search-terms weekly once the campaign
has 14+ days of live data. It pulls real search term
waste, SERP-checks each term for buyer intent, and adds
confirmed-bad terms as campaign-level negatives.

Optional upgrade — /ads-call-tracking: provisions a Twilio
tracking number (in the client's subaccount) for the LPs,
with routing + recording + call logs. LP-only, so the main
site's NAP number is untouched. Google Ads attribution stays
on the gtag click-to-call from Phase 5. Add when the client
wants call recordings / a verified call log.

Estimated time to first lead: 24–72 hours after unpausing
(depends on budget, Quality Score, and search volume).
```

---

## Cost expectation

| Phase | Anthropic API | Google Ads API | Wall clock |
|---|---|---|---|
| 1 · Campaigns | ~$0.10–0.30 (RSA seed copy) | $0 | 3–8 min |
| 2 · RSA Generation | ~$0.05–0.15 × ad groups | $0 | 5–15 min |
| 3 · Negatives | $0 | $0 | 2–3 min |
| 4 · Landing Pages | $0 | $0 | 3–5 min |
| 5 · Tracking | $0 | $0 | 5 min |
| **Total** | **~$1–5 depending on account size** | **$0** | **~20–35 min** |
