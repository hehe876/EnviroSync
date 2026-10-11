# Data schemas and contract for future FastAPI/React integration

This milestone publishes **actual** historical weather reanalysis, not mock records. The following examples are **structural examples only**, with illustrative numbers. They do not represent observations retrieved during this document's generation.

## Normalized dataset object (stored in its owning AWS Region)

S3 key: `envirosync/v1/datasets/{city}-daily-weather.json`.

```json
{
  "schema_version": "1.0",
  "dataset_id": "london-daily-weather-era5",
  "city": "london",
  "country": "United Kingdom",
  "coordinates": {"latitude": 51.5074, "longitude": -0.1278},
  "data_timezone": "Europe/London",
  "start_date": "2024-01-01",
  "end_date": "2025-12-31",
  "observation_count": 731,
  "source": {
    "provider": "Open-Meteo",
    "dataset": "ERA5 historical reanalysis",
    "url": "THE_ACTUAL_OPEN_METEO_REQUEST_URL",
    "retrieved_at_utc": "ACTUAL_UTC_TIMESTAMP",
    "attribution": "Open-Meteo (open-meteo.com); ERA5 / Copernicus Climate Change Service",
    "note": "Model-derived historical reanalysis, not municipal sensor measurements"
  },
  "observations": [
    {"date": "2024-01-01", "max_temp_c": 9.0, "min_temp_c": 3.0, "precipitation_mm": 1.2}
  ]
}
```

*The shown example has only one illustrative record and is not itself schema-valid for the stated observation count; real JSON always contains the complete requested interval.*

All actual records have the same fields, with a full, chronologically ordered daily series. Null values, duplicate dates, nonfinite measurements, negative precipitation, and invalid max/min ordering are rejected.

## Catalog object (stored only in Mumbai)

S3 key: `envirosync/v1/catalog/datasets.json`.

```json
{
  "schema_version": "1.0",
  "project": "EnviroSync Federation",
  "generated_at_utc": "ACTUAL_UTC_TIMESTAMP",
  "datasets": [
    {
      "dataset_id": "london-daily-weather-era5",
      "city": "london",
      "country": "United Kingdom",
      "region": "eu-west-2",
      "bucket": "ACTUAL_LONDON_BUCKET",
      "key": "envirosync/v1/datasets/london-daily-weather.json",
      "start_date": "2024-01-01",
      "end_date": "2025-12-31",
      "observation_count": 731,
      "timezone": "Europe/London",
      "source": "Open-Meteo",
      "sha256": "ACTUAL_64_CHARACTER_HEX_DIGEST",
      "size_bytes": 12345
    }
  ]
}
```

*The illustrative catalog shows only the London entry for brevity. The **actual catalog requires exactly two entries**: Chennai/Mumbai and London/London. `size_bytes` and SHA-256 are computed from real object bytes.*

## Retrieval response for a Python consumer

`S3Federation.retrieve("london", "2025-07-01", "2025-07-03")` returns:

```json
{
  "city": "london",
  "region": "eu-west-2",
  "bucket": "ACTUAL_LONDON_BUCKET",
  "source": {"provider": "Open-Meteo", "dataset": "ERA5 historical reanalysis"},
  "start_date": "2024-01-01",
  "end_date": "2025-12-31",
  "total_records": 3,
  "sha256_verified": true,
  "observations": [
    {"date": "2025-07-01", "max_temp_c": 23.1, "min_temp_c": 13.6, "precipitation_mm": 0.2}
  ]
}
```

*Illustrative, abbreviated response. The real `source` object includes URL, retrieved timestamp, attribution and provenance note; `observations` would contain all three requested daily records.*

## Frontend/backend alignment — not yet an implemented HTTP API

The React teammate must **not** call S3 from the browser, embed AWS secrets, or claim these CLI commands are public HTTP routes. Milestone 1B only exposes a **Python API** (`S3Federation`) and a local CLI. The FastAPI REST gateway will be implemented in Milestone 2 and should use this service's existing data contract.

Recommended API contracts for later review with frontend teammate:

- `GET /api/datasets`: catalog dataset listings with city, region, coverage and provenance.
- `GET /api/observations?city=london&start=2025-07-01&end=2025-07-07`: filtered retrieval response.
- `GET /api/compare?city1=chennai&city2=london&start=2025-07-01&end=2025-07-07`: aligned daily data (date + values for each city).
- `GET /api/predict?city=london`: only after ML is actually trained and evaluated.

These are **proposed**, not deployed. Treat HTTP field names and errors as unapproved until the backend milestone provides exact OpenAPI `/docs` contracts and passing tests.

## Meaningful federated data sharing

Our S3 catalog lists *where* datasets are and *which schema/provenance* each has. Only selected datasets are downloaded for analysis; there is no required replication to the catalog Region. For this prototype, the two city datasets are published under **one AWS account** from a **single original public API**. That distinction must remain visible in the presentation; future cross-account interoperability is a separate milestone.
