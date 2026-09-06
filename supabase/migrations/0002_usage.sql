-- Per-user generation quota.
--
-- Every generation spends the deployment's shared NVIDIA free-tier quota
-- (~40 requests/minute for everyone combined, 2-3 model calls per generation),
-- so one active user can starve the rest. Rows here are counted per user per
-- day and written server-side with the secret key: users may read their own
-- usage but cannot forge or delete it, which is why only `select` is granted.

create table if not exists public.usage_events (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references auth.users(id) on delete cascade,
  kind       text not null check (kind in ('text', 'code', 'audio', 'images', 'quiz', 'sections', 'followup')),
  created_at timestamptz not null default now()
);

create index if not exists usage_events_user_created
  on public.usage_events (user_id, created_at desc);

alter table public.usage_events enable row level security;

drop policy if exists "own usage" on public.usage_events;
create policy "own usage" on public.usage_events
  for select
  using (auth.uid() = user_id);

grant select on public.usage_events to authenticated;
