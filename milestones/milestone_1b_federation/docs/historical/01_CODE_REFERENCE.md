# Code-by-code reference and operating protocols

This reference describes **every Python source module**, its principal functions, inputs, outputs, dependencies, exceptions and verification. Keep this document updated when changing the code.

## `enviro_sync/settings.py` — configuration

**Purpose:** Enforce that the repository references the two already-created private S3 buckets and AWS Regions. Prevent accidental upload to a mistyped region or identical bucket.

**Inputs:** `.env` (`INDIA_BUCKET`, `LONDON_BUCKET`, `INDIA_REGION`, `LONDON_REGION`). Values already set in the PowerShell process have precedence over the `.env` file.

**Outputs:** A `Settings` instance with two `City` records, exact bucket/region pairs, city coordinates, historical-data timezone, and fixed project-managed S3 keys.

**Key components:**

- `City`: immutable dataclass holding `name`, `country`, geographic coordinates, timezone, bucket and region.
- `City.key`: data path in the relevant region: `envirosync/v1/datasets/{city}-daily-weather.json`.
- `Settings.__init__`: reads `.env`, rejects missing or malformed bucket names, rejects region changes and identical bucket names. Does not connect to AWS.
- `Settings.city(name)`: resolves only `chennai` or `london`; raises `ValueError` for unknown names.
- `CATALOG_KEY`: `envirosync/v1/catalog/datasets.json` in the **India bucket**.
- `MAX_JSON_BYTES`: safety limit of two million bytes per stored/retrieved JSON object.

**Verify:** `.venv\\Scripts\\python.exe -m pytest -q`. Do not add raw AWS keys to `.env` or Git.

## `enviro_sync/weather.py` — source ingestion and validation

**Purpose:** Retrieve genuine daily weather reanalysis (not municipal measurements), validate the entire interval, and produce a stable, documented dataset schema.

**Inputs:** A `City`, start date, end date, and the actual HTTPS JSON response from Open-Meteo's `archive-api.open-meteo.com/v1/archive` with `models=era5`.

**Outputs:** A JSON-serializable dict including city, local dates, max/min 2-m temperature in Celsius, daily precipitation in millimeters, source URL, retrieval timestamp, model name, attribution and observed count.

**Key functions:**

- `parse_interval(start, end)`: checks valid dates, chronological order, historical end date, and <= 801 days.
- `fetch_weather(city, start, end)`: makes **one network call** to the external Open-Meteo API, specifies explicit units, timezone, ERA5, and three daily variables. Limits response size and sets a 40-second timeout. Converts network/HTTP errors to explanatory failures.
- `normalize_weather(city, start, end, response, url)`: transforms daily arrays into date-keyed observations; rejects missing dates, empty arrays, wrong timezone, wrong units, null measurements, physically impossible min/max ordering and negative precipitation. This function itself does not use the internet.
- `validate_dataset(data, city)`: checks previously normalized/local/S3 data before publication or after retrieval; checks counts, continuous dates, provenance, unit-bearing field names and numerical validity.

**Source field definitions:**

- `max_temp_c`: ERA5 daily maximum air temperature at 2 m in °C.
- `min_temp_c`: ERA5 daily minimum air temperature at 2 m in °C.
- `precipitation_mm`: ERA5 daily precipitation sum in mm.
- `data_timezone`: city-specific timezone; daily windows align to **local calendar days** (Chennai: Asia/Kolkata; London: Europe/London), not necessarily the same UTC intervals.

**Verify:** `python -m enviro_sync.cli fetch` (internet only), followed by inspection of `preview/` and unit tests.

**Explanatory limitation:** ERA5 data comes from climate reanalysis. It is model-derived historical weather, may use a nearby model grid cell, and is not a claim that Chennai and London each uploaded sovereign government sensor data.

## `enviro_sync/federation.py` — S3 publisher and federated reader

**Purpose:** Write regional datasets to the correct S3 Region, write a lightweight catalog to Mumbai, then discover and read either region from the same Python interface. All S3 communication uses authenticated Boto3 SDK clients, not public S3 URLs.

**Inputs:** Valid `Settings` configuration, validated dataset objects, and AWS credentials obtained through the standard AWS credential chain (CLI profile/SSO/IAM role). Never hardcode credentials.

**Outputs:** Uploaded objects, catalog JSON with region and object keys, plus verified Python response dictionaries with filtered observations and source provenance.

**Functions and methods:**

- `to_json_bytes(value)`: deterministic UTF-8 JSON serialization (sorted keys), enabling reproducible SHA-256 checks.
- `S3Federation(settings, session=None)`: creates clients lazily via `boto3.session.Session`. The `session` injection is used only by the offline fake-S3 tests.
- `client(region)`: caches a Boto3 S3 client for **each actual AWS Region**, using bounded connection/read timeouts and SDK retries.
- `verify_region(bucket, expected_region)`: issues a `HeadBucket` preflight request and rejects region mismatch before any upload. The IAM identity must have the necessary permission to perform this request.
- `put_bytes(region, bucket, key, content)`: writes JSON under an owned prefix with `ContentType=application/json`, explicit free-of-KMS SSE-S3 (`AES256`), and a two-million-byte cap. Does **not** grant public access.
- `get_bytes(region, bucket, key)`: invokes `GetObject` and enforces a two-million-byte response limit, closing the response stream.
- `publish(datasets)`: validates **both** city datasets, checks both bucket Regions, uploads each dataset to its own bucket, then puts the catalog in Mumbai. Catalog entries contain the actual Region, bucket, key, SHA-256 digest, record count, date coverage, provenance and size.
- `discover()`: reads the catalog from the Mumbai bucket. Rejects duplicate cities, invalid digests, and entries pointing outside our two configured bucket/Region pairs. This is the federation *discovery* capability.
- `retrieve(city_name, start=None, end=None)`: uses `discover` to locate the city, then calls `GetObject` against that city's Region; verifies SHA-256 of downloaded bytes and validates schema/metadata before optional inclusive date filtering.

**Important operational semantics:** `publish` is **not transactional across multiple S3 buckets**. If it fails midway, an earlier dataset may already have been uploaded while the catalog remains old. Do not label a failed publication successful. Fix the error and rerun `publish`, then `verify`; avoid concurrent publishing during the demo.

**Security:** App identity needs only the specified object-prefix permissions. This milestone does not authorize cross-account access, change bucket policies, or create public endpoints.

**Verify:** `python -m enviro_sync.cli verify` must read objects from **both AWS Regions** and print `sha256_verified: true`.

## `enviro_sync/cli.py` — operator workflow

**Purpose:** Implement exact terminal commands that separate offline data preparation from explicitly approved AWS writes.

- `fetch`: reads the real third-party API and creates `preview/chennai-daily-weather.json` and `preview/london-daily-weather.json`. **Makes no AWS calls.** Arguments: optional `--start`, `--end`, `--output-dir`.
- `publish --confirm-aws-charges`: loads and validates **already-downloaded local files**; checks matching date range; then performs AWS S3 HEAD/PUT calls. Fails if preview files are absent. Will not prompt for or display keys.
- `discover`: performs one S3 catalog read in Mumbai and prints actual registered metadata.
- `verify`: reads catalog/datasets in both Regions and checks digest/schema/record count for each.
- `read --city london --start 2025-07-01 --end 2025-07-03 --limit 3`: retrieves actual London records; `total_records` is before display truncation, `displayed_records` is the visible count.
- `compare --start 2025-07-01 --end 2025-07-07`: fetches both regional objects, matches identical **local calendar date labels**, and displays daily maximum temperature differences for up to 31 dates. This is a CLI proof; REST and chart UI come later.

**CLI safeguards:** Required publish acknowledgment, invalid city/date errors, limit of 100 displayed rows, input schema validation, and nonzero process exit on failure.

**Run:** All commands use `python -m enviro_sync.cli ...` from this package's top-level folder, after installing `requirements.txt`.

## `tests/` — offline tests

- `conftest.py`: fake S3 in-memory object store and sample API fixture. It never uses AWS or internet.
- `test_weather.py`: checks normalized data, missing dates, missing readings, invalid timezone, invalid date intervals, impossible precipitation values.
- `test_federation.py`: checks true *region-aware code paths* using independent fake clients, integrity checks, date filtering, invalid catalog pointers and unknown cities.
- `test_cli_and_safety.py`: validates local preview loading, failure when preview is missing, mismatched publication dates, and invalid read dates.

**Run:** `python -m pytest -q`; compare with expected 15 passing tests. **Passing mocked tests is not evidence of a successful AWS deployment**; `verify` against real S3 completes that evidence.
