---
name: no-call-whisper
description: Never use a Twilio/call-tracking whisper — calls must connect straight through
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7df3e6ce-2c8e-44e6-8321-b1d9bea3f86b
---

**RULE RETIRED (Santino 2026-08-10):** whisper is now a per-client choice, not a ban. Default stays no-whisper (straight connect); clients who want a source announcement get one (RestorationXpress runs "Call from Restoration AI" and keeps it). Never a press-any-key gate. The ads-call-tracking skill was updated to match.

Never configure a call whisper (no "press any key to accept", no source announcement) on Twilio call tracking or any call-routing setup. Calls always connect straight through to the forward line.

**Why:** User directive ("No call whisper please. Never"). A whisper adds friction/delay before the caller is connected, which hurts the emergency-restoration call experience.

**How to apply:** In [[ads-skills-suite]] / the `ads-call-tracking` skill, the TwiML `<Dial>` bridges directly to `<Number>` with no `<Say>` or `<Number url="">` whisper. Don't add one and don't ask about it. Recording stays an opt-in flag (off by default); whisper is simply never an option.
