# Milestone 2 — FastAPI gateway (Python block)

**Owns:** local read-only REST endpoints, API date validation, errors, dependency injection and region-aligned series presentation.
**Depends on:** the existing Milestone 1B federation service. No duplicate ingestion, catalog, or AWS code lives here.

## Files

- `app.py` — FastAPI composition root, local CORS and error-handler registration.
- `routes.py` — `/api/health`, `/api/datasets`, `/api/observations`, `/api/compare`.
- `services.py` — API-specific interval checks and response formats.
- `dependencies.py` — constructs the *real* Milestone 1B S3Federation via dependency injection.
- `errors.py` — stable client-friendly errors; no credentials/bucket leakage.
- `tests/test_api.py` — API behavior with simulated S3.
- `tests/test_modular_integration.py` — negative controls: removing catalog or regional data causes failure.
- `tests/test_block_architecture.py` — API imports actual Milestone 1B type and exposes intended endpoints.

## Commands (root)

```powershell
.\.venv\Scripts\python.exe -m pytest milestones/milestone_2_api/tests -v
.\scripts\start-api.ps1
```

Then visit http://127.0.0.1:8000/docs. The `/api/health` endpoint is **local-only** and does not confirm S3 objects exist. The other data routes require genuine published S3 objects, correct IAM and a valid root `.env`.
