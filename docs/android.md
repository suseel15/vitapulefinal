# VitaPulse Android client

The Android client is a separate Kotlin/Jetpack Compose application in `android/`. It supplements the web app; it does not replace it. It implements ESP32-001 / MPU6050 connection, local movement processing, and the authenticated Rehab summary flow.

## Configure and build

Open the `android/` directory in Android Studio. Use JDK 17 and install Android SDK Platform 36 plus the matching Android build tools. Configure the local SDK path and client-safe endpoints in the ignored `android/local.properties` file:

```properties
sdk.dir=C\:\\Users\\YOUR_USER\\AppData\\Local\\Android\\Sdk
VITAPULSE_ESP32_BASE_URL=http://192.168.4.1/
VITAPULSE_API_BASE_URL=https://YOUR_BACKEND_ORIGIN/api/v1/
VITAPULSE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITAPULSE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
```

The ESP32 Wi-Fi passphrase is entered at connection time, used only to request the Android Wi-Fi network, and is not persisted or sent to the backend. Never place Supabase service-role keys, database credentials, or Wi-Fi passwords in Gradle files or source control.

Build and run focused Android tests with:

```powershell
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug
```

The app requests local Wi-Fi access only after the athlete taps **Connect device**. Android's system network confirmation selects the ESP32 access point. The selected `Network` and its socket factory are used only for the device HTTP client; API and Supabase Auth requests use the normal Internet route. No raw sensor readings or Wi-Fi credentials are sent to the backend.

## Device and session behavior

- Connects to `VitaPulse-ESP32` at `192.168.4.1` and validates `GET /status` and `GET /data` for ESP32-001 and the MPU6050 before reporting `SENSOR_CONNECTED`.
- Polls over HTTP with a 100 ms requested delay while verifying, calibrating, or recording; the UI reports measured request rate and latency instead of asserting an ideal 10 Hz rate.
- Validates all six finite axis values and conservative numeric bounds. Invalid, failed, timed-out, and stale readings produce visible connection/session errors.
- Calibrates each session from at least 30 stationary live readings. Sensor placement is recorded with the session and does not imply permanent sensor calibration.
- Keeps the bounded recent raw-sample window and summaries on-device. Only an authenticated, owner-scoped session summary and request diagnostics are sent to FastAPI/Supabase.
- Stores completed sessions locally and retries summary sync when the athlete is signed in and the backend is reachable. A client session UUID makes create/retry idempotent.
- Stops polling on disconnect, session pause, or app background. Simulation is not used as a hardware fallback.

The live movement, stability, smoothness, and fatigue values are experimental qualitative signals. They are not diagnoses, medical advice, or return-to-sport clearance.

## Phase 5 movement intelligence

Processing is designed for the app's measured HTTP polling rate (nominally 10 Hz), not a claimed 100 Hz stream. Three-second windows advance by one second, require at least 20 samples and an observed rate of at least 8 Hz, and use the versioned `movement-features-v1` schema (45 features). Invalid or low-quality windows fall back to deterministic repetition/session summaries; they do not become model labels. A single MPU6050 cannot establish full-body biomechanics or diagnose fatigue, injury, or unsafe form.

The session pipeline tracks repetitions, qualitative movement signals, confirmed repeated anomalies, and a placement- and exercise-specific personal baseline. Baselines require at least three completed live sessions and 20 valid repetitions; these are technical data minimums, not clinical thresholds. Model recognition remains unavailable unless a compatible, checksummed `ACTIVE` JSON-forest artifact has been explicitly registered and enabled. No validated labeled multi-athlete dataset or active model is included.

Debug builds expose **Export training sample** after a signed-in live session. The athlete must confirm that the completed recording contains only the selected Rehab exercise before it is recorded as a `MANUAL` label. Only raw live samples are exported. The ZIP contains `metadata.csv`, `samples.csv`, and `labels.csv`, with a locally salted pseudonymous athlete ID. Export is a local file save and does not upload the archive. Treat it as sensitive health data, collect it with informed consent, and have labels reviewed before training. Never use rule-generated predictions as ground truth.

From `backend/`, the dataset pipeline is:

```powershell
python -m scripts.validate_dataset --dataset datasets/movement
python -m scripts.build_features --dataset datasets/movement --output build/movement-features.csv
python -m scripts.train_exercise_model --features build/movement-features.csv --output-dir build/models
python -m scripts.evaluate_exercise_model --evaluation build/models/rf-exercise-v1.evaluation.json
python -m scripts.export_model --artifact build/models/rf-exercise-v1.json --output-dir build/exported-models
python -m scripts.register_model --artifact build/exported-models/rf-exercise-v1.json
```

Install the optional trainer dependency first with `pip install -e ".[ml-training]"`. Training requires at least three pseudonymous athletes, two exercise classes present on both sides of a subject-independent split, and manually or clinician-reviewed labels. Training, export, and registration leave models `EXPERIMENTAL`; activation must be a separate, reviewed registry operation after real-device evaluation. Report per-class metrics and dataset limitations; do not claim performance from the repository's empty starter dataset.

## Phase 6 athlete wellbeing

The Wellbeing tab keeps athlete self-reports, sleep entries, calculated recovery context, and optional camera observations as separate, provenance-labelled records. Check-ins are optional and private to the athlete. Recovery and trends use only available records; they do not diagnose mental health, illness, injury, or readiness. Camera processing is foreground-only, does not retain or upload raw frames/video, and does not perform identity recognition. Turning off camera-history storage keeps the structured result only in the current result screen.

Records use a separate local Room database and remain available offline; signed-in writes are queued for authenticated sync. The optional daily check-in reminder is scheduled inexactly at the athlete's chosen local time. Android 13+ notification permission is requested only when the athlete enables reminders; denying/revoking it leaves reminders disabled. The reminder is not an emergency or clinical alert.

Apply only pending migration `202610060007_phase_6_athlete_wellbeing.sql`, after migrations 005 and 006 and in filename order. Do not re-run a migration already applied to the Supabase project. The migration adds owner-scoped wellbeing records, RLS, and append-only audit events; review it against the target project before applying.

## Backend and Supabase

Apply only pending migrations `202610060005_phase_4_esp32_device_sessions.sql`, `202610060006_phase_5_movement_intelligence.sql`, and `202610060007_phase_6_athlete_wellbeing.sql`, in filename order and after their prerequisites. Do not re-run migrations already applied in the Supabase project. Migration 005 adds owner-scoped device records, a device reference and client idempotency key for Rehab sessions, and compact request-diagnostic summary columns. Migration 006 adds the model/dataset registries, derived prediction/event/baseline/anomaly/fatigue results, and validated summary fields. It does not add raw-sample ingestion or persist Wi-Fi credentials. Migration 007 adds private athlete wellbeing data and audit events.

Authenticated endpoints include `GET/POST /api/v1/devices`, `GET/PATCH /api/v1/devices/{device_id}`, Rehab session and movement-summary routes, `GET /api/v1/ml/models`, `GET /api/v1/ml/models/{model_id}/artifact`, `POST /api/v1/ml/analyze-session`, and `GET /api/v1/ml/movement-summary`. FastAPI verifies the Supabase bearer token and athlete role; data reads are scoped to the caller. Client roles receive no direct write grants to the Phase 5 result tables; writes use the backend service role.

## Verification status

Phase 4 Android tests/build/lint and the prior web/backend checks were verified before Phase 5. Phase 6 backend unit tests have passed, but the current Android changes still require Android unit/build/lint and migration validation against PostgreSQL/Supabase. The physical camera workflow and reminder permission behavior require device acceptance. The physical ESP32 + MPU6050 + Android phone run, actual Wi-Fi join behavior, measured hardware request rate/latency, clinical review, and live Supabase migration have not been performed and must not be represented as verified.
