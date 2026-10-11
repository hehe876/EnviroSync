# Milestone 1A resource contract

This is a documentation-only block because the user already completed infrastructure setup and SHA-256 verification.
It does not prove the resources still exist today.

Required environment variables (set in ignored root `.env`): `INDIA_BUCKET`, `LONDON_BUCKET`, `INDIA_REGION=ap-south-1`, `LONDON_REGION=eu-west-2`.

Optional **read-only AWS checks** from PowerShell after installing/configuring AWS CLI:

```powershell
aws sts get-caller-identity
aws s3api head-bucket --bucket <existing-india-bucket> --region ap-south-1
aws s3api head-bucket --bucket <existing-london-bucket> --region eu-west-2
```

Replace placeholders in angle brackets; do not copy the angle brackets literally. Do not paste account identifiers or secret access keys into a public issue.
These requests may incur AWS costs. Verify your specific AWS Free Tier/billing situation first. No S3 resources are created by offline tests.
The S3 application prefix is `envirosync/v1/`, and the global catalog is stored under India's bucket at `envirosync/v1/catalog/datasets.json`.
