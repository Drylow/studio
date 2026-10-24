# Rendu sur le PC (carte graphique) — Keystone Timelapse

Le cloud n'a pas de carte graphique (plus de 24 h de rendu) ; sur un PC de jeu, compter ~30 min à 1 h 30.

Pré-requis (une fois) : Node.js 20+ et ffmpeg dans le PATH (`winget install OpenJS.NodeJS.LTS` et `winget install Gyan.FFmpeg`).

```
cd <dossier du studio>
git pull
cd citylapse
node tools/render.mjs tel-aviv --fps 60
```
Résultat : `citylapse/cities/tel-aviv/renders/tel-aviv.mp4`. Test rapide d'abord : `--fps 30`.
Si le PC rame : `--workers 2`. Ensuite l'envoyer sur Gofile (ou le dossier partagé) et regarder 4-5 images.
Fiche YouTube : `cities/tel-aviv/UPLOAD.md`, miniatures `cities/tel-aviv/thumb_a.jpg` / `thumb_b.jpg`.
