@echo off
title EDGERUNNERS STUDIO // MONTAGE DES VIDEOS D'ACTU
cd /d "%~dp0"
rem Monte sur ce PC les videos d'actu sport preparees dans le cloud (news\...\plan.json) :
rem telecharge les extraits YouTube, monte, envoie sur Gofile, SUPPRIME les clips, renvoie le lien dans git.
set PYTHONIOENCODING=utf-8
set PY=python
if exist "venv\Scripts\python.exe" set PY=venv\Scripts\python.exe
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
where git >nul 2>nul || (echo  // Git est introuvable : installe-le ^(git-scm.com^). & pause & exit /b)
where curl >nul 2>nul || (echo  // curl est introuvable ^(Windows 10+ l'a deja^). & pause & exit /b)
rem YouTube a besoin d'un moteur JavaScript (deno) : installe tout seul, une fois, dans tools\deno (rien a faire)
if not exist "tools\deno\deno.exe" (
  echo  // Installation automatique du moteur JavaScript pour YouTube ^(une seule fois^)...
  mkdir tools\deno 2>nul
  curl -sSL -o tools\deno\deno.zip https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip
  tar -xf tools\deno\deno.zip -C tools\deno
  del tools\deno\deno.zip 2>nul
)
if exist "tools\deno\deno.exe" set "PATH=%CD%\tools\deno;%PATH%"
%PY% -m pip install -q -U "yt-dlp[default]" imageio-ffmpeg Pillow python-dotenv requests
%PY% production\news.py pc
echo.
echo  // Fini. Les clips telecharges ont ete supprimes.
pause
