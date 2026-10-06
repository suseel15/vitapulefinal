# Supabase setup and data security

For the existing Supabase project, the initial SQL was already run in the SQL Editor; do not run that file again. Check the migration history and apply only pending files, in filename order: `202610060002_athlete_profile_completion.sql`, `202610060003_phase_2_health_foundation.sql`, then `202610060004_phase_3_rehabilitation.sql`. Each later file should be applied once, only if it has not already run. Migration `003` adds Phase 2 health tables and policies; migration `004` adds Rehab program, session, movement, functional-test, readiness, return-to-sport and report tables with owner-scoped policies. For a new project, apply all migration files once in filename order.

The signup trigger creates a profile and an athlete profile by default. A doctor account remains an application until a trusted administrator provisions its role using server-controlled Supabase `app_metadata`. A user-editable `user_metadata` role is never used to grant access.

RLS is enabled on health records. Athletes can read their own data; doctors can read only health records and private report objects for an active athlete relationship; admins can read health records. Authenticated clients receive no health-table write grants. Health mutations are performed by the backend service role only after the user's bearer token and athlete role are verified and all reads/writes are filtered to that athlete.

The audit-event table is read-only to authenticated clients. Backend service-role writes record selected report and health actions. Report files are stored in a private bucket; upload is backend-mediated, and the backend issues short-lived source links only after checking the owner's report record. Keep the Supabase service-role key exclusively in the protected backend environment.

No fake health records, connected devices or demo accounts are seeded. Configure email authentication and set the site's local/deployed URL in Supabase Auth so confirmation and reset links return to the VitaPulse origin.
