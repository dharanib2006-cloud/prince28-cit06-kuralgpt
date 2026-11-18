
$ErrorActionPreference = "Stop"

# Move to the project root folder
Set-Location (Split-Path $PSScriptRoot -Parent)

# Prevent accidental commits to main
$branch = git branch --show-current

if ($branch -ne "feat/day-02-postgres") {
    throw "You are on '$branch'. Switch to feat/day-02-postgres before committing."
}

Write-Host "`nRunning checks before staging..." -ForegroundColor Cyan
& "$PSScriptRoot\check.ps1"

if ($LASTEXITCODE -ne 0) {
    throw "Checks failed. Commit cancelled."
}

Write-Host "`nCurrent Git status:" -ForegroundColor Cyan
git status --short

$message = Read-Host "`nEnter your commit message"

if ([string]::IsNullOrWhiteSpace($message)) {
    throw "Commit message cannot be empty."
}

$confirm = Read-Host "Stage all changes and commit with this message? (yes/no)"

if ($confirm -ne "yes") {
    Write-Host "Commit cancelled. No changes were committed." -ForegroundColor Yellow
    exit
}

git add -A

if ($LASTEXITCODE -ne 0) {
    throw "Git staging failed."
}

Write-Host "`nRunning checks again, including staged files..." -ForegroundColor Cyan
& "$PSScriptRoot\check.ps1"

if ($LASTEXITCODE -ne 0) {
    throw "Checks failed. Commit cancelled. Your changes remain staged."
}

git commit -m $message

if ($LASTEXITCODE -ne 0) {
    throw "Git commit failed."
}

Write-Host "`nCommit completed successfully!" -ForegroundColor Green
git status
