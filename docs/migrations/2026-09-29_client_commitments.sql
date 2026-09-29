-- client_commitments: every promise OUR team makes to a client (on a call,
-- by text, by email), with a due date, an owner and a close-out record.
-- Phase 1 of the follow-through system (docs/FOLLOW-THROUGH-SYSTEM.md).
-- Applied to Supabase project nyscciinkhlutvqkgyvq via the Management API
-- on 2026-09-29. The rank-ai repo keeps no supabase/ migrations dir, so the
-- SQL of record lives here.
create table if not exists public.client_commitments (
  id          uuid primary key default gen_random_uuid(),
  company_id  text not null,
  source      text not null check (source in ('call', 'sms', 'email')),
  source_ref  text,
  said_at     timestamptz,
  quote       text,
  what        text,
  owner       text check (owner in ('monica', 'santino', 'dev')),
  due_at      timestamptz,
  status      text not null default 'open'
              check (status in ('open', 'done', 'cancelled')),
  evidence    text,
  closed_at   timestamptz,
  created_at  timestamptz not null default now(),
  unique (company_id, source_ref, what)
);

create index if not exists client_commitments_open_due_idx
  on public.client_commitments (status, due_at);
create index if not exists client_commitments_company_idx
  on public.client_commitments (company_id, status);

alter table public.client_commitments enable row level security;

-- Same pattern as marketing_work_log / marketing_ops_notes: superadmins read
-- from the app; every write is service-role (bypasses RLS).
drop policy if exists "superadmin view commitments" on public.client_commitments;
create policy "superadmin view commitments" on public.client_commitments
  for select to authenticated
  using (exists (select 1 from profiles
                 where profiles.id = auth.uid()
                   and profiles.role = 'superadmin'));
