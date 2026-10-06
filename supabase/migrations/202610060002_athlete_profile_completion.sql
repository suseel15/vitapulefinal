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
    insert into public.athlete_profiles (
      id,
      date_of_birth,
      sport,
      position,
      height_cm,
      weight_kg,
      dominant_side,
      injury_region,
      rehabilitation_goal
    )
    values (
      new.id,
      nullif(new.raw_user_meta_data ->> 'date_of_birth', '')::date,
      nullif(new.raw_user_meta_data ->> 'sport', ''),
      nullif(new.raw_user_meta_data ->> 'position', ''),
      nullif(new.raw_user_meta_data ->> 'height_cm', '')::numeric,
      nullif(new.raw_user_meta_data ->> 'weight_kg', '')::numeric,
      nullif(new.raw_user_meta_data ->> 'dominant_side', ''),
      nullif(new.raw_user_meta_data ->> 'injury_region', ''),
      nullif(new.raw_user_meta_data ->> 'rehabilitation_goal', '')
    );
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

drop function if exists public.update_my_athlete_profile(text, text, text, text);

create function public.update_my_athlete_profile(
  p_display_name text,
  p_sport text,
  p_position text,
  p_rehabilitation_goal text,
  p_date_of_birth date,
  p_height_cm numeric,
  p_weight_kg numeric,
  p_dominant_side text,
  p_injury_region text
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
  set date_of_birth = p_date_of_birth,
      sport = nullif(btrim(p_sport), ''),
      position = nullif(btrim(p_position), ''),
      height_cm = p_height_cm,
      weight_kg = p_weight_kg,
      dominant_side = nullif(btrim(p_dominant_side), ''),
      injury_region = nullif(btrim(p_injury_region), ''),
      rehabilitation_goal = nullif(btrim(p_rehabilitation_goal), '')
  where id = (select auth.uid());

  if not found then
    raise exception 'Athlete details are unavailable' using errcode = '42501';
  end if;
end;
$$;

revoke all on function public.update_my_athlete_profile(
  text, text, text, text, date, numeric, numeric, text, text
) from public, anon;
grant execute on function public.update_my_athlete_profile(
  text, text, text, text, date, numeric, numeric, text, text
) to authenticated;
