# AWS IAM, security and cost protocol

## Preflight checklist (required before `publish`)

1. Sign into the intended AWS account with a **non-root IAM identity** (IAM user, IAM Identity Center credentials or role).
2. Confirm Milestone 1A already created two **private** general-purpose S3 buckets in `ap-south-1` and `eu-west-2`.
3. Confirm **Block Public Access** is enabled on both buckets; do not add public bucket policies or ACLs.
4. Check Billing / Free Tier consumption in the actual account and Regions, especially legacy (before 15 July 2025) introductory benefits. Legacy 12-month benefits may have expired; S3 is not an Always Free guarantee.
5. Review bucket encryption: standard S3-managed keys (SSE-S3 / `AES256`). Avoid SSE-KMS if you want to eliminate KMS request cost exposure.
6. Set a billing/budget alert if useful but remember **alerts do not block charges** and costs may be reported late.
7. Use your existing configured AWS CLI/Boto3 profile. Do not paste secrets into code, `.env`, commits, screenshots or chat.

## Verify your AWS session (PowerShell)

```powershell
$env:AWS_PAGER = ""
aws sts get-caller-identity --query Arn --output text
aws s3api get-public-access-block --bucket YOUR_INDIA_BUCKET --region ap-south-1
aws s3api get-public-access-block --bucket YOUR_LONDON_BUCKET --region eu-west-2
```

All four Public Access Block flags must be `true` for each bucket. If you used a named profile in AWS CLI, set `$env:AWS_PROFILE = "profile-name"` first. **Never share the full credentials.**

## Recommended least-privilege IAM policy example

Replace both `REPLACE_...` placeholders with your actual existing bucket names before adding to an IAM identity with the help of an authorized IAM administrator. Do not paste the placeholder names directly into a live IAM policy and expect access to work. This is an example to **review**, not an instruction to grant account-wide AdministratorAccess.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RegionalBucketPreflight",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::REPLACE_INDIA_BUCKET",
        "arn:aws:s3:::REPLACE_LONDON_BUCKET"
      ]
    },
    {
      "Sid": "RegionalProjectReadWriteOnly",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": [
        "arn:aws:s3:::REPLACE_INDIA_BUCKET/envirosync/v1/*",
        "arn:aws:s3:::REPLACE_LONDON_BUCKET/envirosync/v1/*"
      ]
    }
  ]
}
```

No IAM policy grants permission by itself: it must be attached to the authenticated principal, and bucket policies, permission boundaries, service control policies and organization restrictions must also permit the request. Bucket creation is **not** required for this milestone. `head_bucket` preflight requires authorization (commonly `s3:ListBucket`) and the code also reads the returned region header.

A read-only gateway role for a later deployment should **not** receive `s3:PutObject`. A real cross-organization implementation will require consent, IAM role assumption or an explicit owner-controlled policy. We are not building that yet.

## Exact S3 object footprint

The `publish` command writes these **three** JSON objects to *already existing* buckets:

| S3 Region | Bucket | Key | Data |
| --- | --- | --- | --- |
| ap-south-1 | `INDIA_BUCKET` | `envirosync/v1/datasets/chennai-daily-weather.json` | Chennai ERA5 observations |
| eu-west-2 | `LONDON_BUCKET` | `envirosync/v1/datasets/london-daily-weather.json` | London ERA5 observations |
| ap-south-1 | `INDIA_BUCKET` | `envirosync/v1/catalog/datasets.json` | Lightweight catalog with regional pointers and checksums |

This uses regular S3 API operations only. There is **no** Cross-Region Replication, S3 Transfer Acceleration, EC2, NAT gateway, API Gateway, SageMaker, KMS customer keys, third regional bucket, or managed workflow scheduler.

## What can still cost money

- S3 object storage in both Regions and S3 `PutObject` / `GetObject` / `HeadBucket` requests.
- Data transferred from S3 to your local computer, especially if other usage exceeds any applicable allowance.
- Extra operations caused by repeated `discover`/`verify`/`read` commands or failed/retried requests.
- Automatic or optional features enabled outside this package, or other AWS workloads already present on your account.

`publish` intentionally requires `--confirm-aws-charges` so the user explicitly acknowledges this risk. It is **not** a zero-spend guarantee or a billing hard cap.

## Avoid during this milestone

- Making S3 buckets or objects public.
- Repeated ingestion on a timer, cross-region object replication, or large/unknown datasets.
- Publishing concurrently from several laptops; the central catalog does not provide transaction locking.
- Supplying static AWS access keys in the frontend or source files.

## Official references

- AWS legacy Free Tier rules: https://repost.aws/knowledge-center/aws-free-tier-account-start-expire
- S3 API `HeadBucket`: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/head_bucket.html
- S3 `GetObject`: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/get_object.html
- S3 `PutObject`: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html
- AWS Billing: https://console.aws.amazon.com/billing/home
