---
name: ads-campaigns
description: Build a full Google Ads SKAG campaign structure for a water damage restoration client — one campaign per service group, one ad group per service × city combination (city SKAGs) plus 7 intent-based ad groups per service (near me, emergency, cost, company, free estimate, insurance, removal), phrase-match keywords, geo targeting, country exclusions, default negatives, and paused RSAs per ad group. Reads build-your-first-skag.md as the SOP. Asks 7 intake questions before touching the API. Dry-runs first, then creates everything PAUSED. Wraps ads_manager.py scaffold. Use when the user says "build the campaign", "scaffold ads", "build SKAGs", "set up Google Ads for {client}", or "ads-campaigns".
---

# Build SKAGs

Builds the full Google Ads campaign structure for a water damage restoration client following the SOP in `rank-ai/Ads/build-your-first-skag.md`. Creates everything PAUSED — nothing serves until the user explicitly unpauses in the Google Ads UI.

**Source of truth:** `rank-ai/Ads/build-your-first-skag.md` — read it fully on every invocation before asking any questions.

## Ads Journal — read first, log after (applies to ALL ads work)

Every client has a running ops log at `rank-ai/clients/{slug}/ads-journal.md` — what we changed, why, and what to watch next time. It exists so nobody (human or cron) ever looks at an account without the context of the last decisions.

**Before** touching any client's account, read the journal:
```bash
python3 scripts/ads_manager.py note --slug {slug}          # list recent entries
```
It also prints automatically at the top of `report`. The journal is the authority on *intended* state (e.g. which campaigns are the live SKAGs vs. legacy-off) — trust it over a cold read of the live account, which has no "why."

**After** any change, leave a note (one line: what + why + what to watch):
```bash
python3 scripts/ads_manager.py note --slug {slug} --kind watch \
  --add "Graduate to Max Conversions once ~20 conv (~early July)."
```
The change commands (`set-budget`, `set-bid-strategy`, `pause`, `enable`, `add-negatives`, `apply-negatives`) **auto-append** an entry on success, so you only add manual notes for decisions/observations the commands can't capture. Tag with `--kind` (`note` | `watch` | `bid` | `budget` | `review`).

## When to invoke

- "build the campaign for {client}"
- "scaffold Google Ads for {client}"
- "set up SKAGs for {client}"
- "build SKAGs" / "build-skags"

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — all paths below are relative to here.

---

## Step 0 — Read the SOP, then ask the 7 intake questions

**Read `Ads/build-your-first-skag.md` fully before proceeding.** It is the source of truth for all campaign settings, geo exclusion logic, RSA pinning rules, and the full settings-to-KEEP-OFF list.

Then determine the client slug. If not provided, ask via `AskUserQuestion` and show available clients from `clients/*.json`.

Load `clients/{slug}/plan-input.json` if it exists. For each question below, use the existing value from `plan-input.json` if present — only ask if the field is missing or the user explicitly wants to change it.

### The 7 questions (from SOP §Step 0)

Ask these via `AskUserQuestion` in a single batch where possible. Do NOT default to any example values — every business is different.

1. **Country**
   > "What country does this business operate in? (e.g. Canada, US, UK, Australia)"
   Used for: positive geo target + excluding every other country (kills VPN/bot clicks)

2. **City + service area radius**
   > "Which city is the business in, and how far out does it serve? (default: 50 km radius, presence-only)"
   If `service_areas` already exists in `plan-input.json`, confirm or let user add/edit.

3. **Website URL**
   > "What is the website URL? If a service-specific landing page doesn't exist yet, provide the domain — I'll use it to build the final URL pattern."
   Used for: final URL on every ad, display URL paths, asset structure.
   This is required — do not proceed without it.

4. **Service(s) to advertise**
   > "Which services should this campaign cover? (e.g. water damage restoration, mold remediation, fire damage)"
   If `services` already exists in `plan-input.json`, confirm or let the user add more.

5. **Daily budget**
   > "What's the daily budget per campaign? Budget = target max-CPC × clicks/day you want. Emergency home-services CPCs run ~$15–30, so ~$75–150/day per service campaign. $20–50/day buys only 1–2 clicks/day and starves the campaign."
   Default: $100/day per service campaign if the user isn't sure (NOT $50 — too low for competitive restoration CPCs).
   Note: raising budget without competitive bids does nothing — see the cold-start bidding rule below.

6. **Target CPA (optional)**
   > "What do you currently pay per lead, or what should a lead cost to be profitable? (skip if unknown — we cold-start on Maximize Clicks + a CPC cap and graduate to a CPA target after ~30 conversions)"
   If unknown: still cold-start on Maximize Clicks + CPC ceiling. Do NOT start on Maximize Conversions — a brand-new campaign has no conversion history, so Smart Bidding bids microscopically and loses ~90% impression share to rank ($0 spend, 0 clicks). See bidding-strategy-playbook.md.

7. **Google Ads Customer ID**
   > "What's your Google Ads customer ID? (10 digits, no dashes — found in the top-right of the Google Ads UI)"
   Check `clients/{slug}/plan-input.json` for `ads_customer_id` first — only ask if missing.

### Confirmation gate

After collecting all answers, summarize back before any API calls:

> "Confirm: I'm about to build a Search campaign for `[services]` in `[city, country]`, `[radius]` km radius (presence only), $`[budget]`/day, Maximize Clicks with a $`[cap]` max-CPC ceiling (cold-start — graduates to Maximize Conversions after ~30 conversions). All countries except `[country]` will be excluded. Customer ID `[id]`. Website: `[url]`. Everything will be PAUSED until you approve. Proceed?"

Do NOT proceed until the user explicitly confirms.

---

## Step 1 — Update plan-input.json if needed

If any required fields were missing or changed, update `clients/{slug}/plan-input.json` before running scaffold:

Required fields scaffold reads:
```json
{
  "services": ["water-damage-restoration", "mold-remediation"],
  "service_areas": [
    {"city": "Toronto", "state": "ON", "slug": "toronto-on", "radius_km": 50}
  ],
  "domain": "example.com",
  "ads_customer_id": "1234567890",
  "ads_daily_budget": 50.0
}
```

Use `Edit` to patch only the missing fields — do not overwrite existing data.

---

## Step 2 — Dry run (show what will be created)

```bash
cd ~/Desktop/mywebsitecode/rank-ai
set -a; . .env; set +a

python3 scripts/ads_manager.py scaffold --slug {slug} --dry-run
```

This prints every campaign, ad group, keyword, and RSA that will be created — no API writes. Show the output to the user. Point out:
- Number of campaigns (one per service group)
- Number of city-based ad groups (services × cities) — one SKAG per service × city combo
- Number of intent-based ad groups (services × 7 intents) — geo-targeted, no city in keyword
- Total ad groups = (services × cities) + (services × 7)
- That everything will start PAUSED

**The 7 intent ad groups per service** (added once per service, not per city — geo targeting handles location):

| Ad Group | Keywords it owns | Angle |
|---|---|---|
| `[service] Near Me` | [service] near me, local [service], [service] near me open now | Proximity |
| `[service] Emergency` | emergency [service], 24/7 [service], [service] open now, after hours [service] | Urgency |
| `[service] Cost` | [service] cost, [service] quote, affordable [service], [service] price | Price |
| `[service] Company` | [service] company, [service] contractor, [service] specialist, professional [service] | Vendor |
| `[service] Free Estimate` | free [service] estimate, free [service] inspection, free [service] quote | Offer |
| `[service] Insurance` | insurance [service], [service] insurance claim, [service] covered by insurance | Insurance |
| `[service] Removal` | [service] removal, [service] cleanup, [service] repair | Variant |

Ask: "Does this structure look right? Proceed with the real build?"

---

## Step 3 — Build (only after explicit approval)

```bash
python3 scripts/ads_manager.py scaffold --slug {slug} --auto-keywords
```

**`--auto-keywords` (recommended, requires Google Ads API Basic Access — approved 2026-06-15):** runs `KeywordPlanIdeaService` keyword research first and seeds the intent ad groups with real, volume-validated keyword variants (falling back to templates where research has no match). Omit the flag to build from templates only. Keyword research is no longer a manual step.

Expected output per the SOP:
```
✓ Budget: customers/{cid}/campaignBudgets/{id}
✓ Campaign: {display_name} - Water Damage Restoration
✓ Geo: {radius} km radius around {city} (presence only)
✓ Excluded: every country except {country} (kills VPN/bot clicks)
✓ Negative keywords: {N} added
✓ Ad group: {service} - {city}, {state}
✓ Keyword: "{service} {city}" (phrase match)
✓ RSA 1/2/3: ...

ALL CREATED · PAUSED · Review at: https://ads.google.com/aw/campaigns
```

If the script fails partway through (partial build), refer to the SOP's **Recovering from a partial build** section — do NOT re-run the full scaffold, use `add_rsas_only.py` to patch the orphaned resources.

---

## Step 4 — Settings to KEEP OFF (from SOP §5.1)

After the build, remind the user of these Google UI prompts to decline when they open the campaign:

| Google's prompt | Decline because |
|-----------------|-----------------|
| "Activate AI Max for Search campaigns" | Defeats SKAG keyword discipline entirely |
| "Enable Dynamic Search Ads (DSA)" | Loses ad copy control |
| "Add automatically created assets" | Breaks pinning + character-limit discipline |
| "Turn on Final URL expansion" | Sends traffic to wrong landing pages |
| "Enable broad match keyword inclusion" | Defeats phrase-match SKAG strategy |
| "Turn on Search Partners" | Wastes budget on lower-quality traffic |

All should be OFF in Settings → Other settings before unpausing.

---

## Step 5 — UI verification checklist (from SOP §5)

Print this for the user to check before unpausing:

```
[ ] Campaign type: "Search" only (no Display, no Search Partners)
[ ] Budget: matches what was set ($X/day)
[ ] Bidding: "Maximize Clicks" with a max-CPC ceiling (cold-start) — NOT Maximize Conversions on a fresh campaign
[ ] Locations: {radius} km radius, "Presence" selected (NOT "Presence or interest")
[ ] Ad schedule: configured per SOP defaults
[ ] Negative keywords: {N} at campaign level
[ ] Each ad group: exactly 1 phrase-match keyword
[ ] 3 RSAs per ad group, Ad Strength: "Good" or "Excellent"
[ ] Final URL: points to a working page (not a 404)
[ ] EU political ads: "Doesn't have EU political ads"
```

Quality Score will show "—" and impressions will be 0 until the campaign serves — that's normal for a brand-new paused campaign (SOP §5.2).

---

## What comes next

After the structure passes review:
1. Run `/generate-ads` to write better RSAs (the scaffold creates functional copy — generate-ads produces optimized 3-angle RSAs per the anatomy spec)
2. Run `/add-negatives` to layer in the full 150-term universal negative list on top of the 15 scaffold defaults
3. Unpause when the landing page is live and the conversion tag is verified

---

## Troubleshooting

See SOP §Troubleshooting table for all known Google Ads API errors and fixes. The most common ones for restoration accounts:
- `This method is not allowed for use with explorer access` → keyword research only; scaffold itself works on Explorer tier
- `Trying to modify the name of an active or paused campaign, where the name is already assigned` → campaign name collision; run `list-campaigns` to check and delete the orphan first
- Partial build recovery → use `python3 google-ads-api-setup/add_rsas_only.py` with the existing ad group resource name

## Cost expectation

- Anthropic API (RSA generation): ~$0.10–0.30 total
- Google Ads API writes: $0
- Wall clock: 3–8 minutes depending on number of services × cities
