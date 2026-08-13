$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Get-Git {
    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    $command = Get-Command git -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw "Git was not found."
}

$git = Get-Git
$env:GIT_CONFIG_COUNT = "1"
$env:GIT_CONFIG_KEY_0 = "safe.directory"
$env:GIT_CONFIG_VALUE_0 = $projectRoot.Replace("\", "/")
if (& $git status --porcelain) {
    throw "Uncommitted changes exist. Create a version before restoring."
}
Write-Host "Available versions:" -ForegroundColor Cyan
& $git tag --sort=-version:refname
$version = (Read-Host "Version to restore (example: v0.2.0)").Trim()
if ($version -notmatch '^v\d+\.\d+\.\d+$') { throw "Version must look like v0.2.0" }
if (-not (& $git tag --list $version)) { throw "Version $version does not exist." }
$branch = "restore/$version"
if (& $git branch --list $branch) {
    & $git switch $branch
} else {
    & $git switch -c $branch $version
}
if ($LASTEXITCODE -ne 0) { throw "Could not restore $version." }
Write-Host "Restored $version on branch $branch" -ForegroundColor Green
Write-Host "Database saves and API keys were not changed." -ForegroundColor Cyan
