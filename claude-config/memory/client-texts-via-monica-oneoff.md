---
name: client-texts-via-monica-oneoff
description: "Claude's one-off client texts go through scripts/monica_oneoff.py (files a [CONTEXT] note), never a raw _ghl POST"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 996c1087-a104-44ea-9b1f-03b5fa628483
  modified: 2026-09-28T17:01:52.195Z
---

scripts/monica_oneoff.py is the only way Claude sends a one-off client text (its docstring, 2026-09-27). It delivers as Monica and files a [CONTEXT] ops note so Monica can answer the client's reply herself. A raw `_ghl("POST", "/conversations/messages")` send leaves her blind to what was asked.

**Why:** On 09-21..28 Claude sent approved texts to Rob Carpenter, Kenny, Jim, Rachelle, Amin via raw _ghl, and Monica had no context for the replies.

**How to apply:** `python3 scripts/monica_oneoff.py --company CO-... --body "..." --context "what we asked and how to answer replies" --send`. Note: since 2026-09-04 all API sends carry Santino's userId + a marketplace appId; fetch_history treats appId rows as machine (fix dc2a24c1a, 09-28). See [[no-human-gates-on-client-requests]].
