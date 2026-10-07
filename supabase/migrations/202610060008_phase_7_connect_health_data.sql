create table public.connected_devices (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  device_type text not null check (length(btrim(device_type)) between 1 and 40),
  brand text check (brand is null or length(brand) <= 80),
  model text check (model is null or length(model) <= 120),
  identifier text not null check (length(btrim(identifier)) between 1 and 120),
  connection_type text not null check (length(btrim(connection_type)) between 1 and 40),
  status text not null check (status in ('CONNECTED', 'DISCONNECTED', 'REGISTERED', 'UNAVAILABLE')),
  last_seen timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (athlete_id, identifier)
);

create table public.wearable_connections (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  provider text not null check (provider in ('HEALTH_CONNECT', 'NOISEFIT', 'DEMO')),
  device_model text check (device_model is null or length(device_model) <= 120),
  connection_status text not null check (
    connection_status in ('CONNECTED', 'SYNCED', 'DISCONNECTED', 'UNKNOWN', 'UNAVAILABLE')
  ),
  last_sync_at timestamptz,
  available_data_types text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (athlete_id, provider, device_model)
);

create table public.health_data_sync_runs (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  source text not null check (source = 'HEALTH_CONNECT'),
  started_at timestamptz not null,
  completed_at timestamptz not null,
  status text not null check (
    status in ('SYNCED', 'PARTIAL', 'NO_DATA', 'FAILED', 'PERMISSION_REQUIRED')
  ),
  records_found integer not null default 0 check (records_found between 0 and 100000),
  records_imported integer not null default 0 check (records_imported between 0 and 100000),
  records_skipped integer not null default 0 check (records_skipped between 0 and 100000),
  records_failed integer not null default 0 check (records_failed between 0 and 100000),
  error_code text check (error_code is null or length(error_code) <= 80),
  data_types text[] not null check (cardinality(data_types) between 1 and 5),
  created_at timestamptz not null default now(),
  unique (athlete_id, id),
  check (completed_at >= started_at)
);

create table public.health_data_sync_sources (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  sync_run_id uuid not null,
  source text not null check (source = 'HEALTH_CONNECT'),
  data_type text not null check (
    data_type in ('SLEEP', 'HEART_RATE', 'STEPS', 'EXERCISE', 'OXYGEN_SATURATION')
  ),
  range_start timestamptz not null,
  range_end timestamptz not null,
  records_imported integer not null default 0 check (records_imported >= 0),
  records_skipped integer not null default 0 check (records_skipped >= 0),
  created_at timestamptz not null default now(),
  constraint health_data_sync_sources_run_owner_fkey
    foreign key (athlete_id, sync_run_id)
    references public.health_data_sync_runs (athlete_id, id) on delete cascade,
  unique (athlete_id, sync_run_id, data_type),
  check (range_end > range_start)
);

create table public.unified_sleep_records (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  start_time timestamptz not null,
  end_time timestamptz not null,
  duration_minutes integer not null check (duration_minutes between 1 and 1440),
  source text not null check (source = 'HEALTH_CONNECT'),
  source_record_id text not null check (length(source_record_id) between 1 and 120),
  source_application text not null check (length(source_application) between 1 and 200),
  last_modified_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (athlete_id, source, source_record_id),
  check (end_time > start_time and end_time - start_time <= interval '24 hours')
);

create table public.unified_heart_rate_records (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  start_time timestamptz not null,
  end_time timestamptz not null,
  average_bpm double precision not null check (average_bpm between 25 and 250),
  sample_count integer not null check (sample_count between 1 and 1000000),
  measurement_type text not null check (measurement_type in ('RESTING', 'WORKOUT', 'GENERAL', 'UNKNOWN')),
  source text not null check (source = 'HEALTH_CONNECT'),
  source_record_id text not null check (length(source_record_id) between 1 and 120),
  source_application text not null check (length(source_application) between 1 and 200),
  last_modified_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (athlete_id, source, source_record_id),
  check (end_time >= start_time)
);

create table public.unified_activity_records (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  start_time timestamptz not null,
  end_time timestamptz not null,
  count bigint not null check (count between 0 and 10000000),
  source text not null check (source = 'HEALTH_CONNECT'),
  source_record_id text not null check (length(source_record_id) between 1 and 120),
  source_application text not null check (length(source_application) between 1 and 200),
  last_modified_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (athlete_id, source, source_record_id),
  check (end_time >= start_time)
);

create table public.unified_exercise_records (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  start_time timestamptz not null,
  end_time timestamptz not null,
  exercise_type integer not null check (exercise_type between 0 and 10000),
  duration_minutes integer not null check (duration_minutes between 1 and 1440),
  title text check (title is null or length(title) <= 120),
  source text not null check (source = 'HEALTH_CONNECT'),
  source_record_id text not null check (length(source_record_id) between 1 and 120),
  source_application text not null check (length(source_application) between 1 and 200),
  last_modified_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (athlete_id, source, source_record_id),
  check (end_time > start_time and end_time - start_time <= interval '24 hours')
);

create table public.unified_oxygen_saturation_records (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  start_time timestamptz not null,
  end_time timestamptz not null,
  percentage double precision not null check (percentage between 0 and 100),
  source text not null check (source = 'HEALTH_CONNECT'),
  source_record_id text not null check (length(source_record_id) between 1 and 120),
  source_application text not null check (length(source_application) between 1 and 200),
  last_modified_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (athlete_id, source, source_record_id),
  check (end_time >= start_time)
);

create table public.health_data_permissions (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  source text not null check (source = 'HEALTH_CONNECT'),
  data_type text not null check (
    data_type in ('SLEEP', 'HEART_RATE', 'STEPS', 'EXERCISE', 'OXYGEN_SATURATION')
  ),
  permission_state text not null check (permission_state in ('GRANTED', 'DENIED', 'REVOKED')),
  checked_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (athlete_id, source, data_type)
);

create table public.connect_audit_events (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  actor_id uuid not null references public.profiles (id) on delete cascade,
  event_type text not null check (length(event_type) between 1 and 80),
  resource_type text not null check (length(resource_type) between 1 and 80),
  resource_id uuid,
  created_at timestamptz not null default now(),
  check (actor_id = athlete_id)
);

create index connected_devices_owner_status_idx
  on public.connected_devices (athlete_id, status, updated_at desc);
create index wearable_connections_owner_updated_idx
  on public.wearable_connections (athlete_id, updated_at desc);
create index health_data_sync_runs_owner_started_idx
  on public.health_data_sync_runs (athlete_id, started_at desc);
create index health_data_sync_sources_run_idx
  on public.health_data_sync_sources (athlete_id, sync_run_id);
create index unified_sleep_owner_start_idx
  on public.unified_sleep_records (athlete_id, start_time desc);
create index unified_heart_rate_owner_start_idx
  on public.unified_heart_rate_records (athlete_id, start_time desc);
create index unified_activity_owner_start_idx
  on public.unified_activity_records (athlete_id, start_time desc);
create index unified_exercise_owner_start_idx
  on public.unified_exercise_records (athlete_id, start_time desc);
create index unified_oxygen_owner_start_idx
  on public.unified_oxygen_saturation_records (athlete_id, start_time desc);
create index health_data_permissions_owner_type_idx
  on public.health_data_permissions (athlete_id, data_type);
create index connect_audit_events_owner_created_idx
  on public.connect_audit_events (athlete_id, created_at desc);

create trigger connected_devices_touch_updated_at
  before update on public.connected_devices
  for each row execute function public.touch_updated_at();
create trigger wearable_connections_touch_updated_at
  before update on public.wearable_connections
  for each row execute function public.touch_updated_at();
create trigger unified_sleep_records_touch_updated_at
  before update on public.unified_sleep_records
  for each row execute function public.touch_updated_at();
create trigger unified_heart_rate_records_touch_updated_at
  before update on public.unified_heart_rate_records
  for each row execute function public.touch_updated_at();
create trigger unified_activity_records_touch_updated_at
  before update on public.unified_activity_records
  for each row execute function public.touch_updated_at();
create trigger unified_exercise_records_touch_updated_at
  before update on public.unified_exercise_records
  for each row execute function public.touch_updated_at();
create trigger unified_oxygen_saturation_records_touch_updated_at
  before update on public.unified_oxygen_saturation_records
  for each row execute function public.touch_updated_at();
create trigger health_data_permissions_touch_updated_at
  before update on public.health_data_permissions
  for each row execute function public.touch_updated_at();

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'connected_devices',
    'wearable_connections',
    'health_data_sync_runs',
    'health_data_sync_sources',
    'unified_sleep_records',
    'unified_heart_rate_records',
    'unified_activity_records',
    'unified_exercise_records',
    'unified_oxygen_saturation_records',
    'health_data_permissions',
    'connect_audit_events'
  ]
  loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('revoke all on public.%I from anon, authenticated', table_name);
    execute format('grant select, insert, update, delete on public.%I to authenticated', table_name);
  end loop;
end $$;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'connected_devices',
    'wearable_connections',
    'health_data_sync_runs',
    'health_data_sync_sources',
    'health_data_permissions'
  ]
  loop
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

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'unified_sleep_records',
    'unified_heart_rate_records',
    'unified_activity_records',
    'unified_exercise_records',
    'unified_oxygen_saturation_records'
  ]
  loop
    execute format(
      'create policy %I on public.%I for select to authenticated using (public.is_authorized_health_reader(athlete_id))',
      table_name || '_read_authorized',
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

alter table public.connect_audit_events enable row level security;
revoke all on public.connect_audit_events from anon, authenticated;
grant select, insert on public.connect_audit_events to authenticated;
create policy connect_audit_events_read_authorized
  on public.connect_audit_events
  for select to authenticated
  using (public.is_authorized_health_reader(athlete_id));
create policy connect_audit_events_insert_self
  on public.connect_audit_events
  for insert to authenticated
  with check (athlete_id = (select auth.uid()) and actor_id = (select auth.uid()));
