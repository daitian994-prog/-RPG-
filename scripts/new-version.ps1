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
$current = (Get-Content -Raw -LiteralPath (Join-Path $projectRoot "VERSION")).Trim()
Write-Host "Current version: v$current" -ForegroundColor Cyan
$version = (Read-Host "New version (example: 0.2.1)").Trim().TrimStart("v")
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Version must look like 0.2.1" }
if (& $git tag --list "v$version") { throw "Tag v$version already exists." }
$message = (Read-Host "Short update description").Trim()
if (-not $message) { throw "An update description is required." }

$trackedChanges = & $git status --porcelain
if (-not $trackedChanges) { throw "There are no changes to version." }
Set-Content -LiteralPath (Join-Path $projectRoot "VERSION") -Value $version -Encoding ASCII
$packagePath = Join-Path $projectRoot "frontend\package.json"
$package = Get-Content -Raw -LiteralPath $packagePath | ConvertFrom-Json
$package.version = $version
$package | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $packagePath -Encoding UTF8
& $git add -A
if ($LASTEXITCODE -ne 0) { throw "Could not stage changes." }
& $git commit -m "release: v$version - $message"
if ($LASTEXITCODE -ne 0) { throw "Could not create the version commit." }
& $git tag -a "v$version" -m "$message"
if ($LASTEXITCODE -ne 0) { throw "Could not create the version tag." }

$backupDir = Join-Path (Split-Path -Parent $projectRoot) "版本备份"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$bundle = Join-Path $backupDir "runeterra-rpg-v$version.bundle"
& $git bundle create $bundle --all
if ($LASTEXITCODE -ne 0) { throw "Could not create the local backup bundle." }

$remote = & $git remote
if ($remote -contains "origin") {
    & $git push origin HEAD
    if ($LASTEXITCODE -ne 0) { throw "Local version is safe, but GitHub branch push failed." }
    & $git push origin "v$version"
    if ($LASTEXITCODE -ne 0) { throw "Branch was pushed, but the GitHub version tag failed." }
    Write-Host "GitHub backup updated." -ForegroundColor Green
}
Write-Host "Created v$version" -ForegroundColor Green
Write-Host "Local backup: $bundle" -ForegroundColor Cyan
