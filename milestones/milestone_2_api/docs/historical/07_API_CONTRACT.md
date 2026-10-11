# Final Milestone 2 REST API contract (frontend handoff)

**Contract version:** `m2-rest-v1`  
**Base URL:** `http://127.0.0.1:8000`  
**Browser origin:** `http://127.0.0.1:5173`  
**Status:** Implemented and tested with offline fakes. Requires real-S3 acceptance checks before production use.

The previous React teammate handoff contains *proposed* API examples. Use the exact shapes below for M2 integration. The frontend teammate should confirm the contract before final wiring.

## GET /api/health

No parameters. Returns HTTP 200:

```json
{"status":"ok","service":"envirosync-api","aws_checked":false}
```

`aws_checked: false` is intentional: health only proves the local server is running.

## GET /api/datasets

No parameters. Returns HTTP 200. Values below illustrate structure; dates come from the real catalog and will reflect your own published dataset.

```json
{
  "schema_version": "1.0",
  "datasets": [
    {
      "dataset_id": "chennai-daily-weather-era5",
      "city": "chennai",
      "display_name": "Chennai",
      "country": "India",
      "aws_region": "ap-south-1",
      "source": "Open-Meteo",
      "variables": ["temp_max_c", "temp_min_c", "precipitation_mm"],
      "start_date": "2024-01-01",
      "end_date": "2025-12-31",
      "observation_count": 731,
      "timezone": "Asia/Kolkata"
    }
  ]
}
```

Actual response has **both Chennai and London**. The `bucket` and `key` fields are deliberately absent from browser-facing responses.

## GET /api/observations

Required parameters: `city` (chennai/london), `start` (YYYY-MM-DD), `end` (YYYY-MM-DD). **At most 31 inclusive days**. Dates must fall within published catalog coverage.

Example:

```
/api/observations?city=london&start=2025-07-01&end=2025-07-03
```

Response shape (numeric readings are placeholders for illustration only; actual API reads S3):

```json
{
  "city": "london",
  "aws_region": "eu-west-2",
  "metric_units": {"temp_max_c": "°C", "temp_min_c": "°C", "precipitation_mm": "mm"},
  "source": "Open-Meteo",
  "provenance": {"provider": "Open-Meteo", "dataset": "ERA5 historical reanalysis"},
  "dataset_version": "1.0",
  "requested_start": "2025-07-01",
  "requested_end": "2025-07-03",
  "row_count": 3,
  "sha256_verified": true,
  "rows": [
    {"date": "2025-07-01", "temp_max_c": 0.0, "temp_min_c": 0.0, "precipitation_mm": 0.0}
  ]
}
```

The real `provenance` object also includes source URL, retrieval timestamp, attribution and source caveat. The real `rows` array includes every requested date (the example shows only one row for brevity).

**Never copy the example's zero values into UI screens as real measurements.** Display only API-returned rows.

## GET /api/compare

Required parameters: `city1`, `city2` (distinct supported cities); `start`, `end` (ISO date, ≤31 inclusive days). Optional: `metric`, default `temp_max_c`. Valid metrics: `temp_max_c`, `temp_min_c`, `precipitation_mm`.

Example:

```
/api/compare?city1=chennai&city2=london&start=2025-07-01&end=2025-07-03&metric=temp_max_c
```

Illustrative response shape (numbers are **not real values**):

```json
{
  "city1": "chennai",
  "city2": "london",
  "metric": "temp_max_c",
  "unit": "°C",
  "points": [
    {"date": "2025-07-01", "chennai": 30.0, "london": 22.0},
    {"date": "2025-07-02", "chennai": 32.0, "london": null}
  ],
  "missing_policy": "null_means_unavailable",
  "sources": {
    "chennai": {"aws_region": "ap-south-1", "source": "Open-Meteo", "sha256_verified": true},
    "london": {"aws_region": "eu-west-2", "source": "Open-Meteo", "sha256_verified": true}
  }
}
```

In the current validated 2024–2025 dataset, both cities have all dates; `null` only occurs when a selected date is missing from a result. UI must treat `null` as unavailable, never as numeric zero. In this milestone `null` can be exercised with test fixtures, even if it does not appear in real completeness-validated data.

## Error contract

Expected input or remote-data errors use:

```json
{"error":{"code":"DATE_RANGE_TOO_LARGE","message":"Select at most 31 inclusive calendar days."}}
```

Typical codes include `DATASET_NOT_FOUND`, `INVALID_DATE`, `INVALID_DATE_RANGE`, `DATE_RANGE_TOO_LARGE`, `OUTSIDE_DATASET_COVERAGE`, `DUPLICATE_CITIES`, `UNKNOWN_METRIC`, `INVALID_REMOTE_DATA`, `AWS_UNAVAILABLE` and `AWS_REQUEST_FAILED`. Check `docs/06_API_CODE_REFERENCE.md` for mapping.

An undefined endpoint like `/api/predict` presently returns FastAPI's default HTTP 404 response. Prediction must remain disabled in React until the real model exists.

## React hookup (copy into frontend/src/services/api.js)

```javascript
const BASE_URL = import.meta.env.VITE_API_BASE_URL;

async function getJson(path, params = {}, signal) {
  if (!BASE_URL) throw new Error("Missing VITE_API_BASE_URL");
  const url = new URL(path, BASE_URL);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  let response;
  try {
    response = await fetch(url, { signal });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Cannot reach EnviroSync API. Is FastAPI running?");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const message = body?.error?.message ?? body?.detail;
    throw new Error(typeof message === "string" ? message : `API request failed (HTTP ${response.status})`);
  }
  if (body === null) throw new Error("API returned invalid JSON");
  return body;
}

export const getDatasets = (signal) => getJson("/api/datasets", {}, signal);
export const getObservations = (filters, signal) => getJson("/api/observations", filters, signal);
export const getComparison = (filters, signal) => getJson("/api/compare", filters, signal);
```

### JavaScript snippet documentation

- `BASE_URL`: taken from `frontend/.env.local` as `VITE_API_BASE_URL=http://127.0.0.1:8000`. No AWS credentials.
- `getJson`: creates an HTTP URL, appends defined query parameters, supports cancellation through `AbortSignal`, validates HTTP status and JSON, and emits actionable errors.
- `getDatasets`: discover city list, AWS Regions and date coverage.
- `getObservations`: `filters={city,start,end}` → S3-verified rows and provenance.
- `getComparison`: `filters={city1,city2,start,end,metric}` → aligned chart points and source metadata.
- Use `AbortController` in React effects to avoid stale responses when user changes tabs/filters.
- Always show loading, empty and error UI states. Avoid fake success on network failures.

### Contract acceptance checklist

- Both developers approve `temp_max_c`, `temp_min_c`, and `precipitation_mm` as public metric names.
- Selectors use city IDs `chennai` and `london`.
- Date range is constrained to 31 inclusive calendar days and within dataset coverage.
- `points` include keys named after selected city IDs, not generic `a/b`.
- `rows` are named `rows` (not internal `observations`).
- React shows API-provided Region and provenance, never infers from city alone.
- Prediction tab states unavailable until M3 is implemented and API tests pass.
