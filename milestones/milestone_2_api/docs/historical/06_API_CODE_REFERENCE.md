# Milestone 2 — API code reference

This document explains the source code in `enviro_sync/api.py`. It builds on the existing, unmodified Milestone 1B code in `settings.py`, `federation.py`, and `weather.py`. See `docs/01_CODE_REFERENCE.md` for those lower-level functions.

## Responsibility and data flow

`api.py` owns **HTTP protocol, input validation, response shaping and safe failure reporting**. It does not download Open-Meteo data, upload objects, bypass the catalog, expose AWS credentials or duplicate regional S3 access logic.

1. Browser calls a FastAPI route with city, date range and optionally comparison metric.
2. `get_federation` constructs `Settings` from local `.env` and makes an `S3Federation` client using the default Boto3 AWS credential chain.
3. Route calls `federation.discover()` to fetch and validate the Mumbai catalog.
4. Route checks city against a strict allowlist and requested coverage against catalog dates.
5. `federation.retrieve()` uses the catalog entry to address the right S3 Region/bucket/key, verifies SHA-256 and validates the entire dataset.
6. Route maps underlying field names to the approved frontend contract, returning actual observations.
7. Errors are converted to safe JSON with a stable `error.code`.

### API dependency versions

- Python 3.12.
- FastAPI ≥0.115, `<1` (ASGI request handling, `Query`, error handlers, OpenAPI).
- Uvicorn ≥0.30, `<1` (local ASGI server).
- Boto3 ≥1.34, `<2` + Botocore (S3 clients + error types).
- `python-dotenv` ≥1, `<2` (`.env` loading).
- Pytest ≥8, `<10`, HTTPX ≥0.27, `<1` (offline tests using FastAPI `TestClient`).

## Function-by-function explanation

| Element | Inputs | Output | Behavior / failure handling |
| --- | --- | --- | --- |
| `METRICS` | Metric identifier | Original S3 field name and physical unit | Strict supported set; stops unknown metrics from reaching internal logic. |
| `ApiProblem` | HTTP status, stable error code, human-facing explanation | Exception | Signals expected input errors without leaking internal details. |
| `error_response` | Status/code/message | JSONResponse | Standard schema `{ "error": { "code": ..., "message": ... } }`. |
| `get_federation` | Local `.env` and AWS CLI credentials | Shared S3Federation client | `lru_cache` avoids creating new clients per request. Invalid bucket/Region settings return configuration error. |
| `checked_city` | Requested city + `federation.settings.cities` | Normalized city name | Only registered `chennai` and `london`; rejects other locations with HTTP 404. |
| `checked_dates` | ISO `start` and `end` strings | Parsed dates | Requires exact `YYYY-MM-DD`, chronological order, no more than 31 inclusive days. |
| `checked_catalog` | Federation service | Validated catalog | Trust boundary: catalog pointer and schema are validated by existing Milestone 1B code. |
| `entry_for_city` | Catalog + approved city | Catalog entry | Locates known city after validated discovery. |
| `ensure_coverage` | Catalog, city, start/end | Catalog entry | Prevents retrieval outside published coverage. |
| `normalize_row` | Internal weather observation dict | Frontend-compatible row | Maps `max_temp_c` → `temp_max_c` and `min_temp_c` → `temp_min_c`; no values fabricated. |
| `align_series` | Two verified result objects + metric | Comparison JSON | Date-key alignment; absent values become JSON `null`, never zero. Returns provenance and integrity status for both datasets. |
| `health` | None | Process health JSON | Explicit `aws_checked:false`; does not consume S3 requests. |
| `datasets` | Dependency-injected federation | Catalog summary | Lists actual registered source data and Regions; omits bucket names and keys. |
| `observations` | `city`, `start`, `end` | Verified regional rows | Reads real stored bytes and returns units, source/provenance, row count, region and SHA-256 status. |
| `compare` | `city1`, `city2`, `start`, `end`, `metric` | Aligned points | Requires distinct known cities and a supported metric, then reads each region. |

## Exception handling

| Condition | HTTP status | `error.code` | What to do |
| --- | --- | --- | --- |
| Unknown city | 404 | `DATASET_NOT_FOUND` | Select Chennai/London or publish supported city in future milestone. |
| Malformed/missing query field | 422 or 400 | `INVALID_QUERY` / `INVALID_DATE` | Check `/docs` and use exact dates. |
| End precedes start | 400 | `INVALID_DATE_RANGE` | Fix start/end order. |
| Range greater than 31 days | 400 | `DATE_RANGE_TOO_LARGE` | Choose a shorter interval. |
| Outside stored dataset dates | 400 | `OUTSIDE_DATASET_COVERAGE` | Use dates from `/api/datasets`. |
| Same city for comparison | 400 | `DUPLICATE_CITIES` | Pick two different locations. |
| Unknown metric | 400 | `UNKNOWN_METRIC` | Use one of the three published metrics. |
| S3 IAM/object failure | 502 | `AWS_REQUEST_FAILED` | Verify AWS permissions, objects, profile and Regions. |
| AWS SDK/connectivity failure | 503 | `AWS_UNAVAILABLE` | Check credentials/network. |
| Invalid `.env` | 503 | `CONFIGURATION_ERROR` | Fix local bucket/Region settings. |
| Corrupted catalog/data | 502 | `INVALID_REMOTE_DATA` | Rerun Milestone 1B `verify`; republish only if necessary and authorized. |
| `/api/predict` (not shipped) | 404 | Default FastAPI not-found response | Prediction is implemented in Milestone 3, not mocked here. |

## Security rationale

- Server binds to `127.0.0.1` only for development. No public interface or cloud hosting is added.
- Explicit CORS allowlist: localhost and 127.0.0.1 on port 5173. CORS does not authenticate clients; binding to loopback helps limit network exposure.
- IAM credentials stay on the backend machine, fetched from the AWS credential provider chain; never passed to React.
- API responses intentionally omit raw S3 bucket names, object keys and authorization material.
- Milestone 1B verifies the regional bucket mapping and SHA-256 hashes before returning data. The catalog stores the expected hashes, so integrity is relative to the catalog (not a tamper-proof external authority).
- All operations are **read-only** (no `PUT`, `POST`, bucket creation, or object update routes).
- Request date windows limited to 31 inclusive calendar days; underlying object reads still fetch the full small JSON file to verify it.

## Running and verifying

See the exact PowerShell commands in `README.md`, sections 3–6. Test with `pytest` first (no AWS), then `GET /api/health`, then real catalog and regional observation/compare calls. Check logs if an AWS request fails; no credentials should be logged.
