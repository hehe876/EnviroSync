# EnviroSync M4C — ALL-IN-ONE ZIP

This ZIP is a **repository overlay**. Every file is stored at its exact path relative to the root of your existing `hehe876/EnviroSync` repository.

It includes all 22 full M4C implementation/test/example files, the complete one-command `setup-m4c.ps1`, the Windows deployment guide, and a SHA-256 file manifest. You do NOT need to create a second repository or replace your `.git` folder.

## Apply to your Windows repository (PowerShell)

1. Save `EnviroSync_M4C_All_In_One_Repo_Overlay.zip` to Downloads.
2. Open PowerShell inside your existing **EnviroSync** repository root.
3. Run:

```powershell
# Confirm your location before extracting
Get-Location
git status

# Save a Git reference for rollback (only once; change the name if it already exists)
git branch backup/before-m4c-onezip

# Extract directly into the repo root; do not create a second EnviroSync folder
Expand-Archive -LiteralPath "$HOME\Downloads\EnviroSync_M4C_All_In_One_Repo_Overlay.zip" -DestinationPath . -Force

# See exactly what changed
git status --short
```

This ZIP never contains `.git`, `.env`, virtual environments, AWS credentials, or generated `node_modules` / `dist` / Lambda build folders. It only replaces the specified M4C source files and adds `setup-m4c.ps1` and this README.

## Run tests and push safely

Your repository's `main` branch may **already** have the M4C files. If `git status` only shows the setup script, README, or SHA manifest, that is normal. Do NOT commit random untracked IAM policy/credentials files.

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
cd milestones/milestone_3_frontend
npm ci --no-audit --no-fund
npm run test
npm run build
cd ../..

# Stage only this feature's sources, docs and automation (NOT unrelated untracked files)
git add .github/workflows/deploy-hosting.yml pyproject.toml MILESTONE_4C_SETUP_WINDOWS.md M4C_ONE_ZIP_README.md M4C_FILE_SHA256.txt setup-m4c.ps1
git add milestones/milestone_2_api milestones/milestone_3_frontend/src milestones/milestone_4_deployment/infrastructure milestones/milestone_4_deployment/scripts milestones/milestone_4_deployment/tests milestones/milestone_4_deployment/examples
git diff --cached --check
git diff --cached --stat
```

If the staged changes are what you expect:

```powershell
git commit -m "Bundle EnviroSync M4C admin upload setup"
git pull --rebase origin main
git push origin main
```

If Git says there is nothing to commit, the code is already pushed. `git status` can still show unrelated untracked files; inspect them rather than adding them blindly.

## One-command deployment setup

From the same repository root, after the Git push succeeds:

```powershell
.\setup-m4c.ps1
```

Requirements: AWS CLI v2, SAM CLI, `gh` authenticated for your repo's GitHub Actions `hosting` environment variables, Git, Python dependencies, and Node/npm. The script checks the expected AWS account, active AWS Free Plan credits, code tests, CloudFormation templates, and deployment role before asking for approval.

**This script makes real AWS changes after confirmation.** It may create a Cognito Lite user pool and administrator, update GitHub environment variables, and trigger the existing GitHub Actions deployment. Supported AWS services can consume credits. It does NOT automatically perform MFA enrollment; finish TOTP in the browser on first admin sign-in. It does not change existing environmental S3 objects.

**Before running setup, review** `MILESTONE_4C_SETUP_WINDOWS.md`, especially AWS cost/permissions. The long manual deployment steps are an ALTERNATIVE to the automated setup; do not run both paths unless troubleshooting.

## Upload test after workflow succeeds

Open your deployed CloudFront site -> `Administrator sign in` -> enroll TOTP -> upload `milestones/milestone_4_deployment/examples/berlin-sample.csv` with city `berlin`, country `Germany`, source `Demo data`, region `eu-west-2`. Confirm it appears in the catalog and can be compared to existing cities where dates overlap.

The ZIP is a source-code deliverable; no AWS deployment or live upload test has been performed by creating this archive.
