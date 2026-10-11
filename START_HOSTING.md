# EnviroSync — Milestone 4A hosting on AWS Free account plan

**Status:** Source package and local tests prepared. The application is NOT deployed yet.

**Designed for:** AWS Free account plan, created 4 July 2026; hosting is limited to `ap-south-1`, without using regional dataset buckets. Data ingestion and cross-region federation are deferred to Milestone 4B.

## First-time Windows setup

1. Extract the ZIP; open its inner `EnviroSync` directory in VS Code (must contain `pyproject.toml`).
2. Install Python 3.12, Node.js 22/npm, AWS CLI v2 (recent enough to support `aws freetier get-account-plan-state`), and AWS SAM CLI. Authenticate AWS CLI using an authorized identity; **never use root account keys or commit credentials**.
3. Run the **read-only AWS Free-plan status check** before deploying:

   ```powershell
   aws sts get-caller-identity
   aws freetier get-account-plan-state --region us-east-1
   ```

   Verify `accountPlanType` is `FREE`, `accountPlanStatus` is `ACTIVE`, credits are positive, and expiration is in the future. If API access is denied, grant a read-only `freetier:GetAccountPlanState` permission; do not bypass the guard.
4. Create virtual environment and install tests:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   .\milestones\milestone_4_deployment\scripts\deploy-hosting.ps1 -PreflightOnly
   ```

   **The first deployment does NOT require `.env`, India/London bucket names, or uploaded environmental data.** You may keep your existing ignored `.env` for later Milestone 4B development.
5. When you have reviewed the resources that consume AWS Free Tier credits, deploy:

   ```powershell
   .\milestones\milestone_4_deployment\scripts\deploy-hosting.ps1 -ConfirmAwsCredits
   ```

   This deploys private S3 React hosting + CloudFront + FastAPI on AWS Lambda and API Gateway in `ap-south-1`. SAM also manages a packaging-artifact bucket. It does not access your environmental data buckets.
6. Wait for CloudFront propagation. Check the URL output by the script:

   ```powershell
   .\.venv\Scripts\python.exe .\milestones\milestone_4_deployment\scripts\check_live_hosting.py --url https://YOUR_REAL_CLOUDFRONT_URL --expect-empty --hosting-only
   ```

   Expected: HTTPS frontend, `/api/health`, empty `/api/datasets`, and HTTP 503 `DATA_NOT_CONNECTED` for observations.

## Later deployment through GitHub

The `.github/workflows/deploy-hosting.yml` workflow is **manual**. It authenticates through GitHub OIDC, verifies Free-plan credits, tests, builds and redeploys. You must first create a reviewed AWS IAM deployment role, a GitHub `hosting` environment, and add **only** `AWS_DEPLOY_ROLE_ARN` as a GitHub variable. The IAM role needs `freetier:GetAccountPlanState`, `sts:GetCallerIdentity` and scoped permissions to manage the hosting stack, not environmental buckets.

See [Milestone 4A full guide](milestones/milestone_4_deployment/README.md) for details, limitations and rollback/cleanup.

## Important limitations

- The Free account plan ends at credit exhaustion or six months after account creation, whichever occurs first. Starting 4 July 2026, the six-month deadline is **around 4 January 2027**; use the actual account-plan expiration from AWS to confirm. The account may close after expiration unless upgraded to Paid.
- AWS-supported services can still **consume promotional credits**. Free account plan prevents out-of-pocket AWS charges while active, but does not make usage resource-free.
- Some cross-region functions are restricted for newer AWS Free Tier accounts. Milestone 4A is intentionally hosting-only; it does not demonstrate real regional federation.
- Live deployment, AWS account policy acceptance, and Vite production build must be verified in your environment.
