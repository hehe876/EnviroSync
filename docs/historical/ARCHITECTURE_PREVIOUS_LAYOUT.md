# System architecture and module responsibilities

## Why this is modular rather than three duplicated milestone packages

In the original ZIP, Milestone 2 shipped copies of `settings.py`, `weather.py`, `federation.py` and `cli.py` from Milestone 1B, alongside the newly added API. That independent packaging was convenient for a standalone demo but caused duplicate copies and import-path mistakes when building one repository.

**This codebase is a modular monorepo**. Business modules do not import FastAPI. The FastAPI layer calls one public federation interface. The storage adapter is the only module that calls Boto3. It is **not** microservices: modules currently run within one local Python process and communicate via imports, not HTTP, messaging or additional AWS resources. They can be split into deployed services in a future milestone only if that need justifies latency, IAM, deployment and cost complexity.

| Module | Files | Inputs | Outputs / responsibility | Dependencies |
| --- | --- | --- | --- | --- |
| Config | `config/settings.py` | `.env` / process environment | `Settings` + `City`; strict 2-bucket/2-region allowlist | `python-dotenv` |
| Common | `common/serialization.py` | Python objects | Canonical UTF-8 JSON bytes for SHA-256 | Python stdlib |
| Ingestion | `ingestion/weather.py`, `ingestion/local.py` | Open-Meteo historical ERA5 JSON / date interval | Normalized, validated preview files | Config city model, urllib, common |
| Storage | `storage/s3.py` | Region, bucket, key, bytes | S3 HEAD/GET/PUT, SSE-S3 on PUT; max size | Boto3, config limits |
| Catalog | `catalog/service.py` | Upload manifest entries, S3ObjectStore | S3 catalog, allowlisted discovery | Config, common, injected store |
| Federation | `federation/service.py` | Settings, prepared datasets, optional FakeSession | `publish`, `discover`, `retrieve`; integrity checks | Ingestion validation, catalog, storage |
| API | `api/{app,routes,services,dependencies,errors}.py` | HTTP query, injected federation | Safe REST errors and JSON, no direct S3 | FastAPI, federation |
| CLI | `cli.py` | PowerShell arguments | local fetch/publish/read/verify/compare commands | Config, ingestion, federation |

### End-to-end data flow

1. CLI `fetch` asks Ingestion to download ERA5 historical data for Chennai and London and to reject missing or inconsistent observations.
2. CLI `publish` loads normalized preview files and validates dates. Federation checks bucket regions, writes each dataset with S3ObjectStore, calculates raw-object SHA-256, then asks CatalogService to publish the manifest.
3. A React client requests `/api/datasets` or `/api/observations`. API injects S3Federation and calls CatalogService for the catalog.
4. CatalogService **rejects untrusted region, bucket and key pointers** that do not match the configured city allowlist.
5. Federation selects the correct private bucket, checks SHA-256, validates the entire downloaded dataset and filters the requested dates before returning values.
6. API hides private bucket names in list responses, returns source region and integrity status, and aligns the two city datasets for comparison.

### Exact stable contracts

- S3 data keys are unchanged: `envirosync/v1/datasets/<city>-daily-weather.json`.
- Manifest key is unchanged: `envirosync/v1/catalog/datasets.json` in the **existing Chennai/Mumbai bucket**.
- Historical data schema remains `1.0`, and supported city names remain `chennai` and `london`.
- CLI remains `python -m enviro_sync.cli`.
- FastAPI app remains `enviro_sync.api:app`.
- Core service API remains `S3Federation(settings, session=None).publish/discover/retrieve`.
- HTTP contracts for Milestone 2 are preserved; `GET /api/predict` is absent.

### Module import migration

| Previous import | Current import |
| --- | --- |
| `from enviro_sync.settings import Settings` | `from enviro_sync.config import Settings` |
| `from enviro_sync.weather import normalize_weather` | `from enviro_sync.ingestion import normalize_weather` |
| `from enviro_sync.federation import S3Federation` | **Unchanged** |
| `from enviro_sync.federation import to_json_bytes` | `from enviro_sync.common import to_json_bytes` |
| `from enviro_sync.cli import load_prepared` | `from enviro_sync.ingestion.local import load_prepared` |
| `from enviro_sync.api import app, get_federation` | **Unchanged** |

Old Python import paths under `settings.py`, `weather.py`, and `federation.py` files were intentionally reorganized. External scripts importing those old locations require the adjustments above. No duplicate source copy exists in a milestone folder.

### Important limitations

- Catalog publication happens after both dataset PUTs; on an unexpected partial failure, one regional object may be newer than the published catalog. Retrieval then rejects mismatched SHA-256. There is no transactional S3 rollback.
- Every retrieval re-reads the catalog and complete corresponding S3 dataset (bounded by 2 MB). This is a small hackathon prototype; add caching/partial access only after measuring real needs.
- ERA5 is **reanalysis/model-derived historical data**, not municipal sensors, live weather predictions, or real-time alerts.
- Local development only. No user auth, request quotas, or hardened internet-hosted deployment.

## Included React layer

`frontend/` is now a real Vite + React module rather than a future handoff. It calls the read-only FastAPI contract through a browser-safe HTTP helper (`frontend/src/lib/api.mjs`) with a Vite proxy for local development. The browser is intentionally isolated from Python, Boto3, AWS credentials and bucket names. The frontend uses live catalog metadata to constrain filters and fetches the two-city chart, raw readings and integrity status from the API. Failure states are explicit; the bundled historical example JSON never silently supplies chart data.
