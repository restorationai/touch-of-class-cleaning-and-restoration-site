# Follow-Through System (Phase 1): never lose a call or a promise

Shipped 2026-09-29. Owner: Santino. Code: `scripts/call_match.py`,
`scripts/fathom_sync.py`, `scripts/promise_tracker.py`, the promise hold in
`scripts/client_concierge.py`, the PROMISES block in
`scripts/client_ops_sync.py`. Table: `public.client_commitments`
(SQL of record: `docs/migrations/2026-09-29_client_commitments.sql`).

## The incidents it fixes

- **Katofsky, 09-20.** The onboarding call (recording 184795857) was mined
  minutes after the company row existed but before bootstrap minted a slug.
  The matcher only knew clients in `clients/company_map.json`, so the call was
  marked "unmatched" forever. On it Santino promised GBP name options "in a
  day or so". Nothing tracked that. Seven days later it was still undelivered
  while Monica kept nudging Michael for a customer list that was not due.
- **RestoPros, 09-24.** The bootstrap job timed out on RestoPros every 2 hours
  for five days (an uncaught `TimeoutExpired` failed the whole job, so even the
  company_map line never got committed). Both calls that day (186419597,
  186576701) were read as a sales prospect and lost.

## 1. Call matching: no call is dropped

The roster is the **database**, not company_map. Every live `companies` row is
matchable from the moment it exists:

- key = slug from `company_map.json`, else `marketing_sites.rank_ai_slug`, else
  the **company id** (a client bootstrap has not slugged yet is still a client;
  its intel goes to `ops_kv meeting-intel/{company id}`, which Monica reads).
- Hard evidence decides before the model: external invitee emails, the GHL
  appointment the recording sat on (contact id / email / phone), names in the
  title ("Daniel Restum - Kick Off Call"), and transcript speaker names, all
  checked against company + contact emails, phones and full names.
- Guards: our own people (Santino, Levi, Monica, Melia) never count as
  evidence; person-named signup stubs that share the owner's email with the
  real company row are dropped; a call recorded more than 30 minutes before
  the client's row existed is a sales conversation, not client work;
  sales-pipeline titles ("20 Jobs In 90 Days ...") stay on the prospect lane.
- **Unmatched is not final.** An unmatched call is retried on every 30-minute
  sync for 7 days (hard evidence every pass; the model again only when the
  roster changed). After 7 days it becomes a `[TODO-SANTINO] CALL COULD NOT BE
  MATCHED: {title} {date} {attendees}` card, unless the prospect/internal
  lane already handled it.
- `sync --since DATE --reprocess` now includes unmatched calls.
- `fathom_sync.py replay --rid ID [--send] [--intel-only]` re-runs specific
  recordings. `--intel-only` writes meeting intel + promises only (no cards,
  no GHL note, no recap, no booking, no client message).
- Signup linkage: `client_ops_sync.ensure_bootstrapped` no longer dies on a
  bootstrap timeout (the partial files, company_map entry first, get
  committed), and skips signup stubs.

## 2. Promise tracker

`public.client_commitments`: one row per promise OUR side made to a client:
`company_id, source (call|sms|email), source_ref (fathom:{rid} | ghl:{msg id}),
said_at, quote, what, owner (monica|santino|dev), due_at, status
(open|done|cancelled), evidence, closed_at`. Superadmins can read it in the
app; only the service role writes.

- **Calls:** every call fathom_sync mines runs a `claude-sonnet-5` pass over
  the FULL transcript (not Fathom's summary). Once per recording.
- **Texts:** daily at 13:20 UTC (`promise-texts` on the Railway ops worker),
  the same pass over HUMAN outbound SMS/email (GHL rows with a userId and no
  marketplace appId, so Santino typed them).
- **Owner:** `monica` = pure communication from info we hold (a link, an
  answer, options already researched); `santino` = decisions, research,
  calls; `dev` = build/ops work.
- **Due date** (client's timezone, 5pm local): "a day or so" / "tomorrow" =
  +1 business day; "couple of days" = +2 business days; "this week" = Friday;
  "next week" = next Friday; a stated date wins; nothing stated = +2
  business days.
- **Closing:** hourly (`promises` job), a `claude-haiku-4-5` yes/no check of
  each open promise against every later outbound message (Monica or human)
  and `marketing_work_log` entry. Only re-asked when something new landed.
  Biased to "not delivered" when unsure.

## 3. Reading the digest PROMISES section

The Client Ops Digest (07:00 PT) now opens with a red-bordered **PROMISES**
box, and a digest goes out on any day it has content even if nothing else
moved:

- **OVERDUE** (red): past due, still open. The client is waiting on us.
- **Due today** (amber) / **Due tomorrow** (blue; on Friday this means Monday).
- Each line: client, `[owner]`, what, due time (client-local), the verbatim
  quote.
- The footer lists clients on **Monica hold** (below).

Fix a wrong row from the terminal:

```
python3 scripts/promise_tracker.py list            # open, overdue first
python3 scripts/promise_tracker.py set <id-prefix> done --evidence "sent 09-30"
python3 scripts/promise_tracker.py set <id-prefix> cancelled --evidence "client withdrew"
```

## 4. Reminders

- **Ops ping to Santino** (the existing concierge ops-ping path, so the 8am to
  8pm PT window applies; night pings are held for morning): once when a
  santino/dev promise is due within 24h, once when it goes overdue. Monica
  promises are included while autosend is off, because a human has to send
  them. A promise that was already more than 72h overdue when the tracker
  first saw it (backfill, a call mined late) is digest-only, no ping.
- **Monica hold:** while a client has an OVERDUE open promise owned by
  `monica` or `santino` (something the client is waiting to hear from us),
  the hourly nudge pass (`compose --all`) drops every client-owed ask and
  skips the send with `promise-hold`. Replies to the client's messages,
  delivering our own promise, and Santino's directives still go. Fail-open:
  a lookup error never blocks. Covered by `client_concierge.py selfcheck`.
  Dev-owned build promises do not hold by default (they live on the dev
  queue and often need the very items Monica asks for; the 09-29 backfill
  had 100+ of them). Widen with `PROMISES_HOLD_OWNERS=monica,santino,dev`.
- **Hold rollout gate:** only promises made on/after `PROMISES_HOLD_SINCE`
  (default `2026-09-29T00:00:00+00:00`) hold Monica. The backfill left 57
  overdue monica/santino promises across 22 clients, unreviewed; holding on
  them would have stopped Monica's nudges fleet-wide on day one. They show
  in the digest; once they are triaged (`set ... done|cancelled`), move the
  date back (Railway ops-worker env) to let older promises hold too.

## 5. Monica autosend (OFF)

With `PROMISES_MONICA_AUTOSEND` unset (current), monica-owned promises are
notify-only (digest + ping). To let Monica deliver them herself at due time:

1. Railway, ops-worker service, Variables: `PROMISES_MONICA_AUTOSEND=1`.
2. Redeploy. From then on each monica-owned promise that comes due files one
   `[FOR MONICA] PROMISE DUE` note. Monica treats it like any `[FOR MONICA]`
   directive (it bypasses the nudge cooldown; business hours, quiet hours and
   the send-time guards still apply) and the close check marks the promise
   done once her message lands.

Unset the variable to turn it off again.

## Commands

```
python3 scripts/promise_tracker.py run [--send]          # close + remind (hourly)
python3 scripts/promise_tracker.py close [--send]        # close only
python3 scripts/promise_tracker.py scan-texts [--send]   # human texts (daily)
python3 scripts/promise_tracker.py backfill --days 21 --out rows.json
python3 scripts/promise_tracker.py backfill --send --apply-file rows.json
python3 scripts/fathom_sync.py replay --rid 184795857 [--send --intel-only]
```

## Not in Phase 1

- Promises inside Monica's own messages still use her one-slot memory
  (`pending_commitment`), not the table.
- Later calls do not close earlier call promises (only messages and the work
  log do). Close by hand when a promise was kept live on a call.
- Receptionist-plan accounts (Leakproof, Rapid Response) are recognised by
  the matcher but not mined.
