# Timelapse 3D de villes (chaîne Keystone Timelapse)

Rendu WebGL (three.js) dans le Chromium de la machine, image par image, puis ffmpeg. Aucune IA, aucun coût.

1. `python timelapse_engine/fetch.py timelapse_engine/cities/<ville>.json work/timelapse/<ville>`
   — bâtiments, routes, parcs, eau (Overture Maps = OpenStreetMap), accès S3 anonyme.
2. Satellite (facultatif, conseillé) : GHSL `GHS_BUILT_S` 1975→2020 (JRC), découpé dans un `.npz`
   (voir `work/timelapse/israel/ghsl/`), chemin dans la clé `ghsl` de la ville.
3. `python timelapse_engine/prep.py timelapse_engine/cities/<ville>.json work/timelapse/<ville>` → `scene.json`.
   Année d'apparition d'un bâtiment : vraie année pour les tours listées (`towers`), sinon le satellite
   (après 1975), sinon la date de fondation documentée du quartier (`zones`). Ces dates de bâtiments
   ordinaires sont une **reconstitution approximative** : le dire sur l'écran de sources.
4. Plan de la vidéo (`plan.json`) : images clés `years` (t → année), `camera` (cible x/z en mètres,
   distance, inclinaison, cap), `eras`, `events` (texte daté), `population`, `labels`, `fade`.
5. Images fixes pour vérifier : `node timelapse_engine/render.mjs --scene … --plan … --stills 0,10,20 --out dir`
   Vidéo : `node timelapse_engine/render.mjs --scene … --plan … --video raw.mp4` (écrit aussi `raw.pops.json`).
   ≈ 1,7-3 s par image en 1080p (WebGL logiciel, 4 cœurs) : 10 min à 30 i/s ≈ 10-12 h.
6. Son : `python timelapse_engine/audio.py raw.mp4 final.mp4 --music work/timelapse/music/<titre>.mp3`
   (musique Kevin MacLeod CC BY 4.0 + « tocs » de bois synthétisés, -14 LUFS).

Repère : x vers l'est, z vers le sud, en mètres depuis `center`. Cap de caméra (`yaw`) : -90 = caméra
à l'ouest (au-dessus de la mer pour Tel-Aviv) qui regarde vers l'est.
