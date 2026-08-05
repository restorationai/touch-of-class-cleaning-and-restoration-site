# Pre-meeting audit webhooks (GHL → Rank AI)

Two flows feed the same audit engine. Pick by **who supplied the website**:

| | Funnel flow | Staff-booked flow |
|---|---|---|
| Trigger | OpDigital application **form submitted** | Team member **books an appointment** (reignite / sales call) |
| Endpoint | `POST /lead-audit` | `POST /lead-audit/ghl-appointment` |
| Website comes from | the form field the lead typed | the **existing GHL contact record** |
| Contact | may not exist yet (gets created) | already exists — we are handed its id |
| Body | hand-mapped merge fields | raw GHL payload is fine |

Everything after "audit starts" is identical: same 5-box report, same teaser
image, same five custom fields, same failure tags.

---

## A. Funnel flow (form) — unchanged

1. Trigger: Form Submitted → the OpDigital application form.
2. Action: **Custom Webhook**
   - Method: POST
   - URL: `https://rank-ai-api-production.up.railway.app/lead-audit`
   - Content-Type: application/json
   - Body:
     ```json
     {
       "website": "{{contact.website}}",
       "name": "{{contact.first_name}} {{contact.last_name}}",
       "email": "{{contact.email}}",
       "phone": "{{contact.phone}}",
       "source": "opdigital",
       "secret": "5a33f1097b63b7063c3cca4b95000fb3"
     }
     ```
3. If the form has a business-name field but no website, send `business_name`
   instead of `website` — the API resolves the site from their Google listing.

This endpoint is strict on purpose (public-facing): it **requires** a valid
email, a 10-digit phone, and a resolvable website, and it enforces public rate
caps (10/day global, 3/IP, 2/domain).

---

## B. Staff-booked flow (appointment) — `POST /lead-audit/ghl-appointment`

Built 2026-08-04 after Hernany Da Silva (Restore & Repel) was booked and got
"It came back graded ." with an invalid media URL: **no audit had ever run for
him.** Nothing fires an audit when a human books the call — only the form did.
The nurture SMS merged five empty fields.

### GHL action config (paste-and-go)

- Trigger: **Appointment** (Customer Booked / Appointment Status = Confirmed) on
  the reignite + sales-call calendars.
- Action: **Send Webhook**
  - Method: **POST**
  - URL: `https://rank-ai-api-production.up.railway.app/lead-audit/ghl-appointment`
  - Headers:
    - `Content-Type: application/json`
    - `X-Rank-AI-Secret: 5a33f1097b63b7063c3cca4b95000fb3`
  - Body:
    ```json
    {
      "contact_id": "{{contact.id}}",
      "website": "{{contact.website}}",
      "name": "{{contact.first_name}} {{contact.last_name}}",
      "email": "{{contact.email}}",
      "phone": "{{contact.phone}}",
      "business_name": "{{contact.company_name}}",
      "source": "ghl-appointment"
    }
    ```

**The only field that actually matters is `contact_id`.** Everything else is
read back off the live contact record. If GHL's "Send Webhook" is left on its
default full payload with no custom body, that still works — the endpoint
digs `contact.id` out of the raw payload.

The secret may travel three ways, any one is enough: the `X-Rank-AI-Secret`
header (preferred — keeps it out of the body), `?secret=…` on the URL, or a
`"secret"` key in the body. Wrong/missing secret → `403`.

### The website field

`{{contact.website}}` is the **standard** GHL contact field (the one already
populated on the contacts, e.g. Hernany's `https://Restorerepel.com`) — not a
custom field. Capitalisation and `https://` are normalised for us.

If it is empty the endpoint also checks the custom fields
`contact.business_website` (`aItF7CZwJrzTSPERe9Ij`) and `contact.website_info`
(`FCB2cajq5GCNrbrI2qqq`).

### Website resolution order

1. `website` on the contact record
2. custom field `business_website`, then `website_info`
3. **Path B** — Google listing lookup by company name (DataForSEO), which also
   rescues a **typo'd** website: a host that does not resolve in DNS is treated
   the same as a missing one. Monique Curchy's contact carried
   `ww.rapidreliefrestoration.net` (2026-08-05) and died on exactly this.
4. Still nothing → **no silent failure**: the contact is tagged
   `audit failed` **and** `audit needs website`, the team gets the standard
   "[Rank AI] Lead audit FAILED" email, and the response is
   `{"status": "no_website"}`. Add the website to the contact and re-fire.

### Responses (always HTTP 200 so GHL never retry-storms)

| status | meaning |
|---|---|
| `queued` | audit running, ~5 min; fields land on the contact |
| `already_audited` | contact already has grade + teaser AND a completed audit for that domain within 30 days — send `"force": true` to re-run anyway |
| `no_website` | tagged + team emailed, see above |
| `rate_limited` | 3 audits already run for this domain today |

### Why this endpoint exists rather than reusing `/lead-audit`

- It takes a **contact id** and treats the live record as the source of truth,
  so delivery writes to that exact contact. `/lead-audit` searches by
  email/phone, which finds nothing for contacts with no phone (Addi McCamon,
  TJ Stoian) and can land on the wrong duplicate.
- It does not demand a valid email + 10-digit phone — a staff-booked contact
  may have neither, and in sales mode the lead is never emailed anyway.
- It swallows the full GHL payload instead of requiring hand-mapped fields.
- Public rate caps do not apply (it is secret-gated); the 30-day dedupe plus a
  3/domain/day ceiling are the guards instead.

---

## What happens after either flow (~5 min, no ops SMS)

- Full 5-box audit report rendered + hosted (R2)
- Teaser image generated (business name + issue count, no findings revealed)
- Written to the contact's custom fields:
  - `audit_report_url` — `f6fg4wFpyEVJk1Z6aqRh`
  - `audit_teaser_image_url` — `KB8K7VAiYQqfisQTKKim`
  - `audit_grade` — `f1ldfttQWYKh0rJNwSWq`
  - `visibility_grade` — `ckDCOW0NCeWYFSVR5dxR` (alias used by the SMS templates)
  - `audit_cities` — `PGpMcm29W36LvrfHKnkr`
- Note on the contact with report + teaser links
- The LEAD receives NOTHING from either flow — the nurture sequence decides
  what they see.

Nurture usage: in any email/SMS step, reference
  `{{contact.audit_teaser_image_url}}`   ← attach/embed as the image
  `{{contact.audit_report_url}}`         ← NEVER send this one to the lead

## REQUIRED workflow guard (add in GHL UI — incident 2026-08-01)

Isaac Gomez's audit died on a WAF 403 before any field was written; the
nurture SMS still fired and merged EMPTY fields — the lead received
"It came back graded ." with an invalid media attachment. Hernany Da Silva hit
the same message on 2026-08-04 by a different route (no audit ever ran).

The API tags the contact with exactly ONE of two mutually-exclusive failure
tags whenever a funnel audit fails (and the audit itself is far more resilient
to bot-blocking):

- **`website down`** — the site is GENUINELY unreachable: dead/typo'd
  domain (NXDOMAIN) or nothing accepting connections on ports 443/80.
  A site that answers with ANY HTTP status (even a 403 bot-block, like
  Isaac's) can never get this tag — it is safe to tell these leads their
  site is not up.
- **`audit failed`** — every other failure (crawler blocked but site is
  up, parse errors, our-side timeouts). The site may be working fine.
  The staff-booked flow adds **`audit needs website`** alongside it when the
  contact simply has no website on file.

The SMS step must be gated on these in the workflow — three branches:

1. **Fields populated** (`audit_grade` is not empty AND
   `audit_teaser_image_url` is not empty AND neither failure tag present)
   → send the existing report SMS (grade + teaser image).
2. **Tag `website down`** → send the dead-site message, NO merge fields:
   "We just tried to check out your website and it's not even up and
   running. What's going on with that?"
3. **Anything else** (tag `audit failed`, or fields empty with no tag =
   audit still running) → NO automated lead-facing SMS. Notify the team
   instead. Never guess: falsely texting a lead that their working site
   is down is worse than silence, and empty merges send "graded ." again.

This guard is what makes the staff-booked flow safe too: the audit takes ~5
minutes, so a booking-triggered SMS sent immediately will ALWAYS merge empty
fields. Either delay the SMS step past the audit or gate it on branch 1.

The team already gets a "[Rank AI] Lead audit FAILED" email on every
failure (it names the classification) — re-run the audit, which fills the
fields, before manually sending the report SMS.

## Manual re-run

```bash
curl -X POST https://rank-ai-api-production.up.railway.app/lead-audit/ghl-appointment \
  -H "Content-Type: application/json" \
  -H "X-Rank-AI-Secret: $LEAD_AUDIT_FUNNEL_SECRET" \
  -d '{"contact_id":"IiZNqoMUMGgi5glVkEpy","force":true}'
```
