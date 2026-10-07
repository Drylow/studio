# Compte TikTok « histoire en pixels » (démarré le 7 oct. 2026)

Demande de l'utilisateur (7 oct., soir) : un compte TikTok français **dans le même style visuel
que @archibald.media**, codé de A à Z en HTML et JavaScript, sans vidéo IA. Vidéos de plus d'une
minute, voix ElevenLabs **v4** (via Algrow, crédits existants), zéro dépense. La piste des persos à
tête d'objet (`production/TIKTOK_PLAN.md`) est **en pause**.

## Ce que l'utilisateur a fixé

- **Copie du style d'Archibald**, pas de ses vidéos : fond **noir**, une seule couleur d'accent,
  un **bleu foncé vif** à la place de son rouge (pas de fond coloré : refusé le 7 oct.).
- **Thèmes** : des **personnages historiques** connus (Napoléon, Mozart, Beethoven…) avec un fait
  surprenant, chiffres à l'appui. Les idées « argent caché » et science pure ont été refusées
  (« à dormir debout »).
- **Les deux premières secondes doivent accrocher** : le chiffre choc est à l'écran dès la première image.

## Le style d'Archibald (analysé image par image, 5 vidéos, 1 min 40 à 2 min)

- **Mise en page :**
  - Titre blanc en grotesque très gras, en haut (environ 16 % de la hauteur).
  - Gros chiffre en police pixel juste dessous.
  - Le dessin occupe le milieu ; le bas de l'écran reste vide (légende TikTok).
- **Animations :**
  - Le chiffre arrive en grand puis claque, avec un flash plein écran d'une image.
  - Les compteurs défilent (14 506 → 150 000) et s'éclaircissent en fin de course.
  - Tampons inclinés (« TCHERNOBYL », « 1 AN »).
  - Mots barrés.
  - Grilles de carrés ou d'icônes (une icône = N personnes).
  - Barres en segments.
- **Fond :**
  - Noir avec une grille très légère.
  - Poussières colorées qui montent.
  - Lueur ronde derrière le sujet.
  - Vignette.
- **Dessins :** pixel art tramé en damier, petites boucles (fumée, feu, « ? » qui clignote).
- **Son :** voix seule, sans musique ; quelques bruitages (impact sur les chiffres, grondement au début).
- **Récit :**
  - Accroche chiffrée.
  - « vous pensez sûrement à ça ».
  - « sauf que les chiffres… ».
  - « mais attendez ».
  - La leçon.
  - Une suite annoncée (carte de fin pleine couleur « LA SUITE DEMAIN ▶ »).
  - Sources dans la description.

## Le moteur (`tiktok_engine/`)

- **`engine.js` + `sprites.js` :**
  - Dessinent l'image du temps t sur un canevas 1080×1920, de façon déterministe.
  - Éléments : `text` (préréglages `title`, `big`, `num`, `label`, `sub` ; `*mot*` = bleu), `counter`, `stamp`,
    `sprite`, `icons`, `grid`, `bars`, `flow` (bande de Minard), `line`, `forest`, `dna`, `rect`, `endcard`.
  - Les gros chiffres utilisent Tiny5, avec des rayures façon écran LED.
- **`render.mjs` :**
  - Chromium dessine chaque image et ffmpeg l'encode, sur 3 pages en parallèle (environ 13 images/s ici).
  - `--stills` sort des images fixes pour la relecture.
  - `--serve` lance un lecteur local.
- **`build.py <dossier> --script videos/<nom>/script.json` :**
  - La voix vient d'Algrow (ou de `voice.mp3` déposé), puis les mots sont datés (SRT d'Algrow, sinon Whisper).
  - La `timeline.json` est calée sur les mots, puis viennent les planches `check/sheet_*.jpg`, le mix (bruitages synthétisés, -14 LUFS) et `video.mp4`.
- **Ancres de temps dans un script :**
  - `"at": "mot"` (début du mot dans ce temps fort), `"mot#2"`, `"mot+0.3"`, `"mot>"` (fin du mot).
  - Un nombre veut dire des secondes depuis le début du temps fort.
  - Avec `"keep": true`, la scène précédente continue.

Polices sous licence OFL (fichiers et licences dans `fonts/`).
