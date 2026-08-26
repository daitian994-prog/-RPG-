$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $projectRoot
$recordPath = Join-Path $workspaceRoot "history-player\.history-player-server.json"

if (-not (Test-Path -LiteralPath $recordPath)) {
    Write-Host "No history version is running."
    exit 0
}

try {
    $record = Get-Content -Raw -LiteralPath $recordPath | ConvertFrom-Json
    $process = Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue
    if (-not $process) {
        Write-Host "The history version was already stopped."
        exit 0
    }
    $recordedStart = ([datetime]$record.startedAtUtc).ToUniversalTime()
    $actualStart = $process.StartTime.ToUniversalTime()
    if ([Math]::Abs(($actualStart - $recordedStart).TotalSeconds) -ge 2) {
        Write-Host "The process record was stale. No other process was stopped." -ForegroundColor Yellow
        exit 0
    }
    Stop-Process -Id $process.Id -ErrorAction Stop
    Write-Host "History version $($record.version) stopped. Its isolated saves remain available." -ForegroundColor Green
} finally {
    Remove-Item -LiteralPath $recordPath -ErrorAction SilentlyContinue
}

