@echo off
chcp 65001 >nul
title Runeterra - Create Version
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\new-version.ps1"
