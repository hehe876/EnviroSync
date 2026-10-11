$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "../milestones/milestone_3_frontend"))
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js/npm not available. Install Node.js 22 LTS, then reopen VS Code."
}
& npm.cmd install
if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed" }
& npm.cmd run test
if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed" }
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
Write-Host "Frontend dependencies installed, tests passed, and build complete."
