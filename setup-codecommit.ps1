<#
.SYNOPSIS
    Sets up the five Intelli RFID git repositories and their AWS CodeCommit remotes.

.DESCRIPTION
    Five repositories, deliberately separate:

        intelli-rfid-workspace      this directory - shared docs only
        intelli-rfid-core           apps\intelli-rfid-core
        intelli-rfid-reader-test    apps\intelli-rfid-reader-test
        intelli-rfid-tunnel         apps\intelli-rfid-tunnel
        intelli-rfid-wayside        apps\intelli-rfid-wayside

    The workspace repo ignores apps\ entirely, so this is not a monorepo - each app
    stays independently versioned and independently shippable.

    Run with no switches to see the current state. Nothing is created or pushed
    unless you ask for it.

.PARAMETER Region
    AWS region. Defaults to $env:AWS_REGION, then ap-south-1.

.PARAMETER Create
    Create any missing repositories in CodeCommit. Requires the AWS CLI.

.PARAMETER Push
    Push each repository's main branch to origin.

.PARAMETER SetupCredentials
    Configure git's global credential helper to use the AWS CLI for CodeCommit.
    Run this once per machine if pushes prompt for a password.

.EXAMPLE
    .\setup-codecommit.ps1
    Show the status of all five repositories.

.EXAMPLE
    .\setup-codecommit.ps1 -Create -Push
    Create the CodeCommit repositories, then push everything.
#>
[CmdletBinding()]
param(
    [string]$Region,
    [switch]$Create,
    [switch]$Push,
    [switch]$SetupCredentials
)

Set-StrictMode -Version Latest

if (-not $Region) {
    $Region = if ($env:AWS_REGION) { $env:AWS_REGION } else { 'ap-south-1' }
}

$Root = $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }

# The workspace repo is this directory; the four app repos live under apps\.
# Paths are built with Join-Path so the script is not tied to a path separator.
$AppNames = @(
    'intelli-rfid-core'
    'intelli-rfid-reader-test'
    'intelli-rfid-tunnel'
    'intelli-rfid-wayside'
)

$Targets = @(
    [pscustomobject]@{ Name = 'intelli-rfid-workspace'; Path = $Root; Label = '.' }
)
foreach ($app in $AppNames) {
    $Targets += [pscustomobject]@{
        Name  = $app
        Path  = (Join-Path (Join-Path $Root 'apps') $app)
        Label = (Join-Path 'apps' $app)
    }
}

# ---------------------------------------------------------------- helpers

function Test-Tool([string]$Name) {
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

# Runs git and returns stdout, with the exit code in $script:GitExitCode.
# git writes ordinary progress to stderr, so stderr is NOT treated as failure.
function Invoke-Git {
    param([string]$RepoPath, [Parameter(ValueFromRemainingArguments)][string[]]$GitArgs)
    $output = & git -C $RepoPath @GitArgs 2>&1
    $script:GitExitCode = $LASTEXITCODE
    return ($output | Out-String).Trim()
}

function Write-Status([string]$Symbol, [string]$Message, [string]$Colour = 'Gray') {
    Write-Host ("  {0} {1}" -f $Symbol, $Message) -ForegroundColor $Colour
}

# ---------------------------------------------------------------- preflight

Write-Host ''
Write-Host 'Intelli RFID - CodeCommit setup' -ForegroundColor Cyan
Write-Host ("Root:   {0}" -f $Root)
Write-Host ("Region: {0}" -f $Region)
Write-Host ''

if (-not (Test-Tool 'git')) {
    Write-Host 'git was not found on PATH. Install Git for Windows: https://git-scm.com/download/win' -ForegroundColor Red
    exit 1
}

$HasAws = Test-Tool 'aws'
if ($Create -and -not $HasAws) {
    Write-Host 'The AWS CLI was not found on PATH, so -Create cannot run.' -ForegroundColor Red
    Write-Host 'Install it (https://aws.amazon.com/cli/) or create the repositories in the AWS console.' -ForegroundColor Red
    exit 1
}

if ($SetupCredentials) {
    if (-not $HasAws) {
        Write-Host 'The AWS CLI was not found; the credential helper needs it at push time.' -ForegroundColor Red
        exit 1
    }
    git config --global credential.helper '!aws codecommit credential-helper $@'
    git config --global credential.UseHttpPath true
    Write-Host 'Configured git to use the AWS CLI credential helper for CodeCommit.' -ForegroundColor Green
    Write-Host ''
}

# ---------------------------------------------------------------- main

$Summary = @()

foreach ($Target in $Targets) {
    $Name = $Target.Name
    $Path = $Target.Path

    Write-Host $Name -ForegroundColor White

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        Write-Status '-' "no directory at $($Target.Label), skipping" 'DarkGray'
        $Summary += [pscustomobject]@{ Repo = $Name; Commits = '-'; Remote = '-'; Pushed = 'skipped' }
        Write-Host ''
        continue
    }

    # --- repository ---
    if (-not (Test-Path -LiteralPath (Join-Path $Path '.git'))) {
        Invoke-Git $Path init -q -b main | Out-Null
        Write-Status '+' 'initialised repository' 'Green'
    }

    # --- initial commit ---
    Invoke-Git $Path rev-parse --verify HEAD | Out-Null
    if ($script:GitExitCode -ne 0) {
        Invoke-Git $Path add -A | Out-Null
        $msg = @"
Initial commit: $Name

Scaffolded against the Silion ModuleAPI_J SDK (SIM7500 / Impinj E710),
targeting a Raspberry Pi CM4 on board the reader.
"@
        Invoke-Git $Path commit -q -m $msg | Out-Null
        if ($script:GitExitCode -eq 0) {
            Write-Status '+' 'created initial commit' 'Green'
        } else {
            Write-Status '!' 'nothing to commit' 'Yellow'
        }
    }

    $Commits = Invoke-Git $Path rev-list --count HEAD
    if ($script:GitExitCode -ne 0) { $Commits = '0' }

    # --- remote ---
    $Url = "https://git-codecommit.$Region.amazonaws.com/v1/repos/$Name"
    $Existing = Invoke-Git $Path remote get-url origin
    if ($script:GitExitCode -ne 0) {
        Invoke-Git $Path remote add origin $Url | Out-Null
        Write-Status '+' "origin -> $Url" 'Green'
    } elseif ($Existing -ne $Url) {
        Invoke-Git $Path remote set-url origin $Url | Out-Null
        Write-Status '~' "origin updated -> $Url" 'Yellow'
    } else {
        Write-Status '=' "origin -> $Url" 'DarkGray'
    }

    # --- create in CodeCommit ---
    if ($Create) {
        & aws codecommit get-repository --repository-name $Name --region $Region 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Status '=' 'already exists in CodeCommit' 'DarkGray'
        } else {
            & aws codecommit create-repository `
                --repository-name $Name `
                --repository-description "Intelli RFID: $Name" `
                --region $Region 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Status '+' 'created in CodeCommit' 'Green'
            } else {
                Write-Status 'x' 'could not create in CodeCommit (check credentials and region)' 'Red'
            }
        }
    }

    # --- push ---
    $PushState = if ($Push) { 'pending' } else { 'not requested' }
    if ($Push) {
        $result = Invoke-Git $Path push -u origin main
        if ($script:GitExitCode -eq 0) {
            Write-Status '+' 'pushed main' 'Green'
            $PushState = 'pushed'
        } else {
            Write-Status 'x' 'push failed' 'Red'
            foreach ($line in ($result -split "`n" | Select-Object -First 4)) {
                Write-Host ("      {0}" -f $line.Trim()) -ForegroundColor DarkRed
            }
            $PushState = 'FAILED'
        }
    }

    $Summary += [pscustomobject]@{
        Repo    = $Name
        Commits = $Commits
        Remote  = $Name
        Pushed  = $PushState
    }
    Write-Host ''
}

# ---------------------------------------------------------------- summary

Write-Host 'Summary' -ForegroundColor Cyan

# Formatted by hand rather than with Format-Table: Format-Table renders nothing when
# output is redirected to a file or a pipe, so the summary would silently vanish from
# any log. This works in a console and in CI alike.
$w = ($Summary.Repo | Measure-Object -Maximum -Property Length).Maximum
if (-not $w -or $w -lt 4) { $w = 4 }
Write-Host ('  {0}  {1,7}  {2}' -f 'REPOSITORY'.PadRight($w), 'COMMITS', 'PUSHED') -ForegroundColor DarkGray
foreach ($row in $Summary) {
    $colour = switch ($row.Pushed) {
        'pushed'  { 'Green' }
        'FAILED'  { 'Red' }
        'skipped' { 'DarkGray' }
        default   { 'Gray' }
    }
    Write-Host ('  {0}  {1,7}  {2}' -f $row.Repo.PadRight($w), $row.Commits, $row.Pushed) -ForegroundColor $colour
}
Write-Host ''

if (-not $Create -and -not $Push) {
    Write-Host 'Nothing was created or pushed. To do both:' -ForegroundColor Yellow
    Write-Host '    .\setup-codecommit.ps1 -Create -Push' -ForegroundColor Yellow
    Write-Host ''
}

if ($Summary | Where-Object { $_.Pushed -eq 'FAILED' }) {
    Write-Host 'Some pushes failed. Common causes:' -ForegroundColor Yellow
    Write-Host '  - The CodeCommit repository does not exist yet   -> re-run with -Create'
    Write-Host '  - git is prompting for credentials               -> .\setup-codecommit.ps1 -SetupCredentials'
    Write-Host '  - Wrong region                                   -> -Region <region>'
    Write-Host ''
}
