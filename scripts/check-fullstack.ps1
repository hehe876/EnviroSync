$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
& ".\.venv\Scripts\python.exe" -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }
Push-Location milestones/milestone_3_frontend
try {
    & npm.cmd run test
    if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed" }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
} finally { Pop-Location }
Write-Host "Fullstack offline checks passed. These checks do not prove live AWS data is published."
