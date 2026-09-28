---
name: verification-code-self-fetch
description: "2FA/verification codes are fetched automatically via scripts/verification_code.py (sender-agnostic GHL search + ops_kv); never ask Santino for a code, never watch one thread"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-27T21:06:57.210Z
---

Any SMS verification code to the agency line (..49 / 805, GHL) or a client Twilio tracking number is fetched by the agent itself:
`python3 scripts/verification_code.py wait --since <epoch right before requesting> --match <apple|google|...>`.

**Why:** 2026-09-27 Apple Podcasts on the Mini: a relay watching ONE GHL thread missed both codes because Apple texts from a NEW sender number each time (+12057938166 Aug, +14084189454 Sept). Santino: "make sure that, moving forward, either you or it would recognize this and automatically retrieve that code." I also nearly handed the Mini a stale Aug code: always compare the text's timestamp to the request time.

**How to apply:** it's a standing rule in docs/MINI-OPERATOR.md. The mini-handoff:apple-2fa relay keys are retired. Codes never go in git.

Related: [[mac-mini-operator]], [[browser-agent-suite]]
