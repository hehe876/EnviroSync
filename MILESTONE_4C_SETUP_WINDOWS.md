# EnviroSync Milestone 4C — Administrator-only dataset publishing

## What this adds

A **real** Cognito-authenticated CSV/JSON publishing workflow, backed by existing regional S3 buckets. Original Chennai/London ERA5 objects and the original catalog are never overwritten. Uploaded datasets are stored separately under `envirosync/v1/uploads/` and automatically join the public dataset list, observation API, and two-city comparison UI.

**Important:** This package supplies complete replacement files and offline tests. It has **not been deployed to your AWS account**. Follow the gated deployment sequence below; it will modify the existing hosting stack and optionally create one small Cognito user pool. Do not run any deployment command until your AWS Free Plan and intended permissions have been reviewed.

### Constraints and behavior

- Upload access: only a Cognito user whose **verified RS256 access token** contains `cognito:groups = ["envirosync-admin", ...]`, the expected issuer, correct client ID, and unexpired timestamp. All public GET APIs stay readable without login.
- Authentication: Cognito **Lite** user pool, self-registration disabled, 14-character complex passwords, **required TOTP MFA**, authorization-code + PKCE, admin-only group. The SPA keeps access tokens only in memory; no browser AWS access keys or app-client secret.
- New datasets: new lowercase city slug; choose **Mumbai `ap-south-1` or London `eu-west-2`**. Only the existing approved S3 buckets are used. The original Chennai/London names are reserved.
- File format: UTF-8 `.csv` columns `date,temp_max_c,temp_min_c,precipitation_mm` (exact order), or `.json` containing a list of the same objects (also accepts an `observations` list). At most **200 KB**, **366 consecutive days**, **20 extra cities**. Units are Celsius/mm. Finite numerical readings, valid ISO dates, chronological ordering, min ≤ max, and nonnegative precipitation are enforced.
- Integrity: normalized dataset bytes are stored once with `IfNoneMatch: *`; a separate registry manifest captures their SHA-256. Every read re-checks the hash. Registry allowlists prohibit arbitrary S3 regions, bucket names, or object paths.
- No overwrite or delete UI by design. Failed registry publication can leave one orphan data object under the uploads prefix; contact an authorized AWS operator to review any such object. Original objects are unaffected.
- No automatic provisioning or uploads on GitHub push. The deployment workflow is **manual** and checks Free Plan account status and credit balance. Upload write IAM is only added when the upload switch is explicitly `true`.

## 1. Apply the complete files

The supplied ZIP has full replacement/new files at repository-relative paths. In **PowerShell**, run from your existing working tree:

```powershell
cd C:\Users\San\EnviroSync_Milestone_4A_AWS_Free_Plan_Ready\EnviroSync
Expand-Archive -Path "$HOME\Downloads\EnviroSync_M4C_Complete_Files.zip" -DestinationPath . -Force
git status
```

If your download directory or filename differs, replace only the ZIP path in the command. Do **not** extract into a second nested `EnviroSync` folder. Do not include `.env` or AWS keys in Git commits.

## 2. Run all local tests BEFORE committing

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m py_compile milestones/milestone_2_api/admin_auth.py milestones/milestone_2_api/upload_service.py
cd milestones/milestone_3_frontend
npm ci --no-audit --no-fund
npm run test
npm run build
cd ../..
sam validate --template-file milestones/milestone_4_deployment/infrastructure/template.yaml
aws cloudformation validate-template --template-body file://milestones/milestone_4_deployment/infrastructure/cognito-admin.yaml --region ap-south-1
```

Expected offline: **67 Python tests** and **16 Node tests** with this package, plus Vite build and AWS template validation on your Windows setup. Python/Node tests use fake S3 and do not contact AWS. This build artifact's Python/Node test counts were verified offline; the actual Vite build and SAM/CloudFormation validation must still be performed locally because these tools were not available to this packaging environment.

If a validation or build command fails, **do not deploy**; fix the actual failure and rerun it.

## 3. Review AWS Free Plan and the current stack

All commands below are real AWS operations; first confirm the profile, account, and remaining credits:

```powershell
aws sts get-caller-identity
python milestones/milestone_4_deployment/scripts/preflight_free_plan.py --region ap-south-1
aws cloudformation describe-stacks --stack-name envirosync-hosting --region ap-south-1 --query 'Stacks[0].StackStatus' --output text
$website = aws cloudformation describe-stacks --stack-name envirosync-hosting --region ap-south-1 --query 'Stacks[0].Outputs[?OutputKey==`WebsiteUrl`].OutputValue | [0]' --output text
$website
```

If PowerShell/AWS CLI quoting makes the `WebsiteUrl` query difficult, retrieve all outputs and read `WebsiteUrl` from the JSON:

```powershell
$siteOutputs = aws cloudformation describe-stacks --stack-name envirosync-hosting --region ap-south-1 --query 'Stacks[0].Outputs' --output json | ConvertFrom-Json
$website = ($siteOutputs | Where-Object { $_.OutputKey -eq 'WebsiteUrl' }).OutputValue
$website
```

Expected: the previous M4B website URL and a healthy existing stack. **Do not** delete or recreate existing S3 buckets. Cognito Lite user pools currently have a **10,000 monthly active user Free Tier** for eligible direct/social sign-in, but Lambda, S3, API Gateway, and CloudFront usage can still spend AWS Free Plan credits; confirm current AWS pricing and your account plan before deploying. Avoid SMS MFA (uses SNS); M4C requires TOTP authenticator MFA.

- Official Cognito pricing: https://aws.amazon.com/cognito/pricing/
- Cognito Lite/features: https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-sign-in-feature-plans.html
- AWS Free Plan preflight: `scripts/preflight_free_plan.py`

## 4. Commit and run the FIRST safe hosting update (uploads disabled)

```powershell
git add .github/workflows/deploy-hosting.yml pyproject.toml MILESTONE_4C_SETUP_WINDOWS.md milestones/milestone_2_api milestones/milestone_3_frontend/src milestones/milestone_4_deployment/infrastructure milestones/milestone_4_deployment/scripts milestones/milestone_4_deployment/tests milestones/milestone_4_deployment/examples
git diff --cached --check
git commit -m "Implement gated M4C administrator dataset uploads"
git push origin main
```

In GitHub → repository **Settings → Environments → hosting → Environment variables**, first ensure `ENVIROSYNC_UPLOADS_ENABLED` is set to **`false`** (or unset). Keep the existing `AWS_DEPLOY_ROLE_ARN` variable unchanged. Leave Cognito variables unset initially.

Open **Actions → Deploy EnviroSync M4C (Free account) → Run workflow → branch main**. It will install/test/build/publish the frontend and backend while uploads remain disabled. It reuses stack `envirosync-hosting`, existing frontend bucket, distribution and API; it does NOT create a Cognito pool or enable S3 upload writes yet. It invokes the real `check_live_hosting.py` smoke test, which ensures original S3 datasets remain accessible and anonymous admin access is denied.

> A manual hosting deployment is still an AWS change. Inspect the proposed SAM template, IAM policy, and available credits **before** manually running it: the workflow uses `--no-confirm-changeset`, so it does not stop for a second interactive approval. If your deployment role lacks an IAM action, diagnose the exact failed step rather than granting wildcards.

## 5. Create the Cognito authentication stack (explicit manual opt-in)

After reviewing Cognito Lite free tier eligibility and confirming that creating a new Cognito User Pool is approved, check template validation from step 2, then run:

```powershell
$prefix = "envirosync-admin-$(Get-Random -Minimum 100000 -Maximum 999999)"
aws cloudformation deploy --template-file milestones/milestone_4_deployment/infrastructure/cognito-admin.yaml --stack-name envirosync-admin-auth --region ap-south-1 --parameter-overrides "WebsiteUrl=$website" "DomainPrefix=$prefix" --no-fail-on-empty-changeset
```

If the domain is already taken, use another unique prefix. This separate stack creates **one Cognito Lite user pool, one browser public client, one admin group, one hosted Cognito domain**. `AdminPool` has `DeletionPolicy: Retain`; review cleanup implications before deleting the stack.

Get its outputs:

```powershell
$authOutputs = aws cloudformation describe-stacks --stack-name envirosync-admin-auth --region ap-south-1 --query 'Stacks[0].Outputs' --output json | ConvertFrom-Json
$poolId = ($authOutputs | Where-Object { $_.OutputKey -eq 'UserPoolId' }).OutputValue
$clientId = ($authOutputs | Where-Object { $_.OutputKey -eq 'ClientId' }).OutputValue
$domain = ($authOutputs | Where-Object { $_.OutputKey -eq 'CognitoDomain' }).OutputValue
$poolId
$domain
```

The pool ID, client ID, and hosted domain are **public configuration values, not passwords**.

## 6. Create your administrator (secure interactive Python, no password in shell history)

```powershell
python milestones/milestone_4_deployment/scripts/create_admin.py --email YOUR_ADMIN_EMAIL@example.com
```

This script prints the AWS account ID, asks you to confirm it, securely prompts for the admin password, creates the user without a welcome email, sets the permanent password and adds that user to `envirosync-admin`. **Do not** paste passwords, tokens, or MFA recovery codes into GitHub, chat, documentation, or `.env.example`.

## 7. Explicitly enable 4C in GitHub Environment variables

Within the **hosting** GitHub environment, set these **variables** (not secrets; none are credentials):

| Variable | Value |
| --- | --- |
| `COGNITO_USER_POOL_ID` | `$poolId` from the auth stack |
| `COGNITO_CLIENT_ID` | `$clientId` from the auth stack |
| `COGNITO_DOMAIN` | `$domain` from the auth stack, including `https://` |
| `ENVIROSYNC_UPLOADS_ENABLED` | `true` |

The repository workflow then injects the Cognito public client info into the React build, and passes the matching pool/client ID as SAM stack parameters. Both server-side token verification **and** the read/write IAM policy remain gated by `UploadsEnabled`.

Manually run **Deploy EnviroSync M4C (Free account)** on `main` again. Expected: current hosting stack updated, Lambda retains original read-only ERA5 policy plus narrowly scoped upload-prefix S3 List/Get/Put. The original catalog and original Chennai/London dataset keys remain immutable to this Lambda. `aws-sam` artifacts use the existing managed SAM bucket. No new regional data buckets are created.

If CloudFormation fails on IAM, check the exact error. The deploy role may require `iam:PutRolePolicy` (and on cleanup `iam:DeleteRolePolicy`) specifically on the stack-generated backend role, not a blanket `iam:*` grant. The workflow uses `CAPABILITY_NAMED_IAM` because the narrow inline upload policy has an explicit name. Review this IAM resource **before triggering** the workflow; the workflow automatically executes the CloudFormation change set after preflight.

## 8. Real website acceptance test (requires one intentional S3 upload)

Visit `$website`, hard refresh, and select **Administrator sign in**. Sign in through Cognito's hosted screen and set up **TOTP MFA** in an authenticator app. Only members of the `envirosync-admin` group receive upload permission.

In the newly visible upload form, enter:

- City identifier: `berlin`
- Country: `Germany`
- Attribution/source: `Demo historical station`
- Storage region: `eu-west-2`
- File: `milestones/milestone_4_deployment/examples/berlin-sample.csv`

Click **Validate and publish** once. Expect a successful registration message with row count `7` and SHA-256 prefix. Dataset `berlin` must appear in the dashboard catalog; choose Berlin as primary, London as comparison, and a shared date range **2025-07-01 to 2025-07-07**. The observation table must show the uploaded values, the comparison graph must show **real** aligned values, and integrity must report verified. CSV export should include the new series.

Run the read-only public smoke test:

```powershell
python milestones/milestone_4_deployment/scripts/check_live_hosting.py --url $website
```

For a negative test, from PowerShell **without** a bearer token:

```powershell
try { Invoke-RestMethod "$website/api/admin/session" } catch { "Expected denial: HTTP $([int]$_.Exception.Response.StatusCode)" }
```

Expected HTTP `401` when uploads are enabled. When disabled, expected HTTP `503` (fail closed). A browser session from an ungrouped Cognito user receives HTTP `403` from admin endpoints. There is deliberately no AWS credential field or password form implemented in React.

If you previously uploaded `berlin`, it will reject another `berlin` upload with HTTP `409` to prevent accidental replacement. Pick a different new city for future tests; the maximum is 20 newly registered cities.

## 9. Rollback/recovery

- To **disable new writes without touching data**: set GitHub `ENVIROSYNC_UPLOADS_ENABLED=false` and manually redeploy. The conditional upload S3 policy disappears and admin requests return `503`. Public original Chennai/London API remains available. Newly uploaded datasets are hidden until re-enabled, but remain intact in S3.
- To roll back code: revert the 4C commit, review the resulting CloudFormation changes, and redeploy. The original objects remain unaffected. Do not casually delete the Cognito stack; its user pool has a Retain policy.
- When a registry write fails after data was successfully stored, there may be an orphan under `envirosync/v1/uploads/datasets/` that requires **manual AWS owner review**. No automated deletion is performed, deliberately.
- If any workflow step fails, stop before rerunning. Get the first error from the failed step. Never run `sam delete`, `aws s3 rm --recursive`, or blanket IAM permission edits to recover.

## 10. File inventory

Full source replacements: `milestones/milestone_2_api/app.py`, `routes.py`, `admin_auth.py`, `upload_service.py`, `milestones/milestone_3_frontend/src/App.jsx`, `src/styles.css`, `src/lib/api.mjs`, `src/lib/admin.mjs`, `src/components/AdminUpload.jsx`, `milestones/milestone_4_deployment/infrastructure/template.yaml`, `scripts/check_live_hosting.py`, `scripts/stage_lambda.py`, `tests/test_hosting.py`, `.github/workflows/deploy-hosting.yml`, `pyproject.toml`.

New complete files: `milestones/milestone_4_deployment/infrastructure/cognito-admin.yaml`, `scripts/create_admin.py`, `examples/berlin-sample.csv`, `examples/pune-sample.json`, `milestones/milestone_2_api/tests/test_admin_uploads.py`, `milestones/milestone_3_frontend/src/lib/admin.test.mjs`, this guide.

**No modifications required** to the original ERA5 ingestion CLI or your actual `.env`; never commit credentials.
