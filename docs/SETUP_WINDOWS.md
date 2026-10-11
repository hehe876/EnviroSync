# Clean Windows 11 setup and commands — CURRENT layout

These instructions assume a new Git working directory with `README.md`, `pyproject.toml`, `milestones/` and `scripts/` at its root. Do not extract over the old EnviroSync repository. Back up the old `.env` and `.git` separately and only copy approved bucket values into the new ignored `.env`.

## 1. Python 3.12

```powershell
cd "$env:USERPROFILE\EnviroSync"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pytest -v
```

The Python executable does **not** need to be in the directory as the source code; the editable installation registers the milestone packages. Always launch from the repo root for consistent `.env` and preview paths. Don't manually set `PYTHONPATH` and don't create a venv in each milestone.

Alternative automated sequence: `./scripts/setup.ps1` if policy permits. If `Copy-Item` complains `.env` exists, leave your valid local configuration untouched.

## 2. Node.js 22 and React

```powershell
cd milestones/milestone_3_frontend
npm.cmd install
npm.cmd run test
npm.cmd run build
cd ../..
```

One React app lives at `milestones/milestone_3_frontend`; do **not** run `npm create vite` again. There is no `frontend/` folder at repo root. On your first successful npm install, commit the generated `milestones/milestone_3_frontend/package-lock.json`.

## 3. Local AWS configuration (only for data requests)

Edit ignored `.env` at repo root with your **pre-existing** bucket names, no access keys:

```dotenv
INDIA_BUCKET=your-existing-india-bucket
LONDON_BUCKET=your-existing-london-bucket
INDIA_REGION=ap-south-1
LONDON_REGION=eu-west-2
```

Existing AWS CLI profile/environment credentials are resolved by Boto3. Test exact IAM permissions and AWS pricing before running requests. Offline unit tests create no AWS resources.

## 4. Start two terminals at the same repository root

Terminal 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn milestones.milestone_2_api:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd milestones/milestone_3_frontend
npm.cmd run dev
```

Open http://127.0.0.1:5173 and http://127.0.0.1:8000/docs. The dev proxy sends `/api` to port 8000. Expect errors for datasets before Milestone 1B has actually published them; **never substitute the bundled examples as live data**.

## 5. CLI and tests (root directory)

```powershell
.\.venv\Scripts\python.exe -m milestones.milestone_1b_federation.cli --help
.\.venv\Scripts\python.exe -m pytest -q
.\scripts\check-fullstack.ps1
```

Optional live S3 GET smoke check **only after verifying AWS costs**:

```powershell
.\scripts\smoke-live-api.ps1
```

The `fetch` command contacts the historical weather provider, while `publish` **writes real S3 objects** and requires `--confirm-aws-charges`. Read the 1B README before using either.
