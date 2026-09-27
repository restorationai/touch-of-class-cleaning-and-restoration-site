---
name: onlinejobs-hiring-screen
description: "OnlineJobs.ph applicant screening playbook: state, policy, and what still needs Santino"
metadata: 
  node_type: memory
  type: project
  originSessionId: 28dab4da-01e7-4aac-99a0-cd45e3436d67
  modified: 2026-08-08T01:51:11.720Z
---

Built 2026-08-07: `browser_agent/playbooks/onlinejobs_ph.py` screens applicants on
Santino's OnlineJobs.ph job posts and answers them. Rides the existing chassis
([[browser-agent-suite]]): dry-run default, kill switch, audit shots, ledger.

**State**: post "Local SEO and AI Search Specialist" (hash `7axBqq3d`), 61 applicants,
none replied to yet. Dry run scored all 61 and wrote a review file to
`browser_agent/runtime/hiring/` (gitignored, applicant PII). AWAITING SANTINO'S
REVIEW of that file before any `--live` send. Two other posts exist and are NOT
in scope: Video Editor (33 applicants), Customer Onboarding (26).

**Screening policy Santino set (08-07)**: must be social, great English, confident,
and WILLING TO JOIN CLIENT KICKOFF/ONBOARDING CALLS; plus availability, real SEO
examples, Claude/AI usage, technical depth. Design call: none of the first four are
knowable from an application and self-report is worthless, so the shortlist reply
asks for a 60-90s VIDEO answering how they feel about client calls. That one
artifact tests English + confidence + presence and screens out anyone who will not
go on camera with a client. Scored dimensions (application only): seo_evidence
(weight 3), english_written, ai_tooling, technical_depth, effort_fit. Shortlist
threshold 30/50.

**Credentials**: `~/.rankai/portal-creds.json` key `onlinejobs.employer` (chmod 600).
Password came through chat in plaintext on 08-07, worth rotating.

**Hard-won operational facts are in `browser_agent/README.md`** (v2 vs www hosts,
human-only login, JSON API endpoints, ground-truth dedupe via message `owner`,
429 backoff). The one worth repeating: a rate-limited applicant used to be SKIPPED,
which means never contacted, and 49 of 61 looks identical to a complete run. Never
let this playbook drop an applicant silently.
