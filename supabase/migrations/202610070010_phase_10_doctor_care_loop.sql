alter type public.relationship_status add value if not exists 'DECLINED';

alter table public.doctor_profiles
  add column if not exists full_name text not null default '',
  add column if not exists professional_title text not null default '',
  add column if not exists license_region text not null default '',
  add column if not exists clinic_name text not null default '',
  add column if not exists clinic_address text not null default '',
  add column if not exists years_experience integer,
  add column if not exists sports_specialties text[] not null default '{}',
  add column if not exists profile_photo_path text,
  add column if not exists verification_status text not null default 'PENDING_VERIFICATION',
  add column if not exists account_status text not null default 'ACTIVE',
  add constraint doctor_profiles_years_experience_check
    check (years_experience is null or years_experience between 0 and 80),
  add constraint doctor_profiles_verification_status_check
    check (verification_status in ('PENDING_VERIFICATION', 'VERIFIED', 'REJECTED', 'SUSPENDED')),
  add constraint doctor_profiles_account_status_check
    check (account_status in ('ACTIVE', 'SUSPENDED', 'CLOSED'));

update public.doctor_profiles doctor
set full_name = profile.display_name,
    verification_status = case when doctor.verified_at is not null then 'VERIFIED' else 'PENDING_VERIFICATION' end
from public.profiles profile
where profile.id = doctor.id;

alter table public.doctor_athlete_relationships
  add column if not exists relationship_type text not null default 'OTHER',
  add column if not exists expires_at timestamptz,
  add column if not exists created_by uuid references public.profiles (id) on delete set null,
  add constraint doctor_relationship_type_check
    check (relationship_type in ('PRIMARY_DOCTOR', 'SPORTS_DOCTOR', 'PHYSIOTHERAPIST', 'REHAB_SPECIALIST', 'OTHER'));

alter table public.athlete_timeline_events
  add column if not exists actor_type text check (actor_type is null or actor_type in ('ATHLETE', 'DOCTOR', 'SYSTEM', 'AI', 'DEVICE')),
  add column if not exists actor_id uuid references public.profiles (id) on delete set null,
  add column if not exists related_entity_type text,
  add column if not exists related_entity_id uuid;

create table public.doctor_athlete_invitations (
  id uuid primary key default gen_random_uuid(),
  doctor_id uuid not null references public.doctor_profiles (id) on delete cascade,
  athlete_id uuid references public.athlete_profiles (id) on delete cascade,
  email text not null check (length(email) between 3 and 254),
  status text not null default 'PENDING'
    check (status in ('PENDING', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'CANCELLED')),
  relationship_type text not null default 'OTHER'
    check (relationship_type in ('PRIMARY_DOCTOR', 'SPORTS_DOCTOR', 'PHYSIOTHERAPIST', 'REHAB_SPECIALIST', 'OTHER')),
  message text not null default '' check (length(message) <= 500),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '30 days'),
  responded_at timestamptz,
  check (expires_at > created_at)
);
create unique index doctor_invitation_pending_email_idx
  on public.doctor_athlete_invitations (doctor_id, email) where status = 'PENDING';

create table public.clinical_audit_logs (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid not null references public.profiles (id) on delete restrict,
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  action text not null check (length(action) between 1 and 100),
  resource_type text not null check (length(resource_type) between 1 and 100),
  resource_id uuid,
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  request_id text,
  created_at timestamptz not null default now()
);

create table public.doctor_notifications (
  id uuid primary key default gen_random_uuid(),
  recipient_id uuid not null references public.profiles (id) on delete cascade,
  actor_id uuid references public.profiles (id) on delete set null,
  athlete_id uuid references public.athlete_profiles (id) on delete cascade,
  notification_type text not null,
  title text not null check (length(title) between 1 and 160),
  body text not null check (length(body) between 1 and 300),
  resource_type text,
  resource_id uuid,
  read_at timestamptz,
  created_at timestamptz not null default now()
);
create unique index doctor_notifications_resource_dedupe_idx
  on public.doctor_notifications (recipient_id, notification_type, resource_type, resource_id)
  where resource_type is not null and resource_id is not null;

create table public.care_plans (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  doctor_id uuid not null references public.doctor_profiles (id) on delete restrict,
  title text not null check (length(title) between 1 and 200),
  description text not null default '' check (length(description) <= 4000),
  status text not null default 'DRAFT'
    check (status in ('DRAFT', 'ACTIVE', 'PAUSED', 'REVIEW_REQUIRED', 'COMPLETED', 'CANCELLED', 'ARCHIVED')),
  rehab_stage text,
  start_date date,
  target_review_date date,
  end_date date,
  version integer not null default 1 check (version > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_date is null or start_date is null or end_date >= start_date)
);

create table public.care_plan_versions (
  id uuid primary key default gen_random_uuid(),
  care_plan_id uuid not null references public.care_plans (id) on delete cascade,
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  version_number integer not null check (version_number > 0),
  created_by uuid not null references public.profiles (id) on delete restrict,
  change_summary text not null check (length(change_summary) between 1 and 1000),
  snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object'),
  created_at timestamptz not null default now(),
  unique (care_plan_id, version_number)
);

create table public.care_plan_goals (
  id uuid primary key default gen_random_uuid(),
  care_plan_id uuid not null references public.care_plans (id) on delete cascade,
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  title text not null check (length(title) between 1 and 200),
  description text not null default '' check (length(description) <= 2000),
  priority text not null default 'MEDIUM' check (priority in ('LOW', 'MEDIUM', 'HIGH')),
  target_date date,
  status text not null default 'NOT_STARTED'
    check (status in ('NOT_STARTED', 'IN_PROGRESS', 'ON_TRACK', 'AT_RISK', 'ACHIEVED', 'PAUSED', 'CANCELLED')),
  measurement_type text,
  target_value numeric,
  current_value numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.care_plan_items (
  id uuid primary key default gen_random_uuid(),
  care_plan_id uuid not null references public.care_plans (id) on delete cascade,
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  assigned_by uuid not null references public.profiles (id) on delete restrict,
  item_type text not null check (item_type in (
    'EXERCISE', 'PROGRAM', 'FUNCTIONAL_TEST', 'RECOVERY_ACTION', 'FOLLOW_UP', 'DOCTOR_NOTE', 'PATIENT_INSTRUCTION', 'REVIEW'
  )),
  title text not null check (length(title) between 1 and 200),
  description text not null default '' check (length(description) <= 4000),
  linked_entity uuid,
  rehab_program_id uuid references public.rehab_programs (id) on delete set null,
  sets integer check (sets is null or sets between 1 and 50),
  repetitions integer check (repetitions is null or repetitions between 1 and 200),
  duration_seconds integer check (duration_seconds is null or duration_seconds between 1 and 86400),
  frequency text,
  rest_seconds integer check (rest_seconds is null or rest_seconds between 0 and 3600),
  intensity text,
  sensor_placement text,
  start_date date,
  end_date date,
  instructions text not null default '' check (length(instructions) <= 4000),
  restrictions text not null default '' check (length(restrictions) <= 2000),
  due_date date,
  review_date date,
  priority text not null default 'MEDIUM' check (priority in ('LOW', 'MEDIUM', 'HIGH')),
  status text not null default 'ASSIGNED'
    check (status in ('ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'OVERDUE')),
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_date is null or start_date is null or end_date >= start_date)
);

create table public.doctor_notes (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  doctor_id uuid not null references public.doctor_profiles (id) on delete restrict,
  note_type text not null check (note_type in (
    'CLINICAL_NOTE', 'REHAB_NOTE', 'MOVEMENT_NOTE', 'SAFETY_NOTE', 'FOLLOW_UP_NOTE', 'GENERAL_NOTE'
  )),
  title text not null check (length(title) between 1 and 200),
  content text not null check (length(content) between 1 and 10000),
  visibility text not null default 'INTERNAL_ONLY' check (visibility in ('INTERNAL_ONLY', 'ATHLETE_VISIBLE')),
  version integer not null default 1 check (version > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.doctor_note_versions (
  id uuid primary key default gen_random_uuid(),
  note_id uuid not null references public.doctor_notes (id) on delete cascade,
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  doctor_id uuid not null references public.doctor_profiles (id) on delete restrict,
  version_number integer not null check (version_number > 0),
  title text not null,
  content text not null,
  visibility text not null check (visibility in ('INTERNAL_ONLY', 'ATHLETE_VISIBLE')),
  edit_reason text not null check (length(edit_reason) between 1 and 1000),
  created_at timestamptz not null default now(),
  unique (note_id, version_number)
);

create table public.doctor_reviews (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  doctor_id uuid not null references public.doctor_profiles (id) on delete restrict,
  review_type text not null check (review_type in (
    'HEALTH_REPORT', 'REHAB_SESSION', 'FUNCTIONAL_TEST', 'READINESS', 'RETURN_TO_SPORT',
    'SAFETY_EVENT', 'WELLBEING', 'CARE_PLAN', 'LONGITUDINAL_INTELLIGENCE', 'GENERAL'
  )),
  subject_type text not null,
  subject_id uuid,
  status text not null default 'REVIEWED',
  summary text not null check (length(summary) between 1 and 4000),
  clinical_interpretation text not null default '' check (length(clinical_interpretation) <= 8000),
  recommendations text not null default '' check (length(recommendations) <= 8000),
  decision text,
  source_ids text[] not null default '{}',
  next_review_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.review_tasks (
  id uuid primary key default gen_random_uuid(),
  doctor_id uuid not null references public.doctor_profiles (id) on delete cascade,
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  task_type text not null,
  priority text not null default 'MEDIUM' check (priority in ('LOW', 'MEDIUM', 'HIGH', 'URGENT')),
  subject_type text not null,
  subject_id uuid,
  title text not null check (length(title) between 1 and 200),
  description text not null default '' check (length(description) <= 2000),
  due_at timestamptz,
  status text not null default 'OPEN' check (status in ('OPEN', 'IN_PROGRESS', 'COMPLETED', 'DISMISSED', 'EXPIRED')),
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  unique (doctor_id, task_type, subject_type, subject_id)
);

create table public.message_threads (
  id uuid primary key default gen_random_uuid(),
  doctor_id uuid not null references public.doctor_profiles (id) on delete cascade,
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (doctor_id, athlete_id)
);

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.message_threads (id) on delete cascade,
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  sender_id uuid not null references public.profiles (id) on delete restrict,
  message_type text not null default 'GENERAL' check (message_type in ('GENERAL', 'CARE_PLAN', 'REHAB', 'FOLLOW_UP', 'REPORT')),
  body text not null check (length(body) between 1 and 4000),
  created_at timestamptz not null default now(),
  read_at timestamptz
);

create table public.doctor_report_comments (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  report_id uuid not null references public.reports (id) on delete cascade,
  doctor_id uuid not null references public.doctor_profiles (id) on delete restrict,
  section text not null check (length(section) between 1 and 100),
  comment text not null check (length(comment) between 1 and 4000),
  created_at timestamptz not null default now()
);

create table public.doctor_dashboard_preferences (
  doctor_id uuid primary key references public.doctor_profiles (id) on delete cascade,
  preferences jsonb not null default '{}'::jsonb check (jsonb_typeof(preferences) = 'object'),
  notification_preferences jsonb not null default '{}'::jsonb check (jsonb_typeof(notification_preferences) = 'object'),
  updated_at timestamptz not null default now()
);

create or replace function public.lookup_athlete_by_email(p_email text)
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select profile.id
  from auth.users as account
  join public.profiles as profile on profile.id = account.id
  where lower(account.email) = lower(btrim(p_email))
    and profile.role = 'ATHLETE'
  limit 1
$$;
revoke all on function public.lookup_athlete_by_email(text) from public, anon, authenticated;
grant execute on function public.lookup_athlete_by_email(text) to service_role;

create or replace function public.is_verified_active_doctor(p_doctor_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.profiles profile
    join public.doctor_profiles doctor on doctor.id = profile.id
    where profile.id = p_doctor_id
      and profile.role = 'DOCTOR'
      and doctor.verification_status = 'VERIFIED'
      and doctor.account_status = 'ACTIVE'
  )
$$;
revoke all on function public.is_verified_active_doctor(uuid) from public, anon;
grant execute on function public.is_verified_active_doctor(uuid) to authenticated, service_role;

create or replace function public.search_connected_doctor_athletes(
  p_doctor_id uuid,
  p_query text,
  p_offset integer,
  p_limit integer
)
returns table (
  athlete_id uuid,
  display_name text,
  sport text,
  position text,
  rehab_stage text,
  injury_region text,
  relationship_type text,
  connected_at timestamptz,
  total_count bigint
)
language sql
stable
security definer
set search_path = ''
as $$
  with matching as (
    select
      athlete.id as athlete_id,
      profile.display_name,
      athlete.sport,
      athlete.position,
      athlete.rehab_stage,
      athlete.injury_region,
      relationship.relationship_type,
      relationship.granted_at as connected_at
    from public.doctor_athlete_relationships relationship
    join public.athlete_profiles athlete on athlete.id = relationship.athlete_id
    join public.profiles profile on profile.id = athlete.id and profile.role = 'ATHLETE'
    where relationship.doctor_id = p_doctor_id
      and relationship.status = 'ACTIVE'
      and public.is_verified_active_doctor(p_doctor_id)
      and (
        nullif(btrim(p_query), '') is null
        or profile.display_name ilike '%' || btrim(p_query) || '%'
        or athlete.sport ilike '%' || btrim(p_query) || '%'
        or athlete.position ilike '%' || btrim(p_query) || '%'
        or athlete.rehab_stage ilike '%' || btrim(p_query) || '%'
        or athlete.injury_region ilike '%' || btrim(p_query) || '%'
        or athlete.id::text ilike '%' || btrim(p_query) || '%'
        or exists (
          select 1 from auth.users account
          where account.id = athlete.id
            and account.email ilike '%' || btrim(p_query) || '%'
        )
      )
  )
  select matching.*, count(*) over ()
  from matching
  order by matching.display_name, matching.athlete_id
  offset greatest(p_offset, 0)
  limit least(greatest(p_limit, 1), 100)
$$;
revoke all on function public.search_connected_doctor_athletes(uuid, text, integer, integer) from public, anon, authenticated;
grant execute on function public.search_connected_doctor_athletes(uuid, text, integer, integer) to service_role;

create or replace function public.is_authorized_health_reader(p_athlete_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select
    p_athlete_id = (select auth.uid())
    or (select public.current_profile_role()) = 'ADMIN'
    or (
      (select public.current_profile_role()) = 'DOCTOR'
      and public.is_verified_active_doctor((select auth.uid()))
      and exists (
        select 1
        from public.doctor_athlete_relationships relationship
        where relationship.doctor_id = (select auth.uid())
          and relationship.athlete_id = p_athlete_id
          and relationship.status = 'ACTIVE'
      )
    )
$$;
revoke all on function public.is_authorized_health_reader(uuid) from public, anon;
grant execute on function public.is_authorized_health_reader(uuid) to authenticated;

create or replace function public.respond_to_doctor_invitation(
  p_invitation_id uuid,
  p_athlete_id uuid,
  p_accept boolean
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  invitation public.doctor_athlete_invitations%rowtype;
  relationship_id uuid;
  next_status text;
begin
  if (select auth.uid()) is not null and (select auth.uid()) <> p_athlete_id then
    raise exception 'Invitation recipient does not match authenticated account' using errcode = '42501';
  end if;
  if not exists (
    select 1 from public.profiles profile
    where profile.id = p_athlete_id and profile.role = 'ATHLETE'
  ) then
    raise exception 'An athlete account is required' using errcode = '42501';
  end if;
  select * into invitation
  from public.doctor_athlete_invitations
  where id = p_invitation_id and athlete_id = p_athlete_id and status = 'PENDING'
    and expires_at > now()
  for update;
  if not found then
    raise exception 'Invitation is unavailable' using errcode = 'P0002';
  end if;
  if p_accept and not public.is_verified_active_doctor(invitation.doctor_id) then
    raise exception 'Doctor account is no longer active' using errcode = '42501';
  end if;

  next_status := case when p_accept then 'ACCEPTED' else 'DECLINED' end;
  update public.doctor_athlete_invitations
  set status = next_status, responded_at = now()
  where id = invitation.id;

  if p_accept then
    insert into public.doctor_athlete_relationships (
      doctor_id, athlete_id, status, relationship_type, granted_at, created_by
    ) values (
      invitation.doctor_id, p_athlete_id, 'ACTIVE', invitation.relationship_type, now(), invitation.doctor_id
    )
    on conflict (doctor_id, athlete_id) do update
      set status = 'ACTIVE', relationship_type = excluded.relationship_type,
          granted_at = now(), revoked_at = null, created_by = excluded.created_by;
    select id into relationship_id from public.doctor_athlete_relationships
    where doctor_id = invitation.doctor_id and athlete_id = p_athlete_id;
    insert into public.doctor_notifications (
      recipient_id, actor_id, athlete_id, notification_type, title, body, resource_type, resource_id
    ) values (
      invitation.doctor_id, p_athlete_id, p_athlete_id, 'RELATIONSHIP_ACTIVATED',
      'Athlete connected', 'An athlete accepted your VitaPulse care invitation.',
      'RELATIONSHIP', relationship_id
    );
    insert into public.clinical_audit_logs (actor_id, athlete_id, action, resource_type, resource_id)
    values (p_athlete_id, p_athlete_id, 'RELATIONSHIP_ACTIVATED', 'RELATIONSHIP', relationship_id);
  else
    insert into public.clinical_audit_logs (actor_id, athlete_id, action, resource_type, resource_id)
    values (p_athlete_id, p_athlete_id, 'INVITATION_DECLINED', 'INVITATION', invitation.id);
  end if;
  return jsonb_build_object('invitation_id', invitation.id, 'status', next_status, 'relationship_id', relationship_id);
end;
$$;
revoke all on function public.respond_to_doctor_invitation(uuid, uuid, boolean) from public, anon, authenticated;
grant execute on function public.respond_to_doctor_invitation(uuid, uuid, boolean) to service_role;

drop policy if exists profiles_read_self_or_authorized_care on public.profiles;
create policy profiles_read_self_or_authorized_care
  on public.profiles for select to authenticated
  using (id = (select auth.uid()) or public.is_authorized_health_reader(id));
drop policy if exists athlete_profiles_read_self_or_authorized_care on public.athlete_profiles;
create policy athlete_profiles_read_self_or_authorized_care
  on public.athlete_profiles for select to authenticated
  using (id = (select auth.uid()) or public.is_authorized_health_reader(id));
drop policy if exists doctor_relationships_read_participants on public.doctor_athlete_relationships;
create policy doctor_relationships_read_participants
  on public.doctor_athlete_relationships for select to authenticated
  using (
    athlete_id = (select auth.uid())
    or (doctor_id = (select auth.uid()) and public.is_verified_active_doctor(doctor_id))
    or (select public.current_profile_role()) = 'ADMIN'
  );

create index doctor_invitations_email_status_idx on public.doctor_athlete_invitations (email, status, created_at desc);
create index doctor_invitations_doctor_status_idx on public.doctor_athlete_invitations (doctor_id, status, created_at desc);
create index clinical_audit_athlete_created_idx on public.clinical_audit_logs (athlete_id, created_at desc);
create index doctor_notifications_recipient_created_idx on public.doctor_notifications (recipient_id, created_at desc);
create index care_plans_athlete_status_idx on public.care_plans (athlete_id, status, updated_at desc);
create index care_plan_goals_plan_idx on public.care_plan_goals (care_plan_id, status);
create index care_plan_items_athlete_due_idx on public.care_plan_items (athlete_id, due_date, status);
create index doctor_notes_athlete_created_idx on public.doctor_notes (athlete_id, created_at desc);
create index doctor_reviews_athlete_created_idx on public.doctor_reviews (athlete_id, created_at desc);
create index review_tasks_doctor_status_due_idx on public.review_tasks (doctor_id, status, due_at);
create index message_threads_doctor_updated_idx on public.message_threads (doctor_id, updated_at desc);
create index messages_thread_created_idx on public.messages (thread_id, created_at);
create index doctor_report_comments_report_idx on public.doctor_report_comments (report_id, created_at);

create trigger care_plans_touch_updated_at before update on public.care_plans
  for each row execute function public.touch_updated_at();
create trigger care_plan_goals_touch_updated_at before update on public.care_plan_goals
  for each row execute function public.touch_updated_at();
create trigger care_plan_items_touch_updated_at before update on public.care_plan_items
  for each row execute function public.touch_updated_at();
create trigger doctor_notes_touch_updated_at before update on public.doctor_notes
  for each row execute function public.touch_updated_at();
create trigger doctor_reviews_touch_updated_at before update on public.doctor_reviews
  for each row execute function public.touch_updated_at();
create trigger message_threads_touch_updated_at before update on public.message_threads
  for each row execute function public.touch_updated_at();
create trigger doctor_dashboard_preferences_touch_updated_at before update on public.doctor_dashboard_preferences
  for each row execute function public.touch_updated_at();

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'doctor_athlete_invitations', 'clinical_audit_logs', 'doctor_notifications', 'care_plans',
    'care_plan_versions', 'care_plan_goals', 'care_plan_items', 'doctor_notes', 'doctor_note_versions',
    'doctor_reviews', 'review_tasks', 'message_threads', 'messages', 'doctor_report_comments',
    'doctor_dashboard_preferences'
  ]
  loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('revoke all on public.%I from anon, authenticated', table_name);
    execute format('grant select on public.%I to authenticated', table_name);
  end loop;
end $$;

create policy care_plans_read_authorized on public.care_plans for select to authenticated
  using (public.is_authorized_health_reader(athlete_id));
create policy care_plan_versions_read_authorized on public.care_plan_versions for select to authenticated
  using (public.is_authorized_health_reader(athlete_id));
create policy care_plan_goals_read_authorized on public.care_plan_goals for select to authenticated
  using (public.is_authorized_health_reader(athlete_id));
create policy care_plan_items_read_authorized on public.care_plan_items for select to authenticated
  using (public.is_authorized_health_reader(athlete_id));
create policy doctor_reviews_read_authorized on public.doctor_reviews for select to authenticated
  using (public.is_authorized_health_reader(athlete_id));
create policy review_tasks_read_doctor on public.review_tasks for select to authenticated
  using (doctor_id = (select auth.uid()) and public.is_verified_active_doctor(doctor_id));
create policy doctor_notes_read_private on public.doctor_notes for select to authenticated
  using (
    (doctor_id = (select auth.uid()) and public.is_verified_active_doctor(doctor_id))
    or (athlete_id = (select auth.uid()) and visibility = 'ATHLETE_VISIBLE')
  );
create policy doctor_note_versions_read_private on public.doctor_note_versions for select to authenticated
  using (doctor_id = (select auth.uid()) and public.is_verified_active_doctor(doctor_id));
create policy invitations_read_participant on public.doctor_athlete_invitations for select to authenticated
  using (
    (doctor_id = (select auth.uid()) and public.is_verified_active_doctor(doctor_id))
    or (athlete_id = (select auth.uid()) and (select public.current_profile_role()) = 'ATHLETE')
  );
create policy messages_read_participant on public.messages for select to authenticated
  using (exists (
    select 1 from public.message_threads thread
    where thread.id = messages.thread_id
      and (thread.doctor_id = (select auth.uid()) or thread.athlete_id = (select auth.uid()))
      and public.is_authorized_health_reader(thread.athlete_id)
  ));
create policy message_threads_read_participant on public.message_threads for select to authenticated
  using (
    doctor_id = (select auth.uid())
    or athlete_id = (select auth.uid())
    or (select public.current_profile_role()) = 'ADMIN'
  );
create policy notifications_read_recipient on public.doctor_notifications for select to authenticated
  using (recipient_id = (select auth.uid()));
create policy doctor_dashboard_preferences_read_self on public.doctor_dashboard_preferences for select to authenticated
  using (doctor_id = (select auth.uid()));
create policy audit_logs_read_actor on public.clinical_audit_logs for select to authenticated
  using (actor_id = (select auth.uid()) and public.is_verified_active_doctor(actor_id));
create policy doctor_report_comments_read_authorized on public.doctor_report_comments for select to authenticated
  using (public.is_authorized_health_reader(athlete_id));

comment on table public.doctor_athlete_invitations is
  'An invitation is not a clinical relationship. Only explicit athlete acceptance activates access.';
comment on table public.doctor_notes is
  'Clinician-entered annotations are separate from immutable source health data; internal notes are never visible to athletes.';
comment on table public.clinical_audit_logs is
  'Auditable log of doctor and athlete care-loop actions; metadata must not include raw clinical source payloads.';
