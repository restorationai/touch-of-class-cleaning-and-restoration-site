# Rank AI — Command Center (KPI Dashboard)

A zero-backend KPI dashboard. A Python aggregator pulls all five data sources,
computes the real scoreboard, and writes **one permanent JSON snapshot per month**
to `data/`. A single static `index.html` renders them. No app, no database.

## What it answers
The KPIs that actually predict revenue — not vanity metrics:
- **Demo → Close %** (the truth metric), **Cost / Demo**, **Cost / Client**, **CAC**
- Spend → Lead → Demo → Close funnel
- MRR / active subs (Stripe)
- Meta campaign spend with CTR shown as *creative-health*, not success

## Data sources
| Source | Used for | Auth |
|---|---|---|
| Meta Ads | spend, leads, campaigns | `config.env` token |
| GoHighLevel | demos booked, closes (Sales Pipeline) | `config.env` PIT token |
| Stripe | MRR, active subs, revenue | app `.env.local` |
| GA4 | site + funnel sessions | `.ga4-sa.json` service acct |
| Supabase | new company signups | service-role key |

## Run it
```bash
python3 aggregate.py            # current month
python3 aggregate.py 2026-05    # backfill a specific month
```
Writes `data/<month>.json` + `data/index.json`.

## Secrets
All live in `config.env` (gitignored, **never deployed**). The aggregator runs
server-side and publishes only computed aggregates — no PII, no keys — so the
deployed site is safe to host.

## Deploy (Cloudflare Pages)
```bash
npx wrangler pages deploy . --project-name rank-ai-command-center
```
Then **protect it**: Cloudflare Zero Trust → Access → add an application over the
Pages URL → allow only `@restorationai.io` emails. (KPI/revenue data should not be public.)

## Auto-refresh (GitHub Action)
Add `.github/workflows/kpi.yml` running weekly: install `google-auth`, write
`config.env` from repo secrets, `python3 aggregate.py`, commit `data/`, Cloudflare
auto-deploys. (Ask Claude to scaffold this when ready.)

## Editing / extending
- Change which KPIs/cards show → edit `index.html` (`cards` array, `insights`).
- Add a metric → compute it in `aggregate.py` `snap["scoreboard"]`, render in `index.html`.
- History accrues automatically: each run adds/refreshes one month file.

## Caveat
`demos_booked` = opportunities whose current GHL stage is "Demo Meeting Booked"
or beyond, created in that month (current-stage proxy; GHL API doesn't expose
historical stage-transition dates without webhooks).
