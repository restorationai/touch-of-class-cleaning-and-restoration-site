---
name: citations-rules-1001
description: 10-01 citations decisions — explicit keep or DBA-on-file only; Thumbtack/HomeAdvisor removed; FB Pages via Santino profile in Ignite portfolio; our tracking line for verification codes
metadata:
  type: project
---
Decisions 2026-10-01 (Santino):
- Citations start ONLY when the DBA filing is uploaded for the chosen name, or a RECORDED keep decision exists (rename_intent.decision=keep). "All candidates dismissed" no longer clears the gate (Reign looked cleared with no conversation).
- Thumbtack and HomeAdvisor are off every target list (SSN check / paid only). Existing ones are only recognized.
- Facebook Pages: we create them from Santino's own FB profile inside the Ignite Systems Business portfolio.
- Group B platforms (Yelp, Nextdoor, Angi): verify with the client's Twilio tracking line (codes land in ops_kv verification-codes:*), then swap the public phone to the real line; client code relay only where forced.
- BrightLocal: The Restoration Group was ordered 09-04 before the rule (no name decided); Veterans' BL location name mismatches his DBA (fix pending).
- A2P 10DLC pipeline (a2p_provision.py) fixed 10-01: TrustHub objects must live in the client SUBACCOUNT; ops-worker lacked TWILIO_MASTER_*; CRW held for legal name/entity. Davis cancelled (own Twilio).
Related: [[mac-mini-operator]], [[gray-area-results-stance]], [[setup-email-standard]].
