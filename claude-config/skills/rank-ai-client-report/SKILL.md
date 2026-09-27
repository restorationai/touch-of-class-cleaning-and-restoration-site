---
name: rank-ai-client-report
description: Generate a monthly HTML client report summarizing posts written, site health verdict, refresh activity, and upcoming work for one Rank AI client. Output goes to clients/{slug}/reports/{YYYY-MM}-monthly.html — self-contained HTML suitable for email delivery (inlined styles, R2-hosted assets). Use when the user says "generate monthly report for {client}", "client report", "send monthly summary", "rank-ai-client-report", or "show me what we did for {client} this month". Wraps `scripts/client_report.py`. v1 shows posts + audit + refresh + queue depth; v2 will add GSC keyword deltas + GA4 traffic data.
---

# Rank AI — Client Report Generator (Mode D component)

The monthly client-facing report. Synthesizes what we did, what we found, and what's coming for one Rank AI client into a single self-contained HTML document.

This is **piece 1+2 of 3** toward Mode D (fully automated monthly maintenance + client email):
- Pieces 1 + 2 (this skill): generate + send the report via `client_report.py preview | send`
- Piece 3 (task #41): schedule via `/schedule` so the master cron handles generation + delivery without prompts

The SendGrid integration calls the v3 REST API directly (`api.sendgrid.com/v3/mail/send`) using `SENDGRID_API_KEY` from `rank-ai/.env`. The Claude Code SendGrid MCP's `send_mail` tool currently has a bug ("Unexpected end of JSON input") — we bypass it. All other SendGrid MCP tools (read-side: list_senders, list_templates, get_global_stats, etc.) work fine and remain usable.

## When to invoke

The user says any of:
- "generate monthly report for {client}"
- "show me what we did for {client} this month"
- "client report" / "monthly summary"
- "rank-ai-client-report"

Also invoke unprompted at the START of each calendar month if any client's `audit.last_audit_at` is more than 25 days old (the data is fresh enough that a report makes sense).

## Project root

`/Users/santino/Desktop/mywebsitecode/rank-ai/`

## Pre-flight

1. **Determine the client slug.** Ask via AskUserQuestion if not provided.
2. **Validate** the client has `status: "active"`. If not, fail fast.
3. **Determine the period.** Default to current calendar month. The user can override with `--period YYYY-MM`.

## Run the generator (preview-only)

```bash
python3 scripts/client_report.py preview --slug {slug}
# or with explicit period:
python3 scripts/client_report.py preview --slug {slug} --period 2026-05
```

## Send via email

```bash
# Test send (always goes to contact@restorationai.io with TEST banner, regardless of client flag):
set -a; source ./.env; set +a
python3 scripts/client_report.py send --slug {slug} --test

# Real send (only when client.report_email_enabled is true):
python3 scripts/client_report.py send --slug {slug}
```

Per-client safety flags in `clients/{slug}.json`:
- `report_email_enabled` (default `false`) — must be flipped to true for real sends
- `report_email_to_override` (optional) — override the recipient (default: `client.contact.email`)

Delivery log: `clients/{slug}/reports/_deliveries.jsonl` (append-only, one record per send).

The script reads per-client state from:
- `clients/{slug}.json` — display name, domain, brand colors, contact info
- `clients/{slug}/content-queue.json` — queued items (pipeline depth)
- `clients/{slug}/onsite-audit.json` — latest audit verdict + site rollup
- `clients/{slug}/refresh-queue.json` — refresh actions
- `sites/{slug}/src/content/blog/*.md` — posts published this month (filtered by `published_at` frontmatter)

Output:
- `clients/{slug}/reports/{YYYY-MM}-monthly.html` — self-contained HTML report with inlined styles
- stdout: path + summary stats (posts count, audit verdict, queue depth)

## What's in the report (v1)

1. **Header** — display name, domain, period
2. **Summary stat strip** — posts count, performance score, refresh actions, queue depth
3. **Content Delivered** — list of blog posts published this period (title + URL + excerpt + target keyword)
4. **Site Health** — audit verdict badge, avg Lighthouse scores, template issues, money-page alerts
5. **Refresh Activity** — System 4 actions surfaced (refresh, audit-then-decide)
6. **Coming Up** — scheduled next-month dates + queue depth
7. **Footer** — generation timestamp + reply contact

## Cost expectation

Zero per run. No API calls. Just file reads + HTML rendering. ~1 second wall clock.

## What to print in interactive mode

1. The stdout summary block from the script
2. The `file://` URL the user can open in their browser to preview
3. A short "what's next" block:
   - **If looks good** → offer to send via SendGrid (rank-ai-client-report-send, task #40)
   - **If posts_this_month is 0 and queue_depth is 0** → flag as concerning; suggest a System 1 run before sending

## Auto-chain rules

- Do NOT auto-send. The user (or Mode D scheduler) explicitly approves delivery.
- The Mode D master scheduler chains report-generation → SendGrid-send automatically only for clients where `client.report_email_enabled: true` (defaults false — opt-in per client).

## State files this skill writes

| Path | Lifecycle |
| --- | --- |
| `clients/{slug}/reports/{YYYY-MM}-monthly.html` | One per client per month, never overwritten |

## Hard rules

- v1 is HONEST about the limitations: shows what we DID (posts, audit, refresh) without overclaiming about rankings/traffic until GSC + GA4 are wired (v2).
- Use the client's own brand colors from `client.brand.colors` (or `brand.primary_color`/`brand.primary_dark`/`brand.accent_color`). Never hardcode narestco's deep red or probritegen's blue.
- Inlined CSS only — no external stylesheets. The report must work in email clients.
- R2-hosted images for hero/logo (no local file paths).
- Never use em dashes in the rendered report body.

## What this skill does NOT do (out of scope)

- Send the email — that's the SendGrid integration (task #40)
- Generate PDF — HTML only in v1; PDF via weasyprint can be added later
- Aggregate across multiple clients into a portfolio report — separate skill if/when needed
- Show GSC keyword data or GA4 traffic — v2 enhancements pending those integrations
