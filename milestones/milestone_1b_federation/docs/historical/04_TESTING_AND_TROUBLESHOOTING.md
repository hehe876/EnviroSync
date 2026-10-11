# Tests, diagnostic commands and troubleshooting

## Offline test suite: no AWS and no internet

From `EnviroSync_Milestone_1B` in Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected result: `15 passed`.

| Test | Required behavior |
| --- | --- |
| Normalize actual API response shape | Correct dates, values, attribution and record count |
| Missing date | Abort; never fabricate a replacement |
| Missing temperature | Abort; never store null measurements |
| Incorrect timezone | Abort; do not compare ambiguous daily intervals |
| Reversed or excessive date interval | Abort with a meaningful error |
| Negative precipitation | Abort schema validation |
| Publish and retrieve with two fake regional clients | Correct S3 region routing and central Mumbai catalog |
| Date-range filtering | Return only included dates |
| Modified regional S3 object | Reject with a SHA-256 integrity error |
| Catalog pointer redirect to another bucket | Reject instead of following arbitrary S3 pointers |
| Unknown city | Reject; do not fall back silently |
| Prepared local files | Load both validated previews without making AWS calls |
| Missing prepared file | Reject publishing when `fetch` has not run |
| Prepared date mismatch | Reject mismatched `--start` / `--end` settings |
| Invalid retrieval date | Reject impossible date values such as July 32 |

**Scope:** Fake S3 clients exist only in tests. They verify implementation logic, **not cloud deployment**. `python -m enviro_sync.cli verify` is the AWS verification command.

## Real AWS acceptance tests

Only run these after checking billing and IAM permissions.

```powershell
.\.venv\Scripts\python.exe -m enviro_sync.cli discover
.\.venv\Scripts\python.exe -m enviro_sync.cli verify
.\.venv\Scripts\python.exe -m enviro_sync.cli read --city london --start 2025-07-01 --end 2025-07-03 --limit 3
.\.venv\Scripts\python.exe -m enviro_sync.cli compare --start 2025-07-01 --end 2025-07-07
```

**Observe:** `discover` contains London `eu-west-2` and Chennai `ap-south-1`. `verify` prints `"status": "PASS"` only after each retrieved object matches catalog SHA-256 and passes data validation. The `read` response contains real values, plus `"sha256_verified": true`. `compare` aligns seven dates across regions for the default 2024–2025 dataset. If a command fails, the feature is **not complete yet**.

## Negative tests (safe but invoke paid-capable reads)

```powershell
.\.venv\Scripts\python.exe -m enviro_sync.cli read --city london --start 2025-07-32 --end 2025-07-33
.\.venv\Scripts\python.exe -m enviro_sync.cli read --city london --start 2030-01-01
```

Both must fail with a clear `ERROR:` and a nonzero exit status. These read tests may issue S3 requests before rejecting date parameters, so do not repeat them excessively in a constrained account.

## Frequent errors and exact corrections

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `No module named dotenv` | Requirements not installed in selected Python interpreter | Run `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` |
| `No module named enviro_sync` | Terminal is outside the extracted package folder | `cd` into `EnviroSync_Milestone_1B`; use `python -m ...` |
| `.env must define ...` | Missing `.env`, old values, or incorrect regions | Copy the Milestone 1A `.env` into this folder; use `ap-south-1` / `eu-west-2` |
| `NoCredentialsError` or `Unable to locate credentials` | AWS CLI credentials missing or wrong profile | Check `aws sts get-caller-identity`; set `$env:AWS_PROFILE` when using a named profile |
| `AccessDenied` at HeadBucket | IAM principal lacks bucket permission for preflight | Ask an authorized IAM administrator to review least-privilege policy in `02_AWS_IAM_AND_COST.md` |
| `AccessDenied` at PutObject/GetObject | Wrong bucket, bucket policy restrictions, or missing object permissions | Review actual bucket names and `envirosync/v1/*` prefix policy. Do not make bucket public |
| `Bucket ... is in ... expected ...` | `.env` references an S3 bucket in a different Region | Fix `.env` to use the two already-verified Milestone 1A buckets; don't force a new Region silently |
| `Open-Meteo returned HTTP 429` | Remote rate limit | Wait; don't rapidly repeat; API access governed by Open-Meteo limits |
| `Could not reach Open-Meteo` | Network, DNS, proxy or remote service unavailable | Check browser connectivity to official Historical Weather API; retry later without uploading fake data |
| `Weather API did not return entire ...` | Missing days or incomplete source response | Do not bypass validation; try a smaller historical interval and pass same `--start`/`--end` to both commands |
| `Missing preview/...` | Attempted `publish` before `fetch` | Run `fetch` first; review local JSON |
| `Preview dates differ` | `fetch` used custom dates but `publish` used defaults | Pass identical `--start`/`--end` for both |
| `sha256 integrity check failed` | Dataset was edited after catalog publication, or interrupted update | Do not ignore; verify source, rerun `publish`, then `verify` once |
| `Catalog ... unsupported / pointer ... unexpected` | Catalog edited or corrupted | Do not disable pointer checks; regenerate by `publish` from validated local files |
| `Unexpected timezone` | Open-Meteo returned different timezone than requested | Inspect response and official API docs. Don't change dates silently |
| `Parameter validation failed` | Command flags in wrong position | `--env` goes before subcommand (`python -m enviro_sync.cli --env .env verify`) |

## Partial AWS publication recovery

S3 uploads to different Regions and the central catalog are **not atomic**. When `publish` fails:

1. Read the exact error; do not create extra buckets or loosen IAM policies broadly.
2. Confirm that local preview files are complete and match the requested interval.
3. Fix access/region/network issue.
4. Rerun the **same** `publish --confirm-aws-charges` command; it overwrites **only the three fixed project keys**.
5. Run `verify` to confirm the catalog matches both regional objects before declaring success.

Avoid concurrent publishers or edits during the demonstration. Do not edit stored observations manually, because the SHA-256 check will detect the mismatch.

## Stop criteria

If two attempts fail due to an unexplained AWS cost/permission issue, stop making cloud calls, record the error and ask for targeted help. Do **not** enable public S3 access, remove encryption, or assign `AdministratorAccess` just to get past an error.
