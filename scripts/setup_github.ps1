# Create GitHub repo and push — run after: gh auth login
$ErrorActionPreference = "Stop"
$env:Path = "C:\Program Files\GitHub CLI;C:\Program Files\Git\bin;" + $env:Path

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

function Test-GhWorkflowScope {
    $status = gh auth status 2>&1 | Out-String
    return $status -match "workflow"
}

function Ensure-GhAuth {
    gh auth status 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Not logged in. Starting device login..." -ForegroundColor Yellow
        gh auth login --hostname github.com --git-protocol https --web
        if ($LASTEXITCODE -ne 0) { exit 1 }
    }
}

function Ensure-WorkflowScope {
    if (Test-GhWorkflowScope) { return $true }
    Write-Host ""
    Write-Host "GitHub token missing 'workflow' scope (required for .github/workflows/ push)." -ForegroundColor Yellow
    Write-Host "Run in terminal and approve in browser:" -ForegroundColor Yellow
    Write-Host "  gh auth refresh -h github.com -s workflow,repo"
    Write-Host "  https://github.com/login/device"
    Write-Host ""
    return $false
}

Ensure-GhAuth
$user = (gh api user --jq .login)
Write-Host "Logged in as: $user" -ForegroundColor Green

$repoName = "monolith-algo-trading"
$gitIdentity = @("-c", "user.email=monolith@local.dev", "-c", "user.name=MONOLITH")

# Remove placeholder remote if present
$remoteUrl = git remote get-url origin 2>$null
if ($remoteUrl -match "github.com/YOU/") {
    git remote remove origin
    Write-Host "Removed placeholder origin remote" -ForegroundColor Yellow
}

if (-not (git remote get-url origin 2>$null)) {
    Write-Host "Creating GitHub repo $repoName ..." -ForegroundColor Cyan
    gh repo create $repoName --public --source=. --remote=origin `
        --description "MONOLITH algo trading platform for MOEX"
    if ($LASTEXITCODE -ne 0) {
        git remote add origin "https://github.com/$user/$repoName.git"
    }
}

Write-Host "Pushing main branch..." -ForegroundColor Cyan
git push -u origin main
if ($LASTEXITCODE -ne 0) {
    $scopeOk = Ensure-WorkflowScope
    if (-not $scopeOk) {
        Write-Host ""
        Write-Host "If push failed on .github/workflows/, grant workflow scope then re-run this script." -ForegroundColor Red
        exit 1
    }
    git push -u origin main
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

# Push CI workflow if present locally but not yet on remote
if ((Test-Path ".github/workflows/test.yml") -and -not (Test-GhWorkflowScope)) {
    Write-Host ""
    Write-Host "CI workflow file exists locally but workflow scope is missing — not pushing .github/workflows/." -ForegroundColor Yellow
    Write-Host "After: gh auth refresh -h github.com -s workflow,repo" -ForegroundColor Yellow
    Write-Host "Run: git add .github/workflows/test.yml && git commit && git push" -ForegroundColor Yellow
} elseif (Test-Path ".github/workflows/test.yml") {
    $tracked = git ls-files --error-unmatch .github/workflows/test.yml 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Adding CI workflow..." -ForegroundColor Cyan
        git add .github/workflows/test.yml
        git @gitIdentity commit -m "Add GitHub Actions CI workflow"
        git push origin main
    }
}

$url = gh repo view --json url --jq .url
Write-Host ""
Write-Host "Repository: $url" -ForegroundColor Green
