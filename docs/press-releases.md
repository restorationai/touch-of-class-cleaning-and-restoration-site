# Quarterly Press Releases (authority moat)

Robinson-teardown adoption: their strongest authority signal is press-release
syndication — dozens of third-party pages repeating their response-time claim
in indexable text. This system does the same for every Rank AI client, but
truth-gated: every claim in a release must be backed by brand data
(`scripts/claims_lint.py` CLAIMS TRUTH TABLE — a draft that fails lint is
never saved).

## What it does

`scripts/press_release.py` drafts one 350-500 word local-news-style release
per client per **quarter**: headline, dateline (`{City}, {ST}`), body with a
generic-spokesperson quote, truth-gated proof points only (24/7 claim iff
`brand.hours` passes the 24/7 gate, synced Google rating/review count from
`brand.ts`, certifications, license, cities served incl. git-provable recent
expansions, founded year), and an "About {company}" boilerplate with NAP +
site URL.

Storage:
- Supabase `marketing_press_releases` (PK `company_id, quarter`;
  status `draft → approved → published`; read-own + update-own RLS) — app
  repo migration `supabase/migrations/20260705200000_create_marketing_press_releases.sql`.
- Repo copy at `clients/{slug}/press/{quarter}.md`.

## Cadence

The **monthly** authority cron (`railway.authority-cron.toml`, 1st of month
09:00 UTC) chains `press_release.py draft --all` after the action-plan steps.
The script gates itself so quarterly cadence emerges from the monthly cron:

- Runs in the first month of a quarter (Jan/Apr/Jul/Oct).
- In months 2-3 it runs only as catch-up if the quarter has **no rows yet**.
- Per client it always skips if a draft/approved/published row already exists
  for the quarter (idempotent). `--quarter`/`--force` bypass the month gate.

Manual: `python3 scripts/press_release.py draft --slug narestco`.

## Operator flow

1. Draft appears automatically each quarter — app → **Marketing → Reports →
   "Press Releases" card** (status badge `draft`).
2. Read it. Fix anything off in Supabase/`clients/{slug}/press/` if needed,
   then hit **Approve**.
3. Copy the markdown (Copy button) and submit through a syndication service:
   [Press Advantage](https://pressadvantage.com) or
   [EIN Presswire](https://www.einpresswire.com).
4. When the syndicated release is live, hit **Mark published** and paste the
   published URL (status → `published`, link shows on the card).

## Cost guidance

- Generation: one short Sonnet call per client per quarter — pennies.
- Syndication: budget **$100-200 per release** (Press Advantage single
  releases / small packs; EIN Presswire Basic runs cheaper per release in
  bundles). One release per client per quarter keeps this ~$33-66/mo/client.
