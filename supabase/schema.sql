-- =====================================================================
-- SLAYBUS database schema
-- Run this once in Supabase: Dashboard -> SQL Editor -> New query ->
-- paste this whole file -> Run. It is safe to re-run.
-- =====================================================================

-- pgvector lets Postgres store embeddings and search them by similarity.
create extension if not exists vector;

-- ---------------------------------------------------------------------
-- profiles: one row per teacher, same id as auth.users
-- ---------------------------------------------------------------------
create table if not exists public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  name        text,
  school      text,
  board       text,
  subjects    text[] not null default '{}',
  classes     text[] not null default '{}',
  created_at  timestamptz not null default now()
);

-- Create an empty profile automatically whenever someone signs up.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name'))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------
-- textbooks: an uploaded PDF and its processing status
-- ---------------------------------------------------------------------
create table if not exists public.textbooks (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users (id) on delete cascade,
  title         text not null,
  subject       text,
  class_level   text,
  board         text,
  file_path     text not null,               -- path inside the "textbooks" storage bucket
  status        text not null default 'uploaded'
                check (status in ('uploaded', 'processing', 'ready', 'failed')),
  error_message text,                         -- filled when status = 'failed'
  page_count    int,
  progress      int not null default 0,       -- 0-100 while processing
  chapter_method text,                        -- bookmarks | headings | ai | whole_book
  created_at    timestamptz not null default now()
);
-- upgrades for databases created from an older version of this file
alter table public.textbooks add column if not exists progress int not null default 0;
alter table public.textbooks add column if not exists chapter_method text;
create index if not exists textbooks_user_id_idx on public.textbooks (user_id);

-- ---------------------------------------------------------------------
-- chapters: detected chapter boundaries inside a textbook
-- ---------------------------------------------------------------------
create table if not exists public.chapters (
  id           uuid primary key default gen_random_uuid(),
  textbook_id  uuid not null references public.textbooks (id) on delete cascade,
  number       int not null,
  title        text not null,
  start_page   int not null,
  end_page     int not null,
  unique (textbook_id, number)
);
create index if not exists chapters_textbook_id_idx on public.chapters (textbook_id);

-- ---------------------------------------------------------------------
-- chunks: small pieces of book text + their embedding (768 numbers)
-- ---------------------------------------------------------------------
create table if not exists public.chunks (
  id           uuid primary key default gen_random_uuid(),
  textbook_id  uuid not null references public.textbooks (id) on delete cascade,
  chapter_id   uuid references public.chapters (id) on delete cascade,
  page         int not null,
  content      text not null,
  token_count  int,
  embedding    vector(768)    -- must match GEMINI_EMBED_DIM in agent/.env
);
create index if not exists chunks_textbook_id_idx on public.chunks (textbook_id);
create index if not exists chunks_chapter_id_idx on public.chunks (chapter_id);
-- HNSW index makes "find the closest chunks" fast (cosine distance).
create index if not exists chunks_embedding_hnsw_idx
  on public.chunks using hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------
-- papers: a generated question paper / worksheet / quiz
-- ---------------------------------------------------------------------
create table if not exists public.papers (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users (id) on delete cascade,
  textbook_id   uuid references public.textbooks (id) on delete set null,
  title         text not null,
  paper_type    text not null default 'question_paper'
                check (paper_type in ('question_paper', 'worksheet', 'quiz')),
  config        jsonb not null default '{}'::jsonb,   -- the blueprint the teacher filled in
  total_marks   int,
  duration_min  int,
  status        text not null default 'generating'
                check (status in ('generating', 'ready', 'failed')),
  error_message text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists papers_user_id_idx on public.papers (user_id);

-- ---------------------------------------------------------------------
-- questions: every generated question (also acts as the question bank)
-- ---------------------------------------------------------------------
create table if not exists public.questions (
  id                uuid primary key default gen_random_uuid(),
  paper_id          uuid references public.papers (id) on delete set null,  -- kept in bank if paper deleted
  user_id           uuid not null references auth.users (id) on delete cascade,
  chapter_id        uuid references public.chapters (id) on delete set null,
  section           text,
  order_index       int not null default 0,
  type              text not null
                    check (type in ('mcq', 'fill_blank', 'true_false', 'short_answer', 'long_answer', 'case_based')),
  difficulty        text not null check (difficulty in ('easy', 'medium', 'hard')),
  marks             numeric(5, 1) not null default 1,
  question_text     text not null,
  options           jsonb,                 -- MCQ: ["a", "b", "c", "d"]
  answer            text,
  explanation       text,
  marking_points    jsonb,                 -- long answers: ["point 1 (1 mark)", ...]
  source_chunk_ids  uuid[] not null default '{}',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
create index if not exists questions_paper_id_idx on public.questions (paper_id, section, order_index);
create index if not exists questions_user_id_idx on public.questions (user_id);
create index if not exists questions_chapter_id_idx on public.questions (chapter_id);

-- Keep updated_at fresh on edits.
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists papers_touch on public.papers;
create trigger papers_touch before update on public.papers
  for each row execute function public.touch_updated_at();

drop trigger if exists questions_touch on public.questions;
create trigger questions_touch before update on public.questions
  for each row execute function public.touch_updated_at();

-- =====================================================================
-- Row Level Security: a teacher can only see and change their own rows.
-- (The agent uses the service-role key, which bypasses RLS, so the agent
--  code itself also filters by user_id on every query.)
-- =====================================================================
alter table public.profiles  enable row level security;
alter table public.textbooks enable row level security;
alter table public.chapters  enable row level security;
alter table public.chunks    enable row level security;
alter table public.papers    enable row level security;
alter table public.questions enable row level security;

-- profiles
drop policy if exists "own profile" on public.profiles;
create policy "own profile" on public.profiles
  for all to authenticated
  using (id = auth.uid()) with check (id = auth.uid());

-- textbooks
drop policy if exists "own textbooks" on public.textbooks;
create policy "own textbooks" on public.textbooks
  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- chapters (owned through their textbook)
drop policy if exists "own chapters" on public.chapters;
create policy "own chapters" on public.chapters
  for all to authenticated
  using (exists (select 1 from public.textbooks t where t.id = textbook_id and t.user_id = auth.uid()))
  with check (exists (select 1 from public.textbooks t where t.id = textbook_id and t.user_id = auth.uid()));

-- chunks (owned through their textbook)
drop policy if exists "own chunks" on public.chunks;
create policy "own chunks" on public.chunks
  for all to authenticated
  using (exists (select 1 from public.textbooks t where t.id = textbook_id and t.user_id = auth.uid()))
  with check (exists (select 1 from public.textbooks t where t.id = textbook_id and t.user_id = auth.uid()));

-- papers
drop policy if exists "own papers" on public.papers;
create policy "own papers" on public.papers
  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- questions
drop policy if exists "own questions" on public.questions;
create policy "own questions" on public.questions
  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- =====================================================================
-- Vector search: find the chunks most similar to a query embedding,
-- limited to one textbook and (optionally) some chapters.
-- security invoker = RLS still applies when a logged-in user calls it.
-- =====================================================================
create or replace function public.match_chunks(
  query_embedding vector(768),
  p_textbook_id   uuid,
  p_chapter_ids   uuid[] default null,
  match_count     int default 8
)
returns table (
  id          uuid,
  chapter_id  uuid,
  page        int,
  content     text,
  similarity  float
)
language sql stable
security invoker
set search_path = public, extensions
as $$
  select c.id, c.chapter_id, c.page, c.content,
         1 - (c.embedding <=> query_embedding) as similarity
  from public.chunks c
  where c.textbook_id = p_textbook_id
    and c.embedding is not null
    and (p_chapter_ids is null or c.chapter_id = any (p_chapter_ids))
  order by c.embedding <=> query_embedding
  limit match_count;
$$;

-- =====================================================================
-- Storage: private bucket for PDFs. Files live at "<user_id>/<file>.pdf",
-- so each teacher can only touch their own folder.
-- =====================================================================
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('textbooks', 'textbooks', false, 52428800, array['application/pdf'])  -- 50 MB (Supabase free-plan limit)
on conflict (id) do update
  set public = false, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "own textbook files read" on storage.objects;
create policy "own textbook files read" on storage.objects
  for select to authenticated
  using (bucket_id = 'textbooks' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "own textbook files insert" on storage.objects;
create policy "own textbook files insert" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'textbooks' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "own textbook files delete" on storage.objects;
create policy "own textbook files delete" on storage.objects
  for delete to authenticated
  using (bucket_id = 'textbooks' and (storage.foldername(name))[1] = auth.uid()::text);
