@echo off
title DRYLOW // INSTALLATION DU MONTAGE AUTOMATIQUE
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer.ps1"
echo.
pause
