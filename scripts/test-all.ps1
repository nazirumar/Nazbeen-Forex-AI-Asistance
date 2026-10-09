# Run the full automated verification suite (matches CI): Django checks,
# migration check, backend tests, then frontend typecheck + build.
#
# Usage:  .\scripts\test-all.ps1

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$failed = $false

Write-Host "=== 1/4 Django system check ===" -ForegroundColor Cyan
uv run python manage.py check
if ($LASTEXITCODE -ne 0) { $failed = $true }

Write-Host "=== 2/4 Migration check ===" -ForegroundColor Cyan
uv run python manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { $failed = $true }

Write-Host "=== 3/4 Backend tests ===" -ForegroundColor Cyan
uv run pytest
if ($LASTEXITCODE -ne 0) { $failed = $true }

Write-Host "=== 4/4 Frontend typecheck + build ===" -ForegroundColor Cyan
Set-Location (Join-Path $root "frontend")
npm run typecheck
if ($LASTEXITCODE -ne 0) { $failed = $true }
npm run build
if ($LASTEXITCODE -ne 0) { $failed = $true }

if ($failed) {
    Write-Host "FAILED: one or more steps reported errors." -ForegroundColor Red
    exit 1
}
Write-Host "All checks passed." -ForegroundColor Green