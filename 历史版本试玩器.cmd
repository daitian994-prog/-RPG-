@echo off
chcp 65001 >nul
title Runeterra - History Player
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\history-player.ps1"

