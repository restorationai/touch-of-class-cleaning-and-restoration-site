# Developer Handoff — The Ads Skills & How We Productize Them (Build Path)

> **Read `handoff-00-ads-system-context.md` first.** That explains *what* the ads system is and *why* each table exists.
> This doc explains the other half: the **automation that builds & launches a contractor's ads** ("the skills"), and **how it becomes a thing the app can trigger** when a client signs up.
>
> Pairs with `handoff-ads-schema.md` + `handoff-ads-call-tracking.md` (the tables). This one adds **one new table + a small UI contract** — everything else is ours.

---

## 0. TL;DR for you (the app developer)

The ads system has two halves:

| | **Read / Report path** | **Build / Launch path** |
|---|---|---|
| What | Google Ads → Supabase → Ads page | Build campaigns + landing pages + tracking, then launch |
| Status | **Live** (`ads_sync.py`, nightly Railway cron) ✅ | Operator-run today; we're productizing it |
| Your job | Render `marketing_ads_*` (already speccd) | **One job-queue table + 3 small UI affordances** (this doc) |

**You do NOT build the pipeline.** It runs on Railway (Python + Claude), writes `marketing_*` via the service-role key — same boundary as everything else. You build: a **job-queue table**, a **"Launch Ads" button** that enqueues a job, a **progress indicator**, and a **"Go Live" toggle**. That's it. Sections 4–5 are your spec; sections 1–3 are context so it makes sense.

---

## 1. What "the skills" are

On our side, the build path is a set of 8 **Claude skills** — structured automations that each own one stage of standing up a contractor's Google Ads account. They mix deterministic Google Ads API calls with Claude-written copy and AI-generated imagery. Here's each, what it produces, and which table it feeds:

| # | Skill | What it does | Output → table |
|---|---|---|---|
| 1 | `ads-campaigns` | Builds the **SKAG** campaign/ad-group structure (one keyword per ad group: service × city + 7 intent groups), budgets, geo targeting. | `marketing_ads_campaigns`, `marketing_ads_ad_groups` |
| 2 | `ads-generate-ads` | Writes **3 RSAs per ad group** (speed / trust / value angles), 15 headlines + 4 descriptions each, keyword headlines pinned to position 1. | `marketing_ads_creatives` |
| 3 | `ads-negative-kw` | Applies the universal negative-keyword list (filters jobs/DIY/"free"/wrong trades). | (roadmap table) |
| 4 | `ads-landing-page` | Builds a **dedicated landing page per ad group** from a `split-test-*` template, generates per-client hero imagery (Nano Banana), deploys as static Astro on Cloudflare Pages. H1 exactly matches the ad keyword. | `marketing_ads_landing_pages` |
| 5 | `ads-tracking` | Creates the **click-to-call** conversion action; wires `gadsId` + conversion label into the site's `brand.ts`. | `marketing_ads_conversions` |
| 6 | `ads-call-tracking` | Provisions a dedicated **Google Ads phone number** in the contractor's existing **Twilio subaccount**, routes it through a Cloudflare Function (optional recording), bridges to their business line or AI agent. | `marketing_ads_call_tracking`, `marketing_ads_calls` |
| 7 | `ads-negative-search-terms` | **Ongoing** (weekly, after 14+ days of live data) — mines search-term reports for new negatives. Not part of initial launch. | (roadmap) |
| 8 | `ads-setup` | **Orchestrator** — runs skills 1→5 in sequence with one consolidated intake and approval gates. This is the skill the productized job mirrors. | (drives the above) |

The companion SEO pipeline (`rank-ai-build-site`, etc.) already works this exact way — a skill that *wraps a Python script* (`build_site.py`) which scaffolds → renders content with Claude → **sync-deploys to the per-client GitHub repo → Cloudflare auto-builds**. The ads build path will be productized with the **same pattern**. (Landing pages literally reuse it: generated Astro files are committed to the client's `{slug}-site` repo and Cloudflare builds them.)

---

## 2. What's deterministic vs. what needs Claude (and the keyword reality)

This is why the build path can't be a pure cron script like `ads_sync.py`:

| Stage | Deterministic (plain Python + Google Ads / Twilio API) | Needs Claude / Nano Banana |
|---|---|---|
| Campaign structure | Create campaigns, ad groups, budgets, geo | — |
| RSAs | Push ads/assets via API | **Writing** the headlines/descriptions per keyword |
| Negatives | Apply lists | — |
| Landing pages | Template fill → git push → Cloudflare build | **LP copy per keyword + hero image** |
| Click-to-call tracking | Create conversion action, edit `brand.ts`, commit | — |
| Call tracking | Provision Twilio number, wire webhook, write tables | — |

### ✅ Keyword research is now AUTOMATED (updated 2026-06-15)
We were approved for **Google Ads API Basic Access**, which unlocks `KeywordPlanIdeaService` (programmatic keyword research). The pipeline now pulls real, volume- and CPC-validated keywords automatically and seeds the ad groups with them — **no operator keyword input required.** The operator supplies only **services + cities**; the worker runs research and builds the SKAGs from it (`scaffold --auto-keywords`).

> Operator picks services + cities → worker auto-researches keywords (Google Ads) → builds structure + copy + LPs + tracking.

For the **Launch form**, this means `services[]` + `cities[]` are the required inputs; a keyword set is **not** required. Keep `extra_keywords[]` as an **optional override** (operator can layer in must-have terms), but it's no longer needed for a normal launch.

---

## 3. The productized build path — end-to-end client journey

```
1. Client signs up                                   [app — exists]
2. Client connects Google Ads (OAuth)                [app — DONE ✅ → user_integrations row]
3. Operator clicks "Launch Ads" — picks services + cities  [app — YOU build: enqueue a job]
       └─ INSERT marketing_ads_jobs (status='queued', payload={services, cities, budget, ...})
4. Railway worker picks up the job                   [OURS — deterministic Python; auto-researches keywords]
       ├─ Phase 1 campaigns   (from submitted keywords)   → PAUSED
       ├─ Phase 2 RSAs        (Claude copy)               → PAUSED
       ├─ Phase 3 negatives
       ├─ Phase 4 landing pages (Claude + Nano Banana) → git push → Cloudflare builds
       ├─ Phase 5 click-to-call tracking  → brand.ts commit
       └─ Phase 6 Twilio call-tracking number
       ↑ updates marketing_ads_jobs.phase/progress each step  [YOU read → show progress]
6. Operator reviews the PAUSED result on the Ads page   [app — render existing tables]
7. Operator clicks "Go Live" → campaigns flip to ENABLED [YOU: write a row/flag the worker acts on]
8. ads_sync.py (nightly, LIVE ✅) reports spend/calls back into the dashboard
```

**Launch safety (decided):** the pipeline always builds to **PAUSED**. Real ad budget only starts spending when a human clicks **Go Live**. Never auto-enable on signup.

---

## 4. What you build — Part A: the job-queue table

This one table is the entire contract between the app (enqueues + reads) and our pipeline (executes + updates). It mirrors the traffic-cop / `master_scheduler` pattern already in the stack.

```sql
create table public.marketing_ads_jobs (
  id uuid primary key default extensions.uuid_generate_v4(),
  company_id text not null references companies(id) on delete cascade,
  rank_ai_slug text not null,
  job_type text not null default 'full_launch'
    check (job_type in ('full_launch','landing_pages_only','tracking_only','go_live')),
  status text not null default 'queued'
    check (status in ('queued','running','needs_review','live','failed','canceled')),
  phase text,                       -- human label of current phase, e.g. "Phase 4 · Landing pages"
  progress integer default 0,       -- 0–100, for a progress bar
  payload jsonb default '{}'::jsonb,-- operator inputs: { keywords:[...], services:[...], cities:[...], daily_budget, lead_value, forward_to, ... }
  result jsonb default '{}'::jsonb, -- summary the worker writes back (counts, LP urls, tracking number)
  error text,                       -- populated on failure
  requested_by uuid,                -- app user who clicked Launch
  created_at timestamptz default now(),
  started_at timestamptz,
  updated_at timestamptz default now()
);
create index on public.marketing_ads_jobs (company_id);
create index on public.marketing_ads_jobs (status);
```

- **App writes:** one INSERT on "Launch Ads" (status `queued`, `payload` = the operator's keyword set + budget + forward target). One UPDATE on "Go Live" — either insert a `job_type='go_live'` row, or flip a flag the worker watches. (Tell us which you prefer; either works.)
- **Pipeline writes:** `status`, `phase`, `progress`, `result`, `error`, `started_at`, `updated_at` via service-role. The app **reads** these to drive the UI.
- **RLS:** same pattern as other `marketing_*` tables — scope rows to the user's `company_id`. The service-role key bypasses RLS for the worker.

---

## 5. What you build — Part B: three small UI affordances (on the existing Ads page)

1. **"Launch Ads" action** — a form that collects the operator's keyword set + daily budget + lead value + forward destination, then INSERTs a `marketing_ads_jobs` row (`job_type='full_launch'`, `status='queued'`). Disabled until the client has a connected Google Ads account (`user_integrations` row exists).
2. **Job progress indicator** — while a job is `running`, show `phase` + `progress`. On `needs_review`, surface the built (PAUSED) campaigns/LPs from the existing `marketing_ads_*` tables for the operator to skim. On `failed`, show `error`.
3. **"Go Live" toggle** — visible when `status='needs_review'`. Clicking it enqueues the `go_live` action; the worker flips campaigns to ENABLED and sets the job `status='live'`.

Nothing here writes `marketing_ads_*` content tables — those stay pipeline-owned. You only touch `marketing_ads_jobs` and render the rest read-only, exactly as in the schema handoff.

---

## 6. Boundaries recap (unchanged from handoff-00)

- **`marketing_ads_*` = pipeline-owned** (service-role writes; app reads). The new `marketing_ads_jobs` is the **one exception**: the app writes the enqueue/go-live rows, the pipeline writes execution status.
- **Core tables** (`companies`, `company_phone_setup`, `company_phone_numbers`) — pipeline reads Twilio creds, never writes; tracking numbers mirror in via the trigger from the call-tracking handoff.
- **Secrets** never reach the frontend. Google/Twilio creds stay server-side.
- **Per-client OAuth** in `user_integrations` (provider `google_ads`) must exist before a launch job can run — that's the gate on enabling the "Launch Ads" button.

---

## 7. What we (the pipeline team) own — for your awareness, not your action

- The Railway worker that polls `marketing_ads_jobs` and runs skills 1–6 via the Claude Agent SDK.
- All Google Ads API writes (structure, RSAs, negatives, conversion actions, enabling on Go Live).
- Landing-page generation + git push to `{slug}-site` repos (Cloudflare builds them).
- Twilio number provisioning + the Cloudflare voice Function.
- Writing every `marketing_ads_*` content/metric row (the read path `ads_sync.py` already does the metrics half).

You build Section 4 + 5. We build Section 7. The handshake is the `marketing_ads_jobs` table.
