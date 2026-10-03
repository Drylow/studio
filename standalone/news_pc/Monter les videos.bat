@echo off
title DRYLOW // MONTAGE DES VIDEOS D'ACTU
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0monter.ps1"
echo.
echo  // Fini. Les clips telecharges ont ete supprimes.
pause
