# Run the Django backend in development on http://127.0.0.1:8000
#
# Usage:  .\scripts\dev-backend.ps1
param(
    [switch]$NoMigrate  # skip the initial migrate call
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $NoMigrate) {
    Write-Host "Applying migrations..." -ForegroundColor Cyan
    uv run python manage.py migrate
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Starting Django development server..." -ForegroundColor Cyan
uv run python manage.py runserver 127.0.0.1:8000