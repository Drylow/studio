@echo off
title DRYLOW STUDIO // NIGHT CITY SERVER
cd /d "%~dp0"
set DB_PATH=drylow_studio.db
set FLASK_ENV=development
set COOKIE_SECURE=0
echo.
echo  // DRYLOW STUDIO — NEURAL LINK EN COURS...
echo  // http://127.0.0.1:5000
echo  // Ferme cette fenetre pour eteindre le serveur.
echo.
start "" http://127.0.0.1:5000
python -c "from app import app; app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)"
pause
