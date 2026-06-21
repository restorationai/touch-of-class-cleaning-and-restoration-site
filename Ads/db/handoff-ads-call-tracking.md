# Developer Handoff — Google Ads Call Tracking (Marketing tab)

> **Read `handoff-00-ads-system-context.md` first** — it explains the whole ads system and the *why* behind these tables.
>
> Hand this to the app developer. It is self-contained. Two design decisions are flagged as **[DECISION]** — accept or adjust.

## Context

Rank AI app (React + Supabase, app.restorationai.io). We're adding **Google Ads call tracking**.

A separate automation pipeline (Python, authenticates to Supabase with the **service-role key**) provisions a dedicated **Google Ads tracking number** per company in that company's existing **Twilio subaccount**, points the number's voice webhook at a Cloudflare Pages Function that bridges the call (with optional recording) to a configurable destination, and writes the number's state to new `marketing_*` tables. The pipeline reads the Twilio subaccount credentials from the **existing** `company_phone_setup` table — it does not store new credentials.

Two things are needed from the app side:
1. Run the DB migrations below.
2. Surface the data in the **Marketing tab** (new "Ads" page) and the **Reports** tab (call log).

The pipeline writes **only** `marketing_*` tables. The core `company_phone_numbers` registry is kept in sync via a DB trigger (below), so the app/DB remains the owner of core tables.

---

## Part 1 — Database migrations (Supabase)

### 1a. Add `number_type` to `company_phone_numbers`

A company can have **both** an AI-agent number and one or more call-tracking numbers at the same time, so the classification is **per-number** (not per-company — do NOT put this on `company_phone_setup`).

```sql
alter table public.company_phone_numbers
  add column number_type text not null default 'ai_agent'
    check (number_type in ('ai_agent', 'call_tracking'));
```

Existing rows backfill to `'ai_agent'` (they're all AI-agent numbers today). Google Ads tracking numbers will be `'call_tracking'`. For `'call_tracking'` rows, the AI-behavior columns (`book_appointments_enabled`, transfer targets, etc.) are not used and may remain null.

### 1b. New table — `marketing_ads_call_tracking` (config, one row per tracking number)

```sql
create table public.marketing_ads_call_tracking (
  id uuid primary key default extensions.uuid_generate_v4(),
  company_id text not null references companies(id) on delete cascade,
  rank_ai_slug text not null,                  -- pipeline key (e.g. "narestco")
  company_phone_number_id uuid references company_phone_numbers(id) on delete set null,
  phone_number text not null,                  -- the Google Ads tracking number (E.164)
  forward_to text not null,                    -- destination: business line (E.164) OR Retell SIP URI
  forward_type text not null default 'pstn' check (forward_type in ('pstn','sip')),
  recording_enabled boolean not null default false,
  source text not null default 'google_ads',   -- attribution source label
  voice_webhook_url text,                       -- Cloudflare Pages Function URL the number points to
  gads_conversion_label text,                   -- the click-to-call conversion label the LPs fire
  status text not null default 'active' check (status in ('active','released')),
  provisioned_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index on public.marketing_ads_call_tracking (company_id);
create unique index on public.marketing_ads_call_tracking (phone_number);
```

### 1c. New table — `marketing_ads_calls` (call log, one row per call; powers the Reports view)

```sql
create table public.marketing_ads_calls (
  id uuid primary key default extensions.uuid_generate_v4(),
  company_id text not null references companies(id) on delete cascade,
  call_tracking_id uuid references marketing_ads_call_tracking(id) on delete cascade,
  twilio_call_sid text unique,
  from_number text,
  to_number text,
  started_at timestamptz,
  duration_seconds integer,
  recording_url text,        -- Twilio recording (auth-protected; see security note)
  recording_sid text,
  is_lead boolean default false,   -- e.g. duration >= a qualifying threshold
  created_at timestamptz default now()
);
create index on public.marketing_ads_calls (company_id);
create index on public.marketing_ads_calls (call_tracking_id);
```

### 1d. **[DECISION]** Keep `company_phone_numbers` in sync (recommended: DB trigger)

So the pipeline writes only `marketing_*` while tracking numbers still appear in the unified phone registry, add a trigger that mirrors a `marketing_ads_call_tracking` row into `company_phone_numbers` (as `number_type='call_tracking'`):

```sql
create or replace function public.sync_ads_tracking_to_phone_numbers()
returns trigger language plpgsql as $$
begin
  insert into public.company_phone_numbers (company_id, phone_number, phone_number_sid, label, number_type)
  values (new.company_id, new.phone_number, null, 'Google Ads tracking', 'call_tracking')
  on conflict (company_id, phone_number) do update
    set number_type = 'call_tracking', updated_at = now();
  -- capture the registry id back onto the marketing row
  update public.marketing_ads_call_tracking m
     set company_phone_number_id = pn.id
    from public.company_phone_numbers pn
   where pn.company_id = new.company_id and pn.phone_number = new.phone_number
     and m.id = new.id;
  return new;
end $$;

create trigger trg_sync_ads_tracking_number
after insert on public.marketing_ads_call_tracking
for each row execute function public.sync_ads_tracking_to_phone_numbers();
```

**Alternative (if you prefer):** let the pipeline insert the `company_phone_numbers` row directly at provision time and skip the trigger. Recommended path is the trigger (keeps the pipeline strictly in `marketing_*`).

---

## Part 2 — App UI

### New "Ads" page in the Marketing tab
Add an **Ads** menu link alongside Site / Content / Connect / Reports. For this first release it shows the company's call-tracking setup:
- The Google Ads tracking number(s) — join `marketing_ads_call_tracking` → `company_phone_numbers`
- Forward destination + type (business line vs AI agent/SIP), recording on/off, status, provisioned date

Leave room for campaigns / landing pages / spend (future `marketing_ads_*` tables — see roadmap), but those aren't populated yet.

### Reports tab — call log
A "Calls" view sourced from `marketing_ads_calls`: date/time, from-number, duration, **recording playback**, and the `is_lead` flag. Filter by company. (Can also live as a sub-section on the Ads page — your call.)

---

## Part 3 — Data flow, security, conventions

- **Writes:** the automation pipeline writes `marketing_ads_call_tracking` and `marketing_ads_calls` via the service-role key. The app does not write these.
- **Reads / RLS:** match the existing `marketing_*` tables — RLS scoping rows to the authenticated user's `company_id`. Apply the same policy pattern to the two new tables.
- **Secrets:** `company_phone_setup.twilio_auth_token` and related secrets stay server-side only. Never expose to the frontend.
- **Recording playback:** Twilio recording URLs require Twilio auth — do **not** embed Twilio credentials client-side. Serve recordings through an authenticated app/edge endpoint that fetches from Twilio with the company's subaccount creds and streams to the client.
- **Keying/conventions:** `company_id text` FK to `companies(id)`, `timestamptz` defaults, naming consistent with existing `marketing_*` tables.

---

## Roadmap (not in this handoff — informs Ads page layout only)
Future pipeline-owned tables to populate the Ads page: `marketing_ads_campaigns`, `marketing_ads_ad_groups`, `marketing_ads_creatives`, `marketing_ads_landing_pages`. Design the Ads page so these can slot in later (Campaigns, Landing Pages, Calls sections).
