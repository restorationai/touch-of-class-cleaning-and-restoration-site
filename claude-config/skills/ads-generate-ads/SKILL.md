---
name: ads-generate-ads
description: Generate high-performing Google Ads RSAs + full asset set (sitelinks, callouts, structured snippets) for a water damage restoration client. Reads anatomy-of-a-good-ad.md and ad-assets-best-practices.md as the quality spec, generates 3 RSAs testing different angles (speed / trust / value) for every service × city combination in plan-input.json, previews all copy in one consolidated file for human review, then pushes all paused ads to Google Ads via ads_manager.py in a single batch. Use when the user says "generate ads", "write ads for {client}", "create RSAs", "build ad copy", or "ads-generate-ads".
---

# Generate Ads

Generates 3 RSAs + full asset set for every service × city combination in a client's `plan-input.json`, shows one consolidated preview for human review, then pushes all as paused ads via `scripts/ads_manager.py` in a single batch.

**Spec files (read both on every invocation — they are the source of truth):**
- `rank-ai/Ads/anatomy-of-a-good-ad.md` — RSA structure, headline patterns, pinning rules, char limits, editorial policy, self-review checklist
- `rank-ai/Ads/ad-assets-best-practices.md` — sitelinks, callouts, structured snippets, business name/logo specs and CTR lift benchmarks

## When to invoke

The user says any of:
- "generate ads for {client}"
- "write RSAs for {client}"
- "create ad copy for {client}"
- "build the ads for {client}"
- "generate-ads"

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — all paths below are relative to here.

## Pre-flight

1. **Read both spec files** (`Ads/anatomy-of-a-good-ad.md` and `Ads/ad-assets-best-practices.md`) fully before generating anything.
2. **Determine the client slug.** If not provided by the user, ask via `AskUserQuestion` (list available slugs from `clients/*/plan-input.json`).
3. **Load the full matrix from `clients/{slug}/plan-input.json`:**
   - `services` — every service slug the client offers
   - `service_areas` — every city/state the client serves
   - `brand` — display name, phone, domain, certifications
   - This produces an N services × M cities matrix of ad groups to generate.
4. **Load ad group resource names from `clients/{slug}/ads/scaffold-output.json`** if it exists. This file is written by `ads-campaigns` after scaffold and maps each `{service}-{city-slug}` to its Google Ads resource name (`customers/{cid}/adGroups/{id}`).
   - If `scaffold-output.json` does not exist, skip the push step and output preview files only. Tell the user to run `/ads-campaigns` first or provide the resource names manually.
5. **Source env:** `set -a; . rank-ai/.env; set +a` for `ANTHROPIC_API_KEY` and `GOOGLE_ADS_DEVELOPER_TOKEN`.
6. **Confirm scope with the user before generating.** Show a summary table:

   ```
   Client: {display_name}
   Services: {N} ({list})
   Cities: {M} ({list})
   Ad groups to generate: {N × M}
   Scaffold output found: yes / no (push will be skipped if no)
   ```

   Ask: "Ready to generate RSAs for all {N × M} ad groups?"

---

## Generate RSAs — loop over every service × city combination

For each combination in the matrix, generate **3 distinct RSAs** — one per angle — using the spec from `anatomy-of-a-good-ad.md`:

| RSA | Angle | Dominant headline themes |
|-----|-------|--------------------------|
| RSA 1 | **Speed / Emergency** | Response time, 24/7, same-day, urgency |
| RSA 2 | **Trust / Credentials** | IICRC certified, licensed, reviews, years in business |
| RSA 3 | **Value / Process** | Free inspection, insurance billing, upfront pricing, what happens next |

For each RSA generate:
- **15 headlines** — cover all 6 patterns from §2 of the anatomy doc (keyword+location, offer/USP, trust/social proof, urgency, guarantee, CTA). Pin 3 keyword headlines to Slot 1. Leave all others unpinned.
- **4 descriptions** — one per angle: service+speed, trust+price, differentiator, direct CTA (§3 of anatomy doc).
- **Display URL paths** — keyword-rich, e.g. `Water-Damage / Tacoma`.

**Hard rules (from anatomy doc §5–6):**
- Every headline ≤ 30 chars (count spaces)
- Every description ≤ 90 chars
- No ALL CAPS words, no exclamation marks in headlines, max 1 per ad in descriptions
- 3 keyword headlines pinned to Slot 1 per RSA
- No `#1`, `best`, `top`, `guaranteed` without third-party proof
- No phone numbers in headlines
- Copy must be specific to the service and city of each combination — never reuse identical headlines across different city ad groups
- **Industry-aware copy:** read `Ads/industries/{template}.json` (where `template` comes from `plan-input.json`) for `rsa_label` and `rsa_guidance`. Use these to ensure copy matches the client's niche — a restoration company's RSAs should say "restoration," an HVAC company's should say "HVAC," etc. Fall back to `Ads/industries/general.json` if no industry file exists for the template.

---

## Generate assets (one set per service, shared across cities)

Using `ad-assets-best-practices.md` as spec, generate one asset set per service slug (not per city — assets are applied at campaign or account level):

**Sitelinks (6–8):** Each title ≤ 15 chars (mobile-safe), unique destination URL, description lines ≤ 35 chars. Target pages appropriate to the service (e.g. for water damage: Water Extraction, Mold Remediation, Fire Damage, Free Estimate, About, Emergency Response).

**Callouts (8–12):** Each ≤ 25 chars. Cover 4 angles minimum: speed, trust, value, guarantee.

**Structured snippets (2 headers):**
- `Services`: list primary service variants
- `Types`: Emergency, Same-Day, Routine, Inspection, Commercial, Residential

---

## Consolidated preview before pushing

Before touching Google Ads, output one preview file at:
`clients/{slug}/ads/preview-all-{date}.md`

Structure:

```
# Ad Preview — {display_name} · {date}
# {N × M} ad groups · Status: PAUSED (not yet pushed)

---

## {Service Display Name} · {City}, {State}
Ad group resource: customers/{cid}/adGroups/{id}  ← or "NOT SCAFFOLDED" if missing

### RSA 1 — Speed / Emergency
Headlines:
  1. [PIN S1] Water Damage {City}     (27 chars)
  2. [PIN S1] {City} Water Damage     (...)
  3. [PIN S1] 24/7 Water Damage {City} (...)
  4-15. ...
Descriptions:
  1. ...
  2. ...
  3. ...
  4. ...

### RSA 2 — Trust / Credentials
...

### RSA 3 — Value / Process
...

---

## {Next service} · {Next city}
...

---

## Assets — {Service Display Name} (shared across all cities)
Sitelinks: ...
Callouts: ...
Structured Snippets: ...

---

## Self-review checklist (applies to all ad groups above)
[ ] All headlines ≤ 30 chars
[ ] All descriptions ≤ 90 chars
[ ] No ALL CAPS, no exclamation marks in headlines
[ ] 3 keyword headlines pinned to Slot 1 per RSA
[ ] City name appears in at least 3 headlines per ad group
[ ] No identical headlines reused across different city ad groups
[ ] Ad Strength target: Good or Excellent
[ ] All sitelink titles ≤ 15 chars
```

**Stop here and show the preview file path to the user.** Ask: "Ready to push all {N × M} ad groups as paused ads to Google Ads?"

---

## Push to Google Ads (only after explicit user approval)

Push each combination sequentially. If `scaffold-output.json` is missing for any combination, skip that ad group and log it as `SKIPPED — no ad group resource`:

```bash
cd ~/Desktop/mywebsitecode/rank-ai
set -a; . .env; set +a

# Repeat for each service × city combination
python3 scripts/ads_manager.py generate-ads \
  --slug {slug} \
  --ad-group {ad_group_resource} \
  --service {service} \
  --city "{city}" \
  --state {state}
```

After all pushes complete, print a summary table:

```
Ad group                                  Status
----------------------------------------  --------
water-damage-restoration · Tacoma, WA    PUSHED (paused)
water-damage-restoration · Seattle, WA   PUSHED (paused)
mold-remediation · Tacoma, WA            PUSHED (paused)
fire-damage-restoration · Seattle, WA    SKIPPED — no scaffold resource
...
```

---

## Output files

| File | Purpose |
|------|---------|
| `clients/{slug}/ads/preview-all-{date}.md` | Consolidated human review copy for all ad groups |
| `clients/{slug}/ads/assets-{service}-{date}.json` | Asset config per service for manual upload or API push |

---

## Cost expectation

- Anthropic API for full matrix: ~$0.05–0.15 per ad group × number of combinations
- Google Ads API writes: $0 (included in developer token quota)
- Wall clock: ~2–5 minutes depending on matrix size
