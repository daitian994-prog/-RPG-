@echo off
chcp 65001 >nul
title Runeterra - Stop History Player
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-history-player.ps1"
pause

