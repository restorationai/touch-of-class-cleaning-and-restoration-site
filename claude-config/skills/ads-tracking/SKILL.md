---
name: ads-tracking
description: Set up Google Ads click-to-call conversion tracking + warm-pixel RLSA audience for a Rank AI client. Creates a phone-call-lead conversion action via API, extracts the AW conversion label, wires gadsId + gadsCallConversionLabel into brand.ts (the LP layouts already contain the gtag loader + tel-click handler that read those fields), verifies the conversion fires on a phone-CTA tap, creates a 540-day warm-pixel audience, and attaches it to the SKAG ad group at +50% bid. The Rank AI landing pages are phone-call-only (no form, no thank-you page). Read setup-conversion-tracking-and-audience.md as the SOP. Use when the user says "set up conversion tracking", "add tracking", "wire up conversions", "click to call", "warm pixel", "RLSA", or "ads-tracking".
---

# Ads Tracking — Click-to-Call Conversion + Warm-Pixel Audience

Sets up Google Ads **click-to-call** conversion tracking and a warm-pixel RLSA audience for a Rank AI client. Everything via API — no clicking in the Google Ads UI.

**The Rank AI landing pages are phone-call-only** — every CTA is a `tel:` link ("Get Help Now" / "Call {phone}"). There is **no lead form, no `/api/lead`, and no `/lp/thank-you/` page**. The conversion is therefore a **tap on a phone CTA**, fired via a `gtag('event','conversion', …)` click handler that is already baked into the LP layout components.

**Source of truth:** `rank-ai/Ads/setup-conversion-tracking-and-audience.md` — read it fully on every invocation. This skill is the Rank AI Astro + Cloudflare Pages adaptation, specialized for click-to-call.

**How the tracking is wired (already built into the LP layouts):**
- The LP layout components (`LpLayoutV1/V2/V3.astro`, from the `split-test-*` templates) read `brand.gadsId` and `brand.gadsCallConversionLabel` defensively.
- When `gadsId` is set, the layout injects the `gtag.js` loader + `config` into the LP `<head>`.
- When `gadsCallConversionLabel` is set, the layout adds a document click listener: any `a[href^="tel:"]` tap fires `gtag('event','conversion', { send_to: label })`.
- Both **no-op when the brand fields are empty** — so this skill's only code change is adding those two fields to `brand.ts`.

> NOTE on signal quality: click-to-call counts the *tap*, not a *connected call*. Strong on mobile (a tap dials), weak on desktop (a tel: tap often does nothing). The gold-standard upgrade is Google's "calls from a website" with a forwarding number + min call duration — documented at the bottom as the Phase-2 enhancement.

## When to invoke

- "set up conversion tracking for {client}"
- "wire up Google Ads conversions"
- "set up click to call for {client}"
- "add the warm pixel for {client}"
- "ads-tracking"
- Naturally follows `ads-landing-page` (landing pages must exist before tracking can be verified)

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — all paths below are relative to here.

---

## Pre-flight

Read `Ads/setup-conversion-tracking-and-audience.md` fully first.

Then verify ALL of the following before asking the user anything:

- [ ] `python3 scripts/ads_manager.py list-campaigns --slug {slug}` succeeds (API credentials valid)
- [ ] `sites/{slug}/src/data/lp-manifest.json` exists and has ≥1 entry (run `ads-landing-page` first if not)
- [ ] At least one LP layout in `sites/{slug}/src/components/lp/` contains the click-to-call handler (`gadsCallConversionLabel`). If missing, the site predates click-to-call tracking — copy the current `split-test-*` templates in first (see `ads-landing-page`).
- [ ] At least one campaign + ad group exists for the client (from `ads-campaigns`)

There is **no `thank-you.astro` to check** — these pages convert on a phone tap, not a page load.

---

## Intake questions

Ask all of these before any API calls. Pre-fill from `clients/{slug}/plan-input.json` where available.

1. **Client slug** — if not provided, ask and show available clients
2. **Lead value**
   > "What's a phone lead worth to you in dollars? Use: average job value × close rate. (e.g. $3,000 job × 30% close = $900). Smart Bidding uses this to set bids — directionally honest beats precise."
   Must be a positive number.
3. **Conversion action name** — default: `Lead · Phone Call`
4. **Currency** — default: USD (or match Google Ads account currency)
5. **Ad group for RLSA attachment**
   > "Which ad group should the warm-pixel audience attach to? Run `python3 scripts/ads_manager.py list-campaigns --slug {slug}` to find ad group resource names, or type 'skip'."
6. **Bid modifier** — default: +50% (warn if outside +25% to +100%)

**Confirmation gate** (required):
> "Confirm: creating a click-to-call conversion action '{name}' valued at ${value} {currency}, firing on phone-CTA taps across the {slug} landing pages; plus a warm-pixel audience for {domain} (540 days) attached to ad group {id} at +{modifier}%. Live changes to Google Ads account {customer_id}. Proceed?"

Do not proceed until the user says yes.

---

## Step 1 — Create the click-to-call conversion action

Use the SOP's `ConversionActionService` spec, with these click-to-call fields:
- `category`: `PHONE_CALL_LEAD`
- `type_`: `WEBPAGE` (we fire it via gtag on the website, not via a Google forwarding number)
- `default_value`: lead_value (from intake)
- `counting_type`: `ONE_PER_CLICK` (one conversion per ad click — repeated taps don't inflate)
- `click_through_lookback_window_days`: 90
- `attribution_model`: `GOOGLE_ADS_DATA_DRIVEN`
- `primary_for_goal`: True

After mutate, extract from the response:
- The `AW-XXXXXXXXXX` global tag ID
- The full conversion label: `AW-XXXXXXXXXX/AbC-D_efGhIjKlMnOp`

Print both to stdout.

---

## Step 1b — Make the phone-lead GOAL biddable (the step that's easy to miss)

Creating the conversion action with `primary_for_goal: True` is **NOT enough.** Campaigns
inherit the account-default conversion goals (`goal_config_level = CUSTOMER`), and Google
often leaves the phone-lead goal **`biddable = False`** — so Smart Bidding has no primary
conversion to optimize toward and the campaign starves. (This is exactly what left NaRestCo
with $0 spend even after bids were fixed: every account goal was non-biddable.) You must
verify/set the GOAL, not just the action.

1. Read the account goals:
   ```
   SELECT customer_conversion_goal.category, customer_conversion_goal.origin,
          customer_conversion_goal.biddable, customer_conversion_goal.resource_name
   FROM customer_conversion_goal
   ```
2. Set the phone-lead goals **biddable = True** (PRIMARY) via `CustomerConversionGoalService`
   (build the mask with `protobuf_helpers.field_mask(None, goal._pb)`):
   - `PHONE_CALL_LEAD / WEBSITE` — the click-to-call action you just created
   - `PHONE_CALL_LEAD / CALL_FROM_ADS` — Google's auto-imported "Calls from ads" (if present)
3. **Value the auto-imported call conversion too.** Google auto-creates "Calls from ads"
   (`AD_CALL`) at **$1**. Set its `value_settings.default_value = lead_value` and
   `always_use_default_value = True` — otherwise your Search ads' main conversion reports $1
   and ROAS is meaningless.
4. **Keep GBP "Local actions" secondary.** `GET_DIRECTIONS / ENGAGEMENT / PAGE_VIEW / CONTACT`
   with origin `GOOGLE_HOSTED` must stay `biddable = False` — never let directions/website-
   visit taps drive bidding. (Usually already secondary; just confirm.)

**API note:** Google-hosted conversions (GBP "Local actions", GBP "Clicks to call") and LSA
(`local_services_phone_lead`) are **read-only** — mutating them returns *"Mutates are not
allowed for the requested resource."* That's fine: they're secondary / separate (LSA runs its
own pay-per-lead auction), so they don't affect Search bidding. Only the website + calls-from-
ads phone-lead goals matter.

Verify the end state before moving on:
```
PRIMARY    PHONE_CALL_LEAD / WEBSITE        ($lead_value)
PRIMARY    PHONE_CALL_LEAD / CALL_FROM_ADS  ($lead_value)
secondary  GET_DIRECTIONS · ENGAGEMENT · PAGE_VIEW · CONTACT  (GOOGLE_HOSTED)
```

---

## Step 2 — Wire the two fields into brand.ts

This is the **only code change** — the LP layouts already contain the gtag loader + tel-click handler that read these fields.

Add to `sites/{slug}/src/lib/brand.ts`:

```typescript
export const brand = {
  slug: "narestco",
  // ...existing fields
  gadsId: "AW-XXXXXXXXXX",                                  // global tag id from Step 1
  gadsCallConversionLabel: "AW-XXXXXXXXXX/AbC-D_efGhIjKlMnOp", // full label from Step 1
} as const;
```

Use `Edit` to add the two fields — do not rewrite the whole file.

- If a different `AW-` id is already hardcoded in `BaseLayout.astro` (the main site's global tag), that's fine — the LPs are standalone and use `brand.gadsId`. Flag any mismatch to the user but don't block.
- If `gadsId` already exists in `brand.ts` and differs from Step 1, ask which is correct before overwriting.

No edits to any `.astro` page are needed. The handler activates automatically on the next build because `gadsCallConversionLabel` is now truthy.

---

## Step 3 — Verify the conversion fires

### 3a — Automated (Playwright, preferred)

```bash
cd sites/{slug}
npx --no-install playwright --version 2>/dev/null || npm install -D playwright && npx playwright install chromium
npm run dev &
DEV_PID=$!
sleep 3
```

Run a Playwright script that:
1. Opens `/lp/{first-slug-from-manifest}/`
2. Waits for `gtag` to be defined (confirms the global tag loaded from `brand.gadsId`)
3. Registers a listener / network wait for a request to `google.com/pagead`, `googleads.g.doubleclick.net`, or a `dataLayer` push containing the conversion `send_to` label
4. Clicks a phone CTA: `a[href^="tel:"]` (in headless Chromium a tel: tap is a no-op navigation, so the page stays and the gtag event fires)
5. Asserts the conversion request/push occurred with the correct label

Exit code 0 = pass. Kill the dev server (`kill $DEV_PID`) after.

### 3b — Manual fallback (Tag Assistant)

1. Install Tag Assistant: https://tagassistant.google.com/
2. `cd sites/{slug} && npm run dev`
3. Connect Tag Assistant to `localhost:4321`
4. Click any "Get Help Now" / "Call …" button on an LP page
5. Confirm a **conversion** hit with the action name appears in Tag Assistant

**If verification fails, stop.** Do not proceed to audience setup with a broken tag. Common cause: `gadsId` not set in `brand.ts` (gtag never loads) — re-check Step 2.

---

## Step 4 — Create the warm-pixel audience

Follow SOP §Step 5 exactly. Unchanged by the click-to-call model.
- Name: `Warm pixel · all visitors · {domain} · 540d`
- Rule: URL contains `{domain}` (from `brand.domain` in `plan-input.json`)
- `membership_life_span`: 540 days (maximum)
- Mode: Observation (not Targeting — see SOP warning)

Save the returned `userList` resource name.

---

## Step 5 — Attach audience to ad group

Follow SOP §Step 7. Verify the ad group's targeting setting is **Observation** before attaching (Targeting would restrict the ad group to the warm audience only, killing reach on a new campaign).

```python
bid_modifier = 1.0 + (bid_modifier_pct / 100)  # e.g. 1.5 for +50%
```

---

## Step 6 — Commit and deploy

```bash
cd ~/Desktop/mywebsitecode/rank-ai
git add sites/{slug}/src/lib/brand.ts
git commit -m "feat({slug}): wire Google Ads click-to-call conversion + warm-pixel audience"
```

> If this client's LP layouts predated click-to-call tracking and you copied fresh `split-test-*` templates in during pre-flight, `git add` those `src/components/lp/*.astro` files too.

Then sync-deploy so the live LPs load the tag + fire conversions:

```bash
python3 scripts/content_writer.py sync-deploy --slug {slug}
```

---

## Step 7 — Report and save runlog

```
✓ Click-to-call conversion action created: {label}
✓ gadsId + gadsCallConversionLabel wired into brand.ts
✓ Conversion verification: PASS (tel: tap fires gtag conversion)
✓ Warm-pixel audience: customers/.../userLists/{id}
✓ Audience attached to ad group {id} at +{modifier}% bid (Observation mode)

Next steps:
- Check Google Ads UI in 24-48h — conversion status should flip to "Recording conversions"
- Audience populates as traffic hits {domain} — expect ~100 members before RLSA fires
- Run /ads-tracking again with a different ad group ID to attach the audience to more campaigns
- Consider upgrading to "calls from a website" (forwarding number) for connected-call tracking — see below
```

Write a runlog to `clients/{slug}/ads/tracking-runlog-{date}.md` with the conversion label, audience resource name, and ad group it's attached to.

---

## What this skill does NOT set up

- **Connected-call tracking ("calls from a website")** — the recommended upgrade. Uses a Google forwarding number injected by gtag that swaps the displayed phone number and counts calls ≥ a minimum duration (e.g. 60s), so you pay for *real conversations*, not taps. Worth doing once calls are flowing; requires the forwarding-number snippet + a phone-call conversion action with `type_`: `WEBSITE_CALL`. Click-to-call (this skill) is the day-1 proxy.
- **Call-from-ads (call asset) conversions** — separate, tracked automatically when call assets are added in `ads-campaigns`.
- **Enhanced conversions** (hashed identifiers) — not worth day-1 complexity.
- **Server-side tracking** (Cloudflare Worker → Google) — Ch 12 of the masterclass.
- **Display retargeting campaign** — the warm-pixel audience this creates is reusable there.

## Cost expectation

- No Anthropic API calls
- Google Ads API: $0
- Wall clock: ~5 minutes including verification
