# Milestone boundary, review demonstration and cleanup

## What the module definitely implements

1. Fetch real ERA5 historical reanalysis records for Chennai and London through the official Open-Meteo API.
2. Validate a continuous two-year daily dataset for each city, including source metadata and units.
3. Store Chennai observations in an already-created Mumbai S3 bucket, London observations in an already-created London S3 bucket.
4. Publish a global **catalog** in Mumbai with dataset-to-region location pointers and checksums.
5. Discover and retrieve either dataset from one authenticated Python interface without cross-region data replication.
6. Verify every downloaded regional dataset against catalog SHA-256 and schema validation.
7. Query selected date ranges and generate a simple date-aligned, two-city comparison in the CLI.
8. Pass 15 offline tests that cover major happy paths and failure paths.

## What this module does NOT implement

- React frontend, deployed REST API, deployed ML model, scheduled/automatic ingestion, streaming data or API hosting.
- Multi-organization identities, delegated trust, independent government databases, consent workflow or production data residency guarantees.
- Guaranteed zero AWS charge, globally high-available catalog or fully atomic distributed publication.
- Government-sourced live station data: both example datasets come from **one** third-party global weather reanalysis source. They are published to geographically different S3 buckets for a technically faithful demonstration.
- Validated superiority of cross-city ML forecasting: ML training and independent test evaluation belong to the later milestone.

## Five-minute judge demonstration

1. Show AWS S3 buckets in `ap-south-1` and `eu-west-2`, both private and separately regioned.
2. Show real preview JSON with source and ERA5 provenance, not fabricated weather readings.
3. Run `discover`: demonstrate lightweight catalog references without copying London's entire dataset to Mumbai.
4. Run `read --city london`: explain how Boto3 selects the `eu-west-2` endpoint, retrieves London object, and verifies SHA-256.
5. Run `verify`: show source-region proofs and complete integrity results.
6. Run `compare`: explain shared-date comparisons across local-time daily aggregates and emphasize limited scientific interpretation.
7. Show the remaining milestones clearly: FastAPI HTTP gateway, React UI and evaluated ML forecasting.

## Handoff to Milestone 2 (FastAPI backend)

- Import and reuse `Settings`, `S3Federation.discover()` and `S3Federation.retrieve()`. Do not rebuild a parallel S3 SDK layer or expose AWS credentials in React.
- Wrap SDK errors as explicit HTTP status codes and consistent JSON error payloads.
- Validate query dates **before** calling S3 so invalid clients do not create avoidable requests.
- Keep a bounded response size and use the existing source-provenance fields.
- Agree on an OpenAPI schema with the React teammate before they connect live data.
- Add FastAPI `TestClient` route tests, including real error propagation; unit tests stay offline.

## Handoff to Milestone 3 (ML)

- Use the **actual** retrieved daily datasets. Create lagged-temperature predictors only from previous dates; avoid target leakage.
- Train on 2024 and evaluate on previously unseen 2025 data per city. Report MAE against persistence and no improvement claims without measured evidence.
- Record model version, training span, features, external data provenance and limitations.
- Run inference through a real callable module; do not display random, hardcoded or fabricated forecasts.

## Controlled cleanup: when the whole project is finished

Do NOT delete datasets before the frontend and ML milestones are validated.

To remove only this milestone's three S3 objects, substitute your **actual** existing bucket names in the following PowerShell commands. Review each value before running. These commands do **not** delete buckets or the Milestone 1A smoke-test object.

```powershell
aws s3api delete-object --bucket ACTUAL_INDIA_BUCKET --key envirosync/v1/datasets/chennai-daily-weather.json --region ap-south-1
aws s3api delete-object --bucket ACTUAL_INDIA_BUCKET --key envirosync/v1/catalog/datasets.json --region ap-south-1
aws s3api delete-object --bucket ACTUAL_LONDON_BUCKET --key envirosync/v1/datasets/london-daily-weather.json --region eu-west-2
```

If S3 bucket versioning was enabled outside this project, a simple delete may add a delete marker rather than permanently deleting all stored versions; inspect versioning and billing before asserting cleanup is complete. Do not run generic `aws s3 rm --recursive` against unrelated keys.

Optional local cleanup removes previews but does not touch AWS:

```powershell
Remove-Item .\preview -Recurse -Force
```

The actual AWS account owner controls whether to keep or delete the two demo buckets after all milestones are finished.
