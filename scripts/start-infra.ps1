# Start the dev services (PostgreSQL + Redis) via Docker Compose.
# Optional — skip if you already run native PostgreSQL/Redis on Windows.
#
# Usage:  .\scripts\start-infra.ps1
param(
    [switch]$Stop   # tear the containers down instead of starting them
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is not installed or not on PATH." -ForegroundColor Red
    Write-Host "Install Docker Desktop for Windows (WSL2 backend), then re-run this script."
    Write-Host "Alternative: run PostgreSQL and Redis natively and point DATABASE_URL / REDIS_URL at them."
    exit 1
}

if ($Stop) {
    docker compose down
    exit $LASTEXITCODE
}

docker compose up -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Waiting for services to become healthy..." -ForegroundColor Cyan
docker compose ps --format "table {{.Service}}\t{{.Status}}"
Write-Host "PostgreSQL:  postgres://nazbeen:nazbeen@localhost:5432/nazbeen_forex" -ForegroundColor Green
Write-Host "Redis:       redis://localhost:6379/0" -ForegroundColor Green