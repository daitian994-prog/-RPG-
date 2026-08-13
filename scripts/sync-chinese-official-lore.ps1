$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw "Python was not found. Run the game launcher once to prepare the runtime." }
    $pythonExe = $python.Source
}
Set-Location -LiteralPath $projectRoot
Write-Host "Synchronizing official Simplified Chinese Ionia lore..." -ForegroundColor Cyan
& $pythonExe -m backend.scripts.sync_chinese_official_lore
if ($LASTEXITCODE -ne 0) { throw "Synchronization failed. Check the network and try again." }
Write-Host "Synchronization complete. Refresh the admin knowledge base to view it." -ForegroundColor Green
