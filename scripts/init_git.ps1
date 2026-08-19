# Initialize git repo with structured commits for MONOLITH
# Run from project root after installing Git: winget install Git.Git

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git not found. Install: winget install Git.Git" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path .git)) {
    git init -b main
    Write-Host "Initialized git repository" -ForegroundColor Green
} else {
    Write-Host "Git repo already exists" -ForegroundColor Yellow
}

$status = git status --porcelain
if (-not $status) {
    Write-Host "Nothing to commit - working tree clean" -ForegroundColor Green
    git log -3 --oneline 2>$null
    exit 0
}

$hasCommits = $false
try {
    git rev-parse HEAD 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $hasCommits = $true }
} catch {
    $hasCommits = $false
}

git add -A
$gitIdentity = @("-c", "user.email=monolith@local.dev", "-c", "user.name=MONOLITH")
if (-not $hasCommits) {
    git @gitIdentity commit -m "Initial commit: MONOLITH algo trading platform"
    Write-Host "Created initial commit" -ForegroundColor Green
} else {
    git @gitIdentity commit -m "Add production infrastructure: ML pipeline, Docker, drift monitoring, smoke tests"
    Write-Host "Created commit" -ForegroundColor Green
}

Write-Host ""
Write-Host "Recent commits:"
git log -3 --oneline

Write-Host ""
Write-Host "Remote setup (manual):"
Write-Host "  git remote add origin https://github.com/YOU/monolith-algo-trading.git"
Write-Host "  git push -u origin main"
