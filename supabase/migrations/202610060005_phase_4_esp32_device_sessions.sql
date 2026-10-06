create table public.movement_devices (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  device_identifier text not null check (length(btrim(device_identifier)) between 1 and 80),
  device_type text not null check (device_type = 'ESP32'),
  sensor_type text not null check (sensor_type = 'MPU6050'),
  transport text not null check (transport = 'HTTP'),
  ip_address inet not null check (ip_address = inet '192.168.4.1'),
  firmware_protocol text not null check (firmware_protocol = 'VITAPULSE_STAGE_1_HTTP'),
  is_active boolean not null default true,
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (athlete_id, device_identifier),
  unique (athlete_id, id)
);

create index movement_devices_athlete_active_idx
  on public.movement_devices (athlete_id, is_active, created_at desc);

alter table public.rehab_sessions
  add column device_id uuid,
  add column client_session_id uuid,
  add column successful_requests integer not null default 0
    check (successful_requests between 0 and 1000000),
  add column failed_requests integer not null default 0
    check (failed_requests between 0 and 1000000),
  add column invalid_samples integer not null default 0
    check (invalid_samples between 0 and 1000000),
  add column measured_rate_hz double precision
    check (measured_rate_hz is null or measured_rate_hz between 0 and 100),
  add column average_latency_ms double precision
    check (average_latency_ms is null or average_latency_ms between 0 and 60000);

alter table public.rehab_sessions
  add constraint rehab_sessions_device_owner_fkey
    foreign key (athlete_id, device_id)
    references public.movement_devices (athlete_id, id)
    on delete restrict,
  add constraint rehab_sessions_live_requires_device_check
    check (source <> 'LIVE_SENSOR' or device_id is not null) not valid;

create unique index rehab_sessions_client_session_id_idx
  on public.rehab_sessions (athlete_id, client_session_id)
  where client_session_id is not null;

create index rehab_sessions_device_idx on public.rehab_sessions (athlete_id, device_id, started_at desc);

alter table public.movement_devices enable row level security;
revoke all on public.movement_devices from anon, authenticated;
grant select on public.movement_devices to authenticated;
create policy movement_devices_read_authorized on public.movement_devices
  for select to authenticated using (public.is_authorized_health_reader(athlete_id));

create trigger movement_devices_touch_updated_at
  before update on public.movement_devices
  for each row execute function public.touch_rehab_updated_at();

comment on table public.movement_devices is
  'Athlete-owned ESP32/MPU6050 descriptors. Wi-Fi passwords and raw sensor readings are never persisted.';
comment on column public.movement_devices.last_seen_at is
  'Time the backend last accepted a summary from a session with locally validated sensor readings.';
comment on column public.rehab_sessions.device_id is
  'Athlete-owned hardware descriptor for a LIVE_SENSOR session; raw IMU samples remain local to the Android device.';
