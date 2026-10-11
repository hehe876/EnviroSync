# Existing AWS resources, IAM and live verification

## No new AWS infrastructure required

All active S3 resources are **reused from Milestone 1A**:

- `INDIA_BUCKET` must point to existing private Chennai bucket in `ap-south-1` (Mumbai).
- `LONDON_BUCKET` must point to existing private London bucket in `eu-west-2` (London).
- Bucket names must differ.
- Catalog: `s3://<INDIA_BUCKET>/envirosync/v1/catalog/datasets.json`.
- Regional objects: `envirosync/v1/datasets/chennai-daily-weather.json` and `envirosync/v1/datasets/london-daily-weather.json` in their assigned buckets.

The code never provisions buckets, IAM users, Lambda, RDS or hosting. No claim of zero AWS cost is made: real S3 GET/PUT/HEAD and inter-region/local transfers can incur charges depending on your plan, account age and remaining allowances. Verify pricing and billing before live calls. Use an IAM user/role with least privilege, not the AWS root identity.

## IAM guidance

The API only needs `s3:GetObject` on these three exact objects. A publisher additionally needs `s3:PutObject` on the same three object ARNs, plus `s3:ListBucket` permissions for `HeadBucket` for the two bucket ARNs (if your setup requires it). Substitute your *already existing* bucket names in the following scopes; consult [original IAM reference](legacy/02_AWS_IAM_AND_COST.md) before changing policies.

```text
arn:aws:s3:::<INDIA_BUCKET>
arn:aws:s3:::<LONDON_BUCKET>
arn:aws:s3:::<INDIA_BUCKET>/envirosync/v1/catalog/datasets.json
arn:aws:s3:::<INDIA_BUCKET>/envirosync/v1/datasets/chennai-daily-weather.json
arn:aws:s3:::<LONDON_BUCKET>/envirosync/v1/datasets/london-daily-weather.json
```

Region verification uses `HeadBucket` and expects the observed region from S3 response metadata. If the installed SDK/backend provides different metadata, live publishing may reject it rather than publishing into an unverified region. No IAM changes have been tested here.

## Safe sequence, from your repo root in PowerShell

**Offline first:**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m enviro_sync.cli --help
```

**Only after you have verified the correct account, billing safeguards, the two existing bucket names, and IAM:**

```powershell
$env:AWS_PAGER = ""
aws sts get-caller-identity --query Arn --output text
.\.venv\Scripts\python.exe -m enviro_sync.cli discover
.\.venv\Scripts\python.exe -m enviro_sync.cli verify
.\.venv\Scripts\python.exe -m enviro_sync.cli read --city london --start 2025-07-01 --end 2025-07-03
```

`discover` validates allowlisted catalog pointers. `verify` checks both regional S3 objects and their SHA-256 against the current catalog. `read` returns the requested rows. If the catalog doesn't yet exist in your account, these commands should fail; a passing offline test doesn't provision anything.

**Only if the canonical catalog/data were never published or you explicitly need to update them:**

```powershell
# Use original real data examples already included (2024-01-01..2025-12-31)
.\.venv\Scripts\python.exe -m enviro_sync.cli publish --start 2024-01-01 --end 2025-12-31 --output-dir data/examples --confirm-aws-charges
```

This writes **three existing keys** and can overwrite previously published content. Do not publish until you have approved that action, checked the account and costs, and backed up originals if necessary. The flag is a local acknowledgment, not a billing guard.

Finally start the API locally and call `GET /api/datasets`, `GET /api/observations`, `GET /api/compare` from `/docs`. Observe the two AWS regions and SHA-256 flags. Never post IAM account IDs, access keys, S3 paths containing private identifiers, or actual `.env` content to GitHub.
