-- Per-account generation quota. Applied to the live project on 2026-09-06.
--
-- Only `select` is granted: rows are written server-side by Flask with the
-- secret key, so a learner can read their own usage but cannot forge or delete
-- it. Deleting the auth.users row cascades these away too (verified).

create table public.usage_events (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references auth.users(id) on delete cascade,
  kind       text not null check (kind in ('text','code','audio','images','quiz','sections','followup')),
  created_at timestamptz not null default now()
);
create index usage_events_user_created on public.usage_events (user_id, created_at desc);
alter table public.usage_events enable row level security;
create policy "own usage" on public.usage_events
  for select using (auth.uid() = user_id);
