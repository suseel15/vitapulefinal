# Environment and secrets

## Browser-safe configuration

`config.js` is public runtime configuration. It may contain:

- `apiBaseUrl`
- `supabaseUrl`
- `supabasePublishableKey`
- `demoModeEnabled` (local loopback only)

The Supabase publishable key is intended for client use in conjunction with RLS. It is not an authorization mechanism. Never place a service-role key, database credential, Gemini key, SMTP password, or FCM private key in browser code. Demo mode is permitted only on `localhost` or `127.0.0.1`, displays a persistent warning, and creates local synthetic sessions only.

The Health UI requires a valid HTTPS (or local loopback HTTP) `apiBaseUrl` and real Supabase athlete session. Demo sessions cannot access health records.

## Backend

Copy `backend/.env.example` to `backend/.env` only when it does not already exist. Settings include app name/environment, API prefix, host/port, Supabase URL and publishable key, server-only service-role key for protected health writes, OCR configuration, private storage and signed-link settings, feature flags, CORS origins, email/FCM toggles, emergency escalation (off by default), demo mode (off by default), and log level.

Scanned-report OCR additionally requires Tesseract and Ghostscript executables installed on the backend host and available on `PATH`; see [Phase 2 Health](./phase2-health.md).

`.env` files are ignored. Preserve any existing local `.env` when updating setup; never overwrite, print, log, or commit its credential values.

The local static server exposes only the web entry point, runtime config, styles, app module and JavaScript modules under `src/`; backend files and environment files are not served. Production hosting must apply equivalent restrictive content and security headers.

## Android (later)

No native Android client or `local.properties` is part of this web-first build. When the Android Studio phase begins, use local ignored configuration for the API URL and Supabase publishable key only. Service-role, Gemini, SMTP, and FCM private keys must remain server-side.
