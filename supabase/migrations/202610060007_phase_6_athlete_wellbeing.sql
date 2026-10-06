create table public.wellbeing_checkins (
  id uuid not null default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  energy smallint not null check (energy between 1 and 5),
  stress smallint not null check (stress between 1 and 5),
  fatigue smallint not null check (fatigue between 1 and 5),
  soreness smallint not null check (soreness between 1 and 5),
  recovery_feeling smallint not null check (recovery_feeling between 1 and 5),
  mood_self_report smallint check (mood_self_report between 1 and 5),
  note text check (note is null or length(note) <= 500),
  source text not null default 'SELF_REPORTED' check (source = 'SELF_REPORTED'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (athlete_id, id)
);

create table public.camera_wellbeing_sessions (
  id uuid not null default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  started_at timestamptz not null,
  completed_at timestamptz,
  duration_seconds smallint not null check (duration_seconds between 0 and 30),
  status text not null check (status in ('COMPLETED', 'INCOMPLETE', 'CANCELLED')),
  camera_facing text not null default 'FRONT' check (camera_facing = 'FRONT'),
  capture_quality text not null check (capture_quality in ('GOOD', 'FAIR', 'POOR', 'INSUFFICIENT_DATA')),
  valid_frame_ratio double precision not null check (valid_frame_ratio between 0 and 1),
  face_presence_ratio double precision not null check (face_presence_ratio between 0 and 1),
  multiple_face_frames integer not null default 0 check (multiple_face_frames >= 0),
  raw_video_retained boolean not null default false check (raw_video_retained = false),
  source text not null default 'CAMERA_OBSERVED' check (source = 'CAMERA_OBSERVED'),
  created_at timestamptz not null default now(),
  primary key (athlete_id, id),
  check (status <> 'COMPLETED' or duration_seconds = 30),
  check (completed_at is null or completed_at >= started_at)
);

create table public.camera_wellbeing_features (
  id uuid not null default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  session_id uuid not null,
  face_presence_ratio double precision not null check (face_presence_ratio between 0 and 1),
  face_position_stability text not null check (face_position_stability in ('STABLE', 'VARIABLE', 'INSUFFICIENT_DATA')),
  head_movement_magnitude double precision not null check (head_movement_magnitude >= 0),
  head_movement_variability double precision not null check (head_movement_variability >= 0),
  head_orientation_range double precision not null check (head_orientation_range >= 0),
  eye_observation_summary jsonb check (eye_observation_summary is null or jsonb_typeof(eye_observation_summary) = 'object'),
  smile_observation_summary jsonb check (smile_observation_summary is null or jsonb_typeof(smile_observation_summary) = 'object'),
  facial_feature_movement double precision check (facial_feature_movement is null or facial_feature_movement >= 0),
  face_detected_frames integer not null default 0 check (face_detected_frames >= 0),
  valid_frames integer not null default 0 check (valid_frames >= 0),
  invalid_frames integer not null default 0 check (invalid_frames >= 0),
  poor_lighting_frames integer not null default 0 check (poor_lighting_frames >= 0),
  face_out_of_frame_frames integer not null default 0 check (face_out_of_frame_frames >= 0),
  capture_quality text not null check (capture_quality in ('GOOD', 'FAIR', 'POOR', 'INSUFFICIENT_DATA')),
  feature_schema_version text not null check (length(btrim(feature_schema_version)) between 1 and 40),
  source text not null default 'CAMERA_OBSERVED' check (source = 'CAMERA_OBSERVED'),
  created_at timestamptz not null default now(),
  primary key (athlete_id, id),
  constraint camera_wellbeing_features_session_owner_fkey
    foreign key (athlete_id, session_id)
    references public.camera_wellbeing_sessions (athlete_id, id) on delete cascade,
  unique (athlete_id, session_id)
);

create table public.sleep_records (
  id uuid not null default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  start_time timestamptz not null,
  end_time timestamptz not null,
  duration_minutes integer not null check (duration_minutes between 1 and 1440),
  quality_rating smallint check (quality_rating between 1 and 5),
  interruptions integer check (interruptions between 0 and 100),
  notes text check (notes is null or length(notes) <= 500),
  source text not null check (source in ('SELF_REPORTED', 'WATCH_DERIVED', 'HEALTH_CONNECT')),
  source_id text check (source_id is null or length(source_id) <= 120),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_time > start_time and end_time - start_time <= interval '24 hours'),
  primary key (athlete_id, id)
);

create table public.recovery_records (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  date date not null,
  recovery_state text not null check (recovery_state in ('GOOD', 'MODERATE', 'LOW', 'INSUFFICIENT_DATA')),
  supporting_factors jsonb not null default '{}'::jsonb check (jsonb_typeof(supporting_factors) = 'object'),
  calculation_version text not null check (length(btrim(calculation_version)) between 1 and 40),
  source text not null default 'CALCULATED' check (source = 'CALCULATED'),
  created_at timestamptz not null default now(),
  unique (athlete_id, date)
);

create table public.wellbeing_trends (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  metric text not null check (length(btrim(metric)) between 1 and 80),
  period_start date not null,
  period_end date not null,
  classification text not null check (classification in ('IMPROVING', 'STABLE', 'VARIABLE', 'DECLINING', 'INSUFFICIENT_DATA')),
  observation_count integer not null check (observation_count >= 0),
  observations jsonb not null default '[]'::jsonb check (jsonb_typeof(observations) = 'array'),
  source text not null check (source in ('SELF_REPORTED', 'CAMERA_OBSERVED', 'WATCH_DERIVED', 'CALCULATED')),
  created_at timestamptz not null default now(),
  check (period_end >= period_start)
);

create table public.wellbeing_reports (
  id uuid not null default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  report_type text not null check (report_type in (
    'WELLBEING_CHECKIN', 'CAMERA_WELLBEING', 'SLEEP', 'RECOVERY', 'WEEKLY_WELLBEING', 'MONTHLY_WELLBEING'
  )),
  report_data jsonb not null check (jsonb_typeof(report_data) = 'object'),
  source_provenance text[] not null,
  limitations text[] not null check (cardinality(limitations) > 0),
  created_at timestamptz not null default now(),
  primary key (athlete_id, id)
);

create table public.wellbeing_audit_events (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  actor_id uuid not null references public.profiles (id) on delete cascade,
  event_type text not null,
  resource_type text not null,
  resource_id uuid,
  created_at timestamptz not null default now()
);

create index wellbeing_checkins_owner_created_idx on public.wellbeing_checkins (athlete_id, created_at desc);
create index camera_wellbeing_sessions_owner_created_idx on public.camera_wellbeing_sessions (athlete_id, created_at desc);
create index camera_wellbeing_features_owner_created_idx on public.camera_wellbeing_features (athlete_id, created_at desc);
create index sleep_records_owner_start_idx on public.sleep_records (athlete_id, start_time desc);
create index recovery_records_owner_date_idx on public.recovery_records (athlete_id, date desc);
create index wellbeing_trends_owner_period_idx on public.wellbeing_trends (athlete_id, period_end desc);
create index wellbeing_reports_owner_created_idx on public.wellbeing_reports (athlete_id, created_at desc);
create index wellbeing_audit_owner_created_idx on public.wellbeing_audit_events (athlete_id, created_at desc);

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'wellbeing_checkins',
    'camera_wellbeing_sessions',
    'camera_wellbeing_features',
    'sleep_records',
    'recovery_records',
    'wellbeing_trends',
    'wellbeing_reports',
    'wellbeing_audit_events'
  ]
  loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format(
      'create policy %I on public.%I for select to authenticated using (athlete_id = (select auth.uid()))',
      table_name || '_read_self',
      table_name
    );
    execute format(
      'create policy %I on public.%I for insert to authenticated with check (athlete_id = (select auth.uid()))',
      table_name || '_insert_self',
      table_name
    );
    execute format(
      'create policy %I on public.%I for update to authenticated using (athlete_id = (select auth.uid())) with check (athlete_id = (select auth.uid()))',
      table_name || '_update_self',
      table_name
    );
    execute format(
      'create policy %I on public.%I for delete to authenticated using (athlete_id = (select auth.uid()))',
      table_name || '_delete_self',
      table_name
    );
  end loop;
end $$;

drop policy if exists wellbeing_audit_events_update_self on public.wellbeing_audit_events;
drop policy if exists wellbeing_audit_events_delete_self on public.wellbeing_audit_events;
drop policy if exists wellbeing_audit_events_insert_self on public.wellbeing_audit_events;
create policy wellbeing_audit_events_insert_self
  on public.wellbeing_audit_events
  for insert to authenticated
  with check (athlete_id = (select auth.uid()) and actor_id = (select auth.uid()));
