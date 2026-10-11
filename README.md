# EnviroSync — Milestone-block modular monorepo

This is the **complete merged** source for Milestones **1A**, **1B**, **2** and the React frontend block. Each milestone owns exactly one functional area; code from earlier milestones is **imported, not copied**.

## Block map

| Folder | Function | Depends on |
|---|---|---|
| `milestones/milestone_1a_infrastructure/` | Existing AWS S3 resource contract and security prerequisites | Existing AWS infrastructure (external) |
| `milestones/milestone_1b_federation/` | Ingestion → regional S3 → global catalog → federated retrieval, integrity, CLI | Existing 1A buckets |
| `milestones/milestone_2_api/` | FastAPI REST gateway and validation | Imports **one** implementation of 1B |
| `milestones/milestone_3_frontend/` | React/Vite UI and presentation logic | Calls Milestone 2 over HTTP |
| `scripts/` | Windows setup/start/check scripts for the entire repo | No business logic |
| `milestones/milestone_4_deployment/` | AWS SAM hosting template, staging, smoke tests, GitHub OIDC workflow | Imports 1B/2, serves existing React |
| `.github/workflows/` | Offline GitHub CI for both Python and React | No AWS keys |

> **Naming:** `milestone_3_frontend` is a proposed block name for the frontend brought in-house; it is not a claim that a separate officially scoped Milestone 3 has already been completed.
> This is a modular monorepo/modular monolith at runtime, **not independently deployed microservices**. Dedicated services can be extracted later if requirements justify them.

## Import and HTTP dependencies

```text
External existing AWS S3 (1A)
           ^
  Milestone 1B (Boto3)
     ^           ^
   CLI      Milestone 2 (FastAPI)
                     ^  HTTP /api/*
               React Frontend
```

Ingest flow: `Open-Meteo ERA5 → 1B.ingestion → 1B.federation → regional S3 + global catalog`.
Query flow: `React → 2.API → 1B.federation → 1B.catalog/storage → S3 → SHA-256 validated data`.

## Host the complete application publicly (Milestone 4A)

See [Milestone 4A AWS deployment guide](milestones/milestone_4_deployment/README.md). This AWS Free account plan release provides a CloudFront HTTPS URL, private S3 frontend and Lambda-hosted FastAPI backend. **M4A hosts the UI/API only and makes no environmental S3 calls**; the read-only Free plan preflight checks credits before provisioning. The deployment can consume credits.

## Start from a clean Windows 11 machine

**Prerequisites:** Python 3.12 (`py` launcher), Node.js 22 LTS and npm, PowerShell, VS Code; an internet connection for dependency installs. AWS CLI and AWS credentials are only needed for optional live S3 calls.

1. Extract ZIP to a **new location**, preserving the included `EnviroSync/` folder. Open that folder in VS Code. Do **not** overwrite your existing `.env` or `.git`.
2. From **the repository root** (this folder), run:

   ```powershell
   .\scripts\setup.ps1
   .\scripts\setup-frontend.ps1
   ```

   If PowerShell blocks execution, use the individual commands in [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md).

3. Set the **existing** Milestone 1A bucket names in the ignored root `.env`; **never store AWS access keys or IAM account IDs in Git**. Offline tests run without this configuration.
4. Start two terminals at this root:

   ```powershell
   .\scripts\start-api.ps1
   # New PowerShell terminal at the same root:
   .\scripts\start-frontend.ps1
   ```

5. Visit http://127.0.0.1:5173 (dashboard) and http://127.0.0.1:8000/docs (API). `/api/health` is local only; data pages need live published Milestone 1B S3 objects.
6. Run every offline check before pushing:

   ```powershell
   .\scripts\check-fullstack.ps1
   ```

Exact files and destinations: [docs/STRUCTURE.md](docs/STRUCTURE.md).

Full instructions: [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md). Paths and old-project migration: [docs/MIGRATION.md](docs/MIGRATION.md). Adding new blocks: [docs/NEW_MILESTONE_CONTRACT.md](docs/NEW_MILESTONE_CONTRACT.md).

## What is tested / not verified

- **50 Python tests passed offline** in the AWS Free plan M4A preparation, including hosting-only isolation and account-plan safeguards.
- **13 Node-only React utility tests passed offline**.
- CLI help and FastAPI local health endpoint verified.
- **Live AWS GET/PUT, actual AWS billing/Free Tier eligibility, Windows PowerShell runs, and Vite production build were not independently verified in this environment.** Do not mistake mocked tests for live AWS acceptance.
- React has no fabricated data fallback; S3 failure should surface as an error. No ML prediction endpoint exists.

## Safety and GitHub

`.gitignore` excludes `.env`, virtual environments, frontend dependencies, build outputs and local data previews. GitHub Actions runs offline tests **without AWS keys**. Keep access tokens private and check `git status`/`git diff --cached` before commits.

```powershell
git init -b main
git add .
git status
git commit -m "Initial EnviroSync milestone-block architecture"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Retain `milestones/milestone_1b_federation/examples/` only as documented historical reference data, not data to be displayed as live API responses.
