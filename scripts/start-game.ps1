param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$gameUrl = "http://127.0.0.1:8000"
$healthUrl = "$gameUrl/health"
$pidFile = Join-Path $projectRoot ".runeterra-server.json"

function Find-Python {
    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    foreach ($name in @("python", "python3", "py")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    throw "Python was not found. Please install Python 3.10 or newer."
}

function Test-GameServer {
    try {
        $result = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        return $result.status -eq "ok"
    } catch { return $false }
}

function Open-GameBrowser {
    if ($NoBrowser) { return }
    try {
        $browserInfo = [System.Diagnostics.ProcessStartInfo]::new()
        $browserInfo.FileName = $gameUrl
        $browserInfo.UseShellExecute = $true
        [System.Diagnostics.Process]::Start($browserInfo) | Out-Null
    } catch {
        Write-Host "Automatic browser opening failed." -ForegroundColor Yellow
        Write-Host "Open this address manually: $gameUrl" -ForegroundColor Cyan
    }
}

Write-Host ""
Write-Host "  Runeterra: The Nameless" -ForegroundColor DarkYellow
Write-Host "  Starting the game..." -ForegroundColor Gray
Write-Host ""

if (Test-GameServer) {
    Write-Host "The game is already running. Opening it now." -ForegroundColor Green
    Open-GameBrowser
    exit 0
}

$pythonExe = Find-Python
& $pythonExe -c "import fastapi, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "First launch: installing backend dependencies..." -ForegroundColor Yellow
    & $pythonExe -m pip install -r (Join-Path $projectRoot "backend\requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Please check your network." }
}

$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $pythonExe
$startInfo.Arguments = "-m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level warning --no-access-log"
$startInfo.WorkingDirectory = $projectRoot
$startInfo.UseShellExecute = $true
$startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$serverProcess = [System.Diagnostics.Process]::Start($startInfo)

@{
    pid = $serverProcess.Id
    startedAtUtc = $serverProcess.StartTime.ToUniversalTime().ToString("O")
    executable = $pythonExe
} | ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding UTF8

$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 300
    if (Test-GameServer) { $ready = $true; break }
    if ($serverProcess.HasExited) { break }
}

if (-not $ready) {
    if (-not $serverProcess.HasExited) { $serverProcess.Kill() }
    throw "The game server could not start."
}

Write-Host "Ready! Opening the game in your browser." -ForegroundColor Green
Write-Host "Use the one-click launcher again whenever you want to play." -ForegroundColor Gray
Write-Host "Game address: $gameUrl" -ForegroundColor Cyan
Open-GameBrowser
