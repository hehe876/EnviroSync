$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "../milestones/milestone_3_frontend"))
if (-not (Test-Path "node_modules")) {
    throw "Run .\scripts\setup-frontend.ps1 from the repository root first."
}
& npm.cmd run dev
