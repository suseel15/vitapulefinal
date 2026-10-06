# VitaPulse architecture

## Current product boundary

The current deliverable is the web application and its initial FastAPI/Supabase foundation. Android Studio work is the next delivery step, not part of this web build. The feature model remains platform-independent: authenticated profile → role-gated feature → repository/API or RLS-protected data → history/report integrations later.

## Web

- `app.js` coordinates authentication state, page navigation, connectivity and interactions.
- `src/config.js` reads only public browser configuration.
- `src/auth.js` owns Supabase Auth calls and minimal session state. It does not grant data access based on locally stored role values.
- `src/ui.js` contains shared components, athlete feature shells and a distinct clinician shell.
- `styles.css` defines centralized light-first tokens, dark mode and responsive layouts, including the five-destination mobile bottom bar.
- `tools/serve.mjs` and `tools/build.mjs` use Node built-ins only.

## Backend and trust boundaries

FastAPI exposes request-ID-correlated response envelopes, health/readiness endpoints, and a protected current-account endpoint. Protected routes validate the Supabase access token through the Supabase Auth user endpoint, then retrieve the role using the same user bearer token. Role checks use the database profile, not a request-body field. Internal error details and credentials are not returned to clients.

Supabase is authoritative for identities and profile data. A trusted database trigger creates a profile on signup. Only server-controlled `app_metadata` may provision a doctor/admin role; `user_metadata` can request doctor verification but cannot grant privileges. RLS limits profiles to their owner, authorized doctor relationships, or controlled admin access.

## Future architecture seams

Future modules should add their own typed API/data contracts and repositories for health, rehab, movement, wellbeing, reports and doctor review. ESP32 polling/WebSocket implementations, CameraX, Health Connect, report generation and AI providers are not active integrations in this web phase. Gemini calls and other secrets belong only on the backend.

`backend/app/services/contracts.py` defines typed `MovementDataSource`, `ReportGenerator`, `AIProvider` and consent-bound camera assessment seams. These are interfaces only; they do not return generated reports, sensor data, or camera assessments.
