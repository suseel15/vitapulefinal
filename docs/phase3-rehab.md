# Phase 3 Rehabilitation

Phase 3 adds the athlete-facing rehabilitation flow to the existing responsive web app and FastAPI/Supabase backend. It does not create an Android Studio project; Android remains deferred until the web flows are reviewed.

## Included

- Responsive Rehab hub and routes for today's plan, programs, exercises, sessions, movement, progress, recovery, functional tests, readiness, return-to-sport, history and report data.
- Athlete-authenticated APIs under `/api/v1/rehab` with athlete ownership checks and server-mediated writes.
- Session lifecycle validation (`PLANNED` → `CALIBRATING` → `ACTIVE` / `PAUSED` → `COMPLETED`, or `CANCELLED` / `ERROR`), duplicate-safe repetition/metric writes and compact movement summaries.
- Deterministic, visibly labelled simulation samples; manual sessions without sensor claims; movement repetition and qualitative signal summaries; local offline session persistence and retry.
- Functional test attempts with a stated method, result source and explicit lack of clinical norms.
- Readiness check-ins and return-to-sport requirement evaluation, both rule-based and explicitly not medical clearance.
- Supabase schema, indexes and owner-scoped RLS in `202610060004_phase_3_rehabilitation.sql`.

## Setup and migration

Use the same web and backend setup in the root [README](../README.md). Migration `004` depends on the identity/profile and Phase 2 Health migrations. The original migration was already run in the existing Supabase SQL Editor: do not rerun it. Check migration history and apply only missing later migrations, in filename order, once each. Do not run `202610060004_phase_3_rehabilitation.sql` if it has already been applied. Local tests do not connect to, inspect or modify the live Supabase project.

## Session and data behavior

- Browser routes include `#rehab/today`, `#rehab/program`, `#rehab/exercises/{id}`, `#rehab/session/{id}`, `#rehab/session/{id}/result`, `#rehab/movement`, `#rehab/progress`, `#rehab/recovery`, `#rehab/functional-tests`, `#rehab/readiness`, `#rehab/return-to-sport`, `#rehab/history` and `#rehab/reports`.
- Simulation is a development source, not a physical sensor. Manual mode records activity without samples or placement claims. `LIVE_SENSOR` is rejected until the Phase 4 transport and device protocol exist.
- Raw samples remain in short-lived browser session memory; persisted local records and API payloads retain compact summaries and repetitions instead of sample arrays.
- If the connection drops, a completed session is kept in user-scoped browser storage and retried when online or when the athlete requests sync. API saves use unique session/repetition and session/metric keys so retries can safely upsert details.
- A session movement warning is a basic signal threshold, not a danger detector. Athletes should stop if they feel pain or unsafe; no emergency monitoring is provided.
- Functional attempts only record elapsed time and source. Stability and movement quality remain `INSUFFICIENT_DATA` without a validated sensor method.
- Readiness and return-to-sport outputs are explainable rule-based status suggestions. Return-to-sport requirements can be configured on an active program with `minimum_completed_sessions`, `required_exercise_ids`, `require_functional_test`, `required_functional_test_ids` and `require_athlete_report`. Malformed program requirements produce a server error rather than being silently ignored.

## Explicit limitations

- There is no clinician-facing program assignment/authoring or review workflow yet. Programs and assignments must be provisioned through an authorized backend/database workflow.
- ESP32 polling/WebSocket classes are transport contracts only. No live sensor, calibration protocol, firmware, or Health Connect integration is connected.
- Movement labels are categorical and signal-specific; they do not estimate exact joint angles, diagnose injuries, score full-body biomechanics, or determine medical readiness.
- The safety monitor only flags a simple signal threshold and does not provide clinical or emergency safety coverage.
- Recovery does not yet connect sleep, wearable or clinical recovery data. Unavailable values are shown as unavailable.
- Reports expose structured data types only; PDF rendering and narrative generation are not enabled.
- Local demo data is synthetic, labelled, browser-only and never sent to the backend.

## Verification

Run the frontend checks from the project root with `npm test` and `npm run build`. Run the backend tests from `backend/` with `pytest`. These checks do not validate the live Supabase migration, real user authentication, a production deployment, clinical protocols or physical hardware.
