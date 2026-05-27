-- Politometro: schema database proprietario
-- Pensato per Postgres/Supabase/Neon/self-hosted Postgres.
-- I dati politici sono sensibili: usare solo con consenso esplicito, privacy policy completa,
-- accesso admin protetto e retention documentata.

create extension if not exists pgcrypto;

create table if not exists user_accounts (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  last_seen_at timestamptz,
  email_hash text unique,
  auth_provider text,
  external_auth_id text,
  nickname text,
  profile_storage_consent boolean not null default false,
  deleted_at timestamptz,
  unique (auth_provider, external_auth_id)
);

create table if not exists admin_users (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  email text not null unique,
  role text not null default 'viewer' check (role in ('owner', 'admin', 'analyst', 'viewer')),
  disabled_at timestamptz
);

create table if not exists model_versions (
  id uuid primary key default gen_random_uuid(),
  model_version text not null,
  entity_registry_version text,
  question_calibration_version text,
  created_at timestamptz not null default now(),
  notes text
);

create table if not exists quiz_sessions (
  id uuid primary key default gen_random_uuid(),
  public_session_id text unique,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  mode text not null check (mode in ('social', 'quick', 'deep', 'election_2027')),
  model_version_id uuid references model_versions(id),
  user_account_id uuid references user_accounts(id) on delete set null,
  consent_version text,
  research_consent boolean not null default false,
  feedback_consent boolean not null default false,
  age_range text,
  education text,
  origin_area text,
  country_region text,
  political_interest text,
  political_knowledge text,
  news_frequency text,
  student_worker text,
  user_agent_hash text,
  ip_hash text,
  deleted_at timestamptz
);

create table if not exists answers (
  id bigserial primary key,
  session_id uuid not null references quiz_sessions(id) on delete cascade,
  question_id text not null,
  answer_value smallint not null check (answer_value between 1 and 7),
  answered_at timestamptz not null default now(),
  unique (session_id, question_id)
);

create table if not exists result_profiles (
  session_id uuid primary key references quiz_sessions(id) on delete cascade,
  created_at timestamptz not null default now(),
  confidence numeric,
  self_coherence numeric,
  reliability_score numeric,
  reliability_label text,
  ideology_name text,
  top_party_name text,
  top_historical_name text,
  nemesis_name text,
  economy numeric,
  authority numeric,
  culture numeric,
  geopolitics numeric,
  environment numeric,
  technology numeric,
  equality numeric,
  justice numeric,
  raw_result jsonb not null
);

create table if not exists feedback (
  id bigserial primary key,
  session_id uuid not null references quiz_sessions(id) on delete cascade,
  created_at timestamptz not null default now(),
  accuracy_rating smallint check (accuracy_rating between 1 and 5),
  self_label text,
  closest_party_self text,
  notes text,
  predicted_ideology text,
  predicted_parties text[]
);

create table if not exists support_contacts (
  id bigserial primary key,
  created_at timestamptz not null default now(),
  name text,
  email text,
  organization text,
  topic text not null default 'supporto',
  message text not null,
  consent_contact boolean not null default false,
  status text not null default 'nuovo' check (status in ('nuovo', 'in_lavorazione', 'chiuso', 'spam')),
  source text
);

create table if not exists admin_audit_log (
  id bigserial primary key,
  created_at timestamptz not null default now(),
  admin_user_id uuid references admin_users(id) on delete set null,
  action text not null,
  target_type text,
  target_id text,
  details jsonb
);

create table if not exists entity_versions (
  id uuid primary key default gen_random_uuid(),
  registry_version text not null,
  created_at timestamptz not null default now(),
  source_note text,
  raw_registry jsonb not null
);

create table if not exists entity_positions (
  id bigserial primary key,
  entity_version_id uuid not null references entity_versions(id) on delete cascade,
  name text not null,
  category text not null check (category in ('partito', 'ideologia', 'storico')),
  high_risk boolean not null default false,
  evidence text,
  source_url text,
  economy numeric not null,
  authority numeric not null,
  culture numeric not null,
  geopolitics numeric not null,
  environment numeric not null,
  technology numeric not null,
  equality numeric not null,
  justice numeric not null,
  unique (entity_version_id, name)
);

create table if not exists election_2027_sources (
  id bigserial primary key,
  party_name text not null,
  source_type text not null check (source_type in ('programma', 'dichiarazione', 'voto_parlamentare', 'intervista', 'fact_check')),
  title text not null,
  url text,
  published_at date,
  captured_at timestamptz not null default now(),
  reliability text not null default 'da_verificare',
  notes text
);

create table if not exists election_2027_positions (
  id bigserial primary key,
  source_id bigint references election_2027_sources(id) on delete set null,
  party_name text not null,
  topic text not null,
  question_id text,
  position_text text not null,
  axis_name text,
  axis_value numeric check (axis_value between -1 and 1),
  confidence numeric check (confidence between 0 and 1),
  reviewer text,
  reviewed_at timestamptz
);

create index if not exists answers_question_idx on answers(question_id);
create index if not exists sessions_created_idx on quiz_sessions(created_at);
create index if not exists sessions_consent_idx on quiz_sessions(research_consent) where research_consent = true;
create index if not exists sessions_user_idx on quiz_sessions(user_account_id) where user_account_id is not null;
create index if not exists result_profiles_party_idx on result_profiles(top_party_name);
create index if not exists result_profiles_ideology_idx on result_profiles(ideology_name);
create index if not exists support_contacts_status_idx on support_contacts(status);
