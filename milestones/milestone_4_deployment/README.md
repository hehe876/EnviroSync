# Milestone 4A — AWS Free account plan public hosting

This milestone deploys the **existing canonical FastAPI and React application** to AWS, without requiring environmental data. It intentionally does not provision or read either existing environmental bucket. This keeps the public hosting stage separate from Milestone 4B's regional federation, whose cross-region behavior may be restricted under the AWS Free account plan.

**Supported scope:** AWS Free account plan with positive credits and ACTIVE status, one deployment region `ap-south-1` (Mumbai); CloudFront is an allowed global CDN. This is a public proof-of-concept, **not an authenticated production service**. No AWS resources are created by the ZIP itself.

## Architecture / actual behavior

```text
Browser HTTPS  https://<cloudfront-domain>/
       |-- /*      -> CloudFront -> private hosting S3 bucket (Vite/React build)
       `-- /api/* -> CloudFront -> API Gateway HTTP API -> Lambda (FastAPI + Mangum)
                                                          |-- /api/health       200 OK
                                                          |-- /api/datasets     [] (no AWS SDK calls)
                                                          |-- /api/observations 503 DATA_NOT_CONNECTED
                                                          `-- /api/compare      503 DATA_NOT_CONNECTED

Existing ap-south-1 and eu-west-2 environmental buckets: NOT ACCESSED.
```

The React dashboard correctly displays **No published datasets**. No fabricated readings are returned. Backend endpoint functionality for regional data remains in the Milestone 1B/2 source; `ENVIROSYNC_HOSTING_ONLY=true` blocks the S3 integration only in the deployed AWS runtime.

## AWS components permitted by AWS's newer Free Tier service list

| AWS service | Role / restriction |
| --- | --- |
| AWS CloudFormation / SAM | Single-region stack; **no StackSets** |
| AWS Lambda | Python 3.12 backend; capped reserved concurrency 2; no Lambda@Edge |
| API Gateway HTTP API | GET API paths; throttled to 2 requests/second, burst 10 |
| Amazon S3 | **New private frontend bucket** (plus possible SAM artifact bucket); no Cross-Region Replication |
| CloudFront | Default AWS-provided HTTPS hostname; PriceClass_100, OAC to private S3 |
| IAM and STS | Role for Lambda, optionally GitHub OIDC deployment; no AWS keys stored in code |
| CloudWatch Logs | Lambda logs retained for 3 days |

The AWS Free account plan prevents out-of-pocket charges while active, but these services can **spend your credits**. CloudFront's alternative flat-rate subscription is not configured by this template. The plan can close on exhaustion or expiration, potentially removing the application. Check AWS Billing before and after deploying.

AWS source material:
- Supported services and feature limitations: https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html
- Free account plan, credits and account closure: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html
- Account plan API: https://docs.aws.amazon.com/cli/latest/reference/freetier/get-account-plan-state.html
- AWS SAM deploy: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html

## Files, inputs and verification

| File | Purpose | Inputs / output |
| --- | --- | --- |
| `infrastructure/template.yaml` | Single-region hosting-only infrastructure, no data bucket permissions | Deploy produces `WebsiteUrl`, `WebBucketName`, `DistributionId` |
| `scripts/preflight_free_plan.py` | Fail-closed account-plan eligibility/remaining-credits check | AWS CLI profile -> PASS/FAIL; **read-only** |
| `scripts/stage_lambda.py` | Copy canonical 1B and 2 code to generated Lambda build | Python source -> generated `build/lambda` |
| `scripts/deploy-hosting.ps1` | One-time Windows infra + frontend deployment | Requires account preflight and `-ConfirmAwsCredits` |
| `scripts/check_live_hosting.py` | Real HTTPS health/empty-catalog/blocked-retrieval checks | `--url https://... --expect-empty --hosting-only` |
| `.github/workflows/deploy-hosting.yml` | Manual deployment by GitHub OIDC; repeats safety preflight | Variable `AWS_DEPLOY_ROLE_ARN`, proper IAM deployment role |
| `tests/test_hosting.py` | Offline API, safety, staging, workflow and preflight tests | `python -m pytest -q`, no AWS account |

## Step-by-step Windows deployment

1. From the repository root containing `pyproject.toml`, install or verify **Python 3.12**, **Node 22**, **AWS CLI v2** and **AWS SAM CLI**:

   ```powershell
   py -3.12 --version
   node --version
   npm --version
   aws --version
   sam --version
   ```

2. Configure AWS CLI authentication with a non-root identity permitted to deploy this stack. Verify identity and Free plan:

   ```powershell
   aws sts get-caller-identity
   aws freetier get-account-plan-state --region us-east-1 --output json
   ```

   You need `freetier:GetAccountPlanState` and `sts:GetCallerIdentity` permissions for the read-only preflight. Check that your Free plan is ACTIVE and credits remain.

3. Install project dependencies and test read-only preflight **without provisioning**:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   .\milestones\milestone_4_deployment\scripts\deploy-hosting.ps1 -PreflightOnly
   ```

   **No `.env` is required for this hosting-only deployment.** Do not upload/copy AWS credentials to the source repository or frontend folder. Existing data buckets are not used.

4. Before creating resources, review AWS Billing → Cost and Usage and your actual remaining credits; review the stack template. A budget can provide another warning but is not a spending cap. Once satisfied:

   ```powershell
   .\milestones\milestone_4_deployment\scripts\deploy-hosting.ps1 -ConfirmAwsCredits
   ```

   If Windows PowerShell blocks the script, run this **single-process** execution-policy alternative:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\milestones\milestone_4_deployment\scripts\deploy-hosting.ps1 -ConfirmAwsCredits
   ```

   Do not use `-ConfirmAwsCharges` from the earlier package; it has been replaced. Deployment may take several minutes for CloudFront. The script should print the real HTTPS hostname.

5. After CloudFront propagates, verify the live application:

   ```powershell
   .\.venv\Scripts\python.exe .\milestones\milestone_4_deployment\scripts\check_live_hosting.py --url https://YOUR_REAL_CLOUDFRONT_DOMAIN --expect-empty --hosting-only
   ```

   Expected output includes four PASS lines (React HTML, API health, zero datasets and blocked data access). Load the same hostname in the browser: UI should say **No published datasets**.

6. Review AWS CloudFormation stack `envirosync-hosting` in `ap-south-1`, CloudFront distribution and private S3 website bucket. Neither regional environmental S3 bucket should be altered.

### GitHub Actions (optional second stage, still a manual trigger)

1. Push the extracted source to your existing GitHub repo, preserving its `.git` history. `.gitignore` excludes `.env`, `.venv`, `node_modules`, build output, credentials. Review `git status` before committing.
2. AWS IAM → Identity providers: reuse/create GitHub OIDC provider `https://token.actions.githubusercontent.com` with audience `sts.amazonaws.com`.
3. Create deployment role with trust restricted to **your** repository and `hosting` environment (example in `docs/github-oidc-trust.example.json`). GitHub OIDC subject formats may differ under newer GitHub enrollment policies, so confirm the actual tokens/claims before applying a trust condition.
4. Grant the role **reviewed, resource-scoped deployment permissions** for CloudFormation, IAM role and `iam:PassRole`, Lambda, API Gateway, CloudFront, S3 **hosting/artifact buckets**, CloudWatch Logs, STS, plus `freetier:GetAccountPlanState`. Do not grant the role access to the existing India/London data buckets. Trust policy alone grants no AWS permissions.
5. GitHub → Settings → Environments → create `hosting`, restrict to `main`, require approval where available. GitHub → Settings → Secrets and variables → Actions → Variables → set `AWS_DEPLOY_ROLE_ARN`. No AWS access keys and no regional bucket variables are needed for M4A.
6. GitHub → Actions → **Deploy EnviroSync M4A (Free account)** → **Run workflow**. This runs the account preflight **before any resource changes**, builds, deploys, uploads React, and checks the public URL. It is deliberately not triggered by every push.

### Troubleshooting

- **No `aws freetier get-account-plan-state` CLI command:** upgrade to current AWS CLI v2. Never bypass account-plan validation.
- **`AccessDenied` in Free Tier API:** deploy identity needs `freetier:GetAccountPlanState`; ask an authorized AWS administrator to grant read-only access.
- **Unexpected account status:** stop; don't upgrade to Paid automatically. Inspect AWS Billing.
- **PowerShell cannot run `deploy-hosting.ps1`:** verify you're in `EnviroSync/`; use the one-process bypass command above, only for trusted local script.
- **403 / React blank:** inspect CloudFormation stack events, S3 `dist/index.html` object, CloudFront OAC and bucket policy.
- **API returns HTML:** CloudFront `/api/*` ordered behavior needs to route to API Gateway origin.
- **`/api/datasets` unexpectedly accesses S3:** verify deployed Lambda environment variable `ENVIROSYNC_HOSTING_ONLY=true` and run API tests. M4A intentionally does not make cross-region calls.
- **SAM fails due account restrictions:** CloudFormation Events should show the exact denied operation. Don't upgrade the plan without a user decision.

### Cleanup and credit consumption

Deleting the stack may retain the hosting S3 bucket because it uses `DeletionPolicy: Retain`; SAM's packaging bucket can also persist. These can consume Free Tier credits. Review names through CloudFormation outputs and the AWS Console before manually removing only **M4A-created resources**. Never delete either Milestone 1A environmental bucket through hosting cleanup. This package performs no AWS creation or cleanup automatically.

### Milestone 4B (later)

Data ingestion, publish global catalog, IAM to exact dataset object keys, cross-region federation and SHA-256 verification are **not part of Milestone 4A**. Confirm the applicable account restrictions before attempting two-region access; do not treat a successful hosting-only smoke test as proof of cross-region federation.
