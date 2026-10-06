# Phase 2 Health

Phase 2 adds the first real, owner-scoped health-data APIs and web screens to the web-first VitaPulse app. It does not implement the deferred Android app.

## Included

- Authenticated athlete routes for medical reports, biomarkers, body-map notes, nutrition, medication, anti-doping status, skin-screening availability, health intelligence, and report drafts.
- PDF/JPEG/PNG validation, size and page limits, SHA-256 duplicate detection, private Supabase Storage, signed source links, and upload/source audit events.
- Asynchronous report processing using FastAPI `BackgroundTasks`, page-level extracted text, conservative biomarker extraction, and source-page/source-text provenance.
- Responsive health navigation and screens. Local demo accounts never call health endpoints or display synthetic patient records.
- Read-only authenticated RLS policies for health tables. User writes go through the backend, which verifies the Supabase bearer token and athlete role, scopes every data query to the authenticated athlete, and uses the server-only service-role key for writes.

## Setup

1. Install Python 3.11+ and the backend dependencies:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e ".[dev]"
   ```

   `pyproject.toml` pins OCRmyPDF to upstream commit `10b37915410d63b82a808b15add3ca7288e106f7`.

2. Install **Tesseract OCR** (with the trained data for the configured languages) and **Ghostscript** separately. Both executables must be on the backend process `PATH`. On Windows, Ghostscript is typically exposed as `gswin64c.exe`; Tesseract is typically `tesseract.exe`. OCRmyPDF is a Python package and does not bundle either executable.

3. If `backend/.env` does not already exist, copy `backend/.env.example` to `backend/.env`. Preserve existing secrets; never print, overwrite, commit or place the Supabase service-role key in browser configuration.

4. Set `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` in the backend environment. Set `OCR_ENABLED=true`, `OCRMY_PDF_ENABLED=true`, and `OCR_LANGUAGES` to installed Tesseract language codes. Configure `CORS_ORIGINS` to the exact web origin.

5. Set browser `apiBaseUrl` to the backend origin in `config.js`. Keep `supabaseUrl` and the client-safe publishable key there; never include server credentials.

6. Apply missing migrations to the intended Supabase project in filename order. The initial SQL was already run in the Supabase SQL Editor; do not run it again. Apply `202610060002_athlete_profile_completion.sql` and `202610060003_phase_2_health_foundation.sql` only if each is still pending. For the Phase 3 Rehab schema, apply `202610060004_phase_3_rehabilitation.sql` only if it has not already run. This repository work does not execute SQL against the live project.

7. Start the backend and web app:

   ```powershell
   cd backend
   .\.venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload
   ```

   In a second terminal, run `npm run dev` from the project root.

## OCR and extraction behavior

- The backend validates file signatures and declared MIME type, rejects encrypted/corrupt PDFs and oversized images/PDFs, and caps uploads at the configured limit (default 25 MB) and PDFs at 200 pages.
- PDFs with usable embedded page text are read with pypdf. Otherwise the backend invokes the pinned OCRmyPDF executable as a child process with a timeout and one OCR job. Images are converted to a temporary PDF for the same flow.
- Temporary processing files are removed after processing. The original stays in the private `medical-reports` bucket; page text and extracted observations are stored in owner-scoped tables.
- The initial extractor recognizes a conservative allowlist of analytes and only records numeric values, units, reference ranges, or abnormal flags that are explicitly present in extracted text. Unrecognized or ambiguous lines are not interpreted. LOINC/other standard codes and OCR confidence remain null unless a verified source is added.
- `LOW_QUALITY_TEXT` and `NO_BIOMARKERS_EXTRACTED` are data-quality warnings, not clinical findings. Biomarker trend direction is descriptive and is not a medical interpretation.

## Current availability and limitations

| Surface | Current behavior |
|---|---|
| Medical reports | Upload consent, private storage, async OCR/status, source-linked extraction, expiring source URLs |
| Body map | Body-region navigation and user-entered notes; no automatic injury diagnosis |
| Biomarkers | Source-linked values, explicit source ranges/flags, descriptive history |
| Nutrition | User-entered goals, meals and hydration; no prescribed diet or generated targets |
| Medication | User-entered medication list; no prescribing or drug-interaction claims |
| Anti-doping | Shows `INSUFFICIENT_INFORMATION` until a current, verified prohibited-list source is connected; it never reports no match as clearance |
| Skin screening | Disabled by default. No image upload or assessment model is enabled; visual screening is not diagnosis |
| Health intelligence | Shows only persisted validated items; no generative interpretation engine is wired |
| Health reports | Creates source-validated drafts. PDF rendering and clinical summaries are not implemented |

FastAPI `BackgroundTasks` is process-local and not a durable queue. It is adequate for this initial integration but must be replaced with a durable worker/queue and retry/outbox strategy before production workloads. The initial migration was previously applied in the Supabase SQL Editor. Apply each later migration only if it is pending; local tests do not execute migrations against the live project. Scanned-image OCR was not run locally.
