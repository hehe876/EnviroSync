#Requires -Version 5.1
<#
.SYNOPSIS
    One-command, guarded EnviroSync M4C administrator upload setup.
.DESCRIPTION
    Validates the existing repo and AWS Free Plan, runs local tests, deploys
    the separate Cognito Lite admin stack if necessary, provisions one admin,
    sets GitHub environment variables, and starts the existing manual M4C
    GitHub Actions workflow. Does NOT modify the environmental buckets directly,
    write credentials to files, force-push, or enroll MFA for the user.

    Run from the EnviroSync repository root:
        .\setup-m4c.ps1

    Requirements: AWS CLI v2 authenticated to the correct account, gh CLI
    authenticated with repo/environment-variable write access, Git, Python
    with the project's dev dependencies, Node/npm, and SAM CLI.
#>
[CmdletBinding()]
param(
    [string]$AdminEmail = '',
    [string]$DomainPrefix = '',
    [switch]$SkipLocalTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Region = 'ap-south-1'
$ExpectedAccountId = '563147319263'
$GitHubRepo = 'hehe876/EnviroSync'
$GitHubEnvironment = 'hosting'
$HostingStackName = 'envirosync-hosting'
$AuthStackName = 'envirosync-admin-auth'
$RepoRoot = (Get-Location).Path
$DeployWorkflow = '.github/workflows/deploy-hosting.yml'
$AuthTemplate = 'milestones/milestone_4_deployment/infrastructure/cognito-admin.yaml'
$HostingTemplate = 'milestones/milestone_4_deployment/infrastructure/template.yaml'
$AdminCreator = 'milestones/milestone_4_deployment/scripts/create_admin.py'
$Preflight = 'milestones/milestone_4_deployment/scripts/preflight_free_plan.py'

function Step([string]$Title) {
    Write-Host "`n=== $Title ===" -ForegroundColor Cyan
}

function Require-Tool([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing $Name. Install it, reopen PowerShell, and rerun the script."
    }
}

function Check-Exit([string]$Label) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed (exit code $LASTEXITCODE). No GitHub deployment was triggered."
    }
}

# Obtain a CloudFormation stack without mistaking AccessDenied for a missing stack.
function Get-CfnStack([string]$Name) {
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $result = & aws cloudformation describe-stacks --stack-name $Name --region $Region --output json --no-cli-pager 2>&1
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($code -ne 0) {
        $message = ($result | Out-String).Trim()
        if ($message -match '(?i)(does not exist|not exist)' -and $message -match 'ValidationError') {
            return $null
        }
        throw "Cannot inspect CloudFormation stack '$Name': $message"
    }
    $response = ($result | Out-String | ConvertFrom-Json)
    if (-not $response.Stacks -or $response.Stacks.Count -ne 1) {
        throw "Expected exactly one CloudFormation stack named $Name."
    }
    return $response.Stacks[0]
}

function Require-CompleteStack($Stack, [string]$Name) {
    if ($Stack.StackStatus -notin @('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE', 'IMPORT_COMPLETE')) {
        throw "Stack $Name is in status $($Stack.StackStatus). Resolve it before continuing."
    }
}

function Stack-Output($Stack, [string]$Name) {
    $item = @($Stack.Outputs | Where-Object { $_.OutputKey -eq $Name })
    if ($item.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$item[0].OutputValue)) {
        throw "Stack output '$Name' was not found."
    }
    return [string]$item[0].OutputValue
}

function Get-GhVariable([string]$Name, [bool]$EnvironmentLevel) {
    $args = @('variable', 'get', $Name, '--repo', $GitHubRepo)
    if ($EnvironmentLevel) { $args += @('--env', $GitHubEnvironment) }
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $value = & gh @args 2>$null
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($code -ne 0) { return '' }
    return (($value | Out-String).Trim())
}

function Set-GhVariable([string]$Name, [string]$Value) {
    & gh variable set $Name --env $GitHubEnvironment --repo $GitHubRepo --body $Value
    Check-Exit "Setting GitHub environment variable $Name"
}

try {
    Step '1/7 - Local tools, repository and permissions'
    foreach ($name in @('git', 'gh', 'aws', 'python', 'npm', 'sam')) {
        Require-Tool $name
    }
    foreach ($path in @($DeployWorkflow, $AuthTemplate, $HostingTemplate, $AdminCreator, $Preflight)) {
        if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $path) -PathType Leaf)) {
            throw "Missing M4C file '$path'. Run this script from your EnviroSync repository root."
        }
    }

    $branch = (& git branch --show-current).Trim()
    Check-Exit 'Reading the Git branch'
    if ($branch -ne 'main') { throw "Expected branch 'main', found '$branch'." }

    $origin = (& git remote get-url origin).Trim()
    Check-Exit 'Reading Git origin'
    if ($origin -notmatch '(?i)github\.com[:/]hehe876/EnviroSync(\.git)?$') {
        throw "Git origin is not the expected $GitHubRepo repository."
    }

    $dirtyTracked = (& git status --porcelain --untracked-files=no | Out-String).Trim()
    Check-Exit 'Checking tracked files'
    if ($dirtyTracked) { throw "Commit or stash tracked changes first:`n$dirtyTracked" }
    # Untracked files are allowed; .env and local IAM policy files are NOT uploaded.
    & git fetch origin main
    Check-Exit 'Fetching the current GitHub main branch'
    $localHead = (& git rev-parse HEAD).Trim()
    Check-Exit 'Reading local HEAD'
    $remoteHead = (& git rev-parse origin/main).Trim()
    Check-Exit 'Reading remote HEAD'
    if ($localHead -ne $remoteHead) {
        throw 'Local main is not identical to origin/main. Resolve Git history before deploying.'
    }

    & gh auth status --hostname github.com *> $null
    Check-Exit 'GitHub CLI authentication'
    & gh api "repos/$GitHubRepo/environments/$GitHubEnvironment" --jq '.name' *> $null
    Check-Exit 'Verifying the existing GitHub hosting environment'

    $deployRole = Get-GhVariable 'AWS_DEPLOY_ROLE_ARN' $true
    if (-not $deployRole) { $deployRole = Get-GhVariable 'AWS_DEPLOY_ROLE_ARN' $false }
    if (-not $deployRole) {
        throw "Set AWS_DEPLOY_ROLE_ARN in GitHub Actions variables for '$GitHubEnvironment' or the repository first."
    }
    if ($deployRole -notmatch ('^arn:aws:iam::' + [regex]::Escape($ExpectedAccountId) + ':role/')) {
        throw 'GitHub AWS_DEPLOY_ROLE_ARN does not reference the expected AWS account.'
    }

    Step '2/7 - Verify AWS identity, Free Plan and existing website'
    $identityRaw = & aws sts get-caller-identity --region $Region --output json --no-cli-pager
    Check-Exit 'AWS identity lookup'
    $identity = $identityRaw | Out-String | ConvertFrom-Json
    if ($identity.Account -ne $ExpectedAccountId) {
        throw "Wrong AWS account: $($identity.Account). Expected $ExpectedAccountId."
    }
    Write-Host "AWS account: $($identity.Account) (verified)"

    & python $Preflight --region $Region
    Check-Exit 'AWS Free Plan and credits preflight'

    $hostingStack = Get-CfnStack $HostingStackName
    if ($null -eq $hostingStack) { throw "Existing hosting stack '$HostingStackName' was not found." }
    Require-CompleteStack $hostingStack $HostingStackName
    $website = (Stack-Output $hostingStack 'WebsiteUrl').TrimEnd('/')
    if ($website -notmatch '^https://[a-zA-Z0-9.-]+$') {
        throw 'Unexpected WebsiteUrl; refusing to configure Cognito callback URLs.'
    }
    Write-Host "Existing website: $website"
    Write-Host 'No S3 buckets or CloudFront distributions will be created or deleted by this script.'

    Step '3/7 - Verify templates and application locally'
    & aws cloudformation validate-template --template-body "file://$AuthTemplate" --region $Region --output json --no-cli-pager | Out-Null
    Check-Exit 'Cognito template validation'
    & sam validate --template-file $HostingTemplate
    Check-Exit 'SAM template validation'

    if (-not $SkipLocalTests) {
        & python -m pytest -q
        Check-Exit 'Python tests'
        Push-Location 'milestones/milestone_3_frontend'
        try {
            & npm ci --no-audit --no-fund
            Check-Exit 'Installing the frontend from package-lock.json'
            & npm run test
            Check-Exit 'Frontend unit tests'
            & npm run build
            Check-Exit 'Vite production build'
        }
        finally { Pop-Location }
    }
    else {
        Write-Host 'Local pytest/npm checks skipped by explicit -SkipLocalTests flag.' -ForegroundColor Yellow
    }

    Step '4/7 - Review and approve AWS changes'
    if ([string]::IsNullOrWhiteSpace($AdminEmail)) {
        $AdminEmail = (Read-Host 'Administrator email').Trim().ToLowerInvariant()
    }
    if ($AdminEmail -notmatch '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$') {
        throw 'Invalid administrator email address.'
    }

    $authStack = Get-CfnStack $AuthStackName
    if ($null -eq $authStack) {
        if (-not $DomainPrefix) {
            $suffix = [guid]::NewGuid().ToString('N').Substring(0, 8)
            $DomainPrefix = "envirosync-$ExpectedAccountId-$suffix"
        }
        if ($DomainPrefix -notmatch '^[a-z0-9][a-z0-9-]{5,50}$') {
            throw 'DomainPrefix must be lowercase letters, numbers, hyphens; 6-51 characters.'
        }
        Write-Host "Will CREATE Cognito Lite stack '$AuthStackName' using domain '$DomainPrefix'."
    }
    else {
        Require-CompleteStack $authStack $AuthStackName
        $stackWebsite = @($authStack.Parameters | Where-Object { $_.ParameterKey -eq 'WebsiteUrl' })
        if ($stackWebsite.Count -ne 1 -or $stackWebsite[0].ParameterValue -ne $website) {
            throw 'Existing Cognito stack has a different website callback URL; stop and review.'
        }
        Write-Host "Will REUSE Cognito stack '$AuthStackName' (no stack replacement)."
    }

    Write-Host ''
    Write-Host 'Changes requiring your approval:' -ForegroundColor Yellow
    Write-Host '  - Create a Cognito Lite user pool/domain and a protected admin account (unless already created).'
    Write-Host '  - Set 4 GitHub hosting environment variables (Cognito IDs/domain and uploads opt-in).'
    Write-Host '  - Trigger ONE existing GitHub Actions deployment, adding a scoped S3 uploads policy.'
    Write-Host '  - Cognito, GitHub Actions, Lambda, S3 and CloudFront usage may spend AWS Free Plan credits.'
    Write-Host '  - IAM deployment permissions must already be sufficient; this script never broadens them.'
    Write-Host '  - TOTP MFA must still be enrolled interactively during first browser login.'
    $approval = Read-Host 'Type ENABLE M4C to approve these changes'
    if ($approval -cne 'ENABLE M4C') { throw 'Approval not given. No AWS resources changed.' }

    Step '5/7 - Provision or reuse Cognito, then create administrator'
    if ($null -eq $authStack) {
        & aws cloudformation deploy `
            --template-file $AuthTemplate `
            --stack-name $AuthStackName `
            --region $Region `
            --parameter-overrides "WebsiteUrl=$website" "DomainPrefix=$DomainPrefix" `
            --no-confirm-changeset `
            --no-fail-on-empty-changeset `
            --no-cli-pager
        Check-Exit 'Creating Cognito authentication stack'
        $authStack = Get-CfnStack $AuthStackName
        if ($null -eq $authStack) { throw 'Cognito deployment returned but its stack is missing.' }
        Require-CompleteStack $authStack $AuthStackName
    }

    $poolId = Stack-Output $authStack 'UserPoolId'
    $clientId = Stack-Output $authStack 'ClientId'
    $cognitoDomain = (Stack-Output $authStack 'CognitoDomain').TrimEnd('/')
    if ($cognitoDomain -notmatch '^https://[a-z0-9-]+\.auth\.ap-south-1\.amazoncognito\.com$') {
        throw 'Cognito domain output format is unexpected; refusing to deploy.'
    }
    Write-Host "Cognito domain: $cognitoDomain"
    Write-Host 'Next: set your administrator password at the secure Python prompt (not stored in Git).'
    & python $AdminCreator --email $AdminEmail --stack $AuthStackName
    Check-Exit 'Creating or updating the Cognito administrator account'

    Step '6/7 - Configure GitHub hosting environment'
    # Set the activation switch LAST, after every other value is safely stored.
    Set-GhVariable 'COGNITO_USER_POOL_ID' $poolId
    Set-GhVariable 'COGNITO_CLIENT_ID' $clientId
    Set-GhVariable 'COGNITO_DOMAIN' $cognitoDomain
    Set-GhVariable 'ENVIROSYNC_UPLOADS_ENABLED' 'true'
    Write-Host 'GitHub environment configured for admin-only uploads.'

    Step '7/7 - Start the existing deployment workflow once'
    Write-Host 'Starting one deployment; this does NOT mean the deployment has passed.'
    & gh workflow run 'deploy-hosting.yml' --repo $GitHubRepo --ref main
    Check-Exit 'Starting GitHub Actions M4C deployment'
    $actionsUrl = "https://github.com/$GitHubRepo/actions/workflows/deploy-hosting.yml"

    Write-Host ''
    Write-Host 'SETUP COMPLETED; THE DEPLOYMENT IS RUNNING, NOT YET VERIFIED.' -ForegroundColor Green
    Write-Host "Actions: $actionsUrl"
    Write-Host "After the workflow succeeds: $website"
    Write-Host 'Open the dashboard, click Administrator sign in, enroll TOTP MFA, then upload Berlin CSV.'
    Write-Host 'If the workflow fails, check its first failed step before rerunning (especially IAM PutRolePolicy).'
    Write-Host 'Your existing Chennai/London S3 data was not modified by this setup script.'
}
catch {
    Write-Host ''
    Write-Host "STOPPED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Do not repeatedly rerun the deployment on error. Fix the reported prerequisite first.' -ForegroundColor Yellow
    exit 1
}
