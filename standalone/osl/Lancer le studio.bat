@echo off
title Oddly Specific Lives Studio
cd /d "%~dp0app"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\lancer.ps1"
echo.
pause
