---
name: ads-landing-page
description: Generate dedicated Google Ads landing pages for every SKAG ad group for a Rank AI client — one page per service × city combination (city SKAGs) plus one page per service × intent (near-me, emergency, cost, company, free-estimate, insurance, removal). Populates the lp-manifest.json with one entry per page (ALL pages default to variant v2 — the hot-pink champion; v3 navy/gold is the CHALLENGER, emitted ONLY when a governed split test is explicitly configured via ads-split-test). Pages are noindex, static (edge-cached), and H1 matches the exact ad keyword. Body content varies by intent angle, sourced from Ads/industries/{template}.json. Use when the user says "build landing pages", "create ad landing pages", "ads-landing-page", "build the LPs", or after /ads-campaigns finishes scaffolding.
---

# Landing Page Generator

Generates one dedicated Astro landing page per SKAG ad group by populating `lp-manifest.json`. The Astro files are pre-built in the site — this skill only generates manifest entries.

- **City pages** — one per `service × city` (e.g. `/lp/water-damage-restoration-federal-way-wa/`)
- **Intent pages** — one per `service × intent` (e.g. `/lp/water-damage-restoration-cost/`)

**Default rule:** every SKAG page ships as the champion (variant **v2**, hot-pink). Never emit a mix of v2/v3 across a live account unless `ads-split-test` is actively running a real traffic split with a decision date — otherwise you get two permanent styles serving simultaneously (exactly the NaRestCo drift we cleaned up).

Two visual variants:
- **v2 (champion · default A)** — `LpLayoutV2.astro`, hot-pink `#f01e5a`. Modern, conversion-focused: white header (logo + phone), dark hero with H1 + CTAs + stars + trust icons, insurance carrier strip, 2-col feature/why/process sections, dark CTA banner, minimal footer. **Primary for all new pages.**
- **v3 (challenger · B)** — `LpLayoutV3.astro`, navy `#17235e` + gold `#f5c63b` on cream. Pill header, bento hero + stats, technician imagery, testimonials, 4-step cards, FAQ accordion. Used ONLY as the split-test B variant via `ads-split-test` — not emitted by default.

Each page's H1 matches the exact keyword pinned in Slot 1 of the Google Ad, maximising Google's Landing Page Experience score.

**Why dedicated pages (not dynamic text replacement):**
Google's Quality Score crawler fetches the base URL and doesn't execute JS. Dedicated pages with the keyword in the URL, H1, and body copy get "Above Average" Landing Page Experience. DTR with a generic fallback headline gets "Average" at best — costing more per click.

---

## Split-test landing page templates

The skill OWNS the active LP designs so they survive across sessions and are the baseline every new campaign starts from. They live in this skill directory — not just in a site:

```
templates/
  split-test-v1/        ← CHAMPION (default A)
    LandingPage.astro   ← deploy as LpLayoutV2.astro  (manifest "variant": "v2")
    image-prompts.json  ← 4 Nano Banana prompts (hero/van/airmover/closing)
    README.md
  split-test-v2/        ← CHALLENGER (B)
    LandingPage.astro   ← deploy as LpLayoutV3.astro  (manifest "variant": "v3")
    image-prompts.json  ← 2 Nano Banana prompts (technician/team)
    README.md
```

**Naming map (important — the labels are easy to confuse):**

| Skill template | Code component | Manifest `variant` | Style |
|---|---|---|---|
| `split-test-v1` (champion) | `LpLayoutV2.astro` | `v2` | "TrustedRestorationPros" — hot-pink `#f01e5a` + light gray, full-height clean-water image hero, insurance strip, feature/why/process, dark urgency banner, image closing, scroll-triggered floating call bar |
| `split-test-v2` (challenger) | `LpLayoutV3.astro` | `v3` | "Plumbera" — navy `#17235e` + gold `#f5c63b` on cream, pill header, bento hero + stats, technician imagery, testimonials, 4-step cards, FAQ accordion |

Both use a self-contained palette (no brand `primary` token); only brand name/phone/logo are dynamic. Both render the manifest `h1` (exact keyword) and a wordmark header (not the logo image).

### Deploy a template into a client site
1. Copy the layout in as its variant component:
   ```bash
   cp ~/.claude/skills/ads-landing-page/templates/split-test-v1/LandingPage.astro \
      sites/{slug}/src/components/lp/LpLayoutV2.astro      # champion → variant v2
   cp ~/.claude/skills/ads-landing-page/templates/split-test-v2/LandingPage.astro \
      sites/{slug}/src/components/lp/LpLayoutV3.astro      # challenger → variant v3
   ```
2. **Generate client photos** from each template's `image-prompts.json` using the Nano Banana MCP tool `mcp__nanobanana-mcp__gemini_generate_image` (model `pro`), saving to `sites/{slug}/public/images/lp/`. Apply `niche_overrides` when the client isn't water-damage restoration. Save each candidate under its own filename (don't overwrite) so versions aren't lost.
3. Wire the image paths into each manifest entry:
   - **v1/v2 (pink):** `heroImageUrl`, `featureImageUrl`, `supportImageUrl`, `closingImageUrl`
   - **v2/v3 (navy):** `heroImageUrl` (technician portrait), `featureImageUrl` (team photo)

### Rotation (when a new winner emerges)
We continuously split-test and promote winners. When a new design wins:
1. Save the winner as `templates/split-test-v{N}/` (LandingPage.astro + image-prompts.json + README.md).
2. Update the CHAMPION row in the table above to point at it.
3. Keep older designs in their folders for rollback/reference.

> A third exploratory design (navy/gold "EmergencyRestorationPros", content-heavy) exists as `LpLayoutV1.astro` in scaffolded sites but is NOT currently saved as a skill template.

## When to invoke

- "build landing pages for {client}"
- "create the ad LPs for {client}"
- "generate landing pages"
- "landing-page"
- Naturally follows `/ads-campaigns` (after scaffold, run landing-page to create the LPs the ads point to)

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — all paths below are relative to here.

---

## The 7 intent page types

| Intent key | H1 pattern | Searcher mindset | Body content angle |
|---|---|---|---|
| `near-me` | `{Service} Near You` | Need local help now | Urgency (same as city pages) |
| `emergency` | `Emergency {Service}` | Crisis, need help immediately | Urgency (same as city pages) |
| `cost` | `{Service} Cost` | Price shopping before deciding | Pricing transparency, cost ranges, free estimate |
| `company` | `{Service} Company` | Vetting who to hire | Credentials, IICRC, license, reviews, local team |
| `free-estimate` | `Free {Service} Estimate` | Want to assess before committing | What the inspection covers, no obligation, what happens next |
| `insurance` | `{Service} Insurance Claims` | Wondering if insurance covers it | How claims work, direct billing, all carriers accepted |
| `removal` | `{Service} Removal` | Practical fix framing, not "restoration" | Process steps, what gets removed vs restored, timeline |

`near-me` and `emergency` share the urgency body content with city pages — no new section needed.

---

## Pre-flight

1. **Determine client slug.** Ask via `AskUserQuestion` if not provided.
2. **Verify pre-built LP files exist** in `sites/{slug}/src/`:
   - `pages/lp/[slug].astro` — router (branches on manifest `variant` field)
   - `components/lp/LpLayoutV2.astro` — default A variant layout
   - `components/lp/LpLayoutV1.astro` — B variant layout
   - `data/lp-manifest.json` — manifest file (populate this)

   If any file is missing, copy it from `templates/astro-starter/src/` — the components are identical across sites.

3. **Load client context:**
   - `clients/{slug}/plan-input.json` → services, service_areas, domain, brand, template
   - `Ads/industries/{template}.json` → service labels + `lp_body_content`
   - `sites/{slug}/src/lib/brand.ts` → phone, displayName, certifications

4. **Confirm the matrix.** Show the user a table of all pages that will be generated:

   ```
   CITY PAGES ({N} pages — variant: v2)
   Slug                                          | H1                                        | URL
   ----------------------------------------------|-------------------------------------------|---------------------------------------------
   water-damage-restoration-federal-way-wa        | Water Damage Restoration in Federal Way   | /lp/water-damage-restoration-federal-way-wa/
   mold-remediation-seattle-wa                    | Mold Remediation in Seattle               | /lp/mold-remediation-seattle-wa/

   INTENT PAGES ({M} pages — variant: v2)
   Slug                                          | H1                                        | URL
   ----------------------------------------------|-------------------------------------------|---------------------------------------------
   water-damage-restoration-cost                  | Water Damage Restoration Cost             | /lp/water-damage-restoration-cost/
   water-damage-restoration-insurance             | Water Damage Restoration Insurance Claims | /lp/water-damage-restoration-insurance/
   ```

   Ask: "Generate {N + M} landing pages ({N} city + {M} intent)? (yes/no)"

---

## Manifest format

The only file this skill writes to is `sites/{slug}/src/data/lp-manifest.json`. Each entry drives one page through the pre-built router.

```json
[
  {
    "slug": "water-damage-restoration-federal-way-wa",
    "variant": "v2",
    "serviceLabel": "Water Damage Restoration",
    "city": "Federal Way",
    "state": "WA",
    "intent": "city",
    "h1": "Water Damage Restoration in Federal Way, WA",
    "metaTitle": "Water Damage Restoration in Federal Way, WA | 24/7 Emergency Response",
    "metaDescription": "Fast, licensed water damage restoration in Federal Way, WA. 24/7 emergency response, insurance billing, free assessment. Call now.",
    "heroSubtitle": "Trusted Cleanup & Recovery Experts — Available Day or Night, When It Matters Most",
    "bodyContent": {
      "heading": "Why Immediate Response Matters",
      "intro": "Water damage spreads rapidly — the first 24 hours determine total restoration cost and whether secondary mold damage occurs.",
      "bullets": [
        "Within 1 hour: water reaches structural components and begins warping flooring",
        "Within 24 hours: mold spores begin to colonize in wet drywall and insulation",
        "Within 48–72 hours: mold spreads, odors set in, and restoration costs multiply"
      ],
      "callout": "Water damage gets worse every hour it sits. Call now to stop the clock on secondary damage."
    }
  },
  {
    "slug": "water-damage-restoration-cost",
    "variant": "v2",
    "serviceLabel": "Water Damage Restoration",
    "city": null,
    "state": null,
    "intent": "cost",
    "h1": "Water Damage Restoration Cost",
    "metaTitle": "Water Damage Restoration Cost | Free Estimate · No Hidden Fees",
    "metaDescription": "Wondering what water damage restoration costs? Get an upfront written estimate. No hidden fees, no surprises. Call for a free assessment.",
    "heroSubtitle": "Upfront Pricing · Free On-Site Estimate · No Hidden Fees",
    "bodyContent": {
      "heading": "What Does Water Damage Restoration Cost?",
      "intro": "Restoration costs depend on the area affected, the severity of damage, and response time. We provide a written upfront estimate before any work starts.",
      "bullets": [
        "Affected area: larger or multi-room damage requires more equipment and labor",
        "Material type: finished vs unfinished areas, hardwood vs carpet, drywall depth",
        "Response time: faster response = less secondary damage = lower total cost",
        "Insurance: most homeowner policies cover sudden water damage — we bill directly"
      ],
      "callout": "We provide a written upfront estimate before any work begins. No surprise invoices."
    }
  }
]
```

**Manifest field rules:**

| Field | Rule |
|---|---|
| `slug` | City pages: `{service-slug}-{city-slug}-{state-lower}` · Intent pages: `{service-slug}-{intent-key}` |
| `variant` | Always `"v2"` for pages generated by this skill. `"v1"` is reserved for `ads-split-test` |
| `serviceLabel` | From industry config `service_labels[{service-slug}]` — e.g. `"Water Damage Restoration"` |
| `city` / `state` | City pages: city name and state abbreviation · Intent pages: `null` |
| `intent` | `"city"` for city pages; intent key string for intent pages |
| `h1` | **City pages:** `{Service Label} in {City}, {State}` — must exactly match Slot 1 keyword · **Intent pages:** use H1 pattern from intent table above |
| `metaTitle` | City: `"{Service Label} in {City}, {State} \| {USP}"` · Intent: `"{H1} \| {USP}"` |
| `metaDescription` | 140–155 chars, includes service + city/intent + key USP + CTA |
| `heroSubtitle` | City + near-me + emergency: urgency + trust tagline · Other intents: match the searcher's question |
| `bodyContent` | From `Ads/industries/{template}.json → lp_body_content.{intent}` (city/near-me/emergency all use `lp_body_content.city`). Replace `{service}` placeholder with `serviceLabel`. Fall back to `Ads/industries/general.json` if missing |
| `processSteps` | Optional — omit to use the component's default 4-step process (V2) or 9-step restoration process (V1) |
| `heroImageUrl` | Optional — path to a hero background image in `/public/`. Leave blank to use gradient |
| `featureImageUrl` | Optional — path to a feature section image in `/public/`. Leave blank to use gradient |

**`heroSubtitle` by intent:**
| Intent | heroSubtitle |
|---|---|
| city / near-me / emergency | `"Trusted Cleanup & Recovery Experts — Available Day or Night, When It Matters Most"` |
| cost | `"Upfront Pricing · Free On-Site Estimate · No Hidden Fees"` |
| company | `"IICRC Certified · Licensed & Insured · Local Experts"` |
| free-estimate | `"Free On-Site Assessment · No Obligation · Respond Within 60 Min"` |
| insurance | `"We Bill Your Insurer Directly · All Major Carriers Accepted"` |
| removal | `"Certified Removal · Professionally Documented · Mold Prevention"` |

---

## Execution steps

### Step 1 — Read industry config + client context

1. Read `clients/{slug}/plan-input.json` → `template` field, `services[]`, `service_areas[]`
2. Read `Ads/industries/{template}.json` → `service_labels`, `lp_body_content`. Fall back to `Ads/industries/general.json` if not found.
3. Check `sites/{slug}/src/lib/brand.ts` for certifications (used in `heroSubtitle` overrides if needed).

### Step 2 — Populate lp-manifest.json

Build the manifest in two passes:

**Pass 1 — City pages** (`services[] × service_areas[]`):
- Generate one entry per combination
- `intent`: `"city"`, `variant`: `"v2"`
- `h1`: `"{Service Label} in {City}, {State}"`
- `bodyContent`: from `lp_body_content.city`

**Pass 2 — Intent pages** (`services[] × 7 intent types`):
- Generate one entry per combination (7 intent types × number of services)
- `intent`: one of the 7 intent keys
- `city`: `null`, `state`: `null`
- `h1`: from the intent table at the top of this skill
- `bodyContent`: from `lp_body_content.{intentKey}` (near-me and emergency use `lp_body_content.city`)

Write the complete manifest to `sites/{slug}/src/data/lp-manifest.json`.

### Step 3 — Preview sample pages

Print the content for:
- The first city page entry
- One intent page entry (e.g. `cost`)

So the user can verify the H1, `heroSubtitle`, and `bodyContent` before deploying.

Ask: "Ready to commit and deploy these {N + M} landing pages?"

### Step 4 — Commit and deploy

```bash
cd ~/Desktop/mywebsitecode/rank-ai
git add sites/{slug}/src/data/lp-manifest.json \
        sites/{slug}/src/pages/lp/ \
        sites/{slug}/src/components/lp/
git commit -m "feat({slug}): add {N} city + {M} intent ad landing pages"
```

Then sync-deploy to the client's GitHub repo:

```bash
python3 scripts/content_writer.py sync-deploy --slug {slug}
```

### Step 5 — Update Final URLs in Google Ads

After deploy confirms pages are live, update each ad group's Final URL:
- City ad groups: `https://{domain}/lp/{service-slug}-{city-slug}-{state}/`
- Intent ad groups: `https://{domain}/lp/{service-slug}-{intent-key}/`

```bash
python3 scripts/ads_manager.py update-final-url \
  --slug {slug} \
  --ad-group "{ad_group_resource}" \
  --final-url "https://{domain}/lp/{slug}/"
```

If `ads_manager.py` doesn't have `update-final-url` yet, list the URLs for the user to paste into each ad group in the Google Ads UI — one line per ad group.

---

## How the Astro files work (reference — do not regenerate)

The LP infrastructure is pre-built in every site. **Do not regenerate these files** unless they're missing.

| File | Location | Purpose |
|---|---|---|
| `pages/lp/[slug].astro` | Per-site | Router: reads `lp-manifest.json`, returns `LpLayoutV2` or `LpLayoutV1` based on `variant` field |
| `components/lp/LpLayoutV2.astro` | Per-site | V2 layout (default A): stripped header, dark hero, insurance strip, 2-col sections, sticky mobile bar |
| `components/lp/LpLayoutV1.astro` | Per-site | V1 layout (B variant): dark header, large phone hero, services list, 9-step process, dark footer |
| `data/lp-manifest.json` | Per-site | Populated by this skill. One JSON entry = one static page |

**V2 layout props** (set in manifest):
- `h1` — exact keyword match (required)
- `heroSubtitle` — tagline below H1
- `serviceLabel` — displayed in trust icons + closing section
- `city`, `state` — displayed in closing section right column (`null` for intent pages)
- `bodyContent.heading` — Feature section H2
- `bodyContent.intro` — Feature section + Why Choose Us body text
- `bodyContent.bullets[]` — Why Choose Us bullet list
- `bodyContent.callout` — Closing section left body (optional)
- `processSteps[]` — optional override for numbered steps (default: 4-step generic process)
- `heroImageUrl` — optional hero background image
- `featureImageUrl` — optional feature section image

**V1 layout props** (same schema, some fields differ):
- Same `h1`, `heroSubtitle`, `serviceLabel`, `city`, `state`, `bodyContent`
- `processSteps[]` — optional override for numbered steps (default: 9-step restoration process)
- No `heroImageUrl` or `featureImageUrl` in V1

---

## Quality checks before signing off

- [ ] Every page is `noindex,nofollow` (enforced by both layout components)
- [ ] City page H1 exactly matches the Slot 1 keyword: `{Service Label} in {City}, {State}`
- [ ] Intent page H1 matches the intent keyword pattern from the table above
- [ ] No navigation links on any LP (both layouts strip the site nav)
- [ ] Phone number in header matches `brand.phone` (pulled from brand.ts automatically)
- [ ] Intent pages with `city: null` don't render "Serving null" anywhere (closing section is conditional)
- [ ] Body content matches the page's intent AND the client's industry — all copy sourced from industry config, not hardcoded restoration copy
- [ ] `bodyContent.heading` is keyword-relevant and intent-specific (not generic)
- [ ] Pages build without errors (`astro build` passes in `sites/{slug}/`)
- [ ] Both layout components exist in `sites/{slug}/src/components/lp/` before deploy

---

## Cost expectation

- No Anthropic API calls (pages are manifest-driven, not AI-generated)
- No DataForSEO calls
- Wall clock: 2–4 minutes to generate manifest + deploy
