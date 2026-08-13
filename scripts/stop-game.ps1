$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot ".runeterra-server.json"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "The game server is not running."
    exit 0
}

try {
    $record = Get-Content -Raw -LiteralPath $pidFile | ConvertFrom-Json
    $process = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
    if ($process) {
        $actualStart = $process.StartTime.ToUniversalTime().ToString("O")
        if ($actualStart -eq $record.startedAtUtc) {
            Stop-Process -Id $record.pid
            Write-Host "The game server was stopped. Your save is safe." -ForegroundColor Green
        } else {
            Write-Host "The saved process record was stale. No other process was stopped." -ForegroundColor Yellow
        }
    } else { Write-Host "The game server was already stopped." }
} finally {
    Remove-Item -LiteralPath $pidFile -ErrorAction SilentlyContinue
}
