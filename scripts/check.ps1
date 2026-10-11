$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
& ".\.venv\Scripts\python.exe" -m pytest -v
if ($LASTEXITCODE -ne 0) { throw "Offline tests failed" }
& ".\.venv\Scripts\python.exe" -c "from milestones.milestone_2_api import app; from milestones.milestone_1b_federation.federation import S3Federation; print('Modular imports OK')"
if ($LASTEXITCODE -ne 0) { throw "Import check failed" }
