$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$adminUrl = "http://127.0.0.1:8000/admin/"
$launcher = Join-Path $PSScriptRoot "start-game.ps1"
$errorLog = Join-Path $projectRoot "backend-server.err.log"

Write-Host ""
Write-Host "  Runeterra Database Manager" -ForegroundColor DarkYellow
Write-Host "  Checking the database manager service..." -ForegroundColor Gray
Write-Host ""

try {
    & $launcher -NoBrowser
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "The backend launcher returned exit code $LASTEXITCODE"
    }

    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 3
    $expectedVersion = (Get-Content -Raw -LiteralPath (Join-Path $projectRoot "VERSION")).Trim()
    if ($health.status -ne "ok" -or $health.version -ne $expectedVersion) {
        throw "The service health check did not return the expected version $expectedVersion"
    }

    Start-Process $adminUrl
    Write-Host ""
    Write-Host "  [READY] The database manager is running." -ForegroundColor Green
    Write-Host "  Address: $adminUrl" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  This window stays open. Closing it will not stop the server." -ForegroundColor Gray
    Write-Host "  If no browser appears, copy the address above." -ForegroundColor Gray
} catch {
    Write-Host ""
    Write-Host "  [FAILED] The database manager could not start." -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "  Error log: $errorLog" -ForegroundColor Gray
}

Write-Host ""
Write-Host "  Check complete. You may keep or close this window." -ForegroundColor DarkGray
