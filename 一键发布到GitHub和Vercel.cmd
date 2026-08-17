@echo off
chcp 65001 >nul
title 一键发布到 GitHub 和 Vercel
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0scripts\new-version.ps1"
