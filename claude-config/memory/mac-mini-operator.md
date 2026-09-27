---
name: mac-mini-operator
description: "Mac Mini agent box LIVE 09-07 — repo at ~/dev/rank-ai, standing orders docs/MINI-OPERATOR.md, git-synced inbox clients/_ops/mini-inbox.md, reports clients/_ops/mini-reports/"
metadata: 
  node_type: memory
  type: project
  originSessionId: f2a4dda8-6875-426c-b9b2-412d862dd33a
  modified: 2026-09-07T16:22:11.508Z
---

Mac Mini set up 2026-09-06/07 as the browser-agent operator box (Antigravity Claude, same account). Repo at ~/dev/rank-ai (NOT Desktop, TCC). Secrets: .env + .gsc-agency-token.json in repo dir, gmail tokens ~/.config/rankai, portal creds ~/.rankai (AirDropped; all in [[secrets-vault]] too). Chrome persistent profile logged into agency Google + Bing ONLY (no GoDaddy per [[registrar-access-human-only]], no LSA per Santino 09-07 "stay away from LSA", no YouTube renames).

TWO-MACHINE CHANNEL (built 09-07, replaces copy-pasting prompts): git is the message bus. repo CLAUDE.md routes by hostname → Mini reads docs/MINI-OPERATOR.md at session start → works clients/_ops/mini-inbox.md checkboxes (MacBook Claude pushes assignments there), else derives from sweep queue/ledger. After every run it commits a report to clients/_ops/mini-reports/ — read those to see what it did. Supervised-first: 3 clean runs per playbook ON THE MINI before autonomy; citation submissions daytime-only (~11:30 PT window).

Session start prompt for Santino (only ever needed once per fresh session): "cd ~/dev/rank-ai, git pull, read CLAUDE.md and follow it."

First assignments queued in inbox: narestco Spotify connect (feed owner email switched to contact@ 09-07), then Houzz supervised batch of 2 (narestco + crew). Outstanding manual citations 09-07: Houzz/3BR/TrustAnalytica missing for 21 clients; 3BR+TrustAnalytica have NO playbooks yet (3BR is editorial/nomination); Reign wrong-data MapQuest+Yelp; ProRestoration +5 extra directories.
