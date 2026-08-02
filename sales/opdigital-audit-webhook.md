# OpDigital application → automatic pre-meeting audit

GHL workflow setup (one time, in GHL UI):

1. Trigger: Form Submitted → the OpDigital application form.
2. Action: **Custom Webhook**
   - Method: POST
   - URL: https://rank-ai-api-production.up.railway.app/lead-audit
   - Content-Type: application/json
   - Body:
     {
       "website": "{{contact.website}}",
       "name": "{{contact.first_name}} {{contact.last_name}}",
       "email": "{{contact.email}}",
       "phone": "{{contact.phone}}",
       "source": "opdigital",
       "secret": "5a33f1097b63b7063c3cca4b95000fb3"
     }
3. (Optional) If the form has a business-name field but no website, send
   "business_name" instead of "website" — the API resolves the site from
   their Google listing.

What happens automatically (~5 min later — no ops SMS; your workflow automation owns all notifications):
- Full 5-box audit report rendered + hosted (R2)
- Teaser image generated (business name + issue count, no findings revealed)
- BOTH URLs written to the contact's custom fields:
    audit_report_url        (field id f6fg4wFpyEVJk1Z6aqRh)
    audit_teaser_image_url  (field id KB8K7VAiYQqfisQTKKim)
- Note on the contact with report + teaser links
- The LEAD receives NOTHING from this flow — the nurture sequence decides
  what they see.

Nurture usage: in any email/SMS step, reference
  {{contact.audit_teaser_image_url}}   ← attach/embed as the image
  {{contact.audit_report_url}}         ← NEVER send this one to the lead

## REQUIRED workflow guard (add in GHL UI — incident 2026-08-01)

Isaac Gomez's audit died on a WAF 403 before any field was written; the
nurture SMS still fired and merged EMPTY fields — the lead received
"It came back graded ." with an invalid media attachment.

The API now tags the contact **"audit failed"** whenever a funnel audit
fails, and the audit itself is far more resilient to bot-blocking. But the
SMS step must ALSO be gated in the workflow:

1. Immediately before the report SMS step, add an If/Else condition:
   - `audit_grade` is not empty  AND
   - `audit_teaser_image_url` is not empty  AND
   - contact does NOT have tag `audit failed`
2. TRUE branch → send the existing SMS (grade + teaser image).
3. FALSE branch → send a no-merge fallback ("Still finishing up your
   report — I'll text it over shortly.") or simply skip + notify the team.
   NEVER reference {{contact.audit_grade}} / the teaser URL in this branch.

The team already gets a "[Rank AI] Lead audit FAILED" email on every
failure — re-run the audit, which fills the fields, before manually
sending the report SMS.
