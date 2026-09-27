---
name: phone-activation-pipeline-broken
description: Phone activation pipeline diagnosed AND repaired 2026-07-16; app fixes MERGED to main 2026-07-21 (95f4d0d) with visual_intake_enabled migration applied to prod via Supabase Management API
metadata: 
  node_type: memory
  type: project
  originSessionId: 6f8f2f2f-2d1c-4a69-aa1d-f3f21f669856
---

Diagnosed AND repaired 2026-07-16 (Joe Dominiak / ServiceMaster Restore KC, CO-1784218277458).

**FIX STATUS (2026-07-16):**
- n8n workflow `PlN-CWP8E8xCWh6zAtbHD` UPDATED IN PROD: Retell `inbound_agents:[{agent_id,weight:1}]` format, greeting_name fallbacks everywhere, new "Has Existing Trunk Setup?" IF node reroutes wrong-flag additional-line calls into full provisioning. First successful execution ever: 268882. (Note: PUT dropped non-API settings keys binaryMode/availableInMCP/timeSavedMode/callerPolicy.)
- Joe LIVE: +18444930080 purchased (subacct ACb25cb57c…, trunk TKe15a24…), in Retell w/ agent bound; row fixed to Main Line/primary; service_schedule M–F 9–5; agent_phone_1 set.
- Trachawk EMERGENCY (CO-1783501433757, +18773029587) and trachawk garbage restoration (CO-1782897412983, +18889267180) both repaired (trunks/creds/Retell) — likely DUPLICATE accounts, Santino to review/cancel one. Phantom +18884713619 row deleted.
- App fixes MERGED to main 2026-07-21 (merge 95f4d0d, Santino approved; migration applied to prod first via Supabase Management API `POST /v1/projects/nyscciinkhlutvqkgyvq/database/query`, CLI token in macOS keychain "Supabase CLI" go-keyring-base64). prod Supabase ref = nyscciinkhlutvqkgyvq (cahinyfcgpoobmgugkqe = staging). Branch contents: WizardManager auto-launches ActivationGateWizard post-core-setup; empty-state green button opens wizard; ProvisionNumberModal awaits webhook + dynamic isInitialLine; ActivationGateWizard pulls core-setup answers into initial row; sync maps onSiteResponseTime + standardAvailability; technician role "Mitigation PM"; rules modal saves work-auth + visual-intake. Migration `20260716200000_add_visual_intake_enabled.sql` MUST be applied at merge.

**Pipeline state:** n8n "Phone Number Activation" workflow (id `PlN-CWP8E8xCWh6zAtbHD`) has ZERO successful runs in retained history; last fully-working activation 2026-06-01 (+18667593783 in Retell). Retell removed `inbound_agent_id` from POST /import-phone-number ("Deprecated API usage") → even the correct Initial-Line branch fails AFTER purchasing the Twilio number.

**Three stacked bugs:**
1. UI: empty-state green "Get your phone number" button (AIDispatcher.tsx ~line 2205) opens ProvisionNumberModal (hardcodes `isInitialLine:false`) instead of ActivationGateWizard → n8n Additional-Line branch reads null `twilio_subaccount_sid` → POST to `/Accounts//IncomingPhoneNumbers.json` → 404. Nothing after CoreSetupWizard checkout auto-launches ActivationGateWizard, so this wrong button is the natural path.
2. App fires the webhook fire-and-forget and inserts `company_phone_numbers` row regardless → UI shows a number that doesn't exist (Joe: +18444930080, never purchased; row id ad5a4927 needs cleanup).
3. Retell deprecation (above). Also one 07-08 failure at Create SIP Trunk "Invalid Domain Name".

**Dead paid numbers:** Trachawk CO-1782897412983 (+18889267180, subacct ACeca1a3ca…) and CO-1783501433757 (+18773029587, subacct AC3fbbe207…) — Twilio numbers purchased 07-01/07-08 but NOT in Retell → dead lines being billed.

**Wizard settings-loss bugs (CoreSetupWizard → syncCompanySettingsToSupabase in lib/supabase.ts):**
- step 9 sends `onSiteResponseTime`, sync only maps `onsiteResponseMinutes` → response time silently dropped
- step 11 `standardAvailability` has NO mapping → companies.service_schedule stays []
- steps 5–7 write phone-rule fields to company_phone_numbers, but zero rows exist at wizard time → silent no-op for every new client
- step 10 technician insert (role "Lead") blocked by DB trigger ERR_TIER_ROLE_FORBIDDEN on Tier 1/Leakproof; error swallowed (console.error)
- Configure Rules modal (AIDispatcher.tsx ~1310) renders `visual_intake_enabled` + `send_work_authorizations_enabled` toggles but Save payload omits both (and visual_intake_enabled isn't a column) → "saved" toggles revert on reload

**Access:** n8n+Twilio master+Supabase service creds in rank-ai/.env; working Retell keys hardcoded in app repo supabase/functions (key_3ca7…, key_7b20…). Fresh app clone required — see [[app-source-github-not-desktop]].
