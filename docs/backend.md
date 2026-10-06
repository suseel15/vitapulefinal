# Backend

The FastAPI app requires Python 3.11+. Install from `backend/` with `pip install -e ".[dev]"`, then run `uvicorn app.main:app --reload`.

Health APIs additionally require `SUPABASE_SERVICE_ROLE_KEY` in the protected backend environment. Never expose that key to the browser.

| Method | Path | Authentication | Purpose |
|---|---|---|---|
| GET | `/health` | None | Process liveness |
| GET | `/ready` | None | Supabase configuration and reachability |
| GET | `/api/v1/health` | None | Versioned liveness |
| GET | `/api/v1/ready` | None | Versioned dependency readiness |
| GET | `/api/v1/me` | Supabase bearer token | Return the authenticated caller's profile |
| GET | `/api/v1/health/overview` | Athlete bearer token | Owner-scoped health summary |
| GET/POST | `/api/v1/health/medical-reports` | Athlete bearer token | List reports or upload with explicit processing consent |
| GET/DELETE | `/api/v1/health/medical-reports/{id}` | Athlete bearer token | Read report metadata/measurements or delete a report |
| POST | `/api/v1/health/medical-reports/{id}/source` | Athlete bearer token | Create a short-lived signed source URL |
| GET | `/api/v1/health/biomarkers` | Athlete bearer token | List measurements and descriptive trend directions |
| GET | `/api/v1/health/biomarkers/{name}` | Athlete bearer token | Read a biomarker history |
| GET/POST | `/api/v1/health/body-map` and `/findings` | Athlete bearer token | Read regions/notes or add a user-entered note |
| GET | `/api/v1/health/health-intelligence` | Athlete bearer token | Read persisted items and engine status |
| GET/PUT | `/api/v1/health/nutrition/profile` | Athlete bearer token | Read or update a user-set nutrition goal |
| GET/POST | `/api/v1/health/nutrition/entries` | Athlete bearer token | Read or add nutrition entries |
| GET/POST/PATCH/DELETE | `/api/v1/health/medications` | Athlete bearer token | Manage the user's medication list |
| GET | `/api/v1/health/anti-doping` | Athlete bearer token | Read reviews and verified-source availability |
| GET | `/api/v1/health/skin-screening` | Athlete bearer token | Read records and feature availability |
| GET/POST | `/api/v1/health/reports` | Athlete bearer token | List or create a source-validated report draft |

Responses use `{ success, data, error, requestId }`. Readiness returns 503 when required Supabase settings are missing or the identity provider cannot be reached. The backend never accepts a client-supplied role as proof of authorization.

Scanned reports require OCRmyPDF, Tesseract and Ghostscript. Processing currently uses FastAPI `BackgroundTasks` and is not durable across process restarts. See [Phase 2 Health](./phase2-health.md) for configuration and limitations.
