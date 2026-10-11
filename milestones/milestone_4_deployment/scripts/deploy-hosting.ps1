# EnviroSync M4A AWS Free account plan hosting. NO environmental bucket access.
# Runs read-only plan/identity checks before any AWS resource changes.
param(
    [string]$StackName = 'envirosync-hosting',
    [string]$Region = 'ap-south-1',
    [switch]$ConfirmAwsCredits,
    [switch]$SkipTests,
    [switch]$PreflightOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($Region -ne 'ap-south-1') { throw 'Hosting-only AWS Free plan deployment is restricted to ap-south-1.' }
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
Set-Location $root
$python = if (Test-Path '.venv\Scripts\python.exe') { '.\.venv\Scripts\python.exe' } else { 'python' }
foreach ($tool in @('aws', 'sam', 'npm.cmd')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Install $tool before deployment." }
}
if ($python -eq 'python' -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Install Python 3.12 or create project .venv.'
}
& $python milestones/milestone_4_deployment/scripts/preflight_free_plan.py --region $Region
if ($LASTEXITCODE -ne 0) { throw 'AWS account plan preflight failed. No infrastructure was changed.' }
if ($PreflightOnly) {
    Write-Host 'PASS: Read-only preflight completed. No resources created.'
    exit 0
}
if (-not $ConfirmAwsCredits) {
    throw 'AWS resources consume Free Tier credits. Re-run with -ConfirmAwsCredits after reviewing account credits and hosting costs.'
}
Write-Host 'Deployment mode: M4A hosting only (no cross-region bucket access).'
Write-Host "Region: $Region | stack: $StackName"
if (-not $SkipTests) {
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
    Push-Location milestones/milestone_3_frontend
    try {
        & npm.cmd install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'npm install failed.' }
        & npm.cmd run test
        if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
    } finally { Pop-Location }
}
& $python milestones/milestone_4_deployment/scripts/stage_lambda.py
if ($LASTEXITCODE -ne 0) { throw 'Lambda staging failed.' }
$template = 'milestones/milestone_4_deployment/infrastructure/template.yaml'
& sam validate --template-file $template
if ($LASTEXITCODE -ne 0) { throw 'SAM template is invalid.' }
& sam build --template-file $template --build-dir .aws-sam/build
if ($LASTEXITCODE -ne 0) { throw 'SAM build failed.' }
& sam deploy --template-file .aws-sam/build/template.yaml --stack-name $StackName --region $Region --resolve-s3 --capabilities CAPABILITY_IAM --no-confirm-changeset --no-fail-on-empty-changeset
if ($LASTEXITCODE -ne 0) { throw 'SAM deployment failed; inspect CloudFormation events before retrying.' }

# No bucket IDs guessed: read them from CloudFormation outputs.
$outputs = @(aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].Outputs' --output json | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) { throw 'Could not read CloudFormation outputs.' }
function Get-Output([string]$key) {
    $result = @($outputs | Where-Object { $_.OutputKey -eq $key } | Select-Object -First 1)
    if ($result.Count -eq 0) { throw "CloudFormation output missing: $key" }
    return $result[0].OutputValue
}
$webBucket = Get-Output 'WebBucketName'
$distribution = Get-Output 'DistributionId'
$website = Get-Output 'WebsiteUrl'
$env:VITE_API_BASE_URL = ''
$frontendEnv = 'milestones/milestone_3_frontend/.env.production'
if (Test-Path $frontendEnv) { throw 'Remove frontend .env.production to ensure relative /api URLs.' }
Push-Location milestones/milestone_3_frontend
try {
    & npm.cmd install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Vite production build failed.' }
} finally { Pop-Location }
& aws s3 sync milestones/milestone_3_frontend/dist "s3://$webBucket/" --delete --region $Region --cache-control 'public,max-age=300'
if ($LASTEXITCODE -ne 0) { throw 'React upload failed.' }
& aws cloudfront create-invalidation --distribution-id $distribution --paths '/*' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'CloudFront invalidation failed.' }
Write-Host "Deployment completed. URL: $website"
Write-Host "Health: $website/api/health"
Write-Host 'Wait for CloudFront propagation, then run check_live_hosting.py --hosting-only.'
