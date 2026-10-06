create table public.rehab_exercises (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  description text not null,
  category text not null,
  target_region text not null,
  target_muscles text[] not null default '{}',
  goal text,
  difficulty text not null default 'BEGINNER',
  instructions jsonb not null default '{}'::jsonb check (jsonb_typeof(instructions) = 'object'),
  common_mistakes text[] not null default '{}',
  contraindications text[] not null default '{}',
  default_sets integer check (default_sets is null or default_sets between 1 and 50),
  default_repetitions integer check (default_repetitions is null or default_repetitions between 1 and 200),
  default_duration_seconds integer check (default_duration_seconds is null or default_duration_seconds between 1 and 3600),
  rest_seconds integer not null default 30 check (rest_seconds between 0 and 3600),
  requires_sensor boolean not null default false,
  supported_sensor_types text[] not null default '{}',
  default_sensor_placement text check (
    default_sensor_placement is null or default_sensor_placement in
      ('THIGH', 'SHANK', 'FOREARM', 'UPPER_ARM', 'WAIST', 'CHEST', 'OTHER')
  ),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.rehab_programs (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  name text not null check (length(btrim(name)) between 1 and 160),
  description text,
  goal text,
  stage text,
  stage_order integer check (stage_order is null or stage_order >= 0),
  stages jsonb not null default '[]'::jsonb check (jsonb_typeof(stages) = 'array'),
  return_to_sport_requirements jsonb not null default '{}'::jsonb
    check (jsonb_typeof(return_to_sport_requirements) = 'object'),
  status text not null default 'ACTIVE'
    check (status in ('DRAFT', 'ACTIVE', 'COMPLETED', 'PAUSED', 'CANCELLED')),
  start_date date,
  target_end_date date,
  assigned_by uuid references public.profiles (id) on delete set null,
  source text not null default 'CLINICIAN_ASSIGNED',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (target_end_date is null or start_date is null or target_end_date >= start_date)
);

create index rehab_programs_athlete_status_idx on public.rehab_programs (athlete_id, status, updated_at desc);

create table public.rehab_program_exercises (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  program_id uuid not null references public.rehab_programs (id) on delete cascade,
  exercise_id uuid not null references public.rehab_exercises (id) on delete restrict,
  order_index integer not null check (order_index >= 0),
  sets integer not null check (sets between 1 and 50),
  repetitions integer check (repetitions is null or repetitions between 1 and 200),
  duration_seconds integer check (duration_seconds is null or duration_seconds between 1 and 3600),
  rest_seconds integer not null default 30 check (rest_seconds between 0 and 3600),
  required boolean not null default true,
  target_quality text check (
    target_quality is null or target_quality in ('GOOD', 'MODERATE', 'NEEDS_ATTENTION', 'INSUFFICIENT_DATA')
  ),
  notes text,
  source text not null default 'CLINICIAN_ASSIGNED',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (program_id, order_index),
  unique (program_id, exercise_id)
);

create index rehab_program_exercises_owner_program_idx
  on public.rehab_program_exercises (athlete_id, program_id, order_index);

create table public.rehab_sessions (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  program_id uuid references public.rehab_programs (id) on delete set null,
  exercise_id uuid not null references public.rehab_exercises (id) on delete restrict,
  source text not null check (source in ('LIVE_SENSOR', 'SIMULATION', 'MANUAL')),
  sensor_type text,
  sensor_placement text check (
    sensor_placement is null or sensor_placement in
      ('THIGH', 'SHANK', 'FOREARM', 'UPPER_ARM', 'WAIST', 'CHEST', 'OTHER')
  ),
  started_at timestamptz,
  ended_at timestamptz,
  status text not null default 'PLANNED'
    check (status in ('PLANNED', 'CALIBRATING', 'ACTIVE', 'PAUSED', 'COMPLETED', 'CANCELLED', 'ERROR')),
  sample_count integer not null default 0 check (sample_count >= 0),
  target_repetitions integer check (target_repetitions is null or target_repetitions between 1 and 200),
  completed_repetitions integer not null default 0 check (completed_repetitions between 0 and 200),
  session_duration_seconds integer check (session_duration_seconds is null or session_duration_seconds between 0 and 86400),
  movement_quality text check (
    movement_quality is null or movement_quality in ('GOOD', 'MODERATE', 'NEEDS_ATTENTION', 'INSUFFICIENT_DATA')
  ),
  stability text check (stability is null or stability in ('GOOD', 'MODERATE', 'NEEDS_ATTENTION', 'INSUFFICIENT_DATA')),
  smoothness text check (smoothness is null or smoothness in ('GOOD', 'MODERATE', 'NEEDS_ATTENTION', 'INSUFFICIENT_DATA')),
  fatigue_signal text check (fatigue_signal is null or fatigue_signal in ('LOW', 'MODERATE', 'HIGH', 'INSUFFICIENT_DATA')),
  safety_events jsonb not null default '[]'::jsonb check (jsonb_typeof(safety_events) = 'array'),
  completion_rate double precision check (completion_rate is null or completion_rate between 0 and 1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (ended_at is null or started_at is null or ended_at >= started_at),
  check (source <> 'MANUAL' or (sensor_type is null and sensor_placement is null)),
  check (source <> 'LIVE_SENSOR' or (sensor_type is not null and sensor_placement is not null))
);

create index rehab_sessions_owner_started_idx on public.rehab_sessions (athlete_id, started_at desc);
create index rehab_sessions_owner_program_idx on public.rehab_sessions (athlete_id, program_id, status);
create index rehab_sessions_owner_exercise_idx on public.rehab_sessions (athlete_id, exercise_id, ended_at desc);

create table public.rehab_repetitions (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  session_id uuid not null references public.rehab_sessions (id) on delete cascade,
  rep_number integer not null check (rep_number between 1 and 200),
  started_at timestamptz not null,
  ended_at timestamptz not null,
  duration_ms integer not null check (duration_ms > 0),
  movement_phase text,
  quality text not null check (quality in ('GOOD', 'MODERATE', 'NEEDS_ATTENTION', 'INSUFFICIENT_DATA')),
  stability text not null check (stability in ('GOOD', 'MODERATE', 'NEEDS_ATTENTION', 'INSUFFICIENT_DATA')),
  smoothness text not null check (smoothness in ('GOOD', 'MODERATE', 'NEEDS_ATTENTION', 'INSUFFICIENT_DATA')),
  range_of_motion_signal text,
  abnormality text,
  source text not null check (source in ('LIVE_SENSOR', 'SIMULATION', 'MANUAL', 'CALCULATED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (session_id, rep_number),
  check (ended_at > started_at)
);

create index rehab_repetitions_owner_session_idx on public.rehab_repetitions (athlete_id, session_id, rep_number);

create table public.movement_metrics (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  session_id uuid not null references public.rehab_sessions (id) on delete cascade,
  metric_name text not null check (length(btrim(metric_name)) between 1 and 80),
  metric_value double precision not null,
  unit text,
  source text not null check (source in ('LIVE_SENSOR', 'SIMULATION', 'MANUAL', 'CALCULATED')),
  calculation_version text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (session_id, metric_name)
);

create index movement_metrics_owner_session_idx on public.movement_metrics (athlete_id, session_id, metric_name);

create table public.movement_quality_results (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  session_id uuid not null references public.rehab_sessions (id) on delete cascade,
  movement_quality text not null check (movement_quality in ('GOOD', 'MODERATE', 'NEEDS_ATTENTION', 'INSUFFICIENT_DATA')),
  stability text not null check (stability in ('GOOD', 'MODERATE', 'NEEDS_ATTENTION', 'INSUFFICIENT_DATA')),
  smoothness text not null check (smoothness in ('GOOD', 'MODERATE', 'NEEDS_ATTENTION', 'INSUFFICIENT_DATA')),
  fatigue_signal text not null check (fatigue_signal in ('LOW', 'MODERATE', 'HIGH', 'INSUFFICIENT_DATA')),
  abnormal_events jsonb not null default '[]'::jsonb check (jsonb_typeof(abnormal_events) = 'array'),
  source text not null check (source in ('LIVE_SENSOR', 'SIMULATION', 'MANUAL', 'CALCULATED')),
  calculation_version text not null default '1',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (session_id)
);

create table public.functional_tests (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  purpose text not null,
  preparation text not null,
  instructions text[] not null default '{}',
  measurement_method text not null,
  target_duration_seconds integer check (
    target_duration_seconds is null or target_duration_seconds between 1 and 3600
  ),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.functional_test_results (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  functional_test_id uuid not null references public.functional_tests (id) on delete restrict,
  session_id uuid references public.rehab_sessions (id) on delete set null,
  duration_seconds double precision check (duration_seconds is null or duration_seconds between 0 and 3600),
  stability text not null check (stability in ('GOOD', 'MODERATE', 'NEEDS_ATTENTION', 'INSUFFICIENT_DATA')),
  movement_quality text not null check (movement_quality in ('GOOD', 'MODERATE', 'NEEDS_ATTENTION', 'INSUFFICIENT_DATA')),
  source text not null check (source in ('SIMULATION', 'MANUAL', 'LIVE_SENSOR')),
  result text not null default 'RECORDED',
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index functional_test_results_owner_test_idx
  on public.functional_test_results (athlete_id, functional_test_id, created_at desc);

create table public.readiness_assessments (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  session_id uuid references public.rehab_sessions (id) on delete set null,
  status text not null check (
    status in ('READY', 'READY_WITH_CAUTION', 'REST_RECOMMENDED', 'REVIEW_REQUIRED', 'INSUFFICIENT_DATA')
  ),
  factors jsonb not null check (jsonb_typeof(factors) = 'array'),
  recommendation text not null,
  source text not null check (source in ('RULE_BASED', 'CLINICIAN_REVIEW', 'MANUAL')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index readiness_assessments_owner_created_idx on public.readiness_assessments (athlete_id, created_at desc);

create table public.return_to_sport_assessments (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  program_id uuid references public.rehab_programs (id) on delete set null,
  stage text,
  status text not null check (
    status in ('NOT_STARTED', 'IN_PROGRESS', 'PROGRESSION_RECOMMENDED', 'READY_FOR_REVIEW', 'REVIEW_REQUIRED')
  ),
  requirements jsonb not null default '{}'::jsonb check (jsonb_typeof(requirements) = 'object'),
  completed_requirements jsonb not null default '{}'::jsonb check (jsonb_typeof(completed_requirements) = 'object'),
  outstanding_requirements jsonb not null default '[]'::jsonb check (jsonb_typeof(outstanding_requirements) = 'array'),
  clinician_review_status text not null default 'PENDING'
    check (clinician_review_status in ('PENDING', 'APPROVED', 'DECLINED')),
  source text not null check (source in ('RULE_BASED', 'CLINICIAN_REVIEW', 'MANUAL')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index return_to_sport_owner_created_idx on public.return_to_sport_assessments (athlete_id, created_at desc);

create table public.rehab_progress (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  program_id uuid references public.rehab_programs (id) on delete set null,
  stage text,
  metric_name text not null,
  metric_value double precision,
  unit text,
  source text not null,
  period_start date,
  period_end date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (period_end is null or period_start is null or period_end >= period_start)
);

create index rehab_progress_owner_period_idx on public.rehab_progress (athlete_id, period_end desc);

create table public.rehab_reports (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  report_type text not null check (
    report_type in (
      'REHAB_SESSION', 'MOVEMENT_ANALYSIS', 'EXERCISE_PROGRESS', 'FUNCTIONAL_TEST',
      'READINESS', 'RETURN_TO_SPORT', 'WEEKLY_REHAB', 'MONTHLY_REHAB'
    )
  ),
  source_ids uuid[] not null default '{}',
  data jsonb not null default '{}'::jsonb check (jsonb_typeof(data) = 'object'),
  status text not null default 'DATA_READY' check (status in ('DATA_READY', 'PENDING_RENDER', 'COMPLETED', 'FAILED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index rehab_reports_owner_created_idx on public.rehab_reports (athlete_id, created_at desc);

insert into public.rehab_exercises (
  slug, name, description, category, target_region, target_muscles, goal, difficulty, instructions,
  common_mistakes, default_sets, default_repetitions, rest_seconds, requires_sensor, default_sensor_placement
) values
  (
    'single-leg-squat', 'Single-Leg Squat',
    'A controlled single-leg strength exercise. Use a stable support if your assigned plan recommends it.',
    'STRENGTH', 'Lower body', array['quadriceps', 'gluteals'], 'Build controlled single-leg strength.',
    'INTERMEDIATE',
    '{"starting_position":"Stand near a stable support with feet hip-width apart.","execution":"Shift weight onto the working leg and sit the hips back through a comfortable range. Return with control.","breathing":"Breathe steadily; do not hold your breath."}'::jsonb,
    array['Knee collapsing inward', 'Moving beyond a comfortable range', 'Losing balance'],
    3, 8, 60, true, 'THIGH'
  ),
  (
    'single-leg-balance', 'Single-Leg Balance',
    'A timed balance task used to observe a movement signal; it does not diagnose injury.',
    'BALANCE', 'Lower body', array['ankle stabilizers', 'gluteals'], 'Practice balance control.',
    'BEGINNER',
    '{"starting_position":"Stand beside a stable support on a clear, level surface.","execution":"Stand on one leg for the comfortable assigned duration. Use support or stop if needed.","breathing":"Breathe normally."}'::jsonb,
    array['Closing your eyes without a prescribed reason', 'Continuing after pain or dizziness'],
    3, null, 30, true, 'SHANK'
  ),
  (
    'sit-to-stand', 'Sit-to-Stand',
    'A controlled chair-rise movement for general lower-body practice.',
    'STRENGTH', 'Lower body', array['quadriceps', 'gluteals'], 'Practice controlled chair transfers.',
    'BEGINNER',
    '{"starting_position":"Sit toward the front of a stable chair with feet grounded.","execution":"Lean forward slightly, stand with control, then sit back down slowly.","breathing":"Exhale while standing; breathe steadily."}'::jsonb,
    array['Letting the chair move', 'Dropping quickly into the seat'],
    2, 8, 45, false, null
  ),
  (
    'calf-raise', 'Supported Calf Raise',
    'A controlled calf raise performed beside a stable support.',
    'STRENGTH', 'Lower leg', array['calf'], 'Practice controlled ankle plantar flexion.',
    'BEGINNER',
    '{"starting_position":"Stand near a stable support with feet hip-width apart.","execution":"Rise onto the balls of the feet within a comfortable range, then lower slowly.","breathing":"Breathe normally."}'::jsonb,
    array['Bouncing through the movement', 'Using an unstable support'],
    2, 10, 45, false, null
  )
on conflict (slug) do nothing;

insert into public.functional_tests (
  slug, name, purpose, preparation, instructions, measurement_method, target_duration_seconds
) values
  (
    'balance-test', 'Balance Test',
    'Record a timed balance attempt and qualitative movement signal.',
    'Use a clear, level surface beside a stable support. Stop if you feel unsafe.',
    array['Stand on one leg for a comfortable duration.', 'Use the support when needed.', 'Stop if you feel pain, dizziness or unsafe.'],
    'Elapsed attempt duration and source-labelled qualitative movement signal; no clinical norms.',
    30
  ),
  (
    'single-leg-stability', 'Single-Leg Stability',
    'Observe a short single-leg stance movement signal.',
    'Use a clear, level surface beside a stable support. Stop if you feel unsafe.',
    array['Stand on one leg for a comfortable duration.', 'Keep your gaze on a fixed point.', 'Stop if you feel pain, dizziness or unsafe.'],
    'Elapsed attempt duration and source-labelled qualitative movement signal; no clinical norms.',
    30
  ),
  (
    'sit-to-stand', 'Sit-to-Stand',
    'Practice a controlled chair-rise task. Repetition timing is not a clinical score.',
    'Use a stable chair against a wall on a clear floor.',
    array['Rise from the chair with control.', 'Sit back down slowly.', 'Stop if uncomfortable or unsafe.'],
    'Manual completion record only; timed performance is not enabled.',
    null
  )
on conflict (slug) do nothing;

create or replace function public.touch_rehab_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'rehab_programs', 'rehab_program_exercises', 'rehab_sessions', 'rehab_repetitions',
    'movement_metrics', 'movement_quality_results', 'functional_test_results',
    'readiness_assessments', 'return_to_sport_assessments', 'rehab_progress', 'rehab_reports'
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
    execute format(
      'create trigger %I before update on public.%I for each row execute function public.touch_rehab_updated_at()',
      table_name || '_touch_updated_at',
      table_name
    );
  end loop;
end
$$;

alter table public.rehab_exercises enable row level security;
alter table public.functional_tests enable row level security;
revoke all on public.rehab_exercises, public.functional_tests from anon, authenticated;
grant select on public.rehab_exercises, public.functional_tests to authenticated;
create policy rehab_exercises_read_active on public.rehab_exercises
  for select to authenticated using (active);
create policy functional_tests_read_active on public.functional_tests
  for select to authenticated using (active);

comment on table public.rehab_sessions is
  'Stores compact session summaries, not high-frequency IMU samples. Source distinguishes live sensor, simulation and manual records.';
comment on table public.movement_quality_results is
  'Qualitative movement signals are source-labelled and are not diagnoses or full-body biomechanics.';
comment on table public.readiness_assessments is
  'Readiness is a traceable rehabilitation signal, not medical clearance.';
comment on table public.return_to_sport_assessments is
  'Progression assessments never imply clinician clearance unless an authorized review is explicitly recorded.';
