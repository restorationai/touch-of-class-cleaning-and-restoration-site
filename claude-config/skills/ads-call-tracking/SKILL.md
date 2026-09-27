---
name: ads-call-tracking
description: Set up Twilio-based call tracking for a Rank AI client's Google Ads landing pages. Provisions a local tracking number in the client's Twilio subaccount, routes it to their real business line via a Cloudflare Pages Function on the client's own site (optional recording; whisper announcement is a PER-CLIENT choice, off unless the client wants one), wires the tracking number into brand.ts as adsTrackingPhone so it displays ONLY on the noindex LPs (the main site keeps its real NAP number), and logs calls via Twilio's native call records. Phase A — pairs with the gtag click-to-call conversion from ads-tracking, which keeps Google Ads attribution. Use when the user says "set up call tracking", "add a tracking number", "Twilio call tracking", "ads-call-tracking", or as the paid upgrade after ads-tracking.
---

# Ads Call Tracking — Twilio (Phase A)

Provisions a Twilio tracking number for a client's Google Ads landing pages so inbound calls are routed, optionally recorded, and logged — using the client's existing Twilio **subaccount**. The number is shown on the **LPs only**; the main site keeps its real number.

**Why Twilio (not CallRail):** Rank AI already provisions a Twilio subaccount per client. Twilio is a programmable platform, so we build the call-tracking layer ourselves — for Phase A that's just number provisioning + routing + logging, which is straightforward via the API. No second vendor, no per-client subscription.

**Phase A scope (this skill):**
- Provision one local tracking number in the client's subaccount
- Route it to the client's real line via a Cloudflare Pages Function on the client's existing site (`functions/twilio/voice.ts`) — ships with the site, no separate infra
- Optional call recording (off by default). **Whisper is per-client** (Santino 2026-08-10): default is none, calls connect straight through; add a brief source announcement like "Call from Restoration AI" only when that client wants it.
- Display the tracking number on the LPs via `brand.adsTrackingPhone` (LP layouts already prefer it over `brand.phone`)
- Google Ads attribution stays on the **gtag click-to-call** conversion from `ads-tracking` — it fires in the browser where the gclid lives, so paid-call attribution is already handled
- Call data lives in Twilio's call logs, queryable via API anytime

**NOT in Phase A (see "Phase B" at the end):** number-pool DNI + gclid capture for keyword-level *connected-call* offline conversions into Google Ads. That's the CallRail-grade upgrade; do it once call volume justifies the build.

## When to invoke

- "set up call tracking for {client}"
- "add a Twilio tracking number"
- "ads-call-tracking"
- The paid upgrade after `ads-tracking` (click-to-call) is live

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/` — all paths below are relative to here.

---

## Credentials

In `rank-ai/.env`:
```
TWILIO_MASTER_ACCOUNT_SID=ACxxxxxxxx     # master/parent account
TWILIO_MASTER_AUTH_TOKEN=xxxxxxxx
```

Per-client subaccount SID lives in `clients/{slug}/plan-input.json` as `twilio_subaccount_sid`. Two supported paths:
- **Subaccount exists** (the norm — Rank AI provisions one per client): use its SID. Authenticate to subaccount resources with the **master** SID+token (parent creds can access subaccount resources) OR a per-client subaccount token if provided.
- **No subaccount yet:** create one with master creds (`POST /2010-04-01/Accounts.json`, `FriendlyName={slug}`), then save the returned SID to `plan-input.json`.

Never hardcode tokens. Source env: `set -a; . rank-ai/.env; set +a`.

---

## Pre-flight

1. **Determine client slug.** Ask if not provided.
2. **Load** `clients/{slug}/plan-input.json` → `brand.phone` (the REAL line = forward target), `brand.primaryState`/area code, `twilio_subaccount_sid`, `domain`.
3. **Verify** `sites/{slug}/src/components/lp/*.astro` exist and reference `displayPhone`/`adsTrackingPhone` (the LP layouts must support the tracking-number swap — current `split-test-*` templates do). If they only use `brand.phone`, copy the current templates in first (see `ads-landing-page`).
4. **Confirm Twilio creds** resolve: `curl -s -u "$TWILIO_MASTER_ACCOUNT_SID:$TWILIO_MASTER_AUTH_TOKEN" https://api.twilio.com/2010-04-01/Accounts.json` returns 200.

---

## Intake questions

Pre-fill from `plan-input.json`. Ask:

1. **Forward-to number** — the client's real business line that calls should ring. Default: current `brand.phone`. (This becomes the `<Dial>` target; the Twilio number is what shows on the LPs.)
2. **Area code** — for a local-looking tracking number. Default: area code of `brand.phone`.
3. **Recording** — record calls? Default: **no**. If yes, warn: adds storage cost and a **two-party-consent** consideration — several states require caller notification; add a recording disclaimer to the greeting if enabled.
4. **Subaccount** — confirm `twilio_subaccount_sid` (or create one).

**Whisper is a per-client choice** (Santino 2026-08-10, replacing the old never-whisper rule): default to none, calls connect straight through. If the client wants a source announcement (e.g. RestorationXpress runs "Call from Restoration AI"), add a short `<Say>` to the answering side only. Never a "press any key to accept" gate.

**Confirmation gate:**
> "Provision 1 local number (area code {X}) in Twilio subaccount {sid}, route to {forward_number}, recording {on/off}. The number will display on the {slug} landing pages only (main site keeps {brand.phone}). This buys a billable number (~$1–2/mo + per-minute usage) on the client's subaccount. Proceed?"

Do not proceed until confirmed.

---

## Step 1 — Resolve/create subaccount

If `twilio_subaccount_sid` is missing:
```bash
curl -s -X POST "https://api.twilio.com/2010-04-01/Accounts.json" \
  -u "$TWILIO_MASTER_ACCOUNT_SID:$TWILIO_MASTER_AUTH_TOKEN" \
  --data-urlencode "FriendlyName={slug}"
```
Save `sid` from the response into `clients/{slug}/plan-input.json` as `twilio_subaccount_sid`. Use this SID as `{SUB}` below. Authenticate subaccount calls with `-u "$TWILIO_MASTER_ACCOUNT_SID:$TWILIO_MASTER_AUTH_TOKEN"` but target the subaccount SID in the path.

---

## Step 2 — Create the call-routing TwiML (Cloudflare Pages Function)

Host the routing TwiML on the client's **own Cloudflare Pages site** — every client site already deploys there, so this ships with the site via the normal `sync-deploy`, needs no separate Twilio Serverless/Worker infra, and is versioned in the repo.

Create `sites/{slug}/functions/twilio/voice.ts`:

```ts
// Twilio Voice webhook — returns TwiML that forwards the tracking number to the
// real business line. Generated by ads-call-tracking. The forward number is the
// client's public business line (not a secret). Regenerate if it changes.
const FORWARD_TO = "+12068830333"; // {brand.phoneRaw} — the REAL line calls ring
const RECORD = false;              // call recording (Step intake)

const handler: PagesFunction = () => {
  const rec = RECORD ? ' record="record-from-answer"' : "";
  const twiml =
    `<?xml version="1.0" encoding="UTF-8"?>` +
    `<Response><Dial${rec} answerOnBridge="true"><Number>${FORWARD_TO}</Number></Dial></Response>`;
  return new Response(twiml, { headers: { "Content-Type": "text/xml" } });
};

// Twilio POSTs the webhook; allow GET too for quick browser/Tag-Assistant checks.
export const onRequestPost = handler;
export const onRequestGet = handler;
```

- **Whisper per client** — default: `<Dial>` bridges straight to `<Number>`. If this client opted into a whisper, use a short `<Number url>` whisper with the announcement; never a keypress gate.
- `record`: set `RECORD = true` only if recording was approved in intake (add a recording disclaimer to a brief `<Say>` greeting *for the caller* if required by state law — but never an agent whisper).
- `answerOnBridge="true"` so the caller hears ringing, not silence.
- The webhook URL the number will point to is `https://{domain}/twilio/voice` (live after Step 6 deploy).

> Optional hardening: validate Twilio's `X-Twilio-Signature` header to reject non-Twilio requests. Not required for Phase A (the only thing exposed is the already-public forward number).
>
> Alternative hosts if the client has no Cloudflare Pages site: a Twilio Function (Serverless API) or a Cloudflare Worker returning the same TwiML. The Pages Function is preferred because it rides the existing deploy.

---

## Step 3 — Provision the tracking number

Search + buy a local number in the subaccount near `{area_code}`:
```bash
# search
curl -s -G "https://api.twilio.com/2010-04-01/Accounts/{SUB}/AvailablePhoneNumbers/US/Local.json" \
  -u "$TWILIO_MASTER_ACCOUNT_SID:$TWILIO_MASTER_AUTH_TOKEN" \
  --data-urlencode "AreaCode={area_code}" --data-urlencode "VoiceEnabled=true"

# buy + point Voice webhook at the client site's Pages Function
curl -s -X POST "https://api.twilio.com/2010-04-01/Accounts/{SUB}/IncomingPhoneNumbers.json" \
  -u "$TWILIO_MASTER_ACCOUNT_SID:$TWILIO_MASTER_AUTH_TOKEN" \
  --data-urlencode "PhoneNumber={chosen_e164}" \
  --data-urlencode "VoiceUrl=https://{domain}/twilio/voice" \
  --data-urlencode "VoiceMethod=POST" \
  --data-urlencode "FriendlyName={slug} · LP tracking" \
  --data-urlencode "StatusCallback={optional_status_webhook}"
```
> The `VoiceUrl` resolves once Step 6 deploys the Pages Function. Buying the number first is fine — just don't unpause ads until the function is live (verified in Step 5).
**Idempotent:** if `clients/{slug}/ads/call-tracking.json` already records a tracking number, reuse it — don't buy another.

Optionally set a `StatusCallback` to a logging endpoint, but it's not required for Phase A — Twilio retains queryable call records (`GET /2010-04-01/Accounts/{SUB}/Calls.json`) and recordings (`/Recordings.json`).

---

## Step 4 — Wire the tracking number into the LPs (LP-only swap)

Add to `sites/{slug}/src/lib/brand.ts` (use `Edit`, don't rewrite):
```typescript
export const brand = {
  // ...existing fields (phone stays the REAL number for the main site / NAP)
  adsTrackingPhone: "(206) 555-0142",      // formatted Twilio number — display
  adsTrackingPhoneRaw: "+12065550142",     // E.164 — tel: href
} as const;
```

The LP layouts already use `const displayPhone = (brand as any).adsTrackingPhone ?? brand.phone` (and `displayPhoneRaw`), so the tracking number appears on every LP automatically and **no `.astro` edits are needed**. The main site's `brand.phone` is untouched → NAP stays consistent for local SEO.

---

## Step 5 — Verify routing (after Step 6 deploy)

The voice webhook must be live first, so run this after the deploy in Step 6.

- Confirm the webhook returns valid TwiML: `curl -s https://{domain}/twilio/voice` → should be `<Response><Dial ...><Number>+1…</Number></Dial></Response>`.
- Call the tracking number from a phone; confirm it rings the forward line straight through (no whisper) and, if recording is on, a recording appears under `GET /2010-04-01/Accounts/{SUB}/Recordings.json`.
- Or use Twilio Console → Monitor → Logs → Calls to see the call + its routing.
- Confirm the LP shows the tracking number: `curl -s https://{domain}/lp/{first-slug}/ | grep -o '{tracking_number_digits}'`.

---

## Step 6 — Commit, deploy, runlog

```bash
cd ~/Desktop/mywebsitecode/rank-ai
git add sites/{slug}/src/lib/brand.ts sites/{slug}/functions/twilio/voice.ts clients/{slug}/plan-input.json
git commit -m "feat({slug}): Twilio LP call tracking number + voice webhook"
python3 scripts/content_writer.py sync-deploy --slug {slug}
```

This deploy makes `https://{domain}/twilio/voice` live — the number's `VoiceUrl` now resolves. Run Step 5 verification after this completes.

Write `clients/{slug}/ads/call-tracking.json`:
```json
{
  "subaccount_sid": "AC...",
  "tracking_number": "+12065550142",
  "forward_to": "+12068830333",
  "voice_webhook_url": "https://{domain}/twilio/voice",
  "recording": false,
  "provisioned_at": "{date}"
}
```

Report:
```
✓ Tracking number {number} provisioned in subaccount {sid}
✓ Routes to {forward} · connects straight through (no whisper) · recording {on/off}
✓ Shown on {slug} LPs only — main site keeps {brand.phone} (NAP intact)
✓ Google Ads attribution: gtag click-to-call (from ads-tracking) — unchanged
✓ Call records + recordings: Twilio API (GET /Calls.json, /Recordings.json)
```

---

## How this fits the conversion stack

| Layer | Tool | Purpose |
|---|---|---|
| Ads conversion (attribution) | gtag click-to-call (`ads-tracking`) | Fires in-browser with gclid → keyword-level Ads conversion |
| Call infrastructure | Twilio (this skill) | Real number, routing, recording, call log, lead verification |
| Phase B (later) | Twilio number-pool DNI + gclid capture | Connected-call → Ads offline conversion (replaces gtag for precision) |

Phase A gives a complete working system: Ads attribution from gtag + true call data from Twilio. Phase B is a precision upgrade, not a prerequisite.

---

## Phase B — connected-call attribution (future, not built)

To make *connected calls* (not taps) the Google Ads conversion with keyword attribution:
1. Provision a **pool** of Twilio numbers.
2. On LP load, capture `gclid` and assign the visitor a number from the pool; store `gclid ↔ number ↔ timestamp` (Cloudflare D1/KV).
3. On call completion (Twilio status callback, duration ≥ threshold), look up the gclid for the dialed number and upload a Google Ads offline click conversion (`ClickConversionService`) with that gclid.
This rebuilds CallRail's core on Twilio. Scope it as a Phase B build when volume justifies it.

## Cost expectation

- No Anthropic API calls
- Twilio: ~$1–2/number/mo + ~$0.013–0.025/min usage (on the client's subaccount) + recording storage if enabled
- Wall clock: ~5–10 minutes
