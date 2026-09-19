# Per-Client Conversion Queue

Standing direction (Santino, 2026-09-19): every system runs on a
per-client basis, never as a bulk sweep with a shared clock. Bulk sweeps
have fixed capacity while the fleet grows, and one slow client can starve
the others. The house pattern, proven on content and video:

> **plan job** (cheap, lists which clients are due, outputs JSON)
> **→ matrix** (one isolated job per client, 5-6 in parallel, its own
> timeout) **→ per-client commit** (only that client's files, with a
> pull-rebase-retry loop so parallel jobs never clobber each other)
> **→ per-client failure alert** (the email names the client).

Converted so far: `content-daily` (validated 2026-09-19: 15 jobs, 0
failures), `video-automation` (2026-09-19). This file is the queue for
what remains, in priority order. Nothing below has been started.

---

## 1. client-ops-sync (the nightly) — the big one

**What it does today, in simple terms:** One giant run every day at 14:00
that does almost everything for every client, one client after another:
updates each client's setup ledger and checklists, harvests their new GBP
photos, applies their GBP service suggestions, runs the parity engine
(service areas + services), syncs citations into their site, checks
backlinks, wires GA4, and then runs the fleet watchdog at the end.

**Why bulk is a problem here:** It is the single biggest bundle we have
(~50 minutes today and growing with every client). If one client's Google
call hangs or errors mid-run, everyone after them in line is late or
skipped. One red X tells us nothing about WHICH client broke.

**Target shape:**
- A small **serial job** keeps the truly fleet-level work (things that are
  about US, not one client): the agency toll-free watch, the pipeline
  watchdog, the cutover harvest sweep, domain hydration.
- A **matrix job per client** does everything client-scoped: ledger +
  checklist, GBP photo harvest, gbp_auto_apply, gbp_parity, citations
  sync, GA4 wiring, backlink check.

**Updates needed:**
1. Add a `list-active` (or reuse slug_map + Active filter) emitter that
   prints the JSON client list for the matrix.
2. Give each client-scoped script a clean single-client entry point (most
   already accept `--slug`; verify each).
3. Split the workflow into `fleet` (serial, ~5 min) and `client` (matrix)
   jobs; move the env blocks accordingly (the missing-secrets bug from
   09-18 is the cautionary tale — every step's env must move WITH it).
4. Per-client commit scope + rebase-retry, same as content/video.
5. Per-client failure email ("ops-sync failed for {slug}").
6. Watchdog stays LAST, in the serial job, after the matrix completes
   (`needs:`), so it judges the run that just happened.

**Watch out for:** scripts that currently share in-process caches across
clients (they'll just re-fetch per job — slower but isolated); Google
API per-minute quotas now hit from 6 runners at once (keep max-parallel
modest, ~4, and rely on the existing retry/backoff).

**Validation:** dispatch on a quiet afternoon; confirm every matrix job
green, ledger/digest output identical in shape to the old run, watchdog
still files its notes; compare one client's ledger before/after.

**Effort:** the big one — a focused session (~half a day).

---

## 2. weekly-maintenance (Mon/Thu) — scanner + audits

**What it does today:** Twice a week: site audits, the sharded AI-search
scanner (stalest 19 clients per run inside a fixed time budget), service
bank staging, and other maintenance, all in one run.

**Why bulk is a problem:** The scanner's shard-and-budget math is exactly
the capacity-ration pattern we're retiring — it works today, but "how
many clients fit in 38 minutes" breaks silently as the fleet grows. The
run also concludes "cancelled" when it hits its ceiling even though the
work landed (it did this on 09-18 while stamping a healthy heartbeat),
which pollutes the watchdog picture.

**Target shape:** plan job lists clients due a scan (stalest-first, same
ordering logic, no budget) + audit-due clients → matrix per client
(scan ~2-4 min each) → serial tail job stamps the fleet heartbeat.

**Updates needed:**
1. `ai_search_scan.py --list-due` emitter (reuse the stalest-first query;
   drop `--shard/--budget-min` from the workflow once matrixed).
2. Same split for the audit steps (each already takes `--slug`?—verify).
3. Heartbeat stamping moves to a `needs: [scan]` tail job (count from the
   matrix results).
4. Interim quick win (can ship independently, 30 min): give the current
   bulk run a clean early exit so it stops concluding "cancelled" when
   healthy — same fix the video cron got.

**Validation:** RX and the other stale clients get fresh `scanned_at`
stamps; heartbeat stamps with the matrix count; run concludes success.

**Effort:** medium (~2-3 hours), plus the 30-minute interim fix.

---

## 3. gbp-maintenance (weekly, Sunday) — posts + photos

**What it does today:** One weekly run loops all clients: generates and
publishes GBP posts (2x/week pattern), pushes photos, cover checks.

**Why bulk is a problem (mildly):** Units are cheap (API calls + short
model calls, seconds-to-a-minute per client), so this breaks LAST — but
a Google quota stall on one client still delays the rest, and a single
red X hides who failed.

**Target shape:** same plan → matrix, one job per client with GBP
connected; max-parallel low (4) because Google per-minute quotas are the
real constraint here.

**Updates needed:**
1. Due-list emitter (clients with connected GBP + post due).
2. Verify `gbp.py`/post scripts run cleanly single-client (`--slug`).
3. Matrix workflow + per-client alert. No repo commits involved (writes
   go to Google + Supabase), so no push-race work needed — simplest
   conversion of the four.

**Validation:** post lands on 2-3 clients' GBPs; failure on a suspended
client (Go Green) alerts by name without touching anyone else.

**Effort:** small (~1-2 hours).

---

## 4. monthly-reports (1st of month) — client report cards

**What it does today:** One run on the 1st builds and publishes every
client's monthly report page, then notifies.

**Why bulk is a problem (barely):** Whole run is minutes and monthly.
Lowest urgency — converting is about consistency and per-client failure
visibility (one client's broken data currently risks the whole batch,
which on the 1st of the month is a bad day to debug a pile).

**Target shape:** plan (all active clients) → matrix per client
(`client_report.py --slug X --period prev --notify`), per-client alert.

**Updates needed:**
1. Matrix workflow (client_report.py already runs single-client — near
   zero script work).
2. Decide notify behavior on partial failure (send the 40 that built;
   alert the 2 that didn't — today it's all-or-nothing).

**Validation:** dry-run period on 2 clients; then first live 1st-of-month.

**Effort:** small (~1 hour).

---

## Explicitly NOT converting (already the right shape)

- **Concierge loops** (inbound SMS, email intake, nudges): event-driven —
  the unit of work is a message, not a fleet sweep.
- **supabase-sync backstop**: seconds per client, nightly, self-healing.
- **dev-agent**: task-queue based; tasks are already per-client.
- **site-render**: dispatched per slug already.
- **Watchdog / SLA / A2P advance / rename workers**: judge and advance
  per client by design.
