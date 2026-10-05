@echo off
title EDGERUNNERS STUDIO // NIGHT CITY SERVER
cd /d "%~dp0"
set DB_PATH=drylow_studio.db
set FLASK_ENV=development
set COOKIE_SECURE=0
rem Utilise le venv du projet s'il existe (sinon le python du PATH).
set PY=python
if exist "venv\Scripts\python.exe" set PY=venv\Scripts\python.exe
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
rem Dépendances manquantes (2D Videos : voix Edge, ffmpeg embarqué…) → installation auto.
%PY% -c "import flask, dotenv, PIL, edge_tts, imageio_ffmpeg" 2>nul || (
  echo  // Installation des dependances...
  %PY% -m pip install -r requirements.txt
)
rem History Docs : moteur d'animation Remotion (Node.js requis, dependances installees une fois).
where node >nul 2>nul || echo  // INFO : Node.js absent - installe-le (nodejs.org) pour History Docs.
where node >nul 2>nul && if not exist "history_engine\node_modules\remotion" (
  echo  // Installation du moteur d'animation Remotion...
  pushd history_engine & call npm install --no-audit --no-fund & popd
)
if not exist ".env" echo  // ATTENTION : pas de fichier .env — copie .env.example en .env et remplis-le.
echo.
echo  // EDGERUNNERS STUDIO — NEURAL LINK EN COURS...
echo  // http://127.0.0.1:5000
echo  // Ferme cette fenetre pour eteindre le serveur.
echo.
rem Ouvre le navigateur seulement quand le serveur repond (sinon : « connexion refusee »).
start "" /b %PY% open_browser.py
%PY% -c "from app import app; app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False, threaded=True)"
pause
