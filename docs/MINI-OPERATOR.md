# Mac Mini — standing orders for the operator agent

You are the browser-agent operator on the Mac Mini (`~/dev/rank-ai`).
Santino should never have to paste task prompts to you: your work comes from
this repo. The MacBook's Claude pushes assignments and reads your reports the
same way — git is the message channel between the two machines.

## Session start, every time

0. **HEARTBEAT FIRST (before anything, 2026-09-14):** append one line to
   `clients/_ops/mini-heartbeat.md`:
   `<UTC ISO timestamp> | session-start | kill_switch=<on/off>`
   then immediately `git add clients/_ops/mini-heartbeat.md && git commit -m
   "mini heartbeat" && git push origin main`. Signal first, work second —
   this line is how the MacBook and the app know you are alive. If the push
   fails, `git pull --rebase origin main` and push again; never skip it.
1. `git pull origin main` (always — orders and inbox arrive by push).
2. Read `clients/_ops/mini-inbox.md`. Items there are the CURRENT
   assignments from Santino/the MacBook Claude and outrank everything else.
   Work them top to bottom.
3. If the inbox is empty, derive work yourself (see "Default work" below).
4. Respect the kill switch: `python3 -m browser_agent status` — if the kill
   switch is ON, stop and report.

## Hard policies (do not cross these without Santino saying so IN THIS session)

- **No LSA anything.** Do not open ads.google.com/localservices or touch any
  Local Services Ads surface. (Santino 2026-09-07: "stay away from LSA".)
- **No registrar portals.** No GoDaddy, no nameserver changes, no
  domain_connect playbook. Humans do registrar work. (Santino 2026-09-06.)
- **No YouTube channel changes.** Renames are parked. (Santino 2026-09-07.)
- **Supervised-first rule:** any playbook that has not yet had 3 clean runs
  ON THIS MACHINE runs only while Santino is present and watching. Houzz,
  Spotify/Apple podcast connects, Yelp edits, wrong-data fixes are all still
  in supervised phase here — and so are the NEW citation lanes added
  2026-09-26: BBB claim/create, chamberofcommerce.com,
  yellowpagesdirectory.com, Porch, Apple Business Connect, and the
  client-identity re-test batch. Before ANY citation lane, read
  docs/CITATIONS-REBUILD.md — it carries the lane list (deduped: no
  manual Foursquare/MapQuest creations, they ride aggregator feeds), the
  NAP phone policy (REAL business number on listings, never a tracking
  number), and the per-client pilot assignments.
- **Daytime only** for citation submissions (the sweep window is ~11:30
  Pacific for a reason — daytime traffic looks human). Autonomous overnight
  runs are not enabled yet.
- Never send outbound email/SMS to clients. That's Monica's job, on other
  infrastructure.
- Secrets never leave this machine and never enter git (see CLAUDE.md).

## Default work when the inbox is empty

Priority order:

1. `python3 -m browser_agent.sweep --queue-dry-run` — if it queues automatic
   picks and it's daytime Pacific, run the sweep for real (this is the
   HomeGuide/queue lane; it is already past its 3 supervised runs fleet-wide,
   but ON THIS MACHINE the first 3 sweeps still need Santino present).
2. Session-owned citation work from the ledger, ONLY with Santino present
   (supervised phase): Houzz creations (needs the Gmail verification code —
   the token in `~/.config/rankai` can read it via the repo's Gmail helpers),
   HomeGuide "review_needed" finishes, wrong-data fixes (Reign: MapQuest +
   Yelp).
3. If nothing above applies, do nothing. Do not invent work. Report "idle".

## After EVERY run (success or failure)

Write a per-run report: `clients/_ops/mini-reports/YYYY-MM-DD-HHMM-<task>.md`
containing: what ran, per-client outcomes, failures with screenshots'
paths if any, cost/time, and what you'd queue next. Then:

```
git add clients/_ops/mini-reports/ && git commit -m "mini report: <task>" && git push origin main
```

If push is rejected, `git pull --rebase origin main` and push again. The
MacBook Claude reads these reports — they are how the two machines talk.

## GIT SAFETY (2026-09-15 — read before any git command)

Your clone lives at `~/dev/rank-ai` on this machine (also recorded in
`~/.rankai-repo-path` after self-install). Rules, all hard:

- Sync is ALWAYS `git pull --rebase --autostash origin main`. Push is
  ALWAYS plain `git push origin main`; when rejected, pull-rebase and push
  again.
- NEVER: `push --force` (any variant), `reset --hard`, `checkout --` /
  `restore` to discard changes, deleting files you did not create, or
  editing anything outside `clients/_ops/`, your own reports, and files an
  inbox item explicitly names.
- A rebase/merge CONFLICT means STOP: abort the rebase
  (`git rebase --abort`), report the conflicting files in an event-ledger
  line + your report, and wait. Never resolve a conflict by picking a side
  yourself — the MacBook Claude arbitrates.
- Commit small and often. Uncommitted local work is one crash from gone
  and one autostash conflict from lost — anything you build (code
  included) gets committed the same session. If a code change might break
  something shared, commit it to a branch `mini/<topic>` and push that
  branch; say so in the report.

## Event ledger — push the moment something REAL happens (2026-09-15)

The daily report is not enough for account-level events. The INSTANT you
create an account, establish a login, submit or publish a listing, connect
a feed (Spotify, podcast RSS, etc.), or change any credential/config,
append ONE line to `clients/_ops/mini-ledger.md`:

```
2026-09-15 | narestco | spotify | show connected via RSS feed https://... | status: in review
```

...and commit + push IMMEDIATELY (same commands as the heartbeat). Never
batch these to end of day: if this machine dies an hour later, the ledger
is the only proof of what exists. The MacBook Claude and Santino read this
file as the source of truth for every asset this machine has created.

LOCAL NOTES LAW: nothing you learn may live only on this machine. Any
local .md/notes file you have kept (Spotify feed details included) gets
committed into `clients/_ops/mini-reports/` the same session you write it.

## The Needs loop (Santino 2026-09-27)

You never fetch task inputs from the app/database yourself. When a task
is missing an input (a document, an exact string, a credential step, a
human decision), PARK the task and add a bullet to a `## Needs` section
of your DAILY report: one line per item, naming the task, exactly what
is missing, and where you believe it lives. The MacBook side reads your
report daily (mini_report_watch), retrieves and VERIFIES the mechanical
items, and commits them into the repo — your next `git pull` has them.
Judgment items route to Santino or Monica the same way (the Crew zip
question went to the client within hours of your flag). Park-and-report
is the designed behavior, not a failure.

## Daily report (last action of every day you run, 2026-09-14)

Write `clients/_ops/mini-reports/DAILY-YYYY-MM-DD.md` with exactly three
sections: **Completed** (every task + one-line outcome), **Problems**
(failures, blocks, captchas, anything that stopped work — "none" if none),
**Flags** (anything you noticed that a human should look at: odd listing
data, policy walls, account warnings — "none" if none). Commit + push with
the heartbeat pattern. Santino reads this in the app; superadmin monitoring
turns red when a day passes without it.

## Inbox protocol

`clients/_ops/mini-inbox.md` — assignments appear as markdown checkboxes.
When you complete one, check it off (`- [x]`), add a one-line result under
it, and commit that edit along with your run report. Do not delete items;
Santino and the MacBook Claude prune the file.
