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
The native destinations are available from the top app menu; the redundant bottom navigation bar is not used.

## Device and session behavior

- Connects to `VitaPulse-ESP32` at `192.168.4.1` and validates the MPU6050 axes in `GET /data` before reporting `SENSOR_CONNECTED`; this also supports the uploaded exercise-counter firmware, which does not expose `/status`.
- When connected outside an active Rehab session, reads the firmware exercise counter while the app is foregrounded. Its picker sends the uploaded sketch's `/exercise?value=0..9` command and its reset button calls `/reset`. The ten supported choices are bicep curl, hammer curl, dumbbell row, wrist curl, reverse wrist curl, lateral raise, front raise, shoulder press, tricep extension, and tricep kickback.
- Polls over HTTP with a 100 ms requested delay while verifying, monitoring the exercise counter, calibrating, or recording; the UI reports measured request rate and latency instead of asserting an ideal 10 Hz rate.
- Validates all six finite axis values and conservative numeric bounds. Invalid, failed, timed-out, and stale readings produce visible connection/session errors.
- Calibrates each session from at least 30 stationary live readings. Sensor placement is recorded with the session and does not imply permanent sensor calibration.
- Keeps the bounded recent raw-sample window and summaries on-device. Only an authenticated, owner-scoped session summary and request diagnostics are sent to FastAPI/Supabase.
- Stores completed sessions locally and retries summary sync when the athlete is signed in and the backend is reachable. A client session UUID makes create/retry idempotent.
- Stops exercise-counter polling on disconnect or app background. An active Rehab session owns the sensor stream; on an explicit session pause, counter polling resumes. Simulation is not used as a hardware fallback.

On Android 10–12, joining the ESP32 asks for foreground location permission because Wi-Fi network selection requires it; newer Android versions request the applicable nearby-Wi-Fi or local-network permission. The app does not request unrelated special access or background location.

The live movement, stability, smoothness, and fatigue values are experimental qualitative signals. They are not diagnoses, medical advice, or return-to-sport clearance.

## Phase 5 movement intelligence

Processing is designed for the app's measured HTTP polling rate (nominally 10 Hz), not a claimed 100 Hz stream. Three-second windows advance by one second, require at least 20 samples and an observed rate of at least 8 Hz, and use the versioned `movement-features-v1` schema (45 features). Invalid or low-quality windows fall back to deterministic repetition/session summaries; they do not become model labels. A single MPU6050 cannot establish full-body biomechanics or diagnose fatigue, injury, or unsafe form.

The session pipeline tracks repetitions, qualitative movement signals, confirmed repeated anomalies, and a placement- and exercise-specific personal baseline. Baselines require at least three completed live sessions and 20 valid repetitions; these are technical data minimums, not clinical thresholds. Model recognition remains unavailable unless a compatible, checksummed `ACTIVE` artifact has been explicitly registered and enabled. The Android client currently supports the JSON random-forest artifact; the Python 1D CNN is an experimental training/evaluation path and is not yet wired into Android inference. No validated labeled multi-athlete dataset or active model is included.

Debug builds expose **Export training sample** after a signed-in live session. The athlete must confirm that the completed recording contains only the selected Rehab exercise before it is recorded as a `MANUAL` label. Only raw live samples are exported. The ZIP contains `metadata.csv`, `samples.csv`, and `labels.csv`, with a locally salted pseudonymous athlete ID. Export is a local file save and does not upload the archive. Treat it as sensitive health data, collect it with informed consent, and have labels reviewed before training. Never use rule-generated predictions as ground truth.

From `backend/`, the dataset pipeline is:

```powershell
python -m scripts.validate_dataset --dataset datasets/movement
python -m scripts.build_features --dataset datasets/movement --output build/movement-features.csv
python -m scripts.train_exercise_model --features build/movement-features.csv --output-dir build/models --model-type cnn
python -m scripts.evaluate_exercise_model --evaluation build/models/cnn-exercise-v2.evaluation.json
```

Install the optional trainer dependency first with `pip install -e ".[ml-training]"`. Training requires at least three pseudonymous athletes, two exercise classes present on both sides of a subject-independent split, and manually or clinician-reviewed labels. The trainer prints a confusion matrix whose rows are actual classes and columns are predicted classes and writes the same metrics to the evaluation JSON. Training leaves models `EXPERIMENTAL`; it does not activate, register in Supabase, or install the CNN in Android. Activation must be a separate, reviewed operation after real-device evaluation. The checked-in starter CSVs contain headers only, so they cannot produce a meaningful confusion matrix; do not claim performance from synthetic unit tests or the empty starter dataset.

## Phase 6 athlete wellbeing

The Wellbeing tab keeps athlete self-reports, sleep entries, calculated recovery context, and optional camera observations as separate, provenance-labelled records. Check-ins are optional and private to the athlete. Recovery and trends use only available records; they do not diagnose mental health, illness, injury, or readiness. Camera processing is foreground-only, does not retain or upload raw frames/video, and does not perform identity recognition. Turning off camera-history storage keeps the structured result only in the current result screen.

Records use a separate local Room database and remain available offline; signed-in writes are queued for authenticated sync. The optional daily check-in reminder is scheduled inexactly at the athlete's chosen local time. Android 13+ notification permission is requested only when the athlete enables reminders; denying/revoking it leaves reminders disabled. The reminder is not an emergency or clinical alert.

Apply only pending migration `202610060007_phase_6_athlete_wellbeing.sql`, after migrations 005 and 006 and in filename order. Do not re-run a migration already applied to the Supabase project. The migration adds owner-scoped wellbeing records, RLS, and append-only audit events; review it against the target project before applying.

## Phase 7 Connect Hub and Health Connect

Health Connect permissions are requested and tracked separately by data type, with an optional consent flow to request all five supported read scopes together. Health Connect availability, client, and granted scopes are refreshed when returning from Android system settings. The app does not request write access. Synced records are cached in the local Room database with provider origin, record time, and cache-sync time. The native Health, Rehab, and Wellbeing screens surface only recent sleep (up to 48 hours), same-day steps, and heart-rate summaries (up to 24 hours); they do not calculate a medical readiness or recovery score from these values.

Account upload is a separate, default-off preference. When enabled, WorkManager performs bounded incremental synchronization and retries only when network access is available. Raw heart-rate samples remain local; the backend receives an average and sample count. Local cache deletion and account-data deletion are distinct actions. NoiseFit Mettle is supported through its official companion-app/Health Connect workflow; VitaPulse does not reverse-engineer a proprietary Bluetooth protocol.

## Phase 9 Reports

The native Reports tab supports authenticated weekly-report creation, status and source-linked details, expiring secure PDF links, and explicit-recipient email delivery. It requires the Phase 9 reports migration (`202610060009_phase_9_reports_intelligence.sql`) to be applied to the Supabase project and the reports/PDF server settings to be enabled. The app reports unavailable backend functionality instead of fabricating results.

The authenticated API exposes `/api/v1/connect/status`, `/api/v1/connect/devices`, `/api/v1/connect/permissions`, `/api/v1/connect/sync`, `/api/v1/connect/sync/history`, `/api/v1/connect/health-data`, and normalized `/api/v1/health-data/{sleep,heart-rate,activity,exercise,spo2}` reads. Apply only pending migration `202610060008_phase_7_connect_health_data.sql`, after migration 007 and in filename order. Review its owner-scoped RLS against the target Supabase project before applying; hosted application has not been confirmed.

Phase 8 emergency escalation is not implemented. The available handoff does not specify validated risk thresholds, consent/availability requirements, or who may be contacted, so the app does not invent automated emergency actions.

## Backend and Supabase

Apply only pending migrations `202610060005_phase_4_esp32_device_sessions.sql` through `202610060008_phase_7_connect_health_data.sql`, in filename order and after their prerequisites. Do not re-run migrations already applied in the Supabase project. Migration 005 adds owner-scoped device records, a device reference and client idempotency key for Rehab sessions, and compact request-diagnostic summary columns. Migration 006 adds the model/dataset registries, derived prediction/event/baseline/anomaly/fatigue results, and validated summary fields. It does not add raw-sample ingestion or persist Wi-Fi credentials. Migration 007 adds private athlete wellbeing data and audit events. Migration 008 adds owner-scoped Connect device, permission, sync, normalized health-record, and audit tables.

Authenticated endpoints include `GET/POST /api/v1/devices`, `GET/PATCH /api/v1/devices/{device_id}`, Rehab session and movement-summary routes, `GET /api/v1/ml/models`, `GET /api/v1/ml/models/{model_id}/artifact`, `POST /api/v1/ml/analyze-session`, `GET /api/v1/ml/movement-summary`, and the Phase 7 Connect and health-record routes above. FastAPI verifies the Supabase bearer token and athlete role; data reads are scoped to the caller. Client roles receive no direct write grants to the Phase 5 result tables; writes use the backend service role.

## Verification status

The Android unit suite and release APK build pass locally; a device-test APK can be signed with the local debug key, but it is not a Play Store release signature. The physical camera workflow, Health Connect provider/device behavior, ESP32 + MPU6050 phone run, actual Wi-Fi join behavior, measured hardware request rate/latency, clinical review, and live Supabase migrations have not been verified and must not be represented as complete.
