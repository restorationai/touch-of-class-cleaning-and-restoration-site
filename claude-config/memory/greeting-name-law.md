---
name: greeting-name-law
description: "LAW 09-16 (Ashley/DryCor): greet ONLY the thread's on-file contact name; wrong-name send guard is live; one-shots never hardcode names"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-16T14:35:27.269Z
---

2026-09-16 incident: two DryCor post-meeting recaps opened "Rob" but
delivered to the PREFERRED contact's thread (Ashley Showalter, office).
One was a hand-written oneshot that hardcoded "Morning Rob" while sending
via resolve_contact (which targets the preferred contact).

**Why:** meeting recaps are the trap — the call is with the owner, the
thread belongs to the office contact. The app Contact Card
(integration_settings.contacts) is the canonical name source; GHL is
secondary.

**How to apply:**
- `wrong_name_violation()` in client_concierge.py blocks any outbound
  whose first-sentence vocative names a known person other than the
  thread's on-file contact (Rob==Robert prefix logic). Runs in
  send_message for EVERY sender, one-shots included.
- Never hardcode a greeting name in a oneshot: resolve the contact FIRST,
  greet with `contact_first_name()`, or use no name.
- Recaps: concise and human, 3-4 sentences, lead with the single action;
  detail lives in the app. (Santino's explicit feedback on the 09-16
  morning message, which was too long.)
- Related: [[no-em-dashes]], [[quiet-hours-outbound]],
  [[monica-never-claims-actions]]
