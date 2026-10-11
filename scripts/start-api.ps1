$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Run .\scripts\setup.ps1 first."
}
& ".\.venv\Scripts\python.exe" -m uvicorn milestones.milestone_2_api:app --host 127.0.0.1 --port 8000
