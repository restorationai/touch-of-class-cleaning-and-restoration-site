---
name: ads-journal-system
description: "Every Rank AI client has clients/{slug}/ads-journal.md — read it before touching their Google Ads, log after every change"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4d36230a-30f9-4230-8ffa-d814dc9fef8b
---

Each client has a running ads ops log at `rank-ai/clients/{slug}/ads-journal.md` (markdown, newest-first, git-tracked). It records what we changed, why, and what to watch — the context a cold read of the live account can't give you.

**Always read it before viewing/changing a client's ads; add an entry after any change.**

- List / read:  `python3 scripts/ads_manager.py note --slug {slug}`
- Add a note:   `python3 scripts/ads_manager.py note --slug {slug} --kind watch --add "..."` (kinds: note | watch | bid | budget | review)
- It auto-prints at the top of `ads_manager.py report`.
- Change commands (set-budget / set-bid-strategy / pause / enable / add-negatives / apply-negatives) **auto-append** an entry on success.
- The weekly `ads_review.py` cron shows prior entries in its email and appends a weekly outcome entry (real `--apply` runs only).

**Why this exists:** on 2026-06-22 I misdiagnosed narestco's account from a context-free live read — called the live SKAGs ("National Restoration Construction - {service}") the problem and recommended re-enabling the legacy-off `narestco-Search-2`. The journal (surfaced in `report`) prevents exactly that.

Built in commit a505685. The ads-campaigns skill documents the read-first/log-after protocol. See [[narestco-paid-and-geogrid-state]] and [[ads-skills-suite]].
