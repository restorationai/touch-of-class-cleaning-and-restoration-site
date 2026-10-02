# SMS compliance: what carrier review checks

Two registrations exist, and they are different things:

- **Toll-free verification**: covers a client's 8xx number, which is their AI answering line and their texting line for review requests and missed-call texts. It runs fully automatically: `scripts/tollfree_autoreg.py watch` runs every 2 hours (`.github/workflows/tollfree-watch.yml`). It submits once the client has the toll-free line, a Twilio subaccount and an EIN, and auto-resubmits on known rejection reasons.
- **A2P 10DLC**: covers texting from a *local* number. The steps are business profile, then A2P bundle, then brand, then campaign. `scripts/a2p_provision.py` advances each client hourly through the ops worker, but a client only enters the pipeline when someone starts it (buys the local number and sets `company_phone_setup.a2p_state`).

The rules below live as code in `scripts/sms_compliance.py`, which both pipelines call before submitting. Keep this list and that file in sync.

## Lessons (each one is a rejection we already paid for)

1. **Legal name plus DBA.** DryCor, 2026-09/10, error 30484 ("Business Name Must Match Official Records").
   - The brand alone ("DRYCOR RESTORE") was rejected, and so was the legal name alone.
   - What passes: BusinessName = the entity the EIN belongs to (`company_phone_setup.legal_business_name`), DoingBusinessAs = the brand, and AdditionalInformation stating "{brand} is the trade name of {legal}".
2. **The website must name the legal entity.** Reviewers open the site.
   - The footer reads "© {legal}, doing business as {brand}". `build_site.py` renders this automatically whenever the vaulted legal name differs from the brand.
   - The privacy and terms pages state the trade-name relationship.
   - Preflight holds the submission if the site does not show it.
3. **EIN with identifier.** DISS, 2026-09-08, error 30527. Send BusinessRegistrationNumber **and** BusinessRegistrationIdentifier=EIN.
4. **SMS privacy clause.** A2P campaign vetting; the Davis campaign failed 2026-10-01.
   - The privacy page must say mobile numbers and SMS opt-in data are never shared with third parties for marketing.
   - It must also describe message frequency, data rates, STOP and HELP.
   - Preflight holds campaign submission until this is live.
5. **Physical address.** A2P customer profiles reject PO boxes; use the street address.
6. **Entity type** must match the IRS record (LLC vs Corporation vs sole proprietor). `a2p_state.business_type` overrides the LLC default. Davis was a corporation.
7. **A2P objects live in the client's subaccount.** The secondary profile, end users, address and A2P bundle are created in the client's Twilio subaccount and linked to our approved ISV primary profile in the master. Built in the master, every brand failed with "Unable to fetch A2P Profile Bundle".
8. **Don't wait on Twilio approvals mid-chain.** Twilio's ISV guide says the next step can proceed while a profile is in review. Stop only on a rejection.
9. **Business email on the business domain.** Dry Bros was rejected 2026-09-10 ("Business Email Address Must Use an Official Domain") and Flood Fixers 2026-08-04 ("Business Information Could Not Be Verified").
   - The contact email must be @their-domain, never Gmail or another free mail service. Preflight holds the submission otherwise.
   - Never put "DBA" inside the business name ("Good Home Construction LLC DBA Flood Fixers"). The legal entity goes in BusinessName and the brand goes in DoingBusinessAs.
10. **Rejections have an edit window** (about 2 weeks). Inside it, fix and resubmit the same verification. After it closes, delete it and submit a new one. DISS sat rejected for a week because the retry didn't know the 30488 wording; it does now.
11. **Never register the client's toll-free number into a 10DLC campaign.** A2P uses the local number bought for it (`a2p_state.number_sid`).
