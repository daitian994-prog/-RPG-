@echo off
chcp 65001 >nul
title 无名者：符文之地 - 停止服务
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-game.ps1"
timeout /t 2 >nul

