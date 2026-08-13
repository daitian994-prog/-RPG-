@echo off
chcp 65001 >nul
title 同步英雄联盟中文官网资料
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\sync-chinese-official-lore.ps1"
echo.
pause
