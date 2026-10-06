alter table public.rehab_sessions
  add constraint rehab_sessions_athlete_id_id_unique unique (athlete_id, id);

alter table public.movement_quality_results
  add column consistency text check (
    consistency is null or consistency in ('STABLE', 'MODERATE', 'VARIABLE', 'INCONSISTENT', 'INSUFFICIENT_DATA')
  ),
  add column sensor_quality_status text check (
    sensor_quality_status is null or sensor_quality_status in ('EXCELLENT', 'GOOD', 'DEGRADED', 'POOR', 'INSUFFICIENT')
  ),
  add column baseline_comparison text check (
    baseline_comparison is null or baseline_comparison in (
      'PERSONAL_BASELINE_NOT_AVAILABLE', 'STABLE', 'IMPROVED', 'DEVIATION_DETECTED', 'INSUFFICIENT_DATA'
    )
  ),
  add column exercise_recognition_status text check (
    exercise_recognition_status is null or exercise_recognition_status in (
      'RECOGNIZED', 'UNKNOWN', 'INSUFFICIENT_DATA', 'MODEL_UNAVAILABLE'
    )
  ),
  add column recognized_exercise text check (
    recognized_exercise is null or recognized_exercise in (
      'REST', 'WALK', 'SQUAT', 'SIT_TO_STAND', 'LEG_RAISE', 'CALF_RAISE',
      'HAMSTRING_BRIDGE', 'BALANCE', 'UNKNOWN'
    )
  ),
  add column prediction_source text check (
    prediction_source is null or prediction_source in ('MODEL_INFERRED', 'DETERMINISTIC', 'MANUAL')
  ),
  add column model_name text,
  add column model_version text,
  add column feature_schema_version text,
  add column processing_version text;

create table public.movement_model_registry (
  id uuid primary key default gen_random_uuid(),
  model_name text not null check (length(btrim(model_name)) between 1 and 100),
  model_type text not null check (model_type = 'RANDOM_FOREST'),
  version text not null check (length(btrim(version)) between 1 and 80),
  feature_schema_version text not null,
  training_dataset_version text not null,
  created_at timestamptz not null default now(),
  metrics jsonb not null default '{}'::jsonb check (jsonb_typeof(metrics) = 'object'),
  artifact_path text not null,
  artifact_sha256 text not null check (artifact_sha256 ~ '^[a-f0-9]{64}$'),
  status text not null check (status in ('EXPERIMENTAL', 'VALIDATED', 'ACTIVE', 'DEPRECATED', 'REJECTED')),
  supported_exercises text[] not null default '{}',
  minimum_sampling_rate_hz double precision not null check (minimum_sampling_rate_hz > 0 and minimum_sampling_rate_hz <= 100),
  recommended_sampling_rate_hz double precision not null check (
    recommended_sampling_rate_hz >= minimum_sampling_rate_hz and recommended_sampling_rate_hz <= 100
  ),
  sensor_type text not null check (sensor_type = 'MPU6050'),
  supported_sensor_placements text[] not null default '{}',
  updated_at timestamptz not null default now(),
  unique (model_name, version)
);

create table public.movement_dataset_registry (
  id uuid primary key default gen_random_uuid(),
  dataset_name text not null check (length(btrim(dataset_name)) between 1 and 120),
  version text not null check (length(btrim(version)) between 1 and 80),
  description text not null default '',
  sample_count integer not null check (sample_count >= 0),
  session_count integer not null check (session_count >= 0),
  athlete_count integer not null check (athlete_count >= 0),
  status text not null check (status in ('DRAFT', 'VALIDATED', 'REJECTED', 'RETIRED')),
  created_at timestamptz not null default now(),
  unique (dataset_name, version)
);

create table public.movement_predictions (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  session_id uuid not null,
  exercise_id uuid not null references public.rehab_exercises (id) on delete restrict,
  prediction_type text not null check (prediction_type = 'EXERCISE_CLASS'),
  prediction text not null check (
    prediction in ('REST', 'WALK', 'SQUAT', 'SIT_TO_STAND', 'LEG_RAISE', 'CALF_RAISE', 'HAMSTRING_BRIDGE', 'BALANCE', 'UNKNOWN')
  ),
  model_name text not null,
  model_version text not null,
  feature_schema_version text not null,
  timestamp timestamptz not null,
  source text not null check (source = 'MODEL_INFERRED'),
  created_at timestamptz not null default now(),
  constraint movement_predictions_session_owner_fkey
    foreign key (athlete_id, session_id)
    references public.rehab_sessions (athlete_id, id) on delete cascade,
  unique (session_id, timestamp, prediction_type)
);

create index movement_predictions_owner_session_idx
  on public.movement_predictions (athlete_id, session_id, timestamp desc);

create table public.movement_events (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  session_id uuid not null,
  timestamp timestamptz not null,
  event_type text not null check (
    event_type in (
      'REP_COMPLETED', 'QUALITY_CHANGED', 'FATIGUE_SIGNAL_CHANGED',
      'ANOMALY_DETECTED', 'EXERCISE_CHANGED', 'SENSOR_QUALITY_DEGRADED'
    )
  ),
  severity text not null check (severity in ('LOW', 'MODERATE', 'HIGH')),
  description text not null check (length(btrim(description)) between 1 and 240),
  source text not null check (source in ('LIVE_SENSOR', 'SIMULATION', 'MANUAL', 'CALCULATED', 'MODEL_INFERRED')),
  created_at timestamptz not null default now(),
  constraint movement_events_session_owner_fkey
    foreign key (athlete_id, session_id)
    references public.rehab_sessions (athlete_id, id) on delete cascade,
  unique (session_id, event_type, timestamp)
);

create index movement_events_owner_session_idx
  on public.movement_events (athlete_id, session_id, timestamp desc);

create table public.athlete_movement_baselines (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  exercise_id uuid not null references public.rehab_exercises (id) on delete restrict,
  sensor_placement text not null check (
    sensor_placement in ('THIGH', 'SHANK', 'FOREARM', 'UPPER_ARM', 'WAIST', 'CHEST', 'OTHER')
  ),
  baseline_version integer not null check (baseline_version >= 1),
  sample_count integer not null check (sample_count >= 0),
  session_count integer not null check (session_count >= 0),
  repetition_count integer not null check (repetition_count >= 0),
  mean_features jsonb not null check (jsonb_typeof(mean_features) = 'object'),
  std_features jsonb not null check (jsonb_typeof(std_features) = 'object'),
  status text not null check (status in ('AVAILABLE', 'REVIEW_REQUIRED', 'RETIRED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (athlete_id, exercise_id, sensor_placement)
);

create index athlete_movement_baselines_owner_exercise_idx
  on public.athlete_movement_baselines (athlete_id, exercise_id, sensor_placement);

create table public.movement_anomaly_results (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  session_id uuid not null,
  event_timestamp timestamptz not null,
  anomaly_type text not null check (anomaly_type = 'UNUSUAL_MOVEMENT_PATTERN'),
  severity text not null check (severity in ('LOW', 'MODERATE', 'HIGH')),
  baseline_deviation double precision check (baseline_deviation is null or baseline_deviation between 0 and 100),
  model_name text,
  model_version text,
  requires_review boolean not null default false,
  source text not null check (source in ('CALCULATED', 'MODEL_INFERRED')),
  created_at timestamptz not null default now(),
  constraint movement_anomaly_session_owner_fkey
    foreign key (athlete_id, session_id)
    references public.rehab_sessions (athlete_id, id) on delete cascade,
  unique (session_id, event_timestamp, anomaly_type)
);

create index movement_anomaly_owner_session_idx
  on public.movement_anomaly_results (athlete_id, session_id, event_timestamp desc);

create table public.movement_fatigue_results (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  session_id uuid not null,
  fatigue_state text not null check (fatigue_state in ('LOW', 'MODERATE', 'HIGH', 'INSUFFICIENT_DATA')),
  trend text not null check (trend in ('IMPROVING', 'STABLE', 'WORSENING', 'INSUFFICIENT_DATA')),
  supporting_metrics jsonb not null default '{}'::jsonb check (jsonb_typeof(supporting_metrics) = 'object'),
  calculation_version text not null,
  source text not null check (source in ('LIVE_SENSOR', 'SIMULATION', 'CALCULATED')),
  created_at timestamptz not null default now(),
  constraint movement_fatigue_session_owner_fkey
    foreign key (athlete_id, session_id)
    references public.rehab_sessions (athlete_id, id) on delete cascade,
  unique (session_id)
);

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'movement_predictions', 'movement_events', 'athlete_movement_baselines',
    'movement_anomaly_results', 'movement_fatigue_results'
  ]
  loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('revoke all on public.%I from anon, authenticated', table_name);
    execute format('grant select on public.%I to authenticated', table_name);
    execute format(
      'create policy %I on public.%I for select to authenticated using (public.is_authorized_health_reader(athlete_id))',
      table_name || '_read_authorized', table_name
    );
  end loop;
end
$$;

alter table public.movement_model_registry enable row level security;
revoke all on public.movement_model_registry from anon, authenticated;
grant select on public.movement_model_registry to authenticated;
create policy movement_model_registry_read_active_or_admin on public.movement_model_registry
  for select to authenticated
  using (status = 'ACTIVE' or (select public.current_profile_role()) = 'ADMIN');

alter table public.movement_dataset_registry enable row level security;
revoke all on public.movement_dataset_registry from anon, authenticated;
grant select on public.movement_dataset_registry to authenticated;
create policy movement_dataset_registry_admin_read on public.movement_dataset_registry
  for select to authenticated
  using ((select public.current_profile_role()) = 'ADMIN');

create trigger movement_model_registry_touch_updated_at
  before update on public.movement_model_registry
  for each row execute function public.touch_rehab_updated_at();
create trigger movement_baselines_touch_updated_at
  before update on public.athlete_movement_baselines
  for each row execute function public.touch_rehab_updated_at();

comment on table public.movement_predictions is
  'Versioned local model exercise predictions; stores neither raw IMU windows nor model confidence.';
comment on table public.movement_anomaly_results is
  'Repeated movement deviations for review; an anomaly is not an injury or emergency diagnosis.';
comment on table public.athlete_movement_baselines is
  'Derived, placement-specific athlete movement statistics; never universal clinical norms.';
comment on table public.movement_model_registry is
  'Private model registry metadata. Artifact writes and activation are controlled outside athlete clients.';
comment on table public.movement_dataset_registry is
  'Admin-only pseudonymous dataset metadata; no direct identifiers or raw samples.';
