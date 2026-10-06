create table public.medical_reports (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  original_filename text not null check (length(original_filename) between 1 and 255),
  mime_type text not null check (mime_type in ('application/pdf', 'image/jpeg', 'image/png')),
  file_size bigint not null check (file_size between 1 and 26214400),
  file_sha256 text not null check (file_sha256 ~ '^[0-9a-f]{64}$'),
  consent_purpose text not null check (consent_purpose = 'HEALTH_REPORT_PROCESSING'),
  consented_at timestamptz not null,
  storage_bucket text not null default 'medical-reports',
  storage_path text not null unique,
  report_date date,
  uploaded_at timestamptz not null default now(),
  processed_at timestamptz,
  processing_status text not null default 'UPLOADED'
    check (processing_status in ('UPLOADED', 'VALIDATING', 'OCR_PROCESSING', 'EXTRACTING', 'VALIDATING_DATA', 'ANALYZING', 'COMPLETED', 'FAILED')),
  ocr_status text not null default 'PENDING'
    check (ocr_status in ('PENDING', 'PROCESSING', 'COMPLETED', 'LOW_QUALITY', 'FAILED')),
  extraction_status text not null default 'PENDING'
    check (extraction_status in ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
  analysis_status text not null default 'PENDING'
    check (analysis_status in ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
  source_type text not null default 'USER_UPLOAD' check (source_type = 'USER_UPLOAD'),
  ocr_quality text check (ocr_quality is null or ocr_quality in ('GOOD', 'LOW_QUALITY', 'TEXT_LAYER')),
  ocr_confidence double precision check (ocr_confidence is null or ocr_confidence between 0 and 1),
  pages_processed integer check (pages_processed is null or pages_processed >= 0),
  text_length integer check (text_length is null or text_length >= 0),
  ocr_engine text,
  ocr_version text,
  data_quality_warnings jsonb not null default '[]'::jsonb check (jsonb_typeof(data_quality_warnings) = 'array'),
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (athlete_id, file_sha256)
);

create index medical_reports_athlete_uploaded_idx on public.medical_reports (athlete_id, uploaded_at desc);
create index medical_reports_athlete_status_idx on public.medical_reports (athlete_id, processing_status);

create table public.medical_report_pages (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  medical_report_id uuid not null references public.medical_reports (id) on delete cascade,
  page_number integer not null check (page_number > 0),
  extracted_text text not null default '',
  extraction_method text not null,
  created_at timestamptz not null default now(),
  unique (medical_report_id, page_number)
);

create index medical_report_pages_owner_report_idx on public.medical_report_pages (athlete_id, medical_report_id);

create table public.medical_report_findings (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  medical_report_id uuid not null references public.medical_reports (id) on delete cascade,
  finding_type text not null,
  description text not null,
  source_text text not null,
  source_page integer not null check (source_page > 0),
  source_type text not null check (source_type in ('DIRECTLY_REPORTED', 'CALCULATED', 'AI_INTERPRETED', 'USER_ENTERED')),
  confidence double precision check (confidence is null or confidence between 0 and 1),
  created_at timestamptz not null default now()
);

create index medical_report_findings_owner_created_idx on public.medical_report_findings (athlete_id, created_at desc);

create table public.biomarkers (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  canonical_name text unique,
  standard_code text,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.biomarker_reference_ranges (
  id uuid primary key default gen_random_uuid(),
  biomarker_id uuid not null references public.biomarkers (id) on delete cascade,
  source_name text not null,
  unit text not null,
  reference_low numeric,
  reference_high numeric,
  age_min_years numeric,
  age_max_years numeric,
  sex_at_birth text,
  effective_date date,
  created_at timestamptz not null default now(),
  check (reference_low is null or reference_high is null or reference_low <= reference_high)
);

create table public.biomarker_measurements (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  medical_report_id uuid references public.medical_reports (id) on delete cascade,
  biomarker_id uuid references public.biomarkers (id) on delete set null,
  biomarker_name text not null,
  canonical_name text,
  standard_code text,
  value_numeric numeric,
  value_text text,
  unit text,
  reference_low numeric,
  reference_high numeric,
  abnormal_flag text check (abnormal_flag is null or abnormal_flag in ('HIGH', 'LOW', 'ABNORMAL')),
  collection_date date,
  source_page integer check (source_page is null or source_page > 0),
  source_text text,
  source_type text not null check (source_type in ('DIRECTLY_REPORTED', 'CALCULATED', 'AI_INTERPRETED', 'USER_ENTERED')),
  extraction_method text,
  confidence double precision check (confidence is null or confidence between 0 and 1),
  created_at timestamptz not null default now(),
  check (value_numeric is not null or value_text is not null),
  check (reference_low is null or reference_high is null or reference_low <= reference_high)
);

create index biomarker_measurements_owner_name_date_idx
  on public.biomarker_measurements (athlete_id, coalesce(canonical_name, biomarker_name), collection_date desc);
create index biomarker_measurements_report_idx on public.biomarker_measurements (medical_report_id);

create table public.body_regions (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  system text not null,
  anatomical_identifier text not null unique,
  display_order integer not null default 0,
  created_at timestamptz not null default now()
);

insert into public.body_regions (name, system, anatomical_identifier, display_order) values
  ('Head', 'Nervous', 'head', 10),
  ('Neck', 'Nervous', 'neck', 20),
  ('Chest', 'Cardiovascular', 'chest-front', 30),
  ('Heart', 'Cardiovascular', 'heart', 40),
  ('Lungs', 'Respiratory', 'lungs', 50),
  ('Abdomen', 'Digestive', 'abdomen-front', 60),
  ('Liver', 'Digestive', 'liver', 70),
  ('Kidneys', 'Urinary', 'kidneys-back', 80),
  ('Pelvis', 'Musculoskeletal', 'pelvis', 90),
  ('Left shoulder', 'Musculoskeletal', 'left-shoulder', 100),
  ('Right shoulder', 'Musculoskeletal', 'right-shoulder', 110),
  ('Left arm', 'Musculoskeletal', 'left-arm', 120),
  ('Right arm', 'Musculoskeletal', 'right-arm', 130),
  ('Back', 'Musculoskeletal', 'back', 140),
  ('Left hip', 'Musculoskeletal', 'left-hip', 150),
  ('Right hip', 'Musculoskeletal', 'right-hip', 160),
  ('Left leg', 'Musculoskeletal', 'left-leg', 170),
  ('Right leg', 'Musculoskeletal', 'right-leg', 180),
  ('Skin', 'Skin', 'skin', 190);

create table public.body_region_findings (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  body_region_id uuid not null references public.body_regions (id),
  medical_report_id uuid references public.medical_reports (id) on delete cascade,
  biomarker_measurement_id uuid references public.biomarker_measurements (id) on delete set null,
  finding_type text not null,
  severity text check (severity is null or severity in ('INFORMATIONAL', 'REVIEW_RECOMMENDED')),
  description text not null,
  source_type text not null check (source_type in ('DIRECTLY_REPORTED', 'CALCULATED', 'AI_INTERPRETED', 'USER_ENTERED')),
  created_at timestamptz not null default now()
);

create index body_region_findings_owner_created_idx on public.body_region_findings (athlete_id, created_at desc);

create table public.health_intelligence_items (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  item_type text not null,
  category text not null,
  title text not null,
  explanation text not null,
  status text not null check (status in ('OBSERVED', 'CALCULATED', 'AI_INTERPRETED', 'REVIEW_REQUIRED', 'DATA_QUALITY_ISSUE')),
  source_ids uuid[] not null default '{}',
  observed_at date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index health_intelligence_owner_created_idx on public.health_intelligence_items (athlete_id, created_at desc);

create table public.health_intelligence_sources (
  id uuid primary key default gen_random_uuid(),
  source_title text not null,
  source_type text not null,
  source_identifier text,
  source_url text,
  retrieved_at timestamptz,
  relevance text,
  claim_supported text,
  created_at timestamptz not null default now()
);

create table public.health_intelligence_item_sources (
  health_intelligence_item_id uuid not null references public.health_intelligence_items (id) on delete cascade,
  health_intelligence_source_id uuid not null references public.health_intelligence_sources (id) on delete restrict,
  primary key (health_intelligence_item_id, health_intelligence_source_id)
);

create table public.nutrition_profiles (
  athlete_id uuid primary key references public.athlete_profiles (id) on delete cascade,
  goal text not null default 'GENERAL_SPORTS_NUTRITION'
    check (goal in ('RECOVERY', 'PERFORMANCE', 'STRENGTH', 'ENDURANCE', 'BODY_COMPOSITION', 'GENERAL_SPORTS_NUTRITION')),
  hydration_goal_ml integer check (hydration_goal_ml is null or hydration_goal_ml between 0 and 15000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.nutrition_entries (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  entry_date date not null,
  entry_type text not null check (entry_type in ('MEAL', 'HYDRATION', 'MICRONUTRIENT')),
  name text not null check (length(name) between 1 and 160),
  calories numeric check (calories is null or calories between 0 and 10000),
  protein_g numeric check (protein_g is null or protein_g between 0 and 1000),
  carbohydrates_g numeric check (carbohydrates_g is null or carbohydrates_g between 0 and 1000),
  fat_g numeric check (fat_g is null or fat_g between 0 and 1000),
  fiber_g numeric check (fiber_g is null or fiber_g between 0 and 1000),
  hydration_ml integer check (hydration_ml is null or hydration_ml between 0 and 15000),
  micronutrients jsonb not null default '{}'::jsonb check (jsonb_typeof(micronutrients) = 'object'),
  source_type text not null default 'USER_ENTERED' check (source_type = 'USER_ENTERED'),
  created_at timestamptz not null default now()
);

create index nutrition_entries_owner_date_idx on public.nutrition_entries (athlete_id, entry_date desc);

create table public.medications (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  name text not null check (length(name) between 1 and 200),
  dose text,
  frequency text,
  start_date date,
  end_date date,
  reason text,
  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'PAUSED', 'COMPLETED')),
  source_type text not null default 'USER_ENTERED' check (source_type in ('USER_ENTERED', 'MEDICAL_REPORT', 'DOCTOR_ENTERED')),
  medical_report_id uuid references public.medical_reports (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_date is null or start_date is null or end_date >= start_date)
);

create index medications_owner_status_idx on public.medications (athlete_id, status, start_date desc);

create table public.anti_doping_sources (
  id uuid primary key default gen_random_uuid(),
  source_name text not null,
  source_version text,
  effective_date date,
  retrieved_at timestamptz,
  verified boolean not null default false,
  created_at timestamptz not null default now(),
  unique (source_name, source_version)
);

create table public.anti_doping_reviews (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  medication_id uuid references public.medications (id) on delete set null,
  substance_name text,
  status text not null check (status in ('NO_KNOWN_MATCH', 'REVIEW_REQUIRED', 'POTENTIAL_PROHIBITED', 'TUE_REVIEW', 'INSUFFICIENT_INFORMATION')),
  review_note text,
  source_id uuid references public.anti_doping_sources (id) on delete set null,
  created_at timestamptz not null default now()
);

create index anti_doping_reviews_owner_created_idx on public.anti_doping_reviews (athlete_id, created_at desc);

create table public.skin_screenings (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  result text not null check (result in ('NO_CONCERNING_VISUAL_PATTERN', 'REVIEW_RECOMMENDED', 'UNABLE_TO_ASSESS_RELIABLY', 'POTENTIALLY_CONCERNING_VISUAL_PATTERN')),
  quality_status text not null check (quality_status in ('GOOD', 'INSUFFICIENT', 'NOT_ASSESSED')),
  consent_purpose text not null,
  consented_at timestamptz not null,
  source_type text not null check (source_type in ('CAMERA', 'GALLERY')),
  storage_bucket text,
  storage_path text,
  retained_until timestamptz,
  created_at timestamptz not null default now(),
  check ((storage_bucket is null) = (storage_path is null))
);

create index skin_screenings_owner_created_idx on public.skin_screenings (athlete_id, created_at desc);

create table public.health_reports (
  id uuid primary key default gen_random_uuid(),
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  report_type text not null check (report_type in ('MEDICAL_REPORT_ANALYSIS', 'BIOMARKER_REPORT', 'BODY_MAP_REPORT', 'HEALTH_INTELLIGENCE_REPORT', 'NUTRITION_REPORT', 'MEDICATION_REPORT', 'ANTI_DOPING_REVIEW', 'SKIN_SCREENING_REPORT', 'FULL_HEALTH_REPORT')),
  source_ids uuid[] not null default '{}',
  status text not null default 'DRAFT' check (status in ('DRAFT', 'READY', 'PROCESSING', 'COMPLETED', 'FAILED')),
  summary text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index health_reports_owner_created_idx on public.health_reports (athlete_id, created_at desc);

create or replace function public.prune_health_report_source()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  deleted_id uuid := (to_jsonb(old) ->> 'id')::uuid;
  owner_id uuid := (to_jsonb(old) ->> 'athlete_id')::uuid;
  pruned_report record;
begin
  for pruned_report in
    select id, array_remove(source_ids, deleted_id) as source_ids
    from public.health_reports
    where athlete_id = owner_id
      and deleted_id = any(source_ids)
    for update
  loop
    if cardinality(pruned_report.source_ids) = 0 then
      delete from public.health_reports where id = pruned_report.id;
    else
      update public.health_reports
      set source_ids = pruned_report.source_ids,
          status = 'DRAFT',
          summary = null,
          updated_at = now()
      where id = pruned_report.id;
    end if;
  end loop;

  return old;
end
$$;

create trigger medical_reports_prune_health_report_sources
  after delete on public.medical_reports
  for each row execute function public.prune_health_report_source();
create trigger biomarker_measurements_prune_health_report_sources
  after delete on public.biomarker_measurements
  for each row execute function public.prune_health_report_source();
create trigger body_region_findings_prune_health_report_sources
  after delete on public.body_region_findings
  for each row execute function public.prune_health_report_source();
create trigger health_intelligence_items_prune_health_report_sources
  after delete on public.health_intelligence_items
  for each row execute function public.prune_health_report_source();
create trigger nutrition_entries_prune_health_report_sources
  after delete on public.nutrition_entries
  for each row execute function public.prune_health_report_source();
create trigger medications_prune_health_report_sources
  after delete on public.medications
  for each row execute function public.prune_health_report_source();
create trigger anti_doping_reviews_prune_health_report_sources
  after delete on public.anti_doping_reviews
  for each row execute function public.prune_health_report_source();
create trigger skin_screenings_prune_health_report_sources
  after delete on public.skin_screenings
  for each row execute function public.prune_health_report_source();

create table public.health_audit_events (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid not null references public.profiles (id) on delete cascade,
  athlete_id uuid not null references public.athlete_profiles (id) on delete cascade,
  event_type text not null,
  resource_type text not null,
  resource_id uuid,
  created_at timestamptz not null default now()
);

create index health_audit_events_owner_created_idx on public.health_audit_events (athlete_id, created_at desc);

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
      and exists (
        select 1 from public.doctor_athlete_relationships as relationship
        where relationship.doctor_id = (select auth.uid())
          and relationship.athlete_id = p_athlete_id
          and relationship.status = 'ACTIVE'
      )
    )
$$;

revoke all on function public.is_authorized_health_reader(uuid) from public, anon;
grant execute on function public.is_authorized_health_reader(uuid) to authenticated;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'medical_reports', 'medical_report_pages', 'medical_report_findings',
    'biomarker_measurements', 'body_region_findings', 'health_intelligence_items',
    'nutrition_profiles', 'nutrition_entries', 'medications', 'anti_doping_reviews',
    'skin_screenings', 'health_reports', 'health_audit_events'
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
end
$$;

alter table public.biomarkers enable row level security;
alter table public.biomarker_reference_ranges enable row level security;
alter table public.body_regions enable row level security;
alter table public.health_intelligence_sources enable row level security;
alter table public.health_intelligence_item_sources enable row level security;
alter table public.anti_doping_sources enable row level security;

revoke all on public.biomarkers, public.biomarker_reference_ranges, public.body_regions,
  public.health_intelligence_sources, public.health_intelligence_item_sources,
  public.anti_doping_sources from anon, authenticated;

grant select on public.biomarkers, public.biomarker_reference_ranges,
  public.body_regions, public.health_intelligence_sources,
  public.health_intelligence_item_sources, public.anti_doping_sources to authenticated;

create policy biomarkers_read_authenticated on public.biomarkers
  for select to authenticated using (true);
create policy reference_ranges_read_authenticated on public.biomarker_reference_ranges
  for select to authenticated using (true);
create policy body_regions_read_authenticated on public.body_regions
  for select to authenticated using (true);
create policy anti_doping_sources_read_authenticated on public.anti_doping_sources
  for select to authenticated using (true);
create policy intelligence_sources_read_authorized on public.health_intelligence_sources
  for select to authenticated using (
    exists (
      select 1
      from public.health_intelligence_item_sources as item_source
      join public.health_intelligence_items as item
        on item.id = item_source.health_intelligence_item_id
      where item_source.health_intelligence_source_id = health_intelligence_sources.id
        and public.is_authorized_health_reader(item.athlete_id)
    )
  );
create policy intelligence_item_sources_read_authorized on public.health_intelligence_item_sources
  for select to authenticated using (
    exists (
      select 1 from public.health_intelligence_items as item
      where item.id = health_intelligence_item_sources.health_intelligence_item_id
        and public.is_authorized_health_reader(item.athlete_id)
    )
  );

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'medical-reports',
  'medical-reports',
  false,
  26214400,
  array['application/pdf', 'image/jpeg', 'image/png']::text[]
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

create policy medical_reports_storage_read_authorized
  on storage.objects for select to authenticated
  using (
    bucket_id = 'medical-reports'
    and (
      (storage.foldername(name))[1] = (select auth.uid())::text
      or (select public.current_profile_role()) = 'ADMIN'
      or (
        (select public.current_profile_role()) = 'DOCTOR'
        and exists (
          select 1 from public.doctor_athlete_relationships as relationship
          where relationship.doctor_id = (select auth.uid())
            and relationship.athlete_id = ((storage.foldername(name))[1])::uuid
            and relationship.status = 'ACTIVE'
        )
      )
    )
  );

create trigger medical_reports_touch_updated_at before update on public.medical_reports
  for each row execute function public.touch_updated_at();
create trigger biomarkers_touch_updated_at before update on public.biomarkers
  for each row execute function public.touch_updated_at();
create trigger health_intelligence_items_touch_updated_at before update on public.health_intelligence_items
  for each row execute function public.touch_updated_at();
create trigger nutrition_profiles_touch_updated_at before update on public.nutrition_profiles
  for each row execute function public.touch_updated_at();
create trigger medications_touch_updated_at before update on public.medications
  for each row execute function public.touch_updated_at();
create trigger health_reports_touch_updated_at before update on public.health_reports
  for each row execute function public.touch_updated_at();

comment on table public.medical_report_pages is
  'Contains sensitive extracted text, always subject to athlete ownership and active clinician-sharing RLS.';
comment on table public.biomarker_measurements is
  'Raw extracted values retain original units, source text, page, source report and provenance. Standard codes may be null.';
comment on table public.body_region_findings is
  'A linked biomarker or body region is informational context and does not establish organ damage or diagnosis.';
comment on table public.health_intelligence_sources is
  'Only factual externally verified evidence sources belong here; empty means evidence is unavailable.';
comment on table public.skin_screenings is
  'Screening signals are non-diagnostic. Images are not retained unless a future explicit-consent workflow is added.';
comment on table public.health_audit_events is
  'Records sensitive health-data access/actions without report contents or extracted text.';
