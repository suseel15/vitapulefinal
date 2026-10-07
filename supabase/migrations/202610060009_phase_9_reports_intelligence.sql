create table public.reports (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  created_by uuid not null references public.profiles (id) on delete restrict,
  report_type text not null check (report_type in (
    'MEDICAL_REPORT_ANALYSIS', 'BIOMARKER_REPORT', 'BODY_MAP_REPORT',
    'HEALTH_INTELLIGENCE_REPORT', 'REHAB_SESSION_REPORT', 'MOVEMENT_ANALYSIS_REPORT',
    'EXERCISE_PROGRESS_REPORT', 'FUNCTIONAL_TEST_REPORT', 'READINESS_REPORT',
    'RETURN_TO_SPORT_REPORT', 'WELLBEING_CHECKIN_REPORT', 'CAMERA_WELLBEING_REPORT',
    'SLEEP_REPORT', 'RECOVERY_REPORT', 'CONNECTIVITY_REPORT', 'NUTRITION_REPORT',
    'MEDICATION_REPORT', 'ANTI_DOPING_REPORT', 'SKIN_SCREENING_REPORT',
    'SAFETY_INCIDENT_REPORT', 'WEEKLY_HEALTH_REPORT', 'WEEKLY_REHAB_REPORT',
    'WEEKLY_WELLBEING_REPORT', 'WEEKLY_ATHLETE_REPORT', 'MONTHLY_HEALTH_REPORT',
    'MONTHLY_REHAB_REPORT', 'MONTHLY_ATHLETE_REPORT', 'DOCTOR_ATHLETE_REPORT',
    'FULL_ATHLETE_REPORT'
  )),
  feature_id uuid,
  status text not null default 'REQUESTED' check (status in (
    'REQUESTED', 'QUEUED', 'COLLECTING_DATA', 'VALIDATING_INPUT', 'GENERATING_AI',
    'VALIDATING_AI', 'BUILDING_REPORT', 'RENDERING_HTML', 'RENDERING_PDF',
    'UPLOADING', 'COMPLETED', 'FAILED', 'CANCELLED'
  )),
  title text not null check (length(title) between 1 and 200),
  summary text not null default '',
  date_range_start timestamptz,
  date_range_end timestamptz,
  provider text,
  model text,
  model_version text,
  prompt_version text,
  schema_version text not null default 'report-v1',
  ai_status text not null default 'PENDING' check (ai_status in ('PENDING', 'COMPLETED', 'UNAVAILABLE', 'REJECTED', 'SKIPPED')),
  html_status text not null default 'PENDING' check (html_status in ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'SKIPPED')),
  pdf_status text not null default 'PENDING' check (pdf_status in ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'SKIPPED')),
  email_status text not null default 'NOT_REQUESTED' check (email_status in ('NOT_REQUESTED', 'QUEUED', 'SENDING', 'SENT', 'FAILED')),
  report_version text not null default 'v1',
  generated_from_version uuid references public.reports (id) on delete set null,
  source_version text not null default 'source-v1',
  template_version text not null default 'v1',
  idempotency_key text,
  input_hash text,
  report_data jsonb not null default '{}'::jsonb check (jsonb_typeof(report_data) = 'object'),
  error_code text check (error_code is null or length(error_code) <= 80),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  check (date_range_end is null or date_range_start is null or date_range_end >= date_range_start),
  unique (athlete_id, idempotency_key)
);

create table public.report_sources (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  report_id uuid not null references public.reports (id) on delete cascade,
  source_type text not null,
  source_id text not null check (length(source_id) between 1 and 160),
  source_timestamp timestamptz not null,
  source_label text not null check (length(source_label) between 1 and 200),
  source_hash text not null check (length(source_hash) = 64),
  provenance text not null check (provenance in (
    'DIRECTLY_REPORTED', 'SELF_REPORTED', 'WATCH_DERIVED', 'LIVE_SENSOR',
    'CALCULATED', 'MODEL_INFERRED', 'AI_INTERPRETED', 'CLINICIAN_ENTERED',
    'SIMULATION', 'USER_ENTERED'
  )),
  created_at timestamptz not null default now(),
  unique (report_id, source_type, source_id)
);

create table public.report_ai_outputs (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  report_id uuid not null references public.reports (id) on delete cascade,
  provider text not null,
  model text not null,
  model_version text not null,
  prompt_version text not null,
  schema_version text not null,
  input_hash text not null check (length(input_hash) = 64),
  structured_output jsonb not null check (jsonb_typeof(structured_output) = 'object'),
  validation_status text not null check (validation_status in ('VALID', 'REJECTED')),
  safety_status text not null check (safety_status in ('PASSED', 'REJECTED')),
  latency_ms integer not null check (latency_ms >= 0),
  created_at timestamptz not null default now()
);

create table public.report_files (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  report_id uuid not null references public.reports (id) on delete cascade,
  file_type text not null check (file_type in ('HTML', 'PDF')),
  storage_bucket text not null,
  storage_path text not null unique,
  mime_type text not null,
  file_size bigint not null check (file_size between 1 and 52428800),
  sha256 text not null check (length(sha256) = 64),
  created_at timestamptz not null default now(),
  unique (report_id, file_type)
);

create table public.report_jobs (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  report_id uuid not null references public.reports (id) on delete cascade,
  job_type text not null check (job_type in ('REPORT_GENERATION', 'AI_GENERATION', 'HTML_RENDER', 'PDF_RENDER', 'UPLOAD', 'EMAIL')),
  status text not null default 'QUEUED' check (status in ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
  attempts integer not null default 0 check (attempts between 0 and 10),
  started_at timestamptz,
  completed_at timestamptz,
  error_code text check (error_code is null or length(error_code) <= 80),
  created_at timestamptz not null default now()
);

create table public.report_pipeline_events (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  report_id uuid not null references public.reports (id) on delete cascade,
  stage text not null,
  status text not null,
  detail_code text,
  created_at timestamptz not null default now()
);

create table public.report_email_deliveries (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  report_id uuid not null references public.reports (id) on delete cascade,
  recipient text not null check (length(recipient) between 3 and 254),
  status text not null default 'QUEUED' check (status in ('QUEUED', 'SENDING', 'SENT', 'FAILED')),
  error_code text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table public.report_access_audit (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  report_id uuid not null references public.reports (id) on delete cascade,
  actor_id uuid not null references public.profiles (id) on delete restrict,
  action text not null check (action in ('REPORT_VIEWED', 'REPORT_DOWNLOADED', 'REPORT_EMAILED', 'REPORT_SHARED')),
  created_at timestamptz not null default now()
);

create table public.ai_prompt_registry (
  id uuid primary key default gen_random_uuid(),
  prompt_name text not null,
  version text not null,
  purpose text not null,
  prompt_hash text not null check (length(prompt_hash) = 64),
  active boolean not null default false,
  created_at timestamptz not null default now(),
  unique (prompt_name, version)
);

create table public.report_schema_registry (
  id uuid primary key default gen_random_uuid(),
  schema_name text not null,
  version text not null,
  schema_json jsonb not null check (jsonb_typeof(schema_json) = 'object'),
  active boolean not null default false,
  created_at timestamptz not null default now(),
  unique (schema_name, version)
);

create table public.report_template_registry (
  id uuid primary key default gen_random_uuid(),
  template_name text not null,
  version text not null,
  active boolean not null default false,
  created_at timestamptz not null default now(),
  unique (template_name, version)
);

create table public.athlete_timeline_events (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  event_type text not null,
  source_type text not null,
  source_id text not null,
  event_time timestamptz not null,
  title text not null,
  summary text not null default '',
  severity text,
  created_at timestamptz not null default now(),
  unique (athlete_id, source_type, source_id)
);

create table public.athlete_intelligence_snapshots (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  report_id uuid not null references public.reports (id) on delete cascade,
  period_start timestamptz not null,
  period_end timestamptz not null,
  data_completeness text not null check (data_completeness in ('HIGH', 'MODERATE', 'LOW', 'INSUFFICIENT')),
  calculation_version text not null,
  summary_json jsonb not null check (jsonb_typeof(summary_json) = 'object'),
  created_at timestamptz not null default now(),
  check (period_end >= period_start),
  unique (report_id, calculation_version)
);

create table public.athlete_intelligence_insights (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  snapshot_id uuid not null references public.athlete_intelligence_snapshots (id) on delete cascade,
  period_start timestamptz not null,
  period_end timestamptz not null,
  insight_type text not null check (insight_type in (
    'TREND', 'CHANGE', 'STABILITY', 'REPEATED_PATTERN', 'CORRELATION',
    'DATA_QUALITY', 'MILESTONE', 'REVIEW_ITEM'
  )),
  statement text not null,
  source_ids text[] not null default '{}',
  evidence_strength text not null check (evidence_strength in ('DIRECT', 'SUPPORTED', 'LIMITED', 'INSUFFICIENT')),
  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'REVIEWED', 'DISMISSED', 'EXPIRED')),
  interpretation_source text not null default 'CALCULATED' check (interpretation_source in ('CALCULATED', 'AI_INTERPRETED')),
  created_at timestamptz not null default now(),
  check (period_end >= period_start),
  unique (snapshot_id, insight_type, statement)
);

create table public.review_items (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  insight_id uuid references public.athlete_intelligence_insights (id) on delete set null,
  title text not null,
  description text not null,
  source_ids text[] not null default '{}',
  status text not null default 'OPEN' check (status in ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'DISMISSED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index reports_owner_created_idx on public.reports (athlete_id, created_at desc);
create index reports_owner_status_idx on public.reports (athlete_id, status, created_at desc);
create index report_sources_report_idx on public.report_sources (athlete_id, report_id);
create index report_jobs_status_idx on public.report_jobs (status, created_at);
create index report_audit_report_idx on public.report_access_audit (report_id, created_at desc);
create index timeline_owner_time_idx on public.athlete_timeline_events (athlete_id, event_time desc);
create index intelligence_insights_owner_period_idx on public.athlete_intelligence_insights (athlete_id, period_end desc);
create index review_items_owner_status_idx on public.review_items (athlete_id, status, created_at desc);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('reports', 'reports', false, 52428800, array['text/html', 'application/pdf'])
on conflict (id) do update set public = false, file_size_limit = 52428800;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'reports', 'report_sources', 'report_ai_outputs', 'report_files',
    'report_jobs', 'report_pipeline_events', 'report_email_deliveries',
    'report_access_audit', 'athlete_timeline_events',
    'athlete_intelligence_snapshots', 'athlete_intelligence_insights', 'review_items'
  ]
  loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('revoke all on public.%I from anon, authenticated', table_name);
    execute format('grant select on public.%I to authenticated', table_name);
    execute format(
      'create policy %I on public.%I for select to authenticated using (public.is_authorized_health_reader(athlete_id))',
      table_name || '_read_authorized',
      table_name
    );
  end loop;
end $$;

alter table public.ai_prompt_registry enable row level security;
alter table public.report_schema_registry enable row level security;
alter table public.report_template_registry enable row level security;
revoke all on public.ai_prompt_registry, public.report_schema_registry, public.report_template_registry from anon, authenticated;
grant select on public.ai_prompt_registry, public.report_schema_registry, public.report_template_registry to authenticated;
create policy ai_prompt_registry_read_authenticated on public.ai_prompt_registry for select to authenticated using (active);
create policy report_schema_registry_read_authenticated on public.report_schema_registry for select to authenticated using (active);
create policy report_template_registry_read_authenticated on public.report_template_registry for select to authenticated using (active);

create policy report_storage_read_authorized on storage.objects
  for select to authenticated
  using (
    case
      when bucket_id = 'reports' then
        case
          when (storage.foldername(name))[1] ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
          then public.is_authorized_health_reader(((storage.foldername(name))[1])::uuid)
          else false
        end
      else false
    end
  );
revoke insert, update, delete on storage.objects from authenticated, anon;
