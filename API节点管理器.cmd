@echo off
chcp 65001 >nul
title Runeterra - AI Node Manager
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\start-admin.ps1"
