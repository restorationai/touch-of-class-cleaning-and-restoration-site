---
name: kickoff-prep-reminder
description: Post-demo kickoff-prep text flow — manual run done for Derek Reid 2026-07-20; BUILT + deployed 2026-07-20
metadata:
  type: project
---

Santino wants an automation: after a closed sales demo with a kickoff call booked, AI reviews the Fathom transcript, extracts what HE told the client to bring, and sends ONE friendly GHL text (never intimidating, "no stress if a piece is missing", no em dashes, single send).

**Manual run 2026-07-20 (the spec):** Fathom list_meetings (today) → demo "20 Water Damage Jobs Guarantee" w/ Derek Reid → transcript grep for asks (customer list spreadsheet, service-area zip codes, one crew photo, business formation docs + address) → GHL contact appointments confirmed "Derek Reid - Kick Off Call" 7/21 → sent via GHL POST /conversations/messages (type SMS, delivered, same thread as booking texts).

**BUILT (2026-07-20):** scripts/kickoff_prep.py + POST /kickoff-prep on rank-ai-api (https://rank-ai-api-production.up.railway.app). GHL workflow webhook fires on kickoff booking -> endpoint validates secret (KICKOFF_PREP_SECRET or LEAD_AUDIT_FUNNEL_SECRET) -> background thread polls Fathom external API every 10 min (max 30 tries; client is matched by TRANSCRIPT SPEAKER name, NOT calendar_invitees which only list Santino on GHL-booked Zooms) -> Claude extracts asks -> ONE GHL SMS + ONE SendGrid email -> tag kickoff-prep-sent (dedupe; also add manually to suppress). No asks found or no meeting -> internal notify email only. FATHOM_API_KEY set on rank-ai-api via Railway GraphQL (needs User-Agent header or 403 error 1010). Derek Reid pre-tagged (manual send already done). Original plan: ops_scheduler job; trigger = kickoff appointment booked on kickoff calendars; match same-day Fathom call by contact name/email; extract only asks LITERALLY stated in transcript; dedupe via contact tag kickoff-prep-sent; skip if Santino already texted a recap manually. Note: Santino usually PROMISES "I'll text you the list" on these calls, so the text fulfills a stated commitment. Related: [[client-concierge]] (Monica handles post-signup asks; this flow is pre-signup/trial kickoff).

## v2 post-meeting flow (2026-07-21, standard for all clients)
- Composer is meeting-date aware (says "yesterday" when sending the day after) and scheduling-aware: NEXT CALL=BOOKED (webhook passed appointment_time) references it; NOT BOOKED -> Claude extracts an EXPLICIT agreed date+time from transcript -> auto-books on kickoff calendar (KICKOFF_CALENDAR_ID env, default DcoatVel3rEw01lKoGlA, ignoreFreeSlotValidation) -> else ends with "let me know what day works" closing. Auto-book path NOT yet exercised live.
- TWO GHL webhooks feed the same endpoint: (1) kickoff-booked workflow WITH appointment_time, (2) demo-completed workflow (appointment status Showed on demo calendar) WITHOUT appointment_time. Dedupe tag prevents double-sends.
- Gregory Arianoff 07-21: email SENT (asks: customer list, PuroClean brand guide, team photo, job photos; ask-his-day closing); SMS IMPOSSIBLE — his +18083006764 is not SMS-capable (Twilio 21614 -> GHL permanent SMS DND; NOT an opt-out). Need his real cell; his GHL companyName typo fixed (was PuoClean). No kickoff booked (he must check Hawaii schedule; Santino floated Tue same-time next week).
