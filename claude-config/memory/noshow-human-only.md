---
name: noshow-human-only
description: LAW 09-18 (Amin incident) - no automation may ever mark a lead no-show; human-only. noshow_checker.py auto-bury branch must become report-only
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 996c1087-a104-44ea-9b1f-03b5fa628483
  modified: 2026-09-18T16:32:07.670Z
---

Santino (2026-09-18, Amin Mashouf / Dry Bros incident): **the only way anyone
is ever marked no-show in GoHighLevel is a human doing it manually.** No
script or workflow may auto-mark.

**Why:** Amin ATTENDED his 9/17 follow-up (rescheduled Zoom, Fathom notetaker
absent, nobody marked "showed", no note logged). `scripts/callist/`
`noshow_checker.py` (runs on Railway 13:00 UTC daily; live copy in the
standalone restorationai/Rank-AI-Call-List repo) hit rule 4 of its ladder
(no Fathom recording + no note = no-show), buried him in "No-Show (Long
Nurture)", tagged him, and the nurture texted "Amin?" — insulting a client
who showed up. Absence of evidence is not evidence of absence: reschedules
and Fathom-less calls look identical to no-shows.

**How to apply:** the checker's SHOWED auto-marking is fine (analytics); its
NO-SHOW branch must only REPORT (note/email listing suspected no-shows for
human confirmation), never move stages, tag, or mark appointments. When
fixing, patch the standalone Rank-AI-Call-List repo (the deployed copy),
not just rank-ai/scripts/callist/.
