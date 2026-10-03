@echo off
title DRYLOW // DESINSTALLATION
powershell -NoProfile -Command "Unregister-ScheduledTask -TaskName 'Drylow Actu' -Confirm:$false -ErrorAction SilentlyContinue"
echo  // Montage automatique enleve. Tu peux supprimer ce dossier.
pause
