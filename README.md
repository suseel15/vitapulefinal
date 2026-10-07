# VitaPulse

VitaPulse is a sports-first health, rehabilitation, recovery and wellbeing product for athletes. The product is **web-first**. The responsive web app is deployed, with a separate Android client for native Health Connect and ESP32-001 + MPU6050 workflows.

For a step-by-step local setup, secrets/environment configuration, Vercel deployment, Android APK build/signing, and movement-model evaluation status, see [SETUP.md](./SETUP.md).

The web app is a light-first responsive site with an athlete home and five-item mobile navigation, separate verified-doctor navigation, Supabase Auth integration, and a FastAPI/Supabase foundation. Phase 2 adds owner-scoped health records, consented report upload/OCR, and source-linked measurements. Phase 3 adds an athlete rehabilitation experience, simulation/manual sessions, qualitative movement summaries, progress, readiness and return-to-sport review. Phases 4–7 add native sensor sessions, movement summaries, athlete wellbeing, and opt-in Health Connect synchronization. Phase 9 adds source-linked HTML/PDF reports, secure file links, optional email delivery, and deterministic period comparisons. The backend has an experimental, subject-independent 1D CNN training path; no validated labeled dataset or active production model is included, so model inference remains disabled until a reviewed artifact is explicitly activated. Unconfigured features remain visibly unavailable rather than showing invented data.

## Run the web app

Requirements: Node.js 20 or later.

```powershell
npm run dev
```

Open <http://127.0.0.1:4173>. Supabase is used for real authentication when configured. On `localhost` and `127.0.0.1` only, a clearly labelled local demo mode is available without Supabase. Demo sessions are synthetic, stay in the current browser tab, never call the backend, and contain no athlete or patient records. The demo is disabled on other hosts.

Set the browser-safe Supabase project URL and **publishable** key in `config.js` to enable real authentication. Never put a Supabase service-role key, database password, Gemini key, or SMTP credential in `config.js`.

```js
window.VITAPULSE_CONFIG = Object.freeze({
  apiBaseUrl: "http://127.0.0.1:8000",
  supabaseUrl: "https://YOUR_PROJECT.supabase.co",
  supabasePublishableKey: "YOUR_SUPABASE_PUBLISHABLE_KEY",
  demoModeEnabled: true,
});
```

The checked-in `config.js` enables demo mode only on local loopback hosts. Keep it disabled for any non-local preview unless you deliberately configure a separate safe demo environment. The publishable key is client-safe only when Row Level Security is enabled and policies are applied. `config.js` is public runtime configuration; never put secrets there.

Local development demo accounts:

| Role | Email | Password |
|---|---|---|
| Athlete | `demo@vitapulse.app` | `Demo@12345!` |
| Doctor | `doctor.demo@vitapulse.app` | `DemoDoctor@12345!` |

These fixed credentials only create isolated synthetic sessions on local loopback. Do not create matching accounts in a production Supabase project or use demo sessions for real athletes/patients.

## Build and test

```powershell
npm test
npm run build
```

The build copies the static app into `dist/`. The development server and build use Node's built-in modules; no npm packages are needed.

## Deploy the web app to Vercel

The Vercel project uses the FastAPI preset with its Root Directory set to `backend`. The build hook copies the web client into `backend/public/`, and FastAPI's frontend integration serves it from Vercel's CDN at the same origin as `/api/...`. `npm run build` remains the local static-web build. Configure the following Vercel backend environment variables for Production, Preview, and Development as needed:

- `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` — the Supabase project URL and publishable/anon key used by the web client. These are public browser values; never use a service-role key for `SUPABASE_PUBLISHABLE_KEY`.
- The backend's remaining server settings, including `SUPABASE_SERVICE_ROLE_KEY`, must remain Vercel server-side environment variables only. The frontend build copies only the Supabase URL and publishable key into the public client configuration and uses the current site origin for its API base.

The Vercel build fails clearly if the Supabase URL/key are missing or invalid, or if the publishable-key variable contains a service-role key. Never put service-role or other server secrets in frontend config. In the hosted Supabase Auth URL settings, set the Site URL to `https://vitapulse-eosin.vercel.app` and allow that origin for redirects. Registration and password-reset requests return to the current site origin. Same-origin browser API requests do not require cross-origin CORS configuration; add the exact Vercel origin to the backend's `CORS_ORIGINS` only for other web origins.

The web Wellbeing hub supports authenticated self-reported check-ins, sleep records, calculated recovery context, history, trends, and summaries through the existing Health API. Home, Wellbeing, and Rehab recovery also show fresh, account-scoped Health Connect sleep, activity, and heart-rate summaries with origin, record time, and sync time. They do not infer a recovery score from wearable data. Local demo entries remain in memory only. Camera capture is deliberately not enabled on the website.

## Android Studio app

Open the `android/` directory in Android Studio, sync the Gradle project, and run the `app` configuration on an Android 10+ device or emulator. The app opens the production VitaPulse website in a secure WebView and keeps the native Connect, Rehab, and Wellbeing screens available from the bottom navigation. Android back navigates the website history before leaving the app; links to other HTTPS sites open in the device browser.

The production web URL is configured by `VITAPULSE_WEB_APP_URL` in Gradle and defaults to `https://vitapulse-eosin.vercel.app/`. To point a local build at another HTTPS deployment, pass `-PVITAPULSE_WEB_APP_URL=https://your-deployment.example/` to Gradle. The WebView has JavaScript and DOM storage enabled for the web client, while file/content access and mixed HTTP content remain disabled. The native bottom navigation includes report creation, progress, source-linked details, secure PDF links, and explicit-recipient email delivery after athlete sign-in. No Supabase service credential is packaged in the Android app.

Health Connect permissions are requested per data type. Records are cached locally and show their provider origin, record time, and local sync time in the Health, Rehab, and Wellbeing views. Upload of summary-only health data to the athlete account is a separate, default-off opt-in; high-frequency heart-rate samples remain local. Apply migration `202610060008_phase_7_connect_health_data.sql` only if it is still pending in the target Supabase project. Hosted migration application and physical-device validation have not been confirmed.

## Backend

Requirements: Python 3.11 or later.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uvicorn app.main:app --reload
```

`GET /health` and `GET /api/v1/health` are liveness endpoints. `GET /ready` and `GET /api/v1/ready` verify Supabase configuration and reachability; without configuration they return a structured 503, not a false-ready response. Authenticated `GET /api/v1/me` verifies the bearer token with Supabase Auth and reads the caller's profile using that same user token. No service-role key is used to authorize a user.

### Reports and longitudinal intelligence

Apply migration `202610060009_phase_9_reports_intelligence.sql` once before enabling reports. The migration creates owner-scoped report/job/source/audit data, timeline and intelligence snapshots, review items, and the private Storage bucket; it has not been applied automatically by the app. Set `REPORTS_ENABLED=true` and `PDF_GENERATION_ENABLED=true` as needed. `ATHLETE_INTELLIGENCE_ENABLED=false` disables period comparison and snapshot persistence while leaving the factual report available. AI interpretation requires `GEMINI_ENABLED=true` and a server-side `GEMINI_API_KEY`; email delivery additionally requires configured SMTP settings and `SMTP_ENABLED=true`. Report generation remains available without AI interpretation, which is marked unavailable or skipped rather than fabricated. Athlete identity is derived from the authenticated profile. Weekly/monthly/longitudinal reports compare periods only when at least three numeric records for a measure exist in both periods.

The web Reports workspace and native Android Reports tab both support athlete report creation, status/details, PDF access through expiring signed URLs, and explicit-recipient email. Timeline, intelligence snapshot/insight, and review-item APIs are available under `/api/v1/reports`; all are owner-scoped. Background generation currently runs through FastAPI background tasks, so a durable worker/recovery service is not included.

Run backend tests from `backend/`:

```powershell
pytest
```

Create `backend/.env` from `backend/.env.example` only if it does not already exist, then configure values in your local environment. `.env` is ignored by Git; keep existing local credentials private and do not print or overwrite them.

## Supabase

1. Create a Supabase project.
2. Apply only migration files that have not already run, in filename order, using the Supabase CLI or SQL editor. Since the initial SQL was already run for your project, do not run it again; check whether migrations `202610060002` through `202610060009` are pending before applying each once. Migration `202610060009_phase_9_reports_intelligence.sql` creates report/intelligence tables and the private `reports` Storage bucket.
3. Enable email authentication and configure the site URL / recovery redirect URL to your local or deployed VitaPulse web origin.
4. Add the project URL and publishable key to local `config.js` and set `apiBaseUrl` to the backend origin.
5. Add the project URL, publishable key, and service-role key to `backend/.env`. The service-role key is used only by protected health routes after backend authentication and owner checks; it must never be exposed to the browser.
6. Configure `CORS_ORIGINS` for the exact web origin. Configure OCR dependencies as described in [Phase 2 Health](./docs/phase2-health.md).

New athlete accounts receive an athlete profile from a database trigger. Self-registered doctor accounts create a pending application only. Pending doctor applicants are not silently granted an athlete session. A trusted administrator must verify credentials and grant the `DOCTOR` role through a protected administrative process. Client-supplied role metadata is never trusted. Doctor screens and data access are separate; database RLS is authoritative.

## Account and data status

- Authentication uses Supabase Auth when configured. Passwords are submitted to Supabase over HTTPS and are never persisted by VitaPulse.
- Browser auth sessions are held in per-tab `sessionStorage` and refreshed through Supabase. Do not treat a browser-stored role as authorization.
- Doctor registration is a request for verification, not an automatic grant of clinical access.
- Development demo credentials are available only on loopback hosts. They create no database users or athlete/doctor records.
- Athlete registration supports optional date of birth, sport, position, height, weight, dominant side, current injury region, and rehabilitation goal. These details are editable later from Profile.
- The web Wellbeing hub supports account-scoped check-ins, sleep records, recovery context, history, trends, and weekly summaries when the Health API is configured. Demo entries exist only in tab memory; browser camera capture is not enabled or requested.
- Health Connect data is fetched only for a signed-in athlete. Home, Wellbeing, and Rehab recovery display recent sleep (48-hour window), heart-rate summary (24-hour window), and same-day steps, labeled with source and record/sync times. An API error is shown rather than replaced with guessed data.
- Rehab simulation and manual sessions are available in the web app. Live ESP32 sensor sessions are handled only by the separate Android client; generated rehabilitation reports, clinician program-authoring screens and medical clearance are not implemented. See [Phase 3 Rehabilitation](./docs/phase3-rehab.md) for web behavior and limits.
- The separate Android client in `android/` implements Phases 4–7 in software, including Health Connect caching and default-off account sync. Android unit tests pass; the APK has intentionally not been packaged pending the user's later APK task. It requires Android Studio/JDK 17/SDK 36 and a local `android/local.properties`; physical hardware and live Supabase validation remain outstanding. See [Android client](./docs/android.md).
- Verified anti-doping sources, skin screening and generated health reports also have intentionally unconfigured states. See [Phase 2 Health](./docs/phase2-health.md) for implemented behavior and limitations.

## Architecture notes

- Web modules: `src/auth.js` (identity provider and session boundary), `src/config.js` (public runtime configuration), and `src/ui.js` (shared accessible UI and role-specific screens).
- Backend routes: versioned under `/api/v1`; user authorization is validated against Supabase Auth and profile roles. Health routes scope operations to the authenticated athlete and use server-only service credentials for writes.
- Database: identity, relationship, and health tables use RLS; Health Connect records are owner-scoped and backend-mediated, and synchronization/access is audited.
- Android is a separate Kotlin/Compose project and uses protected FastAPI endpoints. It never contains service-role credentials or forwards raw movement samples or raw high-frequency heart-rate samples to the backend.

## Project layout

```text
VitaPulse/
├── app.js, config.js, index.html, styles.css
├── src/                    # Browser configuration, Auth and UI modules
├── tests/                  # Web rendering and Auth tests
├── tools/                  # Built-in Node dev server and static build
├── backend/
│   ├── app/                # FastAPI auth, owner-scoped APIs, repositories and OCR services
│   ├── tests/              # API, extraction, upload-validation and configuration tests
│   ├── .env.example
│   └── pyproject.toml
├── supabase/
│   ├── config.toml
│   ├── migrations/         # Identity/profile plus Phase 2–7 health, Rehab, device, wellbeing and Connect schema/RLS
│   └── seed/               # Intentionally no fake personal records
└── docs/                   # Architecture, environment, Phase 2/3 behavior and roadmap
```

The Android Studio client and its implementation status are documented in [Android client](./docs/android.md).

## Current implementation status

The Health web/backend foundation is implemented, with explicit limits where verified data sources or models are not yet configured. OCRmyPDF requires external Tesseract and Ghostscript executables for scanned reports. See [Phase 2 Health](./docs/phase2-health.md). Phase 3 Rehabilitation is implemented in the web/backend foundation, with simulated/manual movement documented in [Phase 3 Rehabilitation](./docs/phase3-rehab.md). Phases 4–7 have software implementations; physical hardware and live Supabase acceptance remain outstanding. Phase 8 automated safety escalation is not implemented because its validated policy and thresholds have not been provided.
