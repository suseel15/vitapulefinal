create extension if not exists pgcrypto with schema extensions;

create type public.app_role as enum ('ATHLETE', 'DOCTOR', 'ADMIN');
create type public.relationship_status as enum ('PENDING', 'ACTIVE', 'REVOKED');
create type public.doctor_application_status as enum ('PENDING', 'APPROVED', 'REJECTED');

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  role public.app_role not null default 'ATHLETE',
  display_name text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.athlete_profiles (
  id uuid primary key references public.profiles (id) on delete cascade,
  date_of_birth date,
  sport text,
  position text,
  rehab_stage text,
  height_cm numeric(5, 2) check (height_cm is null or height_cm between 50 and 260),
  weight_kg numeric(5, 2) check (weight_kg is null or weight_kg between 20 and 350),
  dominant_side text check (dominant_side is null or dominant_side in ('LEFT', 'RIGHT', 'AMBIDEXTROUS')),
  injury_region text,
  rehabilitation_goal text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.doctor_profiles (
  id uuid primary key references public.profiles (id) on delete cascade,
  license_id text,
  specialization text not null default '',
  organization text,
  phone text,
  verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.doctor_applications (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null unique references public.profiles (id) on delete cascade,
  email text not null,
  requested_license_id text,
  requested_specialization text,
  requested_organization text,
  requested_phone text,
  status public.doctor_application_status not null default 'PENDING',
  reviewed_at timestamptz,
  reviewed_by uuid references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.doctor_athlete_relationships (
  id uuid primary key default gen_random_uuid(),
  doctor_id uuid not null references public.doctor_profiles (id) on delete cascade,
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  status public.relationship_status not null default 'PENDING',
  granted_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint doctor_athlete_relationship_unique unique (doctor_id, athlete_id)
);

create index doctor_relationships_athlete_status_idx
  on public.doctor_athlete_relationships (athlete_id, status);
create index doctor_relationships_doctor_status_idx
  on public.doctor_athlete_relationships (doctor_id, status);

create or replace function public.current_profile_role()
returns public.app_role
language sql
stable
security definer
set search_path = ''
as $$
  select p.role
  from public.profiles as p
  where p.id = (select auth.uid())
$$;

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace function public.create_profile_for_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  assigned_role public.app_role;
  requested_type text;
begin
  assigned_role := case new.raw_app_meta_data ->> 'role'
    when 'DOCTOR' then 'DOCTOR'::public.app_role
    when 'ADMIN' then 'ADMIN'::public.app_role
    else 'ATHLETE'::public.app_role
  end;
  requested_type := upper(coalesce(new.raw_user_meta_data ->> 'requested_account_type', 'ATHLETE'));

  insert into public.profiles (id, role, display_name)
  values (new.id, assigned_role, coalesce(new.raw_user_meta_data ->> 'full_name', ''));

  if assigned_role = 'ATHLETE' then
    insert into public.athlete_profiles (id, sport)
    values (new.id, nullif(new.raw_user_meta_data ->> 'sport', ''));
  elsif assigned_role = 'DOCTOR' then
    insert into public.doctor_profiles (id, license_id, specialization)
    values (
      new.id,
      nullif(new.raw_app_meta_data ->> 'license_id', ''),
      coalesce(new.raw_app_meta_data ->> 'specialization', '')
    );
  end if;

  if requested_type = 'DOCTOR' and assigned_role <> 'DOCTOR' then
    insert into public.doctor_applications (
      profile_id,
      email,
      requested_license_id,
      requested_specialization,
      requested_organization,
      requested_phone
    )
    values (
      new.id,
      new.email,
      nullif(new.raw_user_meta_data ->> 'license_id', ''),
      nullif(new.raw_user_meta_data ->> 'specialization', ''),
      nullif(new.raw_user_meta_data ->> 'organization', ''),
      nullif(new.raw_user_meta_data ->> 'phone', '')
    );
  end if;

  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.create_profile_for_new_user();

create trigger profiles_touch_updated_at before update on public.profiles
  for each row execute function public.touch_updated_at();
create trigger athlete_profiles_touch_updated_at before update on public.athlete_profiles
  for each row execute function public.touch_updated_at();
create trigger doctor_profiles_touch_updated_at before update on public.doctor_profiles
  for each row execute function public.touch_updated_at();
create trigger doctor_applications_touch_updated_at before update on public.doctor_applications
  for each row execute function public.touch_updated_at();
create trigger doctor_relationships_touch_updated_at before update on public.doctor_athlete_relationships
  for each row execute function public.touch_updated_at();

alter table public.profiles enable row level security;
alter table public.athlete_profiles enable row level security;
alter table public.doctor_profiles enable row level security;
alter table public.doctor_applications enable row level security;
alter table public.doctor_athlete_relationships enable row level security;

revoke all on public.profiles from anon, authenticated;
revoke all on public.athlete_profiles from anon, authenticated;
revoke all on public.doctor_profiles from anon, authenticated;
revoke all on public.doctor_applications from anon, authenticated;
revoke all on public.doctor_athlete_relationships from anon, authenticated;

grant select on public.profiles to authenticated;
grant update (display_name) on public.profiles to authenticated;
grant select on public.athlete_profiles to authenticated;
grant insert (date_of_birth, sport, position, rehab_stage, height_cm, weight_kg, dominant_side, injury_region, rehabilitation_goal)
  on public.athlete_profiles to authenticated;
grant update (date_of_birth, sport, position, rehab_stage, height_cm, weight_kg, dominant_side, injury_region, rehabilitation_goal)
  on public.athlete_profiles to authenticated;
grant select on public.doctor_profiles to authenticated;
grant select on public.doctor_applications to authenticated;
grant select on public.doctor_athlete_relationships to authenticated;

create policy profiles_read_self_or_authorized_care
  on public.profiles for select to authenticated
  using (
    id = (select auth.uid())
    or (select public.current_profile_role()) = 'ADMIN'
    or (
      (select public.current_profile_role()) = 'DOCTOR'
      and exists (
        select 1 from public.doctor_athlete_relationships as r
        where r.doctor_id = (select auth.uid())
          and r.athlete_id = profiles.id
          and r.status = 'ACTIVE'
      )
    )
  );

create policy profiles_update_own_display_name
  on public.profiles for update to authenticated
  using (id = (select auth.uid()))
  with check (id = (select auth.uid()));

create policy athlete_profiles_read_self_or_authorized_care
  on public.athlete_profiles for select to authenticated
  using (
    id = (select auth.uid())
    or (select public.current_profile_role()) = 'ADMIN'
    or (
      (select public.current_profile_role()) = 'DOCTOR'
      and exists (
        select 1 from public.doctor_athlete_relationships as r
        where r.doctor_id = (select auth.uid())
          and r.athlete_id = athlete_profiles.id
          and r.status = 'ACTIVE'
      )
    )
  );

create policy athlete_profiles_update_own
  on public.athlete_profiles for update to authenticated
  using (id = (select auth.uid()) and (select public.current_profile_role()) = 'ATHLETE')
  with check (id = (select auth.uid()) and (select public.current_profile_role()) = 'ATHLETE');

create policy doctor_profiles_read_self_or_admin
  on public.doctor_profiles for select to authenticated
  using (
    id = (select auth.uid())
    or (select public.current_profile_role()) = 'ADMIN'
  );

create policy doctor_applications_read_own_or_admin
  on public.doctor_applications for select to authenticated
  using (
    profile_id = (select auth.uid())
    or (select public.current_profile_role()) = 'ADMIN'
  );

create policy doctor_relationships_read_participants
  on public.doctor_athlete_relationships for select to authenticated
  using (
    doctor_id = (select auth.uid())
    or athlete_id = (select auth.uid())
    or (select public.current_profile_role()) = 'ADMIN'
  );

create or replace function public.update_my_athlete_profile(
  p_display_name text,
  p_sport text,
  p_position text,
  p_rehabilitation_goal text
)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if (select auth.uid()) is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  update public.profiles
  set display_name = btrim(p_display_name)
  where id = (select auth.uid())
    and role = 'ATHLETE';

  if not found then
    raise exception 'Athlete profile is unavailable' using errcode = '42501';
  end if;

  update public.athlete_profiles
  set sport = nullif(btrim(p_sport), ''),
      position = nullif(btrim(p_position), ''),
      rehabilitation_goal = nullif(btrim(p_rehabilitation_goal), '')
  where id = (select auth.uid());

  if not found then
    raise exception 'Athlete details are unavailable' using errcode = '42501';
  end if;
end;
$$;

revoke all on function public.update_my_athlete_profile(text, text, text, text) from public, anon;
grant execute on function public.update_my_athlete_profile(text, text, text, text) to authenticated;

comment on table public.doctor_applications is
  'A self-registered clinician remains an unprivileged applicant until a trusted administrator verifies and provisions their DOCTOR role.';
