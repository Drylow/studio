@echo off
title DRYLOW STUDIO // MONTAGE DES VIDEOS D'ACTU
cd /d "%~dp0"
rem Monte sur ce PC les videos d'actu sport preparees dans le cloud (news\...\plan.json) :
rem telecharge les extraits YouTube, monte, envoie sur Gofile, SUPPRIME les clips, renvoie le lien dans git.
set PY=python
if exist "venv\Scripts\python.exe" set PY=venv\Scripts\python.exe
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
where git >nul 2>nul || (echo  // Git est introuvable : installe-le ^(git-scm.com^). & pause & exit /b)
where curl >nul 2>nul || (echo  // curl est introuvable ^(Windows 10+ l'a deja^). & pause & exit /b)
where node >nul 2>nul || where deno >nul 2>nul || echo  // INFO : installe Node.js ^(nodejs.org^) : YouTube en a besoin pour le telechargement.
%PY% -m pip install -q -U yt-dlp imageio-ffmpeg Pillow python-dotenv requests
%PY% production\news.py pc
echo.
echo  // Fini. Les clips telecharges ont ete supprimes.
pause
