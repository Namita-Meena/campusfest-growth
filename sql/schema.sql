-- CampusFest Growth Intelligence: Supabase PostgreSQL schema
-- Run this ONCE in Supabase > SQL Editor. It is safe to run again.
-- The app fills the tables with the simulated week-4 demo scenario on first start
-- and whenever "Reset demo workspace" is pressed. The original 2025 dataset is NOT
-- stored here: it ships read-only with the app (data/historical).

create table if not exists public.settings (
  key   text primary key,
  value jsonb
);

create table if not exists public.campaigns (
  id                  text primary key,
  name                text not null,
  type                text not null,          -- acquisition | intervention | event_day | reserve
  owner               text,
  hist_channel        text,                   -- matching 2025 campaign id, if any
  description         text,
  status              text not null default 'Planned',
  start_week          integer default 1,
  start_date          date,
  end_date            date,
  budget_allocated    integer not null default 0 check (budget_allocated >= 0),
  open_commitments    integer not null default 0 check (open_commitments >= 0),
  plan_regs_base      integer default 0,
  plan_regs_stretch   integer default 0,
  exp_confirm_rate    numeric check (exp_confirm_rate is null or (exp_confirm_rate >= 0 and exp_confirm_rate <= 1)),
  p_attend_confirmed  numeric check (p_attend_confirmed is null or (p_attend_confirmed >= 0 and p_attend_confirmed <= 1)),
  base_incremental    integer,
  stretch_incremental integer,
  verified_attendees  integer check (verified_attendees is null or verified_attendees >= 0),
  archived            boolean not null default false,
  updated_at          timestamptz default now()
);

create table if not exists public.campaign_metrics (
  id            text primary key,              -- <campaign_id>-W<week>
  campaign_id   text not null,
  week          integer not null check (week between 1 and 12),
  reach         integer not null default 0,
  leads         integer not null default 0,
  reg_starts    integer not null default 0,
  registrations integer not null default 0,
  confirmed     integer not null default 0,
  spend         integer not null default 0,
  updated_at    timestamptz default now()
);

create table if not exists public.experiment_results (
  id         text primary key,                 -- <experiment>-W<week>
  experiment text not null,
  week       integer not null,
  inputs     jsonb not null default '{}'::jsonb,
  updated_at timestamptz default now()
);

create table if not exists public.tasks (
  id          text primary key,
  title       text not null,
  description text,
  campaign_id text,
  owner       text,
  deadline    date,
  priority    text,
  status      text,
  evidence    text,
  source      text,
  created_at  timestamptz default now()
);

create table if not exists public.decision_logs (
  id             text primary key,
  created_at     timestamptz default now(),
  week           integer,
  decision_key   text,
  campaign_id    text,
  recommendation text,
  metric         text,
  action         text,
  outcome        text,
  amount_moved   integer default 0,
  transfer_from  text,
  transfer_to    text,
  decided_by     text,
  note           text
);

-- Security: Row Level Security ON with NO policies. The publishable (public) key can
-- therefore read and write nothing. The app uses the SECRET key, which stays in
-- Streamlit's server-side secrets and bypasses RLS.
alter table public.settings           enable row level security;
alter table public.campaigns          enable row level security;
alter table public.campaign_metrics   enable row level security;
alter table public.experiment_results enable row level security;
alter table public.tasks              enable row level security;
alter table public.decision_logs      enable row level security;

select 'CampusFest schema ready: 6 tables created' as result;
