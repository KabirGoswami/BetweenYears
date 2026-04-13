-- ============================================================
-- BetweenYears — PostgreSQL Schema
-- Run this in the Supabase SQL Editor
-- ============================================================

-- ── Extensions ────────────────────────────────────────────────
create extension if not exists "uuid-ossp";
create extension if not exists "pg_cron";   -- for scheduled badge checks (optional)

-- ── ENUM types ───────────────────────────────────────────────
create type mood_type as enum ('calm', 'anxious', 'hopeful', 'confused', 'motivated');
create type story_status as enum ('active', 'flagged', 'removed');
create type privacy_request_type as enum ('export', 'delete');
create type privacy_request_status as enum ('pending', 'processing', 'completed', 'cancelled');
create type xp_source as enum (
  'journal_entry', 'mood_log', 'streak_milestone',
  'badge_earned', 'community_story', 'values_test', 'ai_analysis'
);

-- ── Users profile (extends auth.users) ───────────────────────
create table public.user_profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  display_name  text,
  avatar_url    text,
  bio           text,
  -- privacy settings
  journal_private        boolean not null default true,
  analytics_opt_in       boolean not null default false,
  community_anonymous    boolean not null default true,
  -- metadata
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- ── Prompts ──────────────────────────────────────────────────
create table public.prompts (
  id          uuid primary key default uuid_generate_v4(),
  text        text not null,
  category    text not null default 'daily',   -- daily | life | future | ai-generated
  is_active   boolean not null default true,
  created_at  timestamptz not null default now()
);

insert into public.prompts (text, category) values
  ('What is one thing I keep avoiding thinking about?', 'daily'),
  ('What does success mean to me, not to others?', 'daily'),
  ('When do I feel most like myself?', 'daily'),
  ('What fear is holding me back right now?', 'daily'),
  ('What would I choose if I knew I wouldn''t fail?', 'daily'),
  ('What do I value most in my daily life?', 'daily'),
  ('Describe the kind of life you''d feel proud of in 5 years.', 'future'),
  ('What do people ask you for help with most?', 'life'),
  ('When did you last feel completely yourself?', 'life'),
  ('What is one small step I could take this week toward my goal?', 'future');

-- ── Journal entries ───────────────────────────────────────────
create table public.journals (
  id            uuid primary key default uuid_generate_v4(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  prompt_id     uuid references public.prompts(id),
  prompt_text   text,                    -- snapshot of prompt at time of writing
  content       text not null,
  mood          mood_type,
  word_count    int generated always as (
                  array_length(regexp_split_to_array(trim(content), '\s+'), 1)
                ) stored,
  is_public     boolean not null default false,
  ai_analyzed   boolean not null default false,
  deleted_at    timestamptz,             -- soft delete
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- ── AI insights  ──────────────────────────────────────────────
create table public.ai_insights (
  id            uuid primary key default uuid_generate_v4(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  journal_id    uuid references public.journals(id) on delete cascade,
  insight_type  text not null,           -- 'entry_analysis' | 'pattern' | 'prompt' | 'decision'
  themes        text[],
  emotional_tone text,
  summary       text not null,
  follow_up_prompt text,
  raw_response  jsonb,                   -- full Gemini response for debugging
  created_at    timestamptz not null default now()
);

-- ── Streaks ───────────────────────────────────────────────────
create table public.streaks (
  user_id           uuid primary key references auth.users(id) on delete cascade,
  current_streak    int not null default 0,
  longest_streak    int not null default 0,
  last_entry_date   date,
  total_entries     int not null default 0,
  total_xp          int not null default 0,
  level             text not null default 'Beginner',
  updated_at        timestamptz not null default now()
);

-- ── XP event log ─────────────────────────────────────────────
create table public.xp_events (
  id          uuid primary key default uuid_generate_v4(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  source      xp_source not null,
  amount      int not null,
  metadata    jsonb,
  created_at  timestamptz not null default now()
);

-- ── Badge definitions ─────────────────────────────────────────
create table public.badges (
  id          uuid primary key default uuid_generate_v4(),
  slug        text unique not null,
  icon        text not null,
  name        text not null,
  description text not null,
  xp_reward   int not null default 50,
  is_active   boolean not null default true
);

insert into public.badges (slug, icon, name, description, xp_reward) values
  ('first_reflection',  '🌱', 'First Reflection',  'Saved your very first journal entry',         50),
  ('streak_3',          '🔥', '3-Day Streak',       'Reflected 3 days in a row',                  50),
  ('values_explorer',   '💎', 'Values Explorer',    'Completed the values discovery test',         50),
  ('deep_diver',        '🌊', 'Deep Diver',         'Wrote a reflection longer than 200 words',    75),
  ('streak_10',         '⭐', '10-Day Streak',      'Reflected 10 days in a row',                 100),
  ('pattern_seeker',   '🧠', 'Pattern Seeker',     'Used AI analysis 5 times',                    75),
  ('community_voice',   '🤝', 'Community Voice',    'Shared a story in the community section',     50),
  ('streak_30',         '🏆', '30-Day Streak',      'Reflected 30 days in a row — incredible!',   200),
  ('mind_dump',         '🧹', 'Mind Clearer',       'Completed 10 journal entries',               100);

-- ── User badges ───────────────────────────────────────────────
create table public.user_badges (
  id          uuid primary key default uuid_generate_v4(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  badge_id    uuid not null references public.badges(id),
  earned_at   timestamptz not null default now(),
  unique (user_id, badge_id)
);

-- ── Community stories ─────────────────────────────────────────
create table public.community_stories (
  id            uuid primary key default uuid_generate_v4(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  journal_id    uuid references public.journals(id),   -- optional — sourced from a journal
  content       text not null,
  context_label text,             -- e.g. "3rd year, Engineering"
  tags          text[],
  is_anonymous  boolean not null default true,
  status        story_status not null default 'active',
  flag_count    int not null default 0,
  reaction_count int not null default 0,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- ── Story reactions ───────────────────────────────────────────
create table public.story_reactions (
  id          uuid primary key default uuid_generate_v4(),
  story_id    uuid not null references public.community_stories(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  emoji       text not null default '❤️',
  created_at  timestamptz not null default now(),
  unique (story_id, user_id)        -- one reaction per user per story
);

-- ── Story flags (moderation) ──────────────────────────────────
create table public.story_flags (
  id          uuid primary key default uuid_generate_v4(),
  story_id    uuid not null references public.community_stories(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  reason      text,
  created_at  timestamptz not null default now(),
  unique (story_id, user_id)
);

-- ── Notification preferences ──────────────────────────────────
create table public.notification_preferences (
  user_id           uuid primary key references auth.users(id) on delete cascade,
  email_reminders   boolean not null default true,
  reminder_time     time not null default '09:00',    -- local time
  timezone          text not null default 'UTC',
  weekly_summary    boolean not null default true,
  badge_alerts      boolean not null default true,
  streak_alerts     boolean not null default true,
  updated_at        timestamptz not null default now()
);

-- ── Email audit log ───────────────────────────────────────────
create table public.email_log (
  id            uuid primary key default uuid_generate_v4(),
  user_id       uuid references auth.users(id) on delete set null,
  email_address text not null,
  template      text not null,
  status        text not null default 'sent',  -- sent | failed | bounced
  resend_id     text,
  created_at    timestamptz not null default now()
);

-- ── Privacy requests (GDPR) ───────────────────────────────────
create table public.privacy_requests (
  id          uuid primary key default uuid_generate_v4(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  type        privacy_request_type not null,
  status      privacy_request_status not null default 'pending',
  export_url  text,           -- signed URL for data export download
  requested_at  timestamptz not null default now(),
  completed_at  timestamptz
);

-- ============================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================

-- Auto-create supporting rows when a new user signs up
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.user_profiles (id, display_name)
    values (new.id, coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1)));

  insert into public.streaks (user_id)
    values (new.id);

  insert into public.notification_preferences (user_id)
    values (new.id);

  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Update updated_at automatically
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger trg_user_profiles_updated_at
  before update on public.user_profiles
  for each row execute procedure public.set_updated_at();

create trigger trg_journals_updated_at
  before update on public.journals
  for each row execute procedure public.set_updated_at();

create trigger trg_community_stories_updated_at
  before update on public.community_stories
  for each row execute procedure public.set_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

alter table public.user_profiles          enable row level security;
alter table public.journals               enable row level security;
alter table public.ai_insights            enable row level security;
alter table public.streaks                enable row level security;
alter table public.xp_events              enable row level security;
alter table public.user_badges            enable row level security;
alter table public.community_stories      enable row level security;
alter table public.story_reactions        enable row level security;
alter table public.story_flags            enable row level security;
alter table public.notification_preferences enable row level security;
alter table public.privacy_requests       enable row level security;

-- user_profiles: own row only
create policy "Users manage own profile"
  on public.user_profiles for all
  using (auth.uid() = id);

-- journals: own entries only (+ deleted_at filter handled in queries)
create policy "Users manage own journals"
  on public.journals for all
  using (auth.uid() = user_id);

-- ai_insights: own insights only
create policy "Users manage own ai insights"
  on public.ai_insights for all
  using (auth.uid() = user_id);

-- streaks: own row only
create policy "Users manage own streak"
  on public.streaks for all
  using (auth.uid() = user_id);

-- xp_events: own events only
create policy "Users see own XP events"
  on public.xp_events for all
  using (auth.uid() = user_id);

-- user_badges: own badges only
create policy "Users see own badges"
  on public.user_badges for all
  using (auth.uid() = user_id);

-- community_stories: authenticated users can read active stories; own rows full control
create policy "Authenticated users read active stories"
  on public.community_stories for select
  using (auth.role() = 'authenticated' and status = 'active');

create policy "Users manage own stories"
  on public.community_stories for all
  using (auth.uid() = user_id);

-- story_reactions: authenticated users can read; own rows for write
create policy "Authenticated users read reactions"
  on public.story_reactions for select
  using (auth.role() = 'authenticated');

create policy "Users manage own reactions"
  on public.story_reactions for all
  using (auth.uid() = user_id);

-- story_flags
create policy "Users manage own flags"
  on public.story_flags for all
  using (auth.uid() = user_id);

-- notification_preferences: own row only
create policy "Users manage own notification prefs"
  on public.notification_preferences for all
  using (auth.uid() = user_id);

-- privacy_requests: own requests only
create policy "Users manage own privacy requests"
  on public.privacy_requests for all
  using (auth.uid() = user_id);

-- badges table: everyone can read (no RLS needed for global definitions)
alter table public.badges disable row level security;
alter table public.prompts disable row level security;
alter table public.email_log disable row level security;  -- admin only via service role

-- ============================================================
-- INDEXES
-- ============================================================
create index idx_journals_user_id on public.journals(user_id);
create index idx_journals_created_at on public.journals(created_at desc);
create index idx_journals_deleted_at on public.journals(deleted_at) where deleted_at is null;
create index idx_ai_insights_journal_id on public.ai_insights(journal_id);
create index idx_xp_events_user_id on public.xp_events(user_id);
create index idx_user_badges_user_id on public.user_badges(user_id);
create index idx_community_stories_status on public.community_stories(status) where status = 'active';
create index idx_community_stories_created_at on public.community_stories(created_at desc);
create index idx_story_reactions_story_id on public.story_reactions(story_id);
