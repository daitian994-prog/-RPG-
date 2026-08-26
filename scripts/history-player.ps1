param(
    [string]$Version,
    [int]$Port = 8100,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $projectRoot
$historyRoot = Join-Path $workspaceRoot "history-player"
$serverRecordPath = Join-Path $historyRoot ".history-player-server.json"

function Get-Git {
    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    $command = Get-Command git -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw "Git was not found."
}

function Get-Python {
    $projectPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $projectPython) { return $projectPython }
    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    foreach ($name in @("python", "python3", "py")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    throw "Python was not found."
}

function Add-NodeToPath {
    $command = Get-Command node -ErrorAction SilentlyContinue
    if ($command) {
        $env:Path = "$(Split-Path -Parent $command.Source);$env:Path"
        return
    }
    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
    if (Test-Path -LiteralPath $bundled) {
        $env:Path = "$(Split-Path -Parent $bundled);$env:Path"
        return
    }
    throw "Node.js was not found."
}

function Get-RecordedProcess {
    if (-not (Test-Path -LiteralPath $serverRecordPath)) { return $null }
    try {
        $record = Get-Content -Raw -LiteralPath $serverRecordPath | ConvertFrom-Json
        $process = Get-Process -Id ([int]$record.pid) -ErrorAction Stop
        $recordedStart = ([datetime]$record.startedAtUtc).ToUniversalTime()
        $actualStart = $process.StartTime.ToUniversalTime()
        if ([Math]::Abs(($actualStart - $recordedStart).TotalSeconds) -lt 2) {
            return @{ process = $process; record = $record }
        }
    } catch { return $null }
    return $null
}

function Stop-PreviousHistoryServer {
    $owned = Get-RecordedProcess
    if ($owned) {
        Write-Host "Stopping history version $($owned.record.version)..." -ForegroundColor Yellow
        Stop-Process -Id $owned.process.Id -ErrorAction Stop
        Wait-Process -Id $owned.process.Id -Timeout 8 -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $serverRecordPath -ErrorAction SilentlyContinue
}

function Select-Version {
    param([string[]]$Tags)
    Write-Host ""
    Write-Host "Available history versions:" -ForegroundColor Cyan
    for ($index = 0; $index -lt $Tags.Count; $index++) {
        Write-Host ("  {0,2}. {1}" -f ($index + 1), $Tags[$index])
    }
    Write-Host ""
    $answer = (Read-Host "Enter a number or version (example: v0.7.0)").Trim()
    if ($answer -match '^\d+$') {
        $selectedIndex = [int]$answer - 1
        if ($selectedIndex -lt 0 -or $selectedIndex -ge $Tags.Count) {
            throw "That version number does not exist."
        }
        return $Tags[$selectedIndex]
    }
    return $answer
}

function Ensure-Junction {
    param([string]$Path, [string]$Target)
    if (Test-Path -LiteralPath $Path) { return }
    if (-not (Test-Path -LiteralPath $Target)) {
        throw "Dependencies are not installed: $Target"
    }
    New-Item -ItemType Junction -Path $Path -Target $Target | Out-Null
}

function Open-HistoryGame {
    param([string]$Url)
    if ($NoBrowser) { return }
    $browserInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $browserInfo.FileName = $Url
    $browserInfo.UseShellExecute = $true
    [System.Diagnostics.Process]::Start($browserInfo) | Out-Null
}

$git = Get-Git
$env:GIT_CONFIG_COUNT = "1"
$env:GIT_CONFIG_KEY_0 = "safe.directory"
$env:GIT_CONFIG_VALUE_0 = $projectRoot.Replace("\", "/")
$tags = @(& $git -C $projectRoot tag --sort=-version:refname | Where-Object { $_ -match '^v\d+\.\d+\.\d+$' })
if (-not $tags) { throw "No version tags were found." }

if (-not $Version) { $Version = Select-Version -Tags $tags }
$Version = $Version.Trim()
if ($Version -notmatch '^v\d+\.\d+\.\d+$' -or $Version -notin $tags) {
    throw "Version $Version does not exist."
}

$commit = (& $git -C $projectRoot rev-list -n 1 $Version).Trim()
if (-not $commit) { throw "Could not read version $Version." }
$shortCommit = $commit.Substring(0, 8)
$snapshotDir = Join-Path $historyRoot "$Version-$shortCommit"
$archivePath = Join-Path $historyRoot "$Version-$shortCommit.zip"
$markerPath = Join-Path $snapshotDir ".history-player.json"

New-Item -ItemType Directory -Force -Path $historyRoot | Out-Null
Stop-PreviousHistoryServer

if (-not (Test-Path -LiteralPath $markerPath)) {
    if (Test-Path -LiteralPath $snapshotDir) {
        throw "The incomplete history directory must be renamed before retrying: $snapshotDir"
    }
    Write-Host "Preparing an isolated copy of $Version..." -ForegroundColor Cyan
    & $git -C $projectRoot archive --format=zip --output=$archivePath $Version
    if ($LASTEXITCODE -ne 0) { throw "Could not export $Version." }
    Expand-Archive -LiteralPath $archivePath -DestinationPath $snapshotDir
    Remove-Item -LiteralPath $archivePath
    @{ version = $Version; commit = $commit; createdAt = (Get-Date).ToString("O") } |
        ConvertTo-Json | Set-Content -LiteralPath $markerPath -Encoding UTF8
}

# Dependencies are shared through directory links. Current project files are not changed.
Ensure-Junction -Path (Join-Path $snapshotDir "node_modules") -Target (Join-Path $projectRoot "node_modules")
Ensure-Junction -Path (Join-Path $snapshotDir "frontend\node_modules") -Target (Join-Path $projectRoot "frontend\node_modules")

# On first preparation, copy the local database. The history version changes only its copy.
$currentDatabase = Join-Path $projectRoot "backend\database\game.db"
$historyDatabase = Join-Path $snapshotDir "backend\database\game.db"
if ((Test-Path -LiteralPath $currentDatabase) -and -not (Test-Path -LiteralPath $historyDatabase)) {
    Copy-Item -LiteralPath $currentDatabase -Destination $historyDatabase
}

$distIndex = Join-Path $snapshotDir "frontend\dist\index.html"
if (-not (Test-Path -LiteralPath $distIndex)) {
    Write-Host "Building this history version for the first launch..." -ForegroundColor Cyan
    Add-NodeToPath
    $vite = Join-Path $projectRoot "frontend\node_modules\.bin\vite.cmd"
    if (-not (Test-Path -LiteralPath $vite)) { throw "Vite is not installed in the current project." }
    Push-Location (Join-Path $snapshotDir "frontend")
    try { & $vite build } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $distIndex)) {
        throw "The history frontend build failed."
    }
}

$healthUrl = "http://127.0.0.1:$Port/health"
try {
    $occupied = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    throw "Port $Port is already used by version $($occupied.version)."
} catch {
    if ($_.Exception.Message -like "Port $Port is already used*") { throw }
}

$python = Get-Python
$stdoutPath = Join-Path $historyRoot "history-server.log"
$stderrPath = Join-Path $historyRoot "history-server.err.log"
$serverProcess = Start-Process -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "$Port", "--log-level", "warning", "--no-access-log") `
    -WorkingDirectory $snapshotDir -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

@{
    pid = $serverProcess.Id
    startedAtUtc = $serverProcess.StartTime.ToUniversalTime().ToString("O")
    executable = $python
    version = $Version
    port = $Port
    snapshotDir = $snapshotDir
} | ConvertTo-Json | Set-Content -LiteralPath $serverRecordPath -Encoding UTF8

$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 300
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        if ($health.status -eq "ok" -and $health.version -eq $Version.TrimStart("v")) {
            $ready = $true
            break
        }
    } catch { }
    if ($serverProcess.HasExited) { break }
}

if (-not $ready) {
    if (-not $serverProcess.HasExited) { Stop-Process -Id $serverProcess.Id -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $serverRecordPath -ErrorAction SilentlyContinue
    $details = if (Test-Path -LiteralPath $stderrPath) { Get-Content -Raw -LiteralPath $stderrPath } else { "No error log." }
    throw "The history version did not start.`n$details"
}

$gameUrl = "http://127.0.0.1:$Port/?history=$Version"
Write-Host ""
Write-Host "History version $Version is running." -ForegroundColor Green
Write-Host "The current development version was not switched or overwritten." -ForegroundColor Green
Write-Host "Game URL: $gameUrl" -ForegroundColor Cyan
Write-Host "Use Stop History Player when finished." -ForegroundColor Gray
Open-HistoryGame -Url $gameUrl
