# GitHub repo, milestone updates, and required integration proof

## Create a clean new repository

Do not initialize Git inside the old extracted milestone folders. Use the new top-level `EnviroSync` directory containing this README and `pyproject.toml`. Review `.gitignore` before uploading. The ZIP contains **no `.git`, `.venv`, `.env`, `.aws`, private keys or AWS credentials**.

```powershell
git init -b main
git add .
git status --short
git diff --cached --name-only
git commit -m "Refactor EnviroSync into modular backend"
git remote add origin https://github.com/<username>/<repository>.git
git push -u origin main
```

Create an empty repository on GitHub with no auto-generated README/license to keep first push straightforward. Do not force-push an existing remote; if the remote already contains commits, inspect and integrate it first. For coursework, include the GitHub URL and test evidence in your submission.

### GitHub Actions

`.github/workflows/tests.yml` executes Python 3.12 `pytest` offline on pushes/PRs and installs packages using `pip install -e '.[dev]'`. It uses no AWS credentials or real S3 calls. A green workflow proves local behavior only, **not deployed account integration**.

## Milestones 1A / 1B / 2 in one source tree

| Existing milestone | Canonical source location | Don't copy again |
| --- | --- | --- |
| 1A S3 resources | AWS account + `config/settings.py` pointer | No new bucket provisioning, no local static AWS secrets |
| 1B weather | `ingestion/` | No duplicated `weather.py` in another folder |
| 1B regional operations | `storage/`, `catalog/`, `federation/` | No full copied Milestone 1B tree |
| 2 local REST | `api/` | No copy of 1B files inside Milestone 2 |
| React dashboard | `frontend/` | Included; client-side GET API integration, no AWS SDK/keys in browser |

## Future delivery standard (apply to every future milestone)

1. **Incremental patch only**: new feature's module files + tests + docs; no duplicate project snapshot unless a full clean-source release is explicitly requested.
2. Provide a **before/after directory tree** and exact destination relative to repo root for every file.
3. Distinguish *ADD*, *MODIFY*, *REMOVE*, or *RENAME*; preserve public contracts or document migrations.
4. Every added Python module exports an explicit interface and avoids dependency on FastAPI unless it is an API module.
5. Update `pyproject.toml` if dependencies change, avoiding divergent per-milestone `requirements.txt` files.
6. Add fake-S3/HTTP unit and integration tests (positive and negative cases) runnable via `.\.venv\Scripts\python.exe -m pytest -q`.
7. If new AWS resources/services are needed, **do not automatically enable or provision them**. Verify eligibility, IAM and likely costs and obtain approval first.
8. Include exact PowerShell commands and truthful expected output, plus how to roll back the change.
9. Update README, architecture diagram, API contract and GitHub Actions as appropriate.
10. Make the milestone in a feature branch and PR rather than replacing `main` from a new zip.

Example next-branch workflow:

```powershell
git switch -c feature/milestone-3
# add new files inside src/enviro_sync/<module>/, tests/, docs/
.\.venv\Scripts\python.exe -m pytest -q
git add .
git commit -m "Implement milestone 3 module with tests"
git push -u origin feature/milestone-3
```

Open a GitHub pull request and merge only after CI passes and the live-feature boundaries are independently checked.

## Integration tests and negative controls

`tests/test_modular_integration.py` proves the API doesn't magically fabricate Milestone 1B results:

- Without catalog, `/api/health` is still 200 but `/api/datasets` returns 502 (`INVALID_REMOTE_DATA`).
- After fake publishing both regional datasets, `/api/compare` returns correct data and verified London source. Removing the London object makes it return 502; publishing both again restores 200.
- Removing only the catalog makes `/api/datasets` fail.

This is deterministic **offline behavioral evidence**. It is stronger than checking filenames and mocks the AWS transport layer only (not the app's federation or API logic), but still does **not** prove IAM, bucket location or AWS billing conditions on a real account. Live acceptance remains a separate manual check documented in `AWS_AND_LIVE_CHECKS.md`.
