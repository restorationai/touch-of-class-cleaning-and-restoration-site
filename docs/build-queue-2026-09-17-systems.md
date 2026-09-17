# Build Queue — Five Systems Hardening (2026-09-17)

From the RestorationXpress/Roy escalation postmortem + Santino's Dry County
session. Goal for every lane: END-TO-END, self-monitoring, so no client call
ever discovers a dead pipeline again.

---

## A. Google Business Profile Optimizer — AUTO

**A1. Bulk "Apply all services" (fixes the 429).**
Each one-click apply is a FULL location update call to Google, and Google
allows only a handful of location edits per minute. Clicking through Dry
County's 131 suggestions one by one exhausts that quota — that is the exact
429 Santino hit (NOT the per-category cap; that earlier fix lives in the
batch path and returns a different message). The batch path already
coalesces any number of services into ONE update call. Build: an "Apply all
services" button in the app that routes through the batch path, and make
the one-click path honor Google's Retry-After header instead of retrying
inside the same quota minute.

**A2. Nightly auto-apply for the safe classes.**
Services and descriptions are additive and reversible; 16 clients have
~700 researched-but-never-applied items sitting open. Build: nightly sweep
auto-applies OPEN service + description suggestions through the capped
batch path (validateOnly preflight, per-category spill, work-log line per
client). Categories and names STAY human-click — those change identity.

**A3. Removal policy: never suggest removing a plausible service.**
LAW (Santino 2026-09-17, Dry County/biohazard case): a removal may only be
suggested when the service is blatantly outside the vertical (e.g. "wedding
catering" on a restoration profile). Anything restoration-adjacent —
biohazard, trauma, odor, contents, board-up — is NEVER suggested for
removal; most restoration companies do or would take that work. Build:
policy rule in the suggester prompt + a one-time purge that dismisses every
existing open REMOVE suggestion whose service is in the restoration
catalog.

**A5. Service-bank expansion (Santino 2026-09-17: "the more services the
better, as long as each maps to a distinct long-tail search").**
Build a canonical high-intent service-name bank from (a) the union of the
fleet's best service lists (Crew runs hundreds), (b) search-volume data for
the emergency/24-7 variant families ("24/7 water cleanup", "emergency flood
restoration"), (c) the panic-term list. Per client: filter to services they
actually perform (plan-input + site evidence; licensed-trade names like
plumbing ONLY with the license fact), dedupe on the normalized-key rule so
true duplicates merge while distinct modifiers ("Water Cleanup" vs "24/7
Emergency Water Cleanup") both survive, then batch-add toward a 120-150
target through the capped path. RX first (69 today).

**A4. Optimizer coverage report + Build Stages visibility.**
Three surfaces (revised per Santino 2026-09-17):
1. A "Listing Optimized" STAGE on the Build Stages GBP board, after
   "Listing Synced" — derived: zero open auto-safe suggestions = optimized.
2. A glowing dot on the client's profile card while un-optimized items sit
   open, so the board shows who needs the sweep at a glance.
3. One line per client in the morning Client Ops Digest (the daily EMAIL to
   contact@restorationai.io — not a text): open items by type, days since
   last apply, red when auto-safe items sit >7 days.

---

## B. AI Search

**B1. Fix the dead local scanner (the 0% root cause).**
The LLM scanner (the one asking "best water damage company in Davie" and
"my house just flooded — who should I call") has TIMED OUT at 20 minutes
every week since early August and writes nothing. Build: shard it — scan
N clients per run with a resume cursor in ops_kv so every run finishes and
the fleet completes across the week; write each client's history row the
moment that client finishes, not at the end.

**B2. Localize the Google AI Overviews tracker.**
Today it asks only national questions ("how much does water damage
restoration cost") because those trigger AI Overviews — but our content
targets local versions. Build: add city-modified variants ("water damage
restoration cost in Fort Lauderdale") so the tracker measures the queries
our pages can actually win.

**B3. Visibility history freshness guard.**
The app showed a % frozen since Aug 3 and nobody knew. Build: if a client's
newest history row is older than 10 days, the AI Search tab shows "scan
overdue" instead of a stale number, and the health watchdog (D1) flags it.

**B4. Close the loop to content.**
Scans record which sources the AI cited. Build: feed the cited-domains list
into the content planner weekly so the queue targets query families where
citations are winnable (directories we can join, question formats we can
out-answer).

---

## C. Blog / Content Engine

**C1. Content SLA watchdog (the "never starved again" fallback).**
Rule: queued > 0 AND no publish in 14 days = red row in Ops Attention + a
line in the morning digest. Would have caught all three real stalls months
ago (Paul Davis Charleston + ProCraft: 11 queued, ZERO ever published;
ProBrite: 122 days).

**C2. Unstick the three stalled clients.**
Diagnose why Paul Davis Charleston and ProCraft have never published (no
blog collection? excluded slug? crashing item at queue head?) and drain
ProBrite. These are live client-facing failures today.

**C3. Shallow queue, fresh strategy.**
Cap the queue at ~6 items (two weeks of runway). The topic planner refills
from CURRENT strategy each cycle, so a strategy change lands in days — not
after 23 pre-written topics drain (RX today). One-time: trim existing deep
queues back to the best 6, return the rest to the topic bank.

**C4. Panic-moment format (the emergency-plumbing angle, compliant).**
Add a fifth rotation format alongside best-of / cost / who-to-call /
case-study: "Burst pipe in {city}: who to call first" — the panic search a
restoration company can honestly answer (plumber stops the water, we dry
the house) WITHOUT the site advertising plumbing services, so unlicensed
clients stay clean. Seed topics from the ads playbook's panic-term list
(emergency-plumber-intent.md).

**C5. Cadence floor.**
Round-robin currently lands ~1 post per client per 9-14 days. Set an
explicit floor (1/week per active client) and scale the daily batch size to
fleet size so growth never silently dilutes cadence.

**C6. Self-promotion check (already designed, verify end-to-end).**
The four formats self-promote the client in measured ways (rank-1 mention
in who-to-call, the case-study voice). Add a lint: every published post
names the client exactly once in a recommendation context — not zero, not
five.

---

## D. YouTube / Videos (+ every pipeline)

**D1. PIPELINE HEALTH WATCHDOG — the umbrella build, highest leverage.**
One sweep (rides client-ops-sync) checks the recent run conclusions of
every scheduled workflow: video, content-daily, weekly-maintenance, AI
scans, call-intel, authority. TWO consecutive non-successes — including
"cancelled" and timeouts, the states that never alert — raises a red pulse
line + an Ops Attention card naming the pipeline and days dead. This one
monitor would have caught the video pipeline (3 weeks dead), the AI
scanner (6 weeks), and the blog stalls. "Live status checker" per Santino.

**D2. Fix the video crash.**
Runs die on a JSON parse error mid-run, hang, then hit the 120-minute
timeout as "cancelled" (7 of the last 8 runs). Fix the parse (malformed
model output — validate/retry the JSON step), and add a per-client
try/except so one bad client skips instead of hanging the fleet run.

**D3. Backfill the missed 3 weeks.**
After D2, run the batch for clients that missed video slots since Aug 31,
throttled over a few days so channels don't get a suspicious burst.

---

## E. Spam Calls

**E1. Spam-number feedback loop (auto-blocklist).**
Call-intel already labels spam from transcripts. Build the loop: every
number classified spam lands in a per-fleet blocklist; the call router
checks it on every inbound and sends matches straight to a dead-end
voicemail instead of ringing the client. Second call from any boiler room
never reaches Roy. (No keypress gates — house law.)

**E2. Twilio Lookup risk-screening on inbound.**
Score unknown callers via Twilio Lookup (line type + spam risk) in the
router; high-risk goes to voicemail, never forwarded. Catches robocallers
on their FIRST call, before call-intel has a transcript.

**E3. Spam-free client reporting.**
Calls classified spam are excluded from client-facing counts and the calls
card shows "N spam calls blocked/filtered" as a positive line. Roy's
"cleaned call report" becomes the permanent default view. Context that
convinced us: 100% of RX spam hit the GBP tracking line, from dozens of
different 561 numbers at machine-length ~44s durations — the number is
scraped from the Google listing by lead-gen farms (Google's own stats
don't show these calls because Google only counts profile-button taps,
which is the proof).

**E4. Answer-rate surfacing.**
Same forensics found 105 of RX's last 200 calls ended in voicemail. Add
answer-rate to the calls card + monthly report — spam is real, but
unanswered real calls are the more expensive leak, and clients should see
it.

---

## Attack order
1. **D1 watchdog** (catches everything else while we fix it)
2. **B1 AI-scan shard fix** + B3 freshness guard
3. **A1 bulk apply** (unblocks Santino's Dry County session today) + A3 removal law
4. **E1+E2 spam loop**
5. **C1 SLA + C2 unstick** the three stalled clients
6. **A2 nightly auto-apply**, C3-C6, B2/B4, D2-D3, E3-E4

---

## P. PARITY ENGINE — GBP <-> Website, services + locations, failproof
(Santino 2026-09-17: "consistent parity between the Google Business Profile
and the site... services AND locations, both directions, closest areas
first." The area where our system must be provably connected end to end.)

**What already exists (fragments, not a loop):**
- A nightly reconciliation already COMPUTES both service gaps per client
  (marketing_gbp_profiles.reconcile_gbp_without_page /
  reconcile_site_without_gbp) — data, no action.
- Client-confirmed services auto-apply to GBP + queue a website page
  (since 08-03), and A2 (09-17) now auto-applies optimizer service ADDs.
- The page queue drain (gbp.py create-pages) turns queued services into
  built site pages.
- NOTHING exists for location parity, the 20-cap, variant fan-out
  recurrence, or aliveness checks on any of this.

**P1. Parity ledger.** One derived view per client: services on site /
on GBP / missing each direction; areas on site / on GBP / missing each
direction; a single parity % per client. Surfaced on the app's GBP panel
and as a digest line. You cannot keep what you cannot see.

**P2. Service parity loop (both directions, nightly).**
GBP service with no site page -> page auto-queued (existing drain builds
it). Site service page with no GBP service -> service auto-added via the
A2 batch (plus its variant family). Closes the reconcile data into action.

**P3. Location parity loop (both directions, nightly, 20-cap aware).**
Google caps service areas at 20 per profile. Rules:
  - GBP -> site: every GBP service area gets a site city page (no cap
    this direction).
  - Site -> GBP: rank the site's cities by distance from the profile's
    real location; the CLOSEST 20 are maintained as the GBP service
    areas; a new closer city displaces the farthest.
  - The SITE may exceed 20 (organic + AI search have no radius cap);
    pages build closest-first in rings, so when a second profile opens
    (multi-location game plan), its ring of cities is already built and
    its own 20 areas are ready.

**P4. A5 becomes a WEEKLY RECURRING generator (never one-shot).**
The variant bank (emergency/24-7 families, surface-damage families:
ceiling 1,900/mo, hardwood 1,600, laminate 1,000, carpet 720...) refreshes
weekly and re-stages fleet-wide, so a client missed once is caught the
next week and new bank entries apply RETROACTIVELY to every client
automatically. Individually small volumes aggregate; truthful services
only; licensed-trade names still gated.

**P5. Aliveness (the "A5 must be active and alive" guarantee).**
The parity sweep and the A5 generator each write a heartbeat to ops_kv on
every run; the D1 pipeline watchdog red-flags any heartbeat older than 8
days. A dead parity engine announces itself — never discovered on a
client call.

**P6. Retro backfill (first run).** Apply the new surface-damage +
long-tail families to EVERY current client through the A2 nightly batch,
staged per client, RX-first pattern.

Build order: P1 -> P3 (locations are the fully-missing half) -> P2 ->
P4+P5 -> P6.
