
$ErrorActionPreference = "Stop"

function Invoke-Check {
    param(
        [string]$Name,
        [string[]]$Command
    )

    Write-Host "`n========== $Name ==========" -ForegroundColor Cyan

    & $Command[0] $Command[1..($Command.Length - 1)]

    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed. Fix the errors before committing."
    }

    Write-Host "$Name passed!" -ForegroundColor Green
}

Invoke-Check "Pytest" @("uv", "run", "pytest")
Invoke-Check "Ruff lint" @("uv", "run", "ruff", "check", ".")
Invoke-Check "Ruff format" @("uv", "run", "ruff", "format", "--check", ".")
Invoke-Check "Pre-commit" @("uv", "run", "pre-commit", "run", "--all-files")

Write-Host "`nAll quality checks passed!" -ForegroundColor Green
