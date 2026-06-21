# Developer Handoff — Google Ads Data Model (Marketing → Ads page)

> **Read `handoff-00-ads-system-context.md` first** — it explains the whole ads system and the *why* behind every table below.
>
> Part 2 of the ads schema. Pairs with `handoff-ads-call-tracking.md` (which covers `marketing_ads_call_tracking` + `marketing_ads_calls` + the `company_phone_numbers.number_type` column). This file specifies the rest of the `marketing_ads_*` tables that power the **Ads page** in the Marketing tab.

## Context

A Python automation pipeline builds + manages Google Ads campaigns for each company (campaign structure, RSAs, landing pages, conversion actions) and **syncs that state into Supabase via the service-role key** (an `ads_sync.py`, mirroring the existing `supabase_sync.py`). The React app **reads** these tables to render the Ads page. The app does not write them.

**Conventions (match existing `marketing_*` tables):**
- `company_id text` FK → `companies(id)`; also store `rank_ai_slug text` (pipeline key, e.g. `"narestco"`).
- Every row carries the Google Ads **resource name** as the natural unique key — the sync upserts on it (`on_conflict`).
- `synced_at` = last time the pipeline reconciled the row against Google Ads.
- RLS scoped to the user's `company_id`, same policy pattern as existing `marketing_*` tables.

---

## 1. `marketing_ads_campaigns`
One row per Google Ads campaign. Source: `ads-campaigns` scaffold + Google Ads reporting.

```sql
create table public.marketing_ads_campaigns (
  id uuid primary key default extensions.uuid_generate_v4(),
  company_id text not null references companies(id) on delete cascade,
  rank_ai_slug text not null,
  customer_id text not null,                       -- Google Ads customer id (digits, e.g. 3832550597)
  campaign_resource_name text not null unique,     -- customers/{cid}/campaigns/{id}
  name text not null,
  service_group text,                              -- service group this campaign covers
  status text not null default 'paused' check (status in ('paused','enabled','removed')),
  channel_type text default 'SEARCH',
  bidding_strategy text,                           -- MAXIMIZE_CONVERSIONS | TARGET_CPA | ...
  daily_budget numeric(10,2),                      -- account currency
  target_cpa numeric(10,2),                        -- nullable
  geo_targets jsonb default '[]'::jsonb,           -- [{location, radius_miles}]
  synced_at timestamptz default now(),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index on public.marketing_ads_campaigns (company_id);
```

## 2. `marketing_ads_ad_groups`
One row per ad group — both city SKAGs and the 7 intent groups per service. Source: `ads-campaigns`.

```sql
create table public.marketing_ads_ad_groups (
  id uuid primary key default extensions.uuid_generate_v4(),
  company_id text not null references companies(id) on delete cascade,
  rank_ai_slug text not null,
  campaign_id uuid references marketing_ads_campaigns(id) on delete cascade,
  ad_group_resource_name text not null unique,     -- customers/{cid}/adGroups/{id}
  name text not null,
  ad_group_type text not null check (ad_group_type in ('city_skag','intent')),
  service text,                                    -- service slug
  service_label text,
  city text,                                       -- null for intent groups
  state text,
  intent text,                                     -- city | near-me | emergency | cost | company | free-estimate | insurance | removal
  keyword text,                                    -- the SKAG keyword
  match_type text default 'PHRASE',
  status text not null default 'paused' check (status in ('paused','enabled','removed')),
  final_url text,                                  -- the LP this ad group points to
  synced_at timestamptz default now(),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index on public.marketing_ads_ad_groups (company_id);
create index on public.marketing_ads_ad_groups (campaign_id);
```

## 3. `marketing_ads_creatives`
RSAs and assets (sitelinks / callouts / structured snippets). Source: `ads-generate-ads`. `creative_type` discriminates; RSA-specific columns are null for assets and vice-versa.

```sql
create table public.marketing_ads_creatives (
  id uuid primary key default extensions.uuid_generate_v4(),
  company_id text not null references companies(id) on delete cascade,
  rank_ai_slug text not null,
  ad_group_id uuid references marketing_ads_ad_groups(id) on delete cascade,  -- null for campaign/account-level assets
  creative_type text not null check (creative_type in ('rsa','sitelink','callout','structured_snippet')),
  resource_name text unique,                       -- Google Ads ad/asset resource name
  angle text,                                      -- rsa: speed | trust | value
  headlines jsonb,                                 -- rsa: [{ "text": "...", "pinned_position": 1|2|3|null }]
  descriptions jsonb,                              -- rsa: [{ "text": "..." }]
  path1 text, path2 text,                          -- rsa display URL paths
  content jsonb,                                   -- assets: sitelink/callout/snippet payload
  ad_strength text,                                -- rsa: POOR|AVERAGE|GOOD|EXCELLENT
  status text not null default 'paused' check (status in ('paused','enabled','removed')),
  synced_at timestamptz default now(),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index on public.marketing_ads_creatives (company_id);
create index on public.marketing_ads_creatives (ad_group_id);
```

## 4. `marketing_ads_landing_pages`
One row per LP (city + intent pages), including split-test arms. Source: `ads-landing-page` + `ads-split-test`.

```sql
create table public.marketing_ads_landing_pages (
  id uuid primary key default extensions.uuid_generate_v4(),
  company_id text not null references companies(id) on delete cascade,
  rank_ai_slug text not null,
  ad_group_id uuid references marketing_ads_ad_groups(id) on delete set null,
  slug text not null,                              -- water-damage-restoration-federal-way-wa
  url text not null,                               -- full https url
  variant text not null default 'v2',              -- design variant: v1 | v2 | v3
  page_type text check (page_type in ('city','intent')),
  intent text,
  service text, service_label text, city text, state text,
  h1 text,                                         -- keyword H1 (Quality Score)
  split_test_id uuid,                              -- groups A/B arms together (null if not under test)
  split_test_arm text,                             -- 'champion' | 'challenger' (or 'A' | 'B')
  is_control boolean default true,
  status text not null default 'active' check (status in ('active','paused','archived')),
  synced_at timestamptz default now(),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index on public.marketing_ads_landing_pages (company_id);
create unique index on public.marketing_ads_landing_pages (rank_ai_slug, slug);
```

## 5. `marketing_ads_conversions`
The conversion **action** registry (not per-event counts — those live in metrics below). Source: `ads-tracking` (click-to-call now) + future connected-call. Click-to-call is what the LPs fire via gtag.

```sql
create table public.marketing_ads_conversions (
  id uuid primary key default extensions.uuid_generate_v4(),
  company_id text not null references companies(id) on delete cascade,
  rank_ai_slug text not null,
  customer_id text not null,
  conversion_action_resource_name text not null unique,
  name text not null,                              -- e.g. "Lead · Phone Call"
  conversion_kind text not null check (conversion_kind in ('click_to_call','connected_call','form_submit','other')),
  category text,                                   -- e.g. PHONE_CALL_LEAD
  conversion_label text,                           -- AW-XXXXXXXXXX/AbC... (gtag send_to)
  default_value numeric(10,2),
  counting_type text default 'ONE_PER_CLICK',
  status text not null default 'enabled' check (status in ('enabled','paused','removed','hidden')),
  is_primary boolean default true,
  synced_at timestamptz default now(),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index on public.marketing_ads_conversions (company_id);
```

---

## 6. `marketing_ads_metrics` — RECOMMENDED ADDITION (not in the original 6)

Without this, the Ads page can show **structure** but no **performance** (spend, clicks, conversions, CPA over time). Daily rollup pulled from the Google Ads reporting API at `account`, `campaign`, and `ad_group` scope. This is what drives the charts/KPIs on the Ads page.

```sql
create table public.marketing_ads_metrics (
  id uuid primary key default extensions.uuid_generate_v4(),
  company_id text not null references companies(id) on delete cascade,
  rank_ai_slug text not null,
  scope text not null check (scope in ('account','campaign','ad_group')),
  campaign_id uuid references marketing_ads_campaigns(id) on delete cascade,
  ad_group_id uuid references marketing_ads_ad_groups(id) on delete cascade,
  date date not null,
  impressions integer default 0,
  clicks integer default 0,
  cost numeric(12,2) default 0,                    -- account currency
  conversions numeric(10,2) default 0,
  conversion_value numeric(12,2) default 0,
  phone_calls integer default 0,                   -- click-to-call conversions
  synced_at timestamptz default now()
);
create index on public.marketing_ads_metrics (company_id, date);
-- one row per scope target per day:
create unique index marketing_ads_metrics_unique
  on public.marketing_ads_metrics (company_id, scope, coalesce(campaign_id::text,''), coalesce(ad_group_id::text,''), date);
```

---

## Optional / roadmap (mention only — not required for the first Ads page)
- `marketing_ads_split_tests` — a dedicated experiment record (champion vs challenger, traffic split %, start/end, winner). For now, split-test arms are captured inline on `marketing_ads_landing_pages` (`split_test_id`, `split_test_arm`).
- `marketing_ads_negatives` — negative keyword lists per campaign (from `ads-negative-kw`). Useful for an audit view later.

---

## App UI — the Ads page (Marketing tab)

Render from these tables (all filtered by the user's `company_id`):
- **Overview / KPIs:** account-scope `marketing_ads_metrics` (spend, clicks, conversions, CPA, calls) over a date range.
- **Campaigns:** `marketing_ads_campaigns` + campaign-scope metrics (status, budget, spend, conversions).
- **Ad groups & keywords:** `marketing_ads_ad_groups` under each campaign.
- **Creatives:** `marketing_ads_creatives` — RSA preview (headlines/descriptions), ad strength.
- **Landing pages:** `marketing_ads_landing_pages` — grouped by `split_test_id` to show A/B arms side by side, with per-arm metrics once available.
- **Conversions:** `marketing_ads_conversions` — which actions are tracked (click-to-call, etc.).
- **Calls:** `marketing_ads_calls` (from the call-tracking handoff) — log + recording playback (likely under Reports).

## Data flow & security
- Pipeline writes all `marketing_ads_*` via service-role; app reads only.
- RLS scoped to `company_id`, matching existing `marketing_*` policies.
- No secrets in these tables; Twilio/Google credentials stay server-side (see call-tracking handoff).
