@echo off
chcp 65001 >nul
title Runeterra - Restore Version
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\restore-version.ps1"
