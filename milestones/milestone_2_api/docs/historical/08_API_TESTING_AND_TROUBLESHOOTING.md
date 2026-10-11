# Milestone 2 — Testing, troubleshooting and cleanup

## Offline tests (no AWS calls)

Run from the `EnviroSync_Milestone_2_API` root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: **32 passed**.

The 15 inherited Milestone 1B tests cover the weather contract, S3 catalog/publishing validation, SHA-256 verification, date handling and CLI safety. The additional 17 Milestone 2 API tests cover:

1. Health route does not touch AWS.
2. Dataset listing exposes two separate AWS Regions and omits private bucket names.
3. London route returns actual fake-session regional values with checksum verification.
4. Cross-region compare aligns max temperature records.
5. Rainfall comparison maps units correctly.
6–10. Reject unknown city, invalid dates, inverted dates, out-of-coverage requests, and >31-day ranges.
11. Return 422 JSON for required query fields missing.
12–13. Reject same-city comparisons and unknown metrics.
14. Allow only the intended local Vite CORS origin.
15. Prediction route correctly absent until genuine ML implementation.
16. Reject unauthorized or forged catalog bucket pointers.
17. Reject tampered regional dataset bytes.

These tests use the in-memory `FakeSession`/`FakeS3` from `tests/conftest.py` and dependency overrides in FastAPI; no AWS profile is needed for unit tests.

## Live acceptance verification

**Prerequisite:** 1B `verify` already passed against AWS and you have checked remaining applicable S3 request/free usage. Start `uvicorn` with `--host 127.0.0.1 --port 8000`. Then, in another PowerShell terminal:

| Test | Request | Expected |
| --- | --- | --- |
| API-01 | `/api/health` | 200; `aws_checked:false` |
| API-02 | `/api/datasets` | 200; Chennai in `ap-south-1`, London in `eu-west-2` |
| API-03 | `/api/observations?city=london&start=2025-07-01&end=2025-07-03` | 200; three real rows and `sha256_verified:true` |
| API-04 | `/api/compare?city1=chennai&city2=london&start=2025-07-01&end=2025-07-07` | 200; seven aligned points, two Region IDs |
| API-05 | `/api/observations?city=london&start=2025-07-03&end=2025-07-01` | 400; `INVALID_DATE_RANGE` |
| API-06 | `/api/observations?city=unknown&start=2025-07-01&end=2025-07-02` | 404; `DATASET_NOT_FOUND` |
| API-07 | `/api/predict?city=london` | 404; not implemented yet |
| API-08 | React at `127.0.0.1:5173` calls `/api/datasets` | Browser receives real JSON without CORS error |

Do not claim live verification completed until you observe these results against your own S3 account.

## Common problems and exact fixes

| Symptom | Likely cause | What to check |
| --- | --- | --- |
| `ModuleNotFoundError: fastapi` | Installing with wrong Python executable | Run `.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt` in M2 folder. |
| `ModuleNotFoundError: enviro_sync` | Wrong working directory | Run Uvicorn from M2 root, not `enviro_sync/` subfolder. |
| `CONFIGURATION_ERROR` | Missing/incorrect `.env` | Copy the same `.env` used in 1B; check Mumbai/London Regions. |
| `AWS_UNAVAILABLE` | No AWS credential chain or networking | Verify `aws sts get-caller-identity`, `AWS_PROFILE`, internet and profile session. |
| `AWS_REQUEST_FAILED` | S3 IAM deny, missing key, wrong bucket, etc. | Re-run `python -m enviro_sync.cli verify` in Milestone 1B; inspect AWS permissions and CloudTrail if available without enabling extra paid services. |
| `INVALID_REMOTE_DATA` | Catalog pointer mismatch or SHA-256 mismatch | Run 1B `verify`; check that no regional object was edited without updating catalog and provenance through controlled publication. |
| `OUTSIDE_DATASET_COVERAGE` | Date outside actual catalog | Query `/api/datasets` and use dates inside its `start_date`/`end_date`. |
| `DATE_RANGE_TOO_LARGE` | More than 31 dates inclusive | Reduce the selected range; e.g. 2025-07-01 through 2025-07-31 = 31 dates. |
| React browser CORS error | React served on a different origin/port | Run Vite at `127.0.0.1:5173` or discuss exactly allowed origin with backend developer. Do not use insecure browser flags. |
| `ERR_CONNECTION_REFUSED` | Backend off or wrong port | Check Uvicorn running at `127.0.0.1:8000`, then open `/docs`. |
| Browser reports broken JSON fields | Teammate used provisional handoff example names | Use `docs/07_API_CONTRACT.md` final names; request via browser Network tab. |
| Prediction 404 | No ML model deployed yet | Expected. Do not display a fabricated prediction; wait for Milestone 3. |

## Resource and billing safety

- Uvicorn, FastAPI, HTTPX and Pytest execute locally; launching the server alone does not make S3 requests (the health endpoint does not either).
- `/api/datasets` performs at least one S3 catalog `GetObject` request. `/api/observations` fetches the catalog plus the regional object; `/api/compare` fetches catalog and both regional objects (currently catalog validation also occurs inside each `retrieve`, so multiple catalog GETs may occur). **Do not configure the frontend to poll every few seconds.**
- Do not enable API Gateway, Lambda, public bucket access, CloudFront, S3 replication, EC2 or additional resources for this milestone.
- Monitor AWS Billing and Free Tier usage; AWS Budgets are alerts, not hard cost caps.
- No new AWS resources are created, so milestone cleanup is just `Ctrl+C` to stop Uvicorn and optionally remove the local M2 directory. **Do not delete your existing 1B S3 buckets or data**, since future milestones need them.

## What not to claim

- Localhost is not a globally accessible production deployment.
- The project has two AWS geographic regions but does not yet federate independent organizations/accounts.
- The source data is Open-Meteo ERA5 historical reanalysis; it is not municipal sensors and not guaranteed ground-truth measured rainfall at exact street locations.
- The API is working federation, not working ML inference until the next milestone.
