@echo off
chcp 65001 >nul
title Publish to GitHub and Vercel
cd /d "%~dp0"
if /I not "%~1"=="--dry-run" goto publish
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\new-version.ps1" -DryRun
exit /b %errorlevel%
:publish
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\new-version.ps1"
echo.
pause
