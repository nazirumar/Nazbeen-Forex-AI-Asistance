# Run the Next.js frontend in development on http://localhost:3000
#
# Usage:  .\scripts\dev-frontend.ps1
# Optional: copy frontend\.env.example to frontend\.env.local first to set
# BACKEND_URL / NEXT_PUBLIC_BACKEND_URL (defaults point at http://127.0.0.1:8000).

$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "frontend")

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    npm install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Starting Next.js development server..." -ForegroundColor Cyan
npm run dev