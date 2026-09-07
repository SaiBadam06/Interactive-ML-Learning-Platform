-- Saved lessons and quiz results, one row per learner action.
-- Applied to the live project on 2026-09-06 and verified over REST:
-- own-row insert 201, cross-user insert rejected by RLS, anonymous read empty.
-- Deleting an auth.users row cascades to both tables.

create table public.lessons (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  topic       text not null check (char_length(topic) between 1 and 300),
  level       text not null check (level in ('Beginner','Intermediate','Advanced')),
  mode        text not null check (mode in ('text','code','audio','images')),
  payload     jsonb not null,           -- explanation, code, sections, key terms, quiz
  created_at  timestamptz not null default now()
);
create index lessons_user_created on public.lessons (user_id, created_at desc);

create table public.quiz_results (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  lesson_id   uuid references public.lessons(id) on delete cascade,
  topic       text not null,
  score       int  not null check (score >= 0),
  total       int  not null check (total > 0),
  answers     jsonb not null,
  created_at  timestamptz not null default now()
);
create index quiz_results_user_created on public.quiz_results (user_id, created_at desc);

alter table public.lessons      enable row level security;
alter table public.quiz_results enable row level security;

create policy "own lessons"      on public.lessons      for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own quiz results" on public.quiz_results for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
