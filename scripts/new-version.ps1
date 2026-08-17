param([switch]$DryRun)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Find-Tool {
    param([string]$Name, [string[]]$BundledPaths)
    foreach ($path in $BundledPaths) {
        if ($path -and (Test-Path -LiteralPath $path)) { return $path }
    }
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw "未找到 $Name。请先安装该工具，或者使用 Codex 打开一次本项目。"
}

function Invoke-Checked {
    param([string]$Title, [scriptblock]$Action)
    Write-Host ""
    Write-Host "[$Title]" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "$Title 失败（退出码 $LASTEXITCODE）。" }
}

function Set-JsonVersion {
    param([string]$Path, [string]$Version)
    $json = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
    $json.version = $Version
    $json | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Invoke-FrontendBuild {
    $vite = Join-Path $projectRoot "frontend\node_modules\.bin\vite.cmd"
    if (-not (Test-Path -LiteralPath $vite)) {
        Write-Host "首次使用：正在安装前端依赖……" -ForegroundColor Yellow
        $oldCI = $env:CI
        $env:CI = "true"
        try { & $pnpm install --frozen-lockfile } finally { $env:CI = $oldCI }
        if ($LASTEXITCODE -ne 0) { throw "安装前端依赖失败，请检查网络。" }
    }
    Push-Location (Join-Path $projectRoot "frontend")
    try { & $vite build } finally { Pop-Location }
}

$git = Find-Tool -Name "git" -BundledPaths @(
    (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe")
)
$python = Find-Tool -Name "python" -BundledPaths @(
    (Join-Path $projectRoot ".venv\Scripts\python.exe"),
    (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
)
$pnpm = Find-Tool -Name "pnpm" -BundledPaths @(
    (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd")
)
$bundledNode = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
if (Test-Path -LiteralPath $bundledNode) { $env:PATH = "$bundledNode;$env:PATH" }

$env:GIT_CONFIG_COUNT = "1"
$env:GIT_CONFIG_KEY_0 = "safe.directory"
$env:GIT_CONFIG_VALUE_0 = $projectRoot.Replace("\", "/")

$branch = (& $git branch --show-current).Trim()
if ($branch -ne "main") { throw "当前分支是 $branch。为避免发布到错误环境，请先切换到 main 分支。" }

$status = @(& $git status --porcelain)
if (-not $DryRun -and -not $status) {
    Write-Host ""
    Write-Host "当前项目已经全部发布，没有新的修改需要上传。" -ForegroundColor Green
    Write-Host "等下次修改过游戏后，再双击本程序即可。" -ForegroundColor Gray
    exit 0
}
$unsafe = @($status | Where-Object {
    ($_ -match '(^|[/\\])\.env($|\.)' -and $_ -notmatch '\.env\.example$') -or
    $_ -match '\.(db|sqlite|sqlite3|log)$' -or
    $_ -match '(^|[/\\])(node_modules|dist|__pycache__|\.pnpm-store)([/\\]|$)' -or
    $_ -match '\.runeterra-server\.json$'
})
if ($unsafe) {
    Write-Host ($unsafe -join [Environment]::NewLine) -ForegroundColor Red
    throw "检测到密钥、数据库、日志、依赖或缓存文件。为保护隐私，发布已停止。"
}

$current = (Get-Content -Raw -LiteralPath (Join-Path $projectRoot "VERSION")).Trim()
if ($current -notmatch '^(\d+)\.(\d+)\.(\d+)$') { throw "VERSION 文件格式不正确。" }
$nextVersion = "$($Matches[1]).$($Matches[2]).$([int]$Matches[3] + 1)"

Write-Host ""
Write-Host "  《无名者：符文之地》一键发布" -ForegroundColor DarkYellow
Write-Host "  当前版本：v$current" -ForegroundColor Gray
Write-Host "  计划版本：v$nextVersion" -ForegroundColor Green

if ($DryRun) {
    Invoke-Checked "后端自动测试" { & $python -m unittest discover -s backend\tests -v }
    Invoke-Checked "前端正式打包" { Invoke-FrontendBuild }
    Invoke-Checked "Git 文件检查" { & $git diff --check }
    Write-Host ""
    Write-Host "演练通过：没有修改版本、提交或上传任何文件。" -ForegroundColor Green
    exit 0
}

$message = (Read-Host "请用一句中文填写本次更新内容").Trim()
if (-not $message) { throw "必须填写更新内容。" }
Write-Host ""
Write-Host "即将执行：测试 → v$nextVersion → 本地备份 → GitHub → Vercel 自动部署" -ForegroundColor Yellow
$answer = (Read-Host "确认发布请输入 Y，取消请直接关闭窗口").Trim()
if ($answer -notin @("Y", "y")) { Write-Host "已取消，没有上传。"; exit 0 }

$managedPaths = @(
    "VERSION", "CHANGELOG.md", "README.md", "package.json",
    "frontend\package.json", "backend\tests\test_game.py"
)
$original = @{}
foreach ($relative in $managedPaths) {
    $path = Join-Path $projectRoot $relative
    if (Test-Path -LiteralPath $path) { $original[$relative] = [System.IO.File]::ReadAllBytes($path) }
}
$commitCreated = $false

try {
    Set-Content -LiteralPath (Join-Path $projectRoot "VERSION") -Value $nextVersion -Encoding ASCII
    Set-JsonVersion -Path (Join-Path $projectRoot "package.json") -Version $nextVersion
    Set-JsonVersion -Path (Join-Path $projectRoot "frontend\package.json") -Version $nextVersion

    $readmePath = Join-Path $projectRoot "README.md"
    $readme = Get-Content -Raw -LiteralPath $readmePath
    $readme = $readme.Replace("当前版本：**v$current**", "当前版本：**v$nextVersion**")
    Set-Content -LiteralPath $readmePath -Value $readme -Encoding UTF8 -NoNewline

    $testPath = Join-Path $projectRoot "backend\tests\test_game.py"
    $testText = Get-Content -Raw -LiteralPath $testPath
    $testText = $testText.Replace('self.assertEqual(game["gameVersion"], "' + $current + '")', 'self.assertEqual(game["gameVersion"], "' + $nextVersion + '")')
    Set-Content -LiteralPath $testPath -Value $testText -Encoding UTF8 -NoNewline

    $changePath = Join-Path $projectRoot "CHANGELOG.md"
    $changeText = Get-Content -Raw -LiteralPath $changePath
    $entry = "## $nextVersion — $(Get-Date -Format 'yyyy-MM-dd')`r`n`r`n- $message`r`n`r`n"
    $changeText = $changeText -replace '^# 更新记录\r?\n\r?\n', "# 更新记录`r`n`r`n$entry"
    Set-Content -LiteralPath $changePath -Value $changeText -Encoding UTF8 -NoNewline

    Invoke-Checked "后端自动测试" { & $python -m unittest discover -s backend\tests -v }
    Invoke-Checked "前端正式打包" { Invoke-FrontendBuild }
    Invoke-Checked "Git 文件检查" { & $git diff --check }
    Invoke-Checked "收集本次修改" { & $git add -A }

    $staged = @(& $git diff --cached --name-only)
    $blocked = @($staged | Where-Object {
        ($_ -match '(^|/)\.env($|\.)' -and $_ -ne '.env.example') -or
        $_ -match '\.(db|sqlite|sqlite3|log)$' -or
        $_ -match '(^|/)(node_modules|dist|__pycache__|\.pnpm-store)(/|$)' -or
        $_ -eq '.runeterra-server.json'
    })
    if ($blocked) { throw "暂存区包含禁止上传的文件：$($blocked -join ', ')" }

    Invoke-Checked "创建版本提交" { & $git commit -m "release: v$nextVersion - $message" }
    $commitCreated = $true
    Invoke-Checked "创建版本标签" { & $git tag -a "v$nextVersion" -m "$message" }

    $backupDir = Join-Path (Split-Path -Parent $projectRoot) "版本备份"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    $bundle = Join-Path $backupDir "runeterra-ai-rpg-v$nextVersion.bundle"
    Invoke-Checked "创建离线备份" { & $git bundle create $bundle --all }

    $remote = @(& $git remote)
    if ($remote -notcontains "origin") { throw "项目尚未连接 GitHub（缺少 origin）。本地版本和备份已经创建。" }
    Invoke-Checked "上传 GitHub 主分支" { & $git push origin main }
    Invoke-Checked "上传 GitHub 版本标签" { & $git push origin "v$nextVersion" }

    Write-Host ""
    Write-Host "发布完成！" -ForegroundColor Green
    Write-Host "版本：v$nextVersion" -ForegroundColor Cyan
    Write-Host "备份：$bundle" -ForegroundColor Cyan
    Write-Host "Vercel 已收到 GitHub 更新，通常会在 1—3 分钟内自动部署。" -ForegroundColor Yellow
    Write-Host "游戏网址：https://rpg-frontend-alpha.vercel.app" -ForegroundColor Cyan
} catch {
    if (-not $commitCreated) {
        foreach ($relative in $original.Keys) {
            [System.IO.File]::WriteAllBytes((Join-Path $projectRoot $relative), $original[$relative])
        }
    }
    throw
}
