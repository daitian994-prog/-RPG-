@echo off
chcp 65001 >nul
title Runeterra - The Nameless Launcher
cd /d "%~dp0"
if defined RUNETERRA_TEST (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-game.ps1" -NoBrowser
  exit /b %errorlevel%
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-game.ps1"
set LAUNCH_EXIT=%errorlevel%
echo.
if not "%LAUNCH_EXIT%"=="0" echo Launch failed. Please send a screenshot of this window.
if "%LAUNCH_EXIT%"=="0" echo Game is running at http://127.0.0.1:8000
echo You may close this launcher window. Closing it will not stop the game.
pause
exit /b %LAUNCH_EXIT%
