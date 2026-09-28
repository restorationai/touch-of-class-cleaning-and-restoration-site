---
name: oneoff-sends-via-monica
description: "Every one-off client text Claude sends must go through scripts/monica_oneoff.py (Monica's send path + [CONTEXT] note), never the raw GHL key"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-27T20:15:32.284Z
---

Send one-off client texts ONLY with `python3 scripts/monica_oneoff.py --company CO-.. --body ".." --context ".." [--contact-id ..] --send`.

**Why:** 2026-09-27 Rachelle (Desert Valley): a raw-GHL-key send stamped Santino's userId and wasn't in Monica's sent ledger, so Monica treated it as a human mid-thread, held her instant reply (60-min quiet window) and would have deferred 12h, and she had no context for the answer. Santino: "Isn't she supposed to respond quickly?" A held webhook reply is also NOT retried once the hold ends (cursor moves past it); that bug is still open.

**How to apply:** the wrapper files a `[CONTEXT]` ops note (rides into compose, never parsed as a directive, since bodies starting with "[" are not directives) and sends via cc.send_message (machine-sent kv) + record_sent_message. Write the context so Monica can answer the likely replies herself.

Related: [[client-concierge]], [[greeting-name-law]], [[no-em-dashes]]
