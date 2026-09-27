---
name: sales-followup-system
description: Post-demo automation (scripts/sales_followup.py) — recap + full audit + fixed proposal from whichever rep ran the demo; approval mode default; Levi Fathom key still needed
metadata: 
  node_type: memory
  type: project
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-07T03:35:14.241Z
---

BUILT 2026-09-06 (spec settled with Santino + Levi): `scripts/sales_followup.py`, scheduled on the Railway ops-worker every 30 min (ops_scheduler JOBS "sales-followup").

Gate ladder, ALL fail-closed:
1. Title must contain "Rank #1 On Google And Chat GPT" (normalized, ChatGPT/Chat GPT both match)
2. "Follow Up" in title → recap only, never audit/proposal
3. Host (Fathom recorded_by) must be in REPS map: levi@restorationai.io=Levi, ignitesystems3@gmail.com + contact@=Santino (Santino's Fathom records under the ignite Gmail)
4. Prospect: invitee email → GHL contact, else name-from-title → single demo-tagged contact (GHL-booked Zooms carry NO invitee email, [[kickoff-prep-reminder]] pattern); must have a "rank ai demo booked*" tag
5. Secured exclusion: EXACT tag set only (location has both "client secured" AND "client not yet secured" — never substring) + active-company contact emails from [[client-concierge]] fetch_companies
6. Transcript discernment (Claude, structured output — schemas need additionalProperties:false): signed-up-on-call or any doubt → hold + notify rep

On send: tags "Full Audit Sent" (distinct from funnel "audit sent") + "Proposal Sent" + "Demo Summary Sent". Audit = lead_audit.run_audit(email_mode="none") full R2 report. Proposal = fixed 10-deliverable template (sales/proposals pattern, no em dashes), price from transcript else $997, hosted at PUBLIC_BASE/sales-proposals/{rid}/proposal.html.

APPROVAL MODE default: package emails to rep for manual forward (no tags stamped). Flip: SALES_FOLLOWUP_AUTOSEND=1 on Railway worker AND GH repo variable SALES_FOLLOWUP_AUTOSEND (workflow reads vars.).

TRIGGER PATHS (09-06 pt 2): fathom-webhook edge fn (registered on Santino's Fathom 08-10) now dispatches BOTH client-ops-sync.yml and sales-followup.yml on recording-ready → recap lands minutes after the call. Railway 30-min poll = self-healing backstop. Claim lock ("processing:<iso>" in ops_kv state, fresh read per meeting, stale >2h reprocessable) prevents double-sends between the two paths. Levi's Fathom account needs its own webhook registered (same edge fn URL) once his key arrives.

OPEN: Levi's demos record under HIS Fathom account — need his API key in FATHOM_SALES_API_KEYS (comma-separated) on the Railway worker or his demos are invisible. GHL emailFrom=rep is attempted with plain-send fallback (untested against a live send as of build date). State: ops_kv "sales-followup-state" (baselines on first run).
