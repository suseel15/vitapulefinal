# VitaPulse setup and release guide

This guide covers a local prototype, Vercel deployment, Android APK generation, and the current movement-model status. Optional integrations stay disabled until their required account, credentials, data, and review steps are complete; switching a flag alone does not make an integration operational.

## 1. Local web prototype

Requirements: Node.js 20 or later.

From the repository root:

```powershell
npm run dev
```

Open <http://127.0.0.1:4173>. The loopback-only demo sign-in is synthetic and isolated to the browser tab; it does not create or read real athlete records. Use the on-screen demo account helper. Demo features do not prove Supabase, reports, ML, notifications, or connected hardware are configured.

Run the web checks and production bundle:

```powershell
npm test
npm run build
```

## 2. Local API and Supabase

Requirements: Python 3.11 or later and a Supabase project for real accounts and persisted health data.

Create the local backend environment without replacing an existing `.env`:

```powershell
cd backend
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Edit `backend/.env` with your own values. For real authenticated API use, configure:

```dotenv
APP_ENV=development
DEBUG=true
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_PUBLISHABLE_KEY=YOUR_CLIENT_SAFE_PUBLISHABLE_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_ONLY_SERVICE_ROLE_KEY
```

Keep the service-role key, database password, Gemini API key, and SMTP password out of `config.js`, Vercel public/build variables, Android resources, and source control. The browser needs only the Supabase project URL and publishable/anon key. Enable Supabase Row Level Security and apply the project policies before using real records.

In the Supabase SQL editor or CLI, inspect migration history first and apply only migrations not already applied, in filename order. Do not rerun migrations that have already succeeded. The health, rehab, movement, wellbeing, Connect, and reports features depend on their corresponding schemas; the reports pipeline additionally requires `202610060009_phase_9_reports_intelligence.sql`.

Configure the browser-safe client values in `config.js` for local web development:

```js
window.VITAPULSE_CONFIG = Object.freeze({
  apiBaseUrl: "http://127.0.0.1:8000",
  supabaseUrl: "https://YOUR_PROJECT.supabase.co",
  supabasePublishableKey: "YOUR_CLIENT_SAFE_PUBLISHABLE_KEY",
  demoModeEnabled: true,
});
```

Run the backend in a second terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

The API liveness check is <http://127.0.0.1:8000/health>. The readiness endpoint is `/ready`; a missing or unreachable Supabase project is reported as not ready rather than treated as healthy.

## 3. Feature configuration

Backend flags are capability gates, not feature installers. Configure a flag only after its dependency and data path work:

| Capability | Configuration | Required before enabling |
|---|---|---|
| Reports/PDF | `REPORTS_ENABLED`, `PDF_GENERATION_ENABLED` | Supabase configuration, report migration, private Storage bucket and policies |
| AI report interpretation | `GEMINI_ENABLED`, `GEMINI_API_KEY`, `GEMINI_MODEL` | Server-side Gemini key; AI remains advisory and source-checked |
| Email reports | `SMTP_ENABLED` and `SMTP_*` | Verified SMTP provider and an explicit recipient |
| OCR | `OCR_ENABLED` | OCR engine/languages installed in the deployment runtime and upload path tested |
| Skin screening | `SKIN_SCREENING_ENABLED` | A validated screening provider/model and its safety/privacy review |
| Movement model API | `ML_ENABLED` | Reviewed `ACTIVE` model registry row, matching artifact, checksum and schema |
| Android local model download | `ML_LOCAL_INFERENCE_ENABLED` | Above plus artifact accessible to the API and Android-supported model format |
| Push notifications | `FCM_ENABLED` | Firebase app/service configuration and permission-tested Android flow |
| Real emergency escalation | `ENABLE_REAL_EMERGENCY_ESCALATION` | Operational emergency provider, consent, jurisdictional review and safety testing |

`DEMO_MODE_ENABLED` is not the browser demo switch. Browser demo sessions are restricted by the client to `localhost` and `127.0.0.1`. Do not enable synthetic sessions on a public deployment.

The current local backend `.env` has ML and backend demo mode disabled. That is intentional: the checked-in movement CSVs are header-only, there is no validated model in the registry, and no model artifact is present for serving. Leave `ML_ENABLED=false` and `ML_LOCAL_INFERENCE_ENABLED=false` until the workflow in the next section has real reviewed data and an approved artifact.

## 4. Movement model and confusion matrix

Install the optional model-training dependencies from `backend/`:

```powershell
python -m pip install -e ".[ml-training]"
```

Training data must be consented, pseudonymous, recorded from live sensors, and manually or clinician-reviewed. Never use rule-generated predictions as training labels. `metadata.csv`, `samples.csv`, and `labels.csv` must match the schema checked by the dataset validator. Use at least three athletes and ensure every target class has examples in both sides of the subject-independent split; more participants are needed for a meaningful evaluation.

From `backend/`:

```powershell
python -m scripts.validate_dataset --dataset datasets\movement
python -m scripts.build_features --dataset datasets\movement --output build\movement-features.csv
python -m scripts.train_exercise_model --features build\movement-features.csv --output-dir build\models --model-type cnn
python -m scripts.evaluate_exercise_model --evaluation build\models\cnn-exercise-v2.evaluation.json
```

Training prints a confusion matrix with actual classes as rows and predicted classes as columns, plus the subject-independent holdout accuracy and evaluation-file path. It writes metrics to `build/models/cnn-exercise-v2.evaluation.json`. The CNN trains a convolution/ReLU/global-max-pooling/dense-softmax classifier over the versioned movement feature vector; the artifact remains `EXPERIMENTAL`.

### Train on the supplied knee-mobility dataset

The separate knee-mobility trainer consumes the user's `Walking_Data.csv` and `Climbing_Data.csv`. It treats each row's source-provided `Bad`, `Healthy`, or `Moderate` label as the target and each row as a 120-step sequence with 12 values per step. It ignores names, age, gender, BMI, and the separate augmented/activity-classification CSVs. The participant identifier is used only in memory to keep the same participant out of both sides of the split.

From `backend/`, install the optional training dependencies if needed, then run:

```powershell
python -m pip install -e ".[ml-training]"
python -m scripts.train_knee_mobility --dataset "..\Sensor-Based Dataset for Knee Joint Mobility and R" --output-dir build\knee-mobility
```

The script prints the participant-independent holdout confusion matrix and writes an experimental model plus evaluation JSON under the ignored `backend/build/knee-mobility/` folder. It explicitly reports malformed activity rows excluded from training. The provided set includes malformed readings and some participants whose labels differ between the two activity files; the evaluation report preserves these counts. Review the original source and label definitions before any clinical or deployment use.

Latest run on the files in this workspace (seed 17): 200 training samples from 112 participants and 70 test samples from 38 participants. Thirty malformed Walking rows were excluded, and six participants had conflicting labels across the remaining activity rows. Holdout accuracy was 0.343 versus a 0.357 majority-class baseline; the model did not outperform that simple baseline.

| Actual \ Predicted | Bad | Healthy | Moderate |
|---|---:|---:|---:|
| Bad | 7 | 10 | 8 |
| Healthy | 8 | 6 | 10 |
| Moderate | 7 | 3 | 11 |

The model artifact is specific to this 120-by-12 dataset and is not compatible with the existing exercise-recognition API or Android inference path. It does not enable `ML_ENABLED` and is not evidence of clinical validity. Do not commit or upload the source datasets, which include personal data.

The separate gyro-angle CSV has no ground-truth labels, so it is not used to train or evaluate a classifier. Do not infer posture categories from its angles.

### Run a synthetic end-to-end prototype

To verify the generator, feature extraction, subject-independent split, CNN training, and matrix output without pretending the project has collected field data, run this separate pipeline:

```powershell
cd backend
python -m scripts.generate_synthetic_movement_dataset --output datasets\movement-synthetic
python -m scripts.validate_dataset --dataset datasets\movement-synthetic
python -m scripts.build_features --dataset datasets\movement-synthetic --output build\synthetic-movement-features.csv
python -m scripts.train_exercise_model --features build\synthetic-movement-features.csv --output-dir build\synthetic-models --model-type cnn --allow-synthetic
python -m scripts.evaluate_exercise_model --evaluation build\synthetic-models\cnn-exercise-v2.evaluation.json
```

The generator writes simulated-only IMU samples, labels and metadata under `backend/datasets/movement-synthetic/`; it never replaces `backend/datasets/movement/`. The explicit `--allow-synthetic` option is required to train against those data, and training rejects mixed provenance. The resulting artifact stays experimental and is not activated for athletes.

For the generated seed `20261007`, the subject-independent test used 60 windows from three held-out synthetic athlete IDs. Its sample output was:

| Actual \ Predicted | BALANCE | REST | SIT_TO_STAND | SQUAT | WALK |
|---|---:|---:|---:|---:|---:|
| BALANCE | 9 | 3 | 0 | 0 | 0 |
| REST | 0 | 12 | 0 | 0 | 0 |
| SIT_TO_STAND | 0 | 0 | 12 | 0 | 0 |
| SQUAT | 0 | 0 | 0 | 12 | 0 |
| WALK | 0 | 0 | 0 | 0 | 12 |

This run reported `0.950` accuracy on generated data only. It is a pipeline smoke-test result, not evidence of athlete movement recognition.

**Movement model status:** the existing live exercise-recognition pipeline still has no reviewed real sensor training rows in its repository dataset and no validated production model. The separate supplied knee-mobility evaluation is experimental, uses a distinct target/schema, and must not be represented as athlete exercise recognition or clinical performance.

Training does not register or activate a model. The CNN path is currently Python training/evaluation only; the Android local model loader supports the JSON random-forest format, not this CNN artifact. Activation, backend registry integration, and Android CNN inference remain separate work and require held-out real-device validation. Do not flip ML flags to hide these prerequisites.

## 5. Vercel deployment

The project serves the web client and FastAPI from the same origin. In Vercel:

1. Import the repository and set the project Root Directory to `backend`.
2. Select the FastAPI framework/runtime. Keep the repository's `build_frontend.py` build hook enabled; it copies the web assets and generates the browser config from environment variables.
3. Add the following environment variables for the intended Vercel environments (Production, and Preview/Development only when configured):

   - `SUPABASE_URL` — HTTPS Supabase project URL.
   - `SUPABASE_PUBLISHABLE_KEY` — client-safe publishable/anon key.
   - `SUPABASE_SERVICE_ROLE_KEY` — server-only key; never expose to the browser.
   - `APP_ENV=production` and `DEBUG=false`.
   - Optional integrations only after configured and verified; see the feature table above.

4. Deploy, then verify the site root, `/health`, `/ready`, sign-in, and the relevant authenticated API flows.
5. In Supabase Auth, set the Site URL to the final Vercel origin and add the exact origin to allowed redirect URLs. Same-origin browser API requests do not need CORS; configure `CORS_ORIGINS` only for additional, deliberate web origins.
6. Apply pending database/storage migrations once, and verify RLS and private bucket policies against the target project.

Vercel's build rejects missing Supabase URL/publishable key values and rejects service-role keys in the public-key setting. Never paste server secrets into `VITAPULSE_*` browser configuration variables. A successful deploy/build does not itself confirm that migrations, auth redirects, RLS, report storage, or external providers are ready.

## 6. Android APK generation

Requirements: Android Studio, JDK 17, Android SDK Platform 36/build tools, and an Android 10+ device/emulator for runtime validation. Open the `android/` directory in Android Studio and sync Gradle.

Set machine-local values in the ignored `android/local.properties` file:

```properties
sdk.dir=C\:\\Users\\YOUR_USER\\AppData\\Local\\Android\\Sdk
VITAPULSE_WEB_APP_URL=https://YOUR_DEPLOYMENT.vercel.app/
VITAPULSE_API_BASE_URL=https://YOUR_DEPLOYMENT.vercel.app/api/v1/
VITAPULSE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITAPULSE_SUPABASE_PUBLISHABLE_KEY=YOUR_CLIENT_SAFE_PUBLISHABLE_KEY
VITAPULSE_ESP32_BASE_URL=http://192.168.4.1/
```

Never put the Supabase service-role key or Wi-Fi password in Android configuration. The publishable key is client-visible and must be protected by Supabase RLS.

From `android/`, run tests and build a locally installable debug APK:

```powershell
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug
```

The debug APK is written to `android/app/build/outputs/apk/debug/app-debug.apk`. Install it on a test device and validate sign-in, bottom navigation, network/API reachability, Health Connect permissions, camera consent, and (if available) the ESP32 hardware path.

For a distributable release APK, use Android Studio **Build > Generate Signed Bundle / APK > APK** and create/select a release signing key. Keep the keystore and passwords in a secure backup outside Git; losing the keystore prevents updating an app signed with it. Configure the release variant, generate the signed APK, and test that exact APK on a device before distribution. Do not treat an unsigned `assembleRelease` output as a distributable package.

## 7. Final checks and current limits

From the repository root:

```powershell
npm test
npm run build
```

From `backend/`:

```powershell
.\.venv\Scripts\Activate.ps1
pytest
```

From `android/`:

```powershell
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug
```

The web app has a working local synthetic demo and real-account pathways when configured. Some integrations are correctly unavailable until external credentials, migrations, hardware, approved models, or reviewed datasets are supplied. Health and movement summaries are informational, not diagnosis, medical clearance, or emergency response.
