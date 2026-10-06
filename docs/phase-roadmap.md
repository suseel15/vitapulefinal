# VitaPulse phase roadmap

## Current: complete and deploy the web-first Phase 6 athlete wellbeing hub

Responsive web shell, local development demos, Supabase Auth boundary, role-aware athlete/doctor navigation, optional athlete profile details, and backend Health APIs with PostgreSQL RLS. Phase 2 adds consented private report uploads, OCRmyPDF integration, traceable biomarker extraction, body-map notes, nutrition and medication logs, and explicit unavailable states. Phase 3 adds athlete Rehab screens and APIs, simulation/manual sessions, categorical movement and fatigue signals, functional test records, progress/readiness and rule-based return-to-sport requirements. Phase 6 brings private, source-labelled check-ins, sleep, recovery context, trends, history, and weekly summaries into the web hub; browser camera capture remains off. See [Phase 2 Health](./phase2-health.md), [Phase 3 Rehabilitation](./phase3-rehab.md), and [Android client](./android.md).

Phase 4 added a separate Kotlin/Compose Android client for the ESP32-001 + MPU6050 HTTP access point. Phase 5 adds a matching versioned Kotlin/Python movement-feature pipeline, local deterministic repetition and quality analysis, optional safe JSON-forest inference, pseudonymous manual-label dataset export, owner-scoped derived movement APIs, model/dataset registry groundwork, and personal baselines. The later Android Studio phase can wrap the deployed web experience and add native-only capabilities, including ESP32 access and optional on-device camera observations. No validated movement model is active.

Next priorities:

1. Run the web test suite and production build; resolve all failures and review the responsive Wellbeing experience.
2. Configure the public Supabase and API origins safely, deploy the static `dist/` output to Vercel, and verify sign-in, CORS, and authenticated wellbeing flows at the deployed origin.
3. Apply only pending migrations in filename order; validate migration 007 before deployment and smoke-test owner-scoped wellbeing APIs.
4. After the web deployment is accepted, use its Vercel URL as the web experience for an Android Studio app shell, then integrate and test native ESP32 and camera capabilities as separate additions.
5. Review and configure clinician-owned program assignment and review workflows.
6. Collect consented, manually or clinician-reviewed multi-athlete data before evaluating any candidate movement model; do not activate models based on starter/demo data.
7. Replace process-local report background tasks with a durable worker/queue, retries and operational monitoring; add clinician review flows after permissions and sharing are designed.

Vercel deployment, live Supabase migration, physical ESP32 behavior, native camera, Health Connect, Gemini interpretation, clinical decision support and production emergency escalation remain unverified or unimplemented.
