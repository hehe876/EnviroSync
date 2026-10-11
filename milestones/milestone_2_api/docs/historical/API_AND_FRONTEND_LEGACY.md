# Milestone 2 API + React UI (included)

## Architecture and boundaries

The React app is a real, included part of the EnviroSync modular monorepo. `frontend/src/App.jsx` issues GET requests through `frontend/src/lib/api.mjs`; it does not import backend Python code. The FastAPI layer calls the Milestone 1B federation, catalog and S3 adapter. The browser never receives AWS credentials or bucket names. React is client-side only and requires no new AWS resources.

## Start both servers on Windows 11 (two terminals)

From the repository root, first install dependencies with `./scripts/setup.ps1` (backend) and `./scripts/setup-frontend.ps1` (React).

Terminal 1:

```powershell
.\scripts\start-api.ps1
```

Terminal 2:

```powershell
.\scripts\start-frontend.ps1
```

Visit http://127.0.0.1:5173 and optionally http://127.0.0.1:8000/docs. Frontend `/api` calls are proxied by Vite to Python port 8000; no manual `PYTHONPATH` setting is needed. For a custom API URL, use `frontend/.env.local` with `VITE_API_BASE_URL=...`. No AWS access key should ever use a `VITE_` prefix because Vite includes those variables in client code.

## Existing read-only endpoints

| Endpoint | Parameters | UI usage | S3 request? |
| --- | --- | --- | --- |
| `/api/health` | none | API status LED | No |
| `/api/datasets` | none | City cards, date coverage and available regions | Yes |
| `/api/observations` | `city`, `start`, `end` | Daily readings, period averages, source/integrity | Yes |
| `/api/compare` | `city1`, `city2`, `start`, `end`, `metric` | Two-city series chart and CSV | Yes |

`metric` is `temp_max_c`, `temp_min_c`, or `precipitation_mm`. Dates are canonical ISO `YYYY-MM-DD`, chronological, within *both* selected cities' coverage and no longer than 31 inclusive days. Errors use `{"error":{"code":"...","message":"..."}}`. The UI renders the returned error; it does not secretly load example JSON. Read-only AWS operations may incur charges under the account's applicable terms; the frontend does not create or publish objects.

## Verification

Run `./scripts/check-fullstack.ps1` after both installs. That script checks Python integration tests, Node frontend unit tests, and the Vite production build. Then check the following manually:

1. Start Python and React; `/api/health` should show online and the city cards should reflect `/api/datasets`.
2. Verify the catalog really exists in S3; health alone is not sufficient.
3. Load both cities over a valid overlapping period; comparison chart and table must contain S3-returned values.
4. Change metric, apply, and check the chart changes according to `/api/compare`.
5. Export CSV and verify it matches actual returned series, with no made-up rows.
6. Stop the API and refresh; UI must display a failure, never synthetic data.
7. Restore the API but invalidate the catalog access; health should work while the dataset view correctly reports a failure.

For offline testing of Python responses, use the existing fake in-memory S3 test fixture, not a fake frontend. Not implemented: authentication, forecasts, live sensor feeds, map or ML prediction endpoints.

### Opt-in real-AWS integration smoke test

With the configured FastAPI running and published S3 data accessible, run from repository root:

```powershell
.\scripts\smoke-live-api.ps1
```

This command **will make real S3 GET requests** through the API, which can incur AWS charges. It performs no writes. It fails when the catalog is missing, fewer than two datasets are published, the regions do not differ, observations are missing, or either dataset fails SHA-256 verification. It uses the datasets' *actual* overlapping coverage, rather than making assumptions about the current year.
