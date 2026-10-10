# Run the WHOLE dev stack with one command: backend + frontend together.
#
# Usage:  .\scripts\dev.ps1
#   Optional:  .\scripts\dev.ps1 -NoMigrate   (skip the initial migrate call)
#
# What it does:
#   1. Applies database migrations once (visible in this window; fails fast).
#   2. Opens window 1 -> scripts\dev-backend.ps1   (Django, http://127.0.0.1:8000)
#   3. Opens window 2 -> scripts\dev-frontend.ps1  (Next.js, http://localhost:3000)
#
# Each server keeps its own console, so logs never interleave. Close a window
# to stop that server (its whole process tree goes down with it).
#
# Frontend deps install automatically on first run. Copy
# frontend\.env.example to frontend\.env.local first if you need custom
# BACKEND_URL / NEXT_PUBLIC_BACKEND_URL values (defaults point at the backend).

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

$backendScript = Join-Path $PSScriptRoot "dev-backend.ps1"
$frontendScript = Join-Path $PSScriptRoot "dev-frontend.ps1"

# The repository path contains spaces, so the -File path is embedded with
# explicit quotes inside a single argument string (Start-Process does not
# quote array elements itself).
$backendArgs = "-NoExit -ExecutionPolicy Bypass -File `"$backendScript`" -NoMigrate"
$frontendArgs = "-NoExit -ExecutionPolicy Bypass -File `"$frontendScript`""

Write-Host "Starting backend and frontend in separate windows..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList $backendArgs
Start-Process powershell -ArgumentList $frontendArgs

Write-Host ""
Write-Host "Backend  (window 1): http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Frontend (window 2): http://localhost:3000" -ForegroundColor Green
Write-Host "Close a window to stop that server." -ForegroundColor Yellow
