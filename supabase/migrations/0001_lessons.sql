-- Saved lessons and quiz results, one row per user action.
-- Every row is locked to its owner by Row Level Security, so the browser can
-- read and write with the public anon key and still only ever see its own data.

create table if not exists public.lessons (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  topic       text not null check (char_length(topic) between 1 and 300),
  level       text not null check (level in ('Beginner', 'Intermediate', 'Advanced')),
  mode        text not null check (mode in ('text', 'code', 'audio', 'images')),
  -- explanation, code, sections, key terms, quiz; the inline audio data URI
  -- is stripped before saving (the script text is kept instead)
  payload     jsonb not null,
  created_at  timestamptz not null default now()
);

create index if not exists lessons_user_created
  on public.lessons (user_id, created_at desc);

create table if not exists public.quiz_results (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  lesson_id   uuid references public.lessons(id) on delete cascade,
  topic       text not null check (char_length(topic) between 1 and 300),
  score       int  not null check (score >= 0),
  total       int  not null check (total > 0 and score <= total),
  answers     jsonb not null,
  created_at  timestamptz not null default now()
);

create index if not exists quiz_results_user_created
  on public.quiz_results (user_id, created_at desc);

alter table public.lessons      enable row level security;
alter table public.quiz_results enable row level security;

-- "for all" covers select, insert, update and delete in one policy each.
drop policy if exists "own lessons" on public.lessons;
create policy "own lessons" on public.lessons
  for all
  using      (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "own quiz results" on public.quiz_results;
create policy "own quiz results" on public.quiz_results
  for all
  using      (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- The anon role gets nothing by default; authenticated users reach rows
-- only through the policies above.
grant select, insert, update, delete on public.lessons      to authenticated;
grant select, insert, update, delete on public.quiz_results to authenticated;
